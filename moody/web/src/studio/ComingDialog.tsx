/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The preview of a shortcut that is not available yet: what to expect once it opens, as a few
 * quiet cards (`preview` of the shortcut in `catalog.shortcuts`).
 *
 * Each card is a picture with rounded corners under a black layer that deepens toward its foot,
 * where a tool's name and a line on what it is for are read, with a small tag of where it stands.
 * The pictures are scenes of what the tools are for, made for the site: none shows a product's
 * interface or mark. A card is not a control, nothing here starts anything, and the dialog says
 * in a line that none of it runs yet.
 * @module
 */
import { useId } from 'react';
import { Dialog } from '../components/Dialog';
import { ShortcutIcon } from '../components/DisciplineIcon';
import type { Shortcut } from '../lib/catalog';
import { catalogImage } from '../lib/media';

/** Props of {@link ComingDialog}. */
interface ComingDialogProps {
  /** The shortcut whose preview is shown, or `null` while none is. */
  shortcut: Shortcut | null;
  /** Closes the dialog. */
  onClose: () => void;
}

/**
 * Renders the dialog.
 *
 * @param props The component's props.
 * @returns The dialog.
 */
export function ComingDialog({ shortcut, onClose }: ComingDialogProps) {
  const titleId = useId();
  return (
    <Dialog open={shortcut !== null} onClose={onClose} labelledBy={titleId} wide>
      {shortcut === null ? null : (
        <div>
          <h2 id={titleId} className="display flex items-center gap-2.5 pr-10 text-[1.6rem]">
            <span className="icon-tile size-9 rounded-xl">
              <ShortcutIcon shortcut={shortcut} className="size-3" />
            </span>
            {shortcut.label}
          </h2>
          <p className="lede mt-2 text-sm">What to expect here. None of it runs yet.</p>
          <ul className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {(shortcut.preview ?? []).map((card) => (
              <li key={card.name} className="coming-card">
                <img src={catalogImage(card.image)} alt="" width={1200} height={800} decoding="async" />
                <span className="coming-tag">{card.tag}</span>
                <div className="coming-text">
                  <h3 className="text-[0.9375rem] leading-tight font-semibold tracking-tight">{card.name}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-muted">{card.line}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Dialog>
  );
}
