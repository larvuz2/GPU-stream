/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Where the site's artwork and logos are served from.
 *
 * The files live under `public/` and are delivered apart from this code, so every path is built
 * here and every image that uses one tolerates its absence (`components/Art.tsx`): the art is
 * decoration over a gradient, and a logo falls back to the app's name in text.
 *
 * Art follows the catalog by name, one image per app identifier. Logos are listed, because only
 * some apps have one and an `<img>` needs each file's proportions to reserve its space.
 * @module
 */

/** A logo file and the proportions of its artwork. */
export interface LogoFile {
  /** The address the logo is served from. */
  src: string;
  /** The width of the artwork, in its own units. */
  width: number;
  /** The height of the artwork, in its own units. */
  height: number;
}

/** The official logos delivered under `public/logos`, by app identifier. Each is shown unmodified. */
const APP_LOGOS: Readonly<Record<string, LogoFile>> = {
  blender: { src: '/logos/blender.svg', width: 2048, height: 550 },
  unreal: { src: '/logos/unreal.svg', width: 1002, height: 1092 },
};

/** The hero's art, 16:9. */
export const HERO_ART = '/media/hero.webp';

/** The art beside the agent section's command, 3:2. */
export const AGENT_ART = '/media/claude.webp';

/**
 * The art of an app's card, 3:2.
 *
 * @param appId The catalog identifier of the app.
 * @returns The address the image is served from.
 */
export function appImage(appId: string): string {
  return `/media/app-${encodeURIComponent(appId)}.webp`;
}

/**
 * The official logo of an app.
 *
 * @param appId The catalog identifier of the app.
 * @returns The logo file, or `undefined` for an app that is named in text.
 */
export function appLogo(appId: string): LogoFile | undefined {
  return Object.hasOwn(APP_LOGOS, appId) ? APP_LOGOS[appId] : undefined;
}

/**
 * Whether an app's logo is stacked or square rather than a wide wordmark, and so needs more height
 * to read at a size where a wide one is comfortable.
 *
 * @param appId The catalog identifier of the app.
 * @returns `true` for a stacked or square logo, `false` for a wide one or an app without a logo.
 */
export function hasStackedLogo(appId: string): boolean {
  const logo = appLogo(appId);
  return logo !== undefined && logo.width / logo.height < 2;
}
