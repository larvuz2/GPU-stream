/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Entry point of the landing page (`/`): mounts {@link Landing} under `#root`.
 * @module
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../styles.css';
import { Landing } from './Landing';

const root = document.getElementById('root');
if (root !== null) {
  createRoot(root).render(
    <StrictMode>
      <Landing />
    </StrictMode>,
  );
}
