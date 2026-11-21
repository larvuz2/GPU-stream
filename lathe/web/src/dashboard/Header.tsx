/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The dashboard's header: the logo, the credit balance, the way to add credits, and the account
 * menu with sign out.
 * @module
 */
import { useEffect, useId, useRef, useState } from 'react';
import { Coins, LogOut, Plus } from 'lucide-react';
import { Brand } from '../components/Brand';
import { cx } from '../lib/cx';
import { creditCount } from '../lib/format';

/** Props of {@link Header}. */
interface HeaderProps {
  /** The credit balance, or `null` while it is not known. */
  credits: number | null;
  /** The signed-in account's email address. */
  email: string;
  /** Opens the credits dialog. */
  onAddCredits: () => void;
  /** Signs the user out. */
  onSignOut: () => void;
}

/**
 * Renders the dashboard's sticky header.
 *
 * @param props The component's props.
 * @returns The header.
 */
export function Header({ credits, email, onAddCredits, onSignOut }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ink-950/70 backdrop-blur-xl">
      <div className="shell flex h-16 items-center gap-2.5">
        <Brand href="/" />
        <div className="ml-auto flex items-center gap-2">
          <p className="pill h-9 gap-2 px-3 text-sm" aria-label="Credit balance">
            <Coins className="size-4 text-ember-300" aria-hidden="true" />
            <span className="font-semibold tabular-nums">{credits === null ? '—' : creditCount(credits)}</span>
            <span className="hidden font-normal text-muted sm:inline">credits</span>
          </p>
          <button type="button" className="btn btn-primary btn-sm" onClick={onAddCredits}>
            <Plus className="size-4" aria-hidden="true" />
            <span>
              Add<span className="hidden sm:inline"> credits</span>
            </span>
          </button>
          <AccountMenu email={email} onSignOut={onSignOut} />
        </div>
      </div>
    </header>
  );
}

/** Props of {@link AccountMenu}. */
interface AccountMenuProps {
  /** The signed-in account's email address. */
  email: string;
  /** Signs the user out. */
  onSignOut: () => void;
}

/**
 * Renders the account button and the menu it opens.
 *
 * The menu closes on Escape, which returns focus to the button, and on a press anywhere outside.
 *
 * @param props The component's props.
 * @returns The button and, while open, the menu.
 */
function AccountMenu({ email, onSignOut }: AccountMenuProps) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: PointerEvent): void => {
      if (event.target instanceof Node && container.current?.contains(event.target) !== true) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={container} className="relative">
      <button
        ref={button}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label="Account"
        className={cx(
          'grid size-9 place-items-center rounded-full border border-line-strong text-sm font-semibold uppercase',
          'bg-gradient-to-br from-ember/30 to-iris/30 transition-colors hover:border-white/40 focus-visible:rounded-full',
        )}
        onClick={() => {
          setOpen((value) => !value);
        }}
      >
        {email.charAt(0) || '?'}
      </button>
      <div
        id={menuId}
        role="menu"
        hidden={!open}
        className="glass absolute top-full right-0 z-40 mt-2 w-64 rounded-2xl bg-ink-800 p-2 shadow-2xl"
      >
        <p className="px-3 pt-2 text-xs text-faint">Signed in as</p>
        <p className="truncate px-3 pb-2 text-sm font-medium" title={email}>
          {email}
        </p>
        <button
          type="button"
          role="menuitem"
          className="btn btn-quiet w-full justify-start rounded-xl border-t border-line"
          onClick={onSignOut}
        >
          <LogOut className="size-4" aria-hidden="true" />
          Sign out
        </button>
      </div>
    </div>
  );
}
