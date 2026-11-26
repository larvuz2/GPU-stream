# Moody Studio: the plan

Moody becomes a project-based creative studio: a person describes what they want
to make, and an agent builds it with them, step by step, by opening creative
engines on cloud GPUs (FilmCraft, Blender, PhotoCraft, Nuke, and later Unreal
Engine), moving files between them, and asking the person at every decision that
is theirs. This file is the plan and the contract the pieces are built against;
the code that implements each part documents its mechanism.

## What a person sees

The app is three panes, the layout of a coding agent's workspace:

| Pane | Holds |
| --- | --- |
| Left sidebar | New project, **Create** (the short list of things to start, which is `catalog.json`'s `shortcuts`: each starts a project of a discipline, with a format where it means one, and one that is not available yet shows what is coming instead), **Pinned** and **Recent** projects with search opened from the Recent row, the account (**Settings**, the balance, sign out; Settings is a dialog of tabs: Profile, Billing, Agent, Video editing, Connections, API keys) |
| Center | The project's conversation with the agent: messages, tool activity, the agent's questions as choices, generated images and videos inline, the composer |
| Right pane | Modular panels the project shows as it needs them, each folded and unfolded by a quiet arrow: **Screen** (the live stream of an engine), **Latest** (the newest version of the piece, to play, to open full screen, and to download, with the versions before it), **Environment** (the engines running, start and stop, **Connect GitHub**, and, for Unreal Engine, **Connect Epic**), **Plan** (the agent's tasks and their state), **Library** (the project's characters, environments, props, products, or whatever sections the project has) |

Clicking the screen rearranges the panes: the stream becomes the largest area,
above the conversation, which stays visible below it. The library's sections are
the project's own, never a fixed list: a film has characters, environments, and
props; a commercial has products and shots; the agent adds sections as the work
needs them.

A new project starts from one of twelve disciplines (`catalog.json`,
`disciplines`), the first being **Media**, which is video of every kind: film
and television, social media, vertical shows, commercials, music videos, and
education. A video opens on the card that asks which kind it is, and the agent
opens the conversation as that kind does: for a film, a script to bring or one
to write together ("Contract: starting a project by its kind").

## The film workflow (the first one built)

1. **Script.** The person brings one or the agent writes it with them.
2. **Bible.** Characters, environments, and props become library entries, each
   with a tag (`@mara`), a description, and reference images the agent
   generates and the person approves.
3. **Shots.** A shot list; each shot's video is generated from the library's
   reference images with a reference-to-video model (Seedance on fal), the tags
   naming which reference is which in the prompt.
4. **Edit.** The agent opens FilmCraft, imports the shots, and cuts, colors,
   mixes, titles, and exports with the person, through FilmCraft's command
   channel (650+ engine commands, the same the UI runs).
5. **Spin-offs.** A poster opens a PhotoCraft engine on the same project files;
   blocking a scene opens Blender. Engines of one project share its folder.

The agent's craft knowledge is in skills. `moody/skills/video` is how a video
starts by its kind: the card each kind opens with, what the agent has to learn
before it makes anything, and the workflow each kind starts from, the one above
for a story and footage edited by code for social and educational video.
`moody/skills/movie` is the production
before the edit: the opening questions (the story, the main characters, the art
style), the library, prompting with references, animation tests, and the shots,
all of it generated with no engine running. `moody/skills/filmcraft` is the
edit, mapped to FilmCraft's commands, and the point at which the first engine
starts. How a production runs across engines and subagents is a skill of its
own, offered to every project (`moody/skills/studio`), as is how to answer with
an interactive card (`moody/skills/cards`). `moody/skills/README.md` is the
guide to writing another, and `moody/agents/README.md` to writing a subagent.

## Engines

An engine is a catalog app (`catalog.json`, `apps`) running as a Selkies
session on a Modal Sandbox (`addons/modal`). Status: `available` (anyone),
`team` (only the team's accounts, for software whose license is the user's own,
such as Nuke), `byol` (anyone, with the part of it on the user's own license
coming once they have linked that license, which the app's `license` names with
the steps that link it: Unreal Engine's editor on the user's Epic account,
`UNREAL.md`), `next` (being built), `soon`.

- **FilmCraft** is built from the release the fork tracks
  (`github.com/larvuz2/filmcraft`, a fork of `storytold/filmcraft`), pinned by
  version and checksum in `addons/modal/sandbox.py`; updating is a version bump
  after the fork syncs with upstream. The agent drives it through its control
  channel from the control plane (`filmcraft_call` in `addons/modal/sandbox.py`).
- **PhotoCraft** is installed the same way from `storytold/photocraft`'s release
  and driven the same way (`photocraft_call`). It keeps a project's open work
  in the project folder, saved and unsaved, so an engine started later opens
  on it; its skill is `moody/skills/photocraft`.
- **Nuke** runs from the image `selkies-modal` builds from a workspace's own
  install (`nuke_image`). Foundry licenses Nuke per person: a user signs in with
  their own Foundry account in the session, and serving the team's install to
  people outside the team needs Foundry's agreement, so the app is `team`.
  Machines scale per demand up to `MOODY_CAPACITY`, and Nuke additionally to
  the seats its license has (`MOODY_NUKE_SEATS`, two for the trial).
- **Agents spawn engines.** Every engine of a project mounts the user's
  directory of the workspace Volume and opens in the project's folder
  (`projects/<project id>`), so a FilmCraft edit and a PhotoCraft poster read and
  write the same files.
- **One tool drives every engine.** An app's command channel is the launcher
  function named after it, `<app id>_call(sandbox, method, params=None,
  timeout=60) -> dict` in `addons/modal/sandbox.py` (`filmcraft_call`,
  `soundcraft_call`, `cadcraft_call`), which the control plane finds by that
  name. The agent's `engine_call(engine_id, method, params)` reaches whichever
  app the engine runs, so an app gains a channel with no change to the control
  plane, and an engine without one answers that it has none and is driven
  through `engine_exec` and its screen. `filmcraft(engine_id, method, params)`
  is the same call for a FilmCraft engine.
- **Work moves between engines as files.** `engine_files(engine_id, path?)`
  lists the project's folder as one engine's machine sees it (each entry's
  name, kind, size, and modification time), and the agent confirms a hand-off
  there, on the engine that receives it, before that engine opens the file.
  Hand-offs are kept in `handoff/<from app id>-to-<to app id>/`. Each turn
  starts with the project folder's path and, for each open engine, its app and
  whether it has a command channel.
- **Engines that run at the same time exchange files through the control
  plane.** An engine's machine sees the project's folder as it was when the
  machine started, plus what it wrote itself: what it writes is on the Volume
  within seconds, for every engine started later, but a running engine never
  sees another's new file, and Modal refuses to reload the Volume under an
  application with files open (measured on SoundCraft, FilmCraft, PhotoCraft,
  and CADCraft). `engine_send(from_engine_id, path, to_engine_id, to_path?)`
  carries a file or a folder from one running engine of the project into the
  other's folder, at the same path unless `to_path` says otherwise: the bytes
  stream from a command of the one machine to a command of the other, 8 MiB in
  hand at a time (`send_file` in `addons/modal/sandbox.py`), the file appears
  only once whole, and the result is its entry as the receiving engine lists
  it. It is on the Volume from both machines. From a machine outside Modal,
  between two CPU engines: 1 MB in 1.7 s, 100 MB in 5.6 s, 1 GB in 42.7 s. The
  largest transfer is configuration (`MOODY_TRANSFER_MAX_MB`, 4096 by
  default); beyond it the agent is told to send less or to restart the
  receiver, which then opens on everything the folder holds.
- **The agent shows its work.** `preview(engine_id, path | paths, caption,
  kind?, compare?, look?)` brings files an engine wrote in the project's
  folder into the conversation as a work-in-progress card: a frame, a range
  the agent bounced or exported, a render, a document, of whatever length the
  agent chose with that engine's own commands. Nothing in the tool is about
  one engine or one length. A file is shown as it is where a browser plays it
  and it is light; otherwise the engine's own ffmpeg, which every session
  image carries, encodes a lighter copy outside the project's folder (sound to
  AAC, video to H.264 no wider than 1280 pixels, a picture to WebP no wider
  than 2048), the original untouched. What bounds a preview is configuration:
  the largest copy shown (`MOODY_PREVIEW_MAX_MB`, 50), the size over which a
  lighter copy is encoded (`MOODY_PREVIEW_ORIGINAL_MAX_MB`, 8), and the files
  in one preview (`MOODY_PREVIEW_MAX_FILES`, 12); a preview over the first is
  refused with what to render instead. `compare` shows two files of one kind
  as before and after. The model is told each file's facts (length,
  dimensions, size, and for sound its integrated loudness and true peak, read
  by ffmpeg), not the picture or the sound; `look` also hands it one small
  picture of each file (the image, four frames of a video, a sound's
  waveform). `engine_screenshot` shows its picture as the same card. Previews
  are files of the bucket under `<user id>/<project id>/previews/`, never
  library entries, and go when the project does.

## GitHub

A person connects their own GitHub account once, as the user authorization of a
GitHub App the control plane holds (`GITHUB_APP_CLIENT_ID`,
`GITHUB_APP_CLIENT_SECRET`, `GITHUB_APP_SLUG`), with repository Contents (read
and write) and Metadata (read). Its user token lasts eight hours and is kept
sealed beside the refresh token that renews it; the control plane refreshes it
before using one about to expire. The repositories a person can link are those
the app is installed on that they reach; where one is missing ("Don't see your
repository?"), the app's installation page installs it, or sends an
organization's owners the member's request, which an owner approves once. A
Games project can start linked, imported from GitHub in the new-project
dialog. The app makes no repositories: a new one is made on GitHub's own page,
then linked. The token stays in the control plane. The repository may be a
whole team's, so the agent reads it freely and saves the project's documents
only to a branch of its own, `moody/<project name>-<the project id's first
eight characters>`, made from the default branch's head the first time; it
never writes to the default branch or to a branch it did not make, and each
save gives the person the compare link from which they open a pull request.

An Unreal engine of a project linked to a repository clones it as it starts:
the control plane mints the person's token afresh (refreshing it where it has
less than seven hours left) and hands it to the machine in an ephemeral Secret
of that start, with the repository, the branch (the project's, else the
default), and the name and `<id>+<login>@users.noreply.github.com` address the
person commits under. The machine clones into `<project folder>/<repository
name>` with Git LFS and reports how far it has come (`clone`), which the
engine's card and the agent's turn read.

Unreal Engine's editor is licensed through a second, narrow connection,
"Connect Epic": an OAuth App that asks for `read:packages` alone
(`EPIC_GITHUB_CLIENT_ID`, `EPIC_GITHUB_CLIENT_SECRET`), since pulling from
`ghcr.io/epicgames/unreal-engine` takes a token that reads packages across
GitHub, which a GitHub App's token cannot. Whether the connected account is
linked to Epic is the registry's own answer (`linked`), and an Unreal engine
started while it is brings the user's own copy of the editor, pulled with that
token. Without the link the engine still starts, as the desktop the editor
would stream beside, and the studio shows the steps that link GitHub to Epic
with the "Connect Epic" button.

## Contract: the control plane's API

Every route takes the Supabase access token (`Authorization: Bearer`), as the
existing routes do, except GitHub's callback, which GitHub's redirect reaches
with a signed `state` instead, and answers JSON. Refusals are
`{"detail": "..."}`, with the same text under `error` for the first pages, and
the status that says why.

```text
GET    /v1/health                          {ok, agent, github, epic, generation}: which integrations are configured
GET    /v1/projects                        {projects: [Project]}, most recently updated first
POST   /v1/projects                        {name, discipline, format, github_repo?, github_branch?} -> {project}
GET    /v1/projects/{pid}                  {project}
PATCH  /v1/projects/{pid}                  {name?, pinned?, library_sections?} -> {project}
DELETE /v1/projects/{pid}                  204
GET    /v1/projects/{pid}/engines          {engines: [Session]}
POST   /v1/projects/{pid}/engines          {app, tier, region} -> {engine: Session}
GET    /v1/projects/{pid}/engines/{sid}/unreal-projects   {projects: [UnrealProject]}; 409 unless a running Unreal engine
POST   /v1/sessions/{sid}/link             {stream?} -> {url}: a fresh link to the desktop, or to the stream named
DELETE /v1/sessions/{sid}                  stops an engine (existing)
GET    /v1/projects/{pid}/events?after=N   {events: [Event], running}
POST   /v1/projects/{pid}/messages         {text} -> 202 {turn_id}; 409 while a turn runs
POST   /v1/projects/{pid}/stop             stops the running turn -> {stopped}: whether one ran
GET    /v1/projects/{pid}/library          {sections: [string], assets: [Asset]}
POST   /v1/projects/{pid}/library          {section, name, tag?, description?, metadata?} -> {asset}
POST   /v1/projects/{pid}/library/{aid}/media   multipart file -> {asset}
PATCH  /v1/projects/{pid}/library/{aid}    {section?, name?, tag?, description?, metadata?} -> {asset}
DELETE /v1/projects/{pid}/library/{aid}    204
GET    /v1/github                          {configured, connected, login?, avatar_url?}
POST   /v1/github/connect                  {return_to} -> {url}: the GitHub App's authorization page
POST   /v1/github/install                  {return_to} -> {url}: the GitHub App's installation page
GET    /v1/github/callback                 GitHub returns here; redirects to return_to?github=connected|installed|
                                           requested|failed, or, from an installation without Moody's state,
                                           to <site>/app/?github=installed|requested with nothing exchanged
GET    /v1/github/repos                    {repos: [{full_name, private, html_url, updated_at}]}: the GitHub App's
                                           installations' repositories the person reaches
DELETE /v1/github                          disconnects -> the same as GET /v1/github
POST   /v1/projects/{pid}/github           {repo, branch?} -> {project}
DELETE /v1/projects/{pid}/github           -> {project}
GET    /v1/epic                            {configured, connected, login?, linked: true | false | null, detail?}
POST   /v1/epic/connect                    {return_to} -> {url}: the Epic OAuth App's authorization page
GET    /v1/epic/callback                   GitHub returns here; redirects to return_to?epic=connected|failed
DELETE /v1/epic                            disconnects -> the same as GET /v1/epic
```

```text
Project  {id, name, discipline, format, pinned, created_at, updated_at,
          github_repo: "owner/name" | null, github_branch: string | null, library_sections: [string],
          plan: [{id, title, status: "pending" | "active" | "done" | "blocked"}]}
Session  the existing session shape, with project_id and app, and streams?: [{name, url}]
         for a running engine that streams more than its desktop: an Unreal engine's
         [{name: "Desktop", url}, {name: "Unreal", url}], each link minted for that
         listing of the engines, and never written to the event log; and clone?:
         {state: "cloning" | "done" | "failed", path, detail} for a running Unreal
         engine whose machine cloned the project's repository as it started
UnrealProject  {path, name, engine_association, version: "same" | "older" | "newer"
          | "source" | "unknown", opens, cpp_modules: [string], plugins: [string],
          lfs: true | false | string | null, size_bytes: number | null}: a .uproject
          in the engine's workspace, `opens` saying how this engine opens it
Asset    {id, section, name, tag, description, metadata, created_at, updated_at,
          media: [{kind: "image" | "video" | "audio" | "file", url, name}], thumbnail_url}
Event    {id, turn_id, kind, data, created_at}, kind one of
           user_message  {text}
           text          {text}            a piece of the agent's reply, in order
           tool_start    {call_id, tool, title}
           tool_end      {call_id, ok, summary, media?: [{kind, url}]}  `media` are the files a
                                              call made; one whose file is gone is left out
           ask           {question, options: [string]}
           plan          {items}
           library       {asset}, or {sections} when the agent set the sections; the asset
                                              is the entry as that event left it
           engine        {engine: Session}
           screen        {engine_id, stream}  the agent puts an engine, in one of its
                                              streams ("Desktop", "Unreal"), on the Screen
           preview       {engine_id, caption, compare, items: [{kind: "image" | "audio" | "video"
                         | "file", url, name, seconds?, width?, height?}]}  work in progress the
                                              agent shows: files an engine wrote, or its screen;
                                              `compare` makes two items a before and after pair.
                                              Each `url` is signed for the reading of the log
                                              that returned it, and an item whose file is gone
                                              is left out
           turn_end      {}
           error         {message, limit?: "budget" | "steps"}  `limit` names the limit of the
                                              person's the turn reached, where that is why it
                                              stopped; the message says how much it was and
                                              that they change it in their settings
```

The agent runs one turn at a time per project, as a Modal function the message
route spawns; it writes events as it goes and the app polls `events`. Its model
is the most capable Claude model by default (`MOODY_AGENT_MODEL`); it needs
`ANTHROPIC_API_KEY`, and generation needs `FAL_KEY`, both in the Modal Secret
`moody`. Library media is stored in Supabase Storage (bucket `library`,
private); `url` fields are signed and expire. The log keeps a file by its
path, so every `url` in an event (a call's `media`, the files of a `library`
event's asset, a preview's items) is signed for the reading of the log that
returned it, and reading the log again gives a fresh one.

## Contract: the agent on Anthropic's loop

The agent's loop is the Claude Agent SDK (`claude-agent-sdk`), the loop of
Claude Code as a library: it decides the next step, runs it, checks the
result, and goes on, with subagents, skills loaded when they are needed, the
conversation summarized as it grows, hooks, and approvals. Moody is everything
around it and stays Moody's own: the tools, the engines, the skills and
subagent definitions, the event log, storage, and the page. Other models reach
a project as tools (fal's image and video models are the first), so a better
model for one job is a tool added, never a loop replaced.

A turn is one run of the loop (`moody/control/loop.py`), in the worker the
message route spawned. The SDK runs its `claude` program as a child process
of that worker; the program gets the Anthropic key, directories made for the
turn, and the variables the deployment names (`MOODY_LOOP_ENV`), and nothing
else of the worker's environment, so no other secret of the deployment is in
a process the model steers.

- **Tools.** Moody's tools (`TOOLS` and `Agent.tool_<name>` in
  `moody/control/agent.py`) are served to the loop in process, which names
  each `mcp__moody__<name>`, and the loop's own file and shell tools are off:
  the agent reaches nothing of the machine its turn runs on. Of the loop's
  own tools four are on beside the one that starts a subagent, and the events
  call them `web_search`, `web_fetch`, `skill`, and `read`. A fetch is of a
  public web address or it is refused, and `read` reads the files of the
  skills the project is offered and no other path, both checked before the
  call runs. A tool's definition says what it looks like while it runs
  (`activity`, one of `catalog.json`'s `activities`), whether it only reads
  (so the loop may run several at once), and whether the person approves it
  first (`approval`).
- **Looking.** The agent is told what a tool made, not shown it: a file's
  facts cost nothing on the turns that follow, and its pixels would. Where it
  has to judge a result itself it asks to look, and is handed one small
  picture of each file: an image itself, four frames of a video on one sheet,
  a sound's waveform. `preview` and `engine_screenshot` do that for a file in
  an engine, where the engine makes the picture. `look` on `generate_image`
  and `generate_video`, and `library_look` for entries of the library, do it
  for files no engine holds: the turn's own worker makes the picture, with
  ffmpeg run as another user, with an empty environment and no network, so
  the program that parses a generated or uploaded file reaches no secret of
  the deployment. Looking shows the person nothing.
- **Skills** are `moody/skills/<name>/SKILL.md`, loaded by the loop on
  demand: the description of each skill the project is offered is always in
  context, its body when the agent opens it with `skill`, a reference file
  when the body sends the agent to it and the agent reads it with `read`.
  Which skills a project is offered is the discipline's (`skills_for`), and
  the loop refuses to open any other.
- **Subagents** are `moody/agents/<name>.md`: front matter and a system
  prompt. The agent hands a subagent one job; it works in a context of its
  own with the tools its definition lists, several at once where the jobs are
  independent, and only its final report returns to the agent. A subagent
  cannot ask the person a question or start a subagent of its own. The page
  shows each one working.

  ```text
  ---
  name: research                 the id, the same as the file's stem
  title: Research agent          what the page calls it
  description: When the agent should hand work to it, in a sentence or two.
  disciplines: all               or a list of discipline ids, as for a skill
  tools: web_search, web_fetch, library_list, library_upsert
                                 Moody tool names; `engine_*` style prefixes allowed
  skills: movie                  optional: skills it reads
  model: inherit                 inherit (default), balanced, or light: tiers the deployment
                                 maps to models (`MOODY_AGENT_MODEL`, `..._BALANCED`, `..._LIGHT`)
  ---
  The subagent's system prompt.
  ```

  A file whose name starts with `_` is a template, not a subagent. One is
  read: `_operator.md`, from which an operator is derived for every app that
  can be started. Its `name` is the app's id and its `title` "<App name>
  agent"; `{app}` and `{name}` in the template's description and prompt are
  the app's id and name. Its tools are the template's, or else `engine_*` and
  `preview`, then those the skill named after the app lists for it
  (`operator_tools` in that skill's front matter: what drives one engine and
  no other). It reads that skill; an app without one has an operator that
  reads none. A project is offered the operators of its discipline's engines
  and of the engines whose skill it is offered. A definition's text may open
  with a comment (its license header), which is not part of the prompt. A
  definition that names a tool or a skill that does not exist, or whose
  `name` is not its file's, keeps the agent from starting.
- **Approvals.** A tool whose definition says `approval: ask` (starting an
  engine, generating video) waits for the person, unless the project's
  permissions say `always` for it: the call's `tool_start` is followed by an
  `approval` event, and the turn goes on once an `approval_result` is
  recorded. `once` and `always` run the call; `deny` and `expired` end it
  with a `tool_end` that is not ok, and the model is told which. "Always" is
  kept for that tool in that project (`Project.permissions`) and revocable in
  the Environment panel. A wait ends as `expired` after
  `MOODY_APPROVAL_SECONDS` (600 by default), and the model is then told to
  end its turn and ask. An approval is answered once: the first answer
  recorded stands, and the route says whether the one it was sent is that
  answer (`recorded`). A subagent's approval carries its `agent_id`, as its
  result does. Engines cost credits every minute, so none starts unless the
  work needs it or the person asked: planning, writing, and generating need
  no engine, and a turn that is about to end while engines of the project are
  open is told so once, to stop each or say why it stays open.
- **Questions and interactive cards end the turn.** `ask_user` and a
  `show_ui` that waits write their event and end the turn (a tool's result
  says so with `ends_turn`): the loop makes no further model call, and its
  process is gone while the person decides. The person's answer or locked-in
  values start the next turn, which resumes the same session. A message that
  locks in a card names it (`ui_id`, which must be a `ui` event of the
  project) and carries its state (`value`, JSON of at most 64 KiB); the
  model reads them as a line after the person's words.
- **The agent recommends where a decision is the person's.** A question
  (`ask_user`) may name one of its options as `recommended`, the one the agent
  would choose for the project's taste and brief, and the page marks it with a
  quiet "(recommended)"; a question the agent has no preference on names none.
  One whose `recommended` is none of its options, or one of whose options says
  in its own text that it is recommended, is sent back to the agent and does
  not reach the person, so an option's text is only the option. In a report,
  the agent says which way it would go beside each decision it leaves to the
  person. Interactive cards carry no recommendation: a card shows the thing
  and its controls, opens on the starting values the agent gave it, and once
  the person has changed something offers one way back, "Back to default".
- **A long job ends with a report.** After work of many steps the agent's last
  message is organized under short headings it chooses for what it has to
  say (what was done, what there is now, decisions that are the person's,
  what it needs from them, what it does not know), each a few bullets, the
  most important first. A short exchange gets a short answer and no headings.
- **Limits are the person's settings.** What one turn may spend on the model
  and how many steps it may take are settings of the person's account
  (`profiles.turn_budget_usd`, `profiles.turn_limit`), which they change in
  the app. An account that has not set one runs on the deployment's default
  (`MOODY_TURN_BUDGET_USD`, 15; `MOODY_TURN_LIMIT`, 200), and no account sets
  one above the deployment's ceiling (`MOODY_TURN_BUDGET_MAX_USD`, 100;
  `MOODY_TURN_LIMIT_MAX`, 1000). A turn runs on its person's limits as they
  were when it began. A setting made before the ceiling was lowered runs at
  the ceiling, and so does a default set above it. The number of steps is a
  whole number.
- **Sessions.** A project's conversation is one SDK session
  (`projects.agent_session`), its transcript stored in the database
  (`agent_transcripts`) through the SDK's session store as the turn writes
  it, so a turn resumes on any machine, days later. The loop keys a session
  by the turn's working directory, which is `<MOODY_LOOP_ROOT>/<project id>`
  on every machine. What changes between turns (the plan, the library, the
  engines, what was shown) is sent with each message, after the person's
  words. A project that has events and no session yet starts one that is
  first told what was said before.
- **Spending.** The loop enforces the person's two limits. A turn that
  reaches one ends with an `error` event that names it (`limit`), and the
  calls of the answer that reached the budget still run. Every turn ends with
  a `usage` event. `cost_usd` is the loop's own pricing of the turn's model
  calls, subagents' included, and is what the budget is counted in;
  generation and engines are not in it.
- **Stopping.** `POST /v1/projects/{pid}/stop` interrupts the loop: a call
  still running ends with a `tool_end` that is not ok, a subagent's card ends
  `stopped`, and what was written of the answer stays as its last snapshot.

Additions to the API:

```text
POST   /v1/projects/{pid}/messages         {text, ui?: {ui_id, value}} -> 202 {turn_id}: `ui` locks in an
                                           interactive card; `value` is the card's state, JSON. `text` may
                                           be empty with a `ui`. 404 for a card the project has not shown,
                                           413 for a `value` over 64 KiB
POST   /v1/projects/{pid}/approvals/{aid}  {decision: "once" | "always" | "deny"} -> {recorded}: whether this
                                           answer is the one that stands; 404 for an approval the project's
                                           agent did not ask for
GET    /v1/projects/{pid}/environment      {connectors: [Connector], agents: [AgentInfo], skills: [SkillInfo]}
PATCH  /v1/projects/{pid}                  also {permissions?: {tool: "always"}}: what the person no longer
                                           wants to be asked about, the whole of it; a tool left out is
                                           asked again
GET    /v1/me                              also {limits: Limits}
PATCH  /v1/me                              {turn_budget_usd?: number | null, turn_limit?: number | null} -> the
                                           same as GET /v1/me. `null` puts a limit back on the deployment's
                                           default; 400 for a value that is not positive or is over the
                                           deployment's ceiling
```

```text
Project      also {permissions: {tool: "always"}}
Connector    {id, name, kind: "generation" | "repository" | "search" | "license" | "mcp",
              state: "connected" | "available" | "off", detail}: a service the project's agent can
              use, or could once the person connects it. The ids are `fal`, `github`, `web`, and,
              in a project whose discipline has Unreal Engine, `epic`; `off` is a service the
              deployment is not configured for
Limits       {turn_budget_usd, turn_limit, own: {turn_budget_usd: number | null, turn_limit:
              number | null}, default: {turn_budget_usd, turn_limit}, max: {turn_budget_usd,
              turn_limit}}: what a turn of this person's may spend on the model, in dollars, and
              how many steps it may take; `own` is what they set themselves, `null` where they
              have not, and the two at the top are what applies
AgentInfo    {name, title, description}: a subagent this project's agent can hand work to
SkillInfo    {name, description}
Activity     one of catalog.json's `activities` ids: thinking, searching, processing, analyzing,
              creating, curious, confused, focused, surprised, satisfied (the pixel eyes' expressions)
```

Additions to the events. Any event may carry `agent_id` in its `data`: the
subagent it belongs to, absent for the agent itself.

```text
user_message     {text, ui?: {ui_id, value}}
ask              {question, options: [string], recommended?}   `recommended` is the option the agent
                                            would choose, one of `options`, where it has a view
text             {text, block?, partial?}   `block` names the block of the answer this is; a later
                                            event with the same `block` replaces it, which is how an
                                            answer appears while it is written (`partial: true`).
                                            A block is written at most once a second while it grows,
                                            each event carrying all of it so far, and once whole,
                                            without `partial`
thinking         {text, block?, partial?}   the model's reasoning, summarized; folded the same way
tool_start       {call_id, tool, title, activity}
                                            written as the call is about to run, after the words the
                                            model wrote before it. `tool` is Moody's name for it. A
                                            call the loop refuses for its input writes no event, and
                                            handing a job to a subagent writes none: its card stands
                                            for it
agent            {agent_id, group, name, title, task, state: "working" | "completed" | "failed" |
                 "stopped", activity, detail, seconds?, tokens?}
                                            a subagent's card. Every `agent` event carries the whole
                                            card; the latest for an `agent_id` is its state. `group`
                                            is shared by the subagents one step started together,
                                            `task` is the job in a line, `detail` what it is doing now.
                                            `activity` is `thinking` until it runs a tool, then that
                                            tool's, `confused` after a call that failed or when it
                                            ends any way but completed, `satisfied` once completed
approval         {approval_id, tool, title, detail}   the agent waits for the person; `detail` is what
                                            the call will cost, as far as that is known
approval_result  {approval_id, decision: "once" | "always" | "deny" | "expired"}
ui               {ui_id, title, kind: "components" | "html", spec?, html?, height?, submit: string | null,
                 waits, media: [{name, kind, url}]}
                                            an interactive card. `spec` is a tree of the components
                                            `moody/ui.json` defines; `html` is a document the page
                                            runs in a sandboxed frame. `submit` is the lock-in
                                            button's label, null for a card with nothing to send
                                            back. `media` are the files the card shows, signed for
                                            each reading of the log
usage            {input_tokens, output_tokens, cost_usd, seconds, agents}   once per turn, before turn_end.
                                            `input_tokens` counts what was read from and written to
                                            the cache too, `agents` the subagents the turn started
```

## Contract: starting a project by its kind

A project of a discipline is of one of that discipline's formats, its kind:
for Media, in this order, Film & TV, Social Media, Vertical Shows,
Commercials, Music Videos, Education, and Other. The kind decides how the
agent opens and which default workflow it follows, so it is asked first, by
the conversation itself.

- **A project may start without a format.** `POST /v1/projects` takes
  `format` as optional. Where it is left out and the discipline has formats,
  the control plane writes the project's first event itself, with no turn and
  no model: a `ui` card that asks the kind (`catalog.json`: the discipline's
  `opening` title, its `formats`, and for each its `kinds` entry, a line and
  an icon's name in the catalog's `icons`). The card is `instant`: choosing
  locks it. Its data carries `sets: "format"`, and the message that locks it
  sets the project's format to the chosen one before the turn begins, so the
  agent's first turn already knows the kind.

  The event has no `turn_id`, and its data is `{ui_id, title, kind:
  "components", spec: {type: "pick", id: "format", options: [{value, label,
  note?, icon?}]}, submit: null, waits: true, instant: true, sets: "format",
  media: []}`. An option's `value` and `label` are the format, its `note` the
  kind's line, and its `icon` the rows the catalog's `icons` has under the
  name the kind gives, left out where it has none. The pick's id is what the
  card sets, so the message that locks it carries `ui.value` `{format: <the
  kind>}`. A kind the discipline does not offer is a 400 and starts no turn.
  With the kind, a project whose library is untouched takes that kind's first
  sections (`kinds.<format>.sections` in the catalog, else the discipline's
  `sections`). The project's state names the kind at the start of every turn
  (`Kind:`, and `not chosen yet` where the person wrote before choosing), and
  the turn that chose it reads that as a line after the person's words.
- **The agent opens each kind with a card of its own**, written by the
  `video` skill for that kind: where the story comes from for Film & TV, the
  track for a music video, the platform and the goal for social media. It
  gathers what the work needs in as few, as easy answers as it can, and keeps
  the project moving: every turn ends on a next step it has already prepared
  or on one decision made easy.
- **Cards for these openings.** A `pick` option may carry `icon` (a pixel
  icon as rows of `0` and `1`, a square of eight to sixteen cells) in place
  of an image, or `audio` (the name of one of the card's files), which makes
  the option a tile that plays, so two or three sounds are compared by ear. A
  card may be `instant` where its one input is a single choice. An `upload`
  input takes a file from the person into the project's library and answers
  with the entry it made (`{tag, name, kind}`).
- **Sound is generated like pictures.** `generate_audio(prompt, kind:
  "music" | "sound" | "speech", lyrics?, instrumental?, voice?, style?,
  seconds?, count?, save_to?)` makes a song, an instrumental, a sound effect,
  or a spoken line through fal, shows each result with a player, and keeps it
  in the library where `save_to` says. The models are data beside the image
  and video models (`moody/control/generation.py`): MiniMax Music 3 for
  `music` (up to 300 seconds; lyrics, or `instrumental`, never both), ElevenLabs
  Sound Effects v3 for `sound` (half a second to thirty, from at most 450
  characters; the model chooses the length where `seconds` is left out), and
  Gemini 3.8 Flash TTS for `speech` (`prompt` is the words, `voice` one of its
  thirty, `style` a line of direction that is not spoken, and no `seconds`).
  `count` is one to four takes, each a call of its own, run at once: a take
  that does not come back is told, and the others are kept. What a kind does
  not take is refused before anything is paid for. A result is a `tool_end`
  with `media` of kind `audio`.
- **Video is also edited by code.** The Cut Room engine (`cutroom`) is a
  machine with no application to click: FFmpeg, speech-to-text with word
  timings, voice mastering, captions, and the scripts that find the moments
  in footage, cut vertical clips and horizontal explainers, lay narration,
  music, and titles, and check the result. The agent drives it with
  `engine_exec`, by the recipes of its skill, and shows each cut with
  `preview`. It is the default way a Social Media or an Education video is
  made, as FilmCraft's timeline is for Film & TV; a default, which the agent
  leaves when the work or the person calls for something else.
- **The latest version is always at hand.** `preview` takes an optional
  `version`, a short label ("Rough cut", "v3") that marks what it shows as a
  version of the piece itself, and the event carries it, trimmed and at most
  forty characters; a preview without one has no `version`. The page's right
  pane has a **Latest** module that plays the newest version (failing one,
  the newest video or sound the session showed), full screen on request,
  hands its file to the person to keep, and lists the versions before it. The
  file is handed over by the address the control plane signed with `download`
  added, which the storage serves as an attachment under the file's name.
- **Every module of the right pane folds**, and so does each section inside
  Environment, by a quiet arrow that shows on hover and focus.

- **Settings are the person's, and one place holds them.** The account menu
  opens Settings: Profile (name, email), Billing (credits, buying more),
  Agent (what a turn may spend and how many steps it may take), Video editing,
  Connections (GitHub, Epic, Claude), and API keys. A setting that is a plain
  switch or choice is data: `catalog.json`'s `settings` gives each its id, the
  tab it sits on, its label and one line of help, its kind (`toggle` or
  `choice`, with the options), and its default. The control plane keeps what a
  person changed (`profiles.settings`) and refuses an id or a value the
  catalog does not offer, so adding one is a catalog entry and the code that
  reads it. An entry is `{id, tab, label, help, kind: "toggle" | "choice",
  options?: [{value, label}], default, apps?}`: a toggle is `true` or `false`,
  a choice one of its options' `value`. A setting that chooses between
  engines names the app each value stands for in `apps` (a toggle's under
  `on` and `off`, a choice's under its options' values): the agent is told of
  the one that applies, and the form that starts an engine by hand offers
  only that one, so the choice is made in Settings and nowhere else. A value kept from before the catalog
  stopped offering it does not apply, and the default does. The name
  (`profiles.name`) is at most eighty characters, and `null` clears it. A
  change that is refused in any part changes nothing.
- **HyperFrames is the other way to edit by code.** The `hyperframes` engine
  runs HeyGen's open-source HyperFrames (Apache 2.0): a video written as HTML,
  CSS, and seekable animation, rendered by a headless browser and FFmpeg, with
  its live preview on the engine's Screen. It follows upstream: a machine
  takes the newest release and that release's own skills as it starts, and
  falls back on the ones its image was built with. A release is switched to
  only once it has installed whole and rendered on that machine, and the
  update has two minutes; `MOODY_HYPERFRAMES_VERSION` in the control plane's
  environment holds every session on one release. Which engine the agent
  reaches for when a video is edited by code is the person's setting
  (`video_hyperframes`, a switch on the Video editing tab, off by default, so
  the Cut Room unless they turn it on); the turn's state names the one that
  applies, as `A video edited by code is made in: <App> (app `<id>`)`: the
  app the person's value stands for in the setting's `apps` where the catalog
  has it as one that can be started (`hyperframes`, switched on), the app the
  default stands for otherwise (`cutroom`), and no line where the catalog has
  neither to start.

Additions to the API and the events:

```text
GET    /v1/me                              also {name, settings: {id: value}}: every setting of the catalog
                                           with the value that applies, the person's own or its default
PATCH  /v1/me                              also {name?, settings?: {id: value | null}}: `null` puts a setting
                                           back on its default; 400 for an id or a value the catalog does
                                           not offer
POST   /v1/projects                        {name?, discipline, format?, ...}: without a format, the project
                                           opens on the card that asks its kind
ui               also {instant?, sets?: "format"}
preview          also {version?}
```

## What is done when

1. FilmCraft engine on Modal, verified streaming and driven through its command
   channel.
2. The FilmCraft skill.
3. The control plane: projects, library, engines per project, the agent, GitHub.
4. The app: the three panes over that API.
5. The landing page: disciplines first, one page (the two-option toggle goes).
6. The agent driving any engine with a command channel through one tool, and
   moving work between engines through the project's folder (`engine_call`,
   `engine_files`, the `studio` skill).
7. PhotoCraft engine, driven through its command channel, with its skill, and
   work passing between it, FilmCraft, and Blender as files of the project's
   folder.
8. The agent showing its work in the conversation (`preview`), and engines
   that run at the same time exchanging files (`engine_send`).
9. Next: Unreal Engine, billing the agent's model and generation use.
