<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Geometry at real size

How to make, change, measure, bring in, and write out geometry in Blender 5.2.4 from a script.
Every line here was run on a cloud engine, through the bridge or in a Blender without a window,
and each result quoted is what came back. The building of archviz.md and the product of
objects.md are these moves put together.

## Units and axes

- **One unit is one meter.** Leave `scene.unit_settings.scale_length` at 1.0. For a product, set
  `scene.unit_settings.length_unit = "MILLIMETERS"`: the window then reads 180 mm where the
  data says 0.18, and nothing else changes. Lights, camera clipping, glTF, FBX, and USD all
  assume meters; STL has no unit, so it is written with `global_scale=1000.0` for a printer.
- **+Z is up; X is east, Y is north** for a building, the convention of the CADCraft import, so
  a plan's 0,0 is the world's origin and a second import lands on the first.
- **Keep the origin near the work.** A building at its plan coordinates, a product standing on
  the origin at Z = 0.

## Collections and names

A collection is a folder of objects; a script makes one if it is not there, and nests it:

```text
found = bpy.data.collections.get(name) or bpy.data.collections.new(name)
scene.collection.children.link(found)             under the scene; parent.children.link(found) to nest
coll.objects.link(obj)                            an object is in the scene only once it is linked
for c in list(obj.users_collection): c.objects.unlink(obj)      then link elsewhere: a move
coll.hide_render = True                           everything in it is left out of renders
```

Name by what a thing is, most general first (`Wall over Door`, `Frame Window east 2`, `Glass
Window east`): materials, hiding, and exports here all select by the start of the name.

## Making geometry

**From coordinates** (preferred: the object's scale stays 1 and no context is needed). The `box`
of archviz.md's script is the pattern: a `bmesh` cube scaled and moved to two corners, written to
a mesh, the object linked to a collection. For an outline, `mesh.from_pydata(vertices, edges,
faces)`; for a profile turned on a lathe or pushed up, the Screw modifier and
`bmesh.ops.extrude_face_region` (objects.md, archviz.md's `walls.py`).

**From an operator**, as a person would. The new object is selected and active:

```text
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.5))
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.15, depth=1.0, location=(0, 0, 0.2))
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.25, location=(0, 6, 0.25))
bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.2, depth=0.5, location=(0, 6, 1.75))
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.5, 3.0, 1.0), rotation=(math.radians(90), 0, 0))
obj = bpy.context.active_object
```

An operator that works on "the object" needs it selected and active first:

```text
bpy.ops.object.select_all(action="DESELECT"); obj.select_set(True); bpy.context.view_layer.objects.active = obj
```

**A tube or a rail** is a curve with a round section, converted when it has to be a mesh:

```text
curve = bpy.data.curves.new("Rail", "CURVE"); curve.dimensions, curve.bevel_depth, curve.bevel_resolution = "3D", 0.01, 4
spline = curve.splines.new("POLY"); spline.points.add(2)         three points; each point.co is (x, y, z, 1.0)
bpy.ops.object.convert(target="MESH")                             a 20 mm tube: 1.21 by 0.02 by 0.91 m as run
```

## Scale, and why to apply it

Setting `obj.scale = (2.0, 1.0, 0.4)` on a 1 m cube changes how it is drawn, not its mesh, and a
bevel, a boolean, a texture in object coordinates, and some exporters then work in the stretched
space. Apply it:

```text
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
```

As run: scale (2.0, 1.0, 0.4) became (1, 1, 1) with dimensions 2.0 by 1.0 by 0.4 m. Two traps:

- `obj.dimensions` read right after setting the scale still said 1.0 by 1.0 by 1.0. Call
  `bpy.context.view_layer.update()` before you read sizes back.
- On a curve, applying scale also scales its extrusion and bevel (the `vectorcraft` skill's
  hand-off has the case). Convert to a mesh first.

## Modifiers

A modifier changes what an object evaluates to and leaves its mesh alone, so a number can still
change. Keep them live while designing; apply for a boolean's cutter you will delete, for STL,
and where an exporter does not apply them itself.

```text
bevel = obj.modifiers.new("Edges", "BEVEL"); bevel.width, bevel.segments, bevel.limit_method, bevel.angle_limit = 0.02, 3, "ANGLE", math.radians(30)
array = obj.modifiers.new("Row", "ARRAY"); array.count, array.use_relative_offset, array.use_constant_offset = 3, False, True; array.constant_offset_displace = (2.5, 0.0, 0.0)
mirror = obj.modifiers.new("Mirror", "MIRROR"); mirror.use_axis = (True, False, False); mirror.mirror_object = an_empty_at_the_mirror_plane
solid = obj.modifiers.new("Thickness", "SOLIDIFY"); solid.thickness = 0.018            also .offset (-1 inward, 1 outward), .use_even_offset
screw = obj.modifiers.new("Lathe", "SCREW"); screw.axis, screw.steps, screw.render_steps, screw.use_merge_vertices = "Z", 64, 64, True
smooth = obj.modifiers.new("Smooth", "SUBSURF"); smooth.levels = smooth.render_levels = 2
cut = obj.modifiers.new("Hole", "BOOLEAN"); cut.operation, cut.solver, cut.object = "DIFFERENCE", "EXACT", cutter
bpy.ops.object.modifier_apply(modifier="Edges")                    the object selected and active
```

As run on the 2.0 by 1.0 by 0.4 m block: bevel and array of three, 2.5 m apart, evaluated to 7.0
by 1.0 by 0.4 m and 288 vertices from 8; applied, the mesh had those 288. A 1 m panel mirrored
about the world's YZ plane and given 18 mm came to 2.0 by 1.0 by 0.018 m.

**Smooth shading** without rounding hard edges: `bpy.ops.object.shade_auto_smooth(angle=math.radians(30))`
on the active object (it adds a Smooth by Angle modifier, type `NODES`); `mesh.shade_smooth()`
for a form that is all curve.

## Booleans for openings

A hole is a cutter object and a Boolean modifier set to `DIFFERENCE` with the `EXACT` solver
(the others are `FLOAT` and `MANIFOLD`):

- Let the cutter pass clean through: 0.1 m beyond each face. A cutter face that lies in a
  wall's face leaves slivers.
- Keep it live for a design that still moves: the cutter stays, drawn as a wire and left out of
  renders (`cutter.display_type, cutter.hide_render = "WIRE", True`), and moving it moves the hole.
- Check the result by volume: a 0.3 m hole through the 0.4 m block took 0.0282 m³ of 2.396
  (π × 0.15² × 0.4 = 0.0283), with no non-manifold edge. The east window of archviz.md's
  building took 0.76 m³ from walls of 7.722, as 0.2 × 2.0 × 1.9 says it must.

## Measuring

What an object evaluates to, in the world, with its modifiers:

```text
bm = bmesh.new(); bm.from_object(obj, bpy.context.evaluated_depsgraph_get())
bmesh.ops.transform(bm, matrix=obj.matrix_world, verts=bm.verts)
xs, ys, zs = zip(*[tuple(v.co) for v in bm.verts])                 size = max - min on each axis, in meters
bm.calc_volume()                                                    cubic meters, for a closed mesh
sum(1 for e in bm.edges if not e.is_manifold)                       0 for a solid; bm.free() when done
```

`obj.dimensions` is quicker and right for plain meshes. Under a Subdivision modifier it is the
size of the cage: the vase of objects.md read 92.0 by 181.1 mm that way, and its surface, which
is what renders and prints, is 88.5 by 179.7 mm.

Joining and re-centering: with several objects selected, `bpy.ops.object.join()` merges them
into the active one; `bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")` puts an
object's origin at the middle of its bounds.

## Bringing geometry in

| From | Call | What arrives |
|---|---|---|
| DXF (CADCraft) | the `cadcraft` skill's `import_dxf.py`, which reads it with `ezdxf` | one mesh per layer in a collection named for the file, in meters at the plan's coordinates; closed outlines extruded by a height you give per layer; no annotation. Blender has no DXF importer of its own |
| SVG | `bpy.ops.import_curve.svg(filepath=…)` | one curve per shape in a collection named for the file, flat, tiny: CADCraft's SVG of a 4.6 m room came in as 86 curves 0.45 m wide. Scale it by one known length. For a plan, take the DXF |
| glTF, GLB | `bpy.ops.import_scene.gltf(filepath=…)` | meshes in meters, +Z up, with Principled materials and their pictures |
| OBJ | `bpy.ops.wm.obj_import(filepath=…)` | a mesh with its `.mtl` colors; stood up by a 90° rotation on the object: apply it |
| FBX | `bpy.ops.wm.fbx_import(filepath=…)` | meshes, materials' base colors |
| STL | `bpy.ops.wm.stl_import(filepath=…, global_scale=0.001)` | one mesh, no material, flat shaded; the factor stays on the object as scale 0.001: apply it |
| PLY | `bpy.ops.wm.ply_import(filepath=…)` | one mesh, no material |
| USD | `bpy.ops.wm.usd_import(filepath=…)` | the hierarchy with its empties, and an extra empty named `_materials` |
| Alembic | `bpy.ops.wm.alembic_import(filepath=…)` | the hierarchy, no materials |
| A picture as a surface | `bpy.ops.image.import_as_mesh_planes(files=[{"name": "plan.png"}], directory=…, shader="PRINCIPLED", size_mode="ABSOLUTE", height=1.0, align_axis="+Z")` | a plane with the picture as its material and one UV map, 1 m high: scale it to the real width (`plane.scale = (f, f, f)` with `f = width_m / plane.dimensions.x`) |
| A picture to model over | an empty that shows it, below | visible in the viewport, never rendered |

**An import leaves only what it brought selected.** Select your own objects again before an
export of the selection. A reference picture is an empty that displays it:

```text
ref = bpy.data.objects.new("Reference plan", None)
ref.empty_display_type, ref.data = "IMAGE", bpy.data.images.load(path, check_existing=True)
ref.empty_display_size, ref.empty_image_offset = width_m, (0.0, 0.0)
ref.color[3], ref.use_empty_image_alpha = 0.5, True               half transparent
scene.collection.objects.link(ref)
```

How large the empty draws the picture was not measured here: set it, then check it in the
viewport against one known length before you model over it. Never take a size from a picture
without one known dimension in it; where the size matters, use the plane, whose size you read back.

## Writing geometry out

Select what goes (`obj.select_set(True)`), then one call. Each row was written from the vase of
objects.md (a lathe, a 3 mm wall, and a Subdivision modifier, one glazed material with a clear
coat; surface 88.5 by 88.5 by 179.7 mm, 14,850 vertices) and read back:

| Format | Call | Size | Read back as | Kept | Lost |
|---|---|---|---|---|---|
| GLB | `bpy.ops.export_scene.gltf(filepath=…, export_format="GLB", use_selection=True, export_apply=True, export_animations=False)` | 536 kB | the same surface, smooth | size, base color, clear coat | modifiers (applied), procedural textures |
| glTF and `.bin` | the same with `export_format="GLTF_SEPARATE"` | 2 kB + 535 kB | as GLB | as GLB | as GLB |
| OBJ and `.mtl` | `bpy.ops.wm.obj_export(filepath=…, export_selected_objects=True, apply_modifiers=True, export_materials=True)` | 1.5 MB | the surface, upright under a 90° rotation on the object | size, base color | clear coat, everything else of the material |
| FBX | `bpy.ops.export_scene.fbx(filepath=…, use_selection=True, use_mesh_modifiers=True, bake_anim=False)` | 450 kB | the surface, smooth | size, base color | clear coat |
| STL | `bpy.ops.wm.stl_export(filepath=…, export_selected_objects=True, apply_modifiers=True, global_scale=1000.0)` | 1.5 MB | triangles, flat shaded | size (in millimeters) | materials, smoothing, units, names |
| PLY | `bpy.ops.wm.ply_export(filepath=…, export_selected_objects=True, apply_modifiers=True)` | 431 kB | triangles | size | materials, smoothing |
| USD | `bpy.ops.wm.usd_export(filepath=…, selected_objects_only=True, export_animation=False)` | 14 kB | the cage of 898 vertices with its parent | base color, clear coat, the hierarchy | the Subdivision modifier's surface: the mesh read back is the cage, 92 by 181.1 mm, with no modifier on it |
| Alembic | `bpy.ops.wm.alembic_export(filepath=…, selected=True, start=1, end=1)` | 32 kB | the cage of 898 vertices with its parent | the hierarchy | materials, the Subdivision's surface |

- **For a printer: STL in millimeters**, after the check of objects.md. Say "millimeters" with
  the file: STL does not.
- **For the web, a card in the conversation, and a game engine: GLB.** It is meters and +Y up by
  definition and the exporter converts. For a whole scene:

```python
# Write the scene's model as one GLB, for a web viewer, a card in the conversation, or a game engine:
# every mesh a render would show, less the names given.
#   blender -b house.blend --python-exit-code 1 --python scripts/export_glb.py -- exports/house.glb Ground Tree "Scale figure"
import json, os, sys, time
import bpy

arguments = sys.argv[sys.argv.index("--") + 1:]
out, leave_out = os.path.join(os.path.dirname(bpy.data.filepath), arguments[0]), tuple(arguments[1:])
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.object.select_all(action="DESELECT")
chosen = [o for o in bpy.context.scene.objects
          if o.type == "MESH" and not o.hide_render and o.data.polygons and not (leave_out and o.name.startswith(leave_out))]
for obj in chosen:
    obj.select_set(True)
bpy.context.view_layer.objects.active = chosen[0]
began = time.time()
# Modifiers are applied in the file written, not in the scene; glTF is meters with +Y up, and the exporter converts
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_apply=True, export_animations=False)
procedural = sorted({m.name for o in chosen for m in o.data.materials if m and any(
    link.to_node.bl_idname == "ShaderNodeBsdfPrincipled" and link.from_node.bl_idname != "ShaderNodeTexImage" and link.to_socket.name == "Base Color"
    for link in m.node_tree.links)})
print("GLB " + json.dumps({"file": arguments[0], "bytes": os.path.getsize(out), "objects": len(chosen), "seconds": round(time.time() - began, 2),
                           "arrive_white": procedural}))
```

```bash
cd "$SELKIES_MODAL_WORKSPACE/${SELKIES_MODAL_PROJECT:-projects/default}" && blender -b house.blend --python-exit-code 1 --python scripts/export_glb.py -- exports/house.glb Ground Tree "Scale figure" 2>&1 | grep "^GLB\|rror:"
```

It printed `GLB {"file": "exports/house.glb", "bytes": 327356, "objects": 22, "seconds": 4.87,
"arrive_white": ["Concrete", "Oak boards"]}` for the test building: 22 objects in 327 kB.

- **A texture made of nodes does not travel.** Read back, the building's walls were 4.6 by 4.0
  by 2.7 m with the window cut in (the boolean applied), and plaster, paint, metal, glass, and
  fabric kept their color, roughness, metal, and transmission. The materials whose color comes
  from texture nodes (the wood boards, the concrete) arrived white, bumps were gone everywhere,
  and the box-projected picture was still attached but has no UV map to place it. The script
  names those materials (`arrive_white`): give them a plain color in a copy of the file before
  a delivery that has to look right, and say what the model shows. There is no recipe here for
  UV unwrapping or for baking textures into pictures.
- **Before an export**: scale applied, objects named, what should be one object joined.
