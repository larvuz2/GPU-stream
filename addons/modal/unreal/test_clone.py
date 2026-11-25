# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Tests of `clone.py`, the session's `selkies-modal-unreal-clone`, and the credential helper it gives Git.

GitHub is stood in for by bare repositories in a temporary folder, which Git
reaches in place of `https://github.com/` through `url.<base>.insteadOf` in its
environment, so the command runs as the session runs it, with the remote it
records still GitHub's address. Run with `pytest addons/modal/unreal`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "clone.py"
HELPER = HERE / "git-credential.sh"
TOKEN = "ghu_MoodyTestToken0123456789abcdefABCDEF"


def git(folder: Path, *arguments: str) -> str:
    """Run Git in `folder` as an author with a name, and return what it printed."""
    done = subprocess.run(
        ["git", "-c", "user.name=Upstream", "-c", "user.email=upstream@example.com", *arguments],
        cwd=folder,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout


class Session:
    """A session's environment around a stand-in for GitHub, with the command run as the autostart runs it."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.github = root / "github"
        self.folder = root / "workspace" / "projects"
        self.status = root / "run" / "clone.json"
        self.status.parent.mkdir(parents=True)
        (root / "home").mkdir()
        self.environment = {
            "PATH": os.environ["PATH"],
            "HOME": str(root / "home"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{self.github.as_uri()}/.insteadOf",
            "GIT_CONFIG_VALUE_0": "https://github.com/",
            "SELKIES_MODAL_UNREAL_CLONE_STATUS": str(self.status),
            "MOODY_GIT_REPO": "studio/Capyverse",
            "MOODY_GIT_TOKEN": TOKEN,
            "MOODY_GIT_NAME": "Dev Eloper",
            "MOODY_GIT_EMAIL": "dev@example.com",
        }

    def upstream(self, name: str = "studio/Capyverse") -> Path:
        """A repository on the stand-in GitHub with one commit on `main`, and a working copy that pushes to it."""
        bare = self.github / f"{name}.git"
        bare.mkdir(parents=True)
        git(bare, "init", "--bare", "--initial-branch=main")
        work = self.root / "upstream" / name
        work.mkdir(parents=True)
        git(work, "init", "--initial-branch=main")
        (work / "Capyverse.uproject").write_text('{"EngineAssociation": "5.4"}\n')
        (work / "Config.ini").write_text("[Game]\n")
        git(work, "add", ".")
        git(work, "commit", "-m", "First")
        git(work, "remote", "add", "origin", str(bare))
        git(work, "push", "origin", "main")
        return work

    def run(self, *arguments: str, **variables: str) -> tuple[int, dict]:
        """Run the command over the clone folder and return its exit status and the status it left."""
        environment = {**self.environment, **variables}
        done = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *(arguments or (str(self.folder),))],
            env=environment,
            capture_output=True,
            text=True,
        )
        assert TOKEN not in done.stdout + done.stderr
        status = json.loads(self.status.read_text()) if self.status.exists() else {}
        return done.returncode, status

    @property
    def clone(self) -> Path:
        """Where the clone of `studio/Capyverse` goes."""
        return self.folder / "Capyverse"


@pytest.fixture
def session(tmp_path: Path) -> Session:
    """A session with nothing cloned yet."""
    return Session(tmp_path)


def files_holding(root: Path, needle: bytes) -> list[Path]:
    """Every file under `root` whose bytes contain `needle`."""
    return [path for path in root.rglob("*") if path.is_file() and not path.is_symlink() and needle in path.read_bytes()]


def test_a_first_start_clones_the_repository_with_the_developer_as_author_and_keeps_no_token(session: Session) -> None:
    session.upstream()
    code, status = session.run()
    assert code == 0
    assert status["state"] == "done"
    assert status["path"] == str(session.clone)
    assert (session.clone / "Capyverse.uproject").is_file()
    assert git(session.clone, "config", "--local", "user.name").strip() == "Dev Eloper"
    assert git(session.clone, "config", "--local", "user.email").strip() == "dev@example.com"
    assert git(session.clone, "config", "--local", "core.checkStat").strip() == "minimal"
    assert git(session.clone, "config", "remote.origin.url").strip() == "https://github.com/studio/Capyverse.git"
    assert not list(session.folder.glob(".*.cloning"))
    assert files_holding(session.root, TOKEN.encode()) == []


def test_a_later_start_fast_forwards_a_clean_clone_rather_than_cloning_again(session: Session) -> None:
    upstream = session.upstream()
    session.run()
    (session.clone / "Untracked.txt").write_text("the developer's own notes\n")
    (upstream / "Config.ini").write_text("[Game]\nLevel=Ridge\n")
    git(upstream, "commit", "-am", "Second")
    git(upstream, "push", "origin", "main")
    code, status = session.run()
    assert code == 0
    assert status["state"] == "done"
    assert status["detail"].startswith("updated from")
    assert (session.clone / "Config.ini").read_text() == "[Game]\nLevel=Ridge\n"
    assert (session.clone / "Untracked.txt").is_file()


def test_a_clone_with_local_changes_is_fetched_but_left_as_it_is(session: Session) -> None:
    upstream = session.upstream()
    session.run()
    before = git(session.clone, "rev-parse", "HEAD")
    (session.clone / "Config.ini").write_text("[Game]\nLocal=1\n")
    (upstream / "Capyverse.uproject").write_text('{"EngineAssociation": "5.5"}\n')
    git(upstream, "commit", "-am", "Upgrade")
    git(upstream, "push", "origin", "main")
    code, status = session.run()
    assert code == 0
    assert status["detail"].startswith("has local changes, not updated")
    assert git(session.clone, "rev-parse", "HEAD") == before
    assert (session.clone / "Config.ini").read_text() == "[Game]\nLocal=1\n"
    assert git(session.clone, "rev-parse", "origin/main") == git(upstream, "rev-parse", "HEAD")


def test_a_clone_with_local_commits_is_not_moved(session: Session) -> None:
    upstream = session.upstream()
    session.run()
    (session.clone / "Mine.txt").write_text("mine\n")
    git(session.clone, "add", "Mine.txt")
    git(session.clone, "commit", "-m", "Mine")
    mine = git(session.clone, "rev-parse", "HEAD")
    (upstream / "Theirs.txt").write_text("theirs\n")
    git(upstream, "add", "Theirs.txt")
    git(upstream, "commit", "-m", "Theirs")
    git(upstream, "push", "origin", "main")
    code, status = session.run()
    assert code == 0
    assert "not updated" in status["detail"]
    assert git(session.clone, "rev-parse", "HEAD") == mine


def test_a_folder_holding_something_else_is_left_alone_and_the_clone_fails(session: Session) -> None:
    session.upstream()
    session.clone.mkdir(parents=True)
    (session.clone / "Notes.txt").write_text("not a clone\n")
    code, status = session.run()
    assert code == 1
    assert status["state"] == "failed"
    assert "left as it is" in status["detail"]
    assert (session.clone / "Notes.txt").read_text() == "not a clone\n"
    assert not (session.clone / ".git").exists()


def test_a_repository_that_is_not_there_fails_and_leaves_no_folder(session: Session) -> None:
    code, status = session.run(MOODY_GIT_REPO="studio/Missing")
    assert code == 1
    assert status["state"] == "failed"
    assert status["detail"]
    assert not (session.folder / "Missing").exists()
    assert not list(session.folder.glob(".*.cloning"))


def test_a_branch_that_is_not_there_fails_naming_it(session: Session) -> None:
    session.upstream()
    code, status = session.run(MOODY_GIT_BRANCH="release")
    assert code == 1
    assert "has no branch release" in status["detail"]


def test_a_repository_name_that_could_leave_the_folder_is_refused(session: Session) -> None:
    code, status = session.run(MOODY_GIT_REPO="studio/..")
    assert code == 1
    assert "is not a GitHub repository" in status["detail"]


def test_the_status_before_the_clone_starts_says_it_is_coming(session: Session) -> None:
    done = subprocess.run([sys.executable, "-I", str(SCRIPT), "--status"], env=session.environment, capture_output=True, text=True)
    assert done.returncode == 0
    assert json.loads(done.stdout)["state"] == "cloning"
    without = {key: value for key, value in session.environment.items() if key != "MOODY_GIT_REPO"}
    done = subprocess.run([sys.executable, "-I", str(SCRIPT), "--status"], env=without, capture_output=True, text=True)
    assert done.returncode == 2


@pytest.mark.parametrize(
    ("request_lines", "answered"),
    [
        ("protocol=https\nhost=github.com\n\n", True),
        ("protocol=https\nhost=github.com\npath=studio/Capyverse.git\n\n", True),
        ("protocol=https\nhost=gitlab.com\n\n", False),
        ("protocol=http\nhost=github.com\n\n", False),
    ],
)
def test_the_credential_helper_gives_the_token_to_github_over_https_only(request_lines: str, answered: bool) -> None:
    environment = {"PATH": os.environ["PATH"], "MOODY_GIT_TOKEN": TOKEN}
    done = subprocess.run(["sh", str(HELPER), "get"], input=request_lines, env=environment, capture_output=True, text=True)
    assert done.returncode == 0
    assert (done.stdout == f"username=x-access-token\npassword={TOKEN}\n") is answered
    assert done.stdout == "" or answered
    stored = subprocess.run(["sh", str(HELPER), "store"], input=request_lines, env=environment, capture_output=True, text=True)
    assert stored.stdout == ""


def test_git_reaches_the_token_through_the_helper_alone_and_no_other_helper_keeps_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The configuration the command gives its Git: the token for github.com, and a helper of the developer's never asked to store it."""
    programs = tmp_path / "bin"
    programs.mkdir()
    (programs / "selkies-modal-unreal-git-credential").symlink_to(HELPER)
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("[credential]\n\thelper = store\n")
    for name, value in {
        "PATH": f"{programs}:{os.environ['PATH']}",
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "MOODY_GIT_TOKEN": TOKEN,
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)
    specification = importlib.util.spec_from_file_location("clone", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    environment = module.git_environment()

    asked = "protocol=https\nhost=github.com\npath=studio/Capyverse.git\n\n"
    filled = subprocess.run(["git", "credential", "fill"], input=asked, env=environment, capture_output=True, text=True)
    assert filled.returncode == 0
    assert f"username=x-access-token\npassword={TOKEN}\n" in filled.stdout
    subprocess.run(["git", "credential", "approve"], input=filled.stdout, env=environment, check=True, capture_output=True, text=True)
    assert files_holding(tmp_path, TOKEN.encode()) == []

    elsewhere = subprocess.run(
        ["git", "credential", "fill"], input="protocol=https\nhost=gitlab.com\n\n", env=environment, capture_output=True, text=True
    )
    assert elsewhere.returncode != 0
    assert TOKEN not in elsewhere.stdout
