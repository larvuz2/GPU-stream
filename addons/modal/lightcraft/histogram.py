#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Read a rendered picture's histogram as numbers, for an agent that cannot look at one.

    selkies-modal-histogram picture.jpg [--region x0,y0,x1,y1]

LightCraft draws a histogram but its control channel has no command that
returns one, so this reads a file LightCraft rendered (`ui.render`) or exported
and prints one JSON object: the file's size, pixel format, and embedded color
profile, and of its pixels the tonal percentiles, the share clipped at each
end, the mean of each channel, and a 16-bin histogram of luma. `--region`
narrows the pixels to a rectangle given as fractions of the picture, which is
how a patch of skin or a gray card is measured.

Neither ffmpeg nor ffprobe is handed this command's standard input, which a
shell loop reading file names from it would otherwise lose to them.

ffmpeg decodes the file, since it reads every format LightCraft exports that
matters here (JPEG, PNG, TIFF at 8 and 16 bits, WebP), and scales it to at
most 512 pixels wide first: a histogram needs no more, and a 60-megapixel
TIFF is then read in well under a second. The scaling averages, so a few
blown pixels inside a larger area are not counted as clipped; `clipped` is the
share of the picture that is, not a search for specks. Values are those of
the file's own encoding (0 to 255 in its color space), with no conversion
between color spaces.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

WIDTH = 512
# Rec. 709 luma weights, applied to the encoded values as a histogram display does
LUMA = (0.2126, 0.7152, 0.0722)


def probe(path: str) -> dict:
    """The picture's width, height, and pixel format, as ffprobe reads them.

    Raises:
        SystemExit: ffprobe could not read the file, with what it said.
    """
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,pix_fmt", "-of", "json", path],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    streams = json.loads(done.stdout or "{}").get("streams") or []
    if done.returncode != 0 or not streams:
        raise SystemExit(f"selkies-modal-histogram: cannot read {path}: {done.stderr.strip() or 'no picture in it'}")
    return streams[0]


def profile_name(path: str) -> str | None:
    """The description of the ICC profile embedded in the file, or None where it carries none.

    The profile is found by its `acsp` signature, 36 bytes into its header,
    rather than through each container's own framing, and its `desc` tag is
    read in both forms profiles use: the version 2 ASCII description and the
    version 4 multi-localized one. Only the first megabyte is searched, where
    every writer puts the profile, so a large file is not read whole.
    """
    with Path(path).open("rb") as file:
        head = file.read(1 << 20)
    at = head.find(b"acsp")
    if at < 36:
        return None
    start = at - 36
    count = int.from_bytes(head[start + 128 : start + 132], "big")
    for index in range(min(count, 64)):
        entry = start + 132 + 12 * index
        if head[entry : entry + 4] != b"desc":
            continue
        offset = start + int.from_bytes(head[entry + 4 : entry + 8], "big")
        kind = head[offset : offset + 4]
        if kind == b"desc":
            length = int.from_bytes(head[offset + 8 : offset + 12], "big")
            return head[offset + 12 : offset + 12 + length].split(b"\0", 1)[0].decode("ascii", "replace")
        if kind == b"mluc":
            length = int.from_bytes(head[offset + 20 : offset + 24], "big")
            text = offset + int.from_bytes(head[offset + 24 : offset + 28], "big")
            return head[text : text + length].decode("utf-16-be", "replace")
    return None


def pixels(path: str, region: tuple[float, float, float, float] | None) -> bytes:
    """The picture, or `region` of it, as 8-bit RGB triples at most `WIDTH` wide.

    Raises:
        SystemExit: ffmpeg could not decode the file, with what it said.
    """
    filters = []
    if region:
        x0, y0, x1, y1 = region
        filters.append(f"crop=iw*{x1 - x0}:ih*{y1 - y0}:iw*{x0}:ih*{y0}")
    # The comma is escaped for ffmpeg, which otherwise reads it as the end of the filter
    filters.append(f"scale=min({WIDTH}\\,iw):-2:flags=area")
    done = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-frames:v", "1", "-vf", ",".join(filters), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if done.returncode != 0 or not done.stdout:
        raise SystemExit(f"selkies-modal-histogram: cannot decode {path}: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def measure(rgb: bytes) -> dict:
    """The tonal statistics of RGB triples: percentiles, clipping, channel means, and a 16-bin histogram.

    `clipped` counts a pixel as black where every channel is at most 2 and as
    white where every channel is at least 253, and `channelClipped` where any
    one channel is, which is what blows a saturated color (a red dress, a
    blue sky) before the picture as a whole clips.
    """
    red, green, blue = rgb[0::3], rgb[1::3], rgb[2::3]
    count = len(red)
    luma = [round(LUMA[0] * r + LUMA[1] * g + LUMA[2] * b) for r, g, b in zip(red, green, blue, strict=True)]
    ordered = sorted(luma)
    bins = [0] * 16
    for value in luma:
        bins[min(value // 16, 15)] += 1
    black = sum(1 for r, g, b in zip(red, green, blue, strict=True) if max(r, g, b) <= 2)
    white = sum(1 for r, g, b in zip(red, green, blue, strict=True) if min(r, g, b) >= 253)
    any_low = sum(1 for r, g, b in zip(red, green, blue, strict=True) if min(r, g, b) <= 2)
    any_high = sum(1 for r, g, b in zip(red, green, blue, strict=True) if max(r, g, b) >= 253)
    return {
        "luma": {f"p{p}": ordered[min(count - 1, count * p // 100)] for p in (1, 5, 25, 50, 75, 95, 99)},
        "mean": {"luma": round(sum(luma) / count, 1), "r": round(sum(red) / count, 1), "g": round(sum(green) / count, 1), "b": round(sum(blue) / count, 1)},
        "clipped": {"black": round(black / count, 4), "white": round(white / count, 4)},
        "channelClipped": {"low": round(any_low / count, 4), "high": round(any_high / count, 4)},
        "histogram": [round(value / count, 3) for value in bins],
    }


def region_of(text: str) -> tuple[float, float, float, float]:
    """A `--region` value as four fractions, left, top, right, bottom.

    Raises:
        argparse.ArgumentTypeError: The value is not four numbers describing a rectangle inside the picture.
    """
    try:
        x0, y0, x1, y1 = (float(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("a region is x0,y0,x1,y1") from None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise argparse.ArgumentTypeError("a region is x0,y0,x1,y1 as fractions of the picture, 0 to 1")
    return x0, y0, x1, y1


def main() -> int:
    """Print the statistics of the picture named on the command line."""
    parser = argparse.ArgumentParser(description="Print a picture's histogram, clipping, and color profile as JSON.")
    parser.add_argument("picture", help="a JPEG, PNG, TIFF, or WebP file")
    parser.add_argument("--region", type=region_of, metavar="x0,y0,x1,y1", help="measure this rectangle only, as fractions of the picture")
    args = parser.parse_args()
    stream = probe(args.picture)
    result = {
        "path": args.picture,
        "width": stream["width"],
        "height": stream["height"],
        "pixelFormat": stream.get("pix_fmt"),
        "profile": profile_name(args.picture),
        "bytes": Path(args.picture).stat().st_size,
        "region": args.region,
        **measure(pixels(args.picture, args.region)),
    }
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
