/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Copying to the clipboard: a button that confirms it, and the terminal block that shows a
 * command with one.
 * @module
 */
import { Fragment, useEffect, useRef, useState } from 'react';
import { Check, Copy, TriangleAlert } from 'lucide-react';
import { cx } from '../lib/cx';

/** How long the button keeps saying that it copied. */
const CONFIRMATION_MS = 2000;

/** Props of {@link CopyButton}. */
interface CopyButtonProps {
  /** The text to copy. */
  text: string;
  /** The button's label before it is pressed. */
  label?: string;
  /** Extra classes for the button. */
  className?: string;
}

/**
 * Renders a button that copies text and says so for a moment.
 *
 * The clipboard is refused outside a secure context and when the page lacks focus; the button then
 * says the copy failed instead of pretending, and the text beside it stays selectable.
 *
 * @param props The component's props.
 * @returns The button.
 */
export function CopyButton({ text, label = 'Copy', className }: CopyButtonProps) {
  const [outcome, setOutcome] = useState<'idle' | 'copied' | 'failed'>('idle');
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current !== null) {
        window.clearTimeout(timer.current);
      }
    },
    [],
  );

  /** Copies the text and shows the outcome until the confirmation times out. */
  async function copy(): Promise<void> {
    let next: 'copied' | 'failed' = 'copied';
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      next = 'failed';
    }
    setOutcome(next);
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
    }
    timer.current = window.setTimeout(() => {
      setOutcome('idle');
    }, CONFIRMATION_MS);
  }

  const Icon = outcome === 'copied' ? Check : outcome === 'failed' ? TriangleAlert : Copy;
  return (
    <button
      type="button"
      onClick={() => {
        void copy();
      }}
      className={cx('btn btn-ghost btn-sm', outcome === 'copied' && 'text-ok', className)}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      <span aria-live="polite">{outcome === 'copied' ? 'Copied' : outcome === 'failed' ? 'Copy failed' : label}</span>
    </button>
  );
}

/** Props of {@link CommandBlock}. */
interface CommandBlockProps {
  /** The command to show and copy. */
  command: string;
  /** What the block's title bar says the command is for. */
  title: string;
  /** Extra classes for the block. */
  className?: string;
}

/**
 * Renders a shell command in a terminal-styled block with a copy button.
 *
 * The command wraps rather than scrolls, so all of it is readable on a phone. Each argument is a
 * box of its own, so a line breaks between arguments and never inside one, such as after the
 * hyphens of a flag, unless the argument alone is wider than the block. The text stays the
 * command's own characters, so selecting it by hand copies what the button does.
 *
 * @param props The component's props.
 * @returns The block.
 */
export function CommandBlock({ command, title, className }: CommandBlockProps) {
  return (
    <div className={cx('terminal', className)}>
      <div className="flex items-center gap-3 border-b border-line py-2 pr-2 pl-4">
        <span className="flex gap-1.5" aria-hidden="true">
          <i className="size-2.5 rounded-full bg-white/15" />
          <i className="size-2.5 rounded-full bg-white/15" />
          <i className="size-2.5 rounded-full bg-white/15" />
        </span>
        <span className="min-w-0 flex-1 truncate text-xs font-medium text-faint">{title}</span>
        <CopyButton text={command} />
      </div>
      <pre className="p-4 text-left">
        <code>
          <span className="text-ember-300 select-none" aria-hidden="true">
            ${' '}
          </span>
          {command.split(' ').map((argument, index) => (
            // The arguments of one command never reorder, so their position identifies them.
            <Fragment key={index}>
              {index > 0 ? ' ' : null}
              <span className="inline-block max-w-full align-top">{argument}</span>
            </Fragment>
          ))}
        </code>
      </pre>
    </div>
  );
}
