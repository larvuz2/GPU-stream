/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The demo's movie scene (`/app/?demo=movie`): a film from "let's create a movie" to the moment
 * an engine is first needed, played the way the agent on Anthropic's loop writes it
 * (`moody/STUDIO.md`, "the agent on Anthropic's loop").
 *
 * The scene is a script, so whatever the person answers, the film is the sample's. It opens on
 * the person's first message and plays one turn per message:
 *
 * 1. The agent reasons (a `thinking` note), answers while the answer is written (`text` events of
 *    one `block`), and asks for the story.
 * 2. It asks for the main characters, and writes the plan.
 * 3. It asks for the art style with an interactive card (`ui`), which the person locks in.
 * 4. It sets the library's sections and hands pre-production to five subagents at once (`agent`
 *    events of one `group`), which work at different speeds, change what they are doing as they
 *    go, and finish at different times. Each subagent's own tool calls and notes carry its
 *    `agent_id`, so they show inside its card; the references they generate arrive in the library
 *    as they are made. One of them fails a generation and resolves it. Then, before starting
 *    FilmCraft, the agent asks (`approval`): the turn waits for the answer, starts the engine or
 *    goes on without it, and ends on a report and what it cost (`usage`).
 * 5. It runs a long job of its own, the first animation tests, which needs no engine, and ends on
 *    a report too.
 *
 * A turn of many steps ends the way the contract asks ("a long job ends with a report"): its last
 * message is organized under short headings, each a few bullets, the most important first.
 *
 * The long job spends what the account's limits for a turn allow. Where one is reached the turn
 * stops at that step with an `error` that names the limit, and the next message goes on from
 * there with both limits fresh, as the real loop does. With the demo's defaults the job fits in
 * one turn; `/app/?demo=limit` opens the film with everything up to the job already said, on an
 * account that set its spend for a turn low, so the job has stopped at it ({@link movieSoFar}).
 *
 * No engine exists until the approval is given: planning, writing, and generating need none.
 * The pictures are the site's own artwork.
 * @module
 */
import type {
  AgentData,
  AgentInfo,
  Asset,
  Media,
  PlanItem,
  Project,
  TurnId,
  TurnLimit,
  TurnLimits,
  UserMessageData,
} from '../lib/api';
import { catalog, findApp, findTier, IDLE_SHUTDOWN_MINUTES } from '../lib/catalog';
import { usd } from '../lib/format';
import { describeAnswer, inputsOf, startState } from './ui/answer';
import { EXAMPLES } from './ui/gallery/examples';
import { readTree } from './ui/tree';
import {
  asset,
  MINUTE,
  SECOND,
  snapshot,
  still,
  type DistributiveOmit,
  type EventBody,
  type Scheduled,
  type Script,
  type Simulation,
} from './demoKit';

/** The movie scene's project. */
export const MOVIE_PROJECT = 'demo-movie';

/** The tool the scene asks about before it runs: the one that starts an engine. */
const ENGINE_TOOL = 'engine_start';

/** The app the scene starts once allowed, and the tier it starts it on. */
const ENGINE_APP = 'filmcraft';
const ENGINE_TIER = 't4';

/** The subagents a film's agent can hand work to, which the scene's fourth turn runs at once. */
export const MOVIE_AGENTS: AgentInfo[] = [
  {
    name: 'research',
    title: 'Research agent',
    description: 'Finds and reads references on the web when a look, a period, or a technique needs grounding.',
  },
  { name: 'story', title: 'Story agent', description: 'Outlines and drafts: loglines, acts, beats, and scenes.' },
  {
    name: 'character',
    title: 'Character agent',
    description: 'Designs the cast and generates each character’s reference images.',
  },
  {
    name: 'art-direction',
    title: 'Art direction agent',
    description: 'Sets the palette and paints style frames of the world.',
  },
  {
    name: 'asset',
    title: 'Asset agent',
    description: 'Files what the others make in the library, tagged and in the right section.',
  },
];

const IRIS = still('character-iris.webp', 'iris-reference.webp');
const WICK = still('discipline-animation.webp', 'wick-reference.webp');
const WORKSHOP = still('app-blender.webp', 'workshop-isle.webp');
const ISLES = still('discipline-games.webp', 'drifting-isles.webp');

/**
 * The movie scene's project, as the sidebar lists it: new, with nothing in it.
 *
 * @param now The time the demo opens at.
 * @returns The project.
 */
export function movieProject(now: number): Project {
  const time = new Date(now).toISOString();
  return {
    id: MOVIE_PROJECT,
    name: 'Untitled movie',
    discipline: 'media',
    format: 'Film & TV',
    pinned: false,
    created_at: time,
    updated_at: time,
    github_repo: null,
    library_sections: [],
    plan: [],
    permissions: {},
  };
}

/** What the person says to open the scene. */
const OPENING_MESSAGE = 'Let’s create a movie.';

/**
 * The film's plan at a stage of the scene.
 *
 * @param done How many of its steps are done; the one after them is in progress.
 * @returns The plan.
 */
function moviePlan(done: number): PlanItem[] {
  const steps = [
    'Agree the story',
    'Agree the main characters',
    'Agree the art style',
    'Pre-production: outline, references, and style frames',
    'First animation tests',
    'Cut the animatic in FilmCraft',
  ];
  return steps.map((title, index) => ({
    id: `m${index + 1}`,
    title,
    status: index < done ? 'done' : index === done ? 'active' : 'pending',
  }));
}

/** An event of a turn before its turn is named: what {@link Timeline.add} takes. */
type Body = DistributiveOmit<EventBody, 'turn_id'>;

/** A turn being written: events at seconds into it. */
interface Timeline {
  /** The events written so far. */
  events: Scheduled[];
  /**
   * Writes an event.
   *
   * @param seconds When, in seconds into the turn.
   * @param body The event.
   */
  add: (seconds: number, body: Body) => void;
  /**
   * Writes a block of the answer, or of the reasoning, as it grows: an event every few words,
   * each replacing the one before it, the last of them whole.
   *
   * @param from When the first words are written, in seconds into the turn.
   * @param over How long the writing takes, in seconds.
   * @param kind Whether it is the answer or the reasoning.
   * @param block The block's name.
   * @param text The whole text.
   * @param agentId The subagent writing it, for one of a subagent's own.
   */
  write: (from: number, over: number, kind: 'text' | 'thinking', block: string, text: string, agentId?: string) => void;
}

/** How often a block being written is written again, in seconds. */
const WRITE_EVERY = 0.35;

/**
 * Starts writing a turn.
 *
 * @param turn The turn.
 * @param start When it starts.
 * @returns The timeline.
 */
function timeline(turn: TurnId, start: number): Timeline {
  const events: Scheduled[] = [];
  const add = (seconds: number, body: Body): void => {
    events.push({ at: start + seconds * SECOND, event: { ...body, turn_id: turn } });
  };
  return {
    events,
    add,
    write: (from, over, kind, block, text, agentId) => {
      const words = text.split(' ');
      const steps = Math.max(1, Math.round(over / WRITE_EVERY));
      for (let step = 1; step <= steps; step += 1) {
        add(from + (over * step) / steps, {
          kind,
          data: {
            text: words.slice(0, Math.ceil((words.length * step) / steps)).join(' '),
            block,
            partial: step < steps,
          },
          ...(agentId === undefined ? {} : { agent_id: agentId }),
        });
      }
    },
  };
}

/**
 * What the scene's agent says once the script has run out.
 *
 * @param turn The turn.
 * @param start When it starts.
 * @returns The turn.
 */
function afterwards(turn: TurnId, start: number): Script {
  const line = timeline(turn, start);
  line.write(
    0.8,
    1.4,
    'text',
    `${turn}-a`,
    'That is as far as this scene is scripted. In a real project I would cut the tests into an animatic now and check in with you before any decision that is yours.',
  );
  line.add(2.4, { kind: 'usage', data: { input_tokens: 9120, output_tokens: 148, cost_usd: 0.05, seconds: 2.4, agents: 0 } });
  line.add(2.6, { kind: 'turn_end', data: {} });
  return { events: line.events };
}

/**
 * The scene's first three turns, each of which settles one thing and asks for the next.
 *
 * @param stage Which of them: 0 asks for the story, 1 for the characters, 2 for the art style.
 * @param turn The turn.
 * @param start When it starts.
 * @returns The turn.
 */
function asking(stage: number, turn: TurnId, start: number): Script {
  const line = timeline(turn, start);
  let ends: number;
  if (stage === 0) {
    line.write(
      0.7,
      2.2,
      'thinking',
      `${turn}-t`,
      'A movie, and nothing else yet. Before anything is generated I need three things from the person: the story, the main characters, and the art style. None of that needs an engine, so none starts. Ask one thing at a time, the story first.',
    );
    line.write(
      3.1,
      2.4,
      'text',
      `${turn}-a`,
      'Let’s make it. Before I generate anything I need three things from you: **the story**, **the main characters**, and **the art style**. We stay in planning until those are set, so no engine runs and nothing is billed by the minute.',
    );
    line.add(5.8, {
      kind: 'ask',
      data: {
        question: 'What is the story?',
        options: [
          'A young lamplighter and her lantern robot cross the drifting isles to relight the last lamp before the long night',
          'I have a script to paste',
          'Pitch me three ideas',
        ],
        recommended:
          'A young lamplighter and her lantern robot cross the drifting isles to relight the last lamp before the long night',
      },
    });
    ends = 6;
    line.add(ends, { kind: 'usage', data: { input_tokens: 6480, output_tokens: 212, cost_usd: 0.04, seconds: ends, agents: 0 } });
  } else if (stage === 1) {
    line.write(
      0.7,
      1.6,
      'thinking',
      `${turn}-t`,
      'One night, one crossing, a deadline: that is a three-minute short in three acts. Give it a working title and write the plan. Next I need to know who is in it.',
    );
    line.write(
      2.5,
      2,
      'text',
      `${turn}-a`,
      'A crossing, a deadline, and one light left: that is a clean three-minute short. I am calling it **Lamplight** for now.',
    );
    line.add(4.7, { kind: 'plan', data: { items: moviePlan(1) } });
    line.add(5, {
      kind: 'ask',
      data: {
        question: 'Who are the main characters?',
        options: [
          'Iris, nineteen, the last lamplighter, and Wick, her lantern robot, who speaks in clicks',
          'Add her grandfather Theo, the tinkerer who built Wick',
          'Suggest a cast for me',
        ],
        recommended: 'Iris, nineteen, the last lamplighter, and Wick, her lantern robot, who speaks in clicks',
      },
    });
    ends = 5.2;
    line.add(ends, { kind: 'usage', data: { input_tokens: 7350, output_tokens: 186, cost_usd: 0.04, seconds: ends, agents: 0 } });
  } else {
    line.write(
      0.8,
      1.8,
      'text',
      `${turn}-a`,
      'Iris and Wick carry it, and the isles are the third character. One more before I start making things:',
    );
    line.add(2.8, { kind: 'plan', data: { items: moviePlan(2) } });
    line.add(
      3,
      STYLE_CARD === undefined
        ? {
            kind: 'ask',
            data: {
              question: 'What art style?',
              options: [
                'Cinematic and painterly: warm lamplight against violet dusk',
                'Stop-motion felt and paper',
                'Clean stylized 3D with soft light',
              ],
              recommended: 'Cinematic and painterly: warm lamplight against violet dusk',
            },
          }
        : { kind: 'ui', data: STYLE_CARD },
    );
    ends = 3.2;
    line.add(ends, { kind: 'usage', data: { input_tokens: 7910, output_tokens: 94, cost_usd: 0.04, seconds: ends, agents: 0 } });
  }
  line.add(ends + 0.2, { kind: 'turn_end', data: {} });
  return { events: line.events };
}

/**
 * The card the scene asks the art style with: the gallery's own, so the scene shows a card the way
 * a real turn would, as pictures and palettes to choose between rather than a list of words.
 */
const STYLE_CARD = EXAMPLES.find((example) => example.id === 'style')?.ui;

/** The group the scene's five subagents share: one step started them together. */
const GROUP = 'pre-production';

/** The job each of the five is handed, and what it is doing as it starts. */
const JOBS: readonly Pick<AgentData, 'name' | 'task' | 'activity' | 'detail'>[] = [
  {
    name: 'research',
    task: 'Gather references for painterly lamplight at dusk',
    activity: 'searching',
    detail: 'Searching for painterly night scenes',
  },
  { name: 'story', task: 'Outline the short in three acts', activity: 'thinking', detail: 'Reading your story and cast' },
  {
    name: 'character',
    task: 'Design Iris and Wick and generate their references',
    activity: 'creating',
    detail: 'Sketching Iris from your description',
  },
  {
    name: 'art-direction',
    task: 'Set the palette and paint style frames of the isles',
    activity: 'curious',
    detail: 'Trying three palettes for the dusk',
  },
  {
    name: 'asset',
    task: 'File everything in the library, tagged',
    activity: 'processing',
    detail: 'Setting up the library’s sections',
  },
];

/**
 * The scene's fourth turn: pre-production handed to five subagents at once, the approval before
 * FilmCraft, and the report the turn ends on.
 *
 * @param turn The turn.
 * @param start When it starts.
 * @returns The turn, which waits on the approval.
 */
function delegating(turn: TurnId, start: number): Script {
  const line = timeline(turn, start);
  const made = (seconds: number): number => start + seconds * SECOND;

  const library: Asset[] = [
    asset(
      {
        id: 'm-iris',
        section: 'Characters',
        name: 'Iris',
        tag: 'iris',
        description: 'Nineteen, the last lamplighter of the isles. Braids tied back for the wind, a patient smile, soot on her sleeves.',
        metadata: { age: 19, role: 'Lead', palette: 'Amber, umber, deep violet' },
        media: [IRIS],
      },
      made(10),
    ),
    asset(
      {
        id: 'm-wick',
        section: 'Characters',
        name: 'Wick',
        tag: 'wick',
        description: 'Her lantern robot, built from a diving helmet. Speaks in clicks, carries the flame, and is afraid of the dark.',
        metadata: { role: 'Companion', palette: 'Rust, brass, lamp orange' },
        media: [WICK],
      },
      made(16.7),
    ),
    asset(
      {
        id: 'm-workshop',
        section: 'Environments',
        name: 'The workshop isle',
        tag: 'workshop-isle',
        description: 'The floating scrap of land where Iris and Wick live: a potter’s wheel, a hundred lanterns, and one rope bridge out.',
        metadata: { time_of_day: 'Dusk', act: '1' },
        media: [WORKSHOP],
      },
      made(14.7),
    ),
    asset(
      {
        id: 'm-isles',
        section: 'Environments',
        name: 'The drifting isles',
        tag: 'drifting-isles',
        description: 'The crossing: islands adrift over a river of fog, the last lamp a speck on the far ridge.',
        metadata: { time_of_day: 'Last light', act: '2' },
        media: [ISLES],
      },
      made(20.7),
    ),
  ];
  const entry = (id: string): Asset[] => library.filter((candidate) => candidate.id === id);

  /** The five cards as the step starts them; every later event of one carries the whole card again. */
  const cards = new Map<string, AgentData>(
    JOBS.map((job): [string, AgentData] => [
      job.name,
      {
        ...job,
        agent_id: `${turn}-${job.name}`,
        group: GROUP,
        title: MOVIE_AGENTS.find((agent) => agent.name === job.name)?.title ?? job.name,
        state: 'working',
      },
    ]),
  );
  /** When the subagents start, in seconds into the turn. */
  const began = 5;
  /**
   * Writes a subagent's card again, changed.
   *
   * @param seconds When, in seconds into the turn.
   * @param name The subagent.
   * @param changes What changed.
   */
  const card = (seconds: number, name: string, changes: Partial<AgentData>): void => {
    const current = cards.get(name);
    if (current === undefined) {
      return;
    }
    const next: AgentData = { ...current, ...changes, seconds: Math.round(seconds - began) };
    cards.set(name, next);
    line.add(seconds, { kind: 'agent', data: next });
  };
  /**
   * Writes one of a subagent's own tool calls.
   *
   * @param name The subagent.
   * @param from When it starts, in seconds into the turn.
   * @param took How long it takes, in seconds.
   * @param call What the call is and what it came to.
   */
  const call = (
    name: string,
    from: number,
    took: number,
    { tool, title, activity, summary, ok = true, media }: {
      tool: string;
      title: string;
      activity: string;
      summary: string;
      ok?: boolean;
      media?: Media[];
    },
  ): void => {
    const agentId = cards.get(name)?.agent_id;
    const callId = `${turn}-${name}-${from}`;
    line.add(from, { kind: 'tool_start', agent_id: agentId, data: { call_id: callId, tool, title, activity } });
    line.add(from + took, {
      kind: 'tool_end',
      agent_id: agentId,
      data: { call_id: callId, ok, summary, ...(media === undefined ? {} : { media }) },
    });
  };
  /**
   * Puts an asset in the library, as the subagent that made it.
   *
   * @param seconds When, in seconds into the turn.
   * @param name The subagent.
   * @param id The asset.
   */
  const file = (seconds: number, name: string, id: string): void => {
    for (const filed of entry(id)) {
      line.add(seconds, { kind: 'library', agent_id: cards.get(name)?.agent_id, data: { asset: filed } });
    }
  };

  line.write(
    0.6,
    2.2,
    'thinking',
    `${turn}-t1`,
    'Story, cast, and style are set, so pre-production can start. Five jobs do not depend on each other: references, the outline, the character references, the style frames, and filing the library. Hand each to a subagent and run them at once. Still no engine: the pictures come from fal.',
  );
  line.write(
    3,
    1.6,
    'text',
    `${turn}-a1`,
    'That is everything pre-production needs. I am handing it to five specialists who work at the same time. None of it needs an engine: the pictures are generated through fal.',
  );
  line.add(4.7, { kind: 'library', data: { sections: ['Characters', 'Environments', 'Props', 'Logos'] } });
  line.add(4.8, { kind: 'plan', data: { items: moviePlan(3) } });
  for (const name of cards.keys()) {
    card(began, name, {});
  }

  call('research', 5.5, 1.5, {
    tool: 'web_search',
    title: 'Search: lamplight against violet dusk, painterly animation',
    activity: 'searching',
    summary: '9 results',
  });
  card(7.2, 'research', { activity: 'analyzing', detail: 'Reading 6 sources on lamplight at dusk' });
  call('research', 7.3, 1.7, {
    tool: 'web_fetch',
    title: 'Read: how lantern light falls off in night exteriors',
    activity: 'analyzing',
    summary: '3 pages read',
  });
  line.add(9.2, {
    kind: 'text',
    agent_id: cards.get('research')?.agent_id,
    data: {
      text: 'Twelve references kept. What they agree on: the lamps are the only saturated light in frame, the dusk sits two stops under them, and fog carries the violet. Faces are lit from below the eye line, never flat.',
    },
  });
  card(9.5, 'research', { state: 'completed', activity: 'satisfied', detail: '12 references gathered', tokens: 6100 });

  line.write(
    6,
    2,
    'thinking',
    `${turn}-story-t`,
    'Three acts. One: the lamps of the isles fail one by one, and the flame in Wick’s lantern is the last. Two: the crossing, where the bridge gives and Wick must go first in the dark. Three: the last lamp, lit together.',
    cards.get('story')?.agent_id,
  );
  card(8.5, 'story', { activity: 'focused', detail: 'Tightening act two around the crossing' });
  line.add(12, {
    kind: 'text',
    agent_id: cards.get('story')?.agent_id,
    data: {
      text: '**Lamplight**, in three acts and fourteen beats.\n\n1. **The lamps fail.** Iris counts the isles going dark from the workshop; only Wick’s flame is left.\n2. **The crossing.** The rope bridge gives. Wick, who is afraid of the dark, has to go first.\n3. **The last lamp.** They light it together, and the isles answer one by one.',
    },
  });
  card(12.3, 'story', { state: 'completed', activity: 'satisfied', detail: 'Outline written: 3 acts, 14 beats', tokens: 4800 });

  call('character', 5.6, 4.2, {
    tool: 'generate_image',
    title: 'Reference: @iris',
    activity: 'creating',
    summary: 'Two variations; kept the warmer one.',
    media: [IRIS],
  });
  file(10, 'character', 'm-iris');
  card(10.2, 'character', { detail: 'Painting Wick, her lantern robot' });
  call('character', 10.4, 2.6, {
    tool: 'generate_image',
    title: 'Reference: @wick',
    activity: 'creating',
    summary: 'The lantern came out unlit.',
    ok: false,
  });
  card(13.2, 'character', { activity: 'confused', detail: 'Wick’s lantern came out unlit, painting it again' });
  call('character', 13.4, 3.1, {
    tool: 'generate_image',
    title: 'Reference: @wick, lantern lit',
    activity: 'creating',
    summary: 'Lit, and the glow reaches his eyes.',
    media: [WICK],
  });
  file(16.7, 'character', 'm-wick');
  card(16.9, 'character', { activity: 'analyzing', detail: 'Checking the pair side by side' });
  card(18.5, 'character', {
    state: 'completed',
    activity: 'satisfied',
    detail: '2 characters, each with a reference',
    tokens: 9300,
  });

  card(8, 'art-direction', { activity: 'creating', detail: 'Painting the workshop isle at dusk' });
  call('art-direction', 8.2, 6.3, {
    tool: 'generate_image',
    title: 'Style frame: the workshop isle',
    activity: 'creating',
    summary: 'Lamps warm, sky violet, as the references agree.',
    media: [WORKSHOP],
  });
  file(14.7, 'art-direction', 'm-workshop');
  card(15, 'art-direction', { detail: 'Painting the drifting isles' });
  call('art-direction', 15.2, 5.3, {
    tool: 'generate_image',
    title: 'Style frame: the drifting isles',
    activity: 'creating',
    summary: 'The fog carries the violet; one lamp on the far ridge.',
    media: [ISLES],
  });
  file(20.7, 'art-direction', 'm-isles');
  card(21, 'art-direction', { activity: 'surprised', detail: 'Violet fog reads better than blue: keeping it' });
  card(22.6, 'art-direction', {
    state: 'completed',
    activity: 'satisfied',
    detail: 'One palette and 2 style frames',
    tokens: 8700,
  });

  card(6.5, 'asset', { detail: 'Waiting for the first references' });
  card(10.6, 'asset', { detail: 'Filing Iris under Characters' });
  card(17.4, 'asset', { detail: 'Tagging 3 entries' });
  card(21.6, 'asset', { activity: 'analyzing', detail: 'Checking the tags against the outline' });
  card(24, 'asset', {
    state: 'completed',
    activity: 'satisfied',
    detail: 'Library organized: 4 entries in 2 sections',
    tokens: 2900,
  });

  line.write(
    24.6,
    2,
    'thinking',
    `${turn}-t2`,
    'All five reported. The outline has fourteen beats, the references agree on the light, and the library has both characters and two style frames. Next are the first animation tests. Cutting them together needs FilmCraft, a machine billed by the minute, so that is the person’s call: ask before starting it.',
  );
  line.write(
    27,
    3.4,
    'text',
    `${turn}-a2`,
    'All five are done. Next come the first animation tests, and then the animatic they are cut into. The cut needs FilmCraft, which runs on a cloud machine billed by the minute, so starting it is yours to decide.',
  );
  /**
   * The report the turn ends on, once the person has decided about the engine.
   *
   * @param engine What became of FilmCraft, which is what the person just decided and so comes first.
   * @param next What the agent does on the person's word.
   * @returns The report.
   */
  const report = (engine: string, next: string): string =>
    [
      '### Done',
      `- ${engine}`,
      '- **Story.** The outline, in three acts and fourteen beats: the lamps fail, the crossing, the last lamp.',
      '- **References.** Twelve kept. They agree that the lamps are the only saturated light in frame.',
      '',
      '### In the library now',
      '- **Characters.** @iris and @wick, each with a reference. Wick’s first one came out with the lantern unlit and was painted again.',
      '- **Environments.** @workshop-isle and @drifting-isles, in one palette: warm lamplight against violet dusk.',
      '',
      '### Yours to decide',
      '- Whether @wick keeps to clicks until the end or says one word at the last lamp. The outline works both ways; I would keep the clicks.',
      '',
      '### What I need from you',
      `- ${next}`,
      '',
      '### Not known yet',
      '- How long the film runs. The outline reads as four to five minutes; the animatic will tell.',
    ].join('\n');
  line.add(26.9, { kind: 'plan', data: { items: moviePlan(4) } });

  const tier = findTier(ENGINE_TIER);
  const app = findApp(ENGINE_APP)?.name ?? ENGINE_APP;
  return {
    events: line.events,
    pause: {
      turn,
      at: start + 30.8 * SECOND,
      approval: {
        approval_id: `${turn}-approval`,
        tool: ENGINE_TOOL,
        title: `Start ${app}`,
        detail: `A ${tier?.name ?? ENGINE_TIER} machine${tier === undefined || tier.gpu === null ? '' : ` with an NVIDIA ${tier.gpu}`}, ${tier?.credits_per_minute ?? 0} credits a minute while it runs. It stops by itself after ${IDLE_SHUTDOWN_MINUTES} minutes without activity.`,
      },
      resume: (decision, answered) => {
        const rest = timeline(turn, answered);
        const spent = (seconds: number): number => Math.round((answered - start) / SECOND + seconds);
        if (decision === 'deny') {
          rest.write(
            0.8,
            3.2,
            'text',
            `${turn}-a3`,
            report(
              `**${app}** was not started, as you decided, and nothing is billed.`,
              'A word to go on. I will generate the first animation tests, which need no engine, and keep them with the project’s files until you want them cut.',
            ),
          );
          rest.add(4.2, {
            kind: 'usage',
            data: { input_tokens: 48210, output_tokens: 7104, cost_usd: 0.85, seconds: spent(4.2), agents: cards.size },
          });
          rest.add(4.4, { kind: 'turn_end', data: {} });
          return { events: rest.events };
        }
        const engine: Simulation = {
          id: `${turn}-engine`,
          project: MOVIE_PROJECT,
          app: ENGINE_APP,
          tier: ENGINE_TIER,
          phases: [
            { at: answered + 0.6 * SECOND, status: 'queued' },
            { at: answered + 3 * SECOND, status: 'starting' },
            { at: answered + 16 * SECOND, status: 'running' },
          ],
        };
        rest.add(0.3, {
          kind: 'tool_start',
          data: { call_id: `${turn}-engine`, tool: ENGINE_TOOL, title: `Starting ${app}`, activity: 'processing' },
        });
        for (const phase of engine.phases) {
          rest.events.push({ at: phase.at, event: { turn_id: turn, kind: 'engine', data: { engine: snapshot(engine, phase.at) } } });
        }
        rest.add(16.4, {
          kind: 'tool_end',
          data: { call_id: `${turn}-engine`, ok: true, summary: `${app} is running on ${tier?.name ?? ENGINE_TIER}` },
        });
        rest.add(16.6, { kind: 'screen', data: { engine_id: engine.id, stream: 'Desktop' } });
        rest.write(
          17,
          3.2,
          'text',
          `${turn}-a3`,
          report(
            `**${app}** is running on a ${tier?.name ?? ENGINE_TIER} machine, open on the project’s folder, and your screen shows it. It costs ${tier?.credits_per_minute ?? 0} credits a minute and stops by itself after ${IDLE_SHUTDOWN_MINUTES} idle minutes.`,
            'A word to go on. I will generate the first animation tests and bring them into the timeline.',
          ),
        );
        rest.add(20.4, {
          kind: 'usage',
          data: { input_tokens: 51870, output_tokens: 7386, cost_usd: 0.92, seconds: spent(20.4), agents: cards.size },
        });
        rest.add(20.6, { kind: 'turn_end', data: {} });
        return { events: rest.events, engines: [engine] };
      },
    },
  };
}

/** One step of the scene's long job: a call of a tool, and what the model's part of it takes. */
interface JobStep {
  /** The tool. */
  tool: string;
  /** What the call is, as its card says. */
  title: string;
  /** What the agent is doing meanwhile. */
  activity: string;
  /** What the call came to. */
  summary: string;
  /** How long the call takes, in seconds. */
  took: number;
  /** What the model costs for the step, in US dollars. */
  cost: number;
  /** The tokens the model reads for the step. */
  input: number;
  /** The tokens it writes. */
  output: number;
}

/** The scene's long job, the first animation tests, as the steps it takes. None needs an engine. */
const TESTS: readonly JobStep[] = [
  {
    tool: 'github_read',
    title: 'Read act one of the outline',
    activity: 'analyzing',
    summary: '5 beats, 4 of them with movement worth testing',
    took: 1.2,
    cost: 0.21,
    input: 11840,
    output: 236,
  },
  {
    tool: 'github_save',
    title: 'Prompts for four tests',
    activity: 'focused',
    summary: 'tests.md · 4 shots · 6 s each',
    took: 1.5,
    cost: 0.27,
    input: 12910,
    output: 904,
  },
  {
    tool: 'generate_video',
    title: 'Test 1: @iris lights the workshop lamp',
    activity: 'creating',
    summary: '6 s · the flame catches on the second strike',
    took: 2.6,
    cost: 0.29,
    input: 14230,
    output: 412,
  },
  {
    tool: 'generate_video',
    title: 'Test 2: @wick wakes',
    activity: 'creating',
    summary: '6 s · his eyes warm before he moves, on twos',
    took: 2.4,
    cost: 0.28,
    input: 14870,
    output: 388,
  },
  {
    tool: 'generate_video',
    title: 'Test 3: the far lamps go out',
    activity: 'creating',
    summary: '6 s · one isle at a time, left to right',
    took: 2.5,
    cost: 0.31,
    input: 15420,
    output: 431,
  },
  {
    tool: 'generate_video',
    title: 'Test 4: the rope bridge in the wind',
    activity: 'creating',
    summary: '6 s · the fog reads blue, not violet',
    took: 2.3,
    cost: 0.3,
    input: 15990,
    output: 405,
  },
  {
    tool: 'library_look',
    title: 'Compare the tests with the style frames',
    activity: 'analyzing',
    summary: 'Tests 1 to 3 hold the palette; test 4 drifts blue',
    took: 1.6,
    cost: 0.34,
    input: 19650,
    output: 512,
  },
  {
    tool: 'github_save',
    title: 'Notes on each test',
    activity: 'processing',
    summary: 'tests.md · what worked, and what to change',
    took: 1.1,
    cost: 0.22,
    input: 16480,
    output: 730,
  },
];

/** The report the long job ends on. */
const TESTS_REPORT_TEXT = [
  '### Done',
  '- Four animation tests from act one, six seconds each: @iris lighting the workshop lamp, @wick waking, the far lamps going out, and the rope bridge in the wind.',
  '- Each checked against the style frames. Tests 1 to 3 hold the palette; test 4 drifts blue in the fog.',
  '',
  '### What there is now',
  '- The four clips, in `tests/` among the project’s files.',
  '- `tests.md`, with each test’s prompt and a note on what worked.',
  '',
  '### Yours to decide',
  '- **The motion.** Test 2 moves on twos, like stop-motion; the others are smooth. I would take test 2’s rhythm for the whole film.',
  '- **Test 4.** Generate it again with the violet fog, or leave the bridge out of the tests. I would generate it again.',
  '',
  '### What I need from you',
  '- Your pick on the motion before I generate more, since every later shot follows it.',
  '',
  '### Not known yet',
  '- Whether the glow of @wick’s lantern holds across a cut. Four tests cannot show it; the animatic will.',
].join('\n');

/** How the call ids of the long job's steps start, by which a later turn counts the steps done. */
const TEST_CALL = 'animation-test-';

/** How the block of the long job's report is named, by which a later turn knows the job is over. */
const TESTS_REPORT = 'animation-tests-report';

/**
 * How far the long job has come.
 *
 * @param history What was written in the project so far.
 * @returns How many of its steps are done, and whether its report is written.
 */
function testsProgress(history: readonly Scheduled[]): { done: number; reported: boolean } {
  let done = 0;
  let reported = false;
  for (const { event } of history) {
    if (event.kind === 'tool_end' && event.data.ok && event.data.call_id.startsWith(TEST_CALL)) {
      done += 1;
    } else if (event.kind === 'text' && event.data.partial !== true && event.data.block?.startsWith(TESTS_REPORT) === true) {
      reported = true;
    }
  }
  return { done, reported };
}

/**
 * A turn of the scene's long job: the first animation tests, from the step the turns before it
 * reached, for as long as the account's limits allow.
 *
 * A limit is counted from zero in each turn. The steps are counted before one starts, so a turn
 * takes no more of them than its limit; the spend is known only once a step is paid for, so the
 * turn stops after the step that reached it. Either way the turn ends with an `error` that names
 * the limit, in the words the control plane uses, and the next turn goes on from the next step.
 * A turn that reaches the end of the job writes the report.
 *
 * @param turn The turn.
 * @param start When it starts.
 * @param limits The account's limits for a turn.
 * @param done How many of the job's steps earlier turns finished.
 * @returns The turn.
 */
function animating(turn: TurnId, start: number, limits: TurnLimits, done: number): Script {
  const line = timeline(turn, start);
  let at = 2.2;
  let taken = 0;
  let cost = 0.05;
  let input = 9240;
  let output = 61;
  /**
   * Ends the turn on what it cost.
   *
   * @returns The turn.
   */
  const end = (): Script => {
    line.add(at + 0.2, {
      kind: 'usage',
      data: {
        input_tokens: input,
        output_tokens: output,
        cost_usd: Math.round(cost * 100) / 100,
        seconds: Math.round(at),
        agents: 0,
      },
    });
    line.add(at + 0.4, { kind: 'turn_end', data: {} });
    return { events: line.events };
  };
  /**
   * Stops the turn at one of the account's limits.
   *
   * @param limit The limit reached.
   * @returns The turn.
   */
  const stop = (limit: TurnLimit): Script => {
    line.add(at, {
      kind: 'error',
      data: {
        message: `This turn reached your ${
          limit === 'budget'
            ? `spending limit of ${usd(limits.turn_budget_usd)}`
            : `limit of ${limits.turn_limit} ${limits.turn_limit === 1 ? 'step' : 'steps'}`
        } and stopped. You can change the limit in your settings. Send a message to go on.`,
        limit,
      },
    });
    return end();
  };
  const outOfSteps = (): boolean => taken >= limits.turn_limit;

  line.write(
    0.6,
    1.2,
    'text',
    `${turn}-a`,
    done === 0
      ? 'Starting the first animation tests: four shots from act one, six seconds each, generated through fal.'
      : `Going on with the animation tests from where the last turn stopped: ${done} of ${TESTS.length} steps are done.`,
  );
  for (const [index, step] of TESTS.entries()) {
    if (index < done) {
      continue;
    }
    if (outOfSteps()) {
      return stop('steps');
    }
    const callId = `${TEST_CALL}${index + 1}-${turn}`;
    line.add(at, {
      kind: 'tool_start',
      data: { call_id: callId, tool: step.tool, title: step.title, activity: step.activity },
    });
    at += step.took;
    line.add(at, { kind: 'tool_end', data: { call_id: callId, ok: true, summary: step.summary } });
    at += 0.4;
    taken += 1;
    cost += step.cost;
    input += step.input;
    output += step.output;
    if (cost >= limits.turn_budget_usd) {
      return stop('budget');
    }
  }
  if (outOfSteps()) {
    return stop('steps');
  }
  line.add(at, { kind: 'plan', data: { items: moviePlan(5) } });
  line.write(at + 0.2, 3.2, 'text', `${TESTS_REPORT}-${turn}`, TESTS_REPORT_TEXT);
  at += 3.6;
  cost += 0.12;
  input += 17200;
  output += 348;
  return end();
}

/**
 * What the scene's agent answers a message with.
 *
 * @param history What was written in the project before the message.
 * @param turn The turn the message starts.
 * @param start When it starts.
 * @param limits The account's limits for a turn.
 * @returns The turn.
 */
export function movieTurn(history: readonly Scheduled[], turn: TurnId, start: number, limits: TurnLimits): Script {
  const said = history.filter((scheduled) => scheduled.event.kind === 'user_message').length;
  if (said < 3) {
    return asking(said, turn, start);
  }
  if (said === 3) {
    return delegating(turn, start);
  }
  const tests = testsProgress(history);
  return tests.reported ? afterwards(turn, start) : animating(turn, start, limits, tests.done);
}

/**
 * The scene as it opens: the person's first message, and the agent's answer to it.
 *
 * @param now The time the demo opens at.
 * @returns The turn.
 */
export function movieOpening(now: number): Script {
  const turn = 'movie-1';
  const answer = asking(0, turn, now);
  return {
    ...answer,
    events: [{ at: now, event: { turn_id: turn, kind: 'user_message', data: { text: OPENING_MESSAGE } } }, ...answer.events],
  };
}

/**
 * The scene with everything up to its long job already said (`/app/?demo=limit`): the person
 * agreed with each recommendation, locked the style card in as it opened, allowed the engine, and
 * asked for the animation tests, which ran as far as the account's limits let them.
 *
 * @param now The time the demo opens at.
 * @param limits The account's limits for a turn.
 * @returns Every turn so far, all of it in the past, and the engine the fourth started.
 */
export function movieSoFar(now: number, limits: TurnLimits): Script {
  const events: Scheduled[] = [];
  const engines: Simulation[] = [];
  let turns = 0;
  /**
   * Adds a turn: a message of the person's, and the agent's answer to it. A turn that asks before
   * a tool is allowed a few seconds later.
   *
   * @param ago How long before now the turn started, in milliseconds.
   * @param data The message.
   */
  const say = (ago: number, data: UserMessageData): void => {
    turns += 1;
    const turn = `movie-${turns}`;
    const start = now - ago;
    const answer = movieTurn(events, turn, start, limits);
    events.push({ at: start, event: { turn_id: turn, kind: 'user_message', data } }, ...answer.events);
    const { pause } = answer;
    if (pause !== undefined) {
      const answered = pause.at + 6 * SECOND;
      const rest = pause.resume('once', answered);
      events.push(
        { at: pause.at, event: { turn_id: turn, kind: 'approval', data: pause.approval } },
        {
          at: answered,
          event: {
            turn_id: turn,
            kind: 'approval_result',
            data: { approval_id: pause.approval.approval_id, decision: 'once' },
          },
        },
        ...rest.events,
      );
      engines.push(...(rest.engines ?? []));
    }
  };
  /**
   * What the person answers the question the last turn ended on: the agent's own recommendation,
   * or the card as it opened.
   *
   * @returns The message.
   */
  const agree = (): UserMessageData => {
    const asked = events.findLast(({ event }) => event.kind === 'ask' || event.kind === 'ui')?.event;
    if (asked?.kind === 'ask') {
      return { text: asked.data.recommended ?? asked.data.options[0] ?? 'Go on.' };
    }
    if (asked?.kind === 'ui') {
      const root = readTree(asked.data.spec);
      const value = root === null ? {} : startState(inputsOf(root));
      return { text: describeAnswer(asked.data, value), ui: { ui_id: asked.data.ui_id, value } };
    }
    return { text: 'Go on.' };
  };
  say(11 * MINUTE, { text: OPENING_MESSAGE });
  say(10 * MINUTE, agree());
  say(9 * MINUTE, agree());
  say(8 * MINUTE, agree());
  say(6 * MINUTE, { text: 'Go on with the animation tests.' });
  return { events, engines };
}

/** The disciplines whose projects have the film's subagents and its skill. */
export const FILM_DISCIPLINES: ReadonlySet<string> = new Set(
  catalog.disciplines.filter((discipline) => discipline.engines.includes(ENGINE_APP)).map((discipline) => discipline.id),
);
