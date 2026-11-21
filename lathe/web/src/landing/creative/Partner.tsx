/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The second landing page's section on working with Claude, told as what it is like: describe a
 * scene, watch it get built, take over whenever.
 *
 * The first take shows the command and the tools (`../AgentSection.tsx`); this one shows neither.
 * How to connect is the dashboard's to explain, which is where its call to action leads. The
 * exchange drawn over the art is labeled as an example, since it is one.
 * @module
 */
import { ArrowRight, Check, Sparkles } from 'lucide-react';
import { ArtImage } from '../../components/Art';
import { liveApps } from '../../lib/catalog';
import { cx } from '../../lib/cx';
import { AGENT_ART } from '../../lib/media';

/** What working this way comes to, in three short lines. */
const POINTS = [
  'Say what you want in plain words.',
  'Watch each step happen in your own viewport.',
  'Take the mouse back whenever you like.',
];

/** One turn of the example exchange. */
interface Turn {
  /** Whether the visitor or Claude is speaking. */
  from: 'you' | 'claude';
  /** What is said. */
  words: string;
}

/** The example exchange. */
const EXCHANGE: readonly Turn[] = [
  { from: 'you', words: 'A ceramic vase on a wooden table, with warm light from the left.' },
  { from: 'claude', words: 'Done. The vase is on the table with a warm key light. Want the glaze glossier?' },
  { from: 'you', words: 'Yes. And make it evening.' },
];

/**
 * Renders the section.
 *
 * @returns The section.
 */
export function Partner() {
  const app = liveApps[0]?.name ?? 'app';
  return (
    <section id="claude" className="section" aria-labelledby="claude-title">
      <div className="shell grid grid-cols-[minmax(0,1fr)] items-center gap-12 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:gap-16">
        <div>
          <p className="eyebrow">
            <Sparkles className="size-4" aria-hidden="true" />
            A creative partner
          </p>
          <h2 id="claude-title" className="display mt-4 text-[2rem] sm:text-5xl">
            Describe a scene. <span className="text-gradient block w-fit">Watch it get built in front of you.</span>
          </h2>
          <p className="lede mt-5 text-[1.0625rem] sm:text-lg">
            Claude can set up scenes, lighting, and materials in the same {app} you have open. You watch it happen, and
            you can take over at any moment.
          </p>
          <ul className="mt-8 grid gap-3">
            {POINTS.map((point) => (
              <li key={point} className="flex items-center gap-3.5 text-[0.9375rem]">
                <span className="grid size-7 flex-none place-items-center rounded-full border border-ember/40 bg-ember/10 text-ember-300">
                  <Check className="size-3.5" aria-hidden="true" />
                </span>
                {point}
              </li>
            ))}
          </ul>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
            <a href="#signup" className="btn btn-primary btn-lg">
              Set it up in your dashboard
              <ArrowRight className="size-4" aria-hidden="true" />
            </a>
            <span className="text-sm text-muted">Works with Claude.</span>
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
            <p className="text-[0.6875rem] font-semibold tracking-[0.16em] text-faint uppercase">Example</p>
            <ul className="mt-3 grid gap-2.5">
              {EXCHANGE.map((turn) => (
                <li
                  key={turn.words}
                  className={cx('flex items-start gap-2.5', turn.from === 'you' && 'justify-end')}
                >
                  {turn.from === 'claude' ? (
                    <Sparkles className="mt-2.5 size-4 flex-none text-ember-300" aria-hidden="true" />
                  ) : null}
                  <p
                    className={cx(
                      'max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm',
                      turn.from === 'you'
                        ? 'rounded-br-sm border border-line bg-white/[0.07]'
                        : 'rounded-tl-sm bg-black/30 text-muted',
                    )}
                  >
                    <span className="sr-only">{turn.from === 'you' ? 'You: ' : 'Claude: '}</span>
                    {turn.words}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
