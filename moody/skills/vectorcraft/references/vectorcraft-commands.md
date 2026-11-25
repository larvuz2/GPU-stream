<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# VectorCraft commands

Every call below was run on VectorCraft 0.24.1, the version the catalog starts, through the same
channel `engine_call` reaches, and its answer is copied from what came back. Parameter docs are
from the application's own registry: `?` marks an optional key, `=` its default. VectorCraft has
1,430 commands; this is the set a logo, an identity, an icon, or a pattern needs. A command that
is not here has no verified recipe: see "Finding a command" before using one.

## Calling VectorCraft

`engine_call(engine_id, method, params)` sends one request on VectorCraft's control channel.

| Method | Params | What it does |
|---|---|---|
| `engine.execute` | `{command, params}` | Runs one command and returns its result. Nearly everything is this. |
| `document.inspect` | `{depth?}` | The active document: `artboards`, `layers` (the tree, `depth` levels deep), `selection`, `currentLayer`, `dirty`, `history`, `paint` (the fill and stroke new art takes). `depth: 0` is about 1 KB; use it unless you need the tree. |
| `ui.inspect` | none | The app: `documents` (`[{title, dirty}]`), `activeDocument` (an index into it), `ui.dialog` (the open dialog, or null), `fileDialog` (`"save"`, `"open"`, or null), `background` (saves still writing), `tool`. |
| `ui.dialog.set`, `ui.dialog.confirm`, `ui.dialog.cancel` | `{field, value}`, none, none | Fill, accept, or dismiss the open dialog. |
| `ui.tool.select` | `{tool}` | The tool the person sees chosen: `selection`, `directSelection`, `pen`, `type`. |
| `ui.screenshot` | `{path}` | The whole window as a PNG file in the project folder (1920x1050). To look yourself, use `engine_screenshot`. |
| `ui.render` | `{path, artboard?: index, scale?: px per pt}` | One artboard on white as a PNG file, with no window around it: `{width, height, path}`. |
| `app.open` | `{path}` | Opens a file of any readable format as a new document: `{index, title, format, warnings}`. |

A call looks like this, and so does every command in this file:

```text
engine_call(engine_id, "engine.execute", {"command": "shape.rectangle",
  "params": {"x": 60, "y": 60, "width": 240, "height": 240, "radius": 56}})
-> {"id": 2}
```

An answer that is not an object comes back as `{"result": ...}`: `{"result": null}` means done.
A refusal is an error whose text says why, and names the key: `unknown parameter `ids`; the
command takes: offset, joins, miterLimit`. Read it; nothing ran.

**Finding a command.** Do not call `engine.commands`: its answer is 830 KB and arrives cut. The
ids follow the menus (`object.pathfinder.unite` is Object, Pathfinder, Unite). Try the command with
`{}` or one wrong key on a scratch object: the refusal lists the keys it takes. Then check what it
did with `document.node`, and `edit.undo` if it was wrong.

## Units and addressing

- **Lengths are points** (1 pt = 1/72 inch = 0.3528 mm; 1 px at 72 ppi), whatever units the
  document shows the person. `file.new` alone also takes strings with a unit (`"210 mm"`).
- **Coordinates** are in points from the top left corner of the first artboard, x to the right,
  **y down**. A second artboard at `x: 0, y: 380` has its art at y from 380. `x, y` of a shape is
  the top left of its box; `cx, cy` its center. `text.create`'s `x, y` is the start of the
  **baseline**, so the type sits above y.
- **Angles** are degrees: `object.rotate` counter-clockwise, a gradient's `angle` counter-clockwise
  (0 runs left to right), a shape's `rotation` clockwise.
- **Percent** is 0 to 100 (`object.scale` `sx`, opacity, tint).
- **Colors** are `"#rrggbb"`, `{c, m, y, k}` (0 to 100), `{gray}`, or `{l, a, b}`. `#rrggbbaa` is
  refused: opacity is `object.setProps {opacity}`.
- **Ids** are integers. The layer is 1; objects count up from 2. Every command that makes an
  object answers with its id, and **every command that combines or converts objects makes new
  ones**: read the new id from the answer (`{"ids": [9]}`), never count ahead.
- **Artboards** are addressed by 0-based `index` in commands and 1-based numbers in `range`
  strings (`"1-2"`).
- **Paths** in parameters are relative to the project folder, where VectorCraft runs
  (`"out/logo.svg"`), or full. Nothing outside the project folder is read or written
  (`automation path rejected: outside the write root`).

## Traps (each seen in a run)

- **New art takes the last paint used.** After `paint.setFill {color: navy}` every new shape is
  navy with the last stroke. Set fill and stroke on each new object, by `ids`.
- **Some commands work on the selection only** and refuse or ignore `ids`:
  `object.path.outlineStroke`, `object.path.offsetPath`, `object.path.simplify`,
  `type.createOutlines`, `object.distribute`, `object.distributeSpacing`, `object.setBounds`,
  `recolor.apply`, `select.same.*`. Run `select.set {ids}` first. `object.setBounds {ids}` does
  not refuse: it silently resizes whatever is selected.
- **`document.export` does not make folders** (`No such file or directory (os error 2)`), though
  `document.exportForScreens` does. Make them first:
  `engine_exec(engine_id, "mkdir -p <project folder>/out")`. `engine_exec` starts in the home
  folder, not the project folder, so give it the full path.
- **A command that needs a file and gets no `path` opens a file dialog on the person's screen**
  and answers `cancelled`: `file.save {}` on a document that has no file yet, `file.saveAs {}`.
  `ui.inspect` then shows `fileDialog: "save"`. Always pass `path`. To clear a dialog you opened:
  `engine_exec(engine_id, "pkill -x zenity")`, then check `fileDialog` is null.
- **Closing a modified document asks.** `file.close` answers `{"pending": "saveChanges"}` and
  waits. Save first, or discard with `ui.dialog.set {field: "discard", value: true}` then
  `ui.dialog.confirm`; `ui.dialog.cancel` keeps the document open.
- **Saves answer before the file is written**: `{"background": true, "status": "Saving ..."}`.
  The document is saved when `ui.inspect` lists it with `dirty: false` and `background` is empty,
  a second or two later. Exports here answered only once written, with `bytes`.
- **`document.exportForScreens` marks the document modified** (it remembers its settings in it).
  Save after it.
- **A font or style that is not there is replaced, with a `warning` in the answer**: Inter has
  Regular, Medium, and SemiBold only, so `style: "Bold"` draws SemiBold; an unknown family draws
  Source Sans 3. Read every type answer for `warning`.
- **`text.createInPath` uses up the path**: the type object has a new id.
- **`artboard.new` with `side` takes no size**: it copies the size of the artboard it sits beside.
  For another size give `x, y, width, height`.
- **`recolor.colors {}` and `document.info` read the selection when there is one.** `select.none`
  first to read the whole document.
- **Commands go to the active document.** `file.new` and `app.open` make theirs active. With
  two open, read `ui.inspect`'s `activeDocument` before you draw, save, or export, and switch
  with `document.activate {index}`: an export meant for one document wrote the other.
- **A reply may be 60 s late at most.** VectorCraft gives up on a command it has not finished by
  then; nothing in this file takes more than 2 s.
- **A document restored after a restart is named `<name> [Recovered]`**, is modified, and has no
  file: see SKILL.md, "Coming back to a project".

## Reading state

| Call | Answer |
|---|---|
| `document.inspect {depth: 0}` | `{artboards: [{name, x, y, width, height}], layers: [{id, name, visible, bounds}], selection: [ids], currentLayer, dirty, history: [labels], paint: {fill, stroke, strokeWidth}, colorMode, units}` |
| `document.node {id, summary: true, depth?: 0}` | One object: `{id, kind, name, bounds: {x, y, width, height}, fill, stroke, strokeWidth, strokeOptions, anchors, closed, visible, locked, text?, childCount?}`. `bounds` of outlined type is its ink, of live type its line box. |
| `document.node {id}` | The same object in full: every anchor and handle, the appearance stack. |
| `document.find {name?, kind?, text?, within?: [x, y, w, h], intersects?: [x, y, w, h], limit?=100}` | `{matches: [{id, kind, name, path: [parent ids]}], total}`. `kind` is the Layers panel's label: `Path`, `Compound Path`, `Group`, `Type`, `Rectangle`, `Rounded Rectangle`, `Ellipse`. A star and a polygon are `Path`. At least one filter. |
| `document.info {category?: "fonts" \| "objects"}` | `{fonts: ["Inter SemiBold"], objects: {paths, compoundPaths, groups, textObjects, ...}, pathLength, document: {artboards, colorMode, units}}` |
| `swatch.list {}` | `{swatches: [{name, kind, global, spot, hex}], groups}` |
| `text.fontList {}` / `{family}` | `{families: [...]}` / `{family, styles: [...], axes}` |

## Documents and artboards

```text
file.new {name, width?: pt=612 | "210 mm", height?, units?: "Points" | "Pixels" | "Millimeters" | "Inches",
          colorMode?: "rgb" | "cmyk", artboards?: n, bleed?: pt (0 to 72)}        -> {index, previewMode}
artboard.rename {index, name}                                                   -> {renamed: [0]}
artboard.setProps {index, name?, x?, y?, width?, height?}                       -> null
artboard.new {x, y, width, height, name?}  |  {side: "right" | "bottom" | ..., name?}  -> {index}
artboard.duplicate {index, art: true, side?: "bottom"}      -> {index, indices, ids: [the copies of the art, back to front]}
artboard.fitToArt {index}                                                       -> null
artboard.delete {index}
document.setUnits {units}          what the person's rulers and panels show; commands stay in points
document.setup {}                  -> the setup, with bleed: [top, bottom, left, right]
file.documentColorMode {mode: "cmyk" | "rgb"}       -> {changed: n}     converts every color in the document
guide.add {vertical: bool, pos: pt, artboard?: index}                            -> {index}
guide.list {}                      -> [{index, vertical, pos, artboard?}]
layer.new {name}                   -> {id}        the new layer becomes the current one
layer.setCurrent {id}              where new art goes
layer.move {ids: [objects], target: layer id, place: "inside"}                  -> {ids}
layer.setProps {id, name?, visible?, locked?}
```

- `artboard.duplicate` with `art: true` is how a variant starts: the reply's `ids` are the copies
  in stacking order, so the first is the back object. Art on a hidden layer is not copied.
- An artboard's white is paper, not an object: exports are transparent unless you ask otherwise.

## Shapes

```text
shape.rectangle {x, y, width, height, radius?: pt}                  -> {id}
shape.ellipse   {x, y, width, height}                               -> {id}
shape.polygon   {cx, cy, radius, sides=6, rotation?}                -> {id}
shape.star      {cx, cy, radius1, radius2, points=5, rotation?}     -> {id}
shape.line      {x1, y1, x2, y2}                                    -> {id}
object.setLiveShape {id, radius: pt, corners?: [0 top-left, 1 top-right, 2 bottom-right, 3 bottom-left]}
```

`object.setLiveShape` rounds a rectangle's corners later, all of them or the ones named.

## Paths: the pen by numbers

```text
path.create {anchors: [{x, y, in?: [x, y], out?: [x, y]}], closed?: bool}   -> {id}
path.create {d: "M 200 240 C 200 200 260 200 260 240 S 320 280 320 240"}    -> {id}    SVG path data
path.curvature {points: [{x, y, corner?: true}], closed?}                   -> {id}    a smooth curve through the points
path.moveAnchor {id, anchor: index, x, y}            its handles move with it
path.setHandle {id, anchor, which: "in" | "out", x, y}
path.insertAnchor {id, segment: index, t: 0..1}                             -> {anchor: new index}
path.convertAnchor {id, anchor, to: "smooth" | "corner"}
path.close {id}
object.path.simplify {tolerance?: pt=1}      (selection)                    -> {ids, before, after}   anchor counts
object.path.offsetPath {offset: pt, joins?: "miter" | "round" | "bevel"}  (selection) -> {ids}  a new path above; negative insets
object.path.outlineStroke {}                 (selection)                    -> {ids}  the stroke as a filled shape
```

- `in` and `out` are the handles' **absolute positions**, not offsets. A smooth anchor has its two
  handles on one line through it; an anchor with neither is a corner.
- A good curve has few anchors, placed at the extremes of the shape (the leftmost, rightmost,
  top, and bottom points), with handles horizontal or vertical there. A circle is four.
- A symmetric wave across 160 pt, as run: anchors at (100, 224) `out` (126, 198); (180, 224) `in`
  (154, 250) `out` (206, 198); (260, 224) `in` (234, 250).
- Draw a line as a stroked open path while it is being designed (weight and caps stay editable),
  and `outlineStroke` it for the final mark, so it scales as a shape and takes part in Pathfinder.

## Combining shapes (Pathfinder)

```text
object.pathfinder.unite      {ids: [back, ..., front]}   -> {ids: [new]}   one shape; parts that do not touch become one compound path
object.pathfinder.minusFront {ids: [back, front...]}     -> {ids: [new]}   the back object with every front object cut out of it
object.pathfinder.intersect  {ids}                        -> {ids: [new]}   only where they overlap
object.pathfinder.exclude    {ids}                        -> {ids: [new]}   everything but the overlap
object.pathfinder.divide     {ids}                        -> {ids: [group]} every region as its own piece
object.compoundPath.make     {ids}                        -> {id}           the front shapes become holes in the back one, still editable
object.clippingMask.make     {ids: [art..., front shape]} -> {id}           the front shape crops the rest
object.group {ids} -> {id}          object.ungroup {ids}
```

- The inputs are gone after an operation and the result has a new id, the back object's paint
  (Unite, Minus Front), and the back object's name.
- An id of a layer is refused: `id 1 is a layer, not an object`.
- Stacking order decides front and back; a new object is in front of older ones.
  `object.arrange.bringToFront {ids}` and `object.arrange.sendToBack {ids}` change it.

## Fill, stroke, gradient, swatches

```text
paint.setFill   {ids, color: "#rrggbb"} | {ids, none: true} | {ids, swatch: name, tint?: 0..100}  -> {objects: n}
paint.setFill   {ids, gradient: {kind: "linear" | "radial", stops: [{offset: 0..1, color}, ...],
                 start?: [x, y], end?: [x, y]  (document points, both or neither) | angle?: deg}}
paint.setStroke {ids, ...the same keys}
paint.editGradient {ids, angle?: deg, stops?}                -> {ids}
stroke.set {ids, weight?: pt, cap?: "butt" | "round" | "square", join?: "miter" | "round" | "bevel",
            align?: "center" | "inside" | "outside", dash?: [dash, gap, ...] | null}
object.setProps {id | ids, name?, opacity?: 0..100, blend?: "Multiply", visible?, locked?}
swatch.new {name, color, global: true}                       -> {name, names}
swatch.new {name, color: {c, m, y, k}, spot: true}           a spot color (always global)
swatch.edit {name, color}                                    -> {name, relinked: n}   every object filled with it follows
recolor.colors {}                                            -> {colors: [{hex, key, count, swatch?}]}   most used first
recolor.apply {map: {"#1d4ed8": "#7c3aed"}}  (selection)     -> {changed: n}
edit.colors.toGrayscale {ids}                                -> {changed: n}
```

- **Make the palette global swatches first, and fill by swatch.** `document.node` then reports
  `"fill": "Morrow Navy (#14213d)"`, and one `swatch.edit` recolors the whole identity. A fill by
  hex is not linked to anything.
- A gradient given `start` and `end` runs between those two points of the page, so one gradient
  can cross several shapes joined into a compound path. Without them it fits each object's box.
- `paint.setFill {ids: [group]}` fills every object inside the group (`{"objects": 21}`).
- A dotted line: `stroke.set {weight: 4, cap: "round", dash: [0, 10]}`.
- A pattern swatch is a fill too: `paint.setFill {ids, swatch: "dots"}` (see Patterns).

## Type

```text
text.create {x, y, text, font, style?, size: pt, color?, justify?: "left" | "center" | "right"}
    -> {id, bounds: {x, y, width, height}, warning?}                           point type; x, y is the baseline start
text.create {x, y, text, font, size, area: {width, height}}                    -> {id, bounds, overflow?}   area type; x, y is the box's top left
text.setStyle {id, font?, style?, size?, tracking?: 1/1000 em, leading?: pt | "auto", justify?,
               fill?: color, features?: ["ss01", "-liga"], start?: byte, end?: byte}   -> {ids, warning?}
text.setText {id, text}                                                        -> {ids}
text.createInPath {path: id, mode: "onPath" | "area", text, font, style?, size, color?}  -> {id, bounds}
type.pathOptions {id}                              -> {start, end, flip, effect, alignToPath, spacing}
type.pathOptions {id, alignToPath?: "baseline" | "center" | "ascender" | "descender", flip?: bool, start?: 0..1, spacing?: pt}
type.createOutlines {}   (selection)               -> {ids: [group]}   a group of one compound path per glyph
text.fontList {} | {family}
```

- `flip: true` puts type on a path on its other side by reversing the path: the answer still
  says `flip: false`, and `start` now counts from the other end (0.25 came back as 0.75).
- Tracking is in thousandths of an em: -30 tightens a large wordmark, 100 to 300 opens small caps.
- OpenType features that are taken: `liga calt dlig smcp frac onum tnum ordn swsh ss01` to `ss20`
  `salt titl pnum lnum sups subs numr dnom`. Any other tag is refused (`case` is).
- `text.setStyle` with `start` and `end` styles a range; `text.setText` then keeps the style of
  the first run for all of the text.
- **Before `type.createOutlines`, keep the live type**: `edit.duplicate {ids}`, `layer.new {name:
  "type (live)"}`, `layer.move {ids: copies, target: new layer, place: "inside"}`, `layer.setProps
  {id, visible: false}`, `layer.setCurrent {id: the art layer}`. Outlines cannot be retyped.
- Fonts in the engine: Inter (Regular, Medium, SemiBold), Source Sans 3 (Regular, Semibold, Bold,
  Italic), Source Serif 4, Ubuntu and Ubuntu Sans (Thin to Extra Bold, with condensed and italic),
  Noto Sans, Noto Serif, and their Display cuts (Regular, Bold, italics), Liberation Sans, Serif,
  and Mono, DejaVu Sans and Serif, Nimbus Sans, Nimbus Sans Narrow, Nimbus Roman, C059 (a Century
  Schoolbook), P052 (a Palatino), URW Bookman, URW Gothic (a geometric sans), Z003 (a chancery
  italic), JetBrains Mono, Hack, Ubuntu Mono, and Noto for 222 other scripts. Ask
  `text.fontList {family}` for a family's styles before setting one.
- **A font the person brings** (they must hold a license that allows it): put the `.ttf` or `.otf`
  in `<project folder>/fonts/`, then `prefs.set {key: "fontsFolder", value: "<full path>/fonts"}`
  and `text.rescanFonts {}` (`{families: 259, faces: 611}`); `text.fontList {family: "DM Serif
  Display"}` then answers with its styles. The folder and the preference stay with the project.

## Moving, aligning, copying

```text
object.move {ids, dx, dy, copy?: true}                              -> {ids}
object.scale {ids, sx: %, sy?: %, origin?: [x, y]}                  -> {ids}
object.rotate {ids, angle: deg, origin?: [x, y], copy?: true}       -> {ids: [the copy, with copy]}
object.reflect {ids, axis: "vertical" | "horizontal", copy?}
object.setBounds {x?, y?, width?, height?, reference?: 0}  (selection)     exact size and place of the selection's box
object.align {ids, horizontal?: "left" | "center" | "right", vertical?: "top" | "center" | "bottom",
              to?: "selection" | "artboard", artboard?: index}
object.distribute {horizontal?: "left" | "center" | "right", vertical?}  (selection, two or more)
object.distributeSpacing {axis: "horizontal" | "vertical"}  (selection)   equal gaps
edit.duplicate {ids, dx?, dy?}                                      -> {ids}
edit.clear {ids}                                                    deletes
select.set {ids} -> {count, ids}     select.all {} -> {count}     select.none {}
edit.undo {} -> {undone: "label"}    edit.redo {}
edit.undoGroup.begin {label} ... edit.undoGroup.end {}              several commands, one undo step
```

- `object.rotate` with `copy: true` and an `origin` is how rays, petals, and spokes are made: one
  shape, copies turned about the center.
- To place by eye rather than by box, read `bounds` with `document.node` and move by the
  difference; `object.align` aligns boxes, which is not the same as looking aligned.

## Symbols, repeats, patterns

```text
symbol.new {name, ids}                     -> {name, id: the instance that replaces the art}
symbol.place {name, x, y}                  -> {id}        (x, y) is the instance's center
symbol.list {}                             -> {symbols: [{name, instances, size}]}
object.repeat.radial {ids, instances=8, radius: pt}     -> {id}    live: the source stays editable
object.repeat.grid {ids, rows=3, cols=3, hSpacing: pt, vSpacing: pt}    -> {id}
object.repeat.mirror {ids, angle=90 (a vertical axis), offset: pt}      -> {id}
object.expand {object: true}  (selection)  -> {ids}     a repeat, a symbol instance, or live type becomes plain paths
object.pattern.make {ids, name, tileType: "grid" | "brickByRow" | "brickByColumn" | "hexByRow" | "hexByColumn",
                     width: pt, height: pt, edit: false}  -> {name}     a pattern swatch from the art
pattern.list {}                            -> {patterns: [{name, tile: [x, y, w, h], tileType}]}
```

Use a symbol for a mark that appears many times in one document (an icon in a pattern, a logo on
a sheet of applications). Pass `edit: false` to `object.pattern.make`, or VectorCraft enters
pattern editing mode (`pattern.list` answers `editing: {name}`) until `object.pattern.done {}`.

## Looking

```text
view.fitAll {}       view.fitArtboard {}      view.setZoom {zoom: percent, center?: [x, y]}
view.outline {}      -> true (outlines only) | false (back to preview)     toggles
window.panel {panel: "layers" | "swatches" | "stroke"}                    shows a panel to the person
```

`engine_screenshot(engine_id)` shows you the window, scaled to 1280 px wide. At `view.setZoom
{zoom: 100}` one point is one screen pixel, so a mark 16 pt wide is what a 16 px favicon looks
like.

## Saving and exporting

```text
file.saveAs {path: "name.vectorcraft"}          -> {path, format, background: true, status}
file.save {}                                    the same file again; only for a document that has one
document.export {path, artboard?: index, ...}   -> {path, format, bytes, warnings, files?}   the format is the path's extension
document.exportPdf {path, range?: "1", standard?: "pdfX4", marks?: {trim: true, registration: true},
                    bleed?: {useDocument: true}}  -> {path, bytes, warnings}
document.exportForScreens {folder, artboards?: [index], formats: [{format, scale?: "2x" | "512w" | "64h",
                           width?: px, suffix?, background?, quality?}]}  -> {files: [paths], warnings}
document.exportForScreens {folder, preset: "mobile"}       PNG at 1x, 2x, 3x in subfolders
```

| To get | `document.export` params |
|---|---|
| One artboard as SVG | `{path: "out/logo.svg", artboard: 0}`. Live type stays `<text>`: outline it first, or add `svg: {outlineText: true}`. Smaller: `svg: {decimals: 2, minify: true}`. |
| Every artboard as a PDF, one page each | `{path: "out/logo.pdf"}`. One page: `range: "2"` (1-based). Pages are the artboards' sizes in points. |
| A press PDF | `document.exportPdf` as above: PDF/X-4, trim marks, the document's bleed (`file.new {bleed}`). As run on a 600x420 pt artboard with 8.5 pt bleed: TrimBox 600x420, BleedBox 617x437, PDF 1.6. |
| PNG by width | `{path, artboard: 0, width: 2000, background: "transparent"}` |
| PNG by scale or resolution | `scale: 2` (pixels per point) or `ppi: 300` |
| PNG on a color | `background: "white"` or `"#rrggbb"`: the file is then RGB with no transparency |
| JPEG, WebP | `{path: "x.jpg", width, quality: 85}`; WebP is written lossless |
| Only the selected objects | `{path, selectedOnly: true}` |
| The art's own bounds, not an artboard | `{path, useArtboards: false}` |
| One file per artboard | `{path: "out/logo.png", useArtboards: true, width: 400}` writes `logo-<artboard name>.png` |
| EPS, a PDF-compatible `.ai` | `{path: "x.eps", artboard: 0}`, `{path: "x.ai"}`; read `warnings` (EPS flattens transparency) |

- A PNG's stored resolution follows its pixel size (a 16 px icon of a 240 pt artboard says 5 ppi).
  It is metadata only; say so if a printer asks.
- `exportForScreens` names files `<artboard name><suffix>.<ext>`: `icon@512w.png`, `icon@2x.png`,
  `icon.svg`. Give `suffix: "-32"` for `icon-32.png`. Do not put `<scale>` in a `name` pattern: it
  is empty for vector rows and the suffix is still added (`strip-2x@2x.png`, `strip-.svg`).
- Everything VectorCraft writes: `.vectorcraft .svg .svgz .pdf .ai .eps .png .jpg .gif .webp .tif
  .bmp .tga .psd .dxf .emf .wmf .txt`. No `.ico`.

## Opening and placing

```text
app.open {path}                                   -> {index, title, format, warnings}    a new document tab
file.place {path, link: false}                    -> {ids, format, width, height}        into the active document
imageTrace.make {id?: placed image (default: the selection), preset: "Flat Logo"}  -> {id, paths, anchors, colors, warnings}
imageTrace.expand {id}                            -> {ids}       the tracing becomes plain paths, the picture goes
file.close {}        document.activate {index}
```

- Read as documents here: `.svg`, `.pdf`, `.ai`, `.eps` (each reopened from VectorCraft's own
  export with no warnings). VectorCraft also lists `.svgz .ait .psd .dxf .emf .wmf .afdesign .png
  .jpg .webp .tif .heic .jxl` as readable. Read `warnings` on anything that came from another
  application: they say what did not come in as it was.
- A traced picture is a sketch to draw over, not a logo: a simple sheet traced to 341 paths and
  1,505 anchors. Redraw the shapes with `shape.*` and `path.create`, then delete the tracing.
