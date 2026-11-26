/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The open project: its header, conversation, and composer in the center, and in the right column
 * the Screen over the Environment (engines, repositories, and what the agent works with), Plan,
 * and Library panels.
 *
 * It renders three regions of the studio's grid (`studio.css`) and is keyed by the project, so
 * opening another project starts its data afresh. Each region knows how to lead to the others: a
 * tag in the agent's prose opens its asset in the library, a started engine goes on the screen,
 * and the screen's empty state leads to the Environment panel, unfolding the panel and, on a
 * narrow screen, switching to its tab.
 *
 * What the screen shows, the engine and which of its pictures (an Unreal engine's Desktop or
 * Unreal), is chosen here, by whoever chose last: the person, with the screen's toggle, its keys,
 * or an engine's card, or the agent, whose `screen` event the screen follows as it arrives and
 * shows on opening the project until the person picks something else.
 *
 * The conversation is folded here from the project's events, once for both the views that read
 * it: the center pane, and the library's Process tab, which gathers the media the session showed
 * and leads from each file back to the entry it appeared in (`reveal`).
 *
 * A project created from a link into the studio arrives with its first message, which is sent
 * once the project is open, so it shows as sent at once.
 * @module
 */
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { Layers, ListChecks, PanelRightClose, PanelRightOpen, Plus, Server } from 'lucide-react';
import { ALWAYS, isActive, type ControlPlane, type Project, type Session, type TurnLimit } from '../lib/api';
import { AUTO_REGION } from '../lib/catalog';
import { isBoolean, isRecord, type Guard } from '../lib/narrow';
import { Composer } from './Composer';
import { Conversation, type CardUpload } from './Conversation';
import { AgentEnvironment } from './EnvironmentAgent';
import { EngineSection, GitHubSection, type EpicReturn, type GitHubReturn } from './EnvironmentPanel';
import { GitHubMark } from './Menu';
import { usePreference } from './hooks';
import { LibraryBody } from './LibraryPanel';
import { Panel } from './Panel';
import { PlanBody } from './PlanPanel';
import { DisciplineIcon } from '../components/DisciplineIcon';
import { disciplineName, normalizeTag, planProgress } from './present';
import { describeAnswer } from './ui/answer';
import { Stage, type StreamStandIn } from './Stage';
import { buildTranscript, openQuestion, processMedia, type ProcessEntry, type Reveal } from './transcript';
import { connected, type Account, type Epic, type GitHub, type Projects } from './useAccount';
import { useProject } from './useProject';

/** The tabs a narrow screen shows the studio's regions under. */
export type MobileTab = 'projects' | 'chat' | 'screen' | 'workspace';

/** The panels of the right column, each folded or not. */
interface PanelState {
  /** Whether the Screen is unfolded. */
  screen: boolean;
  /** Whether Environment is unfolded. */
  environment: boolean;
  /** Whether the Plan is unfolded. */
  plan: boolean;
  /** Whether the Library is unfolded. */
  library: boolean;
}

/** Checks a stored value into a {@link PanelState}. */
const isPanelState: Guard<PanelState> = (value): value is PanelState =>
  isRecord(value) &&
  isBoolean(value.screen) &&
  isBoolean(value.environment) &&
  isBoolean(value.plan) &&
  isBoolean(value.library);

/** Every panel unfolded, as a new viewer sees them. */
const ALL_OPEN: PanelState = { screen: true, environment: true, plan: true, library: true };

/** A picture of an engine, as the person or the agent put it on screen. */
interface Picked {
  /** The engine. */
  engineId: string;
  /** The picture's name. */
  stream: string;
}

/** Props of {@link Workspace}. */
interface WorkspaceProps {
  /** The control plane, or `null` when none is connected. */
  client: ControlPlane | null;
  /** The open project. */
  project: Project;
  /** The account and what the control plane can do. */
  account: Account;
  /** The projects, which the open one reports its changes to. */
  projects: Projects;
  /** The GitHub connection. */
  github: GitHub;
  /** The outcome of a return from GitHub, shown once. */
  githubReturned: GitHubReturn;
  /** The Epic connection, which Unreal Engine's editor is pulled with. */
  epic: Epic;
  /** The outcome of a return from connecting Epic, shown once. */
  epicReturned: EpicReturn;
  /** Whether focus mode is on. */
  focus: boolean;
  /** Turns focus mode on or off. */
  onFocus: (focus: boolean) => void;
  /** Whether the layout is a narrow screen's tabs. */
  narrow: boolean;
  /** The tab shown on a narrow screen. */
  tab: MobileTab;
  /** Shows a tab on a narrow screen. */
  onTab: (tab: MobileTab) => void;
  /** Whether the right column is folded away. */
  paneCollapsed: boolean;
  /** Folds or unfolds the right column. */
  onPaneCollapsed: (collapsed: boolean) => void;
  /** The first message to send, for a project just created with one. */
  firstMessage: string | null;
  /** Called once the first message has been handed to the composer's send. */
  onFirstMessageTaken: () => void;
  /** Opens the credits dialog. */
  onAddCredits: () => void;
  /** Opens the dialog of a turn's limits on the one a turn reached, or `null` where there are none to set. */
  onLimits: ((reached: TurnLimit) => void) | null;
  /** Drawn instead of the stream, where there is none to show. */
  standIn?: StreamStandIn;
}

/**
 * Renders the open project's regions.
 *
 * @param props The component's props.
 * @returns The center, the stage, and the right column, as children of the studio's grid.
 */
export function Workspace(props: WorkspaceProps) {
  const { client, project, account, projects, github, focus, onFocus, narrow, tab, onTab } = props;
  const data = useProject(client, project, {
    onProject: projects.accept,
    onTouched: () => {
      projects.touch(project.id);
    },
    onSpent: account.refreshMe,
    onScreen: (request) => {
      setPicked({ engineId: request.engineId, stream: request.stream });
      showEngine(request.engineId, false);
    },
  });
  const [panels, setPanels] = usePreference<PanelState>('panels', ALL_OPEN, isPanelState);
  // A first message for a project that opened on the card asking its kind waits here, since the
  // kind is answered first.
  const [draft, setDraft] = useState(() =>
    props.firstMessage !== null && project.format === '' ? props.firstMessage : '',
  );
  const [screenId, setScreenId] = useState<string | null>(null);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [openAssetId, setOpenAssetId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [ledTo, setLedTo] = useState<Reveal | null>(null);
  const items = useMemo(() => buildTranscript(data.events), [data.events]);
  const process = useMemo(() => processMedia(items), [items]);
  const environmentRef = useRef<HTMLDivElement>(null);
  const planRef = useRef<HTMLDivElement>(null);
  const libraryRef = useRef<HTMLDivElement>(null);
  const firstTaken = useRef(false);

  const agentShown = data.screenRequest;
  const screen = pickScreen(data.engines, screenId ?? agentShown?.engineId ?? null);
  const screenEngineId = screen?.id ?? null;
  const shownPicture =
    [picked, agentShown].find((choice) => choice !== null && choice.engineId === screenEngineId)?.stream ?? null;
  const chooseStream = useCallback(
    (name: string): void => {
      if (screenEngineId !== null) {
        setPicked({ engineId: screenEngineId, stream: name });
      }
    },
    [screenEngineId],
  );
  const tags = useMemo(
    () =>
      new Set(
        (data.library?.assets ?? []).flatMap((asset) =>
          asset.tag === null || asset.tag === '' ? [] : [asset.tag.toLowerCase()],
        ),
      ),
    [data.library],
  );

  let blocked: string | null = null;
  if (client === null) {
    blocked = 'The control plane is not connected, so the agent cannot be reached from here.';
  } else if (account.health?.agent === false) {
    blocked =
      'The agent is not switched on for this server yet: it needs its model key. Engines and the library still work.';
  } else if (data.eventsStatus === 'missing') {
    blocked = 'This server does not run the studio’s agent yet.';
  }

  const { firstMessage, onFirstMessageTaken } = props;
  const { send } = data;
  useEffect(() => {
    if (firstMessage === null || firstTaken.current || blocked !== null || data.eventsStatus !== 'ready') {
      return;
    }
    firstTaken.current = true;
    onFirstMessageTaken();
    if (project.format === '') {
      return;
    }
    send(firstMessage).catch(() => {
      // Refused (a turn already running, say): the message waits in the composer instead.
      setDraft(firstMessage);
    });
  }, [firstMessage, onFirstMessageTaken, send, blocked, data.eventsStatus, project.format]);

  /**
   * Unfolds a panel and brings it into view, switching to its tab on a narrow screen.
   *
   * @param name The panel.
   * @param ref Its element.
   */
  function reveal(name: keyof PanelState, ref: RefObject<HTMLDivElement | null>): void {
    if (!panels[name]) {
      setPanels({ ...panels, [name]: true });
    }
    if (props.paneCollapsed) {
      props.onPaneCollapsed(false);
    }
    if (narrow) {
      onTab('workspace');
    }
    window.requestAnimationFrame(() => {
      ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  /**
   * Opens an asset in the library.
   *
   * @param id The asset.
   */
  function openAsset(id: string): void {
    setOpenAssetId(id);
    setAdding(false);
    reveal('library', libraryRef);
  }

  /**
   * Leads to where a file the session showed appeared in the conversation.
   *
   * @param entry The file.
   */
  function showInConversation(entry: ProcessEntry): void {
    setLedTo({ key: entry.itemKey, agentId: entry.agentId, seq: (ledTo?.seq ?? 0) + 1 });
    if (narrow) {
      onTab('chat');
    }
  }

  /**
   * Puts an engine on screen.
   *
   * @param id The engine.
   * @param switchTab Whether a narrow screen switches to the screen's tab: the person's own
   *   request does, while the agent's leaves them reading the conversation.
   */
  function showEngine(id: string, switchTab = true): void {
    setScreenId(id);
    if (!panels.screen) {
      setPanels({ ...panels, screen: true });
    }
    if (props.paneCollapsed && !focus) {
      props.onPaneCollapsed(false);
    }
    if (narrow && switchTab) {
      onTab('screen');
    }
  }

  /**
   * Puts one picture of an engine on screen.
   *
   * @param id The engine.
   * @param stream The picture's name.
   */
  function showPicture(id: string, stream: string): void {
    setPicked({ engineId: id, stream });
    showEngine(id);
  }

  /**
   * Takes a file a card's upload input was given into the library: a new entry named after the
   * file, with it as the entry's first file, in the section the card names or, where it names
   * none, the library's first one.
   *
   * @param file The file.
   * @param into Where the card wants it.
   * @returns The entry as the card is answered with it.
   * @throws ApiError When the entry could not be made or the file could not be stored.
   */
  async function upload(file: File, into: { section: string | null }): Promise<CardUpload> {
    const name = file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim() || 'Upload';
    const tag = normalizeTag(name);
    const made = await data.createAsset(
      {
        section: into.section ?? data.library?.sections[0] ?? 'Uploads',
        name,
        ...(tag === '' ? {} : { tag }),
      },
      file,
    );
    const stored = made.media.at(-1);
    return { tag: made.tag ?? '', name: made.name, kind: stored?.kind ?? 'file', url: stored?.url ?? '' };
  }

  const toggle = (name: keyof PanelState) => () => {
    setPanels({ ...panels, [name]: !panels[name] });
  };
  const plan = data.plan;

  return (
    <>
      <main className="studio-center" aria-label={project.name} data-mobile-hidden={narrow && tab !== 'chat'}>
        <header className="flex min-h-14 items-center gap-3 border-b border-[var(--studio-line)] px-4 py-2 sm:px-5">
          <span className="icon-tile size-8 rounded-lg">
            <DisciplineIcon id={project.discipline} className="size-6" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-[0.9375rem] leading-tight font-semibold tracking-tight">{project.name}</h1>
            <p className="truncate text-xs text-muted">
              {disciplineName(project.discipline)}
              {project.format === '' ? null : (
                <>
                  {' '}
                  <span className="text-faint">·</span> {project.format}
                </>
              )}
            </p>
          </div>
          {data.running ? (
            <span className="hidden items-center gap-2 text-xs text-fg sm:flex">
              <span className="dot dot-busy dot-live" aria-hidden="true" />
              Agent working
            </span>
          ) : blocked === null ? (
            <span className="hidden items-center gap-2 text-xs text-muted sm:flex">
              <span className="dot dot-live" aria-hidden="true" />
              Agent online
            </span>
          ) : null}
          {project.github_repo === null ? null : (
            <a
              className="pill hidden h-7 gap-1.5 text-muted transition-colors hover:text-fg md:inline-flex"
              href={`https://github.com/${project.github_repo}`}
              target="_blank"
              rel="noopener noreferrer"
              title={`${project.github_repo} on GitHub`}
            >
              <GitHubMark className="size-3.5" />
              <span className="max-w-40 truncate">{project.github_repo}</span>
            </a>
          )}
          {narrow ? null : (
            <button
              type="button"
              className="icon-btn"
              aria-label={props.paneCollapsed ? 'Show the panels' : 'Hide the panels'}
              title={props.paneCollapsed ? 'Show the panels' : 'Hide the panels'}
              aria-pressed={!props.paneCollapsed}
              onClick={() => {
                props.onPaneCollapsed(!props.paneCollapsed);
              }}
            >
              {props.paneCollapsed ? <PanelRightOpen aria-hidden="true" /> : <PanelRightClose aria-hidden="true" />}
            </button>
          )}
        </header>
        <Conversation
          project={project}
          data={data}
          items={items}
          reveal={ledTo}
          onStale={data.refreshLinks}
          tags={tags}
          canSend={blocked === null}
          onTag={(tag) => {
            const asset = data.library?.assets.find((candidate) => candidate.tag?.toLowerCase() === tag.toLowerCase());
            if (asset !== undefined) {
              openAsset(asset.id);
            }
          }}
          onOpenAsset={openAsset}
          onShowEngine={showEngine}
          onShowPlan={() => {
            reveal('plan', planRef);
          }}
          onChoose={data.send}
          onApprove={data.approve}
          onLimits={props.onLimits}
          onLock={async (ui, value) => {
            await data.send(describeAnswer(ui, value), { ui_id: ui.ui_id, value });
            if (ui.sets !== undefined) {
              // The answer changed the project itself (its kind), which the header and the sidebar show.
              client
                ?.getProject(project.id)
                .then(projects.accept)
                .catch(() => {
                  // The project is read again with the next change to it.
                });
            }
          }}
          onUpload={upload}
          onSuggest={setDraft}
        />
        <Composer
          value={draft}
          onChange={setDraft}
          running={data.running}
          blocked={blocked}
          agree={openQuestion(items)?.recommended ?? null}
          onSend={data.send}
          onStop={data.stop}
        />
      </main>

      <Stage
        engines={data.engines}
        engine={screen}
        onSelect={setScreenId}
        stream={shownPicture}
        onStream={chooseStream}
        focus={focus}
        onFocus={onFocus}
        open={panels.screen}
        onToggle={toggle('screen')}
        link={data.link}
        onStartEngine={() => {
          reveal('environment', environmentRef);
        }}
        narrow={narrow}
        mobileHidden={narrow && tab !== 'screen'}
        standIn={props.standIn}
      />

      <aside
        className="studio-pane thin-scroll"
        aria-label="Project panels"
        data-mobile-hidden={narrow && tab !== 'workspace'}
      >
        <div ref={environmentRef}>
          <Panel
            title="Environment"
            icon={Server}
            open={panels.environment}
            onToggle={toggle('environment')}
            badge={countRunning(data.engines)}
          >
            <div className="grid grid-cols-1 gap-5">
              <EngineSection
                project={project}
                engines={data.engines}
                enginesStatus={data.enginesStatus}
                screenId={screen?.id ?? null}
                health={account.health}
                me={account.me}
                epic={props.epic}
                epicReturned={props.epicReturned}
                onStart={async (app, tier) => {
                  const engine = await data.startEngine({ app, tier, region: AUTO_REGION });
                  setScreenId(engine.id);
                  return engine;
                }}
                onStop={data.stopEngine}
                onShow={showEngine}
                onShowPicture={showPicture}
                onAddCredits={props.onAddCredits}
                unrealProjects={data.unrealProjects}
                agentRunning={data.running}
                canAsk={blocked === null}
                onAsk={data.send}
              />
              <GitHubSection
                project={project}
                github={github}
                health={account.health}
                returned={props.githubReturned}
                onLink={async (link) => {
                  projects.accept(await connected(client).linkRepo(project.id, link));
                }}
                onUnlink={async () => {
                  projects.accept(await connected(client).unlinkRepo(project.id));
                }}
              />
              <AgentEnvironment
                environment={data.environment}
                status={data.environmentStatus}
                permissions={project.permissions ?? NO_PERMISSIONS}
                onRevoke={async (tool) => {
                  projects.accept(
                    await connected(client).updateProject(project.id, { permissions: withoutTool(project, tool) }),
                  );
                }}
              />
            </div>
          </Panel>
        </div>
        <div ref={planRef} className="border-t border-[var(--studio-line)]">
          <Panel title="Plan" icon={ListChecks} open={panels.plan} onToggle={toggle('plan')} badge={planProgress(plan)}>
            <PlanBody items={plan} />
          </Panel>
        </div>
        <div ref={libraryRef} className="border-t border-[var(--studio-line)]">
          <Panel
            title="Library"
            icon={Layers}
            open={panels.library}
            onToggle={toggle('library')}
            badge={data.library === null ? undefined : String(data.library.assets.length)}
            actions={
              data.libraryStatus === 'ready' && openAssetId === null ? (
                <button
                  type="button"
                  className="btn btn-quiet btn-sm h-7 px-2.5 text-xs"
                  aria-pressed={adding}
                  onClick={() => {
                    setAdding(!adding);
                  }}
                >
                  <Plus className="size-3.5" aria-hidden="true" />
                  Add
                </button>
              ) : undefined
            }
          >
            <LibraryBody
              data={data}
              openAssetId={openAssetId}
              onOpenAsset={setOpenAssetId}
              adding={adding}
              onAdding={setAdding}
              generation={account.health?.generation ?? null}
              process={process}
              onShowInConversation={showInConversation}
            />
          </Panel>
        </div>
      </aside>
    </>
  );
}

/** The kept answers of a project that has none. */
const NO_PERMISSIONS: Readonly<Record<string, string>> = {};

/**
 * The tools a project's agent may still run without asking once one is taken back.
 *
 * @param project The project.
 * @param tool The tool to ask about again.
 * @returns Every other tool the person always allows.
 */
function withoutTool(project: Project, tool: string): Record<string, typeof ALWAYS> {
  return Object.fromEntries(
    Object.entries(project.permissions ?? {}).flatMap(([name, answer]): [string, typeof ALWAYS][] =>
      name !== tool && answer === ALWAYS ? [[name, ALWAYS]] : [],
    ),
  );
}

/**
 * The engine the screen shows: the one chosen while it is active, else the newest running one,
 * else the newest coming up.
 *
 * @param engines The project's engines.
 * @param chosen The engine the person or the agent put on screen, or `null`.
 * @returns The engine, or `null` when none is active.
 */
function pickScreen(engines: Session[], chosen: string | null): Session | null {
  const active = engines.filter(isActive).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  return (
    active.find((engine) => engine.id === chosen) ??
    active.find((engine) => engine.status === 'running') ??
    active[0] ??
    engines.find((engine) => engine.id === chosen) ??
    null
  );
}

/**
 * The Environment panel's badge: how many engines are running.
 *
 * @param engines The project's engines.
 * @returns Text such as `1 running`, or `undefined` for none.
 */
function countRunning(engines: Session[]): string | undefined {
  const running = engines.filter((engine) => engine.status === 'running').length;
  return running === 0 ? undefined : `${running} running`;
}
