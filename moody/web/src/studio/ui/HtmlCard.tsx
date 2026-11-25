/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * An `html` card: a document the agent wrote, for what the catalog cannot express.
 * @module
 */
import type { UiCardProps } from './UiCard';

/**
 * Renders the stand-in of an `html` card.
 *
 * @param props The component's props.
 * @returns A line in the card's place.
 */
export function HtmlCard({ ui }: UiCardProps) {
  return <p className="ui-text-muted">This page does not run {ui.title} yet.</p>;
}
