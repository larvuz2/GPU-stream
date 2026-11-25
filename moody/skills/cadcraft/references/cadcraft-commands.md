<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# CADCraft commands

How to call CADCraft 0.20.1, what its commands take and return, and the traps. Everything here
was run on a cloud engine unless a line says "catalog": those come from `engine.commands` and
were not run.

## Calling CADCraft

`engine_call(engine_id, method, params)` sends one request on CADCraft's control channel and
returns its result, or the error CADCraft gave.

| Method | Params | Does |
|---|---|---|
| `engine.execute` | `{command, params}` | Runs any command with JSON parameters. Never opens a dialog. This is the one you use. |
| `engine.commands` | | Every command (517): `id`, `label`, `menu`, `aliases`, `params` (its parameter doc), `enabled`. |
| `drawing.inspect` | `{entities?: bool, limit?}` | The open drawing: `path`, `title`, `dirty`, `counts` by type, `entityCount`, `extents`, `layers`, `dimStyles`, `textStyles`, `blocks`, `layouts`, `space`, `currentLayer`, `view`, what reading the file left out (`skipped`, `readNotes`). Pass `"entities": false` unless you want every object. |
| `cmdline.input` | `{text}` | Types a line at the command line as a person would: `line 0,0 @10,0 @0,5 c`. Replies the prompt state; a refused line still replies ok, with `error`. Use it to show the person how they would do it; use `engine.execute` to do it. |
| `cmdline.state`, `cmdline.key` | `{key: "enter" \| "escape"}` | The prompt, and Enter or Escape. Escape cancels a command the person left running. |
| `ui.inspect` | | The window: `session.documents` (`index`, `title`, `path`, `dirty`, `active`), `session.running`, `ui.dialog`, the view, `perf`. |
| `ui.screenshot` | `{path?}` | A PNG of the window, 1920 × 1050. Give a `path` in a folder that exists; `engine_screenshot` is simpler for showing the person. |
| `ui.render` | `{path?, width?, height?, fit?, window?, background?, plot_style?}` | A picture of the drawing without the interface. `background`: `"dark"`, `"white"`, `"paper"`, `"#rrggbb"`; `plot_style: "monochrome.ctb"` for how it prints. **Always give `path`**: the reply carries the PNG as base64 either way, and without a path that is all you get. |
| `app.open`, `app.save`, `app.quit` | `{path}` | Open a drawing; save (Save As with a `path`); quit. |
| `control.methods`, `ping` | | The methods; a health check answering `"pong"`. |

CADCraft gives up on a request after 60 s and says whether it had started: an error ending
`(may-have-run)` means inspect the drawing before you send it again; `(not-run)` is safe to
repeat. Calls took about 0.3 s each.

**Finding a command.** `engine.commands`, then read `params`. Ids are the classic CAD command
names in lower case (`line`, `offset`, `dimlinear`, `mview`), with dotted variants for menu
entries (`circle.3p`, `layer.new`, `zoom.extents`).

## Units and addressing

- **Lengths and coordinates** are drawing units, `[x, y]` (a third value is z and is kept, but
  nothing draws in 3D). The unit is the drawing's `INSUNITS`: 4 is millimeters, 1 inches.
- **Angles** in parameters are degrees, counterclockwise from +X. Angles in results from
  `entities` (`rotation` of a dimension, arc `start` and `end`) are radians.
- **Paper space** is millimeters on the sheet: in a layout, `[x, y]` is from the sheet's lower
  left corner.
- **Line weights** are millimeters (`0.5`); **colors** are index numbers 1 to 255 (1 red, 2
  yellow, 3 green, 4 cyan, 5 blue, 6 magenta, 7 white or black, 8 and 9 grays), names, or
  `"r,g,b"`.
- **Objects** are named by `handle`, a hex string (`"1A2"`). Creating commands return `handle`
  (one object) or `handles` (several); `line` always returns `handles`. Handles restart at
  `"100"` in each drawing and are kept in the saved file.
- **Paths** may be relative: CADCraft runs in the project folder, so `"exports/plan.pdf"` and
  `"room.dxf"` land there. `export`, `exportpdf`, `plot`, and `saveas` make missing folders;
  `ui.screenshot` does not.
- **Documents** are tabs, addressed by `index` (`ui.inspect` → `session.documents`). Index 0
  is an empty `Drawing1` that CADCraft opens beside the project's drawing; commands act on the
  active document: `document.switch {"index": 1}`.

## Reading state

```text
drawing.inspect {"entities": false}
entities {"type": "Dimension", "layer": "A-ANNO-DIMS", "window": [[0, 0], [5000, 5000]], "limit": 200, "offset": 0}
```

`entities` returns `{count, returned, offset, entities: [{handle, type, layer, color,
geometry}]}`. `type` is the name `counts` uses: `Line`, `Polyline`, `Circle`, `Arc`,
`Dimension`, `Hatch`, `Text`, `MText`, `Block Reference`, `Viewport`, `Multileader`,
`Tolerance`. Geometry by type: a line has `a` and `b`; a circle `center`, `radius`; a polyline
`vertices: [{p: {x, y}, bulge}]`, `closed`; a dimension `p13`, `p14`, `defpt`, `kind`,
`measurement`, `text`, `style`. `selected: true` limits it to the person's selection.

| Command | Returns |
|---|---|
| `shapes {type?, layer?, window?}` | every closed shape: `handle`, `area`, `perimeter`, `centroid`, `winding`, `selfIntersection`, `duplicateVertices` |
| `loops {}` | closed loops that separate lines and arcs form, and `openChains` with their `ends` and `gap` |
| `texts {contains?, layer?}` | every text as plain text with `at`, `height`, `style` |
| `usage {"type": "layers"}` | per layer (or `blocks`, `textstyles`, `linetypes`): `entities`, `empty`, `used` |
| `count {}` | block references by name |
| `dist {p1, p2}` | `distance`, `dx`, `dy`, `angle` (degrees) |
| `area {points}` or `{handle}` | `area`, `perimeter` |
| `volume.measure {points \| handle, height}` | `volume`, `area` |
| `measuregeom {"mode": "radius", "handle"}` | `radius`, `diameter` |
| `list {handles}`, `properties {handles}` | everything about objects, `bounds` included |
| `getvar {name}`, `setvar {name, value}` | a system variable: `DIMSCALE`, `LTSCALE`, `INSUNITS`, `CLAYER`, `TEXTSIZE` |
| `layer {}` | every layer with color, linetype, line weight, on, frozen, locked, plot |
| `layout.list {}` | layouts with their page setup and viewports |
| `dimstyle.list {"name": "ISO-25"}` | a dimension style's every setting |
| `constraints.inspect {}`, `constraints.dof {}` | constraints, parameters, and how many degrees of freedom remain |
| `status {}`, `audit {}` | a summary line; errors found |

## Traps (each seen in a run)

- **A continued dimension's `measurement` is stale.** Dimensions made by `dimcontinue` report
  the base dimension's value in `entities`. Compute from `p13` and `p14` (checking.md). The
  drawing and the saved file are right.
- **`dimlinear` with `at` on the measured line measures 0.** Give `rotation` (0 or 90).
- **New objects take the current layer, viewports too.** A viewport made while a plotting layer
  is current prints its frame. Commands have no `layer` parameter: `layer.current` first.
- **A layer's linetype must be loaded first** (`linetype {"load": "CENTER"}`), one name per
  call: `"CENTER,HIDDEN"` is refused as one unknown name. `"*"` loads the whole library (19).
- **`{last}` is not a handle here.** CADCraft's command-line tool accepts it; the channel wants
  the hex handle the previous command returned.
- **A new drawing from `new {}` is imperial.** Say `{"metric": true}`. The engine's first
  drawing is already metric.
- **`saveas` renames the open drawing; `export` does not.** After `saveas {"path":
  "exports/part-cut.dxf"}` you are editing that file. Use `export` for copies in other formats
  and `saveas` to start a variant on purpose.
- **The engine opens the newest drawing in the folder**, which after an export or a save may
  not be the one you mean. Check `drawing.inspect` → `path` at the start of every session and
  `open` the right one.
- **A layout does not frame itself.** After `layout.set`, `zoom {"mode": "extents"}` before a
  screenshot.
- **`ui.screenshot` shows the command line's last messages over the bottom of the drawing.**
  For a clean picture use `ui.render`.
- **An unconstrained shape moves where the solver likes.** A length constraint on a free
  rectangle moved its first corner to x = -39.99999886, not its second to 120. Hold the
  shape's relations (`autoconstrain`) and fix the datum (`gcfix {"h1": "100", "p1": "v0"}`)
  before sizing it: then the second corner lands on 120 exactly. Without them, expect solved
  values within about 1e-6 of the number, on whichever side moved.
- **`massprop {}`** answers "Select one or more regions" and takes regions only; `region`
  was not made to work in these runs. For areas and centroids use `area` and `shapes`, which
  need no region.
- **`close {}` closes a drawing with unsaved changes without asking.** Save first.
- **Unknown commands and wrong parameters are refused with a message**
  (``invalid parameters for `export`: …``), which is your cue to read the command's `params`.
- **Text in PDFs is drawn, not typed**: CADCraft's stroke font becomes lines, so a PDF's text
  cannot be searched or selected. A text style with a TrueType font (`style {"name": "NOTES",
  "font": "DejaVu Sans", "current": true}`) is the way to try for real text; not checked.
- **Two engines running at once do not see each other's new files** until `engine_send` carries
  them across (handoff.md).

## Drawing

```text
line {"points": [[600, 200], [600, 1100]]}                              → {"handles": ["104"]}
pline {"vertices": [[0, 0], [600, 0], [600, 200], [200, 200]], "closed": true}   → {"handle": "100"}
pline {"vertices": [{"p": [0, 0], "bulge": 1}, [10, 0]]}                bulge 1 is a half circle to the next vertex
rectang {"p1": [0, 0], "p2": [120, 80], "fillet": 10}                   → {"handle"}; also "chamfer": [d1, d2]
circle {"center": [15, 15], "diameter": 9}                              or "radius"; circle.3p, circle.ttr
arc {"center": [600, 200], "radius": 900, "start": 0, "end": 90}        degrees, counterclockwise
polygon {"sides": 6, "center": [300, 0], "radius": 20}
ellipse {"center": [0, 0], "major": [50, 0], "ratio": 0.5}
xline {"base": [0, 0], "ver": true}                                     a construction line; keep on a non-plotting layer
text {"at": [0, -50], "text": "REV A", "height": 5, "justify": "MC"}
mtext {"at": [1200, 3300], "text": "BEDROOM\\P15.12 m\\U+00B2", "height": 87.5, "width": 1600, "attach": 5}
table {"at": [0, -5], "rows": 2, "cols": 3, "title": "SCHEDULE", "header": ["MARK", "W", "H"], "cells": [["D1", "900", "2100"], ["W1", "1200", "1200"]]}
mleader {"points": [[100, 80], [122, 94]], "text": "3 THK 6061-T6"}     arrow first, text at the last point
centermark {"handles": ["101", "102"]}                                  center lines on circles, on the CENTER linetype
hatch {"handles": ["100"], "pattern": "ANSI31", "scale": 15}            or "points": [[x, y]] inside an enclosed area
imageattach {"path": "sketch.png", "at": [0, 0], "width": 4200}         an underlay to draw over; the path is relative to a saved drawing's folder
```

## Modifying

```text
move {"handles": ["100"], "delta": [0, 20]}          copy {"handles": […], "delta": [0, 300]}
rotate {"handles": […], "base": [200, 0], "angle": 30, "copy": true}
mirror {"handles": […], "p1": [0, -100], "p2": [10, -100]}             → the mirrored copies' handles
scale {"handles": […], "base": [0, 0], "factor": 2}
offset {"handle": "104", "distance": 1, "side": [30, 5]}               → the new object; `side` is a point on the side to offset to
trim {"handle": "106", "pick": [30, 5]}                                 quick trim at the picked piece → the pieces left
fillet {"handle": "104", "polyline": true, "radius": 2}                 every corner; or {"h1", "p1", "h2", "p2", "radius"}
stretch {"window": [[38, -1], [46, 11]], "delta": [5, 0]}               moves the vertices inside the window
arrayrect {"handles": ["101"], "rows": 2, "cols": 2, "rowSpacing": 50, "colSpacing": 90, "associative": false}
arraypolar {"handles": […], "center": [200, 0], "count": 6, "associative": false}   → {"created": 5}
erase {"handles": ["11D"]}                           explode {"handles": ["100"]} → the pieces' handles     join {"handles": […]}  (join: catalog)
properties.set {"handles": ["120"], "layer": "A-ANNO-NPLT"}             also color, linetype, lineweight, and geometry fields
select {"window": [[-1, -1], [11, 6]]}                                  then commands without `handles` act on the selection
find {"find": "REV A", "replace": "REV B"}
undo {"count": 1}                                    redo {}
```

`associative: false` on arrays gives plain copies you can dimension and constrain one by one;
the default makes one array object. Commands that take `handles` fall back to the selection
when it is left out, so name the handles and leave the person's selection alone.

## Layers, styles, blocks

```text
layer.new {"name": "A-WALL", "color": 7, "lineweight": 0.5, "linetype": "Continuous", "current": true}
layer.set {"name": "A-FURN", "frozen": true}          also on, locked, plot, color, linetype, lineweight, newName
layer.current {"name": "A-WALL"}
laydel {"names": ["JUNK"]}                            deletes the layer and everything on it
laymrg {"from": ["Layer1"], "to": "A-WALL"}           moves the objects, deletes the layer
linetype {"load": "HIDDEN"}                           ltscale {"scale": 25}          lwdisplay {"on": true}
dimstyle {"name": "PLAN-25", "current": true, "DIMSCALE": 25, "DIMDEC": 0, "DIMBLK": "_ARCHTICK", "DIMTAD": 1}
style {"name": "NOTES", "font": "DejaVu Sans", "current": true}
block {"name": "BED-1500x2000", "base": [0, 0], "handles": […], "keep": "delete"}
insert {"name": "BED-1500x2000", "at": [2800, 300], "rotation": 90, "scale": 1}
insert {"name": "bracket", "file": "bracket.dxf", "at": [60, 0]}        a drawing file as a block
import {"path": "exports/room.dwg", "at": [0, 40], "scale": 1}          a file's objects, layers, and blocks, loose
purge {}                                              unused blocks, layers, styles
```

`DIMBLK` arrowheads: `"_ARCHTICK"` for architectural ticks; leave it out for filled arrows.
`DIMTAD` 1 puts text above the line (the ISO-25 default), `DIMDEC` is the decimals, `DIMLUNIT`
4 architectural feet and inches (accepted; its display was not examined).

## Dimensions and tolerances

```text
dimlinear {"p1": [0, 0], "p2": [600, 0], "at": [300, -350]}             → {"handle"}; "rotation": 90 forces vertical
dimcontinue {"points": [[1500, 0], [4600, 0]]}                          → {"handles"}; continues the last linear dimension
dimbaseline {"points": [[60, 0]]}                                       from the last linear dimension's first point
dimaligned {"p1": [0, 0], "p2": [30, 40], "at": [0, 40]}
dimangular {"vertex": [0, 0], "p1": [10, 0], "p2": [0, 10], "at": [12, 12]}
dimdiameter {"handle": "101", "at": [32, 30]}          dimradius {"center": [10, 70], "point": [2.93, 77.07]}
dimoverride {"handles": ["10D"], "text": "4X <>"}
tolerance {"at": [128, 40], "symbol": "position", "tol1": {"value": 0.1, "diameter": true, "material": "M"}, "datums": ["A", "B"]}
dimconstraint {"type": "diameter", "h1": "105", "value": 30, "name": "bore"}
parameters {"name": "bore", "value": 36}               parameters {}  lists them
autoconstrain {"handles": ["100"]}                     → {"added": 3}
```

## Sheets and output

```text
layout.rename {"from": "Layout1", "to": "A-101 Plan"}      layout.new {"name": "A-102"} → {"name", "viewport"}
layout.delete {"name": "Layout2"}                          layout.set {"name": "Model"}
pagesetup {"layout": "A-101 Plan", "device": "CADCraft PDF", "paper": "A3", "landscape": true, "plotStyleTable": "monochrome.ctb"}
mview {"p1": [15, 55], "p2": [405, 282]}                   → {"viewports": ["11F"]}
viewport.set {"handle": "11F", "scale": "1:25", "center": [2300, 1825], "locked": true}
exportpdf {"path": "exports/A-101-plan.pdf", "layout": "A-101 Plan"}     → {"path", "pages": 1, "bytes"}
plot {"path": "exports/check.pdf", "layout": "Model", "paper": "A4", "scale": "1:5", "landscape": true}
publish {"path": "exports/set.pdf"}                        one PDF per sheet: set-Model.pdf, set-A-101 Plan.pdf
export {"path": "exports/room.dxf"}                        the extension picks the format: dxf, dwg, svg, png, pdf
saveas {"path": "exports/part-r2000.dxf", "version": 2000}  DXF version 2000 to 2018 (default 2018); renames the drawing
app.save {}                                                → {"path", "bytes"}
```

What each format holds (every one was written and parsed):

| Format | Holds | Use for |
|---|---|---|
| DXF | everything: geometry, layers, blocks, dimensions, hatches, layouts with page setups, constraints; version 2018 (`AC1032`) by default | the working file; fabrication; the hand-off to Blender |
| DWG | the same drawing, version 2018, less what the DWG library does not model | sending to someone who asks for DWG |
| PDF | vector lines at the sheet's size (an A3 layout gives a 420 × 297 mm page); text as strokes | issued drawings |
| SVG | model space flattened to polylines and paths in one group: no layers, hatches as hundreds of strokes, origin moved, y down; `viewBox` is in drawing units and `width` is 1600 px | the web, illustration tools |
| PNG | 2400 × 1600 pixels of model space on the dark canvas (`export`), or any size and background with `ui.render` | previews, the conversation |

`export` to `stl`, `step`, `iges`, `obj`, or `gltf` is refused: CADCraft has no 3D. Model
space has no paper: `export` to PDF or `plot` of `Model` fits it to a sheet for a check print,
and an issued sheet comes from a layout.

## Files and sessions

```text
open {"path": "room.dxf"}                    → {"index", "entities", "warnings"}: read `warnings` for what was left out
new {"metric": true}                         → {"index", "title": "Drawing2"}; unsaved until `saveas`
document.switch {"index": 1}                 close {}
drawingrecovery {}                           → {"files": […]}: autosaves a cut-off session left
drawingrecovery {"action": "open", "path": "…/.cadcraft/autosave/drawing.dxf_….sv$"}    then saveas over the original
drawingrecovery {"action": "discard", "path": "…"}      (catalog)
```

Stopping the engine saves every drawing with unsaved changes (the file as it was stays beside
it as `<name>.dxf.bak`, and a drawing never saved becomes `<Title>.dxf`). `.cadcraft/` in the
project folder is CADCraft's own (settings, logs, autosaves): leave it alone. From
`engine_exec`, `cadcraft-cli info <file>` summarizes a drawing without opening it in the
window, and `cadcraft-cli convert in.dwg out.dxf` converts one.
