/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's hero: the agent's status, the promise, the prompt box that starts a project,
 * and the display where the wordmark turns into what the studio makes.
 *
 * The display is the page's signature. The wordmark assembles from scattered pixels once, then
 * morphs without end through a heart, a game controller, a film clapper, a picture, a sound wave,
 * and a smiling face (`lib/moody.ts`, the Morph), and the line under it finishes the headline's
 * sentence for whichever shape is showing. On a narrow screen the display sits between the words
 * and the prompt box; beside them on a wide one. Below the hero a ticker runs through every format
 * the catalog's disciplines name.
 * @module
 */
import { useCallback, useState } from 'react';
import { MoodyMotion } from '../components/Moody';
import { brand, catalog, cheapestTier, minutesFor } from '../lib/catalog';
import { creditCount, minutesText } from '../lib/format';
import { ANIMATION, GRID_COLS, GRID_ROWS, morphShapeAt, type MorphShape, type View } from '../lib/moody';
import { PromptBox } from './PromptBox';

/** The display's view: the wordmark with a cell of room at each side, and the height of the tallest shape. */
const DISPLAY_VIEW: View = { cx: 0, cy: 0, cols: GRID_COLS + 2, rows: 17 };

/** How the display's caption ends "Make" for each shape of the morph. */
const CAPTIONS: Readonly<Record<MorphShape, string>> = {
  wordmark: 'whatever you imagine',
  heart: 'something you love',
  controller: 'a game',
  clapper: 'a film',
  picture: 'an image',
  waveform: 'a song',
  face: 'someone smile',
};

/**
 * Renders the hero section.
 *
 * @returns The section.
 */
export function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="shell grid grid-cols-[minmax(0,1fr)] gap-x-16 gap-y-9 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
        <div className="lg:col-start-1 lg:row-start-1">
          <p className="eyebrow animate-rise text-fg">
            <span className="dot dot-live" aria-hidden="true" />
            Your creative agent is online
          </p>
          <h1
            id="hero-title"
            className="display mt-6 animate-rise text-[2.9rem] [animation-delay:60ms] sm:text-7xl lg:text-[3.75rem] xl:text-[4.75rem]"
          >
            <span className="block">Make whatever</span>
            <span className="block">you imagine.</span>
          </h1>
          <p className="mt-6 animate-rise text-xl font-medium tracking-tight [animation-delay:120ms] sm:text-2xl">
            One creative agent. An entire production studio.
          </p>
          <p className="lede mt-2 max-w-xl animate-rise text-[1.0625rem] [animation-delay:160ms] sm:text-lg">
            Create films, games, music and worlds with the power of cloud computing.
          </p>
        </div>
        <Display />
        <div className="animate-rise [animation-delay:220ms] lg:col-start-1 lg:row-start-2">
          <PromptBox />
          <p className="mt-3 text-sm text-faint">
            No card needed. {creditCount(catalog.signup_credits)} free credits to start
            {cheapestTier === undefined
              ? '.'
              : `, ${minutesText(minutesFor(catalog.signup_credits, cheapestTier))} of engine time on ${cheapestTier.name}.`}
          </p>
        </div>
      </div>
      <Ticker />
    </section>
  );
}

/**
 * Renders the display: the wordmark's assembly, then its morph, captioned by the shape on screen.
 *
 * @returns The figure.
 */
function Display() {
  const [shape, setShape] = useState<MorphShape>('wordmark');
  const onFrame = useCallback((index: number, seconds: number): void => {
    setShape(index === ANIMATION.morph ? morphShapeAt(seconds) : 'wordmark');
  }, []);
  return (
    <figure className="stage animate-rise self-center [animation-delay:200ms] lg:col-start-2 lg:row-span-2 lg:row-start-1">
      <div className="stage-bar" aria-hidden="true">
        <span className="dot dot-live" />
        {brand}
        <span className="ml-auto text-faint">
          {GRID_COLS} × {GRID_ROWS}
        </span>
      </div>
      <MoodyMotion
        animation={ANIMATION.morph}
        intro={ANIMATION.assembly}
        onFrame={onFrame}
        view={DISPLAY_VIEW}
        label={`The ${brand} wordmark turning into a heart, a game controller, a film clapper, a picture, a sound wave, and a smiling face`}
        className="relative aspect-[28/17] w-full"
      />
      <figcaption className="stage-bar min-h-12 text-[0.8125rem]" aria-hidden="true">
        <span className="text-faint">Make</span>
        <span className="cursor truncate text-lavender">{CAPTIONS[shape]}</span>
      </figcaption>
    </figure>
  );
}

/**
 * Renders the ticker: every format the catalog's disciplines name, running past in one line.
 *
 * It is decoration, hidden from assistive technology, since the disciplines section lists the same
 * formats where they can be read. The line is drawn twice so that it loops without a seam.
 *
 * @returns The ticker.
 */
function Ticker() {
  const formats = [...new Set(catalog.disciplines.flatMap((discipline) => discipline.formats))];
  return (
    <div className="ticker mt-14 lg:mt-20" aria-hidden="true">
      {[0, 1].map((copy) => (
        <ul key={copy} className="ticker-track">
          {formats.map((format) => (
            <li key={format} className="flex items-center gap-8">
              {format}
              <span className="size-1.5 bg-line-strong" />
            </li>
          ))}
        </ul>
      ))}
    </div>
  );
}
