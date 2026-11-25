<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Design: posters, key art, covers, thumbnails

How to decide what goes where, and how to size and export it. Commands are in
photocraft-commands.md; the ones named here were run as written.

## From brief to directions

One sentence first: **what must a stranger know in two seconds?** A film poster: this is the
kind of film it is, and its name. A thumbnail: this is what happens in the video. An ad: this is
the product and why now. Everything on the canvas serves that sentence or goes.

Offer directions that differ in idea, and name each by its idea:

| Direction | The idea | Works when |
|---|---|---|
| The face | One person, large, looking at us or away | The film is about someone; there is a strong portrait |
| The object | One thing, isolated, with room around it | A symbol carries the story; a product |
| The place | A wide scene, a small figure | Scale, loneliness, adventure, a world |
| The mark | Type or a graphic shape is the image | A strong title; no good picture; a festival or event |
| The collision | Two pictures made one (a face holding a landscape, a split) | Two worlds, two leads, a twist |

Describe each in three lines (what is biggest, the palette, what the type does) and ask the
person to pick or mix. Do not build three finished posters to choose from; build the chosen one
well.

## Composition

- **One focal point.** Decide it, then make everything else quieter: smaller, lower in
  contrast, less saturated, or softer. The most common failure is two things of equal weight.
- **Ways to make something the focal point**: size, contrast against what is behind it, the only
  warm color in a cool picture, empty space around it, and lines or a gaze that lead to it.
- **Thirds and center.** A centered subject is calm and iconic, and is right for most posters.
  Off center, put it on a third, with the empty side holding the type or the direction the
  subject looks.
- **The eye's path.** Picture, then title, then the line under it, then the details at the
  bottom. Check that nothing bright or sharp at an edge pulls the eye out of the frame.
- **Margins are part of the design.** Set them with guides before placing anything, equal on
  the sides, and hold everything to them. Type that almost touches an edge looks like a mistake;
  an image that bleeds off the edge looks chosen.
- **A portrait's eyes sit in the upper third.** Leave room above the head, never crop at a
  joint (wrists, knees), and give a profile room in the direction it faces.
- **Depth in three planes**: something near, the subject, something far. A flat picture gains
  it from a darker foreground at the bottom and haze toward the horizon.
- **Bottom weight.** A dark or quiet lower third gives type somewhere to stand. If the picture
  is busy there, fade it out with a gradient on its mask rather than boxing the type.

Guides for a poster: `view.newGuideLayout {"columns": 6, "gutter": "0.25 in", "margin": "0.75 in",
"clearExisting": true}`. Hide them for a screenshot the person will judge:
`ui.menu.invoke {"id": "view.show.guides"}` (it answers `false` when hidden; call it again to show
them).

## Hierarchy and type

Three levels, and the steps between them are large:

| Level | What | Size, relative |
|---|---|---|
| 1 | The title, or the one line of the ad | The biggest type by far |
| 2 | Tagline, names above the title, date, call to action | A quarter to a third of the title |
| 3 | Credits, small print, addresses, logos | Small, even, quiet: the same gray, one size |

- **Two typefaces at most**: one with character for level 1, one plain for everything else.
  Often one family in two weights is enough.
- **Contrast in this order**: size, then weight, then case and spacing, then color. If a level
  needs color to stand apart, the sizes are too close.
- **Capitals want air; lowercase does not.** Track all-caps titles out (`tracking` 50 to 200)
  and small caps lines further (200 to 300); never track lowercase text out. Large type needs
  tighter line spacing than small type (`leading` near the type size for a two-line title).
- **A title's shape matters more than its font.** Break a long title where the sense breaks,
  put the short word on its own line, and align the block to the picture's axis.
- **Legibility is contrast.** Light type on a dark, quiet area or dark on light. Sample what is
  behind the type (`document.sampleColor`) and, if the picture is uneven there, darken it with a
  gradient or a soft shadow (`layer.layerStyle.dropShadow` at low opacity, large size) rather
  than outlining the letters.
- **Never stretch type** (scale it evenly), never fake a bold the family does not have, and
  check the face is the one you asked for (`type.info`, `postscript_name`).
- **Numbers and dates** are level 2 and deserve care: a date reads as one unit, in the title's
  typeface or the plain one, never a third.

**A film poster's parts**, top to bottom: names of the leads above or below the title (two or
three), the title, the tagline, then the billing block and the date or "coming soon", with
laurels or quotes near the top where they do not fight the title.

**The billing block** is the tight block of credits at the bottom: a condensed sans (here
Nimbus Sans Narrow), all capitals, the job in smaller letters before each name, centered, in
one quiet color, two to four lines. On studio films its order and sizes are set by contracts
and guild agreements; a reported rule of thumb is that it is no smaller than about 15% of the
title's size. For an independent film, ask for the credit list in its order (production
companies first, the director last) and set it exactly as given. Do not invent credits.

## Sizes

**Print.** Pixels are inches times pixels an inch. 300 is the standard for anything held in the
hand; a large poster read from across a room prints well from 150 to 200, which also halves the
enlargement a generated picture needs. Ask the printer; say which you chose and why.

| Sheet | Trim | At 300 px/in | At 150 px/in |
|---|---|---|---|
| Film one-sheet | 27 by 40 in | 8100 by 12000 | 4050 by 6000 |
| Large poster | 24 by 36 in | 7200 by 10800 | 3600 by 5400 |
| Medium poster | 18 by 24 in | 5400 by 7200 | 2700 by 3600 |
| Tabloid, small poster | 11 by 17 in | 3300 by 5100 | 1650 by 2550 |
| A2 | 420 by 594 mm | 4961 by 7016 | 2480 by 3508 |
| A3 | 297 by 420 mm | 3508 by 4961 | 1754 by 2480 |
| Letter flyer | 8.5 by 11 in | 2550 by 3300 | |
| Postcard | 4 by 6 in | 1200 by 1800 | |

**Bleed and safe area.** A printed sheet is cut, and the cut wanders. Build the document larger
than the trim by the bleed on every side (0.125 in is the common figure, 3 to 5 mm in metric
shops, some poster printers ask 0.25 in), carry the background to the very edge, and keep type
and faces at least 0.25 in inside the trim. For a 24 by 36 in poster with 0.125 in bleed:
`file.new {"width": 7275, "height": 10875, "resolution": 300, …}`, then guides at the trim and the
safe line. A document made at trim size gains bleed afterwards only if its background can
simply extend: `image.canvasSize {"width": 7275, "height": 10875, "anchor": "center",
"extensionColor": "#0b0d1a"}`.

**Screens.** Make the master at the largest size needed and cut the others from it.

| Where | Pixels | Notes |
|---|---|---|
| Instagram and Facebook feed, portrait | 1080 by 1350 (4:5) | The size that travels: LinkedIn also crops taller than 4:5 |
| Square post | 1080 by 1080 | |
| Stories, Reels, TikTok, Shorts covers | 1080 by 1920 (9:16) | Keep the top and bottom sixth clear of words: the interface sits there |
| YouTube thumbnail | 1280 by 720 (16:9) | Under 2 MB. Read at 160 pixels wide: three words at most |
| YouTube banner | 2560 by 1440 | Only the middle 1546 by 423 is safe on every device |
| Pinterest pin | 1000 by 1500 (2:3) | A 2:3 poster fits as it is |
| Wide link or header image | 1200 by 630, 1600 by 900 | Check the platform's current sheet |
| Presentation or film frame | 1920 by 1080, 3840 by 2160 | |

Platforms change these; when the person names a platform, say the size you used and that its
own help page is the authority.

**A poster is 2:3; most screens are not.** 4:5 and 9:16 can be cut from a 2:3 poster by
cropping the sides or the top and bottom, if the layout kept its important parts in the
middle. 16:9 and 1:1 cannot: they are new layouts of the same parts. Say so, and rebuild them
from the master's layers (key art wider, title beside the subject instead of under it).

## Color

- **Work in RGB**, 8 bits, in the document's default profile, for every job. Convert at the end,
  in the exported copy, never in the master.
- **A palette is three things**: a dominant color, a supporting one, and an accent used once
  (the date, a rule, one word). Take them from the key art (`document.sampleColor`) so type and
  picture belong together.
- **Grade for the idea.** Warm and low in contrast is nostalgia; cool with deep blacks is
  threat; one saturated color in a gray picture is a symbol. One look over the whole image
  (`colorLookup`, `gradientMap` at low opacity, or `curves`), after the parts are matched.
- **Screens**: export in sRGB (`edit.convertToProfile {"profile": "srgb"}` in the copy), or colors
  shift in browsers and apps.
- **Print**: most online and digital printers ask for RGB with its profile embedded and
  convert themselves; an offset printer asks for CMYK in a profile they name. PhotoCraft's
  channel cannot load that profile, and its one CMYK conversion (`edit.convertToProfile
  {"profile": "coated-cmyk"}`) is to a generic coated profile: good for seeing which colors will
  dull (saturated blues, greens, and oranges), not for the file a press needs. Say this, send
  RGB, and let the printer convert or ask them for a proof.
- **Rich black.** Large black areas in print look gray if they are only black ink; that is the
  printer's conversion to make. Leave blacks as they are in RGB and mention it.

## Review before export

Do these yourself, then show the person.

1. **Small.** `ui.set {"fit": true}`, `engine_screenshot`: at this size, what is the first thing
   seen, and can the title be read? If the eye goes to two places, fix the hierarchy.
2. **Gray.** Add `layer.newAdjustmentLayer.blackWhite {"name": "Check"}` on top, look, then
   `layer.delete` it. If the title or the subject disappears in gray, the design leans on hue
   alone; raise the contrast.
3. **Edges.** `ui.set {"zoom": 1, "center": [x, y]}` on each cut-out edge, on the type, and on any
   enlarged picture. Halos, steps, and soft detail show here.
4. **Words.** Read every word aloud against the brief. Check names, dates, and the order of
   credits with the person.
5. **Margins.** Guides on: nothing important outside the safe line, nothing nearly touching it.
6. **Layers.** `layer.list {"flat": true}`: every layer named, grouped, nothing hidden that should
   be deleted, nothing visible that was a test.

## Export

Always from a flat copy, so the master stays layered and at full size:

```text
engine_exec(e, "mkdir -p <project folder>/exports <project folder>/social")

Print, RGB with bleed already in the canvas:
  app.save {"path": "exports/dusk-poster-print.tif", "tiffCompression": "lzw"}        4 s, 41 MB: profile and 300 px/in inside
  app.save {"path": "exports/dusk-poster-print.pdf"}                                   5 s, one flat page at the document's size, no profile
  app.save {"path": "exports/dusk-poster.psd"}, then app.save {"path": "dusk-poster.pcraft"}     for a designer; then back to the master

A platform size, cut from the master (here 4:5 from a 7200 by 10800 poster):
  image.duplicate {"name": "social-4x5", "mergedOnly": true}                           -> {"document": 1}, active
  image.crop {"x": 0, "y": 1500, "width": 7200, "height": 9000, "targetWidth": 1080, "targetHeight": 1350, "resolution": 72}
  edit.convertToProfile {"profile": "srgb"}
  filter.sharpen.unsharpMask {"amount": 40, "radius": 0.4, "threshold": 0}             a reduced picture wants a little sharpening
  app.save {"path": "social/dusk-instagram-4x5-1080x1350.jpg", "quality": 10}          67 KB
  file.close {}                                                                        the copy; the master is active again
```

- The 9:16 cut of the same poster was `image.crop {"x": 562, "y": 0, "width": 6075, "height":
  10800, "targetWidth": 1080, "targetHeight": 1920, "resolution": 72}`: the crop rectangle has the
  target's proportions, and `targetWidth`, `targetHeight` resample it.
- JPEG `quality` 10 for finals, 8 where size matters; PNG for flat graphics, screenshots, and
  anything with transparency; WebP here is lossless and large, so prefer JPEG for photographs.
- Name files for what they are and where they go: `dusk-poster-24x36-print.tif`,
  `dusk-instagram-4x5-1080x1350.jpg`. A new round is a new name (`-v2`), not an overwrite of
  something the person has seen.
- Check each file (photocraft-commands.md, Checking an export) and report path, pixel size, and
  file size. A printed piece: say the trim size, the bleed you built in, the pixels an inch, and
  that the file is RGB.
