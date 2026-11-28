/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The CSS custom properties the studio's layout sets through `style`.
 * @module
 */
import 'react';

declare module 'react' {
  interface CSSProperties {
    /** The width of the right column, which the person drags (`studio.css`). */
    '--pane-w'?: string;
    /** The shape of the frame the versions on the Screen play in, as width over height (`studio.css`). */
    '--versions-shape'?: number;
  }
}
