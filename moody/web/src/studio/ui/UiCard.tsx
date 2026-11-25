/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * An interactive card the agent put in the conversation (`ui` in `moody/STUDIO.md`), as a
 * stand-in: it names the card and, where the card has something to send back, offers its lock-in
 * button, which sends no state of its own.
 *
 * The conversation (`Conversation.tsx`) renders every `ui` entry through {@link UiCard} with
 * these props, and owns what happens on a lock: the value is sent as the person's next message,
 * and the card is locked with it once the log holds that message.
 * @module
 */
import type { UiData } from '../../lib/api';

/** Props of {@link UiCard}. */
export interface UiCardProps {
  /** The card, as its event describes it. */
  ui: UiData;
  /** What the person locked in, or `null` while the card is open. */
  locked: { value: unknown } | null;
  /** Whether the card can be answered now. */
  live: boolean;
  /** Locks the card in with its state. */
  onSubmit: (value: unknown) => void;
}

/**
 * Renders the stand-in for an interactive card.
 *
 * @param props The component's props.
 * @returns The card.
 */
export function UiCard({ ui, locked, live, onSubmit }: UiCardProps) {
  return (
    <section className="ai-card rounded-2xl p-4" aria-label={ui.title}>
      <p className="ai-label">Interactive card</p>
      <p className="mt-2 font-medium text-fg">{ui.title}</p>
      {ui.submit === null ? null : (
        <button
          type="button"
          className="btn btn-primary btn-sm mt-3"
          disabled={!live || locked !== null}
          onClick={() => {
            onSubmit(null);
          }}
        >
          {locked === null ? ui.submit : 'Locked in'}
        </button>
      )}
    </section>
  );
}
