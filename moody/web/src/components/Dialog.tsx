/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A modal dialog on the platform's own `<dialog>`.
 *
 * `showModal()` gives what a hand-built modal has to imitate: the rest of the page is inert, so
 * focus stays inside; Escape closes it; and focus returns to what opened it. This component only
 * ties that to an `open` prop and adds closing on a click outside. That click has to begin outside
 * as well: a drag that selects the text of a field and is released past the dialog's edge is a
 * click on the backdrop to the browser, and must not throw the form away.
 *
 * A dialog is as tall as its content, padded, and scrolls as a whole. One that is a page of its
 * own (`page`) is as tall as the window allows and leaves the padding and the scrolling to its
 * content, which lays out its own regions; on a phone it fills the screen.
 * @module
 */
import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { cx } from '../lib/cx';

/** Props of {@link Dialog}. */
interface DialogProps {
  /** Whether the dialog is shown. */
  open: boolean;
  /** Called when the dialog closes, by Escape, the close button, or a click outside it. */
  onClose: () => void;
  /** The `id` of the element that titles the dialog. */
  labelledBy: string;
  /** Whether the dialog takes the wide layout, for content laid out in columns. */
  wide?: boolean;
  /** Whether the dialog is a page of its own, whose content pads and scrolls itself. */
  page?: boolean;
  /** The dialog's content, mounted only while it is open so its state starts fresh each time. */
  children: ReactNode;
}

/**
 * Renders a modal dialog with a close button.
 *
 * @param props The component's props.
 * @returns The dialog element, which the browser shows in its top layer while open.
 */
export function Dialog({ open, onClose, labelledBy, wide = false, page = false, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const pressedOutside = useRef(false);

  useEffect(() => {
    const dialog = ref.current;
    if (dialog === null) {
      return;
    }
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={labelledBy}
      className={cx('dialog', wide && 'dialog-wide', page && 'dialog-page')}
      onClose={onClose}
      // The dialog has no padding of its own, so only its backdrop reports it as the target.
      onPointerDown={(event) => {
        pressedOutside.current = event.target === event.currentTarget;
      }}
      onClick={(event) => {
        if (pressedOutside.current && event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      {open ? (
        <div className={page ? 'relative h-full' : 'relative p-6 sm:p-8'}>
          {children}
          {/* After the content, so the dialog opens with focus on its first control, not on this. */}
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="btn btn-quiet absolute top-3 right-3 size-9 px-0"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
      ) : null}
    </dialog>
  );
}
