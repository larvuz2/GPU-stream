/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Small hooks the cards' components share.
 * @module
 */
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

/** How long something sent waits to be seen done before it can be sent again. */
const SENDING_TIMEOUT_MS = 12_000;

/**
 * Remembers that the card's answer was just sent.
 *
 * Sending hands the value to the conversation, which sends it and, once the log has the answer,
 * renders the card locked. Between the two the card shows that it was sent and takes no second
 * answer; if it is not locked after a while (the message could not be sent), it is freed again.
 *
 * @returns Whether an answer is on its way, and the function that says one was sent.
 */
export function useSending(): [boolean, () => void] {
  const [sending, setSending] = useState(false);
  useEffect(() => {
    if (!sending) {
      return;
    }
    const timer = window.setTimeout(() => {
      setSending(false);
    }, SENDING_TIMEOUT_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [sending]);
  const send = useCallback(() => {
    setSending(true);
  }, []);
  return [sending, send];
}

/**
 * Follows an element's width.
 *
 * A chart is drawn at the size it is shown, not scaled to it: a drawing scaled down to a phone
 * would shrink its text with it. So the plot is laid out for the measured width and laid out
 * again when that changes.
 *
 * @returns The ref to put on the element, and its content width in CSS pixels, 0 until measured.
 */
export function useWidth<T extends Element>(): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (element === null) {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      const measured = entries[0]?.contentRect.width;
      if (measured !== undefined) {
        setWidth(Math.round(measured));
      }
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, []);
  return [ref, width];
}

/**
 * Follows whether the person asked for less motion.
 *
 * @returns `true` while `prefers-reduced-motion: reduce` matches.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = (): void => {
      setReduced(query.matches);
    };
    query.addEventListener('change', update);
    return () => {
      query.removeEventListener('change', update);
    };
  }, []);
  return reduced;
}
