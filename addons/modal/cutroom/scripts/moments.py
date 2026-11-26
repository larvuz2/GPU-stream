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
"""Find the moments worth cutting in a video: score every second, then propose the best stretches.

    cutroom moments SOURCE [--top 8] [--min 15] [--max 40] [--chat chat.json] [--max-minutes 90]

`SOURCE` is a file of the project folder or a web address yt-dlp reads. The
job folder it makes (`jobs/<name>-<hash>`, printed) is what the cutters work
from: `source.mp4` for a download, `audio.wav`, `transcript.json` (every word
with its start and end, from faster-whisper's `small` model), and
`candidates.json` and `candidates.md`, the moments.

Each second is scored from the signals that exist, and a missing signal is
left out, never invented:

- loudness: how far the second rises above the level around it;
- hype words in the transcript ("no way", "wait", "what");
- the "most replayed" heatmap a video site publishes, where there is one;
- chat messages per second, from a live stream's chat replay or a chat file
  given with `--chat`.

The best seconds become stretches of `--min` to `--max` seconds that do not
overlap, each snapped to start just before a word and end just after one, and
listed in the order they come with why each scored.

A source with no speech still gets candidates, from loudness alone; its
transcript is then empty, and captions have to be written (`cut.py --lines`).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import wave
from pathlib import Path
from typing import Any

import numpy as np
from common import (
    ffprobe,
    is_url,
    job_dir,
    load_json,
    run,
    save_json,
    tool,
    whisper_source,
    ytdlp_base,
    ytdlp_json,
)

HYPE = re.compile(
    r"\b(no way|oh my god|omg|what|wait|bro|let'?s go|holy|insane|crazy|yo+|wtf|dude|look at|nah|run|go go)\b",
    re.I,
)
CHAT_HYPE = re.compile(r"(LMAO|LOL|KEKW|OMEGALUL|W+\b|CLIP|💀|😂|🔥|NO WAY|HOLY)", re.I)
INFO_KEYS = (
    "id",
    "title",
    "uploader",
    "channel",
    "uploader_id",
    "webpage_url",
    "duration",
    "view_count",
    "upload_date",
    "heatmap",
    "is_live",
    "was_live",
)


def fetch(source: str, folder: Path, max_minutes: int) -> tuple[Path, dict[str, Any]]:
    """The footage as a file, and what its site says of it: a download for an address, the file itself otherwise.

    A download is at most 1080 pixels high and, for a source longer than
    `max_minutes`, only that much of its start. A stream that was live also
    gets its chat replay, where the site keeps one.
    """
    info: dict[str, Any] = {}
    if is_url(source):
        info = ytdlp_json(source)
        save_json(folder / "info.json", {key: info.get(key) for key in INFO_KEYS})
        video = folder / "source.mp4"
        if not video.exists():
            formats = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b"
            args = [*ytdlp_base(), "-f", formats, "--merge-output-format", "mp4"]
            args += ["-o", str(video)]
            if (info.get("duration") or 0) > max_minutes * 60:
                args += ["--download-sections", f"*0-{max_minutes * 60}"]
            run([*args, source])
        if info.get("was_live") and not (folder / "chat.json").exists():
            chat = [*ytdlp_base(), "--skip-download", "--write-subs"]
            chat += ["--sub-langs", "live_chat", "-o", str(folder / "chat")]
            run([*chat, source], check=False)
    else:
        video = Path(source)
        save_json(
            folder / "info.json", {"title": video.stem, "webpage_url": str(video)}
        )
    return video, info


def audio_rms(video: Path, folder: Path) -> tuple[Path, np.ndarray]:
    """The footage's sound as a 16 kHz mono file, and its level in decibels for each whole second."""
    wav = folder / "audio.wav"
    if not wav.exists():
        cmd = [tool("ffmpeg"), "-y", "-v", "error", "-i", str(video)]
        run([*cmd, "-ac", "1", "-ar", "16000", str(wav)])
    with wave.open(str(wav)) as file:
        raw = file.readframes(file.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    seconds = len(samples) // 16000
    per_second = samples[: seconds * 16000].reshape(seconds, 16000)
    return wav, 20 * np.log10(np.sqrt((per_second**2).mean(1) + 1e-9))


def transcribe(wav: Path, folder: Path) -> list[dict[str, Any]]:
    """Every word of the footage with its start and end, kept in `transcript.json` so it is heard once.

    The `small` model runs on a GPU where the machine has one and its
    libraries load, and on the CPU otherwise.
    """
    out = folder / "transcript.json"
    if out.exists():
        return load_json(out)
    from faster_whisper import WhisperModel

    try:
        import ctranslate2

        cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        cuda = False
    with wave.open(str(wav)) as file:
        raw = file.readframes(file.getnframes())
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768

    def run_on(device: str) -> list[dict[str, Any]]:
        precision = "float16" if device == "cuda" else "int8"
        model = WhisperModel(
            whisper_source("small"), device=device, compute_type=precision
        )
        segments, _ = model.transcribe(pcm, word_timestamps=True, vad_filter=True)
        return [
            {"w": word.word.strip(), "s": round(word.start, 2), "e": round(word.end, 2)}
            for segment in segments
            for word in (segment.words or [])
        ]

    try:
        words = run_on("cuda" if cuda else "cpu")
    except RuntimeError as error:
        print(f"GPU transcription unavailable ({str(error)[:80]}), using CPU")
        words = run_on("cpu")
    save_json(out, words)
    return words


def chat_series(folder: Path, seconds: int, chat_file: str | None) -> np.ndarray:
    """Chat messages per second, a message with a hype word counting twice.

    Read from the chat replay yt-dlp saved (one JSON action a line) or from
    a chat file with `comments`, each having `content_offset_seconds` and a
    message body.
    """
    counts = np.zeros(seconds)
    replay = list(folder.glob("chat*.live_chat.json"))
    if replay:
        text = replay[0].read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            try:
                action = json.loads(line)["replayChatItemAction"]
                at = int(action["videoOffsetTimeMsec"]) / 1000
                said = json.dumps(action["actions"], ensure_ascii=False)
            except Exception:
                continue
            if 0 <= at < seconds:
                counts[int(at)] += 2 if CHAT_HYPE.search(said) else 1
    elif chat_file:
        for message in load_json(chat_file).get("comments", []):
            at = message.get("content_offset_seconds", 0)
            body = (message.get("message") or {}).get("body", "")
            if 0 <= at < seconds:
                counts[int(at)] += 2 if CHAT_HYPE.search(body) else 1
    return counts


def z(values: Any) -> np.ndarray:
    """Values as distances from their median in standard deviations, or zeros for a flat signal."""
    values = np.asarray(values, dtype=float)
    if values.std() < 1e-9:
        return np.zeros_like(values)
    return (values - np.median(values)) / (values.std() + 1e-9)


def smooth(values: np.ndarray, width: float) -> np.ndarray:
    """A running mean over `width` values, never wider than the signal, which would change its length."""
    width = max(1, min(int(width), len(values)))
    return np.convolve(values, np.ones(width) / width, mode="same")


def pick_windows(
    score: np.ndarray,
    words: list[dict[str, Any]],
    length: float,
    top: int,
    shortest: float,
    longest: float,
) -> list[dict[str, float]]:
    """The best stretches of a scored timeline: `{start, end, peak}` around each peak, none overlapping.

    A stretch is laid so its peak is a little past its middle, snapped to
    start 0.3 s before the first word inside it and end 0.6 s after the last,
    and kept between `shortest` and `longest` seconds. Peaks are taken best
    first, and one whose stretch touches a stretch already taken is skipped.
    """
    n = len(score)
    picks: list[dict[str, float]] = []
    used = np.zeros(n, bool)
    for peak in np.argsort(-score):
        if len(picks) >= top or score[peak] <= 0:
            break
        s0 = max(0, peak - 0.55 * longest)
        e0 = min(length, s0 + longest)
        inside = [x for x in words if x["s"] >= s0 and x["e"] <= e0]
        if inside:
            s0 = max(0, inside[0]["s"] - 0.3)
            e0 = min(length, inside[-1]["e"] + 0.6)
        if e0 - s0 < shortest:
            e0 = min(length, s0 + shortest)
        e0 = min(e0, s0 + longest)
        if used[int(s0) : int(e0)].any():
            continue
        used[int(s0) : int(e0)] = True
        picks.append({"start": round(s0, 2), "end": round(e0, 2), "peak": int(peak)})
    return picks


def main() -> None:
    """Fetch, listen, score, and write the candidates."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--min", type=float, default=15)
    ap.add_argument("--max", type=float, default=40)
    ap.add_argument("--chat")
    ap.add_argument("--max-minutes", type=int, default=90)
    a = ap.parse_args()
    folder = job_dir(a.src)
    video, info = fetch(a.src, folder, a.max_minutes)
    length = float(ffprobe(video)["format"]["duration"])
    wav, db = audio_rms(video, folder)
    n = len(db)
    words = transcribe(wav, folder)
    # Loudness counts where it jumps above the level of the half minute around it
    loud = smooth(np.clip(z(db - smooth(db, 30)), 0, None), 3)
    hype = np.zeros(n)
    for word in words:
        if HYPE.search(word["w"]) and int(word["s"]) < n:
            hype[int(word["s"])] += 1
    hype = smooth(hype, 5)
    heat = np.zeros(n)
    for span in info.get("heatmap") or []:
        heat[int(span["start_time"]) : int(math.ceil(span["end_time"]))] = span["value"]
    chat = chat_series(folder, n, a.chat)
    chatz = smooth(np.clip(z(smooth(chat, 10)), 0, None), 3)
    w_heat = 2.0 if heat.any() else 0
    w_chat = 1.5 if chat.any() else 0
    score = (
        1.0 * loud + 0.8 * z(hype).clip(0) + w_heat * z(heat).clip(0) + w_chat * chatz
    )
    picks: list[dict[str, Any]] = []
    for window in pick_windows(score, words, length, a.top, a.min, a.max):
        s0, e0, peak = window["start"], window["end"], int(window["peak"])
        text = " ".join(x["w"] for x in words if s0 <= x["s"] < e0)
        why = []
        if loud[peak] > 1:
            why.append("loudness spike")
        if hype[peak] > 0:
            why.append("hype words")
        if heat[peak] > 0.5:
            why.append(f"most replayed {heat[peak]:.2f}")
        if w_chat and chatz[peak] > 1:
            why.append("chat spike")
        picks.append(
            {
                "n": len(picks) + 1,
                "start": s0,
                "end": e0,
                "peak": peak,
                "score": round(float(score[peak]), 2),
                "why": why or ["overall energy"],
                "text": text[:400],
            }
        )
    picks.sort(key=lambda x: x["start"])
    for index, pick in enumerate(picks, 1):
        pick["n"] = index
    meta = load_json(folder / "info.json")
    signals = {"heatmap": bool(w_heat), "chat": bool(w_chat), "words": len(words)}
    found = {
        "source": str(video),
        "info": meta,
        "duration": length,
        "candidates": picks,
        "signals": signals,
    }
    save_json(folder / "candidates.json", found)

    def clock(t: float) -> str:
        return f"{int(t // 60)}:{int(t % 60):02d}"

    heard = f"signals: loudness, transcript ({len(words)} words)"
    heard += (", most replayed" if w_heat else "") + (", chat" if w_chat else "")
    md = [f"# Candidates: {meta.get('title', '')}"]
    md += [f"source: {meta.get('webpage_url', '')}", heard, ""]
    for pick in picks:
        seconds = pick["end"] - pick["start"]
        span = f"{clock(pick['start'])}-{clock(pick['end'])} ({seconds:.0f}s)"
        md += [f"## {pick['n']}. {span} score {pick['score']}"]
        md += [f"why: {', '.join(pick['why'])}", f"> {pick['text']}", ""]
    (folder / "candidates.md").write_text("\n".join(md), encoding="utf-8")
    print(f"job: {folder}\n{len(picks)} candidates -> {folder / 'candidates.md'}")


if __name__ == "__main__":
    main()
