/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The icon each discipline is drawn with on both pages: pixel art in the wordmark's grid language.
 *
 * Every icon is twelve rows of twelve cells, written as rows of `1` and `0` the way the motion
 * library writes its shapes (`lib/moody.ts`), and drawn as squares in the current text color. On
 * a twelve-cell grid an icon is sharp at any multiple of twelve pixels, so it is sized `size-3`
 * beside small text and `size-6` and up where it leads. The icons are chosen here by discipline
 * identifier, since the catalog says what a discipline is and not how it looks; one the catalog
 * adds later is drawn as a plain block until it is given its own.
 * @module
 */
import { cx } from '../lib/cx';

/** The side of every icon's grid, in cells. */
const SIZE = 12;

/** The icon of each discipline, by catalog identifier. */
const ICONS: Readonly<Record<string, readonly string[]>> = {
  media: [
    '011001100000',
    '100110010000',
    '100110010000',
    '011001100000',
    '111111110000',
    '111111110001',
    '111111110011',
    '111111111111',
    '111111110011',
    '111111110001',
    '111111110000',
    '000000000000',
  ],
  music: [
    '000000000000',
    '000010000000',
    '000010001000',
    '001010001000',
    '001010101010',
    '101010101010',
    '101010101010',
    '001010101010',
    '001010001000',
    '000010001000',
    '000010000000',
    '000000000000',
  ],
  art: [
    '000000000000',
    '111111111111',
    '100000000001',
    '101100000001',
    '101100000001',
    '100000001001',
    '100000011101',
    '100100111111',
    '101110111111',
    '111111111111',
    '111111111111',
    '000000000000',
  ],
  design: [
    '000000001100',
    '000000011110',
    '000000111111',
    '000001111110',
    '000011111100',
    '000111111000',
    '001111110000',
    '010111100000',
    '010011000000',
    '100110000000',
    '111100000000',
    '000000000000',
  ],
  photography: [
    '000000000000',
    '000111100000',
    '111111111111',
    '100000000001',
    '100011110001',
    '100110011001',
    '100100001001',
    '100110011001',
    '100011110001',
    '100000000001',
    '111111111111',
    '000000000000',
  ],
  animation: [
    '001111111111',
    '001000000001',
    '111111111101',
    '100000000101',
    '100001000101',
    '100011100101',
    '100111110101',
    '100011100101',
    '100001000111',
    '100000000100',
    '111111111100',
    '000000000000',
  ],
  games: [
    '000000000000',
    '000000000000',
    '001111111100',
    '011111111110',
    '110100001011',
    '100010010001',
    '110100000101',
    '111111111111',
    '111100001111',
    '110000000011',
    '000000000000',
    '000000000000',
  ],
  architecture: [
    '000001100000',
    '000011110000',
    '000111111000',
    '001111111100',
    '011111111110',
    '111111111111',
    '000000000000',
    '011001100110',
    '011001100110',
    '011001100110',
    '000000000000',
    '111111111111',
  ],
  fashion: [
    '001100001100',
    '011110011110',
    '111111111111',
    '111111111111',
    '110111111011',
    '000111111000',
    '000111111000',
    '000111111000',
    '000111111000',
    '000111111000',
    '000111111000',
    '000111111000',
  ],
  writing: [
    '011111110000',
    '010000011000',
    '010000001100',
    '010000000110',
    '010111100010',
    '010000000010',
    '010111111010',
    '010000000010',
    '010111111010',
    '010000000010',
    '010000000010',
    '011111111110',
  ],
  technology: [
    '000000000000',
    '000000000000',
    '000000010000',
    '001000010100',
    '010000100010',
    '100000100001',
    '010001000010',
    '001001000100',
    '000010000000',
    '000000000000',
    '000000000000',
    '000000000000',
  ],
  experiences: [
    '000001000000',
    '000001000000',
    '000011100000',
    '000011100000',
    '001111111000',
    '111111111110',
    '001111111000',
    '000011100010',
    '000011100111',
    '000001000010',
    '000001000000',
    '000000000000',
  ],
};

/** The icon of a discipline that has none of its own yet. */
const FALLBACK: readonly string[] = [
  '000000000000',
  '000000000000',
  '001111111100',
  '001000000100',
  '001000000100',
  '001001100100',
  '001001100100',
  '001000000100',
  '001000000100',
  '001111111100',
  '000000000000',
  '000000000000',
];

/** Props of {@link DisciplineIcon}. */
interface DisciplineIconProps {
  /** The discipline's catalog identifier. */
  id: string;
  /** Classes that size and color the icon. */
  className?: string;
}

/**
 * Renders a discipline's icon, hidden from assistive technology since the name is always beside it.
 *
 * @param props The component's props.
 * @returns The icon.
 */
export function DisciplineIcon({ id, className }: DisciplineIconProps) {
  const art = Object.hasOwn(ICONS, id) ? (ICONS[id] ?? FALLBACK) : FALLBACK;
  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      fill="currentColor"
      shapeRendering="crispEdges"
      className={cx('flex-none', className)}
      aria-hidden="true"
    >
      {art.flatMap((row, y) =>
        Array.from(row).flatMap((cell, x) =>
          cell === '1' ? [<rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" />] : [],
        ),
      )}
    </svg>
  );
}
