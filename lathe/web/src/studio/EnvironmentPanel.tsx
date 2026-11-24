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
 * control plane admits for the team's accounts alone, or one on the person's own license can be
 * started, and the rest show their status. A tier the control plane does not list as open is shown
 * but cannot be chosen. Choosing an app on the person's own license (Unreal Engine, on their Epic
 * account) shows whether that license is linked, as the control plane reads it through their
 * GitHub account: linked; not linked, with the steps that link it and Epic's page on them; or
 * unknown, with GitHub to connect first or again. It starts once linked.
 *
 * GitHub is the person's own account, connected once through the control plane's OAuth App and
 * then linked per project to a repository, existing or created for it. The block says plainly
 * when this server has no GitHub configured, or no studio routes yet, instead of failing.
 * @module
 */
import { useEffect, useId, useMemo, useState, type SubmitEvent } from 'react';
import { CircleStop, ExternalLink, Lock, LogOut, MonitorPlay, Play, Plus, Unlink } from 'lucide-react';
import { isActive, type GitHubRepo, type Health, type Me, type Project, type RepoLink, type Session } from '../lib/api';
import {
  catalog,
  findApp,
  findDiscipline,
  findTier,
  gpuLabel,
  isOwnLicense,
  minutesFor,
  ownLicenseLabel,
  type CatalogApp,
  type Tier,
} from '../lib/catalog';
import { cx } from '../lib/cx';
import { clock, minutesText, timestamp } from '../lib/format';
import { useNow } from './hooks';
import { GitHubMark, Menu } from './Menu';
import { describeEndReason } from './messages';
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
  /** Opens the credits dialog. */
  onAddCredits: () => void;
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
  onAddCredits,
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
            />
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
}

/**
 * Renders one active engine.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function EngineRow({ engine, onScreen, onShow, onStop }: EngineRowProps) {
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
  const tier =
    catalog.tiers.find((candidate) => candidate.id === pickedTier && isOpen(candidate)) ??
    catalog.tiers.find((candidate) => candidate.gpu !== null && isOpen(candidate)) ??
    catalog.tiers.find(isOpen);
  const app = findApp(pickedApp);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const ready =
    app !== undefined &&
    canStart(app) &&
    tier !== undefined &&
    (!isOwnLicense(app) || github.status?.epic_linked === true);

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
            <option key={candidate.id} value={candidate.id} disabled={!isOpen(candidate)} title={gpuLabel(candidate)}>
              {candidate.name}
              {isOpen(candidate) ? '' : ' (off)'}
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
      {app !== undefined && isOwnLicense(app) ? <EpicLink app={app} github={github} /> : null}
      {error === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={error} onAddCredits={onAddCredits} />
        </div>
      )}
    </form>
  );
}

/** Props of {@link EpicLink}. */
interface EpicLinkProps {
  /** The app on the person's own license: Unreal Engine. */
  app: CatalogApp;
  /** The GitHub connection, which carries the link. */
  github: GitHub;
}

/**
 * Renders whether the person's Epic account, the license Unreal Engine starts on, is linked.
 *
 * The control plane reads the link from what the person's GitHub account can see, and this shows
 * its answer. Not linked, it lists the catalog's steps and Epic's page on them; unknown, it offers
 * GitHub to connect, first or again, after which the link is read anew.
 *
 * @param props The component's props.
 * @returns The block.
 */
function EpicLink({ app, github }: EpicLinkProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const status = github.status;
  const label = ownLicenseLabel(app);

  /** Sends the person to GitHub, to connect or to connect again; the page comes back here. */
  async function connect(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await github.connect();
    } catch (failure) {
      setError(failure);
      setBusy(false);
    }
  }

  const connectButton = (text: string) => (
    <button
      type="button"
      className="btn btn-ghost btn-sm mt-2 h-8 w-full text-xs"
      disabled={busy}
      onClick={() => {
        void connect();
      }}
    >
      {busy ? <span className="spinner size-3.5" aria-hidden="true" /> : <GitHubMark className="size-3.5" />}
      {text}
    </button>
  );

  let body;
  if (github.availability === 'loading') {
    body = <p className="text-xs text-faint">Checking the link to Epic…</p>;
  } else if (!status?.configured) {
    body = (
      <Notice tone="warn">
        {app.name} starts through a GitHub account linked to Epic, and this server cannot connect GitHub yet.
      </Notice>
    );
  } else if (!status.connected) {
    body = (
      <>
        <Notice tone="warn" title="Connect GitHub first.">
          {app.name} runs on the Epic account your GitHub account is linked to.
        </Notice>
        {connectButton('Connect GitHub')}
      </>
    );
  } else if (status.epic_linked === true) {
    body = (
      <Notice tone="info" title={`${label} is linked.`}>
        {status.login === null ? 'Through your GitHub account.' : `Through GitHub, as ${status.login}.`}
      </Notice>
    );
  } else if (status.epic_linked === false) {
    body = (
      <>
        <Notice tone="warn" title={`${label} is not linked yet.`}>
          {app.name} runs on your own Epic account, which Epic links to your GitHub account
          {status.login === null ? '' : ` (${status.login})`}.
        </Notice>
        <ol className="mt-2 grid list-decimal gap-1 pl-5 text-xs leading-relaxed text-muted">
          {(app.license?.steps ?? []).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        {app.license === undefined ? null : (
          <a
            className="link mt-2 inline-flex items-center gap-1 text-xs"
            href={app.license.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Epic&rsquo;s page on linking GitHub
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
        )}
        {connectButton('Reconnect GitHub')}
      </>
    );
  } else {
    body = (
      <>
        <Notice tone="warn" title="Reconnect GitHub.">
          It was connected before {app.name} needed it to read packages, which checking the link to Epic and
          pulling the engine take.
        </Notice>
        {connectButton('Reconnect GitHub')}
      </>
    );
  }
  return (
    <div className="mt-2.5" aria-live="polite">
      {body}
      {error === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={error} />
        </div>
      )}
    </div>
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
