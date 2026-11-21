/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Ambient types of the build: the environment variables Vite inlines, each optional because the
 * site builds and renders with none of them set, and the CSS custom properties the components set
 * through `style`.
 * @module
 */
import 'react';

declare global {
  /** The variables `lib/env.ts` reads; nothing else in the site touches `import.meta.env`. */
  interface ImportMetaEnv {
    /** The Supabase project's URL. */
    readonly VITE_SUPABASE_URL?: string;
    /** The Supabase project's anonymous (publishable) key. */
    readonly VITE_SUPABASE_PUBLISHABLE_KEY?: string;
    /** The control plane's base URL, with no trailing slash. */
    readonly VITE_LATHE_API_URL?: string;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

declare module 'react' {
  interface CSSProperties {
    /** The tint a card and everything inside it takes, an app's catalog color. */
    '--accent'?: string;
  }
}
