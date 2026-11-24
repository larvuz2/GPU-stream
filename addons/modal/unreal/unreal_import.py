# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The Unreal Editor's half of Send to Unreal: import what Blender put in the bridge folder.

Blender's add-on (`send_to_unreal.py`) has the editor run this file through
its Remote Control API and calls `import_manifest` with the path of the
manifest it wrote beside the exported file. It runs in the editor's own Python
(3.11, with the `unreal` module), on the editor's main thread, and returns what
it did for the add-on to report; anything it raises comes back to Blender as
the traceback of the call.

One `AssetImportTask` imports the file into `/Game/Blender/<name>`, replacing
what an earlier send of the same name made and saving it, with no dialog
(`automated`). A static mesh is glTF, which Interchange imports with its own
defaults: the format fixes its units and axes, so there is nothing to choose.
A rig is FBX, imported through the FBX importer's options as a skeletal mesh
with its animations, materials, textures, morph targets, and a physics asset,
converted from the file's axes and units to Unreal's (`convert_scene`,
`convert_scene_unit`); Blender writes the file's unit into it.

When the manifest asks to place it, each imported mesh gets an actor at the
level's origin in the level open in the editor: the importers keep each mesh's
transform in its vertices, so the origin is where Blender had it. An actor is
tagged with the asset it shows, so sending the same asset again updates the
actor already placed instead of adding a second.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import unreal

DESTINATION_ROOT = "/Game/Blender"
PLACED_TAG = "lathe-bridge:"
NAME = re.compile(r"[A-Za-z0-9_]+")
KINDS = {"static": "gltf", "skeletal": "fbx"}


def read_manifest(path: Path) -> dict:
    """The manifest at `path`, checked: a name Unreal takes, a known kind, and its file beside it.

    Raises:
        ValueError: The manifest is not one the add-on writes, or its file is missing.
    """
    manifest = json.loads(path.read_text())
    name, kind, file = manifest.get("name"), manifest.get("kind"), manifest.get("file")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError(f"{path.name}: the name {name!r} is not one Unreal takes")
    if kind not in KINDS or manifest.get("format") != KINDS[kind]:
        raise ValueError(f"{path.name}: {kind!r} as {manifest.get('format')!r} is not something the bridge imports")
    if not isinstance(file, str) or Path(file).name != file or not (path.parent / file).is_file():
        raise ValueError(f"{path.name}: its file {file!r} is not beside it")
    return manifest


def skeletal_options() -> unreal.FbxImportUI:
    """The FBX importer's options for a rig from Blender."""
    options = unreal.FbxImportUI()
    for name, value in (
        ("automated_import_should_detect_type", False),
        ("import_mesh", True),
        ("import_as_skeletal", True),
        ("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH),
        ("import_animations", True),
        ("import_materials", True),
        ("import_textures", True),
        ("create_physics_asset", True),
    ):
        options.set_editor_property(name, value)
    for data in (options.get_editor_property("skeletal_mesh_import_data"), options.get_editor_property("anim_sequence_import_data")):
        data.set_editor_property("convert_scene", True)
        data.set_editor_property("convert_scene_unit", True)
    options.get_editor_property("skeletal_mesh_import_data").set_editor_property("import_morph_targets", True)
    return options


def import_task(manifest: dict, folder: Path) -> unreal.AssetImportTask:
    """The import of the manifest's file into the content folder named after it."""
    task = unreal.AssetImportTask()
    for name, value in (
        ("filename", str(folder / manifest["file"])),
        ("destination_path", f"{DESTINATION_ROOT}/{manifest['name']}"),
        # Interchange, which imports glTF, names the assets after the file's own and ignores this
        ("destination_name", manifest["name"]),
        ("automated", True),
        ("replace_existing", True),
        ("save", True),
        ("options", skeletal_options() if manifest["kind"] == "skeletal" else None),
    ):
        task.set_editor_property(name, value)
    return task


def place(assets: list) -> int:
    """Give each mesh an actor at the origin of the open level, unless one placed earlier shows it; returns how many."""
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    shown = {str(tag) for actor in actors.get_all_level_actors() for tag in actor.get_editor_property("tags")}
    placed = 0
    for asset in assets:
        tag = f"{PLACED_TAG}{asset.get_path_name()}"
        if not isinstance(asset, (unreal.StaticMesh, unreal.SkeletalMesh)) or tag in shown:
            continue
        actor = actors.spawn_actor_from_object(asset, unreal.Vector(0.0, 0.0, 0.0))
        actor.set_editor_property("tags", [*actor.get_editor_property("tags"), unreal.Name(tag)])
        placed += 1
    return placed


def import_manifest(manifest_path: str) -> dict:
    """Import what a manifest describes, place it where asked, and say what was done.

    Returns:
        The name, the content folder, the paths of the assets made or updated, and how many actors
        were placed.

    Raises:
        ValueError: The manifest is not one the bridge imports.
        RuntimeError: Unreal imported nothing; its Output Log says why.
    """
    path = Path(manifest_path)
    manifest = read_manifest(path)
    task = import_task(manifest, path.parent)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = [str(item) for item in task.get_editor_property("imported_object_paths")]
    if not imported:
        raise RuntimeError(f"Unreal imported nothing from {manifest['file']}; its Output Log says why")
    placed = place([unreal.EditorAssetLibrary.load_asset(item) for item in imported]) if manifest.get("place") else 0
    unreal.log(f"Lathe bridge: {manifest['name']} imported from Blender into {DESTINATION_ROOT}/{manifest['name']}")
    return {
        "name": manifest["name"],
        "destination": f"{DESTINATION_ROOT}/{manifest['name']}",
        "imported": imported,
        "placed": placed,
    }
