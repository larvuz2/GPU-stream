/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Entry point of the studio (`/app/`): decides who may see it, then mounts {@link Studio}.
 *
 * A signed-in visitor gets the studio over the HTTP control plane, authenticated by their Supabase
 * token on every request. A signed-out one is sent to the landing page's sign-in dialog; so is
 * anyone on a build with no Supabase project, where nobody can be signed in. Supabase picks up a
 * sign-in that a provider or an email link just returned in this page's URL before the session is
 * read, so arriving from either lands here signed in. A link into the studio that starts a project
 * (`deeplink.ts`) is kept across that sign-in.
 *
 * `?demo` is the one other way in: it mounts the studio over fixtures (`studio/demo.ts`), never
 * over the HTTP client, so it shows nothing of an account and needs none. `?demo=offline` shows a
 * server with no integrations configured, `?demo=empty` an account with no projects,
 * `?demo=legacy` a control plane from before the studio, `?demo=movie` a new film played from
 * its first message: the agent thinking, asking, handing work to subagents, and asking before it
 * starts an engine, and `?demo=limit` that film further on, where a long job has stopped at the
 * spend the account allows a turn.
 *
 * GitHub's callback returns here with `?github=` and what happened (`connected`, `installed` for
 * the GitHub App installed on more repositories, `requested` for an installation an organization's
 * owners were asked for, or `failed`), and the Epic connection's with `?epic=connected` or
 * `?epic=failed`; each is read once and dropped from the address.
 * @module
 */
import { StrictMode, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import '../styles.css';
import './studio.css';
import { createControlPlane } from '../lib/api';
import { apiUrl } from '../lib/env';
import { accessToken, currentSession, loadSupabase, SIGN_IN_PATH } from '../lib/supabase';
import { clearDraftFromAddress, draftFromAddress, keepDraft, takeKeptDraft } from './deeplink';
import type { EpicReturn, GitHubReturn } from './EnvironmentPanel';
import { Studio } from './Studio';
import { EPIC_RESULT_PARAMETER, GITHUB_RESULT_PARAMETER } from './useAccount';

/** The query parameter that asks for the demo. */
const DEMO_PARAMETER = 'demo';

/**
 * Reads, and drops from the address, one query parameter a callback reported its outcome in.
 *
 * @param parameters The page's query parameters.
 * @param name The parameter.
 * @returns Its value, or `null` when the page was not opened by that callback.
 */
function takeReturn(parameters: URLSearchParams, name: string): string | null {
  const value = parameters.get(name);
  if (value === null) {
    return null;
  }
  const address = new URL(window.location.href);
  address.searchParams.delete(name);
  window.history.replaceState(null, '', address);
  return value;
}

/**
 * Reads, and drops from the address, the outcome of a return from GitHub.
 *
 * @param parameters The page's query parameters.
 * @returns The outcome, or `null` when the page was not opened by GitHub's callback.
 */
function takeGitHubReturn(parameters: URLSearchParams): GitHubReturn {
  const value = takeReturn(parameters, GITHUB_RESULT_PARAMETER);
  if (value === null) {
    return null;
  }
  return value === 'connected' || value === 'installed' || value === 'requested' ? value : 'failed';
}

/**
 * Reads, and drops from the address, the outcome of a return from connecting Epic.
 *
 * @param parameters The page's query parameters.
 * @returns The outcome, or `null` when the page was not opened by that callback.
 */
function takeEpicReturn(parameters: URLSearchParams): EpicReturn {
  const value = takeReturn(parameters, EPIC_RESULT_PARAMETER);
  if (value === null) {
    return null;
  }
  return value === 'connected' ? 'connected' : 'failed';
}

/**
 * Works out what this visit shows.
 *
 * @returns The studio to mount, or `null` after sending the browser elsewhere.
 */
async function resolve(): Promise<ReactNode> {
  const parameters = new URLSearchParams(window.location.search);
  const linked = draftFromAddress(parameters);

  if (parameters.has(DEMO_PARAMETER)) {
    const [{ createDemoControlPlane, DEMO_EMAIL }, { DemoScreen }] = await Promise.all([
      import('./demo'),
      import('./DemoScreen'),
    ]);
    return (
      <Studio
        client={createDemoControlPlane(parameters.get(DEMO_PARAMETER))}
        email={DEMO_EMAIL}
        demo
        draft={linked}
        onDraftDone={clearDraftFromAddress}
        githubReturned={takeGitHubReturn(parameters)}
        epicReturned={takeEpicReturn(parameters)}
        standIn={DemoScreen}
        onSignOut={() => {
          window.location.assign('/');
        }}
      />
    );
  }

  const session = await currentSession().catch(() => null);
  const supabase = await loadSupabase()?.catch(() => null);
  if (session === null || supabase === null || supabase === undefined) {
    if (linked !== null) {
      keepDraft(linked);
    }
    window.location.replace(SIGN_IN_PATH);
    return null;
  }
  // Signing out, here or in another tab, leaves nothing to show.
  supabase.auth.onAuthStateChange((event) => {
    if (event === 'SIGNED_OUT') {
      window.location.replace('/');
    }
  });
  const kept = takeKeptDraft();
  return (
    <Studio
      client={apiUrl === null ? null : createControlPlane(apiUrl, accessToken)}
      email={session.user.email ?? ''}
      demo={false}
      draft={linked ?? kept}
      onDraftDone={clearDraftFromAddress}
      githubReturned={takeGitHubReturn(parameters)}
      epicReturned={takeEpicReturn(parameters)}
      onSignOut={() => {
        void supabase.auth.signOut();
      }}
    />
  );
}

const root = document.getElementById('root');
if (root !== null) {
  void resolve().then((page) => {
    if (page !== null) {
      createRoot(root).render(<StrictMode>{page}</StrictMode>);
    }
  });
}
