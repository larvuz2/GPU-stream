# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""An Unreal Engine project as its Git repository shows it, before any editor runs.

The agent answers "the animations", "the textures", "the maps" of a team's
game from the repository alone (`tool_unreal_assets` in `agent.py`), so the
answer does not wait on an engine that takes long to start, costs credits, and
needs the person's Epic link. What a repository holds is paths and a few text
files, so what this module says of an asset is what its name says:

- **The project.** The `.uproject` nearest the top, no more than
  `PROJECT_DEPTH` folders down (a team keeps it at the top or in a folder such
  as `Game/`); deeper ones are a plugin's test projects or samples. It is JSON:
  `EngineAssociation` is the engine the project needs (a version such as
  `5.4`, a source build's registration GUID in braces, or empty for a project
  inside an engine's own source tree), `Plugins` the plugins it switches on or
  off, and `Modules` its C++ modules, which the editor compiles before it
  opens the project.
- **The assets.** Every `.uasset` and `.umap` under the project's `Content/`
  (mounted as `/Game`) and under the `Content/` of each plugin of its
  `Plugins/` folder, a plugin being a folder with a `.uplugin` at any depth
  there. The files World Partition writes one per actor (`__ExternalActors__`,
  `__ExternalObjects__`) are a map's data, not assets anyone names, and are
  counted apart.
- **The kind.** A `.umap` is a map. A `.uasset` is classified by its name's
  prefix under Epic's recommended asset naming conventions (`EPIC_NAMING`),
  and where Epic's page names no prefix for a type, by the community style
  guides teams follow (`STYLE_GUIDE`, `LOOMAN_GUIDE`). Two prefixes mean two
  things across those guides, `A_` (an animation sequence, or a sound wave) and
  `S_` (a sound wave, or a static mesh), and `AC_` means Epic's actor component
  or the community's animation composite: for those the asset's folder decides
  (`Audio/A_Wind` is a sound), and the first meaning stands where it does not.
  A name with no known prefix is classified by its nearest folder whose name
  says a kind (`Animations/`, `Textures/`, `VFX/`), and is "other" without one.
- **Git LFS.** A `.gitattributes` line with `filter=lfs` stores the files it
  matches with Git LFS, which is how a team keeps its binary assets: Git holds
  a pointer for each, so the paths are all in the tree, and the content is
  fetched with LFS by a clone, not by the contents API.

A name is the team's habit, not the asset's class, so every answer says that it
is by name, and that the editor's Asset Registry gives the exact classes once
an Unreal engine runs on the project.

Once an engine runs, the `.uproject` files the developer cloned into its
workspace are what the machine reports (`unreal_projects` in
`addons/modal/sandbox.py`), and `found_project` puts each in the shape the
agent and the studio read, with how the engine opens it: the version it was
saved with against the engine's (`version_verdict`), which is the table of
`lathe/UNREAL.md`. A project saved with the engine's version opens as it is;
an older one, or one of a source build whose version its file does not say,
opens on the agent's branch, where the editor upgrades what it saves; a newer
one does not open, since Unreal does not open a project in an older editor.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import PurePosixPath
from typing import Any

EPIC_NAMING = (
    "https://dev.epicgames.com/documentation/en-us/unreal-engine/"
    "recommended-asset-naming-conventions-in-unreal-engine-projects"
)
STYLE_GUIDE = "https://github.com/Allar/ue5-style-guide"
LOOMAN_GUIDE = "https://tomlooman.com/unreal-engine-naming-convention-guide/"
KINDS = ("maps", "animations", "textures", "meshes", "materials", "blueprints", "sounds", "effects", "ui", "data", "other")
PROJECT_DEPTH = 3
EXTERNAL = frozenset({"__externalactors__", "__externalobjects__"})

# A name's prefix, before its first underscore and in capitals, and the kinds and types it means, the
# first standing where the asset's folder names none of the others
PREFIXES: dict[str, tuple[tuple[str, str], ...]] = {
    # Epic's recommended asset naming conventions
    "HDR": (("textures", "HDRI"),),
    "M": (("materials", "Material"),),
    "MI": (("materials", "Material Instance"),),
    "PHYS": (("meshes", "Physics Asset"),),
    "PM": (("materials", "Physical Material"),),
    "PPM": (("materials", "Post Process Material"),),
    "SK": (("meshes", "Skeletal Mesh"),),
    "SM": (("meshes", "Static Mesh"),),
    "T": (("textures", "Texture"),),
    "AC": (("blueprints", "Actor Component"), ("animations", "Animation Composite")),
    "ABP": (("animations", "Animation Blueprint"),),
    "BI": (("blueprints", "Blueprint Interface"),),
    "BP": (("blueprints", "Blueprint"),),
    "CT": (("data", "Curve Table"),),
    "DT": (("data", "Data Table"),),
    "E": (("data", "Enum"),),
    "F": (("data", "Structure"),),
    "WBP": (("ui", "Widget Blueprint"),),
    "FXE": (("effects", "Niagara Emitter"),),
    "FXS": (("effects", "Niagara System"),),
    "FXF": (("effects", "Niagara Function"),),
    "RIG": (("animations", "Rig"),),
    "SKEL": (("animations", "Skeleton"),),
    "AM": (("animations", "Animation Montage"),),
    "AS": (("animations", "Animation Sequence"),),
    "BS": (("animations", "Blend Space"),),
    "LS": (("animations", "Level Sequence"),),
    # The community style guide (Allar), for the types Epic's page leaves out
    "A": (("animations", "Animation Sequence"), ("sounds", "Sound Wave")),
    "AO": (("animations", "Aim Offset"),),
    "BPI": (("blueprints", "Blueprint Interface"),),
    "BPFL": (("blueprints", "Blueprint Function Library"),),
    "AIC": (("blueprints", "AI Controller"),),
    "BT": (("blueprints", "Behavior Tree"),),
    "BB": (("blueprints", "Blackboard"),),
    "MF": (("materials", "Material Function"),),
    "MPC": (("materials", "Material Parameter Collection"),),
    "PP": (("materials", "Post Process Material"),),
    "TC": (("textures", "Texture Cube"),),
    "RT": (("textures", "Render Target"),),
    "PS": (("effects", "Cascade Particle System"),),
    "ATT": (("sounds", "Sound Attenuation"),),
    "MIX": (("sounds", "Sound Mix"),),
    "DW": (("sounds", "Dialogue Wave"),),
    "DV": (("sounds", "Dialogue Voice"),),
    "CURVE": (("data", "Curve"),),
    "FONT": (("ui", "Font"),),
    # Tom Looman's guide, after Epic's Lyra sample; its S_ is the community guide's static mesh too
    "S": (("sounds", "Sound Wave"), ("meshes", "Static Mesh")),
    "MSS": (("sounds", "MetaSound Source"),),
    "NS": (("effects", "Niagara System"),),
    "W": (("ui", "Widget Blueprint"),),
    # Common practice that none of the three writes down
    "SC": (("sounds", "Sound Cue"),),
}

# Folder names, in lower case, that say what is in them
FOLDERS: dict[str, frozenset[str]] = {
    "animations": frozenset({"animation", "animations", "anim", "anims", "montages"}),
    "textures": frozenset({"texture", "textures", "tex"}),
    "meshes": frozenset({"mesh", "meshes", "staticmeshes", "skeletalmeshes", "models"}),
    "materials": frozenset({"material", "materials", "mats"}),
    "blueprints": frozenset({"blueprint", "blueprints"}),
    "sounds": frozenset({"audio", "sound", "sounds", "sfx", "music"}),
    "effects": frozenset({"vfx", "fx", "effects", "particles", "niagara"}),
    "ui": frozenset({"ui", "umg", "hud", "widgets"}),
    "data": frozenset({"data", "datatables", "dataassets"}),
}


def within(path: str, folder: str) -> bool:
    """Whether a repository path is a folder or lies inside it; everything lies inside the top, ''."""
    return not folder or path == folder or path.startswith(f"{folder}/")


def parent(path: str) -> str:
    """The folder a repository path is in, '' at the top."""
    return path.rpartition("/")[0]


def find_project(files: list[str], folder: str = "") -> tuple[str | None, list[str]]:
    """The project's `.uproject`, and every other one, among a repository's files.

    The project is the shallowest `.uproject` no more than `PROJECT_DEPTH`
    folders down whose folder holds `folder` or lies inside it, so a folder
    narrows the choice where a repository holds several.
    """
    projects = sorted(
        (path for path in files if path.lower().endswith(".uproject") and path.count("/") <= PROJECT_DEPTH),
        key=lambda path: (path.count("/"), path),
    )
    chosen = next((path for path in projects if within(folder, parent(path)) or within(parent(path), folder)), None)
    return chosen, [path for path in projects if path != chosen]


def read_project(text: str) -> dict[str, Any]:
    """What a `.uproject` says: the engine it needs, its plugins switched on and off, and its C++ modules."""
    try:
        # The editor writes some with a byte order mark, which JSON does not allow
        data = json.loads(text.lstrip("﻿"))
    except ValueError:
        return {"unreadable": "The .uproject is not JSON, so its engine and plugins are not known."}
    if not isinstance(data, dict):
        return {"unreadable": "The .uproject is not a JSON object, so its engine and plugins are not known."}
    association = data.get("EngineAssociation")
    if not isinstance(association, str):
        association = ""
    if association.startswith("{"):
        engine = "a source build registered on the machine that last opened it, not a released version"
    elif association:
        engine = f"Unreal Engine {association}"
    else:
        engine = "none named: the project belongs inside an engine's own source tree"
    plugins = [plugin for plugin in data.get("Plugins") or [] if isinstance(plugin, dict) and isinstance(plugin.get("Name"), str)]
    modules = [module["Name"] for module in data.get("Modules") or [] if isinstance(module, dict) and isinstance(module.get("Name"), str)]
    return {
        "engine_association": association,
        "engine": engine,
        "plugins_enabled": [plugin["Name"] for plugin in plugins if plugin.get("Enabled")],
        "plugins_disabled": [plugin["Name"] for plugin in plugins if not plugin.get("Enabled")],
        "cpp_modules": modules,
    }


def lfs_patterns(text: str) -> list[str]:
    """The patterns a `.gitattributes` stores with Git LFS."""
    patterns = []
    for line in text.splitlines():
        parts = line.split()
        if parts and not parts[0].startswith("#") and "filter=lfs" in parts[1:]:
            patterns.append(parts[0])
    return patterns


def classify(path: str) -> tuple[str, str]:
    """An asset's kind and the type its name says, the type '' where only its folder spoke."""
    folders, _, name = path.rpartition("/")
    stem, _, extension = name.rpartition(".")
    if extension.lower() == "umap":
        return "maps", "Level"
    hinted = next(
        (kind for folder in reversed(folders.split("/")) for kind, names in FOLDERS.items() if folder.lower() in names),
        None,
    )
    prefix, underscore, _ = stem.partition("_")
    meanings = PREFIXES.get(prefix.upper(), ()) if underscore else ()
    if meanings:
        return next((meaning for meaning in meanings if meaning[0] == hinted), meanings[0])
    return hinted or "other", ""


def plugin_files(files: list[str], project: str) -> list[str]:
    """The `.uplugin` files of a project's own plugins, at any depth of its `Plugins/` folder."""
    home = parent(project)
    plugins = f"{home}/Plugins" if home else "Plugins"
    return sorted(path for path in files if path.lower().endswith(".uplugin") and within(path, plugins))


def survey(files: list[str], project: str, folder: str, kind: str | None, shown: int) -> dict[str, Any]:
    """A project's assets by kind: every kind's count, and for `kind` (or each kind) its types and up to `shown` paths.

    `folder` keeps the assets inside it. The paths left out are counted under `more`.
    """
    plugins = plugin_files(files, project)
    roots = [f"{parent(project)}/Content".lstrip("/"), *(f"{parent(path)}/Content" for path in plugins)]
    assets: dict[str, list[tuple[str, str]]] = {name: [] for name in KINDS}
    external = 0
    for path in sorted(files):
        if not path.lower().endswith((".uasset", ".umap")) or not within(path, folder):
            continue
        if not any(within(path, root) for root in roots):
            continue
        if EXTERNAL & {part.lower() for part in path.split("/")}:
            external += 1
            continue
        found, type_name = classify(path)
        assets[found].append((path, type_name))
    listed = {}
    for name in [kind] if kind else KINDS:
        if not assets[name]:
            continue
        types = Counter(type_name or "named by its folder" for _, type_name in assets[name])
        listed[name] = {
            "count": len(assets[name]),
            "types": dict(types.most_common()) if name != "other" else {},
            "paths": [path for path, _ in assets[name][:shown]],
            "more": max(0, len(assets[name]) - shown),
        }
    return {
        "content_roots": roots,
        "project_plugins": [PurePosixPath(path).stem for path in plugins],
        "counts": {name: len(found) for name, found in assets.items()},
        "assets": listed,
        "world_partition_files": external,
    }


def release(version: str) -> tuple[int, ...] | None:
    """An engine version's major and minor release (`5.8.4` is `(5, 8)`), or nothing for one that is not numbers."""
    parts = version.strip().split(".")[:2]
    if len(parts) < 2 or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def version_verdict(association: str, engine: str) -> tuple[str, str]:
    """How an engine of version `engine` opens a project saved with `association`, as a word and a sentence.

    The word is `same`, `older`, `newer`, `source` (a source build's registration GUID, whose
    version the file does not say), or `unknown` (no version named).
    """
    if association.startswith("{"):
        return "source", (
            "Saved with a source build of Unreal, whose version the .uproject does not name: it opens in "
            f"Unreal Engine {engine} on the agent's branch, where the editor upgrades what it saves."
        )
    saved, running = release(association), release(engine)
    if saved is None or running is None:
        return "unknown", f"The .uproject names no engine version: it opens in Unreal Engine {engine} on the agent's branch."
    if saved == running:
        return "same", f"Saved with Unreal Engine {association}, this engine's version: it opens as it is."
    if saved < running:
        return "older", (
            f"Saved with Unreal Engine {association}: it opens in {engine} on the agent's branch, where the editor "
            f"upgrades what it saves; the team's branches stay on {association}."
        )
    return "newer", (
        f"Saved with Unreal Engine {association}, newer than this engine's {engine}: Unreal does not open a project "
        "in an older editor."
    )


def names(items: Any) -> list[str]:
    """The names in a list of names or of objects that name one, switched-off plugins left out.

    A `.uproject` lists modules and plugins as objects (`Name`, `Enabled`); the machine's report
    may write the same in snake case.
    """
    found = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            if not item.get("Enabled", item.get("enabled", True)):
                continue
            item = item.get("Name", item.get("name"))
        if isinstance(item, str) and item:
            found.append(item)
    return found


def lfs_state(raw: dict[str, Any]) -> bool | str | None:
    """Whether a found project's repository keeps files in Git LFS, or the machine's word for their state.

    The report says it as a flag or a word under `lfs`, or as `{used, fetched}` there or under its
    `repository`; a repository whose LFS files are not fetched has pointers in their place, which
    the editor cannot open.
    """
    repository = raw.get("repository")
    lfs = raw.get("lfs", repository.get("lfs") if isinstance(repository, dict) else None)
    if isinstance(lfs, dict):
        if not lfs.get("used"):
            return False
        return True if lfs.get("fetched", True) else "used, but its files are not fetched yet"
    return lfs if isinstance(lfs, (bool, str)) else None


def found_project(raw: dict[str, Any], engine: str) -> dict[str, Any]:
    """A `.uproject` the machine found in its workspace, as the agent and the studio read it.

    `raw` is one entry of the machine's report (`unreal_projects` in `addons/modal/sandbox.py`):
    `path`, `name`, the engine it was saved with (`EngineAssociation`, as the file spells it, or
    `engine_association`), its C++ `modules`, its `plugins`, Git LFS (`lfs_state`), and `size` in
    bytes.
    """
    path = str(raw.get("path") or "")
    association = raw.get("EngineAssociation", raw.get("engine_association"))
    association = association if isinstance(association, str) else ""
    verdict, opens = version_verdict(association, engine)
    size = raw.get("size", raw.get("size_bytes"))
    return {
        "path": path,
        "name": str(raw.get("name") or PurePosixPath(path).stem),
        "engine_association": association,
        "version": verdict,
        "opens": opens,
        "cpp_modules": names(raw.get("modules", raw.get("cpp_modules"))),
        "plugins": names(raw.get("plugins")),
        "lfs": lfs_state(raw),
        "size_bytes": size if isinstance(size, int) and not isinstance(size, bool) else None,
    }
