/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Environment panel: the project's engines, and its GitHub repository.
 *
 * Engines are catalog apps running as sessions of the project. Each shows its state, its clock
 * while it runs, and the controls that put it on the screen or stop it. The start form offers the
 * discipline's engines first, then every other app; only an available app, a team one, which the
 * control plane admits for the team's accounts alone, or one with a part on the person's own
 * license can be started, and the rest show their status. A tier the control plane does not list
 * as open is shown but cannot be chosen. Unreal Engine, whose editor runs on the person's Epic
 * account, starts at once whatever that account: the form says what the engine comes with, the
 * editor too where the control plane reads the Epic link through their GitHub account, and asks
 * nothing of Epic, which the agent explains when the person wants the editor.
 *
 * A running Unreal engine's card lists the Unreal projects in its workspace, each with what it is
 * and an "Open in Unreal" button that asks the agent to open it, the way the person would in a
 * message. Before there is one, the card says how one gets there, with the Desktop view a click
 * away. The list is read when the card appears, whenever the agent starts or ends a turn (it may
 * have cloned or made one), and when the person asks to look again, never on a timer: reading the
 * machine counts as use of it, and a page left open must not keep an engine from shutting down
 * once it is idle.
 *
 * GitHub is the person's own account, connected once through the control plane's OAuth App and
 * then linked per project to a repository, existing or created for it; connecting it again is in
 * its menu, which the Epic link's last step asks for. The block says plainly when this server has
 * no GitHub configured, or no studio routes yet, instead of failing.
 * @module
 */
import { useEffect, useId, useMemo, useState, type ReactNode, type SubmitEvent } from 'react';
import {
  Box,
  CircleStop,
  ExternalLink,
  Lock,
  LogOut,
  Monitor,
  MonitorPlay,
  Play,
  Plus,
  RefreshCw,
  Unlink,
} from 'lucide-react';
import {
  DESKTOP_STREAM,
  isActive,
  isMissing,
  type GitHubRepo,
  type Health,
  type Me,
  type Project,
  type RepoLink,
  type Session,
  type UnrealProject,
} from '../lib/api';
import {
  catalog,
  findApp,
  findDiscipline,
  findTier,
  gpuLabel,
  tierFits,
  isOwnLicense,
  minutesFor,
  type CatalogApp,
  type Tier,
} from '../lib/catalog';
import { cx } from '../lib/cx';
import { clock, minutesText, sizeText, timestamp } from '../lib/format';
import { useNow } from './hooks';
import { GitHubMark, Menu } from './Menu';
import { describeEndReason, describeError } from './messages';
import { ErrorNotice, Notice } from './Notice';
import { ago, appStatusLabel, canStart } from './present';
import type { GitHub } from './useAccount';

/** Props of {@link EngineSection}. */
interface EngineSectionProps {
  /** The open project. */
  project: Project;
  /** Its engines. */
  engines: Session[];
  /** Whether the engines could be read, and how far that has come. */
  enginesStatus: string;
  /** The engine on screen, or `null`. */
  screenId: string | null;
  /** What the control plane can do. */
  health: Health | null;
  /** The signed-in account. */
  me: Me | null;
  /** The GitHub connection, through which an app on the person's own license is linked. */
  github: GitHub;
  /** Starts an engine. */
  onStart: (app: string, tier: string) => Promise<Session>;
  /** Stops an engine. */
  onStop: (id: string) => Promise<void>;
  /** Puts an engine on screen. */
  onShow: (id: string) => void;
  /** Puts one picture of an engine on screen, such as an Unreal engine's Desktop. */
  onShowPicture: (id: string, stream: string) => void;
  /** Opens the credits dialog. */
  onAddCredits: () => void;
  /** Lists the Unreal projects in a running Unreal engine's workspace. */
  unrealProjects: (engineId: string) => Promise<UnrealProject[]>;
  /** Whether the agent is working on a turn, when nothing more can be asked of it. */
  agentRunning: boolean;
  /** Whether the agent can be asked at all on this server. */
  canAsk: boolean;
  /** Asks the agent, as the person's message. */
  onAsk: (text: string) => Promise<void>;
}

/**
 * Renders the project's engines and the form that starts one.
 *
 * @param props The component's props.
 * @returns The engines.
 */
export function EngineSection({
  project,
  engines,
  enginesStatus,
  screenId,
  health,
  me,
  github,
  onStart,
  onStop,
  onShow,
  onShowPicture,
  onAddCredits,
  unrealProjects,
  agentRunning,
  canAsk,
  onAsk,
}: EngineSectionProps) {
  const active = engines.filter(isActive);
  const ended = engines
    .filter((engine) => !isActive(engine))
    .sort((a, b) => Date.parse(b.ended_at ?? b.created_at) - Date.parse(a.ended_at ?? a.created_at))
    .slice(0, 3);
  return (
    <div>
      <h3 className="section-label">Engines</h3>
      {enginesStatus === 'missing' ? (
        <p className="mt-2 text-sm text-faint">Engines per project arrive with the studio&rsquo;s backend.</p>
      ) : enginesStatus === 'failed' ? (
        <p className="mt-2 text-sm text-bad">Could not read the engines. They are read again shortly.</p>
      ) : active.length === 0 ? (
        <p className="mt-2 text-sm text-faint">
          Nothing running. The agent starts what the work needs, or start one here.
        </p>
      ) : (
        <ul className="mt-2 grid grid-cols-1 gap-2">
          {active.map((engine) => (
            <EngineRow
              key={engine.id}
              engine={engine}
              onScreen={engine.id === screenId}
              onShow={onShow}
              onStop={onStop}
            >
              {engine.app === 'unreal' && engine.status === 'running' ? (
                <UnrealProjects
                  engine={engine}
                  load={unrealProjects}
                  agentRunning={agentRunning}
                  canAsk={canAsk}
                  onAsk={onAsk}
                  onShowDesktop={() => {
                    onShowPicture(engine.id, DESKTOP_STREAM);
                  }}
                />
              ) : null}
            </EngineRow>
          ))}
        </ul>
      )}
      {enginesStatus === 'missing' ? null : (
        <StartForm
          project={project}
          health={health}
          me={me}
          github={github}
          onStart={onStart}
          onAddCredits={onAddCredits}
        />
      )}
      {ended.length === 0 ? null : (
        <details className="mt-3 text-xs text-faint">
          <summary className="w-fit rounded">Earlier engines</summary>
          <ul className="mt-2 grid grid-cols-1 gap-1.5">
            {ended.map((engine) => (
              <li key={engine.id} className="flex items-center gap-2">
                <span className={cx('dot', engine.status === 'failed' ? 'dot-bad' : 'dot-idle')} aria-hidden="true" />
                <span className="text-muted">{findApp(engine.app)?.name ?? engine.app}</span>
                <span className="truncate">
                  {describeEndReason(engine.end_reason) ?? (engine.status === 'failed' ? 'Failed' : 'Ended')}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

/** Props of {@link EngineRow}. */
interface EngineRowProps {
  /** The engine. */
  engine: Session;
  /** Whether it is on screen. */
  onScreen: boolean;
  /** Puts it on screen. */
  onShow: (id: string) => void;
  /** Stops it. */
  onStop: (id: string) => Promise<void>;
  /** What the card shows below its header, such as a running Unreal engine's projects. */
  children?: ReactNode;
}

/**
 * Renders one active engine.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function EngineRow({ engine, onScreen, onShow, onStop, children }: EngineRowProps) {
  const running = engine.status === 'running';
  const now = useNow(running);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const app = findApp(engine.app);
  const tier = findTier(engine.tier);
  const started = timestamp(engine.started_at);

  /** Stops the engine. */
  async function stop(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await onStop(engine.id);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  const state =
    engine.status === 'queued'
      ? engine.queue_position === null
        ? 'Queued'
        : `Queued · #${engine.queue_position}`
      : engine.status === 'starting'
        ? 'Starting'
        : started === null
          ? 'Running'
          : `Running · ${clock(now - started)}`;
  return (
    <li
      className={cx(
        'rounded-xl border bg-white/[0.025] p-2.5 transition-colors',
        onScreen ? 'border-ember/40' : 'border-line',
      )}
      style={{ '--accent': app?.accent }}
    >
      <div className="flex items-center gap-2.5">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg text-left"
          disabled={!running}
          title={running ? 'Show on the screen' : undefined}
          onClick={() => {
            onShow(engine.id);
          }}
        >
          <span className="icon-tile size-8 rounded-lg">
            <MonitorPlay className="size-3.5" aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">{app?.name ?? engine.app}</span>
            <span className="flex items-center gap-1.5 text-xs text-muted">
              <span
                className={cx(
                  'dot',
                  engine.status === 'running'
                    ? 'dot-live'
                    : engine.status === 'starting'
                      ? 'dot-ember dot-live'
                      : 'dot-warn dot-live',
                )}
                aria-hidden="true"
              />
              <span className="tabular-nums">{state}</span>
              {tier === undefined ? null : <span className="text-faint">· {tier.name}</span>}
            </span>
          </span>
        </button>
        {onScreen && running ? <span className="pill h-6 text-[0.6875rem] text-ember-200">On screen</span> : null}
        {confirming ? (
          <span className="flex items-center gap-1">
            <button
              type="button"
              className="btn btn-danger btn-sm h-7 px-2.5 text-xs"
              disabled={busy}
              onClick={() => {
                void stop();
              }}
            >
              {busy ? <span className="spinner size-3" aria-hidden="true" /> : null}
              Stop
            </button>
            <button
              type="button"
              className="btn btn-quiet btn-sm h-7 px-2 text-xs"
              onClick={() => {
                setConfirming(false);
              }}
            >
              Keep
            </button>
          </span>
        ) : (
          <button
            type="button"
            className="icon-btn"
            aria-label={`Stop ${app?.name ?? engine.app}`}
            title="Stop"
            onClick={() => {
              setConfirming(true);
            }}
          >
            <CircleStop aria-hidden="true" />
          </button>
        )}
      </div>
      {error === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={error} />
        </div>
      )}
      {children}
    </li>
  );
}

/** Props of {@link UnrealProjects}. */
interface UnrealProjectsProps {
  /** The running Unreal engine. */
  engine: Session;
  /** Lists the Unreal projects in its workspace. */
  load: (engineId: string) => Promise<UnrealProject[]>;
  /** Whether the agent is working on a turn. */
  agentRunning: boolean;
  /** Whether the agent can be asked at all. */
  canAsk: boolean;
  /** Asks the agent, as the person's message. */
  onAsk: (text: string) => Promise<void>;
  /** Puts the engine's Desktop on screen. */
  onShowDesktop: () => void;
}

/**
 * Renders the Unreal projects a running Unreal engine found in its workspace, each with a button
 * that asks the agent to open it in the editor.
 *
 * @param props The component's props.
 * @returns The block, or nothing on a control plane that cannot list them.
 */
function UnrealProjects({ engine, load, agentRunning, canAsk, onAsk, onShowDesktop }: UnrealProjectsProps) {
  const [found, setFound] = useState<UnrealProject[] | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [asked, setAsked] = useState<string | null>(null);
  const [askError, setAskError] = useState<unknown>(null);
  const [reading, setReading] = useState(0);

  useEffect(() => {
    let current = true;
    load(engine.id)
      .then((listed) => {
        if (current) {
          setFound(listed);
          setFailure(null);
        }
      })
      .catch((reason: unknown) => {
        if (current) {
          setFailure(reason);
        }
      });
    return () => {
      current = false;
    };
  }, [engine.id, load, agentRunning, reading]);

  /**
   * Asks the agent to open a project in the editor.
   *
   * @param project The project.
   */
  async function open(project: UnrealProject): Promise<void> {
    setAsked(project.path);
    setAskError(null);
    try {
      await onAsk(`Open ${project.name} in Unreal (${project.path}).`);
    } catch (reason) {
      setAskError(reason);
    }
  }

  if (isMissing(failure)) {
    return null;
  }
  return (
    <div className="mt-2.5 border-t border-line pt-2.5">
      <div className="flex items-center gap-1.5">
        <p className="flex flex-1 items-center gap-1.5 text-[0.6875rem] font-semibold tracking-wide text-faint uppercase">
          <Box className="size-3" aria-hidden="true" />
          Unreal projects
        </p>
        <button
          type="button"
          className="icon-btn icon-btn-sm"
          aria-label="Look for projects again"
          title="Look again"
          onClick={() => {
            setReading(reading + 1);
          }}
        >
          <RefreshCw aria-hidden="true" />
        </button>
      </div>
      <div aria-live="polite">
        {found === null ? (
          <p className="mt-1.5 text-xs text-faint">
            {failure === null ? 'Looking for projects…' : `Could not look for projects: ${describeError(failure)}`}
          </p>
        ) : found.length === 0 ? (
          <div className="mt-1.5 text-xs leading-relaxed text-muted">
            <p>
              No project here yet. Clone your game in the Desktop view (sign in to the GitHub client first), or ask the
              agent for a new one from a template.
            </p>
            <button type="button" className="btn btn-ghost btn-sm mt-2 h-7 px-2.5 text-xs" onClick={onShowDesktop}>
              <Monitor className="size-3.5" aria-hidden="true" />
              Show Desktop
            </button>
          </div>
        ) : (
          <ul className="mt-1.5 grid grid-cols-1 gap-1.5">
            {found.map((project) => (
              <UnrealProjectCard
                key={project.path}
                project={project}
                asked={agentRunning && asked === project.path}
                askable={canAsk && !agentRunning}
                busyReason={!canAsk ? 'The agent is not switched on here.' : agentRunning ? 'The agent is busy.' : null}
                onOpen={() => {
                  void open(project);
                }}
              />
            ))}
          </ul>
        )}
      </div>
      {askError === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={askError} />
        </div>
      )}
    </div>
  );
}

/** Props of {@link UnrealProjectCard}. */
interface UnrealProjectCardProps {
  /** The project. */
  project: UnrealProject;
  /** Whether the agent was just asked to open it. */
  asked: boolean;
  /** Whether the agent can be asked now. */
  askable: boolean;
  /** Why it cannot, when it cannot. */
  busyReason: string | null;
  /** Asks the agent to open it. */
  onOpen: () => void;
}

/**
 * Renders one Unreal project: its name, its version, what it is made of, and how it opens.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function UnrealProjectCard({ project, asked, askable, busyReason, onOpen }: UnrealProjectCardProps) {
  const facts = [
    project.cpp_modules.length === 0
      ? 'Blueprints'
      : `C++, ${project.cpp_modules.length} module${project.cpp_modules.length === 1 ? '' : 's'}`,
    `${project.plugins.length} plugin${project.plugins.length === 1 ? '' : 's'}`,
    project.lfs === true ? 'Git LFS' : typeof project.lfs === 'string' ? `Git LFS: ${project.lfs}` : null,
    project.size_bytes === null ? null : sizeText(project.size_bytes),
  ].filter((fact) => fact !== null);
  const opensAsIs = project.version === 'same';
  const refused = project.version === 'newer';
  return (
    <li className="rounded-lg border border-line bg-white/[0.02] p-2.5">
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-sm font-medium" title={project.path}>
          {project.name}
        </span>
        <span
          className={cx('pill h-5 px-2 text-[0.6875rem]', refused ? 'text-bad' : opensAsIs ? 'text-ok' : 'text-warn')}
        >
          {project.engine_association === '' ? 'No version' : `UE ${project.engine_association}`}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted">{facts.join(' · ')}</p>
      {opensAsIs ? null : <p className="mt-1 text-xs leading-relaxed text-faint">{project.opens}</p>}
      {project.plugins_to_check.length === 0 ? null : (
        <p className="mt-1 text-xs leading-relaxed text-warn">
          May not come along: {project.plugins_to_check.join(', ')}
        </p>
      )}
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          className="btn btn-primary btn-sm h-7 px-2.5 text-xs"
          disabled={!askable || refused}
          title={refused ? project.opens : (busyReason ?? undefined)}
          onClick={onOpen}
        >
          {asked ? (
            <span className="spinner size-3" aria-hidden="true" />
          ) : (
            <Box className="size-3.5" aria-hidden="true" />
          )}
          {asked ? 'Asked the agent' : 'Open in Unreal'}
        </button>
        <span className="mono min-w-0 flex-1 truncate text-[0.6875rem] text-faint" title={project.path}>
          {project.path}
        </span>
      </div>
    </li>
  );
}

/** Props of {@link StartForm}. */
interface StartFormProps {
  /** The open project. */
  project: Project;
  /** What the control plane can do. */
  health: Health | null;
  /** The signed-in account. */
  me: Me | null;
  /** The GitHub connection, through which an app on the person's own license is linked. */
  github: GitHub;
  /** Starts an engine. */
  onStart: (app: string, tier: string) => Promise<Session>;
  /** Opens the credits dialog. */
  onAddCredits: () => void;
}

/**
 * Renders the form that starts an engine: an app and a tier.
 *
 * @param props The component's props.
 * @returns The form.
 */
function StartForm({ project, health, me, github, onStart, onAddCredits }: StartFormProps) {
  const appId = useId();
  const tierId = useId();
  const discipline = findDiscipline(project.discipline);
  const [first, rest] = useMemo(() => {
    const own = (discipline?.engines ?? []).map(findApp).filter((app) => app !== undefined);
    return [own, catalog.apps.filter((app) => !own.includes(app))];
  }, [discipline]);
  const [pickedApp, setPickedApp] = useState(() => [...first, ...rest].find(canStart)?.id ?? '');
  const openTiers = health?.tiers ?? null;
  const isOpen = (tier: Tier): boolean => openTiers === null || openTiers.includes(tier.id);
  const [pickedTier, setPickedTier] = useState<string | null>(null);
  const app = findApp(pickedApp);
  const usable = (candidate: Tier): boolean => isOpen(candidate) && (app === undefined || tierFits(candidate, app));
  const tier =
    catalog.tiers.find((candidate) => candidate.id === pickedTier && usable(candidate)) ??
    catalog.tiers.find((candidate) => candidate.gpu !== null && usable(candidate)) ??
    catalog.tiers.find(usable);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const ready = app !== undefined && canStart(app) && tier !== undefined;

  /**
   * Starts the engine the form describes.
   *
   * @param event The form's submission.
   */
  async function submit(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!ready) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onStart(app.id, tier.id);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  const option = (candidate: (typeof catalog.apps)[number]) => {
    const status = appStatusLabel(candidate);
    return (
      <option key={candidate.id} value={candidate.id} disabled={!canStart(candidate)}>
        {candidate.name}
        {status === '' ? '' : ` (${status})`}
      </option>
    );
  };
  const minutes = me === null || tier === undefined ? null : minutesFor(me.credits, tier);
  return (
    <form
      className="mt-3 rounded-xl border border-dashed border-line-strong p-2.5"
      onSubmit={(event) => {
        void submit(event);
      }}
    >
      <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_auto] gap-1.5">
        <label htmlFor={appId} className="sr-only">
          App
        </label>
        <select
          id={appId}
          className="field field-sm"
          value={pickedApp}
          onChange={(event) => {
            setPickedApp(event.target.value);
          }}
        >
          {first.length === 0 ? null : (
            <optgroup label={`For ${discipline?.name ?? 'this project'}`}>{first.map(option)}</optgroup>
          )}
          <optgroup label="Other apps">{rest.map(option)}</optgroup>
        </select>
        <label htmlFor={tierId} className="sr-only">
          Tier
        </label>
        <select
          id={tierId}
          className="field field-sm"
          value={tier?.id ?? ''}
          onChange={(event) => {
            setPickedTier(event.target.value);
          }}
        >
          {catalog.tiers.map((candidate) => (
            <option key={candidate.id} value={candidate.id} disabled={!usable(candidate)} title={gpuLabel(candidate)}>
              {candidate.name}
              {!isOpen(candidate) ? ' (off)' : app !== undefined && !tierFits(candidate, app) ? ' (needs a GPU)' : ''}
            </option>
          ))}
        </select>
        <button type="submit" className="btn btn-ghost btn-sm h-9 rounded-[0.65rem] px-3" disabled={!ready || busy}>
          {busy ? (
            <span className="spinner size-3.5" aria-hidden="true" />
          ) : (
            <Play className="size-3.5" aria-hidden="true" />
          )}
          Start
        </button>
      </div>
      <p className="mt-2 px-0.5 text-xs text-faint">
        {tier === undefined
          ? 'No tier is switched on right now.'
          : `${gpuLabel(tier)}${minutes === null ? '' : ` · about ${minutesText(minutes)} on your credits`}`}
      </p>
      {app !== undefined && isOwnLicense(app) ? <EditorNote app={app} github={github} /> : null}
      {error === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={error} onAddCredits={onAddCredits} />
        </div>
      )}
    </form>
  );
}

/** Props of {@link EditorNote}. */
interface EditorNoteProps {
  /** The app with a part on the person's own license: Unreal Engine, whose editor is. */
  app: CatalogApp;
  /** The GitHub connection, which carries the Epic link. */
  github: GitHub;
}

/**
 * Renders what an Unreal engine starts with: its desktop always, and the person's own copy of the
 * editor where the control plane reads their Epic link.
 *
 * It asks nothing of the person: the engine starts either way, and the agent says how to link
 * Epic when they ask for the editor.
 *
 * @param props The component's props.
 * @returns The note.
 */
function EditorNote({ app, github }: EditorNoteProps) {
  return (
    <p className="mt-1.5 px-0.5 text-xs leading-relaxed text-muted" aria-live="polite">
      {github.status?.epic_linked === true
        ? `With your own Unreal Editor ${app.version}, on your Epic account, beside a desktop with the GitHub client, Git LFS, Firefox, and Blender.`
        : 'Starts with a desktop: the GitHub client, Git LFS, Firefox, and Blender. The Unreal Editor comes on your Epic account; the agent says how to link it when you open a project.'}
    </p>
  );
}

/** The outcome of returning from GitHub, as its callback reports it. */
export type GitHubReturn = 'connected' | 'failed' | null;

/** Props of {@link GitHubSection}. */
interface GitHubSectionProps {
  /** The open project. */
  project: Project;
  /** The GitHub connection. */
  github: GitHub;
  /** What the control plane can do. */
  health: Health | null;
  /** The outcome of a return from GitHub, shown once. */
  returned: GitHubReturn;
  /** Links the project to a repository. */
  onLink: (link: RepoLink) => Promise<void>;
  /** Unlinks it. */
  onUnlink: () => Promise<void>;
}

/**
 * Renders GitHub: connecting, the account, and the project's repository.
 *
 * @param props The component's props.
 * @returns The GitHub block.
 */
export function GitHubSection({ project, github, health, returned, onLink, onUnlink }: GitHubSectionProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const status = github.status;

  /**
   * Runs an action, showing its progress and what it failed with.
   *
   * @param action The action.
   */
  async function run(action: () => Promise<void>): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  let body;
  if (health?.github === false || status?.configured === false) {
    body = (
      <Notice tone="info">
        GitHub is not configured on this server yet. Projects work without it; linking arrives once it is.
      </Notice>
    );
  } else if (github.availability === 'missing' || github.availability === 'offline') {
    body = <p className="text-sm text-faint">GitHub arrives with the studio&rsquo;s backend.</p>;
  } else if (github.availability === 'loading') {
    body = <div className="h-9 animate-pulse rounded-xl bg-white/[0.04]" aria-label="Loading GitHub" />;
  } else if (github.availability === 'failed' || status === null) {
    body = <p className="text-sm text-bad">Could not read your GitHub connection.</p>;
  } else if (!status.connected) {
    body = (
      <div>
        <p className="text-sm text-muted">
          Keep the script, the library manifest, and the shot list in a repository of your own.
        </p>
        <button
          type="button"
          className="btn btn-ghost btn-sm mt-3 w-full"
          disabled={busy}
          onClick={() => {
            void run(github.connect);
          }}
        >
          {busy ? <span className="spinner size-3.5" aria-hidden="true" /> : <GitHubMark className="size-4" />}
          Connect GitHub
        </button>
      </div>
    );
  } else {
    body = (
      <div className="grid grid-cols-1 gap-3">
        <div className="flex items-center gap-2.5">
          <Avatar url={status.avatar_url} login={status.login} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{status.login ?? 'Connected'}</span>
            <span className="block text-xs text-faint">GitHub connected</span>
          </span>
          <Menu
            label="GitHub account"
            trigger={<GitHubMark className="size-3.5" />}
            triggerClassName="icon-btn"
            items={[
              {
                label: 'Reconnect GitHub',
                icon: <RefreshCw aria-hidden="true" />,
                onSelect: () => {
                  void run(github.connect);
                },
              },
              {
                label: 'Disconnect GitHub',
                icon: <LogOut aria-hidden="true" />,
                danger: true,
                onSelect: () => {
                  void run(github.disconnect);
                },
              },
            ]}
          />
        </div>
        {project.github_repo === null ? (
          <RepoPicker
            project={project}
            loadRepos={github.repos}
            busy={busy}
            onLink={(link) => run(() => onLink(link))}
          />
        ) : (
          <div className="flex items-center gap-2 rounded-xl border border-line bg-white/[0.025] py-2 pr-1.5 pl-3">
            <GitHubMark className="size-3.5 flex-none text-muted" />
            <a
              className="min-w-0 flex-1 truncate text-sm font-medium hover:underline"
              href={`https://github.com/${project.github_repo}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {project.github_repo}
            </a>
            <a
              className="icon-btn icon-btn-sm"
              href={`https://github.com/${project.github_repo}`}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open ${project.github_repo} on GitHub`}
            >
              <ExternalLink aria-hidden="true" />
            </a>
            <button
              type="button"
              className="icon-btn icon-btn-sm"
              aria-label="Unlink the repository"
              title="Unlink"
              disabled={busy}
              onClick={() => {
                void run(onUnlink);
              }}
            >
              <Unlink aria-hidden="true" />
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <h3 className="section-label flex items-center gap-1.5">
        <GitHubMark className="size-3" />
        GitHub
      </h3>
      <div className="mt-2">
        {returned === 'connected' && status?.connected === true ? (
          <div className="mb-2.5">
            <Notice tone="info">GitHub is connected. Link this project to a repository below.</Notice>
          </div>
        ) : null}
        {returned === 'failed' ? (
          <div className="mb-2.5">
            <Notice tone="warn">GitHub did not connect. Try again, and approve the access GitHub asks for.</Notice>
          </div>
        ) : null}
        {body}
        {error === null ? null : (
          <div className="mt-2.5">
            <ErrorNotice error={error} />
          </div>
        )}
      </div>
    </div>
  );
}

/** Props of {@link Avatar}. */
interface AvatarProps {
  /** The avatar's address, or `null`. */
  url: string | null;
  /** The login it stands for. */
  login: string | null;
}

/**
 * Renders a GitHub avatar, or the login's initial where the image is missing.
 *
 * @param props The component's props.
 * @returns The avatar.
 */
function Avatar({ url, login }: AvatarProps) {
  const [failed, setFailed] = useState(false);
  if (url === null || failed) {
    return (
      <span className="grid size-8 place-items-center rounded-full border border-line-strong bg-ink-700 text-xs font-semibold uppercase">
        {login?.charAt(0) ?? '?'}
      </span>
    );
  }
  return (
    <img
      src={url}
      alt=""
      className="size-8 rounded-full border border-line-strong"
      onError={() => {
        setFailed(true);
      }}
    />
  );
}

/**
 * A repository name GitHub accepts, from a project's name.
 *
 * @param name The project's name.
 * @returns Letters, digits, and hyphens, in lowercase.
 */
function repoSlug(name: string): string {
  return (
    name
      .toLowerCase()
      .normalize('NFKD')
      .replace(/[^a-z0-9._-]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 100) || 'lathe-project'
  );
}

/** Props of {@link RepoPicker}. */
interface RepoPickerProps {
  /** The open project. */
  project: Project;
  /** Lists the person's repositories. */
  loadRepos: () => Promise<GitHubRepo[]>;
  /** Whether a link is being made. */
  busy: boolean;
  /** Links the project. */
  onLink: (link: RepoLink) => Promise<void>;
}

/**
 * Renders the choice of a repository: an existing one, or a new one.
 *
 * @param props The component's props.
 * @returns The picker.
 */
function RepoPicker({ project, loadRepos, busy, onLink }: RepoPickerProps) {
  const [mode, setMode] = useState<'existing' | 'new'>('existing');
  const [repos, setRepos] = useState<GitHubRepo[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [query, setQuery] = useState('');
  const [name, setName] = useState(() => repoSlug(project.name));
  const [privateRepo, setPrivateRepo] = useState(true);
  const now = useNow(false);
  const nameId = useId();

  useEffect(() => {
    if (mode !== 'existing' || repos !== null) {
      return;
    }
    let current = true;
    loadRepos()
      .then((listed) => {
        if (current) {
          setRepos(listed);
        }
      })
      .catch((failure: unknown) => {
        if (current) {
          setLoadError(failure);
        }
      });
    return () => {
      current = false;
    };
  }, [mode, repos, loadRepos]);

  const shown = (repos ?? []).filter((repo) => repo.full_name.toLowerCase().includes(query.trim().toLowerCase()));

  /**
   * Creates the repository and links it.
   *
   * @param event The form's submission.
   */
  function create(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    void onLink({ create: { name: name.trim(), private: privateRepo } });
  }

  return (
    <div className="rounded-xl border border-line p-2.5">
      <div className="segmented w-full" role="tablist" aria-label="Repository">
        {(['existing', 'new'] as const).map((choice) => (
          <button
            key={choice}
            type="button"
            role="tab"
            aria-selected={mode === choice}
            className={cx('segment flex-1 justify-center', mode === choice && 'bg-white/10 text-fg')}
            onClick={() => {
              setMode(choice);
            }}
          >
            {choice === 'existing' ? 'Link existing' : 'Create new'}
          </button>
        ))}
      </div>
      {mode === 'existing' ? (
        <div className="mt-2.5">
          <input
            type="search"
            className="field field-sm"
            placeholder="Find a repository"
            aria-label="Find a repository"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
          />
          {loadError === null ? null : (
            <div className="mt-2">
              <ErrorNotice error={loadError} />
            </div>
          )}
          <ul className="thin-scroll mt-1.5 max-h-48 overflow-y-auto">
            {repos === null && loadError === null ? (
              <li className="px-2 py-2 text-xs text-faint">Loading your repositories…</li>
            ) : shown.length === 0 && loadError === null ? (
              <li className="px-2 py-2 text-xs text-faint">No repository matches.</li>
            ) : (
              shown.map((repo) => (
                <li key={repo.full_name}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-white/[0.05]"
                    disabled={busy}
                    onClick={() => {
                      void onLink({ repo: repo.full_name });
                    }}
                  >
                    {repo.private ? <Lock className="size-3 flex-none text-faint" aria-label="Private" /> : null}
                    <span className="min-w-0 flex-1 truncate">{repo.full_name}</span>
                    <span className="text-[0.6875rem] text-faint">{ago(repo.updated_at, now)}</span>
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      ) : (
        <form className="mt-2.5 grid grid-cols-1 gap-2" onSubmit={create}>
          <label htmlFor={nameId} className="sr-only">
            Repository name
          </label>
          <input
            id={nameId}
            className="field field-sm mono"
            required
            maxLength={100}
            pattern="[A-Za-z0-9._\-]+"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
          <label className="flex items-center gap-2 text-xs text-muted">
            <input
              type="checkbox"
              className="accent-ember-300"
              checked={privateRepo}
              onChange={(event) => {
                setPrivateRepo(event.target.checked);
              }}
            />
            Private repository
          </label>
          <button type="submit" className="btn btn-ghost btn-sm h-8" disabled={busy || name.trim() === ''}>
            {busy ? (
              <span className="spinner size-3.5" aria-hidden="true" />
            ) : (
              <Plus className="size-3.5" aria-hidden="true" />
            )}
            Create and link
          </button>
        </form>
      )}
    </div>
  );
}
