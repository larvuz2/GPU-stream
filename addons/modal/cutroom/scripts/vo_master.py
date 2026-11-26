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
"""Master a narration to a studio voice-over: dry, close, even, at -16 LUFS.

    cutroom vo_master in.wav out.wav [--preset studio_warm]

For a generated, cloned, or recorded voice before it is laid under picture.
The presets, each a set of gains for one chain:

- `studio_warm`: no pitch change; strong chest and proximity, dry, tight.
  The one to start from.
- `studio_deep`: one semitone lower with the voice's own formants kept, more
  chest. `studio_deeper`: two semitones lower, more low end.
- `broadcast`: EQ and compression only, no saturation.

The chain: gate, pitch (Rubber Band inside FFmpeg, formants preserved),
high-pass at 65 Hz, low shelf, chest at 125 Hz, a cut of the boxiness at
330 Hz, presence at 2.8 kHz, a de-essing notch at 6.8 kHz, air above 11 kHz,
compression, gentle saturation for warmth, a second compressor, a limiter at
-1.5 dB, and FFmpeg's `loudnorm` to -16 LUFS. There is no room on it: a
studio voice-over is dry, and the cut adds whatever space the picture wants.

Nothing here can be judged by reading it. The loudness can be measured
(`levels.py`); whether the voice sounds right is the person's to hear.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

PRESETS = {
    "broadcast": {
        "semitones": 0,
        "chest": 5.0,
        "low": 0.0,
        "mud": -3.0,
        "presence": 3.0,
        "air": 2.0,
        "sat": 0.0,
    },
    "studio_warm": {
        "semitones": 0,
        "chest": 5.0,
        "low": 2.5,
        "mud": -4.0,
        "presence": 2.0,
        "air": 2.5,
        "sat": 3.0,
    },
    "studio_deep": {
        "semitones": -1,
        "chest": 5.5,
        "low": 3.0,
        "mud": -4.0,
        "presence": 2.0,
        "air": 2.5,
        "sat": 3.0,
    },
    "studio_deeper": {
        "semitones": -2,
        "chest": 6.0,
        "low": 3.5,
        "mud": -4.5,
        "presence": 2.5,
        "air": 2.5,
        "sat": 3.0,
    },
}


def pitch_filter(semitones: float) -> str:
    """The FFmpeg filter that resamples to 48 kHz, after shifting the pitch where `semitones` is not zero."""
    if not semitones:
        return "aresample=48000"
    ratio = 2 ** (semitones / 12)
    return (
        f"rubberband=pitch={ratio:.5f}:formant=preserved:transients=smooth:detector=soft:pitchq=quality,"
        "aresample=48000"
    )


def master(src: str | Path, dst: str | Path, preset: str = "studio_warm") -> Path:
    """Write `src` mastered with a preset to `dst`, 48 kHz mono, and return `dst`."""
    from pedalboard import (
        Compressor,
        Distortion,
        Gain,
        HighpassFilter,
        HighShelfFilter,
        Limiter,
        LowShelfFilter,
        NoiseGate,
        PeakFilter,
        Pedalboard,
    )
    from pedalboard.io import AudioFile

    p = PRESETS[preset]
    with tempfile.TemporaryDirectory() as folder:
        pitched = Path(folder) / "p.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(src),
            "-af",
            pitch_filter(p["semitones"]),
        ]
        subprocess.run([*cmd, "-ac", "1", str(pitched)], check=True)
        with AudioFile(str(pitched)) as file:
            samples, rate = file.read(file.frames), file.samplerate
    chain = [
        NoiseGate(threshold_db=-48, ratio=4, attack_ms=2, release_ms=120),
        HighpassFilter(cutoff_frequency_hz=65),
        LowShelfFilter(cutoff_frequency_hz=90, gain_db=p["low"], q=0.7),
        PeakFilter(cutoff_frequency_hz=125, gain_db=p["chest"], q=0.8),
        PeakFilter(cutoff_frequency_hz=330, gain_db=p["mud"], q=1.3),
        PeakFilter(cutoff_frequency_hz=2800, gain_db=p["presence"], q=1.0),
        PeakFilter(cutoff_frequency_hz=6800, gain_db=-3.0, q=3.0),
        HighShelfFilter(cutoff_frequency_hz=11000, gain_db=p["air"], q=0.7),
        Compressor(threshold_db=-24, ratio=3.5, attack_ms=3, release_ms=70),
        Gain(gain_db=4),
    ]
    if p["sat"]:
        # Warmth, not grit: the drive is taken back out as gain
        chain += [Distortion(drive_db=p["sat"]), Gain(gain_db=-p["sat"] * 0.6)]
    chain += [
        Compressor(threshold_db=-12, ratio=2, attack_ms=10, release_ms=120),
        Limiter(threshold_db=-1.5, release_ms=80),
    ]
    processed = Pedalboard(chain)(samples, rate)
    before = Path(str(dst) + ".pre.wav")
    with AudioFile(str(before), "w", rate, processed.shape[0]) as file:
        file.write(processed)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(before),
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=7",
    ]
    subprocess.run([*cmd, "-ar", "48000", "-ac", "1", str(dst)], check=True)
    before.unlink()
    return Path(dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--preset", default="studio_warm", choices=sorted(PRESETS))
    a = ap.parse_args()
    print(master(a.src, a.dst, a.preset))
