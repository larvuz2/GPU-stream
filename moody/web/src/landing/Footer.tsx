/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The end of the landing page: the last call to action, which sends the visitor back to the
 * prompt box, and the footer, which carries the notice that the product names on the page are their
 * owners' and that the art is illustrative.
 *
 * The call to action is where the wordmark falls into place: its pixels drop in under gravity and
 * bounce to rest each time the block is scrolled to (`lib/moody.ts`, Gravity). The footer closes on
 * the wordmark at the width of the page, as a static drawing.
 * @module
 */
import { ArrowRight } from 'lucide-react';
import { Brand } from '../components/Brand';
import { MoodyMotion } from '../components/Moody';
import { brand, catalog } from '../lib/catalog';
import { ANIMATION, GRID_COLS, GRID_ROWS, RAW, type View } from '../lib/moody';
import { CREATE_HASH } from './studio';

/** The call to action's view of the wordmark: its width, and the height its pixels fall through. */
const DROP_VIEW: View = { cx: 0, cy: -3, cols: GRID_COLS + 4, rows: 16 };

/**
 * Renders the closing call to action.
 *
 * @returns The section.
 */
export function FinalCta() {
  return (
    <section className="section" aria-labelledby="cta-title">
      <div className="shell">
        <div className="stage px-6 pt-4 pb-14 text-center sm:px-12 sm:pb-20">
          <MoodyMotion
            animation={ANIMATION.gravity}
            loop={false}
            view={DROP_VIEW}
            className="relative mx-auto aspect-[30/16] w-full max-w-xl"
          />
          <h2 id="cta-title" className="display relative mx-auto mt-2 max-w-3xl text-[2.4rem] sm:text-6xl lg:text-7xl">
            What will you make?
          </h2>
          <p className="lede relative mx-auto mt-5 max-w-xl text-[1.0625rem] sm:text-lg">
            Describe it in a sentence, and {brand} starts building it with you. The first {catalog.signup_credits}{' '}
            credits are on us.
          </p>
          <div className="relative mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a href={CREATE_HASH} className="btn btn-primary btn-lg w-full sm:w-auto">
              Start creating
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
  { href: '#disciplines', label: 'Disciplines' },
  { href: '#how', label: 'How it works' },
  { href: '#workspace', label: 'Workspace' },
  { href: '#engines', label: 'Engines' },
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
      <div className="shell pt-12">
        <div className="flex flex-col gap-8 md:flex-row md:items-center md:justify-between">
          <div>
            <Brand href="#top" />
            <p className="eyebrow mt-2 flex text-fg">
              <span className="dot dot-live" aria-hidden="true" />
              Made for the endlessly curious.
            </p>
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
            Product names on this page are trademarks of their owners, and {brand} is not affiliated with them. The
            artwork is illustrative, made for this page, and is not anyone&apos;s project.
          </p>
          <p>
            © {YEAR} {brand}
          </p>
        </div>
        <svg
          viewBox={`0 0 ${GRID_COLS} ${GRID_ROWS}`}
          fill="currentColor"
          shapeRendering="crispEdges"
          className="mt-12 block w-full text-ink-700"
          aria-hidden="true"
        >
          {RAW.map(([x, y]) => (
            <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" />
          ))}
        </svg>
      </div>
    </footer>
  );
}
