# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Map a piece of footage before cutting it: contact sheets to look at, its scene cuts, its black, and its level.

    cutroom sheet VIDEO [--out sheets/NAME] [--every 1] [--start S --end E] [--tile 8x8] [--width 320]
    cutroom sheet VIDEO --at 2.3,3.3,4.85,5.25 [--out sheets/NAME] [--width 480]

An agent cannot watch a video, so this turns one into what it can read.

- **Contact sheets.** One frame every `--every` seconds, each with its time
  in the source burned into its corner, tiled into pictures of `--tile`
  frames (`sheet_01.jpg`, ...). One frame a second maps a whole video; half a
  second between `--start` and `--end` reads one stretch closely.
- **Check frames.** `--at` takes the frames at chosen seconds instead, each
  labeled, on one picture (`frames.jpg`): the way to look at a title's
  timing or a finished cut's first frame.
- **Scene cuts.** The seconds at which the picture changes by more than
  `--scene` (0.3), as FFmpeg's scene score measures it. A cut made on one of
  these is never in the middle of a shot.
- **Black.** Stretches of black longer than 0.2 s: fades to skip.
- **Level.** The sound's mean and peak volume and its integrated loudness.
  A recording with no voice reads low and flat, and a speech model invents
  words on silence, so the level is read before a transcript is believed.

Everything measured is printed as one JSON object and kept as
`footage.json` beside the sheets. The sheets are for `preview` with `look`,
which hands their pictures to the agent.

The filters are the ones the workflow this engine comes from ran by hand:
`fps`, `scale`, `drawtext`, and `tile` for a sheet, `select='gt(scene,0.3)'`
with `showinfo` for the cuts.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from check import integrated_lufs
from common import duration, save_json, tool

LABEL = "fontsize={size}:fontcolor=yellow:box=1:boxcolor=black"


def parse_tile(value: str) -> tuple[int, int]:
    """A `--tile` argument, `COLUMNSxROWS`."""
    try:
        columns, rows = (int(x) for x in value.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not COLUMNSxROWS") from None
    if columns < 1 or rows < 1:
        raise argparse.ArgumentTypeError(f"{value!r} has no frames")
    return columns, rows


def time_label(start: float, every: float) -> str:
    """The `drawtext` text that shows a frame's second in the source, with a tenth where frames are closer than 1 s.

    Frames are numbered from zero after the seek, so the source's second is
    the frame's own time plus `start`. `drawtext` formats integers only, so a
    tenth is a second integer after a point.
    """
    at = f"t+{start:g}"
    whole = f"%{{eif\\:trunc({at})\\:d}}"
    if every >= 1 and float(start).is_integer():
        return whole
    return f"{whole}.%{{eif\\:mod(trunc(({at})*10)\\,10)\\:d}}"


def sheet_count(seconds: float, every: float, columns: int, rows: int) -> int:
    """How many sheets a stretch of `seconds` fills at one frame every `every` seconds."""
    frames = max(1, math.ceil(seconds / every))
    return math.ceil(frames / (columns * rows))


def scene_times(log: str) -> list[float]:
    """The seconds `showinfo` printed for the frames a scene filter let through."""
    return [round(float(t), 3) for t in re.findall(r"pts_time:\s*(\d+(?:\.\d+)?)", log)]


def black_spans(log: str) -> list[tuple[float, float]]:
    """The (start, end) of each stretch `blackdetect` reported."""
    found = re.findall(
        r"black_start:\s*(\d+(?:\.\d+)?)\s+black_end:\s*(\d+(?:\.\d+)?)", log
    )
    return [(round(float(a), 2), round(float(b), 2)) for a, b in found]


def volume(log: str) -> dict[str, float]:
    """The mean and peak volume `volumedetect` printed, in decibels."""
    out = {}
    for key in ("mean_volume", "max_volume"):
        found = re.search(rf"{key}:\s*(-?\d+(?:\.\d+)?) dB", log)
        if found:
            out[key.replace("_volume", "_db")] = float(found.group(1))
    return out


def ffmpeg_log(arguments: list[str]) -> str:
    """What FFmpeg prints while running a pass that writes nothing; the script ends where FFmpeg fails."""
    cmd = [tool("ffmpeg"), "-hide_banner", "-nostats", *arguments, "-f", "null", "-"]
    done = subprocess.run(
        cmd, capture_output=True, text=True, errors="replace", check=False
    )
    if done.returncode != 0:
        sys.exit(f"ffmpeg failed: {done.stderr.strip()[-800:]}")
    return done.stderr


def window(start: float, end: float | None) -> list[str]:
    """The input options that read a source between two of its seconds."""
    return ["-ss", f"{start:.3f}", *(["-to", f"{end:.3f}"] if end is not None else [])]


def contact_sheets(
    video: str,
    out: Path,
    start: float,
    end: float,
    every: float,
    tile: tuple[int, int],
    width: int,
) -> list[str]:
    """Write the contact sheets of a stretch and return their paths."""
    columns, rows = tile
    for old in out.glob("sheet_*.jpg"):
        old.unlink()
    label = f"drawtext=text='{time_label(start, every)}':{LABEL.format(size=max(14, width // 11))}"
    chain = f"fps=1/{every:g},scale={width}:-2,{label},tile={columns}x{rows}"
    cmd = [tool("ffmpeg"), "-y", "-v", "error", *window(start, end), "-i", video]
    done = subprocess.run(
        [*cmd, "-vf", chain, "-q:v", "3", str(out / "sheet_%02d.jpg")],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        sys.exit(f"ffmpeg failed: {done.stderr.strip()[-800:]}")
    return sorted(str(path) for path in out.glob("sheet_*.jpg"))


def stack_layout(count: int, columns: int) -> str:
    """The `xstack` layout that sets `count` frames of one size in rows of `columns`, left to right."""
    cells = []
    for index in range(count):
        x = "+".join(["w0"] * (index % columns)) or "0"
        y = "+".join(["h0"] * (index // columns)) or "0"
        cells.append(f"{x}_{y}")
    return "|".join(cells)


def check_frames(video: str, out: Path, seconds: list[float], width: int) -> str:
    """Write one picture of the frames at chosen seconds, each labeled with its second, in rows of four."""
    inputs: list[str] = []
    chains = []
    for index, at in enumerate(seconds):
        inputs += ["-ss", f"{at:.3f}", "-i", video]
        label = f"drawtext=text='{at:g}':{LABEL.format(size=max(14, width // 17))}"
        chains.append(f"[{index}:v]trim=end_frame=1,scale={width}:-2,{label}[f{index}]")
    columns = min(4, len(seconds))
    rows = math.ceil(len(seconds) / columns)
    pads = "".join(f"[f{index}]" for index in range(len(seconds)))
    grid = "[f0]null[v]"
    if len(seconds) > 1:
        grid = f"{pads}xstack=inputs={len(seconds)}:layout={stack_layout(len(seconds), columns)}:fill=black[v]"
    target = out / "frames.jpg"
    cmd = [
        tool("ffmpeg"),
        "-y",
        "-v",
        "error",
        *inputs,
        "-filter_complex",
        ";".join([*chains, grid]),
    ]
    done = subprocess.run(
        [*cmd, "-map", "[v]", "-frames:v", "1", "-q:v", "3", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        sys.exit(f"ffmpeg failed: {done.stderr.strip()[-800:]}")
    return f"{target} ({columns}x{rows})"


def main() -> None:
    """Write the sheets or the check frames, measure the footage, and print what was found."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument(
        "--out",
        default="",
        help="the folder to write into (default sheets/<the video's name>)",
    )
    ap.add_argument(
        "--every",
        type=float,
        default=1.0,
        help="seconds between frames (0.5 for a close look)",
    )
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument(
        "--tile",
        type=parse_tile,
        default=(8, 8),
        help="COLUMNSxROWS frames on one sheet",
    )
    ap.add_argument(
        "--width",
        type=int,
        default=0,
        help="a frame's width (default 320, or 480 with --at)",
    )
    ap.add_argument(
        "--scene",
        type=float,
        default=0.3,
        help="how much the picture changes at a scene cut",
    )
    ap.add_argument(
        "--at", default="", help="seconds to take check frames at, such as 2.3,3.3,4.85"
    )
    a = ap.parse_args()
    if a.every <= 0:
        sys.exit("--every has to be above zero")
    out = Path(a.out or f"sheets/{Path(a.video).stem}")
    out.mkdir(parents=True, exist_ok=True)
    if a.at:
        seconds = [float(x) for x in a.at.split(",") if x.strip()]
        print(check_frames(a.video, out, seconds, a.width or 480))
        return
    length = duration(a.video)
    end = min(a.end, length) if a.end is not None else length
    found: dict[str, Any] = {
        "video": a.video,
        "duration": round(length, 2),
        "start": a.start,
        "end": round(end, 2),
    }
    found["sheets"] = contact_sheets(
        a.video, out, a.start, end, a.every, a.tile, a.width or 320
    )
    found["every"] = a.every
    span = window(a.start, a.end)
    picture = ffmpeg_log(
        [*span, "-i", a.video, "-an", "-vf", f"select='gt(scene,{a.scene:g})',showinfo"]
    )
    found["scene_cuts"] = [round(t + a.start, 3) for t in scene_times(picture)]
    black = ffmpeg_log(
        [*span, "-i", a.video, "-an", "-vf", "blackdetect=d=0.2:pix_th=0.10"]
    )
    found["black"] = [
        (round(x + a.start, 2), round(y + a.start, 2)) for x, y in black_spans(black)
    ]
    sound = ffmpeg_log([*span, "-i", a.video, "-vn", "-af", "volumedetect,ebur128"])
    found["sound"] = (
        {**volume(sound), "lufs": integrated_lufs(sound)}
        if "mean_volume" in sound
        else None
    )
    save_json(out / "footage.json", found)
    print(json.dumps(found, indent=1))


if __name__ == "__main__":
    main()
