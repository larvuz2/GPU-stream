# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Measure a file's sound: its loudness and peak, and the level of chosen stretches.

    cutroom levels FILE [--spans "6.7-10.7,23.3-25.2"]

The agent cannot hear, so a mix is checked by numbers:

- `lufs`: the integrated loudness (EBU R 128), which a cut is normalized
  to: -14 for a finished video, -16 for a mastered voice.
- `lra`: the loudness range, and `true_peak_db`, the highest peak between
  samples, which stays under -1 dB so a platform's own encoding does not clip.
- `mean_db` and `max_db`: the plain mean and peak volume.
- `spans`: the RMS level, in decibels, of each stretch asked for. Measuring
  a stretch where the voice speaks and a gap where only the music plays says
  how far under the voice the music sits. A voice kept on top of quiet,
  ducked music read about -18 dB while speaking and -28 dB in a gap.

Prints one JSON object. What the numbers cannot say, whether it sounds
right, is the person's to hear.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

import numpy as np
from check import integrated_lufs
from sheet import volume

Span = tuple[float, float]


def parse_spans(spec: str) -> list[Span]:
    """`"6.7-10.7,23.3-25.2"` as [(6.7, 10.7), (23.3, 25.2)]."""
    out = []
    for part in (x.strip() for x in spec.split(",") if x.strip()):
        a, b = (float(x) for x in part.split("-"))
        out.append((a, b))
    return out


def summary(log: str) -> dict[str, float | None]:
    """The loudness range and true peak of the summary FFmpeg's `ebur128=peak=true` prints, with the loudness."""
    tail = log[log.rfind("Summary:") :] if "Summary:" in log else ""
    lra = re.search(r"LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", tail)
    peak = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", tail)
    return {
        "lufs": integrated_lufs(log),
        "lra": float(lra.group(1)) if lra else None,
        "true_peak_db": float(peak.group(1)) if peak else None,
    }


def rms_db(samples: np.ndarray) -> float:
    """The RMS level of samples between -1 and 1, in decibels; -180 for silence."""
    if len(samples) == 0:
        return -180.0
    return round(
        float(20 * np.log10(np.sqrt((samples.astype(np.float64) ** 2).mean()) + 1e-9)),
        1,
    )


def span_rms(path: str, span: Span) -> float:
    """The RMS level of one stretch of a file, heard as 16 kHz mono."""
    start, end = span
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{end - start:.3f}",
        "-i",
        path,
    ]
    done = subprocess.run(
        [*cmd, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True,
        check=False,
    )
    return rms_db(np.frombuffer(done.stdout, np.int16).astype(np.float32) / 32768)


def measure(path: str, spans: list[Span]) -> dict[str, Any]:
    """Everything this script measures of a file."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn"]
    done = subprocess.run(
        [*cmd, "-af", "volumedetect,ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if done.returncode != 0 or "Summary:" not in done.stderr:
        sys.exit(f"no sound could be measured in {path}: {done.stderr.strip()[-400:]}")
    found: dict[str, Any] = {
        "file": path,
        **summary(done.stderr),
        **volume(done.stderr),
    }
    if spans:
        found["spans"] = [
            {"start": a, "end": b, "rms_db": span_rms(path, (a, b))} for a, b in spans
        ]
    return found


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file")
    ap.add_argument(
        "--spans",
        default="",
        help='stretches to measure, in seconds: "6.7-10.7,23.3-25.2"',
    )
    a = ap.parse_args()
    print(json.dumps(measure(a.file, parse_spans(a.spans)), indent=1))
