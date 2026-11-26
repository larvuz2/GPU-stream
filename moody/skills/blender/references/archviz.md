<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Architecture visualization

From a plan or a handful of dimensions to pictures a client can judge a building by. The test
building of this file is one room of 4.6 by 4.0 m drawn in CADCraft, with a door, two windows, a
flat roof, a site, and block trees; every script was run on it on a cloud engine, and the
sizes and times quoted are what came back.

## The order of work, and what the person sees

Each stage ends with something shown and a decision. Do not run ahead: a material on a massing
that is about to change is work thrown away.

| Stage | You do | You show | They decide |
|---|---|---|---|
| 1. Brief | collect what is fixed, ask for what a plan cannot say | the list of sizes, with the ones you assumed marked | the assumed sizes |
| 2. Walls | import the plan, or build from dimensions; check the sizes | the Screen, and the sizes read back | nothing yet |
| 3. Massing | openings, slabs, roof, site, block entourage | one or two clay views from eye height | the form: heights, roof, openings |
| 4. Light | sun and sky for the place, date, and hour | the same clay view at two hours, side by side | the hour |
| 5. Views | level cameras, exterior and interior | each view in clay | which views become final frames |
| 6. Materials | the palette, on the approved form | half-size drafts from the final cameras | the palette |
| 7. Final frames | full size as a job; an interior with portals | the stills | changes, or done |
| 8. Motion | an orbit, frames, a clip | the clip | done |

Keep the `.blend` saved after every stage, and say at each one what it cost and what is next.

## 1. What a plan cannot say

A plan has no heights and no site. Before you build, have these, given or assumed out loud:

| Size | Common value | Ask when |
|---|---|---|
| Ceiling height | 2.4 to 2.7 m; 2.7 here | always |
| Outer wall thickness | 0.2 to 0.4 m; from the plan when there is one | there is no plan |
| Door head | 2.1 m | it is not a standard door |
| Window sill and head | 0.9 m and 2.1 m; a picture window 0.4 and 2.3 | always: they make the facade |
| Roof | flat slab 0.25 m with a 0.5 m overhang, or the pitch | always |
| Floor above ground | 0.15 m, one step | the site slopes or the entry matters |
| North | +Y on the plan | the plan has a north arrow that is not up |
| Where on earth, which date and hour | 45° north, an equinox morning | the light matters to them, which it does |

Also ask which side the building is entered and seen from: it places the first camera.

## 2. Walls

**From a CADCraft plan.** The drawing is the source. Have the DXF exported into
`handoff/cadcraft-to-blender/` and import it with the script in the `cadcraft` skill's
`references/handoff.md` (section "CADCraft to Blender: the recipe"): it reads the file with
`ezdxf`, converts millimeters to meters, and extrudes the closed outlines of each layer you give
a height. As run on this building (the first run installs `ezdxf`, 14 s; later ones take a
second):

```text
A-WALL: 32 vertices, 20 faces, size (4.6, 4.0, 2.7) m
A-DOOR: 37 vertices, 0 faces, size (0.9, 1.1, 0.0) m
A-GLAZ: 6 vertices, 0 faces, size (1.2, 0.2, 0.0) m
A-FURN: 152 vertices, 82 faces, size (1.5, 2.0, 0.45) m
```

- The wall object's size has to equal the plan's overall dimensions in meters. Compare it with
  the drawing's dimension chain before anything else.
- The plan's walls stop at doors and windows, so the extrusion leaves each opening open from
  floor to ceiling: the shell script fills in above and below.
- The import saves `<name>.blend` and leaves Blender's start-up cube, light, and camera in the
  scene; the shell script removes them and saves under its own name.
- Where each opening is, read from the drawing (the `cadcraft` skill's `entities` on the door
  and glazing layers), not from the picture.

**From dimensions**, when there is no drawing: the outer rectangle, a thickness, a height, and
partitions as boxes become one wall solid with the name the shell script expects:

```python
# Walls from stated dimensions, with no drawing: a rectangle of outer faces, a wall thickness, and a height
# become one solid named A-WALL, where the shell script and the openings it cuts expect it.
import bpy, bmesh, json, os

P = os.path.join(os.environ["SELKIES_MODAL_WORKSPACE"], os.environ.get("SELKIES_MODAL_PROJECT", "projects/default"))
bpy.ops.wm.read_homefile(use_empty=True, load_ui=False)
scene = bpy.context.scene
scene.unit_settings.system, scene.unit_settings.scale_length, scene.unit_settings.length_unit = "METRIC", 1.0, "METERS"

OUTER = ((0.0, 0.0), (6.0, 4.5))     # meters: the outer faces' corners, x to the east and y to the north
THICK, HEIGHT = 0.3, 2.8
PARTITIONS = [((3.6, 0.3), (3.72, 4.2))]   # inner walls as boxes: corner to corner

(x0, y0), (x1, y1) = OUTER
bm = bmesh.new()
outer = [bm.verts.new(c) for c in ((x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0))]
inner = [bm.verts.new(c) for c in ((x0 + THICK, y0 + THICK, 0), (x1 - THICK, y0 + THICK, 0), (x1 - THICK, y1 - THICK, 0), (x0 + THICK, y1 - THICK, 0))]
for i in range(4):                                   # the ring between the two rectangles, as four quads
    j = (i + 1) % 4
    bm.faces.new((outer[i], outer[j], inner[j], inner[i]))
for (a0, b0), (a1, b1) in PARTITIONS:
    bm.faces.new([bm.verts.new(c) for c in ((a0, b0, 0), (a1, b0, 0), (a1, b1, 0), (a0, b1, 0))])
top = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])["geom"]
bmesh.ops.translate(bm, verts=[g for g in top if isinstance(g, bmesh.types.BMVert)], vec=(0, 0, HEIGHT))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
mesh = bpy.data.meshes.new("A-WALL")
bm.to_mesh(mesh)
volume, loose = bm.calc_volume(), sum(1 for e in bm.edges if not e.is_manifold)
bm.free()
walls = bpy.data.objects.new("A-WALL", mesh)
plan = bpy.data.collections.new("plan")
scene.collection.children.link(plan)
plan.objects.link(walls)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(P, "cabin.blend"))
print(json.dumps({"file": bpy.data.filepath, "size_m": [round(d, 3) for d in walls.dimensions], "volume_m3": round(volume, 3), "non_manifold_edges": loose}))
```

@@WALLS_NOTE@@ Every opening is then a cut (`CUT_OPENINGS` below, the door included, with
`PLAN_OPENINGS` empty).

## 3. The shell

One script takes the walls to a building: wall over and under the plan's openings, booleans
where the walls are whole, glass with frames, door leaves with thresholds, the slab, a floor
finish, a flat roof with overhangs, the site, and block entourage. Edit the numbers at its top;
run it again after any change, and after the plan was imported again.

```python
# From walls to a building shell at real size: wall over and under the openings a plan leaves, openings cut
# with booleans where the walls are whole, glass, frames, door leaves, slab, floor, roof, the site, and block
# entourage. Everything it makes is replaced when it runs again, so it follows walls that were imported again.
import bpy, bmesh, json, os
from mathutils import Vector

P = os.path.join(os.environ["SELKIES_MODAL_WORKSPACE"], os.environ.get("SELKIES_MODAL_PROJECT", "projects/default"))
scene = bpy.context.scene

SAVE_AS = "house.blend"
WALL = "A-WALL"              # the wall solid: the DXF import's, or the one walls.py made
HEIGHT, THICK = 2.7, 0.2     # meters: ceiling height and outer wall thickness
GROUND = -0.15               # the site's level below the floor
# Openings a plan already leaves open floor to ceiling: footprint corner to corner, sill and head heights
PLAN_OPENINGS = [
    {"name": "Door", "lo": (0.6, 0.0), "hi": (1.5, 0.2), "sill": 0.0, "head": 2.1, "glass": False},
    {"name": "Window north", "lo": (1.7, 3.8), "hi": (2.9, 4.0), "sill": 0.9, "head": 2.1, "glass": True},
]
# Openings to cut through whole walls: the same fields
CUT_OPENINGS = [{"name": "Window east", "lo": (4.4, 1.0), "hi": (4.6, 3.0), "sill": 0.4, "head": 2.3, "glass": True}]
ROOF = {"thick": 0.25, "west": 0.5, "east": 0.5, "south": 0.9, "north": 0.5}     # a flat slab and its overhangs
SITE = [("Step", (0.4, -0.45, GROUND), (1.7, 0.0, -0.02)), ("Path", (0.55, -6.0, GROUND), (1.55, -0.45, GROUND + 0.03))]
TREES = [((-3.2, 5.5), 1.7, 3.0), ((8.0, 6.5), 2.1, 3.6), ((-6.0, 0.5), 1.4, 2.6)]   # at (x, y), crown radius, trunk height
FIGURE_AT = (2.6, -2.2)      # a 1.75 m figure for scale


def collection(name, parent=None):
    found = bpy.data.collections.get(name)
    if found is None:
        found = bpy.data.collections.new(name)
        (parent or scene.collection).children.link(found)
    return found


def fresh(name, mesh, coll):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def box(name, lo, hi, coll):
    """A box between two corners in meters. Its vertices are at those coordinates, so its scale is 1."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=[h - l for l, h in zip(lo, hi)], verts=bm.verts)
    bmesh.ops.translate(bm, vec=[(l + h) / 2 for l, h in zip(lo, hi)], verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return fresh(name, mesh, coll)


def span(o):
    """An opening's extent along its wall, the wall's half thickness there, and a function placing boxes in it."""
    (x0, y0), (x1, y1) = o["lo"], o["hi"]
    along_y = (x1 - x0) < (y1 - y0)
    a0, a1, mid, half = (y0, y1, (x0 + x1) / 2, (x1 - x0) / 2) if along_y else (x0, x1, (y0 + y1) / 2, (y1 - y0) / 2)

    def at(b0, b1, depth, z0, z1):
        return ((mid - depth, b0, z0), (mid + depth, b1, z1)) if along_y else ((b0, mid - depth, z0), (b1, mid + depth, z1))

    return a0, a1, half, at


for name in ("Cube", "Light", "Camera"):          # the start-up scene's own
    stray = bpy.data.objects.get(name)
    if stray is not None:
        bpy.data.objects.remove(stray, do_unlink=True)

building = collection("Building")
walls, openings, floors, roof = (collection(n, building) for n in ("Walls", "Openings", "Floors", "Roof"))
cutters, site, entourage = collection("Cutters"), collection("Site"), collection("Entourage")
wall = bpy.data.objects[WALL]

for o in PLAN_OPENINGS:                           # the wall the plan's gap needs below the sill and above the head
    a0, a1, half, at = span(o)
    if o["sill"] > 0:
        box(f"Wall under {o['name']}", *at(a0, a1, half, 0.0, o["sill"]), walls)
    if o["head"] < HEIGHT:
        box(f"Wall over {o['name']}", *at(a0, a1, half, o["head"], HEIGHT), walls)

for o in CUT_OPENINGS:                            # a cutter through the wall; the boolean stays live, so it can move
    a0, a1, half, at = span(o)
    cutter = box(f"Cutter {o['name']}", *at(a0, a1, half + 0.1, o["sill"], o["head"]), cutters)
    cutter.display_type, cutter.hide_render = "WIRE", True
    old = wall.modifiers.get(o["name"])
    if old is not None:
        wall.modifiers.remove(old)
    cut = wall.modifiers.new(o["name"], "BOOLEAN")
    cut.operation, cut.solver, cut.object = "DIFFERENCE", "EXACT", cutter

for o in PLAN_OPENINGS + CUT_OPENINGS:
    a0, a1, half, at = span(o)
    sill, head, bar = o["sill"], o["head"], 0.05   # frame bars of 50 by 80 mm
    if o["glass"]:
        pane = box(f"Glass {o['name']}", *at(a0 + bar, a1 - bar, 0.006, sill + bar, head - bar), openings)
        pane.visible_shadow = False                # daylight passes it; reflection and refraction stay
        # Sill and head run through; the sides fit between them, so no two bars share a face
        bars = ((a0, a1, sill, sill + bar), (a0, a1, head - bar, head), (a0, a0 + bar, sill + bar, head - bar), (a1 - bar, a1, sill + bar, head - bar))
        for i, (b0, b1, z0, z1) in enumerate(bars):
            box(f"Frame {o['name']} {i + 1}", *at(b0, b1, 0.04, z0, z1), openings)
    else:
        box(f"Leaf {o['name']}", *at(a0 + 0.01, a1 - 0.01, 0.02, sill + 0.005, head - 0.005), openings)
        box(f"Threshold {o['name']}", *at(a0, a1, half, 0.0, 0.02), floors)

corners = [wall.matrix_world @ Vector(c) for c in wall.bound_box]
lo = Vector([min(c[i] for c in corners) for i in range(3)])
hi = Vector([max(c[i] for c in corners) for i in range(3)])
box("Slab", (lo.x, lo.y, GROUND - 0.15), (hi.x, hi.y, 0.0), floors)
box("Floor finish", (lo.x + THICK, lo.y + THICK, 0.0), (hi.x - THICK, hi.y - THICK, 0.02), floors)
box("Roof slab", (lo.x - ROOF["west"], lo.y - ROOF["south"], HEIGHT), (hi.x + ROOF["east"], hi.y + ROOF["north"], HEIGHT + ROOF["thick"]), roof)
for name, corner_lo, corner_hi in SITE:
    box(name, corner_lo, corner_hi, site)
cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
box("Ground", (cx - 300, cy - 300, GROUND - 0.5), (cx + 300, cy + 300, GROUND), site)   # far enough to meet the horizon

# Outlines nested on one layer (pillows on a bed) were extruded to one height, so their tops coincide and
# flicker in a render: raise every part but the largest.
furniture = bpy.data.objects.get("A-FURN")
if furniture is not None:
    bm = bmesh.new()
    bm.from_mesh(furniture.data)
    seen, parts = set(), []
    for start in bm.verts:
        if start in seen:
            continue
        stack, part = [start], []
        while stack:
            vert = stack.pop()
            if vert not in seen:
                seen.add(vert)
                part.append(vert)
                stack.extend(edge.other_vert(vert) for edge in vert.link_edges)
        parts.append(part)
    parts.sort(key=lambda part: (max(v.co.x for v in part) - min(v.co.x for v in part)) * (max(v.co.y for v in part) - min(v.co.y for v in part)))
    base_top = max(v.co.z for v in parts[-1])
    for part in parts[:-1]:
        for vert in part:
            if abs(vert.co.z - base_top) < 1e-6:
                vert.co.z += 0.12
    bm.to_mesh(furniture.data)
    bm.free()

# Block entourage: the image has no asset library, so trees and a figure are plain solids that give scale
for index, (at_xy, crown, trunk) in enumerate(TREES, 1):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.14, radius2=0.11, depth=trunk)
    bmesh.ops.translate(bm, vec=(0, 0, trunk / 2), verts=bm.verts)
    ball = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=crown)
    bmesh.ops.translate(bm, vec=(0, 0, trunk + crown * 0.6), verts=ball["verts"])
    mesh = bpy.data.meshes.new(f"Tree {index}")
    bm.to_mesh(mesh)
    bm.free()
    fresh(f"Tree {index}", mesh, entourage).location = (*at_xy, GROUND)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.2, radius2=0.16, depth=1.5)
bmesh.ops.translate(bm, vec=(0, 0, 0.75), verts=bm.verts)
head = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=0.12)
bmesh.ops.translate(bm, vec=(0, 0, 1.63), verts=head["verts"])
mesh = bpy.data.meshes.new("Scale figure")
bm.to_mesh(mesh)
bm.free()
fresh("Scale figure", mesh, entourage).location = (*FIGURE_AT, GROUND)

for name in ("A-DOOR", "A-GLAZ"):                 # the plan's flat wires: guides, not part of a render
    guide = bpy.data.objects.get(name)
    if guide is not None:
        guide.hide_render = True

bpy.context.view_layer.update()
bm = bmesh.new()
bm.from_object(wall, bpy.context.evaluated_depsgraph_get())
report = {
    "wall_size_m": [round(hi[i] - lo[i], 3) for i in range(3)],
    "wall_volume_m3": round(bm.calc_volume(), 3),
    "wall_non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold),
    "collections": {c.name: sorted(o.name for o in c.objects) for c in bpy.data.collections if c.objects},
    "scales_not_1": [o.name for o in scene.objects if any(abs(s - 1) > 1e-6 for s in o.scale)],
}
bm.free()
bpy.ops.ed.undo_push(message="Building shell")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(P, SAVE_AS))
print(json.dumps(report))
```

It answers, for the test building:

```text
@@SHELL_ANSWER@@
```

Check, before you show anything:

- **`wall_size_m`** equals the plan's overall size and the height.
- **`wall_volume_m3`** equals the plan's wall area times the height, less what was cut. Here
  CADCraft's `shapes` gave the two wall outlines 1.68 and 1.18 m²: 2.86 × 2.7 = 7.722 m³, less
  the east window's 0.2 × 2.0 × 1.9 = 0.76, is 6.962. A different number means an opening is in
  the wrong place or a height is wrong.
- **`wall_non_manifold_edges`** is 0, and **`scales_not_1`** is empty.

What the script decides, and why:

- **Booleans stay live.** A cut opening is a cutter in the `Cutters` collection, drawn as a
  wire and not rendered. Moving or resizing the cutter moves the window, so a design change is
  a number, not a rebuild. Exporters apply modifiers themselves (modeling.md).
- **Glass does not cast shadows** (`visible_shadow = False`): the pane still reflects and
  refracts, and daylight reaches the room. With ordinary glass the room is dark.
- **Nested outlines get different heights.** Pillows drawn on the bed's layer were extruded to
  the bed's height, and their coinciding tops flickered in the render; the script raises every
  part but the largest by 0.12 m.
- **The ground reaches the horizon** (300 m each way), or a dark band shows under the sky.
- **Entourage is blocks**, in one collection, so a final frame can leave the figure out
  (`--hide "Scale figure"`) and a white-model presentation can keep it.

## 4 and 5. Light and views

look.md has the script that sets sun, sky, exposure, and cameras, and the rules behind it. For
a building:

- **The first view is from where a visitor arrives**, at eye height, 1.5 to 2.5 building heights
  away, showing two faces (a corner view): one lit, one in shade.
- **Offer the hour as pictures.** Render the clay view at two or three hours (`--sun-elevation`
  moves the sun's height only; for another bearing run the script again with another
  `SOLAR_HOUR`) and show them side by side: people choose light by seeing it.
- **The interior view stands in a corner or a doorway**, 1.5 m up, 18 mm, looking along the
  room's diagonal toward a window, with both side walls in frame.
- **Show the massing in clay from the final cameras**:

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && for view in "Exterior south-east:exterior:-4.96" "Interior from door:interior:-1.7"; do IFS=: read camera name stops <<< "$view"; blender -b house.blend --python-exit-code 1 --python scripts/render.py -- --camera "$camera" --out "previews/$name-clay.png" --clay --percent 50 --exposure "$stops" 2>&1 | grep "^RENDER\|rror:"; done
```

@@CLAY_NOTE@@

## 6 to 8. Materials, final frames, motion

- **Materials** by the script of look.md, which assigns by the names the shell gave. Show half-size
  drafts from the final cameras; change a color or a roughness and render the draft again.
- **Final frames** at full size as jobs (rendering.md), the interior with the portals of look.md.
  Quote the time from the draft: four times it for the size, twice for 128 samples.
- **An orbit** (rendering.md) for a building that is seen from all sides; for one that has a
  front, a short move along it reads better than a full circle.

## When the design changes

The drawing changes first. Export the DXF under a new name, bring it to the engine
(`engine_send` if both run), run the import, then the shell script, then save. Cameras, lights,
and materials are not touched by either script, so the same render commands show the changed
building from the same views: put the two pictures side by side (`preview` with `compare`).

## What this engine cannot give a building

- **No people, trees, cars, or furniture** beyond blocks. A generated or photographed picture
  can stand behind a window or on a wall (modeling.md's picture on a plane); it does not turn
  with the camera.
- **No walls that know they are walls.** There are no building objects: a wall is a solid, a
  window is a hole with a pane, and a schedule is the drawing's job.
- **No sloped roof recipe was run.** A pitched roof is a profile extruded along the ridge
  (`bmesh.ops.extrude_face_region`, as `walls.py` does upward); build it, check its size, and say
  it is new ground.
- **Interiors are slow on `cpu`**: the test room's final frame took @@INTERIOR_CPU@@ there and
  @@INTERIOR_T4@@ on `t4` (rendering.md). Quote before you render.
