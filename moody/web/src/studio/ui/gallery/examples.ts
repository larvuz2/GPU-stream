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
 * from boards, a storyboard put in order, a poster taken apart into its layers, a shot list with
 * its budget, two cues to choose between, and three documents of the agent's own
 * (`documents.ts`): an equalizer, a simulation, and the frame's self-test. The first cards are
 * how a project opens: the kind of video, chosen from squares with pixel icons (`icons.ts`) in
 * one press, where a film's story comes from, and the track of a music video, given as a file.
 * The last cards are the states a card can be in besides open: changed, with the way back to how
 * it opened in view, locked in, unable to be answered for now (a card with a button, and one
 * that locks on its choice), and asking for a file on a page that cannot take one.
 *
 * The photographs are the site's own artwork (`public/media`), named here for the part they play.
 * The rest was made for the gallery, computed from nothing but code (`public/media/card-*`):
 *
 * - The poster's six layers (`card-layer-*.webp`, 800 by 1000) are drawn with numpy and Pillow:
 *   gradients, a seeded scatter of stars, windows, and lanterns, a skyline of boxes, a band of
 *   blurred noise for the fog, and a title set in a 5 by 7 pixel alphabet written for it. No
 *   picture, font, or model went in.
 * - The two cues (`card-cue-*.m4a`, eight seconds, mono) are synthesized with numpy, a pad of sine
 *   partials and a pulse of plucked notes over a thump, written as WAV and encoded with
 *   `ffmpeg -c:a aac -b:a 96k -movflags +faststart`.
 * - The three takes of the lantern's chime (`card-sfx-*.m4a`, three seconds, mono) are synthesized
 *   the same way: a struck bar's partials for the bell, close partials that beat for the gong, and
 *   a burst of noise through a short resonance for the knock.
 * - The robot (`card-robot.glb`, 4,119 vertices) is built with numpy from boxes, cylinders, and
 *   spheres, placed and grouped into four materials, and written as a binary glTF by hand: a JSON
 *   chunk and one buffer of positions, normals, and indices.
 * @module
 */
import type { CardData, UiMedia } from '../tree';
import { CONTACT_DOCUMENT, EQ_DOCUMENT, ISOLATION_DOCUMENT, LANTERNS_DOCUMENT, RUNAWAY_DOCUMENT } from './documents';
import { BOOK, BULB, CLAPPER, DOTS, HEART, MEGAPHONE, NOTES, PAGE, PHONE, SPARK, TRAY, WAVE } from './icons';

/** One card of the gallery, with the exchange it answers. */
export interface Example {
  /** Its place in the address (`?only=<id>`) and its section's id. */
  id: string;
  /** What the person asked. */
  asked: string;
  /** What the agent says before the card. */
  says: string;
  /** The card. */
  ui: CardData;
  /** What it was locked in with, for a card shown locked. */
  locked?: unknown;
  /** What the person has changed on it so far, by input id, for a card shown in the middle of a decision. */
  changed?: Record<string, unknown>;
  /** Whether it is shown as one that cannot be answered now. */
  idle?: boolean;
  /** Whether it is shown on a page that has no way to take a file from the person. */
  takesNoFiles?: boolean;
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

/** The card that asks where a film's story comes from, which the card that cannot be answered now shares. */
const SOURCE_SPEC = {
  type: 'pick',
  id: 'source',
  columns: 3,
  options: [
    { value: 'script', label: 'I have a script', icon: PAGE, note: 'Paste it or give me the file' },
    { value: 'idea', label: 'I have an idea', icon: BULB, note: 'Tell me in a line or two' },
    { value: 'blank', label: 'Start me off', icon: SPARK, note: 'I pitch three loglines' },
  ],
};

/** The card that asks for a music video's track, which the card on a page that takes no files shares. */
const TRACK_SPEC = {
  type: 'stack',
  children: [
    {
      type: 'pick',
      id: 'have',
      label: 'Do you have the track?',
      columns: 2,
      options: [
        { value: 'yes', label: 'I have it', icon: TRAY, note: 'Give me the file' },
        { value: 'no', label: 'Make one with me', icon: WAVE, note: 'Describe it and I write it' },
      ],
    },
    {
      type: 'upload',
      id: 'track',
      label: 'The track',
      accept: 'audio',
      section: 'Music',
      required: true,
      when: { have: 'yes' },
    },
    {
      type: 'field',
      id: 'brief',
      label: 'What should it sound like?',
      placeholder: 'Slow, a lone piano, rain behind it…',
      lines: 2,
      required: true,
      when: { have: 'no' },
    },
  ],
};

/** The gallery's cards, in the order of a production. */
export const EXAMPLES: Example[] = [
  {
    id: 'kind',
    asked: 'I want to make a video.',
    says: 'Then first: what kind of video is it? Each kind starts differently, so pick the closest and we are off.',
    ui: {
      ui_id: 'ui-kind',
      title: 'What are we making?',
      kind: 'components',
      spec: {
        type: 'pick',
        id: 'format',
        columns: 3,
        options: [
          { value: 'Film & TV', icon: CLAPPER, note: 'A story told in scenes' },
          { value: 'Social Media', icon: HEART, note: 'Short pieces for a feed' },
          { value: 'Vertical Shows', icon: PHONE, note: 'Episodes made for a phone' },
          { value: 'Commercials', icon: MEGAPHONE, note: 'A product, a brand, a spot' },
          { value: 'Music Videos', icon: NOTES, note: 'Pictures cut to a track' },
          { value: 'Education', icon: BOOK, note: 'Explainers and lessons' },
          { value: 'Other', icon: DOTS, note: 'Something else' },
        ],
      },
      submit: null,
      waits: true,
      instant: true,
      media: [],
    },
  },
  {
    id: 'source',
    asked: 'Film & TV.',
    says: 'A film, then. Where does the story come from?',
    ui: {
      ui_id: 'ui-source',
      title: 'Where the story starts',
      kind: 'components',
      spec: SOURCE_SPEC,
      submit: null,
      waits: true,
      instant: true,
      media: [],
    },
  },
  {
    id: 'track',
    asked: 'Music Videos.',
    says: 'A music video is cut to its track, so the track comes first. Give it to me if you have it, or we make one.',
    ui: {
      ui_id: 'ui-track',
      title: 'The track',
      kind: 'components',
      spec: TRACK_SPEC,
      submit: 'Go on with this track',
      waits: true,
      media: [],
    },
  },
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
    id: 'layers',
    asked: 'The poster feels busy. What can go?',
    says: 'Here is the poster as its layers. Pick one in the dropdown, hide it or pull it back, and lock in what you want kept: I will rebuild the poster in PhotoCraft from that.',
    ui: {
      ui_id: 'ui-layers',
      title: 'The poster, layer by layer',
      kind: 'components',
      spec: {
        type: 'stack',
        children: [
          {
            type: 'layers',
            id: 'poster',
            layers: [
              { name: 'Sky', src: 'sky' },
              { name: 'Moon', src: 'moon' },
              { name: 'Skyline', src: 'skyline' },
              { name: 'Lanterns', src: 'lanterns', blend: 'screen' },
              { name: 'Fog', src: 'fog', opacity: 80 },
              { name: 'Title', src: 'title' },
            ],
          },
          { type: 'text', tone: 'muted', text: 'Six layers, the sky at the bottom. The lanterns are screened over the street.' },
        ],
      },
      submit: 'Keep these layers',
      waits: true,
      media: [
        file('sky', 'card-layer-sky.webp'),
        file('moon', 'card-layer-moon.webp'),
        file('skyline', 'card-layer-skyline.webp'),
        file('lanterns', 'card-layer-lanterns.webp'),
        file('fog', 'card-layer-fog.webp'),
        file('title', 'card-layer-title.webp'),
      ],
    },
  },
  {
    id: 'model',
    asked: 'Can I see Pip before we rig him?',
    says: 'Here he is, straight out of Blender. Turn him around, try a finish, and leave him at the angle you want for the hero render.',
    ui: {
      ui_id: 'ui-model',
      title: 'Pip, the lantern robot',
      kind: 'components',
      spec: {
        type: 'stack',
        children: [
          { type: 'model', id: 'angle', src: 'pip', finish: '$finish', color: '$paint', spin: true },
          {
            type: 'segmented',
            id: 'finish',
            label: 'Finish',
            options: [
              { value: 'original', label: 'Painted' },
              { value: 'clay', label: 'Clay' },
              { value: 'metal', label: 'Metal' },
              { value: 'gloss', label: 'Gloss' },
              { value: 'wire', label: 'Wire' },
            ],
          },
          {
            type: 'color',
            id: 'paint',
            label: 'Finish color',
            value: '#c6c0f5',
            suggest: ['#c6c0f5', '#d6fa72', '#e8a04a', '#f2f0e8', '#5f8f4e'],
            when: { finish: { not: 'original' } },
          },
          { type: 'text', tone: 'muted', text: 'Drag to orbit, scroll to zoom. The angle you leave him at is the one I render.' },
        ],
      },
      submit: 'Render from this angle',
      waits: true,
      media: [file('pip', 'card-robot.glb', 'model')],
    },
  },
  {
    id: 'shots',
    asked: 'We are over budget on the opening. What do we cut?',
    says: 'Every shot of the opening with what it costs to generate and finish, and where the money goes. Tick the shots you can live without: they light up in the chart, so you see what each cut buys back.',
    ui: {
      ui_id: 'ui-shots',
      title: 'The opening: shots and budget',
      kind: 'components',
      spec: {
        type: 'stack',
        children: [
          {
            type: 'table',
            id: 'cut',
            pick: 'many',
            columns: ['Shot', 'What happens', 'Lens', 'Seconds', 'Cost $'],
            rows: [
              ['1A', 'The city, far below', '24mm', 5, 420],
              ['1B', 'The market wakes', '35mm', 6, 610],
              ['2A', 'Mara, waiting', '85mm', 3, 180],
              ['2B', 'Theo’s workshop', '50mm', 4, 240],
              ['3A', 'The letter', '100mm macro', 2, 95],
              ['3B', 'The road out', '24mm', 5, 455],
            ],
            value: ['3B'],
          },
          {
            type: 'row',
            children: [
              {
                type: 'chart',
                kind: 'bar',
                label: 'Cost by shot',
                unit: '$',
                highlight: '$cut',
                data: [
                  { label: '1A', value: 420 },
                  { label: '1B', value: 610 },
                  { label: '2A', value: 180 },
                  { label: '2B', value: 240 },
                  { label: '3A', value: 95 },
                  { label: '3B', value: 455 },
                ],
              },
              {
                type: 'chart',
                kind: 'share',
                label: 'Where the $2,000 goes',
                unit: '$',
                data: [
                  { label: 'Generation', value: 940 },
                  { label: 'Compositing', value: 520 },
                  { label: 'Sound', value: 310 },
                  { label: 'Color', value: 230 },
                ],
              },
            ],
          },
          {
            type: 'chart',
            kind: 'area',
            label: 'Tension across the opening',
            highlight: '$cut',
            data: [
              { label: '1A', value: 22 },
              { label: '1B', value: 35 },
              { label: '2A', value: 58 },
              { label: '2B', value: 41 },
              { label: '3A', value: 76 },
              { label: '3B', value: 64 },
            ],
          },
        ],
      },
      submit: 'Cut these shots',
      waits: true,
      media: [],
    },
  },
  {
    id: 'cue',
    asked: 'What should the opening sound like?',
    says: 'Two sketches of the opening cue, eight seconds each. Play both and tell me which one the film opens on.',
    ui: {
      ui_id: 'ui-cue',
      title: 'A cue for the opening',
      kind: 'components',
      spec: {
        type: 'stack',
        children: [
          { type: 'audio', src: 'harbor', label: 'A · Slow harbor pad' },
          { type: 'audio', src: 'market', label: 'B · Market pulse' },
          {
            type: 'segmented',
            id: 'cue',
            label: 'Which one opens the film?',
            options: [
              { value: 'a', label: 'A · Harbor' },
              { value: 'b', label: 'B · Market' },
              { value: 'neither', label: 'Neither' },
            ],
          },
          {
            type: 'field',
            id: 'instead',
            label: 'What should it be instead?',
            placeholder: 'Slower, no percussion, a solo instrument…',
            required: true,
            when: { cue: 'neither' },
          },
        ],
      },
      submit: 'Use this cue',
      waits: true,
      media: [file('harbor', 'card-cue-harbor.m4a', 'audio'), file('market', 'card-cue-market.m4a', 'audio')],
    },
  },
  {
    id: 'sounds',
    asked: 'The lantern needs a sound when it lights. What do you have?',
    says: 'Three takes of the chime. Play them against each other and pick the one that belongs in the shot.',
    ui: {
      ui_id: 'ui-sounds',
      title: 'The lantern’s chime',
      kind: 'components',
      spec: {
        type: 'pick',
        id: 'take',
        label: 'Which take?',
        columns: 3,
        options: [
          { value: 'bell', label: 'A · Bell', audio: 'bell', note: 'Bright, rings out' },
          { value: 'gong', label: 'B · Gong', audio: 'gong', note: 'Low, slow to bloom' },
          { value: 'knock', label: 'C · Knock', audio: 'knock', note: 'Dry, a short ring' },
        ],
      },
      submit: 'Use this take',
      waits: true,
      media: [
        file('bell', 'card-sfx-bell.m4a', 'audio'),
        file('gong', 'card-sfx-gong.m4a', 'audio'),
        file('knock', 'card-sfx-knock.m4a', 'audio'),
      ],
    },
  },
  {
    id: 'eq',
    asked: 'The market cue is muddy under the dialogue. Can you clear it up?',
    says: 'I put the cue through three bands of equalization so you can hear the difference yourself. Press play, shape it, and lock in the curve: I will apply it to the stem in SoundCraft.',
    ui: {
      ui_id: 'ui-eq',
      title: 'Shape the market cue',
      kind: 'html',
      html: EQ_DOCUMENT,
      height: 400,
      submit: 'Lock in this EQ',
      waits: true,
      media: [file('cue', 'card-cue-market.m4a', 'audio')],
    },
  },
  {
    id: 'lanterns',
    asked: 'How should the lanterns move in the last shot?',
    says: 'Easier to feel than to describe, so here is a small simulation: every lantern rides the same wind and rises on its own heat. Set it the way the shot should feel and I will match the particle pass to it.',
    ui: {
      ui_id: 'ui-lanterns',
      title: 'Lanterns on the wind',
      kind: 'html',
      html: LANTERNS_DOCUMENT,
      height: 440,
      submit: 'Use this motion',
      waits: true,
      media: [],
    },
  },
  {
    id: 'contact',
    asked: 'One of the opening frames should be the poster. Which?',
    says: 'Here is the contact sheet. Click the frame you want, or double-click it to send it to print right away.',
    ui: {
      ui_id: 'ui-contact',
      title: 'A frame for the poster',
      kind: 'html',
      html: CONTACT_DOCUMENT,
      height: 330,
      submit: 'Print this frame',
      waits: true,
      media: [
        file('towers', 'app-unreal.webp'),
        file('market', 'discipline-media.webp'),
        file('house', 'discipline-architecture.webp'),
        file('studio', 'discipline-art.webp'),
        file('letter', 'discipline-writing.webp'),
        file('vista', 'discipline-games.webp'),
      ],
    },
  },
  {
    id: 'isolation',
    asked: 'What can a card you write actually reach?',
    says: 'Nothing but what I hand it. This card is a document that tries every way out of its frame and reports what became of each.',
    ui: {
      ui_id: 'ui-isolation',
      title: 'What a card’s own code can reach',
      kind: 'html',
      html: ISOLATION_DOCUMENT,
      height: 420,
      submit: 'Keep this report',
      waits: false,
      media: [],
    },
  },
  {
    id: 'runaway',
    asked: 'And if a card tried to leave with what it was shown?',
    says: 'It is stopped where it stands. This one navigates itself away with its files’ addresses in the link; the frame around it refuses, and the card says what happened.',
    ui: {
      ui_id: 'ui-runaway',
      title: 'A card that tries to leave',
      kind: 'html',
      html: RUNAWAY_DOCUMENT,
      height: 120,
      submit: null,
      waits: false,
      media: [file('shot', 'discipline-media.webp')],
    },
  },
  {
    id: 'changed',
    asked: 'Warmer than that, and more grain. Like this?',
    says: 'That holds up. If you would rather start over from where the card opened, "Back to default" beside the button does that in one press.',
    ui: {
      ui_id: 'ui-look-changed',
      title: 'The look of the night market',
      kind: 'components',
      spec: LOOK_SPEC,
      submit: 'Lock in this look',
      waits: true,
      media: [file('shot', 'discipline-media.webp')],
    },
    changed: { warmth: 46, grain: 44 },
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
  {
    id: 'nofile',
    asked: 'Can I give you the track from here?',
    says: 'Not from this page: it has no way to take a file. The card says so where the file would go, and the other way in still works.',
    ui: {
      ui_id: 'ui-track-nofile',
      title: 'The track',
      kind: 'components',
      spec: TRACK_SPEC,
      submit: 'Go on with this track',
      waits: true,
      media: [],
    },
    changed: { have: 'yes' },
    takesNoFiles: true,
  },
  {
    id: 'held',
    asked: 'Before I choose: how long would each take?',
    says: 'A fair question. The card above waits while I work that out: its choices cannot be pressed until I ask again.',
    ui: {
      ui_id: 'ui-source-held',
      title: 'Where the story starts',
      kind: 'components',
      spec: SOURCE_SPEC,
      submit: null,
      waits: true,
      instant: true,
      media: [],
    },
    idle: true,
  },
  {
    id: 'idle',
    asked: 'Actually, hold on. First tell me what the scene costs.',
    says: 'Of course. The card above stays where it is while I work that out: you can still try things on it, and I will ask again when the look is the next thing to settle.',
    ui: {
      ui_id: 'ui-look-idle',
      title: 'The look of the night market',
      kind: 'components',
      spec: LOOK_SPEC,
      submit: 'Lock in this look',
      waits: true,
      media: [file('shot', 'discipline-media.webp')],
    },
    idle: true,
  },
];
