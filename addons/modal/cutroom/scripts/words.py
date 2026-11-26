# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Hear what is said in a piece of media and when: every word with its start and end.

    cutroom words MEDIA [--lang en] [--model medium] [--start S --end E] [--offset 0] [--vad] [--out words.json]

Speech-to-text with word timings, by faster-whisper from the image's own
models. Three things it is for:

- the transcript of footage, before deciding what to cut and what the
  captions say (`moments.py` keeps one of the whole source by itself);
- the second each word of a narration take is spoken, which is what an
  overlay is timed to: the headline `explainer.py` throws word by word, the
  signs `reveal.py` pops in. `--offset` adds the second the take starts at on
  the timeline, so the numbers printed are the output's;
- checking a finished voice says the words that were written.

`--lang` forces the language; without it the model guesses, and says how
sure it is. `--vad` skips stretches with no voice. A recording with no
speech at all still gets a word or two, which the model invents on silence
("You", "Thank you"): read the footage's level (`sheet.py`) before trusting a
short transcript.

Prints the language, then `start  end  word` a line, and with `--out`
writes `[{"w", "s", "e"}, ...]`, the transcript form the cutters read.
"""

from __future__ import annotations

import argparse
from typing import Any

from clean import model, pcm
from common import save_json


def heard(
    media: str,
    start: float = 0.0,
    end: float | None = None,
    model_name: str = "medium",
    language: str | None = None,
    vad: bool = False,
    offset: float = 0.0,
) -> tuple[list[dict[str, Any]], str, float]:
    """The words of a stretch of media, with the language heard and how probable the model holds it.

    Word times are seconds from `start`, plus `offset`.
    """
    segments, info = model(model_name).transcribe(
        pcm(media, start, end),
        word_timestamps=True,
        vad_filter=vad,
        beam_size=5,
        language=language,
    )
    words = [
        {
            "w": word.word.strip(),
            "s": round(word.start + offset, 2),
            "e": round(word.end + offset, 2),
        }
        for segment in segments
        for word in (segment.words or [])
    ]
    return words, info.language, float(info.language_probability)


def main() -> None:
    """Transcribe and print."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("media")
    ap.add_argument(
        "--lang",
        default=None,
        help="the language spoken (en, es, ...); guessed where left out",
    )
    ap.add_argument("--model", default="medium", choices=["small", "medium"])
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument(
        "--offset", type=float, default=0.0, help="seconds added to every time printed"
    )
    ap.add_argument("--vad", action="store_true", help="skip stretches with no voice")
    ap.add_argument("--out", default="", help="write the words as JSON here")
    a = ap.parse_args()
    words, language, sure = heard(
        a.media, a.start, a.end, a.model, a.lang, a.vad, a.offset
    )
    print(f"language: {language} ({sure:.2f})  words: {len(words)}")
    for word in words:
        print(f"{word['s']:7.2f} {word['e']:7.2f}  {word['w']}")
    if a.out:
        save_json(a.out, words)
        print(a.out)


if __name__ == "__main__":
    main()
