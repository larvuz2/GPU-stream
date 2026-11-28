/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The CSS custom properties a pixel loader's cells set through `style` (`PixelLoader.tsx`), which
 * the loaders' keyframes read (`styles.css`).
 * @module
 */
import 'react';

declare module 'react' {
  interface CSSProperties {
    /** How long one loop of the cell's animation takes. */
    '--pixel-loop'?: string;
    /** The opacity the cell's keyframes read first. */
    '--pixel-0'?: number;
    /** The opacity the cell's keyframes read second. */
    '--pixel-1'?: number;
    /** The opacity the cell's keyframes read third. */
    '--pixel-2'?: number;
    /** The opacity the cell's keyframes read fourth. */
    '--pixel-3'?: number;
    /** The opacity the cell's keyframes read fifth. */
    '--pixel-4'?: number;
    /** The opacity the cell's keyframes read sixth. */
    '--pixel-5'?: number;
    /** The opacity the cell's keyframes read seventh. */
    '--pixel-6'?: number;
    /** The opacity the cell's keyframes read eighth. */
    '--pixel-7'?: number;
  }
}
