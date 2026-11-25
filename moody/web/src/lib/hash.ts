/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The URL fragment as state a component can read.
 *
 * The landing page's sign-up dialog is opened by the fragment (`#signup`, `#signin`), so every call
 * to action is a plain link and the dashboard can send a signed-out visitor straight to the
 * dialog. Closing it has to drop the fragment without adding a history entry, and
 * `history.replaceState` fires no `hashchange`, so this module tells its subscribers itself.
 * @module
 */
import { useSyncExternalStore } from 'react';

/** The subscribers to tell of a change made through `history.replaceState`, which fires no event. */
const listeners = new Set<() => void>();

/**
 * Subscribes a listener to fragment changes, the browser's and this module's.
 *
 * @param listener Called after the fragment changes.
 * @returns The function that unsubscribes it.
 */
function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener('hashchange', listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('hashchange', listener);
  };
}

/**
 * Reads the URL fragment and re-renders when it changes.
 *
 * @returns The fragment with its leading `#`, or an empty string when there is none.
 */
export function useHash(): string {
  return useSyncExternalStore(subscribe, () => window.location.hash);
}

/**
 * Replaces the URL fragment in place, without a history entry or a scroll.
 *
 * @param hash The new fragment with its leading `#`, or an empty string to remove it.
 */
export function replaceHash(hash: string): void {
  window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${hash}`);
  for (const listener of listeners) {
    listener();
  }
}
