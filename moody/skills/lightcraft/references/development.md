<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Developing a photograph

The craft, in the order the work goes. Command ids and ranges are in
[lightcraft-commands.md](lightcraft-commands.md).

## Measure before you move a slider

You cannot see the picture the way the person does, and the window dims behind any open dialog,
so a screenshot can lie about brightness. Before the first edit of a photo, and after every
stage, render and read it:

```text
engine_call(id, "ui.render", {"id": 1, "size": 1600, "path": "<project>/renders/1-before.png"})
engine_exec(id, "selkies-modal-histogram <project>/renders/1-before.png")
```

A raw that looked two stops under in a screenshot measured a median of 109 with nothing clipped:
it was correctly exposed, and +0.85 stops would have ruined it. Believe the numbers.

### Reading the histogram

All values are 0 to 255 in the rendered picture.

| What you read | What it means | What to do |
|---|---|---|
| `luma.p50` 100 to 135 | An average scene sits here | Leave exposure alone unless the scene is meant to be dark or bright |
| `luma.p50` under 80 | Dark | Low-key on purpose (night, stage, a black backdrop)? Keep it. Otherwise raise `light.exposure`: about +0.3 stops lifts the median by 15 to 20 |
| `luma.p50` over 160 | Bright | High-key on purpose (snow, a white studio, backlit haze)? Keep it. Otherwise lower exposure |
| `luma.p1` over 25 | No true black: the picture looks flat or hazy | Lower `light.blacks` (-10 to -30) until `p1` is 5 to 15, unless a matte look was asked for |
| `luma.p99` under 225 | No bright white: dull | Raise `light.whites` until `p99` is 240 to 250 |
| `clipped.white` over 0.005 | Blown areas | Lower `light.highlights` (-30 to -70), then exposure. A light source or a reflection on chrome may stay blown; skin, sky, and white fabric may not |
| `clipped.black` over 0.01 | Blocked shadows | Raise `light.shadows` (+15 to +40) or `light.blacks` |
| `channelClipped.high` far above `clipped.white` | One color channel is blown: a red dress, a neon sign, a deep blue sky | Lower `color.saturation` or that band's `mixer.<band>.sat`, or lower exposure. A wider color space at export helps too |
| `histogram` piled into the middle bins | Low contrast | Contrast, or an S-curve |
| `histogram` with two piles and an empty middle | A contrasty scene: backlight, noon sun | Highlights down and shadows up before any contrast |

The numbers describe; the picture's intent decides. A fog scene should have no black. A silhouette
should clip its blacks. Say what you saw and why you left it.

## The order that works

Each stage sets up the next, so going back costs rework. Do the global stages for the whole
picture before any mask.

1. **Profile and lens.** `develop.profile` sets the rendering everything else is built on:
   `lc.color` for most work, `lc.portrait` for people, `lc.landscape` for scenery, `lc.neutral`
   when a heavy grade follows. Choose it first, because it changes contrast and color. Lens
   correction is on for a raw at import; add `remove_ca` when there are color fringes on
   high-contrast edges (branches against sky).
2. **White balance.** Before exposure, since it moves the channels. Start from the camera's
   (`asShot`). Use `develop.wbPick` on something that should be neutral when the scene has one.
   Neutral is not always right: a sunset, candlelight, and blue hour keep their cast. For people,
   skin decides (see [Skin](#skin)).
3. **Exposure.** Set the overall level for the subject, with `light.exposure` only. Do not use it
   to save highlights; that is the next stage.
4. **Tone.** `light.highlights` and `light.shadows` to fit the scene's range, `light.whites` and
   `light.blacks` to set the two ends, then contrast: `light.contrast` or a tone curve, not both
   hard. Highlights and shadows past 60 start to look processed; use a mask for the rest.
5. **Color.** `color.vibrance` first. Then the mixer for single colors. Then the grade
   (`grading.*`), which is taste: do it last among the global steps, on a picture that is already
   correct.
6. **Local.** Masks to lead the eye: lift the subject, hold back a bright edge or sky, even out a
   face. A local change of a third to half a stop is usually enough. If you need more than a stop
   locally, the global tone is wrong: go back.
7. **Detail.** Noise reduction before sharpening, at the end, because every stage above changes
   what noise and edges look like. Sharpen for the subject (`detail.sharpenMasking` 30 to 60 keeps
   sharpening off smooth skin and sky). Output sharpening for the size and medium is added at
   export (`sharpen`), not here.
8. **Crop and straighten.** Level the horizon, then crop for the frame. When the deliverable has a
   fixed ratio, crop to it now, so the person approves the real frame.
9. **Finish.** Vignette and grain last and lightly (`vignette.amount` -8 to -20; `grain.amount` 10
   to 25). Then render, measure once more, and show it.

Starting points, not recipes; measure after each:

| Situation | Try |
|---|---|
| Flat, hazy | `light.blacks` -15, `light.whites` +10, `effects.dehaze` +8 to +15, a gentle S-curve |
| Harsh sun | `light.highlights` -50, `light.shadows` +30, `light.contrast` -5, then set the ends |
| Backlit subject | Exposure for the background, then a `subject` or radial mask at +0.4 to +0.8 |
| Underexposed, high ISO | Exposure up, `detail.nrLuminance` 20 to 40, `detail.nrColor` 25 to 40, sharpening masking 50 |
| Mixed light (window and lamps) | Balance for the skin, then a mask with `temp` to cool or warm the other area |
| Bright sky, dark land | `sky` mask (check it) or a linear mask from the top: exposure -0.3 to -0.7, `dehaze` +10 |

## Skin

Skin is what people judge a photograph by. Measure a patch of evenly lit skin, away from a
highlight and from deep shadow (a cheek, the forehead):

```text
engine_exec(id, "selkies-modal-histogram <project>/renders/9.png --region 0.36,0.48,0.42,0.60")
```

- **Channel order.** Healthy skin of every complexion reads red above green above blue. Green at or
  above red is a green cast: raise `wb.tint`. Blue at or above green is cold or magenta: raise
  `wb.temp`, or lower the tint. Red far above green (more than about 1.5 times) is sunburn or
  oversaturation: lower `mixer.orange.sat` and `mixer.red.sat`.
- **Level.** As a guide for the lit side of a face, as mean luma: light skin 140 to 190, medium
  skin 100 to 155, deep skin 50 to 115. These are ranges people fall in, not targets: expose deep
  skin so it keeps its depth and its highlights, never toward a lighter range, and never lighten or
  darken someone's complexion to fit a look. Measured on a test portrait of a woman with deep skin,
  the cheek read (120, 94, 89) after development, and it looked right.
- **Tools, in this order.** White balance for the cast. Exposure for the level.
  `mixer.orange.lum` (+3 to +10) for a little glow and `mixer.orange.sat` (-3 to -10) to calm
  redness. `effects.texture` -5 to -15 softens pores without the plastic look that negative
  clarity gives. Keep `effects.clarity` and `effects.dehaze` at or below zero on faces.
- **Hold highlights.** Lower `light.highlights` until the forehead and cheek keep texture. Shine is
  retouching, which is PhotoCraft's work.
- **Whites of eyes and teeth** are not white. Do not push them past the brightest skin.
- Ask before you remove anything that is part of a person: moles, scars, freckles, wrinkles.

## A consistent look across a set

A set reads as one piece when white balance, exposure, and contrast match from frame to frame.
The grade comes after that.

1. **Group** the set by scene and light: same place, same light, same lens is one group.
2. **Choose a hero** in each group: sharp, typical, with skin if the set has people. Develop it
   completely and get the person's approval on it before touching the rest.
3. **Carry the correction** to the hero's group: `library.select` the group with the hero as
   `active`, then `develop.sync` with `whiteBalance`, `light`, `toneCurve`, `color`, `colorMixer`,
   `colorGrading`, `effects`, `detail`. Leave `crop` and `masks` out: they belong to one frame.
4. **Carry the look** to the other groups as a preset made from the hero **without**
   `whiteBalance` and `light`, so each group keeps its own correction:
   `preset.create {"name": ..., "groups": ["profile", "toneCurve", "color", "colorMixer", "colorGrading", "effects", "vignette", "grain"]}`,
   then `preset.apply` to the other groups' photos. Correct each group's own hero for white balance
   and exposure first.
5. **Even out exposure** inside a run shot in changing light: `develop.matchExposure` with the
   hero active.
6. **Check the set as a set.** Render every photo small (`ui.render` at 600), measure the median
   and a skin patch of each, and look for the frame that jumps: a median more than 15 away from
   its neighbors, or skin that turns. Fix that frame alone. Then show the person the set together
   (`view.survey` on the selection, `engine_screenshot`).

Never sync white balance across raw and JPEG, or across cameras, without looking: the numbers do
not mean the same thing (see the commands reference), and two cameras render the same Kelvin
differently.

## Presets

A preset is a starting point that saves time, not a look that fits every frame.

- Offer two or three of the built-in presets as directions, rendered on the hero, when the person
  has no reference: `preset.apply` with `amount` 60 to 80 reads as a suggestion rather than a
  filter. Undo between tries (`edit.undo`).
- Save the look you built with the person as a preset in a group named for the project, and
  export it into the project folder (`preset.export`), so it outlives the engine and can be
  brought into the next shoot (`preset.import`).
- After applying any preset, correct white balance and exposure for the frame it landed on.

## Black and white

Black and white is a rendering of color, so the mix is where it is made.

1. Finish white balance and exposure in color first.
2. `version.create` (or `photo.virtualCopy` to keep both), then `develop.treatment {"bw": true}`.
3. `develop.autoBwMix` for a mix from the photo's colors, then shape it: `bw.blue` and `bw.aqua`
   down darkens a sky, `bw.orange` and `bw.red` up lightens skin, `bw.green` and `bw.yellow` up
   opens foliage. Moves beyond 40 on neighboring colors in opposite directions make edges break.
4. Contrast carries a monochrome: set a real black and a real white, and use a curve.
5. Tone it, if at all, with the grading wheels at low saturation (5 to 10): warm highlights and
   cool shadows for a print feel. Grain 15 to 25 suits it.

## Genres

**Portrait.** The eyes and the skin are the picture. Profile `lc.portrait`. Balance and expose for
skin. Soften with `effects.texture`, never with heavy noise reduction. A `subject` or radial mask
at +0.15 to +0.3 and a background a little darker and less saturated separate the person without
looking lit. Sharpen with masking 40 to 60. Crop above or below a joint, never through one, and
leave room in the direction of the gaze.

**Product.** Accuracy first: the color of the product must be the color of the product. Use
`develop.wbPick` on a gray card or the white sweep, and keep a white background white without
clipping the product's own highlights (background 245 to 252, not 255 across the whole frame, if
it will be cut out later). Straighten verticals (`geometry.upright` or `crop.straighten`). Remove
dust with `spot.add`. Keep the grade neutral unless the brand has one. A cut-out, a composite, or a
shadow rebuild goes to PhotoCraft.

**Fashion editorial.** The look is part of the work, and the person or the art director owns it:
ask for references and build toward them on the hero. Skin stays believable however far the grade
goes; protect it with the mixer or grade through `grading.shadows` and `grading.highlights` rather
than a global tint. Fabric color and texture must survive: check `channelClipped.high` on saturated
garments. Consistency across the story matters more than any single frame.

**Landscape.** Range and depth. Profile `lc.landscape`. Hold the sky with highlights and a sky or
linear mask, open the land with shadows, and set the ends. `effects.dehaze` in small amounts (+5 to
+15) clears distance; past +25 it turns skies cyan and adds halos. Blues and greens oversaturate
first: use `mixer.blue.lum` down for a deeper sky instead of more saturation. Level the horizon.

**Events.** Volume and speed, with people who must all look good. Cull hard first. Correct by
group (ceremony, portraits, reception, each light is a group), sync, then touch only the frames
that need it. Mixed and changing light is the problem: fix white balance per group and
`develop.matchExposure` inside runs. Keep the look restrained and consistent; it has to suit
several hundred pictures and still be liked in ten years. Deliver in the order of the day.

## Culling and organizing

Do this before any development; never develop a frame that will be cut.

1. **Import in place** and look at what arrived: count, formats, cameras, and any `previewOnly`
   raw (it can be viewed and exported from its camera preview but not developed; say so).
2. **First pass, technical.** `photo.analyze {}` scores sharpness and clipping and groups
   near-duplicates. Propose rejects (soft, badly clipped, the weaker frames of a burst) as a list
   with the reason for each. Flag them only after the person agrees; a reject is hidden work, not
   a deleted file.
3. **Second pass, selection.** This one is the person's: moments, expressions, and what the set
   needs. Put candidates on screen (`view.compare` for two, `view.survey` for several), let them
   choose, and record it: `photo.flag` pick, `photo.rate` for tiers (5 hero, 4 deliver, 3 maybe).
4. **Organize.** An album per deliverable (`album.create`, `album.addPhotos`), keywords for
   subject and place, the credit line on everything (`metadata.savePreset`,
   `metadata.applyPreset`). A smart album (`album.createSmart`) keeps "four stars and up" current
   by itself.
5. **Report** the numbers: imported, rejected and why, selected, left to decide.
