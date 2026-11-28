/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Subagents at work: the block the conversation shows for one group of them (`agent` events in
 * `moody/STUDIO.md`).
 *
 * The block says that the project is being worked on, holds a card per subagent, and counts under
 * them how many are still working and how each of the others ended. A card is the subagent's
 * title over one line of status. While the subagent works, that line is a pixel loader
 * (`components/PixelLoader.tsx`) beside what it is doing now, in the control plane's words, or
 * the catalog's label for its activity where it has none. Each subagent of a group plays a
 * different one of the six loaders, picked when it starts and kept, and starts it at a point of
 * its own, so cards side by side neither look alike nor move in step (`lib/pixelLoader.ts`). The
 * agent's own eyes stay the agent's: a row of them would say six times that someone is thinking,
 * where six loaders say that six things are going on.
 *
 * Once a subagent has ended, the loader is gone and the line says how, by a mark, a word, and a
 * color: completed, failed, or stopped, with what it was last doing after it. The word is there
 * so that neither the mark nor the color is the only thing that says it.
 *
 * A card unfolds to what the subagent did: its task, and its own tool calls, reasoning, and notes
 * in order, with the media its tools returned. The conversation never shows those itself, since
 * only a subagent's final report is the agent's to use. The whole head of the card is the control,
 * and its arrow is quiet until the pointer or the keyboard is on it.
 *
 * Only the count is announced as it changes. Each card's line changes with every step its
 * subagent takes, and six of them read aloud at once would say nothing.
 *
 * `reveal` names a subagent whose card another part of the page leads to (a file under the
 * library's Process tab): that card unfolds, each time it is asked for.
 * @module
 */
import { useId, useState } from 'react';
import { Check, ChevronRight, GripVertical, Square } from 'lucide-react';
import { PixelLoader } from '../components/PixelLoader';
import type { AgentState } from '../lib/api';
import { spanText, tokenCount } from '../lib/format';
import { loaderOffset, loaderStyle, type LoaderStyle } from '../lib/pixelLoader';
import { showActivity } from './activity';
import { Prose } from './Prose';
import { ThinkingEyes, ThinkingNote } from './ThinkingNote';
import { ToolCard } from './ToolCard';
import type { Reveal, Subagent } from './transcript';

/** How each state of a subagent is said. */
const STATES: Readonly<Record<AgentState, { label: string }>> = {
  working: { label: 'Working' },
  completed: { label: 'Completed' },
  failed: { label: 'Failed' },
  stopped: { label: 'Stopped' },
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
 * @returns Text such as `4 agents working in parallel · 1 completed`.
 */
function countText(agents: readonly Subagent[]): string {
  const working = agents.filter((agent) => agent.state === 'working').length;
  const counts = [
    { label: `${STATES.working.label.toLowerCase()}${working > 1 ? ' in parallel' : ''}`, count: working },
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
  /** What another part of the page leads to in this block, or `null`. */
  reveal: Reveal | null;
}

/**
 * Renders a group of subagents.
 *
 * @param props The component's props.
 * @returns The block.
 */
export function AgentsBlock({ agents, tags, onTag, reveal }: AgentsBlockProps) {
  const [opened, setOpened] = useState<ReadonlySet<string>>(() => new Set());
  const [revealed, setRevealed] = useState(0);
  if (reveal !== null && reveal.seq !== revealed) {
    // A card another part of the page leads to unfolds once per request, and stays the person's to fold.
    setRevealed(reveal.seq);
    if (reveal.agentId !== null && agents.some((agent) => agent.id === reveal.agentId)) {
      setOpened(new Set(opened).add(reveal.agentId));
    }
  }
  const working = agents.some((agent) => agent.state === 'working');
  const group = agents[0]?.id ?? '';
  return (
    <section className="agents-block" aria-label="Subagents">
      <h3 className="agents-heading">{working ? 'Working on your project' : 'Worked on your project'}</h3>
      <ul className="agents-list">
        {agents.map((agent, place) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            loader={loaderStyle(group, place)}
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
        {countText(agents)}
      </p>
    </section>
  );
}

/** Props of {@link AgentCard}. */
interface AgentCardProps {
  /** The subagent. */
  agent: Subagent;
  /** The pixel loader it plays while it works. */
  loader: LoaderStyle;
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
function AgentCard({ agent, loader, open, onToggle, tags, onTag }: AgentCardProps) {
  const bodyId = useId();
  const state = STATES[agent.state];
  const working = agent.state === 'working';
  const facts = [
    agent.seconds === null ? null : spanText(agent.seconds * 1000),
    agent.tokens === null ? null : `${tokenCount(agent.tokens)} tokens`,
  ].filter((fact) => fact !== null);
  return (
    <li className="agent-card" data-state={agent.state} data-agent={agent.id}>
      <button type="button" className="agent-card-head" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
        <span className="agent-card-title">
          <GripVertical className="agent-card-mark" aria-hidden="true" />
          <span className="agent-card-name">{agent.title}</span>
          <ChevronRight className="agent-card-chevron" aria-hidden="true" />
        </span>
        <span className="agent-card-status">
          {working ? <PixelLoader style={loader} offset={loaderOffset(agent.id)} /> : <EndMark state={agent.state} />}
          <span className="agent-card-status-text">
            {working ? (
              <>
                <span className="sr-only">{state.label}: </span>
                {agent.detail === '' ? `${showActivity(agent.activity).label}…` : agent.detail}
              </>
            ) : (
              <>
                {state.label}
                {agent.detail === '' ? null : <span className="agent-card-status-rest"> · {agent.detail}</span>}
              </>
            )}
          </span>
        </span>
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
                    <div className="flex items-start gap-2">
                      {entry.streaming ? <ThinkingEyes /> : null}
                      <div className="min-w-0 flex-1">
                        <ThinkingNote text={entry.text} streaming={entry.streaming} />
                      </div>
                    </div>
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

/** Props of {@link EndMark}. */
interface EndMarkProps {
  /** How the subagent ended. */
  state: AgentState;
}

/**
 * Renders the mark that stands where a subagent's loader was once it has ended: a check for one
 * that completed, an exclamation mark for one that failed, a stop square for one that was stopped.
 *
 * @param props The component's props.
 * @returns The mark, in the color of the line it is on.
 */
function EndMark({ state }: EndMarkProps) {
  if (state === 'completed') {
    return <Check className="agent-card-glyph" strokeWidth={2.5} aria-hidden="true" />;
  }
  if (state === 'failed') {
    return (
      <span className="agent-card-glyph" aria-hidden="true">
        !
      </span>
    );
  }
  return <Square className="agent-card-glyph" fill="currentColor" strokeWidth={0} aria-hidden="true" />;
}
