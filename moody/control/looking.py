# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The picture `look` hands the model of a file: what it is, and how the turn's own worker makes one.

The model is told a file's facts, not shown it, since pixels cost tokens on
every later request of a conversation. Where it has to judge a result itself
it asks to look, and gets one small JPEG of the file (`look_arguments`): a
picture itself, four frames of a video on one sheet, a sound's waveform.

For a file in an engine's folder the engine makes that picture, with its own
ffmpeg (`Agent.prepared`). A file that is in no engine (an image or a video
just generated, an entry of the library) has no engine to make it: most of a
project's generating happens before any engine starts, and starting one to
look at a picture would cost the person credits. So the worker that runs the
turn makes it (`picture_of`), with ffmpeg where its image has one, which is
found when it is needed and never assumed.

That worker holds every secret of the deployment in its environment, and the
file is one a model generated or the person uploaded, so ffmpeg, which is the
program that parses it, is kept from all of it: it runs as another user where
the worker is root (`unprivileged`), with an empty environment, in a
directory made for the one file, reading files and nothing over the network
(`-protocol_whitelist file`, which is what keeps a playlist dressed as a
video from fetching an address), and for `LOOK_SECONDS` at most.
"""

from __future__ import annotations

import os
import pwd
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# The largest picture `look` hands the model, which ffmpeg makes far smaller than this
LOOK_BYTES = 4 * 1024 * 1024
# How long the worker's ffmpeg may take over one file
LOOK_SECONDS = 60
# The account the worker's ffmpeg runs as where the worker is root
LOOK_USER = "nobody"
SOURCE, PICTURE = "source", "look.jpg"


class NoPicture(Exception):
    """Why no picture could be made of a file, in words for the model."""


def look_arguments(kind: str, seconds: float) -> list[str]:
    """ffmpeg's arguments, between input and output, for the one small JPEG `look` hands the model of a file.

    A picture is itself, no wider than 1280 pixels. A video is four frames
    spread over its length on one sheet, since one frame says nothing of
    motion or of a cut; its first frame where its length is not known. Sound is
    its waveform over its whole length, which shows level, dynamics, silence,
    and clipping at a glance.
    """
    if kind == "audio":
        return [
            "-filter_complex",
            "showwavespic=s=1280x320:colors=white",
            "-frames:v",
            "1",
        ]
    if kind == "video" and seconds > 0:
        return [
            "-vf",
            f"fps=4/{seconds:.3f},scale=640:-2,tile=2x2",
            "-frames:v",
            "1",
            "-q:v",
            "4",
        ]
    return ["-frames:v", "1", "-vf", "scale=min(1280\\,iw):-2", "-q:v", "4"]


def unprivileged() -> dict[str, Any]:
    """How `subprocess` starts a child that is not this worker's user, where the worker is root.

    Raises:
        NoPicture: The worker is root and has no account to run the child as.
    """
    if os.geteuid() != 0:
        return {}
    try:
        account = pwd.getpwnam(LOOK_USER)
    except KeyError:
        raise NoPicture(
            f"the machine this turn runs on has no {LOOK_USER} account to read the file as"
        ) from None
    return {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []}


def run(folder: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one of ffmpeg's programs on the file in `folder`, kept from everything else of the worker.

    Raises:
        NoPicture: It took longer than `LOOK_SECONDS`, or the worker has no account to run it as.
    """
    try:
        return subprocess.run(
            command,
            cwd=folder,
            env={"PATH": os.defpath},
            capture_output=True,
            text=True,
            timeout=LOOK_SECONDS,
            **unprivileged(),
        )
    except subprocess.TimeoutExpired:
        raise NoPicture(
            f"reading the file took more than {LOOK_SECONDS} seconds"
        ) from None


def length(folder: Path) -> float:
    """How long the file in `folder` plays, in seconds, or zero where ffprobe is not there or cannot say."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return 0.0
    ran = run(
        folder,
        [
            ffprobe,
            "-v",
            "error",
            "-protocol_whitelist",
            "file",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            SOURCE,
        ],
    )
    try:
        return max(float(ran.stdout.strip()), 0.0) if ran.returncode == 0 else 0.0
    except ValueError:
        return 0.0


def picture_of(data: bytes, kind: str) -> bytes:
    """The small JPEG `look` hands the model of a file this worker holds: an image, a video, or a sound.

    Raises:
        NoPicture: The worker has no ffmpeg, or ffmpeg made no picture of the file.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise NoPicture("the machine this turn runs on has no ffmpeg")
    with tempfile.TemporaryDirectory(prefix="moody-look-") as made:
        folder = Path(made)
        # The child is another user: it reads the file here and writes its picture here
        folder.chmod(0o777)
        (folder / SOURCE).write_bytes(data)
        (folder / SOURCE).chmod(0o644)
        seconds = length(folder) if kind == "video" else 0.0
        ran = run(
            folder,
            [
                ffmpeg,
                "-nostdin",
                "-loglevel",
                "error",
                "-protocol_whitelist",
                "file",
                "-y",
                "-i",
                SOURCE,
                *look_arguments(kind, seconds),
                PICTURE,
            ],
        )
        picture = folder / PICTURE
        if ran.returncode != 0 or not picture.is_file() or picture.is_symlink():
            raise NoPicture(ran.stderr.strip()[-300:] or "ffmpeg made nothing of it")
        if picture.stat().st_size > LOOK_BYTES:
            raise NoPicture("its picture came out too large to hand over")
        return picture.read_bytes()
