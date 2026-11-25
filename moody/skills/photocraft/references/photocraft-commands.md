<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# PhotoCraft commands

The commands the image work uses, with parameters as PhotoCraft's command registry gives them.
Checked against PhotoCraft 0.23.1 on a Moody engine (`cpu` tier): the registry lists 1,009
commands, and every call, answer, and number below was run there through the same channel
`engine_call` uses, and read back. `?` marks an optional key, `=` its default, `…` an abridged
list.

## Calling PhotoCraft

`engine_call(engine_id, method, params)` sends one request on PhotoCraft's control channel.

| Method | Does |
|---|---|
| `engine.execute` `{command, params}` | Runs any command by its id, with exactly the parameters given. It never opens a dialog. |
| `app.open` `{path}` | Opens a file as a new document. Answers `{name, path, warnings}`. |
| `app.save` `{path?, quality?, jpegFormat?, tiffCompression?, tiffLayers?, …}` | Writes the active document; the extension picks the format. Answers `{path, warnings}`. Without `path` it saves a `.pcraft`, `.psd`, or `.psb` document back to its own file. |
| `ui.screenshot` `{path}` | Writes the window as a PNG (1920 by 1080) into the project folder. For looking yourself, `engine_screenshot` is simpler. |
| `ui.set` `{fit: true}` or `{zoom: 1, center: [x, y]}` | Fits the document to the window, or shows it at 100% around a document point. |
| `ui.menu.invoke` `{id}` | Runs a menu item, for the few things that are only menu toggles: `view.show.guides` answers `{result: false}` when it hid them. |

An answer that is not an object arrives wrapped: `layer.renameLayer` answers `{"result": null}`.
A refusal arrives as the tool's error with PhotoCraft's own sentence, which usually says what to
do: `no such layer 99999; the document's layers are 17 "Date", 16 "Credits", …`,
`opacity must be a number in 0..1 (1 = 100 %), got 50`, `command layer.list is not available
right now: no document open`.

**What PhotoCraft does not tell you.** A parameter key it does not know is ignored without an
error (`{"opacty": 0.3}` answered `null` and changed nothing), and so is a blend mode it does
not know. A font family that is not installed is accepted and drawn in another face. Read back
what you set.

**Files.** Paths are relative to the project folder (`exports/poster.png`), or absolute inside
it. Anything outside is refused (`parent traversal is not allowed`), and so is every `file.*`
command that names a path (`file.placeEmbedded`, `file.saveACopy`, `file.export.*`:
"uses ambient filesystem paths and is disabled"), `image.mode.*`, and `view.proofSetup`. Files go
through `app.open` and `app.save` only. **A folder must exist before you save into it**: a
missing one answers `No such file or directory`, so first
`engine_exec(engine_id, "mkdir -p <project folder>/exports")`.

**Finding a command.** `engine.commands` returns all 1,009 and arrives cut; `ui.inspect` is cut
too. Search from the shell instead, which prints each match's id, label, and parameter doc:

```text
engine_exec(engine_id, "photocraft-cli commands --json --filter 'unsharp'")
  -> [{"id": "filter.sharpen.unsharpMask", "label": "Unsharp Mask…", "menu": ["Filter", "Sharpen"],
       "params": "{\"amount\":1..500=50,\"radius\":0.1..1000=1,\"threshold\":0..255=0}", …}]
```

Ids follow the menus a photo editor has: `filter.blur.gaussianBlur`,
`layer.newAdjustmentLayer.curves`, `select.modify.feather`, `image.canvasSize`.

**Reading the state**, small enough to arrive whole:

| Command | Answers |
|---|---|
| `session.inspect {}` | `{active, documents: [{index, name, path, width, height, dirty, revision}], foreground, background}` |
| `layer.list {"flat": true}` | `{activeLayer, layers: [{id, name, kind, depth, parent, bounds: [x, y, w, h], visible, selected, active}]}`, top first |
| `document.inspect {}` | size, `depth`, `history` (step names), `hasSelection`, saved channels, and each layer with `blend`, `opacity`, `fill`, `clipped`, `hasMask`, and an adjustment's `params`. Grows with the layer count: prefer `layer.list`. |
| `type.info {layer}` | text, `runs[].style` (font, size, tracking, color), `lines`, `bounds` |
| `document.sampleColor {x, y, size: 5}` | `[r, g, b, a]`, each 0 to 1, of the picture at a point |

## Units and addressing

- **Pixels** for positions and sizes, origin at the top left, in document space. Lengths that
  take text accept units: guides take `"0.75 in"`, `"50%"`, `"1 cm"`.
- **Points** for type sizes and leading. At 300 pixels an inch a point is 4.167 pixels (`type.info`
  answers `pxPerPt`), so 132 pt type has an em 550 pixels tall. In a 72 pixels-an-inch document a
  point is a pixel.
- **Bounds come in two shapes.** `layer.list` and `shape.create` answer `[x, y, width, height]`;
  `type.create`, `type.info`, and `edit.transform`'s `rect` answer `[x0, y0, x1, y1]`.
- **Opacity has three scales.** `layer.setProps`, `layer.new.layer`, an adjustment layer's
  `opacity`, and brush strokes take 0 to 1. Layer styles, `edit.fill`, `layer.new.group`, and
  the retouching tools take 0 to 100. A value on the wrong scale is refused for `layer.setProps`
  and may simply be wrong elsewhere.
- **Colors** are `"#rrggbb"`. **Scale** is percent, **rotation** degrees, **tracking** thousandths
  of an em, **JPEG quality** 0 to 12.
- **Layers** are addressed by `layer`: the numeric id from the command that made it, or its
  name (`"Grain"`; a duplicated name needs the id). Ids are per session, and a layer gets a new
  id when it becomes a smart object. Without `layer`, a command acts on the selected layers;
  name the layer and leave the person's selection alone.
- **Documents** by zero-based `index` from `session.inspect`. A newly opened or duplicated
  document becomes the active one, and commands go to the active one.
- **Blend modes** by their panel name: `"Multiply"`, `"Screen"`, `"Overlay"`, `"Soft Light"`
  (also accepted as `softLight`).

## The recipe: a poster from a picture

Run as written on the `cpu` tier in 67 s, 34 calls: a 24 by 36 in poster with a film frame as
key art. `$name.layer` below stands for the id an earlier answer returned.

```text
engine_exec(e, "mkdir -p <project folder>/exports")

file.new {"width": 7200, "height": 10800, "resolution": 300, "name": "Dusk poster", "background": "#0b0d1a"}
  -> {"document": 0}

app.open {"path": "handoff/filmcraft-to-photocraft/poster-frame-shot01.png"}     (it is document 1, and active)
layer.copyToDocument {"document": 0, "center": true, "name": "Key art"}
  -> {"document": 0, "layers": [6], "offset": [2640, 4860]}
file.close {"document": 1}                                                       (the poster is active again)

layer.smartObjects.convertToSmartObject {"layer": 6}          -> {"layer": 9}    (a new id)
edit.transform {"layer": 9, "scaleX": 680, "scaleY": 680, "dx": -400, "dy": -1728, "interpolation": "bicubicSmoother"}
layer.layerMask.revealAll {"layer": 9}
paint.gradient {"from": [3600, 4700], "to": [3600, 7300], "colors": ["#ffffff", "#000000"], "target": "mask"}

layer.newAdjustmentLayer.curves {"points": [[0,0],[64,50],[128,128],[192,206],[255,255]], "name": "Contrast", "clipToPrevious": true}
layer.newAdjustmentLayer.colorLookup {"lut": "tealOrange", "name": "Grade", "opacity": 0.4}
layer.new.layer {"name": "Grain", "mode": "Overlay", "fillNeutral": true, "opacity": 0.5}
filter.noise.addNoise {"amount": 6, "distribution": "gaussian", "monochromatic": true}

type.create {"x": 3600, "y": 8350, "text": "THE LONG DUSK", "name": "Title", "align": "center",
             "font": "URW Gothic", "fontStyle": "Demi", "size": 132, "tracking": 120, "color": "#f6efe4"}
  -> {"layer": 13, "bounds": [1109, 7936, 6017, 8359]}
type.create {"x": 3600, "y": 8700, "text": "Some lights refuse to go out.", "name": "Tagline", "align": "center",
             "font": "P052", "fontStyle": "Italic", "size": 38, "color": "#e8c9a0"}
shape.create {"kind": "rect", "rect": [3300, 8870, 600, 6], "fill": "#f4a259", "stroke": null, "name": "Rule"}
type.create {"box": [900, 9480, 5400, 460], "text": "A MOODY STUDIO PRODUCTION   …\nMUSIC BY …", "name": "Credits",
             "align": "center", "font": "Nimbus Sans Narrow", "size": 22, "tracking": 60, "leading": 34, "color": "#9aa0b5"}
type.create {"x": 3600, "y": 10250, "text": "IN THEATERS 12.18", "name": "Date", "align": "center",
             "font": "URW Gothic", "fontStyle": "Demi", "size": 34, "tracking": 240, "color": "#f4a259"}
layer.layerStyle.dropShadow {"layer": 13, "color": "#000000", "opacity": 45, "angle": 90, "distance": 12, "size": 40}

layer.select {"layer": 13}, then {"layer": 14, "mode": "add"} for each of the others
layer.new.groupFromLayers {"name": "Type", "color": "orange"}                  -> {"layer": 18}
view.newGuideLayout {"columns": 6, "gutter": "0.25 in", "margin": "0.75 in", "clearExisting": true}

app.save {"path": "exports/dusk-poster.psd"}     11 s, 368 MB with the grain layer
app.save {"path": "exports/dusk-poster.png"}      8 s,  39 MB  -> warnings: ["11 layer(s) flattened; …"]
app.save {"path": "exports/dusk-poster.jpg", "quality": 10}    6 s, 1.9 MB
app.save {"path": "dusk-poster.pcraft"}          11 s, 127 MB: the master, saved last so it stays the open document
```

Checked outside PhotoCraft: the PNG and the JPEG are 7200 by 10800 and carry 300 pixels an
inch and a color profile; the PSD holds twelve layer records with the type still type, the key
art still a smart object with its mask, both adjustment layers, the clipping, and the group.

What the steps teach:

- **A picture comes in as a document, then as a layer.** `center: true` centers it; `at: [x, y]`
  puts its center on a point. Close the source document: left open, it stays the active one
  and takes your next command.
- **`edit.transform` is relative**: scale percent about the layer's center, then move by
  `dx`, `dy`. Read `layer.list` for where the layer landed, and compute the next move from its
  bounds. `interpolation`: `bicubicSmoother` to enlarge, `bicubicSharper` to reduce.
- **A full-canvas noise layer makes every save heavy** (noise does not compress): the PSD went
  from 37 MB to 368 MB with it. Add grain last, and leave it out of a file you send by mail.
- **Point type is anchored at its baseline** (`x`, `y`, with `align`); paragraph type takes a
  `box` and wraps inside it.

## Layers

| Command | Parameters | Notes |
|---|---|---|
| `layer.new.layer` | `{name?, mode="Normal", opacity: 0..1 = 1, fillNeutral=false, clipToPrevious=false, position: "above"\|"below"}` -> `{layer}` | `fillNeutral` fills with the mode's neutral color (50% gray for Overlay and Soft Light) |
| `layer.new.layerFromBackground` | `{}` -> `{layer}` | A flat photograph opens as a locked "Background"; do this before masking or moving it |
| `layer.new.group` / `layer.new.groupFromLayers` | `{name?, color?, mode="passThrough", opacity: 0..100}` -> `{layer}` | The second groups the selected layers |
| `layer.duplicate` | `{layer?, name?}` -> `{layer}` | |
| `layer.renameLayer` | `{layer?, name}` | |
| `layer.setProps` | `{layer?, visible?, opacity: 0..1?, fill: 0..1?, blend?, clipped?, locked?}` | One step for several with `layers: [id, …]` |
| `layer.select` | `{layer: id\|name, mode: "replace"\|"add"\|"remove"}` -> `{selected: [ids]}` | |
| `layer.moveTo` | `{layer, target: id\|name, position: "above"\|"below"\|"into"}` | `into` puts it in a group |
| `layer.translate` | `{layer?, dx, dy}` | Whole pixels |
| `layer.align.horizontalCenters` (and `.verticalCenters`, `.leftEdges`, …) | `{to: "canvas"}` -> `{moved}` | Acts on the selected layers: `layer.select` first |
| `layer.createClippingMask` / `layer.releaseClippingMask` | `{layer?}` -> `{layers}` | Clips the layer to the one below it |
| `layer.delete` / `layer.lockLayers` / `layer.hideLayers` | `{layer?}` | `hideLayers` shows them again if all were hidden |
| `layer.setLabelColor` | `{layer?, color: "red"\|"orange"\|…\|"none"}` | |
| `layer.stampVisible` | `{}` -> `{layer}` | Everything visible, merged into a new layer on top: the base for sharpening |
| `layer.smartObjects.convertToSmartObject` | `{layer?}` -> `{layer}` | New id. Selected layers combine into one |
| `layer.copyToDocument` | `{document, layers?, center?, at?, name?}` -> `{document, layers, offset}` | A layer's mask travels with it |
| `layerComp.new` / `layerComp.apply` / `layerComp.list` | `{name}` / `{comp: name\|id}` / `{}` | A comp remembers visibility, position, and appearance |

## Masks and selections

A selection is spent when it becomes a mask: making a layer mask or an adjustment layer from it
leaves no selection (`select.deselect` then answers "no selection"). Save one you will need again
with `select.saveSelection {name}`, and load it with `select.loadSelection {channel: name}`.

| Command | Parameters | Notes |
|---|---|---|
| `select.subject` | `{sampleAllLayers=false}` -> `{bounds, selected}` | The main subject of the selected layer. About 1 s at 2048 pixels |
| `layer.removeBackground` | `{layer?}` -> `{layer, bounds}` | Select Subject and a mask in one step |
| `select.sky` | `{}` -> `{coverage, bounds}` | |
| `select.colorRange` | `{select: "skinTones"\|"highlights"\|"shadows"\|"reds"\|…, fuzziness}` or `{color: "#rrggbb", fuzziness}` | |
| `select.rect` | `{x, y, width, height, ellipse=false, feather=0, mode: "replace"\|"add"\|"subtract"}` | |
| `select.inverse` / `select.deselect` / `select.all` | `{}` | |
| `select.modify.feather` / `.expand` / `.contract` | `{radius}` | Pixels |
| `select.refineEdge` | `{radius, smartRadius, feather, contrast, shiftEdge, output: "selection"\|"layerMask"}` | For hair and soft edges |
| `select.loadSelection` | `{channel: "mask", layer, invert?}` | A layer's mask back as a selection |
| `layer.layerMask.revealAll` / `.hideAll` / `.revealSelection` | `{layer?}` | White mask, black mask, or the selection as the mask |
| `layer.layerMask.edit` | `{layer?, feather: px?, density: 0..100?}` | Softens or weakens a mask without repainting it |
| `layer.layerMask.enabled` | `{}` -> `{enabled}` | Toggles: call it twice to compare with and without |
| `paint.gradient` | `{from, to, colors: ["#ffffff", "#000000"], style="linear", target: "mask"}` | A fade: the picture shows where the mask is white |
| `paint.stroke` | `{points: [[x, y], …], size, hardness: 0..1, opacity: 0..1, color, target: "mask"}` | White to reveal, black to hide |
| `layer.matting.defringe` | `{layer?, width}` | Removes the light or dark rim a cut-out keeps |

An adjustment layer made while a selection is active takes the selection as its mask, so it
changes only the selected area. To change the background and leave the subject: `select.subject`,
`select.inverse`, `select.modify.feather {radius: 3}`, then the adjustment.

## Adjustment layers

`layer.newAdjustmentLayer.<kind>` takes the adjustment's own parameters plus
`{name?, opacity: 0..1 = 1, mode?, clipToPrevious=false}` and answers `{layer}`.
`layer.setAdjustment {layer, …}` changes its parameters later.

| Kind | Parameters |
|---|---|
| `curves` | `{points: [[in, out], …]}` in 0 to 255, 2 to 19 points; per channel under `red`, `green`, `blue` |
| `levels` | `{inBlack: 0..253, gamma: 0.01..9.99, inWhite: 2..255, outBlack, outWhite}` |
| `hueSaturation` | `{hue: -180..180, saturation: -100..100, lightness: -100..100}`; per range under `reds`, `yellows`, … |
| `vibrance` | `{vibrance: -100..100, saturation: -100..100}` |
| `colorBalance` | `{shadows, midtones, highlights}`, each `[cyan-red, magenta-green, yellow-blue]` in -100 to 100 |
| `selectiveColor` | `{colors: "reds"\|"yellows"\|…\|"neutrals"\|"blacks", cyan, magenta, yellow, black}` in -100 to 100 |
| `blackWhite` | `{reds, yellows, greens, cyans, blues, magentas}`; at low `opacity` it mutes rather than removes color |
| `photoFilter` | `{filter: "warming85"\|"cooling80"\|…}` or `{color: "#rrggbb"}`, `density: 0..100` |
| `gradientMap` | `{stops: [[0, "#101830"], [1, "#ffe9c8"]]}`: shadows to one color, highlights to another |
| `colorLookup` | `{lut: "tealOrange"\|"warm"\|"cool"\|"bleachBypass"\|"fadedFilm"\|"dayForNight"\|"monoContrast"\|"crossProcess"}`; a LUT file is refused on the channel |

A soft S on `curves` is contrast: `[[0,0],[64,50],[128,128],[192,206],[255,255]]`. Lifting the
first point's output (`[0, 12]`) fades the blacks; the same on `blue` alone cools the shadows.

## Type

| Command | Parameters |
|---|---|
| `type.fonts` | `{}` -> `{families}`; `{family}` -> `{faces: [{style, weight, italic, postscriptName}]}` |
| `type.create` | `{x, y, text, align}` for point type or `{box: [x, y, w, h], text}` for a paragraph, with `name?` and style keys -> `{layer, bounds}` |
| `type.setStyle` | `{layer, range: [start, end]?, font, fontStyle, size: pt, color, tracking, leading: pt\|"auto", caps: "normal"\|"small"\|"all", align, …}` |
| `type.edit` | `{layer, text}` replaces the words and keeps the style; `{box}` or `{point}` changes its kind |
| `type.info` | `{layer}` -> text, runs, lines, bounds |
| `type.warpText` | `{layer, style: "arc"\|"arch"\|"flag"\|…, bend: -100..100}` |
| `type.convertToShape` | `{layer}` -> `{layer, subpaths}`: outlines, no longer editable as words |

**Choose the face from what is installed.** `type.fonts {family}` first, and pass the face's
`style` as `fontStyle`. A family or style that does not exist is accepted and drawn in a
fallback: afterwards `type.info` shows `postscript_name: null` in the run's style. Asking Inter
for weight 800 did exactly that; Inter here has Regular, Medium, and SemiBold.

Families worth knowing, of about 250 (most of the rest are Noto for other scripts):

| For | Family (faces) |
|---|---|
| Geometric display, titles | URW Gothic (Book, Demi, obliques) |
| Clean interface sans | Inter (Regular, Medium, SemiBold), Ubuntu, Ubuntu Sans |
| Neutral sans | Nimbus Sans, Liberation Sans, DejaVu Sans |
| Condensed, for credits and long lines | Nimbus Sans Narrow (Regular, Bold, obliques) |
| Book serifs | P052 (Roman, Italic, Bold), C059, URW Bookman, Nimbus Roman, Liberation Serif |
| Script | Z003 |
| Monospace | JetBrains Mono, Hack, DejaVu Sans Mono |
| Japanese, Korean, Chinese | Shippori Mincho, BIZ UDPGothic, BIZ UDMincho, NanumGothic, Noto Sans CJK |

**Installing the person's font.** Put the font file in the project folder (`fonts/`), then:

```text
engine_exec(e, "mkdir -p ~/.local/share/fonts && cp <project folder>/fonts/*.ttf ~/.local/share/fonts/ && fc-cache -f")
engine_call(e, "app.save", {})        (PhotoCraft reads fonts only as it starts; save first)
engine_call(e, "app.quit", {})        (it starts again by itself in about 15 s, on the last saved document)
engine_call(e, "engine.execute", {"command": "type.fonts", "params": {"family": "Bebas Neue"}})
  -> {"faces": [{"family": "Bebas Neue", "style": "Regular", "postscriptName": "BebasNeue-Regular", …}]}
```

The font lives on that engine's machine: a new engine needs the same two commands again, which
is why the file stays in the project folder. Only install a font the person has the right to
use.

## Shapes, fills, and styles

| Command | Parameters |
|---|---|
| `shape.create` | `{kind: "rect"\|"roundedRect"\|"ellipse"\|"line"\|…, rect: [x, y, w, h], fill: "#rrggbb"\|null, stroke: {width, color}\|null, name?}`; a line takes `{from, to, weight}` |
| `layer.newFillLayer.solidColor` | `{color}` -> `{layer}` |
| `gradient.fill.create` | `{from, to, style: "linear"\|"radial", stops: [[t, color], …], transparency: [[t, 0..100], …], mode?}` -> `{layer}` |
| `edit.fill` | `{contents: "color", color, opacity: 0..100}` fills the active layer or selection |
| `layer.layerStyle.dropShadow` | `{layer, color, opacity: 0..100, angle, distance: px, size: px}` |
| `layer.layerStyle.innerShadow` / `.outerGlow` / `.stroke` / `.colorOverlay` | `{layer, color, opacity: 0..100, size?, blend?, position?}` |
| `layer.layerStyle.clear` | `{layer}` |
| `view.newGuideLayout` | `{columns, gutter, rows?, margin, clearExisting}`, lengths as `"0.25 in"` -> `{vertical, horizontal}` |
| `view.newGuide` / `view.clearGuides` | `{orientation: "vertical"\|"horizontal", position: "50%"}` / `{}` |

A vignette is a radial gradient fill from transparent to black, in Multiply:
`gradient.fill.create {"from": [cx, cy], "to": [cx, bottom + 250], "style": "radial", "stops":
[[0, "#000000"], [1, "#000000"]], "transparency": [[0, 0], [1, 80]], "mode": "multiply"}`.

## Retouching and filters

Brush tools take `points` as `[[x, y], …]` in document pixels and `size` in pixels, and answer
`{damage: [x, y, w, h]}`, the area they changed. They act on the active layer: select the
retouch layer first.

| Command | Parameters | Use |
|---|---|---|
| `image.detectFaces` | `{}` -> `{faces: [{rect: [x, y, w, h], score, landmarks: {leftEye, rightEye, nose, mouthLeft, mouthRight}}]}` | Where the face is, so strokes land on it |
| `paint.spotHealing` | `{points, size}` | A blemish, a dust spot: dab on it |
| `paint.healingBrush` / `paint.cloneStamp` | `{points, source: [x, y], size, hardness: 0..100}` | Heal blends texture into the tone under it; clone copies exactly |
| `edit.contentAwareFill` | `{output: "new"}` on a selection -> `{layer, filled}` | Removes an object onto a new layer |
| `paint.dodge` / `paint.burn` | `{points, size, range: "shadows"\|"midtones"\|"highlights", exposure: 1..100}` | Permanent: only on a copy |
| `filter.liquify` | `{strokes: [{tool: "forwardWarp", size, pressure, points}]}` -> `{maxDisplacement}` | Shape, in small pushes |
| `filter.blur.gaussianBlur` | `{radius: 0.1..1000}` | |
| `filter.other.highPass` | `{radius}` | Sharpening or texture layer (retouching.md) |
| `filter.sharpen.unsharpMask` / `.smartSharpen` | `{amount, radius, threshold}` / `{amount, radius, reduceNoise}` | Last step, on a stamp |
| `filter.noise.addNoise` / `.reduceNoise` | `{amount, distribution: "gaussian", monochromatic}` / `{strength: 0..10, preserveDetails}` | |
| `filter.cameraRaw` | `{exposure, contrast, highlights, shadows, whites, blacks, clarity, texture, dehaze, vibrance, temperature, tint, …}`, each -100 to 100 (exposure -5 to 5) | The developing controls. On a smart object it is a smart filter |
| `layer.smartFilter.setParams` | `{layer, index, params}` | Changes a smart filter later |

## Size, crop, and color

| Command | Parameters |
|---|---|
| `image.duplicate` | `{name, mergedOnly: true}` -> `{document}`: a flat copy to cut exports from, leaving the master alone. 5 s for a 7200 by 10800 poster |
| `image.crop` | `{x, y, width, height, targetWidth, targetHeight, resolution}`: crops, then resamples to exactly the target |
| `file.automate.fitImage` | `{width, height, resample}`: scales to fit inside, keeping proportions |
| `image.imageSize` | `{width, height}` or `{percent}`, `resample: "preserveDetails"\|"bicubicSmoother"\|"bicubicSharper"\|…` |
| `image.canvasSize` | `{width, height, anchor: "center", extensionColor: "#rrggbb"\|"transparent"}`: room around the picture, for bleed |
| `edit.convertToProfile` | `{profile: "srgb"\|"display-p3"\|"adobe-rgb-compat"\|"coated-cmyk"}` -> `{mode, profile}` |
| `file.new` | `{width, height, resolution, name, background: "white"\|"black"\|"transparent"\|"#rrggbb", mode: "rgb"\|"cmyk"\|"gray", depth: 8\|16\|32}` |

## Undo, snapshots, long jobs

- `edit.undo {}` and `edit.redo {}` step once. `history.selectState {"state": 0}` returns to the
  document as it was opened, with every later state still there to redo.
- `history.newSnapshot {name}` -> `{snapshot}` keeps the document as it is now, for the
  session; `history.selectSnapshot {snapshot}` returns to it. Returning also undoes layer comps
  made after it.
- `file.close {}` closes the active document **and discards unsaved changes without asking**.
  `file.close {"save": "ask"}` refuses instead ("the document has unsaved changes"). Use the
  second unless you mean the first.
- PhotoCraft answers within 60 s or reports a timeout without stopping the work. For a step
  that may run longer, add `"wait": false` beside `command` and `params`:
  `{"command": "filter.noise.addNoise", "params": {…}, "wait": false}` answers
  `{"job": 50, "pending": true}`; `jobs.list {}` then shows `{id, state: "running"|"done"|"failed",
  progress: 0..1}`. Until it is done the document refuses other commands ("still running on
  this document").

## Formats

Read (each opened here): PNG (8 and 16 bit), JPEG, TIFF, WebP, GIF, BMP, TGA, EXR (opens at 32
bit), PSD, and PhotoCraft's `.pcraft`. AVIF answered "decoding is not available for this
format". Camera raw files and PDF as input were not tested.

Written by `app.save`, by extension:

| Extension | Keeps | Notes |
|---|---|---|
| `.pcraft` | everything | The master. Moves the document to this file |
| `.psd`, `.psb` | layers, masks, type as type, smart objects, adjustment layers, styles | For Photoshop and others. Moves the document |
| `.ora` | layers | For Krita and GIMP. Moves the document |
| `.png` | flat, transparency, profile, pixels an inch | Lossless |
| `.jpg` | flat, profile, pixels an inch | `quality` 0 to 12, `jpegFormat: "progressive"`. At 2048 by 2048: 12 gave 1.7 MB, 8 gave 250 KB, 5 gave 185 KB |
| `.tif` | flat (`tiffLayers: true` keeps layers), profile | `tiffCompression: "lzw"\|"zip"` |
| `.webp` | flat, transparency | Lossless only: a 1080 by 1920 picture was 531 KB against JPEG's 87 KB |
| `.pdf` | flat, one page at the document's size | No marks, no live text |
| `.exr`, `.jxl`, `.gif`, `.bmp`, `.tga`, `.dds`, `.hdr` | flat | GIF is cut to 256 colors |

Refused: `.avif`, `.heic`, `.svg`, `.jp2`, `.xcf`, `.kra`, and `.ico` above 256 pixels. Every
save answers `warnings` saying what the format dropped; pass them on when they matter.

**In the shell**, the same engine without a window, for conversions and batches that need no
looking (it may read and write anywhere in the project folder, and it can change the color
mode, which the channel cannot):

```text
engine_exec(e, "cd <project folder> && photocraft-cli info exports/poster.psd")          the layer tree as JSON
engine_exec(e, "cd <project folder> && photocraft-cli convert in.tif out.webp")
engine_exec(e, "cd <project folder> && photocraft-cli run exports/poster.png --cmd file.automate.fitImage --params '{\"width\":1080,\"height\":1620}' --out social/poster-1080.jpg")
engine_exec(e, "cd <project folder> && photocraft-cli run photo.jpg --cmd image.mode.cmyk --out photo-cmyk.tif")
```

## Checking an export

After every export, before you tell the person it is done:

```text
engine_files(e, "exports")                     the file is there and its size is not zero
engine_exec(e, "ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt -of csv=p=0 <project folder>/exports/poster.jpg")
  -> mjpeg,7200,10800,yuvj420p
engine_exec(e, "cd <project folder> && photocraft-cli info exports/poster.psd | head -c 2000")      a PSD's layers
```
