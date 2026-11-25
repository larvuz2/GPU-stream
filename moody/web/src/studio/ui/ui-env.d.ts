/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The CSS custom properties the cards' components set through `style` (`ui.css` reads them).
 * @module
 */
import 'react';

declare module 'react' {
  interface CSSProperties {
    /** Where the lit part of a slider's track starts and ends, as percentages of the track. */
    '--ui-from'?: string;
    '--ui-to'?: string;
    /** How a layer of a composite blends with the layers under it: one of the catalog's `blends`. */
    '--ui-blend'?: string;
  }
}
