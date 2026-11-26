/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What a card's components share: its values, its files, and whether it can still change.
 *
 * A card is one piece of state, `{id: value}`, held by `UiCard.tsx`. Every component reads it
 * here rather than through its props, so an input and the picture that follows it need no
 * wiring between them: the slider writes `warmth`, and the image whose `adjust` names `"$warmth"`
 * reads it on the same render.
 * @module
 */
import { createContext, useContext } from 'react';
import type { UiMedia, UiState } from './tree';

/** A file the person gave, as the project's library holds it: its entry, and where the page reads it. */
export interface Uploaded {
  /** The entry's tag. */
  tag: string;
  /** The file's name. */
  name: string;
  /** What the file is: `image`, `video`, `audio`, or `file`. */
  kind: string;
  /** An address the page can show or play it from. */
  url: string;
}

/**
 * Takes a file from the person into the project's library.
 *
 * @param file The file.
 * @param into Where in the library it goes: a section's name, or `null` for the library's own choice.
 * @returns The entry it became. A file that could not be taken rejects with the reason, in words the person can read.
 */
export type UploadFile = (file: File, into: { section: string | null }) => Promise<Uploaded>;

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
  /**
   * Whether choosing locks the card at once: it has no lock-in button, and its one input shows its
   * choices as buttons to press rather than as a selection to move through.
   */
  instant: boolean;
  /** Takes a file from the person, or `null` where the page showing the card has no way to. */
  upload: UploadFile | null;
  /** The card's sounds, so that starting one pauses the others. */
  sounds: Set<HTMLAudioElement>;
  /** One input's value in words, for a text that shows it. */
  words: (id: string) => string;
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
