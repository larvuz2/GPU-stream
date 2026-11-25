/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What a card's components share: its values, its files, whether it can still change, and what
 * the agent recommends.
 *
 * A card is one piece of state, `{id: value}`, held by `UiCard.tsx`. Every component reads it
 * here rather than through its props, so an input and the picture that follows it need no
 * wiring between them: the slider writes `warmth`, and the image whose `adjust` names `"$warmth"`
 * reads it on the same render.
 *
 * A card that sends an answer back also carries the agent's recommendation for each input
 * ({@link Advice}), which is what an input marks, compares itself with, and returns to. A card
 * with nothing to send back decides nothing, so it carries none and its inputs mark nothing.
 * @module
 */
import { createContext, useContext } from 'react';
import type { UiMedia, UiState } from './tree';

/** What the agent recommends for one input. */
export interface Advice {
  /** The recommended value. */
  value: unknown;
  /** The recommended value as a person reads it. */
  words: string;
  /** Whether the input holds it now. */
  kept: boolean;
}

/**
 * Whether a choice is what the agent recommends, or one of what it recommends.
 *
 * @param advice The recommendation of the input the choice belongs to.
 * @param value The choice's value.
 * @returns `true` for the recommended option, and for each of them where several are.
 */
export function isRecommended(advice: Advice | null, value: unknown): boolean {
  if (advice === null) {
    return false;
  }
  return Array.isArray(advice.value) ? advice.value.includes(value) : advice.value === value;
}

/** A card, as its components see it. */
export interface Card {
  /** The card's values, by input id. */
  state: UiState;
  /** Sets one input's value. A locked card ignores it. */
  set: (id: string, value: unknown) => void;
  /** Finds one of the card's files by the name a component gave. */
  media: (name: unknown) => UiMedia | null;
  /** Whether the card is locked in: its inputs show what was chosen and no longer change. */
  frozen: boolean;
  /** One input's value in words, for a text that shows it. */
  words: (id: string) => string;
  /** What the agent recommends for one input, or `null` on a card that sends no answer back. */
  advice: (id: string) => Advice | null;
  /** Returns one input to what the agent recommends. A locked card ignores it. */
  reset: (id: string) => void;
  /** A prefix that makes element ids unique to this card. */
  uid: string;
}

/** The card a component is drawn in. */
export const CardContext = createContext<Card | null>(null);

/**
 * Reads the card a component is drawn in.
 *
 * @returns The card.
 * @throws When called outside a card, which is a mistake in the tree of components.
 */
export function useCard(): Card {
  const card = useContext(CardContext);
  if (card === null) {
    throw new Error('A card component was rendered outside a card.');
  }
  return card;
}
