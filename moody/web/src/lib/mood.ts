/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * How a page tells its wordmark what it feels: a part of the page that has something to react to
 * (the prompt box taking the focus, a pointer over its button) calls {@link express}, and every
 * wordmark mounted as reactive (`MoodyLogo` in `components/Moody.tsx`) plays that expression.
 *
 * The two never import each other, so the wordmark stays in the navigation and the form in the
 * hero with nothing passed between them through the page.
 * @module
 */

/** Receives the index of the expression to play (`lib/moody.ts`, `ANIMATION`). */
type Listener = (expression: number) => void;

const listeners = new Set<Listener>();

/**
 * Asks every reactive wordmark to play an expression.
 *
 * @param expression The expression's index, 0 to 4.
 */
export function express(expression: number): void {
  for (const listener of listeners) {
    listener(expression);
  }
}

/**
 * Subscribes to the expressions the page asks for.
 *
 * @param listener Called with each expression's index.
 * @returns A function that unsubscribes.
 */
export function onExpress(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
