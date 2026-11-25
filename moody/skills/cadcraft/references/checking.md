<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Checking a design

A check is a number read from the drawing and compared with a number from the brief, a
standard, or the process. Run the ones that apply before every checkpoint and before anything is
issued, and report them as a table: what, required, measured, pass or not. A failed check is
the person's decision (change the design, or accept and note it), never something to fix
quietly or leave out. Record the table in `checks.md`.

You check against published figures; you are not the code official or the engineer of record.
Say so once, where it matters: "This meets the clearances I checked; a licensed professional
confirms code compliance and structure."

## The drawing itself

| Check | Command | Pass |
|---|---|---|
| The file is sound | `audit {}` | `errors: 0` |
| No doubled geometry (a doubled line is cut twice and counted twice) | `overkill {}` | 0 deleted; if it deleted any, say how many |
| Outlines that must be closed are | `shapes {"layer": "A-WALL"}` lists closed shapes with `area`, `perimeter`, `selfIntersection`; `loops {}` lists `openChains` with each `gap` | every outline you expect appears in `shapes`; no open chain with a small gap; `selfIntersection: null` |
| Everything is on its layer | `usage {"type": "layers"}`, `entities {"layer": "0"}` | layer `0` holds nothing in model space; no layer is unexpectedly empty |
| Units are what the brief says | `units {}` | `insunits` 4 for millimeters, 1 for inches |
| Extents are plausible | `drawing.inspect {"entities": false}` → `extents` | a room is thousands of units across in millimeters, not 4.6 (drawn in meters) or 181 (inches) |
| Text is the right size and spelled | `texts {}` | heights = paper height × scale; read every string |
| Nothing stray far away (it wrecks zoom-extents and plots) | `extents` again; `entities {"window": […], "crossing": false}` | extents hug the design |

## Dimensions that close

Read every dimension back and add them up; never trust the picture.

```text
entities {"type": "Dimension", "limit": 200}
```

For each linear dimension take `p13` and `p14` (the points measured) and the `rotation` under
`kind.linear` (radians; 0 horizontal), and compute the length along that direction:
`|Δx·cos r + Δy·sin r|`. **Do not use the `measurement` field of a continued dimension**: in
CADCraft 0.20.1 every dimension made by `dimcontinue` reports its base dimension's value there
(a 600, 900, 3100 chain reports 600 three times), though the drawing shows, and the saved DXF
holds, the right values.

- Each chain's parts sum to its overall: 600 + 900 + 3100 = 4600; 1700 + 1200 + 1700 = 4600.
- Opposite sides agree: the top chain and the bottom chain have the same total.
- Inside plus walls equals outside: 4200 + 2 × 200 = 4600.
- A dimension equals the geometry it claims: compare with `dist {"p1": …, "p2": …}` (returns
  `distance`, `dx`, `dy`, `angle`).
- No dimension carries a typed number in place of its measurement, except counted callouts
  (`4X <>`): look for `text` that has no `<>` in it.
- Areas are measured: `area {"points": […]}` or `area {"handle": "100"}` returns `area` and
  `perimeter` in square drawing units (15,120,000 mm² is 15.12 m²; divide by 1e6).

## Clearances for people

Measure with `dist` between the two things, at the tightest point. Figures are common minimums;
the code where the building stands governs.

| Clearance | Metric | US | Source |
|---|---|---|---|
| Door clear opening, accessible | 815 mm (a 900 leaf gives about 850) | 32 in | ADA 2010 Standards 404.2.3 |
| Door clear opening, preferred | 850 to 900 mm | 34 to 36 in | common practice |
| Corridor, dwelling | 900 mm | 36 in | IRC R311.6 |
| Accessible route | 915 mm, 815 at a point | 36 in, 32 in | ADA 403.5.1 |
| Wheelchair turning circle | 1525 mm diameter | 60 in | ADA 304.3.1 |
| Clear floor space at a fixture | 760 × 1220 mm | 30 × 48 in | ADA 305.3 |
| Maneuvering space, pull side of a door, latch side | 455 mm beside the latch | 18 in | ADA 404.2.4 |
| Beside a bed | 600 mm one side at least, 750 preferred | 24 to 30 in | common practice |
| In front of a wardrobe or drawers | 900 mm | 36 in | common practice |
| Kitchen work aisle, one cook | 1065 mm | 42 in | NKBA guideline 6 |
| Kitchen walkway | 915 mm | 36 in | NKBA guideline 7 |
| Dining: table edge to wall, to pass behind a chair | 900 to 1100 mm | 36 to 44 in | common practice |
| In front of a toilet | 530 mm | 21 in | IRC R307.1 |
| Toilet centerline to a side wall | 380 mm | 15 in | IRC R307.1 |
| Habitable room ceiling height | 2130 mm | 7 ft | IRC R305.1 |
| Stair: rise max, run (step depth) min, width min | 196, 254, 915 mm | 7 3/4, 10, 36 in | IRC R311.7 |
| Stair comfort rule | 2 × rise + run = 600 to 640 mm | 24 to 25 in | Blondel's rule |
| Guard height | 915 mm dwelling, 1065 elsewhere | 36, 42 in | IRC R312, IBC 1015 |

Also look: a door's swing arc crosses no furniture and no other swing; a door opens against a
wall, not into the room's middle; windows are not behind wardrobes; every room is reachable.

## Parts: will it go together

- **Mating features agree**: hole spacing on this part equals the spacing on the part it bolts
  to (compare the two drawings' `dist` values); a shaft is smaller than its hole by the fit.
- **Clearance holes** are the standard size for the fastener (drafting.md): M8 needs ⌀9.
- **Tool and head access**: a socket or driver reaches every fastener; washers do not overlap
  an edge or each other (washer outside diameter is about 2 × the thread).
- **Symmetry is deliberate**: a part that fits both ways is drawn symmetric; one that must not
  is made obviously asymmetric.

## Sheet metal and laser, waterjet, or plasma cutting

With material thickness t:

| Rule | Minimum |
|---|---|
| Hole diameter | ≥ t (laser), ≥ 1.2 t (punch) |
| Hole edge to part edge | ≥ 2 t (1.5 t at the least) |
| Between holes, edge to edge | ≥ 2 t |
| Slot or tab width | ≥ t, better 1.5 t |
| Inside corner | a radius ≥ 0.5 t, never a sharp corner (it starts cracks and the cutter rounds it anyway) |
| Bend inside radius | ≥ t for steel and soft aluminum; 2 to 3 t for 6061-T6 |
| Hole or edge to a bend line | ≥ 2.5 t + bend radius |
| Flange length | ≥ 4 t |

- **The cutting file** is a DXF at 1:1 in the shop's unit holding only closed outlines on the
  cut layer: no dimensions, text, hatches, center lines, title block, or duplicate lines. Make
  it as a copy: `saveas` to `exports/<part>-cut.dxf`, `laydel {"names": ["DIMS", "CENTER", …]}`,
  `overkill {}`, `shapes {}` (every outline closed, none self-intersecting), `app.save`, then
  reopen the working drawing. Say the unit and thickness in the file name or a note to the shop.
- **Kerf** (0.1 to 0.3 mm for laser, about 1 mm for waterjet) is the shop's to compensate;
  draw nominal sizes and say so. Ask the shop which DXF version it wants (`saveas … "version":
  2000` is the safest).
- Parts nest with at least t between them (and at least 3 mm).

## CNC milling

- Inside corners in a pocket have the cutter's radius: draw them filleted, radius ≥ 1/3 of the
  pocket depth (a ⌀6 cutter gives R3 and reaches about 18 mm deep).
- Pocket depth ≤ 4 × cutter diameter; walls ≥ 0.8 mm in metal, 1.5 mm in plastic.
- Holes in standard drill sizes; threads specified by name (M6 × 1), depth ≤ 3 × diameter.
- Everything dimensioned from the datum faces the part is clamped against.

## 3D printing (FDM, 0.4 mm nozzle)

A drawing becomes a print through Blender (handoff.md); design for the printer in the drawing.

| Rule | Value |
|---|---|
| Wall thickness | ≥ 0.8 mm (two lines), 1.2 to 2 mm for strength |
| Smallest feature in the plane | ≥ 0.8 mm; text embossed ≥ 0.6 mm wide and high |
| Holes print small | add 0.2 to 0.4 mm to the diameter, or drill after |
| Sliding fit between parts | 0.2 to 0.3 mm gap per side; press fit 0.1 mm or less |
| Overhang without support | up to 45° from vertical |
| Bridge without support | up to about 10 mm reliably |
| Layer height | 0.1 to 0.3 mm; vertical sizes land on multiples of it |
| Bed adhesion | the first layer spreads about 0.2 mm ("elephant foot"): chamfer bottom edges 0.5 mm where a fit matters |
| Size | inside the bed with 5 mm to spare (220 × 220 × 250 mm is a common bed) |

- Orient so the load does not pull layers apart, and so the largest flat face is on the bed.
- Resin (SLA) prints hold ±0.1 mm and want 0.5 mm walls and drain holes in hollow parts.
- The STL must be one closed volume in millimeters: the hand-off checks zero non-manifold
  edges and compares the volume with area × thickness from the drawing
  (`volume.measure {"handle": …, "height": t}`, or the outline's `area` minus the holes').

## The report

```markdown
| Check | Required | Measured | |
|---|---|---|---|
| Chain along the south wall closes | 600 + 900 + 3100 = 4600 | 4600 | pass |
| Room area | 15 m² or more | 15.12 m² | pass |
| Door clear opening | 815 mm | 900 leaf, about 850 clear | pass |
| Bed to east wall | 600 mm | 100 mm | **fails**: move the bed or accept one-sided access |
| Hole edge distance, t = 3 | 6 mm | 10.5 mm | pass |
```
