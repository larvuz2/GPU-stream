/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's plain statements about the product: the three facts under the hero, the
 * three steps of using it, and the grid of what a session comes with.
 *
 * Each says what the product does and nothing measured: no speeds, counts, or guarantees. The
 * steps section is also the second take's, which gives it steps in its own words.
 * @module
 */
import {
  AppWindow,
  FolderCheck,
  Globe,
  HardDrive,
  Hourglass,
  MousePointerClick,
  Power,
  RefreshCcw,
  Save,
  ShieldCheck,
  TimerOff,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { brand, catalog, IDLE_SHUTDOWN_MINUTES, namedRegions } from '../lib/catalog';
import { SectionHeading } from './SectionHeading';

/** A statement with an icon: a title and a sentence under it. */
export interface Point {
  /** The icon beside the title. */
  icon: LucideIcon;
  /** The statement. */
  title: string;
  /** The sentence that explains it. */
  body: string;
}

const list = new Intl.ListFormat('en-US', { type: 'conjunction' });

/** The three facts a visitor should leave the hero knowing. */
const FACTS: readonly Point[] = [
  { icon: Zap, title: 'Starts in seconds', body: 'Pick an app and the stream opens in a new tab.' },
  {
    icon: Power,
    title: `Shuts itself off after ${IDLE_SHUTDOWN_MINUTES} idle minutes`,
    body: 'Nobody pays for a forgotten tab.',
  },
  { icon: FolderCheck, title: 'Your files persist', body: 'Your workspace is there next session.' },
];

/**
 * Renders the strip of three facts under the hero.
 *
 * @returns The strip.
 */
export function TrustStrip() {
  return (
    <section className="relative pt-14 sm:pt-20" aria-label="At a glance">
      <div className="shell">
        <ul className="glass grid divide-y divide-line sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {FACTS.map(({ icon: Icon, title, body }) => (
            <li key={title} className="flex items-center gap-4 p-5 sm:p-6">
              <span className="icon-tile">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <div>
                <p className="leading-snug font-semibold tracking-tight">{title}</p>
                <p className="mt-1 text-sm text-muted">{body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/**
 * The first take's three steps, written from the catalog's first and last tiers.
 *
 * @returns The steps in order.
 */
function technicalSteps(): Point[] {
  const first = catalog.tiers[0];
  const last = catalog.tiers.at(-1);
  const range =
    first === undefined || last === undefined || first === last ? '' : `, from ${first.name} to ${last.name}`;
  return [
    {
      icon: MousePointerClick,
      title: 'Pick an app',
      body: `Choose what you want to run and the tier to run it on${range}. That is the whole setup.`,
    },
    {
      icon: AppWindow,
      title: 'Open the tab',
      body: 'Your workstation starts and its screen streams to a new browser tab. Your keyboard and mouse drive the app as if it were installed on your machine.',
    },
    {
      icon: Save,
      title: 'Save to your workspace',
      body: 'Save into the workspace folder and close the tab. The session shuts itself off, and your files are waiting the next time you start one.',
    },
  ];
}

/** Props of {@link HowItWorks}. */
interface HowItWorksProps {
  /** The section's title. */
  title?: string;
  /** The sentence under the title. */
  lede?: string;
  /** The steps, in order; the first take's when left out. */
  steps?: Point[];
}

/**
 * Renders the "how it works" section: three numbered steps.
 *
 * @param props The component's props.
 * @returns The section.
 */
export function HowItWorks({
  title = 'From zero to viewport in three steps',
  lede = 'No installer, no driver hunt, no render box under the desk.',
  steps = technicalSteps(),
}: HowItWorksProps) {
  return (
    <section id="how" className="section" aria-labelledby="how-title">
      <div className="shell">
        <SectionHeading id="how-title" eyebrow="How it works" title={title} lede={lede} />
        <ol className="mt-12 grid gap-5 md:grid-cols-3">
          {steps.map(({ icon: Icon, title: step, body }, index) => (
            <li key={step} className="glass glass-hover relative p-7">
              <div className="flex items-center justify-between">
                <span className="icon-tile size-12">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <span className="display text-gradient text-5xl opacity-45" aria-hidden="true">
                  0{index + 1}
                </span>
              </div>
              <h3 className="mt-6 text-xl font-semibold tracking-tight">{step}</h3>
              <p className="lede mt-2.5 text-[0.9375rem]">{body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/**
 * What a session comes with, the region names read from the catalog.
 *
 * @returns The features.
 */
function features(): Point[] {
  return [
    {
      icon: ShieldCheck,
      title: 'A session of your own',
      body: 'Every session is a separate workstation that only you can open. Your desktop and your files are not shared with another user.',
    },
    {
      icon: TimerOff,
      title: 'Automatic shutdown',
      body: `Walk away and the session notices. After ${IDLE_SHUTDOWN_MINUTES} minutes with no activity it stops itself, and the meter stops with it.`,
    },
    {
      icon: HardDrive,
      title: 'A workspace that persists',
      body: 'What you save to your workspace is kept when a session ends and is back in place when the next one starts.',
    },
    {
      icon: Hourglass,
      title: 'A queue when it is busy',
      body: 'If every machine is taken, you get a place in line and can see it, instead of an error and a retry button.',
    },
    {
      icon: Globe,
      title: 'Your choice of region',
      body:
        namedRegions.length === 0
          ? `Leave the placement to ${brand} and it picks for you.`
          : `Run in ${list.format(namedRegions.map((region) => region.name))}, or leave it on automatic.`,
    },
    {
      icon: RefreshCcw,
      title: 'Crash recovery',
      body: 'If the app goes down mid-session it is brought back up, and the files you saved to your workspace are untouched.',
    },
  ];
}

/**
 * Renders the features grid.
 *
 * @returns The section.
 */
export function Features() {
  return (
    <section className="section" aria-labelledby="features-title">
      <div className="shell">
        <SectionHeading
          id="features-title"
          eyebrow="What you get"
          title="A workstation that looks after itself"
          lede="The parts of running a remote machine you would rather not think about are already handled."
        />
        <ul className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features().map(({ icon: Icon, title, body }) => (
            <li key={title} className="glass glass-hover p-7">
              <span className="icon-tile">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <h3 className="mt-5 text-lg font-semibold tracking-tight">{title}</h3>
              <p className="lede mt-2 text-[0.9375rem]">{body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
