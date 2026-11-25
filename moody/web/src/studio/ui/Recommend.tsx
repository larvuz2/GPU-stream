/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * How a card shows what the agent recommends: the quiet mark, and the way back to it.
 *
 * Every card that asks for an answer opens on the agent's recommendation ("The agent recommends"
 * in `moody/STUDIO.md`), and the person has to be able to tell which answer that is at any
 * moment, before and after changing it. Two pieces carry that for every input:
 *
 * - {@link Recommended} is the words "(recommended)" after the label of what the agent chose: an
 *   option, a tab, a row, or an input that still holds the recommended value. They are real
 *   text, so a screen reader reads them with the label they follow, and they are small and in
 *   the intelligence's lavender, never the lime of the person's own action.
 * - {@link WayBack} takes the mark's place once the person has changed a value: a button that
 *   names the recommended value and returns to it in one click or one key press. An input that
 *   chooses one option needs none, since the recommended option stays marked and choosing it is
 *   the way back.
 *
 * {@link Advised} picks between the two for an input that sets a value. On a locked card
 * nothing can be returned to, so what was recommended is said as words. On a card that sends no
 * answer back there is no recommendation, and all three render nothing.
 * @module
 */
import { RotateCcw } from 'lucide-react';
import type { InputBinding } from './view';

/** Props of {@link Recommended}. */
interface RecommendedProps {
  /** The recommended value in words, where the mark does not sit beside it already. */
  words?: string;
}

/**
 * Renders the mark of what the agent recommends.
 *
 * @param props The component's props.
 * @returns The words "(recommended)", after the value where one is given.
 */
export function Recommended({ words }: RecommendedProps) {
  return <span className="ui-recommended">{words === undefined ? '(recommended)' : `${words} (recommended)`}</span>;
}

/** Props of {@link WayBack}. */
interface WayBackProps {
  /** The input to return, for its name. */
  input: InputBinding;
  /** What going back sets, as the person reads it; left out for a value too long to say, such as an order. */
  words?: string;
  /** What kind of thing a value too long to say is, such as "order"; without it the button says only where it leads. */
  whole?: string;
  /** Goes back, where that is not the whole input returning to its recommendation. */
  onBack?: () => void;
}

/**
 * Renders the way back to what the agent recommends for one input.
 *
 * @param props The component's props.
 * @returns The button.
 */
export function WayBack({ input, words, whole, onBack }: WayBackProps) {
  const said =
    words !== undefined
      ? `${words} (recommended)`
      : whole !== undefined
        ? `Back to the recommended ${whole}`
        : 'Back to recommended';
  return (
    <button
      type="button"
      className="ui-wayback"
      // The name carries the words in view, so it can be asked for by what is read.
      aria-label={words === undefined ? `${input.label}: ${said.toLowerCase()}` : `${input.label}: back to ${said}`}
      onClick={onBack ?? input.reset}
    >
      <RotateCcw className="size-3 flex-none" aria-hidden="true" />
      <span>{said}</span>
    </button>
  );
}

/** Props of {@link Advised}. */
interface AdvisedProps {
  /** The input. */
  input: InputBinding;
  /**
   * What kind of thing the value is, such as "order", for a value too long to name on the way
   * back. The mark then says which thing is recommended ("This order"), since the label it follows
   * may be an instruction rather than a name, and the way back says where it leads.
   */
  whole?: string;
  /** Whether the value in view already reads as the recommendation, so the mark needs no words of its own. */
  shown?: boolean;
}

/**
 * Renders, for an input that sets a value, the mark while it holds what the agent recommends and
 * the way back once it does not.
 *
 * @param props The component's props.
 * @returns The mark, the way back, what was recommended on a locked card, or nothing on a card that recommends nothing.
 */
export function Advised({ input, whole, shown = true }: AdvisedProps) {
  const advice = input.advice;
  if (advice === null) {
    return null;
  }
  if (advice.kept) {
    return <Recommended words={whole !== undefined ? `This ${whole}` : shown ? undefined : advice.words} />;
  }
  if (input.frozen) {
    return whole === undefined ? <Recommended words={advice.words} /> : null;
  }
  return <WayBack input={input} words={whole === undefined ? advice.words : undefined} whole={whole} />;
}
