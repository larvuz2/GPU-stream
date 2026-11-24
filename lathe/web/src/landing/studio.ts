/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What the landing page says about the studio, worked out from the catalog: the engines of a
 * discipline, whether a person can work in one of them today, what an engine's status is called,
 * and the address a new project opens at.
 *
 * Nothing here repeats a value of the catalog. A discipline is live while one of its engines is
 * available to anyone; every other discipline says its engines are on the way, whatever its own
 * list holds. Every way into the product from the page is one address, the app's
 * (`/app/?discipline=<id>&format=<format>&prompt=<text>`): the app opens a new project prefilled
 * from those parameters and asks a signed-out visitor to sign up first, so the page needs no
 * account state to send someone on.
 * @module
 */
import {
  catalog,
  findApp,
  findDiscipline,
  isAvailable,
  isOwnLicense,
  ownLicenseLabel,
  type CatalogApp,
  type Category,
  type Discipline,
} from '../lib/catalog';
import { DASHBOARD_PATH } from '../lib/supabase';

/**
 * The fragment every "start creating" link on the page points at: the hero's prompt box, which
 * takes the focus.
 */
export const CREATE_HASH = '#create';

/** Joins names into prose: "FilmCraft and Blender", "A, B, and C". */
export const listFormat = new Intl.ListFormat('en-US', { type: 'conjunction' });

/** What a badge calls each engine status. */
const STATUS_LABELS: Readonly<Record<string, string>> = {
  available: 'Live',
  next: 'Coming next',
  team: 'Team',
  soon: 'Soon',
};

/**
 * What a badge calls an engine's status.
 *
 * @param app The catalog app.
 * @returns The label: the license an app of status `byol` runs on, such as "Your Epic account";
 *   an unknown status reads as "Soon", the least it can promise.
 */
export function statusLabel(app: CatalogApp): string {
  return isOwnLicense(app) ? ownLicenseLabel(app) : (STATUS_LABELS[app.status] ?? 'Soon');
}

/**
 * The apps the catalog gives a status, in catalog order.
 *
 * @param status The status, as `catalog.json` writes it.
 * @returns The apps that have it.
 */
export function appsWithStatus(status: string): CatalogApp[] {
  return catalog.apps.filter((app) => app.status === status);
}

/**
 * The engines a discipline works in, its main one first.
 *
 * @param discipline The discipline.
 * @returns The apps its catalog entry names, without any the catalog no longer lists.
 */
export function enginesOf(discipline: Discipline): CatalogApp[] {
  return discipline.engines.flatMap((id): CatalogApp[] => {
    const app = findApp(id);
    return app === undefined ? [] : [app];
  });
}

/**
 * Whether a person can work in a discipline today: one of its engines is available to anyone.
 *
 * @param discipline The discipline.
 * @returns `true` while one of its engines is live.
 */
export function isLive(discipline: Discipline): boolean {
  return enginesOf(discipline).some(isAvailable);
}

/** The disciplines with a live engine, in catalog order. */
export const liveDisciplines: Discipline[] = catalog.disciplines.filter(isLive);

/**
 * The finer categories under a discipline.
 *
 * @param discipline The discipline.
 * @returns Its categories, in catalog order.
 */
export function categoriesOf(discipline: Discipline): Category[] {
  return catalog.categories.filter((category) => category.discipline === discipline.id);
}

/**
 * The discipline an app is first made for, named for a badge such as "for games".
 *
 * @param app The catalog app.
 * @returns The phrase, or `null` for an app whose first discipline the catalog does not list.
 */
export function madeFor(app: CatalogApp): string | null {
  const first = app.disciplines[0];
  const discipline = first === undefined ? undefined : findDiscipline(first);
  return discipline === undefined ? null : `for ${discipline.name.toLowerCase()}`;
}

/** What a new project starts from. */
export interface ProjectStart {
  /** The discipline's identifier. */
  discipline: string;
  /** One of the discipline's formats, when one was chosen. */
  format?: string;
  /** What the person wants to make, in their words. */
  prompt?: string;
}

/**
 * The address that opens a new project in the app, prefilled.
 *
 * @param start What the project starts from. A format or a prompt left empty is left out of the
 *   address, so the app asks for it instead of opening on a blank.
 * @returns The app's address with the project's parameters.
 */
export function newProjectUrl({ discipline, format, prompt }: ProjectStart): string {
  const parameters = new URLSearchParams({ discipline });
  if (format !== undefined && format !== '') {
    parameters.set('format', format);
  }
  const text = prompt?.trim() ?? '';
  if (text !== '') {
    parameters.set('prompt', text);
  }
  return `${DASHBOARD_PATH}?${parameters.toString()}`;
}
