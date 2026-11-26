/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Connections tab of Settings: the accounts the studio is connected to, in one place, each
 * with what it is for, how it stands, and how to connect or disconnect it.
 *
 * GitHub keeps a project's files in a repository of the person's. Epic is the GitHub account
 * their Epic account is linked to, which their own copy of the Unreal Editor is pulled with.
 * Claude is the other way round: an API key lets Claude reach the studio. A project still offers
 * GitHub and Epic where it needs them (the Environment panel, the new-project dialog); this tab
 * gathers them and does not replace those.
 *
 * Connecting leaves the page for GitHub and comes back to the address it left from, which names
 * this tab, so the person returns here and reads what the connection came to. An integration the
 * control plane is not configured for says so and offers nothing to press.
 * @module
 */
import { useState, type ReactNode } from 'react';
import { ArrowRight, Gamepad2, LogOut, Plus, RefreshCw, Sparkles } from 'lucide-react';
import { CommandBlock } from '../../components/Copy';
import type { Health } from '../../lib/api';
import { catalog } from '../../lib/catalog';
import { mcpEndpoint, mcpSetupCommand, SECRET_PLACEHOLDER } from '../../lib/mcp';
import type { EpicReturn, GitHubReturn } from '../EnvironmentPanel';
import { GitHubMark } from '../Menu';
import { ErrorNotice, Notice } from '../Notice';
import type { Availability, Epic, GitHub } from '../useAccount';
import { TabHeading } from './parts';

/** Props of {@link ConnectionsTab}. */
interface ConnectionsTabProps {
  /** The GitHub connection. */
  github: GitHub;
  /** The Epic connection. */
  epic: Epic;
  /** What the control plane can do, or `null` until it answers. */
  health: Health | null;
  /** The outcome of a return from GitHub, shown once. */
  githubReturned: GitHubReturn;
  /** The outcome of a return from connecting Epic, shown once. */
  epicReturned: EpicReturn;
  /** Opens the API keys tab. */
  onKeys: () => void;
}

/**
 * Renders the Connections tab.
 *
 * @param props The component's props.
 * @returns The tab's content.
 */
export function ConnectionsTab({ github, epic, health, githubReturned, epicReturned, onKeys }: ConnectionsTabProps) {
  return (
    <>
      <TabHeading title="Connections">The accounts the studio works with, and what each is for.</TabHeading>
      <ul className="mt-6 grid grid-cols-1 gap-3">
        <li>
          <GitHubConnection github={github} health={health} returned={githubReturned} />
        </li>
        <li>
          <EpicConnection epic={epic} health={health} returned={epicReturned} />
        </li>
        <li>
          <Connection
            icon={<Sparkles className="size-4" aria-hidden="true" />}
            name="Claude"
            purpose="Give Claude an API key and it can start engines, work inside the app you are watching, and stop them when it is done."
            state={null}
          >
            <CommandBlock title="Claude Code" command={mcpSetupCommand()} />
            <p className="mt-3 text-xs leading-relaxed text-faint">
              Replace <span className="mono text-muted">{SECRET_PLACEHOLDER}</span> with a key of yours. Other MCP clients
              connect to <span className="mono break-all text-muted">{mcpEndpoint()}</span> with the key as a bearer
              token.
            </p>
            <div className="mt-3">
              <button type="button" className="btn btn-ghost btn-sm" onClick={onKeys}>
                Create a key
                <ArrowRight className="size-4" aria-hidden="true" />
              </button>
            </div>
          </Connection>
        </li>
      </ul>
    </>
  );
}

/** How a connection stands, as its badge says it. */
type State = 'connected' | 'off' | 'unavailable' | null;

/** What each state's badge reads. */
const STATE_LABELS: Readonly<Record<Exclude<State, null>, string>> = {
  connected: 'Connected',
  off: 'Not connected',
  unavailable: 'Not configured',
};

/** Props of {@link Connection}. */
interface ConnectionProps {
  /** The connection's mark. */
  icon: ReactNode;
  /** What it connects to. */
  name: string;
  /** What it is for, in a sentence. */
  purpose: string;
  /** How it stands, or `null` for one with no state of its own to show. */
  state: State;
  /** How it stands in words, and the controls that change it. */
  children: ReactNode;
}

/**
 * Renders one connection: its mark, name, and state, what it is for, and its controls.
 *
 * @param props The component's props.
 * @returns The connection's card.
 */
function Connection({ icon, name, purpose, state, children }: ConnectionProps) {
  return (
    <article className="rounded-2xl border border-line bg-ink-900 p-4 sm:p-5" data-connection={name}>
      <div className="flex items-center gap-2.5">
        <span className="grid size-8 flex-none place-items-center rounded-md border border-line-strong bg-ink-700">
          {icon}
        </span>
        <h4 className="min-w-0 flex-1 truncate text-[0.9375rem] font-semibold tracking-tight">{name}</h4>
        {state === null ? null : (
          <span className="pill h-6 border-line px-2 text-[0.6875rem] font-medium text-muted" data-state={state}>
            {state === 'connected' ? <span className="dot" aria-hidden="true" /> : null}
            {STATE_LABELS[state]}
          </span>
        )}
      </div>
      <p className="mt-2.5 text-sm leading-relaxed text-muted">{purpose}</p>
      <div className="mt-3.5">{children}</div>
    </article>
  );
}

/**
 * Runs the actions of one connection, one at a time, keeping what the last one failed with.
 *
 * @returns Whether an action is running, what the last failed with, and the function that runs one.
 */
function useActions(): { busy: boolean; error: unknown; run: (action: () => Promise<void>) => void } {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return {
    busy,
    error,
    run: (action) => {
      setBusy(true);
      setError(null);
      action()
        .catch((failure: unknown) => {
          setError(failure);
        })
        .finally(() => {
          setBusy(false);
        });
    },
  };
}

/**
 * Says why a connection cannot be shown, where it cannot.
 *
 * @param availability How far reading it has come.
 * @param name What it connects to.
 * @returns The line to show in its place, or `null` once it has been read.
 */
function unread(availability: Availability, name: string): ReactNode {
  if (availability === 'loading') {
    return <div className="h-8 animate-pulse rounded-lg bg-white/[0.04]" aria-label={`Loading ${name}`} />;
  }
  if (availability === 'missing' || availability === 'offline') {
    return <p className="text-sm text-faint">{name} arrives with the studio&rsquo;s backend.</p>;
  }
  if (availability === 'failed') {
    return <p className="text-sm text-bad">Could not read your {name} connection.</p>;
  }
  return null;
}

/** Props of {@link GitHubConnection}. */
interface GitHubConnectionProps {
  /** The GitHub connection. */
  github: GitHub;
  /** What the control plane can do. */
  health: Health | null;
  /** The outcome of a return from GitHub. */
  returned: GitHubReturn;
}

/** What a return from GitHub came to, in words. */
const GITHUB_RETURNS: Readonly<Record<Exclude<GitHubReturn, null>, { tone: 'info' | 'warn'; text: string }>> = {
  connected: { tone: 'info', text: 'GitHub is connected.' },
  installed: { tone: 'info', text: 'The repositories you chose are now within reach.' },
  requested: {
    tone: 'info',
    text: 'The organization’s owners were asked to approve the installation. Its repositories appear once they do.',
  },
  failed: { tone: 'warn', text: 'GitHub did not connect. Try again, and approve the access it asks for.' },
};

/**
 * Renders the GitHub connection.
 *
 * @param props The component's props.
 * @returns The connection's card.
 */
function GitHubConnection({ github, health, returned }: GitHubConnectionProps) {
  const { busy, error, run } = useActions();
  const status = github.status;
  const unconfigured = health?.github === false || status?.configured === false;
  const waiting = unconfigured ? null : unread(github.availability, 'GitHub');
  let body: ReactNode;
  if (unconfigured) {
    body = <p className="text-sm text-faint">GitHub is not configured on this server yet. Projects work without it.</p>;
  } else if (waiting !== null || status === null) {
    body = waiting;
  } else if (!status.connected) {
    body = (
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        disabled={busy}
        onClick={() => {
          run(() => github.connect());
        }}
      >
        {busy ? <span className="spinner size-3.5" aria-hidden="true" /> : <GitHubMark className="size-4" />}
        Connect GitHub
      </button>
    );
  } else {
    body = (
      <>
        <p className="text-sm">
          Connected as <span className="font-medium">{status.login ?? 'your account'}</span>.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={busy}
            onClick={() => {
              run(() => github.install());
            }}
          >
            <Plus className="size-4" aria-hidden="true" />
            Add repositories
          </button>
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            disabled={busy}
            onClick={() => {
              run(() => github.connect());
            }}
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            Reconnect
          </button>
          <button
            type="button"
            className="btn btn-quiet btn-sm text-bad"
            disabled={busy}
            onClick={() => {
              run(github.disconnect);
            }}
          >
            <LogOut className="size-4" aria-hidden="true" />
            Disconnect
          </button>
        </div>
      </>
    );
  }
  return (
    <Connection
      icon={<GitHubMark className="size-4" />}
      name="GitHub"
      purpose="A project keeps its script, its library’s manifest, and its shot list in a repository of yours, and a repository of yours can be opened as a project."
      state={unconfigured ? 'unavailable' : status === null ? null : status.connected ? 'connected' : 'off'}
    >
      {returned === null ? null : (
        <div className="mb-3">
          <Notice tone={GITHUB_RETURNS[returned].tone}>{GITHUB_RETURNS[returned].text}</Notice>
        </div>
      )}
      {body}
      {error === null ? null : (
        <div className="mt-3">
          <ErrorNotice error={error} />
        </div>
      )}
    </Connection>
  );
}

/** Props of {@link EpicConnection}. */
interface EpicConnectionProps {
  /** The Epic connection. */
  epic: Epic;
  /** What the control plane can do. */
  health: Health | null;
  /** The outcome of a return from connecting Epic. */
  returned: EpicReturn;
}

/**
 * Renders the Epic connection: the GitHub account linked to the person's Epic account, and
 * whether Epic's registry lets it pull the editor.
 *
 * Where the account is connected but not linked to Epic yet, the catalog's steps say how to link
 * it on Epic's site, and "Check again" asks the registry anew.
 *
 * @param props The component's props.
 * @returns The connection's card.
 */
function EpicConnection({ epic, health, returned }: EpicConnectionProps) {
  const { busy, error, run } = useActions();
  const status = epic.status;
  const unconfigured = health?.epic === false || status?.configured === false;
  const waiting = unconfigured ? null : unread(epic.availability, 'Epic');
  // The app whose licensed part comes on the person's own Epic account, with the steps that link it.
  const license = catalog.apps.find((app) => app.license !== undefined)?.license;
  // The last of the catalog's steps is connecting here, which the button does.
  const steps = (license?.steps ?? []).slice(0, -1);
  let body: ReactNode;
  if (unconfigured) {
    body = (
      <p className="text-sm text-faint">
        Epic is not configured on this server yet. Unreal Engine starts as its desktop without it.
      </p>
    );
  } else if (waiting !== null || status === null) {
    body = waiting;
  } else {
    body = (
      <>
        {status.connected ? (
          <p className="text-sm">
            Connected as <span className="font-medium">{status.login ?? 'your account'}</span>
            {status.linked === true
              ? ', which is linked to your Epic account: Unreal Engine starts with your own editor.'
              : status.linked === false
                ? ', which is not linked to an Epic account yet, so the Unreal Editor does not come with it.'
                : `. The link to Epic could not be checked: ${status.detail ?? 'no answer'}`}
          </p>
        ) : null}
        {status.linked === true || steps.length === 0 ? null : (
          <ol className="mt-2 list-decimal space-y-0.5 pl-4 text-sm leading-relaxed text-muted">
            {steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className={status.connected ? 'btn btn-quiet btn-sm' : 'btn btn-ghost btn-sm'}
            disabled={busy}
            onClick={() => {
              run(epic.connect);
            }}
          >
            {busy ? <span className="spinner size-3.5" aria-hidden="true" /> : <GitHubMark className="size-4" />}
            {status.connected ? 'Reconnect' : 'Connect Epic'}
          </button>
          {status.connected ? (
            <>
              <button type="button" className="btn btn-quiet btn-sm" onClick={epic.refresh}>
                <RefreshCw className="size-4" aria-hidden="true" />
                Check again
              </button>
              <button
                type="button"
                className="btn btn-quiet btn-sm text-bad"
                disabled={busy}
                onClick={() => {
                  run(epic.disconnect);
                }}
              >
                <LogOut className="size-4" aria-hidden="true" />
                Disconnect
              </button>
            </>
          ) : null}
        </div>
      </>
    );
  }
  return (
    <Connection
      icon={<Gamepad2 className="size-4" aria-hidden="true" />}
      name="Epic Games"
      purpose="Unreal Engine starts with your own copy of the Unreal Editor, pulled on your Epic account through the GitHub account linked to it."
      state={unconfigured ? 'unavailable' : status === null ? null : status.connected ? 'connected' : 'off'}
    >
      {returned === null ? null : (
        <div className="mb-3">
          <Notice tone={returned === 'failed' ? 'warn' : 'info'}>
            {returned === 'failed'
              ? 'Epic did not connect. Try again, and approve the access GitHub asks for.'
              : 'Epic is connected.'}
          </Notice>
        </div>
      )}
      {body}
      {error === null ? null : (
        <div className="mt-3">
          <ErrorNotice error={error} />
        </div>
      )}
    </Connection>
  );
}
