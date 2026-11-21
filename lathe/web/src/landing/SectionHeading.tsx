/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The heading every section of the landing page opens with.
 * @module
 */
import { cx } from '../lib/cx';

/** Props of {@link SectionHeading}. */
interface SectionHeadingProps {
  /** The `id` of the title, which the section is labeled by. */
  id: string;
  /** The short label above the title. */
  eyebrow: string;
  /** The section's title. */
  title: string;
  /** The sentence or two under the title. */
  lede?: string;
  /** Whether the heading is set flush left instead of centered. */
  start?: boolean;
}

/**
 * Renders a section's eyebrow, title, and lede.
 *
 * @param props The component's props.
 * @returns The heading block.
 */
export function SectionHeading({ id, eyebrow, title, lede, start = false }: SectionHeadingProps) {
  return (
    <div className={cx('max-w-3xl', !start && 'mx-auto text-center')}>
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={id} className="display mt-4 text-[2rem] sm:text-5xl">
        {title}
      </h2>
      {lede === undefined ? null : <p className="lede mt-5 text-[1.0625rem] sm:text-lg">{lede}</p>}
    </div>
  );
}
