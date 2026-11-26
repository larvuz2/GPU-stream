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
"""Check a finished cut before it goes anywhere: one PASS or FAIL per check, and a status of 1 on any FAIL.

    cutroom check CLIP.mp4 [--size 1080x1920] [--rules rules.md] [--caption "post text"] [--lang en]
        [--lufs -17:-13] [--allow-profanity]

What is checked:

- the picture's size (`--size`; 1920x1080 for a horizontal cut), about 30
  frames a second, and that there is sound;
- the length, 7 to 60 s unless the rules file says otherwise;
- the integrated loudness, within `--lufs`: the cutters aim at -14 LUFS, and
  a single pass of `loudnorm` lands within about a unit of it;
- that no swear is heard, by two speech models each listening on two
  alignments (`clean.heard_twice`), read in the captions (the `.ass` beside
  the clip), or written in the hook (the `.json` beside it) or the post text;
- what a rules file asks for.

A rules file is any text with lines of this form, for a platform's or a
campaign's own terms; each line is optional:

    min_seconds: 15
    max_seconds: 60
    required_hashtags: #a #b
    required_mention: @someone
    banned_terms: free download, giveaway

Hashtags, the mention, and banned terms are looked for in the post text
given with `--caption`, banned terms in the hook as well.

The script judges what it can measure. Whether the cut is good, true, and
the person's to post is not in it.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import ffprobe, load_json

Rules = dict[str, Any]


def parse_rules(path: str | None) -> tuple[Rules, bool]:
    """The rules of a file, over the defaults, and whether a file was read."""
    rules: Rules = {"min": 7.0, "max": 60.0, "tags": [], "mention": None, "banned": []}
    if not path or not Path(path).exists():
        return rules, False
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    found = re.search(r"min_seconds:\s*(\d+(?:\.\d+)?)", text, re.I)
    if found:
        rules["min"] = float(found.group(1))
    found = re.search(r"max_seconds:\s*(\d+(?:\.\d+)?)", text, re.I)
    if found:
        rules["max"] = float(found.group(1))
    found = re.search(r"required_hashtags:\s*(.+)", text, re.I)
    if found:
        rules["tags"] = re.findall(r"#\w+", found.group(1))
    found = re.search(r"required_mention:\s*(@\w+)", text, re.I)
    if found:
        rules["mention"] = found.group(1)
    found = re.search(r"banned_terms:\s*(.+)", text, re.I)
    if found:
        rules["banned"] = [
            term.strip().lower() for term in found.group(1).split(",") if term.strip()
        ]
    return rules, True


def fps_of(rate: str) -> float:
    """A frame rate ffprobe gives as a fraction, such as `30000/1001`, as a number; zero where it is not one."""
    try:
        a, b = rate.split("/")
        return float(a) / float(b)
    except (ValueError, ZeroDivisionError):
        return 0.0


def banned_in(text: str, terms: list[str]) -> list[str]:
    """The banned terms a text contains, whatever its case."""
    low = text.lower()
    return [term for term in terms if term in low]


def parse_size(value: str) -> tuple[int, int]:
    """A `--size` argument, `WIDTHxHEIGHT`."""
    try:
        w, h = value.lower().split("x")
        return int(w), int(h)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not WIDTHxHEIGHT") from None


def parse_range(value: str) -> tuple[float, float]:
    """A `--lufs` argument, `LOW:HIGH`, in either order."""
    try:
        a, b = (float(x) for x in value.split(":"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not LOW:HIGH") from None
    return min(a, b), max(a, b)


def integrated_lufs(text: str) -> float | None:
    """The integrated loudness in the summary FFmpeg's `ebur128` filter prints, or nothing where there is none."""
    summary = text[text.rfind("Summary:") :] if "Summary:" in text else ""
    found = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", summary)
    return float(found.group(1)) if found else None


def loudness(clip: Path) -> float | None:
    """A file's integrated loudness in LUFS, as FFmpeg's `ebur128` measures it."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(clip),
        "-vn",
        "-af",
        "ebur128",
        "-f",
        "null",
        "-",
    ]
    done = subprocess.run(
        cmd, capture_output=True, text=True, errors="replace", check=False
    )
    return integrated_lufs(done.stderr)


def shown_bad(ass: Path) -> list[str]:
    """The swears a subtitle file shows, read from its events with their override tags removed."""
    from clean import is_bad

    shown: list[str] = []
    for line in ass.read_text(encoding="utf-8").splitlines():
        if line.startswith("Dialogue:"):
            text = re.sub(r"\{[^}]*\}", " ", line.split(",", 9)[-1]).replace("\\N", " ")
            shown += [word for word in text.split() if is_bad(word)]
    return shown


def main() -> None:
    """Run the checks and print each one's result."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("clip")
    ap.add_argument(
        "--size",
        type=parse_size,
        default=(1080, 1920),
        help="WIDTHxHEIGHT (default 1080x1920)",
    )
    ap.add_argument("--rules", help="a file of a platform's or a campaign's terms")
    ap.add_argument(
        "--caption", default="", help="the post text that goes with the clip"
    )
    ap.add_argument(
        "--lang", default="en", help="language spoken in the clip (en, es, ...)"
    )
    ap.add_argument(
        "--lufs",
        type=parse_range,
        default=(-17.0, -13.0),
        help="LOW:HIGH integrated loudness",
    )
    ap.add_argument(
        "--allow-profanity", action="store_true", help="skip the clean-language checks"
    )
    a = ap.parse_args()
    clip = Path(a.clip)
    results: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    if not clip.exists():
        sys.exit(f"FAIL file not found: {clip}")
    side = clip.with_suffix(".json")
    meta = load_json(side) if side.exists() else {}
    rules, have_rules = parse_rules(a.rules)
    probe = ffprobe(clip)
    streams = probe.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    length = float(probe.get("format", {}).get("duration", 0) or 0)

    width, height = a.size
    size = (video.get("width"), video.get("height")) if video else None
    add(
        f"resolution {width}x{height}",
        size == (width, height),
        f"{size[0]}x{size[1]}" if size else "no video",
    )
    fps = fps_of(video.get("r_frame_rate", "0/1")) if video else 0
    add("fps about 30", 29 <= fps <= 31, f"{fps:.2f}")
    add("has audio", audio is not None)
    span = f"duration {rules['min']:g}-{rules['max']:g}s" + (
        "" if have_rules else " (default)"
    )
    add(span, rules["min"] <= length <= rules["max"], f"{length:.1f}s")
    if audio is not None:
        low, high = a.lufs
        lufs = loudness(clip)
        heard = "not measured" if lufs is None else f"{lufs:.1f} LUFS"
        add(
            f"loudness {low:g} to {high:g} LUFS",
            lufs is not None and low <= lufs <= high,
            heard,
        )
    hook = meta.get("hook", "")
    if rules["banned"]:
        hits = banned_in(hook + " " + a.caption, rules["banned"])
        add("no banned terms in caption or hook", not hits, ", ".join(hits))
    if not a.allow_profanity:
        from clean import heard_twice, is_bad

        heard_words = heard_twice(clip, a.lang)
        add(
            "no swearing in the audio",
            not heard_words,
            ", ".join(f"{word} at {start:.1f}s" for start, _, word in heard_words),
        )
        ass = clip.with_suffix(".ass")
        shown = shown_bad(ass) if ass.exists() else []
        where = "" if ass.exists() else " (no .ass found, hook and caption only)"
        add(
            "no swearing in the captions" + where,
            not shown,
            ", ".join(sorted(set(shown))),
        )
        written = [word for word in (hook + " " + a.caption).split() if is_bad(word)]
        add("no swearing in hook and post caption", not written, ", ".join(written))
    if rules["tags"]:
        missing = [tag for tag in rules["tags"] if tag.lower() not in a.caption.lower()]
        add(
            "required hashtags",
            not missing,
            ("missing " + " ".join(missing)) if missing else " ".join(rules["tags"]),
        )
    if rules["mention"]:
        add(
            "required mention",
            rules["mention"].lower() in a.caption.lower(),
            rules["mention"],
        )
    if not have_rules:
        add("rules file", True, "none given, defaults used (NOT a rules check)")

    for name, ok, detail in results:
        print(
            f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else "")
        )
    failed = [result for result in results if not result[1]]
    print("RESULT: " + ("FAIL" if failed else "PASS"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
