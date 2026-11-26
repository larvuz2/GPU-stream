/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Profile tab of Settings: the person's name, the email address they sign in with, and
 * signing out.
 *
 * The name is theirs to change and is kept by the control plane (`PATCH /v1/me`), which trims it
 * and takes at most {@link NAME_LIMIT} characters; an empty one is sent as `null`, which clears
 * it. It is offered only where the control plane keeps names. The email address is the sign-in's
 * and is shown, not edited: changing it is a change of the sign-in, which this page does not do.
 * @module
 */
import { useId, useState, type SubmitEvent } from 'react';
import { Check, LogOut } from 'lucide-react';
import type { AccountChanges, Me } from '../../lib/api';
import { ErrorNotice, Notice } from '../Notice';
import { Block, TabHeading } from './parts';

/** The longest name the control plane keeps (`moody/STUDIO.md`, "Settings are the person's"). */
const NAME_LIMIT = 80;

/** Props of {@link ProfileTab}. */
interface ProfileTabProps {
  /** The account, or `null` until it has loaded. */
  me: Me | null;
  /** The email address the person signed in with. */
  email: string;
  /** Whether a control plane is connected. */
  connected: boolean;
  /** Saves a change to the account. Rejects with an `ApiError`. */
  onSave: (changes: AccountChanges) => Promise<void>;
  /** Signs the person out. */
  onSignOut: () => void;
}

/**
 * Renders the Profile tab.
 *
 * @param props The component's props.
 * @returns The tab's content.
 */
export function ProfileTab({ me, email, connected, onSave, onSignOut }: ProfileTabProps) {
  const emailId = useId();
  return (
    <>
      <TabHeading title="Profile">Who you are in the studio.</TabHeading>
      {connected ? null : (
        <div className="mt-6">
          <Notice tone="warn" title="Control plane not connected.">
            You are signed in, and the rest of your settings appear here once it is.
          </Notice>
        </div>
      )}
      {me === null ? (
        connected ? (
          <Block>
            <div className="h-[4.6rem] animate-pulse rounded-xl bg-white/[0.04] sm:max-w-md" aria-label="Loading your profile" />
          </Block>
        ) : null
      ) : me.name === undefined ? null : (
        <Block>
          <NameForm name={me.name ?? ''} onSave={onSave} />
        </Block>
      )}
      <Block>
        <p id={emailId} className="text-sm font-medium">
          Email
        </p>
        <p className="mt-1.5 truncate text-[0.9375rem]" aria-labelledby={emailId}>
          {email || 'No email address on this sign-in'}
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-faint">The address you sign in with. It is not changed here.</p>
      </Block>
      <Block>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onSignOut}>
          <LogOut className="size-4" aria-hidden="true" />
          Sign out
        </button>
        <p className="mt-2 text-xs leading-relaxed text-faint">
          Signs you out of this browser. Engines that are running keep running until they are stopped or idle.
        </p>
      </Block>
    </>
  );
}

/** Props of {@link NameForm}. */
interface NameFormProps {
  /** The name the control plane holds, empty where the person gave none. */
  name: string;
  /** Saves a change to the account. */
  onSave: (changes: AccountChanges) => Promise<void>;
}

/**
 * Renders the person's name and saves a change of it.
 *
 * @param props The component's props.
 * @returns The form.
 */
function NameForm({ name, onSave }: NameFormProps) {
  const fieldId = useId();
  const helpId = useId();
  // What the person typed since the name was last read; `null` while the field shows the name held.
  const [typed, setTyped] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const shown = typed ?? name;
  const next = shown.trim().replace(/\s+/g, ' ');
  const unchanged = next === name;

  /**
   * Saves the name, or clears it where the field is empty.
   *
   * @param event The form's submission.
   */
  async function submit(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (unchanged) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSave({ name: next === '' ? null : next });
      setTyped(null);
      setSaved(true);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="sm:max-w-md"
      onSubmit={(event) => {
        void submit(event);
      }}
    >
      <label htmlFor={fieldId} className="text-sm font-medium">
        Name
      </label>
      <div className="mt-1.5 flex gap-2">
        <input
          id={fieldId}
          className="field min-w-0 flex-1"
          autoComplete="name"
          maxLength={NAME_LIMIT}
          placeholder="Your name"
          aria-describedby={helpId}
          value={shown}
          onChange={(event) => {
            setTyped(event.target.value);
            setSaved(false);
            setError(null);
          }}
        />
        <button type="submit" className="btn btn-primary h-[2.9rem]" disabled={busy || unchanged}>
          {busy ? <span className="spinner size-3.5" aria-hidden="true" /> : null}
          Save
        </button>
      </div>
      <p id={helpId} className="mt-1.5 flex items-center gap-1.5 text-xs leading-relaxed text-faint" role="status">
        {saved && unchanged ? (
          <>
            <Check className="size-3.5 text-ok" aria-hidden="true" />
            Saved.
          </>
        ) : (
          'Shown in the studio in place of your email address.'
        )}
      </p>
      {error === null ? null : (
        <div className="mt-3">
          <ErrorNotice error={error} />
        </div>
      )}
    </form>
  );
}
