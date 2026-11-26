/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The product catalog, the one source of every app, tier, region, price, and the brand name.
 *
 * `catalog.json` sits beside this package and the control plane reads the same file, so nothing
 * here or in a component repeats a value from it: a price shown is computed from the tier's
 * credits and the credit's worth, and the brand is `catalog.brand`. The compiler checks the file
 * against {@link Catalog} at the import, so a change of its shape fails the build instead of
 * rendering a hole.
 * @module
 */
import raw from '../../../catalog.json';

/**
 * The license a person brings for an app of status `byol`, and how they link it.
 *
 * The control plane reads the same entry: where the person asks for the part of the app on this
 * license before it is linked, the agent gives these steps.
 */
export interface AppLicense {
  /** What the license is, as a badge names it, such as "Your Epic account". */
  label: string;
  /** The maker's page on linking it. */
  url: string;
  /** The steps that link it, in order, each a sentence. */
  steps: string[];
}

/** An app a session can run. */
export interface CatalogApp {
  /** The identifier the control plane takes, and the stem of the app's art and logo files. */
  id: string;
  /** The app's display name. */
  name: string;
  /** The version offered, or an empty string while none is. */
  version: string;
  /**
   * `available` for an app anyone can launch, `team` for one only the team's accounts can (an app whose
   * license is the user's own, such as Nuke), `byol` for one anyone can launch whose licensed part
   * comes once they have linked their own license for it ({@link CatalogApp.license}: Unreal
   * Engine's editor), `next` for the one being built now, `soon` for the rest.
   */
  status: string;
  /** One sentence on what the app is for. */
  tagline: string;
  /** The CSS color the app's card is tinted with. */
  accent: string;
  /** The disciplines the app serves, by {@link Discipline} identifier. */
  disciplines: string[];
  /** Where the app comes from: its open-source repository or its maker's page. */
  source: string;
  /** The license a person brings, for an app of status `byol`. */
  license?: AppLicense;
  /** Whether the app starts only on a tier with a GPU (Unreal's editor renders on nothing else). */
  requires_gpu?: boolean;
}

/** What a discipline's opening card says of one of its formats, the project's kind. */
export interface Kind {
  /** What the kind is, in a line. */
  note: string;
  /** Its icon, by name in the catalog's {@link Catalog.icons}. */
  icon: string;
  /** The library's first sections for a project of the kind, where they differ from the discipline's. */
  sections?: string[];
}

/**
 * A top-level creative discipline: what a person makes, independent of the software that makes it.
 *
 * A project belongs to one, and its engines are the apps an agent reaches for there.
 */
export interface Discipline {
  /** The identifier a project carries. */
  id: string;
  /** The display name. */
  name: string;
  /** The kinds of work it covers, shown small under the name and offered when a project starts. */
  formats: string[];
  /** One sentence on what is made there. */
  blurb: string;
  /** The apps it uses, by {@link CatalogApp} identifier, the first the main one. */
  engines: string[];
  /**
   * What a project of the discipline is asked first when it starts without a format: the title of
   * the card that asks its kind. A discipline without one asks nothing.
   */
  opening?: string;
  /** What that card says of each format, by the format's name. */
  kinds?: Record<string, Kind>;
  /** The agent's skill that opens a project of each kind with a card of its own. */
  opening_skill?: string;
  /** The library's first sections for a project of the discipline. */
  sections?: string[];
}

/** One card of what a shortcut will offer: a tool that may come, and what it is for. */
export interface ShortcutPreview {
  /** The tool's name. */
  name: string;
  /** What it is for, in a line. */
  line: string;
  /** Where it stands, in a word: "Soon" for one being prepared, "Exploring" for one still looked into. */
  tag: string;
  /** The card's picture, by its file under the site's media. */
  image: string;
}

/**
 * A shortcut into a new project: a kind of work by its everyday name, which the studio's sidebar
 * lists under Create.
 *
 * One that is `available` names the discipline its project belongs to and, where its name means
 * one, the format; one that names no format leaves that choice to the person. One that is `soon`
 * is announced with nothing behind it yet and starts nothing; what it shows instead is its
 * `preview`, where it has one.
 */
export interface Shortcut {
  /** The identifier, which also picks the icon of a shortcut that has one of its own. */
  id: string;
  /** What the sidebar calls it, such as "Video". */
  label: string;
  /** `available` for one a project starts from today, `soon` for one that is only announced. */
  status: string;
  /** The discipline its project belongs to, by {@link Discipline} identifier. */
  discipline?: string;
  /** The format its project starts with, for a shortcut whose name means one. */
  format?: string;
  /** What to expect of one that is not available yet, as cards. */
  preview?: ShortcutPreview[];
}

/** One of the finer creative categories, each under a {@link Discipline}. */
export interface Category {
  /** The identifier. */
  id: string;
  /** The display name. */
  name: string;
  /** The discipline it belongs to. */
  discipline: string;
  /** What is made there, as a phrase. */
  creations: string;
  /** The apps it uses, by {@link CatalogApp} identifier. */
  engines: string[];
}

/**
 * Something an agent is doing, as the page shows it: the pixel eyes play the expression of the
 * same identifier (`lib/moodyEyes.ts`) beside this label.
 *
 * The control plane reads the same list: a tool's definition and a subagent's card name one of
 * these identifiers.
 */
export interface Activity {
  /** The identifier an event carries, and the name of the eyes' expression. */
  id: string;
  /** What the page calls it, such as "Searching". */
  label: string;
}

/** A size of workstation. */
export interface Tier {
  /** The identifier the control plane takes. */
  id: string;
  /** The tier's display name. */
  name: string;
  /** The GPU model, or `null` for a tier that renders in software. */
  gpu: string | null;
  /** Video memory, in gigabytes. */
  vram_gb: number;
  /** Virtual CPU cores. */
  cpu: number;
  /** System memory, in gigabytes. */
  memory_gb: number;
  /** What a running session costs each minute. */
  credits_per_minute: number;
  /** One line on what the tier suits. */
  blurb: string;
}

/** A place a session can run. */
export interface Region {
  /** The identifier the control plane takes. */
  id: string;
  /** The region's display name. */
  name: string;
}

/** A bundle of credits sold at once. */
export interface CreditPack {
  /** The identifier the checkout takes. */
  id: string;
  /** Credits the pack adds to the balance. */
  credits: number;
  /** The pack's price, in US dollars. */
  usd: number;
}

/** One of the values a setting of kind `choice` offers. */
export interface SettingOption {
  /** The value the control plane keeps. */
  value: string;
  /** What the page calls it. */
  label: string;
}

/**
 * A setting of the person's account that is a plain switch or choice.
 *
 * The control plane reads the same entries: it keeps what a person changed and refuses an id or a
 * value they do not offer, so a new setting is an entry here and the code that reads it.
 */
export interface Setting {
  /** The identifier its value is kept under. */
  id: string;
  /** The tab of Settings it sits on, by the tab's name as shown. */
  tab: string;
  /** What the setting is, as its control is labeled. */
  label: string;
  /** One line on what it changes. */
  help: string;
  /** `toggle` for a switch, on or off, or `choice` for one of {@link Setting.options}. */
  kind: string;
  /** What a `choice` offers. */
  options?: SettingOption[];
  /** The value that applies until the person changes it. */
  default: boolean | string;
  /**
   * For a setting that chooses between engines: the app each value stands for, a toggle's under
   * `on` and `off` and a choice's under its options' values ({@link settingApp}).
   */
  apps?: Record<string, string>;
}

/** The shape of `catalog.json`. */
export interface Catalog {
  /** The product's name. */
  brand: string;
  /** What one credit is worth, in US dollars. */
  credit_usd: number;
  /** Credits a new account starts with. */
  signup_credits: number;
  /** What an agent can be shown doing, each an expression of the pixel eyes. */
  activities: Activity[];
  /** The twelve top-level disciplines, in the order they are shown. */
  disciplines: Discipline[];
  /** The shortcuts into a new project, in the order the sidebar lists them. */
  shortcuts: Shortcut[];
  /** The finer categories, each under a discipline. */
  categories: Category[];
  /** Every app, offered or announced. */
  apps: CatalogApp[];
  /** Every tier, cheapest first. */
  tiers: Tier[];
  /** The settings of a person's account that are a plain switch or choice, in the order they are shown. */
  settings: Setting[];
  /** Every region, the automatic choice among them. */
  regions: Region[];
  /** Every credit pack, smallest first. */
  credit_packs: CreditPack[];
  /**
   * Pixel icons by name, each twelve rows of twelve cells written as `0` and `1`. A discipline's
   * kinds name theirs here, and the control plane puts the rows on the card that asks the kind.
   */
  icons: Record<string, string[]>;
}

/** The catalog. */
export const catalog: Catalog = raw;

/** The product's name. */
export const brand: string = catalog.brand;

/** The region that leaves the placement to the control plane, the launch form's default. */
export const AUTO_REGION = 'auto';

/**
 * Minutes without activity after which a session shuts itself down.
 *
 * The control plane enforces it; the pages only say so, and all of them say it from here.
 */
export const IDLE_SHUTDOWN_MINUTES = 10;

/**
 * Whether an app can be launched today.
 *
 * @param app The catalog app.
 * @returns `true` for an available app, `false` for one that is only announced.
 */
export function isAvailable(app: CatalogApp): boolean {
  return app.status === 'available';
}

/**
 * The app a value of a setting stands for.
 *
 * @param setting The catalog's setting.
 * @param value One of its values.
 * @returns The app's identifier, or `undefined` where the setting chooses between no apps or names
 *   none for the value.
 */
export function settingApp(setting: Setting, value: boolean | string): string | undefined {
  const key = setting.kind === 'toggle' ? (value === true ? 'on' : 'off') : String(value);
  return setting.apps !== undefined && Object.hasOwn(setting.apps, key) ? setting.apps[key] : undefined;
}

/**
 * Whether an app has a part on a license the person brings, which comes once they have linked it.
 *
 * @param app The catalog app.
 * @returns `true` for an app of status `byol`.
 */
export function isOwnLicense(app: CatalogApp): boolean {
  return app.status === 'byol';
}

/**
 * What an app of status `byol` is labeled with: the license the person brings.
 *
 * @param app The catalog app.
 * @returns The license's label, such as "Your Epic account", or a phrase for an app whose entry names none.
 */
export function ownLicenseLabel(app: CatalogApp): string {
  return app.license?.label ?? 'Your own license';
}

/** The apps a session can run today, in catalog order. */
export const liveApps: CatalogApp[] = catalog.apps.filter(isAvailable);

/** The apps announced but not offered yet, in catalog order. */
export const upcomingApps: CatalogApp[] = catalog.apps.filter((app) => !isAvailable(app));

/** The regions a user can name, without the automatic choice. */
export const namedRegions: Region[] = catalog.regions.filter((region) => region.id !== AUTO_REGION);

/** The tier a new account's credits last longest on. */
export const cheapestTier: Tier | undefined = catalog.tiers.reduce<Tier | undefined>(
  (cheapest, tier) => (cheapest === undefined || tier.credits_per_minute < cheapest.credits_per_minute ? tier : cheapest),
  undefined,
);

/**
 * What an hour on a tier costs.
 *
 * @param tier The tier.
 * @returns The price in US dollars.
 */
export function hourlyUsd(tier: Tier): number {
  return tier.credits_per_minute * 60 * catalog.credit_usd;
}

/**
 * How long a balance lasts on a tier.
 *
 * @param credits The balance.
 * @param tier The tier.
 * @returns Whole minutes of session time.
 */
export function minutesFor(credits: number, tier: Tier): number {
  return tier.credits_per_minute > 0 ? Math.floor(credits / tier.credits_per_minute) : 0;
}

/**
 * The share of a pack's credits that come on top of what its price buys at the plain rate.
 *
 * @param pack The credit pack.
 * @returns The bonus as a fraction (`0.1` for ten percent), zero for a pack with none.
 */
export function packBonus(pack: CreditPack): number {
  const plain = pack.usd / catalog.credit_usd;
  return plain > 0 ? Math.max(0, pack.credits / plain - 1) : 0;
}

/**
 * Looks an app up by the identifier a session carries.
 *
 * @param id The app identifier.
 * @returns The app, or `undefined` for one the catalog no longer lists.
 */
export function findApp(id: string): CatalogApp | undefined {
  return catalog.apps.find((app) => app.id === id);
}

/**
 * Whether a tier can run an app: any tier, except a tier without a GPU for an app that needs one.
 *
 * @param tier The tier.
 * @param app The app.
 * @returns `true` where the app can start on the tier.
 */
export function tierFits(tier: Tier, app: CatalogApp): boolean {
  return app.requires_gpu !== true || tier.gpu !== null;
}

/**
 * What the page calls an activity.
 *
 * @param id The activity's identifier, as an event names it.
 * @returns Its catalog label, or `undefined` for one the catalog does not list.
 */
export function activityLabel(id: string): string | undefined {
  return catalog.activities.find((activity) => activity.id === id)?.label;
}

/**
 * Looks a discipline up by the identifier a project carries.
 *
 * @param id The discipline identifier.
 * @returns The discipline, or `undefined` for one the catalog no longer lists.
 */
export function findDiscipline(id: string): Discipline | undefined {
  return catalog.disciplines.find((discipline) => discipline.id === id);
}

/**
 * Whether a project of a discipline is asked its kind when it starts without a format.
 *
 * @param discipline The discipline.
 * @returns `true` for one the catalog gives an opening question and formats to answer it with.
 */
export function asksKind(discipline: Discipline): boolean {
  return discipline.opening !== undefined && discipline.formats.length > 0;
}

/**
 * The library sections a project of a discipline and a kind starts with: the kind's own where it
 * has any (a commercial's products and shots), else the discipline's.
 *
 * @param discipline The discipline.
 * @param format The project's format, empty for one whose kind is not chosen yet.
 * @returns The sections, in order.
 */
export function defaultSections(discipline: Discipline, format: string): string[] {
  const kinds = discipline.kinds ?? {};
  const kind = Object.hasOwn(kinds, format) ? kinds[format] : undefined;
  return kind?.sections ?? discipline.sections ?? [];
}

/**
 * The discipline a shortcut starts a project in.
 *
 * @param shortcut The shortcut.
 * @returns The discipline, or `undefined` for a shortcut that starts nothing: one that is not
 *   `available`, or whose discipline the catalog does not list.
 */
export function shortcutDiscipline(shortcut: Shortcut): Discipline | undefined {
  return shortcut.status === 'available' && shortcut.discipline !== undefined
    ? findDiscipline(shortcut.discipline)
    : undefined;
}

/**
 * Looks a tier up by the identifier a session carries.
 *
 * @param id The tier identifier.
 * @returns The tier, or `undefined` for one the catalog no longer lists.
 */
export function findTier(id: string): Tier | undefined {
  return catalog.tiers.find((tier) => tier.id === id);
}

/**
 * Looks a region up by the identifier a session carries.
 *
 * @param id The region identifier.
 * @returns The region, or `undefined` for one the catalog no longer lists.
 */
export function findRegion(id: string): Region | undefined {
  return catalog.regions.find((region) => region.id === id);
}

/**
 * A tier's hardware in a few words, such as `NVIDIA T4 · 16 GB VRAM`.
 *
 * @param tier The tier.
 * @returns The GPU and its memory, or a phrase for a tier without one.
 */
export function gpuLabel(tier: Tier): string {
  return tier.gpu === null ? 'Software rendering' : `NVIDIA ${tier.gpu} · ${tier.vram_gb} GB VRAM`;
}
