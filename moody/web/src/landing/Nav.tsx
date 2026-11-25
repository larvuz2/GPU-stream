/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's navigation: a sticky, translucent bar with the logo, the section links, the
 * sign-in, and the call to action, which takes the visitor to the hero's prompt box.
 * @module
 */
import { useState } from 'react';
import { ArrowRight, Menu, X } from 'lucide-react';
import { Brand } from '../components/Brand';
import { DASHBOARD_PATH } from '../lib/supabase';
import { CREATE_HASH } from './studio';

/** The sections the bar links to, in page order. */
const LINKS = [
  { href: '#disciplines', label: 'Disciplines' },
  { href: '#engines', label: 'Engines' },
  { href: '#pricing', label: 'Pricing' },
] as const;

/** Props of {@link Nav}. */
interface NavProps {
  /** Whether the visitor is signed in, which swaps the sign-in link for a link to the app. */
  signedIn: boolean;
}

/**
 * Renders the navigation bar, with the section links folded into a menu on a narrow screen.
 *
 * @param props The component's props.
 * @returns The bar.
 */
export function Nav({ signedIn }: NavProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = (): void => {
    setMenuOpen(false);
  };

  return (
    <header
      className="sticky top-0 z-40 border-b border-line bg-ink-950/70 backdrop-blur-xl"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          closeMenu();
        }
      }}
    >
      <nav aria-label="Main" className="shell flex h-16 items-center gap-3">
        <Brand href="#top" />
        <ul className="ml-6 hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a href={link.href} className="btn btn-quiet btn-sm font-medium">
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="ml-auto flex items-center gap-2">
          {signedIn ? (
            <a href={DASHBOARD_PATH} className="btn btn-quiet btn-sm hidden sm:inline-flex">
              Open the studio
            </a>
          ) : (
            <a href="#signin" className="btn btn-quiet btn-sm hidden sm:inline-flex">
              Sign in
            </a>
          )}
          <a href={CREATE_HASH} className="btn btn-primary btn-sm" onClick={closeMenu}>
            Start creating
            <ArrowRight className="hidden size-3.5 sm:block" aria-hidden="true" />
          </a>
          <button
            type="button"
            className="btn btn-ghost btn-sm size-9 px-0 md:hidden"
            aria-expanded={menuOpen}
            aria-controls="nav-menu"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            onClick={() => {
              setMenuOpen((open) => !open);
            }}
          >
            {menuOpen ? <X className="size-4" aria-hidden="true" /> : <Menu className="size-4" aria-hidden="true" />}
          </button>
        </div>
      </nav>
      <div id="nav-menu" hidden={!menuOpen} className="border-t border-line md:hidden">
        <ul className="shell grid gap-1 py-3">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a href={link.href} className="btn btn-quiet w-full justify-start font-medium" onClick={closeMenu}>
                {link.label}
              </a>
            </li>
          ))}
          <li className="sm:hidden">
            {signedIn ? (
              <a href={DASHBOARD_PATH} className="btn btn-ghost mt-1 w-full" onClick={closeMenu}>
                Open the studio
              </a>
            ) : (
              <a href="#signin" className="btn btn-ghost mt-1 w-full" onClick={closeMenu}>
                Sign in
              </a>
            )}
          </li>
        </ul>
      </div>
    </header>
  );
}
