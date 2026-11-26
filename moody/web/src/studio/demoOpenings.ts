/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * How a project of the demo starts by its kind (`moody/STUDIO.md`, "Contract: starting a project
 * by its kind"): the card that asks the kind, as the control plane writes it, and what the demo's
 * agent does once it is answered.
 *
 * A project made without a format, in a discipline the catalog gives an opening question, opens
 * on {@link kindCard}: one `pick` of the discipline's formats in the catalog's order, each with
 * the line and the pixel icon its `kinds` entry names. Choosing locks it, and the message that
 * locks it sets the project's format before the agent's first turn.
 *
 * From there the agent opens each kind with cards of its own ({@link openingTurn}), never with a
 * list of questions in prose, and every turn ends on one decision made easy:
 *
 * - **Film & TV** asks where the story comes from (a script to bring, an idea, or from scratch),
 *   then takes the script through an `upload` input, the idea in a field, or offers three
 *   directions as pictures.
 * - **Music Videos** asks whether there is a track: one to upload, or one to make together, for
 *   which it asks the feel and then plays three takes as tiles to compare by ear.
 * - **Social Media** asks in one card for the footage, where the clip goes, and what it is for.
 * - Any other kind is asked what it is about, in one field.
 *
 * Each of the three ends on a turn that shows a version of the piece (a `preview` with a
 * `version`), so the Latest module has something to play, and on a card that asks what comes
 * next. The openings are keyed by the catalog's names of the kinds; one the catalog renames is
 * opened as any other kind is. They start no engine and generate nothing: the files are the
 * demo's own (`public/media`).
 * @module
 */
import type { PreviewItem, Project, TurnId, UiData, UiMedia } from '../lib/api';
import { asksKind, catalog, type Discipline } from '../lib/catalog';
import { SECOND, type Scheduled, type Script } from './demoKit';

/** What of a project the card that asks its kind sets, which is also the id of the card's one input. */
export const KIND_FIELD = 'format';

/**
 * Builds the card that asks a new project's kind.
 *
 * @param discipline The project's discipline.
 * @param id The card's identifier.
 * @returns The card, or `null` for a discipline that asks nothing first.
 */
export function kindCard(discipline: Discipline, id: string): UiData | null {
  if (discipline.opening === undefined || !asksKind(discipline)) {
    return null;
  }
  return {
    ui_id: id,
    title: discipline.opening,
    kind: 'components',
    spec: {
      type: 'pick',
      id: KIND_FIELD,
      options: discipline.formats.map((format) => {
        const kind = discipline.kinds?.[format];
        const icon = kind === undefined ? undefined : catalog.icons[kind.icon];
        return {
          value: format,
          label: format,
          ...(kind === undefined ? {} : { note: kind.note }),
          ...(icon === undefined ? {} : { icon }),
        };
      }),
    },
    submit: null,
    waits: true,
    instant: true,
    sets: KIND_FIELD,
    media: [],
  };
}

/**
 * Reads the kind a locked card chose.
 *
 * @param card The card the message locked.
 * @param value What it was locked with.
 * @returns The kind, or `null` for a card that sets none or a value that names none.
 */
export function chosenKind(card: UiData, value: unknown): string | null {
  if (card.sets !== KIND_FIELD) {
    return null;
  }
  const chosen = answerTo(value, KIND_FIELD);
  return typeof chosen === 'string' ? chosen : null;
}

/**
 * Reads what one input of a locked card held.
 *
 * @param value What the card was locked with: its inputs' values by their ids.
 * @param id The input.
 * @returns Its value, or `undefined` where the card had no such input.
 */
function answerTo(value: unknown, id: string): unknown {
  if (typeof value !== 'object' || value === null || !(id in value)) {
    return undefined;
  }
  const held: Record<string, unknown> = { ...value };
  return held[id];
}

/**
 * Writes a pixel icon as the rows a card takes, from rows drawn with `#` for a lit cell.
 *
 * @param rows The icon, a square of `#` and `.`.
 * @returns The same rows as `1` and `0`.
 */
function icon(...rows: string[]): string[] {
  return rows.map((row) => row.replaceAll('#', '1').replaceAll('.', '0'));
}

/** A page of a script. */
const PAGE = icon(
  '............',
  '..#######...',
  '..#.....##..',
  '..#.###..#..',
  '..#......#..',
  '..#.####.#..',
  '..#......#..',
  '..#.####.#..',
  '..#......#..',
  '..#.###..#..',
  '..########..',
  '............',
);

/** A light bulb, for an idea. */
const BULB = icon(
  '............',
  '....####....',
  '...#....#...',
  '..#......#..',
  '..#......#..',
  '..#......#..',
  '...#....#...',
  '....#..#....',
  '....####....',
  '....####....',
  '.....##.....',
  '............',
);

/** A plus, for starting with nothing. */
const PLUS = icon(
  '............',
  '.....##.....',
  '.....##.....',
  '.....##.....',
  '.....##.....',
  '.##########.',
  '.##########.',
  '.....##.....',
  '.....##.....',
  '.....##.....',
  '.....##.....',
  '............',
);

/** An arrow up out of a tray, for a file to bring. */
const BRING = icon(
  '............',
  '.....##.....',
  '....####....',
  '...######...',
  '..########..',
  '.....##.....',
  '.....##.....',
  '.....##.....',
  '.#........#.',
  '.#........#.',
  '.##########.',
  '............',
);

/** Two beamed notes, for music to write. */
const NOTES = icon(
  '............',
  '....#######.',
  '....#######.',
  '....#.....#.',
  '....#.....#.',
  '....#.....#.',
  '....#.....#.',
  '..###...###.',
  '.####..####.',
  '.####..####.',
  '..##....##..',
  '............',
);

/** A card the agent asks with, before it has its identifier and its files' addresses. */
interface Card {
  /** Which step of the opening it is, which its answer is told by. */
  step: string;
  /** Its heading. */
  title: string;
  /** Its content, in the components of `moody/ui.json`. */
  spec: unknown;
  /** The button that locks it, or `null` for a card whose one choice locks it. */
  submit: string | null;
  /** The files it shows, by the names its content refers to them by. */
  media?: UiMedia[];
}

/** A call of one of the agent's tools, as the conversation shows it. */
interface Work {
  /** The tool. */
  tool: string;
  /** What the call is doing, while it runs. */
  title: string;
  /** What it came to. */
  summary: string;
  /** How long it takes, in seconds. */
  seconds: number;
}

/** A version of the piece the agent shows. */
interface Shown {
  /** What it calls the version. */
  label: string;
  /** What it says of it. */
  caption: string;
  /** The file. */
  item: PreviewItem;
}

/** One turn of an opening: what the agent does, shows, says, and asks. */
interface Step {
  /** The tools it calls first. */
  work?: Work[];
  /** The version of the piece it shows. */
  shown?: Shown;
  /** What it says, in a line or two. */
  says: string;
  /** The card the turn ends on. */
  card?: Card;
}

/** The demo's three takes of a track, as the files of the card that compares them. */
const TAKES: readonly { value: string; label: string; note: string; file: UiMedia; seconds: number }[] = [
  {
    value: 'a',
    label: 'Take A',
    note: 'Piano alone, slow',
    file: { name: 'take-a.m4a', kind: 'audio', url: '/media/preview-theme.m4a' },
    seconds: 10.2,
  },
  {
    value: 'b',
    label: 'Take B',
    note: 'Low strings, a long swell',
    file: { name: 'take-b.m4a', kind: 'audio', url: '/media/card-cue-harbor.m4a' },
    seconds: 8,
  },
  {
    value: 'c',
    label: 'Take C',
    note: 'Plucked, quicker',
    file: { name: 'take-c.m4a', kind: 'audio', url: '/media/card-cue-market.m4a' },
    seconds: 8,
  },
];

/** The card every opening's last turn ends on: what comes next, as one choice. */
const NEXT: Card = {
  step: 'next',
  title: 'What next?',
  spec: {
    type: 'pick',
    id: 'next',
    columns: 3,
    options: [
      { value: 'on', label: 'Keep going', note: 'The next part, the same way.' },
      { value: 'change', label: 'Change this one', note: 'Tell me what is off.' },
      { value: 'other', label: 'Try another take', note: 'The same part, a different way.' },
    ],
  },
  submit: null,
};

/** The cut the demo shows as a first version in pictures. */
const FIRST_CUT: PreviewItem = {
  kind: 'video',
  url: '/media/preview-cut.mp4',
  name: 'first-cut.mp4',
  seconds: 6,
  width: 640,
  height: 360,
};

/** The boards the demo shows cut together, before anything moves. */
const BOARDS: PreviewItem = {
  kind: 'video',
  url: '/media/preview-boards.mp4',
  name: 'boards-cut.mp4',
  seconds: 6,
  width: 640,
  height: 360,
};

/** The film opening's last turn: the opening as boards, cut together. */
const FILM_BOARDS: Step = {
  work: [{ tool: 'generate_image', title: 'Boards for the opening', summary: '2 boards', seconds: 3 }],
  shown: {
    label: 'Boards cut',
    caption: 'The opening as boards, three seconds each: no motion yet, only the order.',
    item: BOARDS,
  },
  says: 'That is the opening as boards. Play it, and say where it should go from here.',
  card: NEXT,
};

/** What the agent opens each kind with, by the catalog's name of the kind. */
const FIRST: Readonly<Record<string, Step>> = {
  'Film & TV': {
    says: 'A film, then. One thing decides how we start.',
    card: {
      step: 'story',
      title: 'Where does the story come from?',
      spec: {
        type: 'pick',
        id: 'story',
        columns: 3,
        options: [
          { value: 'script', label: 'I have a script', note: 'Bring the pages. I break them into scenes and shots.', icon: PAGE },
          { value: 'idea', label: 'I have an idea', note: 'A premise, a character, an image. We grow it.', icon: BULB },
          { value: 'scratch', label: 'From scratch', note: 'Nothing yet. I put three directions on the table.', icon: PLUS },
        ],
      },
      submit: null,
    },
  },
  'Music Videos': {
    says: 'A music video starts from its track.',
    card: {
      step: 'track',
      title: 'Do you have the track?',
      spec: {
        type: 'pick',
        id: 'track',
        columns: 2,
        options: [
          { value: 'upload', label: 'I have the track', note: 'Upload it, and I cut to its beat.', icon: BRING },
          { value: 'make', label: 'Make one together', note: 'Tell me the feel, and I write a few to compare.', icon: NOTES },
        ],
      },
      submit: null,
    },
  },
  'Social Media': {
    says: 'Three quick things, and I can cut the first one.',
    card: {
      step: 'brief',
      title: 'What are we posting?',
      spec: {
        type: 'stack',
        children: [
          { type: 'upload', id: 'footage', label: 'Footage to cut from', accept: 'video', section: 'Footage' },
          {
            type: 'pick',
            id: 'shape',
            label: 'Where it goes',
            columns: 3,
            value: 'vertical',
            options: [
              { value: 'vertical', label: 'Short vertical', note: '9:16, under a minute', icon: catalog.icons.vertical },
              { value: 'feed', label: 'Feed post', note: '4:5, where a scroll stops', icon: catalog.icons.social },
              { value: 'wide', label: 'Long form', note: '16:9, for a channel', icon: catalog.icons.film },
            ],
          },
          {
            type: 'segmented',
            id: 'goal',
            label: 'What it is for',
            value: 'reach',
            options: [
              { value: 'reach', label: 'Reach new people' },
              { value: 'sell', label: 'Sell something' },
              { value: 'teach', label: 'Teach something' },
            ],
          },
        ],
      },
      submit: 'Cut the first one',
    },
  },
};

/** What the agent opens any other kind with. */
const FIRST_OTHER: Step = {
  says: 'Good. Tell me what it is, and I will propose how to make it.',
  card: {
    step: 'about',
    title: 'What is it about?',
    spec: {
      type: 'stack',
      children: [
        {
          type: 'field',
          id: 'about',
          label: 'In a sentence or two',
          placeholder: 'Who it is for, and what they should take from it',
          lines: 3,
          required: true,
        },
        { type: 'upload', id: 'material', label: 'Anything to start from', accept: 'any' },
      ],
    },
    submit: 'Start',
  },
};

/** What the agent does once a card of an opening is answered, by the card's step. */
const AFTER: Readonly<Record<string, (value: unknown) => Step>> = {
  story: (value) => {
    const story = answerTo(value, 'story');
    if (story === 'script') {
      return {
        says: 'Good. Bring the pages, and I will break them into scenes and shots.',
        card: {
          step: 'script',
          title: 'Bring the script',
          spec: {
            type: 'stack',
            children: [
              { type: 'upload', id: 'script', label: 'The script', accept: 'any', section: 'Script', required: true },
              { type: 'field', id: 'note', label: 'Anything I should know before I read it?', lines: 2 },
            ],
          },
          submit: 'Read it',
        },
      };
    }
    if (story === 'idea') {
      return {
        says: 'Then tell it to me the way you would to a friend.',
        card: {
          step: 'idea',
          title: 'The idea',
          spec: {
            type: 'stack',
            children: [
              {
                type: 'field',
                id: 'idea',
                label: 'What happens, or what do we see?',
                placeholder: 'A lighthouse keeper, the night the light fails',
                lines: 4,
                required: true,
              },
              {
                type: 'segmented',
                id: 'length',
                label: 'How long',
                value: 'short',
                options: [
                  { value: 'short', label: 'A minute or two' },
                  { value: 'medium', label: 'Five to ten minutes' },
                  { value: 'long', label: 'Longer' },
                ],
              },
            ],
          },
          submit: 'Develop it',
        },
      };
    }
    return {
      says: 'Then here are three directions. Pick the one that pulls at you.',
      card: {
        step: 'direction',
        title: 'Three directions',
        spec: {
          type: 'pick',
          id: 'direction',
          columns: 3,
          options: [
            { value: 'night', label: 'The last take', note: 'A film crew, one street, one night.', image: 'direction-night.webp' },
            { value: 'flats', label: 'Violet flats', note: 'Two travelers cross a land that glows.', image: 'direction-flats.webp' },
            { value: 'still', label: 'The portrait', note: 'A photographer and the face she cannot forget.', image: 'direction-portrait.webp' },
          ],
        },
        submit: null,
        media: [
          { name: 'direction-night.webp', kind: 'image', url: '/media/discipline-media.webp' },
          { name: 'direction-flats.webp', kind: 'image', url: '/media/discipline-experiences.webp' },
          { name: 'direction-portrait.webp', kind: 'image', url: '/media/discipline-photography.webp' },
        ],
      },
    };
  },
  script: () => FILM_BOARDS,
  idea: () => FILM_BOARDS,
  direction: () => FILM_BOARDS,
  track: (value) =>
    answerTo(value, 'track') === 'upload'
      ? {
          says: 'Bring it in, and I will find its beats and its sections.',
          card: {
            step: 'song',
            title: 'Bring the track',
            spec: { type: 'upload', id: 'song', label: 'The track', accept: 'audio', section: 'Music', required: true },
            submit: 'Use this track',
          },
        }
      : {
          says: 'Then give me the feel of it.',
          card: {
            step: 'feel',
            title: 'What should it sound like?',
            spec: {
              type: 'stack',
              children: [
                {
                  type: 'pick',
                  id: 'mood',
                  label: 'Mood',
                  columns: 3,
                  value: 'warm',
                  options: [
                    { value: 'warm', label: 'Warm and slow' },
                    { value: 'bright', label: 'Bright and quick' },
                    { value: 'dark', label: 'Dark and heavy' },
                  ],
                },
                {
                  type: 'segmented',
                  id: 'voice',
                  label: 'Voice',
                  value: 'instrumental',
                  options: [
                    { value: 'instrumental', label: 'Instrumental' },
                    { value: 'sung', label: 'Sung' },
                  ],
                },
                { type: 'field', id: 'about', label: 'What is the song about?', lines: 2 },
              ],
            },
            submit: 'Write three',
          },
        },
  feel: () => ({
    work: [
      { tool: 'generate_audio', title: 'Writing three takes', summary: '3 takes of the opening bars', seconds: 4 },
    ],
    says: 'Three takes on that feel. Play them, and choose the one the video is cut to.',
    card: {
      step: 'take',
      title: 'Which one is the track?',
      spec: {
        type: 'pick',
        id: 'take',
        columns: 3,
        options: TAKES.map((take) => ({ value: take.value, label: take.label, note: take.note, audio: take.file.name })),
      },
      submit: null,
      media: TAKES.map((take) => take.file),
    },
  }),
  take: (value) => {
    const take = TAKES.find((candidate) => candidate.value === answerTo(value, 'take')) ?? TAKES[0];
    return {
      shown:
        take === undefined
          ? undefined
          : {
              label: `Track, ${take.label}`,
              caption: `${take.label} is the track: ${take.note.toLowerCase()}.`,
              item: { kind: 'audio', url: take.file.url, name: take.file.name, seconds: take.seconds },
            },
      says: 'That is the track. Next I would sketch the pictures to its beats.',
      card: NEXT,
    };
  },
  song: () => ({
    shown: {
      label: 'Beat sketch',
      caption: 'Your track with a cut on every fourth beat: stand-in pictures, to judge the rhythm alone.',
      item: FIRST_CUT,
    },
    says: 'That is the rhythm of the cut against your track. The pictures are stand-ins.',
    card: NEXT,
  }),
  brief: () => ({
    shown: {
      label: 'Clip 1, first cut',
      caption: 'The strongest moment, opening on its hook, six seconds.',
      item: FIRST_CUT,
    },
    says: 'First cut of the first clip. The others are cut the same way once you like this one.',
    card: NEXT,
  }),
};

/** The engine the openings' previews name: none of the project's, since an opening starts none. */
const NO_ENGINE = 'demo-no-engine';

/**
 * Writes one turn of an opening as the events of the log.
 *
 * @param project The project.
 * @param step The turn.
 * @param turn The turn's identifier.
 * @param start When the turn starts.
 * @returns The turn.
 */
function play(project: Project, step: Step, turn: TurnId, start: number): Script {
  const events: Scheduled[] = [];
  let seconds = 0.8;
  const add = (event: Scheduled['event'], after = 0.4): void => {
    seconds += after;
    events.push({ at: start + seconds * SECOND, event });
  };
  (step.work ?? []).forEach((work, index) => {
    const call = `${turn}-${index}`;
    add({ turn_id: turn, kind: 'tool_start', data: { call_id: call, tool: work.tool, title: work.title } });
    add({ turn_id: turn, kind: 'tool_end', data: { call_id: call, ok: true, summary: work.summary } }, work.seconds);
  });
  if (step.shown !== undefined) {
    const call = `${turn}-shown`;
    add({ turn_id: turn, kind: 'tool_start', data: { call_id: call, tool: 'preview', title: 'Preparing a preview' } });
    add(
      {
        turn_id: turn,
        kind: 'preview',
        data: {
          engine_id: NO_ENGINE,
          caption: step.shown.caption,
          items: [step.shown.item],
          compare: false,
          version: step.shown.label,
        },
      },
      2,
    );
    add({ turn_id: turn, kind: 'tool_end', data: { call_id: call, ok: true, summary: `Showed ${step.shown.label}` } });
  }
  add({ turn_id: turn, kind: 'text', data: { text: step.says } }, 0.8);
  if (step.card !== undefined) {
    const { card } = step;
    add({
      turn_id: turn,
      kind: 'ui',
      data: {
        ui_id: `${project.id}:${turn}:${card.step}`,
        title: card.title,
        kind: 'components',
        spec: card.spec,
        submit: card.submit,
        waits: true,
        ...(card.submit === null ? { instant: true } : {}),
        media: card.media ?? [],
      },
    });
  }
  add({ turn_id: turn, kind: 'turn_end', data: {} }, 0.2);
  return { events };
}

/**
 * The demo agent's turn after the person answered a card of an opening.
 *
 * @param project The project, with the kind the answer may just have given it.
 * @param answered The card the person's message locked, or `null` for a message that locked none.
 * @param value What the card was locked with.
 * @param turn The turn the message starts.
 * @param start When the turn starts.
 * @returns The turn, or `null` for a message that answers no card of an opening.
 */
export function openingTurn(
  project: Project,
  answered: UiData | null,
  value: unknown,
  turn: TurnId,
  start: number,
): Script | null {
  if (answered === null) {
    return null;
  }
  if (answered.sets === KIND_FIELD) {
    const first = Object.hasOwn(FIRST, project.format) ? FIRST[project.format] : undefined;
    return play(project, first ?? FIRST_OTHER, turn, start);
  }
  const step = answered.ui_id.startsWith(`${project.id}:`) ? answered.ui_id.split(':').at(-1) : undefined;
  const next = step !== undefined && Object.hasOwn(AFTER, step) ? AFTER[step] : undefined;
  return next === undefined ? null : play(project, next(value), turn, start);
}
