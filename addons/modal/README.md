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
| `soundcraft` | Sends the JSON requests on standard input, one per line, to a SoundCraft session's control channel and prints each reply |
| `cadcraft` | Sends the JSON requests on standard input, one per line, to a CADCraft session's control channel and prints each reply |
| `vectorcraft` | Sends the JSON requests on standard input, one per line, to a VectorCraft session's control channel and prints each reply |
| `lightcraft` | Sends the JSON requests on standard input, one per line, to a LightCraft session's control channel and prints each reply |
| `ls` | Lists the running sessions |
| `down` | Stops a session, with the scene Blender has open kept for the next one, and CADCraft's unsaved drawings saved |
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

### Between two running sessions

A session sees the Volume as it was when its Sandbox started. What it writes
is on the Volume within seconds (1.5 to 5 s, with or without a `sync`), and a
session started after that has it, but a session already running never sees
it: Modal cannot reload a Volume under an application that holds files open
on it (`Sandbox.reload_volumes` answers that open files prevent it), and a
session's application always does. `send` carries a file or a folder from one
running session into the other instead:

```bash
addons/modal/selkies-modal send --name score --to cut /home/ubuntu/workspace/projects/trailer/handoff/mix.wav
```

The bytes pass through the machine that runs the command, 8 MiB in hand at a
time, from a command of the sending session to a command of the receiving one
(`send_file` in `sandbox.py`); the file appears under its name only once all
of it arrived, as the session's user's, and a folder goes as a tar stream. A
second path names where it goes in the receiving session when that is not the
same path. Between two CPU sessions, from a machine outside Modal: 1 MB in
1.7 s, 100 MB in 5.6 s, 1 GB in 42.7 s (24 MB/s), each with the same SHA-256 on
both sides. What the receiving session got is in its own mount, so it reaches
the Volume from there too. A FilmCraft session running since before a
SoundCraft session bounced a WAV imported it once `send` had brought it.

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
the session while it runs (`moody/hermes/gpu-studio/SKILL.md` has the
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

### Coming back to the work

PhotoCraft has no project file that names its open documents, so a session
comes back to the last one's work by PhotoCraft's own two means
(`photocraft/autostart`):

- **Saved work.** PhotoCraft opens on the document at the top of the project
  folder that was saved last (`.pcraft`, `.psd`, or `.psb`).
- **Unsaved changes.** PhotoCraft's settings and the recovery copies it keeps
  of changed documents are in `.photocraft` in the project folder. A project's
  first session sets the recovery interval to one minute, the shortest
  PhotoCraft takes, where its own default is ten. PhotoCraft looks at that
  clock only as it draws a frame, and a window nobody touches draws none, so
  the session asks it for the list of open documents every 20 s, which has it
  draw one. At the next start PhotoCraft reopens each copy, changed and under
  the name and path it had, beside the saved document unless the copy is of
  that same file.

Stopped and started on a 7200 by 10800 pixel poster with eleven layers, a
session had the saved poster and an untitled document with unsaved changes
open again 8 s after Selkies listened. What `down` can lose is what changed in
the minute and a half before it; the idle timeout is longer than that, so a
session it ends loses nothing. A recovery copy is a folder of one small file
per tile (1,800 for that poster), which the Volume fetches on first read: the
session reads them together before PhotoCraft starts (4 s), where PhotoCraft
reading them one after another took three minutes.

### Driving it

PhotoCraft's control channel answers JSON requests, the same commands its
interface runs (1,009 of them in 0.23.1, `docs/control-protocol.md` in
PhotoCraft). It listens on the Sandbox's loopback only (port 7878), and serves
a connection only once it has authenticated. `photocraft` sends JSON requests,
one per line, from inside the Sandbox, and prints each reply; for each it
answers PhotoCraft's challenge, an HMAC over two nonces keyed with the
session's own token, which `up` makes with the session's others, so the token
never crosses the socket (`photocraft/control.sh`).

```bash
addons/modal/selkies-modal exec --name poster -- mkdir -p /home/ubuntu/workspace/projects/trailer/exports
addons/modal/selkies-modal photocraft --name poster <<'EOF'
{"method": "engine.execute", "params": {"command": "file.new", "params": {"width": 7200, "height": 10800, "resolution": 300, "name": "Poster", "background": "#0b0d1a"}}}
{"method": "app.open", "params": {"path": "handoff/filmcraft-to-photocraft/poster-frame-shot01.png"}}
{"method": "engine.execute", "params": {"command": "layer.copyToDocument", "params": {"document": 0, "center": true, "name": "Key art"}}}
{"method": "engine.execute", "params": {"command": "file.close", "params": {"document": 1}}}
{"method": "engine.execute", "params": {"command": "type.create", "params": {"x": 3600, "y": 8350, "text": "THE LONG DUSK", "align": "center", "font": "URW Gothic", "fontStyle": "Demi", "size": 132, "color": "#f6efe4"}}}
{"method": "app.save", "params": {"path": "exports/poster.psd"}}
EOF
```

```text
{"id":null,"ok":true,"result":{"document":0}}
{"id":null,"ok":true,"result":{"name":"poster-frame-shot01.png","path":"handoff/filmcraft-to-photocraft/poster-frame-shot01.png","warnings":[]}}
{"id":null,"ok":true,"result":{"document":0,"layers":[6],"offset":[2640,4860]}}
{"id":null,"ok":true,"result":null}
{"id":null,"ok":true,"result":{"bounds":[1538,7936,5654,8359],"layer":7}}
{"id":null,"ok":true,"result":{"path":"exports/poster.psd","warnings":[]}}
```

The image opens as a document of its own, so its layer is copied into the
poster and it is closed again. A refused request comes back as `{"ok": false, "error": "..."}` with
PhotoCraft's reason, and the status is then 1; the first request waits for
PhotoCraft to listen (`--wait`, 60 s unless given). From Python, the control
plane's way in, `photocraft_call(sandbox, method, params, timeout)` sends one
request and returns its result, raising `RuntimeError` with PhotoCraft's
message, as `filmcraft_call` does. What the channel reads and writes is the
project folder alone, through `app.open` and `app.save` with paths relative to
it; PhotoCraft refuses its own file commands there (`file.placeEmbedded`,
`file.saveACopy`), paths outside the folder, and a folder that does not exist
yet. PhotoCraft gives up on a reply after 60 s without undoing what it
started, so a long filter is started with `"wait": false` and followed with
`jobs.list`. `photocraft-cli`, in the image beside it, is the same engine
without a window (`photocraft-cli commands --json --filter blur`,
`photocraft-cli convert in.tif out.webp`).

### Graphics and speed

A Sandbox has no `/dev/dri`, so nothing presents into the session's display
through a GPU, a T4's included: the window is Mesa's software rasterizer, and
PhotoCraft then composites every document on the CPU whatever rendering mode
it is in (`render path: all documents: CPU (softwareAdapter)` in its log). A
project's first session therefore sets PhotoCraft's CPU compatibility mode,
which is that same path without the notice its automatic mode puts over the
window at every start. The five combinations of rendering mode (`cpu`,
`auto`, `gpu`) and window backend (OpenGL, or Vulkan with `WGPU_BACKEND`) ran
the same work within the spread between machines, and a T4 was no faster.
Measured from inside the Sandbox on the poster above, 7200 by 10800 pixels at
300 ppi with eleven layers:

| | 2 cores, 4 at most (Moody's `cpu` tier) | 18 cores |
| --- | --- | --- |
| A request that reads or sets a value (`layer.list`, `layer.setProps`) | 0.1 s | 0.1 s |
| Opening the saved poster (27 MB) | 1.9 s | 1.3 s |
| Free Transform of a 13056 by 7344 smart object | 7.4 s | 3.6 to 4.4 s |
| Gaussian Blur, radius 12, on a full-canvas layer | 2.0 s | 1.1 s |
| Unsharp Mask on a full-canvas layer | 3.0 s | 1.7 to 2.0 s |
| A brush stroke's frame: canvas, whole interface | 14 ms, 27 ms | 7 to 12 ms, 16 to 24 ms |
| Save as PNG, as layered PSD | 3.0 s, 5.7 s | 1.4 to 1.6 s, 3.1 to 3.4 s |

The whole poster (a film frame as a masked smart object, two adjustment
layers, a grain layer, four type layers, and PSD, PNG, JPEG, and `.pcraft`
saves) took 67 s as 34 calls of `photocraft_call` on the smaller machine, each
call costing 0.3 s to reach the Sandbox. More cores make the heavy steps
faster and a GPU does not, so `--gpu none` is the machine for PhotoCraft.

### Between sessions

A session sees the project folder as it was when the session started: a file
another session writes afterwards does not appear in it, and Modal cannot
reload the Volume under a running session while its application holds files
open there (`Sandbox.reload_volumes` answers that open files prevent it). A
file is on the Volume about 5 s after it was written (one of 368 MB as soon
as one of a few bytes), and a session started 4 s after an export did not
have it, while one started a minute later did. So work moves between two
applications by exporting in one and either carrying the file into the other
while it runs (`send`, under Files) or waiting until the file has reached the
Volume and starting the other: a frame FilmCraft exported
(`file.exportFrame`) opened as a poster's key art in a PhotoCraft session
started after it, and that poster, saved as a 2048 by 3072 PNG, loaded as a
texture in a Blender session started after that.

## CADCraft

`--app cadcraft` starts a session for
[CADCraft](https://github.com/storytold/cadcraft), the same team's open-source
2D drafting application (layers, dimensions, hatches, blocks, paper-space
sheets, constraints; DXF and DWG), which an agent drives through its command
channel while a person drafts in the same window:

```bash
addons/modal/selkies-modal up --app cadcraft --name plan --gpu none --env SELKIES_MODAL_PROJECT=projects/house
```

The image installs the Debian package of CADCraft's GitHub release, checked
against the hash the release's `SHA256SUMS.txt` lists (`CADCRAFT_VERSION` and
`CADCRAFT_SHA256` in `sandbox.py`; updating is a bump of both), as FilmCraft's
is. CADCraft opens maximized, on a drawing of the session's project folder
([`cadcraft/autostart`](cadcraft/autostart)):

- It opens the newest `.dxf` or `.dwg` in the folder, and in a folder with
  none a new `drawing.dxf`, metric (millimeters, the ISO-25 dimension style),
  so Save and the agent's `app.save` write where the next session looks.
  CADCraft also keeps an empty `Drawing1` tab beside it.
- Its settings folder (preferences, logs, plotters, autosaves) is `.cadcraft`
  in the project folder, so one project's autosaves are never offered in
  another.
- Work outlives the session. A session that ends by its idle timeout or
  `down` first saves every drawing with unsaved changes
  ([`cadcraft/keep.sh`](cadcraft/keep.sh), which `session.sh` runs): a drawing
  with a file is saved to it, the file as it was kept beside it as
  `<name>.bak`, and one never saved goes into the folder under its title
  (`Drawing2.dxf`). A session cut off with no chance to (the Sandbox's
  lifetime, a crash) leaves CADCraft's autosave, which the next session
  offers in its Drawing Recovery window and the `drawingrecovery` command
  lists; each start sets the autosave interval to one minute (`SAVETIME`),
  CADCraft's shortest. Measured: two drawings with unsaved changes, `down`
  (5 s), `up`, and both were there, the one that had been in front open; a
  circle drawn 75 s before the Sandbox was terminated outright came back from
  the autosave. CADCraft's window closes with the display at the end of a
  session, which it records as a crash report of under 1 kB in
  `.cadcraft/crash-reports`.

The control channel is CADCraft's JSON lines on the Sandbox's loopback (port
9878; [its protocol](https://github.com/storytold/cadcraft/blob/main/docs/control-protocol.md)).
CADCraft makes the channel's token itself each time it starts and writes it to
a file only the session's user reads, so the launcher holds none: the client
in the session ([`cadcraft/control.sh`](cadcraft/control.sh)) reads it for
each request.

```bash
addons/modal/selkies-modal cadcraft --name plan <<'EOF'
{"method": "engine.execute", "params": {"command": "rectang", "params": {"p1": [0, 0], "p2": [4600, 4000]}}}
{"method": "engine.execute", "params": {"command": "export", "params": {"path": "exports/plan.pdf"}}}
{"method": "drawing.inspect", "params": {"entities": false}}
EOF
```

Each reply is CADCraft's own line, `{"ok": true, "result": ...}` or `{"ok":
false, "error": ...}`, and the status is 1 when one was refused. From Python,
`cadcraft_call(sandbox, method, params, timeout)` sends one request and
returns its result, raising `RuntimeError` with CADCraft's message; the
control plane's `engine_call` finds it by that name. `engine.execute` runs any
of the 517 commands `engine.commands` lists, without opening a dialog.

It writes DXF, DWG, PDF, SVG, and PNG, and has no 3D: `export` refuses STL,
STEP, IGES, OBJ, and glTF. A drawing goes to Blender as its DXF, read there
with `ezdxf` (`moody/skills/cadcraft/references/handoff.md` has the recipe: a
4600 × 4000 mm room's walls arrived 4.6 × 4.0 × 2.7 m).

Two sessions on one workspace do not see each other's new files while both
run: a Sandbox sees the Volume as it was when it started (a file written 13 s
before a start was there, one written 1 s before was not, one written after
never appeared, and `reload_volumes` is refused while the session has files
open). A hand-off is therefore export, then `send` the file to the session
that reads it, or start that session after the export.

### Graphics and speed

The window draws through Mesa's Vulkan in software (`WGPU_BACKEND=vulkan`,
lavapipe), as FilmCraft's does, and a drawing is light work for it. Measured
with `--gpu none` on the default two reserved cores; a GPU session was not
measured, a Sandbox having no render node for it to draw through:

| | |
| --- | --- |
| `up` until Selkies listens, image cached | 4 to 7 s; CADCraft answers 0.4 to 0.7 s later |
| The image, built once | 71 s |
| A request through `cadcraft_call` | 0.29 s median, the Sandbox's exec around a request that takes 28 ms from inside |
| A frame of a dimensioned room plan (362 primitives) | 1.4 ms; 206 frames for 200 zooms |
| `ui.screenshot`; `ui.render` at 2400 × 1600 | 0.26 s; 0.49 s |
| A dimensioned plan, its A3 sheet, a part drawing, and 12 exports | 129 requests, 38 s |
| CADCraft idle | 1.3 % of a core, 486 MB |
| `cadcraft-cli perf`, 200,000 objects | display list 83 ms, DXF write 0.9 s, read 1.5 s |
## VectorCraft

`--app vectorcraft` starts a session for
[VectorCraft](https://github.com/storytold/vectorcraft), the same team's vector
illustration application, for logos, identities, icons, and patterns, which an
agent drives through its command channel while a person works in the same
window:

```bash
addons/modal/selkies-modal up --app vectorcraft --name mark --gpu none --env SELKIES_MODAL_PROJECT=projects/brand
```

The image installs the Debian package of VectorCraft's GitHub release, checked
against the hash the release's `SHA256SUMS.txt` lists (`VECTORCRAFT_VERSION` and
`VECTORCRAFT_SHA256` in `sandbox.py`; updating is a bump of both, and a run of
the VectorCraft skill's recipes, `moody/skills/vectorcraft`). VectorCraft opens
in the session's project folder, the one every engine of the project shares:

- Its data folder (preferences, logs, recovery copies, the fonts folder a
  project names) is `.vectorcraft` in the project folder, so it stays with the
  project and outlives the Sandbox.
- A start opens the newest `.vectorcraft` document of the folder. A folder with
  none starts on the welcome screen: a document's size and color mode are a
  design decision, not a default. VectorCraft answers its channel a second or
  more before that document is open, so requests are held until it is
  (`vectorcraft/control.sh`), and the first answer already lists what the
  project has.
- Unsaved changes outlive the session. VectorCraft keeps recovery copies of
  modified documents, by itself every two minutes; the session asks it for one
  every 10 s (`vectorcraft/resume.sh`), since nothing that ends a Sandbox quits
  the application. The next start restores them as modified documents named
  `<name> [Recovered]`, which stand in for the saved file they came from and
  have no file of their own until saved to one (`file.saveAs` with a `path`).
  Measured: an object added and left unsaved was in a recovery copy 4 s later,
  and was there, with the document's artboards, layers, and swatches, after
  `down` (4 s) and `up` (8 s) on the same workspace and project folder.

### Its command channel

Every menu item and tool of VectorCraft is one of its 1,430 commands, which its
control channel runs as the window does
([VectorCraft's protocol](https://github.com/storytold/vectorcraft/blob/main/docs/control-protocol.md)).
The channel listens on the Sandbox's loopback only (port 7979) and reads and
writes the project folder alone: a path outside it is refused, and a relative
path is read against it. `vectorcraft` sends JSON requests from inside the
Sandbox, one per line, and prints each reply:

```bash
addons/modal/selkies-modal vectorcraft --name mark <<'EOF'
{"method": "engine.execute", "params": {"command": "file.new", "params": {"name": "mark", "width": 512, "height": 512}}}
{"method": "engine.execute", "params": {"command": "shape.ellipse", "params": {"x": 96, "y": 96, "width": 320, "height": 320}}}
{"method": "engine.execute", "params": {"command": "paint.setFill", "params": {"color": "#14213d", "ids": [2]}}}
{"method": "engine.execute", "params": {"command": "file.saveAs", "params": {"path": "mark.vectorcraft"}}}
{"method": "engine.execute", "params": {"command": "document.export", "params": {"path": "mark.svg", "artboard": 0}}}
{"method": "engine.execute", "params": {"command": "document.export", "params": {"path": "/tmp/mark.svg"}}}
## LightCraft

`--app lightcraft` starts a session for
[LightCraft](https://github.com/storytold/lightcraft), the same team's
non-destructive photo developer, installed the same way from its release
(`LIGHTCRAFT_VERSION`, `LIGHTCRAFT_SHA256`) and opened on the same project
folder, so it develops the photographs a PhotoCraft session retouches and a
FilmCraft session cuts in:

```bash
addons/modal/selkies-modal up --app lightcraft --name lab --gpu none --env SELKIES_MODAL_PROJECT=projects/shoot
```

LightCraft never changes a photograph: an edit is a record in its library, and
the library is in the project folder, so a person's work is there in the next
session with nothing to save.

- `lightcraft-library` holds the catalog (every photo's develop settings,
  history, versions, masks, ratings, and albums), the user's develop presets
  and saved export presets, and the preview cache. LightCraft appends each
  change to the catalog's journal and syncs it before it answers, so a session
  that ends by the idle timeout or `down` loses nothing. A new library starts
  empty, without LightCraft's demo photos.
- `.lightcraft` is its settings folder: the interface's state, the lens
  database once it is downloaded (LightCraft offers it at a project's first
  start), and the logs.
- Photos are imported in place, from wherever they are in the project folder,
  and stay there for the project's other engines.

One LightCraft session per project folder at a time: a library's lock file
does not reach from one Sandbox to another, so a second session opens the same
library and the two overwrite each other's catalog.

### Its command channel

Every menu item, slider, and brush stroke in LightCraft is one of its 600-odd
commands, which its control channel runs as the window does
([LightCraft's protocol](https://github.com/storytold/lightcraft/blob/main/docs/control-protocol.md)).
`lightcraft` sends JSON requests, one per line, and prints each reply:

```bash
addons/modal/selkies-modal lightcraft --name lab <<'EOF'
{"method": "engine.execute", "params": {"command": "library.import", "params": {"paths": ["/home/ubuntu/workspace/projects/shoot/photos"], "mode": "add"}}}
{"method": "engine.execute", "params": {"command": "develop.set", "params": {"values": {"light.exposure": 0.15, "light.highlights": -55}, "ids": [1]}}}
{"method": "engine.execute", "params": {"command": "app.export", "params": {"ids": [1], "dir": "/home/ubuntu/workspace/projects/shoot/exports/web", "format": "jpeg", "longEdge": 2048, "colorSpace": "srgb"}}}
EOF
```

```text
{"id":null,"ok":true,"result":{"index":0,"previewMode":"default"}}
{"id":null,"ok":true,"result":{"id":2}}
{"id":null,"ok":true,"result":{"objects":1}}
{"id":null,"ok":true,"result":{"background":true,"format":"vectorcraft","path":"mark.vectorcraft","status":"Saving mark.vectorcraft…","warnings":[]}}
{"id":null,"ok":true,"result":{"bytes":346,"format":"svg","path":"mark.svg","warnings":[]}}
{"error":"automation path rejected: outside the write root .../projects/brand: /tmp/mark.svg","id":null,"ok":false}
```

A refused request comes back as `{"ok": false, "error": "..."}` with
VectorCraft's reason, and the status is then 1. The first request waits for
VectorCraft to listen (`--wait`, 60 s unless given), which it does about a
second after Selkies. From Python, the control plane's way in,
`vectorcraft_call(sandbox, method, params, timeout)` sends one request and
returns its result, raising `RuntimeError` with VectorCraft's message; it is
what Moody's `engine_call` reaches for a VectorCraft engine. Lengths are points,
from the top left corner of the first artboard, with y down.

The release pinned here, 0.24.1, has no sign-in on its channel (its protocol
says so: "the port has no authentication"), so what guards it is where it
listens: the loopback of a Sandbox that is one person's. VectorCraft's main
branch signs each connection in with a token (an `auth` request first), and the
session is ready for the release that brings it: `up` makes
`VECTORCRAFT_CONTROL_TOKEN` with the session's other tokens, and the client
(`vectorcraft/control.sh`) sends the sign-in on every connection, which 0.24.1
answers as an unknown method and the client skips.

### Graphics and speed

No graphics variable is set. VectorCraft rasterizes its canvas on the CPU and
only composites the window through wgpu, and it lists the adapters that can
present into the display itself: on a T4 its log lists the Tesla T4 as
"can't show the window" and it draws on `llvmpipe (Vulkan, Cpu)`, the adapter
it also takes with no GPU. A GPU adds nothing to it, so `--gpu none`
is the machine. Measured on Moody's Starter shape (2 cores reserved, 4 at
most, 4 GiB), on a three-artboard identity document of 99 objects:

| | `--gpu none` |
| --- | --- |
| `up` until Selkies listens, then until VectorCraft answers | 4 to 5 s, then 1 s |
| One command through `vectorcraft_call`, median of 77 | 0.31 s, nearly all of it Modal's round trip |
| A request from inside the Sandbox (`ui.inspect`, which waits for a frame) | 108 ms with the client's start; the frame itself 2 ms |
| The canvas redrawn while an object is dragged (62 pointer events) | 2.6 ms a frame |
| The whole document at 2880x1800 (`vectorcraft-cli bench`) | 14 ms a frame |
| Export: SVG, a three-page PDF, a 2000 px PNG, seven icon files | 0.3 s, 0.3 s, 0.5 s, 0.5 s |
{"id":null,"ok":true,"result":{"duplicates":[],"failed":[],"imported":[1,2,3,4,5,6,7,8,9],"scanned":9,"sidecars":5}}
{"id":null,"ok":true,"result":null}
{"id":null,"ok":true,"result":{"files":[{"bytes":1455492,"height":1363,"path":"...","sidecars":[],"width":2048}]}}
```

A refused request comes back as `{"ok": false, "error": "..."}` with
LightCraft's reason, and the status is then 1. From Python,
`lightcraft_call(sandbox, method, params, timeout)` sends one request and
returns its result, raising `RuntimeError` with LightCraft's message.
`engine.commands` lists every command with its parameters. LightCraft answers
a request within 60 s or gives up on it, so a long export is started with
`background: true` and followed in `ui.inspect`'s `export`.

LightCraft's channel takes no token, unlike FilmCraft's and PhotoCraft's: it
listens on the Sandbox's loopback (port 7980), which nothing outside the
Sandbox reaches, and any process inside it can send it commands. LightCraft
listens a few seconds before its window draws its first frame and refuses what
arrives in between; the client sends such a request again until `--wait` is
over (60 s unless given).

The control channel has no command that returns a histogram, so the image
carries a reader for rendered files: `selkies-modal-histogram <picture>
[--region x0,y0,x1,y1]` prints a JPEG's, PNG's, or TIFF's size, pixel format,
embedded color profile, tonal percentiles, clipping, and channel means as
JSON, which is how an agent measures an edit (`ui.render` writes the picture)
and checks an export.

### Graphics and speed

A Sandbox has no `/dev/dri`, so LightCraft's window draws through Mesa's Vulkan
in software on every machine (`WGPU_BACKEND=vulkan`, as FilmCraft's does).
Without a GPU LightCraft finds only that software adapter and develops on the
CPU, which is its own choice ("the CPU pipeline is faster"); with one, its
develop pipeline runs on the GPU through Vulkan and the pictures come back to
the software window as pixels. OpenGL was tried for the window
(`LIGHTCRAFT_GPU_BACKEND=gl`): on the machine without a GPU its frames were no
quicker than the spread between runs, and on a T4 LightCraft's kernels fail to
build on NVIDIA's OpenGL. Measured from inside the Sandbox, on machines shaped
as a service starts them (the CPU request and twice it as the limit), with
raws of 24 to 33 megapixels:

| | 2 CPU, 4 GiB, no GPU | 4 CPU, 16 GiB, T4 |
| --- | --- | --- |
| `up` until the first request is answered | 6 s | not measured |
| A request that needs a frame (`ui.inspect`), median | 38 to 43 ms | 31 ms |
| A slider change until the finished picture in the window, median | 330 to 380 ms | 170 to 190 ms |
| Stepping to another photo until its finished picture, median | 1.3 to 1.4 s | 0.6 to 0.7 s |
| Export of one 33-megapixel raw: JPEG at 2048 px, JPEG at full size, 16-bit TIFF at full size | 2.3 to 2.6 s, 5.0 to 5.2 s, 7.0 to 7.3 s | 2.4 s, 3.0 s, 7.5 s |
| Export of 9 photos to JPEG at 2048 px | 11.6 to 12.9 s | 11.2 to 11.5 s |

The machine without a GPU serves developing and exporting; a T4 with its four
cores makes the sliders about twice as quick and all but the full-size JPEG
export no faster. The same four cores on a machine without a GPU were quicker
than either (a slider in 115 ms, the batch in 4.8 s).

## Unreal

`--app unreal` starts the desktop an Unreal engine works on, for a studio whose
game lives in a GitHub repository. Epic hands the Linux editor only to people
whose GitHub account is linked to Epic, so the image `up` builds is that desktop
without the editor; the editor is in `unreal_image(registry_secret, version)`,
which pulls it with the user's own credential ([`moody/UNREAL.md`](../../moody/UNREAL.md)).

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
    "MOODY_GIT_REPO": "studio/capyverse", "MOODY_GIT_BRANCH": "main",
    "MOODY_GIT_TOKEN": token,  # a GitHub App user token for that repository, 8 hours
    "MOODY_GIT_NAME": "Dev Eloper", "MOODY_GIT_EMAIL": "dev@example.com",
})])
```

- **The clone.** As the desktop comes up, `selkies-modal-unreal-clone`
  ([`unreal/clone.py`](unreal/clone.py)) clones the branch into the clone folder
  (`<project folder>/<name>`) in the background, Git LFS's files included, with
  a progress line over the client. A folder that already holds the clone, from
  an earlier session on the workspace, is fetched, and fast-forwarded only when
  it is on that branch with no tracked file changed: local changes, local
  commits, and another branch are left as they are, and the status says so
  ("has local changes, not updated"). The commits carry `MOODY_GIT_NAME` and
  `MOODY_GIT_EMAIL`. The clone counts as use of the session while it runs.
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

## SoundCraft

`--app soundcraft` starts a session for
[SoundCraft](https://github.com/storytold/soundcraft), the same team's digital
audio workstation, installed the same way from its release
(`SOUNDCRAFT_VERSION`, `SOUNDCRAFT_SHA256`). It needs no GPU:

```bash
addons/modal/selkies-modal up --app soundcraft --name song --gpu none --env SELKIES_MODAL_PROJECT=projects/trailer
```

- SoundCraft opens the newest `.scraft` session in the project folder, and in a
  folder with none a new `project.scraft`, which SoundCraft's command-line tool
  writes before the window opens. A session keeps the audio it imports in
  `Audio Files` beside its file and its earlier saves in `Backups`.
- Unsaved changes outlive the session. SoundCraft autosaves them within seconds
  of each edit into `.soundcraft` in the project folder (its settings folder:
  preferences, presets, logs, autosaves), and offers them at the next start in
  a "Recover Unsaved Work" question it has no flag to answer. The session's
  autostart answers it, pressing Recover through the control channel once the
  window has its size, so the next session opens with the changes, unsaved, as
  FilmCraft's does. Checked across `down` and `up` with the files dated three
  days back: a track, a fader, and a marker made without saving were there, the
  session marked changed. Where the press does not land, the question stays on
  screen for the person.
- Sound reaches the page. SoundCraft plays to the default ALSA device, which
  the base container's PipeWire carries to the sink Selkies captures. Checked
  with a stand-in page on the session's WebSocket: no audio frames while the
  transport is stopped, 500 Opus frames in 5 s while it plays, and the sink's
  monitor at the loudness of the bounce of the same session (-27.9 LUFS). A
  bounce renders offline and needs no sound device at all.

### Its command channel

Every menu item and button in SoundCraft is one of its 483 commands, and the
running application takes them as JSON on a control channel
([SoundCraft's protocol](https://github.com/storytold/soundcraft/blob/main/docs/control-protocol.md)).
The channel listens on the Sandbox's loopback only (port 7801). SoundCraft's
channel has no token, unlike FilmCraft's and PhotoCraft's: it answers whatever
reaches that address, which is every process of the Sandbox and nothing
outside it. `soundcraft` sends JSON requests, one per line, from inside the
Sandbox:

```bash
addons/modal/selkies-modal soundcraft --name song <<'EOF'
{"method": "engine.execute", "params": {"command": "track.new", "params": {"kind": "instrument", "name": "Keys", "instrument": "subtractive_synth"}}}
{"method": "engine.execute", "params": {"command": "file.bounce_mix", "params": {"path": "mix.wav"}}}
{"method": "session.inspect"}
EOF
```

Each reply is printed on a line of its own; a refusal carries SoundCraft's
reason, and the status is then 1. The first request waits for SoundCraft to
listen (`--wait`, 60 s unless given). From Python,
`soundcraft_call(sandbox, method, params, timeout)` sends one request and
returns its result, raising `RuntimeError` with SoundCraft's message.
SoundCraft answers a request within 90 s or gives up on it, and a bounce
renders within its request.

### Measured

On Sandboxes without a GPU, with the 2 CPUs and 4 GiB `up` reserves:

| | |
| --- | --- |
| `up`, image cached | 7-34 s to the link; Selkies listens 4-6 s after the Sandbox starts |
| First `session.inspect` after `up` | 0.6 s |
| One command through `soundcraft_call` | 0.24 s |
| 170 notes as one `soundcraft` run | 4.6 s |
| Bounce of a 26 s mix (3 instruments, an audio track, 8 inserts, a reverb return) to 24-bit WAV | 1.1 s |
| Bounce of the same session looped to 3 min 49 s | 8.0 s; its four stems 31 s |

The 26 s export measured stereo, 48 kHz, 24-bit, 25.86 s, -14.2 LUFS
integrated and -0.7 dBFS true peak with ffmpeg's EBU R 128 meter, against the
-14.17 LUFS SoundCraft reported for it.

### Several engines of one project

Engines of one project mount the same directory of the Volume, and each sees it
as it was when its Sandbox started. A FilmCraft session started beside a
running SoundCraft one listed the master and stems SoundCraft had written
minutes before. Files written after that do not cross between two running
Sandboxes, in either direction (not after a minute), and
`Sandbox.reload_volumes()` is refused while an application holds files open in
the folder, which each does. A session that is stopped and started again sees
them: 13 s after a write in the running SoundCraft session, a restarted
FilmCraft session listed the file and imported the WAV. Without a restart,
`send` carries the file across (Files, "Between two running sessions").

## Cut Room

`--app cutroom` starts a session with no application to click: a machine for
editing video by code. Its image holds FFmpeg (the base image's, with libass,
Rubber Band, and x264, each checked when the image is built), a Python
environment locked wheel by wheel (`cutroom/python.lock`: faster-whisper,
NumPy, OpenCV, Pedalboard, Pillow, yt-dlp), the Inter and Archivo Black fonts,
two Whisper speech models and a face detector already downloaded, and the
scripts of `cutroom/scripts`, each run as `cutroom NAME` from any directory:

```bash
addons/modal/selkies-modal up --app cutroom --name cuts --gpu none --env SELKIES_MODAL_PROJECT=projects/clips
addons/modal/selkies-modal exec --name cuts -- cutroom
addons/modal/selkies-modal exec --name cuts -- cutroom sheet footage/clip.mp4
addons/modal/selkies-modal exec --name cuts -- cutroom moments footage/clip.mp4
addons/modal/selkies-modal exec --name cuts -- cutroom cut jobs/clip-1a2b3c4d --pick 1 --hook "TEXT"
```

A script runs in the session's project folder, so the paths it takes are
relative to that folder and what it writes is where the project's other
engines look. `cutroom` alone lists the scripts, `cutroom NAME --help` prints
one's parameters, and `cutroom versions` prints what the image holds, each
part with where it came from and its checksum. The session's screen is a
terminal on the log of every `cutroom` command, since there is nothing else to
watch; the scripts read footage (contact sheets, scene cuts, a transcript with
word times, the moments worth cutting), cut vertical clips and horizontal
explainers with captions, titles, voices, and music, master a voice, mute
swearing, check a finished cut, and fit one to a size
(`moody/skills/cutroom` has every command as it was run).

The scripts are adapted from
[gtavi-claudecode](https://github.com/larvuz2/gtavi-claudecode) (MIT), whose
notice each adapted file carries. They call no paid service: a narration is
laid from sound files that already exist. A cut and its check take about six
and four times the clip's length on two cores, most of it two speech models
listening for swear words, so a long one is started with `selkies-modal-job`.
`pytest addons/modal/cutroom` runs the tests of the scripts' own logic.

## HyperFrames

`--app hyperframes` starts another session with no application to click:
[HyperFrames](https://github.com/heygen-com/hyperframes) (HeyGen's, Apache
2.0), in which a video is written as HTML, CSS, and animation, a headless
browser is stepped through its frames, and FFmpeg encodes them. Its image
holds Node.js and Chrome for Testing by version and checksum, the Cut Room's
fonts, the base image's FFmpeg, and the `hyperframes` command line with the
skills its release ships:

```bash
addons/modal/selkies-modal up --app hyperframes --name frames --gpu none --env SELKIES_MODAL_PROJECT=projects/film
addons/modal/selkies-modal exec --name frames -- hyperframes-release status
addons/modal/selkies-modal exec --name frames -- ls /opt/hyperframes/skills
addons/modal/selkies-modal exec --name frames -- bash -c 'cd "$(selkies-modal-project)" && hyperframes init film --non-interactive'
addons/modal/selkies-modal exec --name frames -- bash -c 'cd "$(selkies-modal-project)" && hyperframes-preview film'
addons/modal/selkies-modal exec --name frames -- bash -c 'cd "$(selkies-modal-project)" && hyperframes render film --quiet -o renders/film.mp4'
```

The command line is the one part of any image here that is not pinned. It
follows its upstream: an image is built with the newest release of the npm
package, and a session takes the newest again as it starts, with that
release's skills, so what upstream adds is there the same day. The risk is a
release nobody here has run, and three things bound it
(`hyperframes/release.sh`): a release is switched to only after it installed
whole and rendered half a second of its own starting project on that machine;
the update has 120 seconds, of which the registry has 15 to answer, and a
session that cannot have the newest runs the release its image was built
with; and `MOODY_HYPERFRAMES_VERSION` in the environment of whoever defines
the image (a version, or `built`) holds every session on one release.
`hyperframes-release status` prints which release runs and why.

`hyperframes-preview DIR` puts a project's live preview, the command line's
own studio, on the session's screen in one browser window, and
`hyperframes-preview --stop` closes it; until then the screen is a terminal on
the session's log. Chrome keeps its own sandbox in a Modal Sandbox, so neither
browser is started with a flag that turns it off, and a render captures with
the software renderer on a machine without a GPU. A render of type and motion
took a little over its own length on two cores, and one with a 720p clip as a
layer about twice that. The command line reports its use to its makers unless
told not to; a session tells it not to (`HYPERFRAMES_NO_TELEMETRY`), and
neither its update check nor its skills installer runs, since the release and
its skills are the session's to settle (`moody/skills/hyperframes` has the
commands as they were run).

## The session

The image is the base container by digest with three additions: Blender's
release archive from blender.org, checked against the hash blender.org
publishes, `xprintidle` to read the display's idle counter, and this
directory's scripts. `BASE_IMAGE`, `BLENDER_VERSION`, and `BLENDER_SHA256` at
the top of `sandbox.py` choose what it is built from,
and each craft app's `<APP>_VERSION` and `<APP>_SHA256` do for its image, and a
change to any of them builds a new
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
Editor's ([`moody/UNREAL.md`](../../moody/UNREAL.md)), leaves through a TURN
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
