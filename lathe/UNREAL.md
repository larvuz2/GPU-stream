# Unreal Engine in Lathe: the plan

An Unreal engine is one machine that runs the Unreal Editor and Blender side
by side, on a GPU, for one user and their project, streamed to their browser.
This file is what was measured and found, the design that follows from it, and
what is built in which order. The code that implements each part documents its
mechanism.

## What was measured and found (2026-11-24)

**Unreal versions.** 5.8.4 is the current release (2026-10-20). 5.9 is in
preview (Preview 2, 2026-11-19), with an MCP server that starts with the editor
and an in-editor assistant; Epic calls it a release for next year. The engine
targets 5.8.4 and moves to 5.9 when it is released, when the agent can drive
the editor through that MCP server.

**GPU graphics on Modal.** In a Sandbox whose image sets
`NVIDIA_DRIVER_CAPABILITIES=all`, Modal mounts NVIDIA's graphics libraries and
Vulkan reaches the GPU (`vulkaninfo`: Tesla T4, NVIDIA 620.70.06, Vulkan
1.4), and Vulkan renders with no window (`vkcube --wsi headless`). Vulkan
cannot present into the X display Selkies streams (`vkcube` on the display
fails creating its swapchain): presenting needs `/dev/nvidia-modeset`, which
gVisor does not provide. Without the capability set, the graphics libraries
are not mounted at all, which is why `vulkaninfo` crashed in earlier tests. Epic
says the editor does not work on a software Vulkan driver.

So the editor renders off screen on the GPU and streams itself: Unreal's
editor streaming (Pixel Streaming 2, `-RenderOffScreen`), encoded with NVENC.
Blender and the rest of the desktop stay in the Selkies session beside it.

**Getting the editor.** Every way to the Linux editor goes through a
licensee's identity: the precompiled build behind an Epic sign-in (about 39 GB
to download, 70 GB installed), the source on GitHub, or Epic's container
images on `ghcr.io/epicgames/unreal-engine`. The last two need a GitHub account
linked to an Epic account.

**The license.** The EULA counts making the editor available over a network as
distribution (section 4), and allows public distribution of the editor only
through Fab or Epic's GitHub fork network (sections 5(a)(i) and 6(d)); it also
forbids renting it (6(e)). One shared image of the editor served to every user
is Lathe distributing it, which needs Epic's written agreement. What fits the
text is each user getting their own copy with their own identity: Lathe pulls
Epic's container image with the user's own GitHub token, from the account they
linked to Epic, into an image only their sessions use. Every user needs an Epic
account (9(c)) and accepts the EULA themselves. Epic should confirm this before
it is offered to the public.

## The design

| Part | What it is |
| --- | --- |
| Identity | The user connects GitHub (Lathe's existing step, now also asking `read:packages`) and links that GitHub account to their Epic account on epicgames.com. Lathe checks the link by whether their token can see `EpicGames/UnrealEngine`, and says how to link when it cannot. |
| Image | Per user: Epic's development image of 5.8.4 pulled with the user's token, with the Selkies session, Blender, the bridge, and a TURN relay layered on it. Built once per user and version, then cached; never shared between users. |
| Machine | L4 (24 GB, two NVENC, AV1), 8 cores, 32 GB by default; L40S (48 GB) for heavy scenes. A100 and H100 have no NVENC and are not offered. |
| Picture | Two streams of one machine: the Selkies desktop (Blender, files, the browser for Epic and Fab sign-ins) and the editor's own stream. The studio's Screen panel switches between them. |
| Transport | The editor's stream is WebRTC. Its signalling and player page pass Modal's HTTPS proxy; its media goes through a TURN relay inside the Sandbox, reached over TCP through a raw port Modal exposes (`unencrypted_ports`), with per-session credentials. |
| Blender and Unreal | One machine, one project folder. A Blender add-on exports the selection (glTF, or FBX for rigs) into the project's `bridge/` folder and asks the editor to import it through its Remote Control API on loopback, which runs the import in the editor's Python; the editor sends back the same way to Blender's Python spool. No network between machines is needed for the hand-off. |
| The agent | Drives the editor through the Remote Control API and its Python now, and through the editor's MCP server on 5.9. |

## A studio's existing project

Studios do not start from nothing: a team keeps its game in a GitHub
repository, each developer clones it into a folder of their choosing, opens the
`.uproject` there with the Unreal Editor, and commits what changed from their
own Git client under their own name. The engine does the same thing for them in
the cloud, without changing how the team works.

**Once per person.** Sign up; connect GitHub (one click); link that GitHub
account to Epic, which most Unreal developers already have. Where the team's
GitHub organization restricts third-party apps, which new organizations do by
default, an owner of the organization approves Lathe once (Settings,
Third-party access); until then the organization's repositories do not appear.

**Once per game.** A Games project picks the repository and its branch. Lathe
reads the `.uproject` before anything starts and shows what it found: the
engine version the project was saved with (`EngineAssociation`), whether it has
C++ modules or only Blueprints, its plugins, and whether the repository keeps
its assets in Git LFS.

**Each start.** The machine clones the repository into the user's own folder of
the workspace Volume with their token, Git LFS included, the first time, and
only fetches after that; the engine's derived data cache stays beside it, so
shaders compile once per project rather than once per start. Commits carry the
person's own GitHub name and address, as each developer's own client does.

**Versions.** The engine runs one current version, 5.8.4 now, which carries
Epic's Unreal MCP server (experimental in 5.8); 5.9 becomes the default when it
is released, and is offered as a preview only where Epic publishes its image.
A project is never converted on the team's own branches:

| The project was saved with | What the engine does |
| --- | --- |
| The engine's version | Opens it as it is. |
| An older version | Opens it on the agent's branch (`lathe/<project>`), where the editor upgrades what it saves. Assets saved by a newer editor do not open in an older one, so the upgrade stays on that branch until the team decides to move. |
| A newer version | Says so: Unreal does not open a project in an older editor. |

**What may not come along.** C++ modules are compiled for Linux in the machine
with the engine's own toolchain (the first build takes the longest); where code
written for an older engine no longer compiles, the agent shows the errors and
helps fix them on its branch. A plugin with its source is compiled the same
way; one distributed as binaries only, without a Linux build for this version,
is switched off in the agent's copy of the `.uproject` and listed, so the
editor opens without it. The team still packages Windows builds on their own
machines: the engine runs Linux.

## Order of work

1. Prove the transport: WebRTC media from a Sandbox to a browser outside Modal
   through the TURN relay over the raw TCP port, measured.
2. The image recipe and the session: Epic's image pulled with a registry
   credential, the Selkies session and Blender on it, the editor started off
   screen with editor streaming, the relay, the bridge.
3. Lathe: the Epic link check, the `read:packages` scope, per-user image builds,
   the Unreal engine in the catalog, and the Screen panel's second stream.
4. With a GitHub token linked to Epic: build the real image, open the editor,
   stream it, send a mesh from Blender, and measure start time, frame rate, and
   latency.

## What is built (2026-11-24)

The parts that need no Unreal binary: nobody on the team has a GitHub account
linked to Epic, so the editor cannot be pulled, and each part below is tested
against stand-ins for it.

- **The transport** (step 1, measured). WebRTC video from a Sandbox reached
  headless Chromium and Firefox in a second Sandbox through coturn over TCP,
  on the public address Modal gives a raw port, with the browsers relay-only:
  connected in 0.2 s in one region (0.5 s across the country), the first frame
  in 0.35 s (1.3 s), 30 frames a second with none dropped, a round trip of
  15-17 ms (66-97 ms), at 2.9 to 12 Mbps. A wrong credential and a peer
  outside the Sandbox are refused. The launcher has it as `start_session(...,
  tcp_ports=...)`, `tcp_address()`, `up --tcp-port`, and `with_turn(image)`
  (`addons/modal/webrtc`). Chromium cannot be the test browser inside gVisor
  (it gathers no candidates there); people's own browsers are not affected.
- **Fetching the editor** (`addons/modal/unreal/fetch-engine.sh`). A build step
  that streams one directory out of a container image with crane, logged in
  with the build's secret, which no layer keeps. Checked on Modal: a public
  image's directory arrives owned by the session's user with no login left in
  the image, and `ghcr.io/epicgames/unreal-engine:dev-slim-5.8.4` with a token
  not linked to Epic is refused by ghcr (`DENIED`) with the explanation of what
  the user needs.
- **The machine's desktop and image** (`addons/modal/unreal`, `up --app
  unreal`). A developer brings their team's project in as they do at their
  desk with GitHub Desktop. `session_image("unreal")` is the Selkies desktop
  (with `NVIDIA_DRIVER_CAPABILITIES=all`) opening on a GitHub client with one
  line: sign in, then clone the game here. The client is Desktop Plus, the fork
  of GitHub Desktop that follows it (3.6.12); the Linux fork people know,
  shiftkey/desktop, stops at 3.4.13 of February 2025. Its sign-in goes to
  Firefox and back without a prompt. It is kept in GNOME's keyring in the
  workspace, with the client's settings and Git's name and address. The clone
  dialog offers the project folder (`SELKIES_MODAL_PROJECT`), else `projects`,
  and Git LFS is set up for every repository. Blender is there with Send to
  Unreal enabled. `selkies-modal-unreal-projects`, which
  `unreal_projects(sandbox)` returns, describes every `.uproject` in the
  workspace: the engine it was saved with, its C++ modules, its enabled plugins
  and whether each has its source in `Plugins/`, whether its files are in Git
  LFS and fetched, and its size. The Unreal view is port 8090, reached with
  `unreal_view_link(sandbox)`: a page saying Unreal is not open yet, served by
  an s6 service whose server the player is to replace.
  `selkies-modal-unreal-open` starts the editor off screen with editor
  streaming and Unreal MCP on loopback, after building the project's C++, and
  says so when the machine has no editor. `unreal_image(registry_secret,
  version)` is the same desktop over the engine layer, which sits right above
  the base so no other change fetches it again. Checked on Modal (timings in
  `addons/modal/README.md`, Unreal):
  - The desktop came up on CPU and on a T4.
  - A UE 5.4 sample with 109 LFS files was cloned with git, and a 5.5 one
    through the client into the folder it offered; both were described
    correctly.
  - The view opened through its link and refused the address without its token.
  - Blender's add-on was enabled.
  - The missing editor was reported.
  - The sign-in went as far as GitHub's token exchange, which refused a
    made-up code.
  - The keyring, the repository list, and Git's identity were back in the next
    session.
  - `unreal_image`'s recipe built with a public image in place of Epic's, and
    rebuilt after a script change with the engine layer taken from the cache.
  - The open script's other outcomes ran against stand-ins for the editor.

- **The bridge** (`addons/modal/unreal`). Blender's add-on `send_to_unreal.py`
  (3D viewport sidebar, tab Unreal) exports the selection into the project's
  `bridge/` folder, as glTF binary for meshes and FBX for anything with an
  armature, beside a manifest, and asks the editor to import it:
  `PUT http://127.0.0.1:30010/remote/object/call` on
  `/Script/PythonScriptPlugin.Default__PythonScriptLibrary`, function
  `ExecutePythonCommandEx`, with a `PythonCommand` that runs `unreal_import.py`
  (one `AssetImportTask` into `/Game/Blender/<name>`, placed in the open level
  when asked). The way back, `send_to_blender.py` (Tools, Send to Blender, which
  `init_unreal.py` adds), exports the selected actors or static meshes as FBX
  and puts a request in Blender's spool. `DefaultRemoteControl.ini` is what the
  editor's project needs for the call. Tested in Blender 5.2.4: real exports, a
  stand-in for the Remote Control API that records the request and runs its
  command against a stand-in `unreal` module, and the way back served by
  `blender/session.py` itself (`pytest addons/modal/unreal`).
- **The control plane.** GitHub's OAuth App asks for `read:packages` beside
  `repo` and keeps the scopes it was granted. `epic_link` reads whether the
  user's token sees `EpicGames/UnrealEngine` and the
  `ghcr.io/epicgames/unreal-engine` package (`GET /v1/github`: `epic_linked`,
  `null` without GitHub or the scope). Starting `unreal` (catalog status `byol`)
  is refused until it is linked, with the steps that link it. Each start writes
  the user's login and token into their own named Modal Secret,
  `lathe-ghcr-<user id>` (`REGISTRY_USERNAME`, `REGISTRY_PASSWORD`), which a
  reconnect refreshes and a disconnect deletes, and `launcher.py` passes that
  Secret to `unreal_image(registry_secret, version)` where the launcher has
  one. Named rather than made per start, so the layer that pulls the engine
  (about 40 GB) stays cached per user.
- **The studio.** The catalog lists Unreal Engine 5.8 as `byol`, labeled "Your
  Epic account" on the landing page. Choosing it in the Environment panel shows
  the link: linked, not linked with the steps and Epic's page, or GitHub to
  connect first or again; Start waits for the link. The Screen panel switches
  an engine that reports `streams` between "Desktop" and each stream (the
  Unreal Editor). The demo's Games project, Ember Ridge, has an Unreal engine
  with both.

## What is open

- A session on `unreal_image` with a real editor. Whether the editor starts on
  `addons/modal/unreal/open.sh`'s command line is unchecked: the Unreal MCP
  plugin's name and `-EnablePlugins` are unverified. Also to build: the Pixel
  Streaming player on the Unreal view and the TURN relay under it
  (`addons/modal/unreal/view/view.sh` has the plan), and a page on the player
  counting as use of the session. Whether Modal shares a layer pulled with one
  user's Secret with another user's build has to be checked there.
- The GitHub client's sign-in with a real account: it is checked as far as
  GitHub's token exchange. The client signs in through Desktop Plus's own OAuth
  app, so an organization that restricts third-party apps has an owner approve
  it once, as for Lathe's.
- Firefox shows its own terms of use at its first start in each session, since
  its profile is not kept. The policy that skips them accepts them on every
  user's behalf, so it is not set.
- The control plane does not report a session's `streams` yet: the editor's
  stream address comes with the transport (order of work, step 1).
- Unverified against a running editor: the Remote Control body follows Epic's
  HTTP reference and the function's names in Epic's Python reference (the C++
  parameter names are from a third-party quote of its declaration); the two
  settings that gate remote Python, and the errors each gives, are from a
  third-party package's notes, since Epic's settings page renders only in a
  browser. The add-on shows Unreal's own refusal either way.
- Unverified against GitHub: whether the EpicGames organization restricts
  third-party OAuth Apps. If it does, a linked user's token cannot see the
  repository, so the check cannot show the link (it reads "not linked", or
  unknown with GitHub's refusal), and Lathe needs Epic's approval of its OAuth
  App or another way for a user to grant the pull.
- **The base image the sessions are built on is gone from its registry.** The
  Selkies base digest `addons/modal/sandbox.py` pins
  (`ghcr.io/selkies-project/selkies/base@sha256:5e9d022a...`) answers 404 on
  ghcr now; the newest release there is `2.2.1-ubuntu26.04`. Every session
  image builds today only because Modal has the base cached, so a build that
  has to pull it again (a two-stage Dockerfile did, and failed with "manifest
  unknown") fails. Moving the pin to a published release changes every app's
  image, the Nuke copy among them (about 50 minutes to rebuild), so it is its
  own change, with every app checked and the team's Nuke image built before it
  reaches main.

An Unreal start on a tier without a GPU is refused (`requires_gpu` in the
catalog), and the Environment panel marks such a tier "needs a GPU".

The agent answers questions about a project's assets from its repository
before any engine runs: `unreal_assets` (`lathe/control/unreal.py`) reads the
`.uproject` (the engine it needs, its plugins), lists `Content/` and each
plugin's `Content/` through the Git Trees API, and classifies each asset by its
name's prefix under Epic's naming conventions and its folder, saying that the
exact classes come from the editor's Asset Registry. The `unreal` skill
(`lathe/skills/unreal`), which Games, Architecture, and Experiences projects
load, has it answer that way and leave the team's repository as it is: it
writes only when asked, only to its own branch.
