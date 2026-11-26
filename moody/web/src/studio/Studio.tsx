/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The studio (`/app/`): the three-pane workspace where a person and the agent make a project.
 *
 * The sidebar lists the projects; the center holds the open project's conversation; the right
 * column holds the Screen over the Environment, Plan, and Library panels. The sidebar and the
 * right column fold away, the right column is as wide as the person drags it, and focus mode puts
 * the screen above the conversation and folds the sidebar for as long as it lasts. These are the
 * viewer's own preferences and are remembered in this browser. Below 1024 pixels the regions
 * become tabs.
 *
 * The open project is named in the address (`?project=`), so a reload or a shared link opens it;
 * without one, or with one the account does not have, the most recently updated project opens.
 *
 * It is written against the {@link ControlPlane} interface and renders the same whatever answers
 * it: the HTTP client, the demo's fixtures, or none at all (no API address in the build), which it
 * says in one notice and requests nothing.
 * @module
 */
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { FolderOpen, LayoutGrid, MessageSquare, MonitorPlay, Plus } from 'lucide-react';
import type { ControlPlane, NewProject, TurnLimit } from '../lib/api';
import { asksKind, brand, catalog, shortcutDiscipline, type Shortcut } from '../lib/catalog';
import { midSentence } from '../lib/format';
import { isBoolean, isNumber } from '../lib/narrow';
import { ConnectClaudeDialog } from './ConnectClaude';
import { CreditsDialog } from './CreditsDialog';
import type { EpicReturn, GitHubReturn } from './EnvironmentPanel';
import { useMediaQuery, usePreference } from './hooks';
import { LimitsDialog } from './LimitsDialog';
import { NewProjectDialog, type ProjectDraft } from './NewProjectDialog';
import { ErrorNotice, Notice } from './Notice';
import { DisciplineIcon } from '../components/DisciplineIcon';
import { Sidebar } from './Sidebar';
import type { StreamStandIn } from './Stage';
import { connected, useAccount, useEpic, useGitHub, useProjects } from './useAccount';
import { Workspace, type MobileTab } from './Workspace';

/** The query parameter that names the open project. */
const PROJECT_PARAMETER = 'project';

/** The narrowest and widest the right column can be dragged, in pixels. */
const PANE_MIN = 320;
const PANE_MAX = 760;
/** The share of the window the right column never exceeds, as `studio.css` caps it. */
const PANE_SHARE = 0.36;
/** The right column's width for a new viewer. */
const PANE_DEFAULT = 416;
/** How far one arrow key moves the column's edge. */
const PANE_STEP = 24;

/** The media query under which the regions become tabs. */
const NARROW = '(max-width: 1023.98px)';

/** Props of {@link Studio}. */
interface StudioProps {
  /** What answers the studio's requests, or `null` when no control plane is connected. */
  client: ControlPlane | null;
  /** The signed-in account's email address. */
  email: string;
  /** Whether the studio is showing the demo's sample data. */
  demo: boolean;
  /** Signs the person out. */
  onSignOut: () => void;
  /** What a link into the studio asks the new-project dialog to open with, or `null`. */
  draft: ProjectDraft | null;
  /** Called once that draft has been used or dismissed. */
  onDraftDone: () => void;
  /** The outcome of a return from GitHub, shown once. */
  githubReturned: GitHubReturn;
  /** The outcome of a return from connecting Epic, shown once. */
  epicReturned: EpicReturn;
  /** Drawn instead of the stream, where there is none to show. */
  standIn?: StreamStandIn;
}

/**
 * Reads the project the address names.
 *
 * @returns The project's identifier, or `null`.
 */
function projectInAddress(): string | null {
  return new URLSearchParams(window.location.search).get(PROJECT_PARAMETER);
}

/**
 * Renders the studio.
 *
 * @param props The component's props.
 * @returns The page.
 */
export function Studio({
  client,
  email,
  demo,
  onSignOut,
  draft,
  onDraftDone,
  githubReturned,
  epicReturned,
  standIn,
}: StudioProps) {
  const account = useAccount(client);
  const projects = useProjects(client);
  const github = useGitHub(client);
  const epic = useEpic(client);
  const narrow = useMediaQuery(NARROW);

  const [selectedId, setSelectedId] = useState<string | null>(projectInAddress);
  const [newProject, setNewProject] = useState<ProjectDraft | null>(draft);
  const [creating, setCreating] = useState(draft !== null);
  const [credits, setCredits] = useState(false);
  const [claude, setClaude] = useState(false);
  // The dialog of a turn's limits: closed, open from the menu, or open on the limit a turn reached.
  const [limits, setLimits] = useState<TurnLimit | 'open' | null>(null);
  const [focusWanted, setFocusWanted] = useState(false);
  const [tab, setTab] = useState<MobileTab>('chat');
  const [firstMessage, setFirstMessage] = useState<{ project: string; text: string } | null>(null);
  const [sideCollapsed, setSideCollapsed] = usePreference('side-collapsed', false, isBoolean);
  const [paneCollapsed, setPaneCollapsed] = usePreference('pane-collapsed', false, isBoolean);
  const [paneWidth, setPaneWidth] = usePreference('pane-width', PANE_DEFAULT, isNumber);

  const found = projects.list.find((project) => project.id === selectedId);
  const mostRecent = projects.list[0];
  if (found === undefined && mostRecent !== undefined) {
    // The address named no project, or one the account no longer has: the most recent one opens,
    // and stays open while the list reorders under it.
    setSelectedId(mostRecent.id);
  }
  const selected = found ?? mostRecent ?? null;
  const focus = focusWanted && !narrow && selected !== null;

  useEffect(() => {
    const address = new URL(window.location.href);
    if (selected === null || address.searchParams.get(PROJECT_PARAMETER) === selected.id) {
      return;
    }
    address.searchParams.set(PROJECT_PARAMETER, selected.id);
    window.history.replaceState(null, '', address);
  }, [selected]);

  const select = useCallback(
    (id: string): void => {
      setSelectedId(id);
      setFocusWanted(false);
      if (narrow) {
        setTab('chat');
      }
    },
    [narrow],
  );

  const create = useCallback(
    async (project: NewProject, prompt: string): Promise<void> => {
      const made = await projects.create(project);
      setCreating(false);
      setNewProject(null);
      onDraftDone();
      if (prompt !== '') {
        setFirstMessage({ project: made.id, text: prompt });
      }
      select(made.id);
    },
    [projects, onDraftDone, select],
  );

  const openNewProject = (preset: ProjectDraft | null = null): void => {
    setNewProject(preset);
    setCreating(true);
  };

  /**
   * Starts from a shortcut of the Create list.
   *
   * A shortcut that names a format, or whose discipline asks nothing first, opens the new-project
   * dialog on it. One whose discipline asks its kind makes the project at once, since the
   * conversation asks the rest. So that a stray click leaves nothing behind, a project of that
   * discipline with no kind yet, in which the person has said nothing, is opened again instead of
   * a second one being made.
   *
   * @param shortcut The shortcut chosen.
   * @throws ApiError When the project could not be made, or the one waiting could not be read.
   */
  const startShortcut = async (shortcut: Shortcut): Promise<void> => {
    const discipline = shortcutDiscipline(shortcut);
    if (discipline === undefined) {
      return;
    }
    if (shortcut.format !== undefined || !asksKind(discipline)) {
      openNewProject({ discipline: discipline.id, format: shortcut.format });
      return;
    }
    const plane = connected(client);
    for (const waiting of projects.list.filter((project) => project.discipline === discipline.id && project.format === '')) {
      const { events } = await plane.listEvents(waiting.id, 0);
      if (!events.some((event) => event.kind === 'user_message')) {
        select(waiting.id);
        return;
      }
    }
    const made = await projects.create({ discipline: discipline.id, name: `Untitled ${midSentence(shortcut.label)}` });
    select(made.id);
  };

  const listKeys = useCallback(() => connected(client).listApiKeys(), [client]);
  const createKey = useCallback((name: string) => connected(client).createApiKey(name), [client]);
  const revokeKey = useCallback((id: string) => connected(client).revokeApiKey(id), [client]);
  const checkout = useCallback((pack: string) => connected(client).checkout(pack), [client]);
  const takeFirstMessage = useCallback(() => {
    setFirstMessage(null);
  }, []);

  const clampedWidth = Math.min(PANE_MAX, Math.max(PANE_MIN, paneWidth));
  return (
    <div
      className="studio"
      data-side={sideCollapsed || focus ? 'collapsed' : 'open'}
      data-pane={paneCollapsed || selected === null ? 'collapsed' : 'open'}
      data-focus={focus}
      style={{ '--pane-w': `${clampedWidth}px` }}
    >
      <Sidebar
        projects={projects}
        selectedId={selected?.id ?? null}
        onSelect={select}
        onNewProject={() => {
          openNewProject();
        }}
        onShortcut={startShortcut}
        collapsed={(sideCollapsed || focus) && !narrow}
        onCollapse={(collapsed) => {
          setSideCollapsed(collapsed);
          if (!collapsed) {
            setFocusWanted(false);
          }
        }}
        me={account.me}
        email={email}
        demo={demo}
        onAddCredits={() => {
          setCredits(true);
        }}
        onConnectClaude={() => {
          setClaude(true);
        }}
        onLimits={() => {
          setLimits('open');
        }}
        onSignOut={onSignOut}
        mobileHidden={narrow && tab !== 'projects'}
      />

      {selected === null ? (
        <EmptyCenter
          status={projects.status}
          error={projects.error}
          connectedPlane={client !== null}
          mobileHidden={narrow && tab !== 'chat'}
          onNewProject={openNewProject}
        />
      ) : (
        <Workspace
          key={selected.id}
          client={client}
          project={selected}
          account={account}
          projects={projects}
          github={github}
          githubReturned={githubReturned}
          epic={epic}
          epicReturned={epicReturned}
          focus={focus}
          onFocus={setFocusWanted}
          narrow={narrow}
          tab={tab}
          onTab={setTab}
          paneCollapsed={paneCollapsed}
          onPaneCollapsed={setPaneCollapsed}
          firstMessage={firstMessage?.project === selected.id ? firstMessage.text : null}
          onFirstMessageTaken={takeFirstMessage}
          onAddCredits={() => {
            setCredits(true);
          }}
          onLimits={account.me?.limits === undefined ? null : setLimits}
          standIn={standIn}
        />
      )}

      {narrow || selected === null || paneCollapsed ? null : (
        <ResizeHandle width={clampedWidth} onWidth={setPaneWidth} />
      )}

      {narrow ? <Tabs tab={tab} onTab={setTab} hasProject={selected !== null} /> : null}

      <NewProjectDialog
        open={creating}
        draft={newProject}
        github={github}
        onClose={() => {
          setCreating(false);
          setNewProject(null);
          onDraftDone();
        }}
        onCreate={create}
      />
      <CreditsDialog
        open={credits}
        onClose={() => {
          setCredits(false);
        }}
        onCheckout={checkout}
      />
      {account.me?.limits === undefined ? null : (
        <LimitsDialog
          open={limits !== null}
          onClose={() => {
            setLimits(null);
          }}
          limits={account.me.limits}
          reached={limits === 'open' ? null : limits}
          onSave={account.setLimits}
        />
      )}
      <ConnectClaudeDialog
        open={claude}
        onClose={() => {
          setClaude(false);
        }}
        connected={client !== null}
        onList={listKeys}
        onCreate={createKey}
        onRevoke={revokeKey}
      />
    </div>
  );
}

/** Props of {@link EmptyCenter}. */
interface EmptyCenterProps {
  /** How far the project list has come. */
  status: string;
  /** Why the list failed, while it has. */
  error: unknown;
  /** Whether a control plane is connected. */
  connectedPlane: boolean;
  /** Whether the region is hidden behind another tab on a narrow screen. */
  mobileHidden: boolean;
  /** Opens the new-project dialog, at a discipline when one is given. */
  onNewProject: (preset?: ProjectDraft | null) => void;
}

/**
 * Renders the center with no project open: loading, a server without projects, or the start.
 *
 * @param props The component's props.
 * @returns The center.
 */
function EmptyCenter({ status, error, connectedPlane, mobileHidden, onNewProject }: EmptyCenterProps) {
  let content;
  if (!connectedPlane) {
    content = (
      <Notice tone="warn" title="Control plane not connected.">
        {brand} cannot reach its backend from this build, so projects, engines, and credits are unavailable for now. You
        are signed in, and everything appears here once it is connected.
      </Notice>
    );
  } else if (status === 'loading') {
    content = (
      <p className="flex items-center justify-center gap-2 text-sm text-muted" role="status">
        <span className="spinner" aria-hidden="true" />
        Opening your studio…
      </p>
    );
  } else if (status === 'missing') {
    content = (
      <div className="text-center">
        <h1 className="display text-3xl">Projects are on their way</h1>
        <p className="lede mx-auto mt-3 max-w-md text-sm">
          This server runs a control plane from before the studio, so projects cannot be made here yet. Your credits and
          Claude keys work as before, from the account menu.
        </p>
        <a className="btn btn-ghost btn-sm mt-6" href="/app/?demo">
          See the studio with sample data
        </a>
      </div>
    );
  } else if (status === 'failed') {
    content = <ErrorNotice error={error} />;
  } else {
    content = (
      <div className="text-center">
        <h1 className="display text-3xl sm:text-4xl">What are we making?</h1>
        <p className="lede mx-auto mt-3 max-w-md text-sm">
          Start a project and the agent builds it with you, opening the engines it needs on cloud GPUs and asking you at
          every decision that is yours.
        </p>
        <button
          type="button"
          className="btn btn-primary mt-7"
          onClick={() => {
            onNewProject();
          }}
        >
          <Plus className="size-4" aria-hidden="true" />
          New project
        </button>
        <ul className="mx-auto mt-8 flex max-w-lg flex-wrap justify-center gap-2">
          {catalog.disciplines.map((discipline) => {
            return (
              <li key={discipline.id}>
                <button
                  type="button"
                  className="chip"
                  onClick={() => {
                    onNewProject({ discipline: discipline.id });
                  }}
                >
                  <DisciplineIcon id={discipline.id} className="size-3" />
                  {discipline.name}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    );
  }
  return (
    <main className="studio-center thin-scroll overflow-y-auto" aria-label="Studio" data-mobile-hidden={mobileHidden}>
      <div className="m-auto w-full max-w-xl px-5 py-16">{content}</div>
    </main>
  );
}

/** Props of {@link ResizeHandle}. */
interface ResizeHandleProps {
  /** The right column's width, in pixels. */
  width: number;
  /** Sets it. */
  onWidth: (width: number) => void;
}

/**
 * Renders the edge of the right column that is dragged to resize it.
 *
 * It is a separator the keyboard can move too (the arrow keys, Home and End), and a double click
 * puts it back where it started.
 *
 * @param props The component's props.
 * @returns The handle.
 */
function ResizeHandle({ width, onWidth }: ResizeHandleProps) {
  const start = useRef<{ x: number; width: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  /**
   * Keeps a width within the column's bounds, which the window's own width narrows.
   *
   * @param value The width asked for.
   * @returns The width the column can take.
   */
  const clamp = (value: number): number =>
    Math.round(Math.min(PANE_MAX, window.innerWidth * PANE_SHARE, Math.max(PANE_MIN, value)));

  /**
   * Starts a drag.
   *
   * @param event The press.
   */
  function onPointerDown(event: PointerEvent<HTMLDivElement>): void {
    event.currentTarget.setPointerCapture(event.pointerId);
    // The column's width as drawn, which the window may have capped below the width stored.
    const edge = event.currentTarget.getBoundingClientRect();
    start.current = { x: event.clientX, width: clamp(window.innerWidth - (edge.left + edge.width / 2)) };
    setDragging(true);
  }

  /**
   * Follows a drag: the column grows as the edge moves left.
   *
   * @param event The move.
   */
  function onPointerMove(event: PointerEvent<HTMLDivElement>): void {
    if (start.current !== null) {
      onWidth(clamp(start.current.width + start.current.x - event.clientX));
    }
  }

  /** Ends a drag. */
  function onPointerUp(): void {
    start.current = null;
    setDragging(false);
  }

  /**
   * Moves the edge from the keyboard.
   *
   * @param event The key press.
   */
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    const moves: Readonly<Record<string, number>> = {
      ArrowLeft: width + PANE_STEP,
      ArrowRight: width - PANE_STEP,
      Home: PANE_MAX,
      End: PANE_MIN,
    };
    const next = Object.hasOwn(moves, event.key) ? moves[event.key] : undefined;
    if (next !== undefined) {
      event.preventDefault();
      onWidth(clamp(next));
    }
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize the panels"
      aria-valuemin={PANE_MIN}
      aria-valuemax={PANE_MAX}
      aria-valuenow={width}
      tabIndex={0}
      className="resize-handle"
      data-dragging={dragging}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onDoubleClick={() => {
        onWidth(PANE_DEFAULT);
      }}
      onKeyDown={onKeyDown}
    />
  );
}

/** Props of {@link Tabs}. */
interface TabsProps {
  /** The tab shown. */
  tab: MobileTab;
  /** Shows a tab. */
  onTab: (tab: MobileTab) => void;
  /** Whether a project is open; without one only the projects and the start are offered. */
  hasProject: boolean;
}

/** The tabs of a narrow screen, in order. */
const TABS: readonly { id: MobileTab; label: string; icon: typeof FolderOpen; needsProject: boolean }[] = [
  { id: 'projects', label: 'Projects', icon: FolderOpen, needsProject: false },
  { id: 'chat', label: 'Chat', icon: MessageSquare, needsProject: false },
  { id: 'screen', label: 'Screen', icon: MonitorPlay, needsProject: true },
  { id: 'workspace', label: 'Panels', icon: LayoutGrid, needsProject: true },
];

/**
 * Renders the tab bar of a narrow screen.
 *
 * @param props The component's props.
 * @returns The tab bar.
 */
function Tabs({ tab, onTab, hasProject }: TabsProps) {
  return (
    <nav className="studio-tabs" role="tablist" aria-label="Studio">
      {TABS.map(({ id, label, icon: Icon, needsProject }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={tab === id}
          className="studio-tab disabled:opacity-40"
          disabled={needsProject && !hasProject}
          onClick={() => {
            onTab(id);
          }}
        >
          <Icon className="size-[1.15rem]" aria-hidden="true" />
          {label}
        </button>
      ))}
    </nav>
  );
}
