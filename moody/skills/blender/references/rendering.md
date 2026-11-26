<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Rendering

One script renders everything: stills and frames, clay and materials, CPU and GPU. It was run
as written on a `cpu` engine (2 cores, 4 at most, no GPU) and on a `t4` engine (a Tesla T4),
and every time below is from its own RENDER line.

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
        try:
            prefs.compute_device_type = args.device
            prefs.refresh_devices()
            for device in prefs.devices:
                device.use = device.type == args.device
            found = [device.name for device in prefs.devices if device.use]
        except TypeError:                          # this machine's Cycles knows no such device type
            found = []
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
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && blender -b house.blend --python-exit-code 1 --python scripts/render.py -- --camera "Exterior south-east" --out previews/exterior-final.png --samples 128 --hide "Scale figure" 2>&1 | grep "^RENDER\|rror:"
```

| Parameter | Meaning |
|---|---|
| `--camera NAME` | the camera object to render from; left out, the scene's |
| `--out PATH` | where the picture goes, relative to the `.blend`. With `--frames`, the folder and name before the number: `previews/orbit/frame` writes `frame_0001.png` and on |
| `--device CPU\|OPTIX\|CUDA` | where Cycles renders. A GPU that is not there falls back to the CPU, and the line says so |
| `--samples N` | 64 unless given: enough for a draft. Sampling stops early where a pixel is clean |
| `--percent N` | of the scene's resolution: 50 for drafts |
| `--clay` | every surface in one matte gray, objects named `Glass…` left out |
| `--frames FIRST LAST` | an animation's range instead of one still |
| `--exposure STOPS` | in place of the scene's, for an interior from a file exposed for outdoors |
| `--hide PREFIX …` | leave out objects by the start of their name |
| `--show COLLECTION …` | render collections the file hides, such as `"Lights evening"` |
| `--sun-elevation DEGREES` | move the sky's sun for this render |
| `--engine BLENDER_EEVEE` | EEVEE in place of Cycles (see below before you use it) |
| `--no-denoise` | leave the grain in |

The line it prints, here from the `t4` engine:

```text
@@RENDER_LINE_T4@@
```

- `device` is what Cycles was set to use, by name. `gpu_peak` is what the graphics driver
  reported while the picture rendered: a GPU render shows the GPU busy and its memory in use.
  That pair is the proof of where a render ran; report it with the time.
- `brightness` is read from the written file: `mean` of its pixels from 0 to 1, the share
  `clipped` at white and at `black`. A daylight exterior came out near 0.6 to 0.7; under 0.3 is
  too dark, and `clipped` over 0.02 is burnt. Change `--exposure` by whole stops and render the
  draft again.
- `--python-exit-code 1` makes a script that raises end Blender with status 1; without it a
  failed render still exits 0. The file is read from disk: save in the window first.
- On a machine without a GPU, Blender prints `cycles | WARNING CUEW initialization failed`
  as it starts. It means there is no CUDA to load, and nothing else.

## Which engine and which device

@@DEVICE_SECTION@@

## Samples, denoising, size

- **Drafts: 64 samples at 50%.** They answer form, light, framing, and material. **Finals: 128**
  for an exterior and for a product, and for an interior as well once it has portals; the
  denoiser (OpenImageDenoise, on by default in the script) takes the rest of the grain.
- **Sampling is adaptive** (noise threshold 0.01): a flat wall stops early, so doubling
  `--samples` costs less than double.
- **Size is the scene's** (`scene.render.resolution_x`, `resolution_y`; 1920 by 1080 here)
  times `--percent`. Time grows with the pixels: four times from 50% to 100%.
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

It answers `{"started": ["RUNNING_MODAL"], "rendering": true}` at once. The render window
shows the frame, the time, and the sample count as it goes (`Sample 13/64`), and the bridge
keeps answering. Ask whether it is done, which also clears the window away:

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

`{"rendering": false, "written": true, "windows": 1}` when it is. A render started this way
uses the window's settings and the CPU unless the person's preferences name a GPU; for a
measured or a long render use the script. A render window that is left open is saved with the
file and covers the viewport in the next session too: close it.

## Long renders: a job

`engine_exec` gives a command five minutes. Start anything that could pass four as a job
(SKILL.md, recipe 3), say how long you expect it to take, and ask again:

```text
selkies-modal-job status NAME        running, done, or failed (exit N)
selkies-modal-job log NAME | grep "^RENDER"
```

A job counts as use of the engine, so the engine does not stop as idle under it. Its log is
`jobs/NAME/log` in the workspace. One job at a time: two renders share the same cores.

## Animation: frames, then a clip

Two moves cover most requests: the camera circles the subject (a building), or the subject
turns in front of the camera (a product; objects.md sets that turntable up). The orbit:

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

- **New keys ease in and out.** Without the three lines that set `LINEAR`, the camera had turned
  56° by a quarter of the time instead of 90°, and a loop would stutter at its seam.
- **Render frames, not a movie file.** A job that stops is started again and renders only the
  frames that are missing (`use_overwrite` off in the script):

```bash
P="$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}"; selkies-modal-job start orbit-01 -- blender -b "$P/house.blend" --python-exit-code 1 --python "$P/scripts/render.py" -- --camera Orbit --out previews/house-orbit/frame --frames 1 96 --percent 50 --samples 32 --hide "Scale figure"
```

- **Then encode with the image's FFmpeg** (libx264; a size with even numbers of pixels):

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && ffmpeg -y -loglevel error -framerate 24 -i previews/house-orbit/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart previews/house-orbit.mp4 && ls -l previews/house-orbit.mp4
```

- **A moving camera needs fewer samples than a still**: 32 with the denoiser held up in the
  test clips. Judge one frame as a still first, then quote the whole range from its time.
- **Length**: 96 frames at 24 a second is 4 seconds. A full turn in under 4 seconds feels
  rushed; a turntable of a product reads well at 3 to 6 seconds.

## Measured times

@@TIMES_TABLE@@

## Traps, each seen

- **A material or a world that nothing uses is gone after a save**, and the window-less render
  then fails on its name: `KeyError: … key "Clay" not found`. The script makes its own clay for
  that reason; set `use_fake_user = True` on anything else you keep for later.
- **The window-less Blender reads the file, not the window.** Changes that were not saved are
  not in the render.
- **A render called the plain way from the bridge** (`bpy.ops.render.render(write_still=True)`)
  holds the person's Blender, and the bridge, until it is done: a long one runs the bridge's wait
  out and ends it (SKILL.md, recipe 2).
- **A ground that ends in sight** shows a dark band under the horizon. Make it reach: 300 m to
  each side put its edge on the horizon from eye height.
- **Coplanar faces flicker** (two solids whose tops coincide). Give nested things different
  heights (archviz.md).
