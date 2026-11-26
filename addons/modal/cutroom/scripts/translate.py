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
"""Make one cut clip in other languages: its captions and hook translated, the picture and sound as they were.

    cutroom translate jobs/<id> --pick 1 --langs es,pt,de [--name STEM] [--voice]
        [--layout fill|blur|facecam] [--cam x:y:w:h] [--hook "TEXT"] [--hashtags "#a #b"]

For a clip `cut.py` already made from the job's transcript with the fill,
blur, or facecam layout and no jump cuts: the words spoken between its start
and end are translated a sentence at a time and spread evenly over that
sentence's time, the hook is translated, and each language is rendered as
`edits/<name>_<lang>.mp4` at the same loudness. `edits/<name>_captions.md`
lists the translated hook for each language as post text.

The translation is a machine's (Google's, through deep-translator, which
needs the network and no account). Read every language before it is posted:
a line that fails to translate is kept in the original and said so.

`--voice` has a stock text-to-speech voice (Microsoft's neural stock voices,
through edge-tts, which needs the network and no account) speak the
translated hook over the first 2.5 seconds, sped up to fit, with the clip's
own sound lowered under it. It is a stock voice and is never presented as
the person in the clip; it clones and imitates nobody.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any

from common import ffprobe, load_json, run, tool
from cut import CAP_Y, build_ass, video_filter

VOICES = {
    "es": "es-ES-AlvaroNeural",
    "pt": "pt-BR-AntonioNeural",
    "de": "de-DE-ConradNeural",
    "ru": "ru-RU-DmitryNeural",
    "fr": "fr-FR-HenriNeural",
    "it": "it-IT-DiegoNeural",
    "pl": "pl-PL-MarekNeural",
    "tr": "tr-TR-AhmetNeural",
    "ja": "ja-JP-KeitaNeural",
    "ko": "ko-KR-InJoonNeural",
    "ar": "ar-SA-HamedNeural",
    "hi": "hi-IN-MadhurNeural",
}
HOOK_SECONDS = 2.5

Word = dict[str, Any]


def translator(lang: str) -> Any:
    """A translator into `lang` from whatever language it is given."""
    from deep_translator import GoogleTranslator

    return GoogleTranslator(source="auto", target=lang)


def tr(to: Any, text: str) -> str:
    """Text translated, or the text itself where the service fails, which is said and does not stop the batch."""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        return (to.translate(text) or text).strip()
    except Exception as error:
        print(
            f"warning: translate failed ({error}); keeping original text",
            file=sys.stderr,
        )
        return text


def sentences(words: list[Word]) -> list[list[Word]]:
    """A clip's words as sentences: each ends at closing punctuation or before a pause over 0.8 s."""
    out: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        if current and word["s"] - current[-1]["e"] > 0.8:
            out.append(current)
            current = []
        current.append(word)
        if word["w"][-1:] in ".?!":
            out.append(current)
            current = []
    if current:
        out.append(current)
    return out


def translate_words(to: Any, words: list[Word]) -> list[Word]:
    """Each sentence translated, its new words spread evenly over the time the sentence took."""
    out: list[Word] = []
    for sentence in sentences(words):
        new = tr(to, " ".join(word["w"] for word in sentence)).split()
        if not new:
            continue
        a, b = sentence[0]["s"], sentence[-1]["e"]
        step = (b - a) / len(new)
        out += [
            {"w": word, "s": a + i * step, "e": a + (i + 1) * step}
            for i, word in enumerate(new)
        ]
    return out


def make_voice(lang: str, text: str, dest: Path) -> Path | None:
    """A stock voice speaking `text`, saved as MP3, or nothing where no voice is listed for the language."""
    import edge_tts

    voice = VOICES.get(lang)
    if not voice:
        print(
            f"no stock voice configured for '{lang}', skipping --voice", file=sys.stderr
        )
        return None
    asyncio.run(edge_tts.Communicate(text, voice).save(str(dest)))
    return dest


def render(
    src: str,
    s0: float,
    e0: float,
    layout: str,
    cam: str,
    ass: Path,
    mp4: Path,
    voice: Path | None = None,
) -> None:
    """Render one language's clip: the source between `s0` and `e0` in its layout with the translated captions."""
    v = video_filter(layout, cam, ass)
    cmd = [
        tool("ffmpeg"),
        "-y",
        "-v",
        "error",
        "-ss",
        f"{s0:.2f}",
        "-to",
        f"{e0:.2f}",
        "-i",
        src,
    ]
    if voice:
        length = float(ffprobe(voice)["format"]["duration"])
        tempo = (
            f"atempo={min(2.0, length / HOOK_SECONDS):.3f},"
            if length > HOOK_SECONDS
            else ""
        )
        sound = (
            f"[0:a]volume=0.2:enable='lt(t,{HOOK_SECONDS})'[bed];"
            f"[1:a]{tempo}atrim=0:{HOOK_SECONDS},afade=t=out:st={HOOK_SECONDS - 0.15}:d=0.15,apad[tts];"
            f"[bed][tts]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
        )
        cmd += [
            "-i",
            str(voice),
            "-filter_complex",
            v + ";" + sound,
            "-map",
            "[vo]",
            "-map",
            "[ao]",
        ]
    else:
        cmd += ["-filter_complex", v, "-map", "[vo]", "-map", "0:a?"]
        cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart"]
    run([*cmd, str(mp4)])


def post_block(lang: str, hook: str, hashtags: list[str], url: str | None) -> str:
    """One language's post text: the hook alone with the source's address, and the hook with the hashtags."""
    plain = "\n".join(part for part in (hook, url or "") if part)
    tagged = "\n".join(part for part in (hook, " ".join(hashtags)) if part)
    return f"## {lang}\n\n**Without hashtags**\n\n{plain}\n\n**With hashtags**\n\n{tagged}\n"


def main() -> None:
    """Translate, render each language, and write the post texts."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job")
    ap.add_argument("--pick", type=int, default=1)
    ap.add_argument(
        "--name", default="", help="the clip's file stem, default clip_<pick>"
    )
    ap.add_argument("--langs", default="es,pt,de,ru")
    ap.add_argument("--voice", action="store_true")
    ap.add_argument("--layout", choices=["fill", "blur", "facecam"])
    ap.add_argument("--cam")
    ap.add_argument("--hook")
    ap.add_argument(
        "--hashtags", default="", help="hashtags for the post text, separated by spaces"
    )
    a = ap.parse_args()
    job = Path(a.job)
    out = job / "edits"
    stem = a.name or f"clip_{a.pick}"
    side = out / f"{stem}.json"
    if not side.exists():
        sys.exit(f"{side} not found. Cut the clip first with cut.py.")
    meta = load_json(side)
    if meta.get("segments"):
        sys.exit(
            f"{stem} was cut with jump cuts, which translate.py cannot follow: its words are on another timeline."
        )
    candidates = load_json(job / "candidates.json")
    s0, e0 = meta["start"], meta["end"]
    layout = a.layout or meta.get("layout", "blur")
    if layout not in ("fill", "blur", "facecam"):
        sys.exit(
            f"the {layout} layout is not one translate.py renders; pass --layout fill or blur."
        )
    cam = a.cam or "0.70:0.68:0.30:0.32"
    hook = a.hook if a.hook is not None else meta.get("hook", "")
    words = [
        w for w in load_json(job / "transcript.json") if s0 <= w["s"] < e0 and w["w"]
    ]
    languages = [x.strip() for x in a.langs.split(",") if x.strip()]
    posts = [
        "# Post text, one clip in several languages\n",
        f"Source: {meta.get('source_title') or ''} ({meta.get('source_channel') or ''})\n",
        "Translations are machine translated. Read each one before posting.\n",
    ]
    for lang in languages:
        to = translator(lang)
        new_hook = tr(to, hook) if hook else ""
        ass = out / f"{stem}_{lang}.ass"
        ass.write_text(
            build_ass(translate_words(to, words), s0, e0, new_hook, CAP_Y[layout]),
            encoding="utf-8",
        )
        mp4 = out / f"{stem}_{lang}.mp4"
        voice = None
        if a.voice and new_hook:
            voice = make_voice(
                lang, new_hook, Path(tempfile.gettempdir()) / f"{stem}_{lang}_hook.mp3"
            )
        render(candidates["source"], s0, e0, layout, cam, ass, mp4, voice)
        posts.append(
            post_block(lang, new_hook, a.hashtags.split(), meta.get("source_url"))
        )
        print(mp4)
    (out / f"{stem}_captions.md").write_text("\n".join(posts), encoding="utf-8")
    print(out / f"{stem}_captions.md")


if __name__ == "__main__":
    main()
