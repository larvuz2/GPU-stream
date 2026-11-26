<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Hand-offs: Blender, 3D printing, Unreal Engine

CADCraft draws in 2D. Height, material, light, and a camera are Blender's; a walkable scene is
Unreal's. The drawing stays the source: when the design changes, change the drawing, export
again, and import again (the import below replaces what it made last time).

## How files pass between engines

Every engine of a project opens the same project folder, and that is how work moves. One rule
decides whether it arrives, measured on the cloud machines:

- **An engine sees the folder as it was when the engine started.** A file CADCraft writes
  after Blender started is not visible to that Blender, however long you wait, and the reverse.
- **A newly started engine sees everything written about 15 seconds or more before its
  start** (a start 1 s after the write did not see the file; 13 s after did).

- **`engine_send(from_engine_id, path, to_engine_id)` carries a file or a folder into a running
  engine's folder**, at the same path, whole or not at all.

So the order is: export, save, then either `engine_send` the file to the receiving engine if it
is already running, or start the receiving engine. Before you import, confirm with
`engine_files(receiving_engine_id, "handoff/cadcraft-to-blender")` that the file is listed with
the size the export reported; if it is not (an engine started too soon after the export),
`engine_send` it. To send a later revision, export it under a new name and `engine_send` that:
the receiving engine keeps its own work and stays up. Never tell the person a file was handed
over on the strength of the sender's listing alone.

## CADCraft to Blender: the recipe

| | |
|---|---|
| **Format** | DXF, version 2018, from `export` (the working drawing's own format; nothing is converted) |
| **Reader** | `ezdxf` (MIT), installed once per workspace into Blender's user modules; Blender 5.2 ships no DXF importer. Its native SVG importer reads CADCraft's SVG, but that file has no layers, moves the origin, turns hatches into hundreds of strokes, and arrives at 1600 px wide whatever the drawing's size (a 4.6 m room came in 0.45 m wide), so it is the wrong road |
| **Units** | read from the file's `$INSUNITS` and converted to meters, Blender's unit: millimeters × 0.001, inches × 0.0254 |
| **Axes** | CAD X, Y → Blender X, Y; the plan lies on Z = 0 and heights go up +Z. No rotation: both are Z-up, right-handed. North on the plan is +Y |
| **Origin** | the drawing's 0,0 is Blender's world origin, so a second import lines up with the first |
| **Layers** | one mesh object per layer, named for it, in a collection named for the file |
| **Solids** | every closed outline on a layer you give a height becomes an extrusion; the plan has no heights, so you supply them per layer |
| **Result measured** | walls of the 4600 × 4000 mm room: 4.6 × 4.0 × 2.7 m in Blender, lowest z 0.0; import 0.11 s |

**What is lost on the way:** dimensions, text, leaders, tolerances, and hatches (annotation,
skipped on purpose: it stays on the sheet); line weights, linetypes, and layer colors; paper
space, title block, and viewports; constraints and parameters; block structure (block
references are placed and flattened, so ten chairs are ten copies of geometry, not instances);
curves (arcs and circles become straight segments within 0.5 mm). What the plan never held is
missing too: wall, sill, head, and ceiling heights, door leaves, floor and roof. You add those
in Blender from the brief, and you say which numbers were assumed.

### 1. In CADCraft

```text
app.save {}
export {"path": "handoff/cadcraft-to-blender/room.dxf"}      → {"bytes": 59772, …}
```

Keep geometry that must become solid as closed polylines on its own layer (walls on `A-WALL`,
furniture on `A-FURN`), and check with `shapes {"layer": "A-WALL"}` that each is closed. Tell
the person the heights you are about to use and ask for the ones the brief lacks.

### 2. Start Blender, then confirm the file

`engine_start("blender", "cpu")` builds the model and renders drafts; the `blender` skill says
which later steps want a GPU tier. Then `engine_files(blender_id, "handoff/cadcraft-to-blender")`.

Before the import, make sure Blender has this project's scene open, or an empty one (the
`blender` skill, "The engine, the folder, where Blender stands"). A Blender engine opens the
scene the workspace's last Blender closed with, whichever project that was, and the import
adds to whatever is open and saves it under this drawing's name.

### 3. Import

Blender has no command channel: it runs Python handed to `selkies-modal-blender` on standard
input. With `engine_exec(blender_id, command)`, write the script into the hand-off folder and
run it (the number is the seconds to wait for Blender, which also covers the first install of
`ezdxf`, about 12 s, and in each later session its first use, about 45 s while its modules
load from the workspace):

```bash
P="$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}"
cat > "$P/handoff/cadcraft-to-blender/import_dxf.py" <<'PY'
# Bring a CADCraft DXF into Blender at true size: closed outlines become solids as tall as their
# layer says, everything else stays a flat wire. One object per layer, in a collection named for
# the file; running it again replaces that collection.
import bpy, bmesh, os, subprocess, sys, time

FILE = "handoff/cadcraft-to-blender/room.dxf"
HEIGHTS = {"A-WALL": 2.7, "A-FURN": 0.45}   # meters, per layer: the plan holds no heights
SKIP = {"DIMENSION", "HATCH", "TEXT", "MTEXT", "MULTILEADER", "TOLERANCE", "VIEWPORT", "IMAGE"}

project = os.path.join(os.environ["SELKIES_MODAL_WORKSPACE"], os.environ.get("SELKIES_MODAL_PROJECT", "projects/default"))
mods = bpy.utils.user_resource("SCRIPTS", path="modules", create=True)
if mods not in sys.path:
    sys.path.append(mods)
try:
    import ezdxf
except ImportError:  # once per workspace: Blender's user modules are kept with it
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--target", mods, "ezdxf"], check=True)
    import ezdxf
from ezdxf import path as dxfpath, units

started = time.time()
doc = ezdxf.readfile(os.path.join(project, FILE))
to_m = units.conversion_factor(doc.units, units.M)   # millimeters: 0.001
sag = 0.0005 / to_m                                   # curves flattened to within half a millimeter


def entities(space):
    for e in space:
        if e.dxftype() == "INSERT":                   # a block reference: its contents, placed
            yield from entities(e.virtual_entities())
        elif e.dxftype() not in SKIP:
            yield e


scene = bpy.context.scene
scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1.0
name = os.path.splitext(os.path.basename(FILE))[0]
old = bpy.data.collections.get(name)
if old:
    for o in list(old.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(old)
coll = bpy.data.collections.new(name)
scene.collection.children.link(coll)

meshes = {}
for e in entities(doc.modelspace()):
    try:
        p = dxfpath.make_path(e)
    except TypeError:
        continue
    pts = [(v.x * to_m, v.y * to_m, v.z * to_m) for v in p.flattening(sag)]
    if len(pts) < 2:
        continue
    closed = p.is_closed and len(pts) > 3
    if closed:
        pts.pop()
    bm = meshes.setdefault(e.dxf.layer, bmesh.new())
    verts = [bm.verts.new(v) for v in pts]
    height = HEIGHTS.get(e.dxf.layer)
    if closed and height:
        face = bm.faces.new(verts)
        top = bmesh.ops.extrude_face_region(bm, geom=[face])["geom"]
        bmesh.ops.translate(bm, verts=[g for g in top if isinstance(g, bmesh.types.BMVert)], vec=(0, 0, height))
    else:
        for a, b in zip(verts, verts[1:] + (verts[:1] if closed else [])):
            bm.edges.new((a, b))

for layer, bm in meshes.items():
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(layer)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(layer, mesh)
    coll.objects.link(obj)
    print(f"{layer}: {len(mesh.vertices)} vertices, {len(mesh.polygons)} faces, size {tuple(round(d, 3) for d in obj.dimensions)} m")
print(f"{FILE}: units {units.decode(doc.units)}, x{to_m} to meters, {round(time.time() - started, 2)} s")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(project, name + ".blend"))
PY
selkies-modal-blender 300 < "$P/handoff/cadcraft-to-blender/import_dxf.py"
```

It prints one line per layer:

```text
A-WALL: 32 vertices, 20 faces, size (4.6, 4.0, 2.7) m
A-DOOR: 39 vertices, 0 faces, size (0.9, 1.1, 0.0) m
A-GLAZ: 6 vertices, 0 faces, size (1.2, 0.2, 0.0) m
A-FURN: 154 vertices, 82 faces, size (1.5, 2.0, 0.45) m
handoff/cadcraft-to-blender/room.dxf: units mm, x0.001 to meters, 0.11 s
```

### 4. Check, then build what the plan cannot say

- **Scale:** the wall object's size equals the drawing's overall dimensions in meters. If it is
  1000 times off, the drawing's `INSUNITS` is wrong: fix it in CADCraft (`units`), not here.
- **Orientation:** the door is where the plan has it seen from above (View, Top in Blender is
  the plan); the lowest z is 0.
- **Openings:** the plan's walls stop at doors and windows, so an extrusion leaves them open
  floor to ceiling. Add the wall below the sill and above the head as boxes over the opening's
  footprint (sill 0.9 m and head 2.1 m are common; ask), the same above a door, then a floor
  slab under the walls' bounding box, glass, and a ceiling if the camera looks up.
- The flat wires on `A-DOOR` and `A-GLAZ` are guides to model against; hide them for renders.
- `engine_screenshot(blender_id)` after framing the view, and say what was assumed.

Materials, light, cameras, and rendering are ordinary Blender work from here. Save the
`.blend` in the project folder.

## A flat part to a 3D-print file (STL)

CADCraft cannot write STL. A plate with holes becomes one in Blender: the closed outlines of
the part's layer, filled between the outer boundary and the holes, extruded by the thickness.
Measured on a 120 × 80 × 3 mm bracket with five holes: 2080 triangles, no non-manifold edge,
bounds 0 to 120, 80, 3 mm, volume 25,659.7 mm³ against 25,658.5 from the drawing's areas.

```bash
P="$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}"
cat > "$P/handoff/cadcraft-to-blender/plate_to_stl.py" <<'PY'
# A flat part from CADCraft to a printable solid: the closed outlines of one layer, holes cut,
# given a thickness, written as an STL in millimeters.
import bpy, bmesh, os, sys

FILE, LAYER, THICKNESS_MM = "handoff/cadcraft-to-blender/bracket.dxf", "OUTLINE", 3.0

project = os.path.join(os.environ["SELKIES_MODAL_WORKSPACE"], os.environ.get("SELKIES_MODAL_PROJECT", "projects/default"))
mods = bpy.utils.user_resource("SCRIPTS", path="modules", create=True)
if mods not in sys.path:
    sys.path.append(mods)
import ezdxf  # installed by import_dxf.py
from ezdxf import path as dxfpath, units

doc = ezdxf.readfile(os.path.join(project, FILE))
to_m = units.conversion_factor(doc.units, units.M)
bm = bmesh.new()
for e in doc.modelspace().query(f'*[layer=="{LAYER}"]'):
    p = dxfpath.make_path(e)
    if not p.is_closed:
        continue
    pts = [(v.x * to_m, v.y * to_m, 0) for v in p.flattening(0.01)][:-1]   # within 0.01 units of the curve
    verts = [bm.verts.new(v) for v in pts]
    for a, b in zip(verts, verts[1:] + verts[:1]):
        bm.edges.new((a, b))
bmesh.ops.triangle_fill(bm, edges=bm.edges[:], use_beauty=True)             # between the loops: holes stay open
top = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])["geom"]
bmesh.ops.translate(bm, verts=[g for g in top if isinstance(g, bmesh.types.BMVert)], vec=(0, 0, THICKNESS_MM / 1000))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bmesh.ops.triangulate(bm, faces=bm.faces[:])
print("volume mm3", round(bm.calc_volume() * 1e9, 1), "non-manifold edges", sum(1 for e in bm.edges if not e.is_manifold), "triangles", len(bm.faces))
name = os.path.splitext(os.path.basename(FILE))[0]
mesh = bpy.data.meshes.new(name)
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new(name, mesh)
bpy.context.scene.collection.objects.link(obj)
print("size m", tuple(round(d, 4) for d in obj.dimensions))
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
out = os.path.join(project, "exports", name + ".stl")
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.wm.stl_export(filepath=out, export_selected_objects=True, global_scale=1000)   # meters to millimeters
print("wrote", out, os.path.getsize(out), "bytes")
PY
selkies-modal-blender 300 < "$P/handoff/cadcraft-to-blender/plate_to_stl.py"
```

Before you call it printable: non-manifold edges 0; the volume within a tenth of a percent of
the outline's area minus the holes' areas, times the thickness (`shapes {"layer": "OUTLINE"}`
in CADCraft gives each area); the size in millimeters what the drawing says; the printing rules
in checking.md. STL carries no unit: say "millimeters" with the file. A part that is more than
an extruded outline (bosses, pockets, chamfers, a bend) is modeled in Blender from the
drawing's views, or belongs in a solid modeler; say so instead of forcing it.

For laser or CNC cutting no hand-off is needed: the cutting file is a DXF straight from
CADCraft (checking.md).

## Blender back to CADCraft

Blender has no DXF exporter in this build, but a model's outline comes back as a drawing: the
`blender` skill's hand-off reference has a script that cuts the model at a height and writes
the cut as closed polylines in millimeters into `handoff/blender-to-cadcraft/`. Opened here
(`open`), those were closed polylines whose areas `shapes` measured. Use it to bring a changed
footprint back as a layer to draw over; the drawing stays the source, so the change is then
made here, dimensioned, and sent out again. A top view can also come back as a rendered image
attached under the drawing (`imageattach` with a known `width` in drawing units) for tracing.

## On to Unreal Engine

An Unreal engine is one machine with the Unreal Editor and its own Blender, on the same
project folder (the unreal skill). The road from a drawing is drawing → Blender → Unreal:

1. Export the DXF and save, as above.
2. `engine_start("unreal", …)` after the export (the same rule: it sees the folder as of its
   start), or `engine_send` the DXF to an Unreal engine that is already running. It needs a GPU
   tier, and the editor itself needs the person's Epic link.
3. In that machine's Blender (`engine_exec(unreal_id, "selkies-modal-blender 300 < …")`), run
   the import script: the model is built there, at true size.
4. **Send to Unreal** (Blender's 3D viewport sidebar, tab Unreal; operator
   `moody.send_to_unreal`) exports the selection as glTF binary into the project's `bridge/`
   folder with a manifest and asks the editor to import it into `/Game/Blender/<name>`. glTF
   is meters and +Y up by definition and Unreal converts to its centimeters and Z-up, so a
   4.6 m wall should arrive 460 units long.

How far this is built: the DXF import is verified in Blender 5.2.4. Send to Unreal is tested
against a stand-in for the editor's Remote Control API, not yet against a running editor, and
the drawing-to-Unreal chain as a whole has not been run. Treat step 4 as an attempt: after it,
measure the mesh in the editor (its bounds should be the drawing's size × 100) and show the
person the Unreal view before saying it arrived. Before sending, apply scale and join or name
the objects as the level should have them; give walls real thickness (they have it) and check
normals face outward (the import recalculates them).
