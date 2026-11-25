/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The adjustments a picture takes, as what the browser draws them with.
 *
 * A card's `adjust` maps an adjustment of the catalog (`moody/ui.json`, `adjustments`) to an
 * amount, a number or `"$id"` to follow an input. {@link lookOf} turns that map into a
 * {@link Look}: CSS filter functions for what CSS has (brightness, contrast, saturation, hue,
 * sepia, blur), one color matrix for what it lacks (warmth and tint scale the channels against
 * each other, fade lifts the blacks), and the strength of two overlays (grain and vignette).
 * Everything is a filter on the element or a layer over it, so a look follows a slider at the
 * display's frame rate with no pixel read, and works on a picture from another origin, which a
 * canvas could not read back.
 *
 * `DRAW` has one entry per adjustment of the catalog and fails to compile while one is missing.
 * An amount outside its range is clamped to it, and one that is not a number counts as the
 * adjustment's default, so a look never breaks on a value an input does not hold yet. The
 * adjustments are applied in the catalog's order, so a look is the same however a card lists them.
 * @module
 */
import { isNumber, isRecord } from '../../lib/narrow';
import { ADJUSTMENT_NAMES, CATALOG, isAdjustmentName, type AdjustmentName } from './catalog';
import { follow, type UiState } from './tree';
import { clamp } from './values';

/** What a picture is drawn with. */
export interface Look {
  /** CSS filter functions, in order. */
  filters: string[];
  /** The scale of the red, green, and blue channels. */
  scale: [number, number, number];
  /** What is added to every channel, 0 to 1. */
  lift: number;
  /** How strong the grain is, 0 to 1. */
  grain: number;
  /** How dark the corners are, 0 to 1. */
  vignette: number;
}

/** How far warmth moves red against blue at its most, as a share of the channel. */
const WARMTH_SHIFT = 0.28;

/** How far tint moves green against red and blue at its most. */
const TINT_SHIFT = 0.22;

/** How far fade lifts the blacks at its most, and how much contrast it gives up doing it. */
const FADE_LIFT = 0.22;

/** What each adjustment adds to a look, for an amount inside its range. */
const DRAW: Record<AdjustmentName, (amount: number, look: Look) => void> = {
  brightness: (amount, look) => {
    look.filters.push(`brightness(${1 + amount / 100})`);
  },
  contrast: (amount, look) => {
    look.filters.push(`contrast(${1 + amount / 100})`);
  },
  saturation: (amount, look) => {
    look.filters.push(`saturate(${1 + amount / 100})`);
  },
  hue: (amount, look) => {
    look.filters.push(`hue-rotate(${amount}deg)`);
  },
  warmth: (amount, look) => {
    const shift = (amount / 100) * WARMTH_SHIFT;
    look.scale[0] *= 1 + shift;
    look.scale[1] *= 1 + shift * 0.15;
    look.scale[2] *= 1 - shift;
  },
  tint: (amount, look) => {
    const shift = (amount / 100) * TINT_SHIFT;
    look.scale[0] *= 1 + shift * 0.5;
    look.scale[1] *= 1 - shift;
    look.scale[2] *= 1 + shift * 0.5;
  },
  fade: (amount, look) => {
    const lift = (amount / 100) * FADE_LIFT;
    look.scale = [look.scale[0] * (1 - lift), look.scale[1] * (1 - lift), look.scale[2] * (1 - lift)];
    look.lift += lift;
  },
  sepia: (amount, look) => {
    look.filters.push(`sepia(${amount / 100})`);
  },
  blur: (amount, look) => {
    look.filters.push(`blur(${amount}px)`);
  },
  grain: (amount, look) => {
    look.grain = amount / 100;
  },
  vignette: (amount, look) => {
    look.vignette = amount / 100;
  },
};

/**
 * Reads a card's `adjust` into a look.
 *
 * @param adjust The component's `adjust` property.
 * @param state The card's values, for the amounts that follow an input.
 * @returns The look, which is plain where `adjust` names nothing.
 */
export function lookOf(adjust: unknown, state: UiState): Look {
  const look: Look = { filters: [], scale: [1, 1, 1], lift: 0, grain: 0, vignette: 0 };
  if (!isRecord(adjust)) {
    return look;
  }
  // In the catalog's order, whatever order the card wrote them in: the order filters are applied in shows.
  for (const name of ADJUSTMENT_NAMES) {
    const spec = CATALOG.adjustments[name];
    if (spec === undefined || !isAdjustmentName(name) || !(name in adjust)) {
      continue;
    }
    const amount = follow(adjust[name], state);
    const within = clamp(isNumber(amount) ? amount : spec.default, spec.min, spec.max);
    if (within !== spec.default) {
      DRAW[name](within, look);
    }
  }
  return look;
}

/**
 * Whether a look needs the color matrix.
 *
 * @param look The look.
 * @returns `true` where a channel is scaled or lifted.
 */
export function hasMatrix(look: Look): boolean {
  return look.lift !== 0 || look.scale.some((channel) => channel !== 1);
}

/**
 * Writes a look's color matrix for an SVG `feColorMatrix`.
 *
 * @param look The look.
 * @returns The matrix's twenty values, row by row.
 */
export function matrixOf(look: Look): string {
  const [red, green, blue] = look.scale;
  const lift = look.lift;
  return [red, 0, 0, 0, lift, 0, green, 0, 0, lift, 0, 0, blue, 0, lift, 0, 0, 0, 1, 0]
    .map((value) => String(Math.round(value * 1000) / 1000))
    .join(' ');
}
