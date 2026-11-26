/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The one dialog every call to action opens: sign up or sign in with Google, GitHub, an email and
 * password, or a magic link.
 *
 * All four go through Supabase and end on the dashboard: the providers and the email links return
 * there, and a password sign-in navigates there itself. A sign-up that Supabase holds for email
 * confirmation shows a "check your inbox" state instead. The dialog offers the ways the Supabase
 * project has turned on and no other (`signInWays`), so a project that takes Google alone shows
 * one button; the read starts when the page mounts the dialog, and a visitor who opens it before
 * the answer sees the form wait rather than change under their hand. A build without a Supabase
 * project has no form to offer, so the dialog says that sign-ups open soon rather than showing one
 * that cannot work.
 * @module
 */
import { useEffect, useId, useRef, useState, type SubmitEvent, type ReactNode } from 'react';
import type { SupabaseClient } from '@supabase/supabase-js';
import { ArrowRight, MailCheck, Sparkles, TriangleAlert, WandSparkles } from 'lucide-react';
import { brand, catalog } from '../lib/catalog';
import { cx } from '../lib/cx';
import { supabaseConfig } from '../lib/env';
import { DASHBOARD_PATH, dashboardUrl, loadSupabase, signInWays, type SignInWays } from '../lib/supabase';
import { BrandMark } from './Brand';
import { Dialog } from './Dialog';

/** Which of its two forms the dialog shows. */
export type AuthMode = 'sign-up' | 'sign-in';

/** The sign-in providers offered, by their Supabase identifier. */
type Provider = 'google' | 'github';

/** What a sign-in attempt came to. */
type Outcome =
  | { kind: 'error'; message: string }
  /** The browser is on its way to the provider or the dashboard; the form stays busy. */
  | { kind: 'leaving' }
  /** An email went out: a confirmation of a new account, or a magic link. */
  | { kind: 'sent'; what: 'confirmation' | 'magic-link' };

/** The shortest password the sign-up form accepts before Supabase applies the project's own rule. */
const MIN_PASSWORD_LENGTH = 8;

/** Props of {@link AuthDialog}. */
interface AuthDialogProps {
  /** The form to show, or `null` while the dialog is closed. */
  mode: AuthMode | null;
  /** Called when the dialog closes. */
  onClose: () => void;
  /** Called when the visitor switches between signing up and signing in. */
  onModeChange: (mode: AuthMode) => void;
}

/**
 * Renders the sign-up and sign-in dialog.
 *
 * @param props The component's props.
 * @returns The dialog.
 */
export function AuthDialog({ mode, onClose, onModeChange }: AuthDialogProps) {
  const titleId = useId();
  const ways = useSignInWays();
  return (
    <Dialog open={mode !== null} onClose={onClose} labelledBy={titleId}>
      {mode === null ? null : supabaseConfig === null ? (
        <OpeningSoon titleId={titleId} onClose={onClose} />
      ) : (
        <AuthForm mode={mode} ways={ways} titleId={titleId} onModeChange={onModeChange} />
      )}
    </Dialog>
  );
}

/**
 * Reads the ways to sign in that are on, once, for as long as the component is mounted.
 *
 * @returns The ways, or `null` until the project has answered.
 */
function useSignInWays(): SignInWays | null {
  const [ways, setWays] = useState<SignInWays | null>(null);
  useEffect(() => {
    if (supabaseConfig === null) {
      return;
    }
    let current = true;
    void signInWays().then((read) => {
      if (current) {
        setWays(read);
      }
    });
    return () => {
      current = false;
    };
  }, []);
  return ways;
}

/** Props of {@link OpeningSoon}. */
interface OpeningSoonProps {
  /** The `id` the dialog is titled by. */
  titleId: string;
  /** Closes the dialog. */
  onClose: () => void;
}

/**
 * Renders what the dialog says while no Supabase project is configured.
 *
 * @param props The component's props.
 * @returns The message.
 */
function OpeningSoon({ titleId, onClose }: OpeningSoonProps) {
  return (
    <div className="text-center">
      <span className="icon-tile mx-auto size-14">
        <Sparkles className="size-6" aria-hidden="true" />
      </span>
      <h2 id={titleId} className="display mt-5 text-2xl">
        Sign-ups open soon
      </h2>
      <p className="lede mt-3 text-[0.9375rem]">
        {brand} is not taking new accounts just yet. We are putting the finishing touches on the studio, and this is
        where you will create your account as soon as the doors open.
      </p>
      <p className="mt-4 text-sm text-faint">
        Every new account starts with {catalog.signup_credits} free credits.
      </p>
      <div className="mt-7 flex flex-col gap-2.5 sm:flex-row sm:justify-center">
        <button type="button" className="btn btn-primary" onClick={onClose}>
          Got it
        </button>
        <a href="#apps" className="btn btn-ghost">
          See the apps
        </a>
      </div>
    </div>
  );
}

/** Props of {@link AuthForm}. */
interface AuthFormProps {
  /** Whether the form creates an account or signs in to one. */
  mode: AuthMode;
  /** The ways to sign in the project has on, or `null` until it has said. */
  ways: SignInWays | null;
  /** The `id` the dialog is titled by. */
  titleId: string;
  /** Called when the visitor switches to the other form. */
  onModeChange: (mode: AuthMode) => void;
}

/**
 * Runs one request against Supabase and words any failure.
 *
 * @param run The request, given the client; it resolves to what the attempt came to.
 * @returns That outcome, or an error outcome when Supabase could not be reached at all.
 */
async function attempt(run: (supabase: SupabaseClient) => Promise<Outcome>): Promise<Outcome> {
  try {
    const supabase = await loadSupabase();
    if (supabase === null) {
      return { kind: 'error', message: 'Sign-in is not available right now.' };
    }
    return await run(supabase);
  } catch {
    return { kind: 'error', message: 'Could not reach the sign-in service. Check your connection and try again.' };
  }
}

/**
 * Renders the form of a configured build: the provider buttons, the email and password fields,
 * the magic-link request, and the state after an email was sent, each only where the project has
 * that way to sign in turned on.
 *
 * A dialog opens with focus on its first control. One that opened before the project had said
 * which ways are on had only the switch to the other form to give it, so when the ways arrive the
 * focus moves to the first of them, unless the visitor has moved it since: Enter then signs in,
 * as it does in a dialog that opened with the ways known.
 *
 * @param props The component's props.
 * @returns The form.
 */
function AuthForm({ mode, ways, titleId, onModeChange }: AuthFormProps) {
  const emailId = useId();
  const passwordId = useId();
  const emailInput = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState<Provider | 'password' | 'magic-link' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<'confirmation' | 'magic-link' | null>(null);
  const offered = useRef<HTMLDivElement>(null);
  const modeSwitch = useRef<HTMLButtonElement>(null);
  const waited = useRef(ways === null);
  const signingUp = mode === 'sign-up';

  useEffect(() => {
    if (ways === null || !waited.current) {
      return;
    }
    waited.current = false;
    if (document.activeElement === modeSwitch.current) {
      offered.current?.querySelector<HTMLElement>('button, input')?.focus();
    }
  }, [ways]);

  /**
   * Shows what an attempt came to.
   *
   * @param outcome The attempt's outcome.
   */
  function settle(outcome: Outcome): void {
    if (outcome.kind === 'leaving') {
      return;
    }
    setBusy(null);
    if (outcome.kind === 'error') {
      setError(outcome.message);
    } else {
      setSent(outcome.what);
    }
  }

  /**
   * Sends the visitor to a provider, which returns them to the dashboard.
   *
   * @param provider The provider to sign in with.
   */
  async function continueWith(provider: Provider): Promise<void> {
    setBusy(provider);
    setError(null);
    settle(
      await attempt(async (supabase) => {
        const { error: problem } = await supabase.auth.signInWithOAuth({
          provider,
          options: { redirectTo: dashboardUrl() },
        });
        return problem === null ? { kind: 'leaving' } : { kind: 'error', message: problem.message };
      }),
    );
  }

  /**
   * Creates the account or signs in with the email and password entered.
   *
   * @param event The form's submission.
   */
  async function submit(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy('password');
    setError(null);
    settle(
      await attempt(async (supabase): Promise<Outcome> => {
        if (!signingUp) {
          const { error: problem } = await supabase.auth.signInWithPassword({ email, password });
          if (problem !== null) {
            return { kind: 'error', message: problem.message };
          }
          window.location.assign(DASHBOARD_PATH);
          return { kind: 'leaving' };
        }
        const { data, error: problem } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: dashboardUrl() },
        });
        if (problem !== null) {
          return { kind: 'error', message: problem.message };
        }
        if (data.session !== null) {
          window.location.assign(DASHBOARD_PATH);
          return { kind: 'leaving' };
        }
        // Supabase answers a sign-up for a registered address with a user that has no identities,
        // so that the response does not reveal the account to a stranger; the owner needs the hint.
        if (data.user?.identities?.length === 0) {
          return { kind: 'error', message: 'That email already has an account. Sign in instead.' };
        }
        return { kind: 'sent', what: 'confirmation' };
      }),
    );
  }

  /** Emails a link that signs the visitor in, and creates the account if the address is new. */
  async function sendMagicLink(): Promise<void> {
    if (emailInput.current?.reportValidity() !== true) {
      return;
    }
    setBusy('magic-link');
    setError(null);
    settle(
      await attempt(async (supabase) => {
        const { error: problem } = await supabase.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: dashboardUrl() },
        });
        return problem === null ? { kind: 'sent', what: 'magic-link' } : { kind: 'error', message: problem.message };
      }),
    );
  }

  if (sent !== null) {
    return (
      <div className="text-center" role="status">
        <span className="icon-tile mx-auto size-14">
          <MailCheck className="size-6" aria-hidden="true" />
        </span>
        <h2 id={titleId} className="display mt-5 text-2xl">
          Check your inbox
        </h2>
        <p className="lede mt-3 text-[0.9375rem]">
          {sent === 'confirmation' ? 'We sent a confirmation link to ' : 'We sent a sign-in link to '}
          <strong className="font-semibold break-all text-fg">{email}</strong>.{' '}
          {sent === 'confirmation'
            ? 'Open it to finish creating your account.'
            : 'Open it on this device and you land in your studio.'}
        </p>
        <button
          type="button"
          className="btn btn-ghost mt-7"
          onClick={() => {
            setSent(null);
          }}
        >
          Use a different email
        </button>
      </div>
    );
  }

  const disabled = busy !== null;
  const providers = ways !== null && (ways.google || ways.github);
  const problem =
    error === null ? null : (
      <p className="notice notice-bad" role="alert">
        <TriangleAlert className="mt-0.5 size-4 flex-none" aria-hidden="true" />
        <span>{error}</span>
      </p>
    );
  return (
    <div>
      <BrandMark className="h-6 text-fg" />
      <h2 id={titleId} className="display mt-4 text-[1.7rem]">
        {signingUp ? `Create your ${brand} account` : 'Welcome back'}
      </h2>
      <p className="lede mt-2 text-[0.9375rem]">
        {signingUp
          ? `Start with ${catalog.signup_credits} free credits. No card needed.`
          : 'Sign in to open your studio.'}
      </p>

      {ways === null ? (
        <p className="mt-6 flex items-center gap-2.5 text-sm text-muted" role="status">
          <span className="spinner" aria-hidden="true" />
          Getting sign-in ready
        </p>
      ) : null}

      <div ref={offered}>
        {providers ? (
          <div className="mt-6 grid gap-2.5">
            {ways.google ? (
              <ProviderButton
                label="Continue with Google"
                busy={busy === 'google'}
                disabled={disabled}
                onClick={() => {
                  void continueWith('google');
                }}
              >
                <GoogleGlyph />
              </ProviderButton>
            ) : null}
            {ways.github ? (
              <ProviderButton
                label="Continue with GitHub"
                busy={busy === 'github'}
                disabled={disabled}
                onClick={() => {
                  void continueWith('github');
                }}
              >
                <GitHubGlyph />
              </ProviderButton>
            ) : null}
            {ways.email ? null : problem}
          </div>
        ) : null}

        {providers && ways.email ? (
          <div className="my-5 flex items-center gap-3 text-xs font-medium tracking-wider text-faint uppercase">
            <span className="h-px flex-1 bg-line" />
            or with email
            <span className="h-px flex-1 bg-line" />
          </div>
        ) : null}

        {ways?.email === true ? (
          <form
            className={cx('grid gap-3.5', !providers && 'mt-6')}
            onSubmit={(event) => {
              void submit(event);
            }}
          >
            <div>
              <label htmlFor={emailId} className="mb-1.5 block text-sm font-medium">
                Email
              </label>
              <input
                ref={emailInput}
                id={emailId}
                type="email"
                name="email"
                autoComplete="email"
                inputMode="email"
                required
                placeholder="you@example.com"
                className="field"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                }}
              />
            </div>
            <div>
              <label htmlFor={passwordId} className="mb-1.5 block text-sm font-medium">
                Password
              </label>
              <input
                id={passwordId}
                type="password"
                name="password"
                autoComplete={signingUp ? 'new-password' : 'current-password'}
                required
                minLength={signingUp ? MIN_PASSWORD_LENGTH : undefined}
                placeholder={signingUp ? `At least ${MIN_PASSWORD_LENGTH} characters` : 'Your password'}
                className="field"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                }}
              />
            </div>

            {problem}

            <button type="submit" className="btn btn-primary mt-1 w-full" disabled={disabled}>
              {busy === 'password' ? <span className="spinner" aria-hidden="true" /> : null}
              {signingUp ? 'Create account' : 'Sign in'}
              {busy === 'password' ? null : <ArrowRight className="size-4" aria-hidden="true" />}
            </button>
            <button
              type="button"
              className="btn btn-quiet w-full"
              disabled={disabled}
              onClick={() => {
                void sendMagicLink();
              }}
            >
              {busy === 'magic-link' ? (
                <span className="spinner" aria-hidden="true" />
              ) : (
                <WandSparkles className="size-4" aria-hidden="true" />
              )}
              Email me a magic link instead
            </button>
          </form>
        ) : null}
      </div>

      {ways !== null && !providers && !ways.email ? (
        <p className="notice notice-info mt-6" role="status">
          No way to sign in is switched on yet.
        </p>
      ) : null}

      <p className="mt-5 text-center text-sm text-muted">
        {signingUp ? 'Already have an account?' : `New to ${brand}?`}{' '}
        <button
          ref={modeSwitch}
          type="button"
          className="link font-semibold"
          onClick={() => {
            // What was typed carries over to the other form; what went wrong on this one does not.
            setError(null);
            onModeChange(signingUp ? 'sign-in' : 'sign-up');
          }}
        >
          {signingUp ? 'Sign in' : 'Create an account'}
        </button>
      </p>
    </div>
  );
}

/** Props of {@link ProviderButton}. */
interface ProviderButtonProps {
  /** The button's text. */
  label: string;
  /** Whether this provider's sign-in is under way. */
  busy: boolean;
  /** Whether any sign-in is under way, which holds every button. */
  disabled: boolean;
  /** Starts the sign-in. */
  onClick: () => void;
  /** The provider's glyph. */
  children: ReactNode;
}

/**
 * Renders a "Continue with" button.
 *
 * @param props The component's props.
 * @returns The button.
 */
function ProviderButton({ label, busy, disabled, onClick, children }: ProviderButtonProps) {
  return (
    <button type="button" className="btn btn-ghost h-12 w-full" disabled={disabled} onClick={onClick}>
      {busy ? <span className="spinner" aria-hidden="true" /> : children}
      {label}
    </button>
  );
}

/**
 * Renders Google's "G", in the colors its sign-in guidelines ask for.
 *
 * @returns The glyph.
 */
function GoogleGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="size-[1.1rem]" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

/**
 * Renders GitHub's mark.
 *
 * @returns The glyph.
 */
function GitHubGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="size-[1.15rem]" fill="currentColor" aria-hidden="true">
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  );
}
