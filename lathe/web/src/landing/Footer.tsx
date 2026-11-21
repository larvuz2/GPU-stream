/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The end of the landing page: the last call to action and the footer, which carries the
 * trademark notice for the apps the page names by their owners' logos. Both takes of the landing
 * page end here; the call to action takes each one's closing words.
 * @module
 */
import { ArrowRight } from 'lucide-react';
import { Brand } from '../components/Brand';
import { brand, catalog } from '../lib/catalog';

/** Props of {@link FinalCta}. */
interface FinalCtaProps {
  /** The opening words of the title. */
  lead?: string;
  /** The words of the title set in the gradient. */
  accent?: string;
  /** The sentence under the title, before the note on the free credits. */
  body?: string;
}

/**
 * Renders the closing call to action.
 *
 * @param props The component's props.
 * @returns The section.
 */
export function FinalCta({
  lead = 'Your studio is',
  accent = 'one tab away',
  body = 'Create an account, pick an app, and open the tab.',
}: FinalCtaProps) {
  return (
    <section className="section pt-6" aria-labelledby="cta-title">
      <div className="shell">
        <div className="relative isolate overflow-hidden rounded-[2rem] border border-line-strong bg-ink-900 px-6 py-16 text-center sm:px-12 sm:py-24">
          <div
            className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(60%_90%_at_50%_120%,rgb(255_122_26/0.5),rgb(139_92_246/0.28)_45%,transparent_75%)]"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute top-full left-1/2 -z-10 size-[58rem] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/10"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute top-full left-1/2 -z-10 size-[40rem] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/10"
            aria-hidden="true"
          />
          <h2 id="cta-title" className="display mx-auto max-w-3xl text-[2.2rem] sm:text-6xl">
            {lead} <span className="text-gradient">{accent}</span>
          </h2>
          <p className="lede mx-auto mt-5 max-w-xl text-[1.0625rem] sm:text-lg">
            {body} The first {catalog.signup_credits} credits are on us.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a href="#signup" className="btn btn-primary btn-lg w-full sm:w-auto">
              Start free — {catalog.signup_credits} credits on us
              <ArrowRight className="size-4" aria-hidden="true" />
            </a>
            <a href="#pricing" className="btn btn-ghost btn-lg w-full sm:w-auto">
              See pricing
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

/** The year the copyright line carries, read once when the page loads. */
const YEAR = new Date().getFullYear();

/** The footer's links, in reading order. */
const FOOTER_LINKS = [
  { href: '#apps', label: 'Apps' },
  { href: '#how', label: 'How it works' },
  { href: '#claude', label: 'For Claude' },
  { href: '#pricing', label: 'Pricing' },
  { href: '#faq', label: 'FAQ' },
  { href: '#signin', label: 'Sign in' },
] as const;

/**
 * Renders the footer.
 *
 * @returns The footer.
 */
export function Footer() {
  return (
    <footer className="relative border-t border-line">
      <div className="shell py-12">
        <div className="flex flex-col gap-8 md:flex-row md:items-center md:justify-between">
          <div>
            <Brand href="#top" />
            <p className="mt-3 max-w-xs text-sm text-muted">Spin up a GPU studio in your browser.</p>
          </div>
          <nav aria-label="Footer">
            <ul className="flex flex-wrap gap-x-6 gap-y-3 text-sm text-muted">
              {FOOTER_LINKS.map((link) => (
                <li key={link.href}>
                  <a href={link.href} className="rounded transition-colors hover:text-fg">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="mt-10 grid gap-3 border-t border-line pt-8 text-xs leading-relaxed text-faint">
          <p>
            Blender is a trademark of the Blender Foundation. Unreal Engine is a trademark of Epic Games. {brand} is
            not affiliated with either.
          </p>
          <p>
            Other product names and logos belong to their owners. Artwork on this page is illustrative.
          </p>
          <p>
            © {YEAR} {brand}
          </p>
        </div>
      </div>
    </footer>
  );
}
