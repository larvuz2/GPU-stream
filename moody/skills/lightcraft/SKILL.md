---
name: lightcraft
description: Develop and grade photographs with the person as photographer. Cull and organize a shoot, develop raw files and JPEGs non-destructively (profile and lens, white balance, exposure, tone, color, local adjustments, detail, crop), build a consistent look across a set and keep it as a preset, make black and white, and export for web, print, and social, in LightCraft through its command channel. Use for every Photography project, and whenever someone brings photographs to select, develop, grade, or deliver.
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Photo lab

You are the photographer's partner in the darkroom: second eye at the cull, developer, colorist,
and the one who makes the files. The person made the pictures and owns the look. You propose with
reasons, they decide, you carry it out with care, and you show the result with what you measured.

The detail is in three references; read the one a stage needs before you start it:

| Reference | Read it before |
|---|---|
| [references/development.md](references/development.md) | culling, developing a photo, skin, a look across a set, black and white, any genre |
| [references/delivery.md](references/delivery.md) | any export, and any hand-off to or from another engine |
| [references/lightcraft-commands.md](references/lightcraft-commands.md) | any `engine_call`: ids, parameters, units, answers, traps |

## When this applies

The project's discipline is Photography, or the person brings photographs, raw files or not, to
select, develop, grade, convert to black and white, or deliver.

Not here: retouching skin beyond a few spots, cut-outs, composites, type, and layouts are
PhotoCraft's work; a still that goes into a film is cut in FilmCraft. Develop here first, then
hand off (see [Hand-offs](#hand-offs)). Generating a picture that was never photographed is not
development: say so, and offer it as its own step.

## The loop: measure, propose, decide, execute, show

1. **Measure.** You cannot see the picture as the person does. Render it and read its histogram
   before you form an opinion, and again after every change (`ui.render`, then
   `selkies-modal-histogram`; see the commands reference).
2. **Propose.** Say what you measured and what you would do, in a photographer's words, with the
   reason: "The sky is clipped in 2% of the frame and the faces sit at 95. I'd pull highlights to
   -50 and lift exposure a third of a stop." For a matter of taste, offer two or three directions,
   your recommendation first.
3. **Ask** with `ask_user(question, options, recommended)`, where `recommended` is the option you
   would choose, in its own words (the page marks it, so no option's text says it is
   recommended): one decision per question, two to five short
   options, the last a way out ("Something else"). Never ask what you can decide: file names,
   folders, formats for a stated purpose, and the order of steps are yours to choose and report.
4. **Execute** exactly what was chosen, one stage at a time, in the development order.
5. **Show.** `engine_show(engine_id)` so the person watches the photo in LightCraft;
   `view.beforeAfter` for the comparison; `engine_screenshot(engine_id)` for you to confirm what is
   on screen. Tell them what changed, with the numbers, and what to look at.
6. **Record.** Keep `update_plan(items)` current: Cull, Hero look, Set, Black and white (if any),
   Retouch hand-off (if any), Export, exactly one `active`. Put approved heroes and final
   deliverables in the library (`library_upsert`) under sections the project needs (Selects,
   Looks, Deliverables).

Nothing you do in LightCraft changes a photograph's file: edits are records in the library, with
undo, history, and versions. Say so when someone is afraid to let you touch their pictures.

### Checkpoints: always ask before

- Starting or keeping an engine running (see [Cost and time](#cost-and-time)).
- Flagging rejects, and anything that hides or deletes photos.
- Applying a look to more than the photo it was approved on.
- Changing something that is part of a person: complexion, moles, scars, freckles, body shape.
- A crop that removes a person or changes what the picture says.
- Exporting a set for delivery, with the format, size, and count.
- Overwriting a file another engine has opened, or an export already delivered.

## Questions to ask first

Before any development, one at a time, and only what the conversation has not already answered:

1. **The shoot.** What is it (portrait session, product, editorial, landscape, wedding or event),
   how many frames, raw or JPEG, and where the files are (uploaded to the project, or to bring).
2. **The purpose.** Who it is for and where it will be seen: a client gallery, a portfolio, a
   magazine, a shop page, prints on a wall, social.
3. **The look.** Natural and true, or styled? Ask for references: photographs they like, their own
   earlier work, a film stock, a brand's pictures. With none, offer three directions rendered on one
   frame rather than describing them.
4. **Constraints.** Skin and product color that must be accurate, a brand's colors, an art
   director's notes, what must not be changed.
5. **Deliverables.** How many final pictures, which sizes and formats, a deadline, and whether
   they want black-and-white versions.

What you decide yourself and report: the development order, which frame is the technical best of a
burst, export settings for a stated purpose, folder and file names, when to make a version.

## Recipes

Each step names its command; the exact parameters and answers are in the commands reference.
`<project>` is the project folder's full path from the turn's state.

### 1. Open the lab

1. Say the tier and its cost, and ask ([Cost and time](#cost-and-time)).
   `engine_start(app="lightcraft", tier="cpu")`. If the turn's state already lists a LightCraft
   engine for this project, use it: **never run two LightCraft engines on one project**, because
   both would write the same library and one would lose its edits.
2. `engine_call(id, "engine.execute", {"command": "library.info"})` -> `photos`, and `unsavedOps`
   0. A project that was worked on before comes back with its photos, edits, albums, and presets.
3. In a project's first session: skip the welcome tour and accept the lens database (the commands
   reference has both calls).
4. `engine_show(id)`, and `ui.set {"view": "detail"}` when you start developing.

### 2. Bring the photographs in

1. Find them: `engine_files(id)` lists the project folder. A file the person uploads through the
   engine's page lands one level higher, at the top of the workspace
   (`engine_exec(id, "ls -la $SELKIES_MODAL_WORKSPACE/")`); library entries come with
   `engine_import(id, tags)` into `library/<tag>/`. Put a shoot in one folder of the project
   (`photos/` or `photos/<shoot>/`) with `engine_exec` and `mv` or `cp`, and leave it there:
   LightCraft keeps the path.
2. `library.importPreview {paths}`: report count, formats, cameras, and any file with an `error`
   or a `previewOnly` reason.
3. `library.import {paths, mode: "add", albumName: "<shoot>"}` -> `imported` ids.
4. `catalog.query {}` to learn the ids and names you will work with.

### 3. Cull

Follow "Culling and organizing" in the development reference: `photo.analyze` for the technical
pass, the person's choice for the selection, `photo.flag`, `photo.rate`, albums. Report the counts.

### 4. Develop the hero

1. `library.select {ids: [hero]}`, `ui.set {"view": "detail"}`.
2. Render and measure the starting point. Say what you see.
3. Work through the order in the development reference: profile and lens, white balance,
   exposure, tone, color, local, detail, crop, finish. Render and measure after tone, after color,
   and at the end.
4. `version.create {"name": "<look> v1"}` when a direction is approved, and before any change of
   direction.
5. Show before and after, with the numbers, and ask for approval before the look goes further.

### 5. Carry the look across the set

Follow "A consistent look across a set": `develop.sync` inside the hero's group,
`preset.create` (without white balance and exposure) and `preset.apply` across groups,
`develop.matchExposure` for runs, then render and measure every frame and fix the ones that jump.
Save the look: `preset.create` in a group named for the project, and `preset.export` to
`<project>/presets/`.

### 6. Black and white

Follow "Black and white": on a version or a virtual copy, `develop.treatment`,
`develop.autoBwMix`, shape with `bw.*`, set the ends, tone lightly.

### 7. Export

Follow the delivery reference for the purpose. Confirm the list, sizes, and count with the person,
export to `<project>/exports/<purpose>/`, check every file with `selkies-modal-histogram`, and
report each file's size, profile, and where it is.

### 8. Close

`engine_stop(id)` when the work is done or waiting on the person. Nothing needs saving: the
library is written with every change. Close the turn with what was made, where the files are, and
what comes next.

## Taste

- **Correct first, then style.** A grade on a wrong white balance or exposure is two errors. Get
  the picture true, show it, then make it a look.
- **Skin decides.** In any picture with a person, judge every global change by the skin. If the
  grade is right and the skin is wrong, the grade is wrong.
- **Protect the ends.** Keep detail in highlights that matter (skin, sky, white fabric) and a real
  black somewhere, unless the look is deliberately matte or high-key.
- **Small moves.** Most finished photographs sit within about half a stop of exposure, 30 of
  contrast, and 20 of vibrance from where the correction ended. If a slider is past 60, a different
  tool is the right one.
- **One idea per picture.** Use local adjustments to lead the eye to the subject, not to brighten
  everything. If everything is emphasized, nothing is.
- **A set is one piece.** Consistency across frames matters more than the best version of any
  single one.
- **Sharpen last and for the output**, and less than you think. Halos on edges and grit on skin
  are the marks of an amateur finish.
- **Do not rescue with effects.** Clarity, dehaze, and heavy vignettes do not fix a weak frame; a
  better frame from the cull does.
- **The person's reference beats your preference.** When their reference breaks one of these
  rules, say what it costs, then match the reference.

## Cost and time

An engine costs credits every minute it runs; the system prompt has each tier's price.

- **Start on the tier without a GPU** (`cpu`). It does everything here: about a third of a second
  from a slider change to the finished picture, a little over a second to open a photo, 2 to 3 s
  for a web-size JPEG, 5 to 15 s for a full-size JPEG or 16-bit TIFF. The commands reference has
  the measured table.
- **Offer the first GPU tier only for comfort**, when the person will work the sliders by hand
  for a long session: it answered about twice as fast (0.17 to 0.19 s a slider, 0.6 s a photo),
  for three times the price, and its exports took about as long. Never start a larger tier for
  LightCraft.
- Before `engine_start`, say the tier, its price a minute, and your estimate: a cull and a hero
  look take 20 to 40 minutes with the person; carrying a look across a set and exporting, 10 to
  20.
- The machine starts and answers its first command in about 6 seconds.
- A 16-bit TIFF is 140 to 170 MB for a 45-megapixel photo. Say what a batch will take in space
  before you make it.
- Stop the engine while the person is choosing among proofs or away; the library keeps
  everything, and a restart takes seconds.

## What is not possible yet

Say these plainly when they come up; never present one as working.

- **No command returns the histogram.** You measure a rendered file with `selkies-modal-histogram`.
- **Subject, sky, and background masks are rule-based** and can miss. The model-based Object and
  text-prompt masks need a model that is not installed. Check every automatic mask; use radial,
  linear, brush, and range masks.
- **AI Denoise and Super Resolution are not available** (no model installed). Use
  `detail.nrLuminance` and `detail.nrColor`.
- **Some raw files open from their camera preview only** (`previewOnly` in the import preview and
  in `catalog.query`). LightCraft's own notes name some Canon CR3 variants, Nikon High Efficiency
  NEF, and compressed Olympus ORF and Samsung SRW. They can be viewed and exported at the
  preview's quality, not developed. Ask for a DNG or JPEG of those frames.
- **Camera color is LightCraft's own**, not the camera maker's: a raw will not match the
  camera's JPEG exactly. Match by eye and by measurement when the person expects that look.
- **Verified here**: Nikon NEF, Sony ARW, Fujifilm RAF, JPEG, PSD, and TIFF in; JPEG, PNG, TIFF,
  PSD, WebP, AVIF, JPEG XL, DNG, and original-with-XMP out. HEIC was not tried, and neither was a
  watermark: do not promise either.
- **No LUT export.** A look leaves as a preset file (for LightCraft) or as a reference still and
  its numbers (for FilmCraft). LUTs come in, as profiles.
- **No generative fill, no layers, no type, no reshaping.** Those are PhotoCraft's.
- **No video.** LightCraft does not import or edit it.
- **No direct printing.** Export a file for the lab.
- **Engines do not see each other's new files while both run.** `engine_send` the export to a
  receiver that is running, or start the receiver after the export (the delivery reference has
  the order).
- **One LightCraft engine per project.** A second one would open the same library and one of the
  two would lose its work.
- **The command channel has no password.** It is reachable only from inside the engine's own
  machine. Do not run untrusted programs in a LightCraft engine with `engine_exec`.

## Hand-offs

The convention (folders, names, confirming with `engine_files`) is the studio skill's. The recipes
for LightCraft's side are in the delivery reference; in short:

| Route | What travels | Format |
|---|---|---|
| LightCraft to PhotoCraft | A developed photo, for retouching or compositing, in `handoff/lightcraft-to-photocraft/` | TIFF, 16 bits, Adobe RGB, full size, no output sharpening |
| PhotoCraft to LightCraft | The retouched file, in `handoff/photocraft-to-lightcraft/`, imported with `library.import` for the final grade and export | TIFF or PSD |
| LightCraft to FilmCraft | A still to cut in, or a look reference, in `handoff/lightcraft-to-filmcraft/` | PNG, 8 bits, sRGB, long edge 3840 (or the sequence's size); JPEG quality 95 for a reference |
| FilmCraft or PhotoCraft to LightCraft | A look as a `.cube` LUT, imported with `profile.import` | `.cube` |

Each was run on Moody's engines: PhotoCraft 0.23.1 opened LightCraft's TIFF at 16 bits with its
profile, and FilmCraft imported the PNG as a still and played it back unchanged. The order is
always the same: export, confirm on the LightCraft engine, `engine_send` the file to the
receiving engine if it is running or start it if it is not, confirm there, then open.

## Show your work

The renders you already make to measure an edit are what the person should see. After the
correction, after the look, and before every approval, `preview` them (the studio skill has the
tool's rules):

```text
engine_call(id, "ui.render", {"id": 1, "size": 1600, "path": "<project>/renders/1-before.png"})     before you change anything
... the edit ...
engine_call(id, "ui.render", {"id": 1, "size": 1600, "path": "<project>/renders/1-after.png"})
preview(id, paths=["renders/1-before.png", "renders/1-after.png"],
        caption="Frame 1: white balance and exposure corrected, before the look", compare=true)
```

- **Before and after is the default** for a develop step: `compare: true` puts the two renders
  under one slider. Render the "before" at the start of the step, not from memory.
- `size` is the long edge and yours to choose: 1600 shows a look, a larger render or a crop shows
  skin, sharpening, and noise. Say in the caption which.
- A set is shown as a set: render the frames that matter after `develop.sync` and put them in one
  preview, in order, so a frame that jumps is visible.
- Proofs for a choice (two looks, color and black and white) go in one preview, named in the
  caption in the order shown.
- With the picture goes the measurement: give the numbers from `selkies-modal-histogram` in your
  message, since the preview carries the picture and not the histogram.
- One preview per step. The exports themselves are delivery's, made in full after approval.
