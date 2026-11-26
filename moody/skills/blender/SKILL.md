---
name: blender
description: Model, light, and render in Blender by script, in the window the person watches. Open it whenever the work is 3D, a model at real size, materials, daylight or studio light, a camera, a still render, a turntable or a fly-around clip, or a file for print or the web (STL, GLB, OBJ, FBX, USD). It covers an architecture visualization from a CADCraft plan or from stated dimensions (massing in clay, then light, materials, exterior and interior views), a product or a single object on a studio backdrop, a drawing or a logo given depth, and a model checked, repaired, and made 3D-printable. It holds how Blender is driven here (Python in the Blender on the Screen, renders without the window, long renders as jobs), which machine renders what and how long each takes, what the image does not have, and the hand-offs with CADCraft, PhotoCraft, FilmCraft, and Unreal Engine.
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# The 3D studio

You are the person's modeler, lighter, and photographer. They direct. You propose with reasons,
they decide, you build it at its real size and show it in pictures. A render is a claim about
something that will be built or made: every size in it is one you were given or said you assumed.

The detail lives in six references; read the one a stage needs before you start it:

| Reference | Read it before |
|---|---|
| [references/modeling.md](references/modeling.md) | building or changing geometry, units, modifiers, booleans, and any import or export |
| [references/look.md](references/look.md) | sun and sky, a panorama world, room light, cameras, materials |
| [references/rendering.md](references/rendering.md) | any render: the script, devices, samples, clay, animation, measured times |
| [references/archviz.md](references/archviz.md) | a building or an interior, from a plan or from dimensions |
| [references/objects.md](references/objects.md) | a product or a single object, a turntable, a file for print or a web viewer, a model to repair |
| [references/handoff.md](references/handoff.md) | work arriving from or leaving for another engine |

## When this applies

The person wants to see something in three dimensions, or wants a 3D file: "render my house",
"show the kitchen at dusk", "a turntable of the bottle", "make this chair 3D-printable", "a GLB
for the site". Blender is this project's engine for it in Architecture, Art (the 3D Object
shortcut), Animation, and Games.

What is another skill's job: the measured drawing a building is built from (`cadcraft`; the
drawing is the source and the model follows it), retouching a render or laying out a board
(`photocraft`), cutting frames into a film (`filmcraft`), a walkable scene (`unreal`). This skill
has no recipes for sculpting, rigging, character animation, or simulation: say so before you try
one, and take small steps you check.

## The loop: propose, decide, build, show

1. **Propose.** Two to four options with your recommendation first and one line of why: a
   massing, a time of day, a camera position, a palette.
2. **Ask.** `ask_user(question, options, recommended)` ends your turn. One decision per
   question, the last option a way out. A choice among pictures (three views, two palettes) is a
   card (`show_ui`, the `cards` skill).
3. **Build** exactly what was chosen, by script, at real size.
4. **Read it back.** Every script here prints one line of JSON with what it made: sizes,
   volumes, where the subject falls in the frame, how bright the render came out. Check the
   numbers before you look at a picture, and report them: a picture does not carry them.
5. **Show** a render with `preview` ([Show your work](#show-your-work)), with what to look at.
6. **Record.** Save the `.blend`, keep `update_plan(items)` current (Brief, Massing, Light,
   Views, Materials, Final frames, Motion, Delivery; one `active`), put approved pictures in the
   library (`library_upsert`), and with a repository linked write the decisions (`github_save`):
   the sizes assumed, the sun's date and hour, each camera, the render settings.

### Checkpoints: always ask before

- A size the brief does not give: a ceiling height, a wall thickness, a sill, a product's
  dimensions. Say the number you would use and ask; an assumed size looks exactly like a given one.
- Leaving clay. Form and light are approved on a gray model before any material goes on.
- The views: which cameras become final frames.
- A render or an animation that takes more than a few minutes: say the time and the credits.
- Anything that replaces work: saving over a `.blend`, deleting objects, importing a plan again.
- A larger machine, a second engine, and every export someone will build or print from.

## The questions to ask first

Open with what it is for, because the deliverable decides the rest:

> What should come out at the end: pictures (which views), a short clip (a turntable or a
> fly-around), or a file to print or to put on a site?

Then one at a time, only what you cannot infer:

1. **What is fixed.** A plan drawn in CADCraft, dimensions, a photograph, a sketch. For a
   product: its real size. Without a drawing, ask for the three numbers that matter most.
2. **The light.** Options such as "Morning sun, crisp shadows", "Golden hour, long shadows",
   "Dusk with the lights on". Recommend the one that lights the face the camera sees.
3. **The finish.** "A white model" (clay, about form), "Real materials", or "Both, clay first".
   Recommend both.

File names, collections, sample counts, the device, exposure, focal lengths, and how a model is
built are yours to decide and report.

## Recipes

Blender has no command channel: `engine_call` answers that it has none. Everything goes through
`engine_exec`, and each `bash` block here and in the references is one `engine_exec` command, run
as written on Blender 5.2.4.

### 1. The engine, the folder, where Blender stands

`engine_start("blender", "cpu")` builds, lights, and renders drafts; a GPU tier only makes
renders faster ([Cost and time](#cost-and-time)). Then `engine_show(engine_id)`.

`engine_exec` starts in the home directory and Blender itself runs in the workspace, so name
the project's folder in every command. A project's first engine finds no folder yet: make it.

```bash
P="$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}"; mkdir -p "$P/scripts" "$P/previews"
cat > "$P/scripts/start.py" <<'PY'
# Where this Blender stands: the file it has open, whether that file is this project's, and what the scene holds.
import bpy, json, os

P = os.path.join(os.environ["SELKIES_MODAL_WORKSPACE"], os.environ.get("SELKIES_MODAL_PROJECT", "projects/default"))
scene = bpy.context.scene
print(json.dumps({
    "blender": bpy.app.version_string,
    "project": P,
    "file": bpy.data.filepath,
    "file_in_project": bpy.data.filepath.startswith(P + os.sep),
    "blends_in_project": sorted(f for f in os.listdir(P) if f.endswith(".blend")),
    "units": [scene.unit_settings.system, scene.unit_settings.scale_length, scene.unit_settings.length_unit],
    "engine": scene.render.engine,
    "frames": [scene.frame_start, scene.frame_end, scene.render.fps],
    "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
    "camera": scene.camera.name if scene.camera else None,
    "collections": {c.name: len(c.objects) for c in bpy.data.collections},
    "objects": {o.name: [o.type, [round(d, 3) for d in o.dimensions]] for o in scene.objects},
    "windows": len(bpy.context.window_manager.windows),
}))
PY
selkies-modal-blender 60 < "$P/scripts/start.py"
```

It answers in about a second (8 s while Blender is still starting): `{"blender": "5.2.4 LTS",
"file": "…/projects/<id>/house.blend", "file_in_project": true, "blends_in_project": […],
"units": ["METRIC", 1.0, "METERS"], "camera": "Exterior south-east", "objects": {name: [type,
[x, y, z] in meters]}, "windows": 1, …}`.

**A Blender engine opens the scene the workspace's last Blender closed with, whichever project
that was**, and a new workspace opens Blender's start-up scene (a cube, a light, a camera) with
`file` empty. When `file_in_project` is false and the project has a `.blend`, or the scene is
another project's, set that right before anything else, in a script like the above:

```text
bpy.ops.wm.open_mainfile(filepath=os.path.join(P, "house.blend"), load_ui=False)    this project's file
bpy.ops.wm.read_homefile(use_empty=True, load_ui=False)                              an empty scene
```

After either, `bpy.context.scene` is a new object: fetch it again. `"windows": 2` means a render
window is open over the viewport: close it (rendering.md).

### 2. Python in the Blender the person sees

`selkies-modal-blender SECONDS < script.py` runs the script inside the Blender on the Screen,
as if from its 3D viewport, so `bpy.ops` operators work, and the person watches the scene
change. Keep scripts in `scripts/` of the project's folder: the next session, the window-less
Blender, and a job all run the same files.

- **What comes back** is what the script printed. Print one line of JSON at the end; operators
  add lines of their own before it (`Info: Saved "house.blend"`).
- **Exit status** 0: it ran. 1: it raised, and the traceback follows what it printed (line
  numbers are your script's, shown as `<request>`). 124: Blender did not answer in `SECONDS`.
- **Never let the wait run out on a script that is still running.** After one such 124 the
  bridge answers nothing more in that session: every later call is 124, and the engine's stop no
  longer keeps the open scene for the next one. Give 280 and keep a script's work under a
  minute. If it happened, restart Blender, which takes a second and loses what was not saved,
  then open the saved file:
  `kill "$(pgrep -xf 'blender --python /usr/local/share/selkies-modal/blender-session.py')"`
- **A script holds the window still until it returns.** The person sees a frozen Blender, and a
  render called the plain way holds it for the whole render. Anything long goes to recipe 3.
- **Save where the next engine looks.** `bpy.ops.wm.save_as_mainfile(filepath=os.path.join(P,
  "house.blend"))` once, `bpy.ops.wm.save_mainfile()` after; in a saved file `//previews/a.png` is
  a path beside it. Save before every script that could be slow.
- **A save drops what nothing uses.** A material or a world no object holds is gone from the
  file: set `use_fake_user = True` on one you want kept.
- **Undo.** End a script with `bpy.ops.ed.undo_push(message="Building shell")`: its changes are
  then one step, which `bpy.ops.ed.undo()` takes back, as the person's Ctrl+Z does.
- **Scripts are run again.** Make each one replace what it made last time (remove the object of
  the same name first), so a changed number is a second run, not a second copy.

### 3. Renders: without the window, as a job, in the window

`scripts/render.py` ([rendering.md](references/rendering.md) has it; write it once per project)
renders a saved file in a second Blender that has no window, so the person's stays free:

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && blender -b house.blend --python-exit-code 1 --python scripts/render.py -- --camera "Exterior south-east" --out previews/exterior-draft.png --percent 50 --hide "Scale figure" 2>&1 | grep "^RENDER\|rror:"
```

It printed `RENDER {… "device": ["CPU"], "samples": 64, "size": [960, 540], "seconds": 23.0,
"first": "previews/exterior-draft.png", "brightness": {"mean": 0.603, "clipped": 0.0, "black":
0.0}}`. It reads the file from disk: save in the window first. `--clay` renders the same frame
in gray; on a GPU tier add `--device OPTIX`.

`engine_exec` waits five minutes. A render that could pass four runs as a job, which also keeps
the engine from ending as unused while it works:

```bash
P="$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}"; selkies-modal-job start interior-01 -- blender -b "$P/house.blend" --python-exit-code 1 --python "$P/scripts/render.py" -- --camera "Interior from door" --out previews/interior-draft.png --percent 50 --hide "Scale figure" --exposure -1.7
```

```text
selkies-modal-job status interior-01                     interior-01  running | done | failed (exit 1)  started <time>  <command>
selkies-modal-job log interior-01 | grep "^RENDER"       its RENDER line, once it is done
selkies-modal-job stop interior-01
```

To let the person watch a render fill in, start it in their Blender instead:
`bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)` returns at once and the bridge stays
free (rendering.md has the scripts, and how to close the render window afterwards).

### 4. The stages of a job

| Stage | What you do | Reference | Show |
|---|---|---|---|
| Geometry at real size | walls, slabs, openings, or the product, from a plan or from numbers | modeling.md, archviz.md, objects.md | a clay render, sizes read back |
| Light | sun and sky for a place, date, and hour, or a studio's three lights | look.md | the same view, lit |
| Views | cameras at eye height, level, framed by lens shift | look.md | each view in clay |
| Materials | Principled recipes in meters; pictures from the library | look.md | a draft with materials |
| Final frames | full size, 128 samples, as a job on `cpu` | rendering.md | the finished stills |
| Motion | an orbit, a walk, or a turntable, as frames, then an mp4 | rendering.md, objects.md | the clip |
| Delivery | a GLB for the page, an STL for a printer, pictures for another engine | modeling.md, handoff.md | the file's size and what it kept |

The rules that hold in every stage:

- **One unit is one meter, always.** Millimeters are a way of showing lengths
  (`scene.unit_settings.length_unit = "MILLIMETERS"`), never a scale: lights, cameras, and
  exporters assume meters. +Z is up, and a plan's north is +Y.
- **Build from coordinates, not by scaling.** A box made with its vertices at real coordinates
  has scale 1; an object you scaled needs `bpy.ops.object.transform_apply(location=False,
  rotation=True, scale=True)` before a modifier, a boolean, or an export reads it.
- **Measure the result, not the object.** `obj.dimensions` is stale until
  `bpy.context.view_layer.update()`, and under a Subdivision modifier it is the cage's (a vase
  read 92 mm across where its surface is 88.5). modeling.md has the measurement.
- **Name things for what they are** (`Wall over Door`, `Glass Window east`) in collections
  (`Building`, `Site`, `Cameras`): scripts find objects by the start of their name.

## Taste

- **Clay before color.** A gray model shows proportion and light with nothing to hide behind;
  materials go on a form that is already approved.
- **One sun, and it models the building**: one face in light, the next in shade. Put it 30 to
  60 degrees to one side of the camera, never behind it, and choose the hour for the face the
  camera sees.
- **Architecture is photographed level.** Eye height 1.6 m, the camera turned about the vertical
  only, the frame raised by lens shift, so verticals stay vertical. Interiors 16 to 24 mm,
  exteriors 24 to 35 mm, details 50 to 85 mm. A product takes 70 to 100 mm from a little above.
- **Roughness is the material.** Plaster 0.85, concrete 0.7, oiled wood 0.45, glazed ceramic
  0.1. Nothing is pure white (0.86 is a white wall) or pure black. A texture's scale is a size in
  meters, never "what looks right".
- **Expose before you add light.** A dark interior first gets more exposure (about 3 stops over
  the exterior's), then portals, and only then lamps that would exist in the room.
- **Entourage gives scale and stays quiet**: a figure, a few trees, as plain solids in one pale
  tone. The image has no models of people, plants, or cars.
- **Draft small, finish once.** Half size and 64 samples answer every question about form, light,
  and framing. The full frame is rendered when the person has said yes.

## Cost and time

An engine costs credits every minute it runs (1 on `cpu`, 3 on `t4`; a credit is $0.01), and its
tier is fixed when it starts. Say the tier, the minutes, and the credits before `engine_start`
and before a long render. Which tier a step needs, and how long it took with Cycles on the
references' two test scenes (a one-room building on a site; a vase on a backdrop):

| Step | Tier to use | On `cpu` | On `t4`, on its GPU |
|---|---|---|---|
| Import, build, light, cameras, materials: each a script | `cpu` | about 1 s | the same |
| A draft at 960 × 540: an exterior; an interior | `cpu` | 23 s; 60 s | 2.6 s; 4.2 s |
| Exterior final, 1920 × 1080, 128 samples | either | 2 min 57 s | 11 s |
| Interior final, 1920 × 1080, 128 samples | `t4` | 7 min 41 s | 24 s |
| Product final, 1600 × 1200, 128 samples | either | 3 min 1 s | 10 s |
| A clip of 96 frames at 960 × 540: an orbit, a walk | `t4` | 19 min, 19 credits | 63 to 81 s, 3 to 4 credits |
| A print check, a GLB, an STL, a hand-off file | `cpu` | 3 to 7 s | the same |

- **Build and draft on `cpu`; render final interiors and every clip on `t4`.** It rendered 17 to
  19 times faster at three times the price, so the same frame costs about a sixth. To change
  tier: save, `engine_stop`, then `engine_start("blender", "t4")` on the same project, where the
  folder and the `.blend` wait (up in 11 to 15 s here; a GPU can take minutes to find). Pass
  `--device OPTIX`: without it a GPU engine renders on its processor.
- **A job that goes from plan to final frames in one sitting** can start on `t4`: the building
  scripts take the same second there, and each minute costs 2 credits more.
- **`cpu` engines differ.** The same draft took 24 s on one start and 15 s on another: quote a
  final from a draft on the engine you have (rendering.md).
- `l4` and `a10` were not measured. Stop the engine when the frames are confirmed in `previews/`.

## What is not possible yet

- **No command channel**, and a bridge that dies after a timeout on a running script, taking
  the keeping of the open scene at stop with it (recipe 2). Save often.
- **Nothing but Blender itself is installed.** No asset library (no people, trees, cars,
  furniture, or material packs), no texture library, and only eight small panoramas (look.md).
  Offer block entourage, procedural materials, and pictures from the library (`generate_image`,
  or the person's uploads), and say that is what they are.
- **Only the add-ons Blender ships.** No DXF, DWG, STEP, IGES, or 3MF importer, no 3D-print
  toolbox, no sun-position add-on, no BIM tools (look.md computes the sun; objects.md checks a
  print). Blender's online access is off, and installing an extension was not tried.
- **The window is drawn in software on every tier**, a T4's too, and so is EEVEE, with or
  without the window: on `t4` it took 50 s for a frame Cycles rendered on the GPU in 11, it has
  no bounced light, and it does not take the sky's sun (rendering.md). Use Cycles for what the
  person judges. The viewport's rendered modes were not measured: show renders.
- **A GPU renders only on a GPU tier**; on `cpu`, asking for one falls back to the CPU and the
  RENDER line says so. Blender's kept preferences still list the GPU of an earlier engine:
  trust `gpu_peak` in that line, not a device list.
- **Textures made of nodes stay in Blender.** A GLB or an FBX carries plain values; the
  procedural materials of look.md arrive white and its box-projected pictures unplaced
  (modeling.md). There is no recipe here for UV unwrapping or baking.
- **A plan holds no heights**, and a model does not go back into a drawing: only a cut outline
  returns to CADCraft (handoff.md).
- **Send to Unreal is not in this engine.** It is in the Blender of an Unreal engine (the
  `unreal` skill), and that road was not run for this skill.

## Hand-offs

Files in `handoff/<from>-to-<to>/` of the project's folder; [handoff.md](references/handoff.md)
has each recipe and what was run. A running engine does not see what another wrote after it
started: `engine_send` the file, or start the receiver after the export, and confirm with
`engine_files` on the engine that opens it.

| Route | Format | Folder |
|---|---|---|
| CADCraft to Blender | DXF, read with the `cadcraft` skill's import script | `handoff/cadcraft-to-blender/` |
| Blender to CADCraft | DXF of an outline cut at a height, in millimeters | `handoff/blender-to-cadcraft/` |
| VectorCraft to Blender | SVG of the one-color artwork, as curves | `handoff/vectorcraft-to-blender/` |
| PhotoCraft to Blender | PNG as a material or a picture on a plane | `handoff/photocraft-to-blender/` |
| Blender to PhotoCraft | a 16-bit PNG, or an OpenEXR that keeps the light's range | `handoff/blender-to-photocraft/` |
| Blender to FilmCraft | an mp4, or numbered PNG frames | `handoff/blender-to-filmcraft/` |
| Blender to Unreal Engine | the `.blend`, sent from the Unreal engine's own Blender | the `unreal` skill |
| The library to Blender | `engine_import(engine_id, tags)` | `library/<tag>/` |

## Show your work

The Screen shows Blender's window; a render is what the person judges. Everything shown is a
file under `previews/` that a command of this skill wrote (the studio skill has `preview`'s
rules):

```text
preview(engine_id, path="previews/exterior-clay.png", caption="The massing from the south-east, 10:30 in March, in clay")
preview(engine_id, paths=["previews/exterior-clay.png", "previews/exterior-draft.png"], caption="The same view in clay and with materials", compare=true)
preview(engine_id, path="previews/house-orbit.mp4", caption="One turn around the building, 4 seconds")
```

- A still: `render.py --out previews/<name>.png`; in clay with `--clay`; smaller with `--percent`.
- A clip: `render.py --frames 1 96 --out previews/<name>/frame`, then the `ffmpeg` line of
  rendering.md writes `previews/<name>.mp4`.
- A model to turn in the conversation or on a page: `print_check.py` (objects.md) writes a
  `.glb` of one object and `export_glb.py` (modeling.md) of a whole scene, and a card's `model`
  component shows it (the `cards` skill).
- What the window looks like now: `engine_screenshot(engine_id)`, after closing a render window
  that covers the viewport.
- One preview per stage, with the numbers in your message: the sizes, the sun's hour, the lens,
  the render time. `brightness` in the RENDER line says whether a picture is too dark (mean
  under 0.3) or burnt (`clipped` over 0.02) before you look; `look: true` when you must judge it.
