/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What the demo's scenes are written with: an event waiting for its time, a turn of the demo's
 * agent as a script, and an engine as a schedule of states.
 *
 * The demo's control plane (`demo.ts`) plays these under the studio's own polling. A scene is a
 * {@link Script}: events with the times they are written at, the engines it starts, and, where the
 * agent asks before a tool, a {@link Pause} that holds the turn until the person answers and then
 * writes the rest of it. An engine is a {@link Simulation}, read at a point in time by
 * {@link snapshot} as the control plane would report it then.
 * @module
 */
import type {
  ApprovalData,
  ApprovalDecision,
  Asset,
  EngineStream,
  Media,
  Session,
  SessionStatus,
  StudioEvent,
  TurnId,
} from '../lib/api';
import { catalog } from '../lib/catalog';

export const SECOND = 1000;
export const MINUTE = 60 * SECOND;
export const HOUR = 60 * MINUTE;
export const DAY = 24 * HOUR;

/**
 * A still of the site's artwork, as a media file.
 *
 * @param file Its file under `public/media`.
 * @param name The name it is shown under.
 * @returns The file.
 */
export const still = (file: string, name: string): Media => ({ kind: 'image', url: `/media/${file}`, name });

/** One state of a simulated engine, entered at a point in time. */
export interface Phase {
  /** When the state is entered, in milliseconds since the epoch. */
  at: number;
  /** The state. */
  status: SessionStatus;
  /** Why it ended, for a final state. */
  reason?: string;
}

/** A simulated engine: what it runs, for which project, and the states it passes through. */
export interface Simulation {
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
  /** The pictures it streams, for an engine that streams more than its desktop. */
  streams?: EngineStream[];
}

/**
 * Reads a simulated engine at a point in time.
 *
 * @param simulation The engine's schedule.
 * @param now The time to read it at.
 * @returns The engine as the control plane would report it then.
 */
export function snapshot(simulation: Simulation, now: number): Session {
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
    ...(simulation.streams === undefined ? {} : { streams: simulation.streams }),
  };
}

/** Leaves keys out of each member of a union, keeping the union. */
export type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;

/** An event as the demo's agent writes it, before the log numbers and dates it. */
export type EventBody = DistributiveOmit<StudioEvent, 'id' | 'created_at'>;

/** An event waiting for its time. */
export interface Scheduled {
  /** When it is written, in milliseconds since the epoch. */
  at: number;
  /** What it is. */
  event: EventBody;
}

/** Where a turn of the demo's agent waits for the person: an approval, and how the turn goes on. */
export interface Pause {
  /** The turn that waits. */
  turn: TurnId;
  /** When the approval is written. */
  at: number;
  /** The approval. */
  approval: ApprovalData;
  /**
   * Writes the rest of the turn.
   *
   * @param decision The person's answer; `always` too for a tool they already always allow.
   * @param start When the turn goes on.
   * @returns What follows.
   */
  resume: (decision: ApprovalDecision, start: number) => Script;
}

/** A turn of the demo's agent, or the rest of one: its events, and what it sets going. */
export interface Script {
  /** The events, each with its time. */
  events: Scheduled[];
  /** The engines it starts. */
  engines?: Simulation[];
  /** Where it waits for the person, for a turn that asks before a tool. */
  pause?: Pause;
}

/**
 * Builds an asset of a library.
 *
 * @param fields What sets it apart.
 * @param at When it was made.
 * @returns The asset.
 */
export function asset(
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
