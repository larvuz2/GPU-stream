/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The heading every section of the landing page opens with: a label set like a display's readout
 * behind one lit pixel, the title, and a sentence or two, flush left.
 * @module
 */

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
}

/**
 * Renders a section's eyebrow, title, and lede.
 *
 * @param props The component's props.
 * @returns The heading block.
 */
export function SectionHeading({ id, eyebrow, title, lede }: SectionHeadingProps) {
  return (
    <div className="max-w-3xl">
      <p className="eyebrow">
        <span className="size-2 bg-fg" aria-hidden="true" />
        {eyebrow}
      </p>
      <h2 id={id} className="display mt-5 text-[2.1rem] sm:text-5xl lg:text-[3.5rem]">
        {title}
      </h2>
      {lede === undefined ? null : <p className="lede mt-5 max-w-2xl text-[1.0625rem] sm:text-lg">{lede}</p>}
    </div>
  );
}
