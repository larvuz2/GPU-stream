/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The control plane's HTTP API: its types, the guards that check its responses, and the client.
 *
 * Every request but the health check carries the signed-in user's Supabase access token as a
 * bearer token, and all of them speak JSON. A failure arrives as `{ "error": string }` under a 4xx
 * or 5xx status and leaves here as an {@link ApiError} carrying that status, which is what the
 * dashboard words its messages from (402 out of credits, 409 a limit, 503 a feature not
 * configured). A body is `unknown` until a guard has checked it, so a response of the wrong shape
 * is an error here and never a broken render later.
 *
 * {@link ControlPlane} is the interface the dashboard is written against; {@link createControlPlane}
 * is its HTTP implementation and the dashboard's preview (`dashboard/preview.ts`) its in-memory one.
 * @module
 */
import { arrayOf, isBoolean, isNumber, isRecord, isString, nullable, type Guard } from './narrow';

/** The states a session passes through, in order; `ended` and `failed` are final. */
const SESSION_STATUSES = ['queued', 'starting', 'running', 'ended', 'failed'] as const;

/** One state of a session. */
export type SessionStatus = (typeof SESSION_STATUSES)[number];

/** A workstation session, as the control plane reports it. */
export interface Session {
  /** The session's identifier. */
  id: string;
  /** The catalog app it runs. */
  app: string;
  /** The catalog tier it runs on. */
  tier: string;
  /** The catalog region it was asked for. */
  region: string;
  /** Where the session is in its life. */
  status: SessionStatus;
  /** When it was requested, as an ISO 8601 timestamp. */
  created_at: string;
  /** When its workstation came up, or `null` before that. */
  started_at: string | null;
  /** When it stopped, or `null` while it has not. */
  ended_at: string | null;
  /** Why it stopped, or `null` while it has not or when no reason was recorded. */
  end_reason: string | null;
  /** Credits it has cost so far. */
  credits_used: number;
  /** Its place in line while queued, or `null` otherwise. */
  queue_position: number | null;
}

/** An API key an agent authenticates with; the secret itself is only ever returned at creation. */
export interface ApiKey {
  /** The key's identifier. */
  id: string;
  /** The name its owner gave it. */
  name: string;
  /** The leading characters of the secret, enough to tell keys apart. */
  prefix: string;
  /** When it was created, as an ISO 8601 timestamp. */
  created_at: string;
  /** When it last authenticated a request, or `null` if it never has. */
  last_used_at: string | null;
}

/** The signed-in account. */
export interface Me {
  /** The account's identifier. */
  id: string;
  /** The account's email address. */
  email: string;
  /** The credit balance. */
  credits: number;
  /** How many sessions the account may have active at once. */
  max_sessions: number;
}

/** What the control plane says about itself, to anyone who asks. */
export interface Health {
  /** Whether the control plane is up. */
  ok: boolean;
  /** Whether it is connected to Supabase. */
  supabase: boolean;
  /** Whether it can sell credits. */
  billing: boolean;
  /**
   * The identifiers of the tiers that can be started right now, or `null` from a control plane
   * that does not report them, which means every tier can.
   */
  tiers: string[] | null;
}

/** What a session is launched with: identifiers from the catalog. */
export interface LaunchRequest {
  /** The app to run. */
  app: string;
  /** The tier to run it on. */
  tier: string;
  /** The region to run it in. */
  region: string;
}

/** A key just created, with the one copy of its secret. */
export interface CreatedKey {
  /** The key's record. */
  key: ApiKey;
  /** The secret, which the control plane does not return again. */
  secret: string;
}

/**
 * The operations the dashboard performs, whatever answers them.
 *
 * Each rejects with an {@link ApiError}.
 */
export interface ControlPlane {
  /** Reads what the control plane can do right now; the one call that needs no sign-in. */
  health(): Promise<Health>;
  /** Reads the signed-in account. */
  me(): Promise<Me>;
  /** Lists the active sessions, then the most recent ended ones. */
  listSessions(): Promise<Session[]>;
  /** Starts a session; the call can take around ten seconds. */
  createSession(request: LaunchRequest): Promise<Session>;
  /** Mints a fresh link that opens a running session's stream. */
  sessionLink(id: string): Promise<string>;
  /** Stops a session. */
  stopSession(id: string): Promise<Session>;
  /** Lists the account's API keys. */
  listApiKeys(): Promise<ApiKey[]>;
  /** Creates an API key and returns its secret once. */
  createApiKey(name: string): Promise<CreatedKey>;
  /** Revokes an API key. */
  revokeApiKey(id: string): Promise<void>;
  /** Starts a checkout for a credit pack and returns the page to send the browser to. */
  checkout(pack: string): Promise<string>;
}

/** The status an {@link ApiError} carries when no response arrived at all. */
export const NETWORK_ERROR = 0;

/** A failed control plane request. */
export class ApiError extends Error {
  /** The HTTP status, or {@link NETWORK_ERROR} when the request never got an answer. */
  readonly status: number;

  /**
   * @param status The HTTP status of the failure.
   * @param message The control plane's own explanation, or one worded here.
   */
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * Whether a session still holds, or waits for, a workstation.
 *
 * @param session The session.
 * @returns `true` while it is queued, starting, or running.
 */
export function isActive(session: Session): boolean {
  return session.status === 'queued' || session.status === 'starting' || session.status === 'running';
}

/** Checks a value into a {@link SessionStatus}. */
const isSessionStatus: Guard<SessionStatus> = (value): value is SessionStatus =>
  SESSION_STATUSES.some((status) => status === value);

/**
 * Checks a value into a web address.
 *
 * The browser is sent to the links the control plane returns, so one that is not `http` or
 * `https` (a `javascript:` URL, say) is refused here rather than followed.
 */
const isWebUrl: Guard<string> = (value): value is string => {
  if (!isString(value) || !URL.canParse(value)) {
    return false;
  }
  const { protocol } = new URL(value);
  return protocol === 'https:' || protocol === 'http:';
};

const isNullableString = nullable(isString);
const isNullableNumber = nullable(isNumber);

/** Checks a value into a {@link Session}. */
const isSession: Guard<Session> = (value): value is Session =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.app) &&
  isString(value.tier) &&
  isString(value.region) &&
  isSessionStatus(value.status) &&
  isString(value.created_at) &&
  isNullableString(value.started_at) &&
  isNullableString(value.ended_at) &&
  isNullableString(value.end_reason) &&
  isNumber(value.credits_used) &&
  isNullableNumber(value.queue_position);

/** Checks a value into an {@link ApiKey}. */
const isApiKey: Guard<ApiKey> = (value): value is ApiKey =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.name) &&
  isString(value.prefix) &&
  isString(value.created_at) &&
  isNullableString(value.last_used_at);

/** The health report as it is sent: a control plane that predates `tiers` leaves it out. */
interface HealthReport {
  /** Whether the control plane is up. */
  ok: boolean;
  /** Whether it is connected to Supabase. */
  supabase: boolean;
  /** Whether it can sell credits. */
  billing: boolean;
  /** The identifiers of the tiers that can be started right now. */
  tiers?: string[];
}

/** Checks a value into a {@link HealthReport}. */
const isHealthReport: Guard<HealthReport> = (value): value is HealthReport =>
  isRecord(value) &&
  isBoolean(value.ok) &&
  isBoolean(value.supabase) &&
  isBoolean(value.billing) &&
  (value.tiers === undefined || arrayOf(isString)(value.tiers));

/** Checks a value into a {@link Me}. */
const isMe: Guard<Me> = (value): value is Me =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.email) &&
  isNumber(value.credits) &&
  isNumber(value.max_sessions);

/**
 * Checks a whole response body into a type.
 *
 * @param body The parsed body.
 * @param guard The guard for the expected type.
 * @returns The body, typed.
 * @throws ApiError With status 502 when the body is not of that type.
 */
function expect<T>(body: unknown, guard: Guard<T>): T {
  if (guard(body)) {
    return body;
  }
  throw new ApiError(502, 'The control plane sent a response this page does not understand.');
}

/**
 * Reads one field of a response body.
 *
 * @param body The parsed body.
 * @param key The field's name.
 * @param guard The guard for the field's type.
 * @returns The field, typed.
 * @throws ApiError With status 502 when the body lacks the field or it is of another type.
 */
function field<T>(body: unknown, key: string, guard: Guard<T>): T {
  return expect(isRecord(body) ? body[key] : undefined, guard);
}

/** How long a request may take; a launch alone can take ten seconds. */
const REQUEST_TIMEOUT_MS = 45_000;

/**
 * Builds the HTTP client of the control plane.
 *
 * @param baseUrl The API's base URL, with no trailing slash.
 * @param accessToken Returns the user's current Supabase access token, or `null` when signed out.
 *   It is called on every request, so a token Supabase refreshed is the one sent.
 * @returns The client.
 */
export function createControlPlane(baseUrl: string, accessToken: () => Promise<string | null>): ControlPlane {
  /**
   * Sends one request and returns its parsed body.
   *
   * @param method The HTTP method.
   * @param path The path under the base URL.
   * @param body The JSON body, when the request has one.
   * @param authenticated Whether the request carries the user's token; only the health check
   *   does not.
   * @returns The parsed response body, or `null` for an empty one.
   * @throws ApiError For a response outside the 2xx range, a request that got no response, or a
   *   user who is no longer signed in.
   */
  async function request(method: string, path: string, body?: unknown, authenticated = true): Promise<unknown> {
    const token = authenticated ? await accessToken() : null;
    if (authenticated && token === null) {
      throw new ApiError(401, 'Your sign-in has expired. Sign in again to continue.');
    }
    let response: Response;
    try {
      response = await fetch(`${baseUrl}${path}`, {
        method,
        headers: {
          Accept: 'application/json',
          ...(token === null ? {} : { Authorization: `Bearer ${token}` }),
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? null : JSON.stringify(body),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
    } catch {
      throw new ApiError(NETWORK_ERROR, 'Could not reach the control plane. Check your connection and try again.');
    }
    const payload: unknown = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const explanation = isRecord(payload) && isString(payload.error) ? payload.error : null;
      throw new ApiError(response.status, explanation ?? `The request failed with status ${response.status}.`);
    }
    return payload;
  }

  return {
    health: async () => {
      const report = expect(await request('GET', '/v1/health', undefined, false), isHealthReport);
      return { ...report, tiers: report.tiers ?? null };
    },
    me: async () => expect(await request('GET', '/v1/me'), isMe),
    listSessions: async () => field(await request('GET', '/v1/sessions'), 'sessions', arrayOf(isSession)),
    createSession: async (launch) => field(await request('POST', '/v1/sessions', launch), 'session', isSession),
    sessionLink: async (id) =>
      field(await request('POST', `/v1/sessions/${encodeURIComponent(id)}/link`), 'url', isWebUrl),
    stopSession: async (id) =>
      field(await request('DELETE', `/v1/sessions/${encodeURIComponent(id)}`), 'session', isSession),
    listApiKeys: async () => field(await request('GET', '/v1/api-keys'), 'keys', arrayOf(isApiKey)),
    createApiKey: async (name) => {
      const body = await request('POST', '/v1/api-keys', { name });
      return { key: field(body, 'key', isApiKey), secret: field(body, 'secret', isString) };
    },
    revokeApiKey: async (id) => {
      await request('DELETE', `/v1/api-keys/${encodeURIComponent(id)}`);
    },
    checkout: async (pack) => field(await request('POST', '/v1/billing/checkout', { pack }), 'url', isWebUrl),
  };
}
