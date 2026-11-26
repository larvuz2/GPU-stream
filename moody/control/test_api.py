# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The API, the MCP endpoint, and the agent over the service, with every outside party stood in for.

`FakeStore` answers the calls the service makes to Supabase, its Data API and
its Storage, with the least that keeps them true to the database's functions,
whose own behavior is what the migrations' checks hold; `FakeLauncher` records
what would have reached Modal, `FakeGitHub` what would have reached GitHub and its registry,
`FakeFal` what would have reached fal, and `ScriptedLoop` (`scripted_loop.py`)
stands in for the Claude Agent SDK and its child process, answering the agent
the way a scripted conversation says and recording every request the model
would have been sent. The same turns run through the real SDK and its real
program, against a scripted API, in `test_loop.py`.
What is tested here is this side: who a credential names, what each route and
tool returns and refuses, that one user's sessions, projects, libraries, and
engines are invisible to another, that a turn's events tell what happened in
order, that a project's conversation is one session kept in the database, what
the person approves and what ends a turn, which skills and subagents a project
is offered, that GitHub's callbacks take nothing they did not sign, that the GitHub
App's token is refreshed before it expires and its repositories are its
installations', that the agent writes to no branch of a repository but its
own, that it reads an Unreal project's assets from the repository alone, that
Unreal Engine starts for anyone and brings the editor only to an Epic
connection the registry lets pull it, with that user's own token, that an
engine of a linked project clones it with a token no row keeps, that its two
pictures are linked for the listing page alone, and that the agent brings up a
project cloned into the engine, opens it (an older one on its own branch), and
switches the person's screen to it. Run with `pytest moody/control`.
"""

from __future__ import annotations

import base64
import copy
from contextlib import nullcontext
from dataclasses import replace
import hashlib
import hmac
import itertools
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

import anyio
import httpx
import pytest
from claude_agent_sdk.testing import run_session_store_conformance
from fastapi.testclient import TestClient

from agent import SPECS, TOOL_NAMES, TOOLS, Agent, Result, check_activities, recap, replace_tags, reported_unreal, system_prompt
from api import create_app
from definitions import (
    AgentSpec,
    agents_directory,
    agents_for,
    matching,
    operators,
    read_agents,
    read_skills,
    skills_directory,
    skills_for,
)
from looking import NoPicture, picture_of
from loop import BUILT_INS, PREFIX, SDK_VARIABLES, Blocks, Settings, Workspace, child_environment, fetchable, inside, loop_name
from scripted_loop import Reply, ScriptedLoop
from transcript import Transcript
from generation import AUDIO_MODELS, IMAGE_MODELS, SPEECH_VOICES, VIDEO_MODELS, Fal, GenerationStopped, audio_arguments, audio_units, video_kilotokens
import genui
from github_client import EPIC_FLOW, GitHub, GitHubError, Grant, read_state, seal, sign_state, unseal
from launcher import ModalLauncher, origin
from service import OPEN, Catalog, Clone, Config, OwnCopy, Refused, Sessions, Store, User, hash_key
import unreal

CATALOG = Catalog(Path(__file__).resolve().parent.parent / "catalog.json")


class Counter:
    """The whole numbers from one, each given once.

    `itertools.count` does the same and cannot be pickled from Python 3.14
    on, and the store that holds these is handed to another process as a
    pickle (`test_loop.py`, `trial.py`).
    """

    def __init__(self) -> None:
        self.last = 0

    def __next__(self) -> int:
        self.last += 1
        return self.last
ALICE = User(id="00000000-0000-0000-0000-00000000000a", email="alice@example.test")
BOB = User(id="00000000-0000-0000-0000-00000000000b", email="bob@example.test")
TOKENS = {"alice-token": ALICE, "bob-token": BOB}
SECRET = "test-secret-key"
SITE = "https://site.example.test"
# The GitHub App's client and the Epic OAuth App's, with their secrets, and the GitHub App's name in its pages' address
APP_CLIENT, EPIC_CLIENT = "gh-app-client", "epic-client"
SECRETS = {APP_CLIENT: "gh-app-secret", EPIC_CLIENT: "epic-secret", "": ""}
SLUG = "moody-studio"
SERIAL_TABLES = ("project_events", "agent_transcripts")
# The tables keyed by their user, one row each
CONNECTIONS = ("github_connections", "epic_connections")
DEFAULTS: dict[str, dict[str, Any]] = {
    "projects": {
        "format": "", "pinned": False, "library_sections": [], "plan": [], "github_repo": None, "github_branch": None,
        "turn_id": None, "turn_seen_at": None, "stop_requested": False, "agent_session": None, "permissions": {},
    },
    "assets": {"tag": None, "description": "", "metadata": {}, "media": []},
    "project_events": {"data": {}, "turn_id": None},
    "agent_transcripts": {"subpath": "", "uuid": None},
    "github_connections": {
        "avatar_url": "", "scope": "", "github_id": None, "name": "", "refresh_token_encrypted": None,
        "token_expires_at": None, "refresh_expires_at": None,
    },
    "epic_connections": {"scope": ""},
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
            "sessions": self.sessions, "api_keys": self.keys, "profiles": self.profiles,
            **{
                table: {}
                for table in ("projects", "assets", "project_events", "agent_transcripts", "github_connections", "epic_connections")
            },
        }
        self.files: dict[str, tuple[bytes, str]] = {}
        self.serial = Counter()
        self.clock = Counter()

    def stamp(self) -> str:
        """Now, a microsecond later each time, so rows sort in the order they were written."""
        return (moment() + timedelta(microseconds=next(self.clock))).isoformat()

    def user_of_token(self, token: str) -> User | None:
        return TOKENS.get(token)

    def rpc(self, function: str, **a: Any) -> Any:
        return getattr(self, function)(**a)

    # The database's functions

    def moody_ensure_profile(self, p_user: str, p_email: str, p_signup_credits: int) -> dict[str, Any]:
        return self.profiles.setdefault(
            p_user,
            {"id": p_user, "email": p_email, "credits": p_signup_credits, "max_sessions": 1, "turn_budget_usd": None, "turn_limit": None,
             "name": "", "settings": {}},
        )

    def moody_request_session(
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

    def moody_session_started(self, p_session: str, p_sandbox_id: str) -> dict[str, Any]:
        session = self.sessions[p_session]
        if session["status"] != "starting":
            return {"id": None}
        session.update(status="running", sandbox_id=p_sandbox_id, started_at="2026-11-21T00:00:10+00:00")
        return dict(session)

    def moody_end_session(self, p_session: str, p_reason: str, p_failed: bool) -> dict[str, Any]:
        session = self.sessions[p_session]
        if session["status"] not in ("ended", "failed"):
            session.update(status="failed" if p_failed else "ended", end_reason=p_reason, ended_at="2026-11-21T00:10:00+00:00")
        return dict(session)

    def moody_charge_session(self, p_session: str, p_final: bool) -> int:
        return self.profiles[self.sessions[p_session]["user_id"]]["credits"]

    def moody_claim_queued(self, p_capacity: int) -> list[dict[str, Any]]:
        running = sum(s["status"] in ("starting", "running") for s in self.sessions.values())
        claimed = [s for s in self.sessions.values() if s["status"] == "queued"][: max(p_capacity - running, 0)]
        for session in claimed:
            session["status"] = "starting"
        return [dict(s) for s in claimed]

    def moody_queue_position(self, p_session: str) -> int:
        return 1

    def moody_use_api_key(self, p_key_hash: str) -> str | None:
        key = self.keys.get(p_key_hash)
        return key["user_id"] if key and key["revoked_at"] is None else None

    def moody_add_credits(self, p_user: str, p_delta: int, p_reason: str, p_reference: str | None) -> int:
        if (p_user, p_delta, p_reference) not in self.ledger:
            self.ledger.append((p_user, p_delta, p_reference))
            self.profiles[p_user]["credits"] += p_delta
        return self.profiles[p_user]["credits"]

    def moody_begin_turn(self, p_project: str, p_user: str, p_text: str, p_stale_seconds: int, p_ui: dict[str, Any] | None = None) -> str:
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
        said = {"text": p_text} if p_ui is None else {"text": p_text, "ui": p_ui}
        self.insert("project_events", {"project_id": p_project, "turn_id": turn, "kind": "user_message", "data": said})
        return turn

    def moody_resolve_approval(self, p_project: str, p_approval: str, p_decision: str) -> str:
        events = [e for e in self.tables["project_events"].values() if e["project_id"] == p_project]
        asked = next((e for e in events if e["kind"] == "approval" and e["data"]["approval_id"] == p_approval), None)
        if asked is None:
            raise Refused(*Store.REFUSALS["no_approval"])
        standing = next((e for e in events if e["kind"] == "approval_result" and e["data"]["approval_id"] == p_approval), None)
        if standing is not None:
            return standing["data"]["decision"]
        answer = {"approval_id": p_approval, "decision": p_decision}
        if "agent_id" in asked["data"]:
            answer["agent_id"] = asked["data"]["agent_id"]
        self.insert("project_events", {"project_id": p_project, "turn_id": asked["turn_id"], "kind": "approval_result", "data": answer})
        if p_decision == "always":
            self.tables["projects"][p_project]["permissions"][asked["data"]["tool"]] = "always"
        return p_decision

    def transcript(self, p_project: str, p_project_key: str) -> list[dict[str, Any]]:
        rows = self.tables["agent_transcripts"].values()
        return sorted((r for r in rows if r["project_id"] == p_project and r["project_key"] == p_project_key), key=lambda r: r["id"])

    def moody_append_transcript(self, p_project: str, p_project_key: str, p_session: str, p_subpath: str, p_entries: list[dict[str, Any]]) -> int:
        written = 0
        for entry in p_entries:
            known = {r["uuid"] for r in self.transcript(p_project, p_project_key) if (r["session_id"], r["subpath"]) == (p_session, p_subpath)}
            if entry.get("uuid") is not None and entry["uuid"] in known:
                continue
            self.insert("agent_transcripts", {"project_id": p_project, "project_key": p_project_key, "session_id": p_session,
                                              "subpath": p_subpath, "uuid": entry.get("uuid"), "entry": entry})
            written += 1
        return written

    def moody_transcript_sessions(self, p_project: str, p_project_key: str) -> list[dict[str, Any]]:
        latest: dict[str, str] = {}
        for row in self.transcript(p_project, p_project_key):
            if row["subpath"] == "":
                latest[row["session_id"]] = row["created_at"]
        return [{"session_id": session, "mtime": int(datetime.fromisoformat(stamp).timestamp() * 1000)} for session, stamp in latest.items()]

    def moody_transcript_subkeys(self, p_project: str, p_project_key: str, p_session: str) -> list[dict[str, Any]]:
        found = {r["subpath"] for r in self.transcript(p_project, p_project_key) if r["session_id"] == p_session and r["subpath"]}
        return [{"subpath": subpath} for subpath in sorted(found)]

    def moody_turn_alive(self, p_project: str, p_turn: str) -> bool:
        project = self.tables["projects"].get(p_project)
        if project is None or project["turn_id"] != p_turn or project["stop_requested"]:
            return False
        project["turn_seen_at"] = moment().isoformat()
        return True

    def moody_end_turn(self, p_project: str, p_turn: str) -> bool:
        project = self.tables["projects"].get(p_project)
        if project is None or project["turn_id"] != p_turn:
            return False
        project.update(turn_id=None, turn_seen_at=None, stop_requested=False)
        self.insert("project_events", {"project_id": p_project, "turn_id": p_turn, "kind": "turn_end"})
        return True

    def moody_stop_turn(self, p_project: str, p_user: str, p_stale_seconds: int) -> bool:
        project = self.tables["projects"].get(p_project)
        if project is None or project["user_id"] != p_user or not project["turn_id"]:
            return False
        if moment() - datetime.fromisoformat(project["turn_seen_at"]) >= timedelta(seconds=p_stale_seconds):
            self.moody_end_turn(p_project, project["turn_id"])
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
        self.tables[table][row["user_id"] if table in CONNECTIONS else row["id"]] = row
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
                for owned in ("assets", "project_events", "agent_transcripts"):
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

    def download(self, bucket: str, path: str, limit: int) -> bytes:
        data = self.files[path][0]
        if len(data) > limit:
            raise ValueError(f"{path} is larger than {limit} bytes")
        return data

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
        self.clones: list[Clone | None] = []
        # What each Sandbox reports of the clone it made as it started
        self.clone_states: dict[str, dict[str, Any]] = {}
        self.credentials: dict[str, dict[str, str]] = {}
        self.stopped: list[str] = []
        self.exits: dict[str, int] = {}
        self.fail_start = False
        self.commands: list[tuple[str, str]] = []
        self.calls: list[tuple[str, str, str, Any]] = []
        # The apps whose engines have a command channel
        self.channels = {"filmcraft"}
        # The .uproject files each Sandbox's workspace holds, as the machine reports them
        self.uprojects: dict[str, list[dict[str, Any]]] = {}
        self.project_reads: list[str] = []
        self.links: list[tuple[str, str]] = []
        # What a command containing each text answers, where it is not the default success
        self.answers: list[tuple[str, tuple[int, str]]] = []
        # The files a Sandbox holds, by path, where one's bytes matter; the reads made, and what was carried between two
        self.files: dict[str, bytes] = {}
        self.reads: list[tuple[str, str]] = []
        self.sent: list[tuple[str, str, str, str]] = []
        # Paths a Sandbox asked to send does not have
        self.absent: set[str] = set()

    def start(
        self, session: dict[str, Any], tier: dict[str, Any], region: str | None, own_copy: OwnCopy | None = None,
        clone: Clone | None = None,
    ) -> str:
        if self.fail_start:
            raise RuntimeError("Please add a payment method to use T4 GPU sandboxes.")
        self.started.append((session, tier, region))
        self.own_copies.append(own_copy)
        self.clones.append(clone)
        return f"sb-{len(self.started)}"

    def clone_status(self, sandbox_id: str) -> dict[str, Any] | None:
        return copy.deepcopy(self.clone_states.get(sandbox_id))

    def keep_registry_credential(self, user_id: str, username: str, token: str, create: bool = True) -> None:
        if create or user_id in self.credentials:
            self.credentials[user_id] = {"REGISTRY_USERNAME": username, "REGISTRY_PASSWORD": token}

    def forget_registry_credential(self, user_id: str) -> None:
        self.credentials.pop(user_id, None)

    def state(self, sandbox_id: str) -> int | None:
        return self.exits.get(sandbox_id)

    def link(self, sandbox_id: str) -> str:
        self.links.append((sandbox_id, "Desktop"))
        return f"https://{sandbox_id}.example.test/?_modal_connect_token=x#token=y"

    def unreal_link(self, sandbox_id: str) -> str:
        self.links.append((sandbox_id, "Unreal"))
        return f"https://{sandbox_id}-unreal.example.test/?_modal_connect_token=u"

    def unreal_projects(self, sandbox_id: str) -> list[dict[str, Any]]:
        self.project_reads.append(sandbox_id)
        return copy.deepcopy(self.uprojects.get(sandbox_id, []))

    def stop(self, sandbox_id: str) -> None:
        self.stopped.append(sandbox_id)

    def blender_python(self, sandbox_id: str, code: str) -> tuple[int, str]:
        return (1, "Traceback: boom\n") if "raise" in code else (0, f"ran in {sandbox_id}: {code}\n")

    def screenshot(self, sandbox_id: str) -> bytes:
        return b"\xff\xd8\xff\xe0 a jpeg"

    def exec(self, sandbox_id: str, command: str, timeout: int) -> tuple[int, str]:
        self.commands.append((sandbox_id, command))
        return next((answer for text, answer in self.answers if text in command), (0, f"ran in {sandbox_id}\n"))

    def read_file(self, sandbox_id: str, path: str, limit: int) -> bytes:
        self.reads.append((sandbox_id, path))
        data = self.files.get(path, f"bytes of {PurePosixPath(path).name}".encode())
        if len(data) > limit:
            raise ValueError(f"{path} is larger than {limit} bytes")
        return data

    def send(self, sandbox_id: str, path: str, to_sandbox_id: str, to_path: str, keep_going: Callable[[], bool]) -> int:
        if path in self.absent:
            raise FileNotFoundError(path)
        if not keep_going():
            raise InterruptedError("stopped")
        self.sent.append((sandbox_id, path, to_sandbox_id, to_path))
        return 2048

    def has_channel(self, app: str) -> bool:
        return app in self.channels

    def engine_call(self, sandbox_id: str, app: str, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        if app not in self.channels:
            raise RuntimeError(f"This deployment's launcher has no command channel for {app}.")
        self.calls.append((sandbox_id, app, method, params))
        return {"ok": True, "app": app, "method": method}


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
    """GitHub, as far as Moody reaches it: its two apps' grants, the GitHub App's installations, the container
    registry's answer, and the repositories with their branches and files.

    A code is good for one app (`codes`): a GitHub App code grants an expiring user token and the
    refresh token that renews it, an Epic code a token that reads packages. A token works while it
    is `live`; a refresh retires the refresh token and the token it renewed and grants a new pair,
    as GitHub's does, and `racer`, when set, runs inside the next refresh first, which is how a
    test has another refresh win a race for the same refresh token. Each token is some account's
    (`ACCOUNTS`), whose installations of the GitHub App (`installed`) hold the repositories its
    token reaches; a public repository the app is not installed on is still readable. The registry
    grants Epic's pull to the tokens in `pullers`, and answers with `registry_refusal` instead,
    when set.

    A branch points at a commit, and a commit is a snapshot of every file of its repository
    (`commits`), so a test can hold a branch's files before and after. A tree is listed from a
    commit's files the way the Git Trees API lists one, a subtree's SHA naming its commit and
    folder, and a recursive listing longer than `tree_limit` entries comes back truncated, as
    GitHub's does past 100,000. `files`, the walk over those listings, is the real client's.
    """

    authorize_url = staticmethod(GitHub.authorize_url)
    install_url = staticmethod(GitHub.install_url)
    files = GitHub.files
    ACCOUNTS = {
        "alice": {"login": "alice-gh", "id": 1001, "name": "Alice Example", "avatar_url": "https://avatars.example.test/alice"},
        "bob": {"login": "bob-gh", "id": 1002, "name": None, "avatar_url": "https://avatars.example.test/bob"},
    }

    def __init__(self) -> None:
        self.codes = {
            "good-code": (APP_CLIENT, "alice"),
            "next-code": (APP_CLIENT, "alice"),
            "bob-code": (APP_CLIENT, "bob"),
            "epic-code": (EPIC_CLIENT, "alice"),
            "epic-next-code": (EPIC_CLIENT, "alice"),
            "epic-bob-code": (EPIC_CLIENT, "bob"),
        }
        self.owners: dict[str, str] = {}
        self.live: set[str] = set()
        self.refresh_tokens: dict[str, str] = {}
        self.refreshes: list[str] = []
        self.racer: Callable[[], None] | None = None
        self.minted = itertools.count(1)
        self.pullers: set[str] = set()
        self.registry_refusal: GitHubError | None = None
        self.registry_checks: list[tuple[str, str]] = []
        self.repositories: dict[str, dict[str, Any]] = {}
        self.installed: dict[int, dict[str, Any]] = {
            1: {"account": "alice-gh", "members": {"alice-gh"}, "repositories": []},
            2: {"account": "bob-gh", "members": {"bob-gh"}, "repositories": []},
        }
        self.commits: dict[str, dict[str, str]] = {}
        self.refs: dict[tuple[str, str], str] = {}
        self.made_branches: list[tuple[str, str, str]] = []
        self.tree_calls: list[tuple[str, bool]] = []
        self.tree_limit = 100_000
        self.redirects: list[str] = []
        self.tokens: list[str] = []
        self.add_repository("alice-gh/film", push=True, updated="2026-11-20T00:00:00Z")
        self.add_repository("someone/theirs", push=False, updated="2026-11-19T00:00:00Z", private=False, installation=None)

    def mint(self, who: str, client: str) -> Grant:
        """A grant of one app for an account, its token live from now."""
        number = next(self.minted)
        if client == EPIC_CLIENT:
            token = f"gho_{who}_epic_{number}"
            self.owners[token] = who
            self.live.add(token)
            return Grant(token, "read:packages")
        token, refresh = f"ghu_{who}_{number}", f"ghr_{who}_{number}"
        self.owners[token] = who
        self.live.add(token)
        self.refresh_tokens[refresh] = token
        return Grant(token, "", 28800, refresh, 15897600)

    def login(self, token: str) -> str:
        """The login a live token is for; GitHub's 401 for any other."""
        if token not in self.live:
            raise GitHubError(401, "Bad credentials")
        return self.ACCOUNTS[self.owners[token]]["login"]

    def reaches(self, login: str, full_name: str) -> bool:
        """Whether one of the app's installations the account is in holds the repository."""
        return any(login in found["members"] and full_name in found["repositories"] for found in self.installed.values())

    def install(self, full_name: str, number: int, account: str, members: set[str]) -> None:
        """Install the app on a repository, in a new or existing installation of an account."""
        found = self.installed.setdefault(number, {"account": account, "members": set(members), "repositories": []})
        found["repositories"].append(full_name)

    def add_repository(
        self, full_name: str, push: bool, updated: str = "2026-11-24T00:00:00Z", private: bool = True,
        files: dict[str, str] | None = None, pull: bool = True, installation: int | None = 1,
    ) -> dict[str, Any]:
        """A repository with one commit on `main`, its default branch, in one of the app's installations unless none."""
        self.repositories[full_name] = {
            "full_name": full_name, "private": private, "html_url": f"https://github.com/{full_name}",
            "updated_at": updated, "default_branch": "main", "permissions": {"push": push, "pull": pull},
        }
        if installation is not None:
            self.installed[installation]["repositories"].append(full_name)
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
        client, who = self.codes.get(code, ("", ""))
        if client != client_id or client_secret != SECRETS[client]:
            raise GitHubError(401, "bad_verification_code")
        return self.mint(who, client)

    def refresh(self, client_id: str, client_secret: str, refresh_token: str) -> Grant:
        if self.racer is not None:
            racer, self.racer = self.racer, None
            racer()
        self.refreshes.append(refresh_token)
        if client_id != APP_CLIENT or client_secret != SECRETS[APP_CLIENT] or refresh_token not in self.refresh_tokens:
            raise GitHubError(401, "bad_refresh_token")
        renewed = self.refresh_tokens.pop(refresh_token)
        self.live.discard(renewed)
        return self.mint(self.owners[renewed], APP_CLIENT)

    def registry_pull(self, login: str, token: str) -> bool:
        self.registry_checks.append((login, token))
        if self.registry_refusal is not None:
            raise self.registry_refusal
        return token in self.pullers and token in self.live and self.login(token) == login

    def user(self, token: str) -> dict[str, Any]:
        self.tokens.append(token)
        self.login(token)
        return dict(self.ACCOUNTS[self.owners[token]])

    def installations(self, token: str) -> list[dict[str, Any]]:
        login = self.login(token)
        return [
            {"id": number, "account": {"login": found["account"]}}
            for number, found in self.installed.items()
            if login in found["members"]
        ]

    def installation_repositories(self, token: str, installation_id: int, limit: int) -> list[dict[str, Any]]:
        login = self.login(token)
        found = self.installed.get(installation_id)
        if found is None or login not in found["members"]:
            raise GitHubError(404, "Not Found")
        return [self.repositories[name] for name in found["repositories"]][:limit]

    def repo(self, token: str, full_name: str) -> dict[str, Any]:
        login = self.login(token)
        found = self.repositories.get(full_name)
        if found is None or (found["private"] and not self.reaches(login, full_name)):
            raise GitHubError(404, "Not Found")
        if not self.reaches(login, full_name):
            return {**found, "permissions": {"push": False, "pull": True}}
        return found

    def writable(self, token: str, full_name: str) -> None:
        """GitHub's refusal of a write the app may not make for this token's account."""
        if not self.reaches(self.login(token), full_name):
            raise GitHubError(403, "Resource not accessible by integration")

    def head(self, token: str, full_name: str, branch: str) -> str | None:
        self.repo(token, full_name)
        return self.refs.get((full_name, branch))

    def branches_under(self, token: str, full_name: str, prefix: str) -> list[str]:
        self.repo(token, full_name)
        return sorted(branch for repo, branch in self.refs if repo == full_name and branch.startswith(prefix))

    def create_branch(self, token: str, full_name: str, branch: str, sha: str) -> None:
        self.writable(token, full_name)
        if (full_name, branch) in self.refs:
            raise GitHubError(422, "Reference already exists")
        self.refs[(full_name, branch)] = sha
        self.made_branches.append((full_name, branch, sha))

    def tree(self, token: str, full_name: str, sha: str, recursive: bool) -> dict[str, Any]:
        self.repo(token, full_name)
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
        self.repo(token, full_name)
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
        self.writable(token, full_name)
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
        # What a result's file holds, by its suffix; a file of a suffix not here holds its own address
        self.files: dict[str, bytes] = {}
        # What the next runs raise, one each, before any run answers again
        self.failures: list[Exception] = []

    def run(self, model: str, arguments: dict[str, Any], alive: Callable[[], bool], limit_seconds: float) -> dict[str, Any]:
        self.calls.append((model, arguments))
        if self.failures:
            raise self.failures.pop(0)
        if model in VIDEO_MODELS.values():
            return {"video": {"url": "https://fal.example.test/files/shot.mp4"}, "seed": 7}
        if model == AUDIO_MODELS["music"]:
            # As the music model answers: how long the piece came out, which may be under what was allowed
            return {"audio": {"url": f"https://fal.example.test/files/take-{len(self.calls)}.wav"}, "seed": 40 + len(self.calls), "duration": 42.5}
        if model in AUDIO_MODELS.values():
            return {"audio": {"url": f"https://fal.example.test/files/take-{len(self.calls)}{'.mp3' if model == AUDIO_MODELS['sound'] else '.wav'}"}}
        return {"images": [{"url": f"https://fal.example.test/files/image-{n}.png"} for n in range(arguments["num_images"])]}

    def download(self, url: str) -> tuple[bytes, str]:
        types = {".mp4": "video/mp4", ".wav": "audio/wav", ".mp3": "audio/mpeg"}
        return self.files.get(PurePosixPath(url).suffix, url.encode()), types.get(PurePosixPath(url).suffix, "image/png")

    def cost(self, model: str, units: dict[str, float]) -> float | None:
        if model in VIDEO_MODELS.values():
            return round(0.473 * units["second"], 4) if "second" in units else None
        if model == AUDIO_MODELS["speech"]:
            return round(0.045 * units["1000 character"], 4)
        if model in AUDIO_MODELS.values():
            return round(0.002 * units["second"], 4) if "second" in units else None
        return round(0.15 * units["image"], 4)


CALL_IDS = itertools.count(1)


def say(words: str) -> dict[str, Any]:
    return {"type": "text", "text": words}


def use(tool: str, /, **arguments: Any) -> dict[str, Any]:
    """A call as the model makes one: of a Moody tool or one of the loop's own by Moody's name for it, else as named."""
    name = loop_name(tool) if tool in TOOL_NAMES or tool in BUILT_INS else tool
    return {"type": "tool_use", "id": f"toolu_{next(CALL_IDS):04d}", "name": name, "input": arguments}


def reply(*blocks: dict[str, Any], stop: str | None = None) -> Reply:
    return Reply(content=list(blocks), stop_reason=stop)


def config(**changes: Any) -> Config:
    values: dict[str, Any] = {
        "supabase_url": "https://project.example.test", "supabase_key": "service-key", "stripe_key": "",
        "stripe_webhook_secret": "", "site_url": SITE, "capacity": 10,
        "tiers": frozenset({"cpu", "t4"}), "pin_regions": False, "approval_seconds": 5,
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
    "filmcraft": "---\nname: filmcraft\ndescription: Editing films in FilmCraft.\noperator_tools: filmcraft, library_list\n---\n\n"
                 "Cut on action. FILMCRAFT-SKILL-TEXT\nFor color see [color](references/color.md).\n",
    "studio-basics": "# Basics\n\nName every file. GENERAL-SKILL-TEXT\n",
    "songwriting": "---\ndescription: Writing songs.\ndisciplines: [music]\n---\nSONG-SKILL-TEXT\n",
}
REFERENCE = "Grade last. FILMCRAFT-REFERENCE-TEXT\n"
AGENTS = {
    "research.md": "---\nname: research\ntitle: Research agent\ndescription: Looks things up on the web and in the library.\n"
                   "disciplines: all\ntools: web_search, web_fetch, library_list, library_upsert\nmodel: balanced\n---\nYou research. RESEARCH-PROMPT\n",
    "lyricist.md": "---\nname: lyricist\ntitle: Lyricist\ndescription: Writes lyrics.\ndisciplines: music\ntools: library_*\n"
                   "skills: songwriting\nmodel: light\n---\nYou write lyrics. LYRICIST-PROMPT\n",
    "_operator.md": "---\nname: {app}\ntitle: {name} agent\ndescription: Drives {name} for one job in a running engine.\nskills: {app}\n"
                    "model: inherit\n---\n\n<!--\n  A license header.\n-->\n\nYou operate {name} (app `{app}`). OPERATOR-PROMPT\n",
    "README.md": "# Subagents\n\nHow to write one.\n",
}


def write_definitions(folder: Path) -> tuple[Path, Path]:
    """The fixture skills and subagent definitions as files, under a folder: where the skills are, and the agents."""
    skills, agents = folder / "skills", folder / "agents"
    for name, body in SKILLS.items():
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text(body)
    (skills / "filmcraft" / "references").mkdir()
    (skills / "filmcraft" / "references" / "color.md").write_text(REFERENCE)
    agents.mkdir()
    for name, body in AGENTS.items():
        (agents / name).write_text(body)
    return skills, agents


@pytest.fixture
def studio(tmp_path: Path) -> SimpleNamespace:
    """The Studio's whole backend: every integration configured, and the agent running each turn inline."""
    skills_folder, agents_folder = write_definitions(tmp_path)
    store, launcher, jobs, github, fal, model = FakeStore(), FakeLauncher(), InlineJobs(), FakeGitHub(), FakeFal(), ScriptedLoop()
    # The hook at a turn's end is run by the tests of how a turn ends; any other may leave an engine open without
    # scripting what the model answers to being told so
    model.stop_hooks = False
    settings = config(anthropic_key="sk-ant-test", fal_key="fal-test", github_app_client_id=APP_CLIENT,
                      github_app_client_secret=SECRETS[APP_CLIENT], github_app_slug=SLUG, epic_client_id=EPIC_CLIENT,
                      epic_client_secret=SECRETS[EPIC_CLIENT], secret_key=SECRET, loop_root=str(tmp_path / "loop"),
                      loop_cli="/bin/true")
    sessions = Sessions(settings, CATALOG, store, launcher, jobs, github)
    jobs.sessions = sessions
    skills, agents = read_skills(skills_folder), read_agents(agents_folder)
    derived = operators(agents_folder, CATALOG, skills)
    agent = Agent(sessions, model, fal, skills, agents, derived)
    # The heartbeat's thread stays quiet: the beats a turn makes at its start and before each tool are what a test drives
    agent.heartbeat_seconds = 3600
    agent.approval_poll_seconds = 0.01
    jobs.agent = agent
    with TestClient(create_app(sessions, settings, CATALOG, skills, agents, derived)) as client:
        yield SimpleNamespace(client=client, sessions=sessions, store=store, launcher=launcher, jobs=jobs,
                              github=github, fal=fal, model=model, agent=agent, tmp=tmp_path)
    assert model.may_run_dry or not model.ran_dry, "a turn asked the model for more than the test scripted"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def new_project(client: TestClient, token: str = "alice-token", asks: bool = False, **body: Any) -> dict[str, Any]:
    """Make a project. Its agent runs the tools the person approves without asking, unless `asks` leaves that on."""
    response = client.post("/v1/projects", headers=auth(token), json={"name": "Mara", "discipline": "media", "format": "Film & TV", **body})
    assert response.status_code == 200, response.text
    project = response.json()["project"]
    if not asks:
        always = {name: "always" for name, definition in SPECS.items() if definition["approval"]}
        response = client.patch(f"/v1/projects/{project['id']}", headers=auth(token), json={"permissions": always})
        assert response.status_code == 200, response.text
        project = response.json()["project"]
    return project


def events(client: TestClient, project_id: str, token: str = "alice-token", after: int = 0) -> dict[str, Any]:
    response = client.get(f"/v1/projects/{project_id}/events", headers=auth(token), params={"after": after})
    assert response.status_code == 200, response.text
    return response.json()


def message(client: TestClient, project_id: str, words: str, token: str = "alice-token") -> Any:
    return client.post(f"/v1/projects/{project_id}/messages", headers=auth(token), json={"text": words})


def tool_results(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The results the newest user message of a request carries, by the call they answer.

    A result's content is given as the tools wrote it: text as one string, and
    with a picture in it, the blocks, each picture as the Messages API has one.
    """
    user = next(m for m in reversed(request["messages"]) if m["role"] == "user")
    found = {}
    for block in user["content"]:
        if block["type"] != "tool_result":
            continue
        content = block["content"]
        if isinstance(content, list) and all(part["type"] == "text" for part in content):
            content = "".join(part["text"] for part in content)
        elif isinstance(content, list):
            content = [
                {"type": "image", "source": {"type": "base64", "media_type": part["mimeType"], "data": part["data"]}}
                if part["type"] == "image" else part
                for part in content
            ]
        found[block["tool_use_id"]] = {**block, "content": content}
    return found


def said(request: dict[str, Any], back: int = 1) -> tuple[str, str]:
    """A message of the person in a request, counted from the newest: their words, and the project state after them."""
    spoken = [m for m in request["messages"] if m["role"] == "user" and isinstance(m["content"], list)
              and m["content"][0]["type"] == "text"]
    words, state = spoken[-back]["content"]
    assert state["text"].startswith("<project_state>\n") and state["text"].endswith("\n</project_state>")
    return words["text"], state["text"][len("<project_state>\n"):-len("\n</project_state>")]


def kinds(client: TestClient, project_id: str, after: int = 0) -> list[str]:
    """The kinds of a project's events, in order."""
    return [event["kind"] for event in events(client, project_id, after=after)["events"]]


def test_health_is_open_and_says_what_is_configured(world):
    client = world[0]
    assert client.get("/v1/health").json() == {
        "ok": True, "agent": False, "github": False, "epic": False, "generation": False, "supabase": True,
        "billing": False, "tiers": ["cpu", "t4"],
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
    limits = {
        "turn_budget_usd": 15.0, "turn_limit": 200,
        "own": {"turn_budget_usd": None, "turn_limit": None},
        "default": {"turn_budget_usd": 15.0, "turn_limit": 200},
        "max": {"turn_budget_usd": 100.0, "turn_limit": 1000},
    }
    assert me == {"id": ALICE.id, "email": ALICE.email, "name": "", "credits": CATALOG.signup_credits, "max_sessions": 1, "limits": limits,
                  "settings": {"video_hyperframes": False}}


def test_settings_are_the_persons_each_one_of_the_catalogs_and_on_its_default_until_changed(studio, monkeypatch):
    client, model, store = studio.client, studio.model, studio.store
    mine = lambda token="alice-token": client.get("/v1/me", headers=auth(token)).json()
    change = lambda **body: client.patch("/v1/me", headers=auth("alice-token"), json=body)
    (entry,) = CATALOG.data["settings"]
    assert entry == {
        "id": "video_hyperframes", "tab": "Video editing", "label": "Use HyperFrames for videos edited by code", "help": entry["help"],
        "kind": "toggle", "default": False,
    } and "Cut Room" in entry["help"] and len(entry["help"]) < 140
    assert (mine()["name"], mine()["settings"]) == ("", {"video_hyperframes": False}), "everyone sees it, and it is off"

    changed = change(name="  Mara   Films ", settings={"video_hyperframes": True})
    assert changed.status_code == 200 and changed.json() == mine(), "the answer is the profile"
    assert (mine()["name"], mine()["settings"]) == ("Mara Films", {"video_hyperframes": True})
    assert mine("bob-token")["settings"] == {"video_hyperframes": False} and mine("bob-token")["name"] == ""
    assert change(turn_limit=300).status_code == 200
    assert (mine()["name"], mine()["settings"], mine()["limits"]["turn_limit"]) == ("Mara Films", {"video_hyperframes": True}, 300), (
        "what a change leaves out is left as it is"
    )
    assert change(settings={}).status_code == 200 and mine()["settings"] == {"video_hyperframes": True}
    for refused in ({"settings": {"video_hyperframe": True}}, {"settings": {"video_hyperframes": "yes"}}, {"settings": {"video_hyperframes": 1}},
                    {"settings": [True]}, {"name": 7}, {"settings": {"video_hyperframes": False, "nope": True}, "name": "Other"},
                    {"settings": {"video_hyperframes": False}, "turn_limit": 0}):
        answer = change(**refused)
        assert answer.status_code == 400 and answer.json()["detail"], refused
    assert (mine()["name"], store.profiles[ALICE.id]["settings"]) == ("Mara Films", {"video_hyperframes": True}), "a refused change changes nothing"
    assert change(settings={"video_hyperframe": True}).json()["detail"] == "There is no setting video_hyperframe."
    assert change(settings={"video_hyperframes": "on"}).json()["detail"] == "video_hyperframes is true or false, or null for its default."
    assert change(settings={"video_hyperframes": None}, name=None).status_code == 200
    assert (mine()["name"], mine()["settings"], store.profiles[ALICE.id]["settings"]) == ("", {"video_hyperframes": False}, {}), (
        "null puts a setting back on its default, and the profile keeps only what the person changed"
    )
    assert len(change(name="x" * 200).json()["name"]) == 80

    # A choice is one of its options, and a value the catalog no longer offers is back on the default
    captions = {"id": "captions", "tab": "Video editing", "label": "Captions", "help": "How a video carries its words.", "kind": "choice",
                "options": [{"value": "burned", "label": "Burned in"}, {"value": "file", "label": "A file beside it"}], "default": "burned"}
    monkeypatch.setitem(CATALOG.settings, "captions", captions)
    assert mine()["settings"] == {"video_hyperframes": False, "captions": "burned"}
    assert change(settings={"captions": "file"}).status_code == 200 and mine()["settings"]["captions"] == "file"
    assert change(settings={"captions": "sung"}).json()["detail"] == "captions is burned, file, or null for its default."
    monkeypatch.setitem(CATALOG.settings, "captions", {**captions, "options": captions["options"][:1]})
    assert mine()["settings"]["captions"] == "burned" and store.profiles[ALICE.id]["settings"] == {"captions": "file"}
    monkeypatch.delitem(CATALOG.settings, "captions")
    assert mine()["settings"] == {"video_hyperframes": False}

    # A turn's state names the engine a video is edited by code in, of the engines the catalog has
    film = new_project(client)
    model.script(*[reply(say("Hello."))] * 6)

    def editor() -> str | None:
        message(client, film["id"], "Hi")
        line = next((line for line in said(model.requests[-1])[1].splitlines() if line.startswith("A video edited by code")), None)
        return line and line.removeprefix("A video edited by code is made in: ")

    assert editor() is None, "nothing is said of an engine the catalog does not have"
    monkeypatch.setitem(CATALOG.apps, "cutroom", {"id": "cutroom", "name": "Cut Room", "status": "available"})
    assert editor() == "Cut Room (app `cutroom`)"
    change(settings={"video_hyperframes": True})
    assert editor() == "Cut Room (app `cutroom`)", "switched on, but the catalog has no such engine"
    monkeypatch.setitem(CATALOG.apps, "hyperframes", {"id": "hyperframes", "name": "HyperFrames", "status": "soon"})
    assert editor() == "Cut Room (app `cutroom`)", "nor one that cannot be started yet"
    monkeypatch.setitem(CATALOG.apps, "hyperframes", {"id": "hyperframes", "name": "HyperFrames", "status": "available"})
    assert editor() == "HyperFrames (app `hyperframes`)"
    change(settings={"video_hyperframes": None})
    assert editor() == "Cut Room (app `cutroom`)", "off is the default"


def test_what_a_turn_may_spend_and_how_many_steps_it_may_take_are_the_persons_own_settings(studio):
    client, model, store = studio.client, studio.model, studio.store
    mine = lambda token="alice-token": client.get("/v1/me", headers=auth(token)).json()["limits"]
    change = lambda **limits: client.patch("/v1/me", headers=auth("alice-token"), json=limits)
    assert (mine()["turn_budget_usd"], mine()["turn_limit"], mine()["own"]) == (15.0, 200, {"turn_budget_usd": None, "turn_limit": None})

    changed = change(turn_budget_usd=40, turn_limit=350)
    assert changed.status_code == 200 and changed.json() == client.get("/v1/me", headers=auth("alice-token")).json(), "the answer is the profile"
    assert (mine()["turn_budget_usd"], mine()["turn_limit"], mine()["own"]) == (40, 350, {"turn_budget_usd": 40, "turn_limit": 350})
    assert mine()["default"] == {"turn_budget_usd": 15.0, "turn_limit": 200} and mine()["max"] == {"turn_budget_usd": 100.0, "turn_limit": 1000}
    assert mine("bob-token")["own"] == {"turn_budget_usd": None, "turn_limit": None}, "one person's limits are not another's"
    assert change(turn_limit=None).status_code == 200
    assert (mine()["turn_budget_usd"], mine()["turn_limit"], mine()["own"]) == (40, 200, {"turn_budget_usd": 40, "turn_limit": None}), (
        "null puts a limit back on the default, and a limit left out is left as it is"
    )
    assert change().status_code == 200 and mine()["own"]["turn_budget_usd"] == 40
    assert change(turn_budget_usd=0.5, turn_limit=1000.0).status_code == 200 and mine()["own"] == {"turn_budget_usd": 0.5, "turn_limit": 1000}
    for refused in ({"turn_budget_usd": 0}, {"turn_budget_usd": -3}, {"turn_budget_usd": "ten"}, {"turn_budget_usd": True}, {"turn_budget_usd": 100.01},
                    {"turn_limit": 0}, {"turn_limit": 2.5}, {"turn_limit": 1001}, {"turn_limit": [200]}):
        answer = change(**refused)
        assert answer.status_code == 400 and answer.json()["detail"], refused
    assert "at most $100" in change(turn_budget_usd=250).json()["detail"] and "at most 1000 steps" in change(turn_limit=5000).json()["detail"]
    assert mine()["own"] == {"turn_budget_usd": 0.5, "turn_limit": 1000}, "a refused change changes nothing"
    assert client.patch("/v1/me", json={"turn_limit": 5}).status_code == 401

    # A turn runs on its person's limits, and on no more than the deployment's ceiling
    film = new_project(client)
    change(turn_budget_usd=40, turn_limit=350)
    model.script(reply(say("Hello.")), reply(say("Hello.")), reply(say("Hello.")))
    message(client, film["id"], "Hi")
    assert (model.options[-1].max_budget_usd, model.options[-1].max_turns) == (40.0, 350)
    with_config(studio, turn_budget_max_usd=20.0, turn_limit_max=100, turn_budget_usd=30.0, turn_limit=500)
    assert (mine()["turn_budget_usd"], mine()["turn_limit"], mine()["own"]) == (20.0, 100, {"turn_budget_usd": 40, "turn_limit": 350}), (
        "a setting made before the ceiling came down runs at the ceiling"
    )
    assert mine("bob-token")["default"] == {"turn_budget_usd": 20.0, "turn_limit": 100} and mine("bob-token")["turn_limit"] == 100
    message(client, film["id"], "Hi")
    assert (model.options[-1].max_budget_usd, model.options[-1].max_turns) == (20.0, 100)
    store.profiles[ALICE.id].update(turn_budget_usd=None, turn_limit=None)
    with_config(studio, turn_budget_max_usd=100.0, turn_limit_max=1000, turn_budget_usd=15.0, turn_limit=200)
    message(client, film["id"], "Hi")
    assert (model.options[-1].max_budget_usd, model.options[-1].max_turns) == (15.0, 200), "an account that set none runs on the default"

    # A turn that reaches one says which and how much, and that it is the person's to change
    wrong = lambda: [e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "error"]
    change(turn_limit=2)
    model.script(reply(use("library_list")), reply(use("library_list")), reply(say("never")))
    message(client, film["id"], "Loop")
    assert wrong()[-1] == {
        "message": "This turn reached your limit of 2 steps and stopped. You can change the limit in your settings. Send a message to go on.",
        "limit": "steps",
    }
    model.steps.clear()
    change(turn_limit=None, turn_budget_usd=0.0015)
    model.script(reply(use("library_list")), reply(use("library_list")), reply(say("never")))
    message(client, film["id"], "Spend")
    assert wrong()[-1] == {
        "message": "This turn reached your spending limit of $0.0015 and stopped. You can change the limit in your settings. Send a message to go on.",
        "limit": "budget",
    }
    assert len(wrong()) == 2 and kinds(client, film["id"])[-3:] == ["error", "usage", "turn_end"]
    model.steps.clear()

    for none in ({"turn_budget_usd": 0}, {"turn_limit_max": 0}):
        with pytest.raises(ValueError, match="positive"):
            config(**none)


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
    assert post({"app": "effectcraft", "tier": "cpu"}) == 400, "an app that is announced, not offered"
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
    assert secret.startswith("moody_") and made["key"]["prefix"] == secret[:12] and "key_hash" not in made["key"]
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
    headers = {"Accept": "application/json, text/event-stream", "Host": "moody.example.test"}
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
    for key in (None, "moody_not-a-real-key"):
        refused = tool(client, "start_session", {}, key)
        assert refused["isError"] and launcher.started == []


def test_an_agent_cannot_reach_another_users_session(world):
    client = world[0]
    session = client.post("/v1/sessions", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"}).json()["session"]
    bobs_key = client.post("/v1/api-keys", headers=auth("bob-token"), json={"name": "claude"}).json()["secret"]
    for name, arguments in (("get_session_link", {}), ("run_blender_python", {"code": "print(1)"}), ("screenshot", {}), ("stop_session", {})):
        refused = tool(client, name, {"session_id": session["id"], **arguments}, bobs_key)
        assert refused["isError"] and "No such session" in refused["content"][0]["text"], name


# Moody Studio


def test_health_says_which_integrations_are_configured(studio, world):
    assert studio.client.get("/v1/health").json() == {
        "ok": True, "agent": True, "github": True, "epic": True, "generation": True, "supabase": True, "billing": False,
        "tiers": ["cpu", "t4"],
    }
    bare = world[0].get("/v1/health").json()
    assert (bare["agent"], bare["github"], bare["epic"], bare["generation"]) == (False, False, False, False)


def test_a_project_is_made_listed_read_changed_and_deleted(studio):
    client, store = studio.client, studio.store
    film = new_project(client)
    assert film["library_sections"] == ["Characters", "Environments", "Props"] and film["plan"] == []
    assert film["github_repo"] is None and film["pinned"] is False
    ad = new_project(client, name="  Spot   30 ", format="Commercials")
    assert ad["name"] == "Spot 30" and ad["library_sections"] == ["Products", "Shots"], "a kind's own sections, from the catalog"
    old = client.post("/v1/projects", headers=auth("alice-token"), json={"name": "Old", "discipline": "media", "format": "Movie"})
    assert old.status_code == 400 and "Media has no format 'Movie'" in old.json()["detail"]
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


def test_a_project_made_without_its_kind_opens_on_the_card_that_asks_it_and_locking_the_card_sets_it(studio, monkeypatch):
    client, model, store = studio.client, studio.model, studio.store
    make = lambda **body: client.post("/v1/projects", headers=auth("alice-token"), json={"name": "Reel", **body})
    made = make(discipline="media")
    assert made.status_code == 200
    reel = made.json()["project"]
    assert reel["format"] == "" and reel["library_sections"] == ["Characters", "Environments", "Props"]
    log = events(client, reel["id"])
    assert log["running"] is False and [e["kind"] for e in log["events"]] == ["ui"], "the card is the project's first event"
    assert log["events"][0]["turn_id"] is None and model.requests == [], "written with no turn and no model"
    card = log["events"][0]["data"]
    assert (card["title"], card["kind"], card["instant"], card["sets"], card["submit"], card["waits"], card["media"]) == (
        "What kind of video are you making?", "components", True, "format", None, True, [])
    pick = card["spec"]
    assert (pick["type"], pick["id"]) == ("pick", "format") and set(pick) == {"type", "id", "options"}
    assert [option["value"] for option in pick["options"]] == [
        "Film & TV", "Social Media", "Vertical Shows", "Commercials", "Music Videos", "Education", "Other"], "the kinds, in the catalog's order"
    assert all(option["label"] == option["value"] and option["note"] and len(option["note"]) < 70 for option in pick["options"])
    assert [e["kind"] for e in events(client, new_project(client)["id"])["events"]] == [], "a project made with its kind is not asked it"
    song = make(discipline="music").json()["project"]
    assert [e["kind"] for e in events(client, song["id"])["events"]] == [] and song["library_sections"] == [], (
        "nor is one of a discipline the catalog gives no opening, which starts with the sections the catalog gives it: none"
    )

    # An icon is the registry's rows where the registry has the kind's icon, and the card is checked as any other is
    tiles = lambda: studio.sessions.opening_card(CATALOG.disciplines["media"])["spec"]["options"]
    monkeypatch.setitem(CATALOG.data, "icons", {})
    assert not any("icon" in option for option in tiles())
    film_icon, social_icon = ["00111100"] * 8, ["11110000"] * 4 + ["00001111"] * 4
    monkeypatch.setitem(CATALOG.data, "icons", {"film": film_icon, "social": social_icon})
    assert [option.get("icon") for option in tiles()] == [film_icon, social_icon, None, None, None, None, None]
    monkeypatch.setitem(CATALOG.data, "icons", {"film": ["01", "10"]})
    with pytest.raises(genui.Invalid, match="pixel icon"):
        tiles()
    monkeypatch.undo()

    # The message that locks the card sets the kind, or is refused and starts nothing
    lock = lambda value: client.post(f"/v1/projects/{reel['id']}/messages", headers=auth("alice-token"),
                                     json={"text": "", "ui": {"ui_id": card["ui_id"], "value": value}})
    for refused in ({"format": "Movie"}, {"format": 3}, {}, "Social Media", None):
        answer = lock(refused)
        assert answer.status_code == 400 and "Media has no format" in answer.json()["detail"], refused
    assert store.tables["projects"][reel["id"]]["format"] == "" and kinds(client, reel["id"]) == ["ui"] and model.requests == []
    model.script(reply(say("A commercial. What does it sell?")))
    assert lock({"format": "Commercials"}).status_code == 202
    chosen = client.get(f"/v1/projects/{reel['id']}", headers=auth("alice-token")).json()["project"]
    assert chosen["format"] == "Commercials" and chosen["library_sections"] == ["Products", "Shots"], "with that kind's first sections"
    words, state = said(model.requests[-1])
    assert words == '[The person chose this project\'s kind on the card "What kind of video are you making?": Commercials]'
    assert "Kind: Commercials" in state and "Library sections: Products, Shots" in state, "the first turn already knows the kind"
    opening = next(e["data"] for e in events(client, reel["id"])["events"] if e["kind"] == "user_message")
    assert opening == {"text": "", "ui": {"ui_id": card["ui_id"], "value": {"format": "Commercials"}}}

    # A project the person wrote to first has no kind until they choose, and keeps the library they arranged
    plain = make(discipline="media").json()["project"]
    model.script(reply(say("Hello.")), reply(say("Education it is.")))
    message(client, plain["id"], "Hello")
    assert "Kind: not chosen yet" in said(model.requests[-1])[1]
    client.patch(f"/v1/projects/{plain['id']}", headers=auth("alice-token"), json={"library_sections": ["Lessons"]})
    asked = next(e["data"] for e in events(client, plain["id"])["events"] if e["kind"] == "ui")
    locked = client.post(f"/v1/projects/{plain['id']}/messages", headers=auth("alice-token"),
                         json={"text": "A lesson on tides", "ui": {"ui_id": asked["ui_id"], "value": {"format": "Education"}}})
    assert locked.status_code == 202
    words, state = said(model.requests[-1])
    assert words.startswith("A lesson on tides\n\n[The person chose this project's kind") and "Kind: Education" in state
    assert "Library sections: Lessons" in state
    assert "opening card" not in model.requests[-1]["system"][0]["text"], "this project has no skill that holds its kinds' cards"
    monkeypatch.setitem(CATALOG.disciplines["media"], "opening_skill", "filmcraft")
    model.script(reply(say("Hello.")))
    message(client, plain["id"], "And now?")
    assert "open the `filmcraft` skill and show that kind's opening card" in " ".join(model.requests[-1]["system"][0]["text"].split()), (
        "a turn's prompt names the skill where the project is offered it"
    )


def test_every_discipline_that_asks_its_kind_has_a_card_the_page_renders_and_a_line_for_each_kind():
    asking = [discipline for discipline in CATALOG.disciplines.values() if discipline.get("opening")]
    assert [discipline["id"] for discipline in asking] == ["media"]
    sessions = Sessions(config(), CATALOG, FakeStore(), FakeLauncher(), InlineJobs())
    for discipline in asking:
        card = sessions.opening_card(discipline)
        assert len(card["title"]) <= genui.catalog().limits["title_chars"] and card["spec"]["options"]
        assert set(discipline["kinds"]) == set(discipline["formats"]), "every kind has its line and its icon's name"
        assert all(kind.get("note") and kind.get("icon") for kind in discipline["kinds"].values())
    assert sessions.opening_card(CATALOG.disciplines["music"]) is None


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
                       json={"app": "effectcraft", "tier": "cpu"}).status_code == 400, "an engine that is announced, not offered"
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
    words, state = said(studio.model.requests[0])
    assert words == "Go on" and len(studio.model.requests[0]["messages"]) == 1
    assert "The person: Write me a film" in state, "the model is told what the person said in a turn stopped before it began"


def test_stopping_a_turn_interrupts_the_loop_and_ends_what_it_left_open(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    stop = lambda: client.post(f"/v1/projects/{film['id']}/stop", headers=auth("alice-token")).json()

    def stopped_meanwhile(request: dict[str, Any]) -> Reply:
        assert stop() == {"stopped": True}
        return reply(say("Listing the library."), use("library_list"), use("library_upsert", section="Props", name="Lamp"))

    model.script(stopped_meanwhile, reply(say("This is never asked for.")))
    assert message(client, film["id"], "Look around").status_code == 202
    log = events(client, film["id"])
    assert log["running"] is False and len(model.requests) == 1, "the loop was interrupted before it asked the model again"
    assert [e["kind"] for e in log["events"]] == ["user_message", "text", "tool_start", "tool_end", "usage", "turn_end"]
    ends = [e["data"] for e in log["events"] if e["kind"] == "tool_end"]
    assert [(end["ok"], end["summary"]) for end in ends] == [(False, "Stopped")], "no tool ran once the turn was stopped, and the next was never begun"
    assert client.get(f"/v1/projects/{film['id']}/library", headers=auth("alice-token")).json()["assets"] == []
    assert not any(e["kind"] == "error" for e in log["events"]), "a turn the person stopped is not a failure"


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


def test_the_agent_works_through_its_tools_and_its_conversation_is_one_session_in_the_database(studio):
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
        "thinking", "tool_start", "library", "tool_end",
        "tool_start", "tool_end",
        "tool_start", "library", "tool_end",
        "tool_start", "plan", "tool_end",
        "text", "usage", "turn_end",
    ]
    texts = [(e["kind"], e["data"]["text"]) for e in log["events"] if e["kind"] in ("text", "thinking")]
    assert texts == [("text", "I'll set up the library."), ("thinking", "Making her look."),
                     ("text", "Mara is in the library, and the first shot is ready.")], "an empty block is not shown"
    assert all(e["data"]["block"] and "partial" not in e["data"] for e in log["events"] if e["kind"] in ("text", "thinking"))
    ends = [e["data"] for e in log["events"] if e["kind"] == "tool_end"]
    assert all(end["ok"] for end in ends), ends
    assert ends[2]["summary"] == "2 images saved to @mara, about $0.30" and len(ends[2]["media"]) == 2
    assert ends[3]["summary"] == "1 image, about $0.15", "an image not saved anywhere"
    assert ends[4]["summary"] == "1 video saved to @s01-sh01-t1, about $2.84"

    # Every file the conversation shows is kept by where it is and signed for each reading of the log
    signed = "https://storage.example.test/"
    assert all(set(item) == {"kind", "url"} and item["url"].startswith(signed) for end in ends[2:5] for item in end["media"])
    entries = [e["data"]["asset"] for e in log["events"] if e["kind"] == "library" and "asset" in e["data"]]
    assert [len(entry["media"]) for entry in entries] == [0, 2, 1], "an entry as each event left it"
    assert all(set(item) == {"kind", "url", "name"} and item["url"].startswith(signed) for entry in entries for item in entry["media"])
    assert entries[1]["thumbnail_url"] == entries[1]["media"][0]["url"] and entries[0]["thumbnail_url"] is None
    kept = [row["data"] for row in store.tables["project_events"].values() if row["kind"] in ("tool_end", "library")]
    files = [item for data in kept for item in [*data.get("media", []), *data.get("asset", {}).get("media", [])]]
    assert len(files) == 7 and all("url" not in item and item["path"] in store.files for item in files), (
        "the log keeps where a file is, never a link that expires"
    )
    assert "token=signed" not in json.dumps([row["data"] for row in store.tables["project_events"].values()])
    unsaved = next(path for path in store.files if "/generations/" in path)
    held = store.files.pop(unsaved)
    again = [e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "tool_end"]
    assert again[3]["media"] == [] and len(again[2]["media"]) == 2, "a result whose file is gone is left out"
    store.files[unsaved] = held
    starts = [e["data"] for e in log["events"] if e["kind"] == "tool_start"]
    assert starts[0] == {"call_id": starts[0]["call_id"], "tool": "set_library_sections", "title": "Arranging the library", "activity": "processing"}
    assert starts[2]["title"] == "Generating 2 images" and starts[2]["activity"] == "creating"
    assert [start["call_id"] for start in starts] == [end["call_id"] for end in ends], "each call's end follows its own start"
    usage = next(e["data"] for e in log["events"] if e["kind"] == "usage")
    assert usage == {"input_tokens": 600, "output_tokens": 120, "cost_usd": 0.006, "seconds": usage["seconds"], "agents": 0}

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

    # The loop is given Moody's prompt and tools, and none of its own file or shell tools
    requests = model.requests
    assert len(requests) == 6
    prompt = requests[0]["system"][0]["text"]
    assert "Discipline: Media" in prompt and "Its kinds: Film & TV, Social Media, Vertical Shows" in prompt and f"projects/{film['id']}" in prompt
    assert "Kind: Film & TV" in said(requests[0])[1], "which kind the project is, is its state: it can be chosen after the project is made"
    assert "SKILL-TEXT" not in prompt, "no skill's text is in the prompt: the loop loads one when the work calls for it"
    assert all(r["system"] == requests[0]["system"] for r in requests)
    assert requests[0]["tools"] == ["Agent", "WebSearch", "WebFetch", "Skill", "Read", *(f"{PREFIX}{name}" for name in TOOL_NAMES)]
    words, state = said(requests[0])
    assert words == "Make a film about Mara" and "Library sections: Characters, Environments, Props" in state
    assert "What was said in this project before" not in state, "a project's first turn has nothing before it"

    # The conversation is the loop's session, kept in the database as it is written
    session = store.tables["projects"][film["id"]]["agent_session"]
    options = model.options[0]
    assert (options.session_id, options.resume) == (session, None) and uuid.UUID(session)
    rows = [row for row in store.tables["agent_transcripts"].values() if row["project_id"] == film["id"]]
    assert {row["session_id"] for row in rows} == {session} and {row["subpath"] for row in rows} == {""}
    assert [row["entry"]["message"]["role"] for row in rows] == ["user"] + ["assistant", "user"] * 5 + ["assistant"]

    # The next turn resumes it, from the database alone, with the project's state as it is now
    model.script(reply(say("Shot two next.")))
    message(client, film["id"], "Great, next shot")
    assert (model.options[1].session_id, model.options[1].resume) == (None, session)
    later = model.requests[-1]["messages"]
    assert later[:-1] == [row["entry"]["message"] for row in rows], "the model is sent the conversation as the database kept it"
    words, state = said(model.requests[-1])
    assert words == "Great, next shot"
    assert "- [done] Bible (id bible)" in state and "- @mara: Mara (Characters; 2 image)" in state
    assert "- @s01-sh01-t1: S01 SH01 T1 (Shots; 1 video)" in state and "Library sections: Characters, Shots" in state
    assert "What was said in this project before" not in state, "a resumed session remembers; it is told nothing twice"


def test_ask_user_ends_the_turn_and_the_answer_starts_the_next_on_the_same_session(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    question = use("ask_user", question="Do you have a script, or shall we write one?", options=["I have one", "Let's write one"],
                   recommended="Let's write one")
    model.script(reply(say("Let's begin."), use("library_list"), question), reply(say("This is never asked for.")))
    message(client, film["id"], "Hi")
    log = events(client, film["id"])
    assert [e["kind"] for e in log["events"]] == [
        "user_message", "text", "tool_start", "tool_end", "tool_start", "ask", "tool_end", "usage", "turn_end"]
    asked = next(e["data"] for e in log["events"] if e["kind"] == "ask")
    assert asked == {"question": "Do you have a script, or shall we write one?", "options": ["I have one", "Let's write one"],
                     "recommended": "Let's write one"}, "the question carries the answer the agent would give"
    assert log["running"] is False and len(model.requests) == 1, "the turn ended at the question: no machine waits for the person"

    model.steps.clear()
    model.script(reply(say("Then let's write it together.")))
    message(client, film["id"], "Let's write one")
    assert model.options[1].resume == model.options[0].session_id
    request = model.requests[-1]["messages"]
    assert request[1]["content"][-1] == question and "The question is with the person now" in tool_results({"messages": request[:3]})[question["id"]]["content"]
    assert said(model.requests[-1])[0] == "Let's write one", "the answer is the next turn's message"


def test_one_question_ends_a_turn_and_a_second_in_it_is_refused(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    first = use("ask_user", question="Color or black and white?", options=["Color", "Black and white"], recommended="Color")
    second = use("ask_user", question="How long?", options=["Short", "Feature"], recommended="Short")
    turn = SimpleNamespace(asked=False, event=lambda kind, data: None)
    assert studio.agent.tool_ask_user(turn, **first["input"]).ends_turn
    with pytest.raises(Refused, match="one question at a time"):
        studio.agent.tool_ask_user(turn, **second["input"])
    assert Result("x", "y").ends_turn is False, "a tool's result ends the turn only where it says so"

    model.script(reply(first))
    message(client, film["id"], "Hi")
    assert kinds(client, film["id"]).count("ask") == 1


def test_a_question_may_name_the_option_the_agent_would_choose_and_one_named_wrongly_is_sent_back(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    other = use("ask_user", question="Color or black and white?", options=["Color", "Black and white"], recommended="Sepia")
    marked = use("ask_user", question="Color or black and white?", options=["Color (Recommended for a comedy)", "Black and white"],
                 recommended="Color (Recommended for a comedy)")
    spaced = use("ask_user", question="Color or black and white?", options=["Color", "Black and white"], recommended=" Black and white ")
    model.script(reply(other), reply(marked), reply(spaced))
    message(client, film["id"], "Hi")
    told = [next(iter(tool_results(request).values())) for request in model.requests[1:]]
    assert all(result["is_error"] for result in told) and len(model.requests) == 3, "each is answered, and the turn goes on"
    assert "recommended has to be one of the options, written exactly as it is there: Color / Black and white" in told[0]["content"]
    assert "An option's text is only the option" in told[1]["content"] and "name that option in recommended" in told[1]["content"]
    log = events(client, film["id"])["events"]
    assert [e["data"] for e in log if e["kind"] == "ask"] == [
        {"question": "Color or black and white?", "options": ["Color", "Black and white"], "recommended": "Black and white"}
    ], "one question reached the person, its recommendation as the option is written"
    assert [e["kind"] for e in log][-3:] == ["tool_end", "usage", "turn_end"]

    # A question the agent has no preference on names none, and reaches the person as it is
    model.steps.clear()
    model.script(reply(use("ask_user", question="What is the story?", options=["I have a script", "I have an idea"])))
    message(client, film["id"], "Black and white")
    asked = [e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "ask"]
    assert asked[-1] == {"question": "What is the story?", "options": ["I have a script", "I have an idea"]}


def test_a_tool_input_that_fails_its_schema_is_answered_not_run(studio):
    client, model, fal = studio.client, studio.model, studio.fal
    film = new_project(client)
    bad = use("generate_image", prompt="A lighthouse", count="two")
    cut = use("library_upsert", section="Characters")
    model.script(reply(bad), reply(cut), reply(use("nonsense")), reply(say("Sorry.")))
    message(client, film["id"], "Make a picture")
    assert fal.calls == []
    first, second, third = (tool_results(r) for r in model.requests[1:])
    assert first[bad["id"]]["is_error"] and "Input validation error" in first[bad["id"]]["content"] and "'two'" in first[bad["id"]]["content"]
    assert second[cut["id"]]["is_error"] and "'name' is a required property" in second[cut["id"]]["content"]
    assert third and all(result["is_error"] for result in third.values())
    log = events(client, film["id"])["events"]
    assert [e["kind"] for e in log] == ["user_message", "tool_start", "tool_end", "tool_start", "tool_end", "text", "usage", "turn_end"]
    ends = [e["data"] for e in log if e["kind"] == "tool_end"]
    assert not any(end["ok"] for end in ends) and "Input validation error" in ends[0]["summary"], "the page sees the call fail"
    assert client.get(f"/v1/projects/{film['id']}/library", headers=auth("alice-token")).json()["assets"] == []


def test_a_turn_the_model_could_not_finish_ends_with_an_error_the_person_can_read(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    told = lambda: [e["data"]["message"] for e in events(client, film["id"])["events"] if e["kind"] == "error"]
    model.script(reply(say("I can't help with that."), stop="refusal"))
    message(client, film["id"], "Something")
    assert kinds(client, film["id"])[-3:] == ["error", "usage", "turn_end"] and "declined" in told()[-1]
    model.script(Reply(content=[], error="rate_limit"))
    message(client, film["id"], "Again")
    assert told()[-1] == "The model is busy right now. Try again in a minute."
    assert not any("API Error" in e["data"].get("text", "") for e in events(client, film["id"])["events"]), "the loop's own words for a failure are not the agent's"
    model.script(Reply(content=[], error="server_error"))
    message(client, film["id"], "Again")
    assert told()[-1] == "The model could not be reached. Try again."

    # A loop that breaks is told too, and none of these names a limit of the person's
    assert not any("limit" in e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "error")
    model.may_run_dry = True
    message(client, film["id"], "The script is empty, which breaks the loop")
    assert told()[-1] == "Something went wrong on our side, and this turn stopped."
    assert kinds(client, film["id"])[-3:] == ["usage", "error", "turn_end"] and events(client, film["id"])["running"] is False


def test_the_engine_tools_act_in_the_projects_own_running_engine(studio):
    client, model, launcher, store = studio.client, studio.model, studio.launcher, studio.store
    store.moody_ensure_profile(ALICE.id, ALICE.email, 60)["max_sessions"] = 3
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
    assert launcher.calls == [("sb-2", "filmcraft", "engine.execute", {"command": "file.save", "params": {}})]
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


def start_engine(studio: SimpleNamespace, project_id: str, app: str = "filmcraft", token: str = "alice-token", runs: str | None = None) -> dict[str, Any]:
    """Start an engine of a project; `runs` makes it one of an app that is not on offer yet, by its row."""
    response = studio.client.post(f"/v1/projects/{project_id}/engines", headers=auth(token), json={"app": app, "tier": "cpu"})
    assert response.status_code == 200, response.text
    engine = response.json()["engine"]
    if runs:
        studio.store.sessions[engine["id"]]["app"] = runs
    return engine


def tools_shown(client: TestClient, project_id: str) -> list[tuple[str, str, bool]]:
    """Each call the page was shown, in order: its title, its summary, and whether it worked."""
    shown = events(client, project_id)["events"]
    ends = {event["data"]["call_id"]: event["data"] for event in shown if event["kind"] == "tool_end"}
    return [
        (event["data"]["title"], ends[event["data"]["call_id"]]["summary"], ends[event["data"]["call_id"]]["ok"])
        for event in shown
        if event["kind"] == "tool_start"
    ]


def test_engine_call_reaches_the_command_channel_of_whichever_app_an_engine_runs(studio):
    client, model, launcher, store = studio.client, studio.model, studio.launcher, studio.store
    for user in (ALICE, BOB):
        store.moody_ensure_profile(user.id, user.email, 60)["max_sessions"] = 5
    launcher.channels = {"filmcraft", "soundcraft", "cadcraft"}
    film = new_project(client)
    cut = start_engine(studio, film["id"])
    score = start_engine(studio, film["id"], runs="soundcraft")
    plan = start_engine(studio, film["id"], runs="cadcraft")
    scene = start_engine(studio, film["id"], app="blender")
    bobs = start_engine(studio, new_project(client, "bob-token")["id"], token="bob-token")
    model.script(
        reply(
            use("engine_call", engine_id=cut["id"], method="timeline.place", params={"clip": "a"}),
            use("engine_call", engine_id=score["id"], method="transport.play"),
            use("engine_call", engine_id=plan["id"], method="document.export", params={"format": "step"}),
            use("engine_call", engine_id=scene["id"], method="scene.save"),
            use("engine_call", engine_id=bobs["id"], method="timeline.place"),
            use("filmcraft", engine_id=score["id"], method="timeline.place"),
            use("engine_list"),
        ),
        reply(say("Done.")),
    )
    message(client, film["id"], "Play it")

    assert launcher.calls == [
        ("sb-1", "filmcraft", "timeline.place", {"clip": "a"}),
        ("sb-2", "soundcraft", "transport.play", None),
        ("sb-3", "cadcraft", "document.export", {"format": "step"}),
    ], "each call went to its engine's own app, and none to the engine without a channel or to another user's"
    results = list(tool_results(model.requests[1]).values())
    assert [r.get("is_error", False) for r in results] == [False, False, False, True, True, True, False]
    assert json.loads(results[1]["content"]) == {"ok": True, "app": "soundcraft", "method": "transport.play"}
    assert "This engine has no command channel" in results[3]["content"] and "engine_exec" in results[3]["content"]
    assert "No such" in results[4]["content"]
    assert results[5]["content"] == "That engine is not FilmCraft."
    listed = {engine["id"]: engine["command_channel"] for engine in json.loads(results[6]["content"])}
    assert listed == {cut["id"]: True, score["id"]: True, plan["id"]: True, scene["id"]: False}
    assert tools_shown(client, film["id"])[:6] == [
        ("FilmCraft: timeline.place", "FilmCraft: timeline.place done", True),
        ("SoundCraft: transport.play", "SoundCraft: transport.play done", True),
        ("CADCraft: document.export", "CADCraft: document.export done", True),
        ("Blender: scene.save", results[3]["content"], False),
        ("Engine: timeline.place", results[4]["content"], False),
        ("FilmCraft: timeline.place", "That engine is not FilmCraft.", False),
    ]


def test_engine_files_lists_the_project_folder_as_an_engine_sees_it(studio):
    client, model, launcher = studio.client, studio.model, studio.launcher
    film = new_project(client)
    engine = start_engine(studio, film["id"])
    folder = f"/home/ubuntu/workspace/projects/{film['id']}"
    launcher.answers += [
        ("./handoff/missing", (44, "")),
        ("find", (0, "f\t2048\t1795582875.75\tplan v2.glb\nd\t4096\t1795582800.0\ttextures\nf\t17\t1795582000.0\tNOTES.md\nnot an entry\n")),
    ]
    model.script(
        reply(
            use("engine_files", engine_id=engine["id"], path="handoff/cadcraft-to-blender"),
            use("engine_files", engine_id=engine["id"]),
            use("engine_files", engine_id=engine["id"], path=f"{folder}/handoff/cadcraft-to-blender/"),
            use("engine_files", engine_id=engine["id"], path="handoff/missing"),
            use("engine_files", engine_id=engine["id"], path="../another-project"),
            use("engine_files", engine_id=engine["id"], path="/etc"),
        ),
        reply(say("It is there.")),
    )
    message(client, film["id"], "Is the plan there?")

    results = list(tool_results(model.requests[1]).values())
    assert [r.get("is_error", False) for r in results] == [False, False, False, True, True, True]
    assert json.loads(results[0]["content"]) == {
        "folder": folder,
        "path": "handoff/cadcraft-to-blender",
        "entries": [
            {"name": "NOTES.md", "kind": "file", "size": 17, "modified": "2026-11-25T04:46:40+00:00"},
            {"name": "plan v2.glb", "kind": "file", "size": 2048, "modified": "2026-11-25T05:01:15+00:00"},
            {"name": "textures", "kind": "folder", "modified": "2026-11-25T05:00:00+00:00"},
        ],
    }
    assert json.loads(results[1]["content"])["path"] == "" and json.loads(results[2]["content"])["path"] == "handoff/cadcraft-to-blender"
    assert "There is no handoff/missing" in results[3]["content"]
    assert "outside the project's folder" in results[4]["content"] and "outside the project's folder" in results[5]["content"]
    commands = [command for _, command in launcher.commands]
    assert len(commands) == 4, "a path outside the folder never reaches the machine"
    assert all(command.startswith(f"cd {folder} ") for command in commands)
    assert "find ./handoff/cadcraft-to-blender -mindepth 1 -maxdepth 1" in commands[0] and "find ./ -mindepth 1" in commands[1]
    assert tools_shown(client, film["id"])[0] == ("Listing handoff/cadcraft-to-blender", "3 entries in handoff/cadcraft-to-blender", True)


# How a probe's ffprobe line ends, after the path of the file it reads
PROBED = " 2>/dev/null || true"
MB = 1024 * 1024
PNG = {"streams": [{"codec_type": "video", "codec_name": "png", "width": 1920, "height": 1080}], "format": {"format_name": "png_pipe"}}
WAV = {
    "streams": [{"codec_type": "audio", "codec_name": "pcm_s24le", "sample_rate": "48000", "channels": 2}],
    "format": {"format_name": "wav", "duration": "5.000000"},
}
H264 = {
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 1280, "height": 720},
        {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
    ],
    "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "12.480000"},
}
PRORES = {
    "streams": [{"codec_type": "video", "codec_name": "prores", "pix_fmt": "yuv422p10le", "width": 3840, "height": 2160}],
    "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "2.000000"},
}


def probe(path: str, size: int, answer: dict[str, Any] | None) -> tuple[str, tuple[int, str]]:
    """What an engine answers a preview's probe of a file: its size, and ffprobe's words or that it has no ffmpeg."""
    return f"{shlex.quote('./' + path)}{PROBED}", (0, f"{size}\n{'NO-FFMPEG' if answer is None else json.dumps(answer)}\n")


def previews(client: TestClient, project_id: str) -> list[dict[str, Any]]:
    """The previews the page was shown, in order."""
    return [event["data"] for event in events(client, project_id)["events"] if event["kind"] == "preview"]


def stored_previews(studio: SimpleNamespace, project_id: str) -> dict[str, tuple[bytes, str]]:
    """The files the bucket holds under the project's previews folder, by their names without the random start."""
    prefix = f"{ALICE.id}/{project_id}/previews/"
    return {path[len(prefix) + 13 :]: kept for path, kept in studio.store.files.items() if path.startswith(prefix)}


def with_config(studio: SimpleNamespace, **changes: Any) -> None:
    studio.sessions.config = replace(studio.sessions.config, **changes)


def test_a_preview_shows_each_kind_of_file_as_a_card_and_tells_the_model_only_its_facts(studio):
    client, model, launcher = studio.client, studio.model, studio.launcher
    film = new_project(client)
    eid = start_engine(studio, film["id"])["id"]
    folder = f"/home/ubuntu/workspace/projects/{film['id']}"
    launcher.answers += [
        probe("previews/frame.png", 240_000, PNG),
        probe("previews/chorus.wav", 1_440_078, WAV),
        probe("previews/cut.mp4", 3 * MB, H264),
        probe("previews/plan.pdf", 88_000, {"streams": [{"codec_type": "video", "codec_name": "ansi"}]}),
        ("ebur128", (1, "    I:         -14.2 LUFS\n    Peak:       -1.1 dBFS\n")),
    ]
    model.script(
        reply(
            use("preview", engine_id=eid, path="previews/frame.png", caption="Shot 3 after the grade"),
            use("preview", engine_id=eid, path="previews/chorus.wav", caption="The chorus with the new bass"),
            use("preview", engine_id=eid, path=f"{folder}/previews/cut.mp4", caption="The first twelve seconds of the cut"),
            use("preview", engine_id=eid, paths=["previews/plan.pdf", "previews/frame.png"], caption="The plan and the frame it is for"),
        ),
        reply(say("Shown.")),
    )
    message(client, film["id"], "Show me where it is")

    results = list(tool_results(model.requests[1]).values())
    assert not any(r.get("is_error") for r in results), results
    assert all(isinstance(r["content"], str) for r in results), "the model is given no pixels and no sound unless it asks to look"
    frame, chorus, cut, pair = (json.loads(r["content"]) for r in results)
    assert frame["shown"] == "Shot 3 after the grade" and "look: true" in frame["note"]
    assert frame["files"] == [{"path": "previews/frame.png", "kind": "image", "size": "234 KB", "width": 1920, "height": 1080, "codec": "png"}]
    assert chorus["files"] == [{
        "path": "previews/chorus.wav", "kind": "audio", "size": "1.4 MB", "seconds": 5.0, "codec": "pcm_s24le",
        "sample_rate": 48000, "channels": 2, "loudness_lufs": -14.2, "true_peak_dbfs": -1.1,
    }]
    assert cut["files"][0]["seconds"] == 12.48 and cut["files"][0]["width"] == 1280 and "shown_as" not in cut["files"][0]
    assert [f["kind"] for f in pair["files"]] == ["file", "image"], "a PDF is a file whatever ffprobe makes of it"

    shown = previews(client, film["id"])
    link = f"https://storage.example.test/{ALICE.id}/{film['id']}/previews/"
    assert [(p["caption"], p["engine_id"], p["compare"]) for p in shown] == [
        ("Shot 3 after the grade", eid, False), ("The chorus with the new bass", eid, False),
        ("The first twelve seconds of the cut", eid, False), ("The plan and the frame it is for", eid, False),
    ]
    items = [item for p in shown for item in p["items"]]
    assert all(item["url"].startswith(link) and "path" not in item for item in items)
    assert [{k: v for k, v in item.items() if k != "url"} for item in items] == [
        {"kind": "image", "name": "frame.png", "width": 1920, "height": 1080},
        {"kind": "audio", "name": "chorus.wav", "seconds": 5.0},
        {"kind": "video", "name": "cut.mp4", "seconds": 12.48, "width": 1280, "height": 720},
        {"kind": "file", "name": "plan.pdf"},
        {"kind": "image", "name": "frame.png", "width": 1920, "height": 1080},
    ]
    kept = stored_previews(studio, film["id"])
    assert {name: kind for name, (_, kind) in kept.items()} == {
        "frame.png": "image/png", "chorus.wav": "audio/x-wav", "cut.mp4": "video/mp4", "plan.pdf": "application/pdf",
    }
    assert kept["cut.mp4"][0] == b"bytes of cut.mp4" and (launcher.reads[2] == ("sb-1", f"{folder}/previews/cut.mp4"))
    commands = [command for _, command in launcher.commands]
    assert not any(" -c:v " in command or " -c:a " in command for command in commands), "light files browsers play are shown as they are"
    assert client.get(f"/v1/projects/{film['id']}/library", headers=auth("alice-token")).json()["assets"] == []
    assert not studio.store.tables["assets"], "a preview is never a library entry"
    kinds = [event["kind"] for event in events(client, film["id"])["events"]]
    assert kinds[1:4] == ["tool_start", "preview", "tool_end"] and "library" not in kinds
    assert tools_shown(client, film["id"])[1] == ("Preparing a preview", "Showed 1 audio: The chorus with the new bass", True)
    assert tools_shown(client, film["id"])[3][1] == "Showed 1 file, 1 image: The plan and the frame it is for"


def test_a_before_and_after_pair_is_two_files_of_one_kind(studio):
    client, model, launcher = studio.client, studio.model, studio.launcher
    film = new_project(client)
    eid = start_engine(studio, film["id"])["id"]
    launcher.answers += [probe(f"previews/{name}", 200_000, answer) for name, answer in (("before.png", PNG), ("after.png", PNG), ("mix.wav", WAV))]
    model.script(
        reply(
            use("preview", engine_id=eid, paths=["previews/before.png", "previews/after.png"], caption="The sky, before and after the grade", compare=True),
            use("preview", engine_id=eid, path="previews/after.png", caption="Only one", compare=True),
            use("preview", engine_id=eid, paths=["previews/before.png", "previews/mix.wav"], caption="Two kinds", compare=True),
            use("preview", engine_id=eid, caption="Nothing named"),
            use("preview", engine_id=eid, paths=["previews/after.png"] * 13, caption="Too many"),
        ),
        reply(say("Shown.")),
    )
    message(client, film["id"], "Compare them")

    results = list(tool_results(model.requests[1]).values())
    assert [r.get("is_error", False) for r in results] == [False, True, True, True, True]
    assert "exactly two files" in results[1]["content"] and "of one kind" in results[2]["content"]
    assert "Name the file" in results[3]["content"] and "at most 12 files" in results[4]["content"]
    (pair,) = previews(client, film["id"])
    assert pair["compare"] is True and [item["name"] for item in pair["items"]] == ["before.png", "after.png"]
    assert len(stored_previews(studio, film["id"])) == 2, "a refused preview stores nothing"
    assert tools_shown(client, film["id"])[0][1] == "Showed 2 images as before and after: The sky, before and after the grade"


def test_a_heavy_file_is_shown_as_a_lighter_copy_the_engine_encodes_and_the_original_is_left_alone(studio):
    client, model, launcher = studio.client, studio.model, studio.launcher
    film = new_project(client)
    eid = start_engine(studio, film["id"])["id"]
    folder = f"/home/ubuntu/workspace/projects/{film['id']}"
    launcher.answers += [
        probe("bounces/full mix.wav", 310 * MB, WAV),
        probe("exports/shot 3.mov", 5 * MB, PRORES),
        probe("renders/hero.exr", 60 * MB, {"streams": [{"codec_type": "video", "codec_name": "exr", "width": 4096, "height": 2160}]}),
        probe("renders/broken.mov", 5 * MB, PRORES | {"format": {"duration": "9"}}),
        ("-c:a aac -b:a 160k", (0, "6200000\n")),
        ("ebur128", (1, "    I:         -9.8 LUFS\n    Peak:       0.3 dBFS\n")),
        ("broken.mov -vf", (1, "Invalid data found when processing input\n")),
        ("-c:v libx264", (0, "480000\n")),
        ("-c:v libwebp", (0, "350000\n")),
    ]
    model.script(
        reply(
            use("preview", engine_id=eid, path="bounces/full mix.wav", caption="The whole track, mastered"),
            use("preview", engine_id=eid, path="exports/shot 3.mov", caption="The dissolve into shot 3"),
            use("preview", engine_id=eid, path="renders/hero.exr", caption="The hero render"),
            use("preview", engine_id=eid, path="renders/broken.mov", caption="A file ffmpeg cannot read"),
        ),
        reply(say("Shown.")),
    )
    message(client, film["id"], "Play me the master")

    results = list(tool_results(model.requests[1]).values())
    assert [r.get("is_error", False) for r in results] == [False, False, False, True]
    mix, shot, hero = (json.loads(r["content"])["files"][0] for r in results[:3])
    assert mix["size"] == "310.0 MB" and mix["shown_as"] == "an AAC copy of 5.9 MB; the original is untouched"
    assert mix["loudness_lufs"] == -9.8 and mix["true_peak_dbfs"] == 0.3, "measured on the original, not the copy"
    assert shot["codec"] == "prores" and "H.264 copy of 469 KB" in shot["shown_as"], "light, but no browser plays ProRes"
    assert "WebP copy" in hero["shown_as"]
    assert "ffmpeg could not encode a preview copy of renders/broken.mov: Invalid data" in results[3]["content"]
    kept = stored_previews(studio, film["id"])
    assert {name: kind for name, (_, kind) in kept.items()} == {"full-mix.m4a": "audio/mp4", "shot-3.mp4": "video/mp4", "hero.webp": "image/webp"}
    assert [item["name"] for p in previews(client, film["id"]) for item in p["items"]] == ["full mix.wav", "shot 3.mov", "hero.exr"]
    commands = [command for sandbox, command in launcher.commands if sandbox == "sb-1"]
    encodes = [command for command in commands if " -c:v " in command or " -c:a " in command]
    assert len(encodes) == 4 and all(command.startswith(f"cd {folder} && mkdir -p /tmp/moody-preview/") for command in encodes)
    assert "-i './bounces/full mix.wav' -vn -c:a aac" in encodes[0] and ".m4a 2>&1 && stat -c %s /tmp/moody-preview/" in encodes[0]
    assert "scale=trunc(min(1280\\,iw)/2)*2:-2" in encodes[1] and "-pix_fmt yuv420p" in encodes[1]
    scratch = [path for _, path in launcher.reads]
    assert all(path.startswith("/tmp/moody-preview/") for path in scratch), "the copy is what is read, from outside the project's folder"
    removed = [command for command in commands if command.startswith("rm -rf /tmp/moody-preview/")]
    assert len(removed) == 4, "the copies are removed from the engine whether the preview was shown or refused"
    assert not any(command.startswith("rm") and folder in command for command in commands)


def test_a_preview_over_the_limit_is_refused_with_what_to_render_instead(studio):
    client, model, launcher = studio.client, studio.model, studio.launcher
    with_config(studio, preview_limit_bytes=20 * MB, preview_original_bytes=4 * MB)
    film = new_project(client)
    eid = start_engine(studio, film["id"])["id"]
    launcher.answers += [
        probe("exports/film.mp4", 900 * MB, H264),
        probe("exports/trailer.mp4", 6 * MB, H264),
        probe("handoff/scene.blend", 64 * MB, {}),
        ("film.mp4 -vf", (0, f"{31 * MB}\n")),
        ("trailer.mp4 -vf", (0, f"{2 * MB}\n")),
    ]
    model.script(
        reply(
            use("preview", engine_id=eid, path="exports/film.mp4", caption="The whole film"),
            use("preview", engine_id=eid, path="handoff/scene.blend", caption="The scene file"),
            use("preview", engine_id=eid, paths=["exports/trailer.mp4", "exports/film.mp4"], caption="The trailer and the film"),
            use("preview", engine_id=eid, path="exports/trailer.mp4", caption="The trailer"),
        ),
        reply(say("The film is too long to show whole.")),
    )
    message(client, film["id"], "Show me the film")

    results = list(tool_results(model.requests[1]).values())
    assert [r.get("is_error", False) for r in results] == [True, True, True, False]
    assert results[0]["content"] == (
        "exports/film.mp4 is 31.0 MB as a preview, over the 20.0 MB a preview may be. Render or export something lighter "
        "and preview that: a shorter range, a lower resolution, or a lower bitrate. The file itself stays where it is."
    )
    assert "handoff/scene.blend is 64.0 MB as a preview" in results[1]["content"]
    (trailer,) = previews(client, film["id"])
    assert trailer["caption"] == "The trailer", "a preview with one file refused shows none of its files"
    assert list(stored_previews(studio, film["id"])) == ["trailer.mp4"]
    assert "copy of 2.0 MB" in json.loads(results[3]["content"])["files"][0]["shown_as"], "over what is shown as it is, under the limit"


def test_look_hands_the_model_a_small_picture_of_what_it_previews(studio):
    client, model, launcher = studio.client, studio.model, studio.launcher
    film = new_project(client)
    eid = start_engine(studio, film["id"])["id"]
    launcher.answers += [
        probe("previews/frame.png", 240_000, PNG), probe("previews/cut.mp4", 3 * MB, H264), probe("previews/chorus.wav", 900_000, WAV),
        probe("notes/plan.md", 900, {}),
    ]
    model.script(
        reply(
            use("preview", engine_id=eid, paths=["previews/frame.png", "previews/cut.mp4", "previews/chorus.wav"], caption="Where the scene is", look=True),
            use("preview", engine_id=eid, path="notes/plan.md", caption="The plan", look=True),
        ),
        reply(say("The frame is too dark.")),
    )
    message(client, film["id"], "Is it right?")

    looked, plain = tool_results(model.requests[1]).values()
    assert [block["type"] for block in looked["content"]] == ["image", "image", "image", "text"]
    assert [base64.b64decode(block["source"]["data"]) for block in looked["content"][:3]] == [b"bytes of 0-look.jpg", b"bytes of 1-look.jpg", b"bytes of 2-look.jpg"]
    assert "yours to judge by" in json.loads(looked["content"][3]["text"])["note"]
    looks = [command for _, command in launcher.commands if "-look.jpg" in command]
    assert "scale=min(1280\\,iw):-2" in looks[0] and "fps=4/12.480,scale=640:-2,tile=2x2" in looks[1] and "showwavespic" in looks[2]
    assert isinstance(plain["content"], str) and "not an image, a video, or a sound" in json.loads(plain["content"])["files"][0]["look"]
    assert len(previews(client, film["id"])) == 2 and len(stored_previews(studio, film["id"])) == 4, "the person is shown the files, not the model's pictures"


def test_an_engine_without_ffmpeg_shows_the_file_as_it_is_and_says_so(studio):
    client, model, launcher = studio.client, studio.model, studio.launcher
    film = new_project(client)
    eid = start_engine(studio, film["id"])["id"]
    launcher.answers += [
        probe("bounces/mix.wav", 30 * MB, None), probe("exports/shot.mov", 5 * MB, None), probe("previews/frame.png", 240_000, None),
        probe("bounces/master.wav", 300 * MB, None), probe("logo/mark.svg", 4_000, {}),
    ]
    model.script(
        reply(
            use("preview", engine_id=eid, paths=["bounces/mix.wav", "exports/shot.mov", "previews/frame.png", "logo/mark.svg"], caption="What there is", look=True),
            use("preview", engine_id=eid, path="bounces/master.wav", caption="The master"),
        ),
        reply(say("Shown as they are.")),
    )
    message(client, film["id"], "Show me")

    shown, master = tool_results(model.requests[1]).values()
    mix, shot, frame, mark = json.loads(shown["content"])["files"]
    assert "This engine has no ffmpeg, so no lighter copy was encoded and nothing was measured: it is shown as it is." == mix["note"]
    assert shot["note"].endswith("as a file to open, since browsers do not play it.") and "note" not in frame
    assert "seconds" not in mix and "loudness_lufs" not in mix
    assert [item["kind"] for item in previews(client, film["id"])[0]["items"]] == ["audio", "file", "image", "image"]
    assert mark["kind"] == "image" and "ffmpeg does not read it" in mark["look"], "a browser draws an SVG whatever ffmpeg reads"
    assert master["is_error"] and "300.0 MB as a preview, over the 50.0 MB" in master["content"]
    assert not any("ffmpeg -nostdin" in command for _, command in launcher.commands)


def test_a_preview_reaches_only_the_projects_own_running_engine_and_its_folder(studio):
    client, model, launcher, store = studio.client, studio.model, studio.launcher, studio.store
    for user in (ALICE, BOB):
        store.moody_ensure_profile(user.id, user.email, 60)["max_sessions"] = 5
    film = new_project(client)
    eid = start_engine(studio, film["id"])["id"]
    other = start_engine(studio, new_project(client, name="Other")["id"], app="blender")
    bobs = start_engine(studio, new_project(client, "bob-token")["id"], token="bob-token")
    ended = start_engine(studio, film["id"], app="blender")
    client.delete(f"/v1/sessions/{ended['id']}", headers=auth("alice-token"))
    launcher.answers += [("./previews/missing.png ] || exit 44", (44, "")), ("[ -f ./previews ] || exit 45", (45, ""))]
    model.script(
        reply(
            use("preview", engine_id=bobs["id"], path="previews/frame.png", caption="Another user's engine"),
            use("preview", engine_id=other["id"], path="previews/frame.png", caption="Another project's engine"),
            use("preview", engine_id=ended["id"], path="previews/frame.png", caption="An engine that stopped"),
            use("preview", engine_id=eid, path="../../other/secret.png", caption="Outside the folder"),
            use("preview", engine_id=eid, path="/etc/passwd", caption="Outside the folder"),
            use("preview", engine_id=eid, path="previews/missing.png", caption="Not there"),
            use("preview", engine_id=eid, path="previews", caption="A folder"),
            use("preview", engine_id=eid, path="previews/frame.png", caption="A sound that is a picture", kind="audio"),
        ),
        reply(say("None of those can be shown.")),
    )
    launcher.answers.append(probe("previews/frame.png", 240_000, PNG))
    message(client, film["id"], "Show me Bob's frame")

    results = list(tool_results(model.requests[1]).values())
    assert all(r.get("is_error") for r in results)
    assert "No such session" in results[0]["content"] and "No such engine in this project" in results[1]["content"]
    assert "not running" in results[2]["content"]
    assert "outside the project's folder" in results[3]["content"] and "outside the project's folder" in results[4]["content"]
    assert "There is no previews/missing.png" in results[5]["content"] and "previews is a folder" in results[6]["content"]
    assert results[7]["content"] == "previews/frame.png is not an audio file, as far as ffprobe reads it."
    assert previews(client, film["id"]) == [] and not launcher.reads and not store.files
    assert {sandbox for sandbox, _ in launcher.commands} == {"sb-1"}, "no other engine was asked anything"


def test_a_screenshot_is_shown_as_a_preview_card_and_previews_are_signed_at_each_reading(studio):
    client, model, store = studio.client, studio.model, studio.store
    film = new_project(client)
    eid = start_engine(studio, film["id"])["id"]
    studio.launcher.answers.append(probe("previews/frame.png", 240_000, PNG))
    model.script(
        reply(use("engine_screenshot", engine_id=eid), use("preview", engine_id=eid, paths=["previews/frame.png", "previews/frame.png"], caption="Twice")),
        reply(say("Seen.")),
    )
    message(client, film["id"], "What is on screen?")
    studio.launcher.answers += [probe("previews/frame.png", 240_000, PNG)] * 2
    model.script(
        reply(use("preview", engine_id=eid, path="previews/frame.png", caption="The whole cut", version="  Rough   cut "),
              use("preview", engine_id=eid, path="previews/frame.png", caption="The whole cut", version="x" * 90)),
        reply(say("Shown.")),
    )
    message(client, film["id"], "Show the cut")

    screen, twice, rough, long = previews(client, film["id"])
    assert "version" not in screen and "version" not in twice, "a step along the way is no version of the piece"
    assert rough["version"] == "Rough cut" and long["version"] == "x" * 40, "a version carries its label, kept short"
    assert screen["caption"] == "FilmCraft's screen" and [(i["kind"], i["name"]) for i in screen["items"]] == [("image", "screen.jpg")]
    ended = [e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "tool_end"]
    assert not any("media" in end for end in ended), "the card is the preview, not a second picture under the call"
    assert tool_results(model.requests[1])[model.requests[1]["messages"][-2]["content"][0]["id"]]["content"][0]["type"] == "image"
    rows = [row["data"] for row in store.tables["project_events"].values() if row["kind"] == "preview"]
    assert all("url" not in item and item["path"].startswith(f"{ALICE.id}/{film['id']}/previews/") for row in rows for item in row["items"]), (
        "the log keeps where a file is, never a link that expires"
    )
    del store.files[rows[1]["items"][0]["path"]]
    assert [len(p["items"]) for p in previews(client, film["id"])] == [1, 1, 1, 1], "a file that is gone is left out of its preview"
    client.delete(f"/v1/projects/{film['id']}", headers=auth("alice-token"))
    assert not store.files, "a project's previews go with it"


def test_engine_send_carries_a_file_between_two_running_engines_of_one_project(studio):
    client, model, launcher, store = studio.client, studio.model, studio.launcher, studio.store
    for user in (ALICE, BOB):
        store.moody_ensure_profile(user.id, user.email, 60)["max_sessions"] = 5
    film = new_project(client)
    cut = start_engine(studio, film["id"])
    score = start_engine(studio, film["id"], runs="soundcraft")
    other = start_engine(studio, new_project(client, name="Other")["id"], app="blender")
    bobs = start_engine(studio, new_project(client, "bob-token")["id"], token="bob-token")
    folder = f"/home/ubuntu/workspace/projects/{film['id']}"
    mix = "handoff/soundcraft-to-filmcraft/mix.wav"
    launcher.absent.add(f"{folder}/handoff/gone.wav")
    launcher.answers += [
        ("./handoff/missing.wav ] || exit 44", (44, "")),
        ("stat -c %s ./handoff/stems; fi", (0, f"{5 * 1024 * MB}\n")),
        ("; fi", (0, "2048\n")),
        (f"find ./{mix} -maxdepth 0", (0, "f\t2048\t1795582875.75\tmix.wav\n")),
        ("find ./audio/score.wav -maxdepth 0", (0, "f\t2048\t1795582875.75\tscore.wav\n")),
    ]
    model.script(
        reply(
            use("engine_send", from_engine_id=score["id"], path=mix, to_engine_id=cut["id"]),
            use("engine_send", from_engine_id=score["id"], path=f"{folder}/{mix}", to_engine_id=cut["id"], to_path="audio/score.wav"),
            use("engine_send", from_engine_id=score["id"], path=mix, to_engine_id=other["id"]),
            use("engine_send", from_engine_id=score["id"], path=mix, to_engine_id=bobs["id"]),
            use("engine_send", from_engine_id=bobs["id"], path=mix, to_engine_id=cut["id"]),
            use("engine_send", from_engine_id=score["id"], path="handoff/stems", to_engine_id=cut["id"]),
            use("engine_send", from_engine_id=score["id"], path="handoff/missing.wav", to_engine_id=cut["id"]),
            use("engine_send", from_engine_id=score["id"], path="handoff/gone.wav", to_engine_id=cut["id"]),
            use("engine_send", from_engine_id=score["id"], path=mix, to_engine_id=score["id"]),
            use("engine_send", from_engine_id=score["id"], path=mix, to_engine_id=cut["id"], to_path="../../elsewhere/mix.wav"),
            use("engine_send", from_engine_id=score["id"], path="", to_engine_id=cut["id"]),
        ),
        reply(say("The mix is in FilmCraft.")),
    )
    message(client, film["id"], "Bring the mix into the cut")

    results = list(tool_results(model.requests[1]).values())
    assert [r.get("is_error", False) for r in results] == [False, False, True, True, True, True, True, True, True, True, True]
    assert launcher.sent == [
        ("sb-2", f"{folder}/{mix}", "sb-1", f"{folder}/{mix}"),
        ("sb-2", f"{folder}/{mix}", "sb-1", f"{folder}/audio/score.wav"),
    ], "only between the project's own two engines, and to the same path unless another is given"
    sent = json.loads(results[0]["content"])
    assert sent["to"] == {"engine_id": cut["id"], "app": "filmcraft", "path": mix} and sent["bytes"] == 2048
    assert sent["entry"] == {"name": mix, "kind": "file", "size": 2048, "modified": "2026-11-25T05:01:15+00:00"}, (
        "the entry is the receiving engine's own listing of it"
    )
    assert json.loads(results[1]["content"])["entry"]["name"] == "audio/score.wav"
    assert "No such engine in this project" in results[2]["content"] and all("No such session" in results[index]["content"] for index in (3, 4))
    assert results[5]["content"].startswith("handoff/stems is 5.0 GB, over the 4.0 GB that passes between running engines.")
    assert "stop the FilmCraft engine and start it again" in results[5]["content"]
    assert "There is no handoff/missing.wav in the project's folder on the SoundCraft engine" in results[6]["content"]
    assert "There is no handoff/gone.wav" in results[7]["content"]
    assert "one engine" in results[8]["content"] and "outside the project's folder" in results[9]["content"]
    assert "not the folder itself" in results[10]["content"]
    assert {sandbox for sandbox, _ in launcher.commands} == {"sb-1", "sb-2"}, "no other project's or user's engine was asked anything"
    shown = tools_shown(client, film["id"])[0]
    assert shown[0] == "Sending mix.wav to another engine" and shown[1].startswith("mix.wav is in FilmCraft's folder: 2 KB in ")


def test_the_launcher_reads_a_file_and_carries_one_between_two_sandboxes_through_its_module():
    module = FakeSandboxModule()
    launcher = ModalLauncher(module, app="modal-app")
    launcher.sandbox = lambda sandbox_id: f"sandbox:{sandbox_id}"
    carried = []
    module.read_file = lambda sandbox, path, limit: f"{sandbox} {path} {limit}".encode()
    module.send_file = lambda source, path, target, to_path, keep_going: carried.append((source, path, target, to_path, keep_going())) or 7
    assert launcher.read_file("sb-1", "/tmp/a.m4a", 99) == b"sandbox:sb-1 /tmp/a.m4a 99"
    assert launcher.send("sb-1", "/w/a.wav", "sb-2", "/w/b.wav", lambda: True) == 7
    assert carried == [("sandbox:sb-1", "/w/a.wav", "sandbox:sb-2", "/w/b.wav", True)]


def test_a_turn_starts_knowing_each_engines_app_its_command_channel_and_the_shared_folder(studio):
    client, model, launcher, store = studio.client, studio.model, studio.launcher, studio.store
    store.moody_ensure_profile(ALICE.id, ALICE.email, 60)["max_sessions"] = 3
    film = new_project(client)
    cut = start_engine(studio, film["id"])
    started = use("engine_start", app="blender", tier="cpu")
    model.script(reply(started), reply(say("Blender is open.")), reply(say("Both run.")))
    message(client, film["id"], "Open Blender beside the edit")
    scene = json.loads(tool_results(model.requests[1])[started["id"]]["content"])
    assert [session["project_id"] for session, _, _ in launcher.started] == [film["id"], film["id"]], (
        "the engine the agent starts opens on the project the running one is on")
    assert f"/home/ubuntu/workspace/projects/{film['id']}" in model.requests[0]["system"][0]["text"]

    message(client, film["id"], "What runs?")
    state = turn_state(model.requests[2]).splitlines()
    assert f"Project folder, which every engine of this project opens in and shares: /home/ubuntu/workspace/projects/{film['id']}" in state
    assert f"- {cut['id']}: FilmCraft (app `filmcraft`), running, tier cpu, has a command channel (engine_call)" in state
    assert f"- {scene['id']}: Blender (app `blender`), running, tier cpu, no command channel (engine_exec, or the person on its screen)" in state


def test_the_agent_saves_only_to_a_branch_of_its_own_made_from_the_default_head(studio):
    client, model, github = studio.client, studio.model, studio.github
    film = new_project(client)
    unlinked = use("github_save", path="script.fountain", content="FADE IN:", message="Script")
    model.script(reply(unlinked), reply(say("Link a repository first.")))
    message(client, film["id"], "Save the script")
    assert "connect" in tool_results(model.requests[1])[unlinked["id"]]["content"].lower()

    connect_alice(studio)
    client.post(f"/v1/projects/{film['id']}/github", headers=auth("alice-token"), json={"repo": "alice-gh/film"})
    repo, branch = "alice-gh/film", f"moody/mara-{film['id'][:8]}"
    main_head, main_files = github.refs[(repo, "main")], dict(github.branch_files(repo, "main"))
    # A teammate's project of the same name, linked to the same repository, made its own branch first
    theirs = github.commit(repo, "moody/mara-0000beef", {**main_files, "notes.md": "theirs"})

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
    assert github.refs[(repo, "moody/mara-0000beef")] == theirs, "nor did the teammate's branch"
    assert github.tokens[-1] == "ghu_alice_1", "with her GitHub App token"
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
        if path == "/repos/o/r/git/matching-refs/heads/moody":
            return httpx.Response(200, json=[{"ref": "refs/heads/moody-old"}, {"ref": "refs/heads/moody/mara-0123abcd"}])
        if request.method == "POST" and path == "/repos/o/r/git/refs":
            return httpx.Response(201, json={"ref": "refs/heads/moody/mara-0123abcd"})
        if path == "/repos/o/r/git/trees/c1":
            return httpx.Response(200, json={"tree": [{"path": "Game.uproject", "type": "blob", "sha": "b"}], "truncated": False})
        return httpx.Response(404, json={"message": "Not Found"})

    github = GitHub()
    github.http = httpx.Client(headers=github.http.headers, transport=httpx.MockTransport(answer))
    branch = "moody/mara-0123abcd"
    assert github.save("gho_t", "o/r", "notes.md", "new", "Notes", branch) == {"html_url": "https://github.com/o/r/commit/c2"}
    read, write = seen
    assert read.url.params["ref"] == branch
    assert json.loads(write.content) == {
        "message": "Notes", "content": base64.b64encode(b"new").decode(), "branch": branch, "sha": "blob1"}
    assert github.head("gho_t", "o/r", "main") == "c1" and github.head("gho_t", "o/r", "gone") is None
    assert github.branches_under("gho_t", "o/r", "moody/") == [branch]
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
    assert all(name in text for name in ("unreal_assets", "github_save", "unreal_projects", "unreal_open", "engine_show"))


def connect(
    studio: SimpleNamespace, flow: str = "github", code: str = "good-code", token: str = "alice-token",
    return_to: str = f"{SITE}/app/",
) -> Any:
    """Connect an account through one flow's authorization page and callback, as a browser would."""
    url = studio.client.post(f"/v1/{flow}/connect", headers=auth(token), json={"return_to": return_to}).json()["url"]
    state = parse_qs(urlsplit(url).query)["state"][0]
    return studio.client.get(f"/v1/{flow}/callback", params={"code": code, "state": state}, follow_redirects=False)


def connect_alice(studio: SimpleNamespace, return_to: str = f"{SITE}/app/", code: str = "good-code") -> Any:
    return connect(studio, "github", code, "alice-token", return_to)


def connect_epic(studio: SimpleNamespace, code: str = "epic-code", token: str = "alice-token") -> Any:
    return connect(studio, "epic", code, token)


def expire(store: FakeStore, user: User, seconds_left: float) -> None:
    """Move a GitHub connection's token to expire that many seconds from now."""
    store.tables["github_connections"][user.id]["token_expires_at"] = (moment() + timedelta(seconds=seconds_left)).isoformat()


def plain_tokens(github: FakeGitHub) -> set[str]:
    """Every token and refresh token GitHub granted, as they would read in the clear."""
    return set(github.owners) | {f"ghr_{who}_{number}" for who in ("alice", "bob") for number in range(1, 30)}


def test_github_connects_as_the_apps_user_authorization_and_links_projects(studio):
    client, store, github = studio.client, studio.store, studio.github
    assert client.get("/v1/github", headers=auth("alice-token")).json() == {"configured": True, "connected": False}
    assert client.get("/v1/github/repos", headers=auth("alice-token")).status_code == 409
    url = client.post("/v1/github/connect", headers=auth("alice-token"), json={"return_to": f"{SITE}/app/?p=1#top"}).json()["url"]
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://github.com/login/oauth/authorize"
    assert query["client_id"] == [APP_CLIENT] and "scope" not in query, "a GitHub App asks for its permissions, not scopes"
    assert query["redirect_uri"] == ["http://testserver/v1/github/callback"]
    assert read_state(SECRET, query["state"][0])["u"] == ALICE.id
    assert read_state(SECRET, query["state"][0], flow=EPIC_FLOW) is None, "a GitHub state is no Epic state"

    back = client.get("/v1/github/callback", params={"code": "good-code", "state": query["state"][0]}, follow_redirects=False)
    assert back.status_code == 303 and back.headers["location"] == f"{SITE}/app/?p=1&github=connected#top"
    assert github.redirects == ["http://testserver/v1/github/callback"]
    (row,) = store.tables["github_connections"].values()
    assert not plain_tokens(github) & set(json.dumps(row).replace('"', " ").split()), "no token in the clear"
    assert unseal(SECRET, row["token_encrypted"]) == "ghu_alice_1" and unseal(SECRET, row["refresh_token_encrypted"]) == "ghr_alice_1"
    hours = (datetime.fromisoformat(row["token_expires_at"]) - moment()).total_seconds() / 3600
    months = (datetime.fromisoformat(row["refresh_expires_at"]) - moment()).days / 30
    assert 7.9 < hours <= 8 and 6 <= months < 6.2, "eight hours for the token, six months for its refresh"
    assert (row["github_id"], row["name"]) == (1001, "Alice Example")
    assert client.get("/v1/github", headers=auth("alice-token")).json() == {
        "configured": True, "connected": True, "login": "alice-gh", "avatar_url": "https://avatars.example.test/alice"}
    assert client.get("/v1/github", headers=auth("bob-token")).json()["connected"] is False
    repos = client.get("/v1/github/repos", headers=auth("alice-token")).json()["repos"]
    assert repos == [{"full_name": "alice-gh/film", "private": True, "html_url": "https://github.com/alice-gh/film",
                      "updated_at": "2026-11-20T00:00:00Z"}], "the app's installations only: not a public repository it is not on"

    film = new_project(client)
    link = lambda body: client.post(f"/v1/projects/{film['id']}/github", headers=auth("alice-token"), json=body)
    linked = link({"repo": "alice-gh/film"}).json()["project"]
    assert (linked["github_repo"], linked["github_branch"]) == ("alice-gh/film", None)
    github.add_repository("someone/sealed", push=False, pull=False)
    assert link({"repo": "someone/sealed"}).status_code == 403, "a repository the account cannot read"
    read_only = link({"repo": "someone/theirs"})
    assert read_only.json()["project"]["github_repo"] == "someone/theirs", "reading is enough to link and ask about it"
    assert link({"repo": "someone/missing"}).status_code == 404
    assert link({"repo": "not a repo"}).status_code == 400
    assert link({}).status_code == 400
    made = link({"create": {"name": "mara-film"}})
    assert made.status_code == 400 and "create it on GitHub" in made.json()["detail"], "the app makes no repository"
    github.commit("alice-gh/film", "release", {"README.md": "release"})
    assert link({"repo": "alice-gh/film", "branch": "release"}).json()["project"]["github_branch"] == "release"
    assert link({"repo": "alice-gh/film", "branch": "nope"}).status_code == 404
    assert link({"repo": "alice-gh/film", "branch": "a b"}).status_code == 400
    assert client.post(f"/v1/projects/{film['id']}/github", headers=auth("bob-token"), json={"repo": "alice-gh/film"}).status_code == 404
    unlinked = client.delete(f"/v1/projects/{film['id']}/github", headers=auth("alice-token")).json()["project"]
    assert (unlinked["github_repo"], unlinked["github_branch"]) == (None, None)
    assert client.delete("/v1/github", headers=auth("alice-token")).json() == {"configured": True, "connected": False}
    assert store.tables["github_connections"] == {}


def test_an_expiring_token_is_refreshed_before_use_and_a_refused_refresh_asks_to_connect_again(studio):
    client, store, github, sessions = studio.client, studio.store, studio.github, studio.sessions
    connect_alice(studio)
    listed = lambda: client.get("/v1/github/repos", headers=auth("alice-token"))
    assert listed().status_code == 200 and github.refreshes == [], "a token with hours left is used as it is"

    expire(store, ALICE, 120)
    assert listed().status_code == 200
    assert github.refreshes == ["ghr_alice_1"], "refreshed once, minutes before it would expire"
    row = store.tables["github_connections"][ALICE.id]
    renewed = unseal(SECRET, row["token_encrypted"])
    assert renewed != "ghu_alice_1" and renewed in github.live and "ghu_alice_1" not in github.live
    assert unseal(SECRET, row["refresh_token_encrypted"]) != "ghr_alice_1", "the new refresh token is the one kept"
    assert datetime.fromisoformat(row["token_expires_at"]) > moment() + timedelta(hours=7)
    assert listed().status_code == 200 and len(github.refreshes) == 1

    # Another refresh uses the same refresh token first, as two engines starting at once would
    expire(store, ALICE, -60)
    used = unseal(SECRET, store.tables["github_connections"][ALICE.id]["refresh_token_encrypted"])

    def race() -> None:
        winner = github.refresh(APP_CLIENT, SECRETS[APP_CLIENT], used)
        store.update("github_connections", Sessions.sealed_grant(SECRET, winner), user_id=f"eq.{ALICE.id}")

    github.racer = race
    token = sessions.github_token(ALICE.id)
    assert token == unseal(SECRET, store.tables["github_connections"][ALICE.id]["token_encrypted"]) and token in github.live, (
        "the loser of the race takes the pair the winner stored"
    )

    expire(store, ALICE, -60)
    github.refresh_tokens.clear()
    refused = listed()
    assert refused.status_code == 409 and "Connect GitHub again" in refused.json()["detail"]


def test_the_repositories_offered_are_the_apps_installations_and_a_missing_one_has_an_install_link(studio):
    client, store, github = studio.client, studio.store, studio.github
    github.add_repository("studio/multiverse-br", push=True, updated="2026-11-23T00:00:00Z", installation=None)
    github.install("studio/multiverse-br", 3, "studio", {"alice-gh", "bob-gh"})
    github.add_repository("bob-gh/drafts", push=True, installation=2)
    github.add_repository("other-org/game", push=True, updated="2026-11-24T00:00:00Z", installation=None)
    connect_alice(studio)
    names = lambda: [repo["full_name"] for repo in client.get("/v1/github/repos", headers=auth("alice-token")).json()["repos"]]
    assert names() == ["studio/multiverse-br", "alice-gh/film"], "her account's and her organization's, newest first"

    page = f"{SITE}/app/?project=p1"
    url = client.post("/v1/github/install", headers=auth("alice-token"), json={"return_to": page}).json()["url"]
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == f"https://github.com/apps/{SLUG}/installations/new"
    state = parse_qs(parts.query)["state"][0]
    assert (read_state(SECRET, state)["u"], read_state(SECRET, state)["r"]) == (ALICE.id, page)
    assert client.post("/v1/github/install", headers=auth("alice-token"), json={"return_to": "https://evil.example/"}).status_code == 400
    game = new_project(client, discipline="games", format="Game")
    missing = client.post(f"/v1/projects/{game['id']}/github", headers=auth("alice-token"), json={"repo": "other-org/game"})
    assert missing.status_code == 404 and "not installed" in missing.json()["detail"]

    # The owner installs the app there; GitHub brings the state back with the authorization it asks for
    github.install("other-org/game", 4, "other-org", {"alice-gh"})
    back = client.get("/v1/github/callback", params={"code": "next-code", "state": state, "setup_action": "install",
                                                     "installation_id": "4"}, follow_redirects=False)
    assert back.headers["location"] == f"{page}&github=installed"
    assert names() == ["other-org/game", "studio/multiverse-br", "alice-gh/film"]
    exchanged = len(github.redirects)
    before = copy.deepcopy(store.tables["github_connections"])
    for arrival in ({"code": "c", "setup_action": "install", "installation_id": "5"},
                    {"setup_action": "request"},
                    {"code": "good-code", "state": sign_state("not-our-secret", BOB.id, SITE), "setup_action": "update"}):
        landed = client.get("/v1/github/callback", params=arrival, follow_redirects=False)
        outcome = "requested" if arrival["setup_action"] == "request" else "installed"
        assert landed.status_code == 303 and landed.headers["location"] == f"{SITE}/app/?github={outcome}", arrival
    assert len(github.redirects) == exchanged and store.tables["github_connections"] == before, (
        "an installation that comes back without Moody's state connects nobody and exchanges nothing"
    )
    asked = client.get("/v1/github/callback", params={"state": sign_state(SECRET, ALICE.id, page), "setup_action": "request"},
                       follow_redirects=False)
    assert asked.headers["location"] == f"{page}&github=requested", "a member's request, waiting for the owner"


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
        "another flow's state": sign_state(SECRET, ALICE.id, page, flow=EPIC_FLOW),
        "no signature": body,
        "nothing": "",
        "garbage": "x.y",
    }
    for name, state in forgeries.items():
        refused = client.get("/v1/github/callback", params={"code": "good-code", "state": state}, follow_redirects=False)
        assert refused.status_code == 400 and "location" not in refused.headers, name
        refused = client.get("/v1/epic/callback", params={"code": "epic-code", "state": state if name != "another flow's state"
                                                          else genuine}, follow_redirects=False)
        assert refused.status_code == 400 and "location" not in refused.headers, f"Epic: {name}"
    assert github.redirects == [], "no code was exchanged"
    assert store.tables["github_connections"] == {} and store.tables["epic_connections"] == {}


def test_github_never_sends_anyone_off_the_site(studio):
    client, store = studio.client, studio.store
    for elsewhere in ("https://evil.example/", "https://site.example.test.evil.example/app/", "https://site.example.test@evil.example/",
                      "//evil.example/", "javascript:alert(1)", f"{SITE}\\@evil.example", "http://site.example.test/app/"):
        for route in ("/v1/github/connect", "/v1/github/install", "/v1/epic/connect"):
            refused = client.post(route, headers=auth("alice-token"), json={"return_to": elsewhere})
            assert refused.status_code == 400, (route, elsewhere)
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


def test_github_and_epic_wait_for_their_apps(world):
    client = world[0]
    assert client.get("/v1/github", headers=auth("alice-token")).json() == {"configured": False, "connected": False}
    assert client.get("/v1/epic", headers=auth("alice-token")).json() == {"configured": False, "connected": False, "linked": None}
    for route in ("/v1/github/connect", "/v1/github/install", "/v1/epic/connect"):
        assert client.post(route, headers=auth("alice-token"), json={"return_to": f"{SITE}/app/"}).status_code == 503, route
    refused = client.get("/v1/github/callback", params={"code": "c", "state": sign_state("", ALICE.id, SITE), "setup_action": "install"},
                         follow_redirects=False)
    assert refused.status_code == 400
    refused = client.get("/v1/epic/callback", params={"code": "c", "state": sign_state("", ALICE.id, SITE, flow=EPIC_FLOW)},
                         follow_redirects=False)
    assert refused.status_code == 400


def test_epic_is_a_connection_of_its_own_that_reads_packages_and_nothing_else(studio):
    client, store, github, launcher = studio.client, studio.store, studio.github, studio.launcher
    status = lambda token="alice-token": client.get("/v1/epic", headers=auth(token)).json()
    assert status() == {"configured": True, "connected": False, "linked": None}
    url = client.post("/v1/epic/connect", headers=auth("alice-token"), json={"return_to": f"{SITE}/app/"}).json()["url"]
    query = parse_qs(urlsplit(url).query)
    assert query["client_id"] == [EPIC_CLIENT] and query["scope"] == ["read:packages"]
    assert query["redirect_uri"] == ["http://testserver/v1/epic/callback"]
    assert read_state(SECRET, query["state"][0], flow=EPIC_FLOW)["u"] == ALICE.id and read_state(SECRET, query["state"][0]) is None

    wrong_app = client.get("/v1/epic/callback", params={"code": "good-code", "state": query["state"][0]}, follow_redirects=False)
    assert wrong_app.headers["location"] == f"{SITE}/app/?epic=failed", "a GitHub App code is not the Epic app's"
    assert connect_epic(studio).headers["location"] == f"{SITE}/app/?epic=connected"
    (row,) = store.tables["epic_connections"].values()
    epic_token = unseal(SECRET, row["token_encrypted"])
    assert epic_token.startswith("gho_alice_epic") and epic_token not in json.dumps(row) and row["scope"] == "read:packages"
    assert store.tables["github_connections"] == {}, "Epic connects no repositories"
    assert client.get("/v1/github", headers=auth("alice-token")).json()["connected"] is False

    assert status() == {"configured": True, "connected": True, "login": "alice-gh", "linked": False}
    assert github.registry_checks[-1] == ("alice-gh", epic_token), "asked with her login and token"
    github.pullers.add(epic_token)
    assert status()["linked"] is True
    github.registry_refusal = GitHubError(502, "ghcr.io answered 502")
    unknown = status()
    assert unknown["linked"] is None and "502" in unknown["detail"]
    github.registry_refusal = None
    github.live.discard(epic_token)
    revoked = status()
    assert revoked["linked"] is None and "Connect Epic again" in revoked["detail"], "a refusal of a dead token is no answer"
    assert status("bob-token") == {"configured": True, "connected": False, "linked": None}

    launcher.credentials[ALICE.id] = {"REGISTRY_USERNAME": "alice-gh", "REGISTRY_PASSWORD": epic_token}
    connect_epic(studio, "epic-next-code")
    renewed = unseal(SECRET, store.tables["epic_connections"][ALICE.id]["token_encrypted"])
    assert launcher.credentials[ALICE.id]["REGISTRY_PASSWORD"] == renewed != epic_token, "connecting again refreshes the pull"
    connect_alice(studio)
    client.delete("/v1/github", headers=auth("alice-token"))
    assert ALICE.id in launcher.credentials, "disconnecting GitHub leaves the Epic connection as it is"
    assert client.delete("/v1/epic", headers=auth("alice-token")).json() == {"configured": True, "connected": False, "linked": None}
    assert launcher.credentials == {} and store.tables["epic_connections"] == {}


def test_unreal_starts_for_anyone_and_brings_the_editor_only_for_an_epic_connection_the_registry_lets_pull(studio):
    client, github, launcher, store = studio.client, studio.github, studio.launcher, studio.store
    game = new_project(client, discipline="games", format="World")

    def start(token: str = "alice-token", project: dict[str, Any] = game) -> dict[str, Any]:
        response = client.post(f"/v1/projects/{project['id']}/engines", headers=auth(token), json={"app": "unreal", "tier": "t4"})
        assert response.status_code == 200, response.text
        engine = response.json()["engine"]
        assert store.sessions[engine["id"]]["status"] == "running"
        return engine

    def stop(engine: dict[str, Any], token: str = "alice-token") -> None:
        client.delete(f"/v1/sessions/{engine['id']}", headers=auth(token))

    no_gpu = client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "unreal", "tier": "cpu"})
    assert no_gpu.status_code == 400 and "needs a GPU" in no_gpu.json()["detail"], "the editor renders only on a GPU"

    stop(start())
    connect_alice(studio)
    stop(start())
    assert github.registry_checks == [], "a GitHub App connection is not asked about Epic"
    connect_epic(studio)
    stop(start())
    github.registry_refusal = GitHubError(502, "ghcr.io answered 502")
    stop(start())
    github.registry_refusal = None
    assert launcher.own_copies == [None] * 4, (
        "without Epic, with GitHub alone, unlinked, and while the registry fails, the engine starts without the editor"
    )
    assert launcher.credentials == {}, "a start without the editor keeps no credential for a pull"

    epic_token = unseal(SECRET, store.tables["epic_connections"][ALICE.id]["token_encrypted"])
    github.pullers.add(epic_token)
    engine = start()
    assert launcher.own_copies[-1] == OwnCopy("5.8")
    assert launcher.credentials == {ALICE.id: {"REGISTRY_USERNAME": "alice-gh", "REGISTRY_PASSWORD": epic_token}}, (
        "pulled with her own Epic connection's login and token, kept for her before the start"
    )
    assert epic_token not in json.dumps(store.sessions) + json.dumps(engine), "the token is kept nowhere with the session"
    theirs = new_project(client, "bob-token", discipline="games", format="World")
    stop(start("bob-token", theirs), "bob-token")
    assert launcher.own_copies[-1] is None and BOB.id not in launcher.credentials, "another user's link is not Bob's"
    stop(engine)
    client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "blender", "tier": "t4"})
    assert launcher.own_copies[-1] is None, "an app on Moody's own license gets no credential"
    client.delete("/v1/epic", headers=auth("alice-token"))
    assert launcher.credentials == {}, "disconnecting Epic deletes it"


def test_a_queued_unreal_start_reads_the_epic_link_it_has_when_it_starts(studio):
    client, sessions, store, github = studio.client, studio.sessions, studio.store, studio.github
    connect_epic(studio)
    github.pullers.add(unseal(SECRET, store.tables["epic_connections"][ALICE.id]["token_encrypted"]))
    object.__setattr__(sessions.config, "capacity", 0)
    game = new_project(client, discipline="games", format="World")
    queued = client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "unreal", "tier": "t4"})
    assert queued.json()["engine"]["status"] == "queued"
    client.delete("/v1/epic", headers=auth("alice-token"))
    object.__setattr__(sessions.config, "capacity", 10)
    sessions.reconcile()
    (session,) = store.sessions.values()
    assert session["status"] == "running", "the desktop starts without the editor the disconnect took away"
    assert studio.launcher.own_copies == [None] and studio.launcher.credentials == {}


MULTIVERSE = "studio/multiverse-br"


def test_an_unreal_start_of_a_linked_project_clones_with_a_fresh_token_no_row_keeps(studio):
    client, store, github, launcher, model = studio.client, studio.store, studio.github, studio.launcher, studio.model
    github.add_repository(MULTIVERSE, push=True, installation=None)
    github.install(MULTIVERSE, 3, "studio", {"alice-gh"})
    store.moody_ensure_profile(ALICE.id, ALICE.email, 60)["max_sessions"] = 2
    connect_alice(studio)
    imported = client.post("/v1/projects", headers=auth("alice-token"),
                           json={"name": "MultiverseBR", "discipline": "games", "format": "Game", "github_repo": MULTIVERSE})
    game = imported.json()["project"]
    assert (game["github_repo"], game["github_branch"]) == (MULTIVERSE, None), "imported from GitHub, it starts linked"
    refused = client.post("/v1/projects", headers=auth("alice-token"),
                          json={"name": "x", "discipline": "games", "github_repo": "other-org/missing"})
    assert refused.status_code == 404 and len(store.tables["projects"]) == 1, "nothing is made for a repository it cannot reach"

    expire(store, ALICE, 3600)
    response = client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "unreal", "tier": "t4"})
    engine = response.json()["engine"]
    clone = launcher.clones[-1]
    token = unseal(SECRET, store.tables["github_connections"][ALICE.id]["token_encrypted"])
    assert github.refreshes == ["ghr_alice_1"] and token != "ghu_alice_1", "an hour left is not fresh enough to clone with"
    assert clone == Clone(repo=MULTIVERSE, branch="main", name="Alice Example", email="1001+alice-gh@users.noreply.github.com",
                          token=token)
    assert clone.environment() == {"MOODY_GIT_TOKEN": token, "MOODY_GIT_REPO": MULTIVERSE, "MOODY_GIT_BRANCH": "main",
                                   "MOODY_GIT_NAME": "Alice Example", "MOODY_GIT_EMAIL": "1001+alice-gh@users.noreply.github.com"}
    assert token not in repr(clone)

    sandbox = store.sessions[engine["id"]]["sandbox_id"]
    path = f"/home/ubuntu/workspace/projects/{game['id']}/multiverse-br"
    listing = lambda: next(e for e in client.get(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token")).json()["engines"]
                           if e["id"] == engine["id"])
    assert "clone" not in listing(), "a machine that reports no clone shows none"
    launcher.clone_states[sandbox] = {"state": "cloning", "path": path, "detail": "Git LFS: 812 of 4,210 files"}
    assert listing()["clone"] == {"state": "cloning", "path": path, "detail": "Git LFS: 812 of 4,210 files"}
    model.script(reply(say("It is still cloning.")))
    message(client, game["id"], "Is my game there?")
    assert f"still cloning {MULTIVERSE}" in turn_state(model.requests[-1])
    launcher.clone_states[sandbox] = {"state": "failed", "path": path, "detail": "fatal: Authentication failed"}
    model.script(reply(say("It did not clone.")))
    message(client, game["id"], "And now?")
    assert "could not clone" in turn_state(model.requests[-1]) and "Authentication failed" in turn_state(model.requests[-1])
    launcher.clone_states[sandbox] = {"state": "done", "path": path, "detail": ""}
    model.script(reply(say("Here it is.")))
    message(client, game["id"], "And now?")
    assert listing()["clone"]["state"] == "done" and "clon" not in turn_state(model.requests[-1])
    launcher.clone_states[sandbox] = {"state": "lost", "path": 3}
    assert "clone" not in listing(), "an answer outside the machine's contract is not shown"

    granted = plain_tokens(github)
    kept = json.dumps({table: rows for table, rows in store.tables.items()}, default=str) + json.dumps(listing())
    assert not {word for word in granted if word in kept}, "no token in any row, event, message, or listing"

    client.delete(f"/v1/sessions/{engine['id']}", headers=auth("alice-token"))
    github.commit(MULTIVERSE, "release", {"README.md": "release"})
    client.post(f"/v1/projects/{game['id']}/github", headers=auth("alice-token"), json={"repo": MULTIVERSE, "branch": "release"})
    client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "unreal", "tier": "t4"})
    assert launcher.clones[-1].branch == "release", "the branch the project chose"
    assert len(github.refreshes) == 1, "a token with most of its hours left is not refreshed again"
    client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "blender", "tier": "t4"})
    assert launcher.clones[-1] is None, "only Unreal clones"
    for engine_row in list(store.sessions.values()):
        client.delete(f"/v1/sessions/{engine_row['id']}", headers=auth("alice-token"))

    unlinked = new_project(client, discipline="games", format="Game")
    client.post(f"/v1/projects/{unlinked['id']}/engines", headers=auth("alice-token"), json={"app": "unreal", "tier": "t4"})
    assert launcher.clones[-1] is None, "a project with no repository clones nothing"
    for engine_row in list(store.sessions.values()):
        client.delete(f"/v1/sessions/{engine_row['id']}", headers=auth("alice-token"))
    expire(store, ALICE, -60)
    github.refresh_tokens.clear()
    started = client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "unreal", "tier": "t4"})
    assert store.sessions[started.json()["engine"]["id"]]["status"] == "running" and launcher.clones[-1] is None, (
        "where GitHub will not renew the token, the engine starts without the clone rather than not at all"
    )


def test_one_users_github_and_epic_connections_never_reach_another(studio):
    client, store, github, launcher = studio.client, studio.store, studio.github, studio.launcher
    github.add_repository(MULTIVERSE, push=True, installation=None)
    github.install(MULTIVERSE, 3, "studio", {"alice-gh"})
    github.add_repository("bob-gh/drafts", push=True, installation=2, updated="2026-11-22T00:00:00Z")
    connect_alice(studio)
    connect_epic(studio)
    assert connect(studio, "github", "bob-code", "bob-token").headers["location"].endswith("github=connected")
    assert set(store.tables["github_connections"]) == {ALICE.id, BOB.id} and set(store.tables["epic_connections"]) == {ALICE.id}

    bobs = lambda path, **kwargs: client.request(kwargs.pop("method", "GET"), path, headers=auth("bob-token"), **kwargs)
    assert [repo["full_name"] for repo in bobs("/v1/github/repos").json()["repos"]] == ["bob-gh/drafts"]
    assert bobs("/v1/github").json()["login"] == "bob-gh" and bobs("/v1/epic").json()["connected"] is False
    project = bobs("/v1/projects", method="POST", json={"name": "Mine", "discipline": "games", "format": "Game"}).json()["project"]
    stolen = bobs(f"/v1/projects/{project['id']}/github", method="POST", json={"repo": MULTIVERSE})
    assert stolen.status_code == 404, "Alice's organization's repository is not Bob's to link"
    bobs(f"/v1/projects/{project['id']}/github", method="POST", json={"repo": "bob-gh/drafts"})
    bobs(f"/v1/projects/{project['id']}/engines", method="POST", json={"app": "unreal", "tier": "t4"})
    clone = launcher.clones[-1]
    bob_token = unseal(SECRET, store.tables["github_connections"][BOB.id]["token_encrypted"])
    assert (clone.repo, clone.token, clone.name, clone.email) == ("bob-gh/drafts", bob_token, "bob-gh", "1002+bob-gh@users.noreply.github.com")
    assert launcher.own_copies[-1] is None and BOB.id not in launcher.credentials, "Alice's Epic link is not Bob's"

    # Alice's callback state cannot connect Bob, nor Bob's Alice
    state = parse_qs(urlsplit(client.post("/v1/github/connect", headers=auth("alice-token"),
                                          json={"return_to": f"{SITE}/app/"}).json()["url"]).query)["state"][0]
    client.get("/v1/github/callback", params={"code": "next-code", "state": state}, follow_redirects=False)
    assert unseal(SECRET, store.tables["github_connections"][BOB.id]["token_encrypted"]) == bob_token
    client.delete("/v1/github", headers=auth("alice-token"))
    client.delete("/v1/epic", headers=auth("alice-token"))
    assert set(store.tables["github_connections"]) == {BOB.id}, "a disconnect is the user's own"
    assert bobs("/v1/github/repos").status_code == 200


def running_unreal(studio: SimpleNamespace, linked: bool = True, sessions: int = 1) -> tuple[dict[str, Any], dict[str, Any], str]:
    """A Games project with a running Unreal engine, its Epic connection linked or not: the project, the engine, its Sandbox."""
    studio.store.moody_ensure_profile(ALICE.id, ALICE.email, 60)["max_sessions"] = sessions
    connect_alice(studio)
    connect_epic(studio)
    if linked:
        studio.github.pullers.add(unseal(SECRET, studio.store.tables["epic_connections"][ALICE.id]["token_encrypted"]))
    game = new_project(studio.client, name="Ember Ridge", discipline="games", format="Game")
    engine = studio.client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "unreal", "tier": "t4"}).json()["engine"]
    return game, engine, studio.store.sessions[engine["id"]]["sandbox_id"]


def uproject(path: str, association: str = "5.8", not_fetched: int = 0) -> dict[str, Any]:
    """A .uproject as the machine reports what it found (`addons/modal/unreal/projects.py`): a C++ game in Git LFS.

    Its plugins are one of the engine's, one in the repository with its source, one in the
    repository as binaries only, and one from the marketplace that the repository does not carry.
    """
    def plugin(name: str, **where: Any) -> dict[str, Any]:
        return {"name": name, "in_repository": False, "source_in_repository": False, "path": None, "marketplace": False, **where}

    return {
        "path": path, "name": PurePosixPath(path).stem, "folder": str(PurePosixPath(path).parent),
        "engine_association": association, "engine_version": association,
        "modules": [{"name": "EmberRidge", "type": "Runtime", "loading_phase": "Default"}],
        "plugins": [
            plugin("ModelingToolsEditorMode"),
            plugin("RidgeTools", in_repository=True, source_in_repository=True, path="Plugins/RidgeTools"),
            plugin("Wwise", in_repository=True, path="Plugins/Wwise"),
            plugin("VoxelPro", marketplace=True),
        ],
        "repository": {"root": str(PurePosixPath(path).parent), "branch": "main", "remote": "https://github.com/studio/game",
                       "submodules": [], "lfs": {"uses_lfs": True, "files": 109, "fetched": 109 - not_fetched,
                                                 "not_fetched": not_fetched}},
        "size_bytes": 2_400_000_000, "size": "2.4 GB",
    }


def screens(client: TestClient, project_id: str) -> list[dict[str, Any]]:
    """What the agent put on the person's screen, in order."""
    return [event["data"] for event in events(client, project_id)["events"] if event["kind"] == "screen"]


def turn_state(request: dict[str, Any]) -> str:
    """The project's state a request's turn started with."""
    return said(request)[1]


def test_a_running_unreal_engine_reports_both_pictures_with_links_minted_for_the_page(studio):
    client, launcher, model, store = studio.client, studio.launcher, studio.model, studio.store
    game, engine, sandbox = running_unreal(studio, sessions=2)
    blender = client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"}).json()["engine"]
    listing = lambda: {e["id"]: e for e in client.get(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token")).json()["engines"]}
    shown = listing()
    assert "streams" not in shown[blender["id"]], "an engine that streams its desktop alone"
    assert [stream["name"] for stream in shown[engine["id"]]["streams"]] == ["Desktop", "Unreal"]
    desktop, view = (stream["url"] for stream in shown[engine["id"]]["streams"])
    assert desktop.startswith(f"https://{sandbox}.") and view.startswith(f"https://{sandbox}-unreal.")
    listing()
    assert launcher.links == [(sandbox, "Desktop"), (sandbox, "Unreal")] * 2, "minted afresh for each listing"

    link = lambda body=None, token="alice-token": client.post(f"/v1/sessions/{engine['id']}/link", headers=auth(token), json=body)
    assert link().json()["url"].startswith(f"https://{sandbox}.") and link({"stream": "Desktop"}).json()["url"].startswith(f"https://{sandbox}.")
    assert link({"stream": "Unreal"}).json()["url"].startswith(f"https://{sandbox}-unreal.")
    assert link({"stream": "Sequencer"}).status_code == 404
    assert link({"stream": "Unreal"}, "bob-token").status_code == 404, "another user's engine does not exist for Bob"
    unreal_link = client.post(f"/v1/sessions/{blender['id']}/link", headers=auth("alice-token"), json={"stream": "Unreal"})
    assert unreal_link.status_code == 404

    minted = len(launcher.links)
    model.script(reply(use("engine_list"), use("engine_show", engine_id=engine["id"], stream="Unreal")), reply(say("Both run.")))
    message(client, game["id"], "What runs?")
    assert len(launcher.links) == minted, "the agent's listing and its view switch mint nothing"
    kept = json.dumps(store.tables["project_events"]) + json.dumps(store.tables["agent_transcripts"])
    assert "connect_token" not in kept, "no link is written to the log or the conversation"


def test_the_agent_is_told_of_an_unreal_project_until_it_has_looked_at_it(studio):
    client, model, launcher = studio.client, studio.model, studio.launcher
    film = new_project(client)
    model.script(reply(say("Hello.")))
    message(client, film["id"], "Hello")
    assert launcher.project_reads == [], "no machine is asked where no Unreal engine runs"

    game, engine, sandbox = running_unreal(studio)
    model.script(reply(say("Nothing cloned yet.")))
    message(client, game["id"], "Hi")
    assert "none yet" in turn_state(model.requests[-1])

    path = f"/home/ubuntu/workspace/projects/{game['id']}/ember-ridge/EmberRidge.uproject"
    launcher.uprojects[sandbox] = [uproject(path)]
    model.script(reply(say("Shall we look?")))
    message(client, game["id"], "I cloned the game")
    state = turn_state(model.requests[-1])
    assert path in state and "not reported yet" in state and "unreal_projects" in state

    looking = use("unreal_projects", engine_id=engine["id"])
    model.script(reply(looking), reply(say("Ember Ridge, Unreal Engine 5.8, C++.")))
    message(client, game["id"], "What did you find?")
    found = json.loads(tool_results(model.requests[-1])[looking["id"]]["content"])
    (project,) = found["projects"]
    assert (project["path"], project["engine_association"], project["version"]) == (path, "5.8", "same")
    assert project["cpp_modules"] == ["EmberRidge"] and project["plugins"] == ["ModelingToolsEditorMode", "RidgeTools", "Wwise", "VoxelPro"]
    assert project["plugins_to_check"] == ["Wwise", "VoxelPro"]
    assert project["lfs"] is True and project["size_bytes"] == 2_400_000_000

    model.script(reply(say("Open it?")))
    message(client, game["id"], "Thanks")
    state = turn_state(model.requests[-1])
    assert path in state and "not reported yet" not in state, "what the agent looked at is not raised again"
    assert launcher.project_reads == [sandbox] * 5, "once at each turn's start where Unreal runs, and once for the call"


def test_unreal_open_opens_the_editor_on_the_agents_branch_for_an_older_project_and_shows_it(studio):
    client, model, launcher = studio.client, studio.model, studio.launcher
    game, engine, sandbox = running_unreal(studio)
    folder = f"/home/ubuntu/workspace/projects/{game['id']}"
    same, older, newer = (f"{folder}/{name}/{name}.uproject" for name in ("EmberRidge", "OldRidge", "NextRidge"))
    launcher.uprojects[sandbox] = [uproject(same), uproject(older, "5.4"), uproject(newer, "5.9")]
    branch = f"moody/ember-ridge-{game['id'][:8]}"
    launcher.answers.append(("git branch --show-current", (0, f"branch={branch}\n")))
    calls = [use("unreal_open", engine_id=engine["id"], path=path) for path in (same, older, newer, f"{folder}/Missing.uproject")]
    model.script(reply(*calls), reply(say("Opened.")))
    message(client, game["id"], "Open them in Unreal")

    results = [tool_results(model.requests[-1])[call["id"]] for call in calls]
    assert [result.get("is_error", False) for result in results] == [False, False, True, True]
    assert json.loads(results[0]["content"])["branch"] is None, "the engine's version opens as it is"
    assert json.loads(results[1]["content"])["branch"] == branch
    assert "older editor" in results[2]["content"] and "unreal_projects" in results[3]["content"]
    commands = [command for _, command in launcher.commands]
    opened = [command for command in commands if command.startswith("selkies-modal-unreal-open")]
    assert opened == [f"selkies-modal-unreal-open {same}", f"selkies-modal-unreal-open {older}"], "nothing newer is opened"
    switch = next(index for index, command in enumerate(commands) if "git switch" in command)
    assert f"cd {folder}/OldRidge" in commands[switch] and branch in commands[switch]
    assert commands.index(opened[1]) > switch, "the clone is on the agent's branch before the editor saves anything"
    assert not any(word in command for command in commands for word in ("git commit", "git push", "git reset")), (
        "nothing of the team's is written"
    )
    assert screens(client, game["id"]) == [{"engine_id": engine["id"], "stream": "Unreal"}] * 2


def test_unreal_open_says_the_one_step_that_brings_the_editor_where_it_is_missing(studio):
    client, model, launcher, github = studio.client, studio.model, studio.launcher, studio.github
    game, engine, sandbox = running_unreal(studio, linked=False)
    path = f"/home/ubuntu/workspace/projects/{game['id']}/EmberRidge/EmberRidge.uproject"
    launcher.uprojects[sandbox] = [uproject(path)]
    launcher.answers.append(("selkies-modal-unreal-open", (3, "The Unreal Editor is not installed in this engine.\n")))

    opening = use("unreal_open", engine_id=engine["id"], path=path)
    model.script(reply(opening), reply(say("Link Epic first.")))
    message(client, game["id"], "Open it in Unreal")
    unlinked = tool_results(model.requests[-1])[opening["id"]]
    assert unlinked["is_error"] and "not installed" in unlinked["content"]
    assert "Apps and Accounts" in unlinked["content"] and "start it again" in unlinked["content"]

    github.pullers.add(unseal(SECRET, studio.store.tables["epic_connections"][ALICE.id]["token_encrypted"]))
    opening = use("unreal_open", engine_id=engine["id"], path=path)
    model.script(reply(opening), reply(say("Restart the engine.")))
    message(client, game["id"], "I linked it")
    linked = tool_results(model.requests[-1])[opening["id"]]
    assert linked["is_error"] and "started before" in linked["content"] and "Apps and Accounts" not in linked["content"]
    assert screens(client, game["id"]) == [], "the screen stays where it is"
    log = events(client, game["id"])["events"]
    assert [e["data"]["summary"] for e in log if e["kind"] == "tool_end"] == [
        "The Unreal Editor needs the Epic link", "The Unreal Editor did not open",
    ]


def test_the_unreal_tools_say_how_to_start_unreal_where_none_runs(studio):
    client, model = studio.client, studio.model
    studio.store.moody_ensure_profile(ALICE.id, ALICE.email, 60)["max_sessions"] = 2
    game = new_project(client, name="Ember Ridge", discipline="games", format="Game")
    blender = client.post(f"/v1/projects/{game['id']}/engines", headers=auth("alice-token"), json={"app": "blender", "tier": "cpu"}).json()["engine"]
    calls = [
        use("unreal_open", engine_id=blender["id"], path="/home/ubuntu/workspace/Game.uproject"),
        use("unreal_projects", engine_id=str(uuid.uuid4())),
        use("engine_show", engine_id=blender["id"], stream="Unreal"),
    ]
    model.script(reply(*calls), reply(say("Start Unreal first.")))
    message(client, game["id"], "Open my game")
    results = [tool_results(model.requests[-1])[call["id"]] for call in calls]
    assert all(result["is_error"] for result in results)
    assert "is not Unreal Engine" in results[0]["content"] and "No such engine" in results[1]["content"]
    assert all("Start Unreal Engine on a tier with a GPU (t4)" in result["content"] for result in results[:2])
    assert "desktop only" in results[2]["content"] and screens(client, game["id"]) == []


def test_the_studio_reads_the_unreal_projects_of_a_running_unreal_engine(studio):
    client, launcher = studio.client, studio.launcher
    game, engine, sandbox = running_unreal(studio)
    path = f"/home/ubuntu/workspace/projects/{game['id']}/OldRidge/OldRidge.uproject"
    newer = uproject(f"/home/ubuntu/workspace/projects/{game['id']}/Next/Next.uproject", "5.9", not_fetched=9)
    launcher.uprojects[sandbox] = [uproject(path, "5.4"), newer, "not a project"]
    route = f"/v1/projects/{game['id']}/engines/{engine['id']}/unreal-projects"
    project, later = client.get(route, headers=auth("alice-token")).json()["projects"]
    assert project["version"] == "older" and "agent's branch" in project["opens"]
    assert project["cpp_modules"] == ["EmberRidge"] and project["size_bytes"] == 2_400_000_000
    assert project["plugins"] == ["ModelingToolsEditorMode", "RidgeTools", "Wwise", "VoxelPro"]
    assert project["plugins_to_check"] == ["Wwise", "VoxelPro"], "binaries only, and a marketplace plugin the repository lacks"
    assert project["lfs"] is True
    assert (later["name"], later["version"]) == ("Next", "newer")
    assert later["lfs"] == "used, but 9 of its 109 files are not fetched yet", "pointers the editor cannot open"
    assert client.get(route, headers=auth("bob-token")).status_code == 404
    client.delete(f"/v1/sessions/{engine['id']}", headers=auth("alice-token"))
    assert client.get(route, headers=auth("alice-token")).status_code == 409, "a stopped engine has no workspace to read"


def test_a_project_opens_as_the_version_it_was_saved_with_says():
    verdicts = {saved: unreal.version_verdict(saved, "5.8")[0] for saved in ("5.8", "5.4", "4.27", "5.9", "6.0", "{0A1B2C3D}", "")}
    assert verdicts == {
        "5.8": "same", "5.4": "older", "4.27": "older", "5.9": "newer", "6.0": "newer", "{0A1B2C3D}": "source", "": "unknown",
    }


def test_a_sealed_token_opens_only_under_its_secret():
    sealed = seal(SECRET, "gho_token")
    assert unseal(SECRET, sealed) == "gho_token" and unseal("another", sealed) is None


# The agent's parts


def test_tags_become_their_references_names_longest_first():
    labels = {"@mara": "@Image1", "@mara-young": "@Image2"}
    assert replace_tags("@Mara meets @mara-young; @mara.", labels) == "@Image1 meets @Image2; @Image1."


def test_every_tool_says_how_it_looks_whether_it_only_reads_and_whether_the_person_approves_it(studio, tmp_path):
    client, model = studio.client, studio.model
    known = {activity["id"] for activity in CATALOG.data["activities"]}
    assert all(definition["activity"] in known for definition in TOOLS) and all(built_in.activity in known for built_in in BUILT_INS.values())
    assert {name for name, definition in SPECS.items() if definition["approval"] == "ask"} == {"engine_start", "generate_video"}
    assert {name for name, definition in SPECS.items() if definition["read_only"]} == {
        "library_list", "library_look", "engine_list", "engine_files", "github_read", "unreal_assets", "unreal_projects"}
    assert [name for name, definition in SPECS.items() if definition["main_only"]] == ["ask_user", "show_ui"]
    fewer = tmp_path / "catalog.json"
    fewer.write_text(json.dumps({**CATALOG.data, "activities": [a for a in CATALOG.data["activities"] if a["id"] != "creating"]}))
    with pytest.raises(ValueError, match="generate_image"):
        check_activities(Catalog(fewer))

    # The loop is served each tool with its schema, told which only read, and keeps every result in the conversation
    film = new_project(client, asks=True)
    model.script(reply(say("Hello.")))
    message(client, film["id"], "Hi")
    served = model.clients[0].tools
    assert list(served) == [f"{PREFIX}{name}" for name in TOOL_NAMES]
    listing, stopping = served[f"{PREFIX}library_list"], served[f"{PREFIX}engine_stop"]
    assert listing["inputSchema"] == SPECS["library_list"]["input_schema"] and listing["description"] == SPECS["library_list"]["description"]
    assert listing["annotations"]["readOnlyHint"] is True and stopping["annotations"]["readOnlyHint"] is False
    assert all(tool["_meta"]["anthropic/maxResultSizeChars"] >= 100000 for tool in served.values()), "no result is put in a file the agent cannot read"
    allowed = model.options[0].allowed_tools
    assert f"{PREFIX}library_upsert" in allowed and "WebSearch" in allowed and "WebFetch" in allowed
    assert f"{PREFIX}engine_start" not in allowed and f"{PREFIX}generate_video" not in allowed, "what the person approves is not run unasked"


def test_the_loop_is_configured_by_the_deployment_and_keeps_none_of_its_own_file_or_shell_tools(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    with_config(studio, agent_model="claude-opus-5-5", agent_effort="max", agent_fallback_model="claude-sonnet-5-5",
                turn_budget_usd=2.5, turn_limit=40)
    model.script(reply(say("Hello.")), reply(say("Hello again.")))
    message(client, film["id"], "Hi")
    options = model.options[0]
    assert options.tools == ["Agent", "WebSearch", "WebFetch", "Skill", "Read"], "no shell, and no tool that writes a file"
    assert (options.model, options.effort, options.fallback_model, options.max_budget_usd, options.max_turns) == (
        "claude-opus-5-5", "max", "claude-sonnet-5-5", 2.5, 40)
    assert options.thinking == {"type": "adaptive", "display": "summarized"}, "the model's reasoning comes back summarized, for the page"
    assert options.permission_mode == "default" and options.setting_sources == ["project"] and options.strict_mcp_config
    assert options.verbatim_prompts, "the person's words are never read as a command of the loop or a file to attach"
    assert options.include_partial_messages and options.forward_subagent_text and options.session_store_flush == "eager"
    assert options.disallowed_tools == ["Agent(fork)"] and options.cwd == str(studio.tmp / "loop" / film["id"])

    with_config(studio, agent_model="", agent_thinking=False, agent_fallback_model="")
    message(client, film["id"], "Hi")
    options = model.options[1]
    assert (options.model, options.fallback_model) == ("claude-fable-5-2", None)
    assert options.thinking == {"type": "disabled"}

    with_config(studio, agent_effort="enormous")
    message(client, film["id"], "Hi")
    assert kinds(client, film["id"])[-2:] == ["error", "turn_end"], "an effort the loop does not know is the deployment's mistake, and the turn says it failed"


def test_the_loops_process_is_started_with_the_key_and_the_turns_own_directories_and_nothing_else_of_the_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_never")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "as-never")
    monkeypatch.setenv("FAL_KEY", "fal-never")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.test:3128")
    settings = Settings(key="sk-ant-test", model="claude-fable-5-2", effort="high", thinking=True, fallback_model="", budget_usd=1.0,
                        turn_limit=10, base_url="http://127.0.0.1:9", passed=frozenset({"HTTPS_PROXY", "NOT_SET_ANYWHERE"}), cli="")
    with Workspace(str(tmp_path / "loop"), "project-1") as workspace:
        variables = child_environment(settings, workspace)
        assert variables["ANTHROPIC_API_KEY"] == "sk-ant-test" and variables["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:9"
        assert variables["HTTPS_PROXY"] == "http://proxy.example.test:3128" and "NOT_SET_ANYWHERE" not in variables
        private = workspace.config.parent
        assert {variables["HOME"], variables["CLAUDE_CONFIG_DIR"], variables["TMPDIR"]} == {str(private / name) for name in ("home", "config", "tmp")}
        assert workspace.directory == tmp_path / "loop" / "project-1" and private != workspace.directory

        # The SDK starts its program with the worker's whole environment under these; the launcher lets only these through
        own = {"CLAUDE_CODE_ENTRYPOINT": "sdk-py", "CLAUDE_AGENT_SDK_VERSION": "0.0.0", "CLAUDE_CODE_SDK_READS_SESSION_STATE": "1",
               "PWD": str(workspace.directory)}
        assert set(own) == set(SDK_VARIABLES)
        handed = {**os.environ, **variables, **own, "CLAUDECODE": "1", "CLAUDE_CODE_OAUTH_TOKEN": "oauth-never"}
        assert handed["SUPABASE_SECRET_KEY"] == "sb_secret_never"
        launcher = workspace.launcher("/usr/bin/env", [*variables, *SDK_VARIABLES])
        printed = subprocess.run([launcher], env=handed, cwd=workspace.directory, capture_output=True, text=True, check=True).stdout
        seen = dict(line.split("=", 1) for line in printed.splitlines())
        assert seen == {**{name: value for name, value in variables.items() if name != "MOODY_LOOP_TURN"}, **own}
        assert "never" not in printed and "MODAL_TOKEN_SECRET" not in seen and "FAL_KEY" not in seen
        assert "sk-ant-test" not in Path(launcher).read_text(), "the launcher names variables; no value is written to a file"
        echoed = subprocess.run([workspace.launcher("/bin/echo", ["HOME"]), "--resume=x", "a b"], env=handed, capture_output=True, text=True, check=True)
        assert echoed.stdout == "--resume=x a b\n", "what the SDK passes its program reaches it unchanged"
        # Started outside the turn, as the SDK does once to ask the program's version, it hands over nothing at all
        outside = {**handed, "MOODY_LOOP_TURN": "another-turn"}
        launcher = workspace.launcher("/usr/bin/env", [*variables, *SDK_VARIABLES])
        assert subprocess.run([launcher], env=outside, capture_output=True, text=True, check=True).stdout == ""
        with pytest.raises(ValueError):
            workspace.launcher("/usr/bin/env", ["HOME; rm -rf /"])
    assert not workspace.directory.exists() and not private.exists(), "a turn leaves nothing on the machine it ran on"


def test_an_answer_is_shown_while_it_is_written_about_once_a_second_and_then_whole():
    shown: list[tuple[str, dict[str, Any]]] = []
    now = [100.0]

    async def emit(kind: str, data: dict[str, Any]) -> None:
        shown.append((kind, data))

    async def play() -> None:
        blocks = Blocks(emit, lambda: now[0])
        await blocks.stream({"type": "message_start", "message": {"id": "msg_1"}})
        await blocks.stream({"type": "content_block_start", "index": 0, "content_block": {"type": "thinking"}})
        for word in ("Looking ", "at ", "the ", "library ", "first."):
            now[0] += 0.4
            await blocks.stream({"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": word}})
        await blocks.stream({"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "sig"}})
        await blocks.finished("msg_1", "thinking", "Looking at the library first.")
        await blocks.stream({"type": "content_block_stop", "index": 0})
        await blocks.stream({"type": "content_block_start", "index": 1, "content_block": {"type": "text"}})
        await blocks.stream({"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "On it."}})
        await blocks.finished("msg_1", "text", "On it.")
        await blocks.stream({"type": "content_block_stop", "index": 1})
        await blocks.stream({"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use"}})
        await blocks.stream({"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "{}"}})
        await blocks.stream({"type": "content_block_stop", "index": 2})
        # A stream cut before its block was reported whole still ends with what was written
        await blocks.stream({"type": "message_start", "message": {"id": "msg_2"}})
        await blocks.stream({"type": "content_block_start", "index": 0, "content_block": {"type": "text"}})
        await blocks.stream({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Cut sh"}})
        await blocks.stream({"type": "content_block_stop", "index": 0})
        # And an answer that was never streamed is a block of its own
        await blocks.finished("msg_3", "text", "Not streamed.")
        await blocks.finished("msg_3", "text", "   ")

    anyio.run(play)
    assert shown == [
        ("thinking", {"text": "Looking at the ", "block": "msg_1:0", "partial": True}),
        ("thinking", {"text": "Looking at the library first.", "block": "msg_1:0"}),
        ("text", {"text": "On it.", "block": "msg_1:1"}),
        ("text", {"text": "Cut sh", "block": "msg_2:0"}),
        ("text", {"text": "Not streamed.", "block": "msg_3:whole-1"}),
    ], "a later event of a block replaces the earlier one, and the last is the whole block"


def test_the_transcript_store_keeps_the_sdks_contract_and_one_projects_rows_from_anothers():
    async def check() -> None:
        await run_session_store_conformance(lambda: Transcript(FakeStore(), "project-a"))
        store = FakeStore()
        ours, theirs = Transcript(store, "project-a"), Transcript(store, "project-b")
        key = {"project_key": "-tmp-loop-project-a", "session_id": "0b0c4f0e-0000-4000-8000-000000000001"}
        first, title = {"type": "user", "uuid": "u-1", "message": {"role": "user", "content": "Hi"}}, {"type": "custom-title", "title": "Mara"}
        await ours.append(key, [first, first, title, title])
        await ours.append(key, [first])
        assert await ours.load(key) == [first, title, title], "an entry is kept once by its uuid, and one without a uuid always"
        assert ours.has(key) and not theirs.has(key) and await theirs.load(key) is None
        assert await theirs.list_sessions(key["project_key"]) == [] and [s["session_id"] for s in await ours.list_sessions(key["project_key"])] == [key["session_id"]]
        store.delete("projects", id="eq.none")
        assert all(row["project_id"] == "project-a" for row in store.tables["agent_transcripts"].values())

    anyio.run(check)


def test_a_projects_skills_are_offered_by_name_and_read_with_their_reference_files_when_the_work_calls_for_them(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    opening = use("skill", skill="filmcraft")
    during: dict[str, Any] = {}

    def follow_the_skill(request: dict[str, Any]) -> Reply:
        text = tool_results(request)[opening["id"]]["content"]
        base = re.search(r"Base directory for this skill: (\S+)", text).group(1)
        offered = Path(request["options"].cwd) / ".claude" / "skills"
        during.update(text=text, folders=sorted(path.name for path in offered.iterdir()), base=base, offered=str(offered))
        return reply(
            use("read", file_path=f"{base}/references/color.md"),
            use("read", file_path="references/color.md"),
            use("read", file_path="/etc/hostname"),
            use("read", file_path=f"{base}/../../../../../../etc/hostname"),
            use("read", file_path=str(studio.tmp / "skills" / "songwriting" / "SKILL.md")),
            use("skill", skill="songwriting"),
            use("web_fetch", url="http://169.254.169.254/latest/meta-data/"),
            use("web_fetch", url="https://example.com/lighthouses"),
            use("web_search", query="lighthouse films"),
        )

    model.script(reply(opening), follow_the_skill, reply(say("Done.")))
    message(client, film["id"], "Grade the film")
    options = model.options[0]
    assert options.skills == ["filmcraft", "studio-basics"], "a Media project is offered its discipline's skills and the general ones"
    assert during["folders"] == ["filmcraft", "studio-basics"] and during["base"] == f"{during['offered']}/filmcraft"
    assert "FILMCRAFT-SKILL-TEXT" in during["text"] and "FILMCRAFT-REFERENCE-TEXT" not in during["text"], "a reference is read when the text sends the agent to it"
    results = list(tool_results(model.requests[2]).values())
    assert "FILMCRAFT-REFERENCE-TEXT" in results[0]["content"] and not results[0].get("is_error")
    assert all(r["is_error"] and "Only the files of a skill can be read" in r["content"] for r in results[1:5]), results[1:5]
    assert results[5]["is_error"], "a skill the project is not offered is not opened"
    assert results[6]["is_error"] and "Only public web addresses" in results[6]["content"]
    assert not results[7].get("is_error") and not results[8].get("is_error")
    shown = tools_shown(client, film["id"])
    assert [title for title, _, _ in shown] == [
        "Opening the filmcraft skill", "Reading color.md", "Opening the songwriting skill",
        "Reading example.com", "Searching the web for lighthouse films",
    ], "a read or a fetch that is refused never starts"
    starts = [e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "tool_start"]
    assert [(start["tool"], start["activity"]) for start in starts][:2] == [("skill", "analyzing"), ("read", "analyzing")]
    assert not (studio.tmp / "loop" / film["id"]).exists(), "the working directory goes when the turn does"

    # The same checks, as the functions that make them
    root = studio.tmp / "skills"
    assert inside("filmcraft/references/color.md", root, root) and inside(str(root / "filmcraft" / "SKILL.md"), root, Path("/"))
    assert not inside("../agents/research.md", root, root) and not inside(str(root), root, root) and not inside("/etc/passwd", root, root)
    (root / "escape").symlink_to("/etc")
    assert not inside("escape/hostname", root, root), "a link out of the skills is followed before the check"
    assert fetchable("https://example.com/a") and fetchable("http://8.8.8.8/")
    assert not any(map(fetchable, ("http://localhost:8000/", "http://127.0.0.1/", "http://10.1.2.3/", "http://[::1]/", "file:///etc/passwd",
                                    "http://169.254.169.254/", "https://metadata.internal/", "ftp://example.com/", "http://intranet/", "")))


# A test that takes real media (`media` in `conftest.py`) and has the worker make pictures of it
looks = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg, which makes the pictures the agent looks at, is not installed here")


def jpeg_size(data: bytes) -> tuple[int, int]:
    """A JPEG's width and height, from its frame header."""
    assert data[:2] == b"\xff\xd8", "not a JPEG"
    at = 2
    while at < len(data):
        marker, length = data[at + 1], int.from_bytes(data[at + 2 : at + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(data[at + 7 : at + 9], "big"), int.from_bytes(data[at + 5 : at + 7], "big")
        at += 2 + length
    raise AssertionError("no frame header")


def handed(content: Any) -> list[tuple[str, Any]]:
    """A result's blocks as what the model is handed: each line of text, and each picture as its width and height."""
    if isinstance(content, str):
        return [("text", content)]
    return [
        ("picture", jpeg_size(base64.b64decode(block["source"]["data"]))) if block["type"] == "image" else ("text", block["text"])
        for block in content
    ]


@looks
def test_the_agent_is_handed_pictures_of_what_it_generates_and_of_the_library_when_it_asks_to_look(studio, media):
    client, fal, model, store = studio.client, studio.fal, studio.model, studio.store
    fal.files = media
    film = new_project(client)
    sheet = use("generate_image", prompt="Mara, two ways", count=2, look=True, save_to={"section": "Characters", "name": "Mara", "tag": "@mara"})
    shot = use("generate_video", prompt="Mara climbs", duration_seconds=6, look=True, save_to={"section": "Shots", "name": "Climb", "tag": "@climb"})
    plain = use("generate_image", prompt="A lamp")
    again = use("library_look", tags=["@mara", "@climb"], each=2)
    model.script(reply(sheet), reply(shot), reply(plain), reply(again), reply(say("Seen.")))
    message(client, film["id"], "Design Mara")
    results = [tool_results(model.requests[index])[call["id"]] for index, call in enumerate((sheet, shot, plain, again), start=1)]
    assert not any(result.get("is_error") for result in results)

    made = handed(results[0]["content"])
    assert [kind for kind, _ in made] == ["text", "picture", "text", "picture", "text"]
    assert (made[0][1], made[2][1]) == ("image 1 of 2", "image 2 of 2") and made[1][1] == made[3][1] == (1280, 720), (
        "each image itself, no wider than 1280 pixels, after the line that names it"
    )
    assert "The pictures above are yours to judge by" in made[4][1] and "no_picture" not in made[4][1]
    moving = handed(results[1]["content"])
    assert moving[:2] == [("text", "video 1 of 1"), ("picture", (1280, 720))], "four frames of the video on one sheet"
    assert handed(results[2]["content"])[0][0] == "text" and len(handed(results[2]["content"])) == 1, "without look, the facts alone"
    kept = handed(results[3]["content"])
    assert [value for kind, value in kept if kind == "picture"] == [(1280, 720)] * 3
    assert [value.split(":")[0] for kind, value in kept[:-1] if kind == "text"] == ["@mara, image 1 of 2", "@mara, image 2 of 2", "@climb, video 1 of 1"]
    assert json.loads(kept[-1][1])["no_picture"] == {} and json.loads(kept[-1][1])["no_media"] == []

    log = events(client, film["id"])["events"]
    looked = next(e["data"] for e in log if e["kind"] == "tool_start" and e["data"]["tool"] == "library_look")
    assert (looked["title"], looked["activity"]) == ("Looking at @mara, @climb", "analyzing")
    after = [e["kind"] for e in log[next(i for i, e in enumerate(log) if e["data"].get("call_id") == looked["call_id"]) :]]
    assert after == ["tool_start", "tool_end", "text", "usage", "turn_end"], "looking shows the person nothing new"
    assert next(e["data"] for e in log if e["kind"] == "tool_end" and e["data"]["call_id"] == looked["call_id"])["summary"] == "Looked at 3 files"

    # What cannot be looked at is said, with why, and the rest still is
    store.files[next(path for path in store.files if "climb" in path)] = (b"not a video at all", "video/mp4")
    client.post(f"/v1/projects/{film['id']}/library", headers=auth("alice-token"), json={"section": "Props", "name": "Lamp", "tag": "@lamp"})
    some, none, many, lost = (
        use("library_look", tags=["@climb", "@mara", "@lamp"]),
        use("library_look", tags=["@lamp"]),
        use("library_look", tags=["@mara"] * 5, each=2),
        use("library_look", tags=["@nobody"]),
    )
    model.script(reply(some, none, many, lost), reply(say("Seen.")))
    message(client, film["id"], "Look again")
    told = tool_results(model.requests[-1])
    partly = handed(told[some["id"]]["content"])
    answer = json.loads(partly[-1][1])
    assert [kind for kind, _ in partly] == ["text", "picture", "text"] and answer["no_media"] == ["@lamp"]
    ((unmade, why),) = answer["no_picture"].items()
    assert unmade.startswith("@climb, video 1 of 1: ") and why.startswith("No picture could be made of it: ") and len(why) > 40, (
        "with what ffmpeg said of the file"
    )
    assert [label.split(":")[0] for label in answer["looked_at"]] == ["@mara, image 1 of 2"]
    assert told[none["id"]]["is_error"] and told[many["id"]]["is_error"] and "at most 8" in told[many["id"]]["content"]
    assert told[lost["id"]]["is_error"] and "No library entry is tagged @nobody" in told[lost["id"]]["content"]


def test_sound_is_generated_by_kind_shown_with_a_player_and_kept_like_pictures(studio):
    client, fal, model, store = studio.client, studio.fal, studio.model, studio.store
    film = new_project(client)
    lyrics = "[verse]\nThe lamp turns over the water\n[chorus]\nCome home, come home"
    song = use("generate_audio", kind="music", prompt="Genre: sea shanty. BPM: 96. A low male lead and a fiddle.", lyrics=lyrics, seconds=45,
               save_to={"section": "Music", "name": "The keeper's song", "tag": "@song"})
    bed = use("generate_audio", kind="music", prompt="Slow strings under a storm", instrumental=True, count=3)
    door = use("generate_audio", kind="sound", prompt="A heavy wooden door creaks open in a stone hallway", seconds=3, count=2)
    wave = use("generate_audio", kind="sound", prompt="One wave breaks on rock")
    line = use("generate_audio", kind="speech", prompt="Three cuts, one hook, and you are done.", voice="Fenrir", style="Warm, at a brisk pace.")
    plain = use("generate_audio", kind="speech", prompt="Keep the light.")
    model.script(reply(song), reply(bed), reply(door), reply(wave), reply(line), reply(plain), reply(say("Listen.")))
    message(client, film["id"], "Make the sound")

    # Each model is asked as its own page on fal says, and a take is a call
    asked = [(called, arguments) for called, arguments in fal.calls]
    assert [called for called, _ in asked] == [
        "minimax/music-3", *["minimax/music-3"] * 3, *["elevenlabs/sound-effects/v3"] * 2, "elevenlabs/sound-effects/v3",
        "google/gemini-3.8-flash-tts", "google/gemini-3.8-flash-tts"]
    assert asked[0][1] == {"prompt": "Genre: sea shanty. BPM: 96. A low male lead and a fiddle.", "lyrics": lyrics, "duration": 45}
    assert asked[1][1] == {"prompt": "Slow strings under a storm", "lyrics": "[instrumental]"}, "the model requires lyrics, so no singing is a lyric sheet of one tag"
    assert asked[4][1] == {"text": "A heavy wooden door creaks open in a stone hallway", "duration_seconds": 3} and asked[6][1] == {"text": "One wave breaks on rock"}
    assert asked[7][1] == {"prompt": "Three cuts, one hook, and you are done.", "voice": "Fenrir", "style_instructions": "Warm, at a brisk pace."}
    assert asked[8][1] == {"prompt": "Keep the light.", "voice": "Kore"}
    assert set(AUDIO_MODELS) == {"music", "sound", "speech"} and len(SPEECH_VOICES) == 30 and {"Fenrir", "Puck", "Kore", "Charon"} <= set(SPEECH_VOICES)
    assert audio_arguments("speech", "Hi", None, None, None, None) == ("google/gemini-3.8-flash-tts", {"prompt": "Hi", "voice": "Kore"})
    assert audio_units("speech", "x" * 500, None) == {"1000 character": 0.5} and audio_units("sound", "x", None) == {} and audio_units("music", "x", 42.5) == {"second": 42.5}

    # The person hears each take with a player, and what was saved is in the library
    log = events(client, film["id"])["events"]
    starts = [e["data"] for e in log if e["kind"] == "tool_start"]
    assert [start["title"] for start in starts] == [
        "Generating 1 song", "Generating 3 instrumentals", "Generating 2 sounds", "Generating 1 sound", "Generating 1 spoken line",
        "Generating 1 spoken line"]
    assert {start["activity"] for start in starts} == {"creating"} and not any(e["kind"] == "approval" for e in log)
    ends = [e["data"] for e in log if e["kind"] == "tool_end"]
    assert all(end["ok"] for end in ends), ends
    assert [[item["kind"] for item in end["media"]] for end in ends] == [["audio"], ["audio"] * 3, ["audio"] * 2, ["audio"], ["audio"], ["audio"]]
    assert all(item["url"].startswith("https://storage.example.test/") for end in ends for item in end["media"])
    assert [end["summary"] for end in ends] == [
        "1 song saved to @song, about $0.09", "3 instrumentals, about $0.26", "2 sounds, about $0.01", "1 sound", "1 spoken line, under $0.01",
        "1 spoken line, under $0.01"], "a song is costed by the seconds fal says it made, a sound by those asked for, a line by its characters"
    entry = next(e["data"]["asset"] for e in log if e["kind"] == "library")
    assert (entry["tag"], entry["section"], [item["kind"] for item in entry["media"]]) == ("@song", "Music", ["audio"])
    assert entry["media"][0]["name"].endswith(".wav") and sum("/generations/" in path for path in store.files) == 8
    told = [tool_results(model.requests[index])[call["id"]]["content"] for index, call in enumerate((song, bed, door, wave, line, plain), start=1)]
    assert "Generated 1 song. Saved to @song (Music)" in told[0] and '"seed": 41' in told[0] and '"cost_usd": 0.085' in told[0]
    assert "Generated 3 instrumentals." in told[1] and '"model": "minimax/music-3"' in told[1]
    assert '"cost_usd": null' in told[3], "a sound whose length the model chose has no estimate where fal gives none"

    # What a kind does not take is sent back before anything is paid for
    spent = len(fal.calls)
    wrong = [
        use("generate_audio", kind="music", prompt="A waltz"),
        use("generate_audio", kind="music", prompt="A waltz", lyrics="[verse]\nOne two three", instrumental=True),
        use("generate_audio", kind="sound", prompt="A bell", lyrics="[verse]\nDing"),
        use("generate_audio", kind="music", prompt="A waltz", instrumental=True, voice="Puck"),
        use("generate_audio", kind="speech", prompt="Hello.", seconds=4),
        use("generate_audio", kind="sound", prompt="rain " * 100),
        use("generate_audio", kind="sound", prompt="A bell", seconds=45),
        use("generate_audio", kind="music", prompt="A waltz", instrumental=True, seconds=301),
        use("generate_audio", kind="speech", prompt="Hello.", voice="Mara"),
        use("generate_audio", kind="noise", prompt="Hiss"),
    ]
    model.script(reply(*wrong), reply(say("Sorry.")))
    message(client, film["id"], "More")
    refused = tool_results(model.requests[-1])
    assert all(refused[call["id"]]["is_error"] for call in wrong) and len(fal.calls) == spent
    words = [refused[call["id"]]["content"] for call in wrong]
    assert "give lyrics" in words[0] and "not both" in words[1] and "lyrics and instrumental are for kind music" in words[2]
    assert "voice and style are for kind speech" in words[3] and "as long as its words" in words[4]
    assert "at most 450 characters; this one is 500" in words[5] and "from 0.5 to 30 for kind sound" in words[6] and "from 1 to 300 for kind music" in words[7]

    # A take that does not come back does not cost the person the ones that did, and one take of none fails the call
    fal.failures = [RuntimeError("fal could not generate it: busy")]
    some = use("generate_audio", kind="sound", prompt="A bell", seconds=1, count=3)
    fal_failed = RuntimeError("fal refused the request: no credit")
    none = use("generate_audio", kind="sound", prompt="A bell", seconds=1, count=2)
    model.script(reply(some), reply(none), reply(say("Two of three.")))
    message(client, film["id"], "Bells")
    partly = tool_results(model.requests[-2])[some["id"]]
    assert not partly.get("is_error") and "Generated 2 sounds." in partly["content"]
    assert "1 of 3 takes did not come back, and nothing was kept of them: fal could not generate it: busy" in partly["content"]
    fal.failures = [fal_failed, fal_failed]
    model.script(reply(none), reply(say("None.")))
    message(client, film["id"], "Again")
    assert tool_results(model.requests[-1])[none["id"]]["is_error"] and "no credit" in tool_results(model.requests[-1])[none["id"]]["content"]
    last = [e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "tool_end"]
    assert (last[-1]["ok"], "media" in last[-1]) == (False, False) and last[-3]["summary"] == "2 sounds, under $0.01; 1 failed"


def test_a_look_where_no_picture_can_be_made_says_why_and_the_generation_stands(studio, monkeypatch):
    client, model = studio.client, studio.model
    film = new_project(client)
    monkeypatch.setattr("looking.shutil.which", lambda name: None)
    call = use("generate_image", prompt="A lamp", look=True)
    model.script(reply(call), reply(say("Made.")))
    message(client, film["id"], "A lamp")
    result = tool_results(model.requests[1])[call["id"]]
    assert not result.get("is_error") and isinstance(result["content"], str), "the image was generated and is shown to the person"
    facts = json.loads(result["content"].split("\n", 1)[1])
    assert facts["no_picture"] == {"image 1 of 1": "No picture could be made of it: the machine this turn runs on has no ffmpeg"}
    assert [e["data"]["ok"] for e in events(client, film["id"])["events"] if e["kind"] == "tool_end"] == [True]


def test_the_program_that_reads_a_file_for_a_look_gets_nothing_of_the_worker(monkeypatch):
    # In place of ffmpeg, a program that writes who it runs as and what it was handed where the picture goes
    folder = Path(tempfile.mkdtemp(prefix="moody-test-look-"))
    folder.chmod(0o755)
    program = folder / "ffmpeg"
    program.write_text('#!/bin/sh\nfor last; do :; done\n{ id -u; pwd; env; echo "ARGUMENTS $*"; cat source; } > "$last"\n')
    program.chmod(0o755)
    monkeypatch.setattr("looking.shutil.which", lambda name: str(program) if name == "ffmpeg" else None)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "service-key-of-the-deployment")
    try:
        user, where, *rest = picture_of(b"THE-FILE", "image").decode().splitlines()
    finally:
        shutil.rmtree(folder)
    handed_over = [line for line in rest if "=" in line and not line.startswith("ARGUMENTS")]
    assert {line.split("=")[0] for line in handed_over} <= {"PATH", "PWD", "OLDPWD", "SHLVL", "_"}, "its environment is empty but for a PATH"
    assert "service-key-of-the-deployment" not in "\n".join(rest) and rest[-1] == "THE-FILE"
    assert "-protocol_whitelist file" in next(line for line in rest if line.startswith("ARGUMENTS")), "it reads files and nothing over the network"
    assert where.startswith(tempfile.gettempdir()) and not Path(where).exists(), "in a directory made for the one file, gone afterwards"
    if os.geteuid() == 0:
        assert user != "0", "a worker that is root runs it as another user"
    monkeypatch.setattr("looking.shutil.which", lambda name: "/bin/false")
    with pytest.raises(NoPicture, match="made nothing of it"):
        picture_of(b"THE-FILE", "image")


def test_the_system_prompt_carries_no_skill_and_says_how_the_agent_works_with_engines_approvals_and_subagents():
    skills = read_skills(skills_directory())
    project = {"id": "p", "discipline": "media", "format": "Film & TV"}
    prompt = system_prompt(CATALOG, project, frozenset({"cpu"}))
    offered = skills_for(skills, CATALOG, "media")
    assert len(offered) >= 2 and not any(skill.body[:200] in prompt for skill in offered)
    assert len(prompt) < 12000 < sum(len(skill.body) for skill in offered), "the prompt is a fraction of what the skills' texts were in it"
    flat = " ".join(prompt.split())
    for said_once in ("none starts unless the work needs it or the person asked", "The person approves some steps", "Agent tool",
                      "Skill tool", "<project_state>", "mcp__moody__<name>", "the Moody agent",
                      "Where a decision is the person's and you have a view, say which way you would go",
                      "`ask_user`'s `recommended`", "Keep interactive cards clean",
                      "A long job (many steps, subagents, or minutes of work) ends with a report",
                      "Your job is to keep the project moving", "never leave them at an empty box",
                      "A short exchange gets a short answer in plain sentences, with no headings"):
        assert flat.count(said_once) == 1, said_once
    assert "recap" not in flat and "Keep messages short" not in flat, "how to close is said once, by the kind of work it closes"
    assert "Its kinds: Film & TV, Social Media" in flat and "Kind: " not in flat, "which kind it is can change, so the state says it"

    # A project's first turn opens with its kind's card, from the skill the catalog names, where the project has that skill
    assert CATALOG.disciplines["media"]["opening_skill"] == "video" and "opening card" not in flat
    opened = " ".join(system_prompt(CATALOG, project, frozenset({"cpu"}), ["studio", "video"]).split())
    assert opened.count("open the `video` skill and show that kind's opening card from it, in place of questions in words") == 1
    assert "opening card" not in system_prompt(CATALOG, {**project, "discipline": "music"}, frozenset({"cpu"}), ["studio", "video"])


def test_subagents_are_read_from_files_offered_by_discipline_and_given_their_tools_skills_and_model(studio, tmp_path):
    client, model = studio.client, studio.model
    film, song = new_project(client), new_project(client, name="Tide", discipline="music", format="Song")
    model.script(reply(say("Hello.")), reply(say("Hello.")), reply(say("Hello.")))
    message(client, film["id"], "Hi")
    offered = model.options[0].agents
    assert list(offered) == ["research", "filmcraft", "photocraft", "nuke"], (
        "the defined ones that fit, then an operator for each of the discipline's engines that can be started"
    )
    research, operator = offered["research"], offered["filmcraft"]
    assert research.description == "Looks things up on the web and in the library." and research.model == "claude-sonnet-5-5"
    assert research.tools == [f"{PREFIX}library_list", f"{PREFIX}library_upsert", "WebSearch", "WebFetch"] and research.skills is None
    assert research.prompt.startswith("You research. RESEARCH-PROMPT") and "Your last message is your report" in research.prompt
    assert operator.description == "Drives FilmCraft for one job in a running engine." and operator.model == "inherit"
    assert operator.prompt.startswith("You operate FilmCraft (app `filmcraft`). OPERATOR-PROMPT") and operator.skills == ["filmcraft"]
    driving = [name for name in TOOL_NAMES if name.startswith("engine_") or name == "preview"]
    assert operator.tools == [f"{PREFIX}{name}" for name in TOOL_NAMES if name in (*driving, "filmcraft", "library_list")] + ["Read"], (
        "the template's tools, then those the engine's skill names for its operator"
    )
    unskilled = offered["photocraft"]
    assert unskilled.skills is None and unskilled.tools == [f"{PREFIX}{name}" for name in driving], "an engine without a skill has an operator that reads none"
    assert unskilled.prompt.startswith("You operate PhotoCraft (app `photocraft`). OPERATOR-PROMPT"), "a definition's opening comment is not in its prompt"
    assert unskilled.description == "Drives PhotoCraft for one job in a running engine."

    with_config(studio, agent_model_balanced="claude-opus-5-5", agent_model_light="claude-haiku-5-5")
    message(client, song["id"], "Hi")
    offered = model.options[1].agents
    assert list(offered) == ["lyricist", "research", "soundcraft"] and offered["research"].model == "claude-opus-5-5"
    lyricist = offered["lyricist"]
    assert lyricist.model == "claude-haiku-5-5" and lyricist.skills == ["songwriting"]
    assert lyricist.tools == [f"{PREFIX}library_list", f"{PREFIX}library_look", f"{PREFIX}library_upsert", "Read"]

    # A project with no subagent to offer is offered none, and the definitions say so themselves where they are wrong
    bare = Agent(studio.sessions, model, None, studio.agent.skills)
    studio.jobs.agent = bare
    message(client, film["id"], "Hi")
    assert model.options[2].agents is None
    listed = read_agents(studio.tmp / "agents")
    assert [agent.name for agent in listed] == ["lyricist", "research"], "a template and a file without front matter define nothing"
    derived = operators(studio.tmp / "agents", CATALOG, studio.agent.skills)
    assert [agent.name for agent in derived] == [app["id"] for app in CATALOG.data["apps"] if app["status"] in ("available", "byol", "team")], (
        "every app that can be started has an operator"
    )
    assert operators(tmp_path, CATALOG, studio.agent.skills) == [], "without the template there are no operators"
    assert [a.name for a in agents_for(listed, [], studio.agent.skills, CATALOG, "games")] == ["research"]
    assert [a.name for a in agents_for(listed, derived, [], CATALOG, "games")] == ["research", "blender", "unreal"]
    assert [a.name for a in agents_for([], derived, studio.agent.skills, CATALOG, "writing")] == ["filmcraft"], (
        "an operator is offered with its engine's skill too, where the discipline has no such engine"
    )
    (tmp_path / "wrong.md").write_text("---\nname: other\ndescription: x\n---\nprompt")
    with pytest.raises(ValueError, match="file's stem"):
        read_agents(tmp_path)
    (tmp_path / "wrong.md").write_text("---\nname: wrong\ndescription: x\nmodel: enormous\n---\nprompt")
    with pytest.raises(ValueError, match="model tier"):
        read_agents(tmp_path)
    assert matching(("engine_*", "preview"), TOOL_NAMES)[0] == "engine_start"
    with pytest.raises(ValueError, match="no tool is named engine_teleport"):
        matching(("engine_teleport",), TOOL_NAMES)
    asking = AgentSpec("asker", "Asker", "Asks.", frozenset({"all"}), ("ask_user",), (), "inherit", "Ask.")
    with pytest.raises(ValueError, match="no tool is named ask_user"):
        Agent(studio.sessions, model, None, studio.agent.skills, [asking])
    reading = AgentSpec("reader", "Reader", "Reads.", frozenset({"all"}), ("library_list",), ("typography",), "inherit", "Read.")
    with pytest.raises(ValueError, match="reader names skills there are none of: typography"):
        Agent(studio.sessions, model, None, studio.agent.skills, [reading])


def test_the_subagents_and_skills_of_the_repository_load_and_name_only_tools_the_agent_has(studio):
    skills = read_skills(skills_directory())
    agent = Agent.for_deployment(studio.sessions)
    assert agent.loop.__name__ == "sdk_loop" and [skill.name for skill in agent.skills] == [skill.name for skill in skills]
    for discipline in CATALOG.disciplines:
        offered = agent.subagents({"discipline": discipline}, skills_for(skills, CATALOG, discipline))
        assert all(subagent.description and subagent.prompt for subagent in offered), discipline
        assert not any("ask_user" in subagent.tools for subagent in offered)


def test_a_subagents_steps_show_in_the_conversation_and_its_card_follows_what_it_does(studio):
    client, model, store = studio.client, studio.model, studio.store
    film = new_project(client)
    films = use("Agent", subagent_type="research", description="Find lighthouse films", prompt="Find three films set in lighthouses.")
    survey = use("Agent", subagent_type="research", description="Survey the library", prompt="List what the library holds.")
    search, listing, broken = use("web_search", query="lighthouse films"), use("library_list"), use("library_upsert", name="No section")
    model.script(reply(say("Two jobs out."), films, survey), reply(say("Both are back.")))
    model.script_agent(
        "research",
        reply({"type": "thinking", "thinking": "Where to look.", "signature": "s"}, say("Searching the web."), search),
        reply(say("REPORT: three films.")),
        reply(listing, broken, use("engine_start", app="filmcraft", tier="cpu")),
        reply(say("REPORT: the library is empty.")),
    )
    message(client, film["id"], "Research lighthouses")
    log = events(client, film["id"])["events"]
    cards = [e["data"] for e in log if e["kind"] == "agent"]
    first, second = dict.fromkeys(card["agent_id"] for card in cards)
    assert {card["group"] for card in cards} == {cards[0]["group"]}, "the subagents one step started share a group"
    assert cards[0] == {"agent_id": first, "group": cards[0]["group"], "name": "research", "title": "Research agent",
                        "task": "Find lighthouse films", "state": "working", "activity": "thinking", "detail": ""}
    assert [card["agent_id"] for card in cards[:2]] == [first, second], "both cards are there before either works"
    told = [(card["state"], card["activity"], card["detail"]) for card in cards if card["agent_id"] == first]
    assert told[1:] == [
        ("working", "thinking", "Thinking"), ("working", "thinking", "Searching the web."),
        ("working", "searching", "Searching the web for lighthouse films"), ("working", "searching", "Searching the web for lighthouse films"),
        ("working", "thinking", "REPORT: three films."), ("completed", "satisfied", "REPORT: three films."),
    ]
    last = [card for card in cards if card["agent_id"] == first][-1]
    assert last["seconds"] > 0 and last["tokens"] > 0
    activities = [card["activity"] for card in cards if card["agent_id"] == second]
    assert "confused" in activities and activities[-1] == "satisfied", "a call that failed shows, and so does the end"

    theirs = [e for e in log if e["data"].get("agent_id") == first and e["kind"] != "agent"]
    assert [(e["kind"], e["data"].get("text") or e["data"].get("tool") or e["data"].get("ok")) for e in theirs] == [
        ("thinking", "Where to look."), ("text", "Searching the web."), ("tool_start", "web_search"), ("tool_end", True),
        ("text", "REPORT: three films."),
    ]
    ends = {e["data"]["call_id"]: e["data"] for e in log if e["kind"] == "tool_end"}
    assert ends[listing["id"]]["agent_id"] == second and ends[listing["id"]]["ok"] and not ends[broken["id"]]["ok"]
    own = [e["data"] for e in log if e["kind"] == "text" and "agent_id" not in e["data"]]
    assert [data["text"] for data in own] == ["Two jobs out.", "Both are back."], "the subagents' reports are the agent's to tell, not the person's to read"
    assert not any(e["data"].get("tool") == "Agent" for e in log), "a subagent is a card, not a tool call"
    assert next(e["data"] for e in log if e["kind"] == "usage")["agents"] == 2

    # Each subagent worked in a conversation of its own, with its own prompt, tools, and model, and only its report came back
    asked = [r for r in model.requests if r["agent"] == "research"]
    assert asked[0]["messages"] == [{"role": "user", "content": "Find three films set in lighthouses."}]
    assert asked[0]["system"][0]["text"].startswith("You research. RESEARCH-PROMPT") and asked[0]["model"] == "claude-sonnet-5-5"
    assert asked[0]["tools"] == [f"{PREFIX}library_list", f"{PREFIX}library_upsert", "WebSearch", "WebFetch"]
    refused = tool_results(asked[3])
    assert "No such tool" in refused[next(reversed(refused))]["content"], "a subagent has only the tools its definition lists"
    back = tool_results(model.requests[-1])
    assert "REPORT: three films." in back[films["id"]]["content"] and "REPORT: the library is empty." in back[survey["id"]]["content"]
    assert "Searching the web." not in json.dumps(model.requests[-1]["messages"])
    kept = {row["subpath"] for row in store.tables["agent_transcripts"].values()}
    assert kept == {"", f"subagents/agent-{first}", f"subagents/agent-{second}"}, "a subagent's transcript is kept beside the session's"

    # A tool kept to the agent itself is refused to a subagent, whatever its definition came to list
    turn = SimpleNamespace(beat=lambda: True, acting=lambda agent_id: nullcontext(), event=lambda kind, data: None)
    refusal = studio.agent.run_tool(turn, "ask_user", {"question": "Which?", "options": ["A", "B"], "recommended": "A"}, "call_1", first)
    assert not refusal.ok and "Only the agent itself can use ask_user" in refusal.content


def answering(studio: SimpleNamespace, project_id: str, decision: str) -> threading.Thread:
    """Answer the next approval the project's agent asks for, as the person would while the turn waits.

    It answers as soon as the approval is in the log. The bound is only for
    a turn that never asks, and is long because a loaded machine starts the
    loop's program slowly.
    """

    def answer() -> None:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            rows = [e for e in list(studio.store.tables["project_events"].values()) if e["project_id"] == project_id]
            answered = {e["data"]["approval_id"] for e in rows if e["kind"] == "approval_result"}
            waiting = [e["data"]["approval_id"] for e in rows if e["kind"] == "approval" and e["data"]["approval_id"] not in answered]
            if waiting:
                assert studio.sessions.answer_approval(ALICE, project_id, waiting[0], decision) is True
                return
            time.sleep(0.005)

    thread = threading.Thread(target=answer)
    thread.start()
    return thread


def test_a_step_the_person_approves_waits_for_their_answer_once_always_or_no(studio):
    client, model, store = studio.client, studio.model, studio.store
    store.moody_ensure_profile(ALICE.id, ALICE.email, 60)["max_sessions"] = 5
    film = new_project(client, asks=True)
    assert film["permissions"] == {}
    base = f"/v1/projects/{film['id']}"
    start = lambda: use("engine_start", app="filmcraft", tier="cpu")

    # Once: the call runs, and the next one is asked about again
    first = start()
    model.script(reply(say("Opening FilmCraft."), first), reply(say("It runs.")))
    waiter = answering(studio, film["id"], "once")
    message(client, film["id"], "Cut the film")
    waiter.join()
    log = events(client, film["id"])["events"]
    assert [e["kind"] for e in log] == ["user_message", "text", "tool_start", "approval", "approval_result", "engine", "engine",
                                         "tool_end", "text", "usage", "turn_end"]
    asked = next(e["data"] for e in log if e["kind"] == "approval")
    assert asked == {"approval_id": asked["approval_id"], "tool": "engine_start", "title": "Starting FilmCraft",
                     "detail": "Starter: 1 credit a minute until it is stopped."}
    assert next(e["data"] for e in log if e["kind"] == "approval_result") == {"approval_id": asked["approval_id"], "decision": "once"}
    assert not tool_results(model.requests[1])[first["id"]].get("is_error") and len(studio.launcher.started) == 1
    assert client.get(base, headers=auth("alice-token")).json()["project"]["permissions"] == {}

    # An approval is answered once, by a decision there is, of an approval there was, by its project's person
    again = lambda aid, decision, token="alice-token": client.post(f"{base}/approvals/{aid}", headers=auth(token), json={"decision": decision})
    assert again(asked["approval_id"], "deny").json() == {"recorded": False}, "the first answer stands"
    assert again(asked["approval_id"], "maybe").status_code == 400 and again("no-such-approval", "once").status_code == 404
    assert again(asked["approval_id"], "once", "bob-token").status_code == 404

    # No: nothing runs, and the model is told not to try again
    second = start()
    model.script(reply(second), reply(say("Then I will not.")))
    waiter = answering(studio, film["id"], "deny")
    message(client, film["id"], "Open another")
    waiter.join()
    told = tool_results(model.requests[-1])[second["id"]]
    assert told["is_error"] and "The person declined" in told["content"] and len(studio.launcher.started) == 1
    ends = [e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "tool_end"]
    assert (ends[-1]["ok"], ends[-1]["summary"]) == (False, "Not approved")

    # Always: kept for that tool in that project, so the next call is not asked about, in this turn or a later one
    third, fourth, fifth = start(), start(), start()
    model.script(reply(third), reply(fourth), reply(say("Two more run.")), reply(fifth), reply(say("And one more.")))
    waiter = answering(studio, film["id"], "always")
    message(client, film["id"], "Open two")
    waiter.join()
    assert client.get(base, headers=auth("alice-token")).json()["project"]["permissions"] == {"engine_start": "always"}
    assert f"{PREFIX}engine_start" not in model.options[-1].allowed_tools, "the turn began before the person said always"
    message(client, film["id"], "And one more")
    assert f"{PREFIX}engine_start" in model.options[-1].allowed_tools and f"{PREFIX}generate_video" not in model.options[-1].allowed_tools
    assert "The person no longer wants to be asked before: engine_start" in said(model.requests[-1])[1]
    assert kinds(client, film["id"]).count("approval") == 3 and len(studio.launcher.started) == 4

    # The person takes it back in the Environment panel, and is asked again
    patch = lambda permissions: client.patch(base, headers=auth("alice-token"), json={"permissions": permissions})
    assert patch({}).json()["project"]["permissions"] == {}
    for wrong in ({"engine_start": "never"}, {"Engine Start": "always"}, {"engine_start": True}):
        assert patch(wrong).status_code == 400, wrong
    assert patch({"generate_video": "always"}).json()["project"]["permissions"] == {"generate_video": "always"}

    # No answer in time: the approval is recorded as expired, which stands, and the model is told to end its turn and ask
    with_config(studio, approval_seconds=0.05)
    sixth = start()
    model.script(reply(sixth), reply(say("I wanted to open FilmCraft to cut the film. Say when to go ahead.")))
    message(client, film["id"], "Open it")
    log = events(client, film["id"])["events"]
    expired = [e["data"] for e in log if e["kind"] == "approval_result"][-1]
    assert expired["decision"] == "expired" and again(expired["approval_id"], "once").json() == {"recorded": False}
    told = tool_results(model.requests[-1])[sixth["id"]]
    assert told["is_error"] and "did not answer in time" in told["content"] and "End your turn now" in told["content"]
    assert len(studio.launcher.started) == 4 and log[-1]["kind"] == "turn_end"

    # A turn the person stops while it waits is over at once
    with_config(studio, approval_seconds=30)
    model.script(reply(start()))
    stopper = threading.Timer(0.1, lambda: client.post(f"{base}/stop", headers=auth("alice-token")))
    stopper.start()
    studio.agent.heartbeat_seconds = 0.02
    began = time.monotonic()
    message(client, film["id"], "Open it")
    stopper.join()
    assert time.monotonic() - began < 10 and events(client, film["id"])["running"] is False
    assert kinds(client, film["id"])[-2:] == ["usage", "turn_end"] and len(studio.launcher.started) == 4


def test_a_subagents_step_is_approved_by_the_person_as_the_agents_own_is(studio):
    client, model = studio.client, studio.model
    film = new_project(client, asks=True)
    job = use("Agent", subagent_type="filmcraft", description="Cut the teaser", prompt="Open FilmCraft and cut the teaser.")
    model.script(reply(job), reply(say("The teaser is cut.")))
    model.script_agent("filmcraft", reply(use("engine_start", app="filmcraft", tier="cpu")), reply(say("REPORT: cut.")))
    waiter = answering(studio, film["id"], "once")
    message(client, film["id"], "Cut a teaser")
    waiter.join()
    log = events(client, film["id"])["events"]
    card = next(e["data"] for e in log if e["kind"] == "agent")
    asked, answered = (next(e["data"] for e in log if e["kind"] == kind) for kind in ("approval", "approval_result"))
    assert asked["agent_id"] == card["agent_id"] == answered["agent_id"] and card["title"] == "FilmCraft agent"
    assert all(e["data"]["agent_id"] == card["agent_id"] for e in log if e["kind"] == "engine"), "what a subagent's tool writes is marked as its own"
    assert len(studio.launcher.started) == 1


def test_a_turn_that_would_end_with_engines_open_is_told_so_once(studio):
    client, model = studio.client, studio.model
    model.stop_hooks = True
    film = new_project(client)
    model.script(reply(say("All done.")))
    message(client, film["id"], "Hello")
    assert len(model.requests) == 1, "with no engine open a turn just ends"

    engine = start_engine(studio, film["id"])
    model.script(reply(say("The cut is done.")), reply(say("FilmCraft stays open: you are still watching the cut.")))
    message(client, film["id"], "Cut it")
    nudge = model.requests[-1]["messages"][-1]["content"]
    assert nudge.startswith("Stop hook feedback:") and f"- {engine['id']}: FilmCraft, running" in nudge
    assert "engine_stop" in nudge and "say in one line why" in nudge
    assert len(model.requests) == 3, "the model is told once, and then the turn ends whatever it answers"

    stop = use("engine_stop", engine_id=engine["id"])
    model.script(reply(say("Done.")), reply(stop), reply(say("Stopped FilmCraft.")))
    message(client, film["id"], "Finish")
    assert studio.launcher.stopped == ["sb-1"] and len(model.requests) == 6


def test_a_message_can_lock_in_a_card_the_agent_showed_and_the_model_reads_which_and_with_what(studio):
    client, model, store = studio.client, studio.model, studio.store
    film, other = new_project(client), new_project(client, name="Other")
    post = lambda body, project=film: client.post(f"/v1/projects/{project['id']}/messages", headers=auth("alice-token"), json=body)
    card = {"ui_id": "ui-grade", "title": "Pick a grade", "kind": "components", "spec": {}, "submit": "Lock in", "waits": True, "media": []}
    store.insert("project_events", {"project_id": film["id"], "kind": "ui", "data": card})
    value = {"contrast": 0.65, "look": "Kodak 2383", "layers": ["grain"]}
    jobs, studio.jobs.agent = studio.jobs.agent, None
    refusals = [
        (post({"text": "", "ui": {"ui_id": "ui-nope", "value": value}}), 404),
        (post({"text": "", "ui": {"ui_id": "ui-grade", "value": value}}, other), 404),
        (post({"text": "", "ui": {"ui_id": "ui-grade"}}), 400),
        (post({"text": "", "ui": {"value": value}}), 400),
        (post({"text": "", "ui": {"ui_id": "ui-grade", "value": "x" * 70000}}), 413),
        (post({"text": "  "}), 400),
    ]
    assert [response.status_code for response, _ in refusals] == [status for _, status in refusals], [r.text for r, _ in refusals]
    assert studio.jobs.turns == []
    studio.jobs.agent = jobs

    model.script(reply(say("Grading with that.")), reply(say("Noted.")))
    assert post({"text": "This one.", "ui": {"ui_id": "ui-grade", "value": value}}).status_code == 202
    first = next(e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "user_message")
    assert first == {"text": "This one.", "ui": {"ui_id": "ui-grade", "value": value}}, "the event keeps the card's state as it was sent"
    words, _ = said(model.requests[-1])
    assert words.startswith("This one.\n\n[The person locked in the card \"Pick a grade\" (ui_id ui-grade) with these values: ")
    assert json.loads(words[words.index("values: ") + 8:-1]) == value
    assert post({"ui": {"ui_id": "ui-grade", "value": None}}).status_code == 202, "a card can be locked in with no words"
    assert said(model.requests[-1])[0].startswith("[The person locked in the card")


def test_a_card_that_waits_ends_the_turn_and_its_lock_resumes_the_session_with_what_was_chosen(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    tuner = {"type": "stack", "children": [{"type": "slider", "id": "warmth", "label": "Warmth", "value": 20}]}
    shown = use("show_ui", title="The look of shot 3", components=tuner, submit="Lock in this look", waits=True)
    model.script(reply(say("Tune it and lock it in."), shown), reply(say("This is never asked for.")))
    message(client, film["id"], "Find a look for shot 3")
    log = events(client, film["id"])
    assert [e["kind"] for e in log["events"]] == ["user_message", "text", "tool_start", "ui", "tool_end", "usage", "turn_end"]
    card = next(e["data"] for e in log["events"] if e["kind"] == "ui")
    assert card["waits"] is True and card["submit"] == "Lock in this look" and card["kind"] == "components"
    assert log["running"] is False and len(model.requests) == 1, "the turn ended at the card: no machine waits for the person"

    model.steps.clear()
    model.script(reply(say("Grading the scene to match.")))
    locked = client.post(f"/v1/projects/{film['id']}/messages", headers=auth("alice-token"),
                         json={"text": "Locked in The look of shot 3: Warmth 30.", "ui": {"ui_id": card["ui_id"], "value": {"warmth": 30}}})
    assert locked.status_code == 202
    assert model.options[1].resume == model.options[0].session_id, "the lock goes on in the same session"
    words, _ = said(model.requests[-1])
    assert f'[The person locked in the card "The look of shot 3" (ui_id {card["ui_id"]}) with these values: ' in words
    assert json.loads(words[words.index("values: ") + 8:-1]) == {"warmth": 30}


def test_the_real_definitions_offer_a_film_its_skills_its_subagents_and_an_agent_for_each_engine():
    skills = read_skills(skills_directory())
    agents, derived = read_agents(agents_directory()), operators(agents_directory(), CATALOG, skills)
    offered = {discipline: skills_for(skills, CATALOG, discipline) for discipline in ("media", "animation", "games", "music")}
    names = {discipline: {skill.name for skill in chosen} for discipline, chosen in offered.items()}
    assert "movie" in names["media"] and "movie" in names["animation"], "the film's production is its own skill"
    assert "movie" not in names["games"] and "movie" not in names["music"]
    assert all({"studio", "cards"} <= chosen for chosen in names.values()), "every project runs a studio and can answer with a card"
    film = {agent.name: agent for agent in agents_for(agents, derived, offered["media"], CATALOG, "media")}
    assert {"research", "story", "art-direction", "character-design", "production-design", "librarian", "animation", "review"} <= set(film)
    assert film["filmcraft"].title == "FilmCraft agent" and film["filmcraft"].skills == ("filmcraft",)
    assert all(name in TOOL_NAMES or name.endswith("*") or name in ("web_search", "web_fetch")
               for agent in film.values() for name in agent.tools), "a definition names only tools the agent has"
    assert not any(name in ("ask_user", "show_ui", "engine_start", "engine_stop") for agent in film.values() for name in agent.tools), \
        "asking the person and running engines stay with the agent itself"
    game = {agent.name: agent for agent in agents_for(agents, derived, offered["games"], CATALOG, "games")}
    assert {"unreal_projects", "unreal_assets", "unreal_open"} <= set(game["unreal"].tools), "the Unreal skill gives its operator its own tools"
    assert game["blender"].title == "Blender agent" and game["blender"].skills == (), "an engine without a skill still has an operator"


def test_the_environment_lists_what_a_projects_agent_can_use(studio):
    client = studio.client
    film, game = new_project(client), new_project(client, name="Ember Ridge", discipline="games", format="Game")
    environment = lambda project, token="alice-token": client.get(f"/v1/projects/{project['id']}/environment", headers=auth(token))
    found = environment(film).json()
    assert list(found) == ["connectors", "agents", "skills"]
    connectors = {connector["id"]: connector for connector in found["connectors"]}
    assert list(connectors) == ["fal", "github", "web"], "Epic is for the projects whose discipline uses Unreal"
    assert all(set(connector) == {"id", "name", "kind", "state", "detail"} for connector in connectors.values())
    assert (connectors["fal"]["kind"], connectors["fal"]["state"]) == ("generation", "connected")
    assert (connectors["github"]["kind"], connectors["github"]["state"]) == ("repository", "available") and "Connect GitHub" in connectors["github"]["detail"]
    assert (connectors["web"]["kind"], connectors["web"]["state"]) == ("search", "connected")
    assert found["agents"] == [
        {"name": "research", "title": "Research agent", "description": "Looks things up on the web and in the library."},
        {"name": "filmcraft", "title": "FilmCraft agent", "description": "Drives FilmCraft for one job in a running engine."},
        {"name": "photocraft", "title": "PhotoCraft agent", "description": "Drives PhotoCraft for one job in a running engine."},
        {"name": "nuke", "title": "Nuke agent", "description": "Drives Nuke for one job in a running engine."},
    ]
    assert found["skills"] == [{"name": "filmcraft", "description": "Editing films in FilmCraft."}, {"name": "studio-basics", "description": ""}]

    connect_alice(studio)
    assert {c["id"]: c["state"] for c in environment(film).json()["connectors"]}["github"] == "available", "connected, with no repository linked yet"
    client.post(f"/v1/projects/{film['id']}/github", headers=auth("alice-token"), json={"repo": "alice-gh/film"})
    github = {c["id"]: c for c in environment(film).json()["connectors"]}["github"]
    assert github["state"] == "connected" and "alice-gh/film" in github["detail"]

    played = environment(game).json()
    epic = {c["id"]: c for c in played["connectors"]}["epic"]
    assert (epic["kind"], epic["state"]) == ("license", "available")
    assert [a["name"] for a in played["agents"]] == ["research", "blender", "unreal"]
    connect_epic(studio)
    studio.github.pullers.add(unseal(SECRET, studio.store.tables["epic_connections"][ALICE.id]["token_encrypted"]))
    assert {c["id"]: c["state"] for c in environment(game).json()["connectors"]}["epic"] == "connected"
    assert environment(film, "bob-token").status_code == 404

    with_config(studio, fal_key="", github_app_client_id="", anthropic_key="")
    off = {c["id"]: c["state"] for c in environment(film).json()["connectors"]}
    assert off == {"fal": "off", "github": "off", "web": "off"}


def test_a_session_that_begins_in_a_project_with_a_past_is_told_what_was_said(studio):
    client, model, store = studio.client, studio.model, studio.store
    film = new_project(client)
    question = use("ask_user", question="Color or black and white?", options=["Color", "Black and white"], recommended="Color")
    model.script(reply(say("A film about Mara. One thing first."), question), reply(say("Color it is.")))
    message(client, film["id"], "Make a film about Mara")
    message(client, film["id"], "Color")
    session = store.tables["projects"][film["id"]]["agent_session"]
    assert "What was said in this project before" not in said(model.requests[-1])[1]

    # The session's transcript is gone (another working directory, or a database restored without it): a new one begins
    store.tables["agent_transcripts"].clear()
    model.script(reply(say("Shot list next.")))
    message(client, film["id"], "What next?")
    fresh = store.tables["projects"][film["id"]]["agent_session"]
    assert fresh != session and (model.options[-1].session_id, model.options[-1].resume) == (fresh, None)
    words, state = said(model.requests[-1])
    assert words == "What next?" and len(model.requests[-1]["messages"]) == 1
    before = state[: state.index("The project's state at the start of this turn:")]
    assert before.splitlines()[1:-1] == [
        "The person: Make a film about Mara", "You: A film about Mara. One thing first.",
        "You asked: Color or black and white? (Color / Black and white; you recommended Color)", "The person: Color", "You: Color it is.",
    ], "the recap is the conversation the page shows, without this turn's own message"

    log = [{"kind": "user_message", "data": {"text": "x" * 5000}}] * 5 + [{"kind": "text", "data": {"text": "partial", "partial": True}},
                                                                        {"kind": "text", "data": {"text": "a subagent's", "agent_id": "a1"}},
                                                                        {"kind": "text", "data": {"text": "The last word."}}]
    told = recap(log)
    assert told.endswith("You: The last word.") and "partial" not in told and "subagent" not in told
    assert told.count("The person:") == 2, "the most recent is kept where there is more than a recap carries"


def test_the_unreal_projects_a_session_was_told_of_are_read_from_its_results_as_the_loop_keeps_them():
    call = {"type": "tool_use", "id": "toolu_1", "name": f"{PREFIX}unreal_projects", "input": {"engine_id": "e"}}
    other = {"type": "tool_use", "id": "toolu_2", "name": f"{PREFIX}library_list", "input": {}}
    answer = json.dumps({"projects": [{"path": "game/Game.uproject"}, {"path": "demo/Demo.uproject"}]})
    history = [
        {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
        {"role": "assistant", "content": [call, other]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": [{"type": "text", "text": answer}]},
            {"type": "tool_result", "tool_use_id": "toolu_2", "content": json.dumps({"projects": [{"path": "not/Unreal.uproject"}]})},
        ]},
        {"role": "assistant", "content": [{**call, "id": "toolu_3"}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_3", "content": "That engine is not running.", "is_error": True}]},
    ]
    assert reported_unreal(history) == {"game/Game.uproject", "demo/Demo.uproject"}


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
    launcher = ModalLauncher(module, app="modal-app", site_url="https://moody.example/app/")
    tier = {"gpu": None, "cpu": 2, "memory_gb": 4}
    project = str(uuid.uuid4())
    for app, project_id in (("filmcraft", project), ("filmcraft", project), ("nuke", project), ("blender", None)):
        launcher.start({"id": str(uuid.uuid4()), "user_id": ALICE.id, "app": app, "project_id": project_id}, tier, None)
    assert module.images == ["filmcraft", f"nuke:users/{ALICE.id}", "blender"], "one image per app; Nuke's from the user's install"
    film, _, nuke, blender = (settings for _, settings in module.started)
    assert film["application"] == "filmcraft" and film["image"] == "image:filmcraft"
    site = "https://moody.example"
    assert film["workspace"] == f"/users/{ALICE.id}"
    assert film["env"] == {"SELKIES_MODAL_PROJECT": f"projects/{project}", "SELKIES_FRAME_ANCESTORS": site}
    assert nuke["image"] == f"nuke-image:users/{ALICE.id}" and nuke["application"] == "nuke"
    assert blender["env"] == {"SELKIES_FRAME_ANCESTORS": site} and "moody_project" not in blender["tags"]
    assert ModalLauncher(module, app="modal-app").frame_ancestor == "", "no site, no frame allowed"
    assert origin("javascript:alert(1)") == "" and origin("http://localhost:5173/x") == "http://localhost:5173"



def test_the_launcher_finds_an_apps_command_channel_by_the_apps_id_and_says_where_there_is_none():
    module = FakeSandboxModule()
    launcher = ModalLauncher(module, app="modal-app")
    launcher.sandbox = lambda sandbox_id: f"sandbox:{sandbox_id}"
    assert not launcher.has_channel("filmcraft")
    with pytest.raises(RuntimeError, match="no command channel for filmcraft"):
        launcher.engine_call("sb-1", "filmcraft", "engine.commands", {})
    calls = []

    def channel(app: str) -> Callable[..., dict[str, Any]]:
        return lambda sandbox, method, params=None, timeout=60: calls.append((app, sandbox, method, params, timeout)) or {"app": app}

    for app in ("filmcraft", "soundcraft", "cadcraft", "craft_anything"):
        setattr(module, f"{app}_call", channel(app))
    # A name that is there but is no function is no channel
    module.nuke_call = None
    assert [launcher.has_channel(app) for app in ("filmcraft", "soundcraft", "cadcraft", "craft-anything", "blender", "nuke")] == [
        True, True, True, True, False, False]
    assert launcher.engine_call("sb-1", "filmcraft", "engine.commands", {}) == {"app": "filmcraft"}
    assert launcher.engine_call("sb-2", "soundcraft", "transport.play", None) == {"app": "soundcraft"}
    assert launcher.engine_call("sb-3", "cadcraft", "document.export", {"format": "step"}) == {"app": "cadcraft"}
    assert launcher.engine_call("sb-4", "craft-anything", "ping", None) == {"app": "craft_anything"}
    assert calls == [
        ("filmcraft", "sandbox:sb-1", "engine.commands", {}, 60),
        ("soundcraft", "sandbox:sb-2", "transport.play", None, 60),
        ("cadcraft", "sandbox:sb-3", "document.export", {"format": "step"}, 60),
        ("craft_anything", "sandbox:sb-4", "ping", None, 60),
    ]
    with pytest.raises(RuntimeError, match="no command channel for blender"):
        launcher.engine_call("sb-5", "blender", "ping", None)


def test_every_engine_of_a_project_opens_in_that_projects_folder_whatever_its_app():
    module = FakeSandboxModule()
    launcher = ModalLauncher(module, app="modal-app")
    tier = {"gpu": None, "cpu": 2, "memory_gb": 4}
    project, other = str(uuid.uuid4()), str(uuid.uuid4())
    for app, project_id in (("filmcraft", project), ("blender", project), ("soundcraft", project), ("blender", other)):
        launcher.start({"id": str(uuid.uuid4()), "user_id": ALICE.id, "app": app, "project_id": project_id}, tier, None)
    folders = [settings["env"]["SELKIES_MODAL_PROJECT"] for _, settings in module.started]
    assert folders == [f"projects/{project}"] * 3 + [f"projects/{other}"]
    assert {settings["workspace"] for _, settings in module.started} == {f"/users/{ALICE.id}"}


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

            @staticmethod
            def from_dict(values: dict[str, str]) -> SimpleNamespace:
                # An ephemeral Secret: it has no name, and lives only as long as the Sandbox it is given to
                return SimpleNamespace(ephemeral=dict(values))

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
        f"moody-ghcr-{ALICE.id}": {"REGISTRY_USERNAME": "alice-gh", "REGISTRY_PASSWORD": "gho_a2"},
        f"moody-ghcr-{BOB.id}": {"REGISTRY_USERNAME": "bob-gh", "REGISTRY_PASSWORD": "gho_b2"},
    }, "one Secret per user, holding their latest token"

    pulls = []
    module.unreal_image = lambda registry_secret, version: pulls.append((registry_secret.name, version)) or f"unreal:{registry_secret.name}"
    for user in (ALICE, BOB, ALICE):
        launcher.start(session(user), tier, None, OwnCopy("5.8"))
    alice, bob = f"moody-ghcr-{ALICE.id}", f"moody-ghcr-{BOB.id}"
    assert pulls == [(alice, "5.8"), (bob, "5.8"), (alice, "5.8")], "each start pulls with its user's own named Secret"
    assert [settings["image"] for _, settings in module.started] == [f"unreal:{alice}", f"unreal:{bob}", f"unreal:{alice}"]
    assert module.images == [], "no image of the editor is kept for the next start"
    for user in (ALICE, BOB):
        launcher.start(session(user), tier, None)
    assert module.images == ["unreal"], "without the Epic link, one desktop image with nothing of Epic's, defined once"
    assert [settings["image"] for _, settings in module.started[3:]] == ["image:unreal", "image:unreal"]
    assert len(pulls) == 3, "nothing is pulled with anyone's Secret for it"

    launcher.sandbox = lambda sandbox_id: f"sandbox:{sandbox_id}"
    with pytest.raises(RuntimeError, match="no unreal_view_link"):
        launcher.unreal_link("sb-4")
    with pytest.raises(RuntimeError, match="no unreal_projects"):
        launcher.unreal_projects("sb-4")
    module.unreal_view_link = lambda sandbox: f"https://{sandbox}.example.test/unreal"
    module.unreal_projects = lambda sandbox: [{"path": f"/home/ubuntu/workspace/{sandbox}/Game.uproject"}]
    assert launcher.unreal_link("sb-4") == "https://sandbox:sb-4.example.test/unreal"
    assert launcher.unreal_projects("sb-4") == [{"path": "/home/ubuntu/workspace/sandbox:sb-4/Game.uproject"}]

    launcher.forget_registry_credential(ALICE.id)
    launcher.forget_registry_credential(ALICE.id)
    assert list(modal.secrets) == [bob], "forgetting deletes the user's Secret, and a missing one is no error"


def test_the_launcher_hands_a_clone_to_its_start_alone_in_an_ephemeral_secret(monkeypatch):
    modal = FakeModal()
    monkeypatch.setitem(sys.modules, "modal", modal.module)
    module = FakeSandboxModule()
    launcher = ModalLauncher(module, app="modal-app")
    tier = {"gpu": "L4", "cpu": 8, "memory_gb": 32}
    project = str(uuid.uuid4())
    session = {"id": str(uuid.uuid4()), "user_id": ALICE.id, "app": "unreal", "project_id": project}
    clone = Clone(repo=MULTIVERSE, branch="main", name="Alice Example", email="1001+alice-gh@users.noreply.github.com",
                  token="ghu_alice_secret")
    launcher.start(session, tier, None, clone=clone)
    launcher.start({**session, "id": str(uuid.uuid4())}, tier, None)
    (_, cloning), (_, plain) = module.started
    (secret,) = cloning["secrets"]
    assert secret.ephemeral == clone.environment(), "the clone's variables, in a Secret of this start's own"
    assert "secrets" not in plain, "a start with nothing to clone is handed nothing"
    rest = json.dumps({key: value for key, value in cloning.items() if key != "secrets"}, default=str)
    assert "ghu_alice_secret" not in rest and modal.secrets == {}, "not in its environment, its tags, or a named Secret"

    launcher.sandbox = lambda sandbox_id: f"sandbox:{sandbox_id}"
    assert launcher.clone_status("sb-1") is None, "a launcher module that cannot say reports no clone"
    module.clone_status = lambda sandbox: {"state": "cloning", "path": f"/home/ubuntu/workspace/{sandbox}", "detail": ""}
    assert launcher.clone_status("sb-1") == {"state": "cloning", "path": "/home/ubuntu/workspace/sandbox:sb-1", "detail": ""}


def test_the_epic_link_is_the_registrys_own_answer_to_a_pull_of_epics_image():
    """The real `GitHub` against a stand-in for ghcr.io's token service: what it asks, and what each answer means."""
    seen: list[httpx.Request] = []
    linked = "Basic " + base64.b64encode(b"alice-gh:gho_linked").decode()

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if (request.url.host, request.url.path) != ("ghcr.io", "/token"):
            return httpx.Response(404, json={"message": "Not Found"})
        given = request.headers.get("authorization")
        if given is None:
            return httpx.Response(401, json={"errors": [{"code": "UNAUTHORIZED", "message": "authentication required"}]})
        if given == linked:
            return httpx.Response(200, json={"token": "djE6ZXBpY2dhbWVzL3VucmVhbC1lbmdpbmU6MQ=="})
        if "broken" in base64.b64decode(given.split()[1]).decode():
            return httpx.Response(503, text="unavailable")
        return httpx.Response(403, json={"errors": [{"code": "DENIED", "message": "denied"}]})

    github = GitHub()
    github.http = httpx.Client(headers=github.http.headers, transport=httpx.MockTransport(answer))
    assert github.registry_pull("alice-gh", "gho_linked") is True
    asked = seen[0]
    assert asked.method == "GET" and parse_qs(asked.url.query.decode()) == {
        "scope": ["repository:epicgames/unreal-engine:pull"], "service": ["ghcr.io"]}
    assert asked.headers["authorization"] == linked, "basic auth with the login and the token"
    assert github.registry_pull("alice-gh", "gho_not_linked") is False, "the registry's DENIED"
    with pytest.raises(GitHubError) as failure:
        github.registry_pull("alice-gh", "gho_broken")
    assert failure.value.status == 503, "anything else is no answer"


def test_the_github_client_speaks_the_apps_token_and_installation_endpoints():
    """The real `GitHub` over a recorded GitHub: the grant, its refresh, and the installations a user token lists."""
    seen: list[httpx.Request] = []
    pages = {1: [{"id": n} for n in range(100)], 2: [{"id": 100}]}

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/login/oauth/access_token":
            form = parse_qs(request.content.decode())
            if form.get("refresh_token") == ["ghr_dead"]:
                return httpx.Response(200, json={"error": "bad_refresh_token", "error_description": "The refresh token passed is incorrect or expired."})
            return httpx.Response(200, json={"access_token": "ghu_new", "expires_in": 28800, "refresh_token": "ghr_new",
                                             "refresh_token_expires_in": 15897600, "scope": "", "token_type": "bearer"})
        if path == "/user/installations":
            page = int(request.url.params["page"])
            return httpx.Response(200, json={"total_count": 101, "installations": pages[page]})
        if path == "/user/installations/7/repositories":
            return httpx.Response(200, json={"total_count": 1, "repositories": [{"full_name": "o/r"}]})
        return httpx.Response(404, json={"message": "Not Found"})

    github = GitHub()
    github.http = httpx.Client(headers=github.http.headers, transport=httpx.MockTransport(answer))
    grant = Grant("ghu_new", "", 28800, "ghr_new", 15897600)
    assert github.exchange("Iv1.app", "secret", "code", "https://api.example.test/v1/github/callback") == grant
    assert parse_qs(seen[-1].content.decode()) == {"client_id": ["Iv1.app"], "client_secret": ["secret"], "code": ["code"],
                                                   "redirect_uri": ["https://api.example.test/v1/github/callback"]}
    assert github.refresh("Iv1.app", "secret", "ghr_old") == grant
    assert parse_qs(seen[-1].content.decode()) == {"client_id": ["Iv1.app"], "client_secret": ["secret"],
                                                   "grant_type": ["refresh_token"], "refresh_token": ["ghr_old"]}
    with pytest.raises(GitHubError) as refused:
        github.refresh("Iv1.app", "secret", "ghr_dead")
    assert refused.value.status == 401 and "incorrect or expired" in refused.value.message, "GitHub refuses in a 200's body"

    seen.clear()
    assert [found["id"] for found in github.installations("ghu_new")] == list(range(101))
    assert [request.url.params["page"] for request in seen] == ["1", "2"], "every page, until a short one"
    assert {request.headers["authorization"] for request in seen} == {"Bearer ghu_new"}
    assert github.installation_repositories("ghu_new", 7, 50) == [{"full_name": "o/r"}]

    authorize = urlsplit(GitHub.authorize_url("Iv1.app", "https://api.example.test/v1/github/callback", "s"))
    assert "scope" not in parse_qs(authorize.query)
    epic = parse_qs(urlsplit(GitHub.authorize_url("Ov23.epic", "https://api.example.test/v1/epic/callback", "s", "read:packages")).query)
    assert epic["scope"] == ["read:packages"]
    assert GitHub.install_url("moody-studio", "a.b") == "https://github.com/apps/moody-studio/installations/new?state=a.b"


def test_skills_are_chosen_by_discipline_and_keep_their_reference_files_beside_them(tmp_path):
    folder, _ = write_definitions(tmp_path)
    skills = read_skills(folder)
    media = [skill.name for skill in skills_for(skills, CATALOG, "media")]
    music = [skill.name for skill in skills_for(skills, CATALOG, "music")]
    games = [skill.name for skill in skills_for(skills, CATALOG, "games")]
    assert media == ["filmcraft", "studio-basics"] and music == ["songwriting", "studio-basics"] and games == ["studio-basics"]
    film = next(skill for skill in skills if skill.name == "filmcraft")
    assert film.description == "Editing films in FilmCraft." and film.body.startswith("Cut on action.")
    assert "FILMCRAFT-REFERENCE-TEXT" not in film.body, "a reference file is no part of a skill's text"
    assert (film.directory / "references" / "color.md").read_text() == REFERENCE


def test_a_skill_for_every_discipline_is_read_for_every_project_whatever_it_is_named(tmp_path):
    for name, body in {
        **SKILLS,
        # Named after an engine, which alone would keep it to that engine's disciplines
        "blender": "---\ndescription: Running a production.\ndisciplines: all\n---\nALWAYS-SKILL-TEXT\n",
    }.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "SKILL.md").write_text(body)
    (tmp_path / "README.md").write_text("# Writing a skill\n\nNOT-A-SKILL")
    skills = read_skills(tmp_path)
    assert [skill.name for skill in skills] == ["blender", "filmcraft", "songwriting", "studio-basics"], "a file beside the skills is none"
    for discipline in CATALOG.disciplines:
        assert "blender" in [skill.name for skill in skills_for(skills, CATALOG, discipline)], discipline
    assert [skill.name for skill in skills_for(skills, CATALOG, "music")] == ["blender", "songwriting", "studio-basics"]


def test_the_studio_skill_is_read_for_every_project_and_names_only_tools_the_agent_has():
    skills = read_skills(skills_directory())
    studio_skill = next(skill for skill in skills if skill.name == "studio")
    for discipline in CATALOG.disciplines:
        assert "studio" in [skill.name for skill in skills_for(skills, CATALOG, discipline)], discipline
    named = set(re.findall(r"`((?:engine|unreal|github|library|generate)_[a-z_]+|ask_user|update_plan|filmcraft)[`(]", studio_skill.body))
    assert {"engine_call", "engine_files", "engine_show", "engine_exec", "engine_start", "engine_stop"} <= named
    assert named <= set(TOOL_NAMES), f"the skill names tools the agent does not have: {named - set(TOOL_NAMES)}"
    assert "handoff/" in studio_skill.body and studio_skill.directory == skills_directory() / "studio"


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
        if path == "/rest/v1/agent_transcripts":
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

    assert len(store.every("agent_transcripts", project_id="eq.p", order="id.asc")) == 1500
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
