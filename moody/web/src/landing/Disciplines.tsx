/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's disciplines: a card for each of the catalog's disciplines, then the finer
 * categories listed under the discipline each belongs to.
 *
 * Every card leads with the discipline's pixel icon (`components/DisciplineIcon.tsx`), set on the
 * edge of its picture, which rests in grayscale and blooms to color under the pointer. The first
 * discipline is the catalog's lead and is featured: four cells of the grid, with its blurb, its
 * formats as labels, and a call to action. Every card is one link that starts a project in its
 * discipline and names its formats and its engines with each engine's status; a live engine
 * carries the green LED. A discipline with no engine anyone can use yet says its engines are
 * coming, and still starts a project, which the agent can plan before an engine arrives.
 *
 * The grid has two columns, then four on a wide screen, where the featured card takes a square of
 * four cells. Where the cards leave a single cell of the last row empty, a card that sends the
 * undecided to the prompt box fills it; where they fill every row, it is not drawn.
 * @module
 */
import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { ArtImage } from '../components/Art';
import { DisciplineIcon } from '../components/DisciplineIcon';
import { FormatLine } from '../components/FormatLine';
import { MoodyFace } from '../components/Moody';
import { catalog, isAvailable, type Discipline } from '../lib/catalog';
import { cx } from '../lib/cx';
import { disciplineImage } from '../lib/media';
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
  // The featured card takes a row of two columns, or a square of four cells in four.
  const fillsTwo = (count + 1) % 2 === 1;
  const fillsFour = (count + 3) % 4 === 3;
  return (
    <section id="disciplines" className="section" aria-labelledby="disciplines-title">
      <div className="shell">
        <SectionHeading
          id="disciplines-title"
          eyebrow={`${count} disciplines`}
          title="Start from what you want to make"
          lede={`Each discipline comes with the engines its work needs.${
            liveDisciplines.length === 0 ? '' : ` ${live} open in live engines today.`
          }`}
        />
        <ul className="mt-12 grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {catalog.disciplines.map((discipline, index) => (
            <li key={discipline.id} className={cx('flex', index === 0 && 'sm:col-span-2 lg:row-span-2')}>
              <DisciplineCard discipline={discipline} featured={index === 0} />
            </li>
          ))}
          <li className={cx('flex', !fillsTwo && 'sm:hidden', fillsFour ? 'lg:flex' : 'lg:hidden')}>
            <a href={CREATE_HASH} className="tile w-full justify-between gap-6 border-dashed p-5">
              <span className="tile-icon">
                <MoodyFace className="h-12" idle />
              </span>
              <span>
                <span className="block text-xl font-semibold tracking-tight">Not sure where it fits?</span>
                <span className="lede mt-1.5 block text-sm">
                  Describe it in your own words, and the agent works out the discipline with you.
                </span>
                <span className="mt-4 flex items-center gap-1.5 text-sm font-semibold">
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
      className={cx('tile bloom group w-full', featured && 'tile-featured')}
    >
      <div className={cx('art art-scrim', featured ? 'aspect-[16/10] lg:aspect-auto lg:flex-1' : 'aspect-[5/2] sm:aspect-[16/9]')}>
        <ArtImage src={disciplineImage(discipline.id)} width={1200} height={800} />
        <span className="pill absolute top-3 left-3 z-10">
          {live ? (
            <>
              <span className="dot dot-live" aria-hidden="true" />
              Live
            </>
          ) : (
            <span className="text-muted">Engines soon</span>
          )}
        </span>
        <span className="tile-arrow absolute top-3 right-3 z-10" aria-hidden="true">
          <ArrowUpRight className="size-4" />
        </span>
      </div>
      <div className={cx('relative z-10 flex flex-col', featured ? 'p-6 sm:p-7' : 'p-4')}>
        <span className={cx('tile-icon', featured ? '-mt-16 size-[4.5rem]' : '-mt-11')}>
          <DisciplineIcon id={discipline.id} className={featured ? 'size-12' : 'size-9'} />
        </span>
        <h3 className="mt-3.5">
          <span className={cx('font-semibold tracking-tight', featured ? 'text-4xl' : 'text-xl')}>{discipline.name}</span>
          <span className="sr-only">: start a project</span>
        </h3>
        {featured ? (
          <>
            <p className="lede mt-3 max-w-xl text-[0.9375rem]">{discipline.blurb}</p>
            <ul className="mt-4 flex flex-wrap gap-1.5" aria-label="Formats">
              {discipline.formats.map((format) => (
                <li key={format} className="pill mono border-line text-fg">
                  {format}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="mt-1 text-xs text-faint">
            <FormatLine formats={discipline.formats} />
          </p>
        )}
        <ul className="mt-4 flex flex-wrap gap-1.5" aria-label="Engines">
          {engines.map((app) => (
            <li key={app.id} className={cx('engine-tag', isAvailable(app) && 'engine-tag-live')}>
              {isAvailable(app) ? <span className="dot" aria-hidden="true" /> : null}
              {app.name}
              {isAvailable(app) ? null : <span className="engine-tag-status">{statusLabel(app)}</span>}
            </li>
          ))}
        </ul>
        {featured ? (
          <p className="mt-6 flex items-center gap-1.5 text-sm font-semibold" aria-hidden="true">
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
      <div className="flex flex-col gap-2 border-t border-line pt-8 sm:flex-row sm:items-end sm:justify-between">
        <h3 className="text-2xl font-semibold tracking-tight sm:text-3xl">Explore every kind of creation</h3>
        <p className="eyebrow">
          {catalog.categories.length} categories · {catalog.disciplines.length} disciplines
        </p>
      </div>
      <div className="mt-8 columns-2 gap-x-6 sm:gap-x-8 lg:columns-4">
        {catalog.disciplines.map((discipline) => {
          const categories = categoriesOf(discipline);
          if (categories.length === 0) {
            return null;
          }
          return (
            <section key={discipline.id} className="mb-7 break-inside-avoid" aria-labelledby={`category-${discipline.id}`}>
              <h4 id={`category-${discipline.id}`} className="eyebrow text-faint">
                <DisciplineIcon id={discipline.id} className="size-3 text-fg" />
                {discipline.name}
              </h4>
              <ul className="mt-2.5 grid gap-1">
                {categories.map((category) => (
                  <li key={category.id}>
                    <a
                      href={newProjectUrl({ discipline: discipline.id })}
                      className="-mx-2 block rounded-md px-2 py-1.5 transition-colors hover:bg-ink-700"
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
