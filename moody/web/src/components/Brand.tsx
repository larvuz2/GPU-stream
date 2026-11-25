/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The product's own mark: the pixel wordmark, and its two eyes where the whole word does not fit.
 *
 * The wordmark is lowercase pixels (`lib/moody.ts`), drawn in the current text color, and alive:
 * {@link Brand} carries it as a canvas with the header behavior (`MoodyLogo`). {@link BrandMark} is
 * the eyes alone as a static drawing, for a dialog's head or a collapsed sidebar. The name a
 * person reads or hears is the catalog's.
 * @module
 */
import { brand } from '../lib/catalog';
import { cx } from '../lib/cx';
import { RAW } from '../lib/moody';
import { MoodyLogo } from './Moody';

/** The grid columns the two eyes span, and the rows, with a cell of room around them. */
const EYES = { left: 6, top: 1, cols: 11, rows: 6 } as const;

/** The wordmark's cells that belong to its eyes, the two o's. */
const EYE_CELLS = RAW.filter(([x]) => (x >= 7 && x <= 10) || (x >= 12 && x <= 15));

/** Props of {@link BrandMark}. */
interface BrandMarkProps {
  /** Classes that size the mark. */
  className?: string;
}

/**
 * Renders the mark alone, the wordmark's two eyes, as decoration.
 *
 * @param props The component's props.
 * @returns The mark.
 */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg
      viewBox={`${EYES.left} ${EYES.top} ${EYES.cols} ${EYES.rows}`}
      fill="currentColor"
      shapeRendering="crispEdges"
      className={className}
      aria-hidden="true"
    >
      {EYE_CELLS.map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" />
      ))}
    </svg>
  );
}

/** Props of {@link Brand}. */
interface BrandProps {
  /** Where the logo links to. */
  href: string;
  /** Extra classes for the link. */
  className?: string;
  /** Whether the wordmark plays the moods the page asks for (`lib/mood.ts`). */
  reactive?: boolean;
}

/**
 * Renders the wordmark as a link home, named by the product's name.
 *
 * @param props The component's props.
 * @returns The link.
 */
export function Brand({ href, className, reactive }: BrandProps) {
  return (
    <a href={href} aria-label={`${brand} home`} className={cx('inline-flex items-center rounded-md', className)}>
      <MoodyLogo className="h-12" reactive={reactive} />
    </a>
  );
}
