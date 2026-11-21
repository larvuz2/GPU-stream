/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Which of the two landing pages is shown, as state a component can read.
 *
 * The landing page exists in two takes that share everything but the sections between the
 * navigation and the footer, and a bar at the top switches between them
 * (`landing/CompareBar.tsx`). The choice lives in the address as `?landing=2`, so a link to either
 * take can be handed to someone else, and is remembered in `localStorage`, so the bare address
 * opens on the one last chosen. The address wins where it says: a link is a statement about what
 * its reader should see, and the memory is only a default.
 *
 * The address is kept canonical: the second take always carries its parameter, and the first is
 * the page without one (an explicit `?landing=1` is left as written). It is rewritten in place,
 * with the fragment and every other parameter kept, since switching takes is not a navigation.
 * @module
 */
import { useEffect, useSyncExternalStore } from 'react';

/** A take on the landing page: the first leads with how the product works, the second with what it is for. */
export type LandingOption = 1 | 2;

/** The query parameter that names the take. */
const PARAMETER = 'landing';

/** The `localStorage` key the last choice is kept under. */
const STORAGE_KEY = 'landing-option';

const listeners = new Set<() => void>();

/**
 * The remembered choice, read from storage once: `undefined` until then, `null` when there is
 * none. Held here rather than re-read so that a choice made in another tab does not switch this
 * one's page under its reader.
 */
let remembered: LandingOption | null | undefined;

/**
 * Reads a take from its written form.
 *
 * @param text The parameter's or the stored value.
 * @returns The take, or `null` for anything that does not name one.
 */
function parse(text: string | null): LandingOption | null {
  if (text === '1') {
    return 1;
  }
  return text === '2' ? 2 : null;
}

/**
 * The take the address names.
 *
 * @returns The take, or `null` when the address does not say.
 */
function inAddress(): LandingOption | null {
  return parse(new URLSearchParams(window.location.search).get(PARAMETER));
}

/**
 * The take chosen on an earlier visit.
 *
 * @returns The take, or `null` when none was chosen or storage is not available, as in a private
 *   window that blocks it.
 */
function recall(): LandingOption | null {
  if (remembered === undefined) {
    try {
      remembered = parse(window.localStorage.getItem(STORAGE_KEY));
    } catch {
      remembered = null;
    }
  }
  return remembered;
}

/**
 * The take to show now.
 *
 * @returns The address's take, else the remembered one, else the first.
 */
function current(): LandingOption {
  return inAddress() ?? recall() ?? 1;
}

/**
 * Rewrites the address in place to carry a take, keeping the fragment and the other parameters.
 *
 * @param option The take the address should name; the first is named by leaving the parameter out.
 */
function writeAddress(option: LandingOption): void {
  const parameters = new URLSearchParams(window.location.search);
  if (option === 2) {
    parameters.set(PARAMETER, '2');
  } else {
    parameters.delete(PARAMETER);
  }
  const query = parameters.toString();
  window.history.replaceState(
    window.history.state,
    '',
    `${window.location.pathname}${query === '' ? '' : `?${query}`}${window.location.hash}`,
  );
}

/**
 * Subscribes a listener to changes of the take, this module's and the browser's own when the
 * reader goes back or forward.
 *
 * @param listener Called after the take may have changed.
 * @returns The function that unsubscribes it.
 */
function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener('popstate', listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('popstate', listener);
  };
}

/**
 * Reads which landing page to show and re-renders when that changes.
 *
 * A page opened on the remembered second take has its address completed to say so, which keeps
 * the rule that an address without the parameter is the first take.
 *
 * @returns The take to render.
 */
export function useLandingOption(): LandingOption {
  const option = useSyncExternalStore(subscribe, current);
  useEffect(() => {
    if (option === 2 && inAddress() !== 2) {
      writeAddress(2);
    }
  }, [option]);
  return option;
}

/**
 * Switches the landing page to a take: remembers it, names it in the address, and returns to the
 * top of the page, so that the two are compared from the same place.
 *
 * @param option The take to show.
 */
export function chooseLandingOption(option: LandingOption): void {
  remembered = option;
  try {
    window.localStorage.setItem(STORAGE_KEY, String(option));
  } catch {
    // Without storage the choice still holds for this visit, and the address carries it.
  }
  writeAddress(option);
  for (const listener of listeners) {
    listener();
  }
  // `instant` overrides the page's smooth scrolling: the switch is a cut, not a journey.
  window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
}
