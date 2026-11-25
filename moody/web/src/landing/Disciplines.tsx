/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's disciplines: a card for each of the catalog's disciplines, then the finer
 * categories listed under the discipline each belongs to.
 *
 * The first discipline is the catalog's lead and is featured: twice the size, with its blurb and a
 * call to action. Every card is one link that starts a project in its discipline, tinted by its
 * main engine's accent, and names its formats and its engines with each engine's status. A
 * discipline with no engine anyone can use yet says its engines are coming, and still starts a
 * project, which the agent can plan before an engine arrives.
 *
 * The grid has two columns, then three on a wide screen, where the featured card takes a square of
 * four cells. Where the cards leave a single cell of the last row empty, a card that sends the
 * undecided to the prompt box fills it; where they fill every row, it is not drawn.
 * @module
 */
import { ArrowRight, ArrowUpRight, MessageSquareText } from 'lucide-react';
import { ArtImage } from '../components/Art';
import { catalog, isAvailable, type Discipline } from '../lib/catalog';
import { cx } from '../lib/cx';
import { disciplineImage } from '../lib/media';
import { DisciplineIcon } from './DisciplineIcon';
import { SectionHeading } from './SectionHeading';
import {
  categoriesOf,
  CREATE_HASH,
  enginesOf,
  isLive,
  listFormat,
  liveDisciplines,
  newProjectUrl,
  statusLabel,
} from './studio';

/**
 * Renders the disciplines section.
 *
 * @returns The section.
 */
export function Disciplines() {
  const count = catalog.disciplines.length;
  const live = listFormat.format(liveDisciplines.map((discipline) => discipline.name));
  // The featured card takes a row of two columns, or a square of four cells in three.
  const fillsTwo = (count - 1) % 2 === 1;
  const fillsThree = (count + 3) % 3 === 2;
  return (
    <section id="disciplines" className="section" aria-labelledby="disciplines-title">
      <div className="shell">
        <SectionHeading
          id="disciplines-title"
          eyebrow="Disciplines"
          title="Start from what you want to make"
          lede={`${count} disciplines, each with the engines its work needs.${
            liveDisciplines.length === 0 ? '' : ` ${live} open in live engines today.`
          }`}
        />
        <ul className="mt-12 grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {catalog.disciplines.map((discipline, index) => (
            <li key={discipline.id} className={cx('flex', index === 0 && 'sm:col-span-2 lg:row-span-2')}>
              <DisciplineCard discipline={discipline} featured={index === 0} />
            </li>
          ))}
          <li className={cx('flex', !fillsTwo && 'sm:hidden', fillsThree ? 'lg:flex' : 'lg:hidden')}>
            <a href={CREATE_HASH} className="glass glass-hover flex w-full flex-col justify-between gap-6 p-6">
              <span className="icon-tile">
                <MessageSquareText className="size-5" aria-hidden="true" />
              </span>
              <span>
                <span className="block text-lg font-semibold tracking-tight">Not sure where it fits?</span>
                <span className="lede mt-1.5 block text-sm">
                  Describe it in your own words, and the agent works out the discipline with you.
                </span>
                <span className="mt-4 flex items-center gap-1.5 text-sm font-semibold text-ember-300">
                  Describe it
                  <ArrowRight className="size-4" aria-hidden="true" />
                </span>
              </span>
            </a>
          </li>
        </ul>
        <Categories />
      </div>
    </section>
  );
}

/** Props of {@link DisciplineCard}. */
interface DisciplineCardProps {
  /** The discipline the card presents. */
  discipline: Discipline;
  /** Whether the card is the featured one, drawn larger with its blurb and a call to action. */
  featured: boolean;
}

/**
 * Renders one discipline as a card that starts a project in it.
 *
 * @param props The component's props.
 * @returns The card.
 */
function DisciplineCard({ discipline, featured }: DisciplineCardProps) {
  const engines = enginesOf(discipline);
  const live = isLive(discipline);
  return (
    <a
      href={newProjectUrl({ discipline: discipline.id })}
      className={cx('discipline-card group w-full', featured && 'discipline-card-featured', !live && 'discipline-card-soon')}
      style={{ '--accent': engines[0]?.accent }}
    >
      <div className={cx('art art-scrim', featured ? 'aspect-[16/10] lg:aspect-auto lg:flex-1' : 'aspect-[5/2] sm:aspect-[16/9]')}>
        <ArtImage src={disciplineImage(discipline.id)} width={1200} height={800} />
        <span className="pill absolute top-3.5 left-3.5 z-10">
          {live ? (
            <>
              <span className="dot dot-live" aria-hidden="true" />
              Live
            </>
          ) : (
            <span className="text-muted">Engines soon</span>
          )}
        </span>
        <span className="discipline-arrow absolute top-3.5 right-3.5 z-10" aria-hidden="true">
          <ArrowUpRight className="size-4" />
        </span>
      </div>
      <div className={cx('flex flex-col', featured ? 'p-6 sm:p-7' : 'p-5')}>
        <h3 className="flex items-center gap-2.5">
          <DisciplineIcon
            discipline={discipline.id}
            className={cx('flex-none text-[color-mix(in_oklab,var(--accent)_55%,white)]', featured ? 'size-6' : 'size-5')}
          />
          <span className={cx('font-semibold tracking-tight', featured ? 'text-3xl' : 'text-xl')}>{discipline.name}</span>
          <span className="sr-only">: start a project</span>
        </h3>
        <p className={cx('mt-1.5 text-faint', featured ? 'text-sm' : 'text-xs')}>{discipline.formats.join(' · ')}</p>
        {featured ? <p className="lede mt-3 max-w-xl text-[0.9375rem]">{discipline.blurb}</p> : null}
        <ul className="mt-4 flex flex-wrap gap-1.5" aria-label="Engines">
          {engines.map((app) => (
            <li
              key={app.id}
              className={cx('engine-tag', isAvailable(app) && 'engine-tag-live')}
              style={{ '--accent': app.accent }}
            >
              {app.name}
              {isAvailable(app) ? null : <span className="engine-tag-status">{statusLabel(app)}</span>}
            </li>
          ))}
        </ul>
        {featured ? (
          <p className="mt-6 flex items-center gap-1.5 text-sm font-semibold text-ember-300" aria-hidden="true">
            Start a {discipline.name.toLowerCase()} project
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
          </p>
        ) : null}
      </div>
    </a>
  );
}

/**
 * Renders the finer categories, grouped under their disciplines, each a way into a project in its
 * discipline.
 *
 * @returns The list.
 */
function Categories() {
  return (
    <div className="mt-20">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <h3 className="text-2xl font-semibold tracking-tight sm:text-3xl">Explore every kind of creation</h3>
        <p className="text-sm text-muted">
          {catalog.categories.length} categories across {catalog.disciplines.length} disciplines
        </p>
      </div>
      <div className="mt-8 columns-2 gap-x-6 sm:gap-x-8 lg:columns-4">
        {catalog.disciplines.map((discipline) => {
          const categories = categoriesOf(discipline);
          if (categories.length === 0) {
            return null;
          }
          return (
            <section
              key={discipline.id}
              className="mb-7 break-inside-avoid"
              aria-labelledby={`category-${discipline.id}`}
            >
              <h4
                id={`category-${discipline.id}`}
                className="flex items-center gap-2 text-xs font-semibold tracking-[0.14em] text-faint uppercase"
              >
                <DisciplineIcon discipline={discipline.id} className="size-3.5" />
                {discipline.name}
              </h4>
              <ul className="mt-2.5 grid gap-1">
                {categories.map((category) => (
                  <li key={category.id}>
                    <a
                      href={newProjectUrl({ discipline: discipline.id })}
                      className="block rounded-lg px-2 py-1.5 -mx-2 transition-colors hover:bg-white/5"
                    >
                      <span className="block text-[0.9375rem] font-medium">{category.name}</span>
                      <span className="hidden text-xs leading-relaxed text-muted sm:block">{category.creations}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}
