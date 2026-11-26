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
 * decoration over the pixel grid, and a logo falls back to the app's name in text.
 *
 * Art follows the catalog by name: one image per app identifier and one per discipline identifier.
 * Engine pictures and logos are listed, because only some apps have one, and an `<img>` needs each
 * logo's proportions to reserve its space.
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

/** The still the landing page's video frame shows until the product video plays, 16:9. */
export const VIDEO_POSTER = '/media/video-poster.webp';

/**
 * The product video the landing page's video frame plays, or `null` while there is none.
 *
 * The frame is built around this one value: setting it to the video's address turns the frame's
 * play button from a "coming soon" note into the player, with {@link VIDEO_POSTER} as its poster.
 */
export const PRODUCT_VIDEO: string | null = null;

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
 * A picture the catalog names by its file, such as a card of a shortcut's preview, 3:2.
 *
 * @param file The file's name under the site's media.
 * @returns The address the image is served from.
 */
export function catalogImage(file: string): string {
  return `/media/${encodeURIComponent(file)}`;
}

/**
 * The art of a discipline's card, 3:2.
 *
 * @param disciplineId The catalog identifier of the discipline.
 * @returns The address the image is served from.
 */
export function disciplineImage(disciplineId: string): string {
  return `/media/discipline-${encodeURIComponent(disciplineId)}.webp`;
}

/**
 * The picture of an engine at work, 16:9, by app identifier: the engine's own interface where it
 * is open source, and concept art where the software is someone else's product, whose interface the
 * site does not show.
 */
const ENGINE_ART: Readonly<Record<string, string>> = {
  filmcraft: '/media/engine-filmcraft.webp',
  blender: '/media/engine-blender.webp',
  photocraft: '/media/engine-photocraft.webp',
  unreal: appImage('unreal'),
};

/**
 * The picture of an engine at work.
 *
 * @param appId The catalog identifier of the app.
 * @returns The address the image is served from, or `undefined` for an engine without one.
 */
export function engineImage(appId: string): string | undefined {
  return Object.hasOwn(ENGINE_ART, appId) ? ENGINE_ART[appId] : undefined;
}

/**
 * The portrait of a character in the landing page's illustration of a project library, 1:1.
 *
 * @param name The character's short name, the stem its file is delivered under.
 * @returns The address the image is served from.
 */
export function characterImage(name: string): string {
  return `/media/character-${encodeURIComponent(name)}.webp`;
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
