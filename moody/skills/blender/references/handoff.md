<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Hand-offs

Work moves between engines as files in `handoff/<from app id>-to-<to app id>/` of the project's
folder. The rule that decides whether a file arrives is the studio skill's: an engine sees the
folder as it was when it started, so export, then either `engine_send(from_engine_id, path,
to_engine_id)` to a receiver that is already running or start the receiver, and confirm with
`engine_files(receiving_engine_id, "handoff/…")` before anything opens the file. Each route
below says what was run and what was not.

## CADCraft to Blender: a plan becomes walls

The recipe is the `cadcraft` skill's: open that skill and read its `references/handoff.md`,
"CADCraft to Blender: the recipe". In short, CADCraft's `export` writes the DXF into
`handoff/cadcraft-to-blender/`, and a script run through the bridge reads it with `ezdxf` (which
it installs into Blender's own modules on first use) and makes one mesh per layer, in meters, at
the plan's coordinates, extruding closed outlines by a height you give per layer.

Run again on Blender 5.2.4 for this skill, as that file gives it: a 4600 by 4000 mm room came
in as walls of 4.6 by 4.0 by 2.7 m in 0.14 s; the first run took 14 s with the install. What to
do with the walls next is archviz.md. The same file's plate recipe turns a flat part into an STL
(a 120 by 80 by 3 mm bracket: 2080 triangles, no non-manifold edge, 25,659.7 mm³).

## Blender to CADCraft: an outline to draw over

A model does not go back into a drawing, but a cut through it does: the closed outlines where a
horizontal plane meets the named objects, as polylines in millimeters, one layer per object.

```python
# Blender back to CADCraft: the footprint of objects, cut at a height, as closed polylines in a DXF in
# millimeters, one layer per object. It needs ezdxf in Blender's modules, which the CADCraft hand-off's import
# script installs. Run without the window:
#   blender -b house.blend --python-exit-code 1 --python scripts/outline_dxf.py -- 1.2 A-WALL "Roof slab"
import json, os, sys
import bpy, bmesh
from mathutils import Vector

mods = bpy.utils.user_resource("SCRIPTS", path="modules", create=True)
if mods not in sys.path:
    sys.path.append(mods)
import ezdxf
from ezdxf import units

arguments = sys.argv[sys.argv.index("--") + 1:]
height, names = float(arguments[0]), arguments[1:]
folder = os.path.join(os.path.dirname(bpy.data.filepath), "handoff", "blender-to-cadcraft")
os.makedirs(folder, exist_ok=True)
doc = ezdxf.new("R2018")
doc.units = units.MM
space, report = doc.modelspace(), {}
for name in names:
    obj = bpy.data.objects[name]
    bm = bmesh.new()
    bm.from_object(obj, bpy.context.evaluated_depsgraph_get())
    bmesh.ops.transform(bm, matrix=obj.matrix_world, verts=bm.verts)
    cut = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=Vector((0, 0, height)), plane_no=Vector((0, 0, 1)))
    edges = [g for g in cut["geom_cut"] if isinstance(g, bmesh.types.BMEdge)]
    layer = "B-" + name.upper().replace(" ", "-")
    doc.layers.add(layer)
    loops, left = [], set(edges)
    while left:                                        # walk the cut's edges into closed loops
        edge = left.pop()
        loop, end = [edge.verts[0], edge.verts[1]], edge.verts[1]
        while end != loop[0]:
            step = next((e for e in end.link_edges if e in left), None)
            if step is None:
                break
            left.discard(step)
            end = step.other_vert(end)
            loop.append(end)
        loops.append(loop[:-1] if loop[-1] == loop[0] else loop)
    for loop in loops:
        # A mesh holds single-precision numbers: rounded to a thousandth of a millimeter, 4600 is 4600 again
        space.add_lwpolyline([(round(v.co.x * 1000, 3), round(v.co.y * 1000, 3)) for v in loop], close=True, dxfattribs={"layer": layer})
    report[layer] = {"loops": len(loops), "points": [len(loop) for loop in loops]}
    bm.free()
out = os.path.join(folder, os.path.splitext(os.path.basename(bpy.data.filepath))[0] + "-outline.dxf")
doc.saveas(out)
print("OUTLINE " + json.dumps({"file": os.path.relpath(out, os.path.dirname(bpy.data.filepath)), "bytes": os.path.getsize(out), "cut_at_m": height, "layers": report}))
```

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && blender -b house.blend --python-exit-code 1 --python scripts/outline_dxf.py -- 1.2 A-WALL 2>&1 | grep "^OUTLINE\|rror:"
```

@@OUTLINE_NOTE@@

- The cut height has to pass through the object: a roof slab at 2.7 m gives no outline at 1.2.
- It needs `ezdxf`, so the CADCraft import has to have run once in this workspace.
- Layers are named `B-` and the object's name. In CADCraft, move them to the drawing's own
  layers or trace over them; nothing of the model's heights, materials, or openings' sills comes
  along.

## VectorCraft to Blender: a mark given depth

The `vectorcraft` skill's `references/delivery.md` has the recipe ("To Blender: the mark in
3D"): the one-color SVG arrives as curves through `bpy.ops.import_curve.svg`, is scaled to a real
size, extruded, and converted to a mesh. modeling.md has what an SVG import gives.

## PhotoCraft to Blender, and the library: pictures as textures

The `photocraft` skill has the export of a flat PNG at a texture's size into
`handoff/photocraft-to-blender/`. In Blender it becomes a material (look.md's `pictured`, at a
size in meters) or a picture on a plane (modeling.md). Pictures from the library arrive the same
way: `engine_import(engine_id, ["@tag"])` copies them to `library/<tag>/`.

## Blender to PhotoCraft: a render to retouch, a picture for a board

@@PHOTOCRAFT_SECTION@@

## Blender to FilmCraft: a clip or frames for a cut

@@FILMCRAFT_SECTION@@

## Blender to Unreal Engine

The road is in the `unreal` skill. An Unreal engine has its own Blender on its desktop, on the
same project folder, with a Send to Unreal panel (the 3D viewport's sidebar, tab Unreal) that
this engine's Blender does not have. So a model built here travels as its `.blend`, saved in the
project's folder: start the Unreal engine afterwards, open the file in that machine's Blender
(the same bridge: `engine_exec(unreal_id, "selkies-modal-blender 280 < …")`), and send it from
there. Before it leaves:

- Apply scale and join what should be one object (modeling.md); name objects as the level
  should have them.
- Give materials plain values or pictures: node textures do not travel (modeling.md).
- A GLB written here (`export_scene.gltf`, modeling.md) is the same data the panel sends; it is
  in meters and +Y up, and Unreal converts to its centimeters and +Z up, so a 4.6 m wall should
  arrive 460 units long.

Nothing of this route was run for this skill: no Unreal engine was started. The `cadcraft`
skill's hand-off says how far the panel itself was tested. Measure the mesh in the editor before
you say it arrived.

## A model for the conversation

A GLB in the project's folder is shown turning in a card: the `cards` skill's `model`
component, with the file named in the card's `media`. `print_check.py` (objects.md) writes one
for a single object; for several, select them and call the exporter of modeling.md.
