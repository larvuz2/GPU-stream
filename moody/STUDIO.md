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
| Left sidebar | New project, search, **Pinned** and **Recent** projects, the account (credits, Connect Claude, sign out) |
| Center | The project's conversation with the agent: messages, tool activity, the agent's questions as choices, generated images and videos inline, the composer |
| Right pane | Modular panels the project shows as it needs them: **Screen** (the live stream of an engine), **Environment** (the engines running, start and stop, **Connect GitHub**, and, for Unreal Engine, **Connect Epic**), **Plan** (the agent's tasks and their state), **Library** (the project's characters, environments, props, products, or whatever sections the project has) |

Clicking the screen rearranges the panes: the stream becomes the largest area,
above the conversation, which stays visible below it. The library's sections are
the project's own, never a fixed list: a film has characters, environments, and
props; a commercial has products and shots; the agent adds sections as the work
needs them.

A new project starts from one of twelve disciplines (`catalog.json`,
`disciplines`), the first being **Media** (movie, commercial, episode, vertical
drama), and the agent opens the conversation: a script to bring, or one to
write together.

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

The agent's craft knowledge is a skill (`moody/skills/filmcraft/SKILL.md`):
pre-production, prompting with references, and editing with taste, mapped to
FilmCraft's commands. How a production runs across engines is a skill of its
own, read for every project (`moody/skills/studio/SKILL.md`), and
`moody/skills/README.md` is the guide to writing another.

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
           tool_end      {call_id, ok, summary, media?: [{kind, url}]}
           ask           {question, options: [string]}
           plan          {items}
           library       {asset}, or {sections} when the agent set the sections
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
           error         {message}
```

The agent runs one turn at a time per project, as a Modal function the message
route spawns; it writes events as it goes and the app polls `events`. Its model
is the most capable Claude model by default (`MOODY_AGENT_MODEL`); it needs
`ANTHROPIC_API_KEY`, and generation needs `FAL_KEY`, both in the Modal Secret
`moody`. Library media is stored in Supabase Storage (bucket `library`,
private); `url` fields are signed and expire.

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
