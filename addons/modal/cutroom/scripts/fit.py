# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Encode a finished video again to fit a size, in two passes, keeping its master as it is.

    cutroom fit MASTER.mp4 OUT.mp4 [--mb 18.2] [--audio-kbps 160] [--preset slow]

For a place that takes files up to a limit: a page, a message, an upload
form. The master a cutter wrote is encoded for quality (a constant rate
factor), so its size follows its content; this writes a copy whose size is
chosen instead, and leaves the master for anywhere that takes it whole.

The video's bit rate is what the target leaves once the sound and the
container are paid for:

    kb/s = target megabytes x 8000 / seconds - audio kb/s - 12

and x264 spends it over two passes, the first measuring where the picture
needs it. Aim a little under the limit: 18.2 MB for a 20 MB limit landed
between 18.1 and 18.4 MB, where a target of 19.2 went over.

Prints the bit rate used and the size written. A target that leaves the
video under 150 kb/s is refused: cut the video shorter, or scale it down first.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from common import duration, tool

# The margin left for the container, in kb/s: what the settled encodes subtracted beyond their sound (140 in
# all, with 128 kb/s of sound)
OVERHEAD_KBPS = 12
LOWEST_KBPS = 150


def video_kbps(megabytes: float, seconds: float, audio_kbps: int) -> int:
    """The video bit rate, in kb/s, that fits a video of `seconds` with its sound into `megabytes`."""
    return int(
        megabytes * 8 * 1000 * 1000 / seconds / 1000 - audio_kbps - OVERHEAD_KBPS
    )


def main() -> None:
    """Run the two passes and say what came out."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument(
        "--mb", type=float, default=18.2, help="the size to aim at, in megabytes"
    )
    ap.add_argument("--audio-kbps", type=int, default=160)
    ap.add_argument("--preset", default="slow", help="x264's preset")
    a = ap.parse_args()
    rate = video_kbps(a.mb, duration(a.src), a.audio_kbps)
    if rate < LOWEST_KBPS:
        sys.exit(
            f"{a.mb:g} MB leaves the video {rate} kb/s, too little to watch. Shorten it or scale it down first."
        )
    Path(a.dst).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        log = f"{folder}/pass"
        encode = [
            tool("ffmpeg"),
            "-y",
            "-v",
            "error",
            "-i",
            a.src,
            "-c:v",
            "libx264",
            "-preset",
            a.preset,
        ]
        encode += ["-b:v", f"{rate}k", "-passlogfile", log]
        subprocess.run(
            [*encode, "-pass", "1", "-an", "-f", "null", "/dev/null"], check=True
        )
        second = [
            *encode,
            "-pass",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            f"{a.audio_kbps}k",
        ]
        subprocess.run([*second, "-movflags", "+faststart", a.dst], check=True)
    size = Path(a.dst).stat().st_size
    print(f"{a.dst} {rate}k {size} bytes ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
