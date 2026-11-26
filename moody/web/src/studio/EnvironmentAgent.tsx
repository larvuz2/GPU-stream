/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What the project's agent works with, in the Environment panel under the engines and the
 * repositories: its connectors, the subagents it can hand work to, the skills it reads, and the
 * tools the person lets it run without asking.
 *
 * The first three are the control plane's answer for the project (`GET
 * /v1/projects/{pid}/environment`); nothing here lists one. A connector says what it is for by its
 * icon and whether the agent can use it by its state: connected, available once the person
 * connects it, or off on this server. A control plane that does not serve the route shows none of
 * the three, as it showed none before, and no permissions either unless the project has some.
 *
 * The last is the project's own `permissions`: each tool the person answered "always allow" for
 * in an approval, with a button that takes the answer back, after which the agent asks again.
 *
 * Each of the four is a section that folds (`FoldSection.tsx`).
 * @module
 */
import { useState } from 'react';
import { FolderGit2, Globe, KeyRound, Plug, ShieldCheck, Sparkles, type LucideIcon } from 'lucide-react';
import { MoodyEyes } from '../components/MoodyEyes';
import { ALWAYS, type ConnectorKind, type ConnectorState, type Environment } from '../lib/api';
import { cx } from '../lib/cx';
import { FoldSection } from './FoldSection';
import { ErrorNotice } from './Notice';
import type { Availability } from './useAccount';

/** The icon that says what each kind of connector is for. */
const KIND_ICONS: Readonly<Record<ConnectorKind, LucideIcon>> = {
  generation: Sparkles,
  repository: FolderGit2,
  search: Globe,
  license: KeyRound,
  mcp: Plug,
};

/** How each state of a connector is said and drawn. */
const CONNECTOR_STATES: Readonly<Record<ConnectorState, { label: string; dot: string; className: string }>> = {
  connected: { label: 'Connected', dot: 'dot', className: 'text-fg' },
  available: { label: 'Available', dot: 'dot dot-warn', className: 'text-muted' },
  off: { label: 'Off', dot: 'dot dot-idle', className: 'text-faint' },
};

/** Props of {@link AgentEnvironment}. */
interface AgentEnvironmentProps {
  /** What the control plane says the agent works with, or `null` until it has answered. */
  environment: Environment | null;
  /** How far that has come. */
  status: Availability;
  /** The project's kept answers, by tool name. */
  permissions: Readonly<Record<string, string>>;
  /** Takes back the person's "always allow" for a tool. */
  onRevoke: (tool: string) => Promise<void>;
}

/**
 * Renders the agent's connectors, subagents, and skills, and the tools it may run without asking.
 *
 * @param props The component's props.
 * @returns The sections.
 */
export function AgentEnvironment({ environment, status, permissions, onRevoke }: AgentEnvironmentProps) {
  const allowed = Object.entries(permissions)
    .filter(([, answer]) => answer === ALWAYS)
    .map(([tool]) => tool)
    .sort();
  if ((status === 'missing' || status === 'offline') && allowed.length === 0) {
    return null;
  }
  return (
    <>
      {status === 'loading' ? (
        <FoldSection id="environment.connectors" label="Connectors">
          <div className="mt-2 grid grid-cols-1 gap-1.5" aria-label="Loading the environment">
            {[0, 1, 2].map((row) => (
              <div key={row} className="h-11 animate-pulse rounded-xl bg-white/[0.04]" />
            ))}
          </div>
        </FoldSection>
      ) : status === 'failed' ? (
        <FoldSection id="environment.connectors" label="Connectors">
          <p className="mt-2 text-sm text-bad">Could not read what the agent is connected to.</p>
        </FoldSection>
      ) : environment === null ? null : (
        <>
          <FoldSection
            id="environment.connectors"
            label={
              <>
                Connectors <Count value={environment.connectors.length} />
              </>
            }
          >
            {environment.connectors.length === 0 ? (
              <p className="mt-2 text-sm text-faint">Nothing is connected to this project&rsquo;s agent yet.</p>
            ) : (
              <ul className="mt-2 grid grid-cols-1 gap-1.5">
                {environment.connectors.map((connector) => {
                  const Icon = KIND_ICONS[connector.kind];
                  const state = CONNECTOR_STATES[connector.state];
                  return (
                    <li key={connector.id} className="env-row" data-state={connector.state}>
                      <span className="icon-tile size-8 rounded-lg">
                        <Icon className="size-3.5" aria-hidden="true" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{connector.name}</span>
                        <span className="line-clamp-2 text-xs text-muted">{connector.detail}</span>
                      </span>
                      <span className={cx('flex flex-none items-center gap-1.5 text-xs', state.className)}>
                        <span className={state.dot} aria-hidden="true" />
                        {state.label}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </FoldSection>
          <FoldSection
            id="environment.subagents"
            label={
              <>
                Subagents <Count value={environment.agents.length} />
              </>
            }
          >
            {environment.agents.length === 0 ? (
              <p className="mt-2 text-sm text-faint">This project&rsquo;s agent works alone.</p>
            ) : (
              <ul className="mt-2 grid grid-cols-1 gap-1.5">
                {environment.agents.map((agent) => (
                  <li key={agent.name} className="env-row">
                    <span className="icon-tile h-8 w-10 rounded-lg">
                      <MoodyEyes expression="thinking" still />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{agent.title}</span>
                      <span className="line-clamp-2 text-xs text-muted">{agent.description}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </FoldSection>
          <FoldSection
            id="environment.skills"
            label={
              <>
                Skills <Count value={environment.skills.length} />
              </>
            }
          >
            {environment.skills.length === 0 ? (
              <p className="mt-2 text-sm text-faint">No skill is offered to this project yet.</p>
            ) : (
              <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-3 gap-y-1.5 px-0.5 text-xs leading-relaxed">
                {environment.skills.map((skill) => (
                  <div key={skill.name} className="contents">
                    <dt className="mono text-fg">{skill.name}</dt>
                    <dd className="text-muted">{skill.description}</dd>
                  </div>
                ))}
              </dl>
            )}
          </FoldSection>
        </>
      )}
      <FoldSection
        id="environment.allowed"
        label={
          <>
            Always allowed <Count value={allowed.length} />
          </>
        }
      >
        {allowed.length === 0 ? (
          <p className="mt-2 text-sm text-faint">
            Nothing. The agent asks before a tool that costs or changes something; &ldquo;Always allow&rdquo; puts
            the tool here.
          </p>
        ) : (
          <ul className="mt-2 grid grid-cols-1 gap-1.5">
            {allowed.map((tool) => (
              <Permission key={tool} tool={tool} onRevoke={onRevoke} />
            ))}
          </ul>
        )}
      </FoldSection>
    </>
  );
}

/** Props of {@link Count}. */
interface CountProps {
  /** How many the section holds. */
  value: number;
}

/**
 * Renders the count after a section's label.
 *
 * @param props The component's props.
 * @returns The count, or nothing for an empty section.
 */
function Count({ value }: CountProps) {
  return value === 0 ? null : <span className="font-normal tracking-normal tabular-nums">{value}</span>;
}

/**
 * A tool's name in words: `engine_start` reads "Engine start".
 *
 * @param tool The tool's name.
 * @returns The name with its separators as spaces and its first letter raised.
 */
function toolTitle(tool: string): string {
  const words = tool.replaceAll(/[_-]+/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Props of {@link Permission}. */
interface PermissionProps {
  /** The tool the person always allows. */
  tool: string;
  /** Takes that back. */
  onRevoke: (tool: string) => Promise<void>;
}

/**
 * Renders one tool the agent may run without asking, with the button that takes that back.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function Permission({ tool, onRevoke }: PermissionProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  /** Takes the answer back, after which the row goes with the project's next reading. */
  async function revoke(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await onRevoke(tool);
    } catch (failure) {
      setError(failure);
      setBusy(false);
    }
  }

  return (
    <li>
      <div className="env-row">
        <span className="icon-tile size-8 rounded-lg">
          <ShieldCheck className="size-3.5 text-ok" aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{toolTitle(tool)}</span>
          <span className="mono block truncate text-[0.6875rem] text-faint">{tool}</span>
        </span>
        <button
          type="button"
          className="btn btn-quiet btn-sm h-7 flex-none px-2.5 text-xs"
          disabled={busy}
          title="The agent asks before this tool again"
          onClick={() => {
            void revoke();
          }}
        >
          {busy ? <span className="spinner size-3" aria-hidden="true" /> : null}
          Ask again
        </button>
      </div>
      {error === null ? null : (
        <div className="mt-1.5">
          <ErrorNotice error={error} />
        </div>
      )}
    </li>
  );
}
