<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Drafting practice

What a careful drafter does, why, and the CADCraft commands that do it. Parameters and return
values are in cadcraft-commands.md.

## Layers

A layer says what a thing is; its color, line weight, and linetype follow from that. Objects
stay `ByLayer`: overriding one object's color or weight hides what it is from everyone who
opens the file after you. Make the layers before the geometry, and put each object on its layer
as you draw it (`layer.current`), because new objects land on the current layer.

**Buildings** use the discipline-major-minor names of the AIA CAD Layer Guidelines (the layer
part of the US National CAD Standard; ISO 13567 structures names the same way). `A-` is
architecture; `S-` structure, `E-` electrical, `M-` mechanical, `P-` plumbing, `I-` interiors,
`L-` landscape, `C-` civil.

| Layer | Holds | Color | Weight mm | Linetype |
|---|---|---|---|---|
| `A-WALL` | walls cut by the plan | 7 white | 0.50 | Continuous |
| `A-WALL-PATT` | wall hatch (poché) | 8 gray | 0.13 | Continuous |
| `A-DOOR` | door leaves, swings, frames | 3 green | 0.25 | Continuous |
| `A-GLAZ` | windows, glazing | 4 cyan | 0.18 | Continuous |
| `A-FLOR` | floor edges, steps, level changes | 5 blue | 0.25 | Continuous |
| `A-FLOR-OVHD` | what is above the cut: beams, soffits | 9 | 0.18 | HIDDEN |
| `A-FURN` | furniture | 6 magenta | 0.18 | Continuous |
| `A-EQPM` | fixtures and equipment | 6 | 0.25 | Continuous |
| `A-GRID` | column grid | 1 red | 0.18 | CENTER |
| `A-ANNO-DIMS` | dimensions | 2 yellow | 0.18 | Continuous |
| `A-ANNO-TEXT` | room names, notes | 2 | 0.25 | Continuous |
| `A-ANNO-SYMB` | north arrow, section marks, tags | 2 | 0.25 | Continuous |
| `A-ANNO-TTLB` | border and title block | 7 | 0.35 | Continuous |
| `A-ANNO-NPLT` | viewports, construction lines; `plot: false` | 9 | default | Continuous |

**Parts** need few: `OUTLINE` (visible edges, 7, 0.50), `HIDDEN` (hidden edges, 2, 0.25,
HIDDEN), `CENTER` (center lines and marks, 1, 0.18, CENTER), `DIMS` (dimensions and tolerances,
4, 0.18), `HATCH` (section hatch, 8, 0.13), `NOTES` (3, 0.25), `TITLE` (7, 0.35), and for a
cutting file `CUT`, `ENGRAVE`, `SCORE`, one per operation, in the colors the shop asks for
(many laser shops read red as cut and blue as engrave: ask).

Layer `0` stays empty: it is for geometry inside blocks, which then takes the layer the block
is inserted on. `Defpoints` holds dimension definition points and never plots.

```text
linetype {"load": "HIDDEN"}                      a layer's linetype must be loaded first
layer.new {"name": "HIDDEN", "color": 2, "linetype": "HIDDEN", "lineweight": 0.25}
layer.set {"name": "A-FURN", "frozen": true}     hide for a sheet that does not show furniture
layer.set {"name": "A-ANNO-NPLT", "plot": false}
usage {"type": "layers"}                         which layers hold objects, which are empty
```

## Line weights and linetypes

ISO 128 steps line widths by √2: 0.13, 0.18, 0.25, 0.35, 0.50, 0.70, 1.00 mm, and a drawing
uses two or three of them in the ratio 1:2 (0.25 with 0.50, or 0.35 with 0.70 on large sheets).
ASME Y14.2 asks for two: thick 0.6 mm and thin 0.3 mm.

| Line | Weight | Linetype | Used for |
|---|---|---|---|
| Cut | 0.50 to 0.70 | Continuous | walls, slabs, and members the section plane cuts |
| Visible | 0.35 to 0.50 | Continuous | edges of a part; in a plan, edges seen beyond the cut |
| Hidden | 0.25 | HIDDEN | edges behind the surface, things above the cut plane |
| Center | 0.18 | CENTER | axes of holes and symmetric parts, extended 2 to 3 mm past the outline |
| Dimension, extension, leader | 0.18 | Continuous | |
| Hatch | 0.13 | Continuous | section fill; 45° (`ANSI31`) for general material |
| Phantom | 0.18 | PHANTOM | alternate positions, adjacent parts, repeated detail |
| Break, cutting plane | 0.50 | PHANTOM or DASHDOT | where the section is taken |

Line weights show on screen only with `lwdisplay {"on": true}`, and print through the page
setup (`lineweights: true`, the default). `ltscale {"scale": S}` scales every dash pattern;
set it to the sheet's scale factor in a drawing plotted from model space at 1:S.

## Text

ISO 3098 heights step like line widths: 1.8, 2.5, 3.5, 5, 7, 10 mm on paper. Use 2.5 for
dimensions and notes (3.5 on A1 and A0), 3.5 for names and labels, 5 for view titles, 7 for
the drawing title. US practice: 3/32" notes, 1/8" labels, 3/16" to 1/4" titles. Text is upper
case on technical drawings, horizontal or readable from the right, never over a line it can
avoid.

```text
text {"at": [234, 36], "text": "BEDROOM - FLOOR PLAN", "height": 7}
mtext {"at": [1200, 3300], "text": "BEDROOM\\P15.12 m\\U+00B2", "height": 87.5, "width": 1600, "attach": 5}
```

In model space, height is paper height × scale factor (starting.md). `\\P` is a paragraph
break in MTEXT; `%%c` draws ⌀, `%%p` ±, `%%d` °; `\\U+00B2` is a Unicode character (²).
`attach` 1 to 9 is the anchor, 5 the middle. `texts {}` returns every text with its position
and height, and `find {"find": "REV A", "replace": "REV B"}` edits across the drawing.

## Dimensions

The rules that matter (ISO 129-1, ASME Y14.5):

1. **Each size once**, on the view where the feature's shape shows. A dimension given twice
   will one day be changed in one place only.
2. **Dimension what is made or checked**: wall faces and openings, hole centers from a datum
   edge, overall sizes. Never dimension to a hidden line or to a center line that is not a
   feature's.
3. **Chains close.** A row of dimensions along a wall is followed by one overall dimension
   further out, and the row adds up to it: verify the sum from the geometry (checking.md).
   On a part, prefer baseline or ordinate dimensions from one datum so tolerances do not stack.
4. **Smallest closest.** The first row sits 10 mm from the outline on paper, each next row 7 to
   10 mm further (in model units: × scale factor), shorter dimensions inside longer ones, no
   crossing extension lines.
5. **Outside the outline** wherever there is room; interior room sizes may sit inside the room.
6. **Units once**: a general note ("ALL DIMENSIONS IN MILLIMETERS"), then bare numbers. No
   trailing zeros in millimeters (`DIMDEC` 0 for buildings); two or three decimals in inches.
7. **Holes by diameter (⌀), arcs by radius (R)**, repeated features counted: `4X ⌀9`.
8. **Architecture** uses tick marks and dimensions in continuous strings to wall faces (or to
   centerlines of framed walls and of openings: say which in a note); **mechanical** uses
   arrowheads, datums, and tolerances.

```text
dimstyle {"name": "PLAN-25", "current": true, "DIMSCALE": 25, "DIMDEC": 0, "DIMBLK": "_ARCHTICK", "DIMTAD": 1}
dimlinear {"p1": [0, 0], "p2": [600, 0], "at": [300, -350]}          horizontal: `at` is below
dimcontinue {"points": [[1500, 0], [4600, 0]]}                       the chain, from the last dimension
dimlinear {"p1": [0, 0], "p2": [4600, 0], "at": [2300, -700]}        the overall, one row out
dimlinear {"p1": [2300, 200], "p2": [2300, 3800], "at": [2300, 2000], "rotation": 90}
dimdiameter {"handle": "101", "at": [32, 30]}  →  {"handle": "10D"}
dimoverride {"handles": ["10D"], "text": "4X <>"}                    `<>` is the measured value
```

`DIMSCALE` multiplies every size in the style (text, arrows, gaps) and is the sheet's scale
factor for dimensions drawn in model space. `at` places the dimension line, and its side
chooses horizontal or vertical: when `at` lies between the points along the line being
measured the direction is ambiguous and the result measures 0, so give `rotation` (0
horizontal, 90 vertical) whenever `at` is not clearly beside the points. Dimensions are
associative: they follow the geometry they were snapped to when it moves.

## Tolerances

A dimension without a tolerance is not a manufacturing instruction. Give a general tolerance in
the title block and tighten only where function needs it.

| General tolerance, ISO 2768-1 | 0.5 to 3 | over 3 to 6 | over 6 to 30 | over 30 to 120 | over 120 to 400 |
|---|---|---|---|---|---|
| f (fine) | ±0.05 | ±0.05 | ±0.1 | ±0.15 | ±0.2 |
| m (medium), the usual note "ISO 2768-m" | ±0.1 | ±0.1 | ±0.2 | ±0.3 | ±0.5 |
| c (coarse) | ±0.2 | ±0.3 | ±0.5 | ±0.8 | ±1.2 |

(New designs may cite ISO 22081 with a stated general tolerance instead; the table is still
what shops quote.) What processes hold without special effort: laser and waterjet cutting ±0.1
to ±0.2 mm; CNC milling ±0.05 to ±0.1; FDM printing ±0.2 to ±0.5 or ±0.5 %; site carpentry
±3 to ±5 mm; masonry ±10.

- **Fits** (ISO 286): a shaft in a hole is `⌀10 H7/g6` for a sliding fit, `H7/h6` locating,
  `H7/p6` pressed. Write it as an override: `dimoverride {"handles": […], "text": "<> H7"}`.
- **Limits**: `dimoverride {"handles": […], "text": "<> %%p0.05"}` reads "30 ±0.05".
- **Geometric tolerances** (ISO 1101, ASME Y14.5): a feature control frame says what
  characteristic, how much, and from which datums. Position of a hole pattern is the common
  one: `tolerance {"at": [128, 40], "symbol": "position", "tol1": {"value": 0.1, "diameter":
  true, "material": "M"}, "datums": ["A", "B"]}` draws ⌖ ⌀0.1 Ⓜ A B. Symbols: position,
  flatness, perpendicularity, parallelism, concentricity, circularity, cylindricity,
  straightness, angularity, symmetry, surfaceprofile, lineprofile, circularrunout, totalrunout.
  Datum feature labels are text you place; CADCraft has no datum-feature symbol command.
- **Clearance holes** (ISO 273, medium): M3 3.4, M4 4.5, M5 5.5, M6 6.6, M8 9, M10 11, M12
  13.5. US: #6 0.150", #8 0.177", #10 0.201", 1/4" 0.266" (close fit).

## Design intent: constraints and parameters

Draw a part so that changing one number changes the part correctly. Geometric constraints
(`gccoincident`, `gcparallel`, `gcperpendicular`, `gctangent`, `gchorizontal`, `gcvertical`,
`gcconcentric`, `gcequal`, `gcsymmetric`, `gcfix`, or `autoconstrain` to infer them) hold
relations; dimensional constraints hold sizes and can be expressions of named parameters.

```text
dimconstraint {"type": "diameter", "h1": "105", "value": 30, "name": "bore"}
parameters {"name": "bore", "value": 36}        the circle is re-solved: radius 18
autoconstrain {"handles": ["100"]}              a rectangle's sides: 4 constraints added
gcfix {"h1": "100", "p1": "v0"}                 the datum corner stays where it is
parameters {"name": "wall", "value": 3}         a user parameter
dimconstraint {"type": "linear", "h1": "100", "p1": "v0", "h2": "100", "p2": "v1", "expr": "40 * wall", "name": "length"}
constraints.dof {}                              {"dof": 1, "status": "under"}: what can still move
```

`p1` and `p2` name a point of the object: `"start"`, `"end"`, `"mid"`, `"center"`, or `"v0"`,
`"v1"` for a polyline's vertices. Constrain what the design means, not everything: fix the
datum first (a free shape is re-solved by moving whichever end the solver likes), tie the
features that must move together, name the dimensions someone will change. A solved value
comes back within the solver's tolerance (18.000000000168846 for 18), so compare with a
tolerance and round what you report. Constraints and parameters are saved in the DXF.

## Blocks

Anything that repeats is a block: a door, a chair, a title block, a bolt. Draw it once at real
size on layer `0` or its own layer, with a sensible base point (a door at its hinge, furniture
at a corner), then insert it.

```text
block {"name": "BED-1500x2000", "base": [0, 0], "handles": ["10B", "10C", "10D", "10E"], "keep": "delete", "description": "Double bed 1500 x 2000 mm"}
insert {"name": "BED-1500x2000", "at": [2800, 300], "rotation": 0}
insert {"name": "bracket", "file": "bracket.dxf", "at": [60, 0], "scale": 0.03937}     another drawing as a block
count {}                                             {"blocks": {"BED-1500x2000": 1}}: a schedule's quantities
```

Name blocks by what and size. `keep: "delete"` removes the originals (insert the block where
you want it); `"convert"` (the default) replaces them with a reference in place. Attributes
(`attdef`, then `insert … "attribs": {"TAG": "value"}`) carry a door number or a part number
that `dataextraction` can list.

## Hatches

A hatch needs a closed boundary: a closed polyline (`handles`) or a point inside an enclosed
area (`points`). Poché cut walls (`ANSI31`, or `SOLID` in gray for presentation plans); hatch
sections of parts at 45°, adjacent parts at opposite angles. Put hatches on their own thin
layer and send them behind (`draworder {"handles": […], "order": "back"}`).

```text
hatch {"handles": ["100"], "pattern": "ANSI31", "scale": 15}
hatch {"points": [[21, 1]], "pattern": "SOLID"}
hatch.patterns {}                                    the 23 built-in patterns
```

## Sheets

Model space holds the thing at real size. A layout is a sheet of paper in millimeters, with a
viewport that looks at the model at a scale. One layout per sheet; name it by sheet number.

```text
layout.rename {"from": "Layout1", "to": "A-101 Plan"}
layout.set {"name": "A-101 Plan"}
pagesetup {"layout": "A-101 Plan", "device": "CADCraft PDF", "paper": "A3", "landscape": true, "plotStyleTable": "monochrome.ctb"}
layer.current {"name": "A-ANNO-NPLT"}                the viewport's frame must not plot
mview {"p1": [15, 55], "p2": [405, 282]}  →  {"viewports": ["11F"]}
viewport.set {"handle": "11F", "scale": "1:25", "center": [2300, 1825], "locked": true}
layer.current {"name": "A-ANNO-TTLB"}                border and title block, in paper millimeters
rectang {"p1": [10, 10], "p2": [410, 287]}
zoom {"mode": "extents"}                             a layout does not frame itself
exportpdf {"path": "exports/A-101-plan.pdf", "layout": "A-101 Plan"}
```

- **Border** (ISO 5457): 10 mm from the trimmed edge, 20 mm on the left filing edge of sheets
  that are bound. On A3 landscape (420 × 297): from (10, 10) to (410, 287), or from (20, 10).
- **Title block** (ISO 7200): bottom right, at most 180 mm wide, holding the owner, the title,
  the drawing number, the sheet (1 of n), the revision, the date, who drew and who approved,
  the scale, the sheet size, the general tolerance, and for parts the material and the
  projection symbol (first angle in ISO practice, third angle in the US: say which).
- **`monochrome.ctb`** prints every color black, which is what a drawing set wants; colors on
  screen then only tell layers apart. `grayscale.ctb` keeps values.
- **The viewport scale** is exact (`"1:25"` becomes 0.04) and `locked` keeps a stray zoom from
  changing it. Center it on the model point you want in the middle; check that the drawing and
  its dimensions fall inside: view height in model units is viewport height × scale factor.
- **Several views on a sheet**: one `mview` each, each with its scale, a title under each
  ("PLAN 1:25"), and `viewport.set {"handle": …, "freeze": ["A-FURN"]}` to hide layers in one.
- **Plotting model space without a layout** (`export` to PDF, `plot {"layout": "Model", "scale":
  "1:25", "paper": "A3"}`) is for checks and quick prints; an issued sheet has a title block.

## Views

- **Plan**: a horizontal cut at about 1200 mm (4 ft) above the floor, looking down. What the
  cut passes through is heavy; what is below is lighter; what is above is dashed.
- **Elevation and section**: draw them aligned with the plan (project points across with
  `xline` on the non-plotting layer) so widths cannot disagree. A section's cut is marked on
  the plan with a cutting-plane line and view letters.
- **Part views**: front, top, and right (third angle) or front, top below, and left on the
  right (first angle), aligned, sharing dimensions' datums; a section where the inside matters;
  a detail view at a larger scale for small features. CADCraft has no model to project from:
  every view is drawn, so check that shared dimensions agree between views.
- **A north arrow and a graphic scale bar** on plans; a scale bar still reads true when the
  PDF is printed at the wrong size.
