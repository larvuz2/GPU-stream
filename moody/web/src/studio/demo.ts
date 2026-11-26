/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The studio's demo: a control plane made of fixtures, for seeing the studio without an account
 * or a backend.
 *
 * `/app/?demo` renders the studio against {@link createDemoControlPlane} instead of the HTTP
 * client. This module is a chunk of its own, fetched only when that flag is present. It holds no
 * credentials and sends no request: every answer is computed in memory, so the demo cannot reach
 * an account's data, and it replaces the signed-in path rather than opening a way around it.
 *
 * The sample is a short animated film part way through the film workflow (`moody/STUDIO.md`): a
 * script written, a bible of characters, environments, and props with reference images, FilmCraft
 * open, and the agent asking how the film should open. Time moves as it would: a message sent
 * here starts a turn whose events arrive over a few seconds, under the studio's own polling, and
 * an engine started here queues, starts, and runs. The images are the site's own artwork.
 *
 * Every question the demo's agents ask names the answer they would give (`recommended`), as the
 * agent on Anthropic's loop does.
 *
 * The film's agent shows its work before it asks: five previews of every kind a card takes (the
 * boards cut together, a file, a frame, a before and after pair of a grade, and a six-second
 * animatic), two more than a turn keeps in view, so the earliest are folded. The boards cut and
 * the animatic are versions of the piece (`version`), so the Latest module plays the animatic and
 * lists the boards cut before it. A third project, Lighthouse theme, is a score in SoundCraft
 * whose agent plays the person the first eight bars as a preview, a version too. The clips, the
 * graded frame, and the eight bars are made for the demo: the clips and the frame from the site's
 * own artwork with ffmpeg, the bars synthesized with it (`public/media/preview-*`).
 *
 * Beside the film is a game, Ember Ridge, part way through a studio's onboarding (`moody/UNREAL.md`):
 * the agent started an Unreal engine and put its Desktop on the screen, the developer cloned the
 * game there, and the agent found it and reported what it is, which the engine's card in the
 * Environment panel lists too. Asking to open it, from the agent's question or the card, opens it
 * in the editor and switches the screen to the Unreal view, the other of the engine's two
 * pictures. The demo's Epic connection is linked, the GitHub account whose Epic account the
 * editor runs on.
 *
 * A turn is a script (`demoKit.ts`), played by {@link createDemoControlPlane}'s `play`: its events
 * are written as their times come, and a turn that asks before a tool waits on its approval until
 * the person answers it, then plays the rest. An answer of "always" is kept in the project's
 * permissions, so the same tool runs without asking from then on, until the person revokes it.
 * Each project also has an environment: the connectors, subagents, and skills its agent works
 * with. Every reading of a log returns its files under addresses of that reading (`?read=`), as
 * the control plane signs them afresh each time, so a page that reads the log again gets other
 * addresses for the same files.
 *
 * The scene parameter (`?demo=<scene>`) picks a state: the film by default, `offline` for a
 * server with no integrations configured, `empty` for an account with no projects, `legacy` for a
 * control plane from before the studio, which answers its routes with 404, `no-epic` for an
 * Epic connection whose GitHub account is not linked to Epic, where opening the game in Unreal
 * answers with the steps that link it, `movie` for a new film that starts from its first
 * message with no engine, which plays the agent thinking, asking, delegating to subagents, and
 * asking before it starts one (`demoMovie.ts`), and `limit` for that film further on, on an
 * account that set its spend for a turn low, where a long job has stopped at it.
 *
 * The account has the limits of a turn as settings ({@link DEFAULT_LIMITS}, {@link MAX_LIMITS}),
 * which `updateMe` changes and refuses as the control plane does, and which the film's long job
 * keeps to.
 * @module
 */
import {
  ALWAYS,
  ApiError,
  DESKTOP_STREAM,
  type ApiKey,
  type Asset,
  type Connector,
  type ControlPlane,
  type EngineStream,
  type Environment,
  type EpicStatus,
  type GitHubRepo,
  type GitHubStatus,
  type Health,
  type Limits,
  type Media,
  type Me,
  type PlanItem,
  type PreviewItem,
  type Project,
  type Session,
  type SkillInfo,
  type StudioEvent,
  type TurnId,
  type TurnLimits,
  type UnrealProject,
} from '../lib/api';
import { catalog, findApp, findDiscipline } from '../lib/catalog';
import { creditCount, usd } from '../lib/format';
import { appImage } from '../lib/media';
import {
  asset,
  DAY,
  HOUR,
  MINUTE,
  SECOND,
  snapshot,
  still,
  type EventBody,
  type Pause,
  type Scheduled,
  type Script,
  type Simulation,
} from './demoKit';
import { chosenKind, kindCard } from './demoOpenings';
import {
  FILM_DISCIPLINES,
  MOVIE_AGENTS,
  MOVIE_PROJECT,
  movieOpening,
  movieProject,
  movieSoFar,
  movieTurn,
} from './demoMovie';

/** The address the demo's account is shown under. */
export const DEMO_EMAIL = 'you@example.com';

/** What a turn may spend and take on the demo's deployment, for an account that set neither. */
const DEFAULT_LIMITS: TurnLimits = { turn_budget_usd: 15, turn_limit: 200 };

/** The demo deployment's ceilings, which no account sets a limit above. */
const MAX_LIMITS: TurnLimits = { turn_budget_usd: 100, turn_limit: 1000 };

/** The spend for a turn the account of the `limit` scene set itself, low enough for a long job to reach. */
const LOW_BUDGET_USD = 1;

/** The status a refusal of the demo carries: a feature it does not have. */
const NOT_CONFIGURED = 503;

/** The GitHub login the demo is connected as. */
const LOGIN = 'moody-demo';

/** An avatar drawn inline, so the demo fetches nothing. */
const AVATAR = `data:image/svg+xml,${encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' fill='#191919'/><text x='32' y='41' font-family='system-ui,sans-serif' font-size='26' font-weight='700' text-anchor='middle' fill='#ffffff'>M</text></svg>",
)}`;

const PIP = still('character-theo.webp', 'pip-reference.webp');
const MARA = still('character-mara.webp', 'mara-reference.webp');
const GLASSHOUSE = still('discipline-architecture.webp', 'glasshouse.webp');
const SPIRE = still('discipline-media.webp', 'spire-city.webp');
const PEAKS = still('discipline-experiences.webp', 'ember-peaks-concept.webp');
const BEACON = still('discipline-art.webp', 'beacon.webp');
const RUNNERS = still('discipline-fashion.webp', 'runners.webp');

/** The name of an Unreal engine's second picture, the editor's own stream. */
const UNREAL_STREAM = 'Unreal';

/**
 * What an engine of an app streams in the demo: an Unreal engine, its Desktop and its Unreal view.
 *
 * The demo has no stream to serve, so each picture's address is the art it is drawn with.
 *
 * @param app The catalog app.
 * @returns The streams, or `undefined` for an app that streams its desktop alone.
 */
function demoStreams(app: string): EngineStream[] | undefined {
  const art = (id: string): string => new URL(appImage(id), window.location.origin).href;
  return app === 'unreal'
    ? [
        { name: DESKTOP_STREAM, url: art('blender') },
        { name: UNREAL_STREAM, url: art('unreal') },
      ]
    : undefined;
}

/** The demo game's engine. */
const GAME_ENGINE = 'demo-engine-2';

/** The Unreal project the demo game's engine finds once the developer has cloned the game. */
const EMBER_RIDGE: UnrealProject = {
  path: '/home/ubuntu/workspace/projects/demo-game/ember-ridge/EmberRidge.uproject',
  name: 'EmberRidge',
  engine_association: '5.8',
  version: 'same',
  opens: 'Saved with Unreal Engine 5.8, this engine’s version: it opens as it is.',
  cpp_modules: ['EmberRidge'],
  plugins: ['CommonUI', 'EnhancedInput', 'GameplayAbilities', 'ModelingToolsEditorMode'],
  plugins_to_check: [],
  lfs: true,
  size_bytes: 3_180_000_000,
};

/**
 * The demo game's plan, before and after the game opens in Unreal.
 *
 * @param opened Whether it is open.
 * @returns The plan.
 */
function gamePlan(opened: boolean): PlanItem[] {
  return [
    { id: 'g1', title: 'Start Unreal Engine', status: 'done' },
    { id: 'g2', title: 'Clone Ember Ridge from GitHub in the Desktop view', status: 'done' },
    { id: 'g3', title: 'Open it in Unreal', status: opened ? 'done' : 'active' },
    {
      id: 'g4',
      title: 'Block out the ridge path, with Blender beside the editor',
      status: opened ? 'active' : 'pending',
    },
  ];
}

/** The film's plan as the demo opens. */
function filmPlan(stage: 'opening' | 'answered'): PlanItem[] {
  return [
    { id: 'p1', title: 'Write the script', status: 'done' },
    { id: 'p2', title: 'Build the bible: characters, environments, props', status: 'done' },
    { id: 'p3', title: 'Approve the reference images', status: stage === 'opening' ? 'active' : 'done' },
    { id: 'p4', title: 'Shot list for scene 1', status: stage === 'opening' ? 'pending' : 'active' },
    { id: 'p5', title: 'Generate the shots with Seedance', status: 'pending' },
    { id: 'p6', title: 'Cut, color, and mix in FilmCraft', status: 'pending' },
    { id: 'p7', title: 'Poster in PhotoCraft (coming next)', status: 'blocked' },
  ];
}

/**
 * The film's library.
 *
 * @param now The time the demo opens at.
 * @returns The assets, by section in order.
 */
function filmLibrary(now: number): Asset[] {
  const made = now - 40 * MINUTE;
  return [
    asset(
      {
        id: 'a-pip',
        section: 'Characters',
        name: 'Pip',
        tag: 'pip',
        description:
          'Twelve, an inventor with more ideas than sleep. Brass goggles pushed up, sleeves rolled, a burn on one thumb he is proud of.',
        metadata: {
          age: 12,
          voice: 'Bright, quick, interrupts himself',
          palette: 'Copper, ochre, teal',
          first_seen: 'Scene 1',
        },
        media: [PIP],
      },
      made,
    ),
    asset(
      {
        id: 'a-mara',
        section: 'Characters',
        name: 'Mara',
        tag: 'mara',
        description:
          'A courier of the violet flats, late forties and sun-creased. She has crossed the flats more times than anyone alive, and says so.',
        metadata: { age: 48, role: 'Guide', palette: 'Dust violet, bone', first_seen: 'Scene 2' },
        media: [MARA],
      },
      made,
    ),
    asset(
      {
        id: 'a-cog',
        section: 'Characters',
        name: 'Cog',
        tag: 'cog',
        description: 'Pip’s pocket robot, built from a music box. Speaks only in chimes. Reference to come.',
        media: [],
      },
      made,
    ),
    asset(
      {
        id: 'a-glasshouse',
        section: 'Environments',
        name: 'The glasshouse',
        tag: 'glasshouse',
        description: 'Grandmother Ada’s glasshouse on the sea cliff, the last place that still grows light.',
        metadata: { time_of_day: 'Blue hour', scenes: '3' },
        media: [GLASSHOUSE],
      },
      made,
    ),
    asset(
      {
        id: 'a-spire',
        section: 'Environments',
        name: 'Spire City',
        tag: 'spire-city',
        description: 'A vertical city lit from a single beacon line. When it fails, the fog comes in from below.',
        metadata: { time_of_day: 'Dusk', scenes: '1' },
        media: [SPIRE],
      },
      made,
    ),
    asset(
      {
        id: 'a-peaks',
        section: 'Environments',
        name: 'The ember peaks',
        tag: 'ember-peaks',
        description: 'Concept painting of the ridge Pip and Mara cross at sunset, the flats behind them.',
        metadata: { time_of_day: 'Sunset', scenes: '2' },
        media: [PEAKS],
      },
      made,
    ),
    asset(
      {
        id: 'a-beacon',
        section: 'Props',
        name: 'The beacon',
        tag: 'beacon',
        description:
          'A heart-shaped lattice around a core of living light. Warm to the touch; it dims when Pip is afraid.',
        media: [BEACON],
      },
      made,
    ),
    asset(
      {
        id: 'a-runners',
        section: 'Props',
        name: 'Pip’s runners',
        tag: 'runners',
        description: 'Patched, a size too big, laced with copper wire.',
        media: [RUNNERS],
      },
      made,
    ),
  ];
}

/**
 * The film's conversation up to the agent's question.
 *
 * @param now The time the demo opens at.
 * @param library The film's library, which the events add.
 * @param engine The FilmCraft engine the agent opened.
 * @returns The events, in order, with their times.
 */
function filmEvents(now: number, library: Asset[], engine: Session): Scheduled[] {
  const byTag = (tag: string): Asset[] => library.filter((entry) => entry.tag === tag);
  const turn1 = now - 46 * MINUTE;
  const turn2 = now - 12 * MINUTE;
  const events: EventBody[] = [];
  const times: number[] = [];
  let clock = turn1;
  const add = (event: EventBody, step = 20 * SECOND): void => {
    clock += step;
    events.push(event);
    times.push(clock);
  };
  const t1 = 'turn-1';
  const t2 = 'turn-2';

  add({
    turn_id: t1,
    kind: 'user_message',
    data: {
      text: 'Let’s make a three-minute animated short. A kid inventor, Pip, has to carry a glowing beacon across the violet flats to his grandmother’s glasshouse before the last light in Spire City goes out. Warm, hand-made feel.',
    },
  });
  add({
    turn_id: t1,
    kind: 'text',
    data: {
      text:
        'Love this. Here is the shape I would give it.\n\n' +
        '**Logline.** A twelve-year-old inventor races a dying beacon across a violet desert to relight his grandmother’s glasshouse, and the city that depends on it.\n\n' +
        '1. **Spire City, dusk.** The lights fail block by block; Pip finds the beacon cold in his workshop.\n' +
        '2. **The violet flats.** Mara, a courier, agrees to guide him, for a price.\n' +
        '3. **The glasshouse.** The beacon takes, and the city answers.\n\n' +
        'I will draft the script first, then build the bible so every shot stays consistent.',
    },
  });
  add({ turn_id: t1, kind: 'tool_start', data: { call_id: 'c1', tool: 'github_save', title: 'Draft the script' } });
  add(
    {
      turn_id: t1,
      kind: 'tool_end',
      data: { call_id: 'c1', ok: true, summary: 'script.fountain · 3 scenes · about 2 min 50 s' },
    },
    70 * SECOND,
  );
  add({
    turn_id: t1,
    kind: 'plan',
    data: { items: filmPlan('opening').map((item) => (item.id === 'p3' ? { ...item, status: 'pending' } : item)) },
  });
  add({
    turn_id: t1,
    kind: 'text',
    data: {
      text: 'The script is in the project folder. Now the bible: I am writing up @pip, @mara, and the places, and generating a reference for each.',
    },
  });
  const generate = (call: string, title: string, tags: string[], summary: string): void => {
    add({ turn_id: t1, kind: 'tool_start', data: { call_id: call, tool: 'generate_image', title } });
    const assets = tags.flatMap(byTag);
    add(
      {
        turn_id: t1,
        kind: 'tool_end',
        data: { call_id: call, ok: true, summary, media: assets.flatMap((entry) => entry.media.slice(0, 1)) },
      },
      40 * SECOND,
    );
    for (const entry of assets) {
      add({ turn_id: t1, kind: 'library', data: { asset: entry } }, SECOND);
    }
  };
  generate('c2', 'Reference: @pip', ['pip'], 'Two variations; kept the warmer one.');
  generate('c3', 'Reference: @mara', ['mara'], 'Wide, so her silhouette reads against the door.');
  generate(
    'c4',
    'Environments: the glasshouse and Spire City',
    ['glasshouse', 'spire-city'],
    'Blue hour and dusk, to match the script.',
  );
  generate('c5', 'Props: @beacon and @runners', ['beacon', 'runners'], 'Hero props, lit as in scene 1.');
  add({ turn_id: t1, kind: 'plan', data: { items: filmPlan('opening') } });
  add({
    turn_id: t1,
    kind: 'text',
    data: {
      text: 'References are in the library under Characters, Environments, and Props. Have a look and tell me what to change.',
    },
  });
  add({ turn_id: t1, kind: 'turn_end', data: {} }, SECOND);

  clock = turn2;
  add({
    turn_id: t2,
    kind: 'user_message',
    data: { text: 'These are great. Mara should feel older, more weathered.' },
  });
  add({ turn_id: t2, kind: 'tool_start', data: { call_id: 'c6', tool: 'library_upsert', title: 'Update @mara' } });
  add(
    { turn_id: t2, kind: 'tool_end', data: { call_id: 'c6', ok: true, summary: 'Age and description updated.' } },
    6 * SECOND,
  );
  add({
    turn_id: t2,
    kind: 'text',
    data: {
      text: 'Done: @mara is late forties now, sun-creased, with a courier’s patience. I will regenerate her reference once we lock the opening, so its light matches shot 1.',
    },
  });
  add({ turn_id: t2, kind: 'tool_start', data: { call_id: 'c7', tool: 'engine_start', title: 'Open FilmCraft' } });
  add({ turn_id: t2, kind: 'engine', data: { engine } }, 30 * SECOND);
  add(
    {
      turn_id: t2,
      kind: 'tool_end',
      data: { call_id: 'c7', ok: true, summary: 'FilmCraft on Studio, the project folder mounted.' },
    },
    5 * SECOND,
  );
  add({
    turn_id: t2,
    kind: 'text',
    data: {
      text: 'FilmCraft is open on the project’s folder. The shots do not exist yet, so I cut a rough animatic of the opening from the references and tried the dusk grade on Spire City, to give you something to judge.',
    },
  });
  /** Shows work in progress the way the agent's `preview` tool does: its call, the card, its outcome. */
  const show = (
    call: string,
    summary: string,
    caption: string,
    items: PreviewItem[],
    { compare = false, version }: { compare?: boolean; version?: string } = {},
  ): void => {
    add({ turn_id: t2, kind: 'tool_start', data: { call_id: call, tool: 'preview', title: 'Preparing a preview' } });
    add(
      {
        turn_id: t2,
        kind: 'preview',
        data: { engine_id: engine.id, caption, items, compare, ...(version === undefined ? {} : { version }) },
      },
      3 * SECOND,
    );
    add({ turn_id: t2, kind: 'tool_end', data: { call_id: call, ok: true, summary } }, SECOND);
  };
  show(
    'c7b',
    'Showed 1 video: the boards cut together',
    'The boards cut together in black and white, three seconds each: no motion yet, only the order.',
    [{ kind: 'video', url: '/media/preview-boards.mp4', name: 'opening-boards.mp4', seconds: 6, width: 640, height: 360 }],
    { version: 'Boards cut' },
  );
  show('c8', 'Showed 1 file: the opening’s shot list', 'The opening as a shot list: six shots, 24 seconds.', [
    { kind: 'file', url: '/media/preview-shot-list.txt', name: 'opening-shot-list.txt' },
  ]);
  add({
    turn_id: t2,
    kind: 'tool_start',
    data: { call_id: 'c9', tool: 'filmcraft', title: 'FilmCraft: file.exportFrame' },
  });
  add(
    { turn_id: t2, kind: 'tool_end', data: { call_id: 'c9', ok: true, summary: 'FilmCraft: file.exportFrame done' } },
    2 * SECOND,
  );
  show('c10', 'Showed 1 image: shot 2', 'Shot 2, the violet flats: the frame the animatic cuts to at 0:03.', [
    { kind: 'image', url: '/media/discipline-experiences.webp', name: 'shot02-flats.png', width: 1200, height: 800 },
  ]);
  show(
    'c11',
    'Showed 2 images as before and after: the dusk grade',
    'Shot 1, Spire City: the reference as generated, and with the dusk grade I would give the film. Drag to compare.',
    [
      { kind: 'image', url: SPIRE.url, name: 'shot01-reference.png', width: 1200, height: 800 },
      { kind: 'image', url: '/media/preview-shot-graded.webp', name: 'shot01-graded.png', width: 1200, height: 800 },
    ],
    { compare: true },
  );
  add({
    turn_id: t2,
    kind: 'tool_start',
    data: { call_id: 'c12', tool: 'filmcraft', title: 'FilmCraft: file.exportMedia' },
  });
  add(
    {
      turn_id: t2,
      kind: 'tool_end',
      data: { call_id: 'c12', ok: true, summary: 'previews/opening-animatic-v1.mp4 · 144 frames at 640 × 360' },
    },
    4 * SECOND,
  );
  show(
    'c13',
    'Showed 1 video: the opening animatic',
    'Animatic of the wide opening: Spire City at dusk, then the violet flats. Six seconds, low resolution, no sound yet.',
    [
      {
        kind: 'video',
        url: '/media/preview-cut.mp4',
        name: 'opening-animatic-v1.mp4',
        seconds: 6,
        width: 640,
        height: 360,
      },
    ],
    { version: 'Animatic v1' },
  );
  add({
    turn_id: t2,
    kind: 'text',
    data: {
      text: 'That is the wide opening. The other two I can cut the same way once you have seen this one. One decision first:',
    },
  });
  add({
    turn_id: t2,
    kind: 'ask',
    data: {
      question: 'How should the film open?',
      options: [
        'Cold open on Pip in the workshop as the lights die',
        'Wide on the violet flats at dusk, then cut to the city',
        'Title card over the beacon’s last glow',
      ],
      recommended: 'Cold open on Pip in the workshop as the lights die',
    },
  });
  add({ turn_id: t2, kind: 'turn_end', data: {} }, SECOND);

  return events.map((event, index) => ({ event, at: times[index] ?? now }));
}

/**
 * The game's conversation: the agent starting an Unreal engine and putting its Desktop on the
 * screen, the developer cloning the game there, and the agent reporting what it found.
 *
 * @param start When the first turn starts.
 * @param cloned When the developer says the game is cloned, which starts the second.
 * @param engine The Unreal engine the agent started.
 * @returns The events, in order, with their times.
 */
function gameEvents(start: number, cloned: number, engine: Session): Scheduled[] {
  const first = 'game-turn-1';
  const second = 'game-turn-2';
  const step = (seconds: number, event: EventBody): Scheduled => ({ at: start + seconds * SECOND, event });
  const later = (seconds: number, event: EventBody): Scheduled => ({ at: cloned + seconds * SECOND, event });
  return [
    step(0, {
      turn_id: first,
      kind: 'user_message',
      data: { text: 'Our game, Ember Ridge, is on GitHub. Let’s work on it in Unreal.' },
    }),
    step(3, {
      turn_id: first,
      kind: 'text',
      data: {
        text: 'I’ll start Unreal Engine on a Pro machine, 4 credits a minute. It comes up as a desktop with the GitHub client, Git LFS, Firefox, and Blender, so the game comes in first.',
      },
    }),
    step(4, {
      turn_id: first,
      kind: 'tool_start',
      data: { call_id: 'g1', tool: 'engine_start', title: 'Starting Unreal Engine' },
    }),
    step(70, { turn_id: first, kind: 'engine', data: { engine } }),
    step(71, {
      turn_id: first,
      kind: 'tool_end',
      data: { call_id: 'g1', ok: true, summary: 'Unreal Engine is running' },
    }),
    step(72, {
      turn_id: first,
      kind: 'tool_start',
      data: { call_id: 'g2', tool: 'engine_show', title: 'Showing Desktop on the screen' },
    }),
    step(72.2, { turn_id: first, kind: 'screen', data: { engine_id: engine.id, stream: DESKTOP_STREAM } }),
    step(72.4, {
      turn_id: first,
      kind: 'tool_end',
      data: { call_id: 'g2', ok: true, summary: 'Desktop on the screen' },
    }),
    step(73, {
      turn_id: first,
      kind: 'text',
      data: {
        text: 'It’s up, and your screen shows its **Desktop**. Open the GitHub client there, sign in, and clone the game into the project’s folder under `projects/`, so the clone stays in your workspace. Git LFS comes along with it.',
      },
    }),
    step(74, { turn_id: first, kind: 'turn_end', data: {} }),
    later(0, { turn_id: second, kind: 'user_message', data: { text: 'Cloned it.' } }),
    later(2, {
      turn_id: second,
      kind: 'tool_start',
      data: { call_id: 'g3', tool: 'unreal_projects', title: 'Looking for Unreal projects in the engine' },
    }),
    later(3, {
      turn_id: second,
      kind: 'tool_end',
      data: { call_id: 'g3', ok: true, summary: 'EmberRidge (5.8, C++)' },
    }),
    later(5, {
      turn_id: second,
      kind: 'text',
      data: {
        text: 'Found it: **EmberRidge**, in `projects/demo-game/ember-ridge`.\n- **Unreal Engine 5.8**, this engine’s version, so it opens as it is.\n- **C++**: one module, `EmberRidge`, which compiles for Linux before the editor opens. The first build takes the longest.\n- **4 plugins**: Common UI, Enhanced Input, Gameplay Abilities, and Modeling Tools.\n- **Git LFS** for the assets, 3.2 GB in all.',
      },
    }),
    later(6, {
      turn_id: second,
      kind: 'ask',
      data: {
        question: 'Shall I open EmberRidge in Unreal?',
        options: ['Open it in Unreal', 'Not yet'],
        recommended: 'Open it in Unreal',
      },
    }),
    later(6.5, { turn_id: second, kind: 'turn_end', data: {} }),
  ];
}

/**
 * The demo agent's answer to being asked to open the game in Unreal: the editor opening and the
 * screen switching to it, or, without the Epic link, the steps that bring the editor.
 *
 * @param turn The turn.
 * @param at When each event is written, by seconds into the turn.
 * @param epicLinked Whether the demo's Epic connection is linked to Epic.
 * @returns The turn's events.
 */
function openInUnreal(turn: TurnId, at: (seconds: number) => number, epicLinked: boolean): Scheduled[] {
  if (!epicLinked) {
    const steps = (findApp('unreal')?.license?.steps ?? []).map((step, index) => `${index + 1}. ${step}`).join('\n');
    return [
      {
        at: at(1),
        event: {
          turn_id: turn,
          kind: 'tool_start',
          data: { call_id: `${turn}-u`, tool: 'unreal_open', title: 'Opening EmberRidge in Unreal' },
        },
      },
      {
        at: at(3),
        event: {
          turn_id: turn,
          kind: 'tool_end',
          data: { call_id: `${turn}-u`, ok: false, summary: 'The Unreal Editor needs the Epic link' },
        },
      },
      {
        at: at(4),
        event: {
          turn_id: turn,
          kind: 'text',
          data: {
            text: `The Unreal Editor runs on your own Epic account, and the GitHub account you connected for Epic isn’t linked to one yet. One step, in three parts:\n${steps}\n\nThen stop this Unreal engine and start it again: the start brings your own copy of the editor. The Desktop and your clone stay as they are.`,
          },
        },
      },
      { at: at(4.5), event: { turn_id: turn, kind: 'turn_end', data: {} } },
    ];
  }
  return [
    { at: at(1), event: { turn_id: turn, kind: 'text', data: { text: 'Opening EmberRidge in the Unreal Editor.' } } },
    {
      at: at(1.5),
      event: {
        turn_id: turn,
        kind: 'tool_start',
        data: { call_id: `${turn}-u`, tool: 'unreal_open', title: 'Opening EmberRidge in Unreal' },
      },
    },
    {
      at: at(4),
      event: {
        turn_id: turn,
        kind: 'tool_end',
        data: { call_id: `${turn}-u`, ok: true, summary: 'EmberRidge is opening in Unreal' },
      },
    },
    { at: at(4.2), event: { turn_id: turn, kind: 'screen', data: { engine_id: GAME_ENGINE, stream: UNREAL_STREAM } } },
    { at: at(4.4), event: { turn_id: turn, kind: 'plan', data: { items: gamePlan(true) } } },
    {
      at: at(5),
      event: {
        turn_id: turn,
        kind: 'text',
        data: {
          text: 'Your screen is on the **Unreal** view now. The C++ module compiles first, so the editor takes a few minutes this time. **Desktop** is one click away in the Screen panel, or Alt+1, for the GitHub client and Blender.',
        },
      },
    },
    { at: at(5.5), event: { turn_id: turn, kind: 'turn_end', data: {} } },
  ];
}

/** The score's plan as the demo opens. */
function scorePlan(): PlanItem[] {
  return [
    { id: 's1', title: 'Agree the brief: tempo, key, instruments, length', status: 'done' },
    { id: 's2', title: 'Write the theme’s first eight bars on piano', status: 'done' },
    { id: 's3', title: 'Choose where the theme goes next', status: 'active' },
    { id: 's4', title: 'Arrange, mix, and master to -14 LUFS', status: 'pending' },
  ];
}

/**
 * The score's conversation: the agent writing the first eight bars of a theme in SoundCraft,
 * bouncing them, and showing the bounce as a preview the person can play before deciding.
 *
 * @param start When the conversation began.
 * @param engine The SoundCraft engine the agent opened.
 * @returns The events, in order, with their times.
 */
function scoreEvents(start: number, engine: Session): Scheduled[] {
  const turn = 'score-1';
  const step = (seconds: number, event: EventBody): Scheduled => ({ at: start + seconds * SECOND, event });
  const call = (seconds: number, id: string, tool: string, title: string, took: number, summary: string): Scheduled[] => [
    step(seconds, { turn_id: turn, kind: 'tool_start', data: { call_id: id, tool, title } }),
    step(seconds + took, { turn_id: turn, kind: 'tool_end', data: { call_id: id, ok: true, summary } }),
  ];
  return [
    step(0, {
      turn_id: turn,
      kind: 'user_message',
      data: {
        text: 'A theme for a lighthouse keeper: slow, warm, a little lonely. About two minutes. Start with piano alone.',
      },
    }),
    step(6, {
      turn_id: turn,
      kind: 'text',
      data: {
        text:
          'A slow theme in A minor at 72 BPM, in four-bar phrases, the melody leaving room at the end of each. ' +
          'I will write the first eight bars on piano in SoundCraft and play them to you before going further.',
      },
    }),
    step(8, { turn_id: turn, kind: 'plan', data: { items: scorePlan() } }),
    step(10, {
      turn_id: turn,
      kind: 'tool_start',
      data: { call_id: 'm1', tool: 'engine_start', title: 'Starting SoundCraft' },
    }),
    step(24, { turn_id: turn, kind: 'engine', data: { engine } }),
    step(25, {
      turn_id: turn,
      kind: 'tool_end',
      data: { call_id: 'm1', ok: true, summary: 'SoundCraft is running' },
    }),
    ...call(30, 'm2', 'engine_call', 'SoundCraft: engine.execute', 38, 'Tempo 72, A minor, one piano track, 34 notes'),
    ...call(72, 'm3', 'engine_call', 'SoundCraft: engine.execute', 2, 'previews/theme-bars-1-8.wav · 10.2 s · -19.3 LUFS'),
    step(76, {
      turn_id: turn,
      kind: 'tool_start',
      data: { call_id: 'm4', tool: 'preview', title: 'Preparing a preview' },
    }),
    step(79, {
      turn_id: turn,
      kind: 'preview',
      data: {
        engine_id: engine.id,
        caption: 'The theme’s first eight bars, piano alone: A minor, 72 BPM, nothing mixed yet.',
        items: [{ kind: 'audio', url: '/media/preview-theme.m4a', name: 'theme-bars-1-8.wav', seconds: 10.2 }],
        compare: false,
        version: 'First eight bars',
      },
    }),
    step(80, {
      turn_id: turn,
      kind: 'tool_end',
      data: { call_id: 'm4', ok: true, summary: 'Showed 1 audio: the theme’s first eight bars' },
    }),
    step(84, {
      turn_id: turn,
      kind: 'text',
      data: {
        text:
          'Play the eight bars above. They sit at -19.3 LUFS with peaks at -4.8 dBFS, so there is room for strings. ' +
          'The second phrase answers the first a third lower; tell me if it should rise instead.',
      },
    }),
    step(86, {
      turn_id: turn,
      kind: 'ask',
      data: {
        question: 'Where should the theme go next?',
        options: [
          'Repeat it with strings under the piano',
          'A second, brighter section in C major',
          'Keep it piano alone and let it breathe',
        ],
        recommended: 'Repeat it with strings under the piano',
      },
    }),
    step(87, { turn_id: turn, kind: 'turn_end', data: {} }),
  ];
}

/** The demo's projects, as the sidebar lists them. */
function demoProjects(now: number): Project[] {
  const project = (
    fields: Pick<Project, 'id' | 'name' | 'discipline' | 'format'> & Partial<Project>,
    age: number,
  ): Project => ({
    pinned: false,
    github_repo: null,
    library_sections: [],
    plan: [],
    created_at: new Date(now - age - 2 * DAY).toISOString(),
    updated_at: new Date(now - age).toISOString(),
    ...fields,
  });
  return [
    project(
      {
        id: 'demo-film',
        name: 'The Beacon',
        discipline: 'media',
        format: 'Movie',
        pinned: true,
        github_repo: `${LOGIN}/the-beacon`,
        library_sections: ['Characters', 'Environments', 'Props'],
        plan: filmPlan('opening'),
      },
      4 * MINUTE,
    ),
    project(
      {
        id: 'demo-commercial',
        name: 'Northwind runner launch',
        discipline: 'media',
        format: 'Commercial',
        pinned: true,
        library_sections: ['Products', 'Shots'],
      },
      2 * DAY,
    ),
    project(
      {
        id: 'demo-game',
        name: 'Ember Ridge',
        discipline: 'games',
        format: 'Game',
        library_sections: ['Environments', 'Props'],
        plan: gamePlan(false),
      },
      6 * MINUTE,
    ),
    project(
      { id: 'demo-interior', name: 'Glasshouse retreat', discipline: 'architecture', format: 'Interior' },
      5 * HOUR,
    ),
    project({ id: 'demo-vertical', name: 'Spire City', discipline: 'media', format: 'Vertical drama' }, DAY + 3 * HOUR),
    project({ id: 'demo-art', name: 'Ember peaks key art', discipline: 'art', format: 'Concept art' }, 3 * DAY),
    project(
      { id: 'demo-score', name: 'Lighthouse theme', discipline: 'music', format: 'Score', plan: scorePlan() },
      8 * MINUTE,
    ),
  ];
}

/** The repositories the demo's GitHub account has. */
function demoRepos(now: number): GitHubRepo[] {
  return [
    {
      full_name: `${LOGIN}/the-beacon`,
      private: true,
      html_url: `https://github.com/${LOGIN}/the-beacon`,
      updated_at: new Date(now - 4 * MINUTE).toISOString(),
    },
    {
      full_name: `${LOGIN}/northwind-launch`,
      private: true,
      html_url: `https://github.com/${LOGIN}/northwind-launch`,
      updated_at: new Date(now - 2 * DAY).toISOString(),
    },
    {
      full_name: `${LOGIN}/portfolio`,
      private: false,
      html_url: `https://github.com/${LOGIN}/portfolio`,
      updated_at: new Date(now - 9 * DAY).toISOString(),
    },
  ];
}

/**
 * An event as one reading of the log returns it: each file it carries under an address of that
 * reading, the way the control plane signs a file afresh for each one.
 *
 * @param event The event as it was written.
 * @param read Which reading of the log this is.
 * @returns The event with that reading's addresses.
 */
function readAs(event: EventBody, read: number): EventBody {
  const sign = <File extends { url: string }>(file: File): File => ({
    ...file,
    url: `${file.url}${file.url.includes('?') ? '&' : '?'}read=${read}`,
  });
  switch (event.kind) {
    case 'tool_end':
      return event.data.media === undefined ? event : { ...event, data: { ...event.data, media: event.data.media.map(sign) } };
    case 'preview':
      return { ...event, data: { ...event.data, items: event.data.items.map(sign) } };
    case 'ui':
      return { ...event, data: { ...event.data, media: event.data.media.map(sign) } };
    default:
      return event;
  }
}

/** The skill every project's agent reads in the demo. */
const STUDIO_SKILL: SkillInfo = {
  name: 'studio',
  description: 'How a production runs across engines, and how work moves between them as files.',
};

/** The skill a film's agent reads in the demo. */
const MOVIE_SKILL: SkillInfo = {
  name: 'movie',
  description: 'A film from idea to cut: the story, the cast, and the art style first, then shots, then the edit.',
};

/** What the skill of each engine that has one teaches, by the engine's app. */
const ENGINE_SKILLS: Readonly<Record<string, string | undefined>> = {
  filmcraft: 'Cutting, color, sound, titles, and export in FilmCraft.',
  photocraft: 'Layers, masks, retouching, and key art in PhotoCraft.',
  soundcraft: 'Writing, arranging, mixing, and mastering in SoundCraft.',
  lightcraft: 'Developing and grading photographs in LightCraft.',
  vectorcraft: 'Logos, identities, and patterns in VectorCraft.',
  cadcraft: 'Drafting buildings and products in CADCraft.',
  unreal: 'Opening, building, and working in Unreal projects.',
};

/**
 * Picks what the demo's agent says to a message, by what the message is.
 *
 * @param project The project.
 * @param text The person's message.
 * @param turn The turn it starts.
 * @param start When the turn starts.
 * @param epicLinked Whether the demo's Epic connection is linked to Epic.
 * @param history What was written in the project before this message.
 * @param limits The account's limits for a turn.
 * @returns The turn.
 */
function reply(
  project: Project,
  text: string,
  turn: TurnId,
  start: number,
  epicLinked: boolean,
  history: readonly Scheduled[],
  limits: TurnLimits,
): Script {
  const at = (seconds: number): number => start + seconds * SECOND;
  if (project.id === MOVIE_PROJECT) {
    return movieTurn(history, turn, start, limits);
  }
  if (project.id === 'demo-game' && /\bopen\b.*\bunreal\b/i.test(text)) {
    return { events: openInUnreal(turn, at, epicLinked) };
  }
  const opening = /cold open|workshop|violet flats|title card/i.test(text) && project.id === 'demo-film';
  if (opening) {
    return { events: filmOpening(turn, at) };
  }
  return {
    events: [
      {
        at: at(1.5),
        event: {
          turn_id: turn,
          kind: 'text',
          data: {
            text: 'Got it. This is the demo, so nothing is generated here, but in a real project I would get to work now and check in with you before any decision that is yours.',
          },
        },
      },
      { at: at(2), event: { turn_id: turn, kind: 'turn_end', data: {} } },
    ],
  };
}

/**
 * The film agent's answer to how the film should open: the shot list for scene 1.
 *
 * @param turn The turn.
 * @param at When each event is written, by seconds into the turn.
 * @returns The turn's events.
 */
function filmOpening(turn: TurnId, at: (seconds: number) => number): Scheduled[] {
  return [
    {
      at: at(1.2),
      event: {
        turn_id: turn,
        kind: 'text',
        data: {
          text: 'Good call. Opening on @pip keeps us close to him from the first frame, and the lights dying behind him sets the clock running. Writing the shot list for scene 1 now.',
        },
      },
    },
    {
      at: at(2),
      event: {
        turn_id: turn,
        kind: 'tool_start',
        data: { call_id: `${turn}-a`, tool: 'github_save', title: 'Shot list for scene 1' },
      },
    },
    {
      at: at(4.5),
      event: {
        turn_id: turn,
        kind: 'tool_end',
        data: { call_id: `${turn}-a`, ok: true, summary: 'shots.md · 6 shots · 0:52' },
      },
    },
    { at: at(4.8), event: { turn_id: turn, kind: 'plan', data: { items: filmPlan('answered') } } },
    {
      at: at(5.6),
      event: {
        turn_id: turn,
        kind: 'text',
        data: {
          text: '### Scene 1\n- **1A** Close on @pip’s hands at the bench, the workshop lamp flickering.\n- **1B** The window: Spire City’s towers going dark, block by block.\n- **1C** @beacon on the shelf, cold.\n\nShall I generate 1A to 1C with Seedance, using the references in the library?',
        },
      },
    },
    { at: at(6), event: { turn_id: turn, kind: 'turn_end', data: {} } },
  ];
}

/**
 * Builds a control plane that answers from memory.
 *
 * @param scene The state to open in, as the page's `demo` parameter gave it.
 * @returns The control plane.
 */
export function createDemoControlPlane(scene: string | null): ControlPlane {
  const opened = Date.now();
  const legacy = scene === 'legacy';
  const offline = scene === 'offline';
  const epicLinked = scene !== 'no-epic';
  const atLimit = scene === 'limit';
  const movie = scene === 'movie' || atLimit;
  let projects = scene === 'empty' ? [] : [...(movie ? [movieProject(opened)] : []), ...demoProjects(opened)];
  const libraries = new Map<string, Asset[]>([['demo-film', filmLibrary(opened)]]);
  const filmSimulation: Simulation = {
    id: 'demo-engine-1',
    project: 'demo-film',
    app: 'filmcraft',
    tier: 't4',
    phases: [
      { at: opened - 11 * MINUTE - 40 * SECOND, status: 'queued' },
      { at: opened - 11 * MINUTE - 30 * SECOND, status: 'starting' },
      { at: opened - 11 * MINUTE, status: 'running' },
    ],
  };
  const gameStart = opened - 25 * MINUTE;
  const gameCloned = opened - 6 * MINUTE;
  const gameSimulation: Simulation = {
    id: GAME_ENGINE,
    project: 'demo-game',
    app: 'unreal',
    tier: 'l4',
    phases: [
      { at: gameStart + 5 * SECOND, status: 'starting' },
      { at: gameStart + 70 * SECOND, status: 'running' },
    ],
    streams: demoStreams('unreal'),
  };
  const scoreStart = opened - 10 * MINUTE;
  const scoreSimulation: Simulation = {
    id: 'demo-engine-3',
    project: 'demo-score',
    app: 'soundcraft',
    tier: 'cpu',
    phases: [
      { at: scoreStart + 10 * SECOND, status: 'starting' },
      { at: scoreStart + 24 * SECOND, status: 'running' },
    ],
  };
  let simulations: Simulation[] = [filmSimulation, gameSimulation, scoreSimulation];
  const logs = new Map<string, Scheduled[]>([
    ['demo-film', filmEvents(opened, libraries.get('demo-film') ?? [], snapshot(filmSimulation, opened - 11 * MINUTE))],
    ['demo-game', gameEvents(gameStart, gameCloned, snapshot(gameSimulation, gameStart + 70 * SECOND))],
    ['demo-score', scoreEvents(scoreStart, snapshot(scoreSimulation, scoreStart + 24 * SECOND))],
  ]);
  /** The demo's GitHub account, connected. */
  const demoGitHub: GitHubStatus = { configured: true, connected: true, login: LOGIN, avatar_url: AVATAR };
  let github: GitHubStatus = offline
    ? { configured: false, connected: false, login: null, avatar_url: null }
    : demoGitHub;
  /** The demo's Epic connection, the same account, linked to Epic unless the scene says otherwise. */
  const demoEpic: EpicStatus = { configured: true, connected: true, login: LOGIN, linked: epicLinked, detail: null };
  let epic: EpicStatus = offline
    ? { configured: false, connected: false, login: null, linked: null, detail: null }
    : demoEpic;
  let keys: ApiKey[] = [
    {
      id: 'demo-key-1',
      name: 'Claude on my laptop',
      prefix: 'moody_3f9aQ2',
      created_at: new Date(opened - 6 * DAY).toISOString(),
      last_used_at: new Date(opened - 2 * HOUR).toISOString(),
    },
  ];
  let counter = 100;
  let reads = 0;
  /** What the account set of a turn's limits itself. */
  let own: Limits['own'] = { turn_budget_usd: atLimit ? LOW_BUDGET_USD : null, turn_limit: null };
  /**
   * The account's limits for a turn: what it set, and the deployment's default where it set nothing.
   *
   * @returns The limits, as the control plane reports them.
   */
  const limits = (): Limits => ({
    turn_budget_usd: own.turn_budget_usd ?? DEFAULT_LIMITS.turn_budget_usd,
    turn_limit: own.turn_limit ?? DEFAULT_LIMITS.turn_limit,
    own,
    default: DEFAULT_LIMITS,
    max: MAX_LIMITS,
  });
  /**
   * The account, with its limits unless the control plane is one from before the studio.
   *
   * @returns The account.
   */
  const me = (): Me => ({
    id: 'demo-user',
    email: DEMO_EMAIL,
    credits: 412,
    max_sessions: 3,
    ...(legacy ? {} : { limits: limits() }),
  });
  const health: Health = {
    ok: true,
    agent: !offline,
    github: !offline,
    epic: !offline,
    generation: !offline,
    billing: false,
    tiers: catalog.tiers.slice(0, Math.max(1, catalog.tiers.length - 1)).map((tier) => tier.id),
  };

  /** Refuses a studio route the way a control plane from before the studio does. */
  const missing = (): Promise<never> => Promise.reject(new ApiError(404, 'Not Found'));

  /**
   * Finds a project.
   *
   * @param id The project's identifier.
   * @returns The project.
   * @throws ApiError With status 404 for an unknown project.
   */
  function find(id: string): Project {
    const project = projects.find((candidate) => candidate.id === id);
    if (project === undefined) {
      throw new ApiError(404, 'No such project.');
    }
    return project;
  }

  /**
   * Changes a project and returns it.
   *
   * @param id The project's identifier.
   * @param changes The fields to change.
   * @returns The changed project.
   */
  function change(id: string, changes: Partial<Project>): Project {
    const next = { ...find(id), ...changes };
    projects = projects.map((project) => (project.id === id ? next : project));
    return next;
  }

  /**
   * The log of a project, with every event's place in it.
   *
   * @param id The project's identifier.
   * @returns The events, numbered from one.
   */
  function log(id: string): Scheduled[] {
    const entries = logs.get(id);
    if (entries !== undefined) {
      return entries;
    }
    const fresh: Scheduled[] = [];
    logs.set(id, fresh);
    return fresh;
  }

  /**
   * Applies what an event written now describes, as the real agent's tools would: the plan and the
   * library's sections are the project's, and an asset is in its library.
   *
   * @param project The project.
   * @param scheduled The event.
   */
  function apply(project: string, scheduled: Scheduled): void {
    const { event } = scheduled;
    if (!log(project).includes(scheduled)) {
      // The turn was stopped before this event's time came.
      return;
    }
    if (event.kind === 'plan') {
      change(project, { plan: event.data.items });
    } else if (event.kind === 'library') {
      if ('asset' in event.data) {
        store(project, event.data.asset);
      } else {
        change(project, { library_sections: event.data.sections });
      }
    }
  }

  /** The turns waiting for the person's answer to an approval, by project. */
  const pauses = new Map<string, Pause>();

  /**
   * Sets a turn, or the rest of one, going: its events are written as their times come, its
   * engines start, and where it asks before a tool it waits there, unless the person always
   * allows that tool in this project, which goes on without asking.
   *
   * @param projectId The project.
   * @param script The turn.
   */
  function play(projectId: string, script: Script): void {
    const now = Date.now();
    const events = [...script.events];
    const engines = [...(script.engines ?? [])];
    let pause = script.pause;
    while (pause !== undefined && find(projectId).permissions?.[pause.approval.tool] === ALWAYS) {
      const rest = pause.resume(ALWAYS, pause.at);
      events.push(...rest.events);
      engines.push(...(rest.engines ?? []));
      pause = rest.pause;
    }
    if (pause !== undefined) {
      events.push({ at: pause.at, event: { turn_id: pause.turn, kind: 'approval', data: pause.approval } });
      pauses.set(projectId, pause);
    }
    simulations = [...simulations, ...engines];
    // The log numbers its events in the order they are written, so a turn goes in by time.
    events.sort((a, b) => a.at - b.at);
    log(projectId).push(...events);
    for (const entry of events) {
      window.setTimeout(
        () => {
          apply(projectId, entry);
        },
        Math.max(0, entry.at - now),
      );
    }
  }

  /**
   * What a project's agent works with in the demo: generation, the web, the person's GitHub, Epic
   * for a discipline that uses Unreal Engine, and the discipline's subagents and skills.
   *
   * @param project The project.
   * @returns Its environment.
   */
  function environmentOf(project: Project): Environment {
    const engines = findDiscipline(project.discipline)?.engines ?? [];
    const connectors: Connector[] = [
      {
        id: 'fal',
        name: 'fal',
        kind: 'generation',
        state: offline ? 'off' : 'connected',
        detail: offline ? 'Not configured on this server' : 'Image and video models, billed in credits',
      },
      { id: 'web', name: 'Web search', kind: 'search', state: 'connected', detail: 'Searches and reads the web for references' },
      {
        id: 'github',
        name: 'GitHub',
        kind: 'repository',
        state: !github.configured ? 'off' : github.connected ? 'connected' : 'available',
        detail: !github.configured
          ? 'Not configured on this server'
          : github.connected
            ? `Connected as ${github.login ?? LOGIN}`
            : 'Connect it to keep the project’s documents in a repository',
      },
    ];
    if (engines.includes('unreal')) {
      connectors.push({
        id: 'epic',
        name: 'Epic Games',
        kind: 'license',
        state: !epic.configured ? 'off' : epic.linked === true ? 'connected' : 'available',
        detail: epic.linked === true ? 'Your own Unreal Editor comes with an Unreal engine' : 'Link it for your own Unreal Editor',
      });
    }
    const film = FILM_DISCIPLINES.has(project.discipline);
    return {
      connectors,
      agents: film ? MOVIE_AGENTS : MOVIE_AGENTS.filter((agent) => agent.name === 'research'),
      skills: [
        STUDIO_SKILL,
        ...(film ? [MOVIE_SKILL] : []),
        ...engines.flatMap((engine) => {
          const description = ENGINE_SKILLS[engine];
          return description === undefined ? [] : [{ name: engine, description }];
        }),
      ],
    };
  }

  if (movie) {
    play(MOVIE_PROJECT, atLimit ? movieSoFar(opened, limits()) : movieOpening(opened));
  }

  /**
   * A media file's kind, by its type.
   *
   * @param file The file.
   * @returns Its kind.
   */
  function kindOf(file: File): Media['kind'] {
    if (file.type.startsWith('image/')) {
      return 'image';
    }
    if (file.type.startsWith('video/')) {
      return 'video';
    }
    return file.type.startsWith('audio/') ? 'audio' : 'file';
  }

  /**
   * Finds an asset of a project.
   *
   * @param projectId The project.
   * @param assetId The asset.
   * @returns The asset.
   * @throws ApiError With status 404 for an unknown asset.
   */
  function findAsset(projectId: string, assetId: string): Asset {
    const found = libraries.get(projectId)?.find((entry) => entry.id === assetId);
    if (found === undefined) {
      throw new ApiError(404, 'No such asset.');
    }
    return found;
  }

  /**
   * Puts an asset in a project's library.
   *
   * @param projectId The project.
   * @param entry The asset.
   * @returns The asset.
   */
  function store(projectId: string, entry: Asset): Asset {
    const library = libraries.get(projectId) ?? [];
    libraries.set(
      projectId,
      library.some((other) => other.id === entry.id)
        ? library.map((other) => (other.id === entry.id ? entry : other))
        : [...library, entry],
    );
    return entry;
  }

  /** Answers after a moment, as a request over the network would. */
  const soon = <T>(value: () => T, delay = 250): Promise<T> =>
    new Promise((resolve, reject) => {
      window.setTimeout(() => {
        try {
          resolve(value());
        } catch (failure) {
          reject(failure instanceof Error ? failure : new Error(String(failure)));
        }
      }, delay);
    });

  return {
    health: () => Promise.resolve(health),
    me: () => Promise.resolve(me()),
    updateMe: (changes) =>
      legacy
        ? missing()
        : soon(() => {
            const budget = changes.turn_budget_usd;
            const steps = changes.turn_limit;
            for (const value of [budget, steps]) {
              if (typeof value === 'number' && !(value > 0)) {
                throw new ApiError(400, 'A limit is a positive number, or null for the default.');
              }
            }
            if (typeof budget === 'number' && budget > MAX_LIMITS.turn_budget_usd) {
              throw new ApiError(400, `A turn may spend at most ${usd(MAX_LIMITS.turn_budget_usd)} here.`);
            }
            if (typeof steps === 'number' && !Number.isInteger(steps)) {
              throw new ApiError(400, 'A turn’s steps are a whole number.');
            }
            if (typeof steps === 'number' && steps > MAX_LIMITS.turn_limit) {
              throw new ApiError(400, `A turn may take at most ${creditCount(MAX_LIMITS.turn_limit)} steps here.`);
            }
            own = {
              turn_budget_usd: budget === undefined ? own.turn_budget_usd : budget,
              turn_limit: steps === undefined ? own.turn_limit : steps,
            };
            return me();
          }),
    sessionLink: () => Promise.reject(new ApiError(NOT_CONFIGURED, 'The demo has no stream to open.')),
    stopSession: (id) =>
      soon(() => {
        const simulation = simulations.find((candidate) => candidate.id === id);
        if (simulation === undefined) {
          throw new ApiError(404, 'No such engine.');
        }
        const now = Date.now();
        simulation.phases = [
          ...simulation.phases.filter((phase) => phase.at <= now),
          { at: now, status: 'ended', reason: 'user' },
        ];
        return snapshot(simulation, now);
      }),
    listApiKeys: () => Promise.resolve(keys),
    createApiKey: (name) =>
      soon(() => {
        counter += 1;
        const key: ApiKey = {
          id: `demo-key-${counter}`,
          name,
          prefix: 'moody_demo00',
          created_at: new Date().toISOString(),
          last_used_at: null,
        };
        keys = [key, ...keys];
        return { key, secret: 'moody_demo_sample_key_not_a_real_secret' };
      }),
    revokeApiKey: (id) =>
      soon(() => {
        keys = keys.filter((key) => key.id !== id);
      }),
    checkout: () => Promise.reject(new ApiError(NOT_CONFIGURED, 'The demo has no checkout.')),

    listProjects: () => (legacy ? missing() : soon(() => projects, 350)),
    createProject: (fields) =>
      soon(() => {
        counter += 1;
        const now = new Date().toISOString();
        const discipline = findDiscipline(fields.discipline);
        const project: Project = {
          id: `demo-project-${counter}`,
          name: fields.name ?? 'Untitled project',
          discipline: fields.discipline,
          format: fields.format ?? '',
          pinned: false,
          created_at: now,
          updated_at: now,
          github_repo: fields.github_repo ?? null,
          library_sections: [],
          plan: [],
        };
        projects = [project, ...projects];
        // A project without a format opens on the card that asks its kind, written with no turn.
        const card =
          fields.format === undefined && discipline !== undefined ? kindCard(discipline, `${project.id}-kind`) : null;
        if (card !== null) {
          log(project.id).push({ at: Date.now(), event: { turn_id: null, kind: 'ui', data: card } });
        }
        return project;
      }, 500),
    getProject: (id) => (legacy ? missing() : soon(() => find(id))),
    updateProject: (id, changes) =>
      soon(() =>
        change(id, {
          ...changes,
          ...(changes.name === undefined ? {} : { updated_at: new Date().toISOString() }),
        }),
      ),
    deleteProject: (id) =>
      soon(() => {
        find(id);
        projects = projects.filter((project) => project.id !== id);
      }),
    listEngines: (projectId) =>
      legacy
        ? missing()
        : soon(() =>
            simulations
              .filter((simulation) => simulation.project === projectId)
              .map((simulation) => snapshot(simulation, Date.now())),
          ),
    startEngine: (projectId, request) =>
      soon(() => {
        find(projectId);
        const now = Date.now();
        counter += 1;
        const simulation: Simulation = {
          id: `demo-engine-${counter}`,
          project: projectId,
          app: request.app,
          tier: request.tier,
          phases: [
            { at: now, status: 'queued' },
            { at: now + 4 * SECOND, status: 'starting' },
            { at: now + 12 * SECOND, status: 'running' },
          ],
          streams: demoStreams(request.app),
        };
        simulations = [...simulations, simulation];
        return snapshot(simulation, now);
      }, 700),
    unrealProjects: (projectId, engineId) =>
      legacy
        ? missing()
        : soon(() => {
            const simulation = simulations.find(
              (candidate) => candidate.id === engineId && candidate.project === projectId,
            );
            const now = Date.now();
            if (simulation?.app !== 'unreal' || snapshot(simulation, now).status !== 'running') {
              throw new ApiError(409, 'That engine is not a running Unreal engine.');
            }
            return engineId === GAME_ENGINE && now >= gameCloned ? [EMBER_RIDGE] : [];
          }, 300),
    listEvents: (projectId, after) => {
      if (legacy) {
        return missing();
      }
      return soon(() => {
        find(projectId);
        const now = Date.now();
        const entries = log(projectId);
        const events: StudioEvent[] = [];
        reads += 1;
        entries.forEach((scheduled, index) => {
          const id = index + 1;
          if (scheduled.at <= now && id > after) {
            events.push({ ...readAs(scheduled.event, reads), id, created_at: new Date(scheduled.at).toISOString() });
          }
        });
        const running = pauses.has(projectId) || entries.some((scheduled) => scheduled.at > now);
        return { events, running, cursor: events.at(-1)?.id ?? null };
      }, 120);
    },
    sendMessage: (projectId, text, ui) =>
      soon(() => {
        find(projectId);
        const entries = log(projectId);
        const now = Date.now();
        if (pauses.has(projectId) || entries.some((scheduled) => scheduled.at > now)) {
          throw new ApiError(409, 'A turn is already running.');
        }
        counter += 1;
        const turn = `turn-${counter}`;
        const message: Scheduled = {
          at: now,
          event: { turn_id: turn, kind: 'user_message', data: ui === undefined ? { text } : { text, ui } },
        };
        // The message that locks the card asking the project's kind gives the project its format first.
        const locked = entries.find(({ event }) => event.kind === 'ui' && event.data.ui_id === ui?.ui_id)?.event;
        const kind = locked?.kind === 'ui' ? chosenKind(locked.data, ui?.value) : null;
        const project = kind === null ? find(projectId) : change(projectId, { format: kind });
        const answer = reply(project, text, turn, now, epicLinked, entries, limits());
        play(projectId, { ...answer, events: [message, ...answer.events] });
        change(projectId, { updated_at: new Date(now).toISOString() });
        return turn;
      }),
    stopTurn: (projectId) =>
      soon(() => {
        const now = Date.now();
        const entries = log(projectId).filter((scheduled) => scheduled.at <= now);
        const last = entries.at(-1);
        const pause = pauses.get(projectId);
        if (pause !== undefined && pause.at <= now) {
          entries.push({
            at: now,
            event: {
              turn_id: pause.turn,
              kind: 'approval_result',
              data: { approval_id: pause.approval.approval_id, decision: 'expired' },
            },
          });
        }
        pauses.delete(projectId);
        if (last !== undefined && last.event.kind !== 'turn_end') {
          entries.push({ at: now, event: { turn_id: last.event.turn_id, kind: 'turn_end', data: {} } });
        }
        logs.set(projectId, entries);
      }),
    approve: (projectId, approvalId, decision) =>
      soon(() => {
        const project = find(projectId);
        const pause = pauses.get(projectId);
        const now = Date.now();
        if (pause?.approval.approval_id !== approvalId || pause.at > now) {
          return false;
        }
        pauses.delete(projectId);
        if (decision === ALWAYS) {
          change(projectId, { permissions: { ...project.permissions, [pause.approval.tool]: ALWAYS } });
        }
        const rest = pause.resume(decision, now);
        play(projectId, {
          ...rest,
          events: [
            { at: now, event: { turn_id: pause.turn, kind: 'approval_result', data: { approval_id: approvalId, decision } } },
            ...rest.events,
          ],
        });
        return true;
      }, 200),
    environment: (projectId) => (legacy ? missing() : soon(() => environmentOf(find(projectId)), 300)),
    getLibrary: (projectId) =>
      legacy
        ? missing()
        : soon(() => {
            const project = find(projectId);
            return { sections: project.library_sections, assets: libraries.get(projectId) ?? [] };
          }),
    createAsset: (projectId, fields) =>
      soon(() => {
        const project = find(projectId);
        counter += 1;
        if (!project.library_sections.includes(fields.section)) {
          change(projectId, { library_sections: [...project.library_sections, fields.section] });
        }
        return store(
          projectId,
          asset(
            {
              id: `demo-asset-${counter}`,
              section: fields.section,
              name: fields.name,
              tag: fields.tag ?? null,
              description: fields.description ?? null,
              media: [],
              ...(fields.metadata === undefined ? {} : { metadata: fields.metadata }),
            },
            Date.now(),
          ),
        );
      }),
    uploadMedia: (projectId, assetId, file) =>
      soon(() => {
        const entry = findAsset(projectId, assetId);
        const media: Media = { kind: kindOf(file), url: URL.createObjectURL(file), name: file.name };
        const next: Asset = {
          ...entry,
          media: [...entry.media, media],
          thumbnail_url: entry.thumbnail_url ?? (media.kind === 'image' ? media.url : null),
          updated_at: new Date().toISOString(),
        };
        return store(projectId, next);
      }, 600),
    deleteAsset: (projectId, assetId) =>
      soon(() => {
        findAsset(projectId, assetId);
        libraries.set(
          projectId,
          (libraries.get(projectId) ?? []).filter((entry) => entry.id !== assetId),
        );
      }),
    github: () => (legacy ? missing() : Promise.resolve(github)),
    connectGitHub: () =>
      soon(() => {
        github = demoGitHub;
        throw new ApiError(NOT_CONFIGURED, 'The demo connects without leaving the page: reload to see it connected.');
      }),
    installGitHub: () =>
      Promise.reject(new ApiError(NOT_CONFIGURED, 'The demo has no GitHub App to install: its repositories are all listed.')),
    githubRepos: () => soon(() => demoRepos(opened), 400),
    disconnectGitHub: () =>
      soon(() => {
        github = { ...github, connected: false, login: null, avatar_url: null };
      }),
    linkRepo: (projectId, link) =>
      soon(() => change(projectId, { github_repo: link.repo, github_branch: link.branch ?? null }), 600),
    unlinkRepo: (projectId) => soon(() => change(projectId, { github_repo: null, github_branch: null })),
    epic: () => (legacy ? missing() : Promise.resolve(epic)),
    connectEpic: () =>
      soon(() => {
        epic = demoEpic;
        throw new ApiError(NOT_CONFIGURED, 'The demo connects without leaving the page: reload to see it connected.');
      }),
    disconnectEpic: () =>
      soon(() => {
        epic = { ...epic, connected: false, login: null, linked: null, detail: null };
      }),
  };
}
