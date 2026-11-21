/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The second landing page's apps, in brief: the app that is live with a way to launch it, and the
 * ones on the way named beside it.
 *
 * The first take gives every app a full card (`../Apps.tsx`); here the gallery has already made
 * the case, so this is a compact answer to "what can I open today". Both read the same catalog.
 * @module
 */
import { ArrowRight } from 'lucide-react';
import { AppName, ArtImage } from '../../components/Art';
import { liveApps, upcomingApps, type CatalogApp } from '../../lib/catalog';
import { appImage, hasStackedLogo } from '../../lib/media';
import { SectionHeading } from '../SectionHeading';

const list = new Intl.ListFormat('en-US', { type: 'conjunction' });

/**
 * Renders the compact apps section.
 *
 * @returns The section.
 */
export function AppRow() {
  const liveNames = list.format(liveApps.map((app) => app.name));
  return (
    <section id="apps" className="section" aria-labelledby="apps-title">
      <div className="shell">
        <SectionHeading
          id="apps-title"
          eyebrow="Apps"
          title={liveApps.length === 0 ? 'The first apps are on the way' : `${liveNames} today. More on the way.`}
          lede="Open what is ready now. The rest will appear here as each one goes live."
        />
        <div className="mt-12 grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
          {liveApps.length === 0 ? null : (
            <ul className="grid gap-5">
              {liveApps.map((app) => (
                <li key={app.id} className="flex">
                  <LiveApp app={app} />
                </li>
              ))}
            </ul>
          )}
          {upcomingApps.length === 0 ? null : (
            <div className="glass p-6 sm:p-7">
              <h3 className="text-xs font-semibold tracking-[0.16em] text-faint uppercase">Coming soon</h3>
              <ul className="mt-4 grid gap-3 sm:grid-cols-2">
                {upcomingApps.map((app) => (
                  <li
                    key={app.id}
                    // An odd one out at the end takes the whole row instead of leaving half of it empty.
                    className="app-card-soon flex items-center gap-3.5 rounded-2xl border border-line bg-white/[0.03] p-2.5 sm:last:odd:col-span-2"
                    style={{ '--accent': app.accent }}
                  >
                    <span className="art h-14 w-20 flex-none rounded-xl">
                      <ArtImage src={appImage(app.id)} width={1200} height={800} />
                    </span>
                    <AppName
                      app={app}
                      logoClassName={hasStackedLogo(app.id) ? 'h-10' : 'h-6'}
                      textClassName="min-w-0 text-[0.9375rem] font-semibold"
                    />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

/** Props of {@link LiveApp}. */
interface LiveAppProps {
  /** The available app the card presents. */
  app: CatalogApp;
}

/**
 * Renders an available app as a wide card: its art beside its logo, what it is for, and the way
 * to launch it.
 *
 * @param props The component's props.
 * @returns The card.
 */
function LiveApp({ app }: LiveAppProps) {
  return (
    <article className="app-card app-card-live w-full sm:flex-row" style={{ '--accent': app.accent }}>
      <div className="art aspect-[3/2] sm:aspect-auto sm:w-[42%] sm:flex-none">
        <ArtImage src={appImage(app.id)} width={1200} height={800} />
        <span className="pill absolute top-3.5 left-3.5 z-10">
          <span className="dot dot-live" aria-hidden="true" />
          Live
        </span>
      </div>
      <div className="flex flex-1 flex-col justify-center p-6 sm:p-7">
        <div className="flex min-h-12 items-center justify-between gap-4">
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
        <p className="lede mt-4 text-[0.9375rem]">{app.tagline}</p>
        <a href="#signup" className="btn btn-primary mt-6 w-full sm:w-fit">
          Launch {app.name}
          <ArrowRight className="size-4" aria-hidden="true" />
        </a>
      </div>
    </article>
  );
}
