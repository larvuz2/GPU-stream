/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's engines: the creative software a project's agent opens, grouped by the
 * catalog's status, and how engines hand work to one another.
 *
 * The live engines come first and largest, then the ones with a part on a license of the person's
 * own (Unreal Engine, whose editor runs on their Epic account), badged with that license, then the ones
 * coming next with the discipline each is first made for, then the team's (software whose license
 * is the user's own, such as Nuke), and the rest as compact chips. Every name, status, tagline, and version is the catalog's. An engine
 * is pictured by its own interface where it is open source; software that is someone else's
 * product is pictured by concept art of the work made in it, never by its interface or its logo.
 *
 * The hand-offs name the engines they join by catalog identifier and are drawn only while the
 * catalog lists every engine of one; an engine not live yet is marked as coming.
 * @module
 */
import { ArrowRight, ArrowDown, Globe, KeyRound } from 'lucide-react';
import { ArtImage } from '../components/Art';
import { findApp, findDiscipline, isAvailable, type CatalogApp } from '../lib/catalog';
import { cx } from '../lib/cx';
import { engineImage } from '../lib/media';
import { SectionHeading } from './SectionHeading';
import { appsWithStatus, listFormat, madeFor, statusLabel } from './studio';

/** A step of a hand-off between engines: an engine of the catalog, and what it does there. */
interface HandOffStep {
  /** The catalog identifier of the engine. */
  app: string;
  /** What the engine makes in this hand-off. */
  role: string;
}

/** Two or more engines working on one project's files in turn. */
interface HandOff {
  /** What the hand-off turns into what, in a few words. */
  title: string;
  /** The engines, in the order the work moves through them. */
  steps: readonly HandOffStep[];
  /** Where the work ends up after the last engine, when it leaves them. */
  end?: string;
}

/** The hand-offs the section shows. */
const HAND_OFFS: readonly HandOff[] = [
  {
    title: 'An edit spawns a poster',
    steps: [
      { app: 'filmcraft', role: 'Cuts the film' },
      { app: 'photocraft', role: 'Makes the poster from its frames' },
    ],
  },
  {
    title: 'A scene becomes a playable world',
    steps: [
      { app: 'blender', role: 'Builds the scene' },
      { app: 'unreal', role: 'Lights it in real time' },
    ],
    end: 'Plays in your browser',
  },
];

/**
 * Renders the engines section.
 *
 * @returns The section.
 */
export function Engines() {
  const live = appsWithStatus('available');
  const own = appsWithStatus('byol');
  const next = appsWithStatus('next');
  const team = appsWithStatus('team');
  const soon = appsWithStatus('soon');
  return (
    <section id="engines" className="section" aria-labelledby="engines-title">
      <div className="shell">
        <SectionHeading
          id="engines-title"
          eyebrow="Engines"
          title="Real creative software, on cloud GPUs"
          lede={`The agent opens creative engines on a cloud GPU and streams them to your tab. It works through the same commands their menus run, and you can take the controls at any moment.${
            live.length === 0 ? '' : ` ${listFormat.format(live.map((app) => app.name))} ${live.length === 1 ? 'is' : 'are'} live today.`
          }`}
        />

        {live.length === 0 ? null : (
          <ul className="mt-12 grid grid-cols-[minmax(0,1fr)] gap-5 md:grid-cols-2">
            {live.map((app) => (
              <li key={app.id} className="flex">
                <EngineCard app={app} large />
              </li>
            ))}
          </ul>
        )}

        <ul className="mt-5 grid grid-cols-[minmax(0,1fr)] gap-5 md:grid-cols-2 lg:grid-cols-3">
          {[...own, ...next].map((app) => (
            <li key={app.id} className="flex">
              <EngineCard app={app} large={false} />
            </li>
          ))}
          {team.map((app) => (
            <li key={app.id} className="flex">
              <TeamCard app={app} />
            </li>
          ))}
        </ul>

        {soon.length === 0 ? null : (
          <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-start">
            <p className="flex-none pt-1.5 text-xs font-semibold tracking-[0.16em] text-faint uppercase">On the way</p>
            <ul className="flex flex-wrap gap-2">
              {soon.map((app) => (
                <li key={app.id} className="engine-chip" style={{ '--accent': app.accent }}>
                  <span className="size-2 flex-none rounded-full bg-(--accent)" aria-hidden="true" />
                  {app.name}
                </li>
              ))}
            </ul>
          </div>
        )}

        <HandOffs />
      </div>
    </section>
  );
}

/** Props of {@link EngineCard}. */
interface EngineCardProps {
  /** The engine the card presents. */
  app: CatalogApp;
  /** Whether the card is drawn at the live engines' size. */
  large: boolean;
}

/**
 * Renders an engine with its picture: a live one, one on the person's own license, or one coming next.
 *
 * @param props The component's props.
 * @returns The card.
 */
function EngineCard({ app, large }: EngineCardProps) {
  const live = isAvailable(app);
  const picture = engineImage(app.id);
  const purpose = madeFor(app);
  const disciplines = app.disciplines.flatMap((id) => findDiscipline(id)?.name ?? []);
  return (
    <article className={cx('app-card w-full', live ? 'app-card-live' : 'app-card-soon')} style={{ '--accent': app.accent }}>
      <div className="art art-scrim aspect-video">
        {picture === undefined ? null : <ArtImage src={picture} width={1280} height={720} />}
        <span className="pill absolute top-3.5 left-3.5 z-10">
          {live ? (
            <>
              <span className="dot dot-live" aria-hidden="true" />
              Live
            </>
          ) : (
            <span className="text-muted">
              {statusLabel(app)}
              {purpose === null ? '' : ` · ${purpose}`}
            </span>
          )}
        </span>
      </div>
      <div className={cx('flex flex-1 flex-col', large ? 'p-6 sm:p-7' : 'p-5')}>
        <div className="flex items-start justify-between gap-4">
          <h3 className={cx('font-semibold tracking-tight', large ? 'text-2xl' : 'text-xl')}>{app.name}</h3>
          {app.version === '' ? null : (
            <span className="pill flex-none border-line bg-white/5 text-muted backdrop-blur-none">{app.version}</span>
          )}
        </div>
        <p className={cx('lede mt-2 flex-1', large ? 'text-[0.9375rem]' : 'text-sm')}>{app.tagline}</p>
        {disciplines.length === 0 ? null : (
          <p className="mt-4 text-xs text-faint">For {listFormat.format(disciplines.map((name) => name.toLowerCase()))}</p>
        )}
      </div>
    </article>
  );
}

/** Props of {@link TeamCard}. */
interface TeamCardProps {
  /** The team engine the card presents. */
  app: CatalogApp;
}

/**
 * Renders an engine only the team's accounts can open, whose license each user brings.
 *
 * It carries no picture: the software is someone else's product, so the card names it in text.
 *
 * @param props The component's props.
 * @returns The card.
 */
function TeamCard({ app }: TeamCardProps) {
  return (
    <article className="glass relative flex w-full flex-col overflow-hidden p-6" style={{ '--accent': app.accent }}>
      <div
        className="pointer-events-none absolute -top-20 -right-16 size-56 rounded-full bg-(--accent) opacity-15 blur-3xl"
        aria-hidden="true"
      />
      <span className="pill w-fit text-muted">{statusLabel(app)} · bring your own license</span>
      <span className="icon-tile mt-6">
        <KeyRound className="size-5" aria-hidden="true" />
      </span>
      <div className="mt-5 flex items-start justify-between gap-4">
        <h3 className="text-xl font-semibold tracking-tight">{app.name}</h3>
        {app.version === '' ? null : (
          <span className="pill flex-none border-line bg-white/5 text-muted backdrop-blur-none">{app.version}</span>
        )}
      </div>
      <p className="lede mt-2 flex-1 text-sm">{app.tagline}</p>
      <p className="mt-4 text-xs text-faint">
        Open to the team's accounts for now. Each person signs in with their own license inside the session.
      </p>
    </article>
  );
}

/**
 * Renders how engines hand work to one another, each hand-off a row of its engines.
 *
 * @returns The block, or nothing when the catalog lists no hand-off's engines.
 */
function HandOffs() {
  const handOffs = HAND_OFFS.flatMap((handOff) => {
    const apps = handOff.steps.flatMap((step) => {
      const app = findApp(step.app);
      return app === undefined ? [] : [{ app, role: step.role }];
    });
    return apps.length === handOff.steps.length ? [{ ...handOff, apps }] : [];
  });
  if (handOffs.length === 0) {
    return null;
  }
  return (
    <div className="mt-16">
      <div className="max-w-2xl">
        <h3 className="text-2xl font-semibold tracking-tight sm:text-3xl">Engines talk to each other</h3>
        <p className="lede mt-3 text-[0.9375rem] sm:text-base">
          Every engine of a project opens the same project folder, so what one engine makes is the next one&apos;s
          material. The agent moves the work along and asks you before it does.
        </p>
      </div>
      <ul className="mt-8 grid gap-4">
        {handOffs.map((handOff) => (
          <li
            key={handOff.title}
            className="glass grid grid-cols-[minmax(0,1fr)] items-center gap-4 p-5 sm:p-6 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-8"
          >
            <p className="text-[0.9375rem] font-semibold tracking-tight">{handOff.title}</p>
            <ol className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
              {handOff.apps.map(({ app, role }, index) => (
                <li key={app.id} className="contents">
                  {index === 0 ? null : <Arrow />}
                  <HandOffNode app={app} role={role} />
                </li>
              ))}
              {handOff.end === undefined ? null : (
                <li className="contents">
                  <Arrow />
                  <span className="handoff-node">
                    <Globe className="size-4 flex-none text-ember-300" aria-hidden="true" />
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold">Your tab</span>
                      <span className="block text-xs text-muted">{handOff.end}</span>
                    </span>
                  </span>
                </li>
              )}
            </ol>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Props of {@link HandOffNode}. */
interface HandOffNodeProps {
  /** The engine of this step. */
  app: CatalogApp;
  /** What it makes here. */
  role: string;
}

/**
 * Renders one engine of a hand-off, marked when it is not live yet.
 *
 * @param props The component's props.
 * @returns The node.
 */
function HandOffNode({ app, role }: HandOffNodeProps) {
  return (
    <span className="handoff-node" style={{ '--accent': app.accent }}>
      <span className="size-2.5 flex-none rounded-full bg-(--accent) shadow-[0_0_12px_var(--accent)]" aria-hidden="true" />
      <span className="min-w-0">
        <span className="flex flex-wrap items-baseline gap-x-2 text-sm font-semibold">
          {app.name}
          {isAvailable(app) ? null : <span className="text-[0.6875rem] font-medium text-faint">{statusLabel(app)}</span>}
        </span>
        <span className="block text-xs text-muted">{role}</span>
      </span>
    </span>
  );
}

/**
 * Renders the arrow between two steps of a hand-off, pointing down where the steps stack.
 *
 * @returns The arrow.
 */
function Arrow() {
  return (
    <span className="grid flex-none place-items-center text-faint" aria-hidden="true">
      <ArrowDown className="size-4 sm:hidden" />
      <ArrowRight className="hidden size-4 sm:block" />
    </span>
  );
}
