/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Who is signed in, as state a page can render from.
 * @module
 */
import { useEffect, useState } from 'react';
import { supabaseConfig } from './env';
import { loadSupabase } from './supabase';

/**
 * What a page knows about the visitor's sign-in.
 *
 * `unconfigured` is a build with no Supabase project, where nobody can sign in; `loading` lasts
 * until the client has read its stored session.
 */
export type AuthState =
  | { status: 'unconfigured' | 'loading' | 'signed-out' }
  | { status: 'signed-in'; email: string };

/**
 * Follows the visitor's sign-in for as long as the component is mounted.
 *
 * Supabase reports the stored session to a new subscriber and every change after it, in this tab
 * or another, so the one subscription is both the first read and the updates.
 *
 * @returns The current state.
 */
export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>({ status: supabaseConfig === null ? 'unconfigured' : 'loading' });

  useEffect(() => {
    const pending = loadSupabase();
    if (pending === null) {
      return;
    }
    let active = true;
    let unsubscribe: (() => void) | null = null;
    pending
      .then((supabase) => {
        if (!active) {
          return;
        }
        const { data } = supabase.auth.onAuthStateChange((_event, session) => {
          setState(session === null ? { status: 'signed-out' } : { status: 'signed-in', email: session.user.email ?? '' });
        });
        unsubscribe = () => {
          data.subscription.unsubscribe();
        };
      })
      .catch(() => {
        // The library did not load; the dialog reports that when the visitor tries to sign in.
        setState({ status: 'signed-out' });
      });
    return () => {
      active = false;
      unsubscribe?.();
    };
  }, []);

  return state;
}
