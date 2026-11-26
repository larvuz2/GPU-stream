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
"""Cut one moment of a job into a finished vertical clip: 1080x1920, 30 fps, captions, a hook, -14 LUFS.

    cutroom cut jobs/<id> --pick 1 [--layout fill|blur|focus|facecam|react] [--hook "TEXT"]
        [--segments "12.3-20,23.8-27.3,7.3-9.3@0.5"] [--focus "0:0.62,8:0.45"] [--hook-secs 0]
        [--lines lines.json] [--lines-time source|output] [--voice voice.wav] [--bed-gain 0.3]
        [--cam auto|x:y:w:h] [--title "TEXT" --title-style box|outline --title-secs 0]
        [--captions word|bubble|none] [--cap-y 1180] [--trim-bottom 0.1] [--lang en] [--name STEM]

A job is what `moments.py` made of a source: `candidates.json` names the
footage and the moments, `transcript.json` its words. The clip is written to
`jobs/<id>/edits/<name>.mp4` with its captions (`.ass`) and its facts
(`.json`), which `check.py` and `translate.py` read.

The layouts:

- `blur`: the whole picture centered over a blurred, darkened copy of
  itself. The default, since it never crops the action.
- `fill`: the picture cropped to fill the frame.
- `focus`: a 4:5 window on the action over the blurred copy, with the hook
  above it for the whole clip. `--focus` says where the window looks, as
  `output second:center x` keyframes it glides between.
- `facecam`: the presenter's camera on the top 38%, the rest below.
- `react`: the face on a 730 px panel on top, the screen below, a title on
  the seam. `--cam auto` finds the camera (`facecam.py`).

`--segments` keeps parts of the source, in source seconds, joined with jump
cuts; `a-b@2` plays one at twice the speed and `@0.5` at half. The parts are
cut one by one and then joined (`concat_segments`), so memory stays flat
however long the source is, and every layout then works on the joined file.

Captions are word by word, up to three words at a time, the spoken one in
yellow, from the transcript or from `--lines` (`[[start, end, "text",
"RRGGBB"?], ...]`, the fourth item a speaker's color). `--lines-time output`
says the times are already on the finished clip's timeline, which is what
`narrate.py` writes; `--voice` is then the narration it mixed, laid over the
footage's own sound kept as a bed (`--bed-gain`, 0.3).

Clean language is on unless `--allow-profanity`: swears are left out of the
captions and muted in the sound (`clean.py`), and the finished clip is
listened to again, by two models, and muted further until nothing is heard
or four rounds have passed, in which case the script says the clip must not
be posted.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from common import (
    ffprobe,
    load_json,
    run,
    save_json,
    subtitles_path,
    tool,
    video_stream,
)

W, H = 1080, 1920
# The face panel of the react layout is this tall, which is also where its seam is
TOP = 730
GAME_H = H - TOP
# Where captions are centered, by layout, in pixels from the top
CAP_Y = {"fill": 1380, "blur": 1460, "facecam": 1120, "react": 1560, "focus": 1420}
# The focus layout's 4:5 window, placed with the title above it, both inside a phone app's safe area
FOCUS_Y, FOCUS_H = 320, 1350
FONTS = (
    "Arial Black",
    "Anton",
    "Montserrat Black",
    "Inter Black",
    "Archivo Black",
    "DejaVu Sans",
)

Segment = tuple[float, float, float]
Word = dict[str, Any]

_SLURS = re.compile(
    r"\b(nigg\w*|n[i1]gg?a\w*|f[a@]gg?\w*|retard\w*|tranny\w*|chink\w*|spic\w*|kike\w*)\b",
    re.I,
)
# One word's vowel is written as a class so that a spell checker does not read the pattern as a typo
_SWEARS = re.compile(
    r"\b(fuck\w*|motherfuck\w*|shit\w*|bitch\w*|c[u]nt\w*|dick\w*|pussy\w*|asshole\w*|bastard\w*|whore\w*|slut\w*)\b",
    re.I,
)


def default_font() -> str:
    """The heaviest of the caption faces this machine has, in the order the look was settled with.

    On the Cut Room's image that is Inter Black. A machine without
    fontconfig is asked for the first of them, which its renderer then
    substitutes.
    """
    if not shutil.which("fc-list"):
        return FONTS[0]
    listing = subprocess.run(
        ["fc-list", ":", "family"], capture_output=True, text=True, check=False
    )
    have = listing.stdout.lower()
    return next((font for font in FONTS if font.lower() in have), FONTS[0])


def ts(seconds: float) -> str:
    """Seconds as an ASS timestamp, `h:mm:ss.cc`."""
    seconds = max(0, seconds)
    hours = int(seconds // 3600)
    minutes = int(seconds % 3600 // 60)
    return f"{hours}:{minutes:02d}:{seconds % 60:05.2f}"


def _mask(match: re.Match[str]) -> str:
    word = match.group(0)
    return word[0] + "*" * (len(word) - 1)


def clean(text: str, profanity: bool = False) -> str:
    """Text with slurs masked to their first letter, and hard swears too unless `profanity`."""
    text = _SLURS.sub(_mask, text)
    return text if profanity else _SWEARS.sub(_mask, text)


def esc(text: str) -> str:
    """Text made safe to put in an ASS event: no override braces, no backslashes, one line."""
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def wrap(text: str, width: int) -> list[str]:
    """Text broken into lines of at most `width` characters, at spaces."""
    lines, current = [], ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    return lines + ([current] if current else [])


def build_ass(
    words: list[Word],
    s0: float,
    e0: float,
    hook: str,
    cap_y: int,
    title: tuple[str, str, int, float] | None = None,
    caps: str = "word",
    profanity: bool = False,
    hook_secs: float = 2.6,
    hook_y: int = 170,
    hook_fs: int = 68,
    font: str | None = None,
) -> str:
    """The clip's subtitle file: word-by-word captions, the hook box, and a reaction title.

    `words` are on the source's timeline; those between `s0` and `e0` are
    shown, moved to start at zero. They are grouped three at a time, a group
    ending at punctuation, a pause over 0.6 s, or a change of speaker color,
    and each group is shown once per word with that word in yellow and a
    small pop on the group's first. `caps` `bubble` shows each group once as
    a white speech bubble instead. `title` is (style, text, y, seconds) and
    replaces the hook; a `hook_secs` or title seconds of zero means the whole
    clip.
    """
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial Black,92,&H00FFFFFF,&H0000E5FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1
Style: Hook,Arial Black,68,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,8,70,70,170,1
Style: TitleBox,Arial Black,66,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,1,0,0,5,40,40,0,1
Style: TitleOut,Arial Black,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,9,2,8,50,50,0,1
Style: Bubble,Arial,58,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,16,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    # Slurs are masked whatever the clean-language rule says
    shown = [
        dict(w, w=clean(w["w"], True)) for w in words if s0 <= w["s"] < e0 and w["w"]
    ]
    if not profanity:
        from clean import drop_bad

        shown = drop_bad(shown)
    groups: list[list[Word]] = []
    current: list[Word] = []
    for word in shown:
        if current and (
            len(current) == 3
            or word["s"] - current[-1]["e"] > 0.6
            or current[-1]["w"][-1:] in ".?!,"
            or word.get("c") != current[-1].get("c")
        ):
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)
    hook_end = ((e0 - s0) if hook_secs <= 0 else hook_secs) if hook else 0
    for index, group in enumerate(groups):
        group_end = (
            groups[index + 1][0]["s"]
            if index + 1 < len(groups)
            else group[-1]["e"] + 0.4
        )
        group_end = min(group_end, group[-1]["e"] + 0.8)
        for k, word in enumerate(group):
            a = word["s"] - s0
            b = (group[k + 1]["s"] - s0) if k + 1 < len(group) else group_end - s0
            if b <= a:
                continue
            parts = []
            base = "&H00FFFFFF&"
            if group[0].get("c"):
                # A speaker's color, RRGGBB, in ASS's order; the spoken word is still yellow
                c6 = group[0]["c"]
                base = f"&H00{c6[4:6]}{c6[2:4]}{c6[0:2]}&"
            for j, other in enumerate(group):
                text = esc(other["w"].upper())
                parts.append(
                    "{\\c&H0000E5FF&}" + text + "{\\c" + base + "}" if j == k else text
                )
            if base != "&H00FFFFFF&":
                parts[0] = "{\\c" + base + "}" + parts[0]
            pop = "{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}" if k == 0 else ""
            if caps == "bubble":
                if k == 0:
                    text = esc(" ".join(x["w"] for x in group)).strip()
                    text = text[:1].upper() + text[1:]
                    events.append(
                        f"Dialogue: 0,{ts(a)},{ts(group_end - s0)},Bubble,,0,0,0,,{{\\pos({W // 2},{cap_y})}}{pop}{text}"
                    )
                continue
            events.append(
                f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\pos({W // 2},{cap_y})}}{pop}{' '.join(parts)}"
            )
    if title:
        style, text, title_y, seconds = title
        end = (e0 - s0) if seconds <= 0 else seconds
        body = "\\N".join(wrap(esc(text), 26 if style == "box" else 24))
        if style == "box":
            events.append(
                f"Dialogue: 2,{ts(0)},{ts(end)},TitleBox,,0,0,0,,{{\\pos({W // 2},{title_y})}}{body}"
            )
        else:
            events.append(
                f"Dialogue: 2,{ts(0)},{ts(end)},TitleOut,,0,0,0,,{{\\pos({W // 2},{title_y})\\an8}}{body}"
            )
        hook = ""
    if hook:
        body = "\\N".join(wrap(esc(hook), 22 if hook_fs <= 70 else 19))
        events.append(
            f"Dialogue: 1,{ts(0)},{ts(hook_end)},Hook,,0,0,0,,{{\\an8\\fs{hook_fs}\\pos({W // 2},{hook_y})"
            f"\\fad(0,180)\\fscx92\\fscy92\\t(0,120,\\fscx100\\fscy100)}}{body}"
        )
    return (
        header.replace("Arial Black", font or default_font()) + "\n".join(events) + "\n"
    )


def focus_x(keys: str, cw: str) -> str:
    """The crop's x as an FFmpeg expression gliding between `t:cx,t:cx` keyframes.

    A keyframe is an output second and the window's center as a fraction of
    the picture's width; before the first and after the last the window
    stays. Commas are escaped for a filter graph.
    """
    points = sorted(
        (float(a), float(b)) for a, b in (key.split(":") for key in keys.split(","))
    )

    def px(center: float) -> str:
        return f"(iw*{center:.4f}-{cw}/2)"

    expression = px(points[-1][1])
    for (t0, c0), (t1, c1) in reversed(list(zip(points, points[1:]))):
        expression = f"if(lt(t,{t1}),{px(c0)}+({px(c1)}-{px(c0)})*(t-{t0})/{max(t1 - t0, 0.01)},{expression})"
    expression = f"if(lt(t,{points[0][0]}),{px(points[0][1])},{expression})"
    return f"max(0,min(iw-{cw},{expression}))".replace(",", "\\,")


def parse_segments(spec: str) -> list[Segment]:
    """`"12-20,7.3-9.3@0.5"` as [(12, 20, 1.0), (7.3, 9.3, 0.5)]: source seconds, then a speed."""
    out = []
    for part in (x.strip() for x in spec.split(",") if x.strip()):
        span, _, speed = part.partition("@")
        a, b = (float(x) for x in span.split("-"))
        out.append((a, b, float(speed) if speed else 1.0))
    return out


def lines_to_words(lines: list[list[Any]]) -> list[Word]:
    """Caption lines, `[[start, end, "text", "RRGGBB"?], ...]`, as words spread evenly over each line's time."""
    out: list[Word] = []
    for a, b, text, *color in lines:
        words = text.split()
        step = (b - a) / max(len(words), 1)
        out += [
            dict(
                {
                    "w": word,
                    "s": round(a + i * step, 2),
                    "e": round(a + (i + 1) * step, 2),
                },
                **({"c": color[0]} if color else {}),
            )
            for i, word in enumerate(words)
        ]
    return out


def concat_segments(src: str | Path, segs: Sequence[Segment], dst: str | Path) -> Path:
    """Join the kept parts of a source into one near-lossless file, each at its speed.

    Each part is cut on its own with input seeking and a 30 ms fade at both
    ends of its sound, then the parts are joined without encoding again. A
    source with no sound gets silence, so what follows always has an audio
    stream to work on.
    """
    dst = Path(dst)
    parts = dst.with_suffix(".parts")
    parts.mkdir(exist_ok=True)
    has_audio = any(
        s.get("codec_type") == "audio" for s in ffprobe(src).get("streams", [])
    )
    listing = []
    for index, (x, y, speed) in enumerate(segs):
        part = parts / f"p{index:03d}.mp4"
        vf = f"setpts=(PTS-STARTPTS)/{speed},fps=30"
        af = (f"atempo={speed}," if speed != 1 else "") + (
            f"afade=t=in:d=0.03,afade=t=out:st={max(0, (y - x) / speed - 0.03):.3f}:d=0.03"
        )
        cmd = [
            tool("ffmpeg"),
            "-y",
            "-v",
            "error",
            "-ss",
            f"{x:.3f}",
            "-to",
            f"{y:.3f}",
            "-i",
            str(src),
        ]
        if not has_audio:
            cmd += [
                "-f",
                "lavfi",
                "-t",
                f"{(y - x):.3f}",
                "-i",
                "anullsrc=r=48000:cl=stereo",
            ]
        cmd += [
            "-vf",
            vf,
            "-af",
            af,
            "-map",
            "0:v",
            "-map",
            "0:a" if has_audio else "1:a",
        ]
        cmd += [
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "12",
            "-pix_fmt",
            "yuv420p",
        ]
        cmd += ["-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", str(part)]
        run(cmd)
        listing.append(f"file '{part.resolve()}'")
    (parts / "list.txt").write_text("\n".join(listing) + "\n")
    join = [tool("ffmpeg"), "-y", "-v", "error", "-f", "concat", "-safe", "0"]
    run([*join, "-i", str(parts / "list.txt"), "-c", "copy", str(dst)])
    for file in parts.iterdir():
        file.unlink()
    parts.rmdir()
    return dst


def remap_words(words: list[Word], segs: Sequence[Segment]) -> tuple[list[Word], float]:
    """Words moved onto the timeline the kept parts make, and that timeline's length."""
    out: list[Word] = []
    offset = 0.0
    for a, b, speed in segs:
        out += [
            dict(
                w,
                s=round(offset + (w["s"] - a) / speed, 2),
                e=round(offset + (min(w["e"], b) - a) / speed, 2),
            )
            for w in words
            if a <= w["s"] < b
        ]
        offset += (b - a) / speed
    return out, offset


def even(n: float) -> int:
    """A size rounded down to an even number of pixels, which the encoder needs."""
    return int(n) // 2 * 2


def video_filter(
    layout: str,
    cam: str,
    ass: str | Path,
    band: tuple[int, int, float] | None = None,
    cam_side: str = "right",
    src: tuple[int, int] | None = None,
    game_x: float | None = None,
    face_expr: tuple[int, int, str, str] | None = None,
    inp: str = "[0:v]",
    focus: str | None = None,
    trim_bottom: float = 0.0,
) -> str:
    """The filter graph of a layout with its captions burned in, ending in `[vo]`.

    `cam` is the camera's box as `x:y:w:h` fractions for the facecam and
    react layouts; `face_expr` replaces it with a crop that follows the face.
    `band` draws the white band of a boxed title at (y, height, seconds).
    `trim_bottom` drops that fraction of the source's bottom first, which
    removes burned-in subtitles; in the react layout it trims the lower
    panel only. `translate.py` renders its versions with this too.
    """
    if layout == "fill":
        v = f"[0:v]scale=-2:{H},crop={W}:{H}[v]"
    elif layout == "focus":
        cw = "floor(ih*0.8/2)*2"
        v = (
            f"[0:v]split[a][b];[a]scale=-2:{H},crop={W}:{H},boxblur=30:3,eq=brightness=-0.28[bg];"
            f"[b]crop={cw}:ih:{focus_x(focus or '0:0.5', cw)}:0,scale={W}:{FOCUS_H},setsar=1[fg];"
            f"[bg][fg]overlay=0:{FOCUS_Y}[v]"
        )
    elif layout == "blur":
        v = (
            f"[0:v]split[a][b];[a]scale=-2:{H},crop={W}:{H},boxblur=24:2,eq=brightness=-0.08[bg];"
            f"[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2-80[v]"
        )
    elif layout == "react":
        sw, sh = src
        if face_expr:
            cw, ch, ex, ey = face_expr
            top = f"crop={cw}:{ch}:{ex}:{ey}"
        else:
            x, y, w, h = map(float, cam.split(":"))
            cw, ch = even(sw * w), even(sh * h)
            top = f"crop={cw}:{ch}:{even(sw * x)}:{even(sh * y)}"
        gw = even(sw * GAME_H / sh) if sw * GAME_H / sh >= W else W
        gx = game_x if game_x is not None else ((gw - W) if cam_side == "left" else 0)
        pre = ""
        if trim_bottom > 0:
            gh_src = sh * (1 - trim_bottom)
            gw2 = even(sw * GAME_H / gh_src) if sw * GAME_H / gh_src >= W else W
            gx = min(gw2 - W, gx * gw2 / gw)
            gw = gw2
            pre = f"crop=iw:floor(ih*{1 - trim_bottom:.3f}/2)*2:0:0,"
            trim_bottom = 0.0
        v = (
            f"[0:v]split[a][b];[a]{top},scale={W}:{TOP}:force_original_aspect_ratio=increase,crop={W}:{TOP},setsar=1[cam];"
            f"[b]{pre}scale={gw}:{GAME_H},crop={W}:{GAME_H}:{even(gx)}:0,setsar=1[game];[cam][game]vstack[v]"
        )
        if band:
            y0, band_height, seconds = band
            enable = f":enable='lte(t,{seconds})'" if seconds > 0 else ""
            v = (
                v[:-3]
                + f"[v0];[v0]drawbox=x=0:y={y0}:w=iw:h={band_height}:color=white@1:t=fill{enable}[v]"
            )
    else:
        x, y, w, h = map(float, cam.split(":"))
        v = (
            f"[0:v]split[a][b];[a]crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},scale={W}:{int(H * 0.38)}:force_original_aspect_ratio=increase,"
            f"crop={W}:{int(H * 0.38)}[cam];[b]scale=-2:{H - int(H * 0.38)},crop={W}:{H - int(H * 0.38)}[game];[cam][game]vstack[v]"
        )
    sub = subtitles_path(ass)
    if trim_bottom > 0:
        v = f"{inp}crop=iw:floor(ih*{1 - trim_bottom:.3f}/2)*2:0:0[trim];" + v.replace(
            "[0:v]", "[trim]", 1
        )
        return v + f";[v]fps=30,subtitles='{sub}'[vo]"
    return v.replace("[0:v]", inp) + f";[v]fps=30,subtitles='{sub}'[vo]"


def game_offset(
    video: str | Path,
    s0: float,
    e0: float,
    src: tuple[int, int],
    cam_box: Sequence[float],
) -> int | None:
    """The x offset of the react layout's lower panel that avoids static overlays and the camera.

    The panel is a 1080-wide crop of the scaled source. Static overlays
    (viewer counters, alerts, chat boxes) are pixels that barely change
    across sampled frames but carry edges. The crop stays near the center,
    where subtitles and the action sit, and moves off it only when that
    clearly removes an overlay; it never shows the camera twice. Nothing is
    returned where too few frames could be read.
    """
    import cv2
    import numpy as np

    sw, sh = src
    gw = even(sw * GAME_H / sh)
    if gw <= W:
        return 0
    capture = cv2.VideoCapture(str(video))
    frames = []
    for k in range(12):
        capture.set(cv2.CAP_PROP_POS_MSEC, (s0 + (e0 - s0) * (k + 0.5) / 12) * 1000)
        ok, frame = capture.read()
        if ok:
            frames.append(
                cv2.resize(
                    cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (gw, GAME_H)
                ).astype(np.float32)
            )
    capture.release()
    if len(frames) < 4:
        return None
    stack = np.stack(frames)
    std = stack.std(0)
    median = np.median(stack, 0)
    edges = cv2.Canny(median.astype(np.uint8), 60, 160) > 0
    bad = (std < 6) & cv2.dilate(
        edges.astype(np.uint8), np.ones((9, 9), np.uint8)
    ).astype(bool)
    x, y, w, h = cam_box
    bad[int(y * GAME_H) : int((y + h) * GAME_H), int(x * gw) : int((x + w) * gw)] = True
    columns = bad.sum(0).astype(np.float64)
    cs = np.concatenate([[0], np.cumsum(columns)])
    best, best_x = None, 0
    cam_columns = np.zeros(gw)
    cam_columns[int(x * gw) : int((x + w) * gw)] = 1
    cc = np.concatenate([[0], np.cumsum(cam_columns)])
    for ox in range(0, gw - W + 1, 8):
        if cc[ox + W] - cc[ox] > 0 and (cc[-1] < gw - W):
            continue
        cost = (cs[ox + W] - cs[ox]) * 0.2 + abs(ox - (gw - W) / 2) * GAME_H * 0.05
        if best is None or cost < best:
            best, best_x = cost, ox
    return best_x


def arguments() -> argparse.Namespace:
    """The command line."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job")
    ap.add_argument("--pick", type=int, default=1)
    ap.add_argument(
        "--layout",
        choices=["fill", "blur", "focus", "facecam", "react"],
        default="blur",
    )
    ap.add_argument(
        "--title",
        default="",
        help="react layout: the title on the seam, with CAPS on two or three key words",
    )
    ap.add_argument("--title-style", choices=["box", "outline"], default="box")
    ap.add_argument("--title-secs", type=float, default=0, help="0 = whole clip")
    ap.add_argument("--captions", choices=["word", "bubble", "none"], default="word")
    ap.add_argument("--hook", default="")
    ap.add_argument(
        "--allow-profanity",
        action="store_true",
        help="keep swear words in sound and captions (off by default)",
    )
    ap.add_argument(
        "--cam", default="auto", help="auto (find the webcam) or x:y:w:h fractions"
    )
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    ap.add_argument(
        "--segments",
        default="",
        help='jump cuts in source seconds, e.g. "12.3-20,23.8-27.3,29.5-41.8"',
    )
    ap.add_argument(
        "--focus",
        default="0:0.5",
        help='focus layout: "t:cx,..." keyframes, output seconds : center x fraction',
    )
    ap.add_argument(
        "--hook-secs",
        type=float,
        default=None,
        help="seconds the hook stays; 0 = whole clip (default for focus)",
    )
    ap.add_argument("--name", default="", help="output file stem, default clip_<pick>")
    ap.add_argument(
        "--lines",
        default="",
        help='json [[start, end, "text"], ...] in source seconds: captions written out',
    )
    ap.add_argument(
        "--lines-time",
        choices=["source", "output"],
        default="source",
        help="output: --lines times are already on the finished clip's timeline (narrate.py's lines.json)",
    )
    ap.add_argument(
        "--voice",
        default="",
        help="narration track (narrate.py's voice.wav), mixed over the clip's own sound",
    )
    ap.add_argument(
        "--lang",
        default="en",
        help="language spoken in the clip, for the swear check (en, es, ...)",
    )
    ap.add_argument(
        "--cap-y",
        type=int,
        default=0,
        help="caption center height in px (default per layout); move it off on-screen text",
    )
    ap.add_argument(
        "--bed-gain",
        type=float,
        default=0.3,
        help="volume of the clip's own sound under --voice",
    )
    ap.add_argument(
        "--trim-bottom",
        type=float,
        default=0.0,
        help="fill, blur, focus, react: drop this fraction of the source's bottom (react: lower panel only)",
    )
    ap.add_argument(
        "--font",
        default="",
        help="caption and hook face, e.g. 'Archivo Black' (default: the heaviest installed, Inter Black)",
    )
    return ap.parse_args()


def main() -> None:
    """Cut the clip, check it for swears, and write its facts beside it."""
    a = arguments()
    job = Path(a.job)
    candidates = load_json(job / "candidates.json")
    pick = next(x for x in candidates["candidates"] if x["n"] == a.pick)
    s0 = a.start if a.start is not None else pick["start"]
    e0 = a.end if a.end is not None else pick["end"]
    words = load_json(job / "transcript.json")
    if a.lines:
        words = lines_to_words(load_json(a.lines))
    # Lines already on the output's timeline are placed after the cut is known
    out_words = words if (a.lines and a.lines_time == "output") else None
    segs = parse_segments(a.segments)
    out = job / "edits"
    out.mkdir(exist_ok=True)
    stem = a.name or f"clip_{a.pick}"
    orig_source = candidates["source"]
    source = orig_source
    if segs:
        source = str(concat_segments(orig_source, segs, out / f"{stem}.src.mp4"))
        words, total = remap_words(words, segs)
        s0, e0 = 0.0, total
    if out_words is not None:
        words = [dict(w, s=w["s"] + s0, e=w["e"] + s0) for w in out_words]
    layout, cam, side = a.layout, a.cam, "right"
    face_expr = None
    if layout in ("react", "facecam") and cam == "auto":
        from facecam import face_crop_expr, find_cam, has_gameplay, inner_edges

        found = find_cam(source, s0, e0)
        if layout == "react" and found.get("mode") not in ("cam", "face"):
            sys.exit(
                f"skipped: no presenter's face over the screen in this moment ({found.get('mode')}: {found.get('reason', '')}). "
                "The react layout needs the screen with the camera as a separate box. Pick another moment or source."
            )
        if layout == "react":
            if not has_gameplay(source, s0, e0, found["box"]):
                sys.exit(
                    "skipped: the area outside the webcam is not screen footage (the same scene, or nothing on screen). "
                    "Pick a moment where the screen is shown."
                )
            if found.get("mode") == "face" and found.get("face_track"):
                stream = video_stream(source)
                sw_, sh_ = int(stream["width"]), int(stream["height"])
                bounds = inner_edges(source, s0, e0, found["face"], sw_, sh_)
                print(
                    f"facecam: cam borders L{bounds[0]} T{bounds[1]} R{bounds[2]} B{bounds[3]} px"
                )
                crop = face_crop_expr(
                    found["face_track"], sw_, sh_, W, TOP, bounds=bounds
                )
                face_expr = (crop["w"], crop["h"], crop["x"], crop["y"])
                print(
                    f"facecam: no clean cam frame, tracking the face ({found.get('summary', '')})"
                )
        if found.get("mode") in ("cam", "face"):
            box = list(found["box"])
            if found["mode"] == "face":
                # No webcam frame: the face crop is widened so it is not a blurry close-up
                cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
                bw, bh = min(1.0, box[2] * 2.6), min(1.0, box[3] * 2.2)
                box = [
                    min(max(0.0, cx - bw / 2), 1 - bw),
                    min(max(0.0, cy - bh / 2), 1 - bh),
                    bw,
                    bh,
                ]
            cam = ":".join(f"{v:.4f}" for v in box)
            side = "left" if found["box"][0] + found["box"][2] / 2 < 0.5 else "right"
            print(
                f"facecam: {found.get('mode')} box {cam} ({found.get('summary', '')})"
            )
        else:
            print(
                f"facecam: no stable face found ({found.get('reason', '')}), using the blur layout"
            )
            layout = "blur"
    elif layout in ("react", "facecam") and cam != "auto":
        side = (
            "left"
            if float(cam.split(":")[0]) + float(cam.split(":")[2]) / 2 < 0.5
            else "right"
        )
    cap_y = a.cap_y or CAP_Y[layout]
    title, band = None, None
    if a.title and layout == "react":
        lines = len(wrap(a.title, 26 if a.title_style == "box" else 24))
        if a.title_style == "box":
            band_height = lines * 78 + 44
            band = (TOP - band_height // 2, band_height, a.title_secs)
            title = ("box", a.title, TOP, a.title_secs)
        else:
            title = ("outline", a.title, TOP + 40, a.title_secs)
    ass = out / f"{stem}.ass"
    hook_secs = (
        a.hook_secs if a.hook_secs is not None else (0 if layout == "focus" else 2.6)
    )
    cap_words = words if a.captions != "none" else []
    subtitles = build_ass(
        cap_words,
        s0,
        e0,
        a.hook,
        cap_y,
        title=title,
        caps=a.captions,
        profanity=a.allow_profanity,
        hook_secs=hook_secs,
        hook_y=120 if layout == "focus" else 170,
        hook_fs=80 if layout == "focus" else 68,
        font=a.font or None,
    )
    ass.write_text(subtitles, encoding="utf-8")
    src = None
    game_x = None
    if layout == "react":
        stream = video_stream(source)
        src = (int(stream["width"]), int(stream["height"]))
        game_x = game_offset(source, s0, e0, src, [float(t) for t in cam.split(":")])
    mp4 = out / f"{stem}.mp4"
    if a.trim_bottom and layout == "facecam":
        sys.exit("--trim-bottom works with fill, blur, focus and react")
    v = video_filter(
        layout,
        cam,
        ass,
        band=band,
        cam_side=side,
        src=src,
        game_x=game_x,
        face_expr=face_expr,
        focus=a.focus,
        trim_bottom=a.trim_bottom,
    )
    muted: list[tuple[float, float]] = []
    if not a.allow_profanity:
        from clean import heard_bad, heard_twice, is_bad, merge, mute_filter

        hits = heard_bad(source, s0, e0, language=a.lang)
        cap_hits = [
            (w["s"] - s0, w["e"] - s0, w["w"])
            for w in cap_words
            if s0 <= w["s"] < e0 and is_bad(w["w"])
        ]
        # A mute starts early: the first sound of a word is enough to hear it
        muted = merge(
            [(x - 0.25, max(y, x + 0.45)) for x, y, _ in hits]
            + [(x - 0.25, y + 0.25) for x, y, _ in cap_hits]
        )
        muted = [(max(0.0, float(x)), min(float(e0 - s0), float(y))) for x, y in muted]
        print(
            f"clean: heard {[h[2] for h in hits]}, captions {[h[2] for h in cap_hits]}, muted {muted}"
        )

    def mute_chain() -> str:
        return (mute_filter(muted) + ",") if muted else ""

    if a.voice:
        # The clip's own sound as a quiet bed under the narration, muted where it swears
        graph = (
            f"[0:a]{mute_chain()}volume={a.bed_gain}[bed];[1:a]apad[vox];"
            f"[bed][vox]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
        )
        sound = [
            "-i",
            a.voice,
            "-filter_complex",
            v + ";" + graph,
            "-map",
            "[vo]",
            "-map",
            "[ao]",
        ]
    else:
        sound = ["-filter_complex", v, "-map", "[vo]", "-map", "0:a?"]
        sound += ["-af", mute_chain() + "loudnorm=I=-14:TP=-1.5:LRA=11"]
    cmd = [tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{s0:.2f}", "-to", f"{e0:.2f}"]
    cmd += ["-i", source, *sound]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart"]
    run([*cmd, str(mp4)])
    if not a.allow_profanity:
        # The finished clip is held to what check.py holds it to; only the sound is made again
        for _ in range(4):
            left = heard_twice(mp4, a.lang)
            if not left:
                break
            muted = merge(
                muted
                + [
                    (max(0.0, float(x) - 0.25), float(max(y, x + 0.45)))
                    for x, y, _ in left
                ],
                pad=0.05,
            )
            muted = [
                (max(0.0, float(x)), min(float(e0 - s0), float(y))) for x, y in muted
            ]
            print(
                f"clean: still heard {[(round(float(x), 1), w) for x, _, w in left]}, muted {muted}"
            )
            tmp = mp4.with_suffix(".tmp.mp4")
            if a.voice:
                # A swear in the narration or in the bed: the whole mix is muted there
                graph = (
                    f"[1:a]{mute_filter(muted)},volume={a.bed_gain}[bed];[2:a]apad,{mute_filter(muted)}[vox];"
                    f"[bed][vox]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
                )
                remix = [
                    "-i",
                    a.voice,
                    "-filter_complex",
                    graph,
                    "-map",
                    "0:v",
                    "-map",
                    "[ao]",
                ]
            else:
                remix = ["-map", "0:v", "-map", "1:a"]
                remix += ["-af", f"{mute_filter(muted)},loudnorm=I=-14:TP=-1.5:LRA=11"]
            cmd = [tool("ffmpeg"), "-y", "-v", "error", "-i", str(mp4)]
            cmd += ["-ss", f"{s0:.2f}", "-to", f"{e0:.2f}", "-i", source, *remix]
            cmd += [
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-ar",
                "48000",
                "-shortest",
            ]
            run([*cmd, "-movflags", "+faststart", str(tmp)])
            tmp.replace(mp4)
        else:
            print(
                "clean: WARNING swears still heard after 4 rounds; do not post this clip"
            )
    info = candidates.get("info", {})
    facts = {
        "file": str(mp4),
        "start": s0,
        "end": e0,
        "segments": segs,
        "muted": muted,
        "clean": not a.allow_profanity,
        "source_views": info.get("view_count"),
        "layout": layout,
        "hook": a.hook or a.title,
        "title": a.title,
        "cam": cam,
        "source_file": orig_source,
        "source_url": info.get("webpage_url"),
        "source_title": info.get("title"),
        "source_channel": info.get("channel") or info.get("uploader"),
    }
    save_json(out / f"{stem}.json", facts)
    print(mp4)


if __name__ == "__main__":
    main()
