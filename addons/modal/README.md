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
| `url` | Prints a new link to a running session |
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

## The session

The image is the base container by digest with three additions: Blender's
release archive from blender.org, checked against the hash blender.org
publishes, `xprintidle` to read the display's idle counter, and this
directory's scripts. `BASE_IMAGE`, `BLENDER_VERSION`, and `BLENDER_SHA256` at
the top of `sandbox.py` choose what it is built from, as `FILMCRAFT_VERSION`
and `FILMCRAFT_SHA256` do for FilmCraft's image, and a change to any of them
builds a new image on the next `up` or `build`.

The Selkies window manager runs Blender as the session's application,
maximized, and starts it again if it is quit. Every other
[setting](../../docs/settings.md) is the server's own and passes through
`--env`:

```bash
addons/modal/selkies-modal up --gpu L4 --env SELKIES_DESKTOP=true --env SELKIES_ENCODER=av1enc
```

`SELKIES_DESKTOP=true` starts the session on the desktop shell, with Blender in
a window of it. The transport is WebSockets, the one Modal's proxy carries;
WebRTC needs a UDP path that proxy does not offer, so it is not offered here.
