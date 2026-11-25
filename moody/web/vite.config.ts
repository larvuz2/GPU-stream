/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Vite configuration of the site: a two-page app whose landing page (`index.html`) and studio
 * (`app/index.html`) are separate entries, so a visitor to the landing page downloads none of the
 * studio.
 *
 * The catalog beside this package (`../catalog.json`) names the product, so the static HTML of both
 * pages carries `%BRAND%` and `%LIVE_APPS%` tokens that {@link catalogHtml} fills from it at build
 * time: a rename stays one edit, and the title and description are in the document before any
 * script runs.
 * @module
 */
import { existsSync } from 'node:fs';
import path from 'node:path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, type HtmlTagDescriptor, type Plugin } from 'vite';
import catalog from '../catalog.json' with { type: 'json' };

const root = import.meta.dirname;

/** The art a link preview shows, relative to `public/`. */
const SOCIAL_IMAGE = 'media/hero.webp';

/**
 * The names of the apps a visitor can launch today, as prose ("Blender", "Blender and Godot").
 *
 * @returns The list, or a generic phrase when the catalog has no available app.
 */
function liveAppNames(): string {
  const names = catalog.apps.filter((app) => app.status === 'available').map((app) => app.name);
  return names.length === 0 ? 'creative apps' : new Intl.ListFormat('en-US', { type: 'conjunction' }).format(names);
}

/**
 * The Open Graph tags that need the site's public address.
 *
 * A link preview only takes an absolute image URL, and the address is known only where the host
 * provides it (Netlify exports the site's as `URL`), so a build elsewhere leaves these tags out
 * rather than pointing at a guess.
 *
 * @returns The tags, or none when no address is known or the image was not delivered.
 */
function socialTags(): HtmlTagDescriptor[] {
  const site = process.env.URL;
  if (site === undefined || !site.startsWith('https://') || !existsSync(path.join(root, 'public', SOCIAL_IMAGE))) {
    return [];
  }
  const origin = site.replace(/\/+$/, '');
  return [
    { tag: 'meta', attrs: { property: 'og:url', content: `${origin}/` }, injectTo: 'head' },
    { tag: 'meta', attrs: { property: 'og:image', content: `${origin}/${SOCIAL_IMAGE}` }, injectTo: 'head' },
    { tag: 'meta', attrs: { name: 'twitter:card', content: 'summary_large_image' }, injectTo: 'head' },
  ];
}

/**
 * Fills the catalog tokens of a page's HTML and adds the landing page's social tags.
 *
 * @returns The Vite plugin.
 */
function catalogHtml(): Plugin {
  return {
    name: 'catalog-html',
    transformIndexHtml: {
      order: 'pre',
      handler: (html, context) => ({
        html: html.replaceAll('%BRAND%', catalog.brand).replaceAll('%LIVE_APPS%', liveAppNames()),
        tags: context.path === '/index.html' ? socialTags() : [],
      }),
    },
  };
}

export default defineConfig({
  // A path that is neither page is a 404, not the landing page.
  appType: 'mpa',
  plugins: [catalogHtml(), react(), tailwindcss()],
  server: {
    // The catalog lives one directory above this package.
    fs: { allow: ['..'] },
  },
  build: {
    target: 'es2022',
    rolldownOptions: {
      input: {
        landing: path.resolve(root, 'index.html'),
        studio: path.resolve(root, 'app/index.html'),
        // The development gallery of the agent's interactive cards, which nothing links to.
        cards: path.resolve(root, 'app/cards/index.html'),
      },
      output: {
        // The libraries change far less often than the pages, so each gets a chunk whose hashed
        // name, and so a visitor's cached copy, outlives a release of the site.
        codeSplitting: {
          groups: [
            { name: 'react', test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/ },
            { name: 'supabase', test: /node_modules[\\/]@supabase[\\/]/ },
            // Fetched only when a card shows a 3D model (`src/studio/ui/components/Model.tsx`).
            { name: 'three', test: /node_modules[\\/]three[\\/]/ },
          ],
        },
      },
    },
  },
});
