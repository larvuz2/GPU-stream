/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A discipline's formats as one quiet run of text, a dot between them, as both pages write them
 * small under a discipline's name.
 *
 * Where the run wraps it breaks between formats, never inside one: "3D object" or "Product shot"
 * moves to the next line whole.
 * @module
 */
import { Fragment } from 'react';

/** Props of {@link FormatLine}. */
interface FormatLineProps {
  /** The formats, in the catalog's order. */
  formats: readonly string[];
}

/**
 * Renders the formats.
 *
 * @param props The component's props.
 * @returns The run of text, to sit inside the caller's own paragraph or span.
 */
export function FormatLine({ formats }: FormatLineProps) {
  return formats.map((format, index) => (
    <Fragment key={format}>
      {index === 0 ? null : ' · '}
      <span className="whitespace-nowrap">{format}</span>
    </Fragment>
  ));
}
