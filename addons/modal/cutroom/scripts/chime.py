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
"""Synthesize the sound of a reveal: a soft riser and a rising bell run into a bright chord, then a shimmer.

    cutroom chime sfx/reveal_chime.wav [--seconds 3]

Three seconds, 48 kHz stereo, its volume ramping up and then down: the sound
of something being presented, for `reveal.py` to start as the last sign
lands. It is made of sine partials and filtered noise with a fixed seed, by
no model and from no recording, so it is the same sound every time and
nobody else's.

The parts, in order: an airy riser to 0.62 s; a pentatonic run of celesta
notes panned left to right; a five-note chord at 0.66 s; small high bells
thinning out; a few early reflections for a room; then a high-pass at 250 Hz
and a reverb (Pedalboard), and a ramp in over 0.35 s and out from 1.6 s.
"""

from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np

SR = 48000
NOTES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# A celesta's partials, slightly inharmonic: (multiple of the pitch, level, how much faster it decays)
PARTIALS = (
    (1.0, 1.0, 1.0),
    (2.0, 0.45, 1.8),
    (2.76, 0.25, 2.6),
    (5.4, 0.12, 4.0),
    (8.93, 0.05, 6.0),
)


def bell(
    pitch: float, seconds: float, level: float = 1.0, decay: float = 1.4
) -> np.ndarray:
    """One struck bell note at `pitch` hertz: its partials, each fading faster than the one below it."""
    t = np.arange(int(seconds * SR)) / SR
    tone = sum(
        a * np.sin(2 * np.pi * pitch * m * t) * np.exp(-t * decay * d)
        for m, a, d in PARTIALS
    )
    attack = np.minimum(1, t / 0.004)
    return level * tone * attack


def note(name: str) -> float:
    """A note's pitch in hertz from its name, such as `C6`."""
    return 440 * 2 ** ((NOTES[name[0]] + 12 * (int(name[1:]) + 1) - 69) / 12)


def make(seconds: float = 3.0, seed: int = 7) -> np.ndarray:
    """The chime before its reverb, as two rows of samples peaking at 0.89."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = np.zeros((2, n))

    def add(signal: np.ndarray, start: float, pan: float = 0.0) -> None:
        i = int(start * SR)
        j = min(n, i + len(signal))
        out[0, i:j] += signal[: j - i] * (1 - pan) ** 0.5
        out[1, i:j] += signal[: j - i] * (1 + pan) ** 0.5

    t = np.arange(int(0.65 * SR)) / SR
    noise = rng.standard_normal(len(t))
    # A crude high-pass, which leaves air and no rumble
    hiss = noise - np.convolve(noise, np.ones(40) / 40, "same")
    add(0.05 * hiss * (t / t[-1]) ** 2.5, 0.0)
    run = ["G5", "A5", "C6", "D6", "E6", "G6", "A6", "C7"]
    for i, name in enumerate(run):
        pan = -0.6 + 1.2 * i / (len(run) - 1)
        add(bell(note(name), 1.2, 0.16 + 0.02 * i, 2.4), 0.05 + i * 0.075, pan=pan)
    for name, pan in (
        ("C6", -0.3),
        ("E6", 0.3),
        ("G6", -0.1),
        ("C7", 0.1),
        ("E7", 0.0),
    ):
        add(bell(note(name), seconds - 0.66, 0.30, 1.1), 0.66, pan=pan)
    high = ["C7", "D7", "E7", "G7", "A7", "C8"]
    for _ in range(26):
        start = 0.7 + rng.random() ** 1.6 * 1.9
        level = 0.05 * (1 - (start - 0.7) / 2.2)
        add(
            bell(note(high[rng.integers(len(high))]), 0.6, level, 4.0),
            start,
            pan=rng.uniform(-0.8, 0.8),
        )
    for delay, gain in ((0.031, 0.35), (0.047, 0.28), (0.083, 0.2), (0.127, 0.14)):
        shift = int(delay * SR)
        out[0, shift:] += gain * out[1, :-shift]
        out[1, shift:] += gain * out[0, :-shift]
    at = np.arange(n) / SR
    fall = np.cos(np.clip((at - 1.6) / (seconds - 1.6), 0, 1) * np.pi / 2) ** 2
    out *= np.minimum(1, at / 0.35) * np.where(at < 1.6, 1, fall)
    out /= np.abs(out).max() / 0.89
    return out


def write(dst: str | Path, seconds: float = 3.0) -> str:
    """Write the finished chime to `dst` as 16-bit stereo and return the path."""
    from pedalboard import HighpassFilter, Pedalboard, Reverb

    room = Pedalboard(
        [
            HighpassFilter(250),
            Reverb(room_size=0.55, wet_level=0.22, dry_level=0.85, width=1.0),
        ]
    )
    samples = room(make(seconds).astype(np.float32), SR)
    at = np.arange(samples.shape[1]) / SR
    samples *= np.where(at < seconds - 0.4, 1, np.clip((seconds - at) / 0.4, 0, 1))
    samples /= np.abs(samples).max() / 0.89
    pcm = (np.clip(samples.T, -1, 1) * 32767).astype(np.int16)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dst), "wb") as file:
        file.setnchannels(2)
        file.setsampwidth(2)
        file.setframerate(SR)
        file.writeframes(pcm.tobytes())
    return str(dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dst")
    ap.add_argument("--seconds", type=float, default=3.0)
    a = ap.parse_args()
    print(write(a.dst, a.seconds))
