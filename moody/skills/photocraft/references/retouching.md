<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Retouching, color, and compositing

What a retoucher does, in the order they do it, with the PhotoCraft commands for each step. The
commands were run as written, on a 2048 pixel portrait and on the poster of
photocraft-commands.md; parameters and units are explained there.

## First, look and agree

Open the picture, take a screenshot at fit and one at 100% on the face or the product, and say
what you see before you touch it: what is good, what distracts, what you propose. Then ask how
far to go, because that is the person's call, and recommend "Clean" unless the brief asks for a
look:

- "Clean: dust, blemishes, stray hairs, even skin, a little light. It still looks like the day
  it was taken."
- "Polished: clean, plus shaping light, stronger color, tidied background."
- "Stylized: a look. Tell me the reference."
- "Technical only: color and exposure, no retouching."

Ask separately before changing what is permanent about a person (scars, moles, lines, body
shape, skin tone) and never do it unasked. Ask before removing anything that changes what the
picture says happened.

## The order

Each stage is its own layers above the last, so any stage can be redone. Coarse before fine,
global before local, sharpening last.

| # | Stage | Layers it makes |
|---|---|---|
| 1 | Develop: exposure, white balance, range | A smart filter on the photograph, or adjustment layers |
| 2 | Clean: dust, blemishes, distractions | "Cleanup" (an empty layer above), fills on their own layers |
| 3 | Even: skin tone and texture, where needed | "Skin" group: Low, High |
| 4 | Shape: dodge and burn | "Dodge and burn" (Soft Light, 50% gray) |
| 5 | Color: correct, then grade | Adjustment layers, masked |
| 6 | Finish: grain, vignette, sharpen | "Vignette", "Grain", "Sharpen" on top |

### Set up

```text
app.open {"path": "library/portrait/photo.png"}
layer.new.layerFromBackground {}                      -> {"layer": 78}   (the locked Background becomes a layer)
layer.renameLayer {"layer": 78, "name": "Original"}
image.detectFaces {}
  -> {"faces": [{"rect": [721, 268, 357, 438], "score": 0.95, "landmarks": {"leftEye": [981, 423], "rightEye": [812, 412], "nose": [883, 509], …}}]}
app.save {"path": "portrait-retouch.pcraft"}
```

`image.detectFaces` gives you coordinates to aim at. Use them with a 100% screenshot around the
face (`ui.set {"zoom": 1, "center": [883, 480]}`, then `engine_screenshot`) to find each spot: you
are working blind between screenshots, so make one small stroke, look, and continue. `rightEye`
is the eye on the picture's left.

### 1. Develop

On a smart object, the developing controls stay editable:

```text
layer.smartObjects.convertToSmartObject {"layer": 78}   -> {"layer": 81}
filter.cameraRaw {"exposure": 0.3, "highlights": -20, "shadows": 15, "temperature": 5, "clarity": 6}      2.6 s at 2048 pixels
layer.smartFilter.setParams {"layer": 81, "index": 0, "params": {"clarity": 3}}       to change it later
```

Set white balance on something that should be neutral, recover highlights before lifting
shadows, and stop before the picture looks processed. A smart object's own pixels cannot be
painted ("active layer is a Smart Object layer, not a pixel layer"), which is what keeps the
original safe: the cleaning goes on a layer above it.

### 2. Clean

On an empty layer above the photograph, with the tools told to read the picture beneath, so
every fix can be erased or redone:

```text
layer.new.layer {"name": "Cleanup"}                   -> {"layer": 82}   (it is the active layer)
paint.spotHealing {"points": [[905, 520], [915, 530]], "size": 40, "sampleAllLayers": true}       a blemish: a dab a little larger than it
paint.healingBrush {"points": [[1000, 620], [1020, 630]], "source": [960, 600], "size": 40, "sampleLayer": "currentAndBelow"}     texture from the source, tone from where you paint
paint.cloneStamp {"points": [[300, 300], [340, 320]], "source": [500, 300], "size": 60, "hardness": 30, "sampleLayer": "currentAndBelow"}     an exact copy: edges, patterns, backgrounds
```

A larger object goes with a fill, which needs a pixel layer to read: on a flat copy
(`layer.duplicate {"layer": 78, "name": "Retouch"}` before the photograph becomes a smart object,
or `layer.stampVisible {}` after), select it loosely and fill onto a layer of its own:

```text
select.rect {"x": 60, "y": 60, "width": 160, "height": 160, "feather": 4}
edit.contentAwareFill {"output": "new"}             -> {"layer": 54, "filled": 32940}
select.deselect {}
```

- Heal skin; clone hard edges and repeating patterns; fill larger objects. Take the source from
  nearby, in the same light, and change it often so no patch repeats.
- Remove what is temporary: spots, dust, lint, stray hairs across the face, a crease in a
  backdrop, a sign growing out of a head. Keep what is the person.
- Size the brush just larger than the flaw. Big soft healing smears texture.

### 3. Even skin: tone and texture apart

Only when the skin needs it after cleaning, and never as a substitute for it. Split the picture
into tone and texture, so blotches can be evened without touching pores:

```text
layer.stampVisible {}                                      -> {"layer": 73}   the cleaned picture, merged, on top
layer.duplicate {"layer": 73, "name": "Low (tone)"}        -> {"layer": 74}
filter.blur.gaussianBlur {"radius": 8}                     until the pores just disappear: 4 to 10 at this size
layer.duplicate {"layer": 73, "name": "High (texture)"}    -> {"layer": 75}
layer.moveTo {"layer": 75, "target": 74, "position": "above"}
layer.select {"layer": 75}
filter.other.highPass {"radius": 8}                        the same radius as the blur
layer.setProps {"layer": 75, "blend": "Linear Light", "opacity": 0.5}
```

The two together are the picture again (sampled colors matched the original to within 2 in
255), so nothing has changed yet. Then:

- **Tone**, on Low: select a blotchy area softly and blur it a little more
  (`layer.select {"layer": 74}`, `select.rect {…, "ellipse": true, "feather": 12}`,
  `filter.blur.gaussianBlur {"radius": 10}`, `select.deselect`). Stay inside one plane of the
  face; blurring across the edge of a cheek flattens it.
- **Texture**, on High: clone good pores over bad ones with a hard brush
  (`paint.cloneStamp {…, "hardness": 80, "sampleLayer": "current"}`).
- **Limit it to skin**: keep the stamp hidden under them as the untouched state, group the two (`layer.select` both, `layer.new.groupFromLayers {"name":
  "Skin"}`), hide the group with `layer.layerMask.hideAll`, and paint white on its mask over the
  skin only (`paint.stroke {…, "color": "#ffffff", "target": "mask"}`), away from eyes, lips, brows,
  hairline, and nostrils.

The mistakes that give it away: skin with no pores, a face with no shadow under the cheekbone,
a neck that does not match. Compare at 100% with the group hidden and shown.

### 4. Shape with light: dodge and burn

The step that makes a portrait look expensive, and the safest, because it touches no pixels of
the photograph:

```text
layer.new.layer {"name": "Dodge and burn", "mode": "Soft Light", "fillNeutral": true}     -> {"layer": 44}
paint.stroke {"points": [[820, 420], [900, 400], [1000, 410]], "size": 180, "hardness": 0, "opacity": 0.15, "color": "#ffffff"}    lighten
paint.stroke {"points": [[760, 760], [780, 860]], "size": 160, "hardness": 0, "opacity": 0.15, "color": "#000000"}                 darken
```

- White lightens, black darkens, 50% gray does nothing. Low opacity (0.05 to 0.2), soft brush,
  several passes.
- Follow the light that is already there: brighten where it already falls (forehead, bridge of
  the nose, top of the cheekbones, the catchlight side of the iris), deepen where it already
  shades (under the cheekbone, the jaw line, the sides of the nose). Never invent a second
  light.
- Small brush, low opacity for evening out blotches one at a time; large brush for form.
- Keep it above the cleaning layers. To weaken it all, lower the layer's opacity.
- For a product: brighten the edge that defines its shape, darken the surface it stands on
  toward the frame's edges.

### 5. Color: correct, then grade

Correct first (the picture looks true), then grade (the picture looks like the idea). Every
step is an adjustment layer, named:

```text
layer.newAdjustmentLayer.levels {"inBlack": 8, "gamma": 1.08, "inWhite": 245, "name": "Levels"}       set the black and white points
layer.newAdjustmentLayer.curves {"points": [[0,0],[64,50],[128,128],[192,206],[255,255]], "name": "Contrast"}
layer.newAdjustmentLayer.selectiveColor {"colors": "reds", "yellow": 8, "black": -5, "name": "Skin"}  skin a touch warmer and lighter
layer.newAdjustmentLayer.vibrance {"vibrance": 20, "name": "Vibrance"}                               lifts quiet colors, protects skin
layer.newAdjustmentLayer.colorBalance {"shadows": [-5, 0, 8], "highlights": [6, 0, -6], "name": "Split tone"}     cool shadows, warm highlights
layer.newAdjustmentLayer.gradientMap {"stops": [[0, "#101830"], [1, "#ffe9c8"]], "name": "Duotone", "opacity": 0.25, "mode": "softLight"}
```

- **Skin is the reference.** Whatever the grade, skin should still read as skin: sample it
  (`document.sampleColor`) before and after; red highest, then green, then blue, and no gray or
  green cast in the shadows.
- **Local color** is a selection, then an adjustment (the selection becomes its mask):
  the background alone is `select.subject {}`, `select.inverse {}`, `select.modify.feather
  {"radius": 3}`, then `layer.newAdjustmentLayer.hueSaturation {"saturation": -60, "name": "Mute
  background"}`. A color family alone is `select.colorRange {"select": "skinTones", "fuzziness":
  30}` or `{"color": "#d06040", "fuzziness": 60}`.
- Prefer `vibrance` to `saturation`, `curves` to brightness, and a clipped adjustment
  (`"clipToPrevious": true`) when only one layer should change.
- One look, last, over everything, at reduced opacity. If the look hides a problem, fix the
  problem.

### 6. Finish

```text
gradient.fill.create {"from": [1024, 1024], "to": [1024, 2300], "style": "radial", "stops": [[0, "#000000"], [1, "#000000"]],
                      "transparency": [[0, 0], [1, 80]], "mode": "multiply"}          -> {"layer": 99}; rename it "Vignette", lower its opacity
layer.new.layer {"name": "Grain", "mode": "Overlay", "fillNeutral": true, "opacity": 0.5}
filter.noise.addNoise {"amount": 6, "distribution": "gaussian", "monochromatic": true}

layer.stampVisible {}                                  -> {"layer": 53}   a merged copy on top, to sharpen
layer.renameLayer {"layer": 53, "name": "Sharpen"}
filter.other.highPass {"radius": 3}
layer.setProps {"layer": 53, "blend": "Overlay", "opacity": 0.6}
```

- Sharpen last, at the output size, on its own layer so it can be masked off skin and turned
  down. `filter.sharpen.smartSharpen {"amount": 80, "radius": 1.2, "reduceNoise": 10}` on the
  stamp is the alternative. A picture reduced for the web wants a little more
  (`filter.sharpen.unsharpMask {"amount": 40, "radius": 0.4}`).
- The stamp is a frozen copy: if anything under it changes, delete it and stamp again.
- Grain hides the smoothness of retouching and of enlargement, and ties a composite together.
  It also makes files large: add it last.
- A vignette is felt, not seen. If you notice it, halve it.

## Cutting out

```text
layer.removeBackground {"layer": 42}                   -> {"layer": 42, "bounds": [74, 63, 1914, 1985]}   subject found, mask made
layer.layerMask.edit {"layer": 42, "feather": 1.5}     soften the mask's edge a little
layer.matting.defringe {"layer": 42, "width": 2}       remove the rim of old background color
paint.stroke {"points": [[100, 1900], [400, 1950]], "size": 200, "hardness": 0.5, "color": "#ffffff", "target": "mask"}    bring back what the mask lost
layer.layerMask.enabled {}                             toggle to compare; call again to turn it back on
```

- Judge a mask on the background it will live on, not on the checkerboard: put a
  `layer.newFillLayer.solidColor` of the destination's color under it and look at 100%.
- Hair, fur, glass, and smoke are where it fails. `select.refineEdge {"radius": 4, "smartRadius":
  true, "feather": 1, "output": "selection"}` improves soft edges; a new background close in
  tone to the old one forgives the rest. Say what is not clean.
- Edges are as sharp as the lens made them: a subject in focus has a crisp edge, the far
  shoulder a soft one. One feather value everywhere looks cut out with scissors.
- A generated subject is easier to cut when it was generated for cutting: ask
  `generate_image` for it "on a plain light gray background, evenly lit, whole figure in frame,
  nothing cropped".

## Compositing generated pictures with photographs

A composite convinces when every piece could have been in front of the same camera at the same
moment. Decide the scene first, then make or choose pieces that fit it; fixing a mismatch
afterwards is the hard way.

**Before generating**, read the photograph (or the frame) the piece must join and write down:

| Read from the plate | Ask of the generated piece |
|---|---|
| Where the main light is (left or right, high or low) | "lit from the upper left" |
| Hard or soft shadows | "soft overcast light" or "hard direct sun" |
| The light's color, and the color of the shadows | "warm low sun, cool blue shadows" |
| Camera height and angle (looking up, level, down) | "seen from eye level", "low angle" |
| Lens feel (wide and close, or long and flat) | "wide-angle, close" or "telephoto compression" |
| Depth of field and where the piece will stand | "in sharp focus" or "slightly out of focus" |

Put those words in the `generate_image` prompt, give the library references that fix identity
(`references: ["@mara"]`), and ask for the piece alone on a plain background, so it can be cut.
Generate at the aspect ratio of the space it will fill. A piece lit from the wrong side can be
flipped (`edit.transform.flipHorizontal {}` on its layer) if nothing in it reads backwards (text,
a known face's asymmetry, a watch).

**Assembling**, as run:

```text
app.open {"path": "library/hero/hero.png"}                        the piece is its own document, and active
layer.removeBackground {}                                         -> {"layer": 75, …}
layer.copyToDocument {"document": 0, "name": "Hero", "center": true}       -> {"layers": [77]}; the mask comes with it
file.close {"document": 1}
layer.moveTo {"layer": 77, "target": "Grade", "position": "below"}          under the look that unifies everything
layer.smartObjects.convertToSmartObject {"layer": 77}             -> {"layer": 80}
edit.transform {"layer": 80, "scaleX": 220, "scaleY": 220, "dx": 0, "dy": 900}

layer.newAdjustmentLayer.curves {"points": [[0,0],[128,100],[255,235]], "blue": [[0,12],[255,245]], "name": "Hero match", "clipToPrevious": true}
layer.newAdjustmentLayer.photoFilter {"color": "#e0607a", "density": 30, "name": "Hero ambient", "clipToPrevious": true}
layer.layerStyle.innerShadow {"layer": 80, "color": "#f4a259", "blend": "screen", "opacity": 35, "angle": 60, "distance": 14, "size": 40}

layer.select {"layer": 80}
layer.new.layer {"name": "Contact shadow", "mode": "Multiply", "position": "below"}      -> {"layer": 83}
paint.stroke {"points": [[2600, 8600], [4600, 8600]], "size": 500, "hardness": 0, "opacity": 0.5, "color": "#000000"}
```

**Match, in this order**, each with its own clipped adjustment so it can be tuned:

1. **Scale and perspective.** The horizon of the piece sits on the horizon of the plate; feet
   stand on the ground plane. A figure twice as far is half as tall. Wrong here, nothing else
   helps.
2. **Black and white points.** Sample the darkest dark and brightest bright of the plate and of
   the piece (`document.sampleColor`). The piece's blacks must not be blacker than the plate's:
   lift them with `curves` (`[0, 12]`). Haze lifts and cools blacks with distance.
3. **Contrast and brightness**, with the same `curves`, until the piece sits at the plate's
   level when you look at the whole image small.
4. **Color of light.** Tint the piece toward the plate's light (`photoFilter` with a color
   sampled from the plate's lit areas, density 15 to 35), and its shadows toward the plate's
   shadow color (`colorBalance` on shadows).
5. **Light wrap and rim.** Where a bright background is behind the piece, its edge takes a
   little of that light: an inner shadow in Screen with the background's color, from the side
   of the light, small. Without a bright background, skip it.
6. **Shadows.** A soft, dark contact shadow right where the piece touches the ground, on a
   Multiply layer under it; then a longer, lighter cast shadow away from the light, softer the
   farther it falls. Shadows are the plate's shadow color, not pure black.
7. **Focus and sharpness.** A piece sharper than the plate looks pasted: soften it
   (`filter.blur.gaussianBlur {"radius": 1}` on the smart object, editable) to the plate's
   sharpness at that depth.
8. **Grain and the look.** One grain layer and one grade over everything (the piece went under
   "Grade" for this reason). This is what makes separate sources one picture.

Then the test: fit to screen, look away, look back. Whatever the eye goes to that is not the
focal point is the mismatch. Zoom to 100% along the cut edge. Tell the person what still gives
it away.

**What generated pictures get wrong**, to check before you build on one: hands and teeth, text
and logos (replace them with real type and the real logo file), jewelry and glasses that do not
match on both sides, backgrounds that melt, skin that is already too smooth (add grain; do not
smooth it further), and a likeness that drifted from the reference. Say what you see.

## Enlarging

A generated picture is about two thousand pixels on its long side and a film frame is 1920 by
1080; a 24 by 36 in poster at 300 pixels an inch is 7200 by 10800. PhotoCraft resamples, which
makes a picture larger and softer, not more detailed. In order of preference:

1. **Need fewer pixels.** A poster read from across a room prints well at 150 pixels an inch
   (3600 by 5400), and a picture that fills only part of the poster needs only that part's
   pixels. Design so the picture is not the whole sheet: a band, a window, a duotone field.
2. **Generate it again for the job**, at the poster's aspect ratio (`aspect_ratio: "2:3"`),
   with the frame or the first picture as a reference, so the composition is made for the
   sheet and no pixels are wasted on cropping.
3. **Enlarge and finish.** `edit.transform` with `"interpolation": "bicubicSmoother"` on the
   smart object (the poster recipe enlarged a 1920 pixel frame 6.8 times), or on a flat picture
   `image.imageSize {"percent": 200, "resample": "preserveDetails"}` (4 s from 2048 to 4096).
   Then a grain layer, which gives the eye texture where detail is missing, and a little
   sharpening. Soft, graphic, low-detail pictures (skies, silhouettes, gradients) enlarge well;
   faces, hair, and fabric do not.

Tell the person which of these you did and how it will look at arm's length: "the sky holds up;
the face would be soft at full poster size, so I kept the portrait to the top half at 150
pixels an inch".
