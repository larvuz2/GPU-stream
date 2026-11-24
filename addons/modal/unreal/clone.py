#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Clone the session's game repository into its project folder, or bring an earlier clone up to date.

    selkies-modal-unreal-clone [FOLDER]
    selkies-modal-unreal-clone --status

A Lathe project linked to a GitHub repository starts its Unreal session with
that repository in the session's environment, from a Modal Secret made for the
start (`start_session`'s `secrets` in `addons/modal/sandbox.py`):
`LATHE_GIT_REPO` (`owner/name`), `LATHE_GIT_BRANCH` (else the repository's
default branch), `LATHE_GIT_TOKEN` (a GitHub App user token that reads and
writes that repository for eight hours), and `LATHE_GIT_NAME` and
`LATHE_GIT_EMAIL`, whom the developer's commits are by. The session's autostart
runs this in the background as the desktop comes up, so the developer finds
their game there as they would at their desk, without signing in to GitHub in
the machine. Without `LATHE_GIT_REPO` it does nothing (status 2), and the
developer clones by hand as before.

**Where.** The clone is `FOLDER/<name>`, FOLDER being the folder the GitHub
client's clone dialog offers (`selkies-modal-unreal-github --clone-folder`: the
project folder, else the workspace's `projects`), which is on the workspace
Volume and so there at every later start:

- Nothing there yet, or an empty folder: Git clones into a hidden folder beside
  it (`.<name>.cloning`), which is moved into place once Git has the whole
  repository, so a session that ends halfway leaves no half repository that the
  next would take for the clone; that next one removes the hidden folder and
  starts again.
- A clone of the same repository, from an earlier session: the branch is
  fetched, and the clone fast-forwarded to it only when it is on that branch and
  no tracked file has changed. Local changes, local commits, and another branch
  are never touched: the status says the clone was not updated, and why.
- Anything else: left as it is, and the clone fails saying so.

**Git LFS.** Git checks the files out with LFS's download skipped
(`GIT_LFS_SKIP_SMUDGE`), which would otherwise fetch each LFS file on its own as
it is written, and `git lfs pull` then fetches them in batches. Git LFS prints
no progress where its output is not a terminal, so its progress comes from the
file it writes a line to for each transfer (`GIT_LFS_PROGRESS`): how many of
the files have arrived becomes the status's detail. LFS is installed
system-wide in the image, so the clone has LFS's hooks, as one made at a desk
with LFS set up does.

**The token.** Git reaches it only through a credential helper,
`selkies-modal-unreal-git-credential`, which reads it from the environment of
the Git that asks. These commands alone are given that helper, through Git's
configuration from the environment (`GIT_CONFIG_COUNT`), and every other helper
is cleared for them first: a helper the developer set up, such as one storing
into the keyring in the workspace, is never handed the token to keep. Git asks
for it only when GitHub refuses without one, so a public repository is cloned
without sending it. The remote is the repository's plain address, and neither
it, `.git/config`, Git's output, nor the status holds the token. No prompt is
ever shown: a refused token fails the clone.

**Status.** A JSON object in the file `SELKIES_MODAL_UNREAL_CLONE_STATUS`,
replaced whole at each change: `state` (`cloning`, `done`, or `failed`), `path`
(the clone's folder, null until it is known), and `detail`, a line saying what
happened or is happening. `--status` prints it, which is what `clone_status` in
`sandbox.py` reads, and before this has started, `cloning` with no path. The
same lines go to standard output in the form zenity's progress dialog reads
(`# text`), which the autostart shows over the GitHub client; the clone goes on
when the dialog is closed. While it runs, the clone counts as use of the session
(`SELKIES_MODAL_ACTIVITY_FILE`), so the idle timeout does not cut a large one
short.

The exit status is 0 when the clone is there (`done`), 1 when it is not
(`failed`), and 2 when there is nothing to clone.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO

GITHUB = "https://github.com"
# Run as a command found on PATH (`!`), where a bare name would be `git credential-<name>`
HELPER = "!selkies-modal-unreal-git-credential"
# A part of `owner/name` as GitHub allows it
NAME = re.compile(r"[A-Za-z0-9_.-]+")
# The remotes that name a GitHub repository, over HTTPS or SSH
REMOTE = re.compile(r"(?:https://github\.com/|ssh://git@github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?/?", re.I)
# The lines of Git that say how far a step is
PROGRESS = re.compile(r"(Receiving objects|Resolving deltas|Updating files):.*")
# A line of Git LFS's progress file: the transfer's number of all of them, the bytes of the file so far of its size, and the file
LFS_TRANSFER = re.compile(r"download \d+/(\d+) (\d+)/(\d+) (.+)")
# Seconds between two progress updates of the status, and between two touches of the activity file
PROGRESS_INTERVAL = 0.5
ACTIVITY_INTERVAL = 10


class Failed(Exception):
    """The clone is not where it should be; the message is the status's detail."""


class GitError(Exception):
    """A Git command ended with an error; `lines` is what it printed on standard error."""

    def __init__(self, lines: list[str]) -> None:
        super().__init__(lines[-1] if lines else "Git failed without saying why")
        self.lines = lines


class Status:
    """What the clone is doing, kept in the status file and fed to the progress dialog on standard output.

    The file is written beside itself and renamed over, so a reader never
    finds half of one. Progress within a step is written at most every
    `PROGRESS_INTERVAL` seconds; anything else at once.
    """

    def __init__(self, file: Path) -> None:
        self.file = file
        self.path: Path | None = None
        self.state = "cloning"
        self.detail = ""
        self.written = 0.0

    def set(self, state: str, detail: str, *, progress: bool = False) -> None:
        """Record a state and its detail, and show the detail in the dialog."""
        now = time.monotonic()
        if progress and now - self.written < PROGRESS_INTERVAL:
            return
        self.state, self.detail, self.written = state, detail, now
        replacement = self.file.with_name(f"{self.file.name}.new")
        replacement.write_text(json.dumps({"state": state, "path": self.path and str(self.path), "detail": detail}) + "\n")
        replacement.replace(self.file)
        feed(f"# {detail}")


def feed(line: str) -> None:
    """Write a line for the progress dialog, which may have been closed: the clone carries on without it."""
    try:
        print(line, flush=True)
    except BrokenPipeError:
        # What Python's documentation does on a closed pipe, so its exit does not flush into it again
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())


def git_environment() -> dict[str, str]:
    """The environment of every Git command here: the token's helper as the only one, and no prompt of any kind."""
    environment = dict(os.environ)
    first = int(environment.get("GIT_CONFIG_COUNT") or 0)
    pairs = (("credential.helper", ""), (f"credential.{GITHUB}.helper", HELPER))
    for index, (key, value) in enumerate(pairs, first):
        environment[f"GIT_CONFIG_KEY_{index}"] = key
        environment[f"GIT_CONFIG_VALUE_{index}"] = value
    environment["GIT_CONFIG_COUNT"] = str(first + len(pairs))
    environment["GIT_TERMINAL_PROMPT"] = "0"
    # Set and empty, which keeps Git from asking any graphical prompt the desktop offers
    environment["GIT_ASKPASS"] = ""
    return environment


def git(arguments: list[str], folder: Path, status: Status | None = None, **variables: str) -> str:
    """Run Git in `folder` and return its output, or with `status` what it printed on standard error.

    With `status`, each progress line Git prints becomes the status's detail
    as it comes.

    Raises:
        GitError: Git ended with an error.
    """
    command = ["git", *arguments]
    environment = {**git_environment(), **variables}
    if status is None:
        done = subprocess.run(command, cwd=folder, env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True)
        if done.returncode != 0:
            raise GitError(done.stderr.strip().splitlines())
        return done.stdout
    process = subprocess.Popen(
        command, cwd=folder, env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    lines = read_progress(process.stderr, status)
    if process.wait() != 0:
        raise GitError(lines)
    return "\n".join(lines)


def read_progress(stream: IO[bytes], status: Status) -> list[str]:
    """The lines Git prints on `stream`, as it rewrites them in place with carriage returns, each progress one shown."""
    lines: list[str] = []
    pending = b""
    while chunk := os.read(stream.fileno(), 65536):
        *complete, pending = re.split(rb"[\r\n]", pending + chunk)
        for raw in complete:
            line = " ".join(raw.decode(errors="replace").split())
            if not line:
                continue
            lines.append(line)
            if PROGRESS.fullmatch(line):
                status.set("cloning", line.removesuffix(", done."), progress=True)
    if tail := " ".join(pending.decode(errors="replace").split()):
        lines.append(tail)
    return lines[-200:]


def explain(repository: str, error: GitError) -> str:
    """The status's detail for a Git command that failed: GitHub's refusal in words, else Git's last error."""
    text = "\n".join(error.lines)
    last = next((line for line in reversed(error.lines) if line.startswith(("fatal:", "error:"))), str(error))
    missing = re.search(r"Remote branch (\S+) not found", text)
    if missing:
        return f"{repository} has no branch {missing.group(1)} ({last})"
    if re.search(r"Repository not found|could not read Username|Authentication failed|Invalid username or token", text):
        return f"GitHub did not let this session read {repository}: it does not exist, or the session's token cannot read it ({last})"
    return last


def checked_repository(value: str) -> str:
    """`LATHE_GIT_REPO` as `owner/name`, each part a name GitHub allows and neither `.` nor `..`."""
    parts = value.split("/")
    if len(parts) != 2 or not all(NAME.fullmatch(part) and part not in (".", "..") for part in parts):
        raise Failed(f"LATHE_GIT_REPO={value!r} is not a GitHub repository such as owner/name")
    return value


def checked_branch(value: str, folder: Path) -> str:
    """`LATHE_GIT_BRANCH` as Git takes a branch name, or empty for the repository's default branch."""
    if value:
        try:
            git(["check-ref-format", "--branch", value], folder)
        except GitError:
            raise Failed(f"LATHE_GIT_BRANCH={value!r} is not a branch name") from None
    return value


def clone_folder() -> Path:
    """The folder the GitHub client's clone dialog offers, made if missing."""
    done = subprocess.run(["selkies-modal-unreal-github", "--clone-folder"], capture_output=True, text=True)
    if done.returncode != 0 or not done.stdout.strip():
        raise Failed(f"the clone folder could not be made: {done.stderr.strip()}")
    return Path(done.stdout.strip())


def is_clone_of(folder: Path, repository: str) -> bool:
    """Whether `folder` is the top of a Git repository whose `origin` is `repository` on GitHub.

    Raises:
        Failed: Git would not read the repository there, with its reason.
    """
    if not (folder / ".git").exists():
        return False
    try:
        top = git(["rev-parse", "--show-cdup"], folder).strip()
    except GitError as error:
        raise Failed(f"{folder} is a Git repository that Git would not read ({error})") from None
    try:
        remote = git(["config", "--get", "remote.origin.url"], folder).strip()
    except GitError:
        return False
    match = REMOTE.fullmatch(remote)
    return not top and match is not None and match.group(1).lower() == repository.lower()


def configure(clone: Path) -> None:
    """Set what the clone's own configuration holds for the session: the developer's identity, and how Git sees a change.

    The developer's name and address, where the session was given them, are
    what the clone's commits carry. `core.checkStat=minimal` has Git tell a
    changed file by its size and modification time alone: the clone is on the
    workspace Volume, which each session reads from a new machine, where every
    file has another inode than the one Git recorded, so by default Git reads
    the whole clone, and each LFS file through LFS's filter, to find what
    changed. Measured on a 400 MB sample: `git status` took 150 s at a
    session's start and 10 s alone on a new machine, and 0.3 s with this. The
    Volume keeps sizes and modification times to the nanosecond.
    """
    for key, variable in (("user.name", "LATHE_GIT_NAME"), ("user.email", "LATHE_GIT_EMAIL")):
        value = os.environ.get(variable, "").strip()
        if value:
            git(["config", key, value], clone)
    git(["config", "core.checkStat", "minimal"], clone)


def head(clone: Path) -> str:
    """The commit the clone has checked out, abbreviated."""
    return git(["rev-parse", "--short", "HEAD"], clone).strip()


def lfs_files(progress: Path) -> tuple[int, int] | None:
    """How many Git LFS files have arrived, of how many, by Git LFS's progress file; None before the first transfer."""
    try:
        lines = progress.read_text(errors="replace").splitlines()
    except FileNotFoundError:
        return None
    arrived: set[str] = set()
    total = 0
    for line in lines:
        transfer = LFS_TRANSFER.fullmatch(line)
        if transfer:
            total = int(transfer.group(1))
            if transfer.group(2) == transfer.group(3):
                arrived.add(transfer.group(4))
    return (len(arrived), total) if total else None


def pull_lfs(clone: Path, status: Status) -> str:
    """Fetch and check out the Git LFS files of what the clone has checked out, and say how many arrived.

    Raises:
        Failed: Git LFS did not fetch them, with its reason.
    """
    status.set("cloning", "fetching the Git LFS files")
    progress = status.file.with_name(f"{status.file.name}.lfs")
    progress.unlink(missing_ok=True)
    process = subprocess.Popen(
        ["git", "lfs", "pull"],
        cwd=clone,
        env={**git_environment(), "GIT_LFS_PROGRESS": str(progress)},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    errors: list[str] = []
    # Read on a thread of its own, so Git LFS never waits on a full pipe while the file is watched
    reader = threading.Thread(target=lambda: errors.extend(process.stderr.read().decode(errors="replace").splitlines()))
    reader.start()
    while process.poll() is None:
        files = lfs_files(progress)
        if files:
            status.set("cloning", f"fetching the Git LFS files: {files[0]} of {files[1]}", progress=True)
        time.sleep(PROGRESS_INTERVAL)
    reader.join()
    files = lfs_files(progress)
    progress.unlink(missing_ok=True)
    if process.returncode != 0:
        reason = errors[-1] if errors else f"status {process.returncode}"
        raise Failed(f"{clone} is there, but its Git LFS files were not fetched ({reason})")
    return f"; {files[0]} Git LFS files fetched" if files else ""


def clone(target: Path, repository: str, branch: str, status: Status) -> str:
    """Clone `repository` into `target`, which is not there or is empty, and return the status's detail."""
    staging = target.with_name(f".{target.name}.cloning")
    shutil.rmtree(staging, ignore_errors=True)
    status.set("cloning", f"cloning {repository}")
    try:
        git(
            ["clone", "--progress", *(["--branch", branch] if branch else []), "--", f"{GITHUB}/{repository}.git", str(staging)],
            target.parent,
            status,
            GIT_LFS_SKIP_SMUDGE="1",
        )
        staging.replace(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    configure(target)
    branch = git(["symbolic-ref", "--short", "HEAD"], target).strip()
    fetched = pull_lfs(target, status)
    return f"cloned {repository} at {branch} ({head(target)}){fetched}"


def update(target: Path, repository: str, branch: str, status: Status) -> str:
    """Fetch the branch into the earlier clone in `target`, fast-forward it where nothing local is in the way, and say what happened.

    The clone is there whatever happens, so what keeps it from being updated,
    GitHub's refusal included, is the detail of a clone that is done.
    """
    url = f"{GITHUB}/{repository}.git"
    configure(target)
    status.set("cloning", f"fetching {repository}")
    try:
        if not branch:
            default = re.search(r"^ref: refs/heads/(\S+)\tHEAD$", git(["ls-remote", "--symref", "--", url, "HEAD"], target), re.M)
            if default is None:
                return f"not updated: GitHub named no default branch of {repository}"
            branch = default.group(1)
        # From the plain address rather than `origin`, which may be another form of it
        git(["fetch", "--progress", "--", url, f"+refs/heads/{branch}:refs/remotes/origin/{branch}"], target, status)
    except GitError as error:
        return f"not updated: {explain(repository, error)}"
    try:
        current = git(["symbolic-ref", "--quiet", "--short", "HEAD"], target).strip()
    except GitError:
        current = ""
    if current != branch:
        return f"on {f'branch {current}' if current else 'a detached commit'}, not {branch}: not updated (origin/{branch} fetched)"
    status.set("cloning", "looking for local changes")
    if git(["status", "--porcelain", "--untracked-files=no"], target).strip():
        return f"has local changes, not updated (origin/{branch} fetched)"
    before = head(target)
    try:
        git(["merge", "--ff-only", f"origin/{branch}"], target, GIT_LFS_SKIP_SMUDGE="1")
    except GitError as error:
        if "fast-forward" in str(error):
            return f"has commits that are not on origin/{branch}, not updated (origin/{branch} fetched)"
        raise
    fetched = pull_lfs(target, status)
    after = head(target)
    if after == before:
        return f"up to date with origin/{branch} ({after}){fetched}"
    return f"updated from {before} to {after}, origin/{branch}{fetched}"


def keep_session_in_use() -> None:
    """Touch the session's activity file every `ACTIVITY_INTERVAL` seconds while this runs, as a command the launcher runs does."""
    activity = os.environ.get("SELKIES_MODAL_ACTIVITY_FILE")
    if not activity:
        return

    def touch() -> None:
        while True:
            try:
                Path(activity).touch()
            except OSError:
                pass
            time.sleep(ACTIVITY_INTERVAL)

    threading.Thread(target=touch, daemon=True).start()


def status_file() -> Path:
    """The status file the image names."""
    name = os.environ.get("SELKIES_MODAL_UNREAL_CLONE_STATUS")
    if not name:
        sys.exit("selkies-modal: SELKIES_MODAL_UNREAL_CLONE_STATUS names the clone's status file; the image sets it")
    return Path(name)


def show_status() -> int:
    """Print the status, or, before the clone has started, that it is about to."""
    try:
        sys.stdout.write(status_file().read_text())
    except FileNotFoundError:
        if not os.environ.get("LATHE_GIT_REPO"):
            print("selkies-modal: this session was not given a repository to clone", file=sys.stderr)
            return 2
        print(json.dumps({"state": "cloning", "path": None, "detail": "waiting for the desktop to start the clone"}))
    return 0


def main(arguments: list[str]) -> int:
    """Clone or update the repository and record how it went, one run at a time."""
    if arguments == ["--status"]:
        return show_status()
    if len(arguments) > 1 or arguments[:1] and arguments[0].startswith("-"):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    repository = os.environ.get("LATHE_GIT_REPO", "").strip()
    if not repository:
        print("selkies-modal: this session was not given a repository to clone", file=sys.stderr)
        return 2
    status = Status(status_file())
    # One run at a time: a second waits, then finds the first one's clone and updates it
    with open(f"{status.file}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        keep_session_in_use()
        try:
            checked_repository(repository)
            folder = Path(arguments[0]) if arguments else clone_folder()
            folder.mkdir(parents=True, exist_ok=True)
            branch = checked_branch(os.environ.get("LATHE_GIT_BRANCH", "").strip(), folder)
            status.path = folder / repository.split("/")[1]
            if not status.path.exists() or (status.path.is_dir() and not any(status.path.iterdir())):
                detail = clone(status.path, repository, branch, status)
            elif is_clone_of(status.path, repository):
                detail = update(status.path, repository, branch, status)
            else:
                raise Failed(f"{status.path} already holds something that is not a clone of {repository}; it was left as it is")
        except GitError as error:
            status.set("failed", explain(repository, error))
            return 1
        except Failed as failure:
            status.set("failed", str(failure))
            return 1
        else:
            status.set("done", detail)
            return 0
        finally:
            # The end of the progress dialog's bar, which closes it
            feed("100")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
