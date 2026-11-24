# Selkies on Modal

Run Blender on a cloud GPU and work in it from a browser: a
[Modal](https://modal.com) Sandbox runs the Selkies
[base container](../../docs/components/base-image.md) with Blender layered on
it, and one command hands back the link.

```bash
addons/modal/selkies-modal up
```

```text
selkies-modal: image im-... ready after 1 s
selkies-modal: blender is sb-... on T4; waiting for Selkies
selkies-modal: Selkies listens after 4 s; the session ends after 10 min unused, or 8 h in all
https://....w.modal.host/?_modal_connect_token=...#token=...
```

The first `up` or `build` builds the image, which takes a few minutes; Modal
keeps it, and a session then starts in seconds.

`selkies-modal` installs the Modal client it is written against into a virtual
environment of its own the first time it runs, so it needs only Python 3. The
client finds its token the way it does anywhere: `MODAL_TOKEN_ID` and
`MODAL_TOKEN_SECRET`, or the file `addons/modal/selkies-modal modal token new`
writes after you approve it in a browser.

| Command | What it does |
| --- | --- |
| `up` | Starts the session, or returns the one already running under that name, and prints its link |
| `url` | Prints a new link to a running session, or with `--view unreal` to an Unreal session's Unreal view |
| `exec -- <command>` | Runs a command in the session's environment: on its display, with its GPU |
| `blender` | Runs the Python on standard input inside the session's Blender, the one the page shows |
| `filmcraft` | Sends the JSON requests on standard input, one per line, to a FilmCraft session's control channel and prints each reply |
| `ls` | Lists the running sessions |
| `down` | Stops a session, with the scene Blender has open kept for the next one |
| `drive-login` | Opens Google's sign-in on a Nuke session's screen and keeps the Drive access it grants as a Modal Secret, which `up --secret` hands to a session as rclone's `gdrive:` |
| `build` | Builds the image without starting a session |

Every command but `ls` and `build` takes `--name` (`blender` unless given), so
several sessions run side by side under names of their own.

```bash
echo 'bpy.ops.mesh.primitive_monkey_add()' | addons/modal/selkies-modal blender
```

The code runs as if from the 3D viewport, so operators work as they do there,
and what it prints comes back; an exception comes back as its traceback with a
status of 1.

## The link

The link carries two credentials, and a session takes both:

- `_modal_connect_token`, in the query, is Modal's: its proxy admits no request
  to the Sandbox without it, and answers the first one with a cookie that
  carries the page's later requests and its WebSocket.
- `#token=`, in the fragment, is the Selkies session token of
  [secure mode](../../docs/secure-mode.md). A browser sends a fragment to no
  server, and the client presents the token on the stream's socket.

Whoever holds the link controls the session, so share it as you would a
password. Neither token is stored outside the Sandbox: `url` asks Modal for a
new connect token and reads the session token back out of the Sandbox, which
takes the Modal credentials that started it.

## What a session costs

Modal bills a Sandbox by the second for as long as it runs, so the session
stops itself rather than wait to be stopped:

- **Unused for ten minutes** (`--idle-minutes`), it ends. Use is keyboard or
  pointer input from any page, or a command run through `exec`, for as long as
  that command runs. An open tab nobody touches is not use, and neither is a
  link nobody opened. `--idle-minutes 0` turns this off, for a render left to
  run with the page closed.
- **After eight hours** (`--lifetime-hours`, 24 at most) it ends whatever it is
  doing.
- **`up` twice** returns the session that is running instead of starting a
  second.

`--gpu` picks the GPU (`T4` unless given; `L4` and `A10` are the next steps
up, and any type Modal lists works). Modal starts a GPU only for an account
with a payment method. `--gpu none` runs the session without one, rendering
and encoding in software. `--cpu` and `--memory` are what the session
reserves, 2 cores and 4096 MiB unless given, and it uses more as Blender needs
it.

## Files

`/home/ubuntu/workspace` is the Modal Volume `selkies-workspace`, which
outlives every Sandbox: Blender starts in it, and what is saved there is there
in the next session. A file the page uploads lands there too, and the page's
file list and downloads are of it. The rest of the filesystem is the image's
and is gone when the session ends.

Blender's own state is in the workspace too, under `.blender`: its
preferences, add-ons, and extensions, and its auto-saves, which File > Recover
> Auto Save lists. A session that ends with Blender open, by the idle timeout
or `down`, has Blender quit first and keeps the scene it had open; the next
session's Blender opens that scene again as Blender's own recovery does, an
unsaved scene still unsaved and a saved file under its own path with the
changes that were not saved. A Sandbox that is killed outright, at its
lifetime or from Modal's dashboard, keeps only the last auto-save.

## Nuke

`--app nuke` starts a session for Foundry's Nuke instead. Foundry hands Nuke
out behind a login and a license its user accepts, so the image does not carry
it; the session installs it into the workspace once, at the user's word:

```bash
addons/modal/selkies-modal up --app nuke --name nuke --workspace team/nuke --gpu T4 --memory 16384
```

1. A workspace with no Nuke opens Firefox on Foundry's download page, with
   instructions on top. The user signs in and downloads Nuke for Linux (the
   `.tgz`), which saves into the workspace's `Downloads`; or they upload that
   file through the page's Files panel. A transfer still arriving counts as
   use, so the idle timeout does not end the session in the middle of it.
2. Once it has arrived, a window asks whether to install it, naming Foundry's
   license. Only on "Accept and install" does Foundry's installer run, into
   the workspace (`.apps/nuke`); the archive is then removed.
3. Every later session on that workspace opens Nuke directly. Nuke's settings
   (`~/.nuke`) and Foundry's sign-in (`~/.local/share/Foundry`,
   `~/FoundryLicensing`) are kept in the workspace too, and a script that was
   never saved is auto-saved there (`.nuke-autosave`).

A Nuke session is a desktop: a taskbar keeps Nuke, Firefox, and the setup's
windows in reach however they are minimized, and Nuke is in the start menu to
open again once closed.

Once a workspace has Nuke, `up` copies it into the session image (`/opt/nuke`)
and the session opens that copy: from the Volume, Nuke 17.1 took over seven
minutes to open on a new machine, and from the image 19 s. The copy is made
once per Nuke version, which took 50 minutes for its 15 GB, and later starts
reuse it.

Without its window, `nuke-run` runs Nuke with the interactive license, which a
login license for one person carries where it has no render license, and
`selkies-modal-job` runs a long command in the background, counting as use of
the session while it runs (`lathe/hermes/gpu-studio/SKILL.md` has the
commands).

`--workspace` keeps a session's files in one directory of the Volume, so a
team's Nuke and its scripts are apart from everything else there.

## FilmCraft

`--app filmcraft` starts a session for
[FilmCraft](https://github.com/storytold/filmcraft), the open-source video
editor, which an agent can drive through its command channel while a person
works in the same window:

```bash
addons/modal/selkies-modal up --app filmcraft --name film --gpu none --env SELKIES_MODAL_PROJECT=projects/trailer
```

The image installs the Debian package of FilmCraft's GitHub release, checked
against the hash the release's `SHA256SUMS.txt` lists (`FILMCRAFT_VERSION` and
`FILMCRAFT_SHA256` in `sandbox.py`; updating is a bump of both). FilmCraft
opens maximized, on a project of the session's project folder:

- The folder is `SELKIES_MODAL_PROJECT`, a path relative to the workspace,
  else `projects/default`. FilmCraft opens the newest `.fcproj` there, and in
  a folder with none creates `project.fcproj`, so Save, auto-save, and the
  agent's `file.save` all write where the next session looks. Media and
  exports go in the same folder, where every engine of the project reads them.
- Unsaved changes outlive the session. FilmCraft journals them within about a
  second of each edit into `.filmcraft` in the project folder (its data folder:
  preferences, logs, recovery), and the next session's FilmCraft restores them,
  still unsaved. The folder is the project's own, so one project's changes are
  never restored into another.

### Its command channel

Every menu item, button, and drag in FilmCraft is one of its 700-odd commands,
which its control channel runs exactly as the window does
([FilmCraft's protocol](https://github.com/storytold/filmcraft/blob/main/docs/control-protocol.md)).
The channel listens on the Sandbox's loopback only (port 9876), and FilmCraft
refuses any request without the session's own token, which `up` makes with the
session's other two and nothing outside the Sandbox holds. Requests therefore
go from inside the Sandbox: `filmcraft` sends JSON requests, one per line, and
prints each reply.

```bash
addons/modal/selkies-modal filmcraft --name film <<'EOF'
{"method": "engine.execute", "params": {"command": "file.import", "params": {"paths": ["/home/ubuntu/workspace/projects/trailer/media/shot01.mp4"]}}}
{"method": "engine.execute", "params": {"command": "file.newSequenceFromClip", "params": {"items": [1]}}}
{"method": "engine.execute", "params": {"command": "file.exportMedia", "params": {"path": "/home/ubuntu/workspace/projects/trailer/exports/cut1.mp4", "format": "h264", "hardwareEncoding": "auto"}}}
{"method": "engine.execute", "params": {"command": "jobs.list"}}
EOF
```

```text
{"id":null,"ok":true,"result":{"errors":[],"items":[1]}}
{"id":null,"ok":true,"result":{"clips":[6,7],"sequence":4}}
{"id":null,"ok":true,"result":{"cancel":"jobs.cancel","job":1,"path":"...","poll":"jobs.list","warnings":[]}}
...
```

A refused request comes back as `{"ok": false, "error": "..."}` with
FilmCraft's reason, and the status is then 1. The first request waits for
FilmCraft to be ready (`--wait`, 60 s unless given). From Python, the control
plane's way in, `filmcraft_call(sandbox, method, params, timeout)` sends one
request and returns its result, raising `RuntimeError` with FilmCraft's
message. FilmCraft answers a request within 60 s or gives up on it, so an
export is started without `wait` and followed with `jobs.list` until its job
is `finished`; `engine.commands` lists every command with its parameters.

### Graphics and speed

A Sandbox has no `/dev/dri`, so nothing presents into the session's display
through a GPU: the window draws through Mesa's Vulkan in software (lavapipe)
on every machine (`WGPU_BACKEND=vulkan`), and FilmCraft composites the
monitors on the CPU. NVIDIA's Vulkan cannot present into the display (wgpu
reports an error asking it and moves on to lavapipe; `vulkaninfo` crashes on
the NVIDIA driver Modal mounts), and OpenGL is Mesa's software rasterizer on
both. What a GPU machine adds is NVDEC to decode, NVENC to export H.264 when
the export asks for `hardwareEncoding: "auto"` (`perf.stats` counts the frames
it encoded under `export.hardware`), and the export renderer, which reaches the GPU
through Vulkan without a display; with a blur on every clip it loaded the T4
but was no faster than the CPU, the encoder being the slow part. Measured on
16 s and 64 s of 1080p30 H.264 media, from inside the Sandbox:

| | `--gpu none` | `--gpu T4` |
| --- | --- | --- |
| `up` until Selkies listens | 4 to 6 s | 10 to 13 s |
| A request that needs a UI frame (`ui.inspect`) | 20 ms | 28 ms |
| Seek to the new picture in the Program monitor, median (slowest of 10) | 68 ms (259 ms) | 107 ms (233 ms) |
| 6 s of playback at the monitor's 1/2 resolution | 181 frames, none dropped | 170 frames, none dropped |
| Export of 64 s to H.264 MP4 | 22.9 s, FilmCraft's software encoder | 16.9 s with NVENC; 34.6 s with the software encoder |

Editing is as responsive without a GPU as with one, so `--gpu none` serves
cutting, and a T4 pays for itself on long exports.

## PhotoCraft

`--app photocraft` starts a session for
[PhotoCraft](https://github.com/storytold/photocraft), the same team's photo
editor, installed the same way from its release (`PHOTOCRAFT_VERSION`,
`PHOTOCRAFT_SHA256`) and opened in the same project folder, so it reads and
writes the files a FilmCraft session of that project does:

```bash
addons/modal/selkies-modal up --app photocraft --name poster --gpu none --env SELKIES_MODAL_PROJECT=projects/trailer
```

Its settings and the recovery copies of unsaved documents are in `.photocraft`
in the project folder. A project's first PhotoCraft session settles its
rendering on the CPU (PhotoCraft's CPU compatibility mode): the window has no
hardware adapter in a Sandbox, and PhotoCraft otherwise says so in a notice at
every start. Its control channel listens on the Sandbox's loopback (port 7878)
for the session's own token, and reads and writes the project folder alone. A
connection authenticates first, `{"method": "auth", "params": {"token": ...}}`
from inside the Sandbox, where `PHOTOCRAFT_CONTROL_TOKEN` holds it; the
launcher has no verb for it yet.

## Unreal

`--app unreal` starts the desktop an Unreal engine works on, for a studio whose
game lives in a GitHub repository. Epic hands the Linux editor only to people
whose GitHub account is linked to Epic, so the image `up` builds is that desktop
without the editor; the editor is in `unreal_image(registry_secret, version)`,
which pulls it with the user's own credential ([`lathe/UNREAL.md`](../../lathe/UNREAL.md)).

```bash
addons/modal/selkies-modal up --app unreal --name ue --gpu L4 --env SELKIES_MODAL_PROJECT=projects/capyverse
```

`up` prints the Unreal view's link beside the desktop's; `url --view unreal`
prints a new one.

### The desktop

A developer starts the way they do on their own machine with GitHub Desktop:

1. The session opens on the GitHub client, with one line over it: sign in to
   GitHub, then clone the game here. The line is left out once the clone folder
   holds an Unreal project.
2. Sign in opens GitHub in Firefox and comes back to the client by itself
   (Firefox hands GitHub's `x-github-desktop-auth` link to it without asking).
3. File › Clone repository offers the clone folder: the project folder
   (`SELKIES_MODAL_PROJECT`) when the session has one, else `projects` in the
   workspace. Git LFS is installed for every repository, so the assets arrive
   with the clone.

The sign-in, the client's settings and list of repositories, and Git's name
and address are kept in the workspace (`SELKIES_MODAL_PERSIST`), so later
sessions open on the repository with nobody signing in again. The sign-in is in
GNOME's keyring, which has no login to unlock it here and is unlocked with a
fixed password: it is as private as the workspace and no more
(`unreal/github.sh`).

The client is [Desktop Plus](https://github.com/desktop-plus/desktop-plus),
a fork of GitHub Desktop that follows it release by release (3.6 now, the
version a studio runs on Windows) and publishes Linux packages
(`DESKTOP_PLUS_VERSION` and `DESKTOP_PLUS_SHA256` in `sandbox.py`). The older
Linux fork, shiftkey/desktop, installs and opens here too, but its last release
is 3.4.13 of February 2025, with the Electron of then holding the team's token
and open sign-in failures on Ubuntu (`unreal/install.sh`). Four things in its
bundled code are changed for the session (`unreal/desktop-plus.py`): its clone
dialog offers the session's folder, a repository named on its command line is
added without its Add dialog, it asks to initialize Git LFS only for a
repository whose hooks do not run LFS yet, and a session given a repository
opens on it rather than on the client's welcome. Each change is found by the
shape of the code it changes, which the build checks for, so a new version
that is not that shape fails the build rather than doing something else.

Firefox, Blender, and the client are on the desktop and in the quick launch
beside the start button. Blender is the blender app's, started in the project
folder with the Send to Unreal add-on enabled (the sidebar's Unreal tab;
[`unreal/send_to_unreal.py`](unreal/send_to_unreal.py)), and the launcher's
`blender` verb runs Python in it as in a Blender session.

### The team's repository, cloned at start

A project linked to a GitHub repository needs none of the steps above: the
control plane starts its session with the repository and a token for it in a
Modal Secret of that start, and the session clones it by itself.

```python
start_session(..., application="unreal", secrets=[modal.Secret.from_dict({
    "LATHE_GIT_REPO": "studio/capyverse", "LATHE_GIT_BRANCH": "main",
    "LATHE_GIT_TOKEN": token,  # a GitHub App user token for that repository, 8 hours
    "LATHE_GIT_NAME": "Dev Eloper", "LATHE_GIT_EMAIL": "dev@example.com",
})])
```

- **The clone.** As the desktop comes up, `selkies-modal-unreal-clone`
  ([`unreal/clone.py`](unreal/clone.py)) clones the branch into the clone folder
  (`<project folder>/<name>`) in the background, Git LFS's files included, with
  a progress line over the client. A folder that already holds the clone, from
  an earlier session on the workspace, is fetched, and fast-forwarded only when
  it is on that branch with no tracked file changed: local changes, local
  commits, and another branch are left as they are, and the status says so
  ("has local changes, not updated"). The commits carry `LATHE_GIT_NAME` and
  `LATHE_GIT_EMAIL`. The clone counts as use of the session while it runs.
- **The client.** When the clone is there the client opens it, added to its
  list with no question and no "Initialize Git LFS" (Git LFS is installed
  system-wide and the clone has its hooks), and with no welcome to sign in
  through. Where the clone fails, a line over the client says why and to clone
  by hand.
- **How far it is.** `clone_status(sandbox)` returns
  `{"state": "cloning" | "done" | "failed", "path": ..., "detail": ...}`,
  `detail` being one line: Git's progress, then Git LFS's ("fetching the Git LFS
  files: 49 of 109"), then what happened ("cloned studio/capyverse at main
  (13622e3); 109 Git LFS files fetched", "has local changes, not updated
  (origin/main fetched)", or GitHub's refusal in words). `path` is null until
  the clone starts. Asking does not count as use of the session.
- **The token.** It is in no remote URL, `.git/config`, log, or status, and no
  file of the workspace keeps it. The session's Git reaches it through a
  credential helper that reads it from the environment
  ([`unreal/git-credential.sh`](unreal/git-credential.sh)), given to the
  clone's commands alone with every other helper cleared, and asked only when
  GitHub refuses without it, so a public repository is cloned without sending
  it. The client cannot use such a helper: it runs every Git with the helpers
  cleared and its own in their place, and its own answers github.com only from
  an account signed in to the client. So the client is given the token as an
  `Authorization` header for that repository's address alone, in its
  environment (`http.<url>.extraHeader` through `GIT_CONFIG_COUNT`;
  [`unreal/github.sh`](unreal/github.sh)), and fetches and pushes with it. The
  header goes with every request, so once the token expires, after eight hours,
  GitHub refuses that repository to the client for the rest of the session, a
  sign-in included; a session lives eight hours unless started for longer.
  The base image copies the whole session environment, the token with the
  session's own tokens, into `/tmp/runtime-ubuntu` (`container-env`,
  `selkies-session-env.json`), which goes with the Sandbox.

### Finding the project

`selkies-modal-unreal-projects` describes every `.uproject` in the workspace,
wherever the developer cloned it, as JSON; from Python,
`unreal_projects(sandbox)` returns the list for the control plane:

```json
[{
  "path": "/home/ubuntu/workspace/projects/UEProject_Elementus/ProjectElementus.uproject",
  "name": "ProjectElementus",
  "engine_association": "5.4", "engine_version": "5.4",
  "modules": [{"name": "ProjectElementus", "type": "Runtime", "loading_phase": "Default"}],
  "plugins": [
    {"name": "Swinging", "in_repository": true, "source_in_repository": true, "path": "Plugins/GameFeatures/CustomAbilities/Swinging/Swinging.uplugin", "marketplace": false},
    {"name": "FSR", "in_repository": false, "source_in_repository": false, "path": null, "marketplace": false}
  ],
  "repository": {
    "root": "/home/ubuntu/workspace/projects/UEProject_Elementus", "branch": "main",
    "remote": "https://github.com/lucoiso/UEProject_Elementus.git",
    "submodules": [{"path": "Plugins/UEElementusModules", "checked_out": false}],
    "lfs": {"uses_lfs": true, "files": 109, "fetched": 109, "not_fetched": 0}
  },
  "size_bytes": 247793152, "size": "247.8 MB"
}]
```

(Abridged: the project enables thirteen plugins.)

It skips hidden folders and the ones Unreal regenerates (`Intermediate`,
`Saved`, `DerivedDataCache`, `Binaries`); `unreal/projects.py` documents every
field, and `pytest addons/modal/unreal` tests it.

### The Unreal view

The session's second page is its own port, 8090 (`UNREAL_VIEW_PORT`), behind a
connect token of its own (`unreal_view_link(sandbox)`). Until an editor streams
there, it is a page saying Unreal is not open yet, to clone the project on the
Desktop and ask the agent to open it; the page reloads by itself once something
else answers on the port. The port belongs to an s6 service of the session, so
the Pixel Streaming player taking it over is a change of what that service
runs, and the link stays the same: `unreal/view/view.sh` has the plan for the
player and the TURN relay it carries the stream through.

### Opening a project

`selkies-modal-unreal-open PATH.uproject` opens a project in the editor, off
screen, streaming itself with Pixel Streaming 2's editor streaming, with Unreal
MCP and the Remote Control API on loopback, and the project's C++ built first
where it has any. It runs as the session job `unreal-editor`. Where the image
has no editor it opens nothing and says, with status 3, that the editor is not
installed in this machine yet and what the user does to get it; a machine
without a GPU (4), a project saved by a newer Unreal (5), and an editor that
ends as it starts (1) are refused the same way. `unreal/open.sh` has the command
line and where each flag comes from: none of it has run against an editor yet.

### Measured

On 2026-11-24, with the image cached unless said otherwise:

| | |
| --- | --- |
| First build of the desktop (`build --app unreal`) | 195 s |
| Rebuild after a change to its files | 25 s for a late file, 121 s for the Firefox policy, the earliest |
| `up --app unreal --gpu none` until Selkies listens | 4 s |
| `up --gpu T4` | 7 s from the container's start; Modal took 280 s more to find a T4 |
| `down` | 6 to 8 s |
| Clone of a UE 5.4 sample with `git`, LFS content left out | 7.4 s, 228 MB |
| `git lfs pull` of its 109 LFS files | 3.4 s, 187 MB |
| `unreal_projects`, two projects | 1.3 to 1.6 s; 19.5 s on a new machine, which reads the clones from the Volume for the first time |
| `unreal_image`'s recipe with a public image in place of Epic's | 199 s; 77 s after a script change, the engine layer taken from the cache |
| Clone at start of the UE sample (228 MB, then 109 LFS files of 187 MB) into an empty workspace, no GPU | `done` 12 to 22 s after Selkies listened (git 8 to 16 s, LFS 3 to 4 s); the client open on it 0.7 s after |
| A later start with the clone one commit behind, clean | fetched and fast-forwarded in 2.2 s |
| A later start with local changes | `done`, not updated, in 0.7 s; 150 s before the clone set `core.checkStat=minimal`, Git then reading the whole clone from the Volume on a new machine (`unreal/clone.py`) |
| A repository that does not exist | `failed` 0.7 s after the clone started |
| Rebuild after a change to the client's package script, or to the bundle changes | 220 s, or 95 to 130 s |

## The session

The image is the base container by digest with three additions: Blender's
release archive from blender.org, checked against the hash blender.org
publishes, `xprintidle` to read the display's idle counter, and this
directory's scripts. `BASE_IMAGE`, `BLENDER_VERSION`, and `BLENDER_SHA256` at
the top of `sandbox.py` choose what it is built from, as `FILMCRAFT_VERSION`,
`FILMCRAFT_SHA256`, `PHOTOCRAFT_VERSION`, and `PHOTOCRAFT_SHA256` do for
FilmCraft's and PhotoCraft's images, and a change to any of them builds a new
image on the next `up` or `build`.

The Selkies window manager runs Blender as the session's application,
maximized, and starts it again if it is quit. Every other
[setting](../../docs/settings.md) is the server's own and passes through
`--env`:

```bash
addons/modal/selkies-modal up --gpu L4 --env SELKIES_DESKTOP=true --env SELKIES_ENCODER=av1enc
```

`SELKIES_DESKTOP=true` starts the session on the desktop shell, with Blender in
a window of it. The transport is WebSockets, the one Modal's proxy carries;
WebRTC needs a UDP path that proxy does not offer, so Selkies' own WebRTC is
not offered here. A WebRTC stream an application sends, such as the Unreal
Editor's ([`lathe/UNREAL.md`](../../lathe/UNREAL.md)), leaves through a TURN
relay instead.

## A WebRTC stream

Modal's HTTPS proxy carries HTTP and WebSockets, not the UDP that WebRTC media
travels on, but a Sandbox can also expose raw TCP ports to the internet. A
session's WebRTC stream takes one of them to a TURN relay inside the Sandbox:
the browser is told to use that relay alone, over TCP, and the relay hands the
media on over UDP to the sender's host candidates, which are the Sandbox's own
addresses.

```text
browser --TCP--> r123.modal.host:41234 --(Modal)--> coturn, TCP 3478 --UDP--> the sender, in the same Sandbox
```

From Python, the launcher's interface for a service:

```python
image = with_turn(session_image("blender")).build(app)
sandbox = start_session(app, "unreal", ..., image=image, tcp_ports=(TURN_PORT,))
host, port = tcp_address(sandbox, TURN_PORT)
```

- `start_session(tcp_ports=...)` has Modal expose those ports as raw TCP
  (`unencrypted_ports`), and `tcp_address` returns the public host and port
  Modal gave one of them, which exist only once the Sandbox has started. From
  the command line, `up --tcp-port 3478` does the same and prints the address.
  Such a port takes connections from any address, with no connect token and no
  TLS, so what listens on it authenticates by itself.
- `with_turn(image)` adds the relay's configuration and two commands to a
  session image; coturn itself is the base image's. Nothing starts the relay on
  its own: the application whose stream needs it runs
  `selkies-modal-turnserver`, which listens on TCP port 3478
  (`SELKIES_MODAL_TURN_PORT`) and relays on UDP ports 49152 to 49183.
- `selkies-modal-turn-credentials HOST:PORT [--ttl SECONDS]`, run in the
  Sandbox, prints the entry of `RTCConfiguration.iceServers` a page uses:
  `turn:HOST:PORT?transport=tcp`, with a user name and password of the TURN
  REST scheme, minted from the session's secret (`SELKIES_MODAL_TURN_SECRET`,
  which `start_session` makes for every session and nothing outside the
  Sandbox keeps). The credential is valid for a day unless `--ttl` says
  otherwise, and has to outlast the page's connection, since the relay checks
  it again on every refresh.

The page sets `iceTransportPolicy: "relay"`; the sender needs no ICE server at
all. The relay is not open to other hosts: it takes no UDP and no TLS, relays
to the Sandbox's own IPv4 addresses and to nothing else (a peer outside is
refused with 403), and allows 8 allocations to a user name and 32 in all
(`webrtc/turnserver.conf`, `webrtc/turnserver.sh`).

Measured on 2026-11-24: a WebRTC sender in a CPU Sandbox (aiortc, a moving
1280x720 test pattern in VP8 at 30 fps, signalled over a connect token) beside
the relay, and headless Chromium 136 and Firefox 137 in a second Sandbox,
relay-only over the relay's TCP port. Every run connected on a relay candidate
over TCP paired with the sender's host candidate.

| | Browser in the Sandbox's region (us-east) | Browser across the continent (us-west) |
| --- | --- | --- |
| ICE connected, from the offer | 0.18 to 0.24 s | 0.49 to 0.54 s |
| First frame shown, from the offer | 0.33 to 0.39 s (Firefox 0.73 s) | 1.2 to 1.4 s |
| Frames received and decoded | 30.0 of 30 a second, none dropped | 30.0 of 30 a second, none dropped |
| Round trip of the candidate pair (Chromium), median | 15 to 17 ms | 66 to 97 ms |
| A frame's creation to the browser's frame callback, median | 61 to 72 ms (Firefox 44 ms) | 87 to 122 ms, ±38 ms of clock offset |
| Rates carried | 2.9, 6.0, and 12.0 Mbps | the same |

Nothing was lost up to 6 Mbps; at 12 Mbps 0.3 to 0.5% of packets were lost,
recovered by retransmission and in one run by a single key frame, with no frame
dropped. The loss is not at the
sender's sockets, whose UDP counters show no drop; where it happens between the
relay and the browser is not yet known. A browser that itself runs in a Sandbox,
as a test's does, needs Modal's VM runtime (`runtime="vm"`) for Chromium:
under gVisor, Chromium's list of network interfaces comes out empty (a netlink
socket bound to address-change groups fails with `EOPNOTSUPP`), so it gathers
no candidate at all, while Firefox works there.
