# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# This file incorporates work covered by the following copyright and
# permission notice:
#
#   MIT License
#
#   Copyright (c) 2026 Bodila51
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in all
#   copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#   SOFTWARE.
"""Open a finished horizontal video with a reveal: word-mark signs pop in on the voice, then punch out.

    cutroom reveal in.mp4 out.mp4 --sign first.png@1.9 [--sign second.png@2.75] --end 3.7
        [--chime auto|FILE|none] [--chime-gain 0.6]

A show's signature opening. Each sign is a picture with transparency (a
word mark, a logo; `key.py` cuts one out of a flat background) and the
second it appears at, which is the second the voice says its word
(`words.py` reads that off the narration). Until `--end` the video behind is
dimmed and blurred; then the signs punch out and the video is as it was.

One sign sits in the middle. Two are stacked, the first above and the
second, wider, below, each tilted a little the other way as it lands.

A sign pops in over 0.28 s, from 55% of its size through an overshoot of
108% to 100%, and in the last 0.25 s before `--end` every sign grows by 35%
as it fades. The frames are drawn with Pillow, thirty a second, and laid
over the video by FFmpeg, which leaves the video untouched after `--end`.

A chime starts with the last sign. `auto` is the three-second reveal chime
`chime.py` makes, the same sound every time; a file is used as it is; `none`
leaves the sound alone, and the sound is then copied without encoding again.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import tempfile

from PIL import Image

W, H, FPS = 1920, 1080, 30
POP_SECONDS = 0.28
OUT_SECONDS = 0.25
# Where each sign sits, by how many there are: (center y, width, the tilt it lands from, in degrees)
LAYOUTS = {
    1: ((540, 1060, -2.5),),
    2: ((300, 880, -2.5), (780, 1060, 2.0)),
}

Sign = tuple[Image.Image, float, int, int, float]


def pop(t: float) -> float:
    """A sign's scale `t` seconds after it appears: 0.55, an overshoot to 1.08, then 1.0, eased back out."""
    if t <= 0:
        return 0
    if t >= POP_SECONDS:
        return 1.0
    x = t / POP_SECONDS
    c = 2.2
    return 0.55 + 0.45 * (1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2)


def parse_sign(value: str) -> tuple[str, float]:
    """A `--sign` argument, `FILE@SECOND`, as the file and the second."""
    path, separator, at = value.rpartition("@")
    try:
        return path, float(at) if separator and path else float("nan")
    except ValueError:
        return value, float("nan")


def frame(t: float, end: float, signs: list[Sign]) -> Image.Image:
    """The overlay at second `t`: every sign that has appeared, at its scale, tilt, and opacity."""
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    leaving = (
        0.0
        if t < end - OUT_SECONDS
        else min(1.0, (t - (end - OUT_SECONDS)) / OUT_SECONDS)
    )
    for art, t0, cy, width, lands_from in signs:
        scale = pop(t - t0)
        if scale <= 0:
            continue
        scale *= 1 + 0.35 * leaving
        alpha = 1 - leaving
        w = max(2, int(width * scale))
        h = max(2, int(art.height * w / art.width))
        sign = art.resize((w, h), Image.LANCZOS)
        if alpha < 1:
            sign.putalpha(sign.getchannel("A").point(lambda v, a=alpha: int(v * a)))
        tilt = lands_from * (1 - min(1, (t - t0) / POP_SECONDS))
        if abs(tilt) > 0.05:
            sign = sign.rotate(tilt, resample=Image.BICUBIC, expand=True)
        image.alpha_composite(sign, (W // 2 - sign.width // 2, cy - sign.height // 2))
    return image


def main() -> None:
    """Draw the overlay's frames and lay them, and the chime, over the video."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument(
        "--sign",
        action="append",
        required=True,
        metavar="FILE@SECOND",
        help="one or two",
    )
    ap.add_argument(
        "--end", type=float, required=True, help="the second the signs are gone by"
    )
    ap.add_argument("--chime", default="auto", help="auto, a sound file, or none")
    ap.add_argument("--chime-gain", type=float, default=0.6)
    a = ap.parse_args()
    if len(a.sign) not in LAYOUTS:
        sys.exit("reveal takes one or two signs")
    signs: list[Sign] = []
    for value, (cy, width, lands_from) in zip(a.sign, LAYOUTS[len(a.sign)]):
        path, at = parse_sign(value)
        if math.isnan(at):
            sys.exit(f"--sign {value!r} is not FILE@SECOND")
        signs.append((Image.open(path).convert("RGBA"), at, cy, width, lands_from))
    with tempfile.TemporaryDirectory() as folder:
        for index in range(int(math.ceil(a.end * FPS))):
            frame(index / FPS, a.end, signs).save(f"{folder}/f{index:04d}.png")
        until = a.end - 0.15
        dim = f"eq=brightness=-0.22:saturation=0.75:enable='lt(t,{until})'"
        graph = (
            f"[0:v]{dim},boxblur=6:1:enable='lt(t,{until})'[bg];"
            f"[1:v]format=rgba,setpts=PTS-STARTPTS[ov];[bg][ov]overlay=0:0:eof_action=pass:format=auto[v]"
        )
        inputs = ["-i", a.src, "-framerate", str(FPS), "-i", f"{folder}/f%04d.png"]
        sound = ["-map", "0:a", "-c:a", "copy"]
        if a.chime != "none":
            chime = a.chime
            if chime == "auto":
                from chime import write

                chime = write(f"{folder}/chime.wav")
            inputs += ["-i", chime]
            delay = int(signs[-1][1] * 1000)
            graph += (
                f";[2:a]volume={a.chime_gain},adelay={delay}|{delay}[c];"
                f"[0:a][c]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]"
            )
            sound = ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            *inputs,
            "-filter_complex",
            graph,
            "-map",
            "[v]",
        ]
        cmd += [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "19",
            "-pix_fmt",
            "yuv420p",
        ]
        subprocess.run([*cmd, *sound, "-movflags", "+faststart", a.dst], check=True)
    print(a.dst)


if __name__ == "__main__":
    main()
