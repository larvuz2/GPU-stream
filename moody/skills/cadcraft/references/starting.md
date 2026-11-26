<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Starting a project

The questions that decide a drawing, the defaults to propose for each, and the first commands.
Ask one at a time with `ask_user`, your recommendation first and named in `recommended`; skip
any the person already answered. Write the answers to `README.md` before you draw.

## Intake

| Ask | Why it matters | Propose |
|---|---|---|
| What is it, and who builds or makes it? | A builder, a laser cutter, a print bed, and a client presentation read different drawings | Restate it in one line and confirm |
| What do you need at the end? | Sets the sheets, the scale, and the file | "A PDF drawing set", "A 3D model and render (Blender)", "A file to cut or print", "A DXF or DWG for a consultant" |
| Units and standard? | Fixes the dimension style, text, sheet sizes, and layer names | "Millimeters, ISO", which you recommend outside the US; "Feet and inches, US practice" |
| What is fixed? | Constraints come before design | The measured room or site; mating parts; stock sizes; a machine's limits; a code |
| What is the scale and sheet? | Annotation is sized for one plot scale | See the table below |
| How precise? | Tolerances cost money | General tolerance from the process (drafting.md), tight only where it functions |
| What exists already? | Never redraw what can be opened | DXF, DWG, a dimensioned sketch, a photo with one known size |

For a **building or interior** also ask: the measured dimensions of the space (ask for each wall
length, the ceiling height, and where doors and windows are from a corner); wall construction and
thickness (propose 100 mm interior partitions and 200 to 300 mm exterior walls, or 4 1/2 in and
6 to 10 in, and say it is an assumption until measured); who uses it and how many; what must fit
(a bed size, a table for six, a wheelchair); the code or accessibility standard that applies
(you check against the figures in checking.md and say that a licensed professional signs off).

For a **part or product** also ask: the process and material (laser-cut 3 mm aluminum, FDM in
PLA on a 220 × 220 bed, CNC from 10 mm plate); what it mounts to or holds (hole patterns, a
shaft, a board); loads and which faces matter; fasteners (M4, M8, #8); finish; quantity.

## Units

| Drawing | Unit | Start with | What that sets |
|---|---|---|---|
| Building, interior, product (metric) | millimeter | the drawing the engine opened, or `new {"metric": true}` | `INSUNITS` 4, `MEASUREMENT` 1, dimension style ISO-25 (2.5 mm text and arrows) |
| Site plan, landscape | meter | `new {"metric": true}`, then `units {"insunits": 6}` | Draw 1 unit = 1 m; set the dimension style's sizes for the scale |
| US building | inch (shown as feet and inches) | `new {"metric": false}` | `INSUNITS` 1, `MEASUREMENT` 0, style Standard (0.18 in text); `dimstyle {"name": …, "DIMLUNIT": 4}` for architectural units |
| US mechanical | inch (decimal) | `new {"metric": false}` | as above, `DIMLUNIT` 2 |

`INSUNITS` codes: 1 inch, 2 foot, 4 millimeter, 5 centimeter, 6 meter. The engine's first
drawing is metric millimeters; CADCraft's own `new` with no parameters is imperial. Check with
`units {}` before the first line, and never mix: a drawing has one unit, and everything in it is
drawn at real size in that unit.

## Scale and sheet

Geometry is always 1:1. The scale is how much paper it gets. Pick the sheet first, then the
largest standard scale at which the drawing and its dimensions fit, and size annotation for it.

| Sheet (ISO 5457) | mm | | US sheet | in |
|---|---|---|---|---|
| A4 | 210 × 297 | | ANSI A (Letter) | 8.5 × 11 |
| A3 | 297 × 420 | | ANSI B | 11 × 17 |
| A2 | 420 × 594 | | ARCH C | 18 × 24 |
| A1 | 594 × 841 | | ARCH D | 24 × 36 |
| A0 | 841 × 1189 | | ARCH E | 36 × 48 |

| What | Metric scales (ISO 5455) | US scales |
|---|---|---|
| Site plan | 1:500, 1:200 | 1" = 20', 1" = 40' |
| Floor plan, elevation, section | 1:100, 1:50 | 1/8" = 1'-0" (1:96), 1/4" = 1'-0" (1:48) |
| A room, an interior elevation, a kitchen | 1:25 (US practice) or 1:20, 1:50 | 1/2" = 1'-0" (1:24) |
| Construction detail, joinery | 1:10, 1:5, 1:2, 1:1 | 1 1/2" = 1'-0" (1:8), 3" = 1'-0" (1:4) |
| Part drawing | 1:1 preferred; 2:1, 5:1 enlargements; 1:2, 1:5, 1:10 reductions | 1:1, 2:1, 1:2 |

Does it fit? The paper width a drawing needs is its real width ÷ scale, plus 40 to 60 mm each
side for dimensions. A 4.6 m room at 1:25 is 184 mm of paper: comfortable on A3 (420 mm) with
dimensions and a title block; at 1:20 it is 230 mm, still fine; at 1:50 it would look lost.

With the scale factor S (25 for 1:25, 48 for 1/4" = 1'-0"), annotation drawn in model space is
sized `paper size × S`:

| On paper | At 1:25 | At 1:50 | At 1:100 |
|---|---|---|---|
| Dimension text and notes, 2.5 mm | 62.5 | 125 | 250 |
| Room names, 3.5 mm | 87.5 | 175 | 350 |
| Titles, 5 mm | 125 | 250 | 500 |
| Hatch pattern scale (ANSI31 looks right at) | 15 | 30 | 60 |

Dimensions take the factor from their style: `dimstyle {"name": "PLAN-25", "current": true,
"DIMSCALE": 25}`. Linetypes take it from `ltscale {"scale": S}` (dashes drawn for paper would
be invisible at building size). Text takes it from its `height`.

## The first commands

A metric plan to plot at 1:25, ready to draw (each call is `engine.execute` with the command
and parameters shown; all verified):

```text
units {}                                                    → {"insunits": 4, "lunits": 2, …}: millimeters
linetype {"load": "CENTER"}                                 one name per call; then HIDDEN, DASHED
layer.new {"name": "A-WALL", "color": 7, "lineweight": 0.5}
layer.new {"name": "A-DOOR", "color": 3, "lineweight": 0.25}     … the layer table in drafting.md
layer.new {"name": "A-ANNO-NPLT", "color": 9}
layer.set {"name": "A-ANNO-NPLT", "plot": false}
dimstyle {"name": "PLAN-25", "current": true, "DIMSCALE": 25, "DIMDEC": 0, "DIMBLK": "_ARCHTICK", "DIMTAD": 1}
ltscale {"scale": 25}
layer.current {"name": "A-WALL"}
```

A part at 1:1 needs only the linetypes and layers; ISO-25 is already current.

## The brief, as you save it

```markdown
# <Project>

**What:** a 4.2 × 3.6 m bedroom, furnished, for a client presentation and a builder's plan.
**Deliverable:** A-101 floor plan, A3, 1:25, PDF; a Blender model for two renders.
**Units and standard:** millimeters, ISO; layer names after the AIA guidelines.
**Fixed:** interior 4200 × 3600 (measured); walls 200 (assumed, to confirm); door 900 in the
south wall, 400 from the west corner; window 1200 centered in the north wall, sill 900.
**Must fit:** a 1500 × 2000 bed with 600 clear on both long sides; a wardrobe.
**Open questions:** ceiling height (2700 assumed); the radiator's position.
```
