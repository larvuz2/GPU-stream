/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A card's answer: the state its inputs start with, whether the person has changed it since,
 * what still has to be chosen before it can be locked in, and the answer in words.
 *
 * The answer the agent receives is the card's state, `{id: value}` for a `components` card and
 * whatever the document reported for an `html` one. A person reads it as words: on a locked card
 * as a line per input ({@link summarize}), and in the message that carries it as one sentence
 * ({@link describeAnswer}), which the conversation can send as the message's text beside the
 * value.
 * @module
 */
import { isRecord } from '../../lib/narrow';
import { COMPONENTS } from './registry';
import { flag, holds, idOf, readTree, show, text, walk, type UiData, type UiNode, type UiState } from './tree';
import { isEmpty, sameValue } from './values';

/** One input's value, in words. */
export interface AnswerLine {
  /** The input's id. */
  id: string;
  /** What the input is called. */
  label: string;
  /** Its value as a person reads it. */
  words: string;
}

/**
 * The nodes of a tree that answer, by their ids.
 *
 * @param root The card's tree.
 * @returns Each input's node.
 */
export function inputsOf(root: UiNode): Map<string, UiNode> {
  const inputs = new Map<string, UiNode>();
  for (const node of walk(root)) {
    const id = idOf(node);
    if (id !== null && COMPONENTS[node.type].start !== undefined) {
      inputs.set(id, node);
    }
  }
  return inputs;
}

/**
 * The state a card starts with.
 *
 * @param inputs The card's inputs.
 * @returns Each input's starting value, by id.
 */
export function startState(inputs: ReadonlyMap<string, UiNode>): Record<string, unknown> {
  return Object.fromEntries([...inputs].map(([id, node]) => [id, COMPONENTS[node.type].start?.(node)]));
}

/**
 * An id as the words a person reads: `key_light` as "Key light".
 *
 * @param id The id.
 * @returns The words, the first capitalized, so an input without a label reads like one with.
 */
function asWords(id: string): string {
  const words = id.replaceAll('_', ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * What an input is called: its label, else its id as words.
 *
 * @param id The input's id.
 * @param node The input.
 * @returns The name.
 */
function nameOf(id: string, node: UiNode): string {
  return text(node, 'label') ?? asWords(id);
}

/**
 * One input's value in words.
 *
 * @param node The input.
 * @param value Its value.
 * @returns The words, by the component's own reading of its value where it has one.
 */
export function wordsOf(node: UiNode, value: unknown): string {
  return COMPONENTS[node.type].words?.(node, value) ?? show(value);
}

/**
 * Whether a card's values differ from the ones it opened with.
 *
 * @param inputs The card's inputs.
 * @param state The card's values.
 * @param opened The state the card started with.
 * @returns `true` once any input holds something else.
 */
export function changed(inputs: ReadonlyMap<string, UiNode>, state: UiState, opened: UiState): boolean {
  return [...inputs.keys()].some((id) => !sameValue(state[id], opened[id]));
}

/**
 * The inputs in view: those whose own condition holds, and that of everything they are inside.
 *
 * @param root The card's tree.
 * @param state The card's values.
 * @returns The ids of the inputs the person can see.
 */
function inView(root: UiNode, state: UiState): Set<string> {
  const seen = new Set<string>();
  const visit = (node: UiNode): void => {
    if (!holds(node, state)) {
      return;
    }
    const id = idOf(node);
    if (id !== null) {
      seen.add(id);
    }
    node.children.forEach(visit);
  };
  visit(root);
  return seen;
}

/**
 * The first thing that still has to be chosen before a card can be locked in.
 *
 * @param root The card's tree.
 * @param inputs The card's inputs.
 * @param state The card's values.
 * @returns The name of the first required input in view that holds nothing, or `null`.
 */
export function missing(root: UiNode, inputs: ReadonlyMap<string, UiNode>, state: UiState): string | null {
  const seen = inView(root, state);
  for (const [id, node] of inputs) {
    if (flag(node, 'required') && seen.has(id) && isEmpty(state[id])) {
      return nameOf(id, node);
    }
  }
  return null;
}

/**
 * A card's answer as a line per input.
 *
 * @param inputs The card's inputs.
 * @param state The values locked in.
 * @returns The lines, in the order of the card.
 */
export function summarize(inputs: ReadonlyMap<string, UiNode>, state: UiState): AnswerLine[] {
  return [...inputs].map(([id, node]) => ({ id, label: nameOf(id, node), words: wordsOf(node, state[id]) }));
}

/**
 * A value of an `html` card as lines: an object's fields each a line, anything else one line.
 *
 * @param value What the document reported.
 * @returns The lines.
 */
export function summarizeValue(value: unknown): AnswerLine[] {
  if (isRecord(value)) {
    return Object.entries(value).map(([key, field]) => ({
      id: key,
      label: asWords(key),
      words: isRecord(field) || (Array.isArray(field) && field.some(isRecord)) ? JSON.stringify(field) : show(field),
    }));
  }
  return value === null || value === undefined ? [] : [{ id: 'value', label: 'Answer', words: show(value) }];
}

/**
 * A locked-in card as one sentence, for the message that carries its answer.
 *
 * @param ui The card.
 * @param value What was locked in.
 * @returns Words such as "Locked in The look of shot 3: Warmth 20, Grain 12."
 */
export function describeAnswer(ui: UiData, value: unknown): string {
  const root = ui.kind === 'components' ? readTree(ui.spec) : null;
  const lines =
    root !== null && isRecord(value) ? summarize(inputsOf(root), value) : summarizeValue(value);
  const said = lines.map((line) => `${line.label} ${line.words}`).join(', ');
  return said === '' ? `Locked in ${ui.title}.` : `Locked in ${ui.title}: ${said}.`;
}
