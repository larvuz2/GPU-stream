/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The cards of the development gallery (`/app/cards/`): one moment of a creative project per
 * card, each written as the agent would write it, a `ui` event's data for `show_ui`.
 *
 * Every `components` card here is a tree of `moody/ui.json`'s components and every `html` card a
 * document for the sandboxed frame, so the gallery is also the worked reference for both: a look
 * tuned by sliders over a before and after pair, a lead picked from portraits, a style chosen
 * from boards, a storyboard put in order.
 *
 * The pictures are the site's own artwork (`public/media`), named here for the part they play.
 * @module
 */
import type { UiData, UiMedia } from '../tree';

/** One card of the gallery, with the exchange it answers. */
export interface Example {
  /** Its place in the address (`?only=<id>`) and its section's id. */
  id: string;
  /** What the person asked. */
  asked: string;
  /** What the agent says before the card. */
  says: string;
  /** The card. */
  ui: UiData;
  /** What it was locked in with, for a card shown locked. */
  locked?: unknown;
  /** Whether it is shown as one that cannot be answered now. */
  idle?: boolean;
}

/**
 * Names one of the site's pictures as a card's file.
 *
 * @param name The name the card's components know it by.
 * @param file The file under `public/media`.
 * @param kind What it is.
 * @returns The file as a `ui` event carries it.
 */
function file(name: string, file: string, kind = 'image'): UiMedia {
  return { name, kind, url: `/media/${file}` };
}

/** The sliders of the look tuner, which the locked example shares. */
const LOOK_SPEC = {
  type: 'stack',
  children: [
    {
      type: 'compare',
      before: 'shot',
      after: 'shot',
      adjust: {
        warmth: '$warmth',
        contrast: '$contrast',
        saturation: '$saturation',
        fade: '$fade',
        grain: '$grain',
        vignette: '$vignette',
      },
    },
    { type: 'text', tone: 'muted', text: 'Left of the handle is the frame as generated. Right of it is the grade.' },
    {
      type: 'row',
      children: [
        {
          type: 'stack',
          label: 'Color',
          children: [
            { type: 'slider', id: 'warmth', label: 'Warmth', min: -100, max: 100, value: 18 },
            { type: 'slider', id: 'contrast', label: 'Contrast', min: -100, max: 100, value: 12 },
            { type: 'slider', id: 'saturation', label: 'Saturation', min: -100, max: 100, value: -8 },
          ],
        },
        {
          type: 'stack',
          label: 'Texture',
          children: [
            { type: 'slider', id: 'fade', label: 'Fade', value: 10 },
            { type: 'slider', id: 'grain', label: 'Grain', value: 20 },
            { type: 'slider', id: 'vignette', label: 'Vignette', value: 25 },
          ],
        },
      ],
    },
  ],
};

/** The gallery's cards, in the order of a production. */
export const EXAMPLES: Example[] = [
  {
    id: 'look',
    asked: 'The night market shot feels too clean. Can we find a look for it?',
    says: 'Here is the frame with a grade you can push around. Drag the handle to compare, move the sliders until it feels right, and lock it in: I will grade the whole scene to match.',
    ui: {
      ui_id: 'ui-look',
      title: 'The look of the night market',
      kind: 'components',
      spec: LOOK_SPEC,
      submit: 'Lock in this look',
      waits: true,
      media: [file('shot', 'discipline-media.webp')],
    },
  },
  {
    id: 'cast',
    asked: 'I like all three sketches. Who should carry the film?',
    says: 'That one is yours to call. Pick the lead, and tell me anything you would change about them before I build their reference sheet.',
    ui: {
      ui_id: 'ui-cast',
      title: 'Cast the lead',
      kind: 'components',
      spec: {
        type: 'stack',
        children: [
          {
            type: 'pick',
            id: 'lead',
            label: 'Who carries the film?',
            options: [
              { value: 'mara', label: 'Mara', image: 'mara', note: 'Night courier. Guarded, quick.' },
              { value: 'iris', label: 'Iris', image: 'iris', note: 'Street musician. Hopeful.' },
              { value: 'theo', label: 'Theo', image: 'theo', note: 'Repairman. Has seen it all.' },
            ],
          },
          {
            type: 'field',
            id: 'note',
            label: 'Anything to change about them?',
            placeholder: 'Older, a scar, a different coat…',
            lines: 2,
          },
        ],
      },
      submit: 'Cast this lead',
      waits: true,
      media: [
        file('mara', 'character-mara.webp'),
        file('iris', 'character-iris.webp'),
        file('theo', 'character-theo.webp'),
      ],
    },
  },
  {
    id: 'style',
    asked: 'What could this film look like?',
    says: 'Three directions, each with its references and palette. Open the one you want; the tab you leave open is your answer.',
    ui: {
      ui_id: 'ui-style',
      title: 'An art style for the film',
      kind: 'components',
      spec: {
        type: 'stack',
        children: [
          {
            type: 'tabs',
            id: 'style',
            children: [
              {
                type: 'tab',
                label: 'Neon noir',
                value: 'neon-noir',
                children: [
                  {
                    type: 'gallery',
                    columns: 2,
                    items: [
                      { src: 'noir_street', caption: 'Wet streets, practical light' },
                      { src: 'noir_towers', caption: 'Towers lost in fog' },
                    ],
                  },
                  {
                    type: 'swatches',
                    label: 'Palette',
                    colors: [
                      { color: '#0d0b1a', label: 'Night' },
                      { color: '#3b2a6b', label: 'Violet haze' },
                      { color: '#c6c0f5', label: 'Neon' },
                      { color: '#e8a04a', label: 'Sodium' },
                      { color: '#f2e6c9', label: 'Skin light' },
                    ],
                  },
                  { type: 'text', tone: 'muted', text: 'High contrast, long lenses, light from signs and windows only.' },
                ],
              },
              {
                type: 'tab',
                label: 'Storybook',
                value: 'storybook',
                children: [
                  {
                    type: 'gallery',
                    columns: 2,
                    items: [
                      { src: 'book_island', caption: 'Small worlds, warm lamps' },
                      { src: 'book_robot', caption: 'Rounded, hand-made shapes' },
                    ],
                  },
                  {
                    type: 'swatches',
                    label: 'Palette',
                    colors: [
                      { color: '#1c1410', label: 'Soot' },
                      { color: '#8a4b2a', label: 'Terracotta' },
                      { color: '#e9a03b', label: 'Lantern' },
                      { color: '#5f8f4e', label: 'Moss' },
                      { color: '#f4ead2', label: 'Paper' },
                    ],
                  },
                  { type: 'text', tone: 'muted', text: 'Miniature sets, soft key light, nothing sharper than a thumb.' },
                ],
              },
              {
                type: 'tab',
                label: 'Painterly',
                value: 'painterly',
                children: [
                  {
                    type: 'gallery',
                    columns: 2,
                    items: [
                      { src: 'paint_studio', caption: 'Brushwork you can see' },
                      { src: 'paint_vista', caption: 'Skies that carry the mood' },
                    ],
                  },
                  {
                    type: 'swatches',
                    label: 'Palette',
                    colors: [
                      { color: '#17131f', label: 'Umber' },
                      { color: '#5a3d7a', label: 'Dusk' },
                      { color: '#d9772f', label: 'Ember' },
                      { color: '#f0c27a', label: 'Glow' },
                      { color: '#b9c4d6', label: 'Mist' },
                    ],
                  },
                  { type: 'text', tone: 'muted', text: 'Loose edges, big shapes, color doing the work of detail.' },
                ],
              },
            ],
          },
          {
            type: 'row',
            children: [
              {
                type: 'select',
                id: 'surface',
                label: 'Surface',
                options: ['Clean digital', '35mm grain', 'Visible brushwork', 'Halftone print'],
                value: '35mm grain',
              },
              {
                type: 'segmented',
                id: 'push',
                label: 'How far to push it',
                options: ['Subtle', 'Balanced', 'Bold'],
                value: 'Balanced',
              },
            ],
          },
        ],
      },
      submit: 'Go with this style',
      waits: true,
      media: [
        file('noir_street', 'discipline-media.webp'),
        file('noir_towers', 'app-unreal.webp'),
        file('book_island', 'app-blender.webp'),
        file('book_robot', 'discipline-animation.webp'),
        file('paint_studio', 'discipline-art.webp'),
        file('paint_vista', 'discipline-games.webp'),
      ],
    },
  },
  {
    id: 'storyboard',
    asked: 'The opening drags. Can I try a different order?',
    says: 'Here are the six frames of the opening as they are cut now. Put them in the order you want to see, and I will recut the animatic to it.',
    ui: {
      ui_id: 'ui-storyboard',
      title: 'The opening, in order',
      kind: 'components',
      spec: {
        type: 'stack',
        children: [
          {
            type: 'reorder',
            id: 'order',
            label: 'Drag a frame by its handle, or use the arrows',
            options: [
              { value: 'towers', label: 'The city, far below', image: 'f_towers', note: 'Wide · 5s' },
              { value: 'market', label: 'The market wakes', image: 'f_market', note: 'Crane down · 6s' },
              { value: 'mara', label: 'Mara, waiting', image: 'f_mara', note: 'Close · 3s' },
              { value: 'workshop', label: 'Theo’s workshop', image: 'f_workshop', note: 'Medium · 4s' },
              { value: 'letter', label: 'The letter', image: 'f_letter', note: 'Insert · 2s' },
              { value: 'vista', label: 'The road out', image: 'f_vista', note: 'Wide · 5s' },
            ],
          },
          { type: 'text', tone: 'muted', text: 'Twenty-five seconds in all, whatever the order.' },
        ],
      },
      submit: 'Lock the order',
      waits: true,
      media: [
        file('f_towers', 'app-unreal.webp'),
        file('f_market', 'discipline-media.webp'),
        file('f_mara', 'character-mara.webp'),
        file('f_workshop', 'character-theo.webp'),
        file('f_letter', 'discipline-writing.webp'),
        file('f_vista', 'discipline-games.webp'),
      ],
    },
  },
  {
    id: 'locked',
    asked: 'Show me the look we settled on for the market.',
    says: 'This is the grade you locked in on Tuesday. It is what every shot of the scene is matched to.',
    ui: {
      ui_id: 'ui-look-locked',
      title: 'The look of the night market',
      kind: 'components',
      spec: LOOK_SPEC,
      submit: 'Lock in this look',
      waits: true,
      media: [file('shot', 'discipline-media.webp')],
    },
    locked: { warmth: 34, contrast: 22, saturation: -18, fade: 16, grain: 38, vignette: 42 },
  },
];
