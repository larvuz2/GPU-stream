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
"""Cut a horizontal explainer, 1920x1080: kept parts of a recording under a narration, with subtitles and titles.

    cutroom explainer --src footage.mp4 --segments "63.5-66.5,84-92@2,..." \\
        --lines narration/lines.json --voice narration/voice_warm.wav --out edits/name.mp4 \\
        [--title "How the map works" --title-start 0] [--tag "DEV DIARY"] \\
        [--title-words "THE@4.72,CLOWN@5.18,|GOT@5.66,MEANER@5.92" --title-end 7.0] \\
        [--music music.mp3 --music-gain 0.16] [--bed-gain 0.2] [--lang en]

The form of a dev diary, a tutorial, a walkthrough: one calm voice over
screen footage, the dull stretches sped up and the point shown at speed.

- `--segments` are the parts of `--src` kept, in source seconds, in the order
  they play; `a-b@3` plays one at three times the speed and `@0.5` at half. A
  yellow badge ("3× SPEED") shows over every part that is sped up.
- `--lines` and `--voice` are what `narrate.py` wrote. Each line becomes
  sentence subtitles at the bottom, raised to clear an interface's lower
  edge: one sentence at a time, at most 84 characters, on two lines, each
  shown for a share of the line's time in proportion to its length.
- `--title` is a small title at the top left for 4.6 s from `--title-start`,
  with `--tag` on a colored label above it. Both are off unless given.
- `--title-words` throws a headline at the screen word by word, large and
  centered, each word slamming in at its own second (the second the voice
  says it, which `words.py` reads off the narration), all fading together at
  `--title-end`. `|` before a word starts a new line. The subtitle of the
  line the headline repeats is left out.
- `--music` loops under everything, faded in and out, and ducks further
  whenever the voice speaks; the footage's own sound stays as a quiet bed.

The headline is laid out here, with Pillow measuring Inter Black, since
each word is its own subtitle event at its own place. libass draws that face
at 0.828 of the advance width Pillow reports at the same size, which is the
ratio of the font's em to its ascent plus descent, and was measured.

The finished file is listened to for swears by two speech models, and the
script exits with status 1 if any is heard.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import subtitles_path
from cut import Segment, concat_segments, esc, parse_segments, ts

W, H = 1920, 1080
INTER_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
# libass's width of Inter Black over Pillow's advance width at the same size
LIBASS_WIDTH = 0.828

Chunk = tuple[float, float, str]


def chunks(text: str, a: float, b: float, max_chars: int = 84) -> list[Chunk]:
    """A narration line as subtitle chunks: by sentence, then by words, each timed by its length."""
    parts = [p for p in re.split(r"(?<=[.?!:])\s+", text.strip()) if p]
    out = []
    for part in parts:
        while len(part) > max_chars:
            cut = part.rfind(" ", 0, max_chars)
            out.append(part[:cut])
            part = part[cut + 1 :]
        out.append(part)
    total = sum(len(x) for x in out) or 1
    at, timed = a, []
    for part in out:
        length = (b - a) * len(part) / total
        timed.append((at, at + length, part))
        at += length
    return timed


def wrap2(text: str, width: int = 46) -> str:
    """Text over `width` characters broken into two lines of about equal length, at a space."""
    if len(text) <= width:
        return text
    mid = len(text) // 2
    left, right = text.rfind(" ", 0, mid + 6), text.find(" ", mid - 6)
    cut = left if left > 0 and (right < 0 or mid - left <= right - mid) else right
    return text[:cut] + "\\N" + text[cut + 1 :] if cut > 0 else text


def parse_title_words(spec: str) -> list[tuple[str, float, bool]]:
    """`"THE@4.7,|CLOWN@5.2"` as (word, second, starts a new line) for each word."""
    out = []
    for item in (x.strip() for x in spec.split(",") if x.strip()):
        word, _, at = item.rpartition("@")
        out.append((word.lstrip("|"), float(at), word.startswith("|")))
    return out


def big_words(
    spec: str, end: float, size: int = 232, y: int = 470, max_w: int = 1760
) -> tuple[list[str], float]:
    """The headline's subtitle events, one per word, and the second the first word lands.

    The words are laid out centered over lines no wider than `max_w`, around
    the height `y`. Each slams in at its own second (165% and tilted, through
    96%, to 100% in 230 ms) and all fade out together at `end`.
    """
    from PIL import ImageFont

    words = parse_title_words(spec)
    try:
        font = ImageFont.truetype(INTER_BLACK, size)
    except OSError:
        font = ImageFont.load_default()
    space = font.getlength(" ") * LIBASS_WIDTH
    lines: list[tuple[list[tuple[str, float, float]], float]] = []
    current: list[tuple[str, float, float]] = []
    width = 0.0
    for word, at, new_line in words:
        length = font.getlength(word) * LIBASS_WIDTH
        if current and (new_line or width + space + length > max_w):
            lines.append((current, width))
            current, width = [], 0.0
        width = width + (space if current else 0) + length
        current.append((word, at, length))
    if current:
        lines.append((current, width))
    line_height = size * 1.05
    top = y - line_height * (len(lines) - 1) / 2
    events = []
    for index, (line, line_width) in enumerate(lines):
        x = W / 2 - line_width / 2
        for word, at, length in line:
            cx, cy = x + length / 2, top + index * line_height
            events.append(
                f"Dialogue: 3,{ts(at)},{ts(end)},Big,,0,0,0,,{{\\an5\\pos({cx:.0f},{cy:.0f})\\fad(40,220)"
                f"\\fscx165\\fscy165\\frz-6\\t(0,140,\\fscx96\\fscy96\\frz1)\\t(140,230,\\fscx100\\fscy100\\frz0)}}{esc(word)}"
            )
            x += length + space
    return events, (min(at for _, at, _ in words) if words else 0.0)


def build_ass(
    lines: list[list[Any]],
    title: str,
    tag: str,
    fast: list[tuple[float, float, float]],
    t0: float = 0.0,
    words: str = "",
    words_end: float = 0.0,
) -> str:
    """The explainer's subtitle file: sentence subtitles, the tag and title, the headline, and the speed badges.

    `fast` is (start, end, speed) for each sped-up stretch of the output.
    A narration line that starts within the headline's time, from 0.8 s
    before its first word, gets no subtitle: the headline already says it.
    """
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter SemiBold,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,3,14,0,2,200,200,150,1
Style: Tag,Inter ExtraBold,30,&H00FFFFFF,&H00FFFFFF,&H007F45E8,&H007F45E8,-1,0,0,0,100,100,2,0,3,12,0,7,150,64,190,1
Style: Title,Inter Black,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,3,16,0,7,150,64,246,1
Style: Big,Inter Black,232,&H0042C5F4,&H0042C5F4,&H0014233B,&HA0000000,0,0,0,0,100,100,0,0,1,14,8,5,40,40,0,1
Style: Badge,Inter ExtraBold,30,&H00000000,&H00000000,&H0000E5FF,&H0000E5FF,-1,0,0,0,100,100,2,0,3,10,0,8,64,64,110,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    words_start = None
    if words:
        headline, words_start = big_words(words, words_end)
        events += headline
    for a, b, text, *_ in lines:
        if words_start is not None and words_start - 0.8 <= a <= words_end:
            continue
        for start, end, chunk in chunks(text, a, b):
            events.append(
                f"Dialogue: 0,{ts(start)},{ts(end)},Sub,,0,0,0,,{{\\fad(80,80)}}{wrap2(esc(chunk))}"
            )
    if tag:
        events.append(
            f"Dialogue: 1,{ts(t0)},{ts(t0 + 4.6)},Tag,,0,0,0,,{{\\fad(150,250)}}{esc(tag)}"
        )
    if title:
        events.append(
            f"Dialogue: 1,{ts(t0)},{ts(t0 + 4.6)},Title,,0,0,0,,{{\\fad(150,250)}}{esc(title)}"
        )
    for a, b, speed in fast:
        events.append(f"Dialogue: 1,{ts(a)},{ts(b)},Badge,,0,0,0,,{speed:g}× SPEED")
    return header + "\n".join(events) + "\n"


def fast_parts(segs: list[Segment]) -> tuple[list[tuple[float, float, float]], float]:
    """The sped-up stretches of the output as (start, end, speed), and the output's whole length."""
    fast, at = [], 0.0
    for a, b, speed in segs:
        length = (b - a) / speed
        if speed > 1:
            fast.append((round(at, 2), round(at + length, 2), speed))
        at += length
    return fast, at


def audio_graph(bed_gain: float, music_gain: float | None, total: float) -> str:
    """The sound's filter graph, ending in `[ao]` at -14 LUFS: the footage as a bed, the voice, and music if any.

    Input 0 is the joined footage and 1 the voice; with `music_gain`, input
    2 is the music, looped by the caller. The music is faded in over 1.2 s
    and out over the last 1.8 s, and pushed down by a compressor keyed by the
    voice whenever it speaks.
    """
    graph = f"[0:a]volume={bed_gain}[bed];[1:a]apad[vox];"
    if music_gain is None:
        return (
            graph
            + "[bed][vox]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
        )
    return graph + (
        f"[vox]asplit[vox][key];[2:a]aresample=48000,volume={music_gain},afade=t=in:d=1.2,"
        f"afade=t=out:st={max(0, total - 1.8):.2f}:d=1.8[mus];"
        f"[mus][key]sidechaincompress=threshold=0.015:ratio=5:attack=40:release=450[md];"
        f"[bed][vox][md]amix=inputs=3:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
    )


def main() -> None:
    """Join the parts, burn the text, mix the sound, and listen to the result."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--segments", required=True)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--title", default="", help="a small title at the top left for 4.6 s"
    )
    ap.add_argument("--title-start", type=float, default=0.0)
    ap.add_argument(
        "--tag", default="", help='a label above the title, such as "DEV DIARY"'
    )
    ap.add_argument(
        "--bed-gain", type=float, default=0.2, help="volume of the footage's own sound"
    )
    ap.add_argument("--lang", default="en")
    ap.add_argument(
        "--title-words",
        default="",
        help='a large centered headline thrown word by word: "THE@4.72,CLOWN@5.18,..."',
    )
    ap.add_argument("--title-end", type=float, default=0.0)
    ap.add_argument(
        "--music",
        default="",
        help="music kept under the voice and ducked while it speaks",
    )
    ap.add_argument("--music-gain", type=float, default=0.16)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    segs = parse_segments(a.segments)
    joined = concat_segments(a.src, segs, out.with_suffix(".src.mp4"))
    fast, total = fast_parts(segs)
    lines = json.loads(Path(a.lines).read_text(encoding="utf-8"))
    ass = out.with_suffix(".ass")
    ass.write_text(
        build_ass(
            lines, a.title, a.tag, fast, a.title_start, a.title_words, a.title_end
        ),
        encoding="utf-8",
    )
    picture = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,"
        f"subtitles='{subtitles_path(ass)}'[vo];"
    )
    inputs = ["-i", str(joined), "-i", a.voice]
    if a.music:
        inputs += ["-stream_loop", "-1", "-i", a.music]
    graph = picture + audio_graph(a.bed_gain, a.music_gain if a.music else None, total)
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph]
    cmd += ["-map", "[vo]", "-map", "[ao]"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart"]
    subprocess.run([*cmd, str(out)], check=True)
    from clean import heard_bad

    left = heard_bad(out, language=a.lang) + heard_bad(
        out, model_name="small", language=a.lang
    )
    heard = [word for _, _, word in left] or "none"
    print(f"{out} {total:.1f}s, fast parts {fast}, swears heard: {heard}")
    if left:
        sys.exit(1)


if __name__ == "__main__":
    main()
