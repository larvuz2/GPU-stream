/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Small hooks the studio's layout is built from: a preference remembered in this browser, a media
 * query, and a clock.
 *
 * A preference (a pane's width, a panel folded away) is the viewer's own convenience, so it lives
 * in `localStorage` and nowhere else. Storage can be refused (a private window, blocked site
 * data), so every read and write is guarded and a refusal leaves the default in place.
 * @module
 */
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import type { Guard } from '../lib/narrow';

/** The prefix of every key the studio stores, so its preferences are told apart from others'. */
const PREFIX = 'moody.studio.';

/**
 * Reads a stored preference.
 *
 * @param key The preference's name, without the studio's prefix.
 * @param guard Checks the stored value, which another version of the page may have written.
 * @returns The value, or `undefined` when none is stored, it is unreadable, or storage is refused.
 */
export function readPreference<T>(key: string, guard: Guard<T>): T | undefined {
  try {
    const stored = window.localStorage.getItem(PREFIX + key);
    if (stored === null) {
      return undefined;
    }
    const parsed: unknown = JSON.parse(stored);
    return guard(parsed) ? parsed : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Stores a preference, or removes it.
 *
 * @param key The preference's name, without the studio's prefix.
 * @param value The value, or `undefined` to remove it.
 */
export function writePreference(key: string, value: unknown): void {
  try {
    if (value === undefined) {
      window.localStorage.removeItem(PREFIX + key);
    } else {
      window.localStorage.setItem(PREFIX + key, JSON.stringify(value));
    }
  } catch {
    // Storage refused: the preference lasts as long as the page.
  }
}

/**
 * State that this browser remembers across visits.
 *
 * @param key The preference's name, without the studio's prefix.
 * @param initial The value when none is stored.
 * @param guard Checks a stored value before it is used.
 * @returns The value and the function that replaces it.
 */
export function usePreference<T>(key: string, initial: T, guard: Guard<T>): [T, (next: T) => void] {
  const [value, setValue] = useState<T>(() => readPreference(key, guard) ?? initial);
  const update = useCallback(
    (next: T): void => {
      setValue(next);
      writePreference(key, next);
    },
    [key],
  );
  return [value, update];
}

/**
 * Follows a media query.
 *
 * @param query The query, such as `(max-width: 1023px)`.
 * @returns Whether it matches now.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (listener: () => void): (() => void) => {
      const list = window.matchMedia(query);
      list.addEventListener('change', listener);
      return () => {
        list.removeEventListener('change', listener);
      };
    },
    [query],
  );
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches);
}

/**
 * Follows the clock while something on screen depends on it.
 *
 * @param ticking Whether to keep updating; a view that shows no running time does not re-render.
 * @param everyMs How often to update.
 * @returns The current time in milliseconds, at most `everyMs` old while ticking.
 */
export function useNow(ticking: boolean, everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!ticking) {
      return;
    }
    const update = (): void => {
      setNow(Date.now());
    };
    const first = window.setTimeout(update, 0);
    const interval = window.setInterval(update, everyMs);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(interval);
    };
  }, [ticking, everyMs]);
  return now;
}
