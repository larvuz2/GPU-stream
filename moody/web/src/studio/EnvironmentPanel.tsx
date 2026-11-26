/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Environment panel: the project's engines, and its repositories. What the agent itself
 * works with (connectors, subagents, skills, and the tools it may run without asking) follows
 * them, from `EnvironmentAgent.tsx`.
 *
 * Engines are catalog apps running as sessions of the project. Each shows its state, its clock
 * while it runs, and the controls that put it on the screen or stop it. One that is not up yet
 * reads as work under way, which is lavender here as everywhere: its card is edged in it, a bar
 * runs under its name, and its line counts the time since it was asked for ("Waiting for a
 * machine", then "Starting"), so nobody mistakes a machine being built for one that is ready,
 * whose light is lime. The start form offers the
 * discipline's engines first, then every other app, less the engines the person's settings set
 * aside (`appsSetAside`: of two engines Settings chooses between, the one not chosen); only an
 * available app, a team one, which the
 * control plane admits for the team's accounts alone, or one with a part on the person's own
 * license can be started, and the rest show their status. A tier the control plane does not list
 * as open is shown but cannot be chosen. Unreal Engine, whose editor runs on the person's Epic
 * account, starts at once whatever that account: the form says what the engine comes with, the
 * editor too where Epic's registry lets the person's Epic connection pull it, and otherwise offers
 * "Connect Epic" under the steps that link a GitHub account to Epic first. Nothing of it is
 * required to start: the engine starts as its desktop either way.
 *
 * A running Unreal engine's card lists the Unreal projects in its workspace, each with what it is
 * and an "Open in Unreal" button that asks the agent to open it, the way the person would in a
 * message. An engine of a project linked to a repository clones it as it starts, and the card says
 * so ("Cloning MultiverseBR…") until the machine reports it done, then lists what it found; a clone
 * that failed says why, with the Desktop view a click away to clone by hand. Before there is a
 * project, the card says how one gets there. The list is read when the card appears, when the
 * clone finishes, whenever the agent starts or ends a turn (it may have cloned or made one), and
 * when the person asks to look again, never on a timer: reading the machine counts as use of it,
 * and a page left open must not keep an engine from shutting down once it is idle.
 *
 * Repositories are a list: the ones the project is linked to, each with its branch where one is
 * set and the controls that open or unlink it. A project links one today, and the list holds as
 * many as it comes to have. GitHub is the person's own account, connected once through the control
 * plane's GitHub App and then linked per project to a repository of the app's installations they
 * reach. A repository the
 * list lacks is one the app is not installed on: "Don't see your repository?" opens the app's
 * installation page, where the person installs it, or asks their organization's owners to. The app
 * makes no repositories, so a new one is made on GitHub's own page and then linked. The block says
 * plainly when this server has no GitHub configured, or no studio routes yet, instead of failing.
 * @module
 */
import { useEffect, useId, useMemo, useState, type ReactNode, type SubmitEvent } from 'react';
import {
  Box,
  CircleStop,
  ExternalLink,
  FolderGit2,
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
  type EngineClone,
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
import { FoldSection } from './FoldSection';
import { useNow } from './hooks';
import { GitHubMark, Menu } from './Menu';
import { describeEndReason, describeError } from './messages';
import { ErrorNotice, Notice } from './Notice';
import { RepoList } from './RepoList';
import { appStatusLabel, appsSetAside, canStart } from './present';
import type { Epic, GitHub } from './useAccount';

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
  /** The Epic connection, through which Unreal Engine's editor, on the person's own license, is pulled. */
  epic: Epic;
  /** The outcome of a return from connecting Epic, shown once. */
  epicReturned: EpicReturn;
  /** Starts an engine. */
  onStart: (app: string, tier: string) => Promise<Session>;
  /** Stops an engine. */
  onStop: (id: string) => Promise<void>;
  /** Puts an engine on screen. */
  onShow: (id: string) => void;
  /** Puts one picture of an engine on screen, such as an Unreal engine's Desktop. */
  onShowPicture: (id: string, stream: string) => void;
  /** Opens Settings on Billing, where credits are bought. */
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
  epic,
  epicReturned,
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
    <FoldSection id="environment.engines" label="Engines">
      <EpicReturnNotice returned={epicReturned} epic={epic} />
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
                  repo={project.github_repo}
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
          epic={epic}
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
    </FoldSection>
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
  const now = useNow(true);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const app = findApp(engine.app);
  const tier = findTier(engine.tier);
  const started = timestamp(engine.started_at);
  const asked = timestamp(engine.created_at);
  const waited = asked === null ? '' : ` · ${clock(now - asked)}`;

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
      ? `Waiting for a machine${engine.queue_position === null ? '' : ` · #${engine.queue_position} in line`}${waited}`
      : engine.status === 'starting'
        ? `Starting${waited}`
        : started === null
          ? 'Running'
          : `Running · ${clock(now - started)}`;
  return (
    <li
      className={cx(
        'rounded-xl border bg-white/[0.025] p-2.5 transition-colors',
        !running ? 'border-[var(--ai-line)]' : onScreen ? 'border-line-strong' : 'border-line',
      )}
      style={{ '--accent': app?.accent }}
      aria-busy={!running}
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
              <span className={cx('dot dot-live', running ? '' : 'dot-busy')} aria-hidden="true" />
              <span className={cx('truncate tabular-nums', running ? '' : 'text-lavender')}>{state}</span>
              {tier === undefined ? null : <span className="flex-none text-faint">· {tier.name}</span>}
            </span>
          </span>
        </button>
        {onScreen && running ? <span className="pill h-6 text-[0.6875rem] text-fg">On screen</span> : null}
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
      {running ? null : (
        <div className="mt-2.5">
          <div className="progress" role="progressbar" aria-label={`${app?.name ?? engine.app} is starting`} />
          <p className="mt-1.5 text-[0.6875rem] text-faint">
            {engine.status === 'queued'
              ? 'A machine is being found for it. Nothing is billed until it runs.'
              : 'Its machine is being built: usually about a minute. Nothing is billed until it runs.'}
          </p>
        </div>
      )}
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
  /** The repository the project is linked to, which the engine clones as it starts, or `null`. */
  repo: string | null;
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
 * The name a clone is shown by: the folder it clones into, which is the repository's name.
 *
 * @param clone The clone.
 * @param repo The repository the project is linked to, as `owner/name`, or `null`.
 * @returns The name.
 */
function cloneName(clone: EngineClone, repo: string | null): string {
  return clone.path.split('/').filter(Boolean).pop() ?? repo?.split('/').pop() ?? 'the repository';
}

/**
 * Renders the Unreal projects a running Unreal engine found in its workspace, each with a button
 * that asks the agent to open it in the editor, after the clone the engine made as it started
 * while that is still running or where it failed.
 *
 * @param props The component's props.
 * @returns The block, or nothing on a control plane that cannot list them.
 */
function UnrealProjects({ engine, repo, load, agentRunning, canAsk, onAsk, onShowDesktop }: UnrealProjectsProps) {
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
  }, [engine.id, load, agentRunning, reading, engine.clone?.state]);

  const clone = engine.clone;
  const cloning = clone?.state === 'cloning';

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
        {clone === undefined || clone.state === 'done' ? null : (
          <div className="mt-1.5 text-xs leading-relaxed">
            <p className={cx('flex items-center gap-1.5', cloning ? 'text-muted' : 'text-bad')}>
              {cloning ? (
                <span className="spinner size-3" aria-hidden="true" />
              ) : (
                <FolderGit2 className="size-3.5" aria-hidden="true" />
              )}
              {cloning
                ? `Cloning ${cloneName(clone, repo)}…`
                : `Could not clone ${cloneName(clone, repo)}${clone.detail === '' ? '.' : `: ${clone.detail}`}`}
            </p>
            {cloning && clone.detail !== '' ? <p className="mt-0.5 text-faint">{clone.detail}</p> : null}
            {cloning ? null : (
              <button type="button" className="btn btn-ghost btn-sm mt-2 h-7 px-2.5 text-xs" onClick={onShowDesktop}>
                <Monitor className="size-3.5" aria-hidden="true" />
                Clone it in the Desktop
              </button>
            )}
          </div>
        )}
        {cloning ? null : found === null ? (
          <p className="mt-1.5 text-xs text-faint">
            {failure === null ? 'Looking for projects…' : `Could not look for projects: ${describeError(failure)}`}
          </p>
        ) : found.length === 0 ? (
          <div className="mt-1.5 text-xs leading-relaxed text-muted">
            <p>
              No project here yet. Link the project to your game&rsquo;s repository below and start Unreal again to clone
              it, clone it in the Desktop view&rsquo;s GitHub client, or ask the agent for a new one from a template.
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
  /** The Epic connection, through which an app on the person's own license is linked. */
  epic: Epic;
  /** Starts an engine. */
  onStart: (app: string, tier: string) => Promise<Session>;
  /** Opens Settings on Billing, where credits are bought. */
  onAddCredits: () => void;
}

/**
 * Renders the form that starts an engine: an app and a tier.
 *
 * @param props The component's props.
 * @returns The form.
 */
function StartForm({ project, health, me, epic, onStart, onAddCredits }: StartFormProps) {
  const appId = useId();
  const tierId = useId();
  const discipline = findDiscipline(project.discipline);
  const settings = me?.settings;
  const [first, rest] = useMemo(() => {
    const aside = appsSetAside(settings);
    const own = (discipline?.engines ?? [])
      .map(findApp)
      .filter((app) => app !== undefined)
      .filter((app) => !aside.has(app.id));
    return [own, catalog.apps.filter((app) => !aside.has(app.id) && !own.includes(app))];
  }, [discipline, settings]);
  const [pickedApp, setPickedApp] = useState<string | null>(null);
  const openTiers = health?.tiers ?? null;
  const isOpen = (tier: Tier): boolean => openTiers === null || openTiers.includes(tier.id);
  const [pickedTier, setPickedTier] = useState<string | null>(null);
  // The app picked while it is still offered, else the first that can be started: a change in Settings can take the
  // picked one out of the list
  const offered = [...first, ...rest];
  const app = offered.find((candidate) => candidate.id === pickedApp) ?? offered.find(canStart);
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
          value={app?.id ?? ''}
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
      {app !== undefined && isOwnLicense(app) ? <EditorNote app={app} epic={epic} health={health} /> : null}
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
  /** The Epic connection, which the editor is pulled with. */
  epic: Epic;
  /** What the control plane can do. */
  health: Health | null;
}

/**
 * Renders what an Unreal engine starts with: its desktop always, and the person's own copy of the
 * editor where Epic's registry lets their Epic connection pull it.
 *
 * Where it does not, the catalog's steps say how to link a GitHub account to Epic, and "Connect
 * Epic" connects that account; once linked on Epic's site, "Check again" asks the registry anew.
 * The engine starts either way, as its desktop.
 *
 * @param props The component's props.
 * @returns The note.
 */
function EditorNote({ app, epic, health }: EditorNoteProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const status = epic.status;
  const desktop = 'Starts with a desktop: the GitHub client, Git LFS, Firefox, and Blender.';
  if (status?.linked === true) {
    return (
      <p className="mt-1.5 px-0.5 text-xs leading-relaxed text-muted" aria-live="polite">
        With your own Unreal Editor {app.version}, on your Epic account ({status.login ?? 'connected'}), beside a desktop
        with the GitHub client, Git LFS, Firefox, and Blender.
      </p>
    );
  }
  if (health?.epic === false || !status?.configured) {
    return (
      <p className="mt-1.5 px-0.5 text-xs leading-relaxed text-muted" aria-live="polite">
        {desktop} The Unreal Editor comes on your Epic account; the agent says how to link it when you open a project.
      </p>
    );
  }

  /** Sends the browser to GitHub to connect the account linked to Epic. */
  async function connect(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await epic.connect();
    } catch (failure) {
      setError(failure);
      setBusy(false);
    }
  }

  // The last of the catalog's steps is connecting here, which the button does
  const steps = (app.license?.steps ?? []).slice(0, -1);
  return (
    <div className="mt-1.5 px-0.5 text-xs leading-relaxed text-muted" aria-live="polite">
      <p>
        {desktop}{' '}
        {status.connected && status.linked === false
          ? `Your GitHub account ${status.login ?? ''} is not linked to Epic yet, so the Unreal Editor does not come with it.`
          : status.connected
            ? `Moody could not check your Epic link: ${status.detail ?? 'no answer'}`
            : 'The Unreal Editor comes on your own Epic account, through the GitHub account linked to it.'}
      </p>
      {steps.length === 0 || (status.connected && status.linked === null) ? null : (
        <ol className="mt-1.5 list-decimal space-y-0.5 pl-4 text-faint">
          {steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="btn btn-ghost btn-sm h-7 px-2.5 text-xs"
          disabled={busy}
          onClick={() => {
            void connect();
          }}
        >
          {busy ? <span className="spinner size-3" aria-hidden="true" /> : <GitHubMark className="size-3.5" />}
          {status.connected ? 'Connect Epic again' : 'Connect Epic'}
        </button>
        {status.connected ? (
          <button type="button" className="btn btn-quiet btn-sm h-7 px-2.5 text-xs" onClick={epic.refresh}>
            <RefreshCw className="size-3.5" aria-hidden="true" />
            Check again
          </button>
        ) : null}
      </div>
      {error === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={error} />
        </div>
      )}
    </div>
  );
}

/** The outcome of returning from connecting Epic, as its callback reports it. */
export type EpicReturn = 'connected' | 'failed' | null;

/** Props of {@link EpicReturnNotice}. */
interface EpicReturnNoticeProps {
  /** The outcome of a return from connecting Epic. */
  returned: EpicReturn;
  /** The Epic connection, as read since. */
  epic: Epic;
}

/**
 * Renders, once, what connecting Epic came to: the editor coming with Unreal Engine, an account not
 * linked to Epic yet, or a connection that did not go through.
 *
 * @param props The component's props.
 * @returns The notice, or nothing when the page did not come back from connecting Epic.
 */
function EpicReturnNotice({ returned, epic }: EpicReturnNoticeProps) {
  if (returned === null || (returned === 'connected' && epic.status === null)) {
    return null;
  }
  const linked = epic.status?.linked;
  return (
    <div className="mt-2">
      {returned === 'failed' ? (
        <Notice tone="warn">Epic did not connect. Try again, and approve the access GitHub asks for.</Notice>
      ) : linked === true ? (
        <Notice tone="info">Epic is connected: Unreal Engine starts with your own editor from its next start.</Notice>
      ) : (
        <Notice tone="warn">
          Epic is connected, but that GitHub account is not linked to an Epic account yet. Link it on Epic&rsquo;s site,
          then check again under Unreal Engine.
        </Notice>
      )}
    </div>
  );
}

/** The outcome of returning from GitHub, as its callback reports it. */
export type GitHubReturn = 'connected' | 'installed' | 'requested' | 'failed' | null;

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
 * Renders the project's repositories as a list, over GitHub's own block: connecting, the account,
 * and linking a repository where none is.
 *
 * @param props The component's props.
 * @returns The repositories block.
 */
export function GitHubSection({ project, github, health, returned, onLink, onUnlink }: GitHubSectionProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const status = github.status;
  // A project links one repository today; the list below holds as many as it comes to have.
  const repositories =
    project.github_repo === null ? [] : [{ repo: project.github_repo, branch: project.github_branch ?? null }];

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
            void run(() => github.connect());
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
                label: 'Add repositories',
                icon: <Plus aria-hidden="true" />,
                onSelect: () => {
                  void run(() => github.install());
                },
              },
              {
                label: 'Reconnect GitHub',
                icon: <RefreshCw aria-hidden="true" />,
                onSelect: () => {
                  void run(() => github.connect());
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
        {repositories.length === 0 ? (
          <RepoPicker
            project={project}
            loadRepos={github.repos}
            busy={busy}
            onLink={(link) => run(() => onLink(link))}
            onInstall={() => run(() => github.install())}
          />
        ) : null}
      </div>
    );
  }

  return (
    <FoldSection
      id="environment.repositories"
      label={
        <>
          <GitHubMark className="size-3" />
          Repositories
          {repositories.length === 0 ? null : (
            <span className="font-normal tracking-normal tabular-nums">{repositories.length}</span>
          )}
        </>
      }
    >
      {repositories.length === 0 ? null : (
        <ul className="mt-2 grid grid-cols-1 gap-1.5" aria-label="Linked repositories">
          {repositories.map((repository) => (
            <li key={repository.repo} className="env-row">
              <span className="icon-tile size-8 rounded-lg">
                <FolderGit2 className="size-3.5" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1">
                <a
                  className="block truncate text-sm font-medium hover:underline"
                  href={`https://github.com/${repository.repo}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {repository.repo}
                </a>
                <span className="block truncate text-xs text-muted">{repository.branch ?? 'Default branch'}</span>
              </span>
              <a
                className="icon-btn icon-btn-sm"
                href={`https://github.com/${repository.repo}`}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open ${repository.repo} on GitHub`}
              >
                <ExternalLink aria-hidden="true" />
              </a>
              <button
                type="button"
                className="icon-btn icon-btn-sm"
                aria-label={`Unlink ${repository.repo}`}
                title="Unlink"
                disabled={busy}
                onClick={() => {
                  void run(onUnlink);
                }}
              >
                <Unlink aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2">
        {returned === 'connected' && status?.connected === true ? (
          <div className="mb-2.5">
            <Notice tone="info">GitHub is connected. Link this project to a repository below.</Notice>
          </div>
        ) : null}
        {returned === 'installed' ? (
          <div className="mb-2.5">
            <Notice tone="info">Moody&rsquo;s GitHub App is installed. Its repositories are listed below.</Notice>
          </div>
        ) : null}
        {returned === 'requested' ? (
          <div className="mb-2.5">
            <Notice tone="info">
              Your organization&rsquo;s owners were asked to install Moody&rsquo;s GitHub App. Its repositories appear
              here once one of them approves.
            </Notice>
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
    </FoldSection>
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
      .slice(0, 100) || 'moody-project'
  );
}

/**
 * GitHub's page for a new repository, filled with a name and a visibility.
 *
 * @param name The repository's name.
 * @param privateRepo Whether it is private.
 * @returns The page's address.
 */
function newRepoPage(name: string, privateRepo: boolean): string {
  const page = new URL('https://github.com/new');
  page.searchParams.set('name', name);
  page.searchParams.set('visibility', privateRepo ? 'private' : 'public');
  return page.href;
}

/** Props of {@link RepoPicker}. */
interface RepoPickerProps {
  /** The open project. */
  project: Project;
  /** Lists the repositories of the GitHub App's installations the person reaches. */
  loadRepos: () => Promise<GitHubRepo[]>;
  /** Whether a link is being made. */
  busy: boolean;
  /** Links the project. */
  onLink: (link: RepoLink) => Promise<void>;
  /** Sends the browser to the GitHub App's installation page. */
  onInstall: () => Promise<void>;
}

/**
 * Renders the choice of a repository: one of the GitHub App's, or a new one made on GitHub.
 *
 * @param props The component's props.
 * @returns The picker.
 */
function RepoPicker({ project, loadRepos, busy, onLink, onInstall }: RepoPickerProps) {
  const [mode, setMode] = useState<'existing' | 'new'>('existing');
  // Bumped to read the list again, as after a repository is made on GitHub
  const [reading, setReading] = useState(0);
  const [name, setName] = useState(() => repoSlug(project.name));
  const [privateRepo, setPrivateRepo] = useState(true);
  const nameId = useId();

  /**
   * Opens GitHub's page for the new repository in a new tab, and goes back to the list, read again,
   * to link it once it is made.
   *
   * @param event The form's submission.
   */
  function create(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    window.open(newRepoPage(name.trim(), privateRepo), '_blank', 'noopener,noreferrer');
    setReading(reading + 1);
    setMode('existing');
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
          <RepoList
            key={reading}
            loadRepos={loadRepos}
            busy={busy}
            onPick={(repo) => {
              void onLink({ repo: repo.full_name });
            }}
            onInstall={() => {
              void onInstall();
            }}
          />
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
              className="accent-white"
              checked={privateRepo}
              onChange={(event) => {
                setPrivateRepo(event.target.checked);
              }}
            />
            Private repository
          </label>
          <button type="submit" className="btn btn-ghost btn-sm h-8" disabled={busy || name.trim() === ''}>
            <ExternalLink className="size-3.5" aria-hidden="true" />
            Create on GitHub
          </button>
          <p className="text-xs leading-relaxed text-faint">
            GitHub makes the repository in a new tab. Then link it under Link existing; where Moody&rsquo;s app is on
            only some of your repositories, add it to the app first.
          </p>
        </form>
      )}
    </div>
  );
}
