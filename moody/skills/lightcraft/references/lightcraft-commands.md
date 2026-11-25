<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# LightCraft commands

Every command here was run against LightCraft 0.21.1 on a Moody engine and answered as written.
Anything not listed is unverified: look it up with `engine.commands` before you use it, and check
its result.

## Calling

```text
engine_call(engine_id, "engine.execute", {"command": "<id>", "params": {...}})   an engine command
engine_call(engine_id, "ui.inspect")                                              a window method
```

- An answer that is an object comes back as it is. A list or an empty answer comes back wrapped:
  `{"result": [...]}`, `{"result": null}`. `{"result": null}` is success.
- A refusal is an error whose text says what was wrong and usually lists the allowed values
  (`` `colorSpace` must be one of srgb|displayP3|adobeRgb|proPhoto|rec2020 ``). Read it and fix the
  call. Sending a wrong value on purpose is a fair way to learn an option's values.
- `engine.commands` lists all 604 commands as `{id, label, params, enabled, disabled_reason}`; the
  `params` text is the command's own documentation. It is long: ask once, when you need a command
  this file lacks.
- Paths are absolute: the project folder from the turn's state, then the path inside it.
- Photo ids are integers the library gave at import. They belong to this library; read them again
  with `catalog.query` at the start of a turn rather than trusting memory.
- LightCraft gives up on a request after 60 s. Only a large export can take that long: start it with
  `background: true` and poll (see [Export](#export)).
- A request sent in the first seconds after `engine_start` waits for the window's first frame; the
  channel retries by itself for up to a minute.
- Coordinates are fractions of the picture, `x` from the left and `y` from the top, 0 to 1, in the
  upright picture.
- A slider change is one undo step: `edit.undo {}` -> `{"undone": "<label>"}`, `edit.redo {}`.

### Traps that cost a turn

| Trap | What to do |
|---|---|
| `develop.set` works on the **active** photo. | `library.select {ids: [id]}` first, or pass `ids: [..]` in the call. |
| `mask.adjust` silently ignores a key it does not know and clamps without saying. | Use only the keys listed under [Masks](#masks); read the mask back with `develop.get`. |
| `develop.set` clamps to the control's range without saying (`light.exposure: 99` stores 5). | Stay inside the ranges below. An unknown control id is refused. |
| `develop.auto` answers `{"pending": true}` and applies a moment later. | Read `develop.get` after it; treat its values as a first guess (it set Contrast +68 on a test raw). |
| `photo.virtualCopy` makes the copy the active photo. | Edits after it land on the copy. Select the original again if that is what you meant. |
| `crop.aspect` then `crop.set {rect}` does not hold the ratio: the rect wins. | Compute the rect for the ratio yourself (see [Crop](#crop-and-geometry)). |
| `photo.inspect` returns every saved version's full settings, tens of kilobytes. | Use `develop.get {id}` for settings; `photo.inspect` once for metadata. |
| `app.export` without a size exports full size; without a color space, the last one used. | Pass `format`, a size, `colorSpace`, and `conflict` every time. |
| `photo.editExternal` writes beside the original whatever `dir` says. | Use `app.export` with `path` for a hand-off folder. |
| An imported LUT's id comes from the title inside the file, not its file name. | Take the id from `profile.import`'s answer. |
| White balance numbers mean different things on raw and on JPEG. | See [White balance](#white-balance). |

## The window

| Method | Params | Answer |
|---|---|---|
| `ui.inspect` | none | Large. Useful keys: `active`, `selection`, `loupe {photo, pending, source, failed}`, `export {running: {current, done, total} or null, last: {files, cancelled}}`, `activity`, `import`, `notices`, `libraryProblem` (null when the library opened) |
| `ui.set` | `{"view": "detail"}` | The interface's state. Detail is the single-photo view with the Edit panel |
| `ui.render` | `{id?, size?, path?}` | `{width, height, path}`: the photo with its current settings as a PNG, long edge `size` (default 1024), crop and masks included. This is your way to look at an edit and to measure it |
| `ui.widgets` | `{filter?}` | `[{id, rect}]` on screen now |
| `ui.clickWidget` | `{id}` | Clicks it; fails if it is not on screen |
| `ui.dialog.confirm` / `ui.dialog.cancel` | none | Answers the open dialog |

View commands (through `engine.execute`, all `{}`): `view.detail`, `view.compare` ->
`{select, candidate}` (two photos side by side), `view.survey` -> `{photos}` (the selection
together), `view.beforeAfter` (toggle), `view.clipping` (toggle the clipping warning),
`view.maskOverlay` -> `{maskOverlay}`. They change what the person sees, nothing in the photo.

**A project's first session** shows a welcome tour, then offers the lens database:

```text
engine_call(id, "ui.clickWidget", {"id": "button:welcomeSkip"})   skip the tour (an error once it is gone: ignore)
engine_call(id, "ui.dialog.confirm")                              -> {"downloading": true}: the lens profiles, about 5 MB
engine_call(id, "engine.execute", {"command": "lens.databaseStatus"})
   -> {"download": {"state": "done", "files": 56}, "lenses": 1568, "dir": ".../.lightcraft/lensfun"}
```

Where no dialog is open, `lens.downloadDatabase {}` -> `{"started": true, "dir"}` starts the same
download. It took about 8 s.
The database stays in the project folder; later sessions have it.

## Library: import, find, organize

| Command | Params | Answer and notes |
|---|---|---|
| `library.info` | `{}` | `{path, photos, albums, unsavedOps, unsavedError, ...}`. `unsavedOps` above 0 means the catalog could not be written: stop and say so |
| `library.importPreview` | `{paths: [file or folder]}` | `{candidates: [{path, name, format, kind: "raw"/"image", width, height, captured, duplicate, error, previewOnly}], duplicates, scanned}`. Adds nothing. `previewOnly` says why a raw can only be shown from its camera preview |
| `library.import` | `{paths: [..], mode: "add", albumName?, album?, keywords?, preset?}` | `{imported: [ids], duplicates: [{path, existing, reason}], failed, album}`. `mode: "add"` references the files where they are, which is what a project wants. Folders are read recursively. Importing a path twice reports it under `duplicates` and changes nothing |
| `catalog.query` | `{filter?, sort?, offset?, limit?}` | `{photos: [{id, fileName, format, kind, width, height, camera, captured, rating, flag, label, edited, keywords, copyOf, copyName, previewOnly}]}`. Without `filter`: the current view. `filter` keys used: `text`, `flag`, `kind`, `edited`, `rating` with `ratingOp` |
| `catalog.stats` | `{}` | `{photos, picks, rejects, edited, albums, keywords, byDate}` |
| `library.state` | `{}` | `{selection: {ids, active}, filter, sort, source, sourceLabel, visibleCount, undo, redo}` |
| `library.select` | `{ids: [..], active?}` | `{selected: n}`. Several ids with `active` is how `develop.sync` and `develop.matchExposure` get their source and targets |
| `library.selectBy` | `{flag?, rating?, label?}` | `{selected}` among the photos in view |
| `library.filter` | `{rating?, ratingOp?: "atLeast"/"exactly"/"atMost", flag?, label?, text?, kind?, edited?}` | `{count}`. Narrows the view the person sees; `library.clearFilter {}` undoes it |
| `library.source` | `{kind: "all"/"picks"/"recentlyAdded"/"album", id?}` | `{count}` |
| `library.sort` | `{key: "captureDate"/"importDate"/"editDate"/"fileName"/"rating"/"fileSize", ascending?}` | |
| `photo.rate` | `{rating: 0..5, ids?}` | `{changed}` |
| `photo.flag` | `{flag: "pick"/"reject"/"none", ids?}` | `{changed}` |
| `photo.label` | `{label: "red"/"yellow"/"green"/"blue"/"purple"/"none", ids?}` | `{changed}` |
| `photo.analyze` | `{ids?, burstGap?: seconds, similarity?, pickBest?, rejectBelow?}` | `{photos: [{id, sharpness: 0..100, clipped: fraction, group, best}], groups}`. Scores focus and clipping, groups look-alike frames, marks the sharpest of each group. With `pickBest` or `rejectBelow` it also flags, so leave those off until the person agreed |
| `stack.auto` | `{gap?: seconds, preview?: true}` | `{stacks, photos}`. With `preview` it only counts |
| `album.create` | `{name, addSelected?: false}` | `{id}` |
| `album.addPhotos` | `{id, ids: [..]}` | `{added, skipped}` |
| `album.createSmart` | `{name, rules: {rating: 4, ratingOp: "atLeast"}}` | `{id, count}` |
| `photo.setMeta` | `{ids?, title?, caption?, copyright?, creator?, keywords?, addKeywords?, removeKeywords?}` | `{changed}` |
| `metadata.savePreset` / `metadata.applyPreset` | `{name, fields: {copyright, copyrightStatus, creator}}` / `{name, ids}` | The credit line for a whole shoot in one call |
| `photo.virtualCopy` | `{ids, name?}` | `{ids: [new]}`. A second set of settings on the same file, stacked with the original. The copy becomes active |
| `photo.delete` / `photo.restore` | `{ids}` | To and from Recently Deleted. No file is touched. Ask before deleting |

## Develop

`develop.get {id?}` returns the full settings. Its keys are snake_case sections (`light`, `wb`,
`curve`, `color`, `mixer`, `grading`, `effects`, `detail`, `optics`, `geometry`, `crop`, `masks`,
`profile`, `treatment`, `vignette`, `grain`, `bw_mix`). The ids you **set** are the dotted control
ids below. `develop.controls {section?}` lists `{id, min, max, default, step, value}` for the
active photo.

```text
develop.set {"values": {"light.exposure": 0.3, "light.highlights": -40}, "ids": [4]}   -> {"result": null}
develop.adjust {"control": "light.exposure", "delta": 0.1}                             relative, active photo
develop.quickAdjust {"control": "light.exposure", "delta": 0.1, "ids": [2, 3]}         relative, each from its own value -> {changed}
develop.reset {"ids": [7]}        develop.resetSection {"section": "light"}
develop.sectionEnabled {"section": "grading", "enabled": false}                        switch a section off to compare, then on
```

### Controls and units

| Section | Controls | Range (default) |
|---|---|---|
| Profile | `profile.amount` | 0 to 200 (100) |
| White balance | `wb.temp`, `wb.tint` | 2000 to 50000, -150 to 150; see below |
| Light | `light.exposure` | -5 to 5 stops (0), step 0.01 |
| | `light.contrast`, `.highlights`, `.shadows`, `.whites`, `.blacks` | -100 to 100 (0) |
| Parametric curve | `curve.highlights`, `.lights`, `.darks`, `.shadows` | -100 to 100 (0) |
| | `curve.splitShadows`, `.splitMid`, `.splitHighlights` | 10 to 70 (25), 20 to 80 (50), 30 to 90 (75) |
| Color | `color.vibrance`, `color.saturation` | -100 to 100 (0) |
| Mixer | `mixer.<band>.hue`, `.sat`, `.lum`; bands `red orange yellow green aqua blue purple magenta` | -100 to 100 (0) |
| B&W mix | `bw.<band>` | -100 to 100 (0) |
| Grading | `grading.<range>.hue`, `.sat`, `.lum`; ranges `shadows midtones highlights global` | hue 0 to 360, sat 0 to 100, lum -100 to 100 |
| | `grading.blending`, `grading.balance` | 0 to 100 (50), -100 to 100 (0) |
| Effects | `effects.texture`, `.clarity`, `.dehaze` | -100 to 100 (0) |
| Vignette | `vignette.amount`, `.midpoint`, `.roundness`, `.feather`, `.highlights` | amount -100 to 100 (0), negative darkens |
| Grain | `grain.amount`, `.size`, `.roughness` | 0 to 100 (0, 25, 50) |
| Detail | `detail.sharpenAmount` | 0 to 150 (a raw starts at 40, a JPEG at 0) |
| | `detail.sharpenRadius`, `.sharpenDetail`, `.sharpenMasking` | 0.5 to 3 (1.0), 0 to 100 (25), 0 to 100 (0) |
| | `detail.nrLuminance`, `.nrDetail`, `.nrContrast`, `.nrColor` | 0 to 100 (a raw starts with `nrColor` 25) |
| Optics | `optics.distortion`, `.vignetting`, `.profileDistortion`, `.profileVignetting`, `.defringePurple`, `.defringeGreen` | manual -100 to 100; profile amounts 0 to 200 (100); defringe 0 to 20 |
| Geometry | `geometry.vertical`, `.horizontal`, `.aspect`, `.rotate`, `.scale` | -100 to 100; rotate -10 to 10 degrees; scale 50 to 150 |
| Crop | `crop.angle` | -45 to 45 degrees |

Hue angles of the grading wheels: 0 red, 45 orange, 60 yellow, 120 green, 180 cyan, 215 teal-blue,
240 blue, 300 magenta.

### Profile and lens

```text
profiles.list {}   -> {"result": [{id, name, group}]}
develop.profile {"id": "lc.portrait", "amount": 100}
```

Built-in profiles: `lc.color` (the default), `lc.neutral`, `lc.vivid`, `lc.landscape`,
`lc.portrait`, `lc.mono`; film looks `lc.film.warm-print`, `lc.film.cool-fade`,
`lc.film.golden-hour`, `lc.film.faded-slide`; cinematic `lc.cine.teal-amber`, `lc.cine.night-blue`,
`lc.cine.desert-heat`, `lc.cine.neon-dusk`; muted `lc.muted.matte-soft`, `lc.muted.bleached`,
`lc.muted.pastel-haze`, `lc.muted.quiet-green`; black and white `lc.bw.mono-rich`,
`lc.bw.red-filter`, `lc.bw.soft`, `lc.bw.sepia`.

A raw is imported with its lens correction on (`optics.lens_profile: true` in `develop.get`).
`photo.inspect {id}` -> `embedded_lens` says where the correction came from: the file's own data,
or `"source": "database"` once the lens database is there. Switches that are not sliders are set
with a partial settings object:

```text
develop.merge {"settings": {"optics": {"lens_profile": true, "remove_ca": true}}, "label": "Lens"}
geometry.upright {"mode": "auto"}     -> {mode, transform}; modes off|auto|level|vertical|full
```

### White balance

```text
develop.wb {"mode": "asShot"}                           -> {"temp": 4519, "tint": 41}
develop.wb {"mode": "auto"}                             -> {"temp": 4470, "tint": 52}
develop.wb {"mode": "daylight"}                         -> {"temp": 5500, "tint": 10}   also cloudy|shade|tungsten|fluorescent|flash
develop.wb {"mode": "custom", "temp": 5150, "tint": 10}
develop.wbPick {"x": 0.639, "y": 0.60}                  -> {"temp": 5049, "tint": 37}   a point that should be neutral
```

- **Raw**: `temp` is Kelvin and `tint` is green (negative) to magenta (positive);
  `develop.get` -> `wb.scale` is `"kelvin"` and `photo.inspect` -> `as_shot_wb` is the camera's
  white. A higher number makes the picture warmer.
- **JPEG, TIFF, PSD**: the scale is relative. 6500 and 0 mean "as it is"; 6900 is a little warmer,
  6100 a little cooler. Do not carry a Kelvin value from a raw onto a JPEG.
- `develop.wbPick` on a gray patch brought it from RGB (222, 230, 247) to (229, 229, 229) in the
  test. A point that is not neutral gives nonsense (tint 150): pick gray card, white paper in
  shade, or a gray wall, never a blown highlight.

### Tone curve

```text
develop.curve {"channel": "master", "points": [[0, 0], [0.25, 0.22], [0.5, 0.5], [0.75, 0.78], [1, 1]]}
curve.reset {"channel": "all"}
```

`channel` is `master`, `red`, `green`, or `blue`; points are `[input, output]` from 0 to 1, in
order. An S of 0.03 at the quarter points is a visible but gentle contrast; 0.06 is strong. Lifting
the first point (`[0, 0.04]`) gives matte blacks. The four `curve.*` sliders are the parametric
curve and add to the point curve.

### Color

Use `color.vibrance` before `color.saturation`: it protects skin and already-saturated colors.
The mixer changes one band: `mixer.orange.*` is skin, `mixer.blue.*` sky, `mixer.green.*` and
`mixer.yellow.*` foliage. `develop.targeted {"target": "lum", "x": 0.4, "y": 0.55, "delta": 5}`
moves the bands under a point and returns the controls it changed.

### Black and white

```text
develop.treatment {"bw": true}
develop.autoBwMix {}                -> {"mix": [8 numbers]}: a mix from the photo's own colors
develop.set {"values": {"bw.orange": 12, "bw.blue": -20}}
```

Tone a monochrome with the grading wheels (`grading.shadows.hue` 230 at `sat` 6, highlights 40 at
8 is a quiet split tone).

### Masks

```text
mask.add {"kind": "radial", "center": [0.5, 0.45], "rx": 0.3, "ry": 0.25, "feather": 60, "name": "Lift center"}  -> {"activeMask": 1}
mask.add {"kind": "linear", "start": [0.5, 0.0], "end": [0.5, 0.3], "name": "Top burn"}
mask.add {"kind": "sky"}        mask.add {"kind": "subject"}        mask.add {"kind": "background"}
mask.add {"kind": "luminanceRange", "lo": 0.8, "hi": 1.0}
mask.add {"kind": "colorRange"}  then  mask.sampleColor {"x": 0.40, "y": 0.55}
mask.add {"kind": "brush"}       then  mask.brushStroke {"points": [[0.33, 0.42], [0.35, 0.43]], "size": 0.02, "feather": 80, "flow": 60}
mask.adjust {"values": {"exposure": 0.25, "clarity": 8}}              the selected mask, or {"id": n, "values": ...}
mask.addComponent {"op": "subtract", "kind": "luminanceRange", "lo": 0.0, "hi": 0.25}
mask.invert {}    mask.visible {"visible": false}    mask.select {"id": 2}    mask.delete {}    mask.deleteAll {}
```

- A **radial** mask affects the inside of the ellipse; `rx` and `ry` are fractions of the picture.
- A **linear** mask is full strength at `start` and fades to nothing at `end`; past `end` nothing
  changes. Measured: `start` at the top edge, `end` at mid-height, exposure +1.5 raised the top band
  from 137 to 216 and left the bottom at 52.
- `sky`, `subject`, and `background` are found by rules, not by a model. Look at the result
  (`view.maskOverlay`, `engine_screenshot`) before you trust it; fall back to a radial or a brush.
- `mask.adjust` keys: `exposure` (stops, clamped to plus or minus 4), `contrast`, `highlights`,
  `shadows`, `whites`, `blacks`, `temp`, `tint`, `texture`, `clarity`, `dehaze`, `hue`,
  `saturation`, `sharpness`, `noise`, `moire`, `defringe`, `amount` (all clamped to plus or minus
  100; `amount` 0 to 100 scales the whole mask).
- Masks are listed in `develop.get` -> `masks` with their shapes and values.

### Retouching that stays in LightCraft

`spot.add {"mode": "heal", "points": [[0.9, 0.1]], "size": 0.01}` -> `{index}` removes a dust spot
or a blemish (`spot.delete {}` takes the selected one away). More than a few spots, reshaping,
frequency separation, or compositing is PhotoCraft's work.

### Crop and geometry

```text
crop.set {"rect": [0.1, 0.0, 0.6333, 1.0]}     [x0, y0, x1, y1]
crop.straighten {"angle": 1.5}                 keeps the crop inside the picture, shrinking it if it must
crop.autoStraighten {}                         -> {"changed": false, "reason": "no dominant horizontal or vertical lines"}
crop.reset {}
```

To crop to a ratio, compute the rect from the photo's pixel size (`catalog.query`): for a ratio
`w:h` out of a `W x H` photo at full height, the width fraction is `(H * w / h) / W`. A 4:5 from
8256 x 5504 is `5504 * 0.8 / 8256 = 0.5333` wide, so `[0.1, 0, 0.6333, 1]`, and it exported at
exactly 1080 x 1350.

### Versions, history, undo

```text
version.create {"name": "Color v1"}     version.restore {"index": 1}
history.previous {}    history.next {}    edit.undo {}    edit.redo {}
```

Make a version before a change of direction (color to black and white, a heavier grade) so the
person can go back. Versions are listed in `photo.inspect` -> `versions`, oldest first; a virtual
copy starts with an automatic one at index 0.

## Presets and consistency

```text
presets.list {}                                   -> {"result": [{id, name, group, builtin}]}
preset.create {"name": "Forest warm-cool", "group": "Shoot"}                 -> {"id": "user.41.forest-warm-cool"}
preset.create {"name": "...", "groups": ["light", "toneCurve", "color", "colorGrading"]}
preset.apply {"id": "user.41.forest-warm-cool", "amount": 100, "ids": [2, 3]}
preset.export {"path": "<project>/presets/forest-warm-cool.lcpreset", "ids": ["user.41.forest-warm-cool"]}  -> {count, path}
preset.import {"paths": ["<file or folder>"], "dryRun": true}                -> {imported: [{id, name, group}], failed}
```

- A preset is made from the **active** photo. Without `groups` it takes everything except crop,
  masks, and spot removal, which includes white balance and exposure. For a look that travels
  across a set, name the groups and leave `whiteBalance` and `light` out.
- Setting groups: `profile`, `treatment`, `whiteBalance`, `light`, `toneCurve`, `color`,
  `colorMixer`, `colorGrading`, `effects`, `vignette`, `grain`, `detail`, `optics`, `geometry`,
  `crop`, `masks`, `spots`, `redEye`, `lensBlur`, `calibration`.
- `amount` 0 to 200 scales a preset's strength. 41 presets ship with LightCraft (`lc.golden-hour`,
  `lc.soft-skin`, `lc.clean-studio`, `lc.bw-high-contrast`, `lc.crisp-landscape`, ...).

```text
library.select {"ids": [1, 4, 5], "active": 1}
develop.sync {"groups": ["light", "toneCurve", "colorGrading", "color", "effects"]}   -> {"changed": 2}
develop.matchExposure {}                                                               -> {"changed": 2, "skipped": []}
develop.copy {"groups": ["colorGrading", "toneCurve"]}   then   develop.paste {"ids": [8]}   -> {"changed": 1}
```

`develop.sync` copies the active photo's groups to the rest of the selection.
`develop.matchExposure` sets each selected photo's Exposure so that its total exposure (shutter,
aperture, ISO, and the slider) equals the active photo's: the tool for a run shot in changing
light. `develop.autoSync {"on": false}` -> `{on}`: keep it off, so an edit never spreads by
accident.

A LUT from another engine becomes a profile:

```text
profile.import {"paths": ["<project>/handoff/filmcraft-to-lightcraft/look-v1.cube"]}
   -> {"imported": [{"id": "lut:imported-warm-test", "name": "warm test", "group": "Imported"}], "failed": []}
develop.profile {"id": "lut:imported-warm-test", "amount": 100}
```

## Export

```text
app.export {"ids": [1, 2, 3], "dir": "<project>/exports/web", "format": "jpeg", "longEdge": 2048,
            "quality": 88, "colorSpace": "srgb", "sharpen": "screen", "metadata": "copyright", "conflict": "overwrite"}
   -> {"files": [{"path", "width", "height", "bytes", "sidecars"}]}
app.export {"ids": [1], "path": "<project>/exports/master/CZP_0299.tif", "format": "tiff", "longEdge": 0,
            "bitDepth": 16, "colorSpace": "adobeRgb", "tiffCompression": "zip", "ppi": 300}
```

| Option | Values |
|---|---|
| `ids` | The photos. Without it, the selection |
| `dir` or `path` | A folder (names from `naming`), or one file's full path. Folders are made |
| `format` | `jpeg`, `png`, `tiff`, `psd` (flat), `webp`, `avif`, `jxl`, `dng` (a raw, with its edits embedded), `original` (the file copied, with an `.xmp` beside it) |
| Size: one of | `longEdge` (0 = full size), `shortEdge`, `width` + `height`, `megapixels`, `percent`. `dontEnlarge` is true unless you say otherwise |
| `fit` | With `width` + `height`: `dimensions` (fits either orientation: 2400 x 3000 gave 3000 x 2000 from a landscape) or `widthHeight` (width and height as the photo stands) |
| `quality` | 1 to 100, for `jpeg`, `avif`, lossy `jxl`, `webp` |
| `limitKb` | A file-size ceiling for JPEG: `limitKb: 500` gave 504 kB at 2560 px |
| `colorSpace` | `srgb`, `displayP3`, `adobeRgb`, `proPhoto`, `rec2020`. The profile is embedded |
| `bitDepth` | 8, 10, 16, or 32, where the format carries it: 16 for `tiff`, `png`, `psd` |
| `tiffCompression` | `zip` (default), `lzw`, `none` |
| `ppi` | The print resolution written into the file (240 unless given). It does not resize |
| `sharpen` | `none`, `screen`, `matte`, `glossy`: sharpening for the output size and medium |
| `metadata` | `all`, `allExceptCamera`, `copyright` (credit only; camera data removed), `none`; `removeLocation: true` |
| `naming` | A template: `{name}`, `{seq}`, `{seq:2}`, `{date:%Y%m%d}`, `{camera}`, `{rating}`, `{title}`. `photo.renameTokens {}` lists them |
| `conflict` | `unique` (adds a number), `overwrite`, `skip` |
| `preset` | A saved export preset's name; other options override it |
| `background` | `true` answers `{"background": true, "total": n}` at once |

Built-in export presets (`export.presets {}`): `JPEG (Small)` (2048, q85), `JPEG (Large)` (full,
q92), `Web / Portfolio` (2048, q85, credit only), `Instagram Feed` (1080 long edge, q85, screen
sharpening), `Instagram Story / Reel` (1920), `Full Resolution Master` (full, q95, Display P3),
`Original + Settings`, `DNG`. Save the person's own with
`export.savePreset {"name": "Client web 2400", "params": {...}}` and reuse it with
`{"preset": "Client web 2400"}`.

A long batch:

```text
app.export {..., "background": true}                      -> {"background": true, "total": 9}
ui.inspect  -> export.running {current, done, total}      poll every few seconds
ui.inspect  -> export.running null, export.last.files     done; check last.cancelled is false
```

### Looking at and measuring a result

```text
engine_call(id, "ui.render", {"id": 1, "size": 1600, "path": "<project>/renders/1-after.png"})
engine_exec(id, "selkies-modal-histogram <project>/renders/1-after.png")
engine_exec(id, "selkies-modal-histogram <project>/renders/9-after.png --region 0.36,0.48,0.42,0.60")
```

`selkies-modal-histogram` prints one JSON object for a JPEG, PNG, TIFF, WebP, or PSD:

```text
{"width", "height", "pixelFormat", "profile", "bytes", "region",
 "luma": {"p1", "p5", "p25", "p50", "p75", "p95", "p99"},        0 to 255, of the encoded picture
 "mean": {"luma", "r", "g", "b"},
 "clipped": {"black", "white"},                                   share of the picture with every channel at an end
 "channelClipped": {"low", "high"},                               share with any one channel at an end
 "histogram": [16 shares, dark to light]}
```

`profile` is the embedded color profile's name (`sRGB`, `Display P3`,
`Adobe RGB (1998) compatible`, `ProPhoto RGB`), or null; `pixelFormat` shows the depth (`rgb48le`
is 16 bits). `--region x0,y0,x1,y1` measures a rectangle, in fractions of the picture: a cheek, a
gray card, a sky. It reads a picture scaled to 512 pixels wide, so it reports areas, not single
blown pixels.

## What was measured

On the Starter tier's machine (no GPU), with raws of 24 to 33 megapixels and a 45-megapixel JPEG:

| Step | Time |
|---|---|
| Engine start until the first command is answered | about 6 s |
| One `engine_call` round trip | 0.2 to 0.4 s |
| Import of 9 photos in place | 0.3 s |
| `photo.analyze` of 9 photos | 4 s |
| A slider change until the finished picture is on the person's screen | 0.3 to 0.4 s |
| Opening another photo until its finished picture | 1.1 to 1.4 s |
| `ui.render` at 600 to 1600 px | 0.4 to 2.6 s |
| Export, one photo to JPEG at 2048 px | 2 to 3 s |
| Export, one photo to JPEG at full size (33 MP) | 5 s |
| Export, one photo to 16-bit TIFF at full size | 7 s (33 MP) to 15 s (45 MP) |
| Export, 9 photos to JPEG at 2048 px | 12 s |
| Export, 9 photos to JPEG at full size, in the background | about a minute |

So that no call runs into LightCraft's 60 s limit: export with `background: true` whenever a call
covers more than 15 resized photos or more than 3 at full size.

The Studio tier (a T4, twice the processor, four times the memory) answered a slider in 0.17 to
0.19 s and opened a photo in 0.6 s. Its exports took about as long as the Starter's, but for a
full-size JPEG (3 s instead of 5).
