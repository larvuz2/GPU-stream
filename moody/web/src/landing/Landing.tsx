/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page: its sections in the order a visitor is convinced in, and the sign-in dialog.
 *
 * Every way into the product leads to the hero's prompt box (`#create`) or straight to a new
 * project in the app (`studio.ts`, `newProjectUrl`), which has a signed-out visitor sign up there.
 * The dialog is for those who come back: it is opened by the URL fragment (`lib/hash.ts`), so the
 * navigation's sign-in is a link to `#signin` and the app sends a signed-out visitor to `/#signin`;
 * `#signup` opens its other form. A visitor who is already signed in is taken to the app instead of
 * being shown a form.
 * @module
 */
import { useEffect } from 'react';
import { AuthDialog, type AuthMode } from '../components/AuthDialog';
import { replaceHash, useHash } from '../lib/hash';
import { DASHBOARD_PATH } from '../lib/supabase';
import { useAuth } from '../lib/useAuth';
import { Disciplines } from './Disciplines';
import { Engines } from './Engines';
import { Examples } from './Examples';
import { Faq } from './Faq';
import { FinalCta, Footer } from './Footer';
import { GitHub } from './GitHub';
import { Hero } from './Hero';
import { HowItWorks } from './HowItWorks';
import { Nav } from './Nav';
import { Pricing } from './Pricing';
import { Workspace } from './Workspace';

/** The fragment that opens the dialog on each of its forms. */
const AUTH_HASHES: Readonly<Record<AuthMode, string>> = { 'sign-up': '#signup', 'sign-in': '#signin' };

/**
 * Reads which form of the dialog a fragment asks for.
 *
 * @param hash The URL fragment, with its leading `#`.
 * @returns The form, or `null` for any other fragment.
 */
function authModeOf(hash: string): AuthMode | null {
  if (hash === AUTH_HASHES['sign-up']) {
    return 'sign-up';
  }
  return hash === AUTH_HASHES['sign-in'] ? 'sign-in' : null;
}

/**
 * Renders the landing page.
 *
 * @returns The page.
 */
export function Landing() {
  const requested = authModeOf(useHash());
  const auth = useAuth();
  const signedIn = auth.status === 'signed-in';

  useEffect(() => {
    if (requested !== null && signedIn) {
      window.location.assign(DASHBOARD_PATH);
    }
  }, [requested, signedIn]);

  return (
    <div id="top" className="page">
      <div className="backdrop" aria-hidden="true" />
      <a
        href="#main"
        className="btn btn-primary fixed top-3 left-3 z-[60] -translate-y-20 focus-visible:translate-y-0"
      >
        Skip to content
      </a>
      <Nav signedIn={signedIn} />
      <main id="main">
        <Hero />
        <Disciplines />
        <HowItWorks />
        <Workspace />
        <Engines />
        <GitHub />
        <Examples />
        <Pricing />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
      <AuthDialog
        mode={signedIn ? null : requested}
        onClose={() => {
          // Only the dialog's own fragment is dropped: a link inside it may already have moved on.
          if (authModeOf(window.location.hash) !== null) {
            replaceHash('');
          }
        }}
        onModeChange={(mode) => {
          replaceHash(AUTH_HASHES[mode]);
        }}
      />
    </div>
  );
}
