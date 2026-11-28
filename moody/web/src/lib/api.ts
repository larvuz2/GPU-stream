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
 * The studio's routes and shapes are the contract in `moody/STUDIO.md`: projects, their engines
 * (sessions with a `project_id`), the agent's event log, the library, GitHub, and Epic. The event log is
 * read in pages after a cursor; an event whose kind or data this page does not know is skipped,
 * but still moves the cursor past it, so a newer control plane adds kinds without stalling an
 * older page.
 *
 * The agent runs on Anthropic's loop (the contract's "the agent on Anthropic's loop"), which adds
 * to the log what a person watches it do: its reasoning (`thinking`), an answer that grows while
 * it is written (`text` with a `block`), a card per subagent (`agent`), a question before
 * something costly (`approval`, answered through {@link ControlPlane.approve}), an interactive
 * card (`ui`, whose `spec` stays `unknown` here: the card that renders it narrows it), and what
 * the turn cost (`usage`). An event of a subagent names it (`agent_id`), on the event or in its
 * data; both are read into {@link EventEnvelope.agent_id}.
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

/**
 * One picture of an engine that streams more than its desktop: an Unreal engine's `Desktop` and
 * `Unreal` (the editor's own stream).
 *
 * The control plane mints each link for the listing that reports it, so it is fresh when the page
 * loads it; a later load asks for another ({@link ControlPlane.sessionLink} with the stream's name).
 */
export interface EngineStream {
  /** What the stream shows, as the Screen panel names it: `Desktop` or `Unreal`. */
  name: string;
  /** A link that opens it, minted for the listing. */
  url: string;
}

/** The name of the picture a session's own link opens, which every engine has. */
export const DESKTOP_STREAM = 'Desktop';

/** How an engine of this version opens an Unreal project, by the version it was saved with. */
const UNREAL_VERSIONS = ['same', 'older', 'newer', 'source', 'unknown'] as const;

/** An Unreal project found in a running Unreal engine's workspace, such as a game cloned there. */
export interface UnrealProject {
  /** The `.uproject` file's path in the machine. */
  path: string;
  /** The project's name. */
  name: string;
  /** The engine version it was saved with (`EngineAssociation`), or empty for none named. */
  engine_association: string;
  /** Its version against the engine's: the same, older, newer, a source build's, or not named. */
  version: (typeof UNREAL_VERSIONS)[number];
  /** How the engine opens it, in a sentence. */
  opens: string;
  /** Its C++ modules; none for a project of Blueprints only. */
  cpp_modules: string[];
  /** The plugins it switches on. */
  plugins: string[];
  /** The ones of them that may not come along: binaries only in the repository, or from the marketplace and not in it. */
  plugins_to_check: string[];
  /** Whether its repository keeps files in Git LFS, the machine's word for that, or `null` when unknown. */
  lfs: boolean | string | null;
  /** Its size on disk, or `null` when unknown. */
  size_bytes: number | null;
}

/** Where a clone an engine makes as it starts is: still running, finished, or failed. */
const CLONE_STATES = ['cloning', 'done', 'failed'] as const;

/**
 * The clone of the project's repository a running Unreal engine made as it started, as its machine
 * reports it.
 */
export interface EngineClone {
  /** Whether it is still running, finished, or failed. */
  state: (typeof CLONE_STATES)[number];
  /** The folder it clones into, in the machine: the project's folder and the repository's name. */
  path: string;
  /** The machine's word on it: how far it has come, or why it failed. */
  detail: string;
}

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
  /**
   * The pictures a running engine streams, its desktop among them, absent for an engine that
   * streams its desktop alone and in the event log, which never carries links.
   */
  streams?: EngineStream[];
  /**
   * The clone of the project's repository a running Unreal engine made as it started, absent where
   * it made none or its machine does not say, and in the event log.
   */
  clone?: EngineClone;
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
  /** What a turn of the account's may spend and take; absent from a control plane without such limits. */
  limits?: Limits;
  /** The name the person gave themselves, empty where they gave none; absent from a control plane without names. */
  name?: string | null;
  /**
   * Every setting of the catalog with the value that applies, the person's own or its default;
   * absent from a control plane without settings.
   */
  settings?: Record<string, SettingValue>;
}

/** What a setting of the catalog holds: on or off for a toggle, one of its options' values for a choice. */
export type SettingValue = boolean | string;

/** The limits a turn has, by what reaching one is called: its spend on the model, and its steps. */
const TURN_LIMITS = ['budget', 'steps'] as const;

/** One limit of a turn. */
export type TurnLimit = (typeof TURN_LIMITS)[number];

/** The two limits of a turn, as numbers. */
export interface TurnLimits {
  /** What one turn may spend on the model, in US dollars. */
  turn_budget_usd: number;
  /** How many steps one turn may take. */
  turn_limit: number;
}

/**
 * What a turn of the person's may spend on the model and how many steps it may take: the numbers
 * that apply, what the person set themselves, the deployment's defaults, and its ceilings.
 */
export interface Limits extends TurnLimits {
  /** What the person set themselves; `null` for a limit left on the deployment's default. */
  own: { [Limit in keyof TurnLimits]: number | null };
  /** The deployment's defaults, which apply where the person set nothing. */
  default: TurnLimits;
  /** The deployment's ceilings, which no account sets a limit above. */
  max: TurnLimits;
}

/** The limits to change; one left out stays as it is, and `null` puts one back on the default. */
export type LimitChanges = { [Limit in keyof TurnLimits]?: number | null };

/**
 * What of the account to change. Anything left out stays as it is; a change refused in any part
 * changes nothing.
 */
export interface AccountChanges extends LimitChanges {
  /** The person's name, at most eighty characters; `null` clears it. */
  name?: string | null;
  /** The catalog's settings to change, by id; `null` puts one back on its default. */
  settings?: Record<string, SettingValue | null>;
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
  /** Whether GitHub can be connected: a GitHub App is configured. */
  github: boolean | null;
  /** Whether Epic can be connected: the OAuth App that pulls the person's own Unreal Editor is configured. */
  epic: boolean | null;
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
  /**
   * The kind of work within the discipline, such as `Film & TV`, or the empty string for a project
   * that has not been given one yet: one that opened on the card that asks.
   */
  format: string;
  /** Whether it is pinned to the top of the sidebar. */
  pinned: boolean;
  /** When it was created, as an ISO 8601 timestamp. */
  created_at: string;
  /** When anything of it last changed, as an ISO 8601 timestamp. */
  updated_at: string;
  /** The GitHub repository it is linked to, as `owner/name`, or `null`. */
  github_repo: string | null;
  /**
   * The branch of it an Unreal engine clones, or `null` (or absent, from an older control plane)
   * for the repository's default branch.
   */
  github_branch?: string | null;
  /** The library's sections, in the order they are shown; the project's own, never a fixed list. */
  library_sections: string[];
  /** The agent's plan. */
  plan: PlanItem[];
  /**
   * What the person no longer wants to be asked about, by tool name: `always` for a tool the agent
   * may run in this project without an approval. Absent from a control plane that asks for none.
   */
  permissions?: Record<string, string>;
}

/** The answer kept for a tool the person always allows. */
export const ALWAYS = 'always';

/** What a project is created with. */
export interface NewProject {
  /** Its name; the control plane names a project made without one. */
  name?: string;
  /** The catalog discipline. */
  discipline: string;
  /**
   * The kind of work within the discipline. Left out, in a discipline that asks its kind, the
   * project opens on the card that asks.
   */
  format?: string;
  /** The repository it starts linked to, as `owner/name`: a project imported from GitHub. */
  github_repo?: string;
}

/** The fields of a project that can be changed; each is left as it is when absent. */
export interface ProjectChanges {
  /** A new name. */
  name?: string;
  /** Pins or unpins it. */
  pinned?: boolean;
  /** The library's sections, in their new order. */
  library_sections?: string[];
  /** Every tool the person always allows; one left out is asked about again. */
  permissions?: Record<string, typeof ALWAYS>;
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

/**
 * The address that hands a media file to the person as a file to keep.
 *
 * A link's own `download` attribute saves only a file of the page's origin, which a signed
 * address is not. The storage that signs the address serves the file as an attachment where the
 * address carries `download`, under the name given there or under the file's own. An address
 * that is not a full one (a file the page itself serves or holds) is returned as it is, and the
 * link's attribute does the rest.
 *
 * @param media The file.
 * @returns Its address, asking to be saved under `media.name` where it has one.
 */
export function downloadAddress(media: Media): string {
  if (!/^https?:\/\//i.test(media.url)) {
    return media.url;
  }
  return `${media.url}${media.url.includes('?') ? '&' : '?'}download=${encodeURIComponent(media.name ?? '')}`;
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
  /** The subagent it belongs to, absent for an event of the agent itself. */
  agent_id?: string;
}

/** What an interactive card was locked in with: the card, and its state as the person left it. */
export interface UiLock {
  /** The card's identifier, as its `ui` event names it. */
  ui_id: string;
  /** The card's state, as JSON; its shape is the card's own. */
  value: unknown;
}

/** A message the person sent. */
export interface UserMessageData {
  /** The message. */
  text: string;
  /** The interactive card it locks in, for a message sent by a card's lock-in button. */
  ui?: UiLock;
}

/** A piece of the agent's reply or of its reasoning, in order. */
export interface TextData {
  /** The text, in a small subset of Markdown. */
  text: string;
  /**
   * The block of the answer this is. A later event of the same kind with the same block replaces
   * this one, which is how a block appears while it is written.
   */
  block?: string;
  /** Whether the block is still being written. */
  partial?: boolean;
}

/** The agent started calling a tool. */
export interface ToolStartData {
  /** The call's identifier, which the call's end names too. */
  call_id: string;
  /** The tool's name. */
  tool: string;
  /** What the call does, in words for the person. */
  title: string;
  /**
   * What the tool looks like while it runs, one of the catalog's `activities`; absent from a
   * control plane that does not say.
   */
  activity?: string;
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
  /**
   * The answer the agent would give, one of `options`; absent from a log written before the
   * agent recommended.
   */
  recommended?: string;
}

/** The agent's plan changed. */
export interface PlanData {
  /** The whole plan, as it now stands. */
  items: PlanItem[];
}

/** The library changed: an asset was added or changed, or the agent set its sections. */
export type LibraryData =
  | {
      /** The asset, as it now stands. */
      asset: Asset;
    }
  | {
      /** The library's sections, in the order they are shown. */
      sections: string[];
    };

/** An engine of the project was started or changed state. */
export interface EngineData {
  /** The engine, as it now stands. */
  engine: Session;
}

/** The agent put an engine, in one of its pictures, on the person's screen. */
export interface ScreenData {
  /** The engine. */
  engine_id: string;
  /** The picture's name, such as `Desktop` or `Unreal`. */
  stream: string;
}

/** What a change of a version's edit may be: the lanes of its timeline, and a cut, which removes time. */
export const EDIT_KINDS = ['text', 'captions', 'graphics', 'video', 'voice', 'music', 'sfx', 'cut'] as const;

/** One kind of change. */
export type EditKind = (typeof EDIT_KINDS)[number];

/** What a change is where it is not an edit of what was there. */
const EDIT_TYPES = ['added', 'retimed'] as const;

/** One change a version of a video made, as the tool that keeps the versions recorded it. */
export interface EditChange {
  /** What changed, in the person's words. */
  text: string;
  /** What kind of thing it is; left out for a change that has none. */
  kind?: EditKind;
  /** Where it starts in the version's own video, in seconds; left out, with `to`, for a change to the whole video. */
  from?: number;
  /** Where it ends, in seconds. */
  to?: number;
  /** How much time a cut removed, in seconds. */
  removed?: number;
  /** The file that makes it, from the project's folder. */
  src?: string;
  /** Whether it was added or moved in time, where it is neither left out. */
  type?: (typeof EDIT_TYPES)[number];
}

/**
 * The edit a version of a video is, read from the project's history when the agent showed the
 * version (`moody/control/edits.py`): what the page draws as the version's tracks.
 */
export interface VersionEdit {
  /** What the version is, in a line. */
  message: string;
  /** What the person asked for since the version before, word for word. */
  prompts: string[];
  /** What changed, in the order recorded. */
  changes: EditChange[];
  /** When it was saved, as an ISO 8601 time. */
  saved_at?: string;
  /**
   * Its sound as bars: the loudest moment of each of as many equal stretches of the file, from 0,
   * silence, to 100, full scale. Left out for a file with no sound.
   */
  sound?: number[];
}

/** One file of a preview: a {@link Media} with what is known of its length and its size on screen. */
export interface PreviewItem extends Media {
  /** Its file name in the project's folder. */
  name: string;
  /** How long it plays, in seconds, for sound and video. */
  seconds?: number;
  /** Its width in pixels, for a picture or a video. */
  width?: number;
  /** Its height in pixels, for a picture or a video. */
  height?: number;
  /** The edit it is the render of, for the file of a version whose history holds one. */
  edit?: VersionEdit;
}

/** The agent showed work in progress: files an engine wrote, or its screen. */
export interface PreviewData {
  /** The engine the files came from. */
  engine_id: string;
  /** What the preview shows, in the agent's words. */
  caption: string;
  /** The files, in the order to show them; one whose file is gone is left out. */
  items: PreviewItem[];
  /** Whether two items are a before and after pair, the one before first. */
  compare: boolean;
  /**
   * A short label, such as "Rough cut" or "v3", for a preview that shows a version of the piece
   * itself rather than a step on the way to it.
   */
  version?: string;
}

/** Something went wrong in the turn. */
export interface ErrorData {
  /** What went wrong, for the person. */
  message: string;
  /** The limit of the person's the turn stopped at, for a turn that stopped at one. */
  limit?: TurnLimit;
}

/** Where a subagent stands; `completed`, `failed`, and `stopped` are final. */
const AGENT_STATES = ['working', 'completed', 'failed', 'stopped'] as const;

/** One state of a subagent. */
export type AgentState = (typeof AGENT_STATES)[number];

/**
 * A subagent's card. Every event carries the whole card, and the latest one for an `agent_id` is
 * its state.
 */
export interface AgentData {
  /** The subagent's identifier, which its own events carry as their `agent_id`. */
  agent_id: string;
  /** What the subagents one step started together share: they are shown as one block. */
  group: string;
  /** The definition it runs, such as `research`. */
  name: string;
  /** What the page calls it, such as "Research agent". */
  title: string;
  /** The job it was handed, in a line. */
  task: string;
  /** Where it stands. */
  state: AgentState;
  /** What it is doing, one of the catalog's `activities`. */
  activity: string;
  /** What it is doing now, in a line. */
  detail: string;
  /** How long it has worked, in seconds, where the control plane says. */
  seconds?: number;
  /** The tokens it has used, where the control plane says. */
  tokens?: number;
}

/** The agent waits for the person before a tool that costs or changes something. */
export interface ApprovalData {
  /** The approval's identifier, which the answer and its result name. */
  approval_id: string;
  /** The tool that waits. */
  tool: string;
  /** What it would do, in words for the person. */
  title: string;
  /** What that costs or changes, in a sentence or two. */
  detail: string;
}

/** What a person answers an approval with: this once, for good in this project, or not now. */
const APPROVAL_DECISIONS = ['once', 'always', 'deny'] as const;

/** One answer to an approval. */
export type ApprovalDecision = (typeof APPROVAL_DECISIONS)[number];

/** How an approval ended: with one of the person's answers, or unanswered when its turn did. */
const APPROVAL_OUTCOMES = [...APPROVAL_DECISIONS, 'expired'] as const;

/** One way an approval ended. */
export type ApprovalOutcome = (typeof APPROVAL_OUTCOMES)[number];

/** An approval ended. */
export interface ApprovalResultData {
  /** The approval. */
  approval_id: string;
  /** How it ended. */
  decision: ApprovalOutcome;
}

/** How an interactive card is built: from the page's own components, or as a document of its own. */
const UI_KINDS = ['components', 'html'] as const;

/** A file an interactive card shows. */
export interface UiMedia {
  /** The name the card's content refers to it by. */
  name: string;
  /** What it is: a {@link MediaKind}, or a kind only cards show, such as `model` for a 3D model. */
  kind: string;
  /** Its address, signed for the reading of the log that returned it. */
  url: string;
}

/**
 * An interactive card the agent put in the conversation, such as a slider over a picture or a
 * form, which the person locks in to send its state back as their next message.
 */
export interface UiData {
  /** The card's identifier, which the message that locks it in names. */
  ui_id: string;
  /** What the card is, as its heading. */
  title: string;
  /** How it is built. */
  kind: (typeof UI_KINDS)[number];
  /** A tree of the components `moody/ui.json` defines, for a card of kind `components`. */
  spec?: unknown;
  /** A document the page runs in a sandboxed frame, for a card of kind `html`. */
  html?: string;
  /** The height it asks for, in CSS pixels. */
  height?: number;
  /** The lock-in button's label, or `null` for a card with nothing to send back. */
  submit: string | null;
  /** Whether choosing locks the card, with no button: a card whose one input is a single choice. */
  instant?: boolean;
  /**
   * What of the project the card's answer sets: `format`, on the card that asks a new project's
   * kind, whose locking message gives the project its format before the turn begins.
   */
  sets?: string;
  /** Whether the agent's turn ended to wait for the card. */
  waits: boolean;
  /** The files the card shows, each signed for the reading of the log that returned it. */
  media: UiMedia[];
}

/** What a turn cost, written once as it ends. */
export interface UsageData {
  /** The tokens the model read. */
  input_tokens: number;
  /** The tokens the model wrote. */
  output_tokens: number;
  /** What the model's work cost, in US dollars. */
  cost_usd: number;
  /** How long the turn took, in seconds. */
  seconds: number;
  /** How many subagents it ran. */
  agents: number;
}

/** An event of a project's log, one of the kinds `moody/STUDIO.md` names. */
export type StudioEvent = EventEnvelope &
  (
    | { kind: 'user_message'; data: UserMessageData }
    | { kind: 'text'; data: TextData }
    | { kind: 'thinking'; data: TextData }
    | { kind: 'agent'; data: AgentData }
    | { kind: 'approval'; data: ApprovalData }
    | { kind: 'approval_result'; data: ApprovalResultData }
    | { kind: 'ui'; data: UiData }
    | { kind: 'usage'; data: UsageData }
    | { kind: 'tool_start'; data: ToolStartData }
    | { kind: 'tool_end'; data: ToolEndData }
    | { kind: 'ask'; data: AskData }
    | { kind: 'plan'; data: PlanData }
    | { kind: 'library'; data: LibraryData }
    | { kind: 'engine'; data: EngineData }
    | { kind: 'screen'; data: ScreenData }
    | { kind: 'preview'; data: PreviewData }
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

/** The person's GitHub connection, through the control plane's GitHub App. */
export interface GitHubStatus {
  /** Whether the control plane has a GitHub App to connect with. */
  configured: boolean;
  /** Whether the person has connected their account. */
  connected: boolean;
  /** Their GitHub login, once connected. */
  login: string | null;
  /** Their GitHub avatar, once connected. */
  avatar_url: string | null;
}

/**
 * The person's Epic connection: the GitHub account their Epic account is linked to, connected
 * through an OAuth App that only reads packages, which their own copy of the Unreal Editor is
 * pulled with.
 */
export interface EpicStatus {
  /** Whether the control plane has that OAuth App to connect with. */
  configured: boolean;
  /** Whether the person has connected it. */
  connected: boolean;
  /** The GitHub login connected for it, once connected. */
  login: string | null;
  /**
   * Whether Epic's registry lets that account pull the editor: linked, not linked, or `null` while
   * unknown (not connected, a token GitHub no longer takes, or the registry not answering).
   */
  linked: boolean | null;
  /** Why the link is unknown, where it is unknown though connected. */
  detail: string | null;
}

/** A repository the person can link a project to: one of the GitHub App's installations they reach. */
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

/**
 * How a project is linked to a repository: its `owner/name`, and the branch an Unreal engine clones
 * where not its default. The GitHub App makes no repositories: a new one is made on GitHub.
 */
export interface RepoLink {
  /** The repository, as `owner/name`. */
  repo: string;
  /** The branch an Unreal engine clones, where not the default. */
  branch?: string;
}

/** What a connector is for. */
const CONNECTOR_KINDS = ['generation', 'repository', 'search', 'license', 'mcp'] as const;

/** One kind of connector. */
export type ConnectorKind = (typeof CONNECTOR_KINDS)[number];

/** Whether the agent can use a connector: it can, it could once the person connects it, or it is off here. */
const CONNECTOR_STATES = ['connected', 'available', 'off'] as const;

/** One state of a connector. */
export type ConnectorState = (typeof CONNECTOR_STATES)[number];

/** A service the project's agent can use, or could once the person connects it. */
export interface Connector {
  /** The connector's identifier. */
  id: string;
  /** Its name, such as "fal". */
  name: string;
  /** What it is for. */
  kind: ConnectorKind;
  /** Whether the agent can use it. */
  state: ConnectorState;
  /** What it gives the agent, or what connecting it takes, in a line. */
  detail: string;
}

/** A subagent this project's agent can hand work to. */
export interface AgentInfo {
  /** Its identifier, which an `agent` event's `name` carries. */
  name: string;
  /** What the page calls it, such as "Research agent". */
  title: string;
  /** When the agent hands work to it. */
  description: string;
}

/** A skill this project's agent reads when the work calls for it. */
export interface SkillInfo {
  /** Its name. */
  name: string;
  /** What it teaches, in a sentence or two. */
  description: string;
}

/** What a project's agent works with, beside its engines and its repository. */
export interface Environment {
  /** The services it can use, or could. */
  connectors: Connector[];
  /** The subagents it can hand work to. */
  agents: AgentInfo[];
  /** The skills it reads. */
  skills: SkillInfo[];
}

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
  /**
   * Changes the person's name, the limits of their turns, and their settings, and returns the
   * account; rejects with status 400 for a limit that is not positive or is over the deployment's
   * ceiling, and for a setting or a value the catalog does not offer.
   */
  updateMe(changes: AccountChanges): Promise<Me>;
  /** Mints a fresh link that opens a running session's desktop, or the picture `stream` names. */
  sessionLink(id: string, stream?: string): Promise<string>;
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
  /** Lists the Unreal projects in a running Unreal engine's workspace. */
  unrealProjects(projectId: string, engineId: string): Promise<UnrealProject[]>;
  /** Reads a project's events after a cursor, and whether a turn is running. */
  listEvents(projectId: string, after: number): Promise<EventPage>;
  /**
   * Sends the person's message, which starts a turn; refused with 409 while one runs. With `ui`,
   * the message locks in an interactive card with its state.
   */
  sendMessage(projectId: string, text: string, ui?: UiLock): Promise<TurnId>;
  /** Stops the running turn. */
  stopTurn(projectId: string): Promise<void>;
  /**
   * Answers an approval the running turn waits on.
   *
   * @returns Whether the answer was recorded; `false` for an approval that had already ended.
   */
  approve(projectId: string, approvalId: string, decision: ApprovalDecision): Promise<boolean>;
  /** Reads what a project's agent works with: its connectors, subagents, and skills. */
  environment(projectId: string): Promise<Environment>;
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
  /**
   * Returns the GitHub App's installation page, where the person installs it on an account or
   * organization, or asks its owners to, returning to `returnTo`.
   */
  installGitHub(returnTo: string): Promise<string>;
  /** Lists the repositories of the GitHub App's installations the person reaches. */
  githubRepos(): Promise<GitHubRepo[]>;
  /** Disconnects GitHub. */
  disconnectGitHub(): Promise<void>;
  /** Links a project to a repository. */
  linkRepo(projectId: string, link: RepoLink): Promise<Project>;
  /** Unlinks a project from its repository. */
  unlinkRepo(projectId: string): Promise<Project>;
  /** Reads the person's Epic connection, and whether Epic's registry lets it pull the editor. */
  epic(): Promise<EpicStatus>;
  /** Starts connecting Epic and returns GitHub's authorization page, which returns to `returnTo`. */
  connectEpic(returnTo: string): Promise<string>;
  /** Disconnects Epic. */
  disconnectEpic(): Promise<void>;
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

/** Checks a value into an {@link EngineStream}. */
const isEngineStream: Guard<EngineStream> = (value): value is EngineStream =>
  isRecord(value) && isString(value.name) && isWebUrl(value.url);

/** Checks a value into an {@link EngineClone}. */
const isEngineClone: Guard<EngineClone> = (value): value is EngineClone =>
  isRecord(value) && oneOf(CLONE_STATES)(value.state) && isString(value.path) && isString(value.detail);

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
  optional(isNullableString)(value.project_id) &&
  optional(arrayOf(isEngineStream))(value.streams) &&
  optional(isEngineClone)(value.clone);

/** Checks a value into an {@link UnrealProject}. */
const isUnrealProject: Guard<UnrealProject> = (value): value is UnrealProject =>
  isRecord(value) &&
  isString(value.path) &&
  isString(value.name) &&
  isString(value.engine_association) &&
  oneOf(UNREAL_VERSIONS)(value.version) &&
  isString(value.opens) &&
  isStrings(value.cpp_modules) &&
  isStrings(value.plugins) &&
  isStrings(value.plugins_to_check) &&
  (value.lfs === null || isBoolean(value.lfs) || isString(value.lfs)) &&
  isNullableNumber(value.size_bytes);

/** Checks a value into a {@link ScreenData}. */
const isScreen: Guard<ScreenData> = (value): value is ScreenData =>
  isRecord(value) && isString(value.engine_id) && isString(value.stream);

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
  /** Whether Epic can be connected. */
  epic?: boolean | null;
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
  optional(isNullableBoolean)(value.epic) &&
  optional(isNullableBoolean)(value.generation) &&
  optional(isNullableBoolean)(value.billing) &&
  optional(isStrings)(value.tiers);

/** Checks a value into a {@link TurnLimits}. */
const isTurnLimits: Guard<TurnLimits> = (value): value is TurnLimits =>
  isRecord(value) && isNumber(value.turn_budget_usd) && isNumber(value.turn_limit);

/** Checks a value into a {@link Limits}. */
const isLimits: Guard<Limits> = (value): value is Limits =>
  isRecord(value) &&
  isNumber(value.turn_budget_usd) &&
  isNumber(value.turn_limit) &&
  isRecord(value.own) &&
  isNullableNumber(value.own.turn_budget_usd) &&
  isNullableNumber(value.own.turn_limit) &&
  isTurnLimits(value.default) &&
  isTurnLimits(value.max);

/** Checks a value into the settings of an account, each a switch's state or a choice's value. */
const isSettingValues: Guard<Record<string, SettingValue>> = (value): value is Record<string, SettingValue> =>
  isRecord(value) && Object.values(value).every((held) => isBoolean(held) || isString(held));

/** Checks a value into a {@link Me}. */
const isMe: Guard<Me> = (value): value is Me =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.email) &&
  isNumber(value.credits) &&
  isNumber(value.max_sessions) &&
  optional(isLimits)(value.limits) &&
  optional(isNullableString)(value.name) &&
  optional(isSettingValues)(value.settings);

/** Checks a value into a {@link PlanItem}. */
const isPlanItem: Guard<PlanItem> = (value): value is PlanItem =>
  isRecord(value) && isString(value.id) && isString(value.title) && oneOf(PLAN_STATUSES)(value.status);

const isPlan = arrayOf(isPlanItem);

/** Checks a value into a project's kept answers: a word per tool name. */
const isAnswers: Guard<Record<string, string>> = (value): value is Record<string, string> =>
  isRecord(value) && Object.values(value).every(isString);

/** A project as it is sent, before a format that is absent or `null` is read as none. */
type ProjectReport = Omit<Project, 'format'> & { format?: string | null };

/**
 * Reads a project as it is sent.
 *
 * @param report The project as sent.
 * @returns The project, its format the empty string where it has none yet.
 */
function toProject(report: ProjectReport): Project {
  return { ...report, format: report.format ?? '' };
}

/** Checks a value into a {@link ProjectReport}. */
const isProjectReport: Guard<ProjectReport> = (value): value is ProjectReport =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.name) &&
  isString(value.discipline) &&
  optional(isNullableString)(value.format) &&
  isBoolean(value.pinned) &&
  isString(value.created_at) &&
  isString(value.updated_at) &&
  isNullableString(value.github_repo) &&
  optional(isNullableString)(value.github_branch) &&
  isStrings(value.library_sections) &&
  isPlan(value.plan) &&
  optional(isAnswers)(value.permissions);

/** Checks a value into a {@link Media}. */
const isMedia: Guard<Media> = (value): value is Media =>
  isRecord(value) && oneOf(MEDIA_KINDS)(value.kind) && isWebUrl(value.url) && optional(isString)(value.name);

const isMediaList = arrayOf(isMedia);

/** Checks a value into an {@link EditChange}. */
const isEditChange: Guard<EditChange> = (value): value is EditChange =>
  isRecord(value) &&
  isString(value.text) &&
  optional(oneOf(EDIT_KINDS))(value.kind) &&
  optional(isNumber)(value.from) &&
  optional(isNumber)(value.to) &&
  optional(isNumber)(value.removed) &&
  optional(isString)(value.src) &&
  optional(oneOf(EDIT_TYPES))(value.type);

/** Checks a value into a {@link VersionEdit}. */
const isVersionEdit: Guard<VersionEdit> = (value): value is VersionEdit =>
  isRecord(value) &&
  isString(value.message) &&
  isStrings(value.prompts) &&
  arrayOf(isEditChange)(value.changes) &&
  optional(isString)(value.saved_at) &&
  optional(arrayOf(isNumber))(value.sound);

/** Checks a value into a {@link PreviewItem}. */
const isPreviewItem: Guard<PreviewItem> = (value): value is PreviewItem =>
  isRecord(value) &&
  oneOf(MEDIA_KINDS)(value.kind) &&
  isWebUrl(value.url) &&
  isString(value.name) &&
  optional(isNumber)(value.seconds) &&
  optional(isNumber)(value.width) &&
  optional(isNumber)(value.height) &&
  optional(isVersionEdit)(value.edit);

/** Checks a value into a {@link PreviewData}. */
const isPreview: Guard<PreviewData> = (value): value is PreviewData =>
  isRecord(value) &&
  isString(value.engine_id) &&
  isString(value.caption) &&
  arrayOf(isPreviewItem)(value.items) &&
  isBoolean(value.compare) &&
  optional(isString)(value.version);

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
  optional(isString)(value.agent_id) &&
  isString(value.kind) &&
  isRecord(value.data);

/** Checks a value into a {@link UiLock}; its `value` is whatever the card kept, and is left unchecked. */
const isUiLock: Guard<UiLock> = (value): value is UiLock => isRecord(value) && isString(value.ui_id);

/** Checks a value into a {@link UserMessageData}. */
const isUserMessage: Guard<UserMessageData> = (value): value is UserMessageData =>
  isRecord(value) && isString(value.text) && optional(isUiLock)(value.ui);

/** Checks a value into the data of a piece of the agent's reply or reasoning. */
const isTextData: Guard<TextData> = (value): value is TextData =>
  isRecord(value) && isString(value.text) && optional(isString)(value.block) && optional(isBoolean)(value.partial);

/** Checks a value into a {@link ToolStartData}. */
const isToolStart: Guard<ToolStartData> = (value): value is ToolStartData =>
  isRecord(value) &&
  isString(value.call_id) &&
  isString(value.tool) &&
  isString(value.title) &&
  optional(isString)(value.activity);

/** Checks a value into an {@link AgentData}. */
const isAgent: Guard<AgentData> = (value): value is AgentData =>
  isRecord(value) &&
  isString(value.agent_id) &&
  isString(value.group) &&
  isString(value.name) &&
  isString(value.title) &&
  isString(value.task) &&
  oneOf(AGENT_STATES)(value.state) &&
  isString(value.activity) &&
  isString(value.detail) &&
  optional(isNumber)(value.seconds) &&
  optional(isNumber)(value.tokens);

/** Checks a value into an {@link ApprovalData}. */
const isApproval: Guard<ApprovalData> = (value): value is ApprovalData =>
  isRecord(value) &&
  isString(value.approval_id) &&
  isString(value.tool) &&
  isString(value.title) &&
  isString(value.detail);

/** Checks a value into an {@link ApprovalResultData}. */
const isApprovalResult: Guard<ApprovalResultData> = (value): value is ApprovalResultData =>
  isRecord(value) && isString(value.approval_id) && oneOf(APPROVAL_OUTCOMES)(value.decision);

/** Checks a value into a {@link UiMedia}. */
const isUiMedia: Guard<UiMedia> = (value): value is UiMedia =>
  isRecord(value) && isString(value.kind) && isWebUrl(value.url) && isString(value.name);

/**
 * Reads a card's file as ordinary media, where its kind is one the rest of the page shows.
 *
 * @param file The card's file.
 * @returns The file as media, or `null` for a kind only cards show, such as a 3D model.
 */
export function cardMedia(file: UiMedia): Media | null {
  return oneOf(MEDIA_KINDS)(file.kind) ? { kind: file.kind, url: file.url, name: file.name } : null;
}

/** Checks a value into a {@link UiData}; its `spec` is left for the card to check. */
const isUi: Guard<UiData> = (value): value is UiData =>
  isRecord(value) &&
  isString(value.ui_id) &&
  isString(value.title) &&
  oneOf(UI_KINDS)(value.kind) &&
  optional(isString)(value.html) &&
  optional(isNumber)(value.height) &&
  isNullableString(value.submit) &&
  optional(isBoolean)(value.instant) &&
  optional(isString)(value.sets) &&
  isBoolean(value.waits) &&
  arrayOf(isUiMedia)(value.media);

/** Checks a value into a {@link UsageData}. */
const isUsage: Guard<UsageData> = (value): value is UsageData =>
  isRecord(value) &&
  isNumber(value.input_tokens) &&
  isNumber(value.output_tokens) &&
  isNumber(value.cost_usd) &&
  isNumber(value.seconds) &&
  isNumber(value.agents);

/** Checks a value into a {@link ToolEndData}. */
const isToolEnd: Guard<ToolEndData> = (value): value is ToolEndData =>
  isRecord(value) &&
  isString(value.call_id) &&
  isBoolean(value.ok) &&
  isNullableString(value.summary) &&
  optional(isMediaList)(value.media);

/** Checks a value into an {@link AskData}. */
const isAsk: Guard<AskData> = (value): value is AskData =>
  isRecord(value) && isString(value.question) && isStrings(value.options) && optional(isString)(value.recommended);

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
  const { data } = value;
  // A subagent is named on the event or in its data; an `agent` event's own data names its card.
  const agentId = value.agent_id ?? (value.kind !== 'agent' && isString(data.agent_id) ? data.agent_id : undefined);
  const envelope: EventEnvelope = {
    id: value.id,
    turn_id: value.turn_id,
    created_at: value.created_at,
    ...(agentId === undefined ? {} : { agent_id: agentId }),
  };
  switch (value.kind) {
    case 'user_message':
      return isUserMessage(data) ? { ...envelope, kind: 'user_message', data } : null;
    case 'text':
      return isTextData(data) ? { ...envelope, kind: 'text', data } : null;
    case 'thinking':
      return isTextData(data) ? { ...envelope, kind: 'thinking', data } : null;
    case 'agent':
      return isAgent(data) ? { ...envelope, kind: 'agent', data } : null;
    case 'approval':
      return isApproval(data) ? { ...envelope, kind: 'approval', data } : null;
    case 'approval_result':
      return isApprovalResult(data) ? { ...envelope, kind: 'approval_result', data } : null;
    case 'ui':
      return isUi(data) ? { ...envelope, kind: 'ui', data } : null;
    case 'usage':
      return isUsage(data) ? { ...envelope, kind: 'usage', data } : null;
    case 'tool_start':
      return isToolStart(data) ? { ...envelope, kind: 'tool_start', data } : null;
    case 'tool_end':
      return isToolEnd(data) ? { ...envelope, kind: 'tool_end', data } : null;
    case 'ask':
      return isAsk(data) ? { ...envelope, kind: 'ask', data } : null;
    case 'plan':
      return isPlan(data.items) ? { ...envelope, kind: 'plan', data: { items: data.items } } : null;
    case 'library':
      if (isAsset(data.asset)) {
        return { ...envelope, kind: 'library', data: { asset: data.asset } };
      }
      return isStrings(data.sections) ? { ...envelope, kind: 'library', data: { sections: data.sections } } : null;
    case 'engine':
      return isSession(data.engine) ? { ...envelope, kind: 'engine', data: { engine: data.engine } } : null;
    case 'screen':
      return isScreen(data) ? { ...envelope, kind: 'screen', data } : null;
    case 'preview':
      return isPreview(data) ? { ...envelope, kind: 'preview', data } : null;
    case 'turn_end':
      return { ...envelope, kind: 'turn_end', data };
    case 'error':
      if (!isString(data.message)) {
        return null;
      }
      // A limit this page does not know still reads as the error it is.
      return {
        ...envelope,
        kind: 'error',
        data: { message: data.message, ...(oneOf(TURN_LIMITS)(data.limit) ? { limit: data.limit } : {}) },
      };
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
  /** Whether a GitHub App is configured. */
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

/** The Epic status as it is sent, before an absent login or detail is read as `null`. */
interface EpicReport {
  /** Whether the Epic OAuth App is configured. */
  configured: boolean;
  /** Whether the person has connected. */
  connected: boolean;
  /** The GitHub login connected for Epic. */
  login?: string | null;
  /** Whether Epic's registry lets it pull the editor. */
  linked: boolean | null;
  /** Why that is unknown. */
  detail?: string | null;
}

/** Checks a value into an {@link EpicReport}. */
const isEpicReport: Guard<EpicReport> = (value): value is EpicReport =>
  isRecord(value) &&
  isBoolean(value.configured) &&
  isBoolean(value.connected) &&
  optional(isNullableString)(value.login) &&
  isNullableBoolean(value.linked) &&
  optional(isNullableString)(value.detail);

/** Checks a value into a {@link GitHubRepo}. */
const isGitHubRepo: Guard<GitHubRepo> = (value): value is GitHubRepo =>
  isRecord(value) &&
  isString(value.full_name) &&
  isBoolean(value.private) &&
  isWebUrl(value.html_url) &&
  isString(value.updated_at);

/** Checks a value into a {@link Connector}. */
const isConnector: Guard<Connector> = (value): value is Connector =>
  isRecord(value) &&
  isString(value.id) &&
  isString(value.name) &&
  oneOf(CONNECTOR_KINDS)(value.kind) &&
  oneOf(CONNECTOR_STATES)(value.state) &&
  isString(value.detail);

/** Checks a value into an {@link AgentInfo}. */
const isAgentInfo: Guard<AgentInfo> = (value): value is AgentInfo =>
  isRecord(value) && isString(value.name) && isString(value.title) && isString(value.description);

/** Checks a value into a {@link SkillInfo}. */
const isSkillInfo: Guard<SkillInfo> = (value): value is SkillInfo =>
  isRecord(value) && isString(value.name) && isString(value.description);

/**
 * Reads a project's environment.
 *
 * A connector of a kind or a state this page does not know is left out, as an event of an unknown
 * kind is, so a newer control plane adds one without emptying the panel of an older page.
 *
 * @param body The response body.
 * @returns The environment.
 * @throws ApiError With status 502 when the body is not an environment.
 */
function parseEnvironment(body: unknown): Environment {
  if (!isRecord(body) || !Array.isArray(body.connectors)) {
    throw new ApiError(502, 'The control plane sent a response this page does not understand.');
  }
  return {
    connectors: body.connectors.filter(isConnector),
    agents: field(body, 'agents', arrayOf(isAgentInfo)),
    skills: field(body, 'skills', arrayOf(isSkillInfo)),
  };
}

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
        epic: report.epic ?? null,
        generation: report.generation ?? null,
        billing: report.billing ?? null,
        tiers: report.tiers ?? null,
      };
    },
    me: async () => expect(await request('GET', '/v1/me'), isMe),
    updateMe: async (changes) => expect(await request('PATCH', '/v1/me', changes), isMe),
    sessionLink: async (id, stream) =>
      field(
        await request(
          'POST',
          `/v1/sessions/${encodeURIComponent(id)}/link`,
          stream === undefined ? undefined : { stream },
        ),
        'url',
        isWebUrl,
      ),
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
    listProjects: async () =>
      field(await request('GET', '/v1/projects'), 'projects', arrayOf(isProjectReport)).map(toProject),
    createProject: async (project) =>
      toProject(field(await request('POST', '/v1/projects', project), 'project', isProjectReport)),
    getProject: async (id) => toProject(field(await request('GET', projectPath(id)), 'project', isProjectReport)),
    updateProject: async (id, changes) =>
      toProject(field(await request('PATCH', projectPath(id), changes), 'project', isProjectReport)),
    deleteProject: async (id) => {
      await request('DELETE', projectPath(id));
    },
    listEngines: async (projectId) =>
      field(await request('GET', projectPath(projectId, '/engines')), 'engines', arrayOf(isSession)),
    startEngine: async (projectId, launch) =>
      field(await request('POST', projectPath(projectId, '/engines'), launch), 'engine', isSession),
    unrealProjects: async (projectId, engineId) =>
      field(
        await request('GET', projectPath(projectId, `/engines/${encodeURIComponent(engineId)}/unreal-projects`)),
        'projects',
        arrayOf(isUnrealProject),
      ),
    listEvents: async (projectId, after) =>
      parseEventPage(await request('GET', projectPath(projectId, `/events?after=${after}`))),
    sendMessage: async (projectId, text, ui) =>
      field(
        await request('POST', projectPath(projectId, '/messages'), ui === undefined ? { text } : { text, ui }),
        'turn_id',
        isTurnId,
      ),
    stopTurn: async (projectId) => {
      await request('POST', projectPath(projectId, '/stop'));
    },
    approve: async (projectId, approvalId, decision) =>
      field(
        await request('POST', projectPath(projectId, `/approvals/${encodeURIComponent(approvalId)}`), { decision }),
        'recorded',
        isBoolean,
      ),
    environment: async (projectId) => parseEnvironment(await request('GET', projectPath(projectId, '/environment'))),
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
    installGitHub: async (returnTo) =>
      field(await request('POST', '/v1/github/install', { return_to: returnTo }), 'url', isWebUrl),
    githubRepos: async () => field(await request('GET', '/v1/github/repos'), 'repos', arrayOf(isGitHubRepo)),
    disconnectGitHub: async () => {
      await request('DELETE', '/v1/github');
    },
    linkRepo: async (projectId, link) =>
      toProject(field(await request('POST', projectPath(projectId, '/github'), link), 'project', isProjectReport)),
    unlinkRepo: async (projectId) =>
      toProject(field(await request('DELETE', projectPath(projectId, '/github')), 'project', isProjectReport)),
    epic: async () => {
      const report = expect(await request('GET', '/v1/epic'), isEpicReport);
      return {
        configured: report.configured,
        connected: report.connected,
        login: report.login ?? null,
        linked: report.linked,
        detail: report.detail ?? null,
      };
    },
    connectEpic: async (returnTo) =>
      field(await request('POST', '/v1/epic/connect', { return_to: returnTo }), 'url', isWebUrl),
    disconnectEpic: async () => {
      await request('DELETE', '/v1/epic');
    },
  };
}
