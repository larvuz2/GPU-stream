/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The hero of the second landing page: what a visitor gets to do, before how any of it works.
 *
 * It is the first take's hero in build (`../Hero.tsx`: the same pill, calls to action, strip of
 * app names, and window on its stage) with its own words, its own art in the window, and a note
 * about coming back to a scene instead of one about an agent's tool.
 * @module
 */
import { ArrowRight, History, Images } from 'lucide-react';
import { catalog, cheapestTier, liveApps, minutesFor } from '../../lib/catalog';
import { minutesText } from '../../lib/format';
import { CREATIVE_HERO_ART } from '../../lib/media';
import { AppStrip, StreamStage, type WindowNote } from '../Hero';

/** What the chip over the window says: the scene left open is the one that comes back. */
const RETURN_NOTE: WindowNote = {
  icon: History,
  title: 'Picked up where you left off',
  detail: 'Your last scene, reopened',
};

/**
 * Renders the hero section.
 *
 * @returns The section.
 */
export function CreativeHero() {
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
              is ready when you are
            </span>
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </a>
        )}
        <h1
          id="hero-title"
          className="display mx-auto mt-6 max-w-[62rem] animate-rise text-[2.65rem] [animation-delay:60ms] sm:text-7xl lg:text-[5.4rem]"
        >
          Bring the idea. <span className="text-gradient mx-auto block w-fit">We bring the machine.</span>
        </h1>
        <p className="lede mx-auto mt-6 max-w-2xl animate-rise text-[1.0625rem] [animation-delay:120ms] sm:text-xl">
          Open {live?.name ?? 'your creative apps'} in a browser tab on a powerful cloud workstation and make the thing
          you have been picturing. Close the tab when you are done. Next time, you pick up right where you left off.
        </p>
        <div className="mt-9 flex animate-rise flex-col items-center justify-center gap-3 [animation-delay:180ms] sm:flex-row">
          <a href="#signup" className="btn btn-primary btn-lg w-full sm:w-auto">
            Start free — {catalog.signup_credits} credits on us
            <ArrowRight className="size-4" aria-hidden="true" />
          </a>
          <a href="#make" className="btn btn-ghost btn-lg w-full sm:w-auto">
            <Images className="size-4" aria-hidden="true" />
            See what you can make
          </a>
        </div>
        <p className="mt-4 animate-rise text-sm text-faint [animation-delay:220ms]">
          No card needed to sign up
          {cheapestTier === undefined
            ? null
            : ` · the free credits cover ${minutesText(minutesFor(catalog.signup_credits, cheapestTier))} on ${cheapestTier.name}`}
        </p>
        <AppStrip />
      </div>
      <StreamStage app={live} art={CREATIVE_HERO_ART} note={RETURN_NOTE} />
    </section>
  );
}
