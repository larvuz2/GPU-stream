/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * How the studio presents what the catalog and the control plane name: a discipline's name, an
 * app's status, the plan's progress, a limit of a turn, a library tag, how long ago something
 * happened, and opening a stream in a new tab.
 * @module
 */
import type { PlanItem, TurnLimit } from '../lib/api';
import { brand, findDiscipline, isOwnLicense, ownLicenseLabel, type CatalogApp } from '../lib/catalog';
import { creditCount, usd } from '../lib/format';

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

/**
 * A limit of a turn, as a person reads it.
 *
 * @param limit Which limit it is.
 * @param value Its value.
 * @returns Text such as `$15` or `200 steps`.
 */
export function limitText(limit: TurnLimit, value: number): string {
  return limit === 'budget' ? usd(value) : `${creditCount(value)} ${value === 1 ? 'step' : 'steps'}`;
}

/**
 * Normalizes a tag as prompts name it: lowercase, without the `@`, words joined by hyphens.
 *
 * @param text The tag as typed.
 * @returns The tag.
 */
export function normalizeTag(text: string): string {
  return text
    .trim()
    .replace(/^@+/, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}_-]+/gu, '-')
    .replace(/^-+|-+$/g, '');
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
