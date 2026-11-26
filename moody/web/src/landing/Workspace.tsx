/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's picture of the app: its three panes drawn in markup rather than shown as a
 * screenshot, so it stays sharp at every width and follows the app's layout as the plan
 * (`moody/STUDIO.md`) describes it.
 *
 * The left sidebar holds the projects and the account; the center, the project's conversation with
 * the agent, its tool activity, and a question offered as choices; the right pane, the panels a
 * film project shows: the live Screen of an engine, the Environment with its engines and Connect
 * GitHub, the Plan, and the Library with its characters. Nothing in it is interactive, and it is
 * labeled as an illustration with example content: the project, its people, and its art are made
 * up, while every engine, tier, discipline, and figure is the catalog's. Its pictures rest in
 * grayscale, as the page's art does, and bloom to color while the pointer is over the window.
 *
 * On a narrow screen the sidebar is left out and the panes stack, the conversation first.
 * @module
 */
import type { ReactNode } from 'react';
import {
  ArrowUp,
  Check,
  Circle,
  CircleDot,
  GitBranch,
  LoaderCircle,
  Maximize2,
  Pin,
  Plus,
  Search,
  Square,
  type LucideIcon,
} from 'lucide-react';
import { DisciplineIcon } from '../components/DisciplineIcon';
import { MoodyFace } from '../components/Moody';
import { brand, catalog, liveApps, type CatalogApp } from '../lib/catalog';
import { cx } from '../lib/cx';
import { creditCount } from '../lib/format';
import { characterImage, engineImage } from '../lib/media';
import { SectionHeading } from './SectionHeading';

/** The example project the picture shows. */
const PROJECT = 'Night Shift';

/** A project in the sidebar: its name and the discipline it belongs to. */
interface SidebarProject {
  /** The project's name. */
  name: string;
  /** The identifier of its discipline. */
  discipline: string;
}

/** The pinned projects, the open one first. */
const PINNED: readonly SidebarProject[] = [
  { name: PROJECT, discipline: 'media' },
  { name: 'Glasshouse', discipline: 'architecture' },
];

/** The recent projects. */
const RECENT: readonly SidebarProject[] = [
  { name: 'Coffee at dawn', discipline: 'media' },
  { name: 'Moss and stone', discipline: 'games' },
  { name: 'Little lantern', discipline: 'animation' },
];

/** A character of the example library. */
interface Character {
  /** The tag the agent and the prompts name the character by, without its `@`. */
  tag: string;
  /** The character's name. */
  name: string;
}

/** The example library's characters, each with a portrait under `public/media`. */
const CHARACTERS: readonly Character[] = [
  { tag: 'mara', name: 'Mara' },
  { tag: 'theo', name: 'Theo' },
  { tag: 'iris', name: 'Iris' },
];

/** The state of a task of the plan, as the app's plan panel shows it. */
type TaskState = 'done' | 'active' | 'pending';

/** The example plan. */
const PLAN: readonly { title: string; state: TaskState }[] = [
  { title: 'Outline and script', state: 'done' },
  { title: 'Cast and reference images', state: 'done' },
  { title: 'Shot list', state: 'active' },
  { title: 'Generate the shots', state: 'pending' },
  { title: 'Cut, color, and mix', state: 'pending' },
];

/** The icon of each task state. */
const TASK_ICONS: Readonly<Record<TaskState, LucideIcon>> = {
  done: Check,
  active: CircleDot,
  pending: Circle,
};

/**
 * Renders the workspace section.
 *
 * @returns The section.
 */
export function Workspace() {
  return (
    <section id="workspace" className="section" aria-labelledby="workspace-title">
      <div className="shell">
        <SectionHeading
          id="workspace-title"
          eyebrow="The workspace"
          title="Your project, your agent, and every engine in view"
          lede="Projects on the left. The conversation in the middle, where the agent asks before every decision that is yours. On the right, the engine's live screen, the plan, and the library it builds as it goes."
        />
        <figure className="mt-12">
          <div className="mock-window bloom">
            <div className="flex h-10 items-center gap-3 border-b border-line bg-ink-800 px-4" aria-hidden="true">
              <span className="flex gap-1.5">
                <i className="size-2 bg-line-strong" />
                <i className="size-2 bg-line-strong" />
                <i className="size-2 bg-line-strong" />
              </span>
              <span className="mx-auto truncate text-xs text-faint">
                {brand} · {PROJECT}
              </span>
              <span className="w-10" />
            </div>
            <div className="mock-grid" aria-hidden="true">
              <Sidebar />
              <Conversation />
              <Panels />
            </div>
          </div>
          <figcaption className="mt-4 text-center text-sm text-faint">
            An illustration of the app. The project, its characters, and its art are examples.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

/**
 * Renders the sidebar: a new project, the search, the pinned and recent projects, and the account.
 *
 * @returns The pane.
 */
function Sidebar() {
  return (
    <div className="mock-pane hidden flex-col gap-5 border-r border-line p-3.5 lg:flex">
      <span className="btn btn-primary btn-sm w-full">
        <Plus className="size-4" />
        New project
      </span>
      <span className="flex h-9 items-center gap-2 rounded-lg border border-line bg-ink-800 px-3 text-xs text-faint">
        <Search className="size-3.5" />
        Search projects
      </span>
      <ProjectGroup label="Pinned" projects={PINNED} />
      <ProjectGroup label="Recent" projects={RECENT} />
      <div className="mt-auto grid gap-2 border-t border-line pt-3.5 text-xs">
        <span className="flex items-center gap-2.5">
          <span className="grid size-7 place-items-center rounded-md border border-line-strong bg-ink-700 text-[0.6875rem] font-bold text-fg">
            A
          </span>
          <span className="min-w-0">
            <span className="block truncate font-semibold">Alex</span>
            <span className="block text-faint">{creditCount(catalog.signup_credits)} credits</span>
          </span>
        </span>
        <span className="flex justify-between text-faint">
          <span>Settings</span>
          <span>Sign out</span>
        </span>
      </div>
    </div>
  );
}

/** Props of {@link ProjectGroup}. */
interface ProjectGroupProps {
  /** The group's heading. */
  label: string;
  /** The projects in it. */
  projects: readonly SidebarProject[];
}

/**
 * Renders a group of projects in the sidebar, the open project highlighted.
 *
 * @param props The component's props.
 * @returns The group.
 */
function ProjectGroup({ label, projects }: ProjectGroupProps) {
  return (
    <div>
      <p className="flex items-center gap-1.5 px-1 text-[0.6875rem] font-semibold tracking-[0.14em] text-faint uppercase">
        {label === 'Pinned' ? <Pin className="size-3" /> : null}
        {label}
      </p>
      <ul className="mt-1.5 grid gap-0.5">
        {projects.map((project) => {
          return (
            <li
              key={project.name}
              className={cx(
                'flex items-center gap-2 truncate rounded-lg px-2 py-1.5 text-[0.8125rem]',
                project.name === PROJECT ? 'bg-ink-700 font-semibold text-fg' : 'text-muted',
              )}
            >
              <DisciplineIcon id={project.discipline} className="size-3" />
              <span className="truncate">{project.name}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Renders the conversation: the person's request, the agent's reply and tool activity, a question
 * offered as choices, and the composer.
 *
 * @returns The pane.
 */
function Conversation() {
  const media = catalog.disciplines[0];
  const editor = liveApps[0];
  const tier = catalog.tiers.find((entry) => entry.gpu !== null);
  return (
    <div className="mock-pane flex flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
        <p className="truncate text-sm font-semibold">{PROJECT}</p>
        {media === undefined ? null : (
          <span className="engine-tag flex-none">
            {media.name} · {media.formats[0]}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-4 p-4 text-[0.8125rem] leading-relaxed sm:p-5">
        <p className="ml-auto max-w-[85%] rounded-xl rounded-br-sm border border-line-strong bg-ink-700 px-3.5 py-2.5">
          A short film about a night-shift mechanic who builds a robot to keep her company. Rainy city, warm
          light.
        </p>
        <div className="grid gap-2.5">
          <span className="grid size-7 place-items-center rounded-md border border-line-strong bg-ink-700">
            <MoodyFace className="h-6" />
          </span>
          <p className="text-muted">
            <span className="font-semibold text-fg">Here is the outline and the cast.</span> Mara is the mechanic,
            Theo her old mentor, and Iris the courier who finds the robot. I made reference images for each of them.
          </p>
          <ToolRow state="done" title="Wrote the script" detail="script.md" />
          <ToolRow state="done" title="Generated references" detail="@mara @theo @iris" />
          <div className="flex gap-2">
            {CHARACTERS.map((character) => (
              <span key={character.tag} className="relative w-20 sm:w-24">
                <img
                  src={characterImage(character.tag)}
                  alt=""
                  width={256}
                  height={256}
                  loading="lazy"
                  decoding="async"
                  className="bloom-image aspect-square w-full rounded-lg border border-line object-cover"
                />
                <span className="mono absolute bottom-1 left-1 rounded bg-black/60 px-1 text-[0.625rem] text-fg">
                  @{character.tag}
                </span>
              </span>
            ))}
          </div>
          {editor === undefined ? null : (
            <ToolRow
              state="active"
              title={`Opening ${editor.name}`}
              detail={tier === undefined ? 'Cloud GPU' : `${tier.name} · ${tier.gpu ?? ''}`}
            />
          )}
        </div>
        <div className="ai-card rounded-xl p-3.5">
          <p className="ai-label">Moody asks</p>
          <p className="mt-1.5 font-semibold">Before I cut the trailer: how should the film end?</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {['Hopeful', 'Bittersweet', 'Leave it open'].map((option, index) => (
              <span key={option} className={cx('mock-choice', index === 0 && 'mock-choice-on')}>
                {option}
              </span>
            ))}
          </div>
        </div>
        <div className="mt-auto flex items-center gap-2 rounded-xl border border-line-strong bg-ink-800 py-2 pr-2 pl-3.5 text-faint">
          <span className="flex-1 truncate">Reply, or tell the agent what to change…</span>
          <span className="grid size-8 flex-none place-items-center rounded-md bg-fg text-ink-950">
            <ArrowUp className="size-4" />
          </span>
        </div>
      </div>
    </div>
  );
}

/** Props of {@link ToolRow}. */
interface ToolRowProps {
  /** Whether the tool has finished or is running. */
  state: 'done' | 'active';
  /** What the tool did. */
  title: string;
  /** A few words on what it worked on. */
  detail: string;
}

/**
 * Renders one line of the agent's tool activity.
 *
 * @param props The component's props.
 * @returns The row.
 */
function ToolRow({ state, title, detail }: ToolRowProps) {
  return (
    <p className="flex min-w-0 items-center gap-2.5 rounded-lg border border-line bg-ink-950 px-3 py-2 text-xs">
      {state === 'done' ? (
        <Check className="size-3.5 flex-none text-fg" />
      ) : (
        <LoaderCircle className="size-3.5 flex-none animate-spin text-fg" />
      )}
      <span className="font-semibold">{title}</span>
      <span className="mono min-w-0 flex-1 truncate text-faint">{detail}</span>
    </p>
  );
}

/**
 * Renders the right pane's panels: Screen, Environment, Plan, and Library.
 *
 * @returns The pane.
 */
function Panels() {
  const [editor, ...others] = liveApps;
  const tier = catalog.tiers.find((entry) => entry.gpu !== null);
  return (
    <div className="mock-pane grid content-start gap-3 border-line bg-ink-950 p-3 max-md:border-t md:border-l">
      <Panel title="Screen" aside={editor === undefined ? undefined : <LiveBadge app={editor} />}>
        <div className="art relative aspect-video overflow-hidden rounded-lg" style={{ '--accent': editor?.accent }}>
          {editor === undefined ? null : (
            <img
              src={engineImage(editor.id)}
              alt=""
              width={1280}
              height={720}
              loading="lazy"
              decoding="async"
              className="bloom-image absolute inset-0 size-full object-cover"
            />
          )}
          <span className="absolute right-1.5 bottom-1.5 z-10 grid size-6 place-items-center rounded-md bg-black/60 text-muted">
            <Maximize2 className="size-3" />
          </span>
        </div>
      </Panel>
      <Panel title="Environment">
        <ul className="grid gap-1.5 text-xs">
          {editor === undefined ? null : (
            <EngineRow app={editor} running detail={tier === undefined ? 'Running' : `Running · ${tier.name}`} />
          )}
          {others.map((app) => (
            <EngineRow key={app.id} app={app} running={false} detail="Stopped" />
          ))}
        </ul>
        <span className="btn btn-ghost btn-sm mt-2.5 h-8 w-full text-xs">
          <GitBranch className="size-3.5" />
          Connect GitHub
        </span>
      </Panel>
      <Panel title="Plan">
        <ul className="grid gap-1.5 text-xs">
          {PLAN.map((task) => {
            const Icon = TASK_ICONS[task.state];
            return (
              <li
                key={task.title}
                className={cx('flex items-center gap-2', task.state === 'pending' ? 'text-faint' : 'text-fg')}
              >
                <Icon
                  className={cx(
                    'size-3.5 flex-none',
                    task.state !== 'pending' && 'text-fg',
                  )}
                />
                {task.title}
              </li>
            );
          })}
        </ul>
      </Panel>
      <Panel title="Library">
        <div className="flex gap-1.5 text-[0.6875rem]">
          <span className="mock-choice mock-choice-on py-0.5">Characters</span>
          <span className="mock-choice py-0.5">Environments</span>
          <span className="mock-choice py-0.5">Props</span>
        </div>
        <ul className="mt-2.5 grid grid-cols-3 gap-2">
          {CHARACTERS.map((character) => (
            <li key={character.tag} className="min-w-0">
              <img
                src={characterImage(character.tag)}
                alt=""
                width={256}
                height={256}
                loading="lazy"
                decoding="async"
                className="bloom-image aspect-square w-full rounded-lg border border-line object-cover"
              />
              <p className="mt-1 truncate text-[0.6875rem] font-semibold">{character.name}</p>
              <p className="mono truncate text-[0.625rem] text-faint">@{character.tag}</p>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

/** Props of {@link Panel}. */
interface PanelProps {
  /** The panel's title. */
  title: string;
  /** What sits at the right of the title. */
  aside?: ReactNode;
  /** The panel's content. */
  children: ReactNode;
}

/**
 * Renders one panel of the right pane.
 *
 * @param props The component's props.
 * @returns The panel.
 */
function Panel({ title, aside, children }: PanelProps) {
  return (
    <div className="rounded-lg border border-line bg-ink-900 p-3">
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <p className="text-[0.6875rem] font-semibold tracking-[0.14em] text-faint uppercase">{title}</p>
        {aside}
      </div>
      {children}
    </div>
  );
}

/** Props of {@link LiveBadge}. */
interface LiveBadgeProps {
  /** The engine the screen streams. */
  app: CatalogApp;
}

/**
 * Renders the badge that names the engine on the screen and says it is live.
 *
 * @param props The component's props.
 * @returns The badge.
 */
function LiveBadge({ app }: LiveBadgeProps) {
  return (
    <span className="flex items-center gap-1.5 text-[0.6875rem] font-semibold text-fg">
      <span className="dot dot-live" />
      {app.name}
    </span>
  );
}

/** Props of {@link EngineRow}. */
interface EngineRowProps {
  /** The engine. */
  app: CatalogApp;
  /** Whether it is running. */
  running: boolean;
  /** Its state in a few words. */
  detail: string;
}

/**
 * Renders one engine of the environment panel with its state and its start or stop control.
 *
 * @param props The component's props.
 * @returns The row.
 */
function EngineRow({ app, running, detail }: EngineRowProps) {
  return (
    <li className="flex items-center gap-2 rounded-md bg-ink-800 px-2.5 py-2">
      <span className={cx('dot', !running && 'dot-idle')} />
      <span className="font-semibold">{app.name}</span>
      <span className="min-w-0 flex-1 truncate text-faint">{detail}</span>
      {running ? <Square className="size-3 fill-current text-muted" /> : <Plus className="size-3.5 text-muted" />}
    </li>
  );
}
