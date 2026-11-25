/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The values a card's inputs hold: what each starts as, and how each reads in words.
 *
 * A card's answer is `{id: value}`, and the shape of a value is its component's: a number for a
 * slider, an option's value for a select, a list for checkboxes, an order for a reorderable
 * list, a view for a 3D model, each layer's visibility and opacity for a composite. This module
 * is the one place that knows those shapes. The functions are taken by component in
 * `registry.ts`, beside the renderers, so a component's start, its words, and its drawing are
 * registered together.
 * @module
 */
import { isBoolean, isNumber, isRecord, isString } from '../../lib/narrow';
import { flag, isScalar, items, number, options, show, text, type Scalar, type UiNode } from './tree';

/** Where a 3D model is seen from. */
export interface ModelView {
  /** Degrees around the model, 0 facing its front. */
  azimuth: number;
  /** Degrees above its middle. */
  elevation: number;
  /** How close: 1 frames the whole model, 2 is twice as near. */
  zoom: number;
}

/** One layer of a composite, as the person set it. */
export interface LayerSetting {
  /** Whether it is drawn. */
  visible: boolean;
  /** How opaque, 0 to 100. */
  opacity: number;
}

/** A composite's answer: the layer in the inspector, and every layer's setting by name. */
export interface LayersValue {
  selected: string;
  layers: Record<string, LayerSetting>;
}

/** One layer of a composite, as the card defines it. */
export interface LayerSpec {
  name: string;
  src: string;
  visible: boolean;
  opacity: number;
  blend: string;
}

/**
 * Keeps a number inside a range.
 *
 * @param value The number.
 * @param low The least it may be.
 * @param high The most it may be.
 * @returns The number, or the bound it passed.
 */
export function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/**
 * Whether a value is a 3D model's view.
 *
 * @param value The value to check.
 * @returns `true` for an azimuth, an elevation, and a zoom.
 */
export function isModelView(value: unknown): value is ModelView {
  return isRecord(value) && isNumber(value.azimuth) && isNumber(value.elevation) && isNumber(value.zoom);
}

/**
 * Whether a value is one layer's setting.
 *
 * @param value The value to check.
 * @returns `true` for a visibility and an opacity.
 */
function isLayerSetting(value: unknown): value is LayerSetting {
  return isRecord(value) && isBoolean(value.visible) && isNumber(value.opacity);
}

/**
 * Whether a value is a composite's answer.
 *
 * @param value The value to check.
 * @returns `true` for a selected layer and a setting per layer.
 */
export function isLayersValue(value: unknown): value is LayersValue {
  return (
    isRecord(value) &&
    isString(value.selected) &&
    isRecord(value.layers) &&
    Object.values(value.layers).every(isLayerSetting)
  );
}

/**
 * Reads a composite's layers.
 *
 * @param node The `layers` component.
 * @returns Its layers, the first at the bottom.
 */
export function layerSpecs(node: UiNode): LayerSpec[] {
  return items(node, 'layers', 'layer').flatMap((item): LayerSpec[] => {
    if (!isString(item.name) || !isString(item.src)) {
      return [];
    }
    return [
      {
        name: item.name,
        src: item.src,
        visible: item.visible !== false,
        opacity: isNumber(item.opacity) ? clamp(item.opacity, 0, 100) : 100,
        blend: isString(item.blend) ? item.blend : 'normal',
      },
    ];
  });
}

/**
 * The range of a slider or a number input.
 *
 * @param node The component.
 * @returns Its least and most, either of which a number input may leave open, and its step.
 */
export function range(node: UiNode): { min: number | null; max: number | null; step: number } {
  const step = number(node, 'step');
  return { min: number(node, 'min'), max: number(node, 'max'), step: step !== null && step > 0 ? step : 1 };
}

/**
 * What a slider or a number input starts at: its value, else zero where the range holds it, else its least.
 *
 * @param node The component.
 * @returns The number.
 */
function startNumber(node: UiNode): number {
  const { min, max } = range(node);
  const given = number(node, 'value') ?? 0;
  return clamp(given, min ?? -Infinity, max ?? Infinity);
}

/**
 * What an input of one choice starts at.
 *
 * @param node The component.
 * @returns Its value where that is one of its options, else its first option, else nothing.
 */
function startChoice(node: UiNode): Scalar | null {
  const values = options(node).map((option) => option.value);
  const given = node.props.value;
  return isScalar(given) && values.includes(given) ? given : (values[0] ?? null);
}

/**
 * What an input of several choices starts at.
 *
 * @param node The component.
 * @param allowed The values that may be chosen.
 * @returns The ones of its value that are allowed.
 */
function startChoices(node: UiNode, allowed: Scalar[]): Scalar[] {
  const given = node.props.value;
  return Array.isArray(given) ? allowed.filter((value) => given.includes(value)) : [];
}

/**
 * The first cell of each of a table's rows, which is what a picked row answers with.
 *
 * @param node The `table` component.
 * @returns The cells, one per row that has one.
 */
export function rowKeys(node: UiNode): Scalar[] {
  const rows: unknown = node.props.rows;
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows.flatMap((row: unknown): Scalar[] => {
    const first: unknown = Array.isArray(row) ? row[0] : undefined;
    return isScalar(first) ? [first] : [];
  });
}

/**
 * The value each of a `tabs` component's tabs answers with.
 *
 * @param node The `tabs` component.
 * @returns One value per tab: its `value`, else its label.
 */
export function tabValues(node: UiNode): Scalar[] {
  return node.children.map((tab, index) => {
    const value = tab.props.value;
    return isScalar(value) ? value : (text(tab, 'label') ?? index);
  });
}

/** What each component that answers starts as. */
export const STARTS = {
  slider: startNumber,
  number: startNumber,
  select: startChoice,
  segmented: startChoice,
  toggle: (node: UiNode): boolean => flag(node, 'value'),
  checkboxes: (node: UiNode): Scalar[] =>
    startChoices(
      node,
      options(node).map((option) => option.value),
    ),
  field: (node: UiNode): string => text(node, 'value') ?? '',
  color: (node: UiNode): string => {
    const given = node.props.value;
    const suggested: unknown = Array.isArray(node.props.suggest) ? node.props.suggest[0] : undefined;
    return isString(given) ? given : isString(suggested) ? suggested : (text(node, 'value') ?? '');
  },
  pick: (node: UiNode): Scalar | Scalar[] | null => {
    const values = options(node).map((option) => option.value);
    const given = node.props.value;
    if (flag(node, 'many')) {
      return startChoices(node, values);
    }
    return isScalar(given) && values.includes(given) ? given : null;
  },
  reorder: (node: UiNode): Scalar[] => options(node).map((option) => option.value),
  tabs: (node: UiNode): Scalar | null => tabValues(node)[0] ?? null,
  table: (node: UiNode): Scalar | Scalar[] | null => {
    const keys = rowKeys(node);
    const given = node.props.value;
    if (text(node, 'pick') === 'many') {
      return startChoices(node, keys);
    }
    return isScalar(given) && keys.includes(given) ? given : null;
  },
  model: (node: UiNode): ModelView => ({
    azimuth: number(node, 'azimuth') ?? 0,
    elevation: number(node, 'elevation') ?? 0,
    zoom: 1,
  }),
  layers: (node: UiNode): LayersValue => {
    const layers = layerSpecs(node);
    return {
      selected: layers.at(-1)?.name ?? '',
      layers: Object.fromEntries(
        layers.map((layer): [string, LayerSetting] => [layer.name, { visible: layer.visible, opacity: layer.opacity }]),
      ),
    };
  },
};

/**
 * Writes a chosen option, or several, by the labels the person read.
 *
 * @param node The component whose options they are.
 * @param value The value or values chosen.
 * @returns The labels, or the values themselves where no option carries them.
 */
function chosenWords(node: UiNode, value: unknown): string {
  const labels = new Map(options(node).map((option) => [option.value, option.label]));
  const name = (one: unknown): string => (isScalar(one) ? (labels.get(one) ?? show(one)) : show(one));
  return Array.isArray(value) ? (value.length === 0 ? '—' : value.map(name).join(', ')) : name(value);
}

/**
 * Writes a number with its unit.
 *
 * @param node The slider or number input.
 * @param value Its value.
 * @returns The number, a leading `$` before it or any other unit after it.
 */
export function withUnit(node: UiNode, value: unknown): string {
  const unit = text(node, 'unit') ?? '';
  const words = show(value);
  return unit === '$' ? `$${words}` : `${words}${unit}`;
}

/** How each component's value reads in words, where that is more than the value itself. */
export const WORDS = {
  slider: withUnit,
  number: withUnit,
  select: chosenWords,
  segmented: chosenWords,
  checkboxes: chosenWords,
  pick: chosenWords,
  reorder: (node: UiNode, value: unknown): string => {
    const labels = new Map(options(node).map((option) => [option.value, option.label]));
    const order = Array.isArray(value) ? value : [];
    return order.map((one: unknown) => (isScalar(one) ? (labels.get(one) ?? show(one)) : show(one))).join(' → ');
  },
  tabs: (node: UiNode, value: unknown): string => {
    const index = tabValues(node).findIndex((one) => one === value);
    const tab = node.children[index];
    return tab === undefined ? show(value) : (text(tab, 'label') ?? show(value));
  },
  model: (_node: UiNode, value: unknown): string =>
    isModelView(value)
      ? `${Math.round(value.azimuth)}° around, ${Math.round(value.elevation)}° up, ${show(value.zoom)}× zoom`
      : show(value),
  layers: (_node: UiNode, value: unknown): string =>
    isLayersValue(value)
      ? Object.entries(value.layers)
          .map(([name, layer]) => `${name} ${layer.visible ? `${Math.round(layer.opacity)}%` : 'hidden'}`)
          .join(', ')
      : show(value),
};

/**
 * Whether a value is nothing: no choice, no words, an empty list.
 *
 * @param value The value.
 * @returns `true` for a value a required input may not be locked in with.
 */
export function isEmpty(value: unknown): boolean {
  return value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0);
}
