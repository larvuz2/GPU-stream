/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The foot of an interactive card: the lock-in button, or what was locked in.
 *
 * The button is the one Electric Lime thing in a card, because locking in is the one thing the
 * person does with it that reaches the agent. Beside it is always a line that says where the
 * card stands: that it is as the agent recommends, what the person changed, what still has to
 * be chosen first, or why the card cannot be answered now. A card that cannot be answered is
 * said to be so in words, not only by a dimmed button.
 *
 * A card opens on the agent's recommendation, so while nothing was changed the line says that
 * the card is the recommendation and that locking it in agrees: one press is a yes. Once
 * something differs, the line names what, and a quiet button beside it returns the whole card to
 * the recommendation in one press, whatever the inputs offer of their own. The line is a status
 * region, so the same is told to someone who does not see it change. A locked card says whether
 * the recommendation was kept, or what was changed.
 *
 * Pressing the button hands the value to the conversation, which sends it and, once the log has
 * the answer, renders the card locked. Between the two the button shows that it was pressed and
 * takes no second press; if the card is not locked after a while (the message could not be
 * sent), the button is freed again.
 * @module
 */
import { useEffect, useState } from 'react';
import { Check, Lock, RotateCcw } from 'lucide-react';
import { brand } from '../../lib/catalog';
import type { AnswerLine } from './answer';

/** How long a pressed lock-in button waits for the card to be locked before it can be pressed again. */
const SENDING_TIMEOUT_MS = 12_000;

/** How many of a locked card's values are listed before the rest are counted. */
const SUMMARY_LINES = 8;

/** How many changed inputs the line names before it counts the rest. */
const NAMED_CHANGES = 3;

/** How a card stands against what the agent recommends. */
export interface Standing {
  /** Whether it holds the recommendation. */
  kept: boolean;
  /** What differs, by name, where the differences have names. */
  changed: string[];
}

/** Props of {@link LockBar}. */
interface LockBarProps {
  /** The lock-in button's label, or `null` for a card with nothing to send back. */
  label: string | null;
  /** Whether the card is locked in. */
  locked: boolean;
  /** Whether the card can be answered now. */
  live: boolean;
  /** Why it cannot be locked in yet, as a sentence, or `null` where nothing holds it. */
  blocked: string | null;
  /** What was locked in, a line per value. */
  summary: AnswerLine[];
  /** How the card stands against the agent's recommendation, or `null` where that is not known. */
  advice: Standing | null;
  /** Returns the whole card to the recommendation. */
  onReturn: () => void;
  /** Locks the card in. */
  onLock: () => void;
}

/**
 * Writes what was changed as the end of a sentence.
 *
 * The names are the inputs' labels, which the agent wrote and which may be questions, so they
 * follow a colon as a plain list rather than being worked into the sentence's grammar, and the
 * sentence takes a full stop only where the last name does not end it already.
 *
 * @param names What differs from the recommendation, by name.
 * @returns The first few names, the rest counted.
 */
function listed(names: string[]): string {
  const rest = names.length - NAMED_CHANGES;
  const list = (rest > 0 ? [...names.slice(0, NAMED_CHANGES), `and ${rest} more`] : names).join(', ');
  return /[.?!…]$/.test(list) ? list : `${list}.`;
}

/**
 * Renders the foot of a card.
 *
 * @param props The component's props.
 * @returns The bar, or nothing for a card with nothing to send back.
 */
export function LockBar({ label, locked, live, blocked, summary, advice, onReturn, onLock }: LockBarProps) {
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

  if (label === null) {
    return null;
  }
  const departed = advice !== null && !advice.kept;
  const standing = advice === null ? undefined : departed ? 'changed' : 'kept';
  if (locked) {
    const shown = summary.slice(0, SUMMARY_LINES);
    return (
      <footer className="ui-lockbar" data-locked="true" data-advice={standing}>
        <p className="ui-locked-line">
          <Lock className="size-3.5 flex-none" aria-hidden="true" />
          <span>
            {advice === null
              ? 'You locked this in.'
              : advice.kept
                ? `You locked this in as ${brand} recommended.`
                : advice.changed.length === 0
                  ? 'You locked this in with your own answer.'
                  : `You locked this in with changes to: ${listed(advice.changed)}`}
          </span>
        </p>
        {shown.length === 0 ? null : (
          <dl className="ui-summary">
            {shown.map((line) => (
              <div key={line.id} className="ui-summary-line">
                <dt>{line.label}</dt>
                <dd>{line.words}</dd>
              </div>
            ))}
            {summary.length > shown.length ? (
              <div className="ui-summary-line">
                <dt>and</dt>
                <dd>{summary.length - shown.length} more</dd>
              </div>
            ) : null}
          </dl>
        )}
      </footer>
    );
  }
  const stands =
    advice === null
      ? 'Nothing is sent until you lock it in.'
      : advice.kept
        ? `This is what ${brand} recommends. Lock it in to agree, or change anything first.`
        : `${
            advice.changed.length === 0
              ? `You changed this from what ${brand} recommends.`
              : `You changed: ${listed(advice.changed)}`
          } Nothing is sent until you lock it in.`;
  const hint = !live
    ? `You can explore this, but it cannot be locked in right now: ${brand} is working, or the conversation has moved past it.`
    : (blocked ?? stands);
  return (
    <footer className="ui-lockbar" data-advice={standing}>
      <button
        type="button"
        className="btn btn-primary btn-sm"
        disabled={!live || blocked !== null || sending}
        onClick={() => {
          setSending(true);
          onLock();
        }}
      >
        {sending ? (
          <span className="spinner size-3.5" aria-hidden="true" />
        ) : (
          <Check className="size-4" aria-hidden="true" />
        )}
        {label}
      </button>
      <p className="ui-hint" role="status">
        {hint}
      </p>
      {departed ? (
        <button type="button" className="ui-wayback" onClick={onReturn}>
          <RotateCcw className="size-3 flex-none" aria-hidden="true" />
          <span>Back to the recommendation</span>
        </button>
      ) : null}
    </footer>
  );
}
