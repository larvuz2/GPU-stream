/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The dashboard's preview: a control plane made of fixtures, for looking at the dashboard without
 * an account or a backend.
 *
 * `/app/?preview=1` renders the dashboard against {@link createPreviewControlPlane} instead of the
 * HTTP client, under a banner that says so. This module is a chunk of its own that is only fetched
 * when that flag is present. It holds no credentials and sends no request: every answer is
 * computed in memory, so the preview cannot reach an account's data, and it replaces the signed-in
 * path rather than opening a way around it.
 *
 * A session here is a schedule of states, and what a call returns is the schedule read at the
 * current time, so a session launched in the preview queues, starts, and runs the way a real one
 * does under the dashboard's own polling. `scene` picks the state the page opens in (`running` by
 * default; `queued`, `starting`, `ended`, `failed`, `empty`).
 * @module
 */
import {
  ApiError,
  type ApiKey,
  type ControlPlane,
  type Health,
  type Me,
  type Session,
  type SessionStatus,
} from '../lib/api';
import { AUTO_REGION, catalog, findTier, liveApps } from '../lib/catalog';
import { NOT_CONFIGURED } from './messages';

/** The address the preview's account is shown under. */
export const PREVIEW_EMAIL = 'you@example.com';

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** One state of a simulated session, entered at a point in time. */
interface Phase {
  /** When the state is entered, in milliseconds since the epoch. */
  at: number;
  /** The state. */
  status: SessionStatus;
  /** The place in line, for a queued state. */
  queuePosition?: number;
  /** Why the session ended, for a final state. */
  endReason?: string;
}

/** A simulated session: what it runs, and the states it passes through. */
interface Simulation {
  /** The session's identifier. */
  id: string;
  /** The catalog app. */
  app: string;
  /** The catalog tier. */
  tier: string;
  /** The catalog region. */
  region: string;
  /** The states, in the order they are entered. */
  phases: Phase[];
}

/**
 * Reads a simulated session at a point in time.
 *
 * @param simulation The session's schedule.
 * @param now The time to read it at.
 * @returns The session as the control plane would report it then.
 */
function snapshot(simulation: Simulation, now: number): Session {
  const reached = simulation.phases.filter((phase) => phase.at <= now);
  const first = simulation.phases[0];
  const current = reached.at(-1) ?? first;
  const started = reached.find((phase) => phase.status === 'running');
  const ended = reached.find((phase) => phase.status === 'ended' || phase.status === 'failed');
  const ranUntil = ended?.at ?? now;
  const rate = findTier(simulation.tier)?.credits_per_minute ?? 0;
  return {
    id: simulation.id,
    app: simulation.app,
    tier: simulation.tier,
    region: simulation.region,
    status: current?.status ?? 'ended',
    created_at: new Date(first?.at ?? now).toISOString(),
    started_at: started === undefined ? null : new Date(started.at).toISOString(),
    ended_at: ended === undefined ? null : new Date(ended.at).toISOString(),
    end_reason: ended?.endReason ?? null,
    credits_used: started === undefined ? 0 : Math.ceil((ranUntil - started.at) / MINUTE) * rate,
    queue_position: current?.status === 'queued' ? (current.queuePosition ?? null) : null,
  };
}

/**
 * The sessions a scene opens with.
 *
 * @param scene The scene's name; an unknown one is the default.
 * @param now The time the preview starts at.
 * @returns The schedules, the one in flight first.
 */
function sceneSessions(scene: string | null, now: number): Simulation[] {
  const app = liveApps[0]?.id ?? catalog.apps[0]?.id ?? 'app';
  const [small, medium, large] = [catalog.tiers[0], catalog.tiers[1] ?? catalog.tiers[0], catalog.tiers.at(-2)].map(
    (tier) => tier?.id ?? 'tier',
  );
  const region = catalog.regions.at(1)?.id ?? AUTO_REGION;
  const session = (id: string, tier: string | undefined, phases: Phase[]): Simulation => ({
    id,
    app,
    tier: tier ?? 'tier',
    region,
    phases,
  });
  const history = [
    session('preview-3', medium, [
      { at: now - DAY - 47 * MINUTE, status: 'running' },
      { at: now - DAY, status: 'ended', endReason: 'idle' },
    ]),
    session('preview-2', large, [
      { at: now - 2 * DAY - 2 * HOUR, status: 'running' },
      { at: now - 2 * DAY - 48 * MINUTE, status: 'ended', endReason: 'user' },
    ]),
    session('preview-1', small, [
      { at: now - 3 * DAY, status: 'starting' },
      { at: now - 3 * DAY + MINUTE, status: 'failed', endReason: 'The workstation did not come up in time' },
    ]),
  ];
  switch (scene) {
    case 'empty':
      return [];
    case 'queued':
      return [session('preview-4', medium, [{ at: now - 40_000, status: 'queued', queuePosition: 3 }]), ...history];
    case 'starting':
      return [session('preview-4', medium, [{ at: now - 8000, status: 'starting' }]), ...history];
    case 'ended':
      return [
        session('preview-4', medium, [
          { at: now - 31 * MINUTE, status: 'running' },
          { at: now + 3000, status: 'ended', endReason: 'idle' },
        ]),
        ...history,
      ];
    case 'failed':
      return [
        session('preview-4', medium, [
          { at: now - 20_000, status: 'starting' },
          { at: now + 3000, status: 'failed', endReason: 'The workstation did not come up in time' },
        ]),
        ...history,
      ];
    default:
      return [session('preview-4', medium, [{ at: now - 18 * MINUTE - 24_000, status: 'running' }]), ...history];
  }
}

/**
 * Builds a control plane that answers from memory.
 *
 * @param scene The state to open in, as the page's `scene` parameter gave it.
 * @returns The control plane.
 */
export function createPreviewControlPlane(scene: string | null): ControlPlane {
  const opened = Date.now();
  let simulations = sceneSessions(scene, opened);
  let keys: ApiKey[] =
    scene === 'empty'
      ? []
      : [
          {
            id: 'preview-key-1',
            name: 'Claude on my laptop',
            prefix: 'lathe_3f9aQ2',
            created_at: new Date(opened - 6 * DAY).toISOString(),
            last_used_at: new Date(opened - 2 * HOUR).toISOString(),
          },
        ];
  let counter = 4;
  const me: Me = {
    id: 'preview-user',
    email: PREVIEW_EMAIL,
    credits: scene === 'empty' ? catalog.signup_credits : 412,
    max_sessions: 2,
  };

  /**
   * Finds a session's schedule.
   *
   * @param id The session's identifier.
   * @returns The schedule.
   * @throws ApiError With status 404 for an unknown session.
   */
  function find(id: string): Simulation {
    const simulation = simulations.find((candidate) => candidate.id === id);
    if (simulation === undefined) {
      throw new ApiError(404, 'No such session.');
    }
    return simulation;
  }

  // Every tier but the largest, so the preview shows what a tier that is not switched on looks like.
  const health: Health = {
    ok: true,
    supabase: true,
    billing: false,
    tiers: catalog.tiers.slice(0, Math.max(1, catalog.tiers.length - 1)).map((tier) => tier.id),
  };

  return {
    health: () => Promise.resolve(health),
    me: () => Promise.resolve(me),
    listSessions: () => Promise.resolve(simulations.map((simulation) => snapshot(simulation, Date.now()))),
    createSession: (request) => {
      const now = Date.now();
      counter += 1;
      const simulation: Simulation = {
        id: `preview-${counter}`,
        ...request,
        phases: [
          { at: now, status: 'queued', queuePosition: 2 },
          { at: now + 5000, status: 'queued', queuePosition: 1 },
          { at: now + 10_000, status: 'starting' },
          { at: now + 18_000, status: 'running' },
        ],
      };
      simulations = [simulation, ...simulations];
      return Promise.resolve(snapshot(simulation, now));
    },
    sessionLink: () => Promise.reject(new ApiError(NOT_CONFIGURED, 'The preview has no stream to open.')),
    stopSession: (id) => {
      const now = Date.now();
      const simulation = find(id);
      simulation.phases = [
        ...simulation.phases.filter((phase) => phase.at <= now),
        { at: now, status: 'ended', endReason: 'user' },
      ];
      return Promise.resolve(snapshot(simulation, now));
    },
    listApiKeys: () => Promise.resolve(keys),
    createApiKey: (name) => {
      counter += 1;
      const key: ApiKey = {
        id: `preview-key-${counter}`,
        name,
        prefix: 'lathe_previe',
        created_at: new Date().toISOString(),
        last_used_at: null,
      };
      keys = [key, ...keys];
      return Promise.resolve({ key, secret: 'lathe_preview_sample_key_not_a_real_secret' });
    },
    revokeApiKey: (id) => {
      keys = keys.filter((key) => key.id !== id);
      return Promise.resolve();
    },
    checkout: () => Promise.reject(new ApiError(NOT_CONFIGURED, 'The preview has no checkout.')),
  };
}
