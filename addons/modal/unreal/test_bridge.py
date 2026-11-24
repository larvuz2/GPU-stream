# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The Blender-Unreal bridge, with real Blender and a stand-in for the Unreal Editor.

Blender runs for real (`BLENDER`, else `blender` on the path; the test skips
naming which is missing): the add-on exports what a scene has selected and
calls the editor's Remote Control API, which here is an HTTP server on
loopback that records each request. The stand-in does what the editor does
with a call of `ExecutePythonCommandEx`: it runs the command it was sent, with
`FakeUnreal` as the `unreal` module, and answers with the function's out
parameters as Remote Control returns them. So the request's shape, the import
script it runs, and the way the add-on reads the reply are checked together.
`FakeUnreal` holds the editor's objects with the property names Epic's Python
reference lists for them, and refuses any other name; what Unreal's importers
and exporters do with a file is not modeled, only that they get the right file
with the right options.

The way back runs the editor's script against `FakeUnreal`, whose exporter
writes an FBX Blender made, and then the real spool: Blender's
`blender/session.py`, loaded as a session loads it, serves the request.

Run with `BLENDER=/path/to/blender pytest addons/modal/unreal`.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import shutil
import socket
import subprocess
import sys
import threading
import traceback
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
MODAL = HERE.parent
sys.path.insert(0, str(HERE))


# The editor, stood in for


class Props:
    """An Unreal object's editor properties: only the names given here exist, as in the editor."""

    def __init__(self, **properties: Any) -> None:
        self.__dict__.update(properties)

    def set_editor_property(self, name: str, value: Any) -> None:
        if name not in self.__dict__:
            raise AttributeError(f"{type(self).__name__} has no editor property {name!r}")
        setattr(self, name, value)

    def get_editor_property(self, name: str) -> Any:
        if name not in self.__dict__:
            raise AttributeError(f"{type(self).__name__} has no editor property {name!r}")
        return getattr(self, name)


class Asset(Props):
    """An asset of the content browser, by its object path."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    def get_path_name(self) -> str:
        return self.path

    def get_name(self) -> str:
        return self.path.rsplit(".", 1)[-1]


class FakeUnreal:
    """The `unreal` module, as far as the bridge's editor-side scripts call it."""

    def __init__(self, exported_fbx: Path | None = None, project: Path = Path("/unreal/Ridge")) -> None:
        self.project = project
        self.tasks: list[Any] = []
        self.assets: dict[str, Asset] = {}
        self.level: list[Any] = []
        self.selected_actors: list[Any] = []
        self.selected_assets: list[Asset] = []
        self.logs: list[tuple[str, str]] = []
        self.ticks: dict[int, Any] = {}
        self.exports: list[Any] = []
        self.exported_fbx = exported_fbx
        self.import_nothing = False
        self.module = self.build()

    def build(self) -> types.ModuleType:
        fake = self
        unreal = types.ModuleType("unreal")

        class Name(str):
            pass

        class Vector:
            def __init__(self, x: float, y: float, z: float) -> None:
                self.x, self.y, self.z = x, y, z

        class StaticMesh(Asset):
            pass

        class SkeletalMesh(Asset):
            pass

        class Actor(Props):
            def __init__(self, label: str, shows: Any = None) -> None:
                super().__init__(tags=[])
                self.label, self.shows = label, shows

            def get_actor_label(self) -> str:
                return self.label

        class World:
            def get_name(self) -> str:
                return "Ridge"

        def import_data(**more: Any) -> Props:
            return Props(convert_scene=True, convert_scene_unit=False, force_front_x_axis=False, import_uniform_scale=1.0, **more)

        class FbxImportUI(Props):
            def __init__(self) -> None:
                super().__init__(
                    automated_import_should_detect_type=True, import_mesh=True, import_as_skeletal=False,
                    mesh_type_to_import=None, import_animations=False, import_materials=True, import_textures=True,
                    create_physics_asset=True, original_import_type=None, skeleton=None,
                    skeletal_mesh_import_data=import_data(import_morph_targets=False, use_t0_as_ref_pose=False),
                    anim_sequence_import_data=import_data(),
                    static_mesh_import_data=import_data(),
                )

        class AssetImportTask(Props):
            def __init__(self) -> None:
                super().__init__(
                    async_=False, automated=False, destination_name="", destination_path="", factory=None, filename="",
                    imported_object_paths=[], options=None, replace_existing=True, replace_existing_settings=False,
                    save=False, result=[],
                )

        class AssetExportTask(Props):
            def __init__(self) -> None:
                super().__init__(
                    automated=False, errors=[], exporter=None, filename="", ignore_object_list=[], object=None,
                    options=None, prompt=True, replace_identical=False, selected=False, use_file_archive=False,
                    write_empty_files=False,
                )

        class AssetTools:
            def import_asset_tasks(self, tasks: list[Any]) -> None:
                for task in tasks:
                    fake.tasks.append(task)
                    if not fake.import_nothing:
                        task.imported_object_paths = fake.imported(task)

        class EditorActorSubsystem:
            def get_all_level_actors(self) -> list[Any]:
                return list(fake.level)

            def get_selected_level_actors(self) -> list[Any]:
                return list(fake.selected_actors)

            def spawn_actor_from_object(self, object_to_use: Any, location: Any, rotation: Any = None, transient: bool = False) -> Any:
                actor = Actor(object_to_use.get_name(), object_to_use)
                fake.level.append(actor)
                return actor

        class UnrealEditorSubsystem:
            def get_editor_world(self) -> Any:
                return World()

        subsystems = {EditorActorSubsystem: EditorActorSubsystem(), UnrealEditorSubsystem: UnrealEditorSubsystem()}

        def run_asset_export_task(task: Any) -> bool:
            fake.exports.append(task)
            shutil.copyfile(fake.exported_fbx, task.filename)
            return True

        def register_slate_post_tick_callback(callback: Any) -> int:
            handle = len(fake.ticks) + 1
            fake.ticks[handle] = callback
            return handle

        unreal.__dict__.update(
            Name=Name, Vector=Vector, StaticMesh=StaticMesh, SkeletalMesh=SkeletalMesh, Actor=Actor,
            FbxImportUI=FbxImportUI, AssetImportTask=AssetImportTask, AssetExportTask=AssetExportTask,
            FbxExportOption=lambda: Props(ascii=False, collision=True, level_of_detail=True, vertex_color=True),
            FBXImportType=types.SimpleNamespace(FBXIT_SKELETAL_MESH="FBXIT_SKELETAL_MESH"),
            EditorActorSubsystem=EditorActorSubsystem, UnrealEditorSubsystem=UnrealEditorSubsystem,
            get_editor_subsystem=lambda cls: subsystems[cls],
            AssetToolsHelpers=types.SimpleNamespace(get_asset_tools=AssetTools),
            EditorAssetLibrary=types.SimpleNamespace(load_asset=lambda path: fake.assets[path]),
            EditorUtilityLibrary=types.SimpleNamespace(get_selected_assets=lambda: list(fake.selected_assets)),
            Exporter=types.SimpleNamespace(run_asset_export_task=run_asset_export_task),
            Paths=types.SimpleNamespace(
                project_dir=lambda: "../../Ridge/",
                convert_relative_path_to_full=lambda path: f"{fake.project}/" if path == "../../Ridge/" else path,
            ),
            register_slate_post_tick_callback=register_slate_post_tick_callback,
            unregister_slate_post_tick_callback=lambda handle: fake.ticks.pop(handle),
            log=lambda text: fake.logs.append(("info", text)),
            log_warning=lambda text: fake.logs.append(("warning", text)),
            log_error=lambda text: fake.logs.append(("error", text)),
        )
        return unreal

    def imported(self, task: Any) -> list[str]:
        """What the editor's importers make of a file: checked to be what its name says, then named as Unreal names them."""
        file = Path(task.filename)
        header = file.read_bytes()[:20]
        folder, stem = task.destination_path, file.stem
        if file.suffix == ".glb":
            assert header.startswith(b"glTF") and int.from_bytes(header[4:8], "little") == 2, "a glTF 2.0 binary"
            made = {f"{folder}/{stem}.{stem}": self.module.StaticMesh, f"{folder}/Material.Material": Asset}
        else:
            assert header.startswith(b"Kaydara FBX Binary"), "a binary FBX"
            made = {f"{folder}/{stem}.{stem}": self.module.SkeletalMesh, f"{folder}/{stem}_Skeleton.{stem}_Skeleton": Asset}
        for path, kind in made.items():
            self.assets[path] = kind(path)
        return list(made)

    @contextlib.contextmanager
    def installed(self):
        """The fake as the `unreal` module, while the editor-side code runs."""
        sys.modules["unreal"] = self.module
        try:
            yield self.module
        finally:
            sys.modules.pop("unreal", None)


class StandInEditor:
    """The Remote Control API on loopback: records each request, and runs the Python it is sent, or refuses."""

    def __init__(self, unreal: FakeUnreal, refuse: tuple[int, dict[str, str]] | None = None) -> None:
        self.unreal = unreal
        self.refuse = refuse
        self.requests: list[dict[str, Any]] = []
        editor = self

        class Handler(BaseHTTPRequestHandler):
            def do_PUT(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                editor.requests.append(
                    {"method": "PUT", "path": self.path, "type": self.headers["Content-Type"], "body": json.loads(body)}
                )
                status, reply = editor.answer(json.loads(body))
                data = json.dumps(reply).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def answer(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """What the editor answers a call of `ExecutePythonCommandEx`: its return value and out parameters."""
        if self.refuse is not None:
            return self.refuse
        printed = io.StringIO()
        result = ""
        with self.unreal.installed(), contextlib.redirect_stdout(printed):
            try:
                exec(compile(body["parameters"]["PythonCommand"], "<remote>", "exec"), {"__name__": "__main__"})
            except Exception:
                result = traceback.format_exc()
        log = [{"Type": "Info", "Output": line} for line in printed.getvalue().splitlines()]
        return 200, {"CommandResult": result, "LogOutput": log, "ReturnValue": result == ""}

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


# Blender, for real


@pytest.fixture(scope="session")
def blender() -> str:
    found = os.environ.get("BLENDER") or shutil.which("blender")
    if not found:
        pytest.skip("no Blender: set BLENDER to a Blender 5.2 binary, or put blender on the path")
    return found


@pytest.fixture
def session_env(tmp_path: Path) -> dict[str, str]:
    """The environment a session gives Blender and the editor: a workspace, a project in it, and the spool."""
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "selkies-modal-project").symlink_to(MODAL / "craft" / "project.sh")
    return {
        **os.environ,
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "SELKIES_MODAL_WORKSPACE": str(tmp_path / "workspace"),
        "SELKIES_MODAL_PROJECT": "projects/ridge",
        "SELKIES_MODAL_BLENDER_SPOOL": str(tmp_path / "spool"),
    }


def run_blender(blender: str, script: str, args: dict[str, Any], env: dict[str, str], tmp_path: Path) -> dict[str, Any]:
    """Run a script in a background Blender with `args`, and return what it wrote as its result."""
    driver, given, result = tmp_path / "driver.py", tmp_path / "args.json", tmp_path / "result.json"
    driver.write_text(script)
    given.write_text(json.dumps({**args, "result": str(result)}))
    done = subprocess.run(
        [blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(driver), "--", str(given)],
        env=env, capture_output=True, text=True, timeout=300,
    )
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    return {**json.loads(result.read_text()), "stdout": done.stdout}


SENDS = r"""
import importlib.util, json, os, sys
import bpy

args = json.loads(open(sys.argv[sys.argv.index("--") + 1]).read())
spec = importlib.util.spec_from_file_location("send_to_unreal", args["addon"])
addon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(addon)
addon.register()

def clear():
    for item in list(bpy.data.objects):
        bpy.data.objects.remove(item)

def mesh():
    clear()
    bpy.ops.mesh.primitive_monkey_add()

def rig():
    clear()
    bpy.ops.object.armature_add()
    armature = bpy.context.object
    bpy.ops.mesh.primitive_cube_add()
    body = bpy.context.object
    body.vertex_groups.new(name="Bone").add(list(range(len(body.data.vertices))), 1.0, "REPLACE")
    body.parent = armature
    body.modifiers.new("Armature", "ARMATURE").object = armature
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

def send(endpoint, place):
    os.environ["LATHE_UNREAL_REMOTE_CONTROL"] = endpoint
    bpy.context.scene.lathe_unreal_place = place
    try:
        return {"result": sorted(bpy.ops.lathe.send_to_unreal()), "error": None}
    except RuntimeError as error:
        return {"result": None, "error": str(error)}

results = {}
for name, scene, endpoint, place in args["sends"]:
    {"mesh": mesh, "rig": rig}[scene]()
    results[name] = send(endpoint, place)
json.dump(results, open(args["result"], "w"))
"""


def closed_port() -> int:
    """A loopback port nothing listens on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_blender_sends_meshes_as_gltf_and_rigs_as_fbx_and_the_editor_imports_them(blender, session_env, tmp_path):
    unreal = FakeUnreal()
    editor = StandInEditor(unreal)
    empty = FakeUnreal()
    empty.import_nothing = True
    importing_nothing = StandInEditor(empty)
    refusing = StandInEditor(unreal, (400, {"errorMessage": "Object Default__PythonScriptLibrary cannot be accessed remotely"}))
    sends = [
        ("elsewhere", "mesh", "http://10.0.0.5:30010", False),
        ("closed", "mesh", f"http://127.0.0.1:{closed_port()}", False),
        ("refused", "mesh", refusing.url, False),
        ("nothing imported", "mesh", importing_nothing.url, False),
        ("mesh", "mesh", editor.url, True),
        ("mesh again", "mesh", editor.url, True),
        ("rig", "rig", editor.url, False),
    ]
    try:
        ran = run_blender(blender, SENDS, {"addon": str(HERE / "send_to_unreal.py"), "sends": sends}, session_env, tmp_path)
    finally:
        for server in (editor, importing_nothing, refusing):
            server.close()

    assert "loopback" in ran["elsewhere"]["error"]
    assert "not running" in ran["closed"]["error"]
    assert "cannot be accessed remotely" in ran["refused"]["error"] and "bEnableRemotePythonExecution" in ran["refused"]["error"]
    assert "could not import Suzanne" in ran["nothing imported"]["error"] and "imported nothing" in ran["nothing imported"]["error"]
    for name in ("mesh", "mesh again", "rig"):
        assert ran[name] == {"result": ["FINISHED"], "error": None}, name
    assert "Sent Suzanne to Unreal: 2 assets in /Game/Blender/Suzanne, 1 placed in the level." in ran["stdout"]

    # The request is the one Remote Control's object/call takes, naming the script library's function by its own names
    bridge = tmp_path / "workspace" / "projects" / "ridge" / "bridge"
    request = editor.requests[0]
    assert (request["method"], request["path"], request["type"]) == ("PUT", "/remote/object/call", "application/json")
    assert request["body"].keys() == {"objectPath", "functionName", "parameters", "generateTransaction"}
    assert request["body"]["objectPath"] == "/Script/PythonScriptPlugin.Default__PythonScriptLibrary"
    assert request["body"]["functionName"] == "ExecutePythonCommandEx"
    assert request["body"]["parameters"].keys() == {"PythonCommand"} and request["body"]["generateTransaction"] is False
    command = request["body"]["parameters"]["PythonCommand"]
    assert repr(str(HERE / "unreal_import.py")) in command and repr(str(bridge / "Suzanne.json")) in command
    assert refusing.requests[0]["body"] == request["body"], "the same call, whatever the editor answers"

    # What was exported, and what the editor was told about it
    assert sorted(path.name for path in bridge.iterdir()) == ["Armature.fbx", "Armature.json", "Suzanne.glb", "Suzanne.json"]
    described = json.loads((bridge / "Suzanne.json").read_text())
    assert described == {
        "version": 1, "name": "Suzanne", "kind": "static", "format": "gltf", "file": "Suzanne.glb", "units": "meters",
        "up_axis": "Y", "blender_units": {"system": "METRIC", "scale_length": 1.0}, "source": None, "place": True,
    }
    rigged = json.loads((bridge / "Armature.json").read_text())
    assert (rigged["kind"], rigged["format"], rigged["file"], rigged["place"]) == ("skeletal", "fbx", "Armature.fbx", False)

    # How the editor imported each, and that sending a mesh again did not place it twice
    mesh, again, rig = unreal.tasks
    assert (mesh.filename, mesh.destination_path, mesh.options) == (str(bridge / "Suzanne.glb"), "/Game/Blender/Suzanne", None)
    assert mesh.automated and mesh.replace_existing and mesh.save and again.filename == mesh.filename
    options = rig.options
    assert rig.filename == str(bridge / "Armature.fbx") and rig.destination_path == "/Game/Blender/Armature"
    assert options.import_as_skeletal and options.mesh_type_to_import == "FBXIT_SKELETAL_MESH" and options.import_animations
    assert not options.automated_import_should_detect_type and options.skeletal_mesh_import_data.import_morph_targets
    assert all(data.convert_scene and data.convert_scene_unit for data in (options.skeletal_mesh_import_data, options.anim_sequence_import_data))
    assert [(actor.label, list(actor.tags)) for actor in unreal.level] == [
        ("Suzanne", ["lathe-bridge:/Game/Blender/Suzanne/Suzanne.Suzanne"])
    ]


def test_the_import_script_takes_only_a_file_beside_its_manifest(tmp_path):
    (tmp_path / "Rock.glb").write_bytes(b"glTF")
    outside = tmp_path / "manifest.json"
    with FakeUnreal().installed():
        script = runpy.run_path(str(HERE / "unreal_import.py"))
        for file in ("../Rock.glb", "/etc/passwd", "Missing.glb"):
            outside.write_text(json.dumps({"name": "Rock", "kind": "static", "format": "gltf", "file": file}))
            with pytest.raises(ValueError, match="not beside it"):
                script["import_manifest"](str(outside))
        outside.write_text(json.dumps({"name": "Rock; rm", "kind": "static", "format": "gltf", "file": "Rock.glb"}))
        with pytest.raises(ValueError, match="not one Unreal takes"):
            script["import_manifest"](str(outside))


SOURCE = r"""
import json, sys
import bpy

args = json.loads(open(sys.argv[sys.argv.index("--") + 1]).read())
bpy.ops.export_scene.fbx(filepath=args["fbx"], use_selection=False, object_types={"MESH"})
json.dump({}, open(args["result"], "w"))
"""

SERVE = r"""
import json, runpy, sys
import bpy

args = json.loads(open(sys.argv[sys.argv.index("--") + 1]).read())
session = runpy.run_path(args["session"])
session["serve"]()
collections = {collection.name: sorted(item.type for item in collection.objects) for collection in bpy.data.collections}
json.dump({"collections": collections}, open(args["result"], "w"))
"""


def test_the_editor_sends_its_selection_back_through_blenders_spool(blender, session_env, tmp_path):
    exported = tmp_path / "from-unreal.fbx"
    run_blender(blender, SOURCE, {"fbx": str(exported)}, session_env, tmp_path)
    unreal = FakeUnreal(exported_fbx=exported)
    unreal.selected_actors = [unreal.module.Actor("Rock 01")]
    with pytest.MonkeyPatch.context() as patch, unreal.installed():
        for name in ("PATH", "SELKIES_MODAL_WORKSPACE", "SELKIES_MODAL_PROJECT", "SELKIES_MODAL_BLENDER_SPOOL"):
            patch.setenv(name, session_env[name])
        editor = runpy.run_path(str(HERE / "send_to_blender.py"))
        assert editor["send_selection"]() == "Rock_01"

    bridge = tmp_path / "workspace" / "projects" / "ridge" / "bridge"
    (task,) = unreal.exports
    assert (task.filename, task.selected, task.automated, task.prompt) == (str(bridge / "Rock_01.fbx"), True, True, False)
    spool = Path(session_env["SELKIES_MODAL_BLENDER_SPOOL"])
    (request,) = spool.glob("*.py")
    assert not list(spool.glob("*.tmp")), "the request is whole before Blender can see it"
    (waiting,) = unreal.ticks.values()

    served = run_blender(
        blender, SERVE, {"session": str(MODAL / "blender" / "session.py")},
        {**session_env, "SELKIES_MODAL_BLENDER_RECOVERY": str(tmp_path / "recovery"), "MODAL_SANDBOX_ID": "sb-test",
         "SELKIES_TOKENS_FILE": str(exported)},
        tmp_path,
    )
    assert served["collections"]["Rock_01"] == ["MESH"], "Blender imported the file into a collection of its own"
    assert not request.exists() and request.with_suffix(".json").is_file()

    waiting(0.5)
    assert unreal.ticks == {} and not request.with_suffix(".json").exists(), "the answer was read and removed"
    level, said = unreal.logs[-1]
    assert level == "info" and "Blender imported Rock_01" in said and "Rock_01: 1 objects" in said


def test_a_request_no_blender_takes_is_taken_back(tmp_path):
    exported = tmp_path / "from-unreal.fbx"
    exported.write_bytes(b"Kaydara FBX Binary  ")
    unreal = FakeUnreal(exported_fbx=exported, project=tmp_path / "Ridge")
    unreal.selected_assets = [unreal.module.StaticMesh("/Game/Props/Crate.Crate"), Asset("/Game/Props/Wood.Wood")]
    spool = tmp_path / "spool"
    with pytest.MonkeyPatch.context() as patch, unreal.installed():
        patch.setenv("PATH", "/usr/bin:/bin")
        patch.setenv("SELKIES_MODAL_BLENDER_SPOOL", str(spool))
        editor = runpy.run_path(str(HERE / "send_to_blender.py"))
        assert editor["send_selection"]() == "Crate", "only static meshes go"
        (request,) = spool.glob("*.py")
        (waiting,) = unreal.ticks.values()
        waiting(editor["CLAIM_SECONDS"] - 1)
        assert request.exists(), "still waiting for a Blender to take it"
        waiting(2)
    assert not request.exists() and unreal.ticks == {}
    assert unreal.logs[-1][0] == "warning" and "no Blender took Crate" in unreal.logs[-1][1]
    assert (tmp_path / "Ridge" / "bridge" / "Crate.fbx").is_file(), "outside a session, the Unreal project's folder"
