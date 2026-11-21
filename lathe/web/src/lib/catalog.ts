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

/** An app a session can run. */
export interface CatalogApp {
  /** The identifier the control plane takes, and the stem of the app's art and logo files. */
  id: string;
  /** The app's display name. */
  name: string;
  /** The version offered, or an empty string while none is. */
  version: string;
  /** `available` for an app that can be launched; anything else is announced but not offered. */
  status: string;
  /** One sentence on what the app is for. */
  tagline: string;
  /** The CSS color the app's card is tinted with. */
  accent: string;
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

/** The shape of `catalog.json`. */
export interface Catalog {
  /** The product's name. */
  brand: string;
  /** What one credit is worth, in US dollars. */
  credit_usd: number;
  /** Credits a new account starts with. */
  signup_credits: number;
  /** Every app, offered or announced. */
  apps: CatalogApp[];
  /** Every tier, cheapest first. */
  tiers: Tier[];
  /** Every region, the automatic choice among them. */
  regions: Region[];
  /** Every credit pack, smallest first. */
  credit_packs: CreditPack[];
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
