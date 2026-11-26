/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The tabs of Settings, and the address that names the one that is open.
 *
 * Five tabs are built here: Profile, Billing, Agent, Connections, and API keys. The others come
 * from the catalog: a setting names the tab it sits on (`Setting.tab`, the tab's name as shown),
 * and a name that is none of the five is a tab of its own, between Agent and Connections in the
 * catalog's order. So a setting added to the catalog shows on its tab, and a tab it is the first
 * on appears with it, with no code here to write.
 *
 * A tab is left out where it would hold nothing real: Agent on a control plane with neither a
 * turn's limits nor a setting for it, the catalog's tabs on one that keeps no settings, and all
 * but Profile where no control plane is connected.
 *
 * The open tab is in the address (`?settings=<tab>`), so a link or a reload opens Settings on it,
 * and connecting an account elsewhere comes back to the tab it left from.
 * @module
 */
import type { TurnLimit } from '../../lib/api';
import { catalog, type Setting } from '../../lib/catalog';

/** A tab of Settings. */
export interface SettingsTab {
  /** The tab's name in the address. */
  id: string;
  /** The tab's name as shown, which is what a catalog setting names it by. */
  name: string;
}

/** Who the person is: their name, their email, signing out. */
export const PROFILE: SettingsTab = { id: 'profile', name: 'Profile' };
/** The credit balance, what a credit is worth, and buying more. */
export const BILLING: SettingsTab = { id: 'billing', name: 'Billing' };
/** What one turn of the agent may spend and take. */
export const AGENT: SettingsTab = { id: 'agent', name: 'Agent' };
/** The accounts the studio is connected to. */
export const CONNECTIONS: SettingsTab = { id: 'connections', name: 'Connections' };
/** The keys other programs reach the account with. */
export const KEYS: SettingsTab = { id: 'api-keys', name: 'API keys' };

/** The tabs built here, which a catalog setting may also sit on. */
const BUILT: readonly SettingsTab[] = [PROFILE, BILLING, AGENT, CONNECTIONS, KEYS];

/** What Settings is opened on. */
export interface SettingsTarget {
  /** The tab, by its name in the address; one that does not exist opens the first tab. */
  tab: string;
  /** The limit of a turn whose field takes the focus, for a turn that just stopped at it. */
  limit?: TurnLimit;
}

/**
 * The catalog's settings that sit on a tab.
 *
 * @param tab The tab.
 * @returns Its settings, in the catalog's order.
 */
export function settingsOn(tab: SettingsTab): Setting[] {
  return catalog.settings.filter((setting) => setting.tab === tab.name);
}

/**
 * Makes a tab's name in the address from its name as shown.
 *
 * @param name The name, such as "Video editing".
 * @returns The name in lowercase with hyphens between its words, such as `video-editing`.
 */
function slug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

/** What decides which tabs there are. */
interface TabsFor {
  /** Whether a control plane is connected. */
  connected: boolean;
  /** Whether it reports a turn's limits. */
  limits: boolean;
  /** Whether it keeps the catalog's settings. */
  settings: boolean;
}

/**
 * The tabs of Settings, in the order they are shown.
 *
 * @param has What the control plane offers.
 * @returns The tabs.
 */
export function settingsTabs(has: TabsFor): SettingsTab[] {
  if (!has.connected) {
    return [PROFILE];
  }
  const named = has.settings ? [...new Set(catalog.settings.map((setting) => setting.tab))] : [];
  const fromCatalog = named
    .filter((name) => !BUILT.some((tab) => tab.name === name))
    .map((name) => ({ id: slug(name), name }));
  const agent = has.limits || named.includes(AGENT.name) ? [AGENT] : [];
  return [PROFILE, BILLING, ...agent, ...fromCatalog, CONNECTIONS, KEYS];
}

/** The query parameter that names the open tab of Settings. */
const PARAMETER = 'settings';

/**
 * Reads the tab of Settings the address asks for.
 *
 * @returns What to open Settings on, or `null` where the address does not ask for it.
 */
export function targetInAddress(): SettingsTarget | null {
  const tab = new URLSearchParams(window.location.search).get(PARAMETER);
  return tab === null ? null : { tab };
}

/**
 * Writes the open tab of Settings to the address, or drops it as Settings closes.
 *
 * @param tab The tab's name in the address, or `null` for Settings closed.
 */
export function writeTabToAddress(tab: string | null): void {
  const address = new URL(window.location.href);
  if (address.searchParams.get(PARAMETER) === tab) {
    return;
  }
  if (tab === null) {
    address.searchParams.delete(PARAMETER);
  } else {
    address.searchParams.set(PARAMETER, tab);
  }
  window.history.replaceState(null, '', address);
}
