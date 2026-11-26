# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Join several recordings into one source, and say where each begins in it.

    cutroom join FIRST.mov SECOND.mov [MORE...] --out footage/both.mp4

The cutters take one source and segments of it in its own seconds, so
footage that arrives as several files is joined first, in the order given.
Each clip is brought to 30 frames a second and the first clip's size (fitted
inside it and padded, never stretched) and its sound to 48 kHz stereo, a
clip without sound getting silence; the joined file is near-lossless x264.

Prints each clip's offset: the second it starts at in the joined file. A
time read off the second clip's own contact sheet is that offset later in
the joined source, which is the number a segment takes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import ffprobe, run, tool, video_stream


def offsets(lengths: list[float]) -> list[float]:
    """Where each clip starts in the joined file, given each clip's length."""
    out, at = [], 0.0
    for length in lengths:
        out.append(round(at, 3))
        at += length
    return out


def graph(count: int, width: int, height: int, silent: list[bool]) -> str:
    """The filter graph that brings `count` inputs to one form and joins them into `[v]` and `[a]`.

    Inputs `count` and above are the silences made for the clips `silent`
    marks, in order.
    """
    chains, pads, extra = [], "", count
    for index in range(count):
        fit = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        chains.append(f"[{index}:v]fps=30,{fit},setsar=1,format=yuv420p[v{index}]")
        sound = f"{index}:a"
        if silent[index]:
            sound = f"{extra}:a"
            extra += 1
        chains.append(
            f"[{sound}]aresample=48000,aformat=channel_layouts=stereo[a{index}]"
        )
        pads += f"[v{index}][a{index}]"
    return ";".join(chains) + f";{pads}concat=n={count}:v=1:a=1[v][a]"


def main() -> None:
    """Join the clips and print their offsets."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if len(a.clips) < 2:
        sys.exit("join takes two clips or more")
    probes = [ffprobe(clip) for clip in a.clips]
    lengths = [float(probe["format"]["duration"]) for probe in probes]
    silent = [
        not any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
        for probe in probes
    ]
    first = video_stream(a.clips[0])
    if first is None:
        sys.exit(f"{a.clips[0]} has no picture")
    width, height = int(first["width"]) // 2 * 2, int(first["height"]) // 2 * 2
    inputs = [part for clip in a.clips for part in ("-i", clip)]
    for length, quiet in zip(lengths, silent):
        if quiet:
            inputs += [
                "-f",
                "lavfi",
                "-t",
                f"{length:.3f}",
                "-i",
                "anullsrc=r=48000:cl=stereo",
            ]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    cmd = [tool("ffmpeg"), "-y", "-v", "error", *inputs]
    cmd += [
        "-filter_complex",
        graph(len(a.clips), width, height, silent),
        "-map",
        "[v]",
        "-map",
        "[a]",
    ]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "14",
        "-c:a",
        "aac",
        "-b:a",
        "256k",
    ]
    run([*cmd, a.out])
    starts = offsets(lengths)
    found = [
        {"clip": clip, "offset": start, "seconds": round(length, 3)}
        for clip, start, length in zip(a.clips, starts, lengths)
    ]
    print(
        json.dumps(
            {"out": a.out, "size": f"{width}x{height}", "clips": found}, indent=1
        )
    )


if __name__ == "__main__":
    main()
