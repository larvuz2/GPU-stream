# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Send to Unreal: Blender's half of the bridge to the Unreal Editor running beside it.

An Unreal engine is one machine with Blender and the editor on it, sharing the
project folder, so a hand-off is a file and a request on loopback, with no
network between machines. The panel's button (in the 3D viewport's sidebar,
tab Unreal) exports the selection into the project's `bridge/` folder and asks
the editor to import it.

**The file.** Meshes go as glTF binary (`.glb`): the format itself fixes its
units (meters) and up axis (+Y), so nothing about Blender's scene settings has
to reach the importer, and Unreal reads it through Interchange. Anything with an
armature goes as FBX, which carries the skeleton, skin weights, and actions the
way Unreal's skeletal-mesh importer reads them; it is written in Blender's units
(`apply_unit_scale`) with FBX's default axes, which the importer converts. Beside
the file is a manifest, `<name>.json`: the name, the kind (`static` or
`skeletal`), the format, the file's units and up axis, Blender's own unit
settings, the `.blend` it came from, and whether to place it in the open level.
Both are written under another name and renamed, so the editor never reads half
of one.

**The request.** The editor's Remote Control API (`PUT /remote/object/call`,
port 30010) calls `ExecutePythonCommandEx` on the class default object of
Unreal's Python script library. The command is literal Python that runs
`unreal_import.py`, which ships beside this file, and calls its
`import_manifest` on the manifest. It is literal code, not the "file with
arguments" form Epic's reference also allows, so no path has to survive the
editor's argument splitting. The two enum parameters are left out: their zero
values, `ExecuteFile` and `Private`, are the ones wanted (Epic's Python
reference gives both as 0), so no enum spelling has to survive the JSON either.
The reply carries the function's out parameters beside `ReturnValue`:
`CommandResult` is the traceback when the import raised, and `LogOutput` holds
what it printed, among it the one line, after `RESULT_PREFIX`, that says what
was imported.

**What the editor needs.** The Python Editor Script Plugin and the Remote
Control API plugin, with its web server started and remote Python allowed for
the script library (`DefaultRemoteControl.ini` beside this file, which goes in
the Unreal project's `Config` folder). Each missing piece fails differently,
and the report says which: nothing listening and no editor process is the
editor not running; nothing listening with an editor running is the web server
off; Unreal's own refusal is shown with the setting it points at.

**Where.** The endpoint is loopback only (`LATHE_UNREAL_REMOTE_CONTROL` may move
its port, never its host): the Remote Control API has no authentication, and a
request that runs Python is not sent anywhere else. The project folder is the
session's, as `selkies-modal-project` (`addons/modal/craft/project.sh`) prints
it, which is also where the editor's way back writes; outside a session it is
the saved `.blend`'s folder.

Blender waits for the editor's answer, which comes once the import is done:
the import runs on the editor's main thread either way, one send cannot overlap
the next, and the outcome is reported on the button that was pressed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import bpy

bl_info = {
    "name": "Send to Unreal (Lathe)",
    "author": "Lathe",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar > Unreal",
    "description": "Send the selection to the Unreal Editor running beside Blender",
    "category": "Import-Export",
}

IMPORT_SCRIPT = Path(__file__).resolve().parent / "unreal_import.py"
ENDPOINT_VARIABLE = "LATHE_UNREAL_REMOTE_CONTROL"
DEFAULT_ENDPOINT = "http://127.0.0.1:30010"
LOOPBACK = ("127.0.0.1", "localhost", "::1")
CALL_ROUTE = "/remote/object/call"
# The class default object of UPythonScriptLibrary, in the PythonScriptPlugin module
PYTHON_LIBRARY = "/Script/PythonScriptPlugin.Default__PythonScriptLibrary"
EXECUTE = "ExecutePythonCommandEx"
RESULT_PREFIX = "LATHE_BRIDGE "
BRIDGE_FOLDER = "bridge"
MANIFEST_VERSION = 1
# How long the editor may take over an import; a rig with its actions takes a while
CALL_SECONDS = 600


class BridgeError(Exception):
    """A send that did not happen, with what the person can do about it."""


def endpoint() -> str:
    """The editor's Remote Control address, which has to be on this machine.

    Raises:
        BridgeError: `LATHE_UNREAL_REMOTE_CONTROL` names another host.
    """
    url = os.environ.get(ENDPOINT_VARIABLE, DEFAULT_ENDPOINT).rstrip("/")
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in LOOPBACK:
        raise BridgeError(f"{ENDPOINT_VARIABLE}={url} is not on this machine; the editor is reached on loopback only.")
    return url


def project_folder() -> Path:
    """The project folder Blender and the editor share.

    Raises:
        BridgeError: Outside a session, for a `.blend` that was never saved.
    """
    finder = shutil.which("selkies-modal-project")
    if finder is not None:
        return Path(subprocess.run([finder], check=True, capture_output=True, text=True).stdout.strip())
    if bpy.data.filepath:
        return Path(bpy.path.abspath("//"))
    raise BridgeError("Save the .blend first: outside a session, the bridge folder sits beside it.")


def asset_name(active: bpy.types.Object | None, objects: list[bpy.types.Object]) -> str:
    """The name the selection is sent as: the active object's, as an Unreal asset name allows."""
    source = active.name if active is not None and active in objects else objects[0].name
    return re.sub(r"[^A-Za-z0-9_]+", "_", source).strip("_") or "Blender"


def is_rigged(objects: list[bpy.types.Object]) -> bool:
    """Whether the selection has an armature, or a mesh an armature deforms."""
    return any(item.type == "ARMATURE" or item.find_armature() is not None for item in objects)


def export(path: Path, skeletal: bool) -> None:
    """Write the selection to `path`, as FBX for a rig and glTF binary for everything else."""
    if skeletal:
        bpy.ops.export_scene.fbx(
            filepath=str(path),
            use_selection=True,
            object_types={"ARMATURE", "MESH", "EMPTY"},
            apply_unit_scale=True,
            add_leaf_bones=False,
            use_armature_deform_only=True,
            bake_anim=True,
            mesh_smooth_type="FACE",
            path_mode="COPY",
            embed_textures=True,
        )
    else:
        bpy.ops.export_scene.gltf(
            filepath=str(path), export_format="GLB", use_selection=True, export_apply=True, export_yup=True
        )


def write_atomically(path: Path, write) -> None:
    """Have `write` make a file under a temporary name, then move it to `path` in one step.

    The temporary name keeps the suffix, since Blender's exporters add theirs to a path without it.
    """
    partial = path.with_name(f".{path.stem}.partial{path.suffix}")
    write(partial)
    partial.replace(path)


def manifest(name: str, skeletal: bool, file: Path, place: bool) -> dict:
    """What the editor is told about a file: what it is, its units and axes, and where it came from."""
    units = bpy.context.scene.unit_settings
    return {
        "version": MANIFEST_VERSION,
        "name": name,
        "kind": "skeletal" if skeletal else "static",
        "format": "fbx" if skeletal else "gltf",
        "file": file.name,
        # One unit of the file, and which way is up in it: glTF's are the format's own (meters,
        # +Y); the FBX is written in Blender's units with FBX's default axes (-Z forward, +Y up)
        "units": "meters",
        "up_axis": "Y",
        "blender_units": {"system": units.system, "scale_length": units.scale_length},
        "source": bpy.data.filepath or None,
        "place": place,
    }


def import_command(manifest_path: Path) -> str:
    """The Python the editor runs: `unreal_import.py`'s `import_manifest`, its result printed after the prefix."""
    return (
        "import json, runpy\n"
        f"result = runpy.run_path({str(IMPORT_SCRIPT)!r})['import_manifest']({str(manifest_path)!r})\n"
        f"print({RESULT_PREFIX!r} + json.dumps(result))\n"
    )


def editor_running() -> bool:
    """Whether an Unreal Editor process runs on this machine, from the process table."""
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text().strip() == "UnrealEditor":
                return True
        except OSError:
            continue
    return False


def refusal(status: int, body: bytes) -> BridgeError:
    """What Unreal's refusal of the call means, in its own words and the setting they point at."""
    text = body.decode("utf-8", errors="replace").strip()
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        text = next((value for value in parsed.values() if isinstance(value, str) and value), text)
    hint = ""
    if "cannot be accessed remotely" in text:
        hint = " Allow remote Python in the Unreal project: bEnableRemotePythonExecution=True (DefaultRemoteControl.ini)."
    elif "is not allowed" in text:
        hint = (
            " Allow the script library's calls in the Unreal project: CustomAllowedRemoteFunctionCalls for "
            "/Script/PythonScriptPlugin.PythonScriptLibrary (DefaultRemoteControl.ini)."
        )
    elif "PythonScriptLibrary" in text:
        hint = " Turn on the Python Editor Script Plugin in the Unreal project."
    elif status == 404:
        hint = " Turn on the Remote Control API plugin in the Unreal project."
    return BridgeError(f"The Unreal Editor refused the import ({status}: {text[:300] or 'no reason given'}).{hint}")


def call_editor(url: str, command: str) -> dict:
    """Run `command` in the editor's Python through its Remote Control API and return the reply.

    Raises:
        BridgeError: The editor is not running, its web server is off, it refused the call, or it
            did not finish in time.
    """
    body = {
        "objectPath": PYTHON_LIBRARY,
        "functionName": EXECUTE,
        "parameters": {"PythonCommand": command},
        "generateTransaction": False,
    }
    request = urllib.request.Request(
        f"{url}{CALL_ROUTE}",
        data=json.dumps(body).encode(),
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=CALL_SECONDS) as response:
            reply = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        raise refusal(error.code, error.read()) from None
    except (urllib.error.URLError, ConnectionError, TimeoutError) as error:
        if isinstance(getattr(error, "reason", error), TimeoutError):
            raise BridgeError(
                f"The Unreal Editor did not finish within {CALL_SECONDS // 60} min; it may still be importing "
                "(see its Output Log)."
            ) from None
        if editor_running():
            raise BridgeError(
                f"The Unreal Editor is running, but its Remote Control API does not answer on {url}: turn on the "
                "Remote Control API plugin and start its web server (WebControl.StartServer in the editor's console)."
            ) from None
        raise BridgeError(f"The Unreal Editor is not running ({getattr(error, 'reason', error)}). Start it, then send again.") from None
    if not isinstance(reply, dict):
        raise BridgeError("The Unreal Editor answered with something other than a Remote Control reply.")
    return reply


def outcome(name: str, reply: dict) -> str:
    """What the editor's reply says happened, for the report.

    Raises:
        BridgeError: The import raised in the editor; the last line of its traceback says why, and the
            whole traceback goes to Blender's console.
    """
    if reply.get("ReturnValue") is not True:
        trace = str(reply.get("CommandResult") or "").strip()
        print(trace, file=sys.stderr)
        reason = trace.splitlines()[-1] if trace else "no reason given"
        raise BridgeError(f"The Unreal Editor could not import {name}: {reason}")
    for entry in reply.get("LogOutput") or []:
        line = str(entry.get("Output", "")) if isinstance(entry, dict) else ""
        if line.startswith(RESULT_PREFIX):
            result = json.loads(line[len(RESULT_PREFIX):])
            placed = f", {result['placed']} placed in the level" if result.get("placed") else ""
            return f"Sent {name} to Unreal: {len(result['imported'])} assets in {result['destination']}{placed}."
    return f"Sent {name} to Unreal; the editor did not say what it imported."


def send(context: bpy.types.Context, place: bool) -> str:
    """Export the selection into the bridge folder and have the editor import it; returns the report.

    Raises:
        BridgeError: Nothing is selected, the folder cannot be found, or the editor did not import it.
    """
    objects = list(context.selected_objects)
    if not objects:
        raise BridgeError("Select what to send to Unreal.")
    url = endpoint()
    folder = project_folder() / BRIDGE_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    name = asset_name(context.view_layer.objects.active, objects)
    skeletal = is_rigged(objects)
    file = folder / f"{name}.{'fbx' if skeletal else 'glb'}"
    write_atomically(file, lambda partial: export(partial, skeletal))
    manifest_path = folder / f"{name}.json"
    described = json.dumps(manifest(name, skeletal, file, place), indent=2)
    write_atomically(manifest_path, lambda partial: partial.write_text(described))
    return outcome(name, call_editor(url, import_command(manifest_path)))


class LATHE_OT_send_to_unreal(bpy.types.Operator):
    """Export the selection to the project's bridge folder and import it into the Unreal Editor"""

    bl_idname = "lathe.send_to_unreal"
    bl_label = "Send to Unreal"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(context.selected_objects)

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            self.report({"INFO"}, send(context, context.scene.lathe_unreal_place))
        except BridgeError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


class LATHE_PT_send_to_unreal(bpy.types.Panel):
    """The sidebar tab that holds the button."""

    bl_label = "Send to Unreal"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Unreal"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(context.scene, "lathe_unreal_place")
        layout.operator(LATHE_OT_send_to_unreal.bl_idname, icon="EXPORT")
        selected = len(context.selected_objects)
        layout.label(text=f"{selected} selected" if selected else "Nothing selected")


CLASSES = (LATHE_OT_send_to_unreal, LATHE_PT_send_to_unreal)


def register() -> None:
    bpy.types.Scene.lathe_unreal_place = bpy.props.BoolProperty(
        name="Place in level", description="Also place what is sent in the level open in the editor", default=False
    )
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.lathe_unreal_place


# `blender --python send_to_unreal.py` installs it for that Blender, as enabling the add-on does
if __name__ == "__main__":
    register()
