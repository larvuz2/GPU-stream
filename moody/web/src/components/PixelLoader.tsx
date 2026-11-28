/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A pixel loader on the page: one of the six patterns of `lib/pixelLoader.ts`, drawn as a 5 by 5
 * grid in a small tile (`.pixel-loader`).
 *
 * Each cell is an element that plays the keyframes its pattern names, for the loop and from the
 * point in it the pattern gives, so the animation is the stylesheet's and nothing here runs while
 * it plays. The loaders play at half the patterns' own speed ({@link SPEED}), which reads as work
 * going on rather than as hurry. With motion turned down a loader holds the frame it is on.
 *
 * A loader is decoration: what is at work, and what it is doing, is written beside it.
 * @module
 */
import { memo, type CSSProperties } from 'react';
import { cx } from '../lib/cx';
import { loaderCells, type LoaderCell, type LoaderStyle } from '../lib/pixelLoader';

/** How fast the loaders play, as a share of the patterns' own speed. */
const SPEED = 0.5;

/** The custom properties a cell's keyframes read its opacities from, in the keyframes' order. */
const LEVELS = [
  '--pixel-0',
  '--pixel-1',
  '--pixel-2',
  '--pixel-3',
  '--pixel-4',
  '--pixel-5',
  '--pixel-6',
  '--pixel-7',
] as const;

/**
 * Words a time for the stylesheet.
 *
 * @param seconds The time at full speed.
 * @returns It at the loaders' speed, in seconds to the millisecond.
 */
function time(seconds: number): string {
  return `${(seconds / SPEED).toFixed(3)}s`;
}

/**
 * Builds the inline style of one cell.
 *
 * @param cell The cell.
 * @param offset How far into its loop the loader starts, in seconds at full speed.
 * @returns The style.
 */
function cellStyle(cell: LoaderCell, offset: number): CSSProperties {
  const style: CSSProperties = {};
  if (!cell.visible) {
    style.visibility = 'hidden';
  }
  if (cell.opacity !== null) {
    style.opacity = cell.opacity;
  }
  if (cell.keyframes !== null) {
    style.animationName = cell.keyframes;
    style.animationTimingFunction = cell.timing;
    style.animationDelay = time(cell.delay - offset);
    style['--pixel-loop'] = time(cell.seconds);
    LEVELS.forEach((name, stage) => {
      const level = cell.levels[stage];
      if (level !== undefined) {
        style[name] = level;
      }
    });
  }
  return style;
}

/** Props of {@link PixelLoader}. */
interface PixelLoaderProps {
  /** The pattern to play. */
  style: LoaderStyle;
  /** How far into its loop the loader starts, in seconds at the pattern's own speed; 0 when left out. */
  offset?: number;
  /** Extra classes for the tile. */
  className?: string;
}

/**
 * Renders a pixel loader.
 *
 * @param props The component's props.
 * @returns The tile.
 */
export const PixelLoader = memo(function PixelLoader({ style, offset = 0, className }: PixelLoaderProps) {
  return (
    <span className={cx('pixel-loader', className)} data-loader={style} aria-hidden="true">
      {loaderCells(style).map((cell) => (
        <i key={cell.index} className="pixel-loader-cell" style={cellStyle(cell, offset)} />
      ))}
    </span>
  );
});
