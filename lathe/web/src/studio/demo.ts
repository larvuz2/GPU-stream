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
 * The sample is a short animated film part way through the film workflow (`lathe/STUDIO.md`): a
 * script written, a bible of characters, environments, and props with reference images, FilmCraft
 * open, and the agent asking how the film should open. Time moves as it would: a message sent
 * here starts a turn whose events arrive over a few seconds, under the studio's own polling, and
 * an engine started here queues, starts, and runs. The images are the site's own artwork.
 *
 * The scene parameter (`?demo=<scene>`) picks a state: the film by default, `offline` for a
 * server with no integrations configured, `empty` for an account with no projects, and `legacy`
 * for a control plane from before the studio, which answers its routes with 404.
 * @module
 */
import {
  ApiError,
  type ApiKey,
  type Asset,
  type ControlPlane,
  type GitHubRepo,
  type GitHubStatus,
  type Health,
  type Media,
  type Me,
  type PlanItem,
  type Project,
  type Session,
  type SessionStatus,
  type StudioEvent,
  type TurnId,
} from '../lib/api';
import { catalog } from '../lib/catalog';

/** The address the demo's account is shown under. */
export const DEMO_EMAIL = 'you@example.com';

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** The status a refusal of the demo carries: a feature it does not have. */
const NOT_CONFIGURED = 503;

/** The GitHub login the demo is connected as. */
const LOGIN = 'lathe-demo';

/** An avatar drawn inline, so the demo fetches nothing. */
const AVATAR = `data:image/svg+xml,${encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop stop-color='#ffb070'/><stop offset='1' stop-color='#8b5cf6'/></linearGradient></defs><rect width='64' height='64' fill='url(#g)'/><text x='32' y='41' font-family='system-ui,sans-serif' font-size='26' font-weight='700' text-anchor='middle' fill='#1c0d02'>L</text></svg>",
)}`;

/** A still of the site's artwork, as a media file. */
const still = (file: string, name: string): Media => ({ kind: 'image', url: `/media/${file}`, name });

const PIP = still('character-theo.webp', 'pip-reference.webp');
const MARA = still('character-mara.webp', 'mara-reference.webp');
const GLASSHOUSE = still('discipline-architecture.webp', 'glasshouse.webp');
const SPIRE = still('discipline-media.webp', 'spire-city.webp');
const PEAKS = still('discipline-experiences.webp', 'ember-peaks-concept.webp');
const BEACON = still('discipline-art.webp', 'beacon.webp');
const RUNNERS = still('discipline-fashion.webp', 'runners.webp');

/** One state of a simulated engine, entered at a point in time. */
interface Phase {
  /** When the state is entered, in milliseconds since the epoch. */
  at: number;
  /** The state. */
  status: SessionStatus;
  /** Why it ended, for a final state. */
  reason?: string;
}

/** A simulated engine: what it runs, for which project, and the states it passes through. */
interface Simulation {
  /** The engine's identifier. */
  id: string;
  /** Its project. */
  project: string;
  /** The catalog app. */
  app: string;
  /** The catalog tier. */
  tier: string;
  /** The states, in the order they are entered. */
  phases: Phase[];
}

/**
 * Reads a simulated engine at a point in time.
 *
 * @param simulation The engine's schedule.
 * @param now The time to read it at.
 * @returns The engine as the control plane would report it then.
 */
function snapshot(simulation: Simulation, now: number): Session {
  const reached = simulation.phases.filter((phase) => phase.at <= now);
  const first = simulation.phases[0];
  const current = reached.at(-1) ?? first;
  const started = reached.find((phase) => phase.status === 'running');
  const ended = reached.find((phase) => phase.status === 'ended' || phase.status === 'failed');
  const rate = catalog.tiers.find((tier) => tier.id === simulation.tier)?.credits_per_minute ?? 0;
  return {
    id: simulation.id,
    project_id: simulation.project,
    app: simulation.app,
    tier: simulation.tier,
    region: 'auto',
    status: current?.status ?? 'ended',
    created_at: new Date(first?.at ?? now).toISOString(),
    started_at: started === undefined ? null : new Date(started.at).toISOString(),
    ended_at: ended === undefined ? null : new Date(ended.at).toISOString(),
    end_reason: ended?.reason ?? null,
    credits_used: started === undefined ? 0 : Math.ceil(((ended?.at ?? now) - started.at) / MINUTE) * rate,
    queue_position: current?.status === 'queued' ? 1 : null,
  };
}

/** Leaves keys out of each member of a union, keeping the union. */
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;

/** An event as the demo's agent writes it, before the log numbers and dates it. */
type EventBody = DistributiveOmit<StudioEvent, 'id' | 'created_at'>;

/** An event waiting for its time. */
interface Scheduled {
  /** When it is written, in milliseconds since the epoch. */
  at: number;
  /** What it is. */
  event: EventBody;
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
 * Builds an asset of the film's library.
 *
 * @param fields What sets it apart.
 * @param at When it was made.
 * @returns The asset.
 */
function asset(
  fields: Pick<Asset, 'id' | 'section' | 'name' | 'tag' | 'description' | 'media'> & {
    metadata?: Record<string, unknown>;
  },
  at: number,
): Asset {
  const time = new Date(at).toISOString();
  return {
    metadata: null,
    ...fields,
    created_at: time,
    updated_at: time,
    thumbnail_url: fields.media.find((media) => media.kind === 'image')?.url ?? null,
  };
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
      text: 'FilmCraft is open on the project’s folder, so the cut can start as soon as the shots exist. One decision first:',
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
    },
  });
  add({ turn_id: t2, kind: 'turn_end', data: {} }, SECOND);

  return events.map((event, index) => ({ event, at: times[index] ?? now }));
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
      { id: 'demo-interior', name: 'Glasshouse retreat', discipline: 'architecture', format: 'Interior' },
      5 * HOUR,
    ),
    project({ id: 'demo-vertical', name: 'Spire City', discipline: 'media', format: 'Vertical drama' }, DAY + 3 * HOUR),
    project({ id: 'demo-art', name: 'Ember peaks key art', discipline: 'art', format: 'Concept art' }, 3 * DAY),
    project({ id: 'demo-score', name: 'Lighthouse theme', discipline: 'music', format: 'Score' }, 6 * DAY),
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
 * Picks what the demo's agent says to a message, by what the message is.
 *
 * @param project The project.
 * @param text The person's message.
 * @param turn The turn it starts.
 * @param start When the turn starts.
 * @returns The turn's events, with their times.
 */
function reply(project: Project, text: string, turn: TurnId, start: number): Scheduled[] {
  const at = (seconds: number): number => start + seconds * SECOND;
  const opening = /cold open|workshop|violet flats|title card/i.test(text) && project.id === 'demo-film';
  if (opening) {
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
  return [
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
  let projects = scene === 'empty' ? [] : demoProjects(opened);
  const libraries = new Map<string, Asset[]>([['demo-film', filmLibrary(opened)]]);
  let simulations: Simulation[] = [
    {
      id: 'demo-engine-1',
      project: 'demo-film',
      app: 'filmcraft',
      tier: 't4',
      phases: [
        { at: opened - 11 * MINUTE - 40 * SECOND, status: 'queued' },
        { at: opened - 11 * MINUTE - 30 * SECOND, status: 'starting' },
        { at: opened - 11 * MINUTE, status: 'running' },
      ],
    },
  ];
  const filmEngine = snapshot(
    simulations[0] ?? { id: '', project: '', app: '', tier: '', phases: [] },
    opened - 11 * MINUTE,
  );
  const logs = new Map<string, Scheduled[]>([
    ['demo-film', filmEvents(opened, libraries.get('demo-film') ?? [], filmEngine)],
  ]);
  let github: GitHubStatus = offline
    ? { configured: false, connected: false, login: null, avatar_url: null }
    : { configured: true, connected: true, login: LOGIN, avatar_url: AVATAR };
  let keys: ApiKey[] = [
    {
      id: 'demo-key-1',
      name: 'Claude on my laptop',
      prefix: 'lathe_3f9aQ2',
      created_at: new Date(opened - 6 * DAY).toISOString(),
      last_used_at: new Date(opened - 2 * HOUR).toISOString(),
    },
  ];
  let counter = 100;
  const me: Me = { id: 'demo-user', email: DEMO_EMAIL, credits: 412, max_sessions: 2 };
  const health: Health = {
    ok: true,
    agent: !offline,
    github: !offline,
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
   * Applies what an event written now describes, as the real agent's tools would.
   *
   * @param project The project.
   * @param scheduled The event.
   */
  function apply(project: string, scheduled: Scheduled): void {
    const { event } = scheduled;
    if (event.kind === 'plan') {
      change(project, { plan: event.data.items });
    }
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
    me: () => Promise.resolve(me),
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
          prefix: 'lathe_demo00',
          created_at: new Date().toISOString(),
          last_used_at: null,
        };
        keys = [key, ...keys];
        return { key, secret: 'lathe_demo_sample_key_not_a_real_secret' };
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
        const project: Project = {
          id: `demo-project-${counter}`,
          ...fields,
          pinned: false,
          created_at: now,
          updated_at: now,
          github_repo: null,
          library_sections: [],
          plan: [],
        };
        projects = [project, ...projects];
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
        };
        simulations = [...simulations, simulation];
        return snapshot(simulation, now);
      }, 700),
    listEvents: (projectId, after) => {
      if (legacy) {
        return missing();
      }
      return soon(() => {
        find(projectId);
        const now = Date.now();
        const entries = log(projectId);
        const events: StudioEvent[] = [];
        entries.forEach((scheduled, index) => {
          const id = index + 1;
          if (scheduled.at <= now && id > after) {
            events.push({ ...scheduled.event, id, created_at: new Date(scheduled.at).toISOString() });
          }
        });
        const running = entries.some((scheduled) => scheduled.at > now);
        return { events, running, cursor: events.at(-1)?.id ?? null };
      }, 120);
    },
    sendMessage: (projectId, text) =>
      soon(() => {
        const project = find(projectId);
        const entries = log(projectId);
        const now = Date.now();
        if (entries.some((scheduled) => scheduled.at > now)) {
          throw new ApiError(409, 'A turn is already running.');
        }
        counter += 1;
        const turn = `turn-${counter}`;
        const message: Scheduled = { at: now, event: { turn_id: turn, kind: 'user_message', data: { text } } };
        const scheduled = [message, ...reply(project, text, turn, now)];
        entries.push(...scheduled);
        for (const entry of scheduled) {
          window.setTimeout(
            () => {
              apply(projectId, entry);
            },
            Math.max(0, entry.at - now),
          );
        }
        change(projectId, { updated_at: new Date(now).toISOString() });
        return turn;
      }),
    stopTurn: (projectId) =>
      soon(() => {
        const now = Date.now();
        const entries = log(projectId).filter((scheduled) => scheduled.at <= now);
        const last = entries.at(-1);
        if (last !== undefined && last.event.kind !== 'turn_end') {
          entries.push({ at: now, event: { turn_id: last.event.turn_id, kind: 'turn_end', data: {} } });
        }
        logs.set(projectId, entries);
      }),
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
        github = { configured: true, connected: true, login: LOGIN, avatar_url: AVATAR };
        throw new ApiError(NOT_CONFIGURED, 'The demo connects without leaving the page: reload to see it connected.');
      }),
    githubRepos: () => soon(() => demoRepos(opened), 400),
    disconnectGitHub: () =>
      soon(() => {
        github = { ...github, connected: false, login: null, avatar_url: null };
      }),
    linkRepo: (projectId, link) =>
      soon(() => change(projectId, { github_repo: 'repo' in link ? link.repo : `${LOGIN}/${link.create.name}` }), 600),
    unlinkRepo: (projectId) => soon(() => change(projectId, { github_repo: null })),
  };
}
