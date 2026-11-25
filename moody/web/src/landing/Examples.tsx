/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's examples: the frame the product video plays in, and empty frames where
 * finished projects will be shown, with a plain statement that they are coming.
 *
 * The video frame is built around one value, `PRODUCT_VIDEO` in `lib/media.ts`: while it is `null`
 * the frame shows its poster under a play button marked as coming soon, and once it names a file
 * the same button plays it in place. Until there is real work to show, the gallery shows none:
 * each tile is an empty frame, a video's with a play button and a still's with an image mark, led
 * by its discipline's pixel icon and marked as coming soon. Nothing here is presented as made by
 * anyone.
 * @module
 */
import { useState } from 'react';
import { ImageIcon, Play } from 'lucide-react';
import { ArtImage } from '../components/Art';
import { DisciplineIcon } from '../components/DisciplineIcon';
import { findDiscipline } from '../lib/catalog';
import { cx } from '../lib/cx';
import { PRODUCT_VIDEO, VIDEO_POSTER } from '../lib/media';
import { SectionHeading } from './SectionHeading';

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
          lede="The product video and finished projects, from the first sentence to the export, will be shown here. Until they are ready, these frames stay empty."
        />
        <ProductVideo />
        <ul className="mt-6 grid auto-rows-[8.5rem] grid-cols-2 gap-3 sm:auto-rows-[11rem] sm:gap-4 lg:grid-cols-4">
          {TILES.map((tile) => {
            const discipline = findDiscipline(tile.discipline);
            const kind = tile.kind === 'video' ? 'Video' : 'Still';
            const Icon = tile.kind === 'video' ? Play : ImageIcon;
            return (
              <li key={`${tile.discipline}-${String(tile.format)}`} className={cx('example-tile', tile.span)}>
                <span className="example-mark" aria-hidden="true">
                  <Icon className={cx('size-5', tile.kind === 'video' && 'translate-x-px fill-current')} />
                </span>
                <span className="absolute inset-x-3 bottom-3 flex items-end justify-between gap-2 text-xs">
                  <span className="flex min-w-0 items-center gap-2 font-semibold">
                    <DisciplineIcon id={tile.discipline} className="size-3" />
                    <span className="min-w-0 truncate">
                      {discipline?.name ?? 'Example'}
                      <span className="font-normal text-muted"> · {discipline?.formats[tile.format] ?? kind}</span>
                      <span className="sr-only"> ({kind.toLowerCase()})</span>
                    </span>
                  </span>
                  <span className="mono flex-none text-faint uppercase">Soon</span>
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

/**
 * Renders the 16:9 frame of the product video: the poster and a play button that plays the video
 * in place, or says it is coming while there is none.
 *
 * @returns The frame.
 */
function ProductVideo() {
  const [playing, setPlaying] = useState(false);
  const video = PRODUCT_VIDEO;
  return (
    <figure className="mt-12">
      <div className="video-frame bloom">
        <div className="art aspect-video overflow-hidden rounded-[inherit] lg:aspect-[21/9]">
          {playing && video !== null ? (
            <video
              src={video}
              poster={VIDEO_POSTER}
              className="absolute inset-0 z-10 size-full bg-black object-cover"
              controls
              autoPlay
              playsInline
            />
          ) : (
            <>
              <ArtImage src={VIDEO_POSTER} width={1280} height={720} />
              <div className="video-scrim" aria-hidden="true" />
              {video === null ? (
                <span className="play-button" aria-hidden="true">
                  <Play className="size-7 translate-x-0.5 fill-current" />
                </span>
              ) : (
                <button
                  type="button"
                  className="play-button"
                  aria-label="Play the product video"
                  onClick={() => {
                    setPlaying(true);
                  }}
                >
                  <Play className="size-7 translate-x-0.5 fill-current" aria-hidden="true" />
                </button>
              )}
              <span className="pill absolute bottom-3.5 left-3.5 z-10 text-fg">
                {video === null ? 'Product video coming soon' : 'Watch the studio at work'}
              </span>
            </>
          )}
        </div>
      </div>
    </figure>
  );
}
