# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The edit a version of a video is: what v2 recorded of it, kept so that the page can draw its tracks.

A project whose versions are kept with v2 (the `v2` skill) has a record of
each saved version in its history: what the version is, what the person asked
for, and every change with the time it sits at in the new video and what kind
of thing it is (video, voice, music, graphics, captions, ...). v2's own page
draws that record as a timeline of lanes, but it is served inside the engine
and shown in a browser there, so looking at it costs a running machine. Here
the record is read once, at the moment the agent shows the version (`preview`
with a `version`, when the engine is running for the cut anyway), and kept on
the file in the `preview` event. The page then draws the same lanes from the
log with no engine at all, which is the cheapest a screen can be.

The record is v2's own file (`RECORD`) as the version's tag holds it, read
with Git on the engine (`record_command`). It is taken only where the label
the agent gave is a v2 version's name (`is_version`) and the record names, as
the version's render, one of the very files being shown (`edit_of`): the lanes
under a video are then that video's and no other's. A label that is no v2
name asks the engine nothing, and a project that keeps no versions answers
the one command with nothing, which reads as no edit.

The record is a file the agent's commands wrote, so what is kept of it is
checked field by field and bounded: a count of changes and of prompts, a
length for every text, times that are numbers in order, kinds and types from
v2's own lists. Nothing in it is run, opened, or followed.

The version's sound is kept as bars (`bars_command`, `sound_bars`): the
loudest moment of each of `BARS` equal stretches of the file, which the
engine's ffmpeg measures in one pass and prints as text. A few hundred small
numbers draw a waveform under the voice and the music at any width, where the
samples themselves would be megabytes and a picture of them would not take
the page's colors.
"""

from __future__ import annotations

import json
import math
import re
import shlex
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Collection

# The name v2 gives a saved version, which is also the Git tag its record is read by
VERSION_NAME = re.compile(r"v[1-9][0-9]{0,5}")
# Where v2 keeps a version's record, from the project's folder
RECORD = ".v2/commit.json"
# The most of a record that is read from an engine; a longer one is no record
RECORD_BYTES = 256 * 1024
# What a change may be, as v2 names them: the lanes of its timeline, and a cut, which removes time
KINDS = ("text", "captions", "graphics", "video", "voice", "music", "sfx", "cut")
# What v2 says of a change that is not an edit of what was there
TYPES = ("added", "retimed")
# The most changes and prompts one version's edit keeps, and the longest each text of it may be
CHANGES = 200
PROMPTS = 20
TEXT_CHARACTERS = 300
PROMPT_CHARACTERS = 1000
SOURCE_CHARACTERS = 200
# The longest a video's time may be, in seconds: a day, past which a number is not a time in a video
LONGEST_SECONDS = 86_400.0
# How many bars a version's sound is kept as, and the rate the sound is read at to measure them
BARS = 240
BAR_RATE = 8000
# What ffmpeg's `astats` filter calls the loudest sample of a stretch, in decibels below full scale
PEAK_KEY = "lavfi.astats.Overall.Peak_level"


def is_version(label: str) -> bool:
    """Whether a preview's label is the name v2 gives a saved version (`v1`, `v12`)."""
    return VERSION_NAME.fullmatch(label) is not None


def record_command(folder: str, version: str) -> str:
    """The command that prints v2's record of a version of the project in `folder`, or nothing where there is none.

    `version` has to be a name `is_version` accepts, which is what makes it
    safe to hand a shell. The path is given from the folder itself (`./`), so a
    repository further up is never read in the project's place.
    """
    return f"cd {shlex.quote(folder)} && git show {version}:./{RECORD} 2>/dev/null | head -c {RECORD_BYTES}"


def words(given: Any, most: int) -> str:
    """A text of a record on one line and no longer than `most` characters, or an empty one for anything else."""
    return " ".join(given.split())[:most] if isinstance(given, str) else ""


def seconds(given: Any) -> float | None:
    """A time in a video, in seconds to the millisecond, or nothing for what is not one."""
    if isinstance(given, bool) or not isinstance(given, (int, float)) or not math.isfinite(given):
        return None
    return round(float(given), 3) if 0 <= given <= LONGEST_SECONDS else None


def change_of(given: Any) -> dict[str, Any] | None:
    """One change of a record as the page takes it, or nothing for an entry that says nothing.

    A change with no span is one to the whole video. A span is kept only whole
    and in order, a kind and a type only where they are v2's own, and the time
    a change removed only for a cut.
    """
    if not isinstance(given, dict):
        return None
    text = words(given.get("text"), TEXT_CHARACTERS)
    if not text:
        return None
    change: dict[str, Any] = {"text": text}
    if given.get("kind") in KINDS:
        change["kind"] = given["kind"]
    start, end = seconds(given.get("from")), seconds(given.get("to"))
    if start is not None and end is not None and end >= start:
        change["from"], change["to"] = start, end
    removed = seconds(given.get("removed"))
    if change.get("kind") == "cut" and removed:
        change["removed"] = removed
    source = words(given.get("src"), SOURCE_CHARACTERS)
    if source:
        change["src"] = source
    if given.get("type") in TYPES:
        change["type"] = given["type"]
    return change


def edit_of(record: str, shown: Collection[str]) -> tuple[str, dict[str, Any]] | None:
    """The edit v2's record of a version describes, with the file among `shown` that is its render.

    `shown` holds the paths a preview shows, from the project's folder. The
    answer is nothing where the text is no record, or where its render is not
    one of them: a record says what its own render is made of, and drawn under
    another file its times would be wrong.

    The edit holds the version's `message`, the `prompts` it answers, its
    `changes`, and `saved_at` where the record has a time.
    """
    try:
        given = json.loads(record)
    except ValueError:
        return None
    if not isinstance(given, dict) or not isinstance(given.get("render"), str) or not given["render"].strip():
        return None
    render = PurePosixPath(given["render"].strip()).as_posix()
    if render not in shown:
        return None
    prompts = given.get("prompts") if isinstance(given.get("prompts"), list) else []
    changes = given.get("changes") if isinstance(given.get("changes"), list) else []
    edit: dict[str, Any] = {
        "message": words(given.get("message"), TEXT_CHARACTERS),
        "prompts": [prompt for prompt in (words(one, PROMPT_CHARACTERS) for one in prompts[:PROMPTS]) if prompt],
        "changes": [change for change in (change_of(one) for one in changes[:CHANGES]) if change is not None],
    }
    try:
        edit["saved_at"] = datetime.fromisoformat(words(given.get("saved_at"), 40).replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    return render, edit


def bars_command(folder: str, inside: str, length: float) -> str:
    """The command that prints the loudest moment of each of `BARS` equal stretches of a file's sound.

    `inside` is the file's path from the project's `folder` and `length` how
    long it plays, in seconds. The sound is read at `BAR_RATE`, which is all
    a peak needs, and cut into stretches of as many samples as make `BARS` of
    them; ffmpeg's `astats` then prints each stretch's peak over its channels.
    A file with no sound prints nothing.
    """
    samples = max(1, math.ceil(length * BAR_RATE / BARS))
    chain = f"aresample={BAR_RATE},asetnsamples=n={samples}:p=0,astats=metadata=1:reset=1,ametadata=mode=print:key={PEAK_KEY}:file=-"
    measure = shlex.join(["ffmpeg", "-nostdin", "-v", "error", "-i", f"./{inside}", "-map", "0:a:0", "-af", chain, "-f", "null", "-"])
    return f"cd {shlex.quote(folder)} && {measure} 2>/dev/null | grep -F {PEAK_KEY}= | head -n {BARS}"


def sound_bars(output: str) -> list[int]:
    """The bars in what `bars_command` printed: each stretch's peak from 0, silence, to 100, full scale.

    Fewer than two is no waveform, and is given as none.
    """
    bars = []
    for line in output.splitlines():
        _, found, level = line.partition(f"{PEAK_KEY}=")
        if not found:
            continue
        try:
            decibels = float(level)
        except ValueError:
            continue
        # A silent stretch's peak is minus infinity, which the power turns into nothing; `nan` is no measurement
        bars.append(0 if math.isnan(decibels) else round(100 * min(1.0, 10 ** (decibels / 20))))
    return bars if len(bars) > 1 else []
