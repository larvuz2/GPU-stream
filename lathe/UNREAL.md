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

- `unreal_image(registry_secret, version)` in `addons/modal/sandbox.py`, and
  the session on it: the editor started off screen with editor streaming, the
  TURN relay, Blender beside it with the add-on, `selkies-modal-project` and
  this folder on the editor's Python path, and `DefaultRemoteControl.ini` in
  the editor's project. Whether Modal shares a layer pulled with one user's
  Secret with another user's build has to be checked there.
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
- An Unreal start on a tier without a GPU is not refused yet.
