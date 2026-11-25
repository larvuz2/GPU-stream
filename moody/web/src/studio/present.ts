/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * How the studio presents what the catalog and the control plane name: a discipline's name, an
 * app's status, the plan's progress, how long ago something happened, what an interactive card
 * was locked in with, and opening a stream in a new tab.
 * @module
 */
import type { PlanItem } from '../lib/api';
import { brand, findDiscipline, isOwnLicense, ownLicenseLabel, type CatalogApp } from '../lib/catalog';

/**
 * The name of a discipline.
 *
 * @param id The discipline's identifier.
 * @returns Its catalog name, or the identifier for one the catalog no longer lists.
 */
export function disciplineName(id: string): string {
  return findDiscipline(id)?.name ?? id;
}

/**
 * Whether an app can be started as an engine: an available one; a team one, which the control
 * plane admits for the team's accounts and refuses for anyone else; or one with a part on the
 * person's own license, which starts for anyone and brings that part once the license is linked.
 *
 * @param app The catalog app.
 * @returns `true` for an app that can be asked for.
 */
export function canStart(app: CatalogApp): boolean {
  return app.status === 'available' || app.status === 'team' || isOwnLicense(app);
}

/**
 * What an app's status says beside its name.
 *
 * @param app The catalog app.
 * @returns A word or two, or an empty string for an available app.
 */
export function appStatusLabel(app: CatalogApp): string {
  switch (app.status) {
    case 'available':
      return '';
    case 'byol':
      return ownLicenseLabel(app);
    case 'team':
      return 'Team';
    case 'next':
      return 'Coming next';
    default:
      return 'Soon';
  }
}

/**
 * The plan's progress, for the Plan panel's header.
 *
 * @param items The plan.
 * @returns Text such as `3 of 7`, or `undefined` for an empty plan.
 */
export function planProgress(items: PlanItem[]): string | undefined {
  return items.length === 0 ? undefined : `${items.filter((item) => item.status === 'done').length} of ${items.length}`;
}

/** How many of a locked card's values its line names, and how long the line may get. */
const SUMMARY_FIELDS = 4;
const SUMMARY_LENGTH = 120;

/**
 * Writes one value of a card's state, where it is short enough to say.
 *
 * @param value The value.
 * @returns Text for a string, a number, a boolean, or a list of them; `null` for anything else.
 */
function plainValue(value: unknown): string | null {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    const parts = value.map(plainValue);
    return parts.every((part) => part !== null) ? parts.join(', ') : null;
  }
  return null;
}

/**
 * Says what an interactive card was locked in with, in a line a person can read: a plain value as
 * itself, a record as its first few plain fields. The state's shape is the card's own, so
 * anything deeper is left to the card, which shows it locked.
 *
 * @param value The card's state.
 * @returns The line, or an empty string for a state with nothing plain to say.
 */
export function valueSummary(value: unknown): string {
  const plain = plainValue(value);
  let text = plain ?? '';
  if (plain === null && typeof value === 'object' && value !== null) {
    text = Object.entries(value)
      .flatMap(([key, field]) => {
        const said = plainValue(field);
        return said === null || said === '' ? [] : [`${key.replaceAll('_', ' ')}: ${said}`];
      })
      .slice(0, SUMMARY_FIELDS)
      .join(' · ');
  }
  return text.length > SUMMARY_LENGTH ? `${text.slice(0, SUMMARY_LENGTH).trimEnd()}…` : text;
}

/**
 * Words the message that locks an interactive card in. The card's state travels beside it as
 * data; this is what a reader of the log sees.
 *
 * @param title The card's title.
 * @param value The card's state.
 * @returns The message.
 */
export function lockText(title: string, value: unknown): string {
  const summary = valueSummary(value);
  return summary === '' ? `Locked in “${title}”.` : `Locked in “${title}”: ${summary}`;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const monthDay = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' });

/**
 * Writes how long ago a moment was, as briefly as a list row allows.
 *
 * @param iso An ISO 8601 timestamp.
 * @param now The current time, in milliseconds since the epoch.
 * @returns Text such as `now`, `5m`, `3h`, `2d`, or `Nov 21`.
 */
export function ago(iso: string, now: number): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) {
    return '';
  }
  const elapsed = Math.max(0, now - then);
  if (elapsed < MINUTE) {
    return 'now';
  }
  if (elapsed < HOUR) {
    return `${Math.floor(elapsed / MINUTE)}m`;
  }
  if (elapsed < DAY) {
    return `${Math.floor(elapsed / HOUR)}h`;
  }
  return elapsed < 7 * DAY ? `${Math.floor(elapsed / DAY)}d` : monthDay.format(then);
}

/**
 * Opens a stream in a new tab from a link minted on demand.
 *
 * The tab is opened before the link is asked for, while the click still counts as the person's
 * gesture: a tab opened after the request returns is a pop-up to the browser, and is blocked.
 *
 * @param mint Mints the link.
 * @param appName The app's name, for the waiting tab's title.
 * @returns The link when the browser refused the tab, for the person to follow; `null` otherwise.
 * @throws ApiError When the link could not be minted; the waiting tab is closed first.
 */
export async function openStreamTab(mint: () => Promise<string>, appName: string): Promise<string | null> {
  const tab = window.open('', '_blank');
  if (tab !== null) {
    tab.document.title = `Opening ${appName} — ${brand}`;
  }
  try {
    const url = await mint();
    if (tab === null) {
      return url;
    }
    tab.opener = null;
    tab.location.replace(url);
    return null;
  } catch (failure) {
    tab?.close();
    throw failure;
  }
}
