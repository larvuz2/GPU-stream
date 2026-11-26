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
"""Lay spoken lines on a video's timeline: one voice track, and the caption lines that go with it.

    cutroom narrate spec.json --out jobs/<id>/narration

The lines are sound files that already exist: takes of a generated voice
brought into the project folder, or recordings. This script speaks nothing.
It trims each take, speeds it up where asked, places it, and mixes the track.

spec.json:

    {
      "gap": 0.15,                      seconds left after a captioned line
      "tempo": 1.25,                    optional speed-up of every line, pitch kept
      "master": false,                  optional broadcast chain over the whole track
      "speakers": {"A": {"color": "FFFFFF", "tempo": 1.25}},
      "lines": [
        {"audio": "library/line-01/01-take.wav",   the take, a path in the project folder
         "text": "Wait... is that a trumpet?",      what it says
         "caption": "Wait… is that a TRUMPET?",     what is shown (default: text; "" for none)
         "who": "A",                                optional: a speaker, for its caption color
         "tempo": 1.3,                              optional: this line's own speed
         "at": 0.2}                                 optional: the output second it starts at
      ]
    }

Writes `<out>/voice.wav`, the whole track at 48 kHz mono, and
`<out>/lines.json`, `[[start, end, caption, color?], ...]` in output seconds,
which the cutters take as `--voice` and `--lines` (`cut.py` with
`--lines-time output`).

A line starts at its `at`, or right after the line before it. Captioned
lines never overlap each other: one whose `at` is too early waits for the
line before it to end. A line with an empty caption is a shout or a laugh
and may lie over anything. Each take is prepared once, trimmed of the
silence around it (below -45 dB) and resampled, and kept in `<out>/cache`
under a hash of its bytes, so laying the same lines again costs nothing and
sounds the same.

The narration sets the length of a cut: lay it first, read the times it
prints, then fit the footage to them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# The broadcast voice-over chain a spec turns on with "master": rumble cut, denoise, low end, less mud, presence
# and air, de-ess, compression, a little room, and a limiter. `vo_master.py` is the drier, later chain.
MASTER = (
    "highpass=f=60,afftdn=nf=-35,"
    "equalizer=f=110:t=q:w=0.9:g=5,equalizer=f=300:t=q:w=1.2:g=-3,equalizer=f=3500:t=q:w=1.0:g=3,"
    "treble=g=2:f=10000,deesser=i=0.4,"
    "acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=3,"
    "aecho=0.9:0.35:28|47:0.10|0.06,alimiter=limit=0.9"
)
TRIM = (
    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
    "silenceremove=start_periods=1:start_threshold=-45dB,areverse"
)

Placed = tuple[float, float, str, Path, str]


def ffmpeg(*arguments: str) -> None:
    """Run FFmpeg quietly, ending the script with its words where it fails."""
    done = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        sys.exit(f"ffmpeg failed: {done.stderr.strip()[-600:]}")


def duration(path: str | Path) -> float:
    """A sound file's length in seconds."""
    probe = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
    ]
    done = subprocess.run(
        [*probe, str(path)], capture_output=True, text=True, check=False
    )
    return float(done.stdout.strip())


def prepared(audio: Path, cache: Path) -> Path:
    """A take trimmed of the silence around it, at 48 kHz mono, made once per file content.

    Raises:
        SystemExit: The take is not there.
    """
    if not audio.is_file():
        sys.exit(f"no such take: {audio}")
    key = hashlib.sha1(audio.read_bytes()).hexdigest()[:16]
    wav = cache / f"{key}.wav"
    if not wav.exists():
        ffmpeg("-i", str(audio), "-af", TRIM, "-ar", "48000", "-ac", "1", str(wav))
    return wav


def at_tempo(wav: Path, tempo: float) -> Path:
    """A prepared take played `tempo` times as fast at the same pitch, kept beside it."""
    if tempo == 1.0:
        return wav
    fast = wav.with_name(f"{wav.stem}.x{tempo:g}.wav")
    if not fast.exists():
        ffmpeg("-i", str(wav), "-af", f"atempo={tempo}", str(fast))
    return fast


def place(
    lines: list[dict[str, Any]], lengths: list[float], gap: float
) -> list[tuple[float, float]]:
    """Where each line starts and ends on the timeline, given each take's length.

    A line starts at its `at`, else where the last captioned line ended plus
    `gap`. A captioned line never starts before that point; an uncaptioned
    one starts wherever it says and moves nothing.
    """
    cursor, out = 0.0, []
    for line, length in zip(lines, lengths):
        captioned = bool(line.get("caption", line.get("text", "")))
        start = float(line["at"]) if "at" in line else cursor
        if captioned:
            start = max(start, cursor)
            cursor = start + length + gap
        out.append((start, start + length))
    return out


def mix_graph(starts: list[float], master: bool) -> str:
    """The filter graph that delays each take to its start and sums them, with the broadcast chain if asked."""
    chains = [
        f"[{i}:a]adelay={int(start * 1000)}:all=1[d{i}]"
        for i, start in enumerate(starts)
    ]
    summed = "".join(f"[d{i}]" for i in range(len(starts)))
    graph = (
        ";".join(chains)
        + f";{summed}amix=inputs={len(starts)}:normalize=0:duration=longest[v]"
    )
    if master:
        graph = graph.replace("[v]", "[m]") + f";[m]{MASTER}[v]"
    return graph


def main() -> None:
    """Prepare the takes, place them, mix the track, and write the caption lines."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    out = Path(a.out)
    cache = out / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    gap = float(spec.get("gap", 0.15))
    speakers = spec.get("speakers", {})
    lines = spec["lines"]
    takes, colors = [], []
    for line in lines:
        if "audio" not in line:
            sys.exit(
                f"a line has no audio: {line.get('text', '')!r}. Each line names the take that speaks it."
            )
        who = speakers.get(line.get("who", ""), {})
        tempo = float(line.get("tempo", who.get("tempo", spec.get("tempo", 1.0))))
        takes.append(at_tempo(prepared(Path(line["audio"]), cache), tempo))
        colors.append(who.get("color", ""))
    spans = place(lines, [duration(take) for take in takes], gap)
    placed: list[Placed] = [
        (start, end, line.get("caption", line.get("text", "")), take, color)
        for (start, end), line, take, color in zip(spans, lines, takes, colors)
    ]
    inputs = [part for take in takes for part in ("-i", str(take))]
    graph = mix_graph([start for start, _ in spans], bool(spec.get("master")))
    voice = out / "voice.wav"
    ffmpeg(
        *inputs,
        "-filter_complex",
        graph,
        "-map",
        "[v]",
        "-ar",
        "48000",
        "-ac",
        "1",
        str(voice),
    )
    captions = [
        [round(start, 2), round(end, 2), caption, *([color] if color else [])]
        for start, end, caption, _, color in placed
        if caption
    ]
    (out / "lines.json").write_text(
        json.dumps(captions, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for start, end, caption, _, _ in placed:
        print(f"{start:6.2f}-{end:6.2f}  {caption or '(no caption)'}")
    print(f"voice: {voice} ({duration(voice):.1f}s)")
    print(f"lines: {out / 'lines.json'}")


if __name__ == "__main__":
    main()
