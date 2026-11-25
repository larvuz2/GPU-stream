/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * An approval: the agent waiting for the person before a tool that costs or changes something,
 * such as starting an engine (`approval` in `moody/STUDIO.md`).
 *
 * The card says what the tool would do and what that costs, and offers three answers: allow it
 * this once, always allow that tool in this project (kept in the project's permissions, and
 * revocable in the Environment panel), or not now. It can be answered only while its turn runs,
 * which is while the agent waits; the answer is sent to the control plane, and the card settles
 * once the log holds the approval's result, so what it shows is what was recorded. An approval
 * nobody answered before its turn ended says so.
 *
 * Allowing once is the card's one lime action, the person's to take; the card itself is lavender,
 * since the agent is the one asking.
 * @module
 */
import { useState } from 'react';
import { Check, Clock, ShieldCheck, X, type LucideIcon } from 'lucide-react';
import type { ApprovalDecision, ApprovalOutcome } from '../lib/api';
import { cx } from '../lib/cx';
import { ErrorNotice } from './Notice';

/** The answers offered, in order, the first of them the primary action. */
const ANSWERS: readonly { decision: ApprovalDecision; label: string; className: string }[] = [
  { decision: 'once', label: 'Allow once', className: 'btn-primary' },
  { decision: 'always', label: 'Always allow in this project', className: 'btn-ghost' },
  { decision: 'deny', label: 'Not now', className: 'btn-quiet' },
];

/** How each way an approval ended is said and drawn. */
const OUTCOMES: Readonly<Record<ApprovalOutcome, { text: string; icon: LucideIcon; className: string }>> = {
  once: { text: 'Allowed once', icon: Check, className: 'text-ok' },
  always: {
    text: 'Always allowed in this project. You can take that back in the Environment panel.',
    icon: ShieldCheck,
    className: 'text-ok',
  },
  deny: { text: 'Not now: it did not run.', icon: X, className: 'text-muted' },
  expired: { text: 'Not answered before the turn ended, so it did not run.', icon: Clock, className: 'text-faint' },
};

/** Props of {@link ApprovalCard}. */
interface ApprovalCardProps {
  /** What the tool would do. */
  title: string;
  /** What that costs or changes. */
  detail: string;
  /** The tool's name. */
  tool: string;
  /** How the approval ended, or `null` while the agent waits. */
  outcome: ApprovalOutcome | null;
  /** Whether it can be answered now: its turn is running and the agent can be reached. */
  live: boolean;
  /** Sends the person's answer. */
  onDecide: (decision: ApprovalDecision) => Promise<void>;
}

/**
 * Renders an approval with its three answers, or with how it ended.
 *
 * @param props The component's props.
 * @returns The card.
 */
export function ApprovalCard({ title, detail, tool, outcome, live, onDecide }: ApprovalCardProps) {
  const [sent, setSent] = useState<ApprovalDecision | null>(null);
  const [error, setError] = useState<unknown>(null);

  /**
   * Sends an answer, which stays chosen until the log holds the approval's result.
   *
   * @param decision The answer.
   */
  async function decide(decision: ApprovalDecision): Promise<void> {
    setSent(decision);
    setError(null);
    try {
      await onDecide(decision);
    } catch (failure) {
      setError(failure);
      setSent(null);
    }
  }

  const ended = outcome === null ? null : OUTCOMES[outcome];
  return (
    <section className="ai-card approval-card rounded-2xl p-4" aria-label={`Approval: ${title}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="ai-label">Moody asks first</p>
        <span className="mono truncate text-[0.6875rem] text-faint">{tool}</span>
      </div>
      <p className="mt-2 font-medium text-fg">{title}</p>
      {detail === '' ? null : <p className="mt-1 text-sm leading-relaxed text-muted">{detail}</p>}
      {ended === null ? (
        <div className="mt-3.5 flex flex-wrap items-center gap-2">
          {ANSWERS.map((answer) => (
            <button
              key={answer.decision}
              type="button"
              className={cx('btn btn-sm', answer.className)}
              disabled={!live || sent !== null}
              onClick={() => {
                void decide(answer.decision);
              }}
            >
              {sent === answer.decision ? <span className="spinner size-3.5" aria-hidden="true" /> : null}
              {answer.label}
            </button>
          ))}
        </div>
      ) : (
        <p className={cx('mt-3 flex items-start gap-2 text-sm', ended.className)} role="status">
          <ended.icon className="mt-0.5 size-4 flex-none" aria-hidden="true" />
          <span>{ended.text}</span>
        </p>
      )}
      {outcome === null && !live ? (
        <p className="mt-2.5 text-xs text-faint">This can be answered while the agent is waiting on it.</p>
      ) : null}
      {error === null ? null : (
        <div className="mt-3">
          <ErrorNotice error={error} />
        </div>
      )}
    </section>
  );
}
