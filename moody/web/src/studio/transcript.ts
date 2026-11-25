/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Folds a project's event log into the conversation the center pane shows.
 *
 * The log is a flat list of what happened, in order (`moody/STUDIO.md`, `Event`); the conversation
 * is what a person reads: their messages, the agent's reply as prose, a card per tool call, the
 * agent's questions, and a line for each change it made to the plan, the library, or an engine.
 * The fold is a pure function of the events, so a page that polls only appends and re-folds:
 *
 * - Consecutive `text` events of one turn are paragraphs of one reply (the agent writes each finished
 *   block of its answer, and each note it makes between tools, as one event), so they join into one
 *   block a blank line apart; any other event between them starts a new block, so prose around a
 *   tool call reads in order.
 * - A `tool_start` opens a card and the `tool_end` naming its `call_id` closes it with its outcome
 *   and media. A call still open when its turn ends was cut short (the turn was stopped or
 *   failed), and says so rather than spinning forever.
 * - An `ask` is answered by the person's next message, whichever way it was sent: a choice button
 *   or the composer.
 * - A `preview` is a card of work in progress. Each one knows how many previews its turn showed
 *   after it (`later`), which is what lets the conversation keep a long turn light: it shows the
 *   newest few of a turn and folds the ones before them behind one line.
 * @module
 */
import type { Asset, Media, PlanItem, PreviewItem, Session, StudioEvent, TurnId } from '../lib/api';

/** A tool call's state. */
export type ToolState = 'running' | 'ok' | 'failed' | 'stopped';

/** One entry of the conversation. */
export type TranscriptItem =
  | { type: 'user'; key: string; text: string }
  | { type: 'agent'; key: string; text: string; first: boolean }
  | {
      type: 'tool';
      key: string;
      tool: string;
      title: string;
      state: ToolState;
      summary: string | null;
      media: Media[];
      first: boolean;
    }
  | { type: 'ask'; key: string; question: string; options: string[]; answer: string | null; first: boolean }
  | {
      type: 'preview';
      key: string;
      /** The turn that showed it, whose previews fold together. */
      turn: TurnId | null;
      engineId: string;
      caption: string;
      files: PreviewItem[];
      compare: boolean;
      /** How many previews the same turn showed after this one. */
      later: number;
      first: boolean;
    }
  | { type: 'plan'; key: string; items: PlanItem[] }
  | { type: 'library'; key: string; asset: Asset }
  | { type: 'engine'; key: string; engine: Session }
  | { type: 'error'; key: string; message: string };

/** The agent's kinds of entry, which share a gutter and show its mark beside the first of a run. */
const AGENT_TYPES: ReadonlySet<TranscriptItem['type']> = new Set(['agent', 'tool', 'ask', 'preview']);

/**
 * Builds the conversation from the event log.
 *
 * @param events The project's events, in log order.
 * @returns The conversation's entries, in order.
 */
export function buildTranscript(events: readonly StudioEvent[]): TranscriptItem[] {
  const items: TranscriptItem[] = [];
  const tools = new Map<string, number>();
  const openAsks: number[] = [];
  /** The turn of each tool card still running, to close it when its turn ends. */
  const toolTurns = new Map<number, TurnId | null>();
  /** Where each turn's previews are, in order, so a new one can tell the earlier ones it came. */
  const turnPreviews = new Map<TurnId | null, number[]>();
  let previous: StudioEvent | undefined;

  for (const event of events) {
    const key = String(event.id);
    switch (event.kind) {
      case 'user_message': {
        for (const index of openAsks.splice(0)) {
          const ask = items[index];
          if (ask?.type === 'ask') {
            items[index] = { ...ask, answer: event.data.text };
          }
        }
        items.push({ type: 'user', key, text: event.data.text });
        break;
      }
      case 'text': {
        const last = items.at(-1);
        if (last?.type === 'agent' && previous?.kind === 'text' && previous.turn_id === event.turn_id) {
          items[items.length - 1] = { ...last, text: `${last.text}\n\n${event.data.text}` };
        } else {
          items.push({ type: 'agent', key, text: event.data.text, first: false });
        }
        break;
      }
      case 'tool_start': {
        tools.set(event.data.call_id, items.length);
        toolTurns.set(items.length, event.turn_id);
        items.push({
          type: 'tool',
          key,
          tool: event.data.tool,
          title: event.data.title,
          state: 'running',
          summary: null,
          media: [],
          first: false,
        });
        break;
      }
      case 'tool_end': {
        const index = tools.get(event.data.call_id);
        const card = index === undefined ? undefined : items[index];
        const state: ToolState = event.data.ok ? 'ok' : 'failed';
        const ended = { state, summary: event.data.summary, media: event.data.media ?? [] };
        if (index !== undefined && card?.type === 'tool') {
          items[index] = { ...card, ...ended };
          toolTurns.delete(index);
        } else {
          // An end whose start this log does not hold still reports what the call came to.
          items.push({ type: 'tool', key, tool: '', title: event.data.call_id, first: false, ...ended });
        }
        break;
      }
      case 'ask':
        openAsks.push(items.length);
        items.push({
          type: 'ask',
          key,
          question: event.data.question,
          options: event.data.options,
          answer: null,
          first: false,
        });
        break;
      case 'preview': {
        const earlier = turnPreviews.get(event.turn_id) ?? [];
        for (const index of earlier) {
          const shown = items[index];
          if (shown?.type === 'preview') {
            items[index] = { ...shown, later: shown.later + 1 };
          }
        }
        turnPreviews.set(event.turn_id, [...earlier, items.length]);
        items.push({
          type: 'preview',
          key,
          turn: event.turn_id,
          engineId: event.data.engine_id,
          caption: event.data.caption,
          files: event.data.items,
          compare: event.data.compare,
          later: 0,
          first: false,
        });
        break;
      }
      case 'plan':
        items.push({ type: 'plan', key, items: event.data.items });
        break;
      case 'library':
        items.push({ type: 'library', key, asset: event.data.asset });
        break;
      case 'engine':
        items.push({ type: 'engine', key, engine: event.data.engine });
        break;
      case 'error':
        items.push({ type: 'error', key, message: event.data.message });
        break;
      case 'turn_end':
        for (const [index, turn] of toolTurns) {
          const card = items[index];
          if (turn === event.turn_id && card?.type === 'tool' && card.state === 'running') {
            items[index] = { ...card, state: 'stopped' };
            toolTurns.delete(index);
          }
        }
        break;
    }
    previous = event;
  }

  return items.map((item, index) => {
    if (item.type !== 'agent' && item.type !== 'tool' && item.type !== 'ask' && item.type !== 'preview') {
      return item;
    }
    const before = items[index - 1];
    return { ...item, first: before === undefined || !AGENT_TYPES.has(before.type) };
  });
}

/** Which previews of a conversation are folded away, and where the line that unfolds them goes. */
export interface PreviewFolds {
  /** The keys of the previews not shown. */
  hidden: ReadonlySet<string>;
  /** By the key of each turn's first folded preview, how many of that turn are folded. */
  lines: ReadonlyMap<string, number>;
}

/**
 * Folds the earlier previews of each turn that showed more than a few.
 *
 * The newest `shown` previews of a turn stay; the ones before them are hidden, behind one line
 * where the first of them was, unless the person unfolded that turn.
 *
 * @param items The conversation.
 * @param shown How many previews of a turn stay in view.
 * @param unfolded The turns the person unfolded, as strings.
 * @returns What is hidden, and where each turn's line goes.
 */
export function foldPreviews(
  items: readonly TranscriptItem[],
  shown: number,
  unfolded: ReadonlySet<string>,
): PreviewFolds {
  const hidden = new Set<string>();
  const lines = new Map<string, number>();
  const counted = new Set<string>();
  for (const item of items) {
    if (item.type !== 'preview' || item.later < shown || unfolded.has(String(item.turn))) {
      continue;
    }
    hidden.add(item.key);
    const turn = String(item.turn);
    if (!counted.has(turn)) {
      // The first preview of a turn has every other one after it.
      counted.add(turn);
      lines.set(item.key, item.later + 1 - shown);
    }
  }
  return { hidden, lines };
}

/**
 * Whether the conversation ends on a question the person has not answered.
 *
 * @param items The conversation.
 * @returns The open question, or `undefined`.
 */
export function openQuestion(items: readonly TranscriptItem[]): Extract<TranscriptItem, { type: 'ask' }> | undefined {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index];
    if (item?.type === 'user') {
      return undefined;
    }
    if (item?.type === 'ask' && item.answer === null) {
      return item;
    }
  }
  return undefined;
}
