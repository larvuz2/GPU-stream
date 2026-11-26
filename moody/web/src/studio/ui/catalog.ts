/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The catalog of interactive cards, read from `moody/ui.json`, the file the control plane checks
 * every card against (`moody/control/genui.py`).
 *
 * Nothing here repeats a value of that file. A component's name is a key of it
 * ({@link ComponentType}), so the table of renderers (`registry.ts`) fails to compile while a
 * component the catalog defines has none; a property's default, an adjustment's range, and every
 * limit are read from it where they are used. The compiler checks the file against
 * {@link UiCatalog} at the import, so a change of its shape fails the build instead of rendering
 * a hole.
 * @module
 */
import raw from '../../../../ui.json';

/** How one property of a component, or of a list item, is defined. */
export interface PropSpec {
  /** What the value is: `string`, `number`, `enum`, `media`, `list`, and the rest `genui.py` checks. */
  kind: string;
  /** Whether a card has to give it. */
  required?: boolean;
  /** Whether it also takes `"$id"`, to follow an input. */
  bind?: boolean;
  /** What it is where a card leaves it out. */
  default?: unknown;
  /** The least and the most a number may be. */
  min?: number;
  max?: number;
  /** What an enumeration may be: the values, or the name of the catalog's list or table of them. */
  values?: string | string[];
  /** What a list holds: the name of a shape, or one property's definition. */
  of?: string | PropSpec;
}

/** One component of the catalog. */
export interface ComponentSpec {
  /** `layout`, `content`, or `input`. */
  group: string;
  /** What it is, in a sentence. */
  doc: string;
  /** Its properties, by name. */
  props: Record<string, PropSpec>;
}

/** The shape of one item of a list: an option, a layer, a point of a chart. */
export interface ShapeSpec {
  /** The property a bare value stands for. */
  short?: string;
  /** Its properties, by name. */
  props: Record<string, PropSpec>;
}

/** The range of one adjustment of a picture. */
export interface AdjustmentSpec {
  min: number;
  max: number;
  default: number;
  doc: string;
}

/** The catalog's shape, as far as the app reads it. */
export interface UiCatalog {
  limits: Record<string, number>;
  /** The endings of the names of the files of each kind a card shows or takes. */
  media_kinds: Record<string, string[]>;
  adjustments: Record<string, AdjustmentSpec>;
  finishes: Record<string, { doc: string }>;
  blends: string[];
  shapes: Record<string, ShapeSpec>;
  components: Record<string, ComponentSpec>;
}

/** The catalog. */
export const CATALOG: UiCatalog = raw;

/** A component's name. */
export type ComponentType = keyof typeof raw.components;

/** An adjustment's name. */
export type AdjustmentName = keyof typeof raw.adjustments;

/** A finish's name. */
export type FinishName = keyof typeof raw.finishes;

/**
 * Whether a name is a component of the catalog.
 *
 * @param name The name.
 * @returns `true` for a component this build renders.
 */
export function isComponentType(name: string): name is ComponentType {
  return Object.hasOwn(raw.components, name);
}

/**
 * Whether a name is an adjustment of the catalog.
 *
 * @param name The name.
 * @returns `true` for an adjustment this build draws.
 */
export function isAdjustmentName(name: string): name is AdjustmentName {
  return Object.hasOwn(raw.adjustments, name);
}

/**
 * Whether a name is a finish of the catalog.
 *
 * @param name The name.
 * @returns `true` for a finish this build draws.
 */
export function isFinishName(name: string): name is FinishName {
  return Object.hasOwn(raw.finishes, name);
}

/** The adjustments' names, in the catalog's order. */
export const ADJUSTMENT_NAMES: readonly string[] = Object.keys(raw.adjustments);

/**
 * A limit of the catalog.
 *
 * @param name The limit's name.
 * @param fallback What it is where the catalog names no such limit.
 * @returns The limit.
 */
export function limit(name: string, fallback: number): number {
  return CATALOG.limits[name] ?? fallback;
}
