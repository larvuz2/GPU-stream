/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The centerpiece of the second landing page: a gallery of what people come here to make.
 *
 * Each card is a use case: art, a one-line promise, and a plain description. The art is concept
 * imagery and is never captioned as anyone's work or as something the product made. The cards are
 * laid out as a bento, two of them at feature size with the art filling the card, so the section
 * reads as a wall of possibilities rather than a product grid.
 *
 * A use case names the catalog apps it is made in, and the catalog decides what the card may say:
 * while one of them is available the whole card is a link that starts in it, and while none is,
 * the card is not a link, says "coming soon", and names them. A use case therefore cannot claim an
 * app before the catalog does.
 * @module
 */
import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { ArtImage } from '../../components/Art';
import { catalog, findApp, isAvailable, type CatalogApp } from '../../lib/catalog';
import { cx } from '../../lib/cx';
import { appImage, useCaseImage } from '../../lib/media';
import { SectionHeading } from '../SectionHeading';

/** Something a visitor might come to make. */
interface UseCase {
  /** What the use case is called. */
  title: string;
  /** One line on what it lets its maker do. */
  promise: string;
  /** Two lines of plain description. */
  body: string;
  /** What the card says in place of the description while none of its apps is available. */
  waiting?: string;
  /** The address of the card's art. */
  image: string;
  /** The catalog identifiers of the apps it is made in. */
  appIds: readonly string[];
  /** Whether the card is drawn at feature size. */
  feature: boolean;
  /** The classes that place the card in the bento. */
  placement: string;
}

const list = new Intl.ListFormat('en-US', { type: 'conjunction' });

/** The size of a feature card: two columns by two rows wherever the grid has two columns or more. */
const FEATURE = 'sm:col-span-2 sm:row-span-2';

/**
 * The use cases, in reading order.
 *
 * @returns The cards of the gallery.
 */
function useCases(): UseCase[] {
  return [
    {
      title: 'Product shots and visuals',
      promise: 'Make it look the way it does in your head.',
      body: 'Studio lighting, clean materials, and final stills for a launch, a pitch, or a portfolio.',
      image: useCaseImage('product'),
      appIds: ['blender'],
      feature: true,
      placement: FEATURE,
    },
    {
      title: 'Characters and animation',
      promise: 'Give your characters room to move.',
      body: 'Sculpt, rig, and animate. The heavy lifting happens somewhere other than your desk.',
      image: useCaseImage('character'),
      appIds: ['blender'],
      feature: false,
      placement: '',
    },
    {
      title: 'Architecture and interiors',
      promise: 'Show the space before it exists.',
      body: 'Light a room at dusk, swap the materials, and render the view a client needs to see.',
      image: useCaseImage('archviz'),
      appIds: ['blender'],
      feature: false,
      placement: '',
    },
    {
      title: 'Short films and motion',
      promise: 'Finish the shot you keep putting off.',
      body: 'Build the scene, set the camera, and render it on the cloud machine, not on your laptop.',
      image: useCaseImage('film'),
      appIds: ['blender'],
      feature: false,
      placement: '',
    },
    {
      title: 'Game worlds',
      promise: 'Build the world you want to play in.',
      body: 'Lay out a level, light it, and walk through it, in an editor that opens in a browser tab.',
      waiting: 'Game engines are not here yet. This card will say so when they arrive.',
      image: appImage('unreal'),
      appIds: ['unreal', 'godot'],
      feature: false,
      // Under the card before it, so that the last feature card fills the two columns beside them.
      placement: 'lg:col-start-1 lg:row-start-4',
    },
    {
      title: 'Learning and personal projects',
      promise: 'Follow a tutorial. Then make it yours.',
      body: `Learn without buying a computer for it first. New accounts start with ${catalog.signup_credits} free credits.`,
      image: appImage('blender'),
      appIds: ['blender'],
      feature: true,
      placement: cx(FEATURE, 'lg:col-start-2 lg:row-start-3'),
    },
  ];
}

/**
 * Renders the gallery section.
 *
 * @returns The section.
 */
export function Gallery() {
  return (
    <section id="make" className="section" aria-labelledby="make-title">
      <div className="shell">
        <SectionHeading
          id="make-title"
          eyebrow="For creative minds"
          title="What will you make?"
          lede="Whatever it is, it starts the same way: in a browser tab, on a machine built for the job."
        />
        <ul className="mt-12 grid auto-rows-[23rem] grid-cols-1 gap-5 sm:auto-rows-[22rem] sm:grid-cols-2 lg:auto-rows-[21rem] lg:grid-cols-3">
          {useCases().map((useCase) => (
            <li key={useCase.title} className={cx('flex', useCase.placement)}>
              <UseCard useCase={useCase} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** Props of {@link UseCard}. */
interface UseCardProps {
  /** The use case the card presents. */
  useCase: UseCase;
}

/**
 * Renders one use case as a card, tinted by the app it is made in.
 *
 * @param props The component's props.
 * @returns The card.
 */
function UseCard({ useCase }: UseCardProps) {
  const apps = useCase.appIds.flatMap((id): CatalogApp[] => {
    const app = findApp(id);
    return app === undefined ? [] : [app];
  });
  const ready = apps.find(isAvailable);
  const accent = (ready ?? apps[0])?.accent;
  return (
    <article
      className={cx(
        'art use-card w-full',
        useCase.feature && 'use-card-feature',
        ready === undefined && 'use-card-soon',
      )}
      style={{ '--accent': accent }}
    >
      <ArtImage src={useCase.image} width={1200} height={800} />
      {ready === undefined ? (
        apps.length > 0 && (
          <p className="pill absolute top-4 left-4 z-10 max-w-[calc(100%-2rem)] text-muted">
            <span className="truncate">Coming soon with {list.format(apps.map((app) => app.name))}</span>
          </p>
        )
      ) : (
        <span className="use-arrow absolute top-4 right-4 z-10 grid size-9 place-items-center rounded-full" aria-hidden="true">
          <ArrowUpRight className="size-4" />
        </span>
      )}
      <div className="use-words relative z-10 mt-auto w-full px-6 pb-6 sm:px-7 sm:pb-7">
        <h3 className={cx('font-semibold tracking-tight', useCase.feature ? 'text-xl sm:text-[1.9rem]' : 'text-xl')}>
          {ready === undefined ? (
            useCase.title
          ) : (
            // Stretched over the card, so the whole of it is the way in.
            <a href="#signup" className="after:absolute after:inset-0 after:content-['']">
              {useCase.title}
              <span className="sr-only">: start in {ready.name}</span>
            </a>
          )}
        </h3>
        <p className="mt-2 font-medium text-[color-mix(in_oklab,var(--accent)_45%,white)]">{useCase.promise}</p>
        <p className="mt-1.5 max-w-lg text-sm leading-relaxed text-muted">
          {ready === undefined ? (useCase.waiting ?? useCase.body) : useCase.body}
        </p>
        {ready !== undefined && useCase.feature ? (
          <p className="mt-4 hidden items-center gap-1.5 text-sm font-semibold text-ember-300 sm:flex" aria-hidden="true">
            Start in {ready.name}
            <ArrowRight className="size-4" />
          </p>
        ) : null}
      </div>
    </article>
  );
}
