/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The stand-in of a component the catalog defines and this build does not draw yet.
 * @module
 */
import type { ViewProps } from '../view';

/**
 * Renders a line that names the component in its place.
 *
 * @param props The component's props.
 * @returns The line.
 */
export function Pending({ node }: ViewProps) {
  return <p className="ui-text-muted">This page does not show a {node.type} yet.</p>;
}
