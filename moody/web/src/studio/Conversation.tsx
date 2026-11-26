/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The center pane's conversation, folded from the project's event log (`transcript.ts`).
 *
 * The person's messages sit on the right; the agent's entries share a gutter on the left, its mark
 * beside the first of each run: its prose, a compact card per tool call that unfolds to what the
 * call came to (`ToolCard.tsx`), a block of cards for the subagents it handed work to
 * (`AgentsBlock.tsx`), its questions as buttons that answer by sending the choice, the one the
 * agent recommends marked as such, and the media its tools produced, inline. A change the agent made to the plan, the library, or an engine reads
 * as a line that leads to it. A message just sent shows at once, dimmed until the log has it.
 *
 * What the agent reasons is a quiet note that unfolds (`ThinkingNote.tsx`), with the eyes beside
 * it in the gutter while it is being written, and its answer grows while it is written, ending
 * in a caret until it is whole. Before a tool that costs or changes something it asks, as a card
 * with three answers (`ApprovalCard.tsx`), and a turn ends on one small line of what it took:
 * time, tokens, cost, and subagents. A turn that stopped at one of the person's own limits (an
 * `error` that names the `limit`) is no failure: its line is a caution, not an error, and offers
 * the dialog where that limit is set, beside the message where both fit on a line and under it on
 * a phone.
 *
 * An interactive card (`ui`) is drawn by `ui/UiCard.tsx`. This module decides when it can be
 * answered (it is the newest thing the agent showed, no turn is running, and it is not locked
 * in), sends its state as the person's next message when they lock it in, and shows it locked
 * from that moment, before the log has the message. The message itself reads as one compact line
 * naming the card and what was chosen, never as the state's JSON.
 *
 * While a turn runs, one line under the newest entry says what the agent is doing right now: the
 * pixel eyes playing the activity, its label from the catalog, and the tool it is running
 * (`agentActivity`). The line is lavender, the color of the intelligence at work, and gives way
 * while something else on screen says the same: the answer being written, subagents at work, or
 * an approval that waits for the person.
 *
 * Work in progress the agent shows is a card of its own (`PreviewCard.tsx`). A turn that showed
 * many keeps its newest few in view and folds the earlier ones behind "Show earlier previews",
 * so a long session stays light to scroll and to load (`foldPreviews`).
 *
 * The view follows the newest entry while the person is at the bottom, and stays where they are
 * when they have scrolled up to read, offering a way back down instead. It also stays where it is
 * when the person unfolds something (a subagent's card, a tool call): what they opened grows under
 * their pointer rather than being pushed out of view by a jump to the end. Two things bring the
 * end back into view wherever the person is reading: an approval, since the agent's turn waits on
 * it, and a message the person sends, since it and the answer to it are what they look for next.
 *
 * Another part of the page can lead to an entry (`reveal`, from a file under the library's
 * Process tab): the entry is unfolded where it was folded away, scrolled to, and lit for a moment.
 *
 * Media in the log are served from signed addresses that expire. One that fails to load here
 * reports it (`onStale`), which re-reads the log for fresh addresses; a file whose address then
 * changed is loaded again, since its address is part of its identity in every list.
 * @module
 */
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ArrowDown, Check, ChevronRight, CircleAlert, ListChecks, Lock, MonitorPlay } from 'lucide-react';
import { MoodyFace } from '../components/Moody';
import { MoodyEyes } from '../components/MoodyEyes';
import type { ApprovalDecision, Asset, PlanItem, Project, Session, TurnLimit, UiData } from '../lib/api';
import { findApp, findTier } from '../lib/catalog';
import { cx } from '../lib/cx';
import { midSentence, price, spanText, tokenCount } from '../lib/format';
import { showActivity } from './activity';
import { AgentsBlock } from './AgentsBlock';
import { ApprovalCard } from './ApprovalCard';
import { ErrorNotice, Notice } from './Notice';
import { DisciplineIcon } from '../components/DisciplineIcon';
import { disciplineName } from './present';
import { PreviewCard } from './PreviewCard';
import { Prose } from './Prose';
import { ThinkingEyes, ThinkingNote } from './ThinkingNote';
import { ToolCard } from './ToolCard';
import { UiCard } from './ui/UiCard';
import {
  agentActivity,
  foldPreviews,
  openQuestion,
  sameAnswer,
  type Activity,
  type Locked,
  type Reveal,
  type TranscriptItem,
} from './transcript';
import type { ProjectData } from './useProject';

/** How close to the bottom, in pixels, still counts as following the conversation. */
const FOLLOW_SLACK_PX = 96;

/** How long after a click or a key press a change of height counts as the person's own doing. */
const OWN_CHANGE_MS = 600;

/** How many previews of one turn stay in view; the ones before them fold away. */
const PREVIEWS_IN_VIEW = 3;

/** Props of {@link Conversation}. */
interface ConversationProps {
  /** The open project. */
  project: Project;
  /** Its live data. */
  data: ProjectData;
  /** The conversation, folded from the project's events. */
  items: TranscriptItem[];
  /** An entry another part of the page leads to, or `null`. */
  reveal: Reveal | null;
  /** Reports that a file of the log failed to load, as an expired address does. */
  onStale: () => void;
  /** The library's tags, lowercase, which become references in the agent's prose. */
  tags: ReadonlySet<string>;
  /** Whether the agent can take a message now. */
  canSend: boolean;
  /** Opens the asset a tag names. */
  onTag: (tag: string) => void;
  /** Opens an asset. */
  onOpenAsset: (id: string) => void;
  /** Shows an engine on the screen. */
  onShowEngine: (id: string) => void;
  /** Unfolds the plan. */
  onShowPlan: () => void;
  /** Sends a choice the agent offered. */
  onChoose: (text: string) => Promise<void>;
  /** Answers an approval the running turn waits on. */
  onApprove: (approvalId: string, decision: ApprovalDecision) => Promise<void>;
  /** Opens the dialog of a turn's limits on the one a turn reached, or `null` where there are none to set. */
  onLimits: ((reached: TurnLimit) => void) | null;
  /** Locks an interactive card in with its state, as the person's next message. */
  onLock: (ui: UiData, value: unknown) => Promise<void>;
  /** Puts a suggestion in the composer. */
  onSuggest: (text: string) => void;
}

/**
 * Renders the conversation.
 *
 * @param props The component's props.
 * @returns The scrolling conversation.
 */
export function Conversation(props: ConversationProps) {
  const { project, data, items, reveal, onStale, canSend } = props;
  const question = openQuestion(items);
  const [unfolded, setUnfolded] = useState<ReadonlySet<string>>(() => new Set());
  const folds = useMemo(() => foldPreviews(items, PREVIEWS_IN_VIEW, unfolded), [items, unfolded]);
  const scroller = useRef<HTMLDivElement>(null);
  const [following, setFollowing] = useState(true);
  const [seen, setSeen] = useState(0);
  const touched = useRef(0);
  const activity = useMemo(() => (data.running ? agentActivity(items) : null), [data.running, items]);
  const behind = !following && items.length > seen;

  useLayoutEffect(() => {
    const element = scroller.current;
    if (element !== null && following) {
      element.scrollTop = element.scrollHeight;
    }
  }, [items, data.pending, activity, following]);

  const waiting = useMemo(
    () => items.findLast((item) => item.type === 'approval' && item.outcome === null)?.key ?? null,
    [items],
  );
  const [shownWaiting, setShownWaiting] = useState<string | null>(null);
  if (waiting !== shownWaiting) {
    setShownWaiting(waiting);
    if (waiting !== null) {
      // Following again brings the conversation's end, where the approval is, into view.
      setFollowing(true);
    }
  }
  const sending = data.pending !== null;
  const [wasSending, setWasSending] = useState(false);
  if (sending !== wasSending) {
    setWasSending(sending);
    if (sending) {
      setFollowing(true);
    }
  }

  // The view keeps to the bottom when its height changes too: focus mode resizing it, or an image
  // loading above the newest entry.
  useEffect(() => {
    const element = scroller.current;
    if (element === null || !following) {
      return;
    }
    const observer = new ResizeObserver(() => {
      if (performance.now() - touched.current < OWN_CHANGE_MS) {
        setFollowing(element.scrollHeight - element.scrollTop - element.clientHeight < FOLLOW_SLACK_PX);
        return;
      }
      element.scrollTop = element.scrollHeight;
    });
    observer.observe(element);
    if (element.firstElementChild !== null) {
      observer.observe(element.firstElementChild);
    }
    return () => {
      observer.disconnect();
    };
  }, [following]);

  const [revealed, setRevealed] = useState(0);
  if (reveal !== null && reveal.seq !== revealed) {
    setRevealed(reveal.seq);
    const led = items.find((item) => item.key === reveal.key);
    if (led?.type === 'preview' && folds.hidden.has(led.key)) {
      setUnfolded(new Set(unfolded).add(String(led.turn)));
    }
  }
  useEffect(() => {
    if (reveal === null) {
      return;
    }
    const entry = scroller.current?.querySelector(`[data-entry="${CSS.escape(reveal.key)}"]`);
    const card = reveal.agentId === null ? null : entry?.querySelector(`[data-agent="${CSS.escape(reveal.agentId)}"]`);
    const target = card ?? entry;
    if (target === null || target === undefined) {
      return;
    }
    // Being led here is the person's own doing: the view goes to the entry and stays on it.
    touched.current = performance.now();
    target.scrollIntoView({ block: 'center', behavior: 'smooth' });
    target.setAttribute('data-revealed', 'true');
    const done = (): void => {
      target.removeAttribute('data-revealed');
    };
    target.addEventListener('animationend', done, { once: true });
    return () => {
      target.removeEventListener('animationend', done);
      done();
    };
  }, [reveal]);

  // A file that fails to load does not say so to its ancestors, so the failure is caught on its way down.
  useEffect(() => {
    const element = scroller.current;
    if (element === null) {
      return;
    }
    const onError = (event: Event): void => {
      if (event.target instanceof HTMLImageElement || event.target instanceof HTMLMediaElement) {
        onStale();
      }
    };
    element.addEventListener('error', onError, true);
    return () => {
      element.removeEventListener('error', onError, true);
    };
  }, [onStale]);

  /** Notes whether the person is at the bottom, which decides whether new entries scroll into view. */
  function onScroll(): void {
    const element = scroller.current;
    if (element === null) {
      return;
    }
    const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight < FOLLOW_SLACK_PX;
    setFollowing(atBottom);
    if (atBottom) {
      setSeen(items.length);
    }
  }

  /** Notes that the person acted on the conversation, so what changes next is their own doing. */
  function onTouch(): void {
    touched.current = performance.now();
  }

  const empty = items.length === 0 && data.pending === null;
  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={scroller}
        className="conversation thin-scroll h-full overflow-y-auto"
        onScroll={onScroll}
        onPointerDownCapture={onTouch}
        onKeyDownCapture={onTouch}
      >
        <div className="mx-auto w-full max-w-[46rem] px-4 pt-6 pb-8 sm:px-6">
          {data.eventsStatus === 'loading' ? (
            <p className="flex items-center gap-2 pt-10 text-sm text-muted" role="status">
              <span className="spinner" aria-hidden="true" />
              Opening the conversation…
            </p>
          ) : data.eventsStatus === 'missing' ? (
            <div className="pt-6">
              <Notice tone="info" title="The agent is on its way.">
                This server does not run the studio&rsquo;s agent yet, so the conversation cannot start here. Engines,
                the library, and GitHub appear as their parts arrive.
              </Notice>
            </div>
          ) : empty ? (
            <Welcome project={project} canSend={canSend} onSuggest={props.onSuggest} />
          ) : (
            <ol className="grid grid-cols-1 gap-y-3" aria-label="Conversation">
              {items.map((item) => {
                const folded = folds.lines.get(item.key);
                if (item.type === 'preview' && folded !== undefined) {
                  return (
                    <li key={item.key} className="pl-10">
                      <button
                        type="button"
                        className="flex items-center gap-2 rounded-lg text-xs text-lavender/80 hover:text-lavender"
                        onClick={() => {
                          setUnfolded((turns) => new Set(turns).add(String(item.turn)));
                        }}
                      >
                        <ChevronRight className="size-3.5" aria-hidden="true" />
                        Show {folded} earlier {folded === 1 ? 'preview' : 'previews'}
                      </button>
                    </li>
                  );
                }
                return folds.hidden.has(item.key) ? null : (
                  <Entry key={item.key} item={item} open={item === question} {...props} />
                );
              })}
              {data.pending === null ? null : data.pending.ui === undefined ? (
                <li className="mt-5">
                  <div className="message-user" data-pending="true">
                    {data.pending.text}
                  </div>
                </li>
              ) : (
                <LockLine text={data.pending.text} pending />
              )}
              {activity === null ? null : <ActivityLine activity={activity} />}
            </ol>
          )}
          {data.eventsError === null ? null : (
            <div className="mt-4">
              <ErrorNotice error={data.eventsError} />
            </div>
          )}
        </div>
      </div>
      {behind ? (
        <button
          type="button"
          className="btn btn-ghost btn-sm absolute bottom-3 left-1/2 -translate-x-1/2 bg-ink-800/90 shadow-xl backdrop-blur"
          onClick={() => {
            scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' });
          }}
        >
          <ArrowDown className="size-4" aria-hidden="true" />
          Latest
        </button>
      ) : null}
    </div>
  );
}

/** Props of {@link ActivityLine}. */
interface ActivityLineProps {
  /** What the agent is doing. */
  activity: Activity;
}

/**
 * Renders the line that says what the agent is doing right now.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function ActivityLine({ activity }: ActivityLineProps) {
  const shown = showActivity(activity.activity);
  return (
    <li className="activity-line mt-2" role="status">
      <span className="flex w-7 flex-none justify-center">
        <MoodyEyes expression={shown.expression} tone="active" />
      </span>
      <span className="text-lavender">{shown.label}…</span>
      {activity.detail === null ? null : <span className="min-w-0 truncate text-faint">{activity.detail}</span>}
    </li>
  );
}

/** Props of {@link LockLine}. */
interface LockLineProps {
  /** The message: what was locked in, as the card worded it (`ui/answer.ts`, `describeAnswer`). */
  text: string;
  /** Whether the message is sent but not in the log yet. */
  pending?: boolean;
}

/**
 * Renders the person's message that locked an interactive card in, as one compact line.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function LockLine({ text, pending = false }: LockLineProps) {
  return (
    <li className="mt-5 first:mt-0">
      <div className="lock-line" data-pending={pending ? true : undefined} title={text}>
        <Lock className="size-3.5 flex-none text-lime" aria-hidden="true" />
        <span className="min-w-0 truncate">{text}</span>
      </div>
    </li>
  );
}

/** Props of {@link UiEntry}. */
interface UiEntryProps {
  /** The card. */
  ui: UiData;
  /** What the person locked in, as the log or a message just sent has it, or `null`. */
  locked: Locked | null;
  /** Whether the card can be answered now. */
  live: boolean;
  /** Locks the card in. */
  onLock: (ui: UiData, value: unknown) => Promise<void>;
}

/**
 * Renders an interactive card, and what locking it in failed with, if it did.
 *
 * @param props The component's props.
 * @returns The card.
 */
function UiEntry({ ui, locked, live, onLock }: UiEntryProps) {
  const [error, setError] = useState<unknown>(null);
  return (
    <>
      <UiCard
        ui={ui}
        locked={locked}
        live={live}
        onSubmit={(value) => {
          setError(null);
          onLock(ui, value).catch((failure: unknown) => {
            setError(failure);
          });
        }}
      />
      {error === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={error} />
        </div>
      )}
    </>
  );
}

/** Props of {@link UsageLine}. */
interface UsageLineProps {
  /** What the turn took. */
  usage: Extract<TranscriptItem, { type: 'usage' }>;
}

/**
 * Renders what a turn took, as one line of small print at its end.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function UsageLine({ usage }: UsageLineProps) {
  const tokens = usage.inputTokens + usage.outputTokens;
  const parts = [
    spanText(usage.seconds * 1000),
    `${tokenCount(tokens)} tokens`,
    price(usage.costUsd),
    usage.agents === 0 ? null : `${usage.agents} ${usage.agents === 1 ? 'subagent' : 'subagents'}`,
  ].filter((part) => part !== null);
  return (
    <li className="usage-line pl-10">
      <span title={`${tokenCount(usage.inputTokens)} tokens read, ${tokenCount(usage.outputTokens)} written`}>
        {parts.join(' · ')}
      </span>
    </li>
  );
}

/** Props of {@link Welcome}. */
interface WelcomeProps {
  /** The open project. */
  project: Project;
  /** Whether the agent can take a message now. */
  canSend: boolean;
  /** Puts a suggestion in the composer. */
  onSuggest: (text: string) => void;
}

/** The openings a new project offers, each put in the composer to finish and send. */
const OPENINGS = [
  'I have a script to share. Here it is:\n\n',
  'Let’s write it together. The idea is ',
  'Surprise me with three directions to choose from.',
];

/**
 * Renders the opening of a project with no conversation yet.
 *
 * @param props The component's props.
 * @returns The welcome.
 */
function Welcome({ project, canSend, onSuggest }: WelcomeProps) {
  return (
    <div className="flex flex-col items-center pt-[12vh] text-center">
      <span className="icon-tile size-12 rounded-2xl">
        <DisciplineIcon id={project.discipline} className="size-6" />
      </span>
      <h2 className="display mt-5 text-2xl sm:text-3xl">{project.name}</h2>
      <p className="lede mt-2 max-w-md text-sm">
        {/^[aeiou]/i.test(project.format) ? 'An' : 'A'} {midSentence(project.format)} in{' '}
        {disciplineName(project.discipline)}. Bring what you have, or start from an
        idea, and the agent builds it with you, asking at every decision that is yours.
      </p>
      <ul className="mt-7 grid grid-cols-1 w-full max-w-md gap-2">
        {OPENINGS.map((opening) => (
          <li key={opening}>
            <button
              type="button"
              className="ask-option justify-between"
              disabled={!canSend}
              onClick={() => {
                onSuggest(opening);
              }}
            >
              <span>{opening.trim().replace(/:$/, '')}</span>
              <ChevronRight className="size-4 text-faint" aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Props of {@link Entry}. */
interface EntryProps extends Omit<ConversationProps, 'items' | 'onStale'> {
  /** The entry. */
  item: TranscriptItem;
  /** Whether it is the question the person has yet to answer. */
  open: boolean;
}

/**
 * Renders one entry of the conversation.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function Entry({
  item,
  open,
  data,
  canSend,
  tags,
  onTag,
  onOpenAsset,
  onShowEngine,
  onShowPlan,
  onChoose,
  onApprove,
  onLimits,
  onLock,
  reveal,
}: EntryProps) {
  switch (item.type) {
    case 'user':
      return item.lock ? (
        <LockLine text={item.text} />
      ) : (
        <li className="mt-5 first:mt-0">
          <div className="message-user">{item.text}</div>
        </li>
      );
    case 'agent':
      return (
        <AgentRow first={item.first}>
          <Prose text={item.text} tags={tags} onTag={onTag} streaming={item.streaming} />
        </AgentRow>
      );
    case 'thinking':
      return (
        <AgentRow first={item.first} mark={item.streaming ? <ThinkingEyes /> : undefined}>
          <ThinkingNote text={item.text} streaming={item.streaming} />
        </AgentRow>
      );
    case 'approval':
      return (
        <AgentRow first={item.first}>
          <ApprovalCard
            title={item.title}
            detail={item.detail}
            tool={item.tool}
            outcome={item.outcome}
            live={canSend && data.running}
            onDecide={(decision) => onApprove(item.approvalId, decision)}
          />
        </AgentRow>
      );
    case 'ui': {
      const sent = data.pending?.ui?.ui_id === item.ui.ui_id ? { value: data.pending.ui.value } : null;
      const locked = item.locked ?? sent;
      return (
        <AgentRow first={item.first} entry={item.key}>
          <UiEntry
            ui={item.ui}
            locked={locked}
            live={item.current && locked === null && canSend && !data.running}
            onLock={onLock}
          />
        </AgentRow>
      );
    }
    case 'usage':
      return <UsageLine usage={item} />;
    case 'tool':
      return (
        <AgentRow first={item.first} entry={item.key}>
          <ToolCard title={item.title} tool={item.tool} state={item.state} summary={item.summary} media={item.media} />
        </AgentRow>
      );
    case 'agents':
      return (
        <AgentRow first={item.first} entry={item.key}>
          <AgentsBlock
            agents={item.agents}
            tags={tags}
            onTag={onTag}
            reveal={reveal?.key === item.key ? reveal : null}
          />
        </AgentRow>
      );
    case 'ask':
      return (
        <AgentRow first={item.first}>
          <AskCard
            question={item.question}
            options={item.options}
            recommended={item.recommended}
            answer={item.answer}
            live={open && canSend && !data.running}
            onChoose={onChoose}
          />
        </AgentRow>
      );
    case 'preview': {
      const engine = data.engines.find((candidate) => candidate.id === item.engineId);
      return (
        <AgentRow first={item.first} entry={item.key}>
          <PreviewCard
            caption={item.caption}
            files={item.files}
            compare={item.compare}
            engine={engine === undefined ? null : (findApp(engine.app)?.name ?? engine.app)}
          />
        </AgentRow>
      );
    }
    case 'plan':
      return <PlanLine items={item.items} onShowPlan={onShowPlan} />;
    case 'library':
      return <LibraryLine asset={item.asset} onOpenAsset={onOpenAsset} />;
    case 'engine':
      return <EngineLine engine={item.engine} onShowEngine={onShowEngine} />;
    case 'error': {
      const { limit } = item;
      return limit === null ? (
        <li className="pl-10">
          <Notice tone="bad">{item.message}</Notice>
        </li>
      ) : (
        <li className="pl-10" data-limit={limit}>
          <Notice tone="warn">
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
              <span className="min-w-56 flex-1">{item.message}</span>
              {onLimits === null ? null : (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm -my-1 flex-none"
                  onClick={() => {
                    onLimits(limit);
                  }}
                >
                  Change limits
                </button>
              )}
            </div>
          </Notice>
        </li>
      );
    }
  }
}

/** Props of {@link AgentRow}. */
interface AgentRowProps {
  /** Whether it starts a run of the agent's entries, which shows its mark. */
  first: boolean;
  /** What stands in the gutter instead of the mark: the eyes, for an entry still under way. */
  mark?: ReactNode;
  /** The entry's key, for an entry another part of the page can lead to. */
  entry?: string;
  /** The entry. */
  children: ReactNode;
}

/**
 * Renders an entry of the agent's in its gutter.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function AgentRow({ first, mark, entry, children }: AgentRowProps) {
  return (
    <li className={cx('flex gap-3', first && 'mt-5 first:mt-0')} data-entry={entry}>
      {mark === undefined ? (
        <span className="w-7 flex-none pt-0.5">
          {first ? (
            <span className="agent-mark" title="Agent">
              <MoodyFace className="h-6" />
            </span>
          ) : null}
        </span>
      ) : (
        <span className="flex w-7 flex-none justify-center">{mark}</span>
      )}
      <div className="min-w-0 flex-1">{children}</div>
    </li>
  );
}

/** Props of {@link AskCard}. */
interface AskCardProps {
  /** The question. */
  question: string;
  /** The answers offered. */
  options: string[];
  /** The answer the agent would give, one of the options, or `null`. */
  recommended: string | null;
  /** The person's answer, once given. */
  answer: string | null;
  /** Whether the choices can be sent now. */
  live: boolean;
  /** Sends a choice. */
  onChoose: (text: string) => Promise<void>;
}

/**
 * Renders the agent's question with its answers as buttons.
 *
 * The option the agent would choose says so after its text, as a quiet "(recommended)" in the
 * agent's lavender: it is the agent's word, not an action, so it never takes the lime of what the
 * person does, and it stays on the option once the question is answered, whichever answer was
 * given. Agreeing is one click on that option, or Enter in the empty composer (`Composer.tsx`),
 * which the line under the options says while the question is open.
 *
 * @param props The component's props.
 * @returns The card.
 */
function AskCard({ question, options, recommended, answer, live, onChoose }: AskCardProps) {
  const [sending, setSending] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  /**
   * Sends a choice as the person's message.
   *
   * @param option The choice.
   */
  async function choose(option: string): Promise<void> {
    setSending(option);
    setError(null);
    try {
      await onChoose(option);
    } catch (failure) {
      setError(failure);
    } finally {
      setSending(null);
    }
  }

  const answered = answer !== null;
  return (
    <div className="ai-card rounded-2xl p-4">
      <p className="ai-label">Moody asks</p>
      <p className="mt-2 font-medium text-fg">{question}</p>
      <ul className="mt-3 grid grid-cols-1 gap-2">
        {options.map((option, index) => {
          const chosen = answered && sameAnswer(option, answer);
          return (
            <li key={option}>
              <button
                type="button"
                className="ask-option"
                data-chosen={answered ? chosen : undefined}
                data-recommended={option === recommended ? true : undefined}
                disabled={!live || answered || sending !== null}
                onClick={() => {
                  void choose(option);
                }}
              >
                <span className="ask-key" aria-hidden="true">
                  {chosen ? <Check className="size-3 text-fg" /> : index + 1}
                </span>
                <span className="min-w-0 flex-1">
                  {option}
                  {option === recommended ? <span className="ask-recommended"> (recommended)</span> : null}
                </span>
                {sending === option ? <span className="spinner size-3.5" aria-hidden="true" /> : null}
              </button>
            </li>
          );
        })}
      </ul>
      {answered || !live ? null : (
        <p className="mt-3 text-xs text-faint">
          {recommended === null
            ? 'Or answer in your own words below.'
            : 'Press Enter in the empty message box to go with the recommendation, or answer in your own words.'}
        </p>
      )}
      {error === null ? null : (
        <div className="mt-3">
          <ErrorNotice error={error} />
        </div>
      )}
    </div>
  );
}

/** Props of {@link PlanLine}. */
interface PlanLineProps {
  /** The plan as it now stands. */
  items: PlanItem[];
  /** Unfolds the plan. */
  onShowPlan: () => void;
}

/**
 * Renders the line that says the agent changed the plan.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function PlanLine({ items, onShowPlan }: PlanLineProps) {
  const done = items.filter((item) => item.status === 'done').length;
  return (
    <li className="pl-10">
      <button
        type="button"
        className="flex items-center gap-2 rounded-lg text-xs text-faint hover:text-muted"
        onClick={onShowPlan}
      >
        <ListChecks className="size-3.5" aria-hidden="true" />
        Updated the plan · {done} of {items.length} done
      </button>
    </li>
  );
}

/** Props of {@link LibraryLine}. */
interface LibraryLineProps {
  /** The asset added or changed. */
  asset: Asset;
  /** Opens it. */
  onOpenAsset: (id: string) => void;
}

/**
 * Renders the line that says the agent put an asset in the library.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function LibraryLine({ asset, onOpenAsset }: LibraryLineProps) {
  return (
    <li className="pl-10">
      <button
        type="button"
        className="group flex max-w-full items-center gap-2.5 rounded-xl border border-line bg-white/[0.02] py-1.5 pr-3 pl-1.5 text-left text-xs text-muted transition-colors hover:border-white/20"
        onClick={() => {
          onOpenAsset(asset.id);
        }}
      >
        <span className="asset-thumb size-8 flex-none rounded-lg">
          {asset.thumbnail_url === null ? null : <img src={asset.thumbnail_url} alt="" loading="lazy" />}
        </span>
        <span className="min-w-0 truncate">
          Added <span className="font-medium text-fg">{asset.name}</span>
          {asset.tag === null ? null : <span className="tag-chip ml-1.5">@{asset.tag}</span>} to {asset.section}
        </span>
      </button>
    </li>
  );
}

/** Props of {@link EngineLine}. */
interface EngineLineProps {
  /** The engine as it now stands. */
  engine: Session;
  /** Shows it on the screen. */
  onShowEngine: (id: string) => void;
}

/** How an engine's state reads in a sentence. */
const ENGINE_PHRASES: Readonly<Record<Session['status'], string>> = {
  queued: 'is waiting for a workstation',
  starting: 'is starting',
  running: 'is running',
  ended: 'stopped',
  failed: 'failed to start',
};

/**
 * Renders the line that says the agent started or changed an engine.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function EngineLine({ engine, onShowEngine }: EngineLineProps) {
  const app = findApp(engine.app)?.name ?? engine.app;
  const tier = findTier(engine.tier)?.name;
  const failed = engine.status === 'failed';
  return (
    <li className="pl-10">
      <span className={cx('flex flex-wrap items-center gap-2 text-xs', failed ? 'text-bad' : 'text-faint')}>
        {failed ? (
          <CircleAlert className="size-3.5" aria-hidden="true" />
        ) : (
          <MonitorPlay className="size-3.5" aria-hidden="true" />
        )}
        <span>
          {app} {ENGINE_PHRASES[engine.status]}
          {tier === undefined || engine.status === 'ended' || failed ? '' : ` on ${tier}`}
        </span>
        {engine.status === 'running' ? (
          <button
            type="button"
            className="link text-xs"
            onClick={() => {
              onShowEngine(engine.id);
            }}
          >
            Show on screen
          </button>
        ) : null}
      </span>
    </li>
  );
}
