<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Products and single objects

A thing at its real size, photographed the way a studio would: a seamless backdrop, three
lights, a long lens, and a turntable; then a file a printer or a web page can use. The test
object is a vase 180 mm tall with a 3 mm wall, and everything below was run on it.

## First questions

- **Its real size.** One number is enough to start (its height); ask for the others as they
  matter. A product modeled at the wrong size lights wrong and prints wrong.
- **What it is made of**, in the words of look.md's table (glazed ceramic, anodized metal,
  matte plastic, wood).
- **What comes out**: a hero still, a turntable clip, a GLB for a page, an STL for a printer.
  For a print, also: which process (a filament printer wants walls of 0.8 mm or more and
  overhangs within 45° of vertical; resin takes 0.5 mm), and the printer's bed size.

## The scene

One script makes a new file with the product, the studio, and the turntable. The product here
is a profile turned on a lathe; for another, replace that block with your geometry (modeling.md)
and keep the rest, which sizes itself from the product's measured height and width.

```python
# A product at real size on a studio backdrop: a new file, millimeters on screen, a lathed vase with a wall
# thickness, a cove backdrop, three lights, a product lens with depth of field, and a turntable. Saved as product.blend.
import bpy, bmesh, json, math, os
from mathutils import Vector

P = os.path.join(os.environ["SELKIES_MODAL_WORKSPACE"], os.environ.get("SELKIES_MODAL_PROJECT", "projects/default"))
bpy.ops.wm.read_homefile(use_empty=True, load_ui=False)    # an empty scene; the window layout stays as it is
scene = bpy.context.scene                                  # the scene of the new file: earlier references are gone
scene.unit_settings.system, scene.unit_settings.scale_length, scene.unit_settings.length_unit = "METRIC", 1.0, "MILLIMETERS"

NAME, WALL = "Vase", 0.003                                 # 3 mm wall; one unit stays one meter
PROFILE_MM = [(0, 0), (38, 0), (42, 4), (46, 40), (40, 95), (24, 140), (22, 160), (30, 180)]   # radius, height
TURN_FRAMES, FPS = 72, 24


def collection(name):
    found = bpy.data.collections.new(name)
    scene.collection.children.link(found)
    return found


def material(name, color, roughness, **inputs):
    mat = bpy.data.materials.new(name)
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value, bsdf.inputs["Roughness"].default_value = (*color, 1.0), roughness
    for key, value in inputs.items():
        bsdf.inputs[key].default_value = value
    return mat


def aim(obj, target):
    """Turn an object so that it looks at a point: cameras and lights look down their own -Z."""
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


# The product: a profile turned about Z, given a wall, and smoothed. The modifiers stay live until export.
product = collection("Product")
mesh = bpy.data.meshes.new(NAME)
mesh.from_pydata([(r / 1000, 0.0, z / 1000) for r, z in PROFILE_MM], [(i, i + 1) for i in range(len(PROFILE_MM) - 1)], [])
vase = bpy.data.objects.new(NAME, mesh)
product.objects.link(vase)
screw = vase.modifiers.new("Lathe", "SCREW")
screw.axis, screw.steps, screw.render_steps, screw.use_merge_vertices, screw.merge_threshold = "Z", 64, 64, True, 0.0001
screw.use_normal_calculate = True
solid = vase.modifiers.new("Wall", "SOLIDIFY")
solid.thickness, solid.offset, solid.use_even_offset = WALL, -1.0, True     # inward, so the outside keeps its size
smooth = vase.modifiers.new("Smooth", "SUBSURF")
smooth.levels = smooth.render_levels = 2
vase.data.materials.append(material("Celadon glaze", (0.3, 0.55, 0.45), 0.12, **{"Coat Weight": 1.0, "Coat Roughness": 0.03}))
turntable = bpy.data.objects.new("Turntable", None)
product.objects.link(turntable)
vase.parent = turntable
for frame, angle in ((1, 0.0), (TURN_FRAMES + 1, 2 * math.pi)):
    turntable.rotation_euler = (0.0, 0.0, angle)
    turntable.keyframe_insert("rotation_euler", index=2, frame=frame)
animation = turntable.animation_data
for fcurve in animation.action.layers[0].strips[0].channelbag(animation.action_slot).fcurves:
    for key in fcurve.keyframe_points:
        key.interpolation = "LINEAR"
scene.frame_start, scene.frame_end, scene.render.fps = 1, TURN_FRAMES, FPS

# The size the lights and the camera are set by, measured on the surface the modifiers make: an object's
# `dimensions` are those of the cage under a Subdivision modifier, a few percent larger
bpy.context.view_layer.update()
measured = bmesh.new()
measured.from_object(vase, bpy.context.evaluated_depsgraph_get())
xs, ys, zs = zip(*[tuple(v.co) for v in measured.verts])
measured.free()
size = Vector((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
tall, wide = size.z, max(size.x, size.y)
center = Vector((0.0, 0.0, tall / 2))

# The backdrop: floor, a cove of a quarter circle, and a wall, as one smooth sheet with no visible corner
studio = collection("Studio")
depth, back, cove, high, half = 6 * wide + 0.6, 3 * wide + 0.3, 0.25, 4 * tall + 0.4, 6 * wide + 0.8
profile = [(-depth, 0.0), (back - cove, 0.0)]
profile += [(back - cove + cove * math.sin(a), cove - cove * math.cos(a)) for a in [math.radians(d) for d in range(10, 90, 10)]]
profile += [(back, cove), (back, high)]
bm = bmesh.new()
for y, z in profile:
    bm.verts.new((-half, y, z))
    bm.verts.new((half, y, z))
bm.verts.ensure_lookup_table()
for i in range(len(profile) - 1):
    bm.faces.new((bm.verts[2 * i], bm.verts[2 * i + 1], bm.verts[2 * i + 3], bm.verts[2 * i + 2]))
sheet = bpy.data.meshes.new("Backdrop")
bm.to_mesh(sheet)
bm.free()
sheet.shade_smooth()
backdrop = bpy.data.objects.new("Backdrop", sheet)
studio.objects.link(backdrop)
backdrop.data.materials.append(material("Backdrop paper", (0.78, 0.78, 0.76), 0.9))

# Three-point light: key high at camera left, fill low at camera right at a third of it, rim from behind
reach = 4 * tall + 0.5
for name, at, watts, side in (
    ("Key", (-0.75 * reach, -0.75 * reach, 1.1 * reach), 22.0 * reach ** 2, 2.5 * tall + 0.2),
    ("Fill", (0.9 * reach, -0.6 * reach, 0.45 * reach), 7.0 * reach ** 2, 4.0 * tall + 0.3),
    ("Rim", (0.45 * reach, 0.85 * reach, 1.2 * reach), 30.0 * reach ** 2, 1.5 * tall + 0.1),
):
    data = bpy.data.lights.new(name, "AREA")
    data.shape, data.size, data.energy = "SQUARE", side, watts
    light = bpy.data.objects.new(name, data)
    studio.objects.link(light)
    light.location = at
    aim(light, center)
world = bpy.data.worlds.new("Studio dark")
next(n for n in world.node_tree.nodes if n.bl_idname == "ShaderNodeBackground").inputs["Color"].default_value = (0.02, 0.02, 0.02, 1.0)
scene.world = world
scene.view_settings.exposure = 0.0

# The camera: a long lens from in front and a little above, focused on the product
camera = bpy.data.objects.new("Product camera", bpy.data.cameras.new("Product camera"))
studio.objects.link(camera)
camera.data.lens, camera.data.sensor_width = 85.0, 36.0
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1600, 1200, 100
distance = 1.25 * tall * camera.data.lens / (36.0 * 1200 / 1600)       # the product fills four fifths of the height
camera.location = (0.25 * distance, -0.93 * distance, tall / 2 + 0.28 * distance)
aim(camera, center)
camera.data.dof.use_dof, camera.data.dof.focus_object, camera.data.dof.aperture_fstop = True, vase, 8.0
camera.data.clip_start, camera.data.clip_end = 0.01, 50.0
scene.camera = camera
scene.render.engine = "CYCLES"
scene.cycles.samples = 128

for window in bpy.context.window_manager.windows:          # show the camera's view on the Screen
    for area in window.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(P, "product.blend"))
print(json.dumps({"file": bpy.data.filepath, "size_mm": [round(d * 1000, 1) for d in size], "camera_distance_m": round(distance, 3),
                  "modifiers": [m.type for m in vase.modifiers], "units": scene.unit_settings.length_unit,
                  "lights_w": {o.name: round(o.data.energy, 1) for o in studio.objects if o.type == "LIGHT"}}))
```

It answers `{"file": ".../product.blend", "size_mm": [88.5, 88.5, 179.7], "camera_distance_m":
@@PRODUCT_DISTANCE@@, "modifiers": ["SCREW", "SOLIDIFY", "SUBSURF"], "units": "MILLIMETERS", "lights_w": {"Key":
@@PRODUCT_LIGHTS@@}}`.

- **Millimeters are for the eye.** The file's unit stays the meter; the profile is given in
  millimeters and divided by 1000 as it becomes vertices.
- **The size is measured on the surface**, after the modifiers. The Subdivision modifier pulls
  the surface inside its cage: the profile's 92 mm became 88.5 mm. Where a size must be exact,
  measure, then scale the profile by the ratio and run again.
- **The wall is a modifier** (Solidify, inward), so the outside keeps the profile's size and the
  thickness is one number.
- **The backdrop is one sheet**: floor, a quarter-circle cove, and a wall, shaded smooth, so
  there is no horizon line behind the product. It is sized from the product.
- **Three lights, each aimed at the product's middle**: the key high at camera left, the fill
  low at camera right at a third of the key, the rim behind and above to lift the edge off the
  backdrop. Power scales with the square of their distance, so a larger product keeps the same
  exposure. For a darker, more dramatic picture halve the fill; for a catalog picture raise it
  to two thirds of the key.
- **85 mm from a little above**, focused on the product, f/8. Lower the f-number only for a
  detail.
- **Reflections**: a glossy product shows what surrounds it. The dark world here gives clean
  highlights from the three lights alone; look.md's panorama world (`studio`) adds soft
  reflections for metal and glass.

A draft, then the still:

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && blender -b product.blend --python-exit-code 1 --python scripts/render.py -- --out previews/product-draft.png --percent 50 2>&1 | grep "^RENDER\|rror:"
```

@@PRODUCT_NOTE@@ Read `brightness.mean`: a high-key picture on this backdrop sits near 0.7. If
it is over 0.85 the product is washing out: lower `--exposure` by a stop.

## The turntable

The script parents the product to an empty named `Turntable` that turns once in 72 frames, with
linear keys so the turn is even and the clip loops. Render the range and encode it (rendering.md
has the job form for a long one):

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && blender -b product.blend --python-exit-code 1 --python scripts/render.py -- --out previews/turntable/frame --frames 1 72 --percent 50 --samples 32 2>&1 | grep "^RENDER\|rror:" && ffmpeg -y -loglevel error -framerate 24 -i previews/turntable/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart previews/turntable.mp4 && ls -l previews/turntable.mp4
```

@@TURNTABLE_NOTE@@ A product that is the same all the way round (this vase) shows nothing by
turning: turn the lights' reflections instead by choosing an object with a handle, a label, or
an asymmetry, or show three stills.

## A file for a printer, a file for a page

"Printable" has a definition: one closed surface, facing out, with walls the process can make,
at the right size. The script checks the first three on the solid as it will be written and
writes both files:

```python
# Check an object for 3D printing and write it for a printer (STL, millimeters) and for a web viewer (GLB).
#   blender -b product.blend --python-exit-code 1 --python scripts/print_check.py -- Vase
# The check is of the solid as it will be written, modifiers applied. It prints PRINTCHECK and FILES.
import json, os, sys
import bpy, bmesh

name = sys.argv[sys.argv.index("--") + 1]
out = os.path.join(os.path.dirname(bpy.data.filepath), "exports")
os.makedirs(out, exist_ok=True)
obj = bpy.data.objects[name]
bpy.context.scene.frame_set(1)

bm = bmesh.new()
bm.from_object(obj, bpy.context.evaluated_depsgraph_get())
bmesh.ops.transform(bm, matrix=obj.matrix_world, verts=bm.verts)      # as it stands in the scene
bmesh.ops.triangulate(bm, faces=bm.faces[:])
seen, shells = set(), 0
for start in bm.verts:                                                # pieces that do not touch each other
    if start.index in seen:
        continue
    shells += 1
    stack = [start]
    while stack:
        vert = stack.pop()
        if vert.index not in seen:
            seen.add(vert.index)
            stack.extend(edge.other_vert(vert) for edge in vert.link_edges)
xs, ys, zs = zip(*[tuple(v.co) for v in bm.verts])
check = {
    "size_mm": [round((max(a) - min(a)) * 1000, 2) for a in (xs, ys, zs)],
    "volume_cm3": round(abs(bm.calc_volume(signed=True)) * 1e6, 2),
    "triangles": len(bm.faces),
    "non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold),   # 0 for a printable solid
    "open_edges": sum(1 for e in bm.edges if e.is_boundary),               # 0: no holes in the surface
    "zero_area_faces": sum(1 for f in bm.faces if f.calc_area() < 1e-12),
    "shells": shells,                                                      # 1 unless the parts are meant to be separate
    "normals_inward": bm.calc_volume(signed=True) < 0,                     # false: the surface faces out
}
bm.free()
check["printable"] = check["non_manifold_edges"] == 0 and check["open_edges"] == 0 and not check["normals_inward"]
print("PRINTCHECK " + json.dumps(check))

bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
base = os.path.join(out, name.lower().replace(" ", "-"))
bpy.ops.wm.stl_export(filepath=base + ".stl", export_selected_objects=True, apply_modifiers=True, global_scale=1000.0)   # meters to millimeters
bpy.ops.export_scene.gltf(filepath=base + ".glb", export_format="GLB", use_selection=True, export_apply=True, export_animations=False)
print("FILES " + json.dumps({f: os.path.getsize(os.path.join(out, f)) for f in sorted(os.listdir(out)) if f.startswith(os.path.basename(base) + ".")}))
```

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && blender -b product.blend --python-exit-code 1 --python scripts/print_check.py -- Vase 2>&1 | grep "^PRINTCHECK\|^FILES\|rror:"
```

```text
@@PRINTCHECK_ANSWER@@
```

Read it before you call anything printable:

| Field | Printable when | If not |
|---|---|---|
| `non_manifold_edges` | 0 | an edge has one face or three: a hole, an inner wall, or two shells that touch. Rebuild that part from a closed profile |
| `open_edges` | 0 | the surface has a hole: a profile that does not reach the axis, a face deleted |
| `normals_inward` | false | `bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])` on the mesh |
| `shells` | 1, unless parts are meant to be separate | separate parts print as separate bodies: join them with a Boolean `UNION`, or say they are several pieces |
| `size_mm` | what the person asked for, and inside the printer's bed | scale the source, not the export |
| `volume_cm3` | a sanity check, and the material: 127 cm³ of ceramic-like filament at 1.25 g/cm³ is about 160 g | |

Wall thickness and overhangs are not measured by the script. State the wall you modeled (the
Solidify thickness), and look at the form for faces that lean more than 45° from vertical with
nothing under them: the test vase's shoulder leans in above its widest point, which a filament
printer bridges poorly and a resin printer does well. Say so; do not call a form printable on
the topology alone.

- **STL** is in millimeters (`global_scale=1000.0`) and carries no unit, no color, no smoothing:
  1.5 MB for the vase's 29,696 triangles. Say "millimeters" with it.
- **GLB** is for the page: 536 kB here, with the base color and the clear coat. Show it turning
  in the conversation with a card's `model` component (the `cards` skill has the component;
  name the file in the card's `media`).
## A model someone brings: "make this printable"

A model from a download, a scan, or a generator is usually several closed parts pushed through
each other, some inside out. A slicer may accept it or print the overlaps hollow. The repair
that was run: read the file, apply its scale, turn every part to face out, fuse all parts into
one solid with a Boolean `UNION` over a collection, check before and after, and write an STL
and a `.blend`:

```python
# Make a model someone brought printable: read it, check it, fuse parts that pass through each other into one
# closed solid, check again, and write an STL in millimeters beside a .blend of the repaired model.
#   blender -b --python-exit-code 1 --python scripts/repair.py -- library/chair/01-chair.stl 0.001
# The second argument is meters per unit of the file: 0.001 for an STL in millimeters, 1 for one in meters.
import json, os, sys
import bpy, bmesh

source, to_meters = sys.argv[sys.argv.index("--") + 1], float(sys.argv[sys.argv.index("--") + 2])
P = os.path.join(os.environ["SELKIES_MODAL_WORKSPACE"], os.environ.get("SELKIES_MODAL_PROJECT", "projects/default"))
name = os.path.splitext(os.path.basename(source))[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def check(obj):
    """The print check of print_check.py, on one object."""
    bm = bmesh.new()
    bm.from_object(obj, bpy.context.evaluated_depsgraph_get())
    bmesh.ops.transform(bm, matrix=obj.matrix_world, verts=bm.verts)
    seen, shells = set(), 0
    for start in bm.verts:
        if start.index in seen:
            continue
        shells += 1
        stack = [start]
        while stack:
            vert = stack.pop()
            if vert.index not in seen:
                seen.add(vert.index)
                stack.extend(edge.other_vert(vert) for edge in vert.link_edges)
    xs, ys, zs = zip(*[tuple(v.co) for v in bm.verts])
    found = {"size_mm": [round((max(a) - min(a)) * 1000, 1) for a in (xs, ys, zs)], "volume_cm3": round(bm.calc_volume(signed=True) * 1e6, 1),
             "non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold), "open_edges": sum(1 for e in bm.edges if e.is_boundary), "shells": shells}
    bm.free()
    return found


bpy.ops.wm.stl_import(filepath=os.path.join(P, source), global_scale=to_meters)
model = bpy.context.selected_objects[0]
model.name = name
only(model)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)     # the factor is on the object until applied
report = {"arrived": check(model)}

# Each part by itself: closed or not, and facing out. Then all of them fused into the first.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.normals_make_consistent(inside=False)      # every part faces out, whichever way it arrived
bpy.ops.mesh.separate(type="LOOSE")
bpy.ops.object.mode_set(mode="OBJECT")
parts = sorted(bpy.context.selected_objects, key=lambda o: o.name)
report["parts"] = len(parts)
if len(parts) > 1:
    others = bpy.data.collections.new("Parts to fuse")
    scene.collection.children.link(others)
    for part in parts[1:]:
        for coll in list(part.users_collection):
            coll.objects.unlink(part)
        others.objects.link(part)
    model = parts[0]
    only(model)
    fuse = model.modifiers.new("Fuse", "BOOLEAN")
    fuse.operation, fuse.solver, fuse.operand_type, fuse.collection = "UNION", "EXACT", "COLLECTION", others
    bpy.ops.object.modifier_apply(modifier="Fuse")
    for part in parts[1:]:
        bpy.data.objects.remove(part, do_unlink=True)
    model.name = name
report["repaired"] = check(model)
report["printable"] = report["repaired"]["non_manifold_edges"] == 0 and report["repaired"]["open_edges"] == 0 and report["repaired"]["volume_cm3"] > 0

only(model)
out = os.path.join(P, "exports", name + "-print.stl")
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.wm.stl_export(filepath=out, export_selected_objects=True, global_scale=1000.0)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(P, name + "-print.blend"))
report["wrote"] = {os.path.relpath(out, P): os.path.getsize(out), name + "-print.blend": os.path.getsize(os.path.join(P, name + "-print.blend"))}
print("REPAIR " + json.dumps(report))
```

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && blender -b --python-exit-code 1 --python scripts/repair.py -- library/chair/01-chair.stl 0.001 2>&1 | grep "^REPAIR\|rror:"
```

Run on a chair of six boxes that pass through each other, its back inside out (420 by 420 by
900 mm):

```text
REPAIR {"arrived": {"size_mm": [420.0, 420.0, 900.0], "volume_cm3": 2376.0, "non_manifold_edges": 0, "open_edges": 0, "shells": 6}, "parts": 6, "repaired": {"size_mm": [420.0, 420.0, 900.0], "volume_cm3": 17032.0, "non_manifold_edges": 0, "open_edges": 0, "shells": 1}, "printable": true, "wrote": {"exports/01-chair-print.stl": 9884, "01-chair-print.blend": 88666}}
```

The volume is the proof: 17,032 cm³ is the six boxes' 17,496 less the 464 they shared, where
the file as it arrived summed to 2,376 because one part counted as negative.

- **Ask the unit before you read the file.** STL has none: 0.001 for millimeters, 1 for meters,
  0.0254 for inches. A chair that arrives 0.9 mm or 900 m tall was read with the wrong one.
- **This fixes parts that are each closed.** `open_edges` above 0 on arrival means a surface with
  a hole or with no thickness, which no union closes: say where (the count, and which part), and
  rebuild that part from a closed profile or give it a Solidify thickness. That case was not run.
- **Check the size against the printer's bed** (a common one is 220 by 220 by 250 mm): a 900 mm
  chair is a scale model or several pieces. Scale the object before the export and say the scale
  (1:5 makes it 180 mm tall).
- Walls of 0.8 mm or more for a filament printer (1.2 to 2 for strength), 0.5 mm for resin, and
  overhangs within 45° of vertical, as the `cadcraft` skill's checking rules have them.
