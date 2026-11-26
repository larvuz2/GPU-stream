/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Trying a card in the gallery: a `show_ui` call given in the address is shown as its card.
 *
 * `/app/cards/#card=<the call's JSON, URL-encoded>` draws the card that call would make, which
 * is how a card written into a skill is run before it is written down (`moody/skills/README.md`):
 * the examples of `moody/skills/cards` were each opened this way. The call is the tool's input as
 * the agent writes it: `title`, `components` or `html`, `submit`, `instant`, `waits`, `height`,
 * `media`.
 *
 * The gallery has no library and no engine, so a file named by a tag or an engine's path is
 * stood in for: by the site's picture of that name where there is one, else by a picture, a
 * sound, or a model of the gallery's, by what the path's ending says it is. An item may also
 * give a `url` of its own.
 * @module
 */
import { isBoolean, isNumber, isRecord, isString } from '../../../lib/narrow';
import type { UiMedia } from '../tree';
import type { Example } from './examples';

/** The site's pictures that stand in for a file by its name. */
const NAMED: Readonly<Record<string, string>> = {
  mara: 'character-mara.webp',
  iris: 'character-iris.webp',
  theo: 'character-theo.webp',
};

/** The site's pictures that stand in for any other picture, in turn. */
const PICTURES = [
  'discipline-media.webp',
  'app-unreal.webp',
  'app-blender.webp',
  'discipline-animation.webp',
  'discipline-art.webp',
  'discipline-games.webp',
];

/** The gallery's sounds that stand in for any sound, in turn, so that takes to compare differ. */
const SOUNDS = ['card-sfx-bell.m4a', 'card-sfx-gong.m4a', 'card-sfx-knock.m4a', 'card-cue-market.m4a'];

/** What stands in for a file that is not a picture, by the ending of its path. */
const BY_ENDING: readonly (readonly [RegExp, string, string])[] = [
  [/\.glb$/i, 'model', 'card-robot.glb'],
  [/\.(m4a|mp3|wav|ogg|flac|aac|opus)$/i, 'audio', ''],
  [/\.(mp4|webm|m4v)$/i, 'video', 'preview-cut.mp4'],
];

/**
 * Stands in for the files a call names.
 *
 * @param media The call's `media`.
 * @returns Each file under the name the card knows it by.
 */
function standIns(media: unknown): UiMedia[] {
  if (!Array.isArray(media)) {
    return [];
  }
  let pictures = 0;
  let sounds = 0;
  return media.filter(isRecord).map((item): UiMedia => {
    const tag = isString(item.tag) ? item.tag.replace(/^@/, '').toLowerCase() : null;
    const path = isString(item.path) ? item.path : '';
    const stem = path.split('/').at(-1)?.replace(/\.[^.]*$/, '') ?? '';
    const name = isString(item.name) ? item.name : (tag ?? stem.toLowerCase().replace(/[^a-z0-9_-]+/g, '-'));
    if (isString(item.url)) {
      return { name, kind: isString(item.kind) ? item.kind : 'image', url: item.url };
    }
    const other = BY_ENDING.find(([ending]) => ending.test(path));
    if (other?.[1] === 'audio') {
      sounds += 1;
      return { name, kind: 'audio', url: `/media/${SOUNDS[(sounds - 1) % SOUNDS.length] ?? ''}` };
    }
    if (other !== undefined) {
      return { name, kind: other[1], url: `/media/${other[2]}` };
    }
    const named = NAMED[name] ?? (tag === null ? undefined : NAMED[tag]);
    const picture = named ?? PICTURES[pictures % PICTURES.length] ?? '';
    pictures += named === undefined ? 1 : 0;
    return { name, kind: 'image', url: `/media/${picture}` };
  });
}

/**
 * Reads the card the address asks to try.
 *
 * @returns The card as an example of the gallery, or `null` where the address names none or it is not a call.
 */
export function cardFromAddress(): Example | null {
  const given = new URLSearchParams(window.location.hash.slice(1)).get('card');
  if (given === null) {
    return null;
  }
  let call: unknown;
  try {
    call = JSON.parse(given);
  } catch {
    return null;
  }
  if (!isRecord(call) || !isString(call.title)) {
    return null;
  }
  const html = isString(call.html) ? call.html : undefined;
  return {
    id: 'try',
    asked: 'Show me this card.',
    says: 'Here it is, as the conversation would show it.',
    ui: {
      ui_id: 'ui-try',
      title: call.title,
      kind: html === undefined ? 'components' : 'html',
      spec: html === undefined ? call.components : undefined,
      html,
      height: isNumber(call.height) ? call.height : undefined,
      submit: isString(call.submit) ? call.submit : null,
      waits: isBoolean(call.waits) ? call.waits : false,
      instant: call.instant === true,
      media: standIns(call.media),
    },
  };
}
