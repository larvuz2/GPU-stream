/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page: its sections in the order a visitor is convinced in, and the sign-up dialog
 * they all lead to.
 *
 * The page comes in two takes that differ only in those sections: the first, written out here,
 * explains how the product works, and the second (`creative/CreativeLanding.tsx`) leads with what
 * people make with it. A bar above the navigation switches between them (`CompareBar.tsx`,
 * `option.ts`), and everything around the sections is one and the same.
 *
 * The dialog is opened by the URL fragment (`lib/hash.ts`): every call to action is a link to
 * `#signup` or `#signin`, so no section needs a callback, and the dashboard sends a signed-out
 * visitor to `/#signin`. A visitor who is already signed in is taken to the dashboard instead of
 * being shown a form.
 * @module
 */
import { useEffect } from 'react';
import { AuthDialog, type AuthMode } from '../components/AuthDialog';
import { replaceHash, useHash } from '../lib/hash';
import { DASHBOARD_PATH } from '../lib/supabase';
import { useAuth } from '../lib/useAuth';
import { AgentSection } from './AgentSection';
import { Apps } from './Apps';
import { CompareBar } from './CompareBar';
import { CreativeLanding } from './creative/CreativeLanding';
import { Faq } from './Faq';
import { Features, HowItWorks, TrustStrip } from './Features';
import { FinalCta, Footer } from './Footer';
import { Hero } from './Hero';
import { Nav } from './Nav';
import { chooseLandingOption, useLandingOption } from './option';
import { Pricing } from './Pricing';

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
  const option = useLandingOption();
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
      <CompareBar option={option} onChoose={chooseLandingOption} />
      <Nav signedIn={signedIn} />
      <main id="main">
        {option === 2 ? (
          <CreativeLanding />
        ) : (
          <>
            <Hero />
            <TrustStrip />
            <Apps />
            <HowItWorks />
            <AgentSection />
            <Features />
            <Pricing />
            <Faq />
            <FinalCta />
          </>
        )}
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
