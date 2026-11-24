# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The API, the MCP endpoint, and the agent over the service, with every outside party stood in for.

`FakeStore` answers the calls the service makes to Supabase, its Data API and
its Storage, with the least that keeps them true to the database's functions,
whose own behavior is what the migrations' checks hold; `FakeLauncher` records
what would have reached Modal, `FakeGitHub` what would have reached GitHub,
`FakeFal` what would have reached fal, and `ScriptedModel` answers the agent
the way a scripted conversation says, recording every request it was sent.
What is tested here is this side: who a credential names, what each route and
tool returns and refuses, that one user's sessions, projects, libraries, and
engines are invisible to another, that the agent's conversation only ever
grows, that GitHub's callback takes nothing it did not sign, that the agent
writes to no branch of a repository but its own, that it reads an Unreal
project's assets from the repository alone, and that Unreal Engine starts only
for an account linked to Epic, pulled with that user's own token. Run with
`pytest lathe/control`.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import itertools
import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

import anthropic
import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient

from agent import (
    TOOL_NAMES,
    Agent,
    Claude,
    Reply,
    echoable,
    invalid,
    read_skills,
    replace_tags,
    skills_directory,
    skills_for,
)
from api import create_app
from generation import IMAGE_MODELS, VIDEO_MODELS, Fal, GenerationStopped, video_kilotokens
from github_client import GitHub, GitHubError, Grant, read_state, reads_packages, seal, sign_state, unseal
from launcher import ModalLauncher, origin
from service import OPEN, Catalog, Config, OwnCopy, Refused, Sessions, Store, User, hash_key

CATALOG = Catalog(Path(__file__).resolve().parent.parent / "catalog.json")
ALICE = User(id="00000000-0000-0000-0000-00000000000a", email="alice@example.test")
BOB = User(id="00000000-0000-0000-0000-00000000000b", email="bob@example.test")
TOKENS = {"alice-token": ALICE, "bob-token": BOB}
SECRET = "test-secret-key"
SITE = "https://site.example.test"
SERIAL_TABLES = ("project_events", "agent_messages")
DEFAULTS: dict[str, dict[str, Any]] = {
    "projects": {
        "format": "", "pinned": False, "library_sections": [], "plan": [], "github_repo": None,
        "turn_id": None, "turn_seen_at": None, "stop_requested": False,
    },
    "assets": {"tag": None, "description": "", "metadata": {}, "media": []},
    "project_events": {"data": {}, "turn_id": None},
    "agent_messages": {"turn_id": None},
    "github_connections": {"avatar_url": "", "scope": ""},
}


def text(value: Any) -> str:
    """A column's value as a filter of the Data API spells it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return "null" if value is None else str(value)


def moment() -> datetime:
    return datetime.now(timezone.utc)


class FakeStore:
    """Supabase, as far as the service reaches into it: the database's functions, its tables, and Storage."""

    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.keys: dict[str, dict[str, Any]] = {}
        self.ledger: list[tuple[str, int, str | None]] = []
        self.tables: dict[str, dict[Any, dict[str, Any]]] = {
            "sessions": self.sessions, "api_keys": self.keys,
            **{table: {} for table in ("projects", "assets", "project_events", "agent_messages", "github_connections")},
        }
        self.files: dict[str, tuple[bytes, str]] = {}
        self.serial = itertools.count(1)
        self.clock = itertools.count(1)

    def stamp(self) -> str:
        """Now, a microsecond later each time, so rows sort in the order they were written."""
        return (moment() + timedelta(microseconds=next(self.clock))).isoformat()

    def user_of_token(self, token: str) -> User | None:
        return TOKENS.get(token)

    def rpc(self, function: str, **a: Any) -> Any:
        return getattr(self, function)(**a)

    # The database's functions

    def lathe_ensure_profile(self, p_user: str, p_email: str, p_signup_credits: int) -> dict[str, Any]:
        return self.profiles.setdefault(
            p_user, {"id": p_user, "email": p_email, "credits": p_signup_credits, "max_sessions": 1}
        )

    def lathe_request_session(
        self, p_user: str, p_app: str, p_tier: str, p_region: str, p_credits_per_minute: int, p_capacity: int,
        p_project: str | None = None, p_app_seats: int | None = None,
    ) -> dict[str, Any]:
        profile = self.profiles[p_user]
        projects = self.tables["projects"]
        if p_project is not None and projects.get(p_project, {}).get("user_id") != p_user:
            raise Refused(*Store.REFUSALS["no_project"])
        if profile["credits"] < max(p_credits_per_minute, 1):
            raise Refused(402, "out of credits")
        if sum(s["user_id"] == p_user and s["status"] in OPEN for s in self.sessions.values()) >= profile["max_sessions"]:
            raise Refused(409, "session limit")
        if p_app_seats is not None and sum(s["app"] == p_app and s["status"] in OPEN for s in self.sessions.values()) >= p_app_seats:
            raise Refused(*Store.REFUSALS["no_seats"])
        running = sum(s["status"] in ("starting", "running") for s in self.sessions.values())
        session = {
            "id": str(uuid.uuid4()), "user_id": p_user, "project_id": p_project, "app": p_app, "tier": p_tier,
            "region": p_region, "status": "starting" if running < p_capacity else "queued", "sandbox_id": None,
            "credits_per_minute": p_credits_per_minute, "credits_used": 0, "created_at": "2026-11-21T00:00:00+00:00",
            "claimed_at": "2026-11-21T00:00:00+00:00", "started_at": None, "ended_at": None, "end_reason": None,
        }
        self.sessions[session["id"]] = session
        return dict(session)

    def lathe_session_started(self, p_session: str, p_sandbox_id: str) -> dict[str, Any]:
        session = self.sessions[p_session]
        if session["status"] != "starting":
            return {"id": None}
        session.update(status="running", sandbox_id=p_sandbox_id, started_at="2026-11-21T00:00:10+00:00")
        return dict(session)

    def lathe_end_session(self, p_session: str, p_reason: str, p_failed: bool) -> dict[str, Any]:
        session = self.sessions[p_session]
        if session["status"] not in ("ended", "failed"):
            session.update(status="failed" if p_failed else "ended", end_reason=p_reason, ended_at="2026-11-21T00:10:00+00:00")
        return dict(session)

    def lathe_charge_session(self, p_session: str, p_final: bool) -> int:
        return self.profiles[self.sessions[p_session]["user_id"]]["credits"]

    def lathe_claim_queued(self, p_capacity: int) -> list[dict[str, Any]]:
        running = sum(s["status"] in ("starting", "running") for s in self.sessions.values())
        claimed = [s for s in self.sessions.values() if s["status"] == "queued"][: max(p_capacity - running, 0)]
        for session in claimed:
            session["status"] = "starting"
        return [dict(s) for s in claimed]

    def lathe_queue_position(self, p_session: str) -> int:
        return 1

    def lathe_use_api_key(self, p_key_hash: str) -> str | None:
        key = self.keys.get(p_key_hash)
        return key["user_id"] if key and key["revoked_at"] is None else None

    def lathe_add_credits(self, p_user: str, p_delta: int, p_reason: str, p_reference: str | None) -> int:
        if (p_user, p_delta, p_reference) not in self.ledger:
            self.ledger.append((p_user, p_delta, p_reference))
            self.profiles[p_user]["credits"] += p_delta
        return self.profiles[p_user]["credits"]

    def lathe_begin_turn(self, p_project: str, p_user: str, p_text: str, p_stale_seconds: int) -> str:
        project = self.tables["projects"].get(p_project)
        if project is None or project["user_id"] != p_user:
            raise Refused(*Store.REFUSALS["no_project"])
        if project["turn_id"]:
            if moment() - datetime.fromisoformat(project["turn_seen_at"]) < timedelta(seconds=p_stale_seconds):
                raise Refused(*Store.REFUSALS["turn_running"])
            self.insert("project_events", {"project_id": p_project, "turn_id": project["turn_id"], "kind": "error", "data": {"message": "The previous turn stopped answering."}})
            self.insert("project_events", {"project_id": p_project, "turn_id": project["turn_id"], "kind": "turn_end"})
        turn = str(uuid.uuid4())
        project.update(turn_id=turn, turn_seen_at=moment().isoformat(), stop_requested=False, updated_at=self.stamp())
        self.insert("project_events", {"project_id": p_project, "turn_id": turn, "kind": "user_message", "data": {"text": p_text}})
        return turn

    def lathe_turn_alive(self, p_project: str, p_turn: str) -> bool:
        project = self.tables["projects"].get(p_project)
        if project is None or project["turn_id"] != p_turn or project["stop_requested"]:
            return False
        project["turn_seen_at"] = moment().isoformat()
        return True

    def lathe_end_turn(self, p_project: str, p_turn: str) -> bool:
        project = self.tables["projects"].get(p_project)
        if project is None or project["turn_id"] != p_turn:
            return False
        project.update(turn_id=None, turn_seen_at=None, stop_requested=False)
        self.insert("project_events", {"project_id": p_project, "turn_id": p_turn, "kind": "turn_end"})
        return True

    def lathe_stop_turn(self, p_project: str, p_user: str, p_stale_seconds: int) -> bool:
        project = self.tables["projects"].get(p_project)
        if project is None or project["user_id"] != p_user or not project["turn_id"]:
            return False
        if moment() - datetime.fromisoformat(project["turn_seen_at"]) >= timedelta(seconds=p_stale_seconds):
            self.lathe_end_turn(p_project, project["turn_id"])
        else:
            project["stop_requested"] = True
        return True

    # Tables

    def matching(self, table: str, query: dict[str, str]) -> list[dict[str, Any]]:
        """The stored rows a filter selects, in the order asked for; the rows themselves, not copies."""
        rows = list(self.tables[table].values())
        for column, condition in query.items():
            if column in ("order", "limit", "offset", "select"):
                continue
            operator, _, value = condition.partition(".")
            if operator == "eq":
                rows = [r for r in rows if text(r.get(column)) == value]
            elif operator == "in":
                rows = [r for r in rows if text(r.get(column)) in value.strip("()").split(",")]
            elif operator == "is":
                rows = [r for r in rows if r.get(column) is None]
            elif operator == "gt":
                rows = [r for r in rows if r[column] > int(value)]
            else:
                raise AssertionError(f"no such filter: {condition}")
        if "order" in query:
            column, _, direction = query["order"].partition(".")
            rows.sort(key=lambda r: r[column], reverse=direction == "desc")
        rows = rows[int(query.get("offset", 0)):]
        return rows[: int(query["limit"])] if "limit" in query else rows

    def rows(self, table: str, **query: str) -> list[dict[str, Any]]:
        return copy.deepcopy(self.matching(table, query))

    every = rows

    def check_unique(self, row: dict[str, Any]) -> None:
        """The database's unique tag per project, which the service has to have checked before."""
        if row.get("tag") is not None and any(
            other is not row and other["project_id"] == row["project_id"] and other["tag"] == row["tag"]
            for other in self.tables["assets"].values()
        ):
            raise AssertionError("a duplicate tag reached the database")

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        if table == "api_keys":
            row = {**row, "id": str(uuid.uuid4()), "created_at": "2026-11-21T00:00:00+00:00", "last_used_at": None, "revoked_at": None}
            self.keys[row["key_hash"]] = row
            return dict(row)
        stamp = self.stamp()
        row = {**copy.deepcopy(DEFAULTS[table]), "created_at": stamp, "updated_at": stamp, **copy.deepcopy(row)}
        row.setdefault("id", next(self.serial) if table in SERIAL_TABLES else str(uuid.uuid4()))
        if table == "assets":
            self.check_unique(row)
        self.tables[table][row["user_id"] if table == "github_connections" else row["id"]] = row
        return copy.deepcopy(row)

    def update(self, table: str, changes: dict[str, Any], **query: str) -> list[dict[str, Any]]:
        changed = self.matching(table, query)
        for row in changed:
            row.update(copy.deepcopy(changes))
            if table == "assets":
                self.check_unique(row)
        return copy.deepcopy(changed)

    def delete(self, table: str, **query: str) -> None:
        for row in self.matching(table, query):
            key = next(key for key, stored in self.tables[table].items() if stored is row)
            del self.tables[table][key]
            if table == "projects":
                for owned in ("assets", "project_events", "agent_messages"):
                    self.tables[owned] = {k: r for k, r in self.tables[owned].items() if r["project_id"] != row["id"]}
                for session in self.sessions.values():
                    if session.get("project_id") == row["id"]:
                        session["project_id"] = None

    def upsert(self, table: str, row: dict[str, Any], on_conflict: str) -> dict[str, Any]:
        existing = [stored for stored in self.tables[table].values() if stored[on_conflict] == row[on_conflict]]
        if existing:
            existing[0].update(copy.deepcopy(row))
            return copy.deepcopy(existing[0])
        return self.insert(table, row)

    # Storage

    def upload(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        assert bucket == "library"
        self.files[path] = (data, content_type)

    def sign(self, bucket: str, paths: list[str], seconds: int) -> dict[str, str]:
        return {path: f"https://storage.example.test/{path}?token=signed" for path in paths if path in self.files}

    def remove(self, bucket: str, paths: list[str]) -> None:
        for path in paths:
            self.files.pop(path, None)

    def remove_prefix(self, bucket: str, prefix: str) -> None:
        self.files = {path: kept for path, kept in self.files.items() if not path.startswith(prefix + "/")}


class FakeLauncher:
    """Modal, as far as the service drives it: every Sandbox it was asked for, and what was done to each."""

    def __init__(self) -> None:
        self.started: list[tuple[dict[str, Any], dict[str, Any], str | None]] = []
        self.own_copies: list[OwnCopy | None] = []
        self.credentials: dict[str, dict[str, str]] = {}
        self.stopped: list[str] = []
        self.exits: dict[str, int] = {}
        self.fail_start = False
        self.commands: list[tuple[str, str]] = []
        self.calls: list[tuple[str, str, Any]] = []

    def start(self, session: dict[str, Any], tier: dict[str, Any], region: str | None, own_copy: OwnCopy | None = None) -> str:
        if self.fail_start:
            raise RuntimeError("Please add a payment method to use T4 GPU sandboxes.")
        self.started.append((session, tier, region))
        self.own_copies.append(own_copy)
        return f"sb-{len(self.started)}"

    def keep_registry_credential(self, user_id: str, username: str, token: str, create: bool = True) -> None:
        if create or user_id in self.credentials:
            self.credentials[user_id] = {"REGISTRY_USERNAME": username, "REGISTRY_PASSWORD": token}

    def forget_registry_credential(self, user_id: str) -> None:
        self.credentials.pop(user_id, None)

    def state(self, sandbox_id: str) -> int | None:
        return self.exits.get(sandbox_id)

    def link(self, sandbox_id: str) -> str:
        return f"https://{sandbox_id}.example.test/?_modal_connect_token=x#token=y"

    def stop(self, sandbox_id: str) -> None:
        self.stopped.append(sandbox_id)

    def blender_python(self, sandbox_id: str, code: str) -> tuple[int, str]:
        return (1, "Traceback: boom\n") if "raise" in code else (0, f"ran in {sandbox_id}: {code}\n")

    def screenshot(self, sandbox_id: str) -> bytes:
        return b"\xff\xd8\xff\xe0 a jpeg"

    def exec(self, sandbox_id: str, command: str, timeout: int) -> tuple[int, str]:
        self.commands.append((sandbox_id, command))
        return 0, f"ran in {sandbox_id}\n"

    def filmcraft(self, sandbox_id: str, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        self.calls.append((sandbox_id, method, params))
        return {"ok": True, "method": method}


class InlineJobs:
    """Jobs run at once, in the request that asked for them; a turn runs where an agent is given."""

    sessions: Sessions

    def __init__(self) -> None:
        self.agent: Agent | None = None
        self.turns: list[tuple[str, str]] = []

    def start(self, session_id: str) -> None:
        self.sessions.run_start(session_id)

    def stop(self, session_id: str, reason: str) -> None:
        self.sessions.run_stop(session_id, reason)

    def turn(self, project_id: str, turn_id: str) -> None:
        self.turns.append((project_id, turn_id))
        if self.agent is not None:
            self.agent.run(project_id, turn_id)


class FakeGitHub:
    """GitHub, as far as Lathe reaches it: one account, the codes it grants, its repositories, their branches and files.

    `repo-only-code` is a grant from before Lathe asked for `read:packages`. `linked_to_epic` holds
    the tokens whose account sees Epic's repository and images, and `epic_refusal` is what GitHub
    answers the check with instead, when set.

    A branch points at a commit, and a commit is a snapshot of every file of its repository
    (`commits`), so a test can hold a branch's files before and after. A tree is listed from a
    commit's files the way the Git Trees API lists one, a subtree's SHA naming its commit and
    folder, and a recursive listing longer than `tree_limit` entries comes back truncated, as
    GitHub's does past 100,000. `files`, the walk over those listings, is the real client's.
    """

    authorize_url = staticmethod(GitHub.authorize_url)
    files = GitHub.files

    def __init__(self) -> None:
        self.codes = {
            "good-code": Grant("gho_alice_token", "read:packages,repo"),
            "repo-only-code": Grant("gho_alice_old", "repo"),
            "next-code": Grant("gho_alice_next", "read:packages,repo"),
        }
        self.linked_to_epic: set[str] = set()
        self.epic_refusal: GitHubError | None = None
        self.epic_checks: list[str] = []
        self.repositories: dict[str, dict[str, Any]] = {}
        self.commits: dict[str, dict[str, str]] = {}
        self.refs: dict[tuple[str, str], str] = {}
        self.made_branches: list[tuple[str, str, str]] = []
        self.tree_calls: list[tuple[str, bool]] = []
        self.tree_limit = 100_000
        self.redirects: list[str] = []
        self.tokens: list[str] = []
        self.add_repository("alice-gh/film", push=True, updated="2026-11-20T00:00:00Z")
        self.add_repository("someone/theirs", push=False, updated="2026-11-19T00:00:00Z", private=False)

    def add_repository(
        self, full_name: str, push: bool, updated: str = "2026-11-24T00:00:00Z", private: bool = True,
        files: dict[str, str] | None = None, pull: bool = True,
    ) -> dict[str, Any]:
        """A repository with one commit on `main`, its default branch."""
        self.repositories[full_name] = {
            "full_name": full_name, "private": private, "html_url": f"https://github.com/{full_name}",
            "updated_at": updated, "default_branch": "main", "permissions": {"push": push, "pull": pull},
        }
        self.commit(full_name, "main", files or {"README.md": f"# {full_name}\n"})
        return self.repositories[full_name]

    def commit(self, full_name: str, branch: str, files: dict[str, str]) -> str:
        """Point a branch at a new commit of these files; returns the commit's SHA."""
        sha = f"{len(self.commits) + 1:040x}"
        self.commits[sha] = dict(files)
        self.refs[(full_name, branch)] = sha
        return sha

    def branch_files(self, full_name: str, branch: str) -> dict[str, str]:
        return self.commits[self.refs[(full_name, branch)]]

    def at(self, full_name: str, ref: str | None) -> dict[str, str]:
        """The files at a branch, at a commit, or on the default branch for no ref."""
        if ref is None:
            ref = self.repositories[full_name]["default_branch"]
        if (full_name, ref) in self.refs:
            return self.branch_files(full_name, ref)
        if ref in self.commits:
            return self.commits[ref]
        raise GitHubError(404, f"No commit found for the ref {ref}")

    def exchange(self, client_id: str, client_secret: str, code: str, redirect_uri: str) -> Grant:
        self.redirects.append(redirect_uri)
        if code not in self.codes:
            raise GitHubError(401, "bad_verification_code")
        return self.codes[code]

    def epic_access(self, token: str) -> bool:
        self.epic_checks.append(token)
        if self.epic_refusal is not None:
            raise self.epic_refusal
        return token in self.linked_to_epic

    def user(self, token: str) -> dict[str, Any]:
        self.tokens.append(token)
        return {"login": "alice-gh", "avatar_url": "https://avatars.example.test/alice"}

    def repos(self, token: str) -> list[dict[str, Any]]:
        self.tokens.append(token)
        return list(self.repositories.values())

    def repo(self, token: str, full_name: str) -> dict[str, Any]:
        if full_name not in self.repositories:
            raise GitHubError(404, "Not Found")
        return self.repositories[full_name]

    def create_repo(self, token: str, name: str, private: bool) -> dict[str, Any]:
        full_name = f"alice-gh/{name}"
        if full_name in self.repositories:
            raise GitHubError(422, "name already exists on this account")
        return self.add_repository(full_name, push=True, private=private)

    def head(self, token: str, full_name: str, branch: str) -> str | None:
        return self.refs.get((full_name, branch))

    def branches_under(self, token: str, full_name: str, prefix: str) -> list[str]:
        return sorted(branch for repo, branch in self.refs if repo == full_name and branch.startswith(prefix))

    def create_branch(self, token: str, full_name: str, branch: str, sha: str) -> None:
        if (full_name, branch) in self.refs:
            raise GitHubError(422, "Reference already exists")
        self.refs[(full_name, branch)] = sha
        self.made_branches.append((full_name, branch, sha))

    def tree(self, token: str, full_name: str, sha: str, recursive: bool) -> dict[str, Any]:
        self.tree_calls.append((sha, recursive))
        commit, _, folder = sha.partition(":")
        prefix = f"{folder}/" if folder else ""
        entries: dict[str, dict[str, Any]] = {}
        for path in sorted(self.commits[commit]):
            if not path.startswith(prefix):
                continue
            parts = path[len(prefix) :].split("/")
            for depth in range(1, len(parts)):
                below = "/".join(parts[:depth])
                entries[below] = {"path": below, "type": "tree", "sha": f"{commit}:{prefix}{below}"}
            entries["/".join(parts)] = {"path": "/".join(parts), "type": "blob", "sha": f"blob-{path}"}
        listing = [entry for entry in entries.values() if recursive or "/" not in entry["path"]]
        truncated = recursive and len(listing) > self.tree_limit
        return {"sha": sha, "tree": listing[: self.tree_limit] if truncated else listing, "truncated": truncated}

    def read(self, token: str, full_name: str, path: str, ref: str | None = None) -> dict[str, Any]:
        files = self.at(full_name, ref)
        prefix = f"{path}/" if path else ""
        if path in files:
            return {"text": files[path], "sha": f"blob-{path}"}
        below = {name[len(prefix) :].split("/")[0] + ("/" if "/" in name[len(prefix) :] else "") for name in files if name.startswith(prefix)}
        if not below:
            raise GitHubError(404, "Not Found")
        return {"entries": sorted(below)}

    def save(
        self, token: str, full_name: str, path: str, content: str, message: str, branch: str | None = None
    ) -> dict[str, Any]:
        self.tokens.append(token)
        # As GitHub's contents API does, a write that names no branch commits to the default branch
        branch = branch or self.repositories[full_name]["default_branch"]
        if (full_name, branch) not in self.refs:
            raise GitHubError(404, f"Branch {branch} not found")
        sha = self.commit(full_name, branch, {**self.branch_files(full_name, branch), path: content})
        return {"html_url": f"https://github.com/{full_name}/commit/{sha}", "message": message}


class FakeFal:
    """fal, as far as the generation tools reach it: what was asked of which model, and files to download."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def run(self, model: str, arguments: dict[str, Any], alive: Callable[[], bool], limit_seconds: float) -> dict[str, Any]:
        self.calls.append((model, arguments))
        if model in VIDEO_MODELS.values():
            return {"video": {"url": "https://fal.example.test/files/shot.mp4"}, "seed": 7}
        return {"images": [{"url": f"https://fal.example.test/files/image-{n}.png"} for n in range(arguments["num_images"])]}

    def download(self, url: str) -> tuple[bytes, str]:
        return url.encode(), "video/mp4" if url.endswith(".mp4") else "image/png"

    def cost(self, model: str, units: dict[str, float]) -> float | None:
        if model in VIDEO_MODELS.values():
            return round(0.473 * units["second"], 4) if "second" in units else None
        return round(0.15 * units["image"], 4)


Step = Reply | Callable[[dict[str, Any]], Reply]


class ScriptedModel:
    """Claude, answering from a script: each request takes the next reply, or the reply a step makes of the request."""

    def __init__(self) -> None:
        self.steps: list[Step] = []
        self.requests: list[dict[str, Any]] = []

    def script(self, *steps: Step) -> None:
        self.steps.extend(steps)

    def respond(self, system: list[dict[str, Any]], messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                on_block: Callable[[dict[str, Any]], None], alive: Callable[[], bool]) -> Reply:
        request = {"system": copy.deepcopy(system), "messages": copy.deepcopy(messages), "tools": [t["name"] for t in tools]}
        self.requests.append(request)
        step = self.steps.pop(0)
        reply = step(request) if callable(step) else step
        for block in reply.content:
            on_block(block)
        return reply


CALL_IDS = itertools.count(1)


def say(words: str) -> dict[str, Any]:
    return {"type": "text", "text": words}


def use(tool: str, /, **arguments: Any) -> dict[str, Any]:
    return {"type": "tool_use", "id": f"toolu_{next(CALL_IDS):04d}", "name": tool, "input": arguments}


def reply(*blocks: dict[str, Any], stop: str | None = None) -> Reply:
    calls = any(block["type"] == "tool_use" for block in blocks)
    return Reply(content=list(blocks), stop_reason=stop or ("tool_use" if calls else "end_turn"))


def config(**changes: Any) -> Config:
    values: dict[str, Any] = {
        "supabase_url": "https://project.example.test", "supabase_key": "service-key", "stripe_key": "",
        "stripe_webhook_secret": "", "site_url": SITE, "capacity": 10,
        "tiers": frozenset({"cpu", "t4"}), "pin_regions": False,
    }
    return Config(**{**values, **changes})


@pytest.fixture
def world() -> tuple[TestClient, Sessions, FakeStore, FakeLauncher]:
    store, launcher, jobs = FakeStore(), FakeLauncher(), InlineJobs()
    sessions = Sessions(config(), CATALOG, store, launcher, jobs)
    jobs.sessions = sessions
    with TestClient(create_app(sessions, sessions.config, CATALOG)) as client:
        yield client, sessions, store, launcher


SKILLS = {
    "filmcraft": "---\nname: filmcraft\ndescription: Editing films in FilmCraft.\n---\n\nCut on action. FILMCRAFT-SKILL-TEXT\n",
    "studio-basics": "# Basics\n\nName every file. GENERAL-SKILL-TEXT\n",
    "songwriting": "---\ndescription: Writing songs.\ndisciplines: [music]\n---\nSONG-SKILL-TEXT\n",
}


@pytest.fixture
def studio(tmp_path: Path) -> SimpleNamespace:
    """The Studio's whole backend: every integration configured, and the agent running each turn inline."""
    for name, body in SKILLS.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "SKILL.md").write_text(body)
    store, launcher, jobs, github, fal, model = FakeStore(), FakeLauncher(), InlineJobs(), FakeGitHub(), FakeFal(), ScriptedModel()
    settings = config(anthropic_key="sk-ant-test", fal_key="fal-test", github_client_id="gh-client",
                      github_client_secret="gh-secret", secret_key=SECRET)
    sessions = Sessions(settings, CATALOG, store, launcher, jobs, github)
    jobs.sessions = sessions
    agent = Agent(sessions, model, fal, read_skills(tmp_path))
    # The heartbeat's thread stays quiet: the loop's own beats between steps are what a test drives
    agent.heartbeat_seconds = 3600
    jobs.agent = agent
    with TestClient(create_app(sessions, settings, CATALOG)) as client:
        yield SimpleNamespace(client=client, sessions=sessions, store=store, launcher=launcher, jobs=jobs,
                              github=github, fal=fal, model=model, agent=agent)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def new_project(client: TestClient, token: str = "alice-token", **body: Any) -> dict[str, Any]:
    response = client.post("/v1/projects", headers=auth(token), json={"name": "Mara", "discipline": "media", "format": "Movie", **body})
    assert response.status_code == 200, response.text
    return response.json()["project"]


def events(client: TestClient, project_id: str, token: str = "alice-token", after: int = 0) -> dict[str, Any]:
    response = client.get(f"/v1/projects/{project_id}/events", headers=auth(token), params={"after": after})
    assert response.status_code == 200, response.text
    return response.json()


def message(client: TestClient, project_id: str, words: str, token: str = "alice-token") -> Any:
    return client.post(f"/v1/projects/{project_id}/messages", headers=auth(token), json={"text": words})


def tool_results(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The results the newest user message of a request carries, by the call they answer."""
    user = next(m for m in reversed(request["messages"]) if m["role"] == "user")
    return {block["tool_use_id"]: block for block in user["content"] if block["type"] == "tool_result"}


def test_health_is_open_and_says_what_is_configured(world):
    client = world[0]
    assert client.get("/v1/health").json() == {
        "ok": True, "agent": False, "github": False, "generation": False, "supabase": True, "billing": False,
        "tiers": ["cpu", "t4"],
    }


def test_an_unconfigured_service_answers_health_and_refuses_the_rest():
    unconfigured = config(supabase_url="", supabase_key="")
    with TestClient(create_app(None, unconfigured, CATALOG)) as client:
        assert client.get("/v1/health").json()["supabase"] is False
        assert client.get("/v1/me", headers=auth("alice-token")).status_code == 503


def test_no_credential_and_a_wrong_one_are_refused(world):
    client = world[0]
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers=auth("nobody")).status_code == 401
    assert client.get("/v1/me", headers={"Authorization": "Basic abc"}).json()["error"]


def test_a_first_visit_makes_a_profile_with_the_sign_up_credits(world):
    client = world[0]
    me = client.get("/v1/me", headers=auth("alice-token")).json()
    assert me == {"id": ALICE.id, "email": ALICE.email, "credits": CATALOG.signup_credits, "max_sessions": 1}


def test_a_session_starts_in_the_users_own_workspace_and_hands_back_a_link(world):
    client, _, _, launcher = world
    session = client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu", "region": "eu"}).json()["session"]
    assert session["status"] == "starting" and "sandbox_id" not in session and session["queue_position"] is None
    started, tier, region = launcher.started[0]
    assert started["user_id"] == ALICE.id and tier["id"] == "cpu"
    assert region is None, "a region is pinned only where the deployment turned pinning on"
    listed = client.get("/v1/sessions", headers=auth("alice-token")).json()["sessions"]
    assert [s["status"] for s in listed] == ["running"]
    link = client.post(f"/v1/sessions/{session['id']}/link", headers=auth("alice-token")).json()["url"]
    assert link.startswith("https://sb-1.")


def test_what_is_not_on_offer_is_refused(world):
    client = world[0]
    post = lambda body: client.post("/v1/sessions", headers=auth("alice-token"), json=body).status_code
    assert post({"app": "photocraft", "tier": "cpu"}) == 400, "an app that is coming next"
    assert post({"app": "godot", "tier": "cpu"}) == 400, "an app that is coming soon"
    assert post({"app": "blender", "tier": "nope"}) == 400
    assert post({"app": "blender", "tier": "cpu", "region": "mars"}) == 400
    assert post({"app": "blender", "tier": "a10"}) == 409, "a tier the deployment has not switched on"


def test_a_second_open_session_is_refused(world):
    client = world[0]
    body = {"app": "blender", "tier": "cpu"}
    assert client.post("/v1/sessions", headers=auth("alice-token"), json=body).status_code == 200
    assert client.post("/v1/sessions", headers=auth("alice-token"), json=body).status_code == 409


def test_another_users_session_does_not_exist_for_this_one(world):
    client = world[0]
    session = client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"}).json()["session"]
    assert client.get("/v1/sessions", headers=auth("bob-token")).json()["sessions"] == []
    assert client.post(f"/v1/sessions/{session['id']}/link", headers=auth("bob-token")).status_code == 404
    assert client.delete(f"/v1/sessions/{session['id']}", headers=auth("bob-token")).status_code == 404


def test_an_id_that_is_not_one_is_a_missing_session_not_a_filter(world):
    client = world[0]
    for strange in ("nope", "1,user_id.eq.x", "(select 1)"):
        assert client.post(f"/v1/sessions/{strange}/link", headers=auth("alice-token")).status_code == 404
        assert client.delete(f"/v1/api-keys/{strange}", headers=auth("alice-token")).status_code == 204


def test_stopping_ends_the_sandbox_and_the_session(world):
    client, _, _, launcher = world
    session = client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"}).json()["session"]
    client.delete(f"/v1/sessions/{session['id']}", headers=auth("alice-token"))
    assert launcher.stopped == ["sb-1"]
    ended = client.get("/v1/sessions", headers=auth("alice-token")).json()["sessions"][0]
    assert ended["status"] == "ended" and ended["end_reason"] == "stopped"
    assert client.post(f"/v1/sessions/{session['id']}/link", headers=auth("alice-token")).status_code == 409


def test_a_start_modal_refuses_fails_the_session_with_the_reason(world):
    client, _, _, launcher = world
    launcher.fail_start = True
    client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "blender", "tier": "t4"})
    failed = client.get("/v1/sessions", headers=auth("alice-token")).json()["sessions"][0]
    assert failed["status"] == "failed" and "payment method" in failed["end_reason"]


def test_sessions_past_capacity_queue_and_start_when_there_is_room(world):
    client, sessions, _, launcher = world
    object.__setattr__(sessions.config, "capacity", 1)
    first = client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"}).json()["session"]
    queued = client.post("/v1/sessions", headers=auth("bob-token"), json={"app": "blender", "tier": "cpu"}).json()["session"]
    assert queued["status"] == "queued" and queued["queue_position"] == 1 and len(launcher.started) == 1
    launcher.exits["sb-1"] = 0
    assert sessions.reconcile() == {"ended": 1, "out_of_credits": 0, "failed": 0, "started": 1}
    statuses = {s["id"]: s["status"] for u in ("alice-token", "bob-token") for s in client.get("/v1/sessions", headers=auth(u)).json()["sessions"]}
    assert statuses == {first["id"]: "ended", queued["id"]: "running"}


def test_the_reconciler_names_how_a_sandbox_ended(world):
    client, sessions, store, launcher = world
    client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"})
    client.post("/v1/sessions", headers=auth("bob-token"), json={"app": "blender", "tier": "cpu"})
    launcher.exits.update({"sb-1": 143, "sb-2": 137})
    assert sessions.reconcile() == {"ended": 1, "out_of_credits": 0, "failed": 1, "started": 0}
    reasons = sorted(s["end_reason"] for s in store.sessions.values())
    assert reasons == ["crashed (exit 137)", "stopped"]


def test_a_session_out_of_credits_is_stopped(world):
    client, sessions, store, launcher = world
    client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"})
    store.profiles[ALICE.id]["credits"] = 0
    assert sessions.reconcile()["out_of_credits"] == 1
    assert launcher.stopped == ["sb-1"]
    assert next(iter(store.sessions.values()))["end_reason"] == "out of credits"


def test_an_api_key_is_shown_once_stored_hashed_and_dies_when_revoked(world):
    client, _, store, _ = world
    made = client.post("/v1/api-keys", headers=auth("alice-token"), json={"name": "laptop"}).json()
    secret = made["secret"]
    assert secret.startswith("lathe_") and made["key"]["prefix"] == secret[:12] and "key_hash" not in made["key"]
    assert list(store.keys) == [hash_key(secret)], "only the hash is stored"
    assert client.get("/v1/me", headers=auth(secret)).json()["id"] == ALICE.id
    assert client.get("/v1/api-keys", headers=auth("bob-token")).json()["keys"] == []
    assert client.delete(f"/v1/api-keys/{made['key']['id']}", headers=auth("bob-token")).status_code == 204
    assert client.get("/v1/me", headers=auth(secret)).status_code == 200, "another user cannot revoke it"
    assert client.delete(f"/v1/api-keys/{made['key']['id']}", headers=auth("alice-token")).status_code == 204
    assert client.get("/v1/me", headers=auth(secret)).status_code == 401


def test_checkout_is_refused_until_payments_are_configured(world):
    client = world[0]
    assert client.post("/v1/billing/checkout", headers=auth("alice-token"), json={"pack": "pack-10"}).status_code == 503


def test_a_paid_checkout_is_credited_once_and_only_with_stripes_signature(world):
    client, sessions, store, _ = world
    object.__setattr__(sessions.config, "stripe_key", "sk_test")
    object.__setattr__(sessions.config, "stripe_webhook_secret", "whsec_test")
    client.get("/v1/me", headers=auth("alice-token"))
    payload = json.dumps({"type": "checkout.session.completed", "data": {"object": {
        "id": "cs_1", "payment_status": "paid", "metadata": {"user_id": ALICE.id, "credits": "1000"}}}}).encode()

    def deliver(secret: str, stamp: int) -> int:
        signed = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
        return client.post("/v1/billing/webhook", content=payload, headers={"Stripe-Signature": f"t={stamp},v1={signed}"}).status_code

    now = int(time.time())
    assert deliver("whsec_wrong", now) == 400
    assert deliver("whsec_test", now - 3600) == 400, "a delivery replayed an hour later"
    assert store.profiles[ALICE.id]["credits"] == CATALOG.signup_credits
    assert deliver("whsec_test", now) == 200 and deliver("whsec_test", now) == 200
    assert store.profiles[ALICE.id]["credits"] == CATALOG.signup_credits + 1000


def mcp(client: TestClient, method: str, params: dict[str, Any], key: str | None) -> dict[str, Any]:
    headers = {"Accept": "application/json, text/event-stream", "Host": "lathe.example.test"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def tool(client: TestClient, name: str, arguments: dict[str, Any], key: str | None) -> dict[str, Any]:
    return mcp(client, "tools/call", {"name": name, "arguments": arguments}, key)["result"]


def test_an_agent_with_a_key_starts_a_session_works_in_it_and_stops_it(world):
    client, _, _, launcher = world
    key = client.post("/v1/api-keys", headers=auth("alice-token"), json={"name": "claude"}).json()["secret"]
    names = {t["name"] for t in mcp(client, "tools/list", {}, key)["result"]["tools"]}
    assert names == {"list_apps", "start_session", "list_sessions", "get_session_link", "stop_session", "run_blender_python", "screenshot"}

    started = tool(client, "start_session", {}, key)
    assert not started.get("isError"), started
    session = started["structuredContent"]
    assert session["status"] == "running" and session["link"].startswith("https://sb-1.")
    assert launcher.started[0][0]["user_id"] == ALICE.id

    ran = tool(client, "run_blender_python", {"session_id": session["id"], "code": "print(1)"}, key)
    assert "ran in sb-1: print(1)" in ran["content"][0]["text"]
    raised = tool(client, "run_blender_python", {"session_id": session["id"], "code": "raise X"}, key)
    assert "Traceback" in raised["content"][0]["text"] and "[exit status 1]" in raised["content"][0]["text"]

    picture = tool(client, "screenshot", {"session_id": session["id"]}, key)["content"][0]
    assert picture["type"] == "image" and picture["mimeType"] == "image/jpeg"

    assert not tool(client, "stop_session", {"session_id": session["id"]}, key).get("isError")
    assert launcher.stopped == ["sb-1"]


def test_an_agent_without_a_valid_key_gets_an_error_not_a_session(world):
    client, _, _, launcher = world
    for key in (None, "lathe_not-a-real-key"):
        refused = tool(client, "start_session", {}, key)
        assert refused["isError"] and launcher.started == []


def test_an_agent_cannot_reach_another_users_session(world):
    client = world[0]
    session = client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"}).json()["session"]
    bobs_key = client.post("/v1/api-keys", headers=auth("bob-token"), json={"name": "claude"}).json()["secret"]
    for name, arguments in (("get_session_link", {}), ("run_blender_python", {"code": "print(1)"}), ("screenshot", {}), ("stop_session", {})):
        refused = tool(client, name, {"session_id": session["id"], **arguments}, bobs_key)
        assert refused["isError"] and "No such session" in refused["content"][0]["text"], name


# Lathe Studio


def test_health_says_which_integrations_are_configured(studio, world):
    assert studio.client.get("/v1/health").json() == {
        "ok": True, "agent": True, "github": True, "generation": True, "supabase": True, "billing": False,
        "tiers": ["cpu", "t4"],
    }
    bare = world[0].get("/v1/health").json()
    assert (bare["agent"], bare["github"], bare["generation"]) == (False, False, False)


def test_a_project_is_made_listed_read_changed_and_deleted(studio):
    client, store = studio.client, studio.store
    film = new_project(client)
    assert film["library_sections"] == ["Characters", "Environments", "Props"] and film["plan"] == []
    assert film["github_repo"] is None and film["pinned"] is False
    ad = new_project(client, name="  Spot   30 ", format="Commercial")
    assert ad["name"] == "Spot 30" and ad["library_sections"] == ["Products", "Shots"]
    assert [p["id"] for p in client.get("/v1/projects", headers=auth("alice-token")).json()["projects"]] == [ad["id"], film["id"]]

    pinned = client.patch(f"/v1/projects/{film['id']}", headers=auth("alice-token"), json={"pinned": True}).json()["project"]
    assert pinned["pinned"] is True and pinned["updated_at"] == film["updated_at"], "pinning keeps a project's place"
    renamed = client.patch(f"/v1/projects/{film['id']}", headers=auth("alice-token"),
                           json={"name": "Mara's Light", "library_sections": ["Characters", " characters", "Shots"]}).json()["project"]
    assert renamed["name"] == "Mara's Light" and renamed["library_sections"] == ["Characters", "Shots"]
    assert client.get("/v1/projects", headers=auth("alice-token")).json()["projects"][0]["id"] == film["id"]
    assert client.get(f"/v1/projects/{film['id']}", headers=auth("alice-token")).json()["project"]["name"] == "Mara's Light"
    assert client.patch(f"/v1/projects/{film['id']}", headers=auth("alice-token"), json={"name": "  "}).status_code == 400

    entry = client.post(f"/v1/projects/{film['id']}/library", headers=auth("alice-token"),
                        json={"section": "Characters", "name": "Mara"}).json()["asset"]
    client.post(f"/v1/projects/{film['id']}/library/{entry['id']}/media", headers=auth("alice-token"),
                files={"file": ("mara.png", b"png", "image/png")})
    engine = client.post(f"/v1/projects/{film['id']}/engines", headers=auth("alice-token"), json={"app": "filmcraft", "tier": "cpu"}).json()["engine"]
    assert engine["project_id"] == film["id"] and store.files

    assert client.delete(f"/v1/projects/{film['id']}", headers=auth("alice-token")).status_code == 204
    assert client.get(f"/v1/projects/{film['id']}", headers=auth("alice-token")).status_code == 404
    assert store.files == {}, "the library's files go with the project"
    assert studio.launcher.stopped == ["sb-1"], "and so do its engines"
    assert [p["id"] for p in client.get("/v1/projects", headers=auth("alice-token")).json()["projects"]] == [ad["id"]]


def test_a_project_is_of_a_discipline_and_format_the_catalog_offers(studio):
    client = studio.client
    post = lambda body: client.post("/v1/projects", headers=auth("alice-token"), json=body)
    assert post({"name": "x", "discipline": "cooking"}).status_code == 400
    assert post({"name": "x", "discipline": "media", "format": "Opera"}).status_code == 400
    refused = post({"name": "x"})
    assert refused.status_code == 422 and refused.json()["detail"] == "discipline: Field required"
    assert post({"name": "", "discipline": "music"}).json()["project"]["name"] == "Untitled project"


def test_another_users_project_does_not_exist_for_this_one(studio):
    client = studio.client
    film = new_project(client)
    entry = client.post(f"/v1/projects/{film['id']}/library", headers=auth("alice-token"),
                        json={"section": "Characters", "name": "Mara", "tag": "@mara"}).json()["asset"]
    base = f"/v1/projects/{film['id']}"
    bob = auth("bob-token")
    refusals = [
        client.get(base, headers=bob),
        client.patch(base, headers=bob, json={"name": "mine"}),
        client.delete(base, headers=bob),
        client.get(f"{base}/events", headers=bob),
        client.post(f"{base}/messages", headers=bob, json={"text": "do my bidding"}),
        client.post(f"{base}/stop", headers=bob),
        client.get(f"{base}/library", headers=bob),
        client.post(f"{base}/library", headers=bob, json={"section": "Props", "name": "Cup"}),
        client.post(f"{base}/library/{entry['id']}/media", headers=bob, files={"file": ("x.png", b"x", "image/png")}),
        client.patch(f"{base}/library/{entry['id']}", headers=bob, json={"name": "Not Mara"}),
        client.delete(f"{base}/library/{entry['id']}", headers=bob),
        client.get(f"{base}/engines", headers=bob),
        client.post(f"{base}/engines", headers=bob, json={"app": "filmcraft", "tier": "cpu"}),
        client.post(f"{base}/github", headers=bob, json={"repo": "alice-gh/film"}),
        client.delete(f"{base}/github", headers=bob),
    ]
    assert [r.status_code for r in refusals] == [404] * len(refusals), [r.text for r in refusals if r.status_code != 404]
    assert all(r.json()["detail"] == "No such project." for r in refusals)
    assert client.get("/v1/projects", headers=bob).json()["projects"] == []
    assert studio.launcher.started == [] and studio.jobs.turns == []

    # Alice's entry through Bob's own project is no entry either
    theirs = new_project(client, "bob-token")
    assert client.patch(f"/v1/projects/{theirs['id']}/library/{entry['id']}", headers=bob, json={"name": "x"}).status_code == 404
    assert client.delete(f"/v1/projects/{theirs['id']}/library/{entry['id']}", headers=bob).status_code == 404
    assert client.get(f"{base}/library", headers=auth("alice-token")).json()["assets"][0]["name"] == "Mara"
    for strange in ("nope", "1,user_id.eq.x"):
        assert client.get(f"/v1/projects/{strange}", headers=auth("alice-token")).status_code == 404
        assert client.delete(f"{base}/library/{strange}", headers=auth("alice-token")).status_code == 404


def test_the_library_keeps_entries_and_hands_out_their_files_as_signed_links(studio):
    client, store = studio.client, studio.store
    film = new_project(client)
    base = f"/v1/projects/{film['id']}/library"
    mara = client.post(base, headers=auth("alice-token"), json={
        "section": "Characters", "name": "Mara", "tag": "Mara", "description": "A lighthouse keeper", "metadata": {"age": 34},
    }).json()["asset"]
    assert mara["tag"] == "@mara" and mara["media"] == [] and mara["thumbnail_url"] is None
    assert client.post(base, headers=auth("alice-token"), json={"section": "Props", "name": "Other", "tag": "@mara"}).status_code == 409
    assert client.post(base, headers=auth("alice-token"), json={"section": "Props", "name": "Odd", "tag": "@mara!"}).status_code == 400
    client.post(base, headers=auth("alice-token"), json={"section": "Wardrobe", "name": "Raincoat"})

    uploaded = client.post(f"{base}/{mara['id']}/media", headers=auth("alice-token"),
                           files={"file": ("../front view.png", b"\x89PNG", "image/png")}).json()["asset"]
    (front,) = uploaded["media"]
    assert front["kind"] == "image" and front["name"] == "../front view.png"
    assert front["url"].startswith("https://storage.example.test/") and "token=" in front["url"]
    assert uploaded["thumbnail_url"] == front["url"]
    (path,) = store.files
    assert path.startswith(f"{ALICE.id}/{film['id']}/{mara['id']}/") and ".." not in path and " " not in path
    clip = client.post(f"{base}/{mara['id']}/media", headers=auth("alice-token"),
                       files={"file": ("walk.mp4", b"mp4", "video/mp4")}).json()["asset"]
    assert [m["kind"] for m in clip["media"]] == ["video", "image"] and clip["thumbnail_url"] == front["url"]
    assert client.post(f"{base}/{mara['id']}/media", headers=auth("alice-token"),
                       files={"file": ("empty.png", b"", "image/png")}).status_code == 400

    changed = client.patch(f"{base}/{mara['id']}", headers=auth("alice-token"), json={"tag": "", "section": "Leads"}).json()["asset"]
    assert changed["tag"] is None and changed["section"] == "Leads" and changed["description"] == "A lighthouse keeper"
    library = client.get(base, headers=auth("alice-token")).json()
    assert library["sections"] == ["Characters", "Environments", "Props", "Wardrobe", "Leads"]
    assert [a["name"] for a in library["assets"]] == ["Mara", "Raincoat"]

    assert client.delete(f"{base}/{mara['id']}", headers=auth("alice-token")).status_code == 204
    assert store.files == {} and [a["name"] for a in client.get(base, headers=auth("alice-token")).json()["assets"]] == ["Raincoat"]


def test_an_engine_starts_in_its_projects_folder_on_the_users_credits(studio):
    client, launcher = studio.client, studio.launcher
    film = new_project(client)
    other = new_project(client, name="Other")
    engine = client.post(f"/v1/projects/{film['id']}/engines", headers=auth("alice-token"),
                         json={"app": "filmcraft", "tier": "cpu", "region": "eu"}).json()["engine"]
    session, tier, _ = launcher.started[0]
    assert session["project_id"] == film["id"] and session["app"] == "filmcraft" and tier["id"] == "cpu"
    assert engine["project_id"] == film["id"] and engine["app"] == "filmcraft"
    assert [e["id"] for e in client.get(f"/v1/projects/{film['id']}/engines", headers=auth("alice-token")).json()["engines"]] == [engine["id"]]
    assert client.get(f"/v1/projects/{other['id']}/engines", headers=auth("alice-token")).json()["engines"] == []
    assert client.post(f"/v1/projects/{other['id']}/engines", headers=auth("alice-token"),
                       json={"app": "blender", "tier": "cpu"}).status_code == 409, "one open session per user, as before"
    assert client.post(f"/v1/projects/{other['id']}/engines", headers=auth("alice-token"),
                       json={"app": "photocraft", "tier": "cpu"}).status_code == 400, "an engine that is coming next"
    assert client.post(f"/v1/sessions/{engine['id']}/link", headers=auth("alice-token")).json()["url"].startswith("https://sb-1.")
    client.delete(f"/v1/sessions/{engine['id']}", headers=auth("alice-token"))
    assert launcher.stopped == ["sb-1"]


def test_nuke_is_for_the_teams_accounts_and_its_seats(studio):
    client, sessions, store = studio.client, studio.sessions, studio.store
    film = new_project(client)
    start = lambda token, project: client.post(f"/v1/projects/{project['id']}/engines", headers=auth(token), json={"app": "nuke", "tier": "cpu"})
    refused = start("alice-token", film)
    assert refused.status_code == 403 and "team" in refused.json()["detail"]
    assert client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "nuke", "tier": "cpu"}).status_code == 403
    assert studio.launcher.started == []

    object.__setattr__(sessions.config, "team_emails", frozenset({"alice@example.test", "bob@example.test"}))
    object.__setattr__(sessions.config, "nuke_seats", 1)
    assert start("alice-token", film).status_code == 200
    theirs = new_project(client, "bob-token")
    taken = start("bob-token", theirs)
    assert taken.status_code == 409 and "seat" in taken.json()["detail"]
    nukes = [s for s in store.sessions.values() if s["app"] == "nuke"]
    client.delete(f"/v1/sessions/{nukes[0]['id']}", headers=auth("alice-token"))
    assert start("bob-token", theirs).status_code == 200, "a freed seat is taken again"
    blender = client.post(f"/v1/projects/{film['id']}/engines", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"})
    assert blender.status_code == 200, "the seats hold Nuke alone"


def test_a_message_starts_one_turn_at_a_time_and_stop_ends_it(studio):
    client, jobs, agent = studio.client, studio.jobs, studio.agent
    film = new_project(client)
    jobs.agent = None
    first = message(client, film["id"], "Write me a film")
    assert first.status_code == 202
    turn_id = first.json()["turn_id"]
    assert jobs.turns == [(film["id"], turn_id)]
    log = events(client, film["id"])
    assert log["running"] is True
    assert [(e["kind"], e["data"]) for e in log["events"]] == [("user_message", {"text": "Write me a film"})]
    second = message(client, film["id"], "Hurry up")
    assert second.status_code == 409 and "still working" in second.json()["detail"]
    assert message(client, film["id"], "   ").status_code == 400

    assert client.post(f"/v1/projects/{film['id']}/stop", headers=auth("alice-token")).json() == {"stopped": True}
    agent.run(film["id"], turn_id)
    assert studio.model.requests == [], "a turn stopped before it began asks nothing"
    log = events(client, film["id"], after=log["events"][-1]["id"])
    assert [e["kind"] for e in log["events"]] == ["turn_end"] and log["running"] is False
    assert client.post(f"/v1/projects/{film['id']}/stop", headers=auth("alice-token")).json() == {"stopped": False}

    jobs.agent = agent
    studio.model.script(reply(say("Here we go.")))
    assert message(client, film["id"], "Go on").status_code == 202
    sent = studio.model.requests[0]["messages"]
    assert [(m["role"], m["content"]) for m in sent[:2]] == [("user", "Write me a film"), ("user", "Go on")], (
        "the model knows every message the person sent, a stopped turn's too")
    assert [m["role"] for m in sent] == ["user", "user", "system"], "the stopped turn's state is not"


def test_a_message_waits_for_the_agent_to_be_configured(world):
    client = world[0]
    film = new_project(client)
    refused = message(client, film["id"], "hello")
    assert refused.status_code == 503 and refused.json() == {"detail": "The agent is not switched on yet.",
                                                             "error": "The agent is not switched on yet."}


def test_a_dead_turn_does_not_hold_the_project(studio):
    client, store = studio.client, studio.store
    film = new_project(client)
    studio.jobs.agent = None
    message(client, film["id"], "first")
    store.tables["projects"][film["id"]]["turn_seen_at"] = (moment() - timedelta(minutes=10)).isoformat()
    assert events(client, film["id"])["running"] is False
    assert message(client, film["id"], "second").status_code == 202
    kinds = [e["kind"] for e in events(client, film["id"])["events"]]
    assert kinds == ["user_message", "error", "turn_end", "user_message"]


def test_a_clip_longer_than_its_model_makes_is_refused_before_fal_is_asked(studio):
    client, fal, model = studio.client, studio.fal, studio.model
    film = new_project(client)
    model.script(
        reply(use("generate_video", prompt="A wide coast at dusk.", duration_seconds=20, resolution="720p")),
        reply(use("generate_video", prompt="A wide coast at dusk.", duration_seconds=20, resolution="720p", model="fast")),
        reply(say("Done.")),
    )
    assert message(client, film["id"], "Make the long shot").status_code == 202
    ends = [e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "tool_end"]
    assert not ends[0]["ok"] and "at most 14 seconds" in ends[0]["summary"], "the standard model stops at 14 s"
    assert ends[1]["ok"], "the fast model makes 30 s"
    assert [called for called, _ in fal.calls] == ["bytedance/seedance-2.5/flash/reference-to-video"]


def test_the_agent_works_through_its_tools_and_only_ever_appends_to_the_conversation(studio):
    client, fal, model, store = studio.client, studio.fal, studio.model, studio.store
    film = new_project(client)
    model.script(
        reply({"type": "thinking", "thinking": "", "signature": "sig-1"}, say("I'll set up the library."),
              use("set_library_sections", sections=["Characters", "Shots"]),
              use("library_upsert", section="Characters", name="Mara", tag="@Mara", description="A lighthouse keeper",
                  metadata={"approved": False})),
        reply({"type": "thinking", "thinking": "Making her look.", "signature": "sig-2"},
              use("generate_image", prompt="Turnaround sheet of @mara", count=2, aspect_ratio="16:9", save_to={"tag": "@mara"})),
        reply(use("generate_image", prompt="@mara at the lamp", references=["@mara"], model="cheap", aspect_ratio="9:16")),
        reply(use("generate_video", prompt="Wide shot: @mara climbs the stairs.", references=["@mara"], duration_seconds=6,
                  resolution="720p", save_to={"section": "Shots", "name": "S01 SH01 T1", "tag": "@s01-sh01-t1"})),
        reply(use("update_plan", items=[{"id": "bible", "title": "Bible", "status": "done"}, {"title": "Shots", "status": "active"}])),
        reply(say("Mara is in the library, and the first shot is ready.")),
    )
    assert message(client, film["id"], "Make a film about Mara").status_code == 202

    log = events(client, film["id"])
    assert log["running"] is False
    assert [e["kind"] for e in log["events"]] == [
        "user_message", "text",
        "tool_start", "library", "tool_end", "tool_start", "library", "tool_end",
        "text", "tool_start", "library", "tool_end",
        "tool_start", "tool_end",
        "tool_start", "library", "tool_end",
        "tool_start", "plan", "tool_end",
        "text", "turn_end",
    ]
    texts = [e["data"]["text"] for e in log["events"] if e["kind"] == "text"]
    assert texts == ["I'll set up the library.", "Making her look.", "Mara is in the library, and the first shot is ready."]
    ends = [e["data"] for e in log["events"] if e["kind"] == "tool_end"]
    assert all(end["ok"] for end in ends), ends
    assert ends[2]["summary"] == "2 images saved to @mara, about $0.30" and len(ends[2]["media"]) == 2
    assert ends[3]["summary"] == "1 image, about $0.15", "an image not saved anywhere"
    assert ends[4]["summary"] == "1 video saved to @s01-sh01-t1, about $2.84"
    starts = [e["data"] for e in log["events"] if e["kind"] == "tool_start"]
    assert starts[0]["tool"] == "set_library_sections" and starts[2]["title"] == "Generating 2 images"

    # fal was asked for the right models, the references as positional names and signed links
    (sheet_model, sheet), (still_model, still), (shot_model, shot) = fal.calls
    assert sheet_model == IMAGE_MODELS["best"][0] and "image_urls" not in sheet and sheet["num_images"] == 2
    assert still_model == IMAGE_MODELS["cheap"][1] and still["image_size"] == "portrait_16_9"
    assert still["prompt"] == "@Image1 at the lamp\n\n@Image1 is Mara."
    assert shot_model == VIDEO_MODELS["standard"] and shot["duration"] == "6" and shot["resolution"] == "720p"
    assert shot["prompt"] == "Wide shot: @Image1 climbs the stairs.\n\n@Image1 is Mara."
    assert shot["image_urls"] == still["image_urls"] and shot["image_urls"][0].startswith("https://storage.example.test/")

    library = client.get(f"/v1/projects/{film['id']}/library", headers=auth("alice-token")).json()
    assert library["sections"] == ["Characters", "Shots"]
    mara, take = library["assets"]
    assert (mara["tag"], mara["description"], mara["metadata"]) == ("@mara", "A lighthouse keeper", {"approved": False})
    assert [m["kind"] for m in mara["media"]] == ["image", "image"] and mara["thumbnail_url"]
    assert (take["tag"], take["section"], [m["kind"] for m in take["media"]]) == ("@s01-sh01-t1", "Shots", ["video"])
    assert any(path.startswith(f"{ALICE.id}/{film['id']}/generations/") for path in store.files), "the unsaved image is kept beside"
    plan = client.get(f"/v1/projects/{film['id']}", headers=auth("alice-token")).json()["project"]["plan"]
    assert plan == [{"id": "bible", "title": "Bible", "status": "done"}, {"id": "2", "title": "Shots", "status": "active"}]

    # Every request carries the same system prompt and tools, and the conversation of the one before it
    requests = model.requests
    assert len(requests) == 6
    system = requests[0]["system"]
    prompt = system[0]["text"]
    assert "Discipline: Media" in prompt and "Format: Movie" in prompt and f"projects/{film['id']}" in prompt
    assert "FILMCRAFT-SKILL-TEXT" in prompt and "GENERAL-SKILL-TEXT" in prompt and "SONG-SKILL-TEXT" not in prompt
    assert all(r["system"] == system and r["tools"] == TOOL_NAMES for r in requests)
    for before, after in zip(requests, requests[1:]):
        assert after["messages"][: len(before["messages"])] == before["messages"], "the conversation is append-only"
    first = requests[0]["messages"]
    assert first[0] == {"role": "user", "content": "Make a film about Mara"}
    assert first[1]["role"] == "system" and "Library sections: Characters, Environments, Props" in first[1]["content"]
    assert requests[1]["messages"][2]["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig-1"}
    assert [m["role"] for m in requests[5]["messages"]] == ["user", "system"] + ["assistant", "user"] * 5
    stored = sorted(store.tables["agent_messages"].values(), key=lambda m: m["id"])
    assert [{"role": m["role"], "content": m["content"]} for m in stored] == requests[5]["messages"] + [
        {"role": "assistant", "content": [say("Mara is in the library, and the first shot is ready.")]}]

    # The next turn goes on from all of it, with the project's state as it is now
    model.script(reply(say("Shot two next.")))
    message(client, film["id"], "Great, next shot")
    later = model.requests[-1]["messages"]
    assert later[: len(stored)] == [{"role": m["role"], "content": m["content"]} for m in stored]
    assert later[-2] == {"role": "user", "content": "Great, next shot"}
    state = later[-1]["content"]
    assert "- [done] Bible (id bible)" in state and "- @mara: Mara (Characters; 2 image)" in state
    assert "- @s01-sh01-t1: S01 SH01 T1 (Shots; 1 video)" in state and "Library sections: Characters, Shots" in state


def test_ask_user_ends_the_turn_and_the_reply_answers_it(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    question = use("ask_user", question="Do you have a script, or shall we write one?", options=["I have one", "Let's write one"])
    listing = use("library_list")
    model.script(reply(say("Let's begin."), question, listing))
    message(client, film["id"], "Hi")
    log = events(client, film["id"])
    assert [e["kind"] for e in log["events"]] == ["user_message", "text", "ask", "tool_start", "tool_end", "turn_end"]
    assert log["events"][2]["data"] == {"question": "Do you have a script, or shall we write one?", "options": ["I have one", "Let's write one"]}
    assert log["running"] is False and len(model.requests) == 1

    model.script(reply(say("Then let's write it together.")))
    message(client, film["id"], "Let's write one")
    request = model.requests[-1]["messages"]
    assert request[:3] == model.requests[0]["messages"] + [{"role": "assistant", "content": [say("Let's begin."), question, listing]}]
    answer = request[3]
    assert answer["role"] == "user" and [b["tool_use_id"] for b in answer["content"]] == [listing["id"], question["id"]]
    assert answer["content"][1] == {"type": "tool_result", "tool_use_id": question["id"], "content": "Let's write one"}
    assert request[4]["role"] == "system" and len(request) == 5


def test_a_turn_left_unfinished_is_completed_by_the_next(studio):
    client, model, store = studio.client, studio.model, studio.store
    film = new_project(client)
    # What a turn stopped between the model's calls and their tools leaves, and one stopped before any answer
    pending = use("library_list")
    for role, content in (("user", "First"), ("system", "state"), ("assistant", [say("Looking."), pending]),
                          ("user", "Second"), ("system", "stale state")):
        store.insert("agent_messages", {"project_id": film["id"], "role": role, "content": content})
    model.script(reply(say("Back to it.")))
    message(client, film["id"], "Third")
    sent = model.requests[0]["messages"]
    assert [m["role"] for m in sent] == ["user", "system", "assistant", "user", "user", "system"]
    assert sent[3]["content"] == "Second", "the stale state with nothing after it is gone, the rest kept"
    results = sent[4]["content"]
    assert results[0]["tool_use_id"] == pending["id"] and results[0]["is_error"] is True and "Not run" in results[0]["content"]
    assert results[1] == {"type": "text", "text": "Third"}
    assert "stale state" not in [m["content"] for m in store.tables["agent_messages"].values()]


def test_a_tool_input_that_fails_its_schema_is_answered_not_run(studio):
    client, model, fal = studio.client, studio.model, studio.fal
    film = new_project(client)
    bad = use("generate_image", prompt="A lighthouse", count="two")
    cut = use("library_upsert", section="Characters")
    model.script(reply(bad), reply(cut, stop="max_tokens"), reply(use("nonsense")), reply(say("Sorry.")))
    message(client, film["id"], "Make a picture")
    assert fal.calls == []
    first, second, third = (tool_results(r) for r in model.requests[1:])
    assert first[bad["id"]]["is_error"] and "INVALID_INPUT" in first[bad["id"]]["content"] and "count" in first[bad["id"]]["content"]
    assert second[cut["id"]]["is_error"] and "cut off" in second[cut["id"]]["content"]
    assert third and all(result["is_error"] for result in third.values())
    assert [e["kind"] for e in events(client, film["id"])["events"]] == ["user_message", "text", "turn_end"]


def test_a_refused_or_failing_model_ends_the_turn_with_an_error(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    model.script(Reply(content=[], stop_reason="refusal"))
    message(client, film["id"], "Something")
    assert [e["kind"] for e in events(client, film["id"])["events"]][-2:] == ["error", "turn_end"]
    assert [m["role"] for m in studio.store.tables["agent_messages"].values()] == ["user", "system"], "nothing refused is kept"


def test_the_engine_tools_act_in_the_projects_own_running_engine(studio):
    client, model, launcher, store = studio.client, studio.model, studio.launcher, studio.store
    store.lathe_ensure_profile(ALICE.id, ALICE.email, 60)["max_sessions"] = 3
    film = new_project(client)
    other = new_project(client, name="Other")
    elsewhere = client.post(f"/v1/projects/{other['id']}/engines", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"}).json()["engine"]
    mara = client.post(f"/v1/projects/{film['id']}/library", headers=auth("alice-token"),
                       json={"section": "Characters", "name": "Mara", "tag": "@mara"}).json()["asset"]
    client.post(f"/v1/projects/{film['id']}/library/{mara['id']}/media", headers=auth("alice-token"),
                files={"file": ("sheet.png", b"png", "image/png")})
    started = use("engine_start", app="filmcraft", tier="cpu")

    def drive(request: dict[str, Any]) -> Reply:
        engine = json.loads(tool_results(request)[started["id"]]["content"])
        assert engine["status"] == "running" and engine["project_id"] == film["id"]
        eid = engine["id"]
        return reply(
            use("filmcraft", engine_id=eid, method="engine.execute", params={"command": "file.save", "params": {}}),
            use("engine_screenshot", engine_id=eid),
            use("engine_import", engine_id=eid, tags=["@mara"]),
            use("engine_exec", engine_id=eid, command="ls library"),
            use("engine_list"),
            use("engine_stop", engine_id=elsewhere["id"]),
            use("engine_stop", engine_id=eid),
        )

    model.script(reply(started), drive, reply(say("Saved and stopped.")))
    message(client, film["id"], "Open FilmCraft")

    session, _, _ = launcher.started[1]
    assert session["app"] == "filmcraft" and session["project_id"] == film["id"]
    assert launcher.calls == [("sb-2", "engine.execute", {"command": "file.save", "params": {}})]
    (sandbox, script), (_, listing) = launcher.commands
    assert sandbox == "sb-2" and listing == "ls library"
    folder = f"/home/ubuntu/workspace/projects/{film['id']}/library/mara/"
    assert folder in script and "https://storage.example.test/" in script and script.startswith("set -e")
    results = list(tool_results(model.requests[2]).values())
    assert [r.get("is_error", False) for r in results] == [False, False, False, False, False, True, False]
    picture = results[1]["content"][0]
    assert picture["type"] == "image" and base64.b64decode(picture["source"]["data"]) == launcher.screenshot("sb-2")
    assert json.loads(results[2]["content"])["files"] == [f"{folder}01-sheet.png"]
    assert "No such engine in this project" in results[5]["content"]
    assert launcher.stopped == ["sb-2"], "the other project's engine was left alone"
    engine_events = [e["data"]["engine"]["status"] for e in events(client, film["id"])["events"] if e["kind"] == "engine"]
    assert engine_events == ["starting", "running", "ended"]


def test_the_agent_saves_only_to_a_branch_of_its_own_made_from_the_default_head(studio):
    client, model, github = studio.client, studio.model, studio.github
    film = new_project(client)
    unlinked = use("github_save", path="script.fountain", content="FADE IN:", message="Script")
    model.script(reply(unlinked), reply(say("Link a repository first.")))
    message(client, film["id"], "Save the script")
    assert "connect" in tool_results(model.requests[1])[unlinked["id"]]["content"].lower()

    connect_alice(studio)
    client.post(f"/v1/projects/{film['id']}/github", headers=auth("alice-token"), json={"repo": "alice-gh/film"})
    repo, branch = "alice-gh/film", f"lathe/mara-{film['id'][:8]}"
    main_head, main_files = github.refs[(repo, "main")], dict(github.branch_files(repo, "main"))
    # A teammate's project of the same name, linked to the same repository, made its own branch first
    theirs = github.commit(repo, "lathe/mara-0000beef", {**main_files, "notes.md": "theirs"})

    saved = use("github_save", path="/script.fountain", content="FADE IN:", message="Lock the script")
    escape = use("github_read", path="../secrets")
    on_default = use("github_read", path="script.fountain")
    on_own = use("github_read", path="script.fountain", ref="agent")
    model.script(reply(saved, escape, on_default, on_own), reply(say("Saved.")))
    message(client, film["id"], "Save the script")
    results = tool_results(model.requests[-1])
    first = json.loads(results[saved["id"]]["content"])
    assert (first["branch"], first["branch_made_now"], first["default_branch"]) == (branch, True, "main")
    assert first["compare"] == f"https://github.com/{repo}/compare/main...{branch}?expand=1"
    assert github.made_branches == [(repo, branch, main_head)], "made once, from the default branch's head"
    assert results[escape["id"]]["is_error"]
    assert results[on_default["id"]]["is_error"], "what the agent saved is not on the default branch"
    assert results[on_own["id"]]["content"] == "FADE IN:"

    # Renamed since, the project still saves to the branch it made
    client.patch(f"/v1/projects/{film['id']}", headers=auth("alice-token"), json={"name": "Mara's Light"})
    again = use("github_save", path="shotlist.md", content="| 1 | wide |", message="Shot list")
    model.script(reply(again), reply(say("Saved again.")))
    message(client, film["id"], "Save the shot list")
    second = json.loads(tool_results(model.requests[-1])[again["id"]]["content"])
    assert (second["branch"], second["branch_made_now"]) == (branch, False)
    assert len(github.made_branches) == 1
    assert github.branch_files(repo, branch) == {**main_files, "script.fountain": "FADE IN:", "shotlist.md": "| 1 | wide |"}
    assert github.refs[(repo, "main")] == main_head and github.branch_files(repo, "main") == main_files, "the default branch never changed"
    assert github.refs[(repo, "lathe/mara-0000beef")] == theirs, "nor did the teammate's branch"
    assert github.tokens[-1] == "gho_alice_token"
    log = events(client, film["id"])["events"]
    ends = [e["data"]["summary"] for e in log if e["kind"] == "tool_end"]
    assert f"Committed script.fountain to {branch}, a new branch" in ends and f"Committed shotlist.md to {branch}" in ends


def test_a_repository_the_account_cannot_push_to_is_refused_and_left_as_it_is(studio):
    client, model, github = studio.client, studio.model, studio.github
    film = new_project(client)
    connect_alice(studio)
    client.post(f"/v1/projects/{film['id']}/github", headers=auth("alice-token"), json={"repo": "alice-gh/film"})
    # The account's access was lowered to read after the project was linked
    github.repositories["alice-gh/film"]["permissions"]["push"] = False
    before = dict(github.refs)
    saved = use("github_save", path="script.fountain", content="FADE IN:", message="Script")
    read = use("github_read", path="README.md")
    model.script(reply(saved, read), reply(say("I cannot save there.")))
    message(client, film["id"], "Save the script")
    results = tool_results(model.requests[-1])
    assert results[saved["id"]]["is_error"] and "cannot push to alice-gh/film" in results[saved["id"]]["content"]
    assert "saved nothing" in results[saved["id"]]["content"]
    assert github.refs == before and github.made_branches == []
    assert results[read["id"]]["content"] == "# alice-gh/film\n", "reading still works"


def test_the_github_client_names_the_branch_on_every_write():
    """The real client over a recorded GitHub: a save reads and commits on the branch it is given, never the default."""
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if request.method == "GET" and path == "/repos/o/r/contents/notes.md":
            return httpx.Response(200, json={"encoding": "base64", "content": base64.b64encode(b"old").decode(), "sha": "blob1"})
        if request.method == "PUT" and path == "/repos/o/r/contents/notes.md":
            return httpx.Response(201, json={"commit": {"html_url": "https://github.com/o/r/commit/c2"}})
        if path == "/repos/o/r/git/ref/heads/main":
            return httpx.Response(200, json={"object": {"sha": "c1"}})
        if path == "/repos/o/r/git/matching-refs/heads/lathe":
            return httpx.Response(200, json=[{"ref": "refs/heads/lathe-old"}, {"ref": "refs/heads/lathe/mara-0123abcd"}])
        if request.method == "POST" and path == "/repos/o/r/git/refs":
            return httpx.Response(201, json={"ref": "refs/heads/lathe/mara-0123abcd"})
        if path == "/repos/o/r/git/trees/c1":
            return httpx.Response(200, json={"tree": [{"path": "Game.uproject", "type": "blob", "sha": "b"}], "truncated": False})
        return httpx.Response(404, json={"message": "Not Found"})

    github = GitHub()
    github.http = httpx.Client(headers=github.http.headers, transport=httpx.MockTransport(answer))
    branch = "lathe/mara-0123abcd"
    assert github.save("gho_t", "o/r", "notes.md", "new", "Notes", branch) == {"html_url": "https://github.com/o/r/commit/c2"}
    read, write = seen
    assert read.url.params["ref"] == branch
    assert json.loads(write.content) == {
        "message": "Notes", "content": base64.b64encode(b"new").decode(), "branch": branch, "sha": "blob1"}
    assert github.head("gho_t", "o/r", "main") == "c1" and github.head("gho_t", "o/r", "gone") is None
    assert github.branches_under("gho_t", "o/r", "lathe/") == [branch]
    github.create_branch("gho_t", "o/r", branch, "c1")
    assert json.loads(seen[-1].content) == {"ref": f"refs/heads/{branch}", "sha": "c1"}
    assert github.files("gho_t", "o/r", "c1") == ([{"path": "Game.uproject", "type": "blob", "sha": "b"}], True)
    assert seen[-1].url.params["recursive"] == "1"


CAPYVERSE = "capy-studio/capyverse-odyssey"
LFS_POINTER = "version https://git-lfs.github.com/spec/v1\noid sha256:0\nsize 1\n"
CAPYVERSE_FILES = {
    ".gitattributes": "*.uasset filter=lfs diff=lfs merge=lfs -text\n*.umap filter=lfs diff=lfs merge=lfs -text\n"
                      "# art sources\n*.psd filter=lfs diff=lfs merge=lfs -text\n*.ini text eol=lf\n",
    "README.md": "# Capyverse Odyssey\n",
    # The editor writes some with a byte order mark
    "CapyverseOdyssey.uproject": "\ufeff" + json.dumps({
        "FileVersion": 3, "EngineAssociation": "5.8", "Category": "",
        "Modules": [{"Name": "CapyverseOdyssey", "Type": "Runtime", "LoadingPhase": "Default"}],
        "Plugins": [{"Name": "ModelingToolsEditorMode", "Enabled": True, "TargetAllowList": ["Editor"]},
                    {"Name": "CapyAbilities", "Enabled": True}, {"Name": "Bridge", "Enabled": False}],
    }, indent="\t"),
    "Config/DefaultEngine.ini": "[/Script/EngineSettings.GameMapsSettings]\n",
    "Source/CapyverseOdyssey/CapyverseOdyssey.cpp": "// The game's module\n",
    **{f"Content/{path}": LFS_POINTER for path in (
        "Maps/L_Burrow.umap", "Maps/L_Burrow_BuiltData.uasset", "Maps/L_Swamp.umap",
        "__ExternalActors__/Maps/L_Swamp/0/AB/3XK9QZ.uasset", "__ExternalActors__/Maps/L_Swamp/1/C4/9Y2M1P.uasset",
        "Blueprints/BP_Capy.uasset",
        "Characters/Capy/SK_Capy.uasset", "Characters/Capy/SKEL_Capy.uasset",
        "Characters/Capy/Animations/A_Capy_Idle.uasset", "Characters/Capy/Animations/A_Capy_Run.uasset",
        "Characters/Capy/Animations/AM_Capy_Bite.uasset", "Characters/Capy/Animations/BS_Capy_Locomotion.uasset",
        "Characters/Capy/Animations/ABP_Capy.uasset", "Characters/Capy/Animations/Capy_Dodge.uasset",
        "Environment/Swamp/SM_Lily.uasset", "Environment/Swamp/SM_Log.uasset",
        "Environment/Swamp/T_Lily_D.uasset", "Environment/Swamp/T_Lily_N.uasset",
        "Environment/Swamp/M_Swamp.uasset", "Environment/Swamp/MI_Lily_Wet.uasset",
        "UI/WBP_MainMenu.uasset", "UI/WBP_HUD.uasset",
        "Audio/S_Splash.uasset", "Audio/A_Wind.uasset", "Audio/SC_Swamp.uasset",
        "VFX/NS_Splash.uasset",
        "Data/DT_Loot.uasset",
        "Developers/alice/Scratch.uasset",
    )},
    "Plugins/Gameplay/CapyAbilities/CapyAbilities.uplugin": "{\"FriendlyName\": \"Capy Abilities\"}",
    "Plugins/Gameplay/CapyAbilities/Content/Abilities/BP_Dash.uasset": LFS_POINTER,
    "Plugins/Gameplay/CapyAbilities/Content/Animations/AS_Dash.uasset": LFS_POINTER,
    "Plugins/Gameplay/CapyAbilities/Source/CapyAbilities/CapyAbilities.cpp": "// The plugin's module\n",
    "Samples/Demo/Demo.uproject": "{\"EngineAssociation\": \"5.3\"}",
    "Samples/Demo/Content/SM_Cube.uasset": LFS_POINTER,
}
CAPYVERSE_COUNTS = {
    "maps": 2, "animations": 8, "textures": 2, "meshes": 3, "materials": 2, "blueprints": 2, "sounds": 3,
    "effects": 1, "ui": 2, "data": 1, "other": 2,
}


def unreal_project(studio: SimpleNamespace) -> dict[str, Any]:
    """A Games project linked to the team's Unreal repository, which the account can push to."""
    studio.github.add_repository(CAPYVERSE, push=True, files=CAPYVERSE_FILES)
    connect_alice(studio)
    game = new_project(studio.client, name="Capyverse Odyssey", discipline="games", format="Game")
    linked = studio.client.post(f"/v1/projects/{game['id']}/github", headers=auth("alice-token"), json={"repo": CAPYVERSE})
    assert linked.status_code == 200, linked.text
    return game


def test_unreal_assets_are_read_from_the_repository_by_their_names(studio):
    client, model, github = studio.client, studio.model, studio.github
    game = unreal_project(studio)
    before = dict(github.refs)
    everything = use("unreal_assets")
    animations = use("unreal_assets", kind="animations")
    environment = use("unreal_assets", path="Content/Environment")
    model.script(reply(everything, animations, environment), reply(say("There are 28 assets.")))
    message(client, game["id"], "List me all the assets")
    results = tool_results(model.requests[-1])
    assert not any(result.get("is_error") for result in results.values()), results

    whole = json.loads(results[everything["id"]]["content"])
    assert whole["counts"] == CAPYVERSE_COUNTS
    project = whole["project"]
    assert (project["file"], project["engine_association"], project["engine"]) == (
        "CapyverseOdyssey.uproject", "5.8", "Unreal Engine 5.8")
    assert project["plugins_enabled"] == ["ModelingToolsEditorMode", "CapyAbilities"] and project["plugins_disabled"] == ["Bridge"]
    assert project["project_plugins"] == ["CapyAbilities"] and project["cpp_modules"] == ["CapyverseOdyssey"]
    assert whole["other_projects"] == ["Samples/Demo/Demo.uproject"]
    assert whole["content_roots"] == ["Content", "Plugins/Gameplay/CapyAbilities/Content"]
    assert whole["git_lfs"] == ["*.psd", "*.uasset", "*.umap"]
    listed = [path for kind in whole["assets"].values() for path in kind["paths"]]
    assert not any(path.startswith("Samples/") or "__ExternalActors__" in path for path in listed), "another project's and a map's data"
    assert whole["assets"]["maps"]["paths"] == ["Content/Maps/L_Burrow.umap", "Content/Maps/L_Swamp.umap"]
    assert "Content/Maps/L_Burrow_BuiltData.uasset" in whole["assets"]["other"]["paths"], "a .uasset is never a map"
    assert whole["assets"]["sounds"]["types"] == {"Sound Wave": 2, "Sound Cue": 1}, "A_ in Audio/ is a sound, not an animation"
    assert whole["assets"]["meshes"]["types"] == {"Static Mesh": 2, "Skeletal Mesh": 1}
    notes = " ".join(whole["notes"])
    assert "Asset Registry" in notes and "dev.epicgames.com" in notes and "Git LFS" in notes and "2 files are World Partition" in notes

    one = json.loads(results[animations["id"]]["content"])
    assert one["counts"] == {"animations": 8} and list(one["assets"]) == ["animations"]
    assert "Plugins/Gameplay/CapyAbilities/Content/Animations/AS_Dash.uasset" in one["assets"]["animations"]["paths"]
    assert one["assets"]["animations"]["types"]["named by its folder"] == 1, "Capy_Dodge, in Animations/"
    assert one["assets"]["animations"]["types"]["Animation Sequence"] == 3

    swamp = json.loads(results[environment["id"]]["content"])
    assert {kind: count for kind, count in swamp["counts"].items() if count} == {"textures": 2, "meshes": 2, "materials": 2}

    log = events(client, game["id"])["events"]
    titles = [e["data"]["title"] for e in log if e["kind"] == "tool_start"]
    assert titles == ["Listing the Unreal project's assets", "Listing the Unreal project's animations",
                      "Listing the Unreal project's assets in Content/Environment"]
    ends = [e["data"]["summary"] for e in log if e["kind"] == "tool_end"]
    assert ends[0].startswith("28 assets: 2 maps, 8 animations") and ends[1] == "8 animations"
    assert github.refs == before and github.made_branches == [], "reading the team's repository changed nothing"


def test_a_tree_github_truncates_is_walked_a_subtree_at_a_time(studio):
    client, model, github = studio.client, studio.model, studio.github
    game = unreal_project(studio)
    listings = []
    for limit in (100_000, 12):
        github.tree_limit = limit
        calls = len(github.tree_calls)
        listing = use("unreal_assets")
        model.script(reply(listing), reply(say("Listed.")))
        message(client, game["id"], "All the assets")
        listings.append((json.loads(tool_results(model.requests[-1])[listing["id"]]["content"]), github.tree_calls[calls:]))
    (whole, untruncated), (walked, truncated) = listings
    assert untruncated == [(github.refs[(CAPYVERSE, "main")], True)], "one recursive listing where GitHub gives it all"
    assert any(not recursive for _, recursive in truncated) and len(truncated) > len(untruncated)
    assert walked == whole, "the walk finds every asset the whole listing does"


def test_unreal_assets_cuts_long_lists_and_says_how_many_more(studio, monkeypatch):
    client, model = studio.client, studio.model
    game = unreal_project(studio)
    monkeypatch.setattr("agent.ASSET_PATHS_EACH", 2)
    listing = use("unreal_assets")
    model.script(reply(listing), reply(say("Listed.")))
    message(client, game["id"], "All the assets")
    found = json.loads(tool_results(model.requests[-1])[listing["id"]]["content"])
    animations = found["assets"]["animations"]
    assert len(animations["paths"]) == 2 and animations["count"] == 8 and animations["more"] == 6
    assert found["counts"] == CAPYVERSE_COUNTS, "the counts are of everything"
    assert any("left out" in note for note in found["notes"])


def test_unreal_assets_says_when_the_repository_is_not_an_unreal_project(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    connect_alice(studio)
    client.post(f"/v1/projects/{film['id']}/github", headers=auth("alice-token"), json={"repo": "alice-gh/film"})
    listing = use("unreal_assets")
    model.script(reply(listing), reply(say("No Unreal project there.")))
    message(client, film["id"], "List the maps")
    result = tool_results(model.requests[-1])[listing["id"]]
    assert result["is_error"] and "no .uproject" in result["content"]


def test_the_unreal_skill_is_read_for_the_disciplines_that_use_unreal():
    skills = read_skills(skills_directory())
    chosen = {discipline: [skill.name for skill in skills_for(skills, CATALOG, discipline)]
              for discipline in ("games", "architecture", "experiences", "media")}
    assert all("unreal" in chosen[discipline] for discipline in ("games", "architecture", "experiences"))
    assert "unreal" not in chosen["media"] and "filmcraft" in chosen["media"] and "filmcraft" not in chosen["games"]
    text = next(skill for skill in skills if skill.name == "unreal").body
    assert "unreal_assets" in text and "github_save" in text


def connect_alice(studio: SimpleNamespace, return_to: str = f"{SITE}/app/", code: str = "good-code") -> Any:
    state = parse_qs(urlsplit(studio.client.post("/v1/github/connect", headers=auth("alice-token"), json={"return_to": return_to}).json()["url"]).query)["state"][0]
    return studio.client.get("/v1/github/callback", params={"code": code, "state": state}, follow_redirects=False)


def test_github_connects_through_a_signed_state_and_links_projects(studio):
    client, store, github = studio.client, studio.store, studio.github
    assert client.get("/v1/github", headers=auth("alice-token")).json() == {"configured": True, "connected": False, "epic_linked": None}
    assert client.get("/v1/github/repos", headers=auth("alice-token")).status_code == 409
    url = client.post("/v1/github/connect", headers=auth("alice-token"), json={"return_to": f"{SITE}/app/?p=1#top"}).json()["url"]
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://github.com/login/oauth/authorize"
    assert query["client_id"] == ["gh-client"] and query["scope"] == ["repo read:packages"]
    assert query["redirect_uri"] == ["http://testserver/v1/github/callback"]
    assert read_state(SECRET, query["state"][0])["u"] == ALICE.id

    back = client.get("/v1/github/callback", params={"code": "good-code", "state": query["state"][0]}, follow_redirects=False)
    assert back.status_code == 303 and back.headers["location"] == f"{SITE}/app/?p=1&github=connected#top"
    assert github.redirects == ["http://testserver/v1/github/callback"]
    (row,) = store.tables["github_connections"].values()
    assert "gho_alice_token" not in json.dumps(row) and unseal(SECRET, row["token_encrypted"]) == "gho_alice_token"
    assert row["scope"] == "read:packages,repo", "the scopes GitHub granted, kept beside the token"
    assert client.get("/v1/github", headers=auth("alice-token")).json() == {
        "configured": True, "connected": True, "login": "alice-gh", "avatar_url": "https://avatars.example.test/alice",
        "epic_linked": False}
    assert client.get("/v1/github", headers=auth("bob-token")).json()["connected"] is False
    repos = client.get("/v1/github/repos", headers=auth("alice-token")).json()["repos"]
    assert repos[0] == {"full_name": "alice-gh/film", "private": True, "html_url": "https://github.com/alice-gh/film",
                        "updated_at": "2026-11-20T00:00:00Z"}

    film = new_project(client)
    link = lambda body: client.post(f"/v1/projects/{film['id']}/github", headers=auth("alice-token"), json=body)
    assert link({"repo": "alice-gh/film"}).json()["project"]["github_repo"] == "alice-gh/film"
    studio.github.add_repository("someone/sealed", push=False, pull=False)
    assert link({"repo": "someone/sealed"}).status_code == 403, "a repository the account cannot read"
    read_only = link({"repo": "someone/theirs"})
    assert read_only.json()["project"]["github_repo"] == "someone/theirs", "reading is enough to link and ask about it"
    assert link({"repo": "someone/missing"}).status_code == 404
    assert link({"repo": "not a repo"}).status_code == 400
    assert link({}).status_code == 400
    assert link({"create": {"name": "mara-film"}}).json()["project"]["github_repo"] == "alice-gh/mara-film"
    assert link({"create": {"name": "mara-film"}}).status_code == 409
    assert client.post(f"/v1/projects/{film['id']}/github", headers=auth("bob-token"), json={"repo": "alice-gh/film"}).status_code == 404
    assert client.delete(f"/v1/projects/{film['id']}/github", headers=auth("alice-token")).json()["project"]["github_repo"] is None
    assert client.delete("/v1/github", headers=auth("alice-token")).json() == {"configured": True, "connected": False, "epic_linked": None}
    assert store.tables["github_connections"] == {}


def test_a_github_callback_whose_state_was_not_signed_here_is_refused(studio):
    client, store, github = studio.client, studio.store, studio.github
    page = f"{SITE}/app/"
    genuine = sign_state(SECRET, ALICE.id, page)
    body, _, mac = genuine.partition(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    swapped = base64.urlsafe_b64encode(json.dumps({**payload, "u": BOB.id}).encode()).rstrip(b"=").decode()
    forgeries = {
        "another secret": sign_state("not-our-secret", ALICE.id, page),
        "a payload changed under its signature": f"{swapped}.{mac}",
        "an expired state": sign_state(SECRET, ALICE.id, page, now=time.time() - 3600),
        "no signature": body,
        "nothing": "",
        "garbage": "x.y",
    }
    for name, state in forgeries.items():
        refused = client.get("/v1/github/callback", params={"code": "good-code", "state": state}, follow_redirects=False)
        assert refused.status_code == 400 and "location" not in refused.headers, name
    assert github.redirects == [], "no code was exchanged"
    assert store.tables["github_connections"] == {}


def test_github_never_sends_anyone_off_the_site(studio):
    client, store = studio.client, studio.store
    for elsewhere in ("https://evil.example/", "https://site.example.test.evil.example/app/", "https://site.example.test@evil.example/",
                      "//evil.example/", "javascript:alert(1)", f"{SITE}\\@evil.example", "http://site.example.test/app/"):
        refused = client.post("/v1/github/connect", headers=auth("alice-token"), json={"return_to": elsewhere})
        assert refused.status_code == 400, elsewhere
    # A state this deployment signed can still not name a page off the site
    signed_elsewhere = sign_state(SECRET, ALICE.id, "https://evil.example/")
    refused = client.get("/v1/github/callback", params={"code": "good-code", "state": signed_elsewhere}, follow_redirects=False)
    assert refused.status_code == 400 and "location" not in refused.headers
    declined = client.get("/v1/github/callback", params={"error": "access_denied", "state": sign_state(SECRET, ALICE.id, SITE)},
                          follow_redirects=False)
    assert declined.status_code == 303 and declined.headers["location"] == f"{SITE}?github=failed"
    bad_code = client.get("/v1/github/callback", params={"code": "stolen", "state": sign_state(SECRET, ALICE.id, f"{SITE}/app/")},
                          follow_redirects=False)
    assert bad_code.headers["location"] == f"{SITE}/app/?github=failed" and store.tables["github_connections"] == {}


def test_github_waits_for_its_oauth_app(world):
    client = world[0]
    assert client.get("/v1/github", headers=auth("alice-token")).json() == {"configured": False, "connected": False, "epic_linked": None}
    assert client.post("/v1/github/connect", headers=auth("alice-token"), json={"return_to": f"{SITE}/app/"}).status_code == 503
    refused = client.get("/v1/github/callback", params={"code": "c", "state": sign_state("", ALICE.id, SITE)}, follow_redirects=False)
    assert refused.status_code == 400


def test_unreal_starts_only_for_a_github_account_linked_to_epic(studio):
    client, github, launcher, store = studio.client, studio.github, studio.launcher, studio.store
    game = new_project(client, discipline="games", format="World")
    start = lambda token="alice-token", project=game: client.post(
        f"/v1/projects/{project['id']}/engines", headers=auth(token), json={"app": "unreal", "tier": "t4"})
    linked = lambda: client.get("/v1/github", headers=auth("alice-token")).json()["epic_linked"]

    assert linked() is None, "unknown without GitHub"
    no_gpu = client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "unreal", "tier": "cpu"})
    assert no_gpu.status_code == 400 and "needs a GPU" in no_gpu.json()["detail"], "the editor renders only on a GPU"
    refused = start()
    assert refused.status_code == 409 and "Connect GitHub first" in refused.json()["detail"]

    connect_alice(studio, code="repo-only-code")
    assert linked() is None, "unknown for a grant without read:packages"
    refused = start()
    assert refused.status_code == 409 and "Connect GitHub again" in refused.json()["detail"]
    assert github.epic_checks == [], "GitHub is not asked what the grant cannot show"

    connect_alice(studio)
    assert linked() is False
    refused = start()
    detail = refused.json()["detail"]
    assert refused.status_code == 403
    assert "epicgames.com" in detail and "Apps and Accounts" in detail and "EpicGames organization" in detail
    assert detail.index("Apps and Accounts") < detail.index("EpicGames organization") < detail.index("Reconnect GitHub")

    github.epic_refusal = GitHubError(502, "Server Error")
    assert linked() is None, "unknown while GitHub fails"
    refused = start()
    assert refused.status_code == 409 and "Server Error" in refused.json()["detail"]
    github.epic_refusal = None
    assert launcher.started == [], "nothing started while the link was not shown"

    assert launcher.credentials == {}, "connecting GitHub alone keeps no credential for a pull"
    github.linked_to_epic.add("gho_alice_token")
    assert linked() is True
    engine = start().json()["engine"]
    assert engine["app"] == "unreal" and store.sessions[engine["id"]]["status"] == "running"
    assert launcher.own_copies == [OwnCopy("5.8")]
    assert launcher.credentials == {ALICE.id: {"REGISTRY_USERNAME": "alice-gh", "REGISTRY_PASSWORD": "gho_alice_token"}}, (
        "pulled with her own login and token, kept for her before the start"
    )
    assert "gho_alice_token" not in json.dumps(store.sessions) + json.dumps(engine), "the token is kept nowhere with the session"

    connect_alice(studio, code="next-code")
    assert launcher.credentials[ALICE.id]["REGISTRY_PASSWORD"] == "gho_alice_next", "connecting again refreshes it"
    theirs = new_project(client, "bob-token", discipline="games", format="World")
    assert start("bob-token", theirs).status_code == 409, "another user's link is not Bob's"
    client.delete(f"/v1/sessions/{engine['id']}", headers=auth("alice-token"))
    client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "blender", "tier": "t4"})
    assert launcher.own_copies[-1] is None, "an app on Lathe's own license gets no credential"
    client.delete("/v1/github", headers=auth("alice-token"))
    assert launcher.credentials == {}, "disconnecting GitHub deletes it"


def test_a_queued_unreal_start_uses_the_github_connection_it_has_when_it_starts(studio):
    client, sessions, store, github = studio.client, studio.sessions, studio.store, studio.github
    connect_alice(studio)
    github.linked_to_epic.add("gho_alice_token")
    object.__setattr__(sessions.config, "capacity", 0)
    game = new_project(client, discipline="games", format="World")
    queued = client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "unreal", "tier": "t4"})
    assert queued.json()["engine"]["status"] == "queued"
    client.delete("/v1/github", headers=auth("alice-token"))
    object.__setattr__(sessions.config, "capacity", 10)
    sessions.reconcile()
    (session,) = store.sessions.values()
    assert session["status"] == "failed" and "Connect GitHub again" in session["end_reason"]
    assert studio.launcher.started == [] and studio.launcher.credentials == {}


def test_a_sealed_token_opens_only_under_its_secret():
    sealed = seal(SECRET, "gho_token")
    assert unseal(SECRET, sealed) == "gho_token" and unseal("another", sealed) is None


# The agent's parts


def test_a_schema_check_refuses_what_a_cut_off_or_wrong_input_would_be():
    schema = {"type": "object", "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 4},
                                               "tags": {"type": "array", "items": {"type": "string"}},
                                               "mode": {"type": "string", "enum": ["a", "b"]}}, "required": ["count"]}
    assert invalid(schema, {"count": 2, "tags": ["@a"], "mode": "a"}) is None
    assert invalid(schema, {}) == "input is missing count"
    assert invalid(schema, {"count": True}) == "input.count should be an integer"
    assert invalid(schema, {"count": 9}) == "input.count should be from 1 to 4"
    assert invalid(schema, {"count": 1, "tags": [3]}) == "input.tags[0] should be a string"
    assert invalid(schema, {"count": 1, "mode": "c"}) == "input.mode should be one of a, b"
    assert invalid(schema, None) == "input should be an object"


def test_after_a_fallback_only_what_the_fallback_model_said_goes_back():
    declined = [
        {"type": "thinking", "thinking": "", "signature": "a"}, say("Partial"), use("library_list"),
        {"type": "fallback", "from": {"model": "claude-fable-5-2"}, "to": {"model": "claude-opus-4-8"}},
        {"type": "thinking", "thinking": "", "signature": "b"}, say("Done"),
    ]
    assert [b["type"] for b in echoable(declined)] == ["text", "fallback", "thinking", "text"]
    plain = [say("a"), use("engine_list")]
    assert echoable(plain) == plain


def test_tags_become_their_references_names_longest_first():
    labels = {"@mara": "@Image1", "@mara-young": "@Image2"}
    assert replace_tags("@Mara meets @mara-young; @mara.", labels) == "@Image1 meets @Image2; @Image1."


def test_the_streamed_answer_comes_back_as_the_api_sent_it():
    """The real adapter over a recorded stream: the request asks for what the module says, and blocks round-trip."""
    sent: list[dict[str, Any]] = []
    stream = [
        {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-fable-5-2",
                                               "content": [], "stop_reason": None, "stop_sequence": None,
                                               "usage": {"input_tokens": 10, "output_tokens": 1}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "Checking the library."}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "sig-abc"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Looking."}},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "toolu_1", "name": "library_list", "input": {}}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "{\"section\": \"Charac"}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "ters\"}"}},
        {"type": "content_block_stop", "index": 2},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None}, "usage": {"output_tokens": 20}},
        {"type": "message_stop"},
    ]

    def answer(request: httpx2.Request) -> httpx2.Response:
        sent.append({"headers": dict(request.headers), "body": json.loads(request.content)})
        body = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in stream)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())

    claude = Claude("sk-ant-test", "claude-fable-5-2")
    claude.client = anthropic.Anthropic(api_key="sk-ant-test", max_retries=0,
                                        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(answer)))
    blocks: list[dict[str, Any]] = []
    result = claude.respond([{"type": "text", "text": "system"}], [{"role": "user", "content": "hi"}],
                            [{"name": "library_list", "description": "d", "input_schema": {"type": "object"}, "eager_input_streaming": True}],
                            blocks.append, lambda: True)
    assert result.stop_reason == "tool_use"
    assert result.content == [
        {"type": "thinking", "thinking": "Checking the library.", "signature": "sig-abc"},
        {"type": "text", "text": "Looking."},
        {"type": "tool_use", "id": "toolu_1", "name": "library_list", "input": {"section": "Characters"}},
    ]
    assert blocks == result.content
    (request,) = sent
    body = request["body"]
    assert body["model"] == "claude-fable-5-2" and body["stream"] is True and body["max_tokens"] == 64000
    assert body["thinking"] == {"type": "adaptive", "display": "updates", "block_binding": {"prefix_mismatch_behavior": "drop_block"}}
    assert body["output_config"] == {"effort": "high"} and body["fallbacks"] == "default"
    assert body["cache_control"] == {"type": "ephemeral"} and body["tools"][0]["eager_input_streaming"] is True
    assert set(request["headers"]["anthropic-beta"].split(",")) == {
        "server-side-fallback-2026-07-01", "thinking-binding-controls-2026-08-01", "thinking-display-updates-2026-08-18"}


class FakeSandboxModule:
    """`addons/modal/sandbox.py`, as far as the launcher calls it, without `filmcraft_call` until one is given."""

    APP_NAME = "selkies"

    def __init__(self) -> None:
        self.images: list[str] = []
        self.started: list[tuple[str, dict[str, Any]]] = []

    def session_image(self, app: str) -> str:
        self.images.append(app)
        return f"image:{app}"

    def nuke_image(self, workspace: str) -> str:
        self.images.append(f"nuke:{workspace}")
        return f"nuke-image:{workspace}"

    def start_session(self, app: Any, name: str, **settings: Any) -> Any:
        self.started.append((name, settings))
        return SimpleNamespace(object_id=f"sb-{len(self.started)}", wait_until_ready=lambda timeout: None, terminate=lambda: None)


def test_the_launcher_starts_each_app_from_its_own_image_in_the_users_workspace():
    module = FakeSandboxModule()
    launcher = ModalLauncher(module, app="modal-app", site_url="https://lathe.example/app/")
    tier = {"gpu": None, "cpu": 2, "memory_gb": 4}
    project = str(uuid.uuid4())
    for app, project_id in (("filmcraft", project), ("filmcraft", project), ("nuke", project), ("blender", None)):
        launcher.start({"id": str(uuid.uuid4()), "user_id": ALICE.id, "app": app, "project_id": project_id}, tier, None)
    assert module.images == ["filmcraft", f"nuke:users/{ALICE.id}", "blender"], "one image per app; Nuke's from the user's install"
    film, _, nuke, blender = (settings for _, settings in module.started)
    assert film["application"] == "filmcraft" and film["image"] == "image:filmcraft"
    site = "https://lathe.example"
    assert film["workspace"] == f"/users/{ALICE.id}"
    assert film["env"] == {"SELKIES_MODAL_PROJECT": f"projects/{project}", "SELKIES_FRAME_ANCESTORS": site}
    assert nuke["image"] == f"nuke-image:users/{ALICE.id}" and nuke["application"] == "nuke"
    assert blender["env"] == {"SELKIES_FRAME_ANCESTORS": site} and "lathe_project" not in blender["tags"]
    assert ModalLauncher(module, app="modal-app").frame_ancestor == "", "no site, no frame allowed"
    assert origin("javascript:alert(1)") == "" and origin("http://localhost:5173/x") == "http://localhost:5173"

    launcher.sandbox = lambda sandbox_id: f"sandbox:{sandbox_id}"
    with pytest.raises(RuntimeError, match="no FilmCraft command channel"):
        launcher.filmcraft("sb-1", "engine.commands", {})
    calls = []
    module.filmcraft_call = lambda sandbox, method, params=None, timeout=60: calls.append((sandbox, method, params, timeout)) or {"ok": True}
    assert launcher.filmcraft("sb-1", "engine.commands", {}) == {"ok": True}
    assert calls == [("sandbox:sb-1", "engine.commands", {}, 60)]


class FakeModal:
    """Modal's named Secrets, as far as the launcher keeps registry credentials in them."""

    def __init__(self) -> None:
        self.secrets: dict[str, dict[str, str]] = {}
        fake = self

        class NotFoundError(Exception):
            pass

        class Secret:
            def __init__(self, name: str) -> None:
                self.name = name

            @staticmethod
            def from_name(name: str) -> Secret:
                return Secret(name)

            def hydrate(self) -> Secret:
                if self.name not in fake.secrets:
                    raise NotFoundError(self.name)
                return self

            def update(self, values: dict[str, str]) -> None:
                fake.secrets[self.hydrate().name].update(values)

        def create(name: str, values: dict[str, str], *, allow_existing: bool = False) -> None:
            if name in fake.secrets and not allow_existing:
                raise AssertionError(f"{name} exists")
            fake.secrets.setdefault(name, dict(values))

        def delete(name: str, *, allow_missing: bool = False) -> None:
            if name not in fake.secrets and not allow_missing:
                raise NotFoundError(name)
            fake.secrets.pop(name, None)

        Secret.objects = SimpleNamespace(create=create, delete=delete)
        self.module = SimpleNamespace(Secret=Secret, exception=SimpleNamespace(NotFoundError=NotFoundError))


def test_the_launcher_pulls_unreal_with_each_users_own_named_secret(monkeypatch):
    modal = FakeModal()
    monkeypatch.setitem(sys.modules, "modal", modal.module)
    module = FakeSandboxModule()
    launcher = ModalLauncher(module, app="modal-app")
    tier = {"gpu": "L4", "cpu": 8, "memory_gb": 32}
    session = lambda user: {"id": str(uuid.uuid4()), "user_id": user.id, "app": "unreal", "project_id": None}
    with pytest.raises(RuntimeError, match="cannot build Unreal Engine's image yet"):
        launcher.start(session(ALICE), tier, None, OwnCopy("5.8"))

    launcher.keep_registry_credential(BOB.id, "bob-gh", "gho_b", create=False)
    assert modal.secrets == {}, "refreshing makes no Secret for a user without one"
    launcher.keep_registry_credential(ALICE.id, "alice-gh", "gho_a")
    launcher.keep_registry_credential(ALICE.id, "alice-gh", "gho_a2")
    launcher.keep_registry_credential(BOB.id, "bob-gh", "gho_b")
    launcher.keep_registry_credential(BOB.id, "bob-gh", "gho_b2", create=False)
    assert modal.secrets == {
        f"lathe-ghcr-{ALICE.id}": {"REGISTRY_USERNAME": "alice-gh", "REGISTRY_PASSWORD": "gho_a2"},
        f"lathe-ghcr-{BOB.id}": {"REGISTRY_USERNAME": "bob-gh", "REGISTRY_PASSWORD": "gho_b2"},
    }, "one Secret per user, holding their latest token"

    pulls = []
    module.unreal_image = lambda registry_secret, version: pulls.append((registry_secret.name, version)) or f"unreal:{registry_secret.name}"
    for user in (ALICE, BOB, ALICE):
        launcher.start(session(user), tier, None, OwnCopy("5.8"))
    alice, bob = f"lathe-ghcr-{ALICE.id}", f"lathe-ghcr-{BOB.id}"
    assert pulls == [(alice, "5.8"), (bob, "5.8"), (alice, "5.8")], "each start pulls with its user's own named Secret"
    assert [settings["image"] for _, settings in module.started] == [f"unreal:{alice}", f"unreal:{bob}", f"unreal:{alice}"]
    with pytest.raises(RuntimeError, match="own registry credential"):
        launcher.start(session(ALICE), tier, None)
    assert module.images == [], "no image of Unreal is kept for the next start"

    launcher.forget_registry_credential(ALICE.id)
    launcher.forget_registry_credential(ALICE.id)
    assert list(modal.secrets) == [bob], "forgetting deletes the user's Secret, and a missing one is no error"


def test_github_reads_an_epic_link_from_what_the_token_can_see():
    """The real `GitHub` over a recorded GitHub: which calls the check makes, and what each answer means."""
    seen: list[httpx.Request] = []
    status: dict[str, int] = {}

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "gho_new", "scope": "repo,read:packages", "token_type": "bearer"})
        code = status.get(request.url.path, 200)
        return httpx.Response(code, json={"message": "Not Found"} if code == 404 else {})

    github = GitHub()
    github.http = httpx.Client(headers=github.http.headers, transport=httpx.MockTransport(answer))
    repo, package = "/repos/EpicGames/UnrealEngine", "/orgs/EpicGames/packages/container/unreal-engine"
    assert github.epic_access("gho_t") is True
    assert [(request.method, request.url.path) for request in seen] == [("GET", repo), ("GET", package)]
    assert {request.headers["authorization"] for request in seen} == {"Bearer gho_t"}

    seen.clear()
    status[repo] = 404
    assert github.epic_access("gho_t") is False and len(seen) == 1, "not in Epic's organization: the images are not asked"
    status.update({repo: 200, package: 404})
    assert github.epic_access("gho_t") is False, "the repository without the images is not a link the engine can be pulled with"
    status[repo] = 500
    with pytest.raises(GitHubError):
        github.epic_access("gho_t")

    assert github.exchange("id", "secret", "code", "https://api.example.test/cb") == Grant("gho_new", "repo,read:packages")
    assert [reads_packages(scope) for scope in ("repo,read:packages", "write:packages", "repo", "")] == [True, True, False, False]


def test_skills_are_chosen_by_discipline_with_their_references(tmp_path):
    for name, body in SKILLS.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "SKILL.md").write_text(body)
    (tmp_path / "filmcraft" / "references").mkdir()
    (tmp_path / "filmcraft" / "references" / "prompting.md").write_text("# Prompting\n\nPROMPTING-REFERENCE")
    skills = read_skills(tmp_path)
    media = [skill.name for skill in skills_for(skills, CATALOG, "media")]
    music = [skill.name for skill in skills_for(skills, CATALOG, "music")]
    games = [skill.name for skill in skills_for(skills, CATALOG, "games")]
    assert media == ["filmcraft", "studio-basics"] and music == ["songwriting", "studio-basics"] and games == ["studio-basics"]
    film = next(skill for skill in skills if skill.name == "filmcraft")
    assert film.description == "Editing films in FilmCraft." and "## references/prompting.md\n\n# Prompting" in film.body


def test_the_store_speaks_the_data_and_storage_apis():
    """The real `Store` over a recorded Supabase: the paths, filters, and headers each call sends."""
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.raw_path.decode().split("?")[0]
        if path == "/storage/v1/object/sign/library":
            return httpx.Response(200, json=[
                {"path": "u/p/a.png", "signedURL": "/object/sign/library/u/p/a.png?token=t", "error": None},
                {"path": "u/p/gone.png", "signedURL": None, "error": "Object not found"},
            ])
        if path == "/storage/v1/object/list/library":
            folder = json.loads(request.content)["prefix"]
            listing = [{"name": "a.png", "id": "1"}, {"name": "shots", "id": None}] if folder == "u/p" else [{"name": "b.mp4", "id": "2"}]
            return httpx.Response(200, json=listing)
        if path == "/rest/v1/agent_messages":
            offset = int(request.url.params["offset"])
            return httpx.Response(200, json=[{"id": n} for n in range(offset, min(offset + 1000, 1500))])
        if path == "/rest/v1/github_connections":
            return httpx.Response(201, json=[json.loads(request.content)])
        return httpx.Response(200, json={})

    store = Store("https://project.example.test", "sb_secret_key")
    store.http = httpx.Client(base_url="https://project.example.test", headers=store.http.headers, transport=httpx.MockTransport(answer))

    store.upload("library", "u/p/front view.png", b"png", "image/png")
    upload = seen[-1]
    assert upload.method == "POST" and upload.url.raw_path == b"/storage/v1/object/library/u/p/front%20view.png"
    assert upload.headers["x-upsert"] == "true" and upload.headers["content-type"] == "image/png" and upload.content == b"png"
    assert upload.headers["apikey"] == "sb_secret_key" and "authorization" not in upload.headers, "a secret key is never a bearer token"

    links = store.sign("library", ["u/p/a.png", "u/p/gone.png"], 3600)
    assert links == {"u/p/a.png": "https://project.example.test/storage/v1/object/sign/library/u/p/a.png?token=t"}
    assert json.loads(seen[-1].content) == {"expiresIn": 3600, "paths": ["u/p/a.png", "u/p/gone.png"]}

    store.remove_prefix("library", "u/p")
    removal = seen[-1]
    assert removal.method == "DELETE" and json.loads(removal.content) == {"prefixes": ["u/p/a.png", "u/p/shots/b.mp4"]}

    assert len(store.every("agent_messages", project_id="eq.p", order="id.asc")) == 1500
    assert [request.url.params["offset"] for request in seen[-2:]] == ["0", "1000"]

    store.upsert("github_connections", {"user_id": "u", "login": "x"}, on_conflict="user_id")
    assert seen[-1].url.params["on_conflict"] == "user_id"
    assert seen[-1].headers["prefer"] == "resolution=merge-duplicates,return=representation"


def test_fal_runs_a_generation_through_its_queue_and_prices_it():
    """The real `Fal` over a recorded fal: submit, poll the URLs fal gave, fetch, cancel when stopped, and price."""
    seen: list[httpx.Request] = []
    queue = "https://queue.fal.run/fal-ai/nano-banana-pro/requests/r1"
    prices = {
        "fal-ai/nano-banana-pro": ("0.15", "images"),
        "bytedance/seedream/v5.5/edit": ("0.03", "units"),
        "bytedance/seedance-2.5/reference-to-video": ("0.0214", "1000 tokens"),
        "fal-ai/other-video": ("0.014", "megapixels"),
    }

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)
        if request.method == "POST" and url.startswith("https://queue.fal.run/"):
            return httpx.Response(200, json={"request_id": "r1", "status_url": f"{queue}/status", "response_url": queue,
                                             "cancel_url": f"{queue}/cancel"})
        if url == f"{queue}/status":
            return httpx.Response(200, json={"status": "COMPLETED"})
        if url == queue:
            return httpx.Response(200, json={"images": [{"url": "https://v3.fal.media/files/out.png"}]})
        if request.url.path == "/v1/models/pricing":
            model = request.url.params["endpoint_id"]
            if model not in prices:
                return httpx.Response(404, json={"error": {"type": "not_found", "message": "no such model"}})
            price, unit = prices[model]
            return httpx.Response(200, json={"prices": [{"endpoint_id": model, "unit_price": float(price), "unit": unit, "currency": "USD"}]})
        if request.url.path == "/v1/models/pricing/estimate":
            return httpx.Response(200, json={"estimate_type": "historical_api_price", "total_cost": 2.5, "currency": "USD"})
        return httpx.Response(200, json={})

    fal = Fal("fal-key")
    fal.http = httpx.Client(headers=fal.http.headers, transport=httpx.MockTransport(answer))
    assert fal.run("fal-ai/nano-banana-pro", {"prompt": "a lighthouse"}, lambda: True, 60) == {"images": [{"url": "https://v3.fal.media/files/out.png"}]}
    submit, status, result = seen
    assert str(submit.url) == "https://queue.fal.run/fal-ai/nano-banana-pro" and json.loads(submit.content) == {"prompt": "a lighthouse"}
    assert submit.headers["authorization"] == "Key fal-key" and str(status.url) == f"{queue}/status" and str(result.url) == queue

    seen.clear()
    with pytest.raises(GenerationStopped):
        fal.run("fal-ai/nano-banana-pro", {"prompt": "a lighthouse"}, lambda: False, 60)
    assert [(request.method, str(request.url)) for request in seen][1:] == [("PUT", f"{queue}/cancel")], "a stopped turn cancels what it queued"

    assert fal.cost("fal-ai/nano-banana-pro", {"image": 2}) == 0.3
    assert fal.cost("bytedance/seedream/v5.5/edit", {"image": 2, "unit": 2}) == 0.06, "priced per output"
    tokens = video_kilotokens("720p", "16:9", 4)
    assert tokens == 86.4, "720p 16:9 is 21,600 tokens a second"
    assert video_kilotokens("720p", "9:16", 4) == tokens and video_kilotokens("720p", "auto", 4) == tokens
    assert fal.cost("bytedance/seedance-2.5/reference-to-video", {"video": 1, "second": 4, "1000 token": tokens}) == 1.849
    assert fal.cost("fal-ai/other-video", {"video": 1, "second": 6}) == 2.5, "priced in a unit the call does not count: fal's estimate"
    assert fal.cost("unknown/model", {"image": 1}) is None, "a price fal does not give is left out"
