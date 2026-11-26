/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A pixel icon a card draws on a tile, in the wordmark's grid language.
 *
 * The icon arrives as rows of `1` and `0`, the way the site writes its own
 * (`components/DisciplineIcon.tsx`), and is drawn as squares in the current text color with crisp
 * edges. A card's icon may be eight to sixteen cells a side, and a grid is only sharp at a whole
 * number of pixels per cell, so the icon is sized by its cells ({@link CELL} pixels each) rather
 * than stretched to its box.
 * @module
 */

/** The side of one cell, in CSS pixels. */
const CELL = 4;

/** Props of {@link PixelIcon}. */
interface PixelIconProps {
  /** The icon: a square of rows of `0` and `1`. */
  art: readonly string[];
}

/**
 * Renders a pixel icon, hidden from assistive technology since its tile's words are beside it.
 *
 * @param props The component's props.
 * @returns The drawing.
 */
export function PixelIcon({ art }: PixelIconProps) {
  const side = art.length;
  return (
    <svg
      viewBox={`0 0 ${side} ${side}`}
      width={side * CELL}
      height={side * CELL}
      fill="currentColor"
      shapeRendering="crispEdges"
      className="flex-none"
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
