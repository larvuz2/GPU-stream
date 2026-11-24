/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The control plane's HTTP API: its types, the guards that check its responses, and the client.
 *
 * Every request but the health check carries the signed-in user's Supabase access token as a
 * bearer token, and all of them speak JSON but a media upload, which is multipart. A failure
 * arrives as `{ "error": string }` or `{ "detail": string }` under a 4xx or 5xx status and leaves
 * here as an {@link ApiError} carrying that status, which is what the studio words its messages
 * from (402 out of credits, 404 a route this control plane does not serve yet, 409 a limit or a
 * turn already running, 503 a feature not configured). A body is `unknown` until a guard has
 * checked it, so a response of the wrong shape is an error here and never a broken render later.
 *
 * The studio's routes and shapes are the contract in `lathe/STUDIO.md`: projects, their engines
 * (sessions with a `project_id`), the agent's event log, the library, and GitHub. The event log is
 * read in pages after a cursor; an event whose kind or data this page does not know is skipped,
 * but still moves the cursor past it, so a newer control plane adds kinds without stalling an
 * older page.
 *
 * {@link ControlPlane} is the interface the studio is written against; {@link createControlPlane}
 * is its HTTP implementation and the studio's demo (`studio/demo.ts`) its in-memory one.
 * @module
 */
import { arrayOf, isBoolean, isNumber, isRecord, isString, nullable, type Guard } from './narrow';

/** The states a session passes through, in order; `ended` and `failed` are final. */
const SESSION_STATUSES = ['queued', 'starting', 'running', 'ended', 'failed'] as const;

/** One state of a session. */
export type SessionStatus = (typeof SESSION_STATUSES)[number];

/** A workstation session, as the control plane reports it; a project's engine is one. */
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
  /** The project it is an engine of, absent or `null` for a session started outside one. */
  project_id?: string | null;
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

/**
 * What the control plane says about itself, to anyone who asks.
 *
 * Each integration is `true` or `false` as the control plane reports it, or `null` from one that
 * does not report it (a control plane from before the studio), which the studio treats as unknown
 * rather than as off.
 */
export interface Health {
  /** Whether the control plane is up. */
  ok: boolean;
  /** Whether the agent can run: a model key is configured. */
  agent: boolean | null;
  /** Whether GitHub can be connected: an OAuth App is configured. */
  github: boolean | null;
  /** Whether images and videos can be generated: a generation key is configured. */
  generation: boolean | null;
  /** Whether it can sell credits. */
  billing: boolean | null;
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

/** The states of a step of the agent's plan. */
const PLAN_STATUSES = ['pending', 'active', 'done', 'blocked'] as const;

/** One state of a plan step. */
export type PlanStatus = (typeof PLAN_STATUSES)[number];

/** A step of the agent's plan for a project. */
export interface PlanItem {
  /** The step's identifier. */
  id: string;
  /** What the step is, in a few words. */
  title: string;
  /** Where the step stands. */
  status: PlanStatus;
}

/** A creative project: the conversation, engines, plan, and library the studio shows. */
export interface Project {
  /** The project's identifier. */
  id: string;
  /** The name its owner gave it. */
  name: string;
  /** The catalog discipline it belongs to. */
  discipline: string;
  /** The kind of work within the discipline, such as `Movie`. */
  format: string;
  /** Whether it is pinned to the top of the sidebar. */
  pinned: boolean;
  /** When it was created, as an ISO 8601 timestamp. */
  created_at: string;
  /** When anything of it last changed, as an ISO 8601 timestamp. */
  updated_at: string;
  /** The GitHub repository it is linked to, as `owner/name`, or `null`. */
  github_repo: string | null;
  /** The library's sections, in the order they are shown; the project's own, never a fixed list. */
  library_sections: string[];
  /** The agent's plan. */
  plan: PlanItem[];
}

/** What a project is created with. */
export interface NewProject {
  /** Its name. */
  name: string;
  /** The catalog discipline. */
  discipline: string;
  /** The kind of work within the discipline. */
  format: string;
}

/** The fields of a project that can be changed; each is left as it is when absent. */
export interface ProjectChanges {
  /** A new name. */
  name?: string;
  /** Pins or unpins it. */
  pinned?: boolean;
  /** The library's sections, in their new order. */
  library_sections?: string[];
}

/** The kinds of media a library asset or a tool's result carries. */
const MEDIA_KINDS = ['image', 'video', 'audio', 'file'] as const;

/** One kind of media. */
export type MediaKind = (typeof MEDIA_KINDS)[number];

/** A media file: a library asset's reference, or what a tool produced. */
export interface Media {
  /** What kind of file it is, which decides how it is shown. */
  kind: MediaKind;
  /** Where it is served from; a signed address that expires. */
  url: string;
  /** Its file name, where one was given. */
  name?: string;
}

/** An entry of a project's library: a character, an environment, a prop, a product, a shot. */
export interface Asset {
  /** The asset's identifier. */
  id: string;
  /** The library section it belongs to. */
  section: string;
  /** Its display name. */
  name: string;
  /** The tag prompts name it by, without the `@`, or `null` for one without a tag. */
  tag: string | null;
  /** What it is, in prose, or `null`. */
  description: string | null;
  /** Free-form details the agent or the person recorded, or `null`. */
  metadata: Record<string, unknown> | null;
  /** When it was created, as an ISO 8601 timestamp. */
  created_at: string;
  /** When it last changed, as an ISO 8601 timestamp. */
  updated_at: string;
  /** Its reference media, in order. */
  media: Media[];
  /** The image that stands for it in a grid, or `null` while it has none. */
  thumbnail_url: string | null;
}

/** What an asset is created with. */
export interface NewAsset {
  /** The section it goes in; a new name makes a new section. */
  section: string;
  /** Its name. */
  name: string;
  /** Its tag, without the `@`. */
  tag?: string;
  /** What it is. */
  description?: string;
  /** Free-form details. */
  metadata?: Record<string, unknown>;
}

/** A project's library: its sections and every asset in them. */
export interface Library {
  /** The sections, in the order they are shown. */
  sections: string[];
  /** The assets, each naming its section. */
  assets: Asset[];
}

/** The identifier of an agent turn, as the control plane mints it. */
export type TurnId = string | number;

/** What every event carries, whatever its kind. */
interface EventEnvelope {
  /** The event's place in the project's log; the cursor a page is read after. */
  id: number;
  /** The turn it belongs to, or `null` for one outside a turn. */
  turn_id: TurnId | null;
  /** When it was written, as an ISO 8601 timestamp. */
  created_at: string;
}

/** A message the person sent. */
export interface UserMessageData {
  /** The message. */
  text: string;
}

/** A piece of the agent's reply, in order. */
export interface TextData {
  /** The text, in a small subset of Markdown. */
  text: string;
}

/** The agent started calling a tool. */
export interface ToolStartData {
  /** The call's identifier, which the call's end names too. */
  call_id: string;
  /** The tool's name. */
  tool: string;
  /** What the call does, in words for the person. */
  title: string;
}

/** A tool call finished. */
export interface ToolEndData {
  /** The call's identifier. */
  call_id: string;
  /** Whether it succeeded. */
  ok: boolean;
  /** What it came to, in a line, or `null`. */
  summary: string | null;
  /** The images, videos, or files it produced. */
  media?: Media[];
}

/** The agent asks the person to decide. */
export interface AskData {
  /** The question. */
  question: string;
  /** The answers offered, each sent as the person's message when chosen. */
  options: string[];
}

/** The agent's plan changed. */
export interface PlanData {
  /** The whole plan, as it now stands. */
  items: PlanItem[];
}

/** An asset of the library was added or changed. */
export interface LibraryData {
  /** The asset, as it now stands. */
  asset: Asset;
}

/** An engine of the project was started or changed state. */
export interface EngineData {
  /** The engine, as it now stands. */
  engine: Session;
}

/** Something went wrong in the turn. */
export interface ErrorData {
  /** What went wrong, for the person. */
  message: string;
}

/** An event of a project's log, one of the kinds `lathe/STUDIO.md` names. */
export type StudioEvent = EventEnvelope &
  (
    | { kind: 'user_message'; data: UserMessageData }
    | { kind: 'text'; data: TextData }
    | { kind: 'tool_start'; data: ToolStartData }
    | { kind: 'tool_end'; data: ToolEndData }
    | { kind: 'ask'; data: AskData }
    | { kind: 'plan'; data: PlanData }
    | { kind: 'library'; data: LibraryData }
    | { kind: 'engine'; data: EngineData }
    | { kind: 'turn_end'; data: Record<string, unknown> }
    | { kind: 'error'; data: ErrorData }
  );

/** One page of a project's event log. */
export interface EventPage {
  /** The events this page understands, in order. */
  events: StudioEvent[];
  /** Whether a turn is running. */
  running: boolean;
  /** The highest event identifier the page held, understood or not, or `null` for an empty page. */
  cursor: number | null;
}

/** The person's GitHub connection. */
export interface GitHubStatus {
  /** Whether the control plane has a GitHub OAuth App to connect with. */
  configured: boolean;
  /** Whether the person has connected their account. */
  connected: boolean;
  /** Their GitHub login, once connected. */
  login: string | null;
  /** Their GitHub avatar, once connected. */
  avatar_url: string | null;
}

/** A repository of the person's that a project can be linked to. */
export interface GitHubRepo {
  /** `owner/name`. */
  full_name: string;
  /** Whether only invited people can see it. */
  private: boolean;
  /** Its page on GitHub. */
  html_url: string;
  /** When it last changed, as an ISO 8601 timestamp. */
  updated_at: string;
}

/** How a project is linked to a repository: an existing one, or one created for it. */
export type RepoLink = { repo: string } | { create: { name: string; private: boolean } };

/**
 * The operations the studio performs, whatever answers them.
 *
 * Each rejects with an {@link ApiError}.
 */
export interface ControlPlane {
  /** Reads what the control plane can do right now; the one call that needs no sign-in. */
  health(): Promise<Health>;
  /** Reads the signed-in account. */
  me(): Promise<Me>;
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
  /** Lists the account's projects, most recently updated first. */
  listProjects(): Promise<Project[]>;
  /** Creates a project. */
  createProject(project: NewProject): Promise<Project>;
  /** Reads one project. */
  getProject(id: string): Promise<Project>;
  /** Changes a project's name, pin, or library sections. */
  updateProject(id: string, changes: ProjectChanges): Promise<Project>;
  /** Deletes a project. */
  deleteProject(id: string): Promise<void>;
  /** Lists a project's engines. */
  listEngines(projectId: string): Promise<Session[]>;
  /** Starts an engine in a project; the call can take around ten seconds. */
  startEngine(projectId: string, request: LaunchRequest): Promise<Session>;
  /** Reads a project's events after a cursor, and whether a turn is running. */
  listEvents(projectId: string, after: number): Promise<EventPage>;
  /** Sends the person's message, which starts a turn; refused with 409 while one runs. */
  sendMessage(projectId: string, text: string): Promise<TurnId>;
  /** Stops the running turn. */
  stopTurn(projectId: string): Promise<void>;
  /** Reads a project's library. */
  getLibrary(projectId: string): Promise<Library>;
  /** Adds an asset to a project's library. */
  createAsset(projectId: string, asset: NewAsset): Promise<Asset>;
  /** Uploads a media file to an asset. */
  uploadMedia(projectId: string, assetId: string, file: File): Promise<Asset>;
  /** Deletes an asset. */
  deleteAsset(projectId: string, assetId: string): Promise<void>;
  /** Reads the person's GitHub connection. */
  github(): Promise<GitHubStatus>;
  /** Starts connecting GitHub and returns GitHub's authorization page, which returns to `returnTo`. */
  connectGitHub(returnTo: string): Promise<string>;
  /** Lists the person's repositories. */
  githubRepos(): Promise<GitHubRepo[]>;
  /** Disconnects GitHub. */
  disconnectGitHub(): Promise<void>;
  /** Links a project to a repository, creating it first when asked to. */
  linkRepo(projectId: string, link: RepoLink): Promise<Project>;
  /** Unlinks a project from its repository. */
  unlinkRepo(projectId: string): Promise<Project>;
}

/** The status an {@link ApiError} carries when no response arrived at all. */
export const NETWORK_ERROR = 0;

/** The status of a route the control plane does not serve, or of a record it does not have. */
export const NOT_FOUND = 404;

/** The status of a message sent while a turn is still running. */
export const TURN_RUNNING = 409;

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
 * Whether a request failed because the control plane does not serve the route yet, as a control
 * plane from before the studio answers every one of the studio's routes.
 *
 * @param error What the request rejected with.
 * @returns `true` for a 404.
 */
export function isMissing(error: unknown): boolean {
  return error instanceof ApiError && error.status === NOT_FOUND;
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

/**
 * Builds a guard for one of a fixed set of strings.
 *
 * @param values The strings the guard accepts.
 * @returns The guard.
 */
function oneOf<T extends string>(values: readonly T[]): Guard<T> {
  return (value: unknown): value is T => values.some((candidate) => candidate === value);
}

/**
 * Checks a value into a web address.
 *
 * The browser is sent to, and shows media from, the links the control plane returns, so one that
 * is not `http` or `https` (a `javascript:` URL, say) is refused here rather than followed.
 */
const isWebUrl: Guard<string> = (value): value is string => {
  if (!isString(value) || !URL.canParse(value)) {
    return false;
  }
  const { protocol } = new URL(value);
  return protocol === 'https:' || protocol === 'http:';
};

/**
 * Widens a guard to accept a field that is absent as well.
 *
 * @param guard The guard for the field's type.
 * @returns A guard for that type or `undefined`.
 */
function optional<T>(guard: Guard<T>): Guard<T | undefined> {
  return (value: unknown): value is T | undefined => value === undefined || guard(value);
}

const isNullableString = nullable(isString);
const isNullableNumber = nullable(isNumber);
const isNullableBoolean = nullable(isBoolean);
const isStrings = arrayOf(isString);

/** Checks a value into a {@link Session}. */
const isSession: Guard<Session> = (value): value is Session =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.app) &&
  isString(value.tier) &&
  isString(value.region) &&
  oneOf(SESSION_STATUSES)(value.status) &&
  isString(value.created_at) &&
  isNullableString(value.started_at) &&
  isNullableString(value.ended_at) &&
  isNullableString(value.end_reason) &&
  isNumber(value.credits_used) &&
  isNullableNumber(value.queue_position) &&
  optional(isNullableString)(value.project_id);

/** Checks a value into an {@link ApiKey}. */
const isApiKey: Guard<ApiKey> = (value): value is ApiKey =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.name) &&
  isString(value.prefix) &&
  isString(value.created_at) &&
  isNullableString(value.last_used_at);

/** The health report as it is sent: only `ok` is certain, the rest depend on the control plane's age. */
interface HealthReport {
  /** Whether the control plane is up. */
  ok: boolean;
  /** Whether the agent can run. */
  agent?: boolean | null;
  /** Whether GitHub can be connected. */
  github?: boolean | null;
  /** Whether media can be generated. */
  generation?: boolean | null;
  /** Whether it can sell credits. */
  billing?: boolean | null;
  /** The identifiers of the tiers that can be started right now. */
  tiers?: string[];
}

/** Checks a value into a {@link HealthReport}. */
const isHealthReport: Guard<HealthReport> = (value): value is HealthReport =>
  isRecord(value) &&
  isBoolean(value.ok) &&
  optional(isNullableBoolean)(value.agent) &&
  optional(isNullableBoolean)(value.github) &&
  optional(isNullableBoolean)(value.generation) &&
  optional(isNullableBoolean)(value.billing) &&
  optional(isStrings)(value.tiers);

/** Checks a value into a {@link Me}. */
const isMe: Guard<Me> = (value): value is Me =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.email) &&
  isNumber(value.credits) &&
  isNumber(value.max_sessions);

/** Checks a value into a {@link PlanItem}. */
const isPlanItem: Guard<PlanItem> = (value): value is PlanItem =>
  isRecord(value) && isString(value.id) && isString(value.title) && oneOf(PLAN_STATUSES)(value.status);

const isPlan = arrayOf(isPlanItem);

/** Checks a value into a {@link Project}. */
const isProject: Guard<Project> = (value): value is Project =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.name) &&
  isString(value.discipline) &&
  isString(value.format) &&
  isBoolean(value.pinned) &&
  isString(value.created_at) &&
  isString(value.updated_at) &&
  isNullableString(value.github_repo) &&
  isStrings(value.library_sections) &&
  isPlan(value.plan);

/** Checks a value into a {@link Media}. */
const isMedia: Guard<Media> = (value): value is Media =>
  isRecord(value) && oneOf(MEDIA_KINDS)(value.kind) && isWebUrl(value.url) && optional(isString)(value.name);

const isMediaList = arrayOf(isMedia);

/** Checks a value into an {@link Asset}. */
const isAsset: Guard<Asset> = (value): value is Asset =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.section) &&
  isString(value.name) &&
  isNullableString(value.tag) &&
  isNullableString(value.description) &&
  (value.metadata === null || isRecord(value.metadata)) &&
  isString(value.created_at) &&
  isString(value.updated_at) &&
  isMediaList(value.media) &&
  nullable(isWebUrl)(value.thumbnail_url);

/** Checks a value into a {@link Library}. */
const isLibrary: Guard<Library> = (value): value is Library =>
  isRecord(value) && isStrings(value.sections) && arrayOf(isAsset)(value.assets);

/** Checks a value into a {@link TurnId}. */
const isTurnId: Guard<TurnId> = (value): value is TurnId => isString(value) || isNumber(value);

/** Checks a value into an {@link EventEnvelope} with its kind and data still unchecked. */
const isEnvelope: Guard<EventEnvelope & { kind: string; data: Record<string, unknown> }> = (
  value,
): value is EventEnvelope & { kind: string; data: Record<string, unknown> } =>
  isRecord(value) &&
  isNumber(value.id) &&
  nullable(isTurnId)(value.turn_id) &&
  isString(value.created_at) &&
  isString(value.kind) &&
  isRecord(value.data);

/** Checks a value into the data of a message or a piece of text. */
const isTextData: Guard<TextData> = (value): value is TextData => isRecord(value) && isString(value.text);

/** Checks a value into a {@link ToolStartData}. */
const isToolStart: Guard<ToolStartData> = (value): value is ToolStartData =>
  isRecord(value) && isString(value.call_id) && isString(value.tool) && isString(value.title);

/** Checks a value into a {@link ToolEndData}. */
const isToolEnd: Guard<ToolEndData> = (value): value is ToolEndData =>
  isRecord(value) &&
  isString(value.call_id) &&
  isBoolean(value.ok) &&
  isNullableString(value.summary) &&
  optional(isMediaList)(value.media);

/** Checks a value into an {@link AskData}. */
const isAsk: Guard<AskData> = (value): value is AskData =>
  isRecord(value) && isString(value.question) && isStrings(value.options);

/**
 * Reads one event of a page, by the kind it names.
 *
 * @param value The event as it was sent.
 * @returns The event, typed, or `null` for one of a kind this page does not know or whose data is
 *   not of its kind's shape.
 */
function parseEvent(value: unknown): StudioEvent | null {
  if (!isEnvelope(value)) {
    return null;
  }
  const envelope: EventEnvelope = { id: value.id, turn_id: value.turn_id, created_at: value.created_at };
  const { data } = value;
  switch (value.kind) {
    case 'user_message':
      return isTextData(data) ? { ...envelope, kind: 'user_message', data } : null;
    case 'text':
      return isTextData(data) ? { ...envelope, kind: 'text', data } : null;
    case 'tool_start':
      return isToolStart(data) ? { ...envelope, kind: 'tool_start', data } : null;
    case 'tool_end':
      return isToolEnd(data) ? { ...envelope, kind: 'tool_end', data } : null;
    case 'ask':
      return isAsk(data) ? { ...envelope, kind: 'ask', data } : null;
    case 'plan':
      return isPlan(data.items) ? { ...envelope, kind: 'plan', data: { items: data.items } } : null;
    case 'library':
      return isAsset(data.asset) ? { ...envelope, kind: 'library', data: { asset: data.asset } } : null;
    case 'engine':
      return isSession(data.engine) ? { ...envelope, kind: 'engine', data: { engine: data.engine } } : null;
    case 'turn_end':
      return { ...envelope, kind: 'turn_end', data };
    case 'error':
      return isString(data.message) ? { ...envelope, kind: 'error', data: { message: data.message } } : null;
    default:
      return null;
  }
}

/**
 * Reads a page of the event log.
 *
 * @param body The response body.
 * @returns The page.
 * @throws ApiError With status 502 when the body is not a page of events.
 */
function parseEventPage(body: unknown): EventPage {
  if (!isRecord(body) || !Array.isArray(body.events) || !isBoolean(body.running)) {
    throw new ApiError(502, 'The control plane sent a response this page does not understand.');
  }
  const events: StudioEvent[] = [];
  let cursor: number | null = null;
  for (const raw of body.events) {
    if (isRecord(raw) && isNumber(raw.id)) {
      cursor = Math.max(cursor ?? raw.id, raw.id);
    }
    const event = parseEvent(raw);
    if (event !== null) {
      events.push(event);
    }
  }
  return { events, running: body.running, cursor };
}

/** The GitHub status as it is sent, before an absent login or avatar is read as `null`. */
interface GitHubReport {
  /** Whether an OAuth App is configured. */
  configured: boolean;
  /** Whether the person has connected. */
  connected: boolean;
  /** Their login. */
  login?: string | null;
  /** Their avatar. */
  avatar_url?: string | null;
}

/** Checks a value into a {@link GitHubReport}. */
const isGitHubReport: Guard<GitHubReport> = (value): value is GitHubReport =>
  isRecord(value) &&
  isBoolean(value.configured) &&
  isBoolean(value.connected) &&
  optional(isNullableString)(value.login) &&
  optional(nullable(isWebUrl))(value.avatar_url);

/** Checks a value into a {@link GitHubRepo}. */
const isGitHubRepo: Guard<GitHubRepo> = (value): value is GitHubRepo =>
  isRecord(value) &&
  isString(value.full_name) &&
  isBoolean(value.private) &&
  isWebUrl(value.html_url) &&
  isString(value.updated_at);

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

/**
 * Reads the control plane's explanation of a refusal.
 *
 * The existing routes say it as `error`, the studio's as `detail`, which is also what the web
 * framework answers a route it does not serve with; a `detail` that is not a string (a list of
 * validation failures) is left for the status to word.
 *
 * @param payload The parsed body of the refusal.
 * @returns The explanation, or `null` when the body has none.
 */
function refusalText(payload: unknown): string | null {
  if (!isRecord(payload)) {
    return null;
  }
  if (isString(payload.error)) {
    return payload.error;
  }
  return isString(payload.detail) ? payload.detail : null;
}

/** How long a request may take; a launch alone can take ten seconds. */
const REQUEST_TIMEOUT_MS = 45_000;

/** How long an upload may take, which a large video on a slow link needs. */
const UPLOAD_TIMEOUT_MS = 10 * 60_000;

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
   * @param body The JSON body, or a form for a multipart upload, when the request has one.
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
    const form = body instanceof FormData ? body : null;
    let response: Response;
    try {
      response = await fetch(`${baseUrl}${path}`, {
        method,
        headers: {
          Accept: 'application/json',
          ...(token === null ? {} : { Authorization: `Bearer ${token}` }),
          // A form sets its own multipart type, boundary included.
          ...(body === undefined || form !== null ? {} : { 'Content-Type': 'application/json' }),
        },
        body: form ?? (body === undefined ? null : JSON.stringify(body)),
        signal: AbortSignal.timeout(form === null ? REQUEST_TIMEOUT_MS : UPLOAD_TIMEOUT_MS),
      });
    } catch {
      throw new ApiError(NETWORK_ERROR, 'Could not reach the control plane. Check your connection and try again.');
    }
    const payload: unknown = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(
        response.status,
        refusalText(payload) ?? `The request failed with status ${response.status}.`,
      );
    }
    return payload;
  }

  /**
   * Builds the path of a project's route.
   *
   * @param projectId The project.
   * @param rest What follows the project's own path, with its leading slash.
   * @returns The path.
   */
  const projectPath = (projectId: string, rest = ''): string => `/v1/projects/${encodeURIComponent(projectId)}${rest}`;

  /**
   * Builds the path of an asset's route.
   *
   * @param projectId The project.
   * @param assetId The asset.
   * @param rest What follows the asset's own path, with its leading slash.
   * @returns The path.
   */
  const assetPath = (projectId: string, assetId: string, rest = ''): string =>
    projectPath(projectId, `/library/${encodeURIComponent(assetId)}${rest}`);

  return {
    health: async () => {
      const report = expect(await request('GET', '/v1/health', undefined, false), isHealthReport);
      return {
        ok: report.ok,
        agent: report.agent ?? null,
        github: report.github ?? null,
        generation: report.generation ?? null,
        billing: report.billing ?? null,
        tiers: report.tiers ?? null,
      };
    },
    me: async () => expect(await request('GET', '/v1/me'), isMe),
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
    listProjects: async () => field(await request('GET', '/v1/projects'), 'projects', arrayOf(isProject)),
    createProject: async (project) => field(await request('POST', '/v1/projects', project), 'project', isProject),
    getProject: async (id) => field(await request('GET', projectPath(id)), 'project', isProject),
    updateProject: async (id, changes) =>
      field(await request('PATCH', projectPath(id), changes), 'project', isProject),
    deleteProject: async (id) => {
      await request('DELETE', projectPath(id));
    },
    listEngines: async (projectId) =>
      field(await request('GET', projectPath(projectId, '/engines')), 'engines', arrayOf(isSession)),
    startEngine: async (projectId, launch) =>
      field(await request('POST', projectPath(projectId, '/engines'), launch), 'engine', isSession),
    listEvents: async (projectId, after) =>
      parseEventPage(await request('GET', projectPath(projectId, `/events?after=${after}`))),
    sendMessage: async (projectId, text) =>
      field(await request('POST', projectPath(projectId, '/messages'), { text }), 'turn_id', isTurnId),
    stopTurn: async (projectId) => {
      await request('POST', projectPath(projectId, '/stop'));
    },
    getLibrary: async (projectId) => expect(await request('GET', projectPath(projectId, '/library')), isLibrary),
    createAsset: async (projectId, asset) =>
      field(await request('POST', projectPath(projectId, '/library'), asset), 'asset', isAsset),
    uploadMedia: async (projectId, assetId, file) => {
      const form = new FormData();
      form.append('file', file, file.name);
      return field(await request('POST', assetPath(projectId, assetId, '/media'), form), 'asset', isAsset);
    },
    deleteAsset: async (projectId, assetId) => {
      await request('DELETE', assetPath(projectId, assetId));
    },
    github: async () => {
      const report = expect(await request('GET', '/v1/github'), isGitHubReport);
      return {
        configured: report.configured,
        connected: report.connected,
        login: report.login ?? null,
        avatar_url: report.avatar_url ?? null,
      };
    },
    connectGitHub: async (returnTo) =>
      field(await request('POST', '/v1/github/connect', { return_to: returnTo }), 'url', isWebUrl),
    githubRepos: async () => field(await request('GET', '/v1/github/repos'), 'repos', arrayOf(isGitHubRepo)),
    disconnectGitHub: async () => {
      await request('DELETE', '/v1/github');
    },
    linkRepo: async (projectId, link) =>
      field(await request('POST', projectPath(projectId, '/github'), link), 'project', isProject),
    unlinkRepo: async (projectId) =>
      field(await request('DELETE', projectPath(projectId, '/github')), 'project', isProject),
  };
}
