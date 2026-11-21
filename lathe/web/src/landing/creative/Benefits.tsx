/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The second landing page's benefits: what it is like to work this way.
 *
 * Each one is a behavior of the product said from the maker's side of the screen, the same
 * behaviors the first take lists as features (`../Features.tsx`): it opens in a tab, the work runs
 * on the cloud machine, the workspace and the open scene come back, it stops itself when idle, and
 * a session is private. Nothing here is measured and nothing is promised beyond those.
 * @module
 */
import { Fan, History, Laptop, LockKeyhole, Wallet } from 'lucide-react';
import { IDLE_SHUTDOWN_MINUTES, liveApps } from '../../lib/catalog';
import { cx } from '../../lib/cx';
import type { Point } from '../Features';
import { SectionHeading } from '../SectionHeading';

/**
 * The benefits, naming the live app where the catalog has one.
 *
 * @returns The benefits in the order they are shown.
 */
function benefits(): Point[] {
  const app = liveApps[0]?.name ?? 'Your app';
  return [
    {
      icon: Laptop,
      title: 'Nothing to buy. Nothing to install.',
      body: `${app} opens in a browser tab on the computer you already have. No workstation on the desk and no setup day.`,
    },
    {
      icon: Fan,
      title: 'The heavy work happens somewhere else',
      body: 'Big scenes and final-quality renders run on the cloud machine. Your laptop and its fan get the day off.',
    },
    {
      icon: History,
      title: 'It is all there next time',
      body: 'Your files, preferences, and add-ons are kept. The scene you had open reopens too, even if you had not saved it.',
    },
    {
      icon: Wallet,
      title: 'You only pay while you create',
      body: `Walk away and it stops itself after ${IDLE_SHUTDOWN_MINUTES} idle minutes, and the meter stops with it. There is no subscription.`,
    },
    {
      icon: LockKeyhole,
      title: 'Your work is yours alone',
      body: 'A private workstation and private files. Your desktop and your projects are not shared with anyone else.',
    },
  ];
}

/**
 * Renders the benefits section: three cards over two wider ones.
 *
 * @returns The section.
 */
export function Benefits() {
  const items = benefits();
  return (
    <section className="section" aria-labelledby="why-title">
      <div className="shell">
        <SectionHeading
          id="why-title"
          eyebrow="Why it feels better"
          title="All of the making. None of the machine."
          lede="What changes when the workstation is somewhere else and the work is still yours."
        />
        <ul className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-6">
          {items.map(({ icon: Icon, title, body }, index) => (
            <li
              key={title}
              className={cx(
                'glass glass-hover p-7',
                // Three across, then two; the fifth has a row to itself where the grid is two wide.
                index < 3 ? 'lg:col-span-2' : 'lg:col-span-3',
                index === items.length - 1 && 'sm:max-lg:col-span-2',
              )}
            >
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
