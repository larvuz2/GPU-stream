/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Subagents at work: the block the conversation shows for one group of them (`agent` events in
 * `moody/STUDIO.md`).
 *
 * The block says how many tasks the agent handed out, holds a card per subagent, and counts under
 * them how many are still working and how each of the others ended. A card is the subagent's
 * title, the pixel eyes playing what it is doing beside that activity's label from the catalog,
 * what it is doing now in a line, and where it stands at the right. While it works the label ends
 * in an ellipsis; done, it reads as the catalog labels it. A subagent that failed or was stopped
 * is not doing anything, so its eyes rest.
 *
 * A card unfolds to what the subagent did: its task, and its own tool calls, reasoning, and notes
 * in order, with the media its tools returned. The conversation never shows those itself, since
 * only a subagent's final report is the agent's to use.
 *
 * `reveal` names a subagent whose card another part of the page leads to (a file under the
 * library's Process tab): that card unfolds.
 * @module
 */
import { useId, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { MoodyEyes, type EyesTone } from '../components/MoodyEyes';
import type { AgentState } from '../lib/api';
import { cx } from '../lib/cx';
import { spanText, tokenCount } from '../lib/format';
import { showActivity } from './activity';
import { Prose } from './Prose';
import { ThinkingNote } from './ThinkingNote';
import { ToolCard } from './ToolCard';
import type { Subagent } from './transcript';

/** How each state of a subagent is said and drawn. */
const STATES: Readonly<Record<AgentState, { label: string; className: string; tone: EyesTone }>> = {
  working: { label: 'Working', className: 'text-faint', tone: 'default' },
  completed: { label: 'Completed', className: 'text-ok', tone: 'ok' },
  failed: { label: 'Failed', className: 'text-bad', tone: 'bad' },
  stopped: { label: 'Stopped', className: 'text-faint', tone: 'faint' },
};

/** The states a subagent ends in, in the order the count names them. */
const ENDED: readonly Exclude<AgentState, 'working'>[] = ['completed', 'failed', 'stopped'];

/**
 * Counts subagents, in words.
 *
 * @param count How many.
 * @returns Text such as `1 agent` or `4 agents`.
 */
function agentsText(count: number): string {
  return `${count} ${count === 1 ? 'agent' : 'agents'}`;
}

/**
 * Says how many subagents are still working and how the others ended.
 *
 * @param agents The subagents.
 * @returns Text such as `4 agents working · 1 completed`.
 */
function countText(agents: readonly Subagent[]): string {
  const counts = [
    { label: STATES.working.label.toLowerCase(), count: agents.filter((agent) => agent.state === 'working').length },
    ...ENDED.map((state) => ({
      label: STATES[state].label.toLowerCase(),
      count: agents.filter((agent) => agent.state === state).length,
    })),
  ].filter((entry) => entry.count > 0);
  return counts
    .map((entry, index) => `${index === 0 ? agentsText(entry.count) : entry.count} ${entry.label}`)
    .join(' · ');
}

/** Props of {@link AgentsBlock}. */
interface AgentsBlockProps {
  /** The subagents of one group, in the order they were started. */
  agents: Subagent[];
  /** The library's tags, lowercase, which become references in a subagent's notes. */
  tags: ReadonlySet<string>;
  /** Opens the asset a tag names. */
  onTag: (tag: string) => void;
  /** A subagent whose card to unfold, or `null`. */
  reveal: string | null;
}

/**
 * Renders a group of subagents.
 *
 * @param props The component's props.
 * @returns The block.
 */
export function AgentsBlock({ agents, tags, onTag, reveal }: AgentsBlockProps) {
  const [opened, setOpened] = useState<ReadonlySet<string>>(() => new Set());
  const [revealed, setRevealed] = useState<string | null>(null);
  if (reveal !== revealed) {
    // A card another part of the page leads to unfolds once, and stays the person's to fold.
    setRevealed(reveal);
    if (reveal !== null && agents.some((agent) => agent.id === reveal)) {
      setOpened(new Set(opened).add(reveal));
    }
  }
  const working = agents.filter((agent) => agent.state === 'working').length;
  const failed = agents.some((agent) => agent.state === 'failed');
  const tasks = agents.length === 1 ? 'a task' : 'tasks';
  const specialists = `${agents.length} specialized ${agents.length === 1 ? 'agent' : 'agents'}`;
  return (
    <section className="agents-block" aria-label="Subagents">
      <h3 className="agents-heading">
        {working > 0 ? `Delegating ${tasks} to ${specialists}…` : `Delegated ${tasks} to ${specialists}`}
      </h3>
      <ul className="mt-3 grid grid-cols-1 gap-2">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            open={opened.has(agent.id)}
            onToggle={() => {
              const next = new Set(opened);
              if (!next.delete(agent.id)) {
                next.add(agent.id);
              }
              setOpened(next);
            }}
            tags={tags}
            onTag={onTag}
          />
        ))}
      </ul>
      <p className="agents-count" role="status">
        <span
          className={cx('dot', working > 0 ? 'dot-busy dot-live' : failed ? 'dot-bad' : 'dot-done')}
          aria-hidden="true"
        />
        {countText(agents)}
      </p>
    </section>
  );
}

/** Props of {@link AgentCard}. */
interface AgentCardProps {
  /** The subagent. */
  agent: Subagent;
  /** Whether the card is unfolded. */
  open: boolean;
  /** Folds or unfolds it. */
  onToggle: () => void;
  /** The library's tags. */
  tags: ReadonlySet<string>;
  /** Opens the asset a tag names. */
  onTag: (tag: string) => void;
}

/**
 * Renders one subagent's card.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function AgentCard({ agent, open, onToggle, tags, onTag }: AgentCardProps) {
  const bodyId = useId();
  const state = STATES[agent.state];
  const shown = showActivity(agent.activity);
  const working = agent.state === 'working';
  const resting = agent.state === 'failed' || agent.state === 'stopped';
  const facts = [
    agent.seconds === null ? null : spanText(agent.seconds * 1000),
    agent.tokens === null ? null : `${tokenCount(agent.tokens)} tokens`,
  ].filter((fact) => fact !== null);
  return (
    <li className="agent-card" data-state={agent.state} data-agent={agent.id}>
      <button type="button" className="agent-card-head" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
        <ChevronRight className="agent-card-chevron" aria-hidden="true" />
        <span className="agent-card-title">{agent.title}</span>
        <span className={cx('agent-card-state', state.className)}>{state.label}</span>
        <span className={cx('agent-card-activity', working ? 'text-muted' : state.className)}>
          <MoodyEyes expression={shown.expression} tone={state.tone} still={resting} />
          <span>
            {shown.label}
            {working ? '…' : ''}
          </span>
        </span>
        <span className="agent-card-detail">{agent.detail}</span>
      </button>
      {open ? (
        <div id={bodyId} className="agent-card-body">
          <p className="text-xs leading-relaxed text-faint">
            <span className="font-medium text-muted">Task</span> {agent.task}
            {facts.length === 0 ? '' : ` · ${facts.join(' · ')}`}
          </p>
          {agent.entries.length === 0 ? (
            <p className="mt-2 text-xs text-faint">
              {working ? 'Nothing to show yet: its steps appear here as it takes them.' : 'It left no steps to show.'}
            </p>
          ) : (
            <ol className="mt-2.5 grid grid-cols-1 gap-2.5" aria-label={`What the ${agent.title} did`}>
              {agent.entries.map((entry) => (
                <li key={entry.key}>
                  {entry.type === 'tool' ? (
                    <ToolCard
                      title={entry.title}
                      tool={entry.tool}
                      state={entry.state}
                      summary={entry.summary}
                      media={entry.media}
                      compact
                    />
                  ) : entry.type === 'thinking' ? (
                    <ThinkingNote text={entry.text} streaming={entry.streaming} />
                  ) : (
                    <Prose text={entry.text} tags={tags} onTag={onTag} streaming={entry.streaming} />
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : null}
    </li>
  );
}
