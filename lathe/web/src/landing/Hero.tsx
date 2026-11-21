/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's hero: the headline, the two calls to action, the apps named by their logos,
 * and the streaming window with its rings.
 *
 * The window frames the hero art, concept imagery that is decoration rather than a picture of the
 * product. Should the file be missing, a drawn stand-in takes its place: the rings of a form
 * turning on a lathe, in the same frame.
 *
 * The window on its stage and the strip of app names are what any hero of this page is built
 * from, so they are exported for the second take's hero (`creative/CreativeHero.tsx`), which sets
 * its own art and its own note in the same frame.
 * @module
 */
import { useState } from 'react';
import { ArrowRight, Lock, Play, Sparkles, type LucideIcon } from 'lucide-react';
import { AppName, ArtImage } from '../components/Art';
import { brand, catalog, cheapestTier, liveApps, minutesFor, upcomingApps, type CatalogApp } from '../lib/catalog';
import { cx } from '../lib/cx';
import { creditCount, minutesText } from '../lib/format';
import { SCRIPT_TOOL } from '../lib/mcp';
import { hasStackedLogo, HERO_ART } from '../lib/media';

/**
 * Renders the hero section.
 *
 * @returns The section.
 */
export function Hero() {
  const live = liveApps[0];
  return (
    <section className="relative pt-12 pb-10 sm:pt-20" aria-labelledby="hero-title">
      <div className="shell relative z-10 text-center">
        {live === undefined ? null : (
          <a href="#apps" className="pill animate-rise h-8 gap-2 pr-2.5 pl-3 text-[0.8125rem] font-medium text-muted">
            <span className="dot dot-live" aria-hidden="true" />
            <span>
              <span className="font-semibold text-fg">
                {live.name} {live.version}
              </span>{' '}
              is live
            </span>
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </a>
        )}
        <h1
          id="hero-title"
          className="display mx-auto mt-6 max-w-[62rem] animate-rise text-[2.65rem] [animation-delay:60ms] sm:text-7xl lg:text-[5.4rem]"
        >
          Spin up a GPU studio <span className="text-gradient mx-auto block w-fit">in your browser</span>
        </h1>
        <p className="lede mx-auto mt-6 max-w-2xl animate-rise text-[1.0625rem] [animation-delay:120ms] sm:text-xl">
          {brand} runs your creative apps on cloud workstations and streams them to a tab in seconds. Nothing to
          install, no hardware to buy, and Claude can work in the same session while you watch.
        </p>
        <div className="mt-9 flex animate-rise flex-col items-center justify-center gap-3 [animation-delay:180ms] sm:flex-row">
          <a href="#signup" className="btn btn-primary btn-lg w-full sm:w-auto">
            Start free — {catalog.signup_credits} credits on us
            <ArrowRight className="size-4" aria-hidden="true" />
          </a>
          <a href="#how" className="btn btn-ghost btn-lg w-full sm:w-auto">
            <Play className="size-4" aria-hidden="true" />
            See how it works
          </a>
        </div>
        <p className="mt-4 animate-rise text-sm text-faint [animation-delay:220ms]">
          No card needed to sign up
          {cheapestTier === undefined
            ? null
            : ` · ${creditCount(catalog.signup_credits)} credits is ${minutesText(minutesFor(catalog.signup_credits, cheapestTier))} on ${cheapestTier.name}`}
        </p>
        <AppStrip />
      </div>

      <StreamStage app={live} />
    </section>
  );
}

/** What the chip floating over the window says: one thing going on in the session it frames. */
export interface WindowNote {
  /** The icon in the chip's tile. */
  icon: LucideIcon;
  /** The chip's statement. */
  title: string;
  /** The line under the statement. */
  detail: string;
  /** Whether the detail is an identifier, set in the monospace face. */
  code?: boolean;
}

/** The note of the first take: an agent at work, named by the tool it is running. */
const AGENT_NOTE: WindowNote = {
  icon: Sparkles,
  title: 'Claude is in the session',
  detail: SCRIPT_TOOL,
  code: true,
};

/** Props of {@link StreamStage}. */
interface StreamStageProps {
  /** The app the window's title names, when one is live. */
  app: CatalogApp | undefined;
  /** The address of the art the window frames. */
  art?: string;
  /** What the chip over the window says. */
  note?: WindowNote;
}

/**
 * Renders the hero's visual: the window in its light, with the rings turning behind it.
 *
 * @param props The component's props.
 * @returns The stage.
 */
export function StreamStage({ app, art = HERO_ART, note = AGENT_NOTE }: StreamStageProps) {
  return (
    <div className="shell relative mt-12 sm:mt-16">
      <div className="rings" aria-hidden="true">
        <span className="ring ring-1" />
        <span className="ring ring-2" />
        <span className="ring ring-3" />
        <span className="ring ring-4" />
      </div>
      <div className="relative mx-auto max-w-5xl">
        <div className="stream-glow" aria-hidden="true" />
        <StreamWindow app={app} art={art} note={note} />
      </div>
    </div>
  );
}

/**
 * Renders the row under the calls to action that names the apps: the live ones, then the ones on
 * the way, each by its official logo where there is one.
 *
 * @returns The row.
 */
export function AppStrip() {
  return (
    <div className="mt-10 flex animate-rise flex-col items-center justify-center gap-x-10 gap-y-5 [animation-delay:260ms] lg:flex-row">
      <AppGroup label="Live now" apps={liveApps} />
      <span className="hidden h-8 w-px bg-line lg:block" aria-hidden="true" />
      <AppGroup label="Coming soon" apps={upcomingApps} />
    </div>
  );
}

/** Props of {@link AppGroup}. */
interface AppGroupProps {
  /** What the apps in the group have in common. */
  label: string;
  /** The apps to name. */
  apps: CatalogApp[];
}

/**
 * Renders a labeled list of app names.
 *
 * @param props The component's props.
 * @returns The list, or nothing for an empty group.
 */
function AppGroup({ label, apps }: AppGroupProps) {
  if (apps.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col items-center gap-x-6 gap-y-3 sm:flex-row">
      <span className="text-xs font-semibold tracking-[0.16em] text-faint uppercase">{label}</span>
      <ul className="flex flex-wrap items-center justify-center gap-x-7 gap-y-3">
        {apps.map((app) => (
          <li key={app.id} className="flex items-center">
            <AppName
              app={app}
              logoClassName={hasStackedLogo(app.id) ? 'h-11' : 'h-7'}
              textClassName="text-[0.9375rem] font-semibold text-muted"
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Props of {@link StreamWindow}. */
interface StreamWindowProps {
  /** The app the window's title names, when one is live. */
  app: CatalogApp | undefined;
  /** The address of the art the window frames. */
  art: string;
  /** What the chip over the window says. */
  note: WindowNote;
}

/**
 * Renders the browser-tab frame around the hero art, with a chip that shows something going on in
 * the session.
 *
 * @param props The component's props.
 * @returns The frame.
 */
function StreamWindow({ app, art, note }: StreamWindowProps) {
  const [artMissing, setArtMissing] = useState(false);
  const { icon: NoteIcon } = note;
  return (
    <div className="stream-window animate-rise [animation-delay:320ms]">
      <div className="overflow-hidden rounded-[inherit]">
        <div className="flex h-10 items-center gap-3 border-b border-line bg-white/[0.035] px-3.5 sm:h-11 sm:px-4">
          <span className="flex gap-1.5" aria-hidden="true">
            <i className="size-2.5 rounded-full bg-white/15" />
            <i className="size-2.5 rounded-full bg-white/15" />
            <i className="size-2.5 rounded-full bg-white/15" />
          </span>
          <span className="mx-auto flex h-6 max-w-[70%] min-w-0 items-center gap-1.5 rounded-full border border-line bg-black/30 px-3 text-xs text-muted sm:h-7">
            <Lock className="size-3 flex-none" aria-hidden="true" />
            <span className="truncate">
              {brand} studio{app === undefined ? '' : ` · ${app.name}`}
            </span>
          </span>
          <span className="flex items-center gap-1.5 text-xs font-semibold text-ok">
            <span className="dot dot-live" aria-hidden="true" />
            Live
          </span>
        </div>
        <div className="art aspect-[4/3] sm:aspect-video">
          {artMissing ? (
            <LatheScene />
          ) : (
            <ArtImage
              src={art}
              width={1920}
              height={1080}
              priority
              onMissing={() => {
                setArtMissing(true);
              }}
            />
          )}
        </div>
      </div>
      <div
        className={cx(
          'glass absolute -bottom-7 left-3 z-10 flex max-w-[calc(100%-1.5rem)] animate-float items-center gap-3',
          'rounded-2xl bg-ink-800/85 py-2.5 pr-4 pl-2.5 text-left backdrop-blur-xl sm:-left-8 sm:bottom-10',
        )}
      >
        <span className="icon-tile size-10 rounded-xl">
          <NoteIcon className="size-[1.1rem]" aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-semibold">{note.title}</span>
          <span className={cx(note.code === true && 'mono', 'block truncate text-xs text-muted')}>
            {note.detail}
          </span>
        </span>
      </div>
    </div>
  );
}

/** The silhouette of the turned form: each ring's height in the drawing and its radius. */
const PROFILE: readonly (readonly [number, number])[] = [
  [70, 46],
  [88, 58],
  [106, 52],
  [124, 44],
  [142, 52],
  [160, 74],
  [178, 100],
  [196, 122],
  [214, 138],
  [232, 148],
  [250, 152],
  [268, 148],
  [286, 138],
  [304, 122],
  [322, 102],
  [340, 82],
  [358, 70],
  [376, 78],
];

/** How flat a ring is drawn, the cosine of the angle the form is seen from. */
const TILT = 0.22;

/**
 * Renders the stand-in for the hero art: a vase as the rings a lathe would cut it in, their dashes
 * circling as if it were turning.
 *
 * @returns The drawing.
 */
function LatheScene() {
  return (
    <svg
      viewBox="0 0 800 450"
      fill="none"
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 size-full drop-shadow-[0_0_14px_rgb(255_122_26/0.65)]"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="lathe-stroke" x1="400" y1="60" x2="400" y2="400" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ffc48f" />
          <stop offset="0.5" stopColor="#ff7a1a" />
          <stop offset="1" stopColor="#a678ff" />
        </linearGradient>
      </defs>
      <ellipse cx="400" cy="398" rx="220" ry="34" stroke="rgb(255 255 255 / 0.12)" />
      <ellipse cx="400" cy="398" rx="150" ry="23" stroke="rgb(255 255 255 / 0.08)" />
      <g stroke="url(#lathe-stroke)" strokeWidth="1.6" strokeLinecap="round">
        {PROFILE.map(([y, radius]) => (
          <ellipse key={y} className="lathe-ring" cx="400" cy={y} rx={radius} ry={radius * TILT} />
        ))}
        <polyline points={PROFILE.map(([y, radius]) => `${400 - radius},${y}`).join(' ')} opacity="0.55" />
        <polyline points={PROFILE.map(([y, radius]) => `${400 + radius},${y}`).join(' ')} opacity="0.55" />
      </g>
    </svg>
  );
}
