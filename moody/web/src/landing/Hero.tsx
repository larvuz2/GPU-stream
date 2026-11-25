/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's hero: the promise, the prompt box that starts a project, and the frame the
 * product video plays in.
 *
 * The backdrop is concept art of an empty soundstage, its subject in the right half so the
 * words on the left stay on dark ground; it fades into the page below. The video frame is built
 * around one value, `PRODUCT_VIDEO` in `lib/media.ts`: while it is `null` the frame shows its
 * poster under a play button marked as coming soon, and once it names a file the same button
 * plays it in place.
 * @module
 */
import { useState } from 'react';
import { ArrowRight, Play } from 'lucide-react';
import { ArtImage } from '../components/Art';
import { catalog, cheapestTier, liveApps, minutesFor } from '../lib/catalog';
import { creditCount, minutesText } from '../lib/format';
import { HERO_ART, PRODUCT_VIDEO, VIDEO_POSTER } from '../lib/media';
import { PromptBox } from './PromptBox';
import { listFormat } from './studio';

/**
 * Renders the hero section.
 *
 * @returns The section.
 */
export function Hero() {
  const live = listFormat.format(liveApps.map((app) => [app.name, app.version].filter(Boolean).join(' ')));
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-art" aria-hidden="true">
        <ArtImage src={HERO_ART} width={1920} height={864} priority />
      </div>
      <div className="shell relative z-10 grid grid-cols-[minmax(0,1fr)] items-center gap-12 lg:grid-cols-[minmax(0,1.08fr)_minmax(0,1fr)] lg:gap-14">
        <div>
          {liveApps.length === 0 ? null : (
            <a href="#engines" className="pill animate-rise h-8 max-w-full gap-2 pr-2.5 pl-3 text-[0.8125rem] font-medium text-muted">
              <span className="dot dot-live" aria-hidden="true" />
              <span className="truncate">
                <span className="font-semibold text-fg">{live}</span> {liveApps.length === 1 ? 'is' : 'are'} live
              </span>
              <ArrowRight className="size-3.5 flex-none" aria-hidden="true" />
            </a>
          )}
          <h1
            id="hero-title"
            className="display mt-6 animate-rise text-[2.6rem] [animation-delay:60ms] sm:text-6xl xl:text-[4.25rem]"
          >
            Describe it. <span className="text-gradient block w-fit">An agent builds it with you.</span>
          </h1>
          <p className="lede mt-5 max-w-xl animate-rise text-[1.0625rem] [animation-delay:120ms] sm:text-lg">
            Say what you want to make. A creative agent plans it with you, builds its characters, worlds, and props,
            and works in real creative software on cloud GPUs while you watch and steer.
          </p>
          <div className="animate-rise [animation-delay:180ms]">
            <PromptBox />
          </div>
          <p className="mt-2 text-sm text-faint">
            No card needed. {creditCount(catalog.signup_credits)} free credits to start
            {cheapestTier === undefined
              ? '.'
              : `, ${minutesText(minutesFor(catalog.signup_credits, cheapestTier))} of engine time on ${cheapestTier.name}.`}
          </p>
        </div>
        <ProductVideo />
      </div>
    </section>
  );
}

/**
 * Renders the 16:9 frame of the product video: the poster and a play button that plays the video
 * in place, or says it is coming while there is none.
 *
 * @returns The frame.
 */
function ProductVideo() {
  const [playing, setPlaying] = useState(false);
  const video = PRODUCT_VIDEO;
  return (
    <figure className="animate-rise [animation-delay:240ms]">
      <div className="video-frame">
        <div className="art aspect-video overflow-hidden rounded-[inherit]">
          {playing && video !== null ? (
            <video
              src={video}
              poster={VIDEO_POSTER}
              className="absolute inset-0 size-full bg-black object-cover"
              controls
              autoPlay
              playsInline
            />
          ) : (
            <>
              <ArtImage src={VIDEO_POSTER} width={1280} height={720} priority />
              <div className="video-scrim" aria-hidden="true" />
              {video === null ? (
                <span className="play-button" aria-hidden="true">
                  <Play className="size-7 translate-x-0.5 fill-current" />
                </span>
              ) : (
                <button
                  type="button"
                  className="play-button"
                  aria-label="Play the product video"
                  onClick={() => {
                    setPlaying(true);
                  }}
                >
                  <Play className="size-7 translate-x-0.5 fill-current" aria-hidden="true" />
                </button>
              )}
              <span className="pill absolute bottom-3.5 left-3.5 z-10 text-muted">
                {video === null ? 'Product video coming soon' : 'Watch the studio at work'}
              </span>
            </>
          )}
        </div>
      </div>
    </figure>
  );
}
