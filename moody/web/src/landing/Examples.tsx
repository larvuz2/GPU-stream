/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's examples: empty frames where finished projects will be shown, and a plain
 * statement that they are coming.
 *
 * Until there is real work to show, the gallery shows none: each tile is an empty frame, a video's
 * with a play button and a still's with an image mark, tinted by its discipline's main engine and
 * marked as coming soon. Nothing here is presented as made by anyone.
 * @module
 */
import { ImageIcon, Play } from 'lucide-react';
import { findDiscipline } from '../lib/catalog';
import { cx } from '../lib/cx';
import { SectionHeading } from './SectionHeading';
import { enginesOf } from './studio';

/** An empty frame of the gallery. */
interface Tile {
  /** The identifier of the discipline the piece will come from. */
  discipline: string;
  /** The piece's format, by its place in the discipline's formats in the catalog. */
  format: number;
  /** Whether the piece will be a video or a still. */
  kind: 'video' | 'image';
  /** The classes that size the frame in the grid, in cells; a frame without them takes one. */
  span: string;
}

/**
 * The gallery's frames, in reading order. In two columns and in four, their spans fill every row:
 * a wide feature and a tall vertical video beside two small frames, then a wide frame and two more.
 */
const TILES: readonly Tile[] = [
  { discipline: 'media', format: 0, kind: 'video', span: 'col-span-2 row-span-2' },
  { discipline: 'media', format: 3, kind: 'video', span: 'row-span-2' },
  { discipline: 'design', format: 0, kind: 'image', span: '' },
  { discipline: 'animation', format: 0, kind: 'video', span: '' },
  { discipline: 'games', format: 1, kind: 'video', span: 'col-span-2' },
  { discipline: 'architecture', format: 1, kind: 'image', span: '' },
  { discipline: 'art', format: 0, kind: 'image', span: '' },
];

/**
 * Renders the examples section.
 *
 * @returns The section.
 */
export function Examples() {
  return (
    <section id="examples" className="section" aria-labelledby="examples-title">
      <div className="shell">
        <SectionHeading
          id="examples-title"
          eyebrow="Examples"
          title="Examples coming soon"
          lede="Finished projects, from the first sentence to the export, will be shown here. Until they are ready, these frames stay empty."
        />
        <ul className="mt-12 grid auto-rows-[8.5rem] grid-cols-2 gap-3 sm:auto-rows-[11rem] sm:gap-4 lg:grid-cols-4">
          {TILES.map((tile) => {
            const discipline = findDiscipline(tile.discipline);
            const kind = tile.kind === 'video' ? 'Video' : 'Still';
            const Icon = tile.kind === 'video' ? Play : ImageIcon;
            return (
              <li
                key={`${tile.discipline}-${String(tile.format)}`}
                className={cx('example-tile', tile.span)}
                style={{ '--accent': discipline === undefined ? undefined : enginesOf(discipline)[0]?.accent }}
              >
                <span className="example-mark" aria-hidden="true">
                  <Icon className={cx('size-5', tile.kind === 'video' && 'translate-x-px fill-current')} />
                </span>
                <span className="absolute inset-x-3 bottom-3 flex items-end justify-between gap-2 text-xs">
                  <span className="min-w-0 truncate font-semibold">
                    {discipline?.name ?? 'Example'}
                    <span className="font-normal text-muted"> · {discipline?.formats[tile.format] ?? kind}</span>
                    <span className="sr-only"> ({kind.toLowerCase()})</span>
                  </span>
                  <span className="flex-none text-faint">Soon</span>
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
