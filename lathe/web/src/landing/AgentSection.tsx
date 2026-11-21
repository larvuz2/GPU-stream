/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's "Built for Claude" section: what an agent can do over MCP, the one command
 * that connects it, and the tools it gets.
 *
 * The command comes from `lib/mcp.ts` with a placeholder where the key belongs; the key itself is
 * created in the dashboard, which is where the call to action leads. The exchange drawn over the
 * art is labeled as an example, since it is one.
 * @module
 */
import { ArrowRight, KeyRound, Sparkles } from 'lucide-react';
import { ArtImage } from '../components/Art';
import { CommandBlock } from '../components/Copy';
import { brand, catalog, liveApps } from '../lib/catalog';
import { MCP_TOOLS, mcpSetupCommand, SCRIPT_TOOL, SECRET_PLACEHOLDER } from '../lib/mcp';
import { AGENT_ART } from '../lib/media';

/** The steps from no account to an agent at work. */
const SETUP = ['Create an API key in your dashboard.', 'Paste one command into your terminal.', 'Ask Claude for a scene.'];

/**
 * Renders the agent section.
 *
 * @returns The section.
 */
export function AgentSection() {
  const app = liveApps[0];
  const tier = catalog.tiers[1] ?? catalog.tiers[0];
  return (
    <section id="claude" className="section" aria-labelledby="claude-title">
      <div className="shell grid grid-cols-[minmax(0,1fr)] items-center gap-12 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:gap-16">
        <div>
          <p className="eyebrow">
            <Sparkles className="size-4" aria-hidden="true" />
            Built for Claude
          </p>
          <h2 id="claude-title" className="display mt-4 text-[2rem] sm:text-5xl">
            Claude builds. <span className="text-gradient block w-fit">You watch it happen.</span>
          </h2>
          <p className="lede mt-5 text-[1.0625rem] sm:text-lg">
            {brand} speaks MCP. Claude can start a session, build inside the same {app?.name ?? 'app'} you have open
            in your tab, check its own work with screenshots, and shut everything down when the job is done.
          </p>

          <ol className="mt-8 grid gap-3">
            {SETUP.map((step, index) => (
              <li key={step} className="flex items-center gap-3.5 text-[0.9375rem]">
                <span className="grid size-7 flex-none place-items-center rounded-full border border-ember/40 bg-ember/10 text-xs font-bold text-ember-300">
                  {index + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>

          <CommandBlock className="mt-8" title="Set up with Claude Code" command={mcpSetupCommand()} />
          <p className="mt-3 text-sm text-faint">
            Replace <span className="mono text-muted">{SECRET_PLACEHOLDER}</span> with a key from your dashboard.
          </p>

          <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
            <a href="#signup" className="btn btn-primary btn-lg">
              <KeyRound className="size-4" aria-hidden="true" />
              Get your key
              <ArrowRight className="size-4" aria-hidden="true" />
            </a>
            <span className="text-sm text-muted">Free to create. It takes a minute.</span>
          </div>
        </div>

        <div className="relative">
          <div
            className="pointer-events-none absolute -inset-10 rounded-full bg-[radial-gradient(closest-side,rgb(255_122_26/0.22),rgb(139_92_246/0.14)_55%,transparent)] blur-2xl"
            aria-hidden="true"
          />
          <div className="art relative aspect-[3/2] rounded-3xl border border-line-strong shadow-[0_40px_120px_-50px_rgb(139_92_246/0.8)]">
            <ArtImage src={AGENT_ART} width={1200} height={800} />
          </div>
          <div className="glass relative z-10 mx-3 -mt-12 rounded-2xl bg-ink-800/90 p-5 backdrop-blur-xl sm:mx-8 sm:-mt-16">
            <p className="text-[0.6875rem] font-semibold tracking-[0.16em] text-faint uppercase">Example session</p>
            <p className="mt-3 rounded-xl rounded-tl-sm border border-line bg-white/5 px-3.5 py-2.5 text-sm">
              Model a ceramic vase on a turntable and light it warm.
            </p>
            <ul className="mt-3 grid gap-1.5">
              <ToolCall name="start_session" detail={[app?.id, tier?.name].filter(Boolean).join(' · ')} />
              <ToolCall name={SCRIPT_TOOL} detail="bpy.ops.mesh.primitive_cylinder_add(…)" />
              <ToolCall name="screenshot" detail="checks the viewport" />
            </ul>
            <p className="mt-3 flex items-start gap-2.5 text-sm text-muted">
              <Sparkles className="mt-0.5 size-4 flex-none text-ember-300" aria-hidden="true" />
              The vase is on the turntable with a warm key light. It is in your tab now.
            </p>
          </div>
        </div>
      </div>

      <div className="shell mt-14">
        <h3 className="text-center text-sm font-semibold tracking-[0.16em] text-faint uppercase">
          The tools Claude gets
        </h3>
        <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {MCP_TOOLS.map((tool) => (
            <li key={tool.name} className="glass rounded-2xl p-4 last:lg:col-span-2">
              <p className="mono font-semibold text-ember-200">{tool.name}</p>
              <p className="mt-1.5 text-sm text-muted">{tool.summary}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** Props of {@link ToolCall}. */
interface ToolCallProps {
  /** The tool's name. */
  name: string;
  /** A few words on what the call carries. */
  detail: string;
}

/**
 * Renders one tool call of the example exchange.
 *
 * @param props The component's props.
 * @returns The row.
 */
function ToolCall({ name, detail }: ToolCallProps) {
  return (
    <li className="flex min-w-0 items-center gap-2.5 rounded-lg bg-black/30 px-3 py-2 text-xs">
      <span className="dot dot-ember" aria-hidden="true" />
      <span className="mono font-semibold text-fg">{name}</span>
      <span className="mono min-w-0 flex-1 truncate text-right text-faint">{detail}</span>
    </li>
  );
}
