/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The pixel icons of the gallery's cards, each as an agent would write one into a tile: twelve
 * rows of twelve cells, `1` for a cell that is drawn.
 *
 * The seven that stand for a kind of video are the catalog's own (`icons` in `catalog.json`),
 * which the control plane puts on the card that asks the kind: they are read from there, so there
 * is one drawing of each and the gallery shows the one a project opens with. The others were
 * drawn for the gallery and for the demo's openings, cell by cell, in the grid language of the
 * site's own icons (`components/DisciplineIcon.tsx`); the sound wave is the site's Music icon.
 * @module
 */
import { catalog } from '../../../lib/catalog';

/**
 * Reads one of the catalog's icons.
 *
 * @param name The icon's name in the catalog.
 * @returns Its rows, or none for a name the catalog no longer has, which leaves a tile its words.
 */
function registered(name: string): string[] {
  return catalog.icons[name] ?? [];
}

/** A clapperboard: Film & TV. */
export const CLAPPER = registered('film');

/** A heart in a message: Social Media. */
export const HEART = registered('social');

/** A phone held upright, playing: Vertical Shows. */
export const PHONE = registered('vertical');

/** A megaphone: Commercials. */
export const MEGAPHONE = registered('commercial');

/** Two joined notes: Music Videos. */
export const NOTES = registered('music-video');

/** An open book: Education. */
export const BOOK = registered('education');

/** Three dots: Other. */
export const DOTS = registered('other');

/** A written page: a script. */
export const PAGE = [
  '001111110000',
  '001000011000',
  '001000010100',
  '001000011110',
  '001000000010',
  '001011110010',
  '001000000010',
  '001011110010',
  '001000000010',
  '001011100010',
  '001000000010',
  '001111111110',
];

/** A light bulb: an idea. */
export const BULB = [
  '000011110000',
  '000100001000',
  '001000000100',
  '001000000100',
  '001000000100',
  '000100001000',
  '000010010000',
  '000011110000',
  '000010010000',
  '000011110000',
  '000001100000',
  '000000000000',
];

/** A four-pointed spark: a blank page, begun for you. */
export const SPARK = [
  '000001100000',
  '000001100000',
  '000011110000',
  '000011110000',
  '011111111110',
  '111111111111',
  '011111111110',
  '000011110000',
  '000011110000',
  '000001100000',
  '000001100000',
  '000000000000',
];

/** An arrow up into a tray: a file to give. */
export const TRAY = [
  '000001100000',
  '000011110000',
  '000111111000',
  '001101101100',
  '000001100000',
  '000001100000',
  '000001100000',
  '000000000000',
  '110000000011',
  '110000000011',
  '111111111111',
  '111111111111',
];

/** A sound wave: a track to make. */
export const WAVE = [
  '000000000000',
  '000010000000',
  '000010001000',
  '001010001000',
  '001010101010',
  '101010101010',
  '101010101010',
  '001010101010',
  '001010001000',
  '000010001000',
  '000010000000',
  '000000000000',
];

/** A map pin: a site. */
export const PIN = [
  '000111111000',
  '001111111100',
  '011100001110',
  '011000000110',
  '011000000110',
  '011100001110',
  '001111111100',
  '000111111000',
  '000011110000',
  '000011110000',
  '000001100000',
  '000001100000',
];

/** A house with a plus beside it: a building to add to. */
export const EXTEND = [
  '000011000000',
  '000111100000',
  '001100110000',
  '011000011000',
  '111111110000',
  '010000100110',
  '010000100110',
  '010000111111',
  '010000111111',
  '010000100110',
  '011111100110',
  '000000000000',
];

/** A framed picture: photographs of a place. */
export const PHOTO = [
  '000000000000',
  '111111111111',
  '100000000001',
  '100000001101',
  '100000001101',
  '100010000001',
  '100111000101',
  '101111101111',
  '111111111111',
  '100000000001',
  '111111111111',
  '000000000000',
];

/** A ruler: measurements. */
export const RULER = [
  '000000000000',
  '000000000000',
  '000000000000',
  '111111111111',
  '100100100101',
  '100100100101',
  '100000100001',
  '100000000001',
  '111111111111',
  '000000000000',
  '000000000000',
  '000000000000',
];

/** Stacked layers: something printed layer by layer. */
export const LAYERS = [
  '000001100000',
  '000111111000',
  '011111111110',
  '000111111000',
  '000001100000',
  '011000000110',
  '000110011000',
  '000001100000',
  '011000000110',
  '000110011000',
  '000001100000',
  '000000000000',
];

/** A sheet with shapes cut from it: something cut from flat material. */
export const SHEET = [
  '111111111111',
  '100000000001',
  '101111000001',
  '101001000001',
  '101001001101',
  '101111010011',
  '100000010011',
  '100000001101',
  '100000000001',
  '101010101011',
  '100000000001',
  '111111111111',
];

/** A hammer: something built in a workshop. */
export const HAMMER = [
  '000000000000',
  '011111111000',
  '011111111100',
  '011111111100',
  '011100111000',
  '000000111000',
  '000000111000',
  '000000111000',
  '000000111000',
  '000000111000',
  '000000111000',
  '000000000000',
];
