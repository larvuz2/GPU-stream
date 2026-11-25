<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Identity design: the craft

What a brand designer knows, as rules with their reasons, and where each meets VectorCraft. The
commands named here are in vectorcraft-commands.md.

## The brief

The interview is the first design act: most weak logos answer a question nobody asked. Ask one
question at a time, with options where the person may not have words for it, and write the
answers into the library (section Brief) as you go.

| Ask | Why it matters | Options to offer |
|---|---|---|
| What is this mark for? | A rebrand carries equity that must survive; a new mark is free | New company, Rebrand, Product or sub-brand, Event or campaign, Personal |
| The name, exactly: spelling, capitals, spaces, pronunciation | The letters are the raw material; a long name wants a symbol or a stacked lockup, a short one can be the mark | (open) |
| Where does the name come from, and what does it mean to you? | The best marks come from the name's own story, shape, or sound | (open) |
| What do you do, and for whom? | Audience decides register: a law firm and a skate shop can share a name, not a mark | (open) |
| Three words it should feel like; three it must never feel like | Gives you criteria to judge directions against, instead of taste | Offer pairs: calm or energetic, classic or contemporary, warm or precise, playful or serious, premium or accessible |
| Who else does this, and whose identity do you admire (in any field)? | You design into the gap: if every competitor is a blue circle, do not be one | (open; ask for names or links) |
| Where will it be seen first, and smallest? | A favicon, a stitched cap, and a truck side each rule things out | App icon, Website, Sign, Packaging, Clothing, Print, Social |
| Is anything fixed? A color, a typeface, a symbol people already know | Constraints save rounds | (open) |
| What do you need to walk away with? | Scope and cost | Logo only; Logo, colors, type; Full identity sheet; Icon set; Pattern |

Then read the brief back in five lines: who it is for, the one idea the mark should carry, the
feel in three words, the hardest use, and the deliverables. Have it confirmed before you draw.

**From answers to criteria.** Turn the brief into three or four tests you will hold every
direction to, in the person's own words: "works as a 16 px favicon", "feels warm, not corporate",
"could be stitched in one thread color", "does not look like the two competitors named". Quote
them when you recommend a direction.

**Look at the field.** You cannot browse competitors' logos from an engine. Ask the person to
describe or upload them, and name the conventions you hear (color, shape, type style) so the
direction can break one on purpose.

## What a mark is

- **Kinds.** A wordmark (the name, set and refined), a lettermark or monogram (initials), a
  pictorial mark (a thing), an abstract mark (a shape with no literal meaning), an emblem (type
  inside a shape), and a combination (symbol beside wordmark). A new, unknown name usually needs
  its name in the mark: a symbol alone has to be learned with money.
- **Three criteria, in this order** (the working test at Chermayeff & Geismar & Haviv):
  *appropriate* to the organization in feeling, not a picture of what it sells; *distinctive*
  enough to be told from its neighbors and remembered after one look; *simple* enough to work
  small, in one color, cut in vinyl, or stitched. A mark is an identifier, not an explanation: it
  cannot say everything, so it should say one thing.
- **One idea.** A mark that combines a letter, a leaf, a roof, and a swoosh has four ideas and no
  memory. If a direction needs a sentence with "and" to explain, cut it in two.
- **Meaning is acquired.** A simple shape gathers meaning from what the organization does. Do not
  load it with symbolism the brief did not ask for.

## Process

1. **Many, fast, in black.** Three to five directions as plain black shapes on separate
   artboards. No color, no gradient, no effects: they hide weak shapes and make the person choose
   by color.
2. **Choose one** with the person, against the criteria. Take pieces from another direction only
   if the idea stays one idea.
3. **Refine the geometry** (below). This is most of the work and most of the difference between
   an idea and a logo.
4. **Add the wordmark**, then the lockups.
5. **Add color**, on copies, with the black version kept.
6. **Stress it**: 16 px, one color, reversed on dark, on a photograph, beside its competitors,
   in a long horizontal space and a small square one.
7. **Build the system** and deliver.

## Geometry and optical balance

- **Build from primitives.** Circles, squares, and their Pathfinder combinations give curves
  that agree with each other. Draw freehand shapes with `path.create` only where no primitive
  fits, and then with anchors at the extremes and handles at 0 or 90 degrees.
- **A construction grid is a tool, not a proof.** Divide the mark's box into equal units (8, 12,
  or 16 across), and let edges, centers, and gaps land on units; use one circle size family for
  every curve. `guide.add` the key lines. The grid serves the eye: where the grid and the eye
  disagree, the eye wins.
- **Overshoot.** A circle or a point the same height as a square looks smaller. Let round and
  pointed forms pass the flat ones' edges by 1 to 3 percent (2 to 6 pt on a 240 pt mark).
- **Optical center.** The middle of a box is not the middle of a shape: a triangle sits low, a
  play symbol sits left. Center by area: move the shape toward its heavy side's opposite until
  it looks centered, and compare in a screenshot. The eye also reads the true center of a page
  as slightly low, so place a mark a little above the middle of its tile.
- **Weights.** Horizontal strokes look heavier than vertical ones of equal weight, and a stroke
  through a curve looks thinner at the joins. Thin horizontals by a few percent; open the acute
  joins with a small notch (an ink trap) if they fill in at small sizes.
- **Corners.** A rounded square whose inner shape follows it needs concentric radii: inner radius
  = outer radius minus the gap. Keep one radius family.
- **Negative space is a shape.** Look at the gaps as carefully as the forms. A gap narrower than
  a tenth of the stroke around it closes at small size.
- **Minimum size.** Find it, do not assume it: the smallest width at which every part still
  reads. Typical floors are 16 to 24 px on screen for a symbol and 0.5 in (12 mm) in print for a
  lockup with type; a detailed emblem needs more. Below the floor, deliver a simplified version
  (drop the tagline first, then the fine detail).
- **Clear space.** No other element inside a margin of one unit taken from the mark itself, so it
  scales with it: the x-height of the wordmark, the cap height of its first letter, or a quarter
  of the symbol's height are the usual units. Build the artboard to the art plus that margin, so
  every exported file carries its clear space.

## Typography and lettering

- **Classify before you choose.** Geometric sans (URW Gothic): modern, plain, open. Grotesque or
  neo-grotesque (Inter, Nimbus Sans, Liberation Sans): neutral, technical. Humanist sans (Source
  Sans 3, Noto Sans, Ubuntu): warm, legible. Old-style or transitional serif (P052, C059, Nimbus
  Roman, Source Serif 4): bookish, trusted. Slab or wide serif (URW Bookman): sturdy, friendly.
  Script or chancery (Z003): personal, formal. Mono (JetBrains Mono): technical, raw. Match the
  three words of the brief, and say which class you chose and why.
- **Look at the name's letters.** Set the name in four or five candidate faces on one artboard
  and compare the letters this name actually has: the double letters, the first capital, any
  awkward pair (rw, ty, LA, AV). The right face is the one whose letters of this word look best.
- **Case.** All lowercase reads friendly and modern; all capitals reads stable and formal and
  wants tracking of 50 to 200; mixed case reads like a name.
- **Spacing is the wordmark.** Large type needs tighter tracking than text (start at -10 to -40);
  small capitals need more (100 to 300). Then fix pairs by eye: after outlining, nudge single
  letters with `object.move`. The test: turn it upside down (`object.rotate {angle: 180, copy:
  true}`), and the gaps should still look even.
- **One custom move.** A wordmark becomes ownable through one change, not five: a cut terminal, a
  shared stroke between two letters, a dot replaced, a crossbar lifted. Outline the type, edit
  anchors with `path.moveAnchor` and `path.setHandle`, and keep stroke weights matching the
  untouched letters.
- **Never distort.** Do not scale type on one axis, do not add a stroke to fake a bolder weight
  (it rounds the corners and closes the counters). If the weight is missing, choose another face.
- **Wordmark and symbol** should share something: stroke weight, corner radius, or a curve.
  Match the symbol's line weight to the letters' stems.
- **The supporting typeface** for headlines and text is a recommendation in the system sheet:
  one family with enough weights, a second only for a reason. Check `text.fontList {family}` for
  the styles the engine really has before promising a weight.
- **Licensing.** The engine's fonts are open ones the person can use commercially. A font the
  person brings must be theirs to use in a logo; say so once. Outlined type in the delivered
  files needs no font on anyone's machine.

## Color

- **Start from roles.** Primary (the brand's own, used most), secondary (one or two that support
  or contrast), neutrals (a dark for text, a light for grounds), and at most one accent for
  calls to action. Five to seven colors is a system; twelve is a mood board.
- **Choose the primary against the field** (not the competitors' color) and for the feeling
  words. Then derive: a dark neutral that is the primary darkened and desaturated looks more
  related than black; a light neutral tinted toward the primary looks warmer than white.
- **Test in pairs.** Every text-on-ground pair needs contrast of 4.5 to 1, large type and
  graphic parts 3 to 1 (WCAG). Relative luminance is 0.2126 R + 0.7152 G + 0.0722 B on
  linearized channels, and the ratio is (lighter + 0.05) / (darker + 0.05): work it out, do not
  guess. A coral on white often fails for text; darken it for type and keep the bright one for
  shapes.
- **One-color and reversed versions are not afterthoughts.** A gradient mark needs a flat
  version; a two-color mark needs a version where shape alone separates the parts (knock one out
  of the other).
- **Gradients** are a look of a period. Use one when it carries the idea (light, heat, depth),
  between neighbors on the color wheel, never as the only thing separating two parts.
- **For press**: name each color and record hex, RGB, and CMYK, and a spot reference only if the
  printer gives one. Bright screen colors (pure RGB green, electric blue, neon orange) have no
  CMYK equal: warn before the person falls in love with one. Rich black for large areas is the
  printer's recipe, not yours.
- **In VectorCraft**: one global swatch per color, named by brand and role (`Morrow Navy`). Tints
  come from the swatch (`paint.setFill {swatch, tint: 40}`), so they follow it.

## The identity system

A logo is one file; an identity is a set of parts with rules. Build each as an artboard of one
document, named for what it is:

| Artboard | What it holds | Notes |
|---|---|---|
| `primary` | Symbol and wordmark, horizontal | The default. Clear space built into the artboard. |
| `stacked` | Symbol above wordmark | For square and narrow spaces. Re-space it; do not just move the parts. |
| `symbol` | The symbol alone | Earned use: avatars, app icons, places where the name is beside it anyway. |
| `wordmark` | The name alone | For running headers and very wide, short spaces. |
| `one-color` | Each of the above in black | Shape does the separating. |
| `reversed` | Each in white, for dark and photographic grounds | Thin parts may need a touch more weight: light on dark looks bolder in shapes, thinner in hairlines. |
| `icon` | The symbol on its tile, square, edge to edge | The source for favicons and app icons. |
| `palette` | Swatch squares with names and values as live text | The person reads the values off this sheet. |
| `type` | The typefaces with a sample line each | Name, weights, where each is used. |
| `usage` | Clear space, minimum size, and what not to do | Three or four misuse examples at most: stretched, recolored, on a busy ground, crowded. |

Keep everything in one `.vectorcraft` file so swatches and symbols are shared, and make the
symbol a VectorCraft symbol (`symbol.new`) when it appears on many artboards, so one edit
changes all.

## Icons

- **A set is a system.** One grid, one stroke weight, one corner radius, one cap and join, one
  level of detail. Draw the first three icons together, not one at a time, and fix the rules
  before the fourth.
- **Grid.** 24x24 is the common unit for interface icons, with the drawing inside a 20x20 live
  area and 2 units of padding; keyline shapes (a circle, a square, a tall and a wide rectangle)
  of equal visual weight keep a round icon from looking smaller than a square one. Work at 10
  times (240x240 pt) and export down.
- **Stroke.** 1.5 to 2 units at 24 is typical. Round caps and joins read friendly, butt and
  miter read precise. Keep gaps at least one stroke wide.
- **Pixels.** Icons are seen small: put straight edges on whole units and stroke centers on
  half units when the stroke is odd, so edges stay sharp at 1x.
- **Filled and outline styles** are two sets, not a mix.
- **Deliver** each icon on its own artboard, named in lowercase with hyphens (`arrow-left`),
  strokes outlined, united into one path, exported as SVG.

## Illustration

Flat vector illustration follows the same rules at a larger scale: a limited palette (five or
six colors from the brand's, with tints), shapes built from primitives and Pathfinder, one
light direction, one line weight if lines are used at all, and detail spent on the focal point
only. Build back to front on named layers (`layer.new`), group each object, and keep shadows as
separate shapes at `Multiply` (`object.setProps {blend: "Multiply", opacity}`), so the color
beneath shows through.

## Patterns

- **The motif comes from the mark**: a piece of the symbol, its curve, its grid. A pattern that
  could belong to any brand is decoration.
- **Tile.** A plain grid shows its rows and columns; a half-drop or brick repeat (`tileType:
  "brickByRow"`) hides them; a hex repeat suits round motifs. Vary rotation and scale within the
  tile only if the tile is large enough that the eye does not find the repeat.
- **Density and scale** are chosen for the use: a lining or a tissue wants a small, even,
  low-contrast texture; a hero wall wants a large, sparse one. Deliver two scales.
- **Seams.** What crosses the tile's right edge must enter at the left, at the same height (and
  top to bottom). Look at a 3x3 field at arm's length (`view.fitAll`): any line, stripe, or hole
  you notice is the seam.
- **In VectorCraft**: draw the motif, `object.pattern.make {ids, name, tileType, width, height,
  edit: false}`, fill a large rectangle with `paint.setFill {swatch: name}`, and judge it there.
  For textile hand-off, export the tile itself (an artboard exactly one tile in size) and a
  filled swatch for preview, and state the tile's size in millimeters and the repeat type.
- **Live repeats** (`object.repeat.radial`, `.grid`, `.mirror`) are for building a motif (a
  rosette, a border), and stay editable; `object.expand` them before export.
