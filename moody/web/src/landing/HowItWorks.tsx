/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's "how it works": the four steps of a project, from the first sentence to the
 * export.
 *
 * Each step says what the studio does and nothing measured. The engines named are the catalog's
 * live ones, and the library's sections are the film's, the example the plan builds first; the
 * agent gives every project the sections its work needs.
 * @module
 */
import { Boxes, Check, MessageSquareText, MonitorPlay, type LucideIcon } from 'lucide-react';
import { liveApps } from '../lib/catalog';
import { SectionHeading } from './SectionHeading';
import { listFormat } from './studio';

/** One step of a project. */
interface Step {
  /** The icon beside the step's number. */
  icon: LucideIcon;
  /** The step, in a few words. */
  title: string;
  /** What happens in it. */
  body: string;
  /** Small labels under the body that show the step's material. */
  tags: string[];
}

/**
 * The four steps, naming the live engines.
 *
 * @returns The steps in order.
 */
function steps(): Step[] {
  const engines = liveApps.map((app) => app.name);
  return [
    {
      icon: MessageSquareText,
      title: 'Describe it',
      body: 'Say what you want to make, in your own words, or bring a script you already have. Pick a discipline and a format, or let the agent ask.',
      tags: ['A sentence', 'A script', 'A reference'],
    },
    {
      icon: Boxes,
      title: 'The agent plans and builds your library',
      body: 'It writes the plan with you, then fills the project library: characters, environments, and props, each with reference images you approve.',
      tags: ['Characters', 'Environments', 'Props'],
    },
    {
      icon: MonitorPlay,
      title: 'It opens engines on cloud GPUs',
      body: `${engines.length === 0 ? 'Creative engines start' : `${listFormat.format(engines)} start`} on a cloud GPU and stream to your tab. The agent works in them while you watch, and you can steer or take the controls at any moment.`,
      tags: engines,
    },
    {
      icon: Check,
      title: 'You decide, and export',
      body: 'The agent asks at every decision that is yours: the ending, the cut, the color. Approve it, export it, and keep every file of the project.',
      tags: ['Your call', 'Export', 'Keep the files'],
    },
  ];
}

/**
 * Renders the "how it works" section.
 *
 * @returns The section.
 */
export function HowItWorks() {
  return (
    <section id="how" className="section" aria-labelledby="how-title">
      <div className="shell">
        <SectionHeading
          id="how-title"
          eyebrow="How it works"
          title="From one sentence to a finished piece"
          lede="You bring the idea and make the calls. The agent does the legwork in real creative software."
        />
        <ol className="mt-12 grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-2 xl:grid-cols-4">
          {steps().map(({ icon: Icon, title, body, tags }, index) => (
            <li key={title} className="glass glass-hover relative flex flex-col p-6">
              <div className="flex items-center justify-between">
                <span className="icon-tile">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <span className="display text-gradient text-4xl opacity-60" aria-hidden="true">
                  0{index + 1}
                </span>
              </div>
              <h3 className="mt-6 text-lg leading-snug font-semibold tracking-tight">{title}</h3>
              <p className="lede mt-2 flex-1 text-[0.9375rem]">{body}</p>
              <ul className="mt-5 flex flex-wrap gap-1.5" aria-label="Examples">
                {tags.map((tag) => (
                  <li key={tag} className="engine-tag">
                    {tag}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
