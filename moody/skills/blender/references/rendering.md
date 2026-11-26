<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Rendering

One script renders everything: stills and frames, clay and materials, CPU and GPU. It was run
as written on `cpu` engines (2 cores, 4 at most, no GPU) and on a `t4` engine (a Tesla T4 with 8
cores at most), and every time below is from its own RENDER line.

## The render script

Write it once into the project's `scripts/` (one `engine_exec`: `cat > "$P/scripts/render.py"
<<'PY'`, the script, `PY`):

```python
# Render a saved .blend without its window: one still or a range of frames, in clay or with its materials.
#   blender -b house.blend --python-exit-code 1 --python scripts/render.py -- --camera "Exterior south-east" --out previews/exterior-clay.png --clay
# Everything after "--" is this script's. It prints one line starting RENDER: what it used, how long it took,
# how bright the picture came out, and, on a GPU, how hard the GPU worked while it rendered.
import argparse, json, os, subprocess, sys, threading, time
import bpy
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--camera", help="the camera object's name; left out: the scene's own")
parser.add_argument("--out", required=True, help="a path in the .blend's folder; for frames, the folder and the name before the number")
parser.add_argument("--engine", default="CYCLES", choices=["CYCLES", "BLENDER_EEVEE"])
parser.add_argument("--device", default="CPU", choices=["CPU", "OPTIX", "CUDA"], help="for Cycles")
parser.add_argument("--samples", type=int, default=64)
parser.add_argument("--percent", type=int, default=100, help="of the scene's resolution")
parser.add_argument("--clay", action="store_true", help="every surface in one matte gray, glass left out")
parser.add_argument("--frames", type=int, nargs=2, metavar=("FIRST", "LAST"), help="render this range instead of one still")
parser.add_argument("--frame", type=int, help="the frame of an animation a still is taken at")
parser.add_argument("--exposure", type=float, help="in stops, in place of the scene's")
parser.add_argument("--no-denoise", action="store_true")
parser.add_argument("--format", default="png", choices=["png", "png16", "exr"], help="8-bit PNG, 16-bit PNG, or 32-bit OpenEXR")
parser.add_argument("--hide", nargs="*", default=[], metavar="PREFIX", help="leave out objects whose name starts with one of these")
parser.add_argument("--show", nargs="*", default=[], metavar="COLLECTION", help="render these collections though the file hides them")
parser.add_argument("--sun-elevation", type=float, help="degrees, for the world's Sky Texture, in place of the file's")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

scene = bpy.context.scene
folder = os.path.dirname(bpy.data.filepath)
if args.camera:
    scene.camera = bpy.data.objects[args.camera]
if args.frame is not None:
    scene.frame_set(args.frame)
scene.render.engine = args.engine
scene.render.resolution_percentage = args.percent
if args.exposure is not None:
    scene.view_settings.exposure = args.exposure
image = scene.render.image_settings
image.file_format, image.color_depth = {"png": ("PNG", "8"), "png16": ("PNG", "16"), "exr": ("OPEN_EXR", "32")}[args.format]

used, on_gpu = ["CPU"], False
if args.engine == "CYCLES":
    cycles, prefs = scene.cycles, bpy.context.preferences.addons["cycles"].preferences
    cycles.samples, cycles.use_adaptive_sampling, cycles.adaptive_threshold = args.samples, True, 0.01
    cycles.use_denoising, cycles.denoiser, cycles.device = not args.no_denoise, "OPENIMAGEDENOISE", "CPU"
    if args.device != "CPU":
        # Ask Cycles what this machine has now. The preferences are kept in the workspace, and their own
        # list (prefs.devices) still names the GPU of an engine that ran there before.
        try:
            prefs.compute_device_type = args.device
            here = [device for device in prefs.get_devices_for_type(args.device) if device.type == args.device]
        except TypeError:                          # this machine's Cycles knows no such device type
            here = []
        for device in prefs.devices:
            device.use = False
        for device in here:
            device.use = True
        found = [device.name for device in here]
        if found:
            cycles.device, cycles.denoising_use_gpu, used, on_gpu = "GPU", True, [f"{args.device}: {name}" for name in found], True
        else:
            used = [f"CPU (this machine has no {args.device} device)"]
else:
    scene.eevee.taa_render_samples = args.samples

if args.clay:
    clay = bpy.data.materials.get("Clay") or bpy.data.materials.new("Clay")
    bsdf = next(n for n in clay.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value, bsdf.inputs["Roughness"].default_value = (0.8, 0.8, 0.8, 1.0), 0.9
    bpy.context.view_layer.material_override = clay
    args.hide.append("Glass")
for obj in scene.objects:
    if any(obj.name.startswith(prefix) for prefix in args.hide):
        obj.hide_render = True
for name in args.show:
    bpy.data.collections[name].hide_render = False
if args.sun_elevation is not None:
    sky = next(n for n in scene.world.node_tree.nodes if n.bl_idname == "ShaderNodeTexSky")
    sky.sun_elevation = args.sun_elevation * 3.141592653589793 / 180

# While a GPU renders, ask the driver once a second how busy it is: the proof of where the render ran
peak, finished = {"gpu_percent": 0, "gpu_mib": 0}, threading.Event()


def watch():
    while not finished.wait(1.0):
        try:
            answer = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                                    capture_output=True, text=True, timeout=5).stdout.split(",")
            peak["gpu_percent"], peak["gpu_mib"] = max(peak["gpu_percent"], int(answer[0])), max(peak["gpu_mib"], int(answer[1]))
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            return


if on_gpu:
    threading.Thread(target=watch, daemon=True).start()
began = time.time()
if args.frames:
    scene.frame_start, scene.frame_end = args.frames
    scene.render.filepath = os.path.join(folder, args.out + "_")
    scene.render.use_overwrite = False            # started again, it renders only the frames that are missing
    scene.render.use_persistent_data = True       # the scene stays loaded between frames
    bpy.ops.render.render(animation=True)
    written = sorted(f for f in os.listdir(os.path.dirname(scene.render.filepath)) if f.startswith(os.path.basename(args.out) + "_"))
    shown = os.path.join(os.path.dirname(scene.render.filepath), written[0])
else:
    scene.render.filepath = os.path.join(folder, args.out)
    bpy.ops.render.render(write_still=True)
    written, shown = [args.out], scene.render.filepath
seconds = round(time.time() - began, 1)
finished.set()
if args.engine == "BLENDER_EEVEE":                # what drew it is known only once it has drawn
    import gpu
    used = [f"{gpu.platform.backend_type_get()}: {gpu.platform.renderer_get()}"]

picture = bpy.data.images.load(shown)
report = {
    "file": os.path.basename(bpy.data.filepath), "camera": scene.camera.name, "engine": args.engine, "device": used,
    "samples": args.samples, "size": list(picture.size), "frames": len(written), "seconds": seconds, "first": written[0],
}
if args.format != "exr":
    # How bright the picture came out, read back from the file as it is stored: the mean of its pixels, 0 to 1,
    # and the share at each limit. An OpenEXR holds light, not a picture, so it has no such reading.
    picture.colorspace_settings.name = "Non-Color"
    pixels = np.empty(picture.size[0] * picture.size[1] * 4, dtype=np.float32)
    picture.pixels.foreach_get(pixels)
    value = pixels.reshape(-1, 4)[:, :3].max(axis=1)
    report["brightness"] = {"mean": round(float(value.mean()), 3), "clipped": round(float((value > 0.98).mean()), 3), "black": round(float((value < 0.02).mean()), 3)}
if on_gpu:
    report["gpu_peak"] = peak
print("RENDER " + json.dumps(report))
```

Run it on a saved file, from the project's folder, in a Blender that has no window:

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && blender -b house.blend --python-exit-code 1 --python scripts/render.py -- --camera "Exterior south-east" --out previews/exterior-draft.png --percent 50 --hide "Scale figure" 2>&1 | grep "^RENDER\|rror:"
```

| Parameter | Meaning |
|---|---|
| `--camera NAME` | the camera object to render from; left out, the scene's |
| `--out PATH` | where the picture goes, relative to the `.blend`. With `--frames`, the folder and name before the number: `previews/orbit/frame` writes `frame_0001.png` and on |
| `--device CPU\|OPTIX\|CUDA` | where Cycles renders. A GPU that is not there falls back to the CPU, and the line says so |
| `--samples N` | 64 unless given: enough for a draft |
| `--percent N` | of the scene's resolution: 50 for drafts |
| `--clay` | every surface in one matte gray, objects named `Glass…` left out |
| `--frames FIRST LAST` | an animation's range instead of one still |
| `--frame N` | the frame a still is taken at, to judge one frame of a move |
| `--exposure STOPS` | in place of the scene's, for an interior from a file exposed for outdoors |
| `--hide PREFIX …` | leave out objects by the start of their name |
| `--show COLLECTION …` | render collections the file hides, such as `"Lights evening"` |
| `--sun-elevation DEGREES` | move the sky's sun up or down for this render |
| `--format png\|png16\|exr` | 8-bit PNG for the conversation; 16-bit PNG or OpenEXR for a hand-off (handoff.md) |
| `--engine BLENDER_EEVEE` | EEVEE in place of Cycles: read "Which engine and which device" first |
| `--no-denoise` | leave the grain in |

The line it prints, here from the `t4` engine with `--device OPTIX --samples 128`:

```text
RENDER {"file": "house.blend", "camera": "Exterior south-east", "engine": "CYCLES", "device": ["OPTIX: Tesla T4"], "samples": 128, "size": [1920, 1080], "frames": 1, "seconds": 11.2, "first": "previews/exterior-final.png", "brightness": {"mean": 0.602, "clipped": 0.0, "black": 0.0}, "gpu_peak": {"gpu_percent": 99, "gpu_mib": 892}}
```

- `device` is what Cycles was set to use, by name. `gpu_peak` is what the graphics driver
  reported while the picture rendered: 99 percent busy and 0.9 GB in use. That pair is the
  proof of where a render ran; report it with the time. A GPU render whose `gpu_percent` is 0
  ran somewhere else.
- `brightness` is read from the written file: the `mean` of its pixels from 0 to 1, and the
  share `clipped` at white and at `black`. A daylight exterior came out near 0.6, an interior
  near 0.64, a product on a pale backdrop near 0.73. Under 0.3 is too dark, and `clipped` over
  0.02 is burnt: an evening room at `--exposure 1.5` read mean 0.935, clipped 0.494, and at -2.5
  it read 0.60. Change `--exposure` by whole stops on a draft. An OpenEXR has no such reading.
- `--python-exit-code 1` makes a script that raises end Blender with status 1; without it a
  failed render still exits 0. The file is read from disk: save in the window first.
- On a machine without a GPU, Blender prints `cycles | WARNING CUEW initialization failed`
  as it starts. It means there is no CUDA to load, and nothing else.

## Which engine and which device

**Cycles renders everything the person judges.**

- **On `cpu`** it renders on the processor (`"device": ["CPU"]`). `--device OPTIX` there answers
  `"device": ["CPU (this machine has no OPTIX device)"]` and renders all the same.
- **On `t4`** Cycles lists three devices: the processor, and the `Tesla T4` twice, as `CUDA` and
  as `OPTIX`. Pass `--device OPTIX`. The exterior final took 10.6 s with `OPTIX`, 9.6 s with
  `CUDA`, and 114 s on that machine's own processor: without `--device`, a GPU engine renders
  on its CPU and you pay three times the price for the slow road. The script also denoises on
  the GPU.
- **Blender's preferences remember machines.** They are kept in the workspace, and their device
  list still named the `Tesla T4`, switched on, on a `cpu` engine started after the GPU one. A
  script that trusted that list reported a GPU render that ran on the processor, with
  `gpu_peak` at 0. So the script asks Cycles what is here now (`get_devices_for_type`), and you
  read `gpu_peak`.
- **Two `cpu` engines are not the same machine.** The same product draft took 24 s on one start
  and 15 s on another. Quote a final from a draft on the engine you have: four times the draft
  for full size, twice for 128 samples.

**EEVEE is a software renderer here**, in the window and without it, on every tier: its RENDER
line names what drew it, `"device": ["OPENGL: llvmpipe (LLVM 21.1.8, 256 bits)"]`, on `cpu`
and on `t4` alike, because the display is not drawn by the GPU. Measured: 15 s for the exterior
at 960 × 540 on `cpu` (a Cycles draft took 23 s), and 50 s at 1920 × 1080 on the `t4` machine
(Cycles on its GPU: 11 s). What it leaves out: bounced light (shadows come out harder and bluer),
glass (it shows as a mirror), and the sky's sun (look.md has the Sun light that stands in). Use
it only when the person asks for it by name, and say what it is.

The viewport's Material Preview and Rendered modes run on the same software renderer. They were
not measured: show renders, not the viewport.

## Samples, denoising, size

- **Drafts: 64 samples at 50%.** They answer form, light, framing, and material. **Finals: 128**
  for an exterior, a product, and an interior with portals; the denoiser (OpenImageDenoise, on
  by default in the script) takes the rest of the grain. 256 samples doubled an interior's time
  (24 s to 46 s on `t4`): reach for it only when a 128 shows blotches in the corners.
- **Time follows the work.** 128 samples at full size took 7.9 times a 64-sample draft at half
  size on the exterior: four times for the pixels, twice for the samples.
- **Size is the scene's** (`scene.render.resolution_x`, `resolution_y`; 1920 by 1080 for the
  building, 1600 by 1200 for the product) times `--percent`.
- **A light picture for the conversation** is the same render at `--percent 50`; the full frame
  is for the deliverable.

## Clay

`--clay` overrides every material with one matte gray (base 0.8, roughness 0.9) for that render
only, and leaves out glass, so rooms keep their daylight. Use it for the massing, for the light,
and for every camera before materials: the file is not changed, so the same command without
`--clay` is the material version of the same frame.

## A render the person watches

To show a render filling in on the Screen, start it in their Blender. Through the bridge:

```python
# Start a render in the Blender the person sees and return at once: they watch it fill in, in a render
# window, and the bridge stays free. Ask live_render_done.py whether it has finished.
import bpy, json

scene = bpy.context.scene
CAMERA, OUT, SAMPLES, PERCENT = "Exterior south-east", "//previews/exterior-live.png", 64, 100

scene.camera = bpy.data.objects[CAMERA]
scene.render.engine = "CYCLES"
scene.cycles.samples, scene.render.resolution_percentage = SAMPLES, PERCENT
scene.render.filepath = OUT                         # "//" is the folder of the saved .blend
result = bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)
print(json.dumps({"started": sorted(result), "rendering": bpy.app.is_job_running("RENDER")}))
```

It answers `{"started": ["RUNNING_MODAL"], "rendering": true}` at once. A render window opens
over Blender's and shows the frame, the time, and the sample count as it goes (`Sample 8/64`,
`Remaining: 01:27`), and the bridge keeps answering. Ask whether it is done, which also clears
the window away:

```python
# Has the render in the person's Blender finished? Once it has, close every window but the main one, so the
# render window no longer covers the viewport on the Screen.
import bpy, json, os

running = bpy.app.is_job_running("RENDER")
path = bpy.path.abspath(bpy.context.scene.render.filepath)
if not running:
    for window in list(bpy.context.window_manager.windows)[1:]:
        with bpy.context.temp_override(window=window):
            bpy.ops.wm.window_close()
print(json.dumps({"rendering": running, "file": path, "written": os.path.exists(path), "windows": len(bpy.context.window_manager.windows)}))
```

`{"rendering": false, "written": true, "windows": 1}` when it is. On `cpu` this exterior took
about 100 s at full size. On a GPU tier, name the device first, or the window renders on the
processor:

```python
# The same render in the person's Blender, on the machine's GPU: ask Cycles which devices are here now, turn
# those on in Blender's preferences, tell the scene to use them, then start the render as live_render.py does.
import bpy, json

scene = bpy.context.scene
CAMERA, OUT, SAMPLES, PERCENT, KIND = "Exterior south-east", "//previews/exterior-live.png", 128, 100, "OPTIX"

prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = KIND
here = [device for device in prefs.get_devices_for_type(KIND) if device.type == KIND]
for device in prefs.devices:                           # the list also keeps devices of engines that ran before
    device.use = False
for device in here:
    device.use = True
used = [device.name for device in here]
scene.camera = bpy.data.objects[CAMERA]
scene.render.engine = "CYCLES"
scene.cycles.device, scene.cycles.denoising_use_gpu = ("GPU", True) if used else ("CPU", False)
scene.cycles.samples, scene.render.resolution_percentage = SAMPLES, PERCENT
scene.render.filepath = OUT
result = bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)
print(json.dumps({"started": sorted(result), "device": used or ["CPU: this machine has no " + KIND + " device"], "rendering": bpy.app.is_job_running("RENDER")}))
```

It answered `{"started": ["RUNNING_MODAL"], "device": ["Tesla T4"], "rendering": true}`, and the
window showed 25 of 128 samples after 2.8 s. A render window that is left open is saved with
the file and covers the viewport in the next session too: always ask the second script. For a
measured or a long render use `render.py`: it leaves the person's Blender free.

## Long renders: a job

`engine_exec` gives a command five minutes. Start anything that could pass four as a job
(SKILL.md, recipe 3), say how long you expect it to take, and ask again:

```text
selkies-modal-job status NAME                    NAME  running, then done  started <time>  <command>
selkies-modal-job log NAME | grep "^RENDER"      the RENDER line, once the job is done
```

A job counts as use of the engine, so the engine does not stop as idle under it. Its log is
`jobs/NAME/log` in the workspace. One job at a time: two renders share the same cores.

## Animation: frames, then a clip

Three moves cover most requests: the camera circles the subject, the camera walks toward or past
it, or the subject turns in front of the camera (a product; objects.md sets that turntable up).

**The orbit**, a full level turn around a point:

```python
# A camera that circles a point at eye height, level, once in a number of frames: the move for a building's
# fly-around. A pivot turns; the camera is its child and looks at it.
import bpy, json, math

scene = bpy.context.scene
CENTER, EYE, RADIUS = (2.3, 2.0), 1.6, 12.0     # meters: the point circled, the eye's height, the distance from it
FRAMES, FPS, START_BEARING = 96, 24, 135.0      # a full turn in 96 frames, starting south-east of the center
LENS, SHIFT = 28.0, 0.05


def fresh(name, data, coll):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    return obj


cameras = bpy.data.collections.get("Cameras") or bpy.data.collections.new("Cameras")
if cameras.name not in scene.collection.children:
    scene.collection.children.link(cameras)
pivot = fresh("Orbit pivot", None, cameras)
pivot.location = (*CENTER, EYE)
orbit = fresh("Orbit", bpy.data.cameras.new("Orbit"), cameras)
orbit.parent = pivot
orbit.location, orbit.rotation_euler = (0.0, -RADIUS, 0.0), (math.radians(90), 0.0, 0.0)
orbit.data.lens, orbit.data.shift_y, orbit.data.clip_end = LENS, SHIFT, 1000.0
scene.render.fps, scene.frame_start, scene.frame_end = FPS, 1, FRAMES
first = math.radians(180.0 - START_BEARING)
for frame, turn in ((1, 0.0), (FRAMES + 1, 2 * math.pi)):      # frame FRAMES + 1 repeats frame 1, so the clip loops
    pivot.rotation_euler = (0.0, 0.0, first + turn)
    pivot.keyframe_insert("rotation_euler", index=2, frame=frame)
# New keys ease in and out. An even turn needs them linear, and a key's curve is in the action's channelbag.
animation = pivot.animation_data
for fcurve in animation.action.layers[0].strips[0].channelbag(animation.action_slot).fcurves:
    for key in fcurve.keyframe_points:
        key.interpolation = "LINEAR"

bpy.ops.ed.undo_push(message="Orbit camera")
bpy.ops.wm.save_mainfile()
places = {}
for frame in (1, FRAMES // 4 + 1, FRAMES // 2 + 1):
    scene.frame_set(frame)
    places[frame] = [round(c, 2) for c in orbit.matrix_world.translation]
scene.frame_set(1)
print(json.dumps({"camera": orbit.name, "frames": [scene.frame_start, scene.frame_end, scene.render.fps], "camera_at_frame": places}))
```

It answers `{"camera": "Orbit", "frames": [1, 96, 24], "camera_at_frame": {"1": [10.79, -6.49,
1.6], "25": [10.79, 10.49, 1.6], "49": [-6.19, 10.49, 1.6]}}`: a quarter turn by frame 25.
New keys ease in and out: without the lines that set `LINEAR`, the camera had turned 56° by a
quarter of the time instead of 90°, and a loop would stutter at its seam.

**The walk**, through waypoints, each with the point the eye is on:

```python
# A camera that walks: it passes through waypoints at eye height, level, looking at a point given for each.
# The keys keep Blender's own curves, which ease into and out of the move. For an approach or a walk past a building.
import bpy, json, math

scene = bpy.context.scene
EYE, LENS, SHIFT = 1.6, 24.0, 0.04
FRAMES, FPS = 96, 24
WAYPOINTS = [  # where the eye is (x, y), and the point on the ground it looks toward (x, y), in meters
    ((1.05, -11.0), (2.3, 2.0)),
    ((1.05, -5.5), (2.3, 2.0)),
    ((5.2, -4.2), (2.6, 2.0)),
    ((9.2, 0.6), (3.2, 2.0)),
]

cameras = bpy.data.collections.get("Cameras") or bpy.data.collections.new("Cameras")
if cameras.name not in scene.collection.children:
    scene.collection.children.link(cameras)
old = bpy.data.objects.get("Walk")
if old is not None:
    bpy.data.objects.remove(old, do_unlink=True)
walk = bpy.data.objects.new("Walk", bpy.data.cameras.new("Walk"))
cameras.objects.link(walk)
walk.data.lens, walk.data.shift_y, walk.data.clip_start, walk.data.clip_end = LENS, SHIFT, 0.05, 1000.0
scene.render.fps, scene.frame_start, scene.frame_end = FPS, 1, FRAMES

heading = None
for index, (eye, toward) in enumerate(WAYPOINTS):
    frame = 1 + round(index * (FRAMES - 1) / (len(WAYPOINTS) - 1))
    turn = math.atan2(-(toward[0] - eye[0]), toward[1] - eye[1])
    if heading is not None:                        # the short way round, never a spin through 360 degrees
        while turn - heading > math.pi:
            turn -= 2 * math.pi
        while turn - heading < -math.pi:
            turn += 2 * math.pi
    heading = turn
    walk.location = (eye[0], eye[1], EYE)
    walk.rotation_euler = (math.radians(90), 0.0, heading)      # level: verticals stay vertical all the way
    walk.keyframe_insert("location", frame=frame)
    walk.keyframe_insert("rotation_euler", frame=frame)

bpy.ops.ed.undo_push(message="Walk camera")
bpy.ops.wm.save_mainfile()
places = {}
for frame in (1, FRAMES // 2, FRAMES):
    scene.frame_set(frame)
    places[frame] = {"eye": [round(c, 2) for c in walk.matrix_world.translation], "heading_deg": round(math.degrees(walk.rotation_euler.z), 1)}
scene.frame_set(1)
print(json.dumps({"camera": walk.name, "frames": [scene.frame_start, scene.frame_end, scene.render.fps], "at_frame": places}))
```

It answers `{"camera": "Walk", "frames": [1, 96, 24], "at_frame": {"1": {"eye": [1.05, -11.0,
1.6], "heading_deg": -5.5}, "48": {"eye": [2.3, -4.79, 1.6], "heading_deg": -1.8}, "96": {"eye":
[9.2, 0.6, 1.6], "heading_deg": 76.9}}}`. Here the keys keep their easing, which a walk wants.
Keep every waypoint outside the walls and on ground the eye could stand on: nothing stops the
camera from passing through a wall, and a closed door is one. Look at three frames as stills
before you render the range (`--camera Walk --frame 48 --percent 25` took 5 s on `cpu`).

**Render frames, not a movie file.** A job that stops is started again and renders only the
frames that are missing (`use_overwrite` is off in the script):

```bash
P="$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}"; selkies-modal-job start orbit-01 -- blender -b "$P/house.blend" --python-exit-code 1 --python "$P/scripts/render.py" -- --camera Orbit --out previews/house-orbit/frame --frames 1 96 --percent 50 --samples 32 --hide "Scale figure"
```

On a GPU tier add `--device OPTIX` to the script's parameters. **Then encode with the image's
FFmpeg** (libx264; a size with even numbers of pixels):

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && ffmpeg -y -loglevel error -framerate 24 -i previews/house-orbit/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart previews/house-orbit.mp4 && ls -l previews/house-orbit.mp4
```

- The 96 frames at 960 × 540 became an mp4 of 806 kB in under a second: H.264 at 24 frames a
  second, which FilmCraft imported and read as 4.0 s.
- **A moving camera needs fewer samples than a still**: 32 with the denoiser held up in these
  clips. Judge one frame as a still first, then quote the whole range from its time.
- **Length**: 96 frames at 24 a second is 4 seconds. A full turn in under 4 seconds feels
  rushed; a product's turntable reads well at 3 to 6 seconds.

## Measured times

Cycles with its denoiser; `t4` with `--device OPTIX`. The `cpu` column is one machine; on
another start the product draft took 15 s instead of 24.

| Render | Size | Samples | `cpu` | `t4` |
|---|---|---|---|---|
| Exterior, clay, draft | 960 × 540 | 64 | 18 s | 2.3 s |
| Exterior, materials, draft | 960 × 540 | 64 | 23 s | 2.6 s |
| Interior, materials, draft | 960 × 540 | 64 | 60 s | 4.2 s |
| Product, draft | 800 × 600 | 64 | 24 s | 2.8 s |
| Exterior, clay | 1920 × 1080 | 64 | 74 s | 5.5 s |
| Exterior, final | 1920 × 1080 | 128 | 177 s | 10.6 s |
| Interior, clay | 1920 × 1080 | 64 | 174 s | 11.1 s |
| Interior, final | 1920 × 1080 | 128 | 461 s | 24.1 s |
| Interior, evening, lamps on | 1920 × 1080 | 128 | 124 s at half size | 25.2 s |
| Product, final | 1600 × 1200 | 128 | 181 s | 10.2 s |
| Orbit, a frame | 960 × 540 | 32 | 11.9 s | 0.66 s |
| Turntable, a frame | 800 × 600 | 32 | 12.4 s | 0.73 s |
| Orbit, 96 frames, and its mp4 | 960 × 540 | 32 | about 19 min (24 frames took 285 s) | 63 s, then 0.9 s |
| Turntable, 72 frames, and its mp4 | 800 × 600 | 32 | about 15 min (12 frames took 149 s) | 53 s, then 0.5 s |

Each command also spends 2 to 5 s starting Blender and loading the file.

## Traps, each seen

- **A material or a world that nothing uses is gone after a save**, and a script that asks for
  it by name then fails: `KeyError: … key "Clay" not found`. The render script makes its own
  clay for that reason; set `use_fake_user = True` on anything else you keep for later.
- **The window-less Blender reads the file, not the window.** Changes that were not saved are
  not in the render.
- **A render called the plain way from the bridge** (`bpy.ops.render.render(write_still=True)`)
  returns only when the picture is done, and holds the person's Blender and the bridge until
  then: a long one runs the bridge's wait out and ends it (SKILL.md, recipe 2).
- **A ground that ends in sight** shows a dark band under the horizon. Make it reach: 300 m to
  each side put its edge on the horizon from eye height.
- **Two solids that share a face flicker or show black** where they overlap: window frame bars
  that ran through each other at the corners rendered as black squares. Butt parts, never
  overlap them, and give nested things different heights (archviz.md).
