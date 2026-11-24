# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The Unreal Editor's way back to Blender: send the selection to the Blender beside it.

`send_selection` exports what is selected into the project's `bridge/` folder
as FBX, through Unreal's own exporters, and hands Blender a request to import
it. The level's selected actors go as one file, through the level exporter
with `selected` set; with no actor selected, each static mesh selected in the
Content Browser goes as a file of its own. FBX is the one format both
exporters write without a plugin, and it records its units (centimeters) and
axes, which Blender's FBX importer converts to the scene's.

The request goes through the spool Blender's session already serves
(`addons/modal/blender/session.py`): a Python file in
`SELKIES_MODAL_BLENDER_SPOOL`, written under another name and renamed so
Blender never runs half of one, which Blender's main thread runs as it runs
any request, writing its output beside it as `<request>.json`. The request
imports each file into a collection named after it. The editor does not wait
for the answer: a Slate tick callback looks for it, logs it to the Output Log,
and removes it, so the editor's frame never stalls on Blender. A request
Blender has not picked up after `CLAIM_SECONDS` (no Blender open) is taken
back, as `run-python.sh` does, so it does not run in a Blender opened later.

The bridge folder is the session's project folder, as `selkies-modal-project`
prints it, the one Blender's half of the bridge writes to too; outside a
session it is the Unreal project's folder. This file and `init_unreal.py`,
which puts Send to Blender in the editor's Tools menu, are on the editor's
Python path.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import unreal

SPOOL_VARIABLE = "SELKIES_MODAL_BLENDER_SPOOL"
# Where `addons/modal/sandbox.py` puts the spool (`BLENDER_SPOOL`), for an editor started without the variable
DEFAULT_SPOOL = "/tmp/selkies-modal/blender"
BRIDGE_FOLDER = "bridge"
# How long Blender has to pick a request up, and then to run it
CLAIM_SECONDS = 30
ANSWER_SECONDS = 600
POLL_SECONDS = 0.25

# What Blender runs for a request; FILES is the list of (collection name, FBX path) it is given
BLENDER_IMPORT = """
import bpy

layers = bpy.context.view_layer
for name, path in FILES:
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    layers.active_layer_collection = layers.layer_collection.children[collection.name]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    added = [item for item in bpy.data.objects if item not in before]
    print(f"{collection.name}: {len(added)} objects from {path}")
"""


class BridgeError(Exception):
    """A send that did not happen, with what the person can do about it."""


def project_folder() -> Path:
    """The project folder the editor and Blender share."""
    finder = shutil.which("selkies-modal-project")
    if finder is not None:
        return Path(subprocess.run([finder], check=True, capture_output=True, text=True).stdout.strip())
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def safe_name(name: str) -> str:
    """A name as a file and a Blender collection take it."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "Unreal"


def selection() -> list[tuple[str, object, bool]]:
    """What to export: (name, object, whether only its selection), for the actors or the meshes selected.

    Raises:
        BridgeError: Neither an actor nor a static mesh is selected.
    """
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors()
    if actors:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        name = actors[0].get_actor_label() if len(actors) == 1 else f"{world.get_name()}_selection"
        return [(safe_name(name), world, True)]
    meshes = [asset for asset in unreal.EditorUtilityLibrary.get_selected_assets() if isinstance(asset, unreal.StaticMesh)]
    if not meshes:
        raise BridgeError("Select actors in the level, or static meshes in the Content Browser, to send to Blender.")
    return [(safe_name(mesh.get_name()), mesh, False) for mesh in meshes]


def export(subject: object, selected: bool, path: Path) -> None:
    """Write `subject` (a world's selected actors, or a static mesh) to `path` as FBX.

    Raises:
        BridgeError: The exporter refused, with what it said.
    """
    task = unreal.AssetExportTask()
    for name, value in (
        ("object", subject),
        ("filename", str(path)),
        ("selected", selected),
        ("automated", True),
        ("prompt", False),
        ("replace_identical", True),
        ("options", unreal.FbxExportOption()),
    ):
        task.set_editor_property(name, value)
    if not unreal.Exporter.run_asset_export_task(task) or not path.is_file():
        errors = "; ".join(str(error) for error in task.get_editor_property("errors")) or "no reason given"
        raise BridgeError(f"Unreal could not export {path.name}: {errors}")


def spool() -> Path:
    """The directory Blender's session takes requests from."""
    return Path(os.environ.get(SPOOL_VARIABLE, DEFAULT_SPOOL))


def hand_to_blender(files: list[tuple[str, Path]]) -> Path:
    """Put a request in Blender's spool to import `files`, and return the request's path."""
    directory = spool()
    directory.mkdir(parents=True, exist_ok=True)
    code = f"FILES = {[(name, str(path)) for name, path in files]!r}\n{BLENDER_IMPORT}"
    stem = f"{time.time_ns()}-unreal-{os.getpid()}"
    partial = directory / f"{stem}.tmp"
    partial.write_text(code)
    request = partial.with_suffix(".py")
    partial.rename(request)
    return request


class Answer:
    """Waits for Blender's answer to a request on the editor's Slate tick, and logs it."""

    def __init__(self, request: Path, what: str) -> None:
        self.request = request
        self.answer = request.with_suffix(".json")
        self.what = what
        self.waited = 0.0
        self.since_check = 0.0
        self.handle = None

    def start(self) -> None:
        """Look for the answer on every tick from now until it comes or the wait is over."""
        self.handle = unreal.register_slate_post_tick_callback(self.tick)

    def stop(self) -> None:
        unreal.unregister_slate_post_tick_callback(self.handle)

    def tick(self, delta_seconds: float) -> None:
        self.waited += delta_seconds
        self.since_check += delta_seconds
        if self.since_check < POLL_SECONDS:
            return
        self.since_check = 0.0
        if self.answer.is_file():
            self.stop()
            reply = json.loads(self.answer.read_text())
            self.answer.unlink()
            if reply.get("ok"):
                unreal.log(f"Lathe bridge: Blender imported {self.what}. {reply.get('output', '').strip()}")
            else:
                unreal.log_error(f"Lathe bridge: Blender could not import {self.what}:\n{reply.get('error')}")
        elif self.request.is_file() and self.waited > CLAIM_SECONDS:
            self.stop()
            self.request.unlink(missing_ok=True)
            unreal.log_warning(
                f"Lathe bridge: no Blender took {self.what} within {CLAIM_SECONDS} s; open Blender and send again."
            )
        elif self.waited > ANSWER_SECONDS:
            self.stop()
            unreal.log_warning(f"Lathe bridge: Blender did not finish importing {self.what} within {ANSWER_SECONDS // 60} min.")


def send_selection() -> str:
    """Export the selection to the bridge folder and have Blender import it; returns what was sent.

    The outcome of Blender's import arrives later, in the Output Log.

    Raises:
        BridgeError: Nothing is selected, or an export failed.
    """
    folder = project_folder() / BRIDGE_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for name, subject, selected in selection():
        path = folder / f"{name}.fbx"
        export(subject, selected, path)
        files.append((name, path))
    what = ", ".join(name for name, _ in files)
    Answer(hand_to_blender(files), what).start()
    unreal.log(f"Lathe bridge: sent {what} to Blender from {folder}")
    return what


def menu_action() -> None:
    """Send to Blender as the Tools menu runs it: a refusal is a line in the Output Log, not a traceback."""
    try:
        send_selection()
    except BridgeError as error:
        unreal.log_error(f"Lathe bridge: {error}")
