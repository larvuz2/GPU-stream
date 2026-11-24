# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Tests of `projects.py`, the session's `selkies-modal-unreal-projects`, run as the session runs it.

Each test builds a workspace with a cloned-looking repository in a temporary
folder, commits it with Git, and reads what the command prints. Run with
`pytest addons/modal/unreal`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "projects.py"
POINTER = "version https://git-lfs.github.com/spec/v1\noid sha256:{}\nsize 2048\n".format("0" * 64)


def run(folder: Path) -> list[dict]:
    """What `selkies-modal-unreal-projects FOLDER` prints, parsed."""
    done = subprocess.run([sys.executable, "-I", str(SCRIPT), str(folder)], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def write(path: Path, content: str | dict) -> None:
    """Write a file, making its folders, with a dict as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent="\t") if isinstance(content, dict) else content)


def git(folder: Path, *arguments: str) -> None:
    """Run Git in `folder` as an author with a name, so commits work on any machine."""
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *arguments],
        cwd=folder,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A workspace with one game repository cloned into `projects`, as the GitHub client clones it.

    The game is a C++ project saved with 5.4 that enables an engine plugin and
    a Fab plugin, disables one, and has two plugins of its own: one with source,
    one shipped as binaries only. Its assets are Git LFS files, one fetched and
    one still a pointer. Beside it are the folders the search must not enter.
    """
    repository = tmp_path / "projects" / "Capyverse"
    game = repository / "Game"
    write(repository / ".gitattributes", "*.uasset filter=lfs diff=lfs merge=lfs -text\n")
    write(
        game / "CapyverseOdyssey.uproject",
        "﻿"
        + json.dumps(
            {
                "FileVersion": 3,
                "EngineAssociation": "5.4",
                "Modules": [{"Name": "CapyverseOdyssey", "Type": "Runtime", "LoadingPhase": "Default"}],
                "Plugins": [
                    {"Name": "ModelingToolsEditorMode", "Enabled": True},
                    {"Name": "FabThing", "Enabled": True, "MarketplaceURL": "com.epicgames.launcher://ue/Fab/x"},
                    {"Name": "OpenXR", "Enabled": False},
                ],
            }
        ),
    )
    write(game / "Plugins" / "Rope" / "Rope.uplugin", {"FileVersion": 3})
    write(game / "Plugins" / "Rope" / "Source" / "Rope" / "Rope.Build.cs", "// module\n")
    write(game / "Plugins" / "Vendor" / "Prebuilt" / "Prebuilt.uplugin", {"FileVersion": 3})
    write(game / "Plugins" / "Vendor" / "Prebuilt" / "Binaries" / "Linux" / "lib.so", "binary")
    write(game / "Plugins" / "Off" / "Off.uplugin", {"FileVersion": 3, "EnabledByDefault": False})
    write(game / "Content" / "Hero.uasset", "x" * 4096)
    write(game / "Content" / "Rock.uasset", POINTER)
    write(game / "Source" / "CapyverseOdyssey" / "CapyverseOdyssey.Build.cs", "// module\n")
    git(repository, "init", "-q", "-b", "main")
    git(repository, "remote", "add", "origin", "https://someone:secret-token@github.com/studio/capyverse.git")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "game")
    # What a search must skip: regenerated folders and hidden ones, which hold stray project files
    write(game / "Intermediate" / "Stale" / "Stale.uproject", {"EngineAssociation": "5.0"})
    write(game / "Saved" / "Big.bin", "y" * 100_000)
    write(tmp_path / ".home" / "Hidden" / "Hidden.uproject", {"EngineAssociation": "5.0"})
    return tmp_path


def test_finds_the_project_and_skips_regenerated_and_hidden_folders(workspace: Path) -> None:
    projects = run(workspace)
    assert [project["name"] for project in projects] == ["CapyverseOdyssey"]
    assert projects[0]["path"].endswith("projects/Capyverse/Game/CapyverseOdyssey.uproject")


def test_reports_the_engine_the_project_was_saved_with(workspace: Path) -> None:
    project = run(workspace)[0]
    assert project["engine_association"] == "5.4"
    assert project["engine_version"] == "5.4"
    assert [module["name"] for module in project["modules"]] == ["CapyverseOdyssey"]


def test_lists_enabled_plugins_with_where_their_source_is(workspace: Path) -> None:
    plugins = {plugin["name"]: plugin for plugin in run(workspace)[0]["plugins"]}
    assert set(plugins) == {"ModelingToolsEditorMode", "FabThing", "Rope", "Prebuilt"}
    assert plugins["Rope"]["in_repository"] and plugins["Rope"]["source_in_repository"]
    assert plugins["Prebuilt"]["in_repository"] and not plugins["Prebuilt"]["source_in_repository"]
    assert not plugins["ModelingToolsEditorMode"]["in_repository"]
    assert plugins["FabThing"]["marketplace"] and not plugins["ModelingToolsEditorMode"]["marketplace"]


def test_tells_fetched_lfs_files_from_pointers(workspace: Path) -> None:
    repository = run(workspace)[0]["repository"]
    assert repository["lfs"] == {"uses_lfs": True, "files": 2, "fetched": 1, "not_fetched": 1}
    assert repository["branch"] == "main"


def test_reads_a_workspace_mounted_elsewhere_by_the_path_it_was_given(workspace: Path) -> None:
    # A session's workspace is a link to the Volume's mount point, which Git names the repository by
    link = workspace.parent / f"{workspace.name}-mounted"
    link.symlink_to(workspace)
    project = run(link)[0]
    assert project["repository"]["root"].startswith(str(link))
    assert project["repository"]["lfs"]["files"] == 2


def test_keeps_credentials_out_of_the_remote(workspace: Path) -> None:
    remote = run(workspace)[0]["repository"]["remote"]
    assert remote == "https://github.com/studio/capyverse.git"


def test_counts_the_checkout_but_not_regenerated_folders(workspace: Path) -> None:
    project = run(workspace)[0]
    assert 4096 < project["size_bytes"] < 100_000


def test_lists_a_project_whose_descriptor_is_broken(tmp_path: Path) -> None:
    write(tmp_path / "Broken" / "Broken.uproject", "{ not json")
    project = run(tmp_path)[0]
    assert project["name"] == "Broken" and "error" in project
    assert project["engine_version"] is None and project["repository"] is None
