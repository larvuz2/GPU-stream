/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The gallery's stand-in for the project's library: a file the person gives a card is kept in
 * the page.
 *
 * In the studio a card's `upload` input hands its file to the conversation, which stores it in
 * the project's library and answers with the entry it made. The gallery has no project, so
 * {@link keepInPage} answers in its place: it takes a moment over the file, as a network would,
 * so that the input's waiting state is seen; it refuses an empty file in a sentence, as the
 * library would refuse what it cannot hold; and it names the entry after the file and gives the
 * page an address of the file's own bytes, which lasts as long as the page does.
 * @module
 */
import { CATALOG } from '../catalog';
import type { Uploaded } from '../context';

/** How long the stand-in takes over a file, in milliseconds. */
const MOMENT_MS = 900;

/**
 * Takes a file as the library would, keeping it in the page.
 *
 * @param file The file the person gave.
 * @returns The entry it would have become.
 * @throws When the file is empty, with the reason in words.
 */
export async function keepInPage(file: File): Promise<Uploaded> {
  await new Promise((resolve) => window.setTimeout(resolve, MOMENT_MS));
  if (file.size === 0) {
    throw new Error(`${file.name} is empty, so there is nothing to add to the library.`);
  }
  const named = file.name.toLowerCase();
  const kind = Object.entries(CATALOG.media_kinds).find(([, endings]) => endings.some((ending) => named.endsWith(ending)));
  const stem = named.replace(/\.[^.]+$/, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return {
    tag: `@${stem === '' ? 'file' : stem}`,
    name: file.name,
    kind: kind?.[0] ?? 'file',
    url: URL.createObjectURL(file),
  };
}
