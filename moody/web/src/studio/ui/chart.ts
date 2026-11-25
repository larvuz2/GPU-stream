/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The arithmetic of a card's chart: its points, the round numbers its axis is ticked at, how a
 * value is written, and the path of a line.
 *
 * A chart shows one series, `[{label, value}]`. The axis runs from zero (or the least value,
 * where one is negative) to the first round number at or past the greatest, in steps of 1, 2,
 * or 5 times a power of ten, so its ticks are numbers a person reads at a glance. A value is
 * written in full where it is short and compactly (12.5K, 4.2M) on an axis, with the chart's
 * unit: a leading `$`, or anything else after the number.
 * @module
 */
import { isNumber, isString } from '../../lib/narrow';
import { items, type UiNode } from './tree';

/** One value of a chart. */
export interface Point {
  label: string;
  value: number;
}

/** How many parts a share bar shows before the smallest are folded into one. */
export const SHARE_PARTS = 6;

/** What the folded parts of a share bar are called. */
const OTHER = 'Other';

/**
 * Reads a chart's points.
 *
 * @param node The `chart` component.
 * @returns Its points, in the card's order.
 */
export function points(node: UiNode): Point[] {
  return items(node, 'data', 'point').flatMap((item): Point[] =>
    isString(item.label) && isNumber(item.value) ? [{ label: item.label, value: item.value }] : [],
  );
}

/**
 * The parts of one whole, largest first, with the tail folded into "Other".
 *
 * @param data The chart's points; a part of nothing or less is left out.
 * @returns At most {@link SHARE_PARTS} parts.
 */
export function parts(data: readonly Point[]): Point[] {
  const ranked = data.filter((point) => point.value > 0).sort((one, other) => other.value - one.value);
  if (ranked.length <= SHARE_PARTS) {
    return ranked;
  }
  const kept = ranked.slice(0, SHARE_PARTS - 1);
  const rest = ranked.slice(SHARE_PARTS - 1).reduce((sum, point) => sum + point.value, 0);
  return [...kept, { label: OTHER, value: rest }];
}

/**
 * The round numbers an axis is ticked at.
 *
 * @param low The least value shown.
 * @param high The greatest value shown.
 * @param count About how many ticks to aim for.
 * @returns The ticks, from the first round number at or under `low` to the first at or over `high`.
 */
export function ticks(low: number, high: number, count = 4): number[] {
  const span = high - low;
  if (!(span > 0)) {
    return [low, low + 1];
  }
  const rough = span / count;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((factor) => factor * power).find((candidate) => candidate >= rough) ?? rough;
  const first = Math.floor(low / step) * step;
  const last = Math.ceil(high / step) * step;
  const found: number[] = [];
  for (let tick = first; tick <= last + step / 2; tick += step) {
    // The sum of binary steps drifts; a tick is the round number it stands for.
    found.push(Math.round(tick / step) * step);
  }
  return found;
}

/**
 * Writes a value with the chart's unit.
 *
 * @param value The value.
 * @param unit The unit: `$` leads the number, anything else follows it.
 * @param compact Whether to shorten a large number, as an axis does.
 * @returns The words.
 */
export function amount(value: number, unit: string | null, compact = false): string {
  const number = new Intl.NumberFormat('en-US', {
    notation: compact && Math.abs(value) >= 10_000 ? 'compact' : 'standard',
    maximumFractionDigits: Math.abs(value) < 10 ? 2 : 1,
  }).format(value);
  if (unit === null) {
    return number;
  }
  return unit === '$' ? `$${number}` : `${number}${unit}`;
}

/**
 * Writes a share of a whole.
 *
 * @param part The part.
 * @param whole The whole.
 * @returns The share as a whole percentage, or "<1%" for a sliver.
 */
export function share(part: number, whole: number): string {
  const percent = whole > 0 ? (part / whole) * 100 : 0;
  return percent > 0 && percent < 1 ? '<1%' : `${Math.round(percent)}%`;
}

/**
 * Writes the SVG path through a line's points.
 *
 * @param coordinates The points, as x and y in the plot.
 * @returns The path's data.
 */
export function linePath(coordinates: readonly (readonly [number, number])[]): string {
  return coordinates.map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
}
