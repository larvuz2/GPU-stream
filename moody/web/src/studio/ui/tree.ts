/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A card as the page holds it: the `ui` event's data, and a `components` card's tree read into
 * nodes a renderer can trust.
 *
 * The event arrives as JSON the control plane already checked against the catalog
 * (`moody/control/genui.py`), but the page checks nothing it did not read itself: `spec` is
 * `unknown` here, and {@link readTree} keeps only the nodes whose component this build knows,
 * with their properties still `unknown`. A renderer reads each property through the readers below
 * ({@link text}, {@link number}, {@link flag}, {@link items}), which narrow it and fall back to the
 * catalog's default, so a card written for a newer catalog renders what this build understands
 * rather than failing whole.
 *
 * The same readers resolve what follows an input: `"$id"` in a property that binds
 * ({@link bound}), `{id}` in a text ({@link fill}), and a `when` condition ({@link holds}).
 * @module
 */
import { isBoolean, isNumber, isRecord, isString } from '../../lib/narrow';
import type { UiData } from '../../lib/api';
import { CATALOG, isComponentType, limit, type ComponentType } from './catalog';

export type { UiData, UiMedia } from '../../lib/api';

/**
 * A card's data as this folder reads it: the wire shape, and `instant`, which the `ui` event
 * carries for a card that locks on its one choice (`moody/STUDIO.md`).
 */
export type CardData = UiData & { instant?: boolean };

/**
 * Whether a card locks as soon as the person chooses, with no lock-in button.
 *
 * @param ui The card's data.
 * @returns `true` where the event says the card is instant.
 */
export function instantOf(ui: UiData): boolean {
  return 'instant' in ui && ui.instant === true;
}

/** A card's values, by the id of the input each belongs to. */
export type UiState = Readonly<Record<string, unknown>>;

/** A value an option, a cell, or a condition carries. */
export type Scalar = string | number | boolean;

/** One component of a card's tree. */
export interface UiNode {
  /** Which component it is. */
  type: ComponentType;
  /** Where it is in the tree, which is stable for a card and so serves as its React key. */
  path: string;
  /** Its properties as the card gave them. */
  props: Readonly<Record<string, unknown>>;
  /** The components inside it. */
  children: readonly UiNode[];
}

/** One choice of an input, read from the catalog's `option` shape, or its `tile` shape for a pick. */
export interface UiOption {
  /** What the answer carries. */
  value: Scalar;
  /** What the person reads. */
  label: string;
  /** The name of its picture among the card's files. */
  image: string | null;
  /** Its pixel icon: a square of rows of `0` and `1`. */
  icon: readonly string[] | null;
  /** The name of its sound among the card's files. */
  audio: string | null;
  /** A line under the label. */
  note: string | null;
}

/** How a bindable property names the input it follows. */
const BINDING = /^\$([a-z][a-z0-9_]*)$/;

/** How a text names an input whose value it shows. */
const PLACEHOLDER = /\{([a-z][a-z0-9_]*)\}/g;

/**
 * Whether a value is one an option, a cell, or a condition carries.
 *
 * @param value The value to check.
 * @returns `true` for a string, a finite number, or a boolean.
 */
export function isScalar(value: unknown): value is Scalar {
  return isString(value) || isNumber(value) || isBoolean(value);
}

/**
 * Reads a card's tree.
 *
 * @param spec The `ui` event's `spec`.
 * @param path Where this node is, for its key.
 * @returns The node, or `null` for anything that is not a component this build knows.
 */
export function readTree(spec: unknown, path = 'root'): UiNode | null {
  if (!isRecord(spec) || !isString(spec.type) || !isComponentType(spec.type)) {
    return null;
  }
  const given = Array.isArray(spec.children) ? spec.children : [];
  const children = given
    .map((child: unknown, index) => readTree(child, `${path}.${index}`))
    .filter((child) => child !== null);
  return { type: spec.type, path, props: spec, children };
}

/**
 * Lists every node of a tree, the root first.
 *
 * @param root The tree.
 * @returns Its nodes in document order.
 */
export function walk(root: UiNode): UiNode[] {
  return [root, ...root.children.flatMap(walk)];
}

/**
 * What a property is where the card leaves it out.
 *
 * @param node The component.
 * @param name The property.
 * @returns The catalog's default, or `undefined` where it names none.
 */
function fallback(node: UiNode, name: string): unknown {
  return CATALOG.components[node.type]?.props[name]?.default;
}

/**
 * Reads a property that may follow an input.
 *
 * @param node The component.
 * @param name The property.
 * @param state The card's values.
 * @returns The input's value where the property is `"$id"`, else the property itself.
 */
export function bound(node: UiNode, name: string, state: UiState): unknown {
  return follow(node.props[name], state);
}

/**
 * Resolves a value that may be `"$id"`.
 *
 * @param value The value as the card gave it.
 * @param state The card's values.
 * @returns The input's value where it is a binding, else the value itself.
 */
export function follow(value: unknown, state: UiState): unknown {
  const id = isString(value) ? BINDING.exec(value)?.[1] : undefined;
  return id === undefined ? value : state[id];
}

/**
 * Reads a string property.
 *
 * @param node The component.
 * @param name The property.
 * @returns The string, the catalog's default, or `null`.
 */
export function text(node: UiNode, name: string): string | null {
  const value = node.props[name] ?? fallback(node, name);
  return isString(value) ? value : null;
}

/**
 * Reads a number property.
 *
 * @param node The component.
 * @param name The property.
 * @returns The number, the catalog's default, or `null`.
 */
export function number(node: UiNode, name: string): number | null {
  const value = node.props[name];
  const chosen = isNumber(value) ? value : fallback(node, name);
  return isNumber(chosen) ? chosen : null;
}

/**
 * Reads a boolean property.
 *
 * @param node The component.
 * @param name The property.
 * @returns The boolean, or the catalog's default, or `false`.
 */
export function flag(node: UiNode, name: string): boolean {
  const value = node.props[name];
  const chosen = isBoolean(value) ? value : fallback(node, name);
  return chosen === true;
}

/**
 * Reads the id of a component that answers.
 *
 * @param node The component.
 * @returns Its id, or `null` for one that has none.
 */
export function idOf(node: UiNode): string | null {
  return isString(node.props.id) ? node.props.id : null;
}

/**
 * Reads a list property whose items are of one of the catalog's shapes.
 *
 * A bare value stands for the shape's `short` property, as the catalog says, so `"Coat"` and
 * `{"value": "Coat"}` read the same.
 *
 * @param node The component.
 * @param name The property.
 * @param shape The shape's name in the catalog.
 * @returns The items as records; anything that is neither a record nor a bare value is left out.
 */
export function items(node: UiNode, name: string, shape: string): Record<string, unknown>[] {
  const list = node.props[name];
  const short = CATALOG.shapes[shape]?.short;
  if (!Array.isArray(list)) {
    return [];
  }
  return list.flatMap((item: unknown): Record<string, unknown>[] => {
    if (isRecord(item)) {
      return [item];
    }
    return short !== undefined && isScalar(item) ? [{ [short]: item }] : [];
  });
}

/**
 * Reads a pixel icon: a square of rows of `0` and `1`, of a side within the catalog's limits.
 *
 * @param value What the card gave.
 * @returns The rows, or `null` for anything that is not such a square.
 */
function readIcon(value: unknown): string[] | null {
  if (!Array.isArray(value) || value.length < limit('icon_min', 8) || value.length > limit('icon_max', 16)) {
    return null;
  }
  const rows = value.filter(isString).filter((row) => row.length === value.length && /^[01]+$/.test(row));
  return rows.length === value.length ? rows : null;
}

/**
 * Reads a component's options.
 *
 * @param node The component.
 * @param shape The catalog's shape of one option: `option`, or `tile` for a pick.
 * @returns Its choices, each with the label the person reads.
 */
export function options(node: UiNode, shape = 'option'): UiOption[] {
  return items(node, 'options', shape).flatMap((item): UiOption[] => {
    if (!isScalar(item.value)) {
      return [];
    }
    return [
      {
        value: item.value,
        label: isString(item.label) ? item.label : String(item.value),
        image: isString(item.image) ? item.image : null,
        icon: readIcon(item.icon),
        audio: isString(item.audio) ? item.audio : null,
        note: isString(item.note) ? item.note : null,
      },
    ];
  });
}

/**
 * Whether one entry of a `when` condition holds.
 *
 * @param actual The input's value.
 * @param expected What the condition asks of it: a value, any of a list, or one comparison.
 * @returns Whether it holds.
 */
function matches(actual: unknown, expected: unknown): boolean {
  if (Array.isArray(expected)) {
    return expected.includes(actual);
  }
  if (!isRecord(expected)) {
    return actual === expected;
  }
  if ('not' in expected) {
    return actual !== expected.not;
  }
  if ('gt' in expected) {
    return isNumber(actual) && isNumber(expected.gt) && actual > expected.gt;
  }
  if ('lt' in expected) {
    return isNumber(actual) && isNumber(expected.lt) && actual < expected.lt;
  }
  if ('has' in expected) {
    return Array.isArray(actual) && actual.includes(expected.has);
  }
  return false;
}

/**
 * Whether a component is in view.
 *
 * @param node The component.
 * @param state The card's values.
 * @returns `false` only while its `when` names a condition that does not hold.
 */
export function holds(node: UiNode, state: UiState): boolean {
  const when = node.props.when;
  return !isRecord(when) || Object.entries(when).every(([id, expected]) => matches(state[id], expected));
}

/**
 * Writes a value as a person reads one.
 *
 * @param value The value.
 * @returns A number without a long tail, a switch as on or off, a list by commas, a dash for nothing.
 */
export function show(value: unknown): string {
  if (isNumber(value)) {
    return String(Math.round(value * 100) / 100);
  }
  if (isBoolean(value)) {
    return value ? 'on' : 'off';
  }
  if (isString(value)) {
    return value === '' ? '—' : value;
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? '—' : value.map(show).join(', ');
  }
  return '—';
}

/**
 * Fills a text's `{id}` places with the inputs' values.
 *
 * @param template The text as the card gave it.
 * @param read Gives the words for one input's value.
 * @returns The text to show.
 */
export function fill(template: string, read: (id: string) => string): string {
  return template.replace(PLACEHOLDER, (_whole, id: string) => read(id));
}
