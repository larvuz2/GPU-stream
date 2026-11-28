/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Folds a project's event log into the conversation the center pane shows.
 *
 * The log is a flat list of what happened, in order (`moody/STUDIO.md`, `Event`); the conversation
 * is what a person reads: their messages, the agent's reply as prose, its reasoning as notes, a
 * card per tool call, a block of cards per group of subagents, its questions, approvals, and
 * interactive cards, and a line for each change it made to the plan, the library, or an engine.
 * The fold is a pure function of the events, so a page that polls only appends and re-folds:
 *
 * - Consecutive `text` events of one turn are paragraphs of one reply, a blank line apart, and so
 *   are consecutive `thinking` events of one note; any entry between them starts a new one, so
 *   prose around a tool call reads in order. An event that names a `block` replaces the earlier
 *   event of that block where it stands, which is how an answer grows while it is written, and an
 *   entry is `streaming` while one of its blocks is `partial`.
 * - A `tool_start` opens a card and the `tool_end` naming its `call_id` closes it with its outcome
 *   and media.
 * - An `agent` event is a subagent's whole card. The subagents of one `group` are one block, where
 *   the first of them arrived, and the latest event for an `agent_id` is its card. A subagent's own
 *   `tool_start`, `tool_end`, `text`, and `thinking` events (those carrying its `agent_id`) are
 *   folded the same way into its card's `entries`, never into the conversation; one naming a
 *   subagent no `agent` event has introduced is left out, since there is no card to put it in.
 *   Anything else a subagent wrote (an asset in the library, an approval it waits on) is the
 *   conversation's.
 * - An `ask` is answered by the person's next message, whichever way it was sent: a choice button
 *   or the composer. The option it names as `recommended` is kept as the agent's recommendation
 *   where it is one of the options offered.
 * - An `approval` is answered by its `approval_result`.
 * - An `error` is a line of its own. One that names the `limit` of the person's the turn stopped
 *   at keeps it, since that line is no failure and offers the setting.
 * - A `ui` card is locked in by a later `user_message` whose `ui` names it, with that message's
 *   value; one not locked in is `current` until the person sends anything else.
 * - A `preview` is a card of work in progress. Each one knows how many previews its turn showed
 *   after it (`later`), which is what lets the conversation keep a long turn light: it shows the
 *   newest few of a turn and folds the ones before them behind one line.
 *
 * A turn's end closes what the turn left open, so nothing spins forever after a stop or a failure:
 * a tool call still running and a subagent still working were stopped, a block still being written
 * is as long as it got, and an approval nobody answered has expired.
 *
 * {@link agentActivity} reads from the fold what the agent is doing right now,
 * {@link processMedia} every picture, video, and sound the session showed, which the library
 * gathers under Process, and {@link versions} the versions of the piece itself, which the Latest
 * module plays.
 * @module
 */
import type {
  AgentState,
  ApprovalOutcome,
  Asset,
  Media,
  PlanItem,
  PreviewItem,
  Session,
  StudioEvent,
  TurnId,
  TurnLimit,
  UiData,
  VersionEdit,
} from '../lib/api';
import { cardMedia } from '../lib/api';

/** A tool call's state. */
export type ToolState = 'running' | 'ok' | 'failed' | 'stopped';

/** What a locked interactive card was locked in with. */
export interface Locked {
  /** The card's state, as the person left it. */
  value: unknown;
}

/** One entry of the conversation. */
export type TranscriptItem =
  | {
      type: 'user';
      key: string;
      text: string;
      /** Whether the message locked an interactive card in: its text then says what was locked. */
      lock: boolean;
    }
  | { type: 'agent'; key: string; text: string; streaming: boolean; first: boolean }
  | { type: 'thinking'; key: string; text: string; streaming: boolean; first: boolean }
  | {
      type: 'tool';
      key: string;
      tool: string;
      title: string;
      /** What the tool looks like while it runs, as one of the catalog's `activities`. */
      activity: string;
      state: ToolState;
      summary: string | null;
      media: Media[];
      first: boolean;
    }
  | {
      type: 'ask';
      key: string;
      question: string;
      options: string[];
      /** The option the agent would choose, or `null` where it named none of them. */
      recommended: string | null;
      answer: string | null;
      first: boolean;
    }
  | {
      type: 'agents';
      key: string;
      /** The turn that started them, which closes the ones still working when it ends. */
      turn: TurnId | null;
      agents: Subagent[];
      first: boolean;
    }
  | {
      type: 'approval';
      key: string;
      approvalId: string;
      tool: string;
      title: string;
      detail: string;
      /** How it ended, or `null` while the agent still waits. */
      outcome: ApprovalOutcome | null;
      first: boolean;
    }
  | {
      type: 'ui';
      key: string;
      ui: UiData;
      /** What the person locked in, or `null` while it is open. */
      locked: Locked | null;
      /** Whether nothing the person sent has followed it, so it can still be answered. */
      current: boolean;
      first: boolean;
    }
  | {
      type: 'preview';
      key: string;
      /** The turn that showed it, whose previews fold together. */
      turn: TurnId | null;
      engineId: string;
      caption: string;
      files: PreviewItem[];
      compare: boolean;
      /** What the agent called it, for a preview that shows a version of the piece itself; else `null`. */
      version: string | null;
      /** How many previews the same turn showed after this one. */
      later: number;
      first: boolean;
    }
  | { type: 'plan'; key: string; items: PlanItem[] }
  | { type: 'library'; key: string; asset: Asset }
  | { type: 'engine'; key: string; engine: Session }
  | {
      type: 'usage';
      key: string;
      seconds: number;
      inputTokens: number;
      outputTokens: number;
      costUsd: number;
      agents: number;
    }
  | {
      type: 'error';
      key: string;
      message: string;
      /** The limit of the person's the turn stopped at, or `null` for any other error. */
      limit: TurnLimit | null;
    };

/** What a subagent's card unfolds to: its own tool calls, notes, and reasoning. */
export type SubagentEntry = Extract<TranscriptItem, { type: 'agent' | 'thinking' | 'tool' }>;

/** A subagent, as its card shows it. */
export interface Subagent {
  /** Its identifier. */
  id: string;
  /** What the page calls it, such as "Research agent". */
  title: string;
  /** The job it was handed, in a line. */
  task: string;
  /** Where it stands; one still working when its turn ended was stopped. */
  state: AgentState;
  /** What it is doing, as one of the catalog's `activities`. */
  activity: string;
  /** What it is doing now, in a line. */
  detail: string;
  /** How long it has worked, in seconds, or `null` where the log does not say. */
  seconds: number | null;
  /** The tokens it has used, or `null` where the log does not say. */
  tokens: number | null;
  /** What it did, in order. */
  entries: SubagentEntry[];
}

/** The agent's kinds of entry, which share a gutter and show its mark beside the first of a run. */
const AGENT_TYPES: ReadonlySet<TranscriptItem['type']> = new Set([
  'agent',
  'thinking',
  'tool',
  'ask',
  'agents',
  'approval',
  'ui',
  'preview',
]);

/** The kinds of a subagent's events that go in its card. */
const CARD_KINDS: ReadonlySet<StudioEvent['kind']> = new Set(['tool_start', 'tool_end', 'text', 'thinking']);

/** The catalog activity of a tool whose event names none: it is running something. */
const TOOL_ACTIVITY = 'processing';

/** The catalog activity of the agent between two steps, and while it reasons. */
const THINKING_ACTIVITY = 'thinking';

/** One block of a piece of prose: an event's text, and the block it names. */
interface Part {
  /** The block's name within the log, or `null` for an event that names none. */
  block: string | null;
  /** The text. */
  text: string;
  /** Whether the block is still being written. */
  partial: boolean;
}

/** A piece of prose as the fold keeps it: its blocks, and the turn that wrote it. */
interface Prose {
  /** The blocks, in order. */
  parts: Part[];
  /** The turn. */
  turn: TurnId | null;
}

/**
 * Whether an answer is one of a question's options, as a person or the agent wrote it: letter
 * case and the space around it do not tell two answers apart.
 *
 * @param option The option.
 * @param answer The answer, or `undefined` for none.
 * @returns `true` where they are the same answer.
 */
export function sameAnswer(option: string, answer: string | null | undefined): boolean {
  return typeof answer === 'string' && answer.trim().toLowerCase() === option.trim().toLowerCase();
}

/**
 * Whether an entry goes in a subagent's card.
 *
 * @param item The entry.
 * @returns `true` for prose, reasoning, and tool calls.
 */
function isEntry(item: TranscriptItem): item is SubagentEntry {
  return item.type === 'agent' || item.type === 'thinking' || item.type === 'tool';
}

/**
 * Builds the conversation from the event log.
 *
 * @param events The project's events, in log order.
 * @returns The conversation's entries, in order.
 */
export function buildTranscript(events: readonly StudioEvent[]): TranscriptItem[] {
  const own: StudioEvent[] = [];
  const inside = new Map<string, StudioEvent[]>();
  for (const event of events) {
    if (event.agent_id !== undefined && CARD_KINDS.has(event.kind)) {
      const list = inside.get(event.agent_id);
      if (list === undefined) {
        inside.set(event.agent_id, [event]);
      } else {
        list.push(event);
      }
      continue;
    }
    own.push(event);
    if (event.kind === 'turn_end') {
      // A subagent's card closes what it left open as the conversation does.
      for (const list of inside.values()) {
        list.push(event);
      }
    }
  }
  return fold(own, (agentId) => fold(inside.get(agentId) ?? [], () => []).filter(isEntry));
}

/**
 * Folds one speaker's events: the conversation's, or those of one subagent's card.
 *
 * @param events The events, in log order.
 * @param entriesOf Folds what a subagent did, for its card.
 * @returns The entries, in order.
 */
function fold(events: readonly StudioEvent[], entriesOf: (agentId: string) => SubagentEntry[]): TranscriptItem[] {
  const items: TranscriptItem[] = [];
  const tools = new Map<string, number>();
  const openAsks: number[] = [];
  /** The turn of each tool card still running, to close it when its turn ends. */
  const toolTurns = new Map<number, TurnId | null>();
  /** Where each turn's previews are, in order, so a new one can tell the earlier ones it came. */
  const turnPreviews = new Map<TurnId | null, number[]>();
  /** The blocks of each piece of prose or reasoning, by where it is. */
  const prose = new Map<number, Prose>();
  /** Where each named block is. */
  const blocks = new Map<string, number>();
  /** Where each group's block of subagents is, and where each subagent's card is. */
  const groups = new Map<string, number>();
  const agentBlocks = new Map<string, number>();
  /** Where each approval still waiting is, and the turn that waits on it. */
  const approvals = new Map<string, { index: number; turn: TurnId | null }>();
  const cards = new Map<string, number>();

  /**
   * Writes a piece of prose again from its blocks.
   *
   * @param index Where it is.
   */
  const rewrite = (index: number): void => {
    const item = items[index];
    const kept = prose.get(index);
    if (kept !== undefined && (item?.type === 'agent' || item?.type === 'thinking')) {
      items[index] = {
        ...item,
        text: kept.parts
          .map((part) => part.text)
          .filter((text) => text !== '')
          .join('\n\n'),
        streaming: kept.parts.some((part) => part.partial),
      };
    }
  };

  /**
   * Takes in a piece of the agent's reply or of its reasoning.
   *
   * @param type Which of the two it is.
   * @param event The event.
   */
  const write = (type: 'agent' | 'thinking', event: Extract<StudioEvent, { kind: 'text' | 'thinking' }>): void => {
    const name = event.data.block === undefined ? null : `${type}:${String(event.turn_id)}:${event.data.block}`;
    const part: Part = { block: name, text: event.data.text, partial: event.data.partial === true };
    const known = name === null ? undefined : blocks.get(name);
    const lastIndex = items.length - 1;
    const last = items[lastIndex];
    let index: number;
    if (known !== undefined) {
      index = known;
      const kept = prose.get(index);
      if (kept !== undefined) {
        kept.parts = kept.parts.map((other) => (other.block === name ? part : other));
      }
    } else if (last?.type === type && prose.get(lastIndex)?.turn === event.turn_id) {
      index = lastIndex;
      prose.get(index)?.parts.push(part);
    } else {
      index = items.length;
      items.push({ type, key: String(event.id), text: '', streaming: false, first: false });
      prose.set(index, { parts: [part], turn: event.turn_id });
    }
    if (name !== null) {
      blocks.set(name, index);
    }
    rewrite(index);
  };

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
        const lock = event.data.ui;
        const lockedIndex = lock === undefined ? undefined : cards.get(lock.ui_id);
        items.forEach((item, index) => {
          if (item.type === 'ui' && (item.current || index === lockedIndex)) {
            items[index] = {
              ...item,
              current: false,
              locked: index === lockedIndex && lock !== undefined ? { value: lock.value } : item.locked,
            };
          }
        });
        items.push({ type: 'user', key, text: event.data.text, lock: lock !== undefined });
        break;
      }
      case 'text':
        write('agent', event);
        break;
      case 'thinking':
        write('thinking', event);
        break;
      case 'tool_start': {
        tools.set(event.data.call_id, items.length);
        toolTurns.set(items.length, event.turn_id);
        items.push({
          type: 'tool',
          key,
          tool: event.data.tool,
          title: event.data.title,
          activity: event.data.activity ?? TOOL_ACTIVITY,
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
          items.push({
            type: 'tool',
            key,
            tool: '',
            title: event.data.call_id,
            activity: TOOL_ACTIVITY,
            first: false,
            ...ended,
          });
        }
        break;
      }
      case 'agent': {
        const { data } = event;
        const group = `${String(event.turn_id)}:${data.group}`;
        let index = agentBlocks.get(data.agent_id) ?? groups.get(group);
        if (index === undefined) {
          index = items.length;
          items.push({ type: 'agents', key, turn: event.turn_id, agents: [], first: false });
          groups.set(group, index);
        }
        agentBlocks.set(data.agent_id, index);
        const block = items[index];
        if (block?.type === 'agents') {
          const card: Subagent = {
            id: data.agent_id,
            title: data.title,
            task: data.task,
            state: data.state,
            activity: data.activity,
            detail: data.detail,
            seconds: data.seconds ?? null,
            tokens: data.tokens ?? null,
            entries: [],
          };
          items[index] = {
            ...block,
            agents: block.agents.some((other) => other.id === card.id)
              ? block.agents.map((other) => (other.id === card.id ? card : other))
              : [...block.agents, card],
          };
        }
        break;
      }
      case 'approval':
        approvals.set(event.data.approval_id, { index: items.length, turn: event.turn_id });
        items.push({
          type: 'approval',
          key,
          approvalId: event.data.approval_id,
          tool: event.data.tool,
          title: event.data.title,
          detail: event.data.detail,
          outcome: null,
          first: false,
        });
        break;
      case 'approval_result': {
        const waiting = approvals.get(event.data.approval_id);
        const approval = waiting === undefined ? undefined : items[waiting.index];
        if (waiting !== undefined && approval?.type === 'approval') {
          items[waiting.index] = { ...approval, outcome: event.data.decision };
          approvals.delete(event.data.approval_id);
        }
        break;
      }
      case 'ui':
        cards.set(event.data.ui_id, items.length);
        items.push({ type: 'ui', key, ui: event.data, locked: null, current: true, first: false });
        break;
      case 'ask':
        openAsks.push(items.length);
        items.push({
          type: 'ask',
          key,
          question: event.data.question,
          options: event.data.options,
          recommended: event.data.options.find((option) => sameAnswer(option, event.data.recommended)) ?? null,
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
          version: event.data.version ?? null,
          later: 0,
          first: false,
        });
        break;
      }
      case 'plan':
        items.push({ type: 'plan', key, items: event.data.items });
        break;
      case 'library':
        // The sections the agent set show in the library itself; an asset also gets a line here.
        if ('asset' in event.data) {
          items.push({ type: 'library', key, asset: event.data.asset });
        }
        break;
      case 'engine':
        items.push({ type: 'engine', key, engine: event.data.engine });
        break;
      case 'usage':
        items.push({
          type: 'usage',
          key,
          seconds: event.data.seconds,
          inputTokens: event.data.input_tokens,
          outputTokens: event.data.output_tokens,
          costUsd: event.data.cost_usd,
          agents: event.data.agents,
        });
        break;
      case 'error':
        items.push({ type: 'error', key, message: event.data.message, limit: event.data.limit ?? null });
        break;
      case 'turn_end':
        for (const [index, turn] of toolTurns) {
          const card = items[index];
          if (turn === event.turn_id && card?.type === 'tool' && card.state === 'running') {
            items[index] = { ...card, state: 'stopped' };
            toolTurns.delete(index);
          }
        }
        for (const [index, kept] of prose) {
          if (kept.turn === event.turn_id && kept.parts.some((part) => part.partial)) {
            kept.parts = kept.parts.map((part) => ({ ...part, partial: false }));
            rewrite(index);
          }
        }
        for (const index of new Set(groups.values())) {
          const block = items[index];
          if (block?.type === 'agents' && block.turn === event.turn_id) {
            items[index] = {
              ...block,
              agents: block.agents.map((agent) => (agent.state === 'working' ? { ...agent, state: 'stopped' } : agent)),
            };
          }
        }
        for (const [id, waiting] of approvals) {
          const approval = items[waiting.index];
          if (waiting.turn === event.turn_id && approval?.type === 'approval') {
            items[waiting.index] = { ...approval, outcome: 'expired' };
            approvals.delete(id);
          }
        }
        break;
      case 'screen':
        break;
    }
  }

  return items.flatMap((item, index): TranscriptItem[] => {
    if ((item.type === 'agent' || item.type === 'thinking') && item.text === '' && !item.streaming) {
      // Prose every block of which came to nothing has nothing to show.
      return [];
    }
    if (!isAgents(item)) {
      return [item];
    }
    const before = items[index - 1];
    const first = before === undefined || !AGENT_TYPES.has(before.type);
    if (item.type === 'agents') {
      return [{ ...item, first, agents: item.agents.map((agent) => ({ ...agent, entries: entriesOf(agent.id) })) }];
    }
    return [{ ...item, first }];
  });
}

/**
 * Whether an entry is one of the agent's, which carries whether it starts a run of them.
 *
 * @param item The entry.
 * @returns `true` for an entry of one of {@link AGENT_TYPES}.
 */
function isAgents(item: TranscriptItem): item is Extract<TranscriptItem, { first: boolean }> {
  return AGENT_TYPES.has(item.type);
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

/** What the agent is doing right now. */
export interface Activity {
  /** What it looks like, as one of the catalog's `activities`. */
  activity: string;
  /** What it is doing, in the words of the tool it is running, or `null` while it is thinking. */
  detail: string | null;
}

/**
 * What the agent itself is doing while its turn runs, from the entries since the person's last
 * message.
 *
 * A tool it is running says so, the latest one where several run at once; with none running it
 * is thinking, which is also what it does between two steps. There is nothing to say while
 * something else on screen already says it: an approval waiting for the person, the answer or a
 * note of its reasoning being written, or subagents still at work, whose block counts them.
 *
 * @param items The conversation.
 * @returns The activity, or `null` while another entry shows what is going on.
 */
export function agentActivity(items: readonly TranscriptItem[]): Activity | null {
  const since = items.slice(items.findLastIndex((item) => item.type === 'user') + 1);
  if (since.some((item) => item.type === 'approval' && item.outcome === null)) {
    return null;
  }
  const running = since.findLast((item) => item.type === 'tool' && item.state === 'running');
  if (running?.type === 'tool') {
    return { activity: running.activity, detail: running.title };
  }
  const last = since.at(-1);
  if ((last?.type === 'agent' || last?.type === 'thinking') && last.streaming) {
    return null;
  }
  if (since.some((item) => item.type === 'agents' && item.agents.some((agent) => agent.state === 'working'))) {
    return null;
  }
  return { activity: THINKING_ACTIVITY, detail: null };
}

/** An entry of the conversation another part of the page leads to, such as a file's under Process. */
export interface Reveal {
  /** The entry's key. */
  key: string;
  /** The subagent whose card holds what is led to, or `null` for the entry itself. */
  agentId: string | null;
  /** Which request this is, so asking for the same entry again leads there again. */
  seq: number;
}

/** A picture, video, or sound the session showed, and where in the conversation it appeared. */
export interface ProcessEntry {
  /** A key of its own among the session's media. */
  key: string;
  /** The file. */
  media: Media;
  /** What showed it: the tool call's title, the preview's caption, or the card's title. */
  caption: string;
  /** The key of the conversation's entry it appeared in. */
  itemKey: string;
  /** The subagent whose card holds it, for a file one of a subagent's tools returned. */
  agentId: string | null;
}

/**
 * Whether a file is something to look at or listen to, rather than a document to open.
 *
 * @param media The file.
 * @returns `true` for a picture, a video, or a sound.
 */
function isShown(media: Media): boolean {
  return media.kind === 'image' || media.kind === 'video' || media.kind === 'audio';
}

/**
 * Gathers every picture, video, and sound the session showed: what the agent's and its subagents'
 * tools returned, the previews (an engine's screenshots among them), and what interactive cards
 * show.
 *
 * @param items The conversation.
 * @returns The files, newest first, each with the entry that leads back to it.
 */
export function processMedia(items: readonly TranscriptItem[]): ProcessEntry[] {
  const entries: ProcessEntry[] = [];
  const add = (files: readonly Media[], caption: string, itemKey: string, agentId: string | null, scope: string): void => {
    files.forEach((media, index) => {
      if (isShown(media)) {
        entries.push({ key: `${scope}:${index}`, media, caption, itemKey, agentId });
      }
    });
  };
  for (const item of items) {
    switch (item.type) {
      case 'tool':
        add(item.media, item.title, item.key, null, item.key);
        break;
      case 'preview':
        add(item.files, item.caption, item.key, null, item.key);
        break;
      case 'ui':
        add(
          item.ui.media.flatMap((file) => cardMedia(file) ?? []),
          item.ui.title,
          item.key,
          null,
          item.key,
        );
        break;
      case 'agents':
        for (const agent of item.agents) {
          for (const entry of agent.entries) {
            if (entry.type === 'tool') {
              add(entry.media, entry.title, item.key, agent.id, `${agent.id}:${entry.key}`);
            }
          }
        }
        break;
      default:
        break;
    }
  }
  return entries.reverse();
}

/** A version of the piece the session showed, to play or to look at again. */
export interface Version {
  /** A key of its own among the versions. */
  key: string;
  /** The file to play: a video or a sound, or a picture for a version that holds nothing that plays. */
  media: Media;
  /** What the agent called the version, or `null` for a file that stands in where none was named. */
  label: string | null;
  /** What showed it, in the agent's words. */
  caption: string;
  /** The key of the conversation's entry it appeared in. */
  itemKey: string;
  /** The edit the file is the render of, where the project's history holds one; else `null`. */
  edit: VersionEdit | null;
  /** How long the file plays, in seconds, where that is known; else `null`. */
  seconds: number | null;
  /** The file's width over its height on screen, where both are known; else `null`. */
  aspect: number | null;
}

/** The kinds of file a version is played by, the first a preview holds winning. */
const PLAYED_BY: readonly Media['kind'][] = ['video', 'audio', 'image'];

/**
 * The versions of the piece the session has shown, the newest first.
 *
 * A version is a preview the agent called one (`version`), played by the file that carries the
 * version's edit, failing that its first video, failing that its first sound, failing that its
 * first picture. Where no preview names a version, the newest video or sound the session showed
 * stands in as the only one, so there is something to play as soon as anything that plays has
 * been shown.
 *
 * @param items The conversation.
 * @returns The versions, or none while the session has shown nothing that plays.
 */
export function versions(items: readonly TranscriptItem[]): Version[] {
  const named: Version[] = [];
  for (const item of items) {
    if (item.type !== 'preview' || item.version === null) {
      continue;
    }
    const media =
      item.files.find((file) => file.edit !== undefined) ??
      PLAYED_BY.map((kind) => item.files.find((file) => file.kind === kind)).find((file) => file !== undefined);
    if (media !== undefined) {
      named.push({
        key: item.key,
        media,
        label: item.version,
        caption: item.caption,
        itemKey: item.key,
        edit: media.edit ?? null,
        seconds: media.seconds ?? null,
        aspect: media.width !== undefined && media.height !== undefined ? media.width / media.height : null,
      });
    }
  }
  if (named.length > 0) {
    return named.reverse();
  }
  const newest = processMedia(items).find((entry) => entry.media.kind === 'video' || entry.media.kind === 'audio');
  return newest === undefined
    ? []
    : [
        {
          key: newest.key,
          media: newest.media,
          label: null,
          caption: newest.caption,
          itemKey: newest.itemKey,
          edit: null,
          seconds: null,
          aspect: null,
        },
      ];
}
