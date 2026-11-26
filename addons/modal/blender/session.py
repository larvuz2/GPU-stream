# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Blender's side of a Selkies session on Modal, run as it starts (`blender --python`).

It does the two things only Blender can do for itself.

It keeps what the end of a session would lose. Blender writes its auto-save
files, and the scene it quits with, into its temporary directory, which is the
Sandbox's own disk and goes with the Sandbox. This points that directory at the
workspace Volume, beside the preferences, add-ons, and extensions the image
already keeps there (`BLENDER_USER_RESOURCES`), so File > Recover finds them in
the next session. Where a session ended with Blender open, `session.sh` had it
quit and kept the scene Blender wrote on its way out under that Sandbox's name;
a Blender starting in another Sandbox opens that scene again, as Blender's own
recovery does: an unsaved scene comes back unsaved, and a saved file under its
own path with its unsaved changes. A Blender started again within the same
Sandbox finds only its own Sandbox's scene, and opens its start-up file as
usual.

It runs the Python it is handed, in the Blender the page shows. A request is a
file in the spool directory; a timer on Blender's main thread, the only one
`bpy` may be called from, runs each in turn and writes what it printed and how
it ended beside it. `run-python.sh` is the other end. The code runs as if from
the 3D viewport, since most operators refuse to run without one and a timer has
no window of its own.

This is Python because Blender's scripting interface is.
"""

import contextlib
import io
import json
import os
import shutil
import traceback
from pathlib import Path

import bpy

SPOOL = Path(os.environ["SELKIES_MODAL_BLENDER_SPOOL"])
RECOVERY = Path(os.environ["SELKIES_MODAL_BLENDER_RECOVERY"])
OWN_SCENE = RECOVERY / f"resume-{os.environ['MODAL_SANDBOX_ID']}.blend"
POLL_SECONDS = 0.25


def viewport() -> dict:
    """The window, screen, area, and region of the first 3D viewport, or nothing where there is none."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for region in area.regions:
                if region.type == "WINDOW":
                    return {"window": window, "screen": window.screen, "area": area, "region": region}
    return {}


def run(source: str) -> dict:
    """Run one request and report what it printed and the traceback it ended with, if any.

    An exit the code asks for is reported like any other failure: it must not
    take the user's Blender down with it.
    """
    output = io.StringIO()
    error = None
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            with bpy.context.temp_override(**viewport()):
                exec(compile(source, "<request>", "exec"), {"__name__": "__main__", "bpy": bpy})
    except (Exception, SystemExit, KeyboardInterrupt) as raised:
        # From the request's own frame on: the caller did not write this function
        error = "".join(traceback.format_exception(type(raised), raised, raised.__traceback__.tb_next))
    return {"ok": error is None, "output": output.getvalue(), "error": error}


def serve() -> float:
    """Answer every waiting request, oldest first, and ask to be called again.

    An answer is written under another name and renamed, so its reader never
    sees half of one.

    A sender that stops waiting takes its request back (`run-python.sh`), which
    can happen before the request's turn or while it runs. Such a request is
    skipped, or its answer removed, since nobody reads it. Neither may raise
    here: Blender drops a timer whose function raises, and with it every later
    request of the session and the scene `session.sh` keeps at its end.
    """
    for request in sorted(SPOOL.glob("*.py")):
        try:
            source = request.read_text()
        except FileNotFoundError:
            continue
        partial = request.with_suffix(".partial")
        partial.write_text(json.dumps(run(source)))
        answer = partial.rename(request.with_suffix(".json"))
        try:
            request.unlink()
        except FileNotFoundError:
            answer.unlink(missing_ok=True)
    return POLL_SECONDS


def resume() -> None:
    """Open the scene another Sandbox's session ended with, where there is one, and keep it as a backup."""
    kept = sorted((scene for scene in RECOVERY.glob("resume-*.blend") if scene != OWN_SCENE), key=os.path.getmtime)
    if not kept:
        return
    scene = str(kept[-1])
    with bpy.context.temp_override(**viewport()):
        bpy.ops.wm.recover_auto_save(filepath=scene)
    if bpy.data.filepath == scene:
        # A scene that had never been saved comes back named after the recovery file, where a
        # save would land out of sight. Read as a start-up file it has no name, as it had.
        with bpy.context.temp_override(**viewport()):
            bpy.ops.wm.read_homefile(filepath=scene)
    kept[-1].replace(RECOVERY / "resumed.blend")
    for older in kept[:-1]:
        older.unlink()


def clear_dead_sessions() -> None:
    """Remove the temporary directories of Blenders that ended with an earlier Sandbox.

    A Blender that is killed leaves its own behind, which the Sandbox's disk
    forgot for it and the Volume does not. One made since this Sandbox started
    may be a running Blender's, so the session's start, which the token table
    is as old as, is the line.
    """
    started = os.path.getmtime(os.environ["SELKIES_TOKENS_FILE"])
    for directory in RECOVERY.glob("blender_*"):
        if directory.is_dir() and os.path.getmtime(directory) < started:
            shutil.rmtree(directory, ignore_errors=True)


SPOOL.mkdir(parents=True, exist_ok=True)
RECOVERY.mkdir(parents=True, exist_ok=True)
clear_dead_sessions()
bpy.context.preferences.filepaths.temporary_directory = str(RECOVERY)


def begin() -> None:
    """Open the last session's scene, then start answering requests.

    In that order, so a request that was waiting for Blender to start runs in
    the scene the session resumes rather than in the start-up file it replaces.
    Serving outlives every file that is loaded from here on.
    """
    resume()
    bpy.app.timers.register(serve, first_interval=POLL_SECONDS, persistent=True)


# From a timer rather than here: a file cannot be loaded until Blender has finished starting
bpy.app.timers.register(begin, first_interval=POLL_SECONDS)
