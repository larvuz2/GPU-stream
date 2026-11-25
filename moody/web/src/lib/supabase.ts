/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Supabase client, loaded on demand.
 *
 * The library is a dynamic import, so it is a chunk of its own that the landing page fetches after
 * its first paint rather than a part of what a visitor waits for. One client serves a page: it
 * keeps the session in `localStorage`, refreshes the access token, and picks a session up from the
 * URL a provider or an email link returns to. The implicit flow is kept over PKCE because a
 * confirmation or magic link is often opened on another device than the one that asked for it,
 * where a PKCE verifier would not exist.
 * @module
 */
import type { Session as AuthSession, SupabaseClient } from '@supabase/supabase-js';
import { supabaseConfig } from './env';

/** Where a signed-in user lands, and where the providers and email links return to. */
export const DASHBOARD_PATH = '/app/';

/** The landing page address that opens the sign-in dialog, where a signed-out visitor is sent. */
export const SIGN_IN_PATH = '/#signin';

/** The page's one client, once something has asked for it. */
let client: Promise<SupabaseClient> | null = null;

/**
 * Returns the page's Supabase client, creating it on first use.
 *
 * @returns A promise of the client, or `null` when no Supabase project is configured.
 */
export function loadSupabase(): Promise<SupabaseClient> | null {
  if (supabaseConfig === null) {
    return null;
  }
  const { url, publishableKey } = supabaseConfig;
  client ??= import('@supabase/supabase-js').then(({ createClient }) => createClient(url, publishableKey));
  return client;
}

/**
 * Reads the current session, completing a sign-in the URL carries first.
 *
 * @returns The session, or `null` when nobody is signed in or no project is configured.
 */
export async function currentSession(): Promise<AuthSession | null> {
  const supabase = await loadSupabase();
  if (supabase === null) {
    return null;
  }
  const { data } = await supabase.auth.getSession();
  return data.session;
}

/**
 * Reads the access token the control plane authenticates a request with.
 *
 * @returns The token, or `null` when nobody is signed in.
 */
export async function accessToken(): Promise<string | null> {
  return (await currentSession())?.access_token ?? null;
}

/**
 * The absolute address of the dashboard, for a provider or an email link to return to.
 *
 * @returns The dashboard's URL on this origin.
 */
export function dashboardUrl(): string {
  return new URL(DASHBOARD_PATH, window.location.origin).href;
}
