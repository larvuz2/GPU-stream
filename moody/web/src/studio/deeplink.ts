/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Links into the studio that start a project: `/app/?discipline=<id>&format=<text>&prompt=<text>`.
 *
 * `source=github` opens the dialog on importing a repository, which is where connecting GitHub
 * from the dialog comes back to.
 *
 * The landing page links here with what a visitor picked and typed, and the studio opens the
 * new-project dialog filled with it, sending the prompt as the project's first message once it is
 * created. A visitor who is not signed in yet is sent to sign in first, and the way back from a
 * provider or an email link is the bare `/app/`, so the draft is kept in this browser for the
 * length of a sign-in and picked up when the studio opens. It is the visitor's own text, held
 * only on their device, and it is dropped once used or once it is an hour old.
 * @module
 */
import { readPreference, writePreference } from './hooks';
import type { ProjectDraft } from './NewProjectDialog';
import { isNumber, isRecord, isString, type Guard } from '../lib/narrow';

/** The query parameters a link into the studio carries. */
const PARAMETERS = ['discipline', 'format', 'prompt', 'source'] as const;

/** The longest prompt a link may carry, which is more than any address bar holds. */
const PROMPT_LIMIT = 20_000;

/** The preference the draft is kept under during a sign-in. */
const STASH = 'draft';

/** How long a kept draft stays usable. */
const STASH_MS = 60 * 60_000;

/** A draft kept during a sign-in, with when it was kept. */
interface StashedDraft {
  /** The discipline's identifier. */
  discipline?: string;
  /** The format. */
  format?: string;
  /** The first message. */
  prompt?: string;
  /** Where the project comes from: `github` for a repository imported from GitHub. */
  source?: string;
  /** When it was kept, in milliseconds since the epoch. */
  at: number;
}

/** Checks a stored value into a {@link StashedDraft}. */
const isStashedDraft: Guard<StashedDraft> = (value): value is StashedDraft =>
  isRecord(value) &&
  isNumber(value.at) &&
  (value.discipline === undefined || isString(value.discipline)) &&
  (value.format === undefined || isString(value.format)) &&
  (value.prompt === undefined || isString(value.prompt)) &&
  (value.source === undefined || isString(value.source));

/**
 * Reads the draft a link carries.
 *
 * @param parameters The page's query parameters.
 * @returns The draft, or `null` when the link carries none of its parameters.
 */
export function draftFromAddress(parameters: URLSearchParams): ProjectDraft | null {
  const draft: ProjectDraft = {};
  for (const name of PARAMETERS) {
    const value = parameters.get(name)?.trim();
    if (value !== undefined && value !== '') {
      draft[name] = name === 'prompt' ? value.slice(0, PROMPT_LIMIT) : value;
    }
  }
  return Object.keys(draft).length === 0 ? null : draft;
}

/**
 * Keeps a draft in this browser while its visitor signs in.
 *
 * @param draft The draft.
 */
export function keepDraft(draft: ProjectDraft): void {
  writePreference(STASH, { ...draft, at: Date.now() });
}

/**
 * Takes the draft kept during a sign-in, once.
 *
 * @returns The draft, or `null` when none was kept or it is too old.
 */
export function takeKeptDraft(): ProjectDraft | null {
  const kept = readPreference(STASH, isStashedDraft);
  writePreference(STASH, undefined);
  if (kept === undefined || Date.now() - kept.at > STASH_MS) {
    return null;
  }
  return { discipline: kept.discipline, format: kept.format, prompt: kept.prompt, source: kept.source };
}

/** Drops a link's draft from the address, so a reload does not open the dialog again. */
export function clearDraftFromAddress(): void {
  const address = new URL(window.location.href);
  if (PARAMETERS.some((name) => address.searchParams.has(name))) {
    for (const name of PARAMETERS) {
      address.searchParams.delete(name);
    }
    window.history.replaceState(null, '', address);
  }
}
