<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Delivery: files, sizes, hand-offs

A logo that cannot be used is not finished. This is the production side: what the master file
holds, what is exported for which use, how each file is checked, and how the work goes to
PhotoCraft and Blender. `<folder>` is the project folder from the turn's state, as a full path.

## The master file

One `<brand>.vectorcraft` in the project folder is the source of everything.

- **Artboards** named for what they hold, in lowercase with hyphens: `primary`, `stacked`,
  `symbol`, `wordmark`, `one-color`, `reversed`, `icon`. Exports are named after artboards, so
  the names are the file names.
- **Each artboard is the art plus its clear space**, so no exported file can be crowded. The
  `icon` artboard is the exception: the tile edge to edge, square.
- **Layers**: the art on a layer named for the mark, the live type on a hidden layer `type
  (live)`, construction guides on their own. Objects named (`object.setProps {id, name}`): a
  hand-off's layers and a later edit both read these names.
- **Type is outlined** in the visible art, or the SVG and PDF depend on a font the receiver may
  not have. `document.find {kind: "Type"}` lists what is still live, each with its `path` of
  parent ids: only objects of the hidden `type (live)` layer should be there.
- **Strokes that are part of the mark are outlined**, live shapes, repeats, and symbol instances
  expanded (`object.expand {object: true}` on the selection), in the delivery copy. Keep the live
  version in the master where it helps later edits.
- **Colors are global swatches.** `swatch.list` is the palette's record.
- **Clean up**: nothing left over from construction, nothing outside the artboards.
  `document.find {within: [x, y, width, height]}` with an artboard's box lists what is on it.
- With two documents open, commands go to the active one: `ui.inspect` gives
  `activeDocument` (an index into `documents`), and `document.activate {index}` changes it. Check
  before exporting.

## Exporting

Make the folders once (`document.export` does not):

```text
engine_exec(engine_id, "mkdir -p <folder>/out/logo <folder>/out/icon <folder>/out/print")
```

Then, with artboard indexes from `document.inspect {depth: 0}`:

| File | Call | Use |
|---|---|---|
| `out/logo/<brand>-primary.svg`, one per artboard | `document.export {path, artboard: i}` | Web, apps, any designer. The file to prefer everywhere. |
| `out/logo/<brand>.pdf` | `document.export {path}`: every artboard, one page each, at its size in points | Printers, sign makers, anyone without a vector tool |
| `out/logo/<brand>-primary-2000.png` | `document.export {path, artboard: i, width: 2000, background: "transparent"}` | Documents, slides, social |
| `out/logo/<brand>-primary-800.png`, `-400.png` | the same with `width` | Email signatures, small web |
| `out/icon/…` | `document.exportForScreens {folder: "out/icon", artboards: [icon], formats: [...]}` | Favicons and app icons, below |
| `out/print/<brand>-cmyk.pdf` | See Print | Press |

As run: an SVG or a PDF took 0.3 s, a 2000 px PNG 0.5 s, seven icon sizes 0.5 s. A width of 2000
for a 782x360 pt artboard gave 2000x921 px, RGBA, transparent outside the art.

### Screen sizes

| Use | Size | Notes |
|---|---|---|
| Favicon | `icon.svg`; PNG 16 and 32; `favicon.ico` holding both | The `.ico` is made below. Test the 16: simplify the mark for it if it clogs. |
| Apple touch icon | PNG 180x180, **opaque** | iOS puts transparent corners on black: export the square tile on its color, `background: "#rrggbb"`, from an artboard with no rounded corners. |
| Web app manifest | PNG 192 and 512; a maskable 512 with the mark inside the middle 80 percent | The maskable icon is cropped to a circle or squircle by the system. |
| iOS and macOS app icon | PNG 1024x1024, opaque, square, no rounded corners | The system applies the mask and the corner radius. Keep the mark centered with room around it. |
| Android adaptive icon | Foreground and background layers of 108x108 dp each (432 px at the largest density); the mark inside the middle 66 dp | The outer 18 dp on each side is cropped or revealed by motion. Play Store listing: 512x512. |
| Social avatar | PNG 800 to 1024 square, the symbol on its color | Shown as a circle on most networks: keep the mark inside the inscribed circle. |
| Link preview (Open Graph) | PNG or JPEG 1200x630 | The lockup centered on a brand color; not the logo edge to edge. |
| Email signature | PNG 300 to 600 wide, on white or transparent | Many mail clients do not show SVG. |

Icon rows for `exportForScreens`, as run: `{format: "png", scale: "1024w", background:
"transparent"}`, the same for `512w`, `180w`, `64w`, `32w`, `16w`, and `{format: "svg"}`, which
wrote `icon@1024w.png` … `icon@16w.png` and `icon.svg`, each square and transparent at the
corners. For plain names give each row a `suffix` (`"-32"`).

The favicon container, from the two PNGs (VectorCraft writes no `.ico`; the engine has ffmpeg):

```text
engine_exec(engine_id, "cd <folder>/out/icon && ffmpeg -loglevel error -y -i icon-16.png -i icon-32.png -map 0 -map 1 favicon.ico && file favicon.ico")
-> favicon.ico: MS Windows icon resource - 2 icons, 16x16, 32 bits/pixel, 32x32, 32 bits/pixel
```

### Print

1. Work on a copy: `file.saveAs {path: "<brand>-cmyk.vectorcraft"}`, then `file.documentColorMode
   {mode: "cmyk"}` (`{changed: n}`, every color converted). The RGB master stays the master: the
   open document is now the copy, so `file.save {}` when done, and `app.open {path:
   "<brand>.vectorcraft"}` to go back to the master.
2. Tell the person which colors moved: bright RGB colors dull in CMYK. A printed proof decides,
   not the screen.
3. A press PDF: `document.exportPdf {path: "out/print/<brand>-cmyk.pdf", standard: "pdfX4",
   marks: {trim: true, registration: true}, bleed: {useDocument: true}}`. Bleed is the
   document's (`file.new {bleed: 8.5}` is 3 mm): art that touches the trim edge must run into it.
   As run on the three-artboard identity, with no bleed: three pages, each its artboard (TrimBox
   782x360 pt) inside 24 pt of room for the marks, PDF 1.6.
4. A logo for a printer is the plain vector PDF of the one-color and CMYK artboards, type
   outlined, no marks. Marks and bleed are for a laid-out piece (a card, a label).
5. Common trims, in points: business card 85x55 mm = 241x156 (Europe) or 3.5x2 in = 252x144
   (US); A4 = 595x842; US Letter = 612x792.
6. One-color uses (stamp, engraving, embroidery, single-ink print) get the `one-color` artboard:
   solid shapes, no tints, no hairlines under 0.25 pt, counters wide enough for the process.
   Embroidery wants shapes above about 1 mm and no gradients; ask the maker for their limits.

### Check every file

```text
engine_files(engine_id, "out/logo")
engine_exec(engine_id, "cd <folder>/out && file logo/*.png icon/*.png && pdfinfo logo/<brand>.pdf | grep -E 'Pages|Page size'")
engine_exec(engine_id, "cd <folder>/out/logo && python3 -c \"import xml.etree.ElementTree as ET, sys; r = ET.parse(sys.argv[1]).getroot(); print(r.get('viewBox'), sum(1 for e in r.iter() if e.tag.endswith('}text')), 'text elements', sum(1 for e in r.iter() if e.tag.endswith('}path')), 'paths')\" <brand>-primary.svg")
```

- Each file is listed, not empty, and newer than the export.
- `file` reports each PNG's pixel size and `RGBA` for transparent ones (`RGB` for one on a
  ground).
- The PDF has one page per artboard at the artboards' sizes.
- The SVG parses, its `viewBox` is the artboard's size, and it has **0 text elements** (type that
  is still live would be drawn in whatever font the viewer has). A plain circle or rectangle is
  written as its own element, not a path, so the path count is only a hint.
- Open one export back in VectorCraft (`app.open {path}`) and `engine_screenshot`: what you see
  is what the receiver gets. Close it (`file.close`).

Then tell the person where the files are, and offer a one-page summary of what each is for.

## To PhotoCraft: the logo on a poster, a mock-up, a photograph

**Send** the artboard as SVG, type outlined, to `handoff/vectorcraft-to-photocraft/<brand>-<part>-v1.svg`,
and the 2000 px transparent PNG beside it as a fallback.

**What arrives**: a Smart Object layer named after the file, holding the SVG itself (PhotoCraft
reports `smartSource: {kind: "embedded", fileName: "….svg"}`), so it scales up and down without
loss, with gradients as drawn. Its box is the art's bounds, not the artboard: the clear space is
yours to keep in the layout. Global swatches, layer names, and live type do not cross; it is one
layer.

**Recipe**, on a PhotoCraft engine started after the export (run on PhotoCraft 0.23.1):

1. `engine_files(photocraft_engine, "handoff/vectorcraft-to-photocraft")` shows the SVG.
2. Place it in a new document with PhotoCraft's own headless tool, which writes a `.pcraft`
   file (`scale` is percent of the SVG's size in pixels at 72 ppi; `center` is in pixels):

   ```text
   engine_exec(photocraft_engine, "cd <folder> && photocraft-cli run --new '{\"width\": 2400, \"height\": 3000, \"resolution\": 300, \"background\": \"#fdf0d5\", \"name\": \"poster\"}' --cmd file.placeEmbedded --params '{\"path\": \"<folder>/handoff/vectorcraft-to-photocraft/<brand>-primary-v1.svg\", \"smartObject\": true, \"scale\": 250, \"center\": [1200, 900]}' --out poster.pcraft")
   -> {"command":"file.placeEmbedded","result":{"bounds":[223.0,450.0,2178.0,1350.0],"layer":32,"scale":250.0,"smartObject":true}}
   ```

   To place into a document that exists, give its file in place of `--new '{…}'` and another
   name to `--out`.
3. Show it in the window. If the turn's state says the PhotoCraft engine has a command channel:
   `engine_call(photocraft_engine, "app.open", {"path": "<folder>/poster.pcraft"})`, which
   answers `{name, path, warnings}`. If it has none, `engine_show` the engine and ask the person
   to open `poster.pcraft` with File, Open.
4. `engine_screenshot(photocraft_engine)` and check the layer is there and sharp.

Traps, each seen: PhotoCraft's live channel refuses `file.placeEmbedded` and `file.open` through
`engine.execute` ("uses ambient filesystem paths and is disabled"), which is why the placing is
done by `photocraft-cli`; and `photocraft <file>` from `engine_exec` starts a second PhotoCraft
instead of opening the file in the one on screen.

## To Blender: the mark in 3D

**Send** the **one-color** artboard as SVG: every shape a closed filled path, type outlined,
strokes outlined, knockouts made with Minus Front (they arrive as holes). To
`handoff/vectorcraft-to-blender/<brand>-one-color-v1.svg`.

**What arrives**: one curve object per shape (21 for a tile with a wordmark and a line of small
type), flat, in a collection named after the file, each with a material of its fill color.
**Lost**: gradients (the object arrives with no material), strokes that were not outlined,
opacity, blend modes, and anything live. **Scale**: 1 pt arrives as 1/3543 m, so a 782 pt wide
artboard's art is 0.19 m across: scale it up.

**Recipe**, on a Blender engine started after the export (run on Blender 5.2.4). Blender takes
Python on standard input through `selkies-modal-blender`:

```text
engine_exec(blender_engine, "selkies-modal-blender 120 <<'PY'
import bpy, os
folder = '<folder>'
before = set(bpy.data.objects)
bpy.ops.import_curve.svg(filepath=os.path.join(folder, 'handoff/vectorcraft-to-blender/<brand>-one-color-v1.svg'))
curves = [o for o in bpy.data.objects if o not in before and o.type == 'CURVE']
bpy.ops.object.select_all(action='DESELECT')
for curve in curves:
    curve.select_set(True)
bpy.context.view_layer.objects.active = curves[0]
bpy.ops.object.join()
mark = bpy.context.view_layer.objects.active
mark.name = '<brand>-mark'
scale = 4.0 / max(mark.dimensions.x, mark.dimensions.y)   # 4 m wide
mark.scale = (scale, scale, scale)
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
mark.location = (0, 0, 1)
mark.rotation_euler = (1.5708, 0, 0)                      # standing up, facing -Y
mark.data.extrude = 0.12 / scale                          # 0.12 m each way: 0.24 m deep
mark.data.bevel_depth = 0.01 / scale
mark.data.bevel_resolution = 2
bpy.ops.object.convert(target='MESH')
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
print(len(curves), 'curves ->', len(mark.data.vertices), 'vertices', [round(v, 2) for v in mark.dimensions])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, '<brand>-mark-3d.blend'))
PY")
```

As run: 21 curves in 0.01 s, a mesh of 39,350 vertices, 4.02 x 0.26 x 1.47 m, the knockouts
open holes through it.

Traps, each seen:

- **Do not apply the scale to the curve before extruding.** `transform_apply(scale=True)` on a
  curve multiplies its points' radius, and the extrusion with it: the mark came out 5.5 m deep.
  Keep the scale on the object, give `extrude` and `bevel_depth` divided by it, convert to a
  mesh, and apply the scale then.
- `transform_apply` with its defaults also applies location and rotation, which a 2D curve
  refuses: pass `location=False, rotation=False`.
- The color version imports too, but its gradient shapes have no material: assign materials in
  Blender, where they belong, and send the one-color file for the geometry.
- Many small letters make a heavy mesh. Lower `bevel_resolution`, or leave small type out of the
  3D version: at sign scale it is rarely wanted.

## Engines and the shared folder

Checked with VectorCraft, Blender, and PhotoCraft engines on one project folder:

- An engine **started after** a file was written sees it (20 seconds after the export, with the
  VectorCraft engine still running).
- Engines **already running** do not see each other's new files: a file exported by VectorCraft
  was still missing in a running Blender and a running PhotoCraft five minutes later, and
  VectorCraft did not see what they had written either.
- After a stop and a start, an engine sees everything all of them wrote.

So: export, confirm with `engine_files` on the VectorCraft engine, start the receiver (or stop it
and start it again), confirm there, then open. When work comes back (a render from Blender to
place in a layout), the same holds the other way: stop and start VectorCraft, after saving.
