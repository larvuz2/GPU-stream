# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""What the control plane's test modules share that pytest hands out by name."""

from __future__ import annotations

import shutil
import subprocess

import pytest


@pytest.fixture(scope="session")
def media(tmp_path_factory: pytest.TempPathFactory) -> dict[str, bytes]:
    """A picture, a video, and a sound that are what they say, by suffix: what fal or a person's upload hands a worker.

    ffmpeg makes them, so a test that asks for them is one that needs ffmpeg
    and says so (`looks` in `test_api.py`).
    """
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg is not None, (
        "a test that takes real media is marked as needing ffmpeg"
    )
    folder = tmp_path_factory.mktemp("media")
    sources = {
        ".png": [
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=1920x1080:rate=1",
            "-frames:v",
            "1",
        ],
        ".mp4": [
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=640x360:rate=10",
            "-t",
            "2",
            "-pix_fmt",
            "yuv420p",
        ],
        ".wav": ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"],
    }
    made = {}
    for suffix, arguments in sources.items():
        subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-loglevel",
                "error",
                "-y",
                *arguments,
                str(folder / f"made{suffix}"),
            ],
            check=True,
        )
        made[suffix] = (folder / f"made{suffix}").read_bytes()
    return made
