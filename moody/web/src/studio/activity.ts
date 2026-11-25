/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * How an activity an event names is shown: the expression the pixel eyes play for it, and the
 * label written beside them.
 *
 * Both come from the activity's identifier, one of `catalog.json`'s `activities`: the eyes play
 * the expression of that name (`lib/moodyEyes.ts`) and the label is the catalog's. An identifier
 * the eyes do not know plays as thinking, as the brand's library plays it, and still reads as the
 * catalog labels it.
 * @module
 */
import { activityLabel } from '../lib/catalog';
import { expressionOf, type Expression } from '../lib/moodyEyes';

/** An activity as the page shows it. */
export interface ShownActivity {
  /** The expression the eyes play. */
  expression: Expression;
  /** What the page calls it, such as "Searching". */
  label: string;
}

/**
 * Reads how an activity is shown.
 *
 * @param activity The activity's identifier, as an event names it.
 * @returns Its expression and its label.
 */
export function showActivity(activity: string): ShownActivity {
  const expression = expressionOf(activity);
  return { expression, label: activityLabel(activity) ?? activityLabel(expression) ?? expression };
}
