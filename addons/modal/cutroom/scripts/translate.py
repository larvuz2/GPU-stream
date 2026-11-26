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
"""Make one cut clip in another language: its captions and hook translated, the picture and sound as they were.

    cutroom translate jobs/<id> --pick 1 --sentences
    cutroom translate jobs/<id> --pick 1 --lang es --text translations/es.json [--voice]
        [--name STEM] [--layout fill|blur|facecam] [--cam x:y:w:h] [--hashtags "#a #b"]
    cutroom translate jobs/<id> --pick 1 --langs es,pt,de [--voice]

For a clip `cut.py` already made from the job's transcript with the fill,
blur, or facecam layout and no jump cuts. The words spoken between its start
and end are taken a sentence at a time, each sentence's translation is
spread evenly over the time the sentence took, and the language is rendered
as `edits/<name>_<lang>.mp4` at the same loudness, with
`edits/<name>_<lang>.post.md` holding the translated hook as post text.

The translation is given, not fetched: `--sentences` prints the clip's hook
and its sentences as JSON, whoever drives this translates them (an agent
does that well, and can be asked to keep a joke a joke), and `--text` takes
a file of the same shape, `{"hook": "...", "sentences": ["...", ...]}`, with
as many sentences as were printed.

`--langs` without `--text` asks a machine instead (Google's, through
deep-translator, with no account). That service refuses many requests from
a data center's address; a language any part of which could not be
translated is not rendered, and the script ends with status 1 saying so.

`--voice` has a stock text-to-speech voice (Microsoft's neural stock voices,
through edge-tts, which needs the network and no account) speak the
translated hook over the first 2.5 seconds, sped up to fit, with the clip's
own sound lowered under it. It is a stock voice and is never presented as
the person in the clip; it clones and imitates nobody.
"""

from __future__ import annotations

import argparse
import asyncio
import json
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


def spread(spoken: list[list[Word]], texts: list[str]) -> list[Word]:
    """Each sentence's translation as words spread evenly over the time the sentence took."""
    out: list[Word] = []
    for sentence, text in zip(spoken, texts):
        new = text.split()
        if not new:
            continue
        a, b = sentence[0]["s"], sentence[-1]["e"]
        step = (b - a) / len(new)
        out += [
            {"w": word, "s": a + i * step, "e": a + (i + 1) * step}
            for i, word in enumerate(new)
        ]
    return out


def machine(lang: str, hook: str, texts: list[str]) -> tuple[str, list[str]] | None:
    """The hook and the sentences translated by the machine, or nothing where it refused any of them."""
    from deep_translator import GoogleTranslator

    to = GoogleTranslator(source="auto", target=lang)
    out = []
    for text in [hook, *texts]:
        if not text.strip():
            out.append("")
            continue
        try:
            out.append((to.translate(text) or "").strip())
        except Exception as error:
            print(
                f"{lang}: the translation service refused ({str(error)[:160]})",
                file=sys.stderr,
            )
            return None
        if not out[-1]:
            print(
                f"{lang}: the translation service returned nothing for {text!r}",
                file=sys.stderr,
            )
            return None
    return out[0], out[1:]


def given(path: str, count: int) -> tuple[str, list[str]]:
    """The hook and the sentences of a `--text` file, which has to hold as many sentences as the clip.

    Raises:
        SystemExit: The file's sentences are not a list of `count` texts.
    """
    data = load_json(path)
    texts = data.get("sentences")
    if not isinstance(texts, list) or len(texts) != count:
        have = len(texts) if isinstance(texts, list) else "no"
        sys.exit(
            f"{path} has {have} sentences and the clip has {count}; --sentences prints them"
        )
    return str(data.get("hook", "")), [str(text) for text in texts]


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
    cmd = [tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{s0:.2f}", "-to", f"{e0:.2f}"]
    cmd += ["-i", src]
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
        cmd += ["-i", str(voice), "-filter_complex", v + ";" + sound]
        cmd += ["-map", "[vo]", "-map", "[ao]"]
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
    """Print what to translate, or render each language from its translation."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job")
    ap.add_argument("--pick", type=int, default=1)
    ap.add_argument(
        "--name", default="", help="the clip's file stem, default clip_<pick>"
    )
    ap.add_argument(
        "--sentences",
        action="store_true",
        help="print the hook and sentences to translate",
    )
    ap.add_argument("--lang", default="", help="the language of --text, such as es")
    ap.add_argument(
        "--text", default="", help='a translation: {"hook": "...", "sentences": [...]}'
    )
    ap.add_argument(
        "--langs", default="", help="languages to machine translate, such as es,pt,de"
    )
    ap.add_argument("--voice", action="store_true")
    ap.add_argument("--layout", choices=["fill", "blur", "facecam"])
    ap.add_argument("--cam")
    ap.add_argument(
        "--hook", help="the hook to translate, where it is not the clip's own"
    )
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
    spoken = sentences(words)
    texts = [" ".join(word["w"] for word in sentence) for sentence in spoken]
    if a.sentences:
        print(
            json.dumps({"hook": hook, "sentences": texts}, ensure_ascii=False, indent=1)
        )
        return
    if a.text and not a.lang:
        sys.exit("--text needs --lang, the language it is in")
    languages = (
        [a.lang] if a.text else [x.strip() for x in a.langs.split(",") if x.strip()]
    )
    if not languages:
        sys.exit("give --lang with --text, or --langs for a machine translation")
    source = f"Source: {meta.get('source_title') or ''} ({meta.get('source_channel') or ''})\n"
    refused = []
    for lang in languages:
        translated = given(a.text, len(texts)) if a.text else machine(lang, hook, texts)
        if translated is None:
            refused.append(lang)
            continue
        new_hook, new_texts = translated
        ass = out / f"{stem}_{lang}.ass"
        captions = build_ass(spread(spoken, new_texts), s0, e0, new_hook, CAP_Y[layout])
        ass.write_text(captions, encoding="utf-8")
        mp4 = out / f"{stem}_{lang}.mp4"
        voice = None
        if a.voice and new_hook:
            voice = make_voice(
                lang, new_hook, Path(tempfile.gettempdir()) / f"{stem}_{lang}_hook.mp3"
            )
        render(candidates["source"], s0, e0, layout, cam, ass, mp4, voice)
        post = post_block(lang, new_hook, a.hashtags.split(), meta.get("source_url"))
        text = "\n".join([source, "Read the translation before posting.\n", post])
        (out / f"{stem}_{lang}.post.md").write_text(text, encoding="utf-8")
        print(mp4)
        print(out / f"{stem}_{lang}.post.md")
    if refused:
        sys.exit(
            f"not rendered, for want of a translation: {', '.join(refused)}. Translate them and pass --text."
        )


if __name__ == "__main__":
    main()
