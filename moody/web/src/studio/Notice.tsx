/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The studio's inline messages: a banner, and the notice a failed request leaves beside the
 * control that made it.
 * @module
 */
import type { ReactNode } from 'react';
import { CircleAlert, Info, TriangleAlert, type LucideIcon } from 'lucide-react';
import { ApiError } from '../lib/api';
import { cx } from '../lib/cx';
import { describeError, OUT_OF_CREDITS } from './messages';

/** How serious a message is, which picks its color and icon. */
type Tone = 'info' | 'warn' | 'bad';

/** The class and the icon each tone is drawn with. */
const TONES: Readonly<Record<Tone, { className: string; icon: LucideIcon }>> = {
  info: { className: 'notice-info', icon: Info },
  warn: { className: 'notice-warn', icon: TriangleAlert },
  bad: { className: 'notice-bad', icon: CircleAlert },
};

/** Props of {@link Notice}. */
interface NoticeProps {
  /** How serious the message is. */
  tone: Tone;
  /** The message's bold first words. */
  title?: string;
  /** The message. */
  children: ReactNode;
  /** A control shown after the message, such as a button that resolves it. */
  action?: ReactNode;
  /** Whether a screen reader announces the message when it appears. */
  announce?: boolean;
}

/**
 * Renders a message in a tinted box.
 *
 * @param props The component's props.
 * @returns The message.
 */
export function Notice({ tone, title, children, action, announce = false }: NoticeProps) {
  const { className, icon: Icon } = TONES[tone];
  return (
    <div className={cx('notice', className)} role={announce ? 'alert' : undefined}>
      <Icon className="mt-0.5 size-4 flex-none" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {title === undefined ? null : <strong className="font-semibold text-fg">{title} </strong>}
        {children}
      </div>
      {action}
    </div>
  );
}

/** Props of {@link ErrorNotice}. */
interface ErrorNoticeProps {
  /** What a request rejected with, or `null` when nothing failed. */
  error: unknown;
  /** Opens Settings on Billing, offered when the failure is a lack of credits. */
  onAddCredits?: () => void;
}

/**
 * Renders what a failed request came to, with a way to add credits when that is the cure.
 *
 * @param props The component's props.
 * @returns The notice, or nothing while there is no error.
 */
export function ErrorNotice({ error, onAddCredits }: ErrorNoticeProps) {
  if (error === null) {
    return null;
  }
  const outOfCredits = error instanceof ApiError && error.status === OUT_OF_CREDITS;
  return (
    <Notice
      tone={outOfCredits ? 'warn' : 'bad'}
      announce
      action={
        outOfCredits && onAddCredits !== undefined ? (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onAddCredits}>
            Add credits
          </button>
        ) : undefined
      }
    >
      {describeError(error)}
    </Notice>
  );
}
