<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Delivery and hand-offs

Every recipe here was exported on a Moody engine and the file checked for its size, depth, and
embedded profile. Options and their values are in
[lightcraft-commands.md](lightcraft-commands.md#export).

## Before any export

- Export from approved settings only. An export is cheap to redo, but a delivered file is not
  recalled.
- Keep exports in `<project folder>/exports/<purpose>/` (`web`, `social`, `print`, `master`). The
  originals and the library are never an export target.
- Pass `format`, a size, `colorSpace`, and `conflict` in every call. Use `"conflict": "overwrite"`
  when you are replacing your own earlier export of the same version, `"unique"` otherwise.
- Check every export before you report it:
  `engine_exec(id, "selkies-modal-histogram <file>")` and read `width`, `height`, `profile`,
  `pixelFormat`, `bytes`. Compare `mean` with the render the person approved; they should match
  within a few levels.

## The screen

| For | Recipe |
|---|---|
| A web page, a portfolio, email | `format: "jpeg"`, `longEdge: 2048` (2560 for a full-bleed hero), `quality: 85` to `88`, `colorSpace: "srgb"`, `sharpen: "screen"`, `metadata: "copyright"` |
| A page with a size budget | Add `limitKb` (300 to 500). LightCraft lowers quality to fit; check the result still holds up |
| A site that serves modern formats | `format: "webp"` or `"avif"` at `quality` 80, same size and color space. Keep a JPEG as the fallback |
| A client proofing gallery | `longEdge: 1600`, `quality: 80`, with `naming: "{name}"` so their picks map back to files |
| Full-resolution delivery for screens | `format: "jpeg"`, `longEdge: 0`, `quality: 92` to `95`, `colorSpace: "srgb"` |

sRGB is the color space for anything seen in a browser or sent to someone whose software you do
not know: a file in a wider space looks dull wherever color management is missing. Use
`displayP3` only when the person asks for it and knows where it will be shown.

## Social

Crop to the platform's ratio first (`crop.set`, with the ratio math from the commands reference),
show the crop, then export at the exact size with `fit: "widthHeight"`:

| Placement | Ratio | Pixels |
|---|---|---|
| Instagram feed, portrait (the most screen a post gets) | 4:5 | 1080 x 1350 |
| Instagram feed, square | 1:1 | 1080 x 1080 |
| Instagram feed, landscape | 1.91:1 | 1080 x 566 |
| Instagram or TikTok story, reel cover | 9:16 | 1080 x 1920 |

```text
crop.set {"rect": [0.1, 0.0, 0.6333, 1.0]}
app.export {"ids": [9], "dir": "<project>/exports/social", "format": "jpeg", "width": 1080, "height": 1350,
            "fit": "widthHeight", "quality": 85, "colorSpace": "srgb", "sharpen": "screen",
            "metadata": "copyright", "naming": "{name}-ig", "conflict": "overwrite"}
   -> 1080 x 1350, sRGB, 127 kB
```

Platforms change their sizes: say which size you used, and ask when the person names a platform
this table lacks. A crop for social is a version of its own: `photo.virtualCopy` first, so the
full frame keeps its crop. Platforms recompress, so there is no point above quality 85, and
`sharpen: "screen"` counters the softening of the downsize. Keep faces and text away from the top
and bottom sixth of a 9:16 frame, where the interface sits.

## Print

Ask the lab or printer what it wants before you export. Without an answer:

| For | Recipe |
|---|---|
| A photo lab, an online print service | `format: "jpeg"`, `quality: 95`, `colorSpace: "srgb"`, full size or sized to the print, `ppi: 300`, `sharpen: "glossy"` or `"matte"` for the paper |
| A fine-art printer, a retoucher, an archive master | `format: "tiff"`, `bitDepth: 16`, `colorSpace: "adobeRgb"` (or `"proPhoto"` on request), `tiffCompression: "zip"`, `longEdge: 0`, `ppi: 300` |
| A magazine or agency that sent a specification | Exactly what the specification says |

- **Size.** Pixels = inches x ppi. 300 ppi is the standard for a print held in the hand: an 8 x 10
  inch print needs 2400 x 3000, A4 needs 2480 x 3508, A3 3508 x 4961. A large print seen from a
  distance holds at 150 to 200 ppi. Say so when a file is too small for the size asked, rather
  than enlarging silently (`dontEnlarge` is on unless you turn it off).
- **`ppi` only labels the file.** It does not resize. Set the pixel size with `width` and `height`
  and the label with `ppi`.
- **Ratio.** Paper sizes are not the camera's 3:2. Crop to the print's ratio and show it; do not
  let the lab crop.
- **Color space.** A wide space sent to a lab that ignores profiles prints flat. sRGB unless the
  lab says otherwise.
- **Prints come out darker than a screen.** If the person will not see a proof, offer a version
  lifted by +0.15 to +0.3 stops and say why.
- A 16-bit TIFF of a 45-megapixel photo is 140 to 170 MB. Say so before you make twenty.

## Masters and archives

- `format: "original"` copies the photo with an `.xmp` holding its edits beside it: the hand-over
  for someone who develops in other software.
- `format: "dng"` writes a raw as a DNG with the edits embedded.
- `preset.export` saves the project's looks as a `.lcpreset` file in the project folder.
- The library itself is the working archive: it stays in the project folder with every edit,
  version, and rating.

## Hand-offs

Work moves between engines as files in the project folder, in `handoff/<from>-to-<to>/`, named for
what it is and its version (`portrait-headwrap-v1.tif`). The studio skill holds the convention.
Two facts measured on Moody's engines decide the order of every hand-off:

- **A running engine does not see a file another engine wrote after it started.** Three engines
  running together did not see each other's new files in 90 seconds.
- **An engine that starts afterwards sees it**, including files written seconds before.

So: export, confirm with `engine_files` on the LightCraft engine, then **start the receiving
engine** (or stop and start it if it was running), and confirm with `engine_files` there before it
opens the file. The same holds for LightCraft as the receiver. Stopping LightCraft loses nothing:
every edit is already in the library.

### To PhotoCraft: retouching and compositing

PhotoCraft does what a developer cannot: skin and blemish retouching, liquify, cut-outs,
composites, type, layers.

```text
app.export {"ids": [9], "path": "<project>/handoff/lightcraft-to-photocraft/portrait-headwrap-v1.tif",
            "format": "tiff", "bitDepth": 16, "colorSpace": "adobeRgb", "tiffCompression": "zip",
            "longEdge": 0, "sharpen": "none"}
   -> 8256 x 5504, 139 MB, 7 s
```

| | |
|---|---|
| Format | TIFF, flat, ZIP-compressed. A PSD (`"format": "psd"`) carries the same picture and is twice the size |
| Depth | 16 bits, so retouching has room to push tones without banding |
| Color space | Adobe RGB, embedded. PhotoCraft 0.23.1 opened it as 16-bit RGB at full size and read the profile as embedded ("Adobe RGB (1998) compatible") |
| Size | Full, uncropped unless the crop is final |
| Sharpening | None at export, and keep `detail.sharpenAmount` moderate: retouching wants an unsharpened file, and output sharpening is the last step of the last engine |
| Finish first | White balance, exposure, tone, and color. Leave heavy local work, grain, and vignette for after the retouch, or do them in PhotoCraft |

The retouched file comes back in `handoff/photocraft-to-lightcraft/`. Bring it into the library
and it is a photo like any other, for the final grade, crop, and export:

```text
library.import {"paths": ["<project>/handoff/photocraft-to-lightcraft/portrait-headwrap-retouch-v1.tif"], "mode": "add", "albumName": "Retouched"}
```

A file that came back retouched is already developed: start its settings from zero and add only
the finish (grade, grain, vignette, crop). Do not paste the original's tone settings onto it.

### To FilmCraft: a still, or a look reference

```text
app.export {"ids": [8], "path": "<project>/handoff/lightcraft-to-filmcraft/landscape-peyto-still-v1.png",
            "format": "png", "bitDepth": 8, "colorSpace": "srgb", "longEdge": 3840}
   -> 3840 x 3072, 17 MB, 0.8 s
```

| | |
|---|---|
| Format | PNG for a still that will be cut into the film; JPEG at quality 95 for a reference that is only looked at |
| Depth | 8 bits |
| Color space | sRGB, which a Rec. 709 sequence shows as it is |
| Size | Long edge 3840 for a UHD sequence, 1920 for HD. For a still that fills the frame, crop to the sequence's ratio first (16:9, or 9:16 for vertical) and export at the sequence's size with `width` and `height` |

On the FilmCraft engine, `file.import` with the file's path brought the PNG in as a Still Image of
five seconds, and a frame exported from the sequence was identical to the file, pixel for pixel.
Movement over a still (a slow push or pan) is made in FilmCraft; export larger than the sequence
(long edge 5760 for UHD) when it will be scaled.

A **look reference** is a developed still of the look the film should match, with a line saying
what makes it: where the shadows and highlights are tinted, how much contrast, how saturated.
LightCraft cannot write a LUT, so the look travels as a picture and as numbers, and the colorist's
match is made in FilmCraft. Read the numbers from `develop.get` (`grading`, `curve`, `color`).

### From FilmCraft and PhotoCraft

- A frame or a retouched file: `library.import` it, as above.
- A look as a `.cube` LUT: `profile.import`, then `develop.profile` with the id it answers. The
  look is then a profile with an `amount` from 0 to 200, under all the usual controls.
