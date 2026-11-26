/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * How the studio words what the control plane reports: a failed request, and why an engine
 * ended.
 *
 * The statuses with a meaning of their own are introduced as what they are (402 out of credits,
 * 404 a route this control plane does not serve yet, 409 a limit, 503 a feature not configured),
 * the last two followed by the control plane's own explanation of which limit or feature; anything
 * else is shown in its words alone.
 * @module
 */
import { ApiError, NOT_FOUND } from '../lib/api';
import { IDLE_SHUTDOWN_MINUTES } from '../lib/catalog';

/** The status of a request the account lacks the credits for. */
export const OUT_OF_CREDITS = 402;

/** The status of an account the control plane does not serve: one outside its invite list. */
export const NOT_SERVED = 403;

/** The status of a request that ran into a limit. */
const LIMIT_REACHED = 409;

/** The status of a feature the control plane has not been configured for. */
export const NOT_CONFIGURED = 503;

/**
 * Words a failed request for the person looking at the studio.
 *
 * @param error What the request rejected with.
 * @returns A sentence to show beside what failed.
 */
export function describeError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Something went wrong. Try again in a moment.';
  }
  switch (error.status) {
    case OUT_OF_CREDITS:
      return 'You are out of credits. Add credits to keep going.';
    case NOT_FOUND:
      // The web framework's own answer to a route it does not serve, as opposed to a record it lacks.
      return error.message === 'Not Found' ? 'This server does not offer that yet.' : error.message;
    case LIMIT_REACHED:
      return `You have reached a limit: ${error.message}`;
    case NOT_CONFIGURED:
      return `Not switched on yet: ${error.message}`;
    default:
      return error.message;
  }
}

/** The reasons an engine ends that the studio can say better than the identifier does. */
const END_REASONS: Readonly<Record<string, string>> = {
  idle: `Shut down after ${IDLE_SHUTDOWN_MINUTES} idle minutes`,
  idle_timeout: `Shut down after ${IDLE_SHUTDOWN_MINUTES} idle minutes`,
  user: 'Stopped by you',
  stopped: 'Stopped by you',
  credits: 'Ran out of credits',
  out_of_credits: 'Ran out of credits',
};

/**
 * Words why a session ended.
 *
 * The control plane's reason is an identifier or a short phrase; the ones known here read as a
 * sentence, and any other is shown as it came, with its underscores as spaces.
 *
 * @param reason The session's `end_reason`.
 * @returns The reason as text, or `null` when none was recorded.
 */
export function describeEndReason(reason: string | null): string | null {
  if (reason === null || reason.trim() === '') {
    return null;
  }
  const known = Object.hasOwn(END_REASONS, reason) ? END_REASONS[reason] : undefined;
  if (known !== undefined) {
    return known;
  }
  const words = reason.replaceAll('_', ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
