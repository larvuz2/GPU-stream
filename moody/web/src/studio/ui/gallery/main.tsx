/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Entry point of the cards' development gallery (`/app/cards/`), a page of its own that nothing
 * in the product links to. It needs no account and sends no request: the cards are fixtures
 * (`examples.ts`) over the site's own artwork.
 * @module
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../../../styles.css';
import '../../studio.css';
import { Gallery } from './Gallery';

const root = document.getElementById('root');
if (root !== null) {
  createRoot(root).render(
    <StrictMode>
      <Gallery />
    </StrictMode>,
  );
}
