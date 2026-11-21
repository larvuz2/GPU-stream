/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Entry point of the dashboard (`/app/`): decides who may see it, then mounts {@link Dashboard}.
 *
 * A signed-in visitor gets the dashboard over the HTTP control plane, authenticated by their
 * Supabase token on every request. A signed-out one is sent to the landing page's sign-in dialog;
 * so is anyone on a build with no Supabase project, where nobody can be signed in. Supabase picks
 * up a sign-in that a provider or an email link just returned in this page's URL before the
 * session is read, so arriving from either lands here signed in.
 *
 * `?preview=1` is the one other way in: it mounts the dashboard over fixtures
 * (`dashboard/preview.ts`), never over the HTTP client, so it shows nothing of an account and
 * needs none.
 * @module
 */
import { StrictMode, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import '../styles.css';
import { createControlPlane } from '../lib/api';
import { apiUrl } from '../lib/env';
import { accessToken, currentSession, loadSupabase, SIGN_IN_PATH } from '../lib/supabase';
import { Dashboard } from './Dashboard';

/** The query parameter that asks for the preview, and the value that turns it on. */
const PREVIEW_PARAMETER = 'preview';

/**
 * Works out what this visit shows.
 *
 * @returns The dashboard to mount, or `null` after sending the browser elsewhere.
 */
async function resolve(): Promise<ReactNode> {
  const parameters = new URLSearchParams(window.location.search);
  if (parameters.get(PREVIEW_PARAMETER) === '1') {
    const { createPreviewControlPlane, PREVIEW_EMAIL } = await import('./preview');
    return (
      <Dashboard
        client={createPreviewControlPlane(parameters.get('scene'))}
        email={PREVIEW_EMAIL}
        preview
        onSignOut={() => {
          window.location.assign('/');
        }}
      />
    );
  }

  const session = await currentSession().catch(() => null);
  const supabase = await loadSupabase()?.catch(() => null);
  if (session === null || supabase === null || supabase === undefined) {
    window.location.replace(SIGN_IN_PATH);
    return null;
  }
  // Signing out, here or in another tab, leaves nothing to show.
  supabase.auth.onAuthStateChange((event) => {
    if (event === 'SIGNED_OUT') {
      window.location.replace('/');
    }
  });
  return (
    <Dashboard
      client={apiUrl === null ? null : createControlPlane(apiUrl, accessToken)}
      email={session.user.email ?? ''}
      preview={false}
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
