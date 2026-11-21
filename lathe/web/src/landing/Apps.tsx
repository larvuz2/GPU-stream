/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's app cards, one per catalog app.
 *
 * A card is tinted by its app's accent and topped by the app's art; an app that can be launched
 * gets the call to action, and one that is only announced steps back (its art dimmed, a "Coming
 * soon" badge) while staying a card worth looking at. An official logo is never dimmed with it.
 * @module
 */
import { ArrowRight } from 'lucide-react';
import { AppName, ArtImage } from '../components/Art';
import { catalog, isAvailable, liveApps, type CatalogApp } from '../lib/catalog';
import { cx } from '../lib/cx';
import { appImage, hasStackedLogo } from '../lib/media';
import { SectionHeading } from './SectionHeading';

const list = new Intl.ListFormat('en-US', { type: 'conjunction' });

/**
 * Renders the apps section.
 *
 * @returns The section.
 */
export function Apps() {
  const liveNames = list.format(liveApps.map((app) => app.name));
  return (
    <section id="apps" className="section" aria-labelledby="apps-title">
      <div className="shell">
        <SectionHeading
          id="apps-title"
          eyebrow="Apps"
          title="The tools you already know, one click away"
          lede={
            liveApps.length === 0
              ? 'The first apps are on their way.'
              : `${liveNames} ${liveApps.length === 1 ? 'is' : 'are'} live today. More creative apps are on the way.`
          }
        />
        <ul className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {catalog.apps.map((app) => (
            <li key={app.id} className="flex">
              <AppCard app={app} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** Props of {@link AppCard}. */
interface AppCardProps {
  /** The app the card presents. */
  app: CatalogApp;
}

/**
 * Renders one app's card.
 *
 * @param props The component's props.
 * @returns The card.
 */
function AppCard({ app }: AppCardProps) {
  const live = isAvailable(app);
  return (
    <article
      className={cx('app-card w-full', live ? 'app-card-live' : 'app-card-soon')}
      style={{ '--accent': app.accent }}
    >
      <div className="art art-scrim aspect-[3/2]">
        <ArtImage src={appImage(app.id)} width={1200} height={800} />
        <span className="pill absolute top-3.5 left-3.5 z-10">
          {live ? (
            <>
              <span className="dot dot-live" aria-hidden="true" />
              Live
            </>
          ) : (
            <span className="text-muted">Coming soon</span>
          )}
        </span>
      </div>
      <div className="flex flex-1 flex-col p-6">
        <div className="flex min-h-14 items-center justify-between gap-4">
          <h3 className="flex items-center">
            <AppName
              app={app}
              logoClassName={hasStackedLogo(app.id) ? 'h-14' : 'h-9'}
              textClassName="text-2xl font-semibold tracking-tight"
            />
          </h3>
          {app.version === '' ? null : (
            <span className="pill border-line bg-white/5 text-muted backdrop-blur-none">{app.version}</span>
          )}
        </div>
        <p className="lede mt-4 flex-1 text-[0.9375rem]">{app.tagline}</p>
        <div className="mt-6">
          {live ? (
            <a href="#signup" className="btn btn-primary w-full">
              Launch {app.name}
              <ArrowRight className="size-4" aria-hidden="true" />
            </a>
          ) : (
            <p className="flex h-11 items-center justify-center rounded-full border border-dashed border-line-strong text-sm font-medium text-faint">
              Coming soon
            </p>
          )}
        </div>
      </div>
    </article>
  );
}
