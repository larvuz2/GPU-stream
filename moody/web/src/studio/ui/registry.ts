/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The table of components: for each one the catalog defines, what draws it, and for one that
 * answers, what it starts as and how its value reads in words.
 *
 * The table is keyed by the catalog's own component names ({@link ComponentType}), so adding a
 * component to `moody/ui.json` fails this file's compilation until it has an entry here: the
 * catalog and the renderers cannot drift apart unnoticed. Adding a component is that entry and
 * its renderer, nothing else.
 * @module
 */
import type { ComponentType } from './catalog';
import { Audio } from './components/Audio';
import { Chart } from './components/Chart';
import { Compare, Gallery, Image, Swatches, Text, Video } from './components/content';
import { Checkboxes, ColorInput, Field, NumberInput, Segmented, Select, Slider, Toggle } from './components/inputs';
import { Layers } from './components/Layers';
import { Grid, Row, Stack, Tab, Tabs } from './components/layout';
import { Model } from './components/Model';
import { Pick, Reorder } from './components/pick';
import { Table } from './components/Table';
import type { UiNode } from './tree';
import { STARTS, WORDS } from './values';
import type { View } from './view';

/** One component of the table. */
export interface ComponentDef {
  /** Draws it. */
  view: View;
  /** What it answers with before the person touches it, for a component that can have an id. */
  start?: (node: UiNode) => unknown;
  /** Its value in words, where that is more than the value itself. */
  words?: (node: UiNode, value: unknown) => string;
}

/** Every component of the catalog. */
export const COMPONENTS: Record<ComponentType, ComponentDef> = {
  stack: { view: Stack },
  row: { view: Row },
  grid: { view: Grid },
  tabs: { view: Tabs, start: STARTS.tabs, words: WORDS.tabs },
  tab: { view: Tab },
  text: { view: Text },
  image: { view: Image },
  video: { view: Video },
  audio: { view: Audio },
  gallery: { view: Gallery },
  compare: { view: Compare },
  swatches: { view: Swatches },
  table: { view: Table, start: STARTS.table },
  chart: { view: Chart },
  model: { view: Model, start: STARTS.model, words: WORDS.model },
  layers: { view: Layers, start: STARTS.layers, words: WORDS.layers },
  slider: { view: Slider, start: STARTS.slider, words: WORDS.slider },
  number: { view: NumberInput, start: STARTS.number, words: WORDS.number },
  select: { view: Select, start: STARTS.select, words: WORDS.select },
  segmented: { view: Segmented, start: STARTS.segmented, words: WORDS.segmented },
  toggle: { view: Toggle, start: STARTS.toggle },
  checkboxes: { view: Checkboxes, start: STARTS.checkboxes, words: WORDS.checkboxes },
  field: { view: Field, start: STARTS.field },
  color: { view: ColorInput, start: STARTS.color },
  pick: { view: Pick, start: STARTS.pick, words: WORDS.pick },
  reorder: { view: Reorder, start: STARTS.reorder, words: WORDS.reorder },
};
