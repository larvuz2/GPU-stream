# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Cut a picture out of its flat background: a sign made on green or magenta becomes one with transparency.

    cutroom key IN.png OUT.png [--color auto|green|magenta] [--low 40] [--high 120]

Art for an overlay (a word mark, a logo, a badge) is generated on a flat,
pure background with no shadow, and the background is keyed out here, which
needs no model. Green (#00FF00) for most art; magenta (#FF00FF) when the art
itself is green, such as leaves. `auto` reads the picture's corners.

The key is how much a pixel is the background's color and nothing else: for
green, its green above the larger of its red and blue; for magenta, the
smaller of its red and blue above its green. A pixel is opaque below `--low`
of that, transparent above `--high`, and partly so between, which keeps the
edge soft. The same amount is then taken out of the edge pixels' color
(despill), so no fringe of the background is left on the art.

The result is cropped to what is left and written as PNG; its size is
printed. Look at it over a dark and a light color before using it
(`preview` with `look`): a background that was not flat leaves a haze.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
from PIL import Image


def background(pixels: np.ndarray) -> str:
    """Which key color a picture's corners are, `green` or `magenta`; the script's caller is told where neither.

    Raises:
        ValueError: The corners are neither green nor magenta.
    """
    size = max(2, min(pixels.shape[0], pixels.shape[1]) // 50)
    corners = np.concatenate(
        [
            pixels[:size, :size].reshape(-1, 3),
            pixels[:size, -size:].reshape(-1, 3),
            pixels[-size:, :size].reshape(-1, 3),
            pixels[-size:, -size:].reshape(-1, 3),
        ]
    )
    r, g, b = np.median(corners, axis=0)
    if g - max(r, b) > 80:
        return "green"
    if min(r, b) - g > 80:
        return "magenta"
    raise ValueError(
        f"the corners are rgb({r:.0f}, {g:.0f}, {b:.0f}), neither green nor magenta"
    )


def key(
    pixels: np.ndarray, color: str, low: float = 40.0, high: float = 120.0
) -> np.ndarray:
    """An RGB picture as RGBA with the key color made transparent and taken out of the edges.

    `pixels` is height by width by 3, 0 to 255. The answer has the same
    height and width, as 8-bit values.
    """
    rgb = pixels.astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    if color == "green":
        amount = g - np.maximum(r, b)
        g = np.where(amount > 0, np.minimum(g, np.maximum(r, b)), g)
    else:
        amount = np.minimum(r, b) - g
        least = np.minimum(r, b)
        r = np.where(amount > 0, np.minimum(r, g + np.maximum(0, r - least)), r)
        b = np.where(amount > 0, np.minimum(b, g + np.maximum(0, b - least)), b)
    alpha = np.clip(1 - (amount - low) / (high - low), 0, 1)
    return np.dstack([r, g, b, alpha * 255]).astype(np.uint8)


def main() -> None:
    """Key the picture, crop it, and write it."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--color", choices=["auto", "green", "magenta"], default="auto")
    ap.add_argument(
        "--low",
        type=float,
        default=40.0,
        help="below this much of the key color a pixel is opaque",
    )
    ap.add_argument(
        "--high",
        type=float,
        default=120.0,
        help="above this much a pixel is transparent",
    )
    a = ap.parse_args()
    pixels = np.asarray(Image.open(a.src).convert("RGB"))
    color = a.color
    if color == "auto":
        try:
            color = background(pixels)
        except ValueError as error:
            sys.exit(
                f"{error}. Pass --color, or make the art again on a flat #00FF00 or #FF00FF background."
            )
    image = Image.fromarray(key(pixels, color, a.low, a.high), "RGBA")
    box = image.getbbox()
    if box is None:
        sys.exit("nothing is left: the whole picture is the key color")
    image = image.crop(box)
    image.save(a.dst)
    print(f"{a.dst} {image.width}x{image.height} keyed from {color}")


if __name__ == "__main__":
    main()
