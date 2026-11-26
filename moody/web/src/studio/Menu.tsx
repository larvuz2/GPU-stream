/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A button that opens a menu of actions, and the GitHub mark the studio names GitHub with.
 *
 * The menu closes on Escape, which returns focus to its button, on a press anywhere outside, and
 * after any of its items is chosen. The arrow keys move between its items. Choosing an item gives
 * the focus back to the button too, before the item's own work shows: a dialog the item opens
 * then returns the focus there as it closes, where the item itself is gone by then.
 * @module
 */
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { cx } from '../lib/cx';

/** One action of a {@link Menu}. */
export interface MenuAction {
  /** The item's label. */
  label: string;
  /** Its icon. */
  icon: ReactNode;
  /** What choosing it does. */
  onSelect: () => void;
  /** Whether it destroys something, which colors it. */
  danger?: boolean;
  /** Whether it cannot be chosen now. */
  disabled?: boolean;
}

/** Props of {@link Menu}. */
interface MenuProps {
  /** The button's accessible name. */
  label: string;
  /** What the button shows. */
  trigger: ReactNode;
  /** Classes for the button. */
  triggerClassName: string;
  /** The items, or a node for a menu with content of its own. */
  items: MenuAction[] | ReactNode;
  /** Where the menu opens, relative to its button. */
  placement?: 'below-end' | 'below-start' | 'above-start';
  /** Classes for the menu. */
  menuClassName?: string;
}

/** Where each placement puts the menu. */
const PLACEMENTS = {
  'below-end': 'top-full right-0 mt-1.5',
  'below-start': 'top-full left-0 mt-1.5',
  'above-start': 'bottom-full left-0 mb-2',
} as const;

/**
 * Renders the button and, while open, its menu.
 *
 * @param props The component's props.
 * @returns The button and the menu.
 */
export function Menu({ label, trigger, triggerClassName, items, placement = 'below-end', menuClassName }: MenuProps) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
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
    const onKeyDown = (event: globalThis.KeyboardEvent): void => {
      if (event.key === 'Escape') {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    menu.current?.querySelector<HTMLElement>('[role="menuitem"]:not(:disabled)')?.focus();
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  /**
   * Moves focus between the items with the arrow keys.
   *
   * @param event The key press inside the menu.
   */
  function onMenuKey(event: KeyboardEvent<HTMLDivElement>): void {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') {
      return;
    }
    event.preventDefault();
    const enabled = [...(menu.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)') ?? [])];
    const at = enabled.findIndex((item) => item === document.activeElement);
    const step = event.key === 'ArrowDown' ? 1 : -1;
    enabled[(at + step + enabled.length) % enabled.length]?.focus();
  }

  return (
    <div ref={container} className="relative">
      <button
        ref={button}
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        className={triggerClassName}
        onClick={() => {
          setOpen(!open);
        }}
      >
        {trigger}
      </button>
      {open ? (
        <div
          ref={menu}
          id={menuId}
          role="menu"
          aria-label={label}
          className={cx('menu', PLACEMENTS[placement], menuClassName)}
          onKeyDown={onMenuKey}
          onClick={(event) => {
            if (event.target instanceof Element && event.target.closest('[role="menuitem"]') !== null) {
              setOpen(false);
              button.current?.focus();
            }
          }}
        >
          {Array.isArray(items)
            ? items.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  role="menuitem"
                  disabled={item.disabled}
                  className={cx('menu-item', item.danger === true && 'menu-item-danger')}
                  onClick={item.onSelect}
                >
                  {item.icon}
                  {item.label}
                </button>
              ))
            : items}
        </div>
      ) : null}
    </div>
  );
}

/** Props of {@link GitHubMark}. */
interface GitHubMarkProps {
  /** Classes that size the mark. */
  className?: string;
}

/**
 * Renders GitHub's mark, as decoration beside the word GitHub.
 *
 * The path is the `mark-github` icon of GitHub's Octicons (MIT).
 *
 * @param props The component's props.
 * @returns The mark.
 */
export function GitHubMark({ className }: GitHubMarkProps) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
