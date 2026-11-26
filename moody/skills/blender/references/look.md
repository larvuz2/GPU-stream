<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Light, cameras, and materials

What makes a model read as a place or a thing: one clear light, a camera where a person would
stand, and surfaces that answer light the way their material does. Every script and number here
was run on Blender 5.2.4 on a cloud engine. The order on a job is light, then cameras, then
materials: a material is judged in the light it will be seen in.

## Daylight: sun and sky for a place, a date, and an hour

The world's Sky Texture is a physical sky with the sun's disc in it. Two angles place the sun:

- `sun_elevation`, radians above the horizon.
- `sun_rotation`, radians, a compass bearing: 0 is +Y (north), and it turns clockwise seen from
  above. Measured with a pole's shadow: at 0 the shadow fell toward -Y, at 90° toward -X.

The sky is far brighter than 1, so a picture needs negative exposure
(`scene.view_settings.exposure`, in stops). Measured on sunlit ground of albedo 0.8, and the
exposure that brings it to 0.8:

| Sun's elevation | 3° | 10° | 20° | 30° | 45° | 60° |
|---|---|---|---|---|---|---|
| Sunlit ground, scene-linear | 1.2 | 5.1 | 11.7 | 18.3 | 27.2 | 35.0 |
| Exposure, stops | -0.6 | -2.7 | -3.9 | -4.5 | -5.1 | -5.5 |

`-5.7 - 1.2 * log2(sin(elevation))` follows that row within 0.1 stop, and is what the script
sets. It also makes the cameras, since a sun is chosen for a view:

```python
# Daylight and views: sun and sky for a place, a date, and an hour, the exposure that suits them, and level
# cameras at eye height whose lens shift, not a tilt, frames the building. Run it again to change any of it.
import bpy, json, math, os
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

scene = bpy.context.scene

LATITUDE, DAY_OF_YEAR, SOLAR_HOUR = 45.0, 81, 10.5     # degrees north; day 81 is 21 March; 10:30 by the sun
NORTH = 0.0                                            # degrees from +Y to the plan's north, clockwise
CAMERAS = [
    # name, eye (x, y, z) in meters, the point on the ground it looks toward (x, y), focal length mm, lens shift up
    ("Exterior south-east", (8.6, -7.4, 1.6), (2.3, 2.0), 28.0, 0.05),
    ("Interior from door", (0.75, 0.55, 1.5), (3.9, 3.3), 18.0, 0.0),
]
SUBJECT = ["A-WALL", "Roof slab"]                      # what the first camera has to hold in frame


def sun_angles(latitude, day_of_year, solar_hour):
    """The sun's elevation and its compass bearing (clockwise from north), in radians."""
    declination = math.radians(23.44) * math.sin(math.radians(360 / 365 * (day_of_year - 81)))
    lat, hour = math.radians(latitude), math.radians(15 * (solar_hour - 12))
    elevation = math.asin(math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(declination) * math.cos(hour))
    bearing = math.atan2(-math.sin(hour), math.tan(declination) * math.cos(lat) - math.sin(lat) * math.cos(hour))
    return elevation, bearing % (2 * math.pi)


elevation, bearing = sun_angles(LATITUDE, DAY_OF_YEAR, SOLAR_HOUR)
world = bpy.data.worlds.get("Sun and sky") or bpy.data.worlds.new("Sun and sky")
scene.world = world
nodes, links = world.node_tree.nodes, world.node_tree.links
sky = next((n for n in nodes if n.bl_idname == "ShaderNodeTexSky"), None) or nodes.new("ShaderNodeTexSky")
background = next(n for n in nodes if n.bl_idname == "ShaderNodeBackground")
links.new(sky.outputs["Color"], background.inputs["Color"])
sky.sky_type, sky.sun_disc = "MULTIPLE_SCATTERING", True
sky.sun_elevation, sky.sun_rotation = elevation, bearing + math.radians(NORTH)    # rotation 0 is +Y, clockwise from above
background.inputs["Strength"].default_value = 1.0
# The sky is physical and far brighter than 1: this exposure brings a sunlit white wall to about 0.8
scene.view_settings.exposure = -5.7 - 1.2 * math.log2(max(math.sin(elevation), 0.05))

cameras = bpy.data.collections.get("Cameras") or bpy.data.collections.new("Cameras")
if cameras.name not in scene.collection.children:
    scene.collection.children.link(cameras)
report = {"sun_elevation_deg": round(math.degrees(elevation), 1), "sun_bearing_deg": round(math.degrees(bearing), 1),
          "exposure": round(scene.view_settings.exposure, 2), "cameras": {}}
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1920, 1080, 100
for name, eye, toward, lens, shift in CAMERAS:
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        cameras.objects.link(cam)
    cam.location = eye
    # Level: turned about the vertical only, so vertical edges stay vertical in the picture
    cam.rotation_euler = (math.radians(90), 0.0, math.atan2(-(toward[0] - eye[0]), toward[1] - eye[1]))
    cam.data.lens, cam.data.sensor_width, cam.data.shift_x, cam.data.shift_y = lens, 36.0, 0.0, shift
    cam.data.clip_start, cam.data.clip_end = 0.05, 1000.0
    report["cameras"][name] = {"eye_m": eye, "lens_mm": lens, "shift_y": shift}

# Where the subject falls in the first camera's frame: 0 to 1 across and up; outside that range it is cut off
scene.camera = bpy.data.objects[CAMERAS[0][0]]
bpy.context.view_layer.update()
corners = [bpy.data.objects[n].matrix_world @ Vector(c) for n in SUBJECT for c in bpy.data.objects[n].bound_box]
seen = [world_to_camera_view(scene, scene.camera, c) for c in corners]
report["subject_in_frame"] = {"across": [round(min(s.x for s in seen), 3), round(max(s.x for s in seen), 3)],
                              "up": [round(min(s.y for s in seen), 3), round(max(s.y for s in seen), 3)]}

for window in bpy.context.window_manager.windows:      # the Screen shows the framing
    for area in window.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
bpy.ops.ed.undo_push(message="Daylight and views")
bpy.ops.wm.save_mainfile()
print(json.dumps(report))
```

It answers `{"sun_elevation_deg": 40.8, "sun_bearing_deg": 149.6, "exposure": -4.96, "cameras":
{…}, "subject_in_frame": {"across": [0.207, 0.744], "up": [0.147, 0.665]}}`. Other dates as run
at 45° north: 21 June at 10:00, elevation 57.5° and bearing 121.4°; 21 June at 16:00, 37.3° and
266.9°. `SOLAR_HOUR` is the sun's time: noon is the sun at its highest, which a clock shows
within the hour either way.

- **Choose the hour for the view.** The sun 30 to 60 degrees to the side of the camera's
  direction lights one face and shades the next. A high sun puts a wall under a deep overhang
  in shadow from top to bottom: at 57.5° a 0.9 m canopy shaded a 2.7 m wall entirely, and at
  40.8° it drew a band across the top third.
- **A sun below the horizon is twilight.** `--sun-elevation -4` in `render.py` gave the blue
  hour behind an evening interior.
- **EEVEE does not take the sky's sun disc**: under it this world lights the scene with the sky
  alone, dim and blue (a mean brightness of 0.44 where Cycles gave 0.62). Render daylight in
  Cycles. Where EEVEE must do, a Sun light on the sky's bearing stands in for the disc. Its
  strength, measured as what lit the ground in Cycles as the disc did:

| Sun's elevation | 10° | 20° | 30° | 45° | 60° |
|---|---|---|---|---|---|
| Sun light strength, W/m² | 71 | 104 | 120 | 131 | 137 |

```python
# Give the scene a Sun light that stands in for the Sky Texture's sun disc, on the same bearing and height,
# for EEVEE, which does not take the disc. It changes the open scene and does not save: run it ahead of
# render.py in one command, or through the bridge and save.
#   blender -b house.blend --python scripts/sun_light.py --python scripts/render.py -- --engine BLENDER_EEVEE --out previews/exterior-eevee.png
import bpy, json, math
from mathutils import Vector

scene = bpy.context.scene
sky = next(n for n in scene.world.node_tree.nodes if n.bl_idname == "ShaderNodeTexSky")
elevation, bearing = sky.sun_elevation, sky.sun_rotation
# The strength in W/m2 that lit the ground as the disc did, measured at these elevations in degrees
measured = [(10, 71.0), (20, 104.0), (30, 120.0), (45, 131.0), (60, 137.0)]
degrees = min(max(math.degrees(elevation), 10.0), 60.0)
strength = next(a[1] + (b[1] - a[1]) * (degrees - a[0]) / (b[0] - a[0]) for a, b in zip(measured, measured[1:]) if a[0] <= degrees <= b[0])

sun = bpy.data.objects.get("Sun") or bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
if sun.name not in scene.collection.all_objects:
    scene.collection.objects.link(sun)
toward_sun = Vector((math.sin(bearing) * math.cos(elevation), math.cos(bearing) * math.cos(elevation), math.sin(elevation)))
sun.rotation_euler = (-toward_sun).to_track_quat("-Z", "Y").to_euler()      # a light shines down its own -Z
sun.data.energy, sun.data.angle = strength, math.radians(0.545)             # the sun's width in the sky
sky.sun_disc = False                                                         # or Cycles would count the sun twice
print("SUNLIGHT " + json.dumps({"elevation_deg": round(math.degrees(elevation), 1), "bearing_deg": round(math.degrees(bearing), 1), "strength_w_m2": round(strength, 1)}))
```

On the test building it printed `SUNLIGHT {"elevation_deg": 40.8, "bearing_deg": 149.6,
"strength_w_m2": 127.9}`. Cycles then rendered the same picture with the light as with the
disc (mean brightness 0.615 against 0.617), and EEVEE came to 0.59.

## A panorama for light and reflections

The image ships no HDRI library, but Blender carries eight small panoramas (1024 by 512, made
from Poly Haven's, in `datafiles/studiolights/world/` of the installation): `city`,
`courtyard`, `forest`, `interior`, `night`, `studio`, `sunrise`, `sunset`. They are enough to
light softly and to put something into reflections, and too coarse to appear in a picture, so
the camera is given a plain color in their place:

```python
# Light a scene with one of the eight panoramas Blender ships (city, courtyard, forest, interior, night,
# studio, sunrise, sunset). They are 1024 by 512 pixels: enough to light and to reflect, too coarse to look at,
# so the camera sees a plain color in their place. Run in the Blender the person sees, on the open file.
import bpy, json, math, os

scene = bpy.context.scene
PANORAMA, STRENGTH, TURN_DEG = "studio", 1.0, 0.0      # which one, how bright, turned about the vertical
BACKDROP, EXPOSURE = (0.05, 0.05, 0.05), 0.0           # what the camera sees behind the scene; stops

path = os.path.join(bpy.utils.resource_path("LOCAL"), "datafiles", "studiolights", "world", PANORAMA + ".exr")
world = bpy.data.worlds.get("Panorama") or bpy.data.worlds.new("Panorama")
tree = world.node_tree
tree.nodes.clear()
coord, mapping, picture = tree.nodes.new("ShaderNodeTexCoord"), tree.nodes.new("ShaderNodeMapping"), tree.nodes.new("ShaderNodeTexEnvironment")
light, seen, path_kind = tree.nodes.new("ShaderNodeBackground"), tree.nodes.new("ShaderNodeBackground"), tree.nodes.new("ShaderNodeLightPath")
mix, output = tree.nodes.new("ShaderNodeMixShader"), tree.nodes.new("ShaderNodeOutputWorld")
picture.image = bpy.data.images.load(path, check_existing=True)
mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(TURN_DEG))
light.inputs["Strength"].default_value = STRENGTH
seen.inputs["Color"].default_value = (*BACKDROP, 1.0)
tree.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
tree.links.new(mapping.outputs["Vector"], picture.inputs["Vector"])
tree.links.new(picture.outputs["Color"], light.inputs["Color"])
tree.links.new(path_kind.outputs["Is Camera Ray"], mix.inputs["Fac"])
tree.links.new(light.outputs["Background"], mix.inputs[1])
tree.links.new(seen.outputs["Background"], mix.inputs[2])
tree.links.new(mix.outputs["Shader"], output.inputs["Surface"])
scene.world = world
scene.view_settings.exposure = EXPOSURE
bpy.ops.ed.undo_push(message="Panorama world")
bpy.ops.wm.save_mainfile()
print(json.dumps({"world": world.name, "panorama": [os.path.basename(path), list(picture.image.size)], "strength": STRENGTH}))
```

It answers `{"world": "Panorama", "panorama": ["studio.exr", [1024, 512]], "strength": 1.0}`.
Run on the product scene of objects.md with its three lights kept, it lifted the picture's mean
brightness from 0.73 to 0.81 and flattened the shadow: with a panorama, lower `STRENGTH` or take
the fill light out. It replaces the scene's world, so on a building it replaces the sun and sky.

A sharper panorama has to come from the library: an equirectangular picture the person uploads
or you generate, brought with `engine_import` and loaded in place of `path`. That was not run
here, and a generated picture is not a measured sky: its brightness is whatever looks right.

## Room light

A room lit by daylight through windows is the slow case: little light gets in, and it bounces.
In order:

1. **Exposure first.** About 3 stops over the exterior's: the test room rendered at -1.7 (mean
   brightness 0.64) where its exterior took -4.96. Read `brightness.mean` in the RENDER line
   and aim for 0.45 to 0.7.
2. **Glass that lets light in.** A pane with `visible_shadow = False` on its object, as the
   building script sets. With glass that casts shadows the same room lost its patch of sun
   and fell to a mean of 0.48.
3. **Portals.** An area light the size of each opening, facing in, with `cycles.is_portal`: it
   gives no light and tells Cycles where the sky is. In the test room at 64 samples the grain
   fell from 0.067 to 0.055 (the mean difference of a pixel from its neighbors) for 5% more time.
4. **Lamps that would be there**, for an evening view: warm, with a real size, kept in a
   collection that is hidden until a render shows it.

```python
# Light for a room: portals that tell Cycles where daylight enters, and warm lights for an evening view,
# kept in a collection that stays hidden until a render asks for it. Each part is replaced when this runs again.
import bpy, json, math

scene = bpy.context.scene
WINDOWS = [  # name, center (x, y, z) in meters, width, height, the room is toward: "-x", "+x", "-y", or "+y"
    ("Window east", (4.5, 2.0, 1.35), 2.0, 1.9, "-x"),
    ("Window north", (2.3, 3.9, 1.5), 1.2, 1.2, "-y"),
]
LAMPS = [  # name, kind, at (x, y, z), watts, kelvin, size in meters (an area light's sides, a point light's radius)
    ("Ceiling panel", "AREA", (2.0, 2.0, 2.68), 180.0, 3000.0, (1.2, 0.6)),
    ("Bedside lamp", "POINT", (2.55, 2.5, 0.75), 40.0, 2700.0, 0.06),
]
INWARD = {"-x": (0, math.radians(90), 0), "+x": (0, math.radians(-90), 0), "-y": (math.radians(-90), 0, 0), "+y": (math.radians(90), 0, 0)}


def collection(name):
    found = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if found.name not in scene.collection.children:
        scene.collection.children.link(found)
    return found


def fresh(name, data, coll):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    return obj


# A portal is an area light the size of the opening, facing into the room, that gives no light of its own
portals = collection("Portals")
for name, at, width, height, toward in WINDOWS:
    data = bpy.data.lights.new(f"Portal {name}", "AREA")
    data.shape = "RECTANGLE"
    data.size, data.size_y = (height, width) if toward in ("-x", "+x") else (width, height)
    data.cycles.is_portal = True
    portal = fresh(f"Portal {name}", data, portals)
    portal.location, portal.rotation_euler = at, INWARD[toward]

evening = collection("Lights evening")
for name, kind, at, watts, kelvin, size in LAMPS:
    data = bpy.data.lights.new(name, kind)
    data.energy, data.use_temperature, data.temperature = watts, True, kelvin
    if kind == "AREA":
        data.shape, (data.size, data.size_y) = "RECTANGLE", size
    else:
        data.shadow_soft_size = size
    lamp = fresh(name, data, evening)
    lamp.location = at                             # an area light shines down its own -Z: unrotated, at the floor
evening.hide_render = evening.hide_viewport = True

bpy.ops.ed.undo_push(message="Portals and evening lights")
bpy.ops.wm.save_mainfile()
print(json.dumps({"portals": [o.name for o in portals.objects], "evening": {o.name: [o.data.type, o.data.energy, o.data.temperature] for o in evening.objects}}))
```

It answers `{"portals": ["Portal Window east", "Portal Window north"], "evening": {"Ceiling
panel": ["AREA", 180.0, 3000.0], "Bedside lamp": ["POINT", 40.0, 2700.0]}}`. An evening view is
then `render.py … --show "Lights evening" --sun-elevation -4 --exposure -2.5`: in the test room
a mean brightness of 0.60, lamp light on the walls, a blue-hour sky in the windows, and the
lamps mirrored in the glass. At `--exposure 1.5` the same frame was burnt (half its pixels
clipped), which the RENDER line said before anyone looked.

- Light power is in watts of light, not of electricity: 180 W on a panel is a strong ceiling
  fixture, 40 W a bright bedside lamp.
- `use_temperature` with `temperature` in kelvin colors a lamp. 3000 and 2700 gave a deep
  orange room against the blue hour; that is what those numbers look like next to a twilight
  sky, so say it before the person is surprised.

## Cameras

- **Architecture is level.** Rotation `(90°, 0, heading)`: the camera turns about the vertical
  only, so vertical edges stay vertical. Raise or lower what it sees with `shift_y`, not with a
  tilt. `shift_y` is in widths of the frame: 0.1 moved a point down by 0.178 of the height at
  16:9.
- **Eye height.** 1.6 m standing, 1.2 m seated, 1.5 m in a small room.
- **Focal length** (`lens`, mm, on a 36 mm sensor): interiors 16 to 24 (18 in the test room;
  under 16 the corners stretch), exteriors 24 to 35 (28 for the test building), details 50 to 85.
- **Check the framing by numbers.** `world_to_camera_view(scene, camera, point)` gives where a
  point lands in the frame, 0 to 1 across and up. The script reports the subject's bounds: both
  ranges inside 0.05 to 0.95 and it is all in view; aim for a building's foot near 0.15 to 0.2
  up, with ground under it.
- **Put the viewport on the camera** (`region_3d.view_perspective = "CAMERA"`, as the script
  does) so the Screen shows the person the frame you mean.
- **A camera that looks at a thing** (a product, a detail): aim it with
  `obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()`; cameras and
  lights both look down their own -Z.
- **Depth of field** belongs to close views: `cam.data.dof.use_dof = True`, `focus_object` (or
  `focus_distance` in meters), `aperture_fstop`: 8 kept a 180 mm product sharp front to back at
  0.7 m. Leave it off for architecture, where everything is in focus.

## Materials

A new material already holds a Principled BSDF and an output; set its inputs by name. (Do not
set `use_nodes`: on a world it warns that the property goes away in Blender 6.0.) The inputs in
5.2: `Base Color`, `Metallic`, `Roughness`, `IOR`, `Alpha`, `Normal`, `Subsurface Weight`,
`Specular IOR Level`, `Anisotropic`, `Transmission Weight`, `Coat Weight`, `Coat Roughness`,
`Sheen Weight`, `Sheen Roughness`, `Emission Color`, `Emission Strength`, `Thin Film Thickness`,
and their companions.

| Material | Base color | Roughness | What else makes it |
|---|---|---|---|
| Plaster | 0.86, 0.84, 0.80 | 0.85 | a fine noise (scale 180 a meter) as a 1 mm bump, seen only in grazing light |
| Concrete | 0.36 to 0.62 gray | 0.7 | clouds at 1.3 a meter in the color, pits at 90 a meter as a 2 mm bump |
| Wood boards | 0.33, 0.2, 0.1 to 0.62, 0.45, 0.27 | 0.45 | noise stretched 20 times along the grain; a brick texture for boards of 1.2 by 0.14 m with 2 mm joints |
| Metal, anodized | 0.16, 0.16, 0.17 | 0.35 | `Metallic` 1.0 |
| Glass | 1, 1, 1 | 0.0 | `Transmission Weight` 1.0, `IOR` 1.5; the pane 12 mm thick, its object with `visible_shadow = False` |
| Fabric | 0.62, 0.66, 0.7 | 0.95 | `Sheen Weight` 0.6, `Sheen Roughness` 0.5, a wave texture at 400 a meter as a 0.5 mm weave |
| Glazed ceramic | 0.3, 0.55, 0.45 | 0.12 | `Coat Weight` 1.0, `Coat Roughness` 0.03 (objects.md) |
| Paint, semi-gloss | 0.07, 0.16, 0.2 | 0.4 | nothing: paint is a color and a sheen |

```python
# Materials for a building, each a Principled BSDF with a procedural texture in meters, assigned by object name.
# Object coordinates are used throughout: the objects have scale 1 and their origin at the world's, so 1 is 1 m.
import bpy, json, os

P = os.path.join(os.environ["SELKIES_MODAL_WORKSPACE"], os.environ.get("SELKIES_MODAL_PROJECT", "projects/default"))
scene = bpy.context.scene


def material(name, color, roughness, **inputs):
    """A Principled material, made or reset: base color (r, g, b), roughness, and any other input by its name."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    tree = mat.node_tree
    for node in list(tree.nodes):
        if node.bl_idname not in ("ShaderNodeBsdfPrincipled", "ShaderNodeOutputMaterial"):
            tree.nodes.remove(node)
    bsdf = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    for key, value in inputs.items():
        bsdf.inputs[key].default_value = value
    return mat, tree, bsdf


def coordinates(tree, scale=(1.0, 1.0, 1.0)):
    """Object coordinates through a Mapping node: scale 4 repeats a texture every quarter meter."""
    coord, mapping = tree.nodes.new("ShaderNodeTexCoord"), tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = scale
    tree.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    return mapping.outputs["Vector"]


def noise(tree, vector, scale, detail=4.0):
    node = tree.nodes.new("ShaderNodeTexNoise")
    node.inputs["Scale"].default_value, node.inputs["Detail"].default_value = scale, detail
    tree.links.new(vector, node.inputs["Vector"])
    return node.outputs["Fac"]


def bump(tree, bsdf, height, strength, distance):
    """Relief from a gray value; distance is the relief's depth in meters."""
    node = tree.nodes.new("ShaderNodeBump")
    node.inputs["Strength"].default_value, node.inputs["Distance"].default_value = strength, distance
    tree.links.new(height, node.inputs["Height"])
    tree.links.new(node.outputs["Normal"], bsdf.inputs["Normal"])


def tint(tree, bsdf, factor, dark, light):
    """Base color between two colors by a gray value."""
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color, ramp.color_ramp.elements[1].color = (*dark, 1.0), (*light, 1.0)
    tree.links.new(factor, ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return ramp


def pictured(name, path, meters, roughness=0.6):
    """A material from a picture in the project's folder, box-projected so that the picture covers `meters`."""
    mat, tree, bsdf = material(name, (0.6, 0.6, 0.6), roughness)
    picture = tree.nodes.new("ShaderNodeTexImage")
    picture.image = bpy.data.images.load(os.path.join(P, path), check_existing=True)
    picture.projection, picture.projection_blend = "BOX", 0.1
    tree.links.new(coordinates(tree, (1 / meters,) * 3), picture.inputs["Vector"])
    tree.links.new(picture.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


# Plaster: matte, nearly white, with a fine grain you only see where light grazes it
plaster, tree, bsdf = material("Plaster", (0.86, 0.84, 0.80), 0.85)
bump(tree, bsdf, noise(tree, coordinates(tree), 180.0), 0.25, 0.001)

# Concrete: mid gray, cloudy at the scale of a meter, pitted at the scale of a centimeter
concrete, tree, bsdf = material("Concrete", (0.5, 0.5, 0.48), 0.7)
vector = coordinates(tree)
tint(tree, bsdf, noise(tree, vector, 1.3, 6.0), (0.36, 0.36, 0.35), (0.62, 0.62, 0.6))
bump(tree, bsdf, noise(tree, vector, 90.0), 0.4, 0.002)

# Wood boards: grain stretched along x, boards 1.2 m by 0.14 m with dark joints
wood, tree, bsdf = material("Oak boards", (0.45, 0.3, 0.17), 0.45)
grain = noise(tree, coordinates(tree, (1.5, 30.0, 30.0)), 3.0, 8.0)
ramp = tint(tree, bsdf, grain, (0.33, 0.2, 0.1), (0.62, 0.45, 0.27))
boards = tree.nodes.new("ShaderNodeTexBrick")
boards.inputs["Scale"].default_value, boards.inputs["Mortar Size"].default_value = 1.0, 0.002
boards.inputs["Brick Width"].default_value, boards.inputs["Row Height"].default_value = 1.2, 0.14
boards.inputs["Color1"].default_value = boards.inputs["Color2"].default_value = (1.0, 1.0, 1.0, 1.0)
boards.inputs["Mortar"].default_value = (0.25, 0.25, 0.25, 1.0)
tree.links.new(coordinates(tree), boards.inputs["Vector"])
joints = tree.nodes.new("ShaderNodeMix")
joints.data_type, joints.blend_type = "RGBA", "MULTIPLY"
joints.inputs["Factor"].default_value = 1.0
tree.links.new(ramp.outputs["Color"], joints.inputs["A"])
tree.links.new(boards.outputs["Color"], joints.inputs["B"])
tree.links.new(joints.outputs["Result"], bsdf.inputs["Base Color"])
bump(tree, bsdf, boards.outputs["Fac"], 0.3, 0.001)

# Metal: dark anodized aluminum for frames
metal, tree, bsdf = material("Anodized aluminum", (0.16, 0.16, 0.17), 0.35, Metallic=1.0)

# Glass: clear. The pane's object is set not to cast shadows (visible_shadow), so daylight passes it.
glass, tree, bsdf = material("Glass", (1.0, 1.0, 1.0), 0.0, IOR=1.5)
bsdf.inputs["Transmission Weight"].default_value = 1.0

# Fabric: matte, with sheen at grazing angles and a fine weave
fabric, tree, bsdf = material("Linen", (0.62, 0.66, 0.7), 0.95)
bsdf.inputs["Sheen Weight"].default_value, bsdf.inputs["Sheen Roughness"].default_value = 0.6, 0.5
weave = tree.nodes.new("ShaderNodeTexWave")
weave.inputs["Scale"].default_value = 400.0
tree.links.new(coordinates(tree), weave.inputs["Vector"])
bump(tree, bsdf, weave.outputs["Fac"], 0.3, 0.0005)

# Paint, lawn, and the pale tone of block entourage
paint, tree, bsdf = material("Door paint", (0.07, 0.16, 0.2), 0.4)
lawn, tree, bsdf = material("Lawn", (0.2, 0.3, 0.1), 0.95)
vector = coordinates(tree)
tint(tree, bsdf, noise(tree, vector, 0.6, 8.0), (0.1, 0.17, 0.05), (0.27, 0.36, 0.12))
bump(tree, bsdf, noise(tree, vector, 60.0), 0.6, 0.02)
pale, tree, bsdf = material("Entourage", (0.75, 0.78, 0.72), 0.9)

# A picture from the library, where the project has one: engine_import puts it at library/<tag>/NN-<name>
paving_picture = "library/paving/01-paving.png"
paving = pictured("Paving", paving_picture, 2.0) if os.path.exists(os.path.join(P, paving_picture)) else concrete

RULES = [  # the first prefix that matches an object's name gives its material
    ("A-WALL", plaster), ("Wall ", plaster), ("Slab", concrete), ("Step", concrete), ("Roof", concrete),
    ("Floor", wood), ("Threshold", wood), ("Frame", metal), ("Glass", glass), ("Leaf", paint),
    ("A-FURN", fabric), ("Ground", lawn), ("Path", paving), ("Tree", pale), ("Scale figure", pale),
]
assigned = {}
for obj in scene.objects:
    if obj.type != "MESH":
        continue
    mat = next((m for prefix, m in RULES if obj.name.startswith(prefix)), None)
    if mat is not None:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        assigned[obj.name] = mat.name
bpy.ops.file.make_paths_relative()                 # pictures stay found when the folder is opened on another machine
bpy.ops.ed.undo_push(message="Materials")
bpy.ops.wm.save_mainfile()
print(json.dumps({"materials": sorted(set(assigned.values())), "objects": len(assigned),
                  "without_material": [o.name for o in scene.objects if o.type == "MESH" and not o.data.materials],
                  "pictures": {i.name: [i.filepath, list(i.size)] for i in bpy.data.images if i.filepath}}))
```

It answers `{"materials": [the ten names], "objects": 27, "without_material": ["A-DOOR",
"A-GLAZ", "Cutter Window east"], "pictures": {"01-paving.png":
["//library/paving/01-paving.png", [512, 512]]}}`: the flat guides and the cutter need none.

- **Textures are in meters because the coordinates are.** Object coordinates on an object with
  scale 1 and its origin at the world's are world meters, so "boards 0.14 m wide" is a number in
  the script. An object you scaled, or one built away from the origin and moved, shifts the
  pattern: apply the scale (modeling.md).
- **A picture from the library**: `engine_import(engine_id, ["@paving"])` copies an entry's media
  to `library/paving/01-<name>` in the project's folder and answers with the paths; `pictured`
  box-projects it so that no UV map is needed, at a size in meters you state. It was run on a
  picture written to that path by hand, since no library was at hand. The script makes paths
  relative (`bpy.ops.file.make_paths_relative()`), so the file opens on the next machine.
- **The palette is the person's.** In an Architecture project the Materials section of the
  library holds one entry per material with a close picture: use `pictured` for those that are
  a pattern (a stone, a tile, a weave) and a plain recipe from the table, with the entry's
  color, for those that are a finish.
- **A material nothing uses is not saved** (`use_fake_user = True` keeps one).
- **Nodes do not leave Blender.** These textures render here and are lost in a GLB or an FBX
  (modeling.md): a model that leaves gets plain colors.
- **Judge a material in a draft**, half size and 64 samples, from the final camera, before the
  final frame is rendered.
