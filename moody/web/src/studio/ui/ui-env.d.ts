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
    /** The color one mark of a chart is drawn in. */
    '--ui-mark'?: string;
  }
}
