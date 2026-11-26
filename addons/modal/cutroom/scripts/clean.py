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
"""Find the swear words said in a piece of media, so a cut has none: heard or read.

    cutroom clean MEDIA [--lang en]      prints each swear heard as (start, end, word)

The rule the cutters hold a clip to (`cut.py`, `explainer.py`) and the final
check verifies (`check.py`):

- Sound: every swear heard, whoever says it, is muted to silence.
- Captions: a swear is left out, never starred.

Slurs are treated the same way. English and Spanish words are known
(`SWEAR`); the language given decides what the speech model listens for, and
forcing the wrong one makes it hear words nobody said.

Hearing is done on short overlapping pieces (`heard_bad`): on a whole clip
Whisper skips quiet or overlapping lines and its word times drift, while on
five-second pieces it hears more and times each word closely. A hit in any
piece counts, and a caller that must be sure listens again with a second
model and with the pieces' edges shifted, since a word cut at one edge is
whole in another pass.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from common import whisper_source

# One word's vowel is written as a class so that a spell checker does not read the pattern as a typo
SWEAR = re.compile(
    r"^(fuck\w*|f[u*]+ck\w*|motherfuck\w*|shit\w*|bullshit\w*|bitch\w*|c[u]nt\w*|dick\w*|cock\w*|pussy\w*|ass|asses|asshole\w*|"
    r"bastard\w*|whore\w*|slut\w*|damn\w*|goddamn\w*|hell|crap\w*|piss\w*|wtf|stfu|"
    r"nigg\w*|n[i1]gg?a\w*|f[a@]gg?\w*|retard\w*|tranny\w*|chink\w*|spic\w*|kike\w*|"
    # Spanish
    r"mierd\w*|pendej\w*|cabr[oó]n\w*|cabrona\w*|ching\w*|put[ao]s?|puto\w*|putas?|verga\w*|culer[oa]\w*|culo|"
    r"jod[aeiao]\w*|joder|co[ñn]o|pinche\w*|mamad[ao]\w*|marica\w*|maric[oó]n\w*|perra|hijueputa\w*|chupa\w*)$",
    re.I,
)

_MODEL: dict[str, Any] = {}

Hit = tuple[float, float, str]


def core(word: str) -> str:
    """A word without its punctuation, in lower case, as it is matched."""
    return re.sub(r"[^\w*']", "", word).strip("'").lower()


def is_bad(word: str) -> bool:
    """Whether a word is a swear or a slur, or was already starred by whoever wrote it."""
    bare = core(word)
    return bool(bare) and ("*" in bare or bool(SWEAR.match(bare)))


def drop_bad(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Caption words with the swears left out: "What the fuck?" becomes "What the…?".

    The word before a dropped one takes its time and its closing punctuation,
    where the two are less than 0.8 s apart, so the caption does not blink off
    while the muted word is said.
    """
    out: list[dict[str, Any]] = []
    for word in words:
        if not is_bad(word["w"]):
            out.append(dict(word))
            continue
        tail = re.sub(r"^.*?([.?!,…]*)$", r"\1", word["w"])
        if out and word["s"] - out[-1]["e"] < 0.8:
            previous = out[-1]["w"].rstrip(".,!?…")
            out[-1] = dict(
                out[-1],
                w=previous + "…" + tail.replace(".", "").replace("…", ""),
                e=word["e"],
            )
    return out


def model(name: str) -> Any:
    """A Whisper model on the CPU with 8-bit weights, loaded once for the life of the script."""
    if name not in _MODEL:
        from faster_whisper import WhisperModel

        _MODEL[name] = WhisperModel(
            whisper_source(name), device="cpu", compute_type="int8"
        )
    return _MODEL[name]


def pcm(media: str | Path, start: float = 0.0, end: float | None = None) -> np.ndarray:
    """A file's sound as 16 kHz mono samples, with quiet speech lifted so a line under a louder voice is heard."""
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        f"{start:.3f}",
        *(["-to", f"{end:.3f}"] if end else []),
        "-i",
        str(media),
        "-vn",
        "-af",
        "highpass=f=100,lowpass=f=7000,dynaudnorm=f=150:g=7",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "s16le",
        "-",
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def heard_bad(
    media: str | Path,
    start: float = 0.0,
    end: float | None = None,
    model_name: str = "medium",
    chunk: float = 5.0,
    hop: float = 2.5,
    offset: float = 0.0,
    language: str = "en",
) -> list[Hit]:
    """The swears spoken in `media` between `start` and `end`, as (start, end, word) in seconds from `start`.

    `offset` shifts the edges of the pieces by that many seconds. The same
    word found by two overlapping pieces is one hit.
    """
    samples = pcm(media, start, end)
    rate, hits = 16000, []
    seconds = len(samples) / rate
    at = -offset if offset else 0.0
    while at < seconds:
        piece = samples[int(max(0.0, at) * rate) : int(min(seconds, at + chunk) * rate)]
        if len(piece) > rate * 0.5:
            segments, _ = model(model_name).transcribe(
                piece,
                word_timestamps=True,
                vad_filter=False,
                beam_size=5,
                language=language,
                condition_on_previous_text=False,
            )
            base = max(0.0, at)
            hits += [
                (
                    round(base + word.start, 2),
                    round(base + word.end, 2),
                    word.word.strip(),
                )
                for segment in segments
                for word in (segment.words or [])
                if is_bad(word.word)
            ]
        if at + chunk >= seconds:
            break
        at += hop
    out: list[Hit] = []
    for hit in sorted(hits):
        if (
            out
            and hit[0] < out[-1][1] + 0.3
            and core(hit[2])[:4] == core(out[-1][2])[:4]
        ):
            out[-1] = (min(out[-1][0], hit[0]), max(out[-1][1], hit[1]), out[-1][2])
        else:
            out.append(hit)
    return out


def heard_twice(media: str | Path, language: str = "en") -> list[Hit]:
    """Every swear two models hear in a finished file, each listening on two alignments of the pieces.

    One pass missing a word is not a pass, so this is what a finished cut is
    held to.
    """
    return (
        heard_bad(media, language=language)
        + heard_bad(media, model_name="small", language=language)
        + heard_bad(media, offset=2.5, language=language)
        + heard_bad(media, model_name="small", offset=2.5, language=language)
    )


def merge(
    windows: list[tuple[float, float]], pad: float = 0.12
) -> list[tuple[float, float]]:
    """Time windows widened by `pad` on each side and joined where they touch."""
    out: list[list[float]] = []
    for a, b in sorted((max(0, a - pad), b + pad) for a, b in windows):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(round(a, 2), round(b, 2)) for a, b in out]


def mute_filter(windows: list[tuple[float, float]]) -> str:
    """The FFmpeg audio filter that silences the windows, in output seconds, or nothing for none."""
    if not windows:
        return ""
    spans = "+".join(f"between(t,{a},{b})" for a, b in windows)
    return f"volume=0:enable='{spans}'"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("media")
    parser.add_argument(
        "--lang", default="en", help="the language spoken (en, es, ...)"
    )
    arguments = parser.parse_args()
    found = heard_bad(arguments.media, language=arguments.lang)
    for hit in found:
        print(hit)
    print(f"{len(found)} heard")
    sys.exit(0)
