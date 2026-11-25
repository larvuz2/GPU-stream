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
 * card stands: that nothing is sent until it is pressed, what still has to be chosen first, or
 * why the card cannot be answered now. A card that cannot be answered is said to be so in words,
 * not only by a dimmed button.
 *
 * Pressing the button hands the value to the conversation, which sends it and, once the log has
 * the answer, renders the card locked. Between the two the button shows that it was pressed and
 * takes no second press; if the card is not locked after a while (the message could not be
 * sent), the button is freed again.
 * @module
 */
import { useEffect, useState } from 'react';
import { Check, Lock } from 'lucide-react';
import { brand } from '../../lib/catalog';
import type { AnswerLine } from './answer';

/** How long a pressed lock-in button waits for the card to be locked before it can be pressed again. */
const SENDING_TIMEOUT_MS = 12_000;

/** How many of a locked card's values are listed before the rest are counted. */
const SUMMARY_LINES = 8;

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
  /** Locks the card in. */
  onLock: () => void;
}

/**
 * Renders the foot of a card.
 *
 * @param props The component's props.
 * @returns The bar, or nothing for a card with nothing to send back.
 */
export function LockBar({ label, locked, live, blocked, summary, onLock }: LockBarProps) {
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
  if (locked) {
    const shown = summary.slice(0, SUMMARY_LINES);
    return (
      <footer className="ui-lockbar" data-locked="true">
        <p className="ui-locked-line">
          <Lock className="size-3.5 flex-none" aria-hidden="true" />
          <span>You locked this in.</span>
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
  const hint = !live
    ? `You can explore this, but it cannot be locked in right now: ${brand} is working, or the conversation has moved past it.`
    : (blocked ?? 'Nothing is sent until you lock it in.');
  return (
    <footer className="ui-lockbar">
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
      <p className="ui-hint" role={live ? undefined : 'status'}>
        {hint}
      </p>
    </footer>
  );
}
