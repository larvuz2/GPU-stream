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
"""What the Cut Room's scripts share: where work lives, and how FFmpeg, yt-dlp, and the speech models are reached.

Work is kept per source in `jobs/<name>-<hash>` under the folder a script
runs in, which `cutroom` makes the session's project folder: the footage, its
sound, its transcript, the moments found in it, and the cuts made from it
(`edits/`). `CUTROOM_HOME` names another folder.

The speech models and the face detector are files of the image
(`CUTROOM_MODELS`, `/opt/cutroom/models`), put there when it was built, so no
session downloads one. A machine without that folder, such as one running the
tests, falls back on the model's name, which faster-whisper fetches.

A command that fails ends the script with its last words, since the caller is
an agent reading the output, and a traceback of this module tells it nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(os.environ.get("CUTROOM_HOME", Path.cwd()))
JOBS = ROOT / "jobs"
MODELS = Path(os.environ.get("CUTROOM_MODELS", "/opt/cutroom/models"))
FACE_MODEL = MODELS / "face_detection_yunet_2023mar.onnx"


def tool(name: str) -> str:
    """The path of a program the image carries, such as `ffmpeg`; the script ends where it is missing."""
    path = shutil.which(name)
    if not path:
        sys.exit(f"{name} not found on this machine.")
    return path


def run(
    cmd: Sequence[Any], check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a command, ending the script with the tail of its errors where it fails and `check` is set."""
    done = subprocess.run(
        [str(part) for part in cmd],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and done.returncode != 0:
        said = (done.stderr or "")[-1500:] if capture else ""
        sys.exit(
            f"command failed ({done.returncode}): {' '.join(map(str, cmd))[:200]}\n{said}"
        )
    return done


def ytdlp_base() -> list[str]:
    """The yt-dlp command of this environment, quiet enough to read its JSON."""
    return [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-progress"]


def ytdlp_json(url: str, extra: Sequence[str] = ()) -> dict[str, Any]:
    """What yt-dlp knows of a video without downloading it."""
    return json.loads(run([*ytdlp_base(), "-J", *extra, url], capture=True).stdout)


def is_url(source: str) -> bool:
    """Whether a source is a web address and not a file."""
    return bool(re.match(r"https?://", source))


def job_dir(source: str) -> Path:
    """The folder a source's work is kept in, made if missing: a readable stem and a hash of the source."""
    key = hashlib.sha1(source.encode()).hexdigest()[:8]
    name = (
        source.split("v=")[-1].split("/")[-1] if is_url(source) else Path(source).stem
    )
    stem = re.sub(r"[^a-z0-9]+", "-", name.lower())[:24].strip("-")
    folder = JOBS / f"{stem or 'job'}-{key}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def ffprobe(path: str | Path) -> dict[str, Any]:
    """A file's duration and, for each stream, its kind, size, and frame rate."""
    done = run(
        [
            tool("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    return json.loads(done.stdout)


def duration(path: str | Path) -> float:
    """A file's length in seconds."""
    return float(ffprobe(path)["format"]["duration"])


def video_stream(path: str | Path) -> dict[str, Any] | None:
    """The first video stream `ffprobe` reports for a file, or nothing."""
    streams = ffprobe(path).get("streams", [])
    return next((s for s in streams if s.get("codec_type") == "video"), None)


def save_json(path: str | Path, value: Any) -> None:
    """Write a value as indented UTF-8 JSON."""
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def load_json(path: str | Path) -> Any:
    """Read a JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def whisper_source(name: str) -> str:
    """Where faster-whisper loads a model from: the image's copy of it, else its name."""
    local = MODELS / f"faster-whisper-{name}"
    return str(local) if (local / "model.bin").exists() else name


def subtitles_path(path: str | Path) -> str:
    """A file's path as FFmpeg's `subtitles` filter takes it inside a filter graph."""
    return str(path).replace("\\", "/").replace(":", "\\:")
