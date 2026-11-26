# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""What Moody does for a user, whoever asks: the web API and the MCP endpoint both call this.

A session is a row in Supabase and a Sandbox on Modal, and this module keeps the
two in step. The row moves only through the database's own functions
(`moody/supabase/migrations`), each one transaction, so the rules about
credits, limits, and the queue hold whatever happens here; the Sandbox is
started, linked, and stopped through the launcher the `selkies-modal` command
uses (`addons/modal/sandbox.py`), so a session a user starts from the site is
the session that command starts.

Starting and stopping a Sandbox takes seconds, so neither happens inside a
request. A request records what was asked and hands the rest to a job
(`Jobs`), and the page polls; a job that dies leaves a row the reconciler
(`Sessions.reconcile`) finds. That reconciler is also the whole of monitoring
and metering: once a minute it charges what ran, ends what ran out of credits,
closes the row of every Sandbox that ended itself (idle, stopped, or crashed),
fails what never started, and starts what was queued.

Each user's sessions mount their own directory of the workspace Volume, and
nothing else of it, which is what keeps one user's files out of another's
session.

Moody Studio adds projects around that. A project is a row its user owns, and
every route that names one finds it through the user first (`owned_project`),
so another user's project, its library, its events, and its engines are a 404
here, never a filter a caller could widen. An engine is a session started for
a project: the same credits, queue, and capacity, opened in the project's
folder of the user's workspace. The library's entries are rows of the project
and their files objects of a private Storage bucket, handed out only as signed
links that expire. What the agent does in a project arrives as an append-only
log of events the page polls (`events`), and a message to the agent claims the
project's one turn in the database before a job runs it (`send_message`,
`agent.py`). A message may lock in an interactive card the agent showed
(`ui`), whose values go to the agent with it. A project made without a format,
in a discipline whose kinds the catalog asks for, opens on a card the control
plane writes itself (`opening_card`), and the message that locks that card
sets the project's kind before its turn begins (`chosen_kind`, `set_kind`).
Where the agent waits for the
person's approval of a step, their answer is recorded once, in the database
(`answer_approval`), and `always` is kept among the project's permissions,
which the person can also set and clear (`update_project`). What one turn
may spend on the model and how many steps it may take are settings of the
person's account (`limits`, `change_me`): the deployment's default where
they set none, and never above the deployment's ceiling. The account's other
settings are the catalog's (`catalog.json`, `settings`): each is a switch or a
choice with a default, the profile keeps what the person changed, and
`settings` answers every one with the value that applies. What a project's
agent can use beyond its tools is listed for the page (`connectors`). The
user's GitHub account is connected through a GitHub App whose
user token, and the refresh token that renews it, are kept sealed
(`github_client.py`); the token is refreshed only when it is about to expire
(`github_token`), and the repositories offered are those of the app's
installations the user reaches (`github_repos`).

An app of status `byol` has a part that runs on a license the user brings.
Unreal Engine's is the editor, on the user's Epic account, which Epic links to
a GitHub account. The engine starts for anyone on a tier with a GPU, so the
desktop it streams (a GitHub client, Git LFS, Firefox, and Blender) is there
before anyone mentions Epic; what the start reads is whether the user's Epic
connection, an OAuth App of its own that reads packages, is granted a pull of
Epic's image by the registry (`epic_link`). With it, the image is the user's
own copy of the editor, pulled from Epic's registry with that user's own GitHub
login and token, since Epic's license lets each user have their copy but not
Moody hand one copy around (`moody/UNREAL.md`); without it, the image is the
same desktop without the editor, and opening a project says what links it
(`editor_license`). The launcher keeps that credential as the user's own
registry credential (`Launcher.keep_registry_credential`), written again at
every start of the app on a linked account and when the user connects Epic
again, and forgotten when they disconnect it; it is never kept beside a session
or used for another user's image.

An Unreal engine of a project linked to a repository clones it as it starts:
the start mints the user's GitHub App token afresh and hands it to the machine
in an ephemeral Secret with the repository, its branch, and the name and
address the user commits under (`clone_for`, `Clone`). The token is in no row,
event, or message; what the machine reports of the clone (`clone_status`) is
what the engine's listing and the agent's turn read.

An Unreal engine streams two pictures of one machine: its desktop, and the
Unreal view, where the editor streams itself once it is open (a placeholder
page until then). The engines a page lists report both as `streams`, each a
link minted for that listing as `link` mints one, and the link route mints
either again (`stream_link`). Links carry the session's credentials, so they
go to the page that asked and are never written to the event log.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx

import genui
from github_client import EPIC_FLOW, EPIC_SCOPE, GitHub, GitHubError, Grant, read_state, seal, sign_state, unseal
import unreal

IDLE_SECONDS = 600
LIFETIME_SECONDS = 8 * 3600
READY_SECONDS = 120
# A session still `starting` after this long has lost its job
START_LIMIT_SECONDS = 300
OPEN = ("queued", "starting", "running")
# The catalog statuses an app can be started under: anyone's, the team's, or with a part on the user's own license
STARTABLE = ("available", "team", "byol")
# What a session's link opens, and the name of each picture an engine streams
DESKTOP = "Desktop"
UNREAL_VIEW = "Unreal"
# The pictures an app's engines stream, by app: an app not named here streams its desktop alone
STREAMS: dict[str, tuple[str, ...]] = {"unreal": (DESKTOP, UNREAL_VIEW)}
SESSION_FIELDS = (
    "id",
    "project_id",
    "app",
    "tier",
    "region",
    "status",
    "created_at",
    "started_at",
    "ended_at",
    "end_reason",
    "credits_used",
)
API_KEY_PREFIX = "moody_"
# A turn not heard from for this long has lost its worker (`agent.py` beats every 20 seconds)
TURN_STALE_SECONDS = 120
LIBRARY_BUCKET = "library"
SIGNED_URL_SECONDS = 3600
MEGABYTE = 1024 * 1024
MEDIA_LIMIT_BYTES = 200 * MEGABYTE
# The folder of a project's files in the bucket that holds the agent's previews, which are not library entries
PREVIEWS = "previews"
# The events that carry files, by kind, and the field of each that lists them by their paths in the bucket
SIGNED_FILES = {"preview": "items", "ui": "media"}
MESSAGE_LIMIT = 20000
# The largest state of an interactive card a message may lock in, as JSON
UI_VALUE_LIMIT_BYTES = 64 * 1024
# What a project's permissions say of a tool the person no longer wants to be asked about, and how a tool is named
ALWAYS = "always"
TOOL_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")
# What the person may answer an approval with
APPROVAL_DECISIONS = ("once", ALWAYS, "deny")
PROJECT_FIELDS = (
    "id",
    "name",
    "discipline",
    "format",
    "pinned",
    "created_at",
    "updated_at",
    "github_repo",
    "github_branch",
    "library_sections",
    "plan",
    "permissions",
)
# What of a project the card that asks its kind sets, which is also the id of that card's one input
KIND_FIELD = "format"
# The longest name an account gives itself
NAME_LIMIT = 80
# The limits of one turn an account sets for itself, as `profiles` and `Config` name them
LIMITS = ("turn_budget_usd", "turn_limit")
ASSET_FIELDS = ("id", "section", "name", "tag", "description", "metadata", "created_at", "updated_at")
EVENT_FIELDS = ("id", "turn_id", "kind", "data", "created_at")
PLAN_STATUSES = ("pending", "active", "done", "blocked")
SECTION_LIMIT = 30
TAG_BODY = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
REPO_NAME = re.compile(r"[A-Za-z0-9._-]{1,100}")
REPO_FULL_NAME = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}")
BRANCH_NAME = re.compile(r"[A-Za-z0-9._/-]{1,250}")
# A GitHub App user token with less than this left is refreshed before it is used
TOKEN_MARGIN_SECONDS = 300
# What a token handed to an engine that clones at its start has left at least: most of its eight hours
CLONE_TOKEN_SECONDS = 7 * 3600
# Repositories the picker lists at most, across every installation
REPO_LIMIT = 1000
# What GitHub's redirect after an installation says happened (`setup_action`)
INSTALL_ACTIONS = ("install", "update", "request")
# What a machine reports of the clone it makes at its start
CLONE_STATES = ("cloning", "done", "failed")


class Refused(Exception):
    """A request the service will not carry out, with the HTTP status that says why."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class User:
    """Who a request is for, as its credential named them."""

    id: str
    email: str


@dataclass(frozen=True)
class OwnCopy:
    """A start that pulls the user's own copy of an app, of this version.

    The copy is pulled with the registry credential the launcher keeps for the
    session's user, which the service writes before the start
    (`Launcher.keep_registry_credential`).
    """

    version: str


@dataclass(frozen=True)
class Clone:
    """What an engine clones as it starts: a repository at a branch, with the user's token, under their name.

    The token is a GitHub App user token minted for this start; it reaches the machine only in
    the ephemeral Secret `environment` fills, and is left out of `repr` so no log shows it.
    """

    repo: str
    branch: str
    name: str
    email: str
    token: str = field(repr=False)

    def environment(self) -> dict[str, str]:
        """The variables the machine clones with, which the launcher passes in an ephemeral Secret."""
        return {
            "MOODY_GIT_TOKEN": self.token,
            "MOODY_GIT_REPO": self.repo,
            "MOODY_GIT_BRANCH": self.branch,
            "MOODY_GIT_NAME": self.name,
            "MOODY_GIT_EMAIL": self.email,
        }


@dataclass(frozen=True)
class Config:
    """What the deployment is configured with; every value comes from the environment (`app.py`)."""

    supabase_url: str
    # The project's secret key (`sb_secret_...`), or its legacy `service_role` key
    supabase_key: str
    stripe_key: str
    stripe_webhook_secret: str
    site_url: str
    # Sessions that may run at once across all users; more are queued
    capacity: int
    # Tier ids users may start; the others are refused, as GPU tiers are until Modal will start them
    tiers: frozenset[str]
    # Whether a chosen region is pinned on Modal, which bills a pinned Sandbox at a higher rate
    pin_regions: bool
    # The Anthropic API key the agent runs on, and the model it runs where not the default (`agent.py`)
    anthropic_key: str = ""
    agent_model: str = ""
    # fal.ai's key, for image and video generation
    fal_key: str = ""
    # The GitHub App users connect their accounts through: its client, and its name in its pages' address
    github_app_client_id: str = ""
    github_app_client_secret: str = ""
    github_app_slug: str = ""
    # The OAuth App that reads packages, through which a user's Epic link pulls their copy of Unreal Engine
    epic_client_id: str = ""
    epic_client_secret: str = ""
    # Signs GitHub's `state` and seals the tokens it grants; any long random string
    secret_key: str = ""
    # The accounts, by email in lowercase, that may start apps of status `team`
    team_emails: frozenset[str] = field(default_factory=frozenset)
    # Nuke sessions that may be open at once across all users: the seats its license has
    nuke_seats: int = 2
    # The API's own address, where it differs from the one a request arrives at
    api_url: str = ""
    # The largest copy of a file the agent's `preview` puts in the conversation; a larger one is refused
    preview_limit_bytes: int = 50 * MEGABYTE
    # A file over this, or in a format browsers do not play, is shown as a lighter copy the engine encodes
    preview_original_bytes: int = 8 * MEGABYTE
    # The files one preview may show
    preview_files: int = 12
    # The largest file or folder `engine_send` carries from one running engine to another
    transfer_limit_bytes: int = 4096 * MEGABYTE
    # The agent's loop (`loop.py`): how hard the model works, whether it thinks, and the model a request falls
    # back to where the agent's own is overloaded or declines; empty for none
    agent_effort: str = "high"
    agent_thinking: bool = True
    agent_fallback_model: str = ""
    # The models a subagent's `balanced` and `light` tiers run on; `inherit` is the agent's own
    agent_model_balanced: str = "claude-sonnet-5-5"
    agent_model_light: str = "claude-haiku-5-5"
    # What one turn may spend on the model, in dollars as the loop prices it, and the most steps it may take, for
    # an account that has set neither; and the most an account may set either to (`Sessions.limits`)
    turn_budget_usd: float = 15.0
    turn_limit: int = 200
    turn_budget_max_usd: float = 100.0
    turn_limit_max: int = 1000
    # How long a step waits for the person's approval before the agent is told to end its turn and ask
    approval_seconds: float = 600
    # Where the loop reaches the Messages API where not Anthropic's own address: a proxy that holds the key
    anthropic_base_url: str = ""
    # Under which a turn's working directory is made, `<root>/<project id>`. The loop keys a session's transcript
    # by that path, so it is the same on every machine and changing it starts every project's session anew
    loop_root: str = "/tmp/moody-loop"
    # Variables of the worker's environment the loop's process also gets, beside the Anthropic key: a proxy's
    # address, a certificate bundle. Nothing else of the worker's environment reaches it
    loop_env: frozenset[str] = frozenset()
    # The `claude` program the loop runs, where not the one the SDK bundles
    loop_cli: str = ""

    def __post_init__(self) -> None:
        """Refuse limits of a turn that are none: a default or a ceiling of zero would end every turn as it began."""
        if min(self.turn_budget_usd, self.turn_budget_max_usd) <= 0:
            raise ValueError("MOODY_TURN_BUDGET_USD and MOODY_TURN_BUDGET_MAX_USD are positive numbers of dollars")
        if min(self.turn_limit, self.turn_limit_max) <= 0:
            raise ValueError("MOODY_TURN_LIMIT and MOODY_TURN_LIMIT_MAX are positive numbers of steps")

    @property
    def supabase(self) -> bool:
        """Whether a Supabase project is configured at all."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def billing(self) -> bool:
        """Whether payments can be taken."""
        return bool(self.stripe_key and self.stripe_webhook_secret)

    @property
    def agent(self) -> bool:
        """Whether a project's agent can run."""
        return bool(self.anthropic_key)

    @property
    def generation(self) -> bool:
        """Whether the agent can generate images and video."""
        return bool(self.fal_key)

    @property
    def github(self) -> bool:
        """Whether users can connect GitHub accounts through the GitHub App."""
        return bool(self.github_app_client_id and self.github_app_client_secret and self.github_app_slug and self.secret_key)

    @property
    def epic(self) -> bool:
        """Whether users can connect the GitHub account linked to Epic, which their copy of Unreal Engine is pulled with."""
        return bool(self.epic_client_id and self.epic_client_secret and self.secret_key)


class Catalog:
    """The disciplines, apps, tiers, regions, and credit packs on offer, read from `moody/catalog.json`.

    The site reads the same file, so what a page shows and what the service
    accepts and charges are one definition.
    """

    def __init__(self, path: Path) -> None:
        self.data: dict[str, Any] = json.loads(path.read_text())
        self.apps = {app["id"]: app for app in self.data["apps"]}
        self.disciplines = {discipline["id"]: discipline for discipline in self.data.get("disciplines", [])}
        self.tiers = {tier["id"]: tier for tier in self.data["tiers"]}
        self.regions = {region["id"] for region in self.data["regions"]}
        self.packs = {pack["id"]: pack for pack in self.data["credit_packs"]}
        # What a person may set for themselves beyond the limits of a turn, by id (`Sessions.settings`)
        self.settings = {setting["id"]: setting for setting in self.data.get("settings", [])}
        self.signup_credits: int = self.data["signup_credits"]


class Store:
    """The Supabase project, reached with its secret key: its auth server and its tables.

    Row-level security keeps every other key out of the tables, so this is the
    only reader and writer, and each method names the one thing it does there.
    A refusal the database raises by name (`insufficient_credits`) comes back
    as `Refused`.

    The key goes in the `apikey` header. A legacy `service_role` key is a JWT
    and is sent as the bearer token too, which is how the Data API takes its
    role from one; a secret key (`sb_secret_...`) is not a JWT and must not be,
    since whatever reads a bearer token tries to verify it as one.
    """

    REFUSALS = {
        "insufficient_credits": (402, "You are out of credits. Add credits to start a session."),
        "session_limit": (409, "You already have a session open. Stop it before starting another."),
        "no_profile": (409, "This account has no profile yet. Reload and try again."),
        "no_project": (404, "No such project."),
        "no_seats": (409, "Every seat of this app is in use. Try again when one is free."),
        "turn_running": (409, "The agent is still working on this project. Wait for it, or stop it."),
        "no_approval": (404, "The agent is not waiting for that approval."),
    }

    def __init__(self, url: str, key: str) -> None:
        headers = {"apikey": key}
        if not key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {key}"
        self.http = httpx.Client(base_url=url.rstrip("/"), headers=headers, timeout=20)

    def user_of_token(self, token: str) -> User | None:
        """The user a Supabase access token belongs to, as its auth server says, or nobody."""
        response = self.http.get("/auth/v1/user", headers={"Authorization": f"Bearer {token}"})
        if response.status_code != 200:
            return None
        body = response.json()
        return User(id=body["id"], email=body.get("email") or "")

    def rpc(self, function: str, **arguments: Any) -> Any:
        """Call one of the database's functions and return what it returned."""
        response = self.http.post(f"/rest/v1/rpc/{function}", json=arguments)
        if response.status_code >= 400:
            message = response.json().get("message", "") if response.content else ""
            if message in self.REFUSALS:
                raise Refused(*self.REFUSALS[message])
            response.raise_for_status()
        return response.json() if response.content else None

    def rows(self, table: str, **query: str) -> list[dict[str, Any]]:
        """Rows of a table, filtered and ordered as PostgREST's query parameters say."""
        response = self.http.get(f"/rest/v1/{table}", params=query)
        response.raise_for_status()
        return response.json()

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        """Insert a row and return it as stored."""
        response = self.http.post(f"/rest/v1/{table}", json=row, headers={"Prefer": "return=representation"})
        response.raise_for_status()
        return response.json()[0]

    def update(self, table: str, changes: dict[str, Any], **query: str) -> list[dict[str, Any]]:
        """Change the rows a filter selects and return them."""
        response = self.http.patch(
            f"/rest/v1/{table}", json=changes, params=query, headers={"Prefer": "return=representation"}
        )
        response.raise_for_status()
        return response.json()

    def every(self, table: str, **query: str) -> list[dict[str, Any]]:
        """All the rows a filter selects, a page at a time, since the Data API answers at most a page per call."""
        found: list[dict[str, Any]] = []
        while True:
            page = self.rows(table, **query, limit="1000", offset=str(len(found)))
            found.extend(page)
            if len(page) < 1000:
                return found

    def delete(self, table: str, **query: str) -> None:
        """Delete the rows a filter selects."""
        self.http.delete(f"/rest/v1/{table}", params=query).raise_for_status()

    def upsert(self, table: str, row: dict[str, Any], on_conflict: str) -> dict[str, Any]:
        """Insert a row, or change the one it collides with on `on_conflict`, and return it as stored."""
        response = self.http.post(
            f"/rest/v1/{table}",
            json=row,
            params={"on_conflict": on_conflict},
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )
        response.raise_for_status()
        return response.json()[0]

    # Storage, whose buckets the same key reaches

    def upload(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        """Store a file at a path of a bucket, replacing what is there."""
        response = self.http.post(
            f"/storage/v1/object/{bucket}/{quote(path)}",
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "true"},
            timeout=300,
        )
        response.raise_for_status()

    def download(self, bucket: str, path: str, limit: int) -> bytes:
        """A file of a bucket, whole.

        Raises:
            ValueError: The file is larger than `limit` bytes; no more than that is read of it.
        """
        with self.http.stream("GET", f"/storage/v1/object/{bucket}/{quote(path)}", timeout=300) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes():
                data += chunk
                if len(data) > limit:
                    raise ValueError(f"{path} is larger than {limit} bytes")
        return bytes(data)

    def sign(self, bucket: str, paths: list[str], seconds: int) -> dict[str, str]:
        """Links that read each path for `seconds`, by path; a path with no file has none."""
        response = self.http.post(f"/storage/v1/object/sign/{bucket}", json={"expiresIn": seconds, "paths": paths})
        response.raise_for_status()
        base = f"{self.http.base_url}".rstrip("/")
        return {item["path"]: f"{base}/storage/v1{item['signedURL']}" for item in response.json() if item.get("signedURL")}

    def remove(self, bucket: str, paths: list[str]) -> None:
        """Delete files of a bucket."""
        for start in range(0, len(paths), 1000):
            self.http.request(
                "DELETE", f"/storage/v1/object/{bucket}", json={"prefixes": paths[start : start + 1000]}
            ).raise_for_status()

    def remove_prefix(self, bucket: str, prefix: str) -> None:
        """Delete every file under a folder of a bucket, its folders' too."""
        files: list[str] = []
        folders = [prefix.rstrip("/")]
        while folders:
            folder, offset = folders.pop(), 0
            while True:
                response = self.http.post(
                    f"/storage/v1/object/list/{bucket}", json={"prefix": folder, "limit": 1000, "offset": offset}
                )
                if response.status_code == 404:
                    return
                response.raise_for_status()
                items = response.json()
                for item in items:
                    # A folder is listed as an entry without an ID
                    (files if item.get("id") else folders).append(f"{folder}/{item['name']}")
                if len(items) < 1000:
                    break
                offset += 1000
        if files:
            self.remove(bucket, files)


class Launcher(Protocol):
    """The part of `addons/modal/sandbox.py` this service drives, which a test stands in for."""

    def start(
        self,
        session: dict[str, Any],
        tier: dict[str, Any],
        region: str | None,
        own_copy: OwnCopy | None = None,
        clone: Clone | None = None,
    ) -> str:
        """Start the session's Sandbox, wait until it streams, and return the Sandbox's ID.

        `own_copy` is given for an app whose licensed part the user has linked, whose image is then
        pulled with the registry credential kept for the session's user; without it, such an app
        starts without that part. `clone` is the repository the machine clones as it starts, with
        the token that reaches it, which only the Sandbox's own ephemeral Secret carries.
        """

    def keep_registry_credential(self, user_id: str, username: str, token: str, create: bool = True) -> None:
        """Keep the user's own registry login and token, which their copies of an app are pulled with.

        With `create` false, only a credential already kept for the user is written again.
        """

    def forget_registry_credential(self, user_id: str) -> None:
        """Delete the registry credential kept for the user, if there is one."""

    def state(self, sandbox_id: str) -> int | None:
        """The Sandbox's exit status, or nothing while it runs."""

    def link(self, sandbox_id: str) -> str:
        """A fresh link that opens the session."""

    def unreal_link(self, sandbox_id: str) -> str:
        """A fresh link that opens an Unreal engine's Unreal view, where the editor streams once it is open."""

    def unreal_projects(self, sandbox_id: str) -> list[dict[str, Any]]:
        """The `.uproject` files in an Unreal engine's workspace, as the machine reports them (`unreal.found_project`)."""

    def clone_status(self, sandbox_id: str) -> dict[str, Any] | None:
        """What the machine reports of the clone it made as it started: `{state, path, detail}`, or nothing."""

    def stop(self, sandbox_id: str) -> None:
        """End the session, keeping the scene Blender has open."""

    def blender_python(self, sandbox_id: str, code: str) -> tuple[int, str]:
        """Run Python in the session's Blender and return its status and output."""

    def screenshot(self, sandbox_id: str) -> bytes:
        """The session's screen as a JPEG."""

    def exec(self, sandbox_id: str, command: str, timeout: int) -> tuple[int, str]:
        """Run a shell command in the session's environment, as its user, and return its status and output."""

    def read_file(self, sandbox_id: str, path: str, limit: int) -> bytes:
        """A file of the session, whole.

        Raises:
            ValueError: The file is larger than `limit` bytes.
            RuntimeError: It could not be read, with why.
        """

    def send(self, sandbox_id: str, path: str, to_sandbox_id: str, to_path: str, keep_going: Callable[[], bool]) -> int:
        """Copy a file or a folder of one running session to a path of another, and return the bytes carried.

        Raises:
            FileNotFoundError: The session has nothing at `path`.
            InterruptedError: `keep_going` said to stop; nothing is left at `to_path`.
            RuntimeError: Either session refused, with why.
        """

    def has_channel(self, app: str) -> bool:
        """Whether engines of this app have a command channel, which `engine_call` reaches."""

    def engine_call(self, sandbox_id: str, app: str, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Call a method of the app's command channel in the session and return its answer.

        Raises:
            RuntimeError: The app refused the call or did not answer, or it has no command channel, with why.
        """


class Jobs(Protocol):
    """Work that outlasts a request: starting and stopping a Sandbox, and an agent's turn."""

    def start(self, session_id: str) -> None:
        """Have `Sessions.run_start` run for this session."""

    def stop(self, session_id: str, reason: str) -> None:
        """Have `Sessions.run_stop` run for this session."""

    def turn(self, project_id: str, turn_id: str) -> None:
        """Have the project's agent run this turn (`agent.Agent.run`)."""


def hash_key(secret: str) -> str:
    """The form an API key is stored and looked up in."""
    return hashlib.sha256(secret.encode()).hexdigest()


def is_id(value: str) -> bool:
    """Whether a string a caller sent is shaped like a row's ID, before it is put in a filter."""
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def now() -> str:
    """The time, as the database writes it."""
    return datetime.now(timezone.utc).isoformat()


def normal_tag(value: str | None) -> str | None:
    """A library tag as stored, `@` and a lowercase name (`@mara`), from however it was typed; none for none.

    Raises:
        Refused: 400 for a tag that is not letters, digits, dashes, and underscores.
    """
    body = re.sub(r"\s+", "-", (value or "").strip().lower().lstrip("@"))
    if not body:
        return None
    if not TAG_BODY.fullmatch(body):
        raise Refused(400, f"A tag is letters, digits, dashes, and underscores, like @mara; {value!r} is not one.")
    return f"@{body}"


def media_kind(content_type: str) -> str:
    """What a file is to the library, by its content type."""
    kind = content_type.split("/", 1)[0]
    return kind if kind in ("image", "video", "audio") else "file"


def safe_name(name: str) -> str:
    """A file name that is safe as the last part of a Storage path."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")[:80]
    return cleaned or "file"


def with_query(url: str, **params: str) -> str:
    """A URL with parameters added to its query, before any fragment."""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True) + list(params.items())
    return urlunsplit(parts._replace(query=urlencode(query)))


def setting_app(setting: dict[str, Any], value: Any) -> str | None:
    """The app a value of a catalog setting stands for, or nothing where the setting chooses between no apps.

    A setting that chooses between engines names them in `apps`: a toggle's
    under `on` and `off`, a choice's under its options' values. The agent is
    told of the one that applies, and the page offers a person only that one
    to start, so the choice is made in Settings and nowhere else.
    """
    key = ("on" if value else "off") if setting["kind"] == "toggle" else value
    return setting.get("apps", {}).get(key)


def default_sections(discipline: dict[str, Any], project_format: str) -> list[str]:
    """The library sections a project of a discipline and a kind starts with, as the catalog gives them.

    A kind's own (`kinds.<format>.sections`: a commercial's products and
    shots) where it has any, else the discipline's (`sections`: a film's cast
    and world), else none.
    """
    kind = discipline.get("kinds", {}).get(project_format, {})
    return list(kind.get("sections") or discipline.get("sections") or [])


def clean_sections(sections: list[str]) -> list[str]:
    """Section names trimmed, deduplicated regardless of case, and bounded in length and number."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for section in sections:
        name = " ".join(str(section).split())[:40]
        if name and name.lower() not in seen:
            seen.add(name.lower())
            cleaned.append(name)
    return cleaned[:SECTION_LIMIT]


class Sessions:
    """Everything a user can do, and the upkeep that runs without them."""

    def __init__(
        self,
        config: Config,
        catalog: Catalog,
        store: Store,
        launcher: Launcher,
        jobs: Jobs,
        github: GitHub | None = None,
    ) -> None:
        self.config = config
        self.catalog = catalog
        self.store = store
        self.launcher = launcher
        self.jobs = jobs
        self.github = github or GitHub()
        # Access tokens seen in the last minute, so a polling page costs the auth server one call a minute
        self._seen: dict[str, tuple[float, User]] = {}

    # Who is asking

    def authenticate(self, credential: str) -> User:
        """The user a bearer credential names: an API key of ours, or a Supabase access token.

        Raises:
            Refused: 401 where the credential names nobody.
        """
        if credential.startswith(API_KEY_PREFIX):
            user_id = self.store.rpc("moody_use_api_key", p_key_hash=hash_key(credential))
            if not user_id:
                raise Refused(401, "This API key is not valid. Create a new one in your dashboard.")
            return User(id=user_id, email="")
        seen = self._seen.get(credential)
        if seen and seen[0] > time.monotonic():
            return seen[1]
        user = self.store.user_of_token(credential)
        if user is None:
            raise Refused(401, "Your sign-in has expired. Sign in again.")
        if len(self._seen) > 1000:
            self._seen.clear()
        self._seen[credential] = (time.monotonic() + 60, user)
        return user

    def me(self, user: User) -> dict[str, Any]:
        """The user's profile, made with its sign-up credits the first time it is asked for."""
        profile = self.store.rpc(
            "moody_ensure_profile", p_user=user.id, p_email=user.email, p_signup_credits=self.catalog.signup_credits
        )
        return {
            "id": profile["id"],
            "email": profile["email"],
            "name": profile.get("name") or "",
            "credits": profile["credits"],
            "max_sessions": profile["max_sessions"],
            "limits": self.limits(profile),
            "settings": self.settings(profile),
        }

    @staticmethod
    def offered(setting: dict[str, Any], value: Any) -> bool:
        """Whether a value is one a setting of the catalog may have: on or off for a toggle, one of a choice's options."""
        if setting["kind"] == "toggle":
            return isinstance(value, bool)
        return any(value == option["value"] for option in setting.get("options", []))

    def settings(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Every setting of the catalog with the value that applies to this person: their own, or its default.

        A value kept from before the catalog stopped offering it does not
        apply, so a choice whose option was removed is back on its default
        without anyone's row being rewritten.
        """
        own = profile.get("settings") or {}
        return {
            name: own[name] if name in own and self.offered(setting, own[name]) else setting["default"]
            for name, setting in self.catalog.settings.items()
        }

    def limits(self, profile: dict[str, Any]) -> dict[str, Any]:
        """What one turn of this person's may spend on the model and how many steps it may take, and where that comes from.

        Each limit is the person's own setting where they made one, else the
        deployment's default, and in either case no more than the deployment's
        ceiling, which also holds a setting made before the ceiling was
        lowered. `own`, `default`, and `max` are the three it is made from,
        for the page that lets the person change it.
        """
        config = self.config
        ceiling = {"turn_budget_usd": config.turn_budget_max_usd, "turn_limit": config.turn_limit_max}
        default = {"turn_budget_usd": min(config.turn_budget_usd, ceiling["turn_budget_usd"]), "turn_limit": min(config.turn_limit, ceiling["turn_limit"])}
        own = {name: profile.get(name) for name in LIMITS}
        applies = {name: min(default[name] if own[name] is None else own[name], ceiling[name]) for name in LIMITS}
        return {**applies, "own": own, "default": default, "max": ceiling}

    def change_me(self, user: User, changes: dict[str, Any]) -> dict[str, Any]:
        """Change what is the user's to set of their account, and return their profile.

        `changes` holds what to change: a limit of a turn by its name, `name`,
        and `settings`, the catalog's settings to change by id. `None` puts a
        limit or a setting back on its default, and clears the name. Nothing
        is written where anything is refused.

        Raises:
            Refused: 400 for a limit that is not a positive number, a number of steps that is not whole, or
                one over the deployment's ceiling; for a name that is not text; for settings that are
                not an object, an id the catalog does not have, or a value it does not offer.
        """
        config = self.config
        kept: dict[str, Any] = {}
        if "name" in changes:
            name = changes["name"]
            if name is not None and not isinstance(name, str):
                raise Refused(400, "A name is text.")
            kept["name"] = " ".join((name or "").split())[:NAME_LIMIT]
        chosen: dict[str, Any] | None = None
        if "settings" in changes:
            chosen = changes["settings"]
            if not isinstance(chosen, dict):
                raise Refused(400, "settings is the settings to change, each by its id.")
            for name, value in chosen.items():
                setting = self.catalog.settings.get(name)
                if setting is None:
                    raise Refused(400, f"There is no setting {name}.")
                if value is not None and not self.offered(setting, value):
                    wanted = "true or false" if setting["kind"] == "toggle" else ", ".join(str(option["value"]) for option in setting["options"])
                    raise Refused(400, f"{name} is {wanted}, or null for its default.")
        for name, value in changes.items():
            if name not in LIMITS:
                continue
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0):
                raise Refused(400, "A limit is a positive number, or null for the default.")
            if name == "turn_budget_usd" and value is not None and value > config.turn_budget_max_usd:
                raise Refused(400, f"A turn may spend at most ${config.turn_budget_max_usd:g} here.")
            if name == "turn_limit" and value is not None:
                if value != int(value):
                    raise Refused(400, "A turn's steps are a whole number.")
                if value > config.turn_limit_max:
                    raise Refused(400, f"A turn may take at most {config.turn_limit_max} steps here.")
                value = int(value)
            kept[name] = value
        profile = self.me(user)
        if chosen:
            own = self.store.rows("profiles", id=f"eq.{user.id}")[0].get("settings") or {}
            kept["settings"] = {name: value for name, value in {**own, **chosen}.items() if value is not None}
        if kept:
            self.store.update("profiles", kept, id=f"eq.{user.id}")
            profile = self.me(user)
        return profile

    # Sessions

    def public(self, row: dict[str, Any]) -> dict[str, Any]:
        """A session as the API shows it: no Sandbox ID, and its place in the queue while it waits."""
        session = {name: row[name] for name in SESSION_FIELDS}
        session["queue_position"] = (
            self.store.rpc("moody_queue_position", p_session=row["id"]) if row["status"] == "queued" else None
        )
        return session

    def list(self, user: User) -> list[dict[str, Any]]:
        """The user's open sessions, then their ten most recent that are over."""
        active = self.store.rows(
            "sessions", user_id=f"eq.{user.id}", status=f"in.({','.join(OPEN)})", order="created_at.desc"
        )
        over = self.store.rows(
            "sessions",
            user_id=f"eq.{user.id}",
            status="in.(ended,failed)",
            order="created_at.desc",
            limit="10",
        )
        return [self.public(row) for row in active + over]

    def owned(self, user: User, session_id: str) -> dict[str, Any]:
        """The user's session of that ID.

        Raises:
            Refused: 404 where there is none, which is also what another user's session is to this one.
        """
        rows = self.store.rows("sessions", id=f"eq.{session_id}", user_id=f"eq.{user.id}") if is_id(session_id) else []
        if not rows:
            raise Refused(404, "No such session.")
        return rows[0]

    def start(self, user: User, app: str, tier: str, region: str, project_id: str | None = None) -> dict[str, Any]:
        """Record a new session for the user, in a project where one is named, and hand its start to a job or queue it.

        An app of status `team` is for the accounts `MOODY_TEAM_EMAILS` names,
        since its license is the user's own (Nuke's is per person), and Nuke
        has as many seats open at once as `MOODY_NUKE_SEATS` says, counted by
        the database with the capacity (`moody_request_session`). An app of
        status `byol` starts for anyone, its licensed part coming with it where
        the user has linked that license (`run_start`); the one such app is
        Unreal Engine, since its license is the only one this service checks.

        Raises:
            Refused: 400 for an app, tier, or region that is not on offer, or a tier without the GPU
                the app needs (`requires_gpu`: Unreal's editor renders only on one), 402 without the credits
                for a first minute, 403 for a team app outside the team, 409 at the user's session limit,
                with every seat of the app taken, or for a tier that is switched off.
        """
        offered = self.catalog.apps.get(app, {})
        if offered.get("status") not in STARTABLE or (offered["status"] == "byol" and app != "unreal"):
            raise Refused(400, "That app is not available yet.")
        if tier not in self.catalog.tiers or region not in self.catalog.regions:
            raise Refused(400, "Unknown tier or region.")
        if tier not in self.config.tiers:
            raise Refused(409, "That tier is not switched on yet. Pick another one.")
        if offered.get("requires_gpu") and not self.catalog.tiers[tier]["gpu"]:
            raise Refused(400, f"{offered['name']} needs a GPU. Pick a tier with one.")
        profile = self.me(user)
        if offered["status"] == "team" and (profile["email"] or user.email).lower() not in self.config.team_emails:
            raise Refused(403, f"{offered['name']} is open to the team's accounts only.")
        row = self.store.rpc(
            "moody_request_session",
            p_user=user.id,
            p_app=app,
            p_tier=tier,
            p_region=region,
            p_credits_per_minute=self.catalog.tiers[tier]["credits_per_minute"],
            p_capacity=self.config.capacity,
            p_project=project_id,
            p_app_seats=self.config.nuke_seats if app == "nuke" else None,
        )
        if row["status"] == "starting":
            self.jobs.start(row["id"])
        return self.public(row)

    def link(self, user: User, session_id: str, stream: str | None = None) -> str:
        """A fresh link to the user's running session: its desktop, or the picture `stream` names.

        Raises:
            Refused: 409 while the session is not running, 404 for a stream the session does not have.
        """
        row = self.owned(user, session_id)
        if row["status"] != "running":
            raise Refused(409, "This session is not running.")
        if stream not in (None, DESKTOP, *STREAMS.get(row["app"], ())):
            raise Refused(404, f"This engine streams no picture named {stream!r}.")
        return self.stream_link(row, stream or DESKTOP)

    def stream_link(self, row: dict[str, Any], stream: str) -> str:
        """A fresh link to one picture of a running session, by its name in `STREAMS`."""
        if stream == UNREAL_VIEW:
            return self.launcher.unreal_link(row["sandbox_id"])
        return self.launcher.link(row["sandbox_id"])

    def streams(self, row: dict[str, Any]) -> list[dict[str, str]] | None:
        """Fresh links to each picture a running engine streams, for an app that streams more than its desktop.

        Nothing for any other engine, and for one whose links cannot be minted right now (a
        Sandbox that just ended, a launcher without the Unreal view), which the next listing
        tries again; the page then opens the desktop through `link`, which says what failed.
        """
        names = STREAMS.get(row["app"])
        if not names or row["status"] != "running":
            return None
        try:
            return [{"name": name, "url": self.stream_link(row, name)} for name in names]
        except (Exception, SystemExit):
            # The launcher module reports a session it cannot read with SystemExit, as its command line does
            return None

    def stop(self, user: User, session_id: str) -> dict[str, Any]:
        """Stop the user's session: at once where it has no Sandbox yet, through a job where it has."""
        row = self.owned(user, session_id)
        if row["status"] == "running":
            self.jobs.stop(row["id"], "stopped")
        elif row["status"] in OPEN:
            row = self.store.rpc("moody_end_session", p_session=row["id"], p_reason="stopped", p_failed=False)
        return self.public(row)

    def running(self, user: User, session_id: str) -> str:
        """The Sandbox of the user's running session, for the tools that act inside it."""
        row = self.owned(user, session_id)
        if row["status"] != "running":
            raise Refused(409, "This session is not running.")
        return row["sandbox_id"]

    # API keys

    def create_key(self, user: User, name: str) -> tuple[dict[str, Any], str]:
        """Make an API key for the user and return its row and its secret, which is shown this once."""
        self.me(user)
        secret = API_KEY_PREFIX + secrets.token_urlsafe(32)
        row = self.store.insert(
            "api_keys",
            {
                "user_id": user.id,
                "name": name.strip()[:60] or "API key",
                "prefix": secret[:12],
                "key_hash": hash_key(secret),
            },
        )
        return self.public_key(row), secret

    @staticmethod
    def public_key(row: dict[str, Any]) -> dict[str, Any]:
        """An API key as the API shows it, without its hash."""
        return {name: row[name] for name in ("id", "name", "prefix", "created_at", "last_used_at")}

    def keys(self, user: User) -> list[dict[str, Any]]:
        """The user's keys that have not been revoked, newest first."""
        rows = self.store.rows("api_keys", user_id=f"eq.{user.id}", revoked_at="is.null", order="created_at.desc")
        return [self.public_key(row) for row in rows]

    def revoke_key(self, user: User, key_id: str) -> None:
        """Revoke one of the user's keys; a key that is not theirs is left alone."""
        if not is_id(key_id):
            return
        self.store.update(
            "api_keys",
            {"revoked_at": datetime.now(timezone.utc).isoformat()},
            id=f"eq.{key_id}",
            user_id=f"eq.{user.id}",
        )

    # Payments

    def checkout(self, user: User, pack_id: str) -> str:
        """The address of a Stripe Checkout page that sells the user one credit pack.

        Raises:
            Refused: 503 while no Stripe keys are configured, 400 for a pack that is not on offer.
        """
        if not self.config.billing:
            raise Refused(503, "Payments are not switched on yet.")
        pack = self.catalog.packs.get(pack_id)
        if pack is None:
            raise Refused(400, "Unknown credit pack.")
        self.me(user)
        response = httpx.post(
            "https://api.stripe.com/v1/checkout/sessions",
            auth=(self.config.stripe_key, ""),
            timeout=20,
            data={
                "mode": "payment",
                "success_url": f"{self.config.site_url}/app/?purchase=success",
                "cancel_url": f"{self.config.site_url}/app/",
                "client_reference_id": user.id,
                "line_items[0][quantity]": "1",
                "line_items[0][price_data][currency]": "usd",
                "line_items[0][price_data][unit_amount]": str(pack["usd"] * 100),
                "line_items[0][price_data][product_data][name]": f"{pack['credits']} {self.catalog.data['brand']} credits",
                "metadata[user_id]": user.id,
                "metadata[credits]": str(pack["credits"]),
            },
        )
        response.raise_for_status()
        return response.json()["url"]

    def stripe_event(self, payload: bytes, signature: str) -> None:
        """Credit a paid checkout that Stripe reports, once however often it reports it.

        The event is taken only with Stripe's signature over the exact bytes
        received and a timestamp from the last five minutes, which is what
        keeps anyone else from granting credits through this route.

        Raises:
            Refused: 400 for a signature that does not verify.
        """
        fields = dict(part.split("=", 1) for part in signature.split(",") if "=" in part)
        stamp = fields.get("t", "")
        expected = hmac.new(
            self.config.stripe_webhook_secret.encode(), stamp.encode() + b"." + payload, hashlib.sha256
        ).hexdigest()
        fresh = stamp.isdigit() and abs(time.time() - int(stamp)) < 300
        if not self.config.billing or not fresh or not hmac.compare_digest(expected, fields.get("v1", "")):
            raise Refused(400, "Bad signature.")
        event = json.loads(payload)
        checkout = event["data"]["object"]
        if event["type"] == "checkout.session.completed" and checkout.get("payment_status") == "paid":
            self.store.rpc(
                "moody_add_credits",
                p_user=checkout["metadata"]["user_id"],
                p_delta=int(checkout["metadata"]["credits"]),
                p_reason="purchase",
                p_reference=checkout["id"],
            )

    # Projects

    @staticmethod
    def public_project(row: dict[str, Any]) -> dict[str, Any]:
        """A project as the API shows it, without its turn's bookkeeping."""
        return {name: row[name] for name in PROJECT_FIELDS}

    def projects(self, user: User) -> list[dict[str, Any]]:
        """The user's projects, most recently updated first."""
        rows = self.store.every("projects", user_id=f"eq.{user.id}", order="updated_at.desc")
        return [self.public_project(row) for row in rows]

    def owned_project(self, user: User, project_id: str) -> dict[str, Any]:
        """The user's project of that ID.

        Raises:
            Refused: 404 where there is none, which is also what another user's project is to this one.
        """
        rows = self.store.rows("projects", id=f"eq.{project_id}", user_id=f"eq.{user.id}") if is_id(project_id) else []
        if not rows:
            raise Refused(404, "No such project.")
        return rows[0]

    def create_project(
        self,
        user: User,
        name: str,
        discipline: str,
        project_format: str,
        github_repo: str | None = None,
        github_branch: str | None = None,
    ) -> dict[str, Any]:
        """Make a project of one of the catalog's disciplines, in one of its formats, with that format's first sections.

        A project made without a format, in a discipline that asks its kind, opens on the card that
        asks it (`opening_card`): the project's first event, written here with no turn and no model.

        With `github_repo`, the project starts linked to that repository (and `github_branch`, where
        given), which is checked as `link_repo` checks it before anything is made: what the studio's
        "Import from GitHub" makes.

        Raises:
            Refused: 400 for a discipline the catalog does not have, or a format its discipline does not;
                for a repository, what `link_repo` refuses.
        """
        offered = self.catalog.disciplines.get(discipline)
        if offered is None:
            raise Refused(400, "Unknown discipline.")
        if project_format and project_format not in offered["formats"]:
            raise Refused(400, f"{offered['name']} has no format {project_format!r}.")
        self.me(user)
        linked = self.readable_repo(user, github_repo, github_branch) if github_repo else (None, None)
        row = self.store.insert(
            "projects",
            {
                "user_id": user.id,
                "name": " ".join(name.split())[:120] or "Untitled project",
                "discipline": discipline,
                "format": project_format,
                "library_sections": default_sections(offered, project_format),
                "github_repo": linked[0],
                "github_branch": linked[1],
            },
        )
        card = None if project_format else self.opening_card(offered)
        if card is not None:
            self.add_event(row["id"], None, "ui", card)
        return self.public_project(row)

    def opening_card(self, discipline: dict[str, Any]) -> dict[str, Any] | None:
        """The card that asks a new project's kind, as its `ui` event, or nothing for a discipline that does not ask.

        A discipline asks where the catalog gives it an `opening`, the card's
        title, and formats to choose from. The card is one `pick` of the
        formats, in the catalog's order, each with the line and the icon its
        `kinds` entry names: the icon is looked up in the catalog's `icons`
        and left out where there is none. Choosing locks the card (`instant`), and `sets`
        names what of the project the choice sets, which is also the pick's
        id, so the message that locks it carries `{format: <the kind>}`
        (`chosen_kind`). The card is built and checked as any other is
        (`genui.card`), so it is one the page renders.

        Raises:
            genui.Invalid: The catalog describes a card the catalog of cards does not allow.
        """
        formats = discipline.get("formats") or []
        if not discipline.get("opening") or not formats:
            return None
        icons = self.catalog.data.get("icons", {})
        options = []
        for name in formats:
            kind = discipline.get("kinds", {}).get(name, {})
            option = {"value": name, "label": name}
            if kind.get("note"):
                option["note"] = kind["note"]
            if icons.get(kind.get("icon")):
                option["icon"] = icons[kind["icon"]]
            options.append(option)
        spec = {"type": "pick", "id": KIND_FIELD, "options": options}
        data, _ = genui.card(
            genui.catalog(), uuid.uuid4().hex[:12], discipline["opening"], spec, None, None, True, None, {}, instant=True
        )
        return {**data, "sets": KIND_FIELD, "media": []}

    def chosen_kind(self, project: dict[str, Any], card: dict[str, Any], value: Any) -> str | None:
        """The kind a message that locks a card chooses for the project, or nothing where the card sets none.

        Raises:
            Refused: 400 for a kind the project's discipline does not offer.
        """
        if card.get("sets") != KIND_FIELD:
            return None
        discipline = self.catalog.disciplines.get(project["discipline"], {})
        chosen = value.get(KIND_FIELD) if isinstance(value, dict) else None
        if not isinstance(chosen, str) or chosen not in discipline.get("formats", []):
            raise Refused(400, f"{discipline.get('name', project['discipline'])} has no format {chosen!r}.")
        return chosen

    def set_kind(self, project: dict[str, Any], chosen: str) -> None:
        """Make a project one of its discipline's kinds, with that kind's first sections where the library is untouched."""
        discipline = self.catalog.disciplines.get(project["discipline"], {})
        changes: dict[str, Any] = {"format": chosen, "updated_at": now()}
        untouched = project["library_sections"] == default_sections(discipline, project["format"])
        if untouched and not self.project_assets(project):
            changes["library_sections"] = default_sections(discipline, chosen)
        self.store.update("projects", changes, id=f"eq.{project['id']}")

    def update_project(
        self,
        user: User,
        project_id: str,
        name: str | None = None,
        pinned: bool | None = None,
        library_sections: list[str] | None = None,
        permissions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Rename the user's project, pin or unpin it, set its library's sections, or set what its agent may do unasked.

        Pinning leaves `updated_at` as it was, so a project keeps its place
        among the recent ones when it is pinned, and so does a change of
        permissions. `permissions` is the whole of them, `{tool: "always"}`:
        a tool left out is one the agent asks about again.

        Raises:
            Refused: 400 for a name that is blank, or permissions that are not a tool's name to `always`.
        """
        row = self.owned_project(user, project_id)
        changes: dict[str, Any] = {}
        if permissions is not None:
            if len(permissions) > 64 or any(
                not isinstance(tool, str) or not TOOL_NAME.fullmatch(tool) or value != ALWAYS
                for tool, value in permissions.items()
            ):
                raise Refused(400, f'Permissions name a tool and say "{ALWAYS}" for it.')
            changes["permissions"] = permissions
        if name is not None:
            cleaned = " ".join(name.split())[:120]
            if not cleaned:
                raise Refused(400, "A project needs a name.")
            changes["name"] = cleaned
        if library_sections is not None:
            changes["library_sections"] = clean_sections(library_sections)
        if changes.keys() - {"permissions"}:
            changes["updated_at"] = now()
        if pinned is not None:
            changes["pinned"] = pinned
        if not changes:
            return self.public_project(row)
        return self.public_project(self.store.update("projects", changes, id=f"eq.{row['id']}")[0])

    def delete_project(self, user: User, project_id: str) -> None:
        """Delete the user's project, with its turn ended, its engines stopped, and its library's files removed."""
        row = self.owned_project(user, project_id)
        self.store.rpc("moody_stop_turn", p_project=row["id"], p_user=user.id, p_stale_seconds=0)
        engines = self.store.rows(
            "sessions", project_id=f"eq.{row['id']}", user_id=f"eq.{user.id}", status=f"in.({','.join(OPEN)})"
        )
        for engine in engines:
            self.stop(user, engine["id"])
        self.store.remove_prefix(LIBRARY_BUCKET, f"{user.id}/{row['id']}")
        self.store.delete("projects", id=f"eq.{row['id']}", user_id=f"eq.{user.id}")

    def touch(self, project_id: str) -> None:
        """Mark a project changed now, which moves it to the top of its user's recent projects."""
        self.store.update("projects", {"updated_at": now()}, id=f"eq.{project_id}")

    # Engines: a project's sessions

    def engines(self, user: User, project_id: str, links: bool = False) -> list[dict[str, Any]]:
        """The project's open engines, then its ten most recent that are over.

        With `links`, a running engine that streams more than its desktop reports each picture
        with a fresh link (`streams`): what the page that lists the engines opens them with. Minting
        one counts as use of the session, so nothing else asks for them. The page's listing also
        reports the clone a running Unreal engine made as it started (`clone`), which it reads on
        the same occasion.
        """
        row = self.owned_project(user, project_id)
        scope = {"user_id": f"eq.{user.id}", "project_id": f"eq.{row['id']}", "order": "created_at.desc"}
        active = self.store.rows("sessions", **scope, status=f"in.({','.join(OPEN)})")
        over = self.store.rows("sessions", **scope, status="in.(ended,failed)", limit="10")
        listed = []
        for session in active + over:
            shown = self.public(session)
            streams = self.streams(session) if links else None
            if streams:
                shown["streams"] = streams
            clone = self.clone_state(session) if links else None
            if clone:
                shown["clone"] = clone
            listed.append(shown)
        return listed

    def clone_state(self, row: dict[str, Any]) -> dict[str, Any] | None:
        """What a running Unreal engine reports of the clone it made as it started, or nothing.

        Nothing for any other engine, for one whose machine made no clone or cannot say (a launcher
        without `clone_status`), and for an answer that is not the machine's contract, `{state:
        "cloning" | "done" | "failed", path, detail}`.
        """
        if row["app"] != "unreal" or row["status"] != "running":
            return None
        try:
            found = self.launcher.clone_status(row["sandbox_id"])
        except (Exception, SystemExit):
            # The launcher module reports a session it cannot read with SystemExit, as its command line does
            return None
        if not isinstance(found, dict) or found.get("state") not in CLONE_STATES:
            return None
        return {"state": found["state"], "path": str(found.get("path") or ""), "detail": str(found.get("detail") or "")}

    def engine_clone(self, user: User, project_id: str, session_id: str) -> dict[str, Any] | None:
        """What one of the project's engines reports of its clone (`clone_state`)."""
        return self.clone_state(self.project_engine(user, project_id, session_id))

    def start_engine(self, user: User, project_id: str, app: str, tier: str, region: str) -> dict[str, Any]:
        """Start an engine for the user's project: a session that opens in the project's folder (`start`)."""
        row = self.owned_project(user, project_id)
        return self.start(user, app, tier, region, project_id=row["id"])

    def project_engine(self, user: User, project_id: str, session_id: str) -> dict[str, Any]:
        """One of the project's engines.

        Raises:
            Refused: 404 for a session that is not this project's.
        """
        row = self.owned(user, session_id)
        if row.get("project_id") != project_id:
            raise Refused(404, "No such engine in this project.")
        return row

    def running_unreal(self, user: User, project_id: str, session_id: str) -> dict[str, Any]:
        """One of the project's engines that runs Unreal Engine.

        Raises:
            Refused: 404 for a session that is not this project's, 409 for one that is not a running
                Unreal engine, saying how to start one.
        """
        try:
            row = self.project_engine(user, project_id, session_id)
        except Refused as refused:
            raise Refused(404, f"No such engine in this project. {self.start_unreal_hint()}") from refused
        if row["app"] != "unreal" or row["status"] != "running":
            what = "is not Unreal Engine" if row["app"] != "unreal" else f"is {row['status']}, not running"
            raise Refused(409, f"That engine {what}. {self.start_unreal_hint()}")
        return row

    def start_unreal_hint(self) -> str:
        """How an Unreal engine is started, for a refusal that needs one."""
        gpus = [tier["id"] for tier in self.catalog.data["tiers"] if tier["gpu"] and tier["id"] in self.config.tiers]
        tiers = f" ({', '.join(gpus)})" if gpus else ""
        return f"Start Unreal Engine on a tier with a GPU{tiers} first."

    def unreal_projects(self, user: User, project_id: str, session_id: str) -> list[dict[str, Any]]:
        """The Unreal projects in a running Unreal engine's workspace, each with how the engine opens it.

        Raises:
            Refused: as `running_unreal` does, and 502 where the machine could not be read.
        """
        row = self.running_unreal(user, project_id, session_id)
        version = self.catalog.apps["unreal"]["version"]
        try:
            found = self.launcher.unreal_projects(row["sandbox_id"])
        except (Exception, SystemExit) as error:
            raise Refused(502, f"The engine could not list its projects: {error}") from error
        return [unreal.found_project(raw, version) for raw in found if isinstance(raw, dict)]

    # The library

    def public_asset(self, row: dict[str, Any], links: dict[str, str]) -> dict[str, Any]:
        """A library entry as the API shows it, its files as the signed links given."""
        asset = {name: row[name] for name in ASSET_FIELDS}
        asset["media"] = [
            {"kind": item["kind"], "url": links.get(item["path"]), "name": item["name"]} for item in row["media"]
        ]
        asset["thumbnail_url"] = next((item["url"] for item in asset["media"] if item["kind"] == "image"), None)
        return asset

    @staticmethod
    def kept_asset(row: dict[str, Any]) -> dict[str, Any]:
        """A library entry as an event of the log keeps it: its fields, and its files by their paths in the bucket.

        `shown_events` turns it into the entry the API shows, with links
        signed for that reading.
        """
        return {**{name: row[name] for name in ASSET_FIELDS}, "media": row["media"]}

    def links(self, rows: list[dict[str, Any]]) -> dict[str, str]:
        """Signed links to every file of these entries, by path, in one call to Storage."""
        paths = [item["path"] for row in rows for item in row["media"]]
        return self.store.sign(LIBRARY_BUCKET, paths, SIGNED_URL_SECONDS) if paths else {}

    def shown_assets(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Library entries as the API shows them."""
        links = self.links(rows)
        return [self.public_asset(row, links) for row in rows]

    def project_assets(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        """Every entry of a project's library, oldest first."""
        return self.store.every("assets", project_id=f"eq.{project['id']}", order="created_at.asc")

    def library(self, user: User, project_id: str) -> dict[str, Any]:
        """The project's library: its sections, and every entry with its files."""
        project = self.owned_project(user, project_id)
        return {"sections": project["library_sections"], "assets": self.shown_assets(self.project_assets(project))}

    def owned_asset(self, project: dict[str, Any], asset_id: str) -> dict[str, Any]:
        """An entry of the project's library.

        Raises:
            Refused: 404 for one that is not this project's.
        """
        found = (
            self.store.rows("assets", id=f"eq.{asset_id}", project_id=f"eq.{project['id']}") if is_id(asset_id) else []
        )
        if not found:
            raise Refused(404, "No such library entry.")
        return found[0]

    def create_asset(
        self,
        user: User,
        project_id: str,
        section: str,
        name: str,
        tag: str | None = None,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add an entry to the user's project's library."""
        project = self.owned_project(user, project_id)
        return self.public_asset(self.new_asset(project, section, name, tag, description, metadata or {}), {})

    def new_asset(
        self,
        project: dict[str, Any],
        section: str,
        name: str,
        tag: str | None,
        description: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Insert a library entry, adding its section to the project's where it is new.

        Raises:
            Refused: 400 for a blank section or name or a malformed tag, 409 for a tag another entry has.
        """
        sections = clean_sections([section])
        cleaned = " ".join(name.split())[:120]
        if not sections or not cleaned:
            raise Refused(400, "A library entry needs a section and a name.")
        tag = normal_tag(tag)
        self.check_tag_free(project, tag, None)
        row = self.store.insert(
            "assets",
            {
                "project_id": project["id"],
                "section": sections[0],
                "name": cleaned,
                "tag": tag,
                "description": description[:4000],
                "metadata": metadata,
            },
        )
        self.add_section(project, sections[0])
        self.touch(project["id"])
        return row

    def check_tag_free(self, project: dict[str, Any], tag: str | None, asset_id: str | None) -> None:
        """Refuse a tag another entry of the project has, with 409."""
        if tag is not None and any(
            row["id"] != asset_id for row in self.store.rows("assets", project_id=f"eq.{project['id']}", tag=f"eq.{tag}")
        ):
            raise Refused(409, f"Another library entry is already tagged {tag}.")

    def add_section(self, project: dict[str, Any], section: str) -> None:
        """Append a section to the project's library where it does not have it, in the row given too."""
        if section.lower() in (name.lower() for name in project["library_sections"]):
            return
        project["library_sections"] = clean_sections([*project["library_sections"], section])
        self.store.update("projects", {"library_sections": project["library_sections"]}, id=f"eq.{project['id']}")

    def update_asset(self, user: User, project_id: str, asset_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Change an entry of the user's project's library; the keys of `changes` are the fields to change."""
        project = self.owned_project(user, project_id)
        row = self.change_asset(project, self.owned_asset(project, asset_id), changes)
        return self.shown_assets([row])[0]

    def change_asset(self, project: dict[str, Any], row: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
        """Change the fields of an entry that `changes` names, a blank tag clearing the tag, and return the entry.

        Raises:
            Refused: 400 for a blank section or name or a malformed tag, 409 for a tag another entry has.
        """
        update: dict[str, Any] = {}
        if "section" in changes:
            sections = clean_sections([changes["section"] or ""])
            if not sections:
                raise Refused(400, "A library entry needs a section.")
            update["section"] = sections[0]
            self.add_section(project, sections[0])
        if "name" in changes:
            update["name"] = " ".join((changes["name"] or "").split())[:120]
            if not update["name"]:
                raise Refused(400, "A library entry needs a name.")
        if "tag" in changes:
            update["tag"] = normal_tag(changes["tag"])
            self.check_tag_free(project, update["tag"], row["id"])
        if "description" in changes:
            update["description"] = (changes["description"] or "")[:4000]
        if "metadata" in changes:
            update["metadata"] = changes["metadata"] or {}
        if not update:
            return row
        update["updated_at"] = now()
        changed = self.store.update("assets", update, id=f"eq.{row['id']}")[0]
        self.touch(project["id"])
        return changed

    def delete_asset(self, user: User, project_id: str, asset_id: str) -> None:
        """Delete an entry of the user's project's library, and its files."""
        project = self.owned_project(user, project_id)
        row = self.owned_asset(project, asset_id)
        paths = [item["path"] for item in row["media"]]
        if paths:
            self.store.remove(LIBRARY_BUCKET, paths)
        self.store.delete("assets", id=f"eq.{row['id']}", project_id=f"eq.{project['id']}")
        self.touch(project["id"])

    def add_media(
        self, user: User, project_id: str, asset_id: str, filename: str, content_type: str, data: bytes
    ) -> dict[str, Any]:
        """Add a file the user uploaded to an entry of their project's library.

        Raises:
            Refused: 400 for an empty file, 413 for one over `MEDIA_LIMIT_BYTES`.
        """
        project = self.owned_project(user, project_id)
        row = self.owned_asset(project, asset_id)
        if not data:
            raise Refused(400, "That file is empty.")
        if len(data) > MEDIA_LIMIT_BYTES:
            raise Refused(413, f"A library file can be up to {MEDIA_LIMIT_BYTES // (1024 * 1024)} MB.")
        return self.shown_assets([self.store_media(project, row, data, content_type, filename)])[0]

    def store_media(
        self, project: dict[str, Any], row: dict[str, Any], data: bytes, content_type: str, filename: str
    ) -> dict[str, Any]:
        """Store a file in the library bucket as the entry's newest, under its user's and project's folder."""
        path = f"{project['user_id']}/{project['id']}/{row['id']}/{uuid.uuid4().hex[:12]}-{safe_name(filename)}"
        self.store.upload(LIBRARY_BUCKET, path, data, content_type)
        item = {"kind": media_kind(content_type), "path": path, "name": filename[:120] or "file", "content_type": content_type}
        changed = self.store.update("assets", {"media": [item, *row["media"]], "updated_at": now()}, id=f"eq.{row['id']}")
        self.touch(project["id"])
        return changed[0]

    def upsert_asset(
        self,
        project: dict[str, Any],
        section: str,
        name: str,
        tag: str | None,
        description: str | None,
        metadata: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], bool]:
        """The agent's write to the library: change the entry with the tag, or make it; returns it and whether it is new.

        Without a tag, the entry is the section's of that name. Metadata given
        is merged into what the entry has, so the agent can add a field
        without restating the rest.
        """
        tag = normal_tag(tag)
        for row in self.project_assets(project):
            if (row["tag"] == tag) if tag else (row["section"].lower() == section.lower() and row["name"] == name):
                changes: dict[str, Any] = {"section": section, "name": name}
                if description is not None:
                    changes["description"] = description
                if metadata is not None:
                    changes["metadata"] = {**row["metadata"], **metadata}
                return self.change_asset(project, row, changes), False
        return self.new_asset(project, section, name, tag, description or "", metadata or {}), True

    def assets_by_tags(self, project: dict[str, Any], tags: list[str]) -> list[dict[str, Any]]:
        """The project's entries with these tags, in the order given.

        Raises:
            Refused: 404 naming the first tag no entry has.
        """
        tagged = {row["tag"]: row for row in self.project_assets(project) if row["tag"]}
        found = []
        for tag in tags:
            row = tagged.get(normal_tag(tag))
            if row is None:
                raise Refused(404, f"No library entry is tagged {tag}.")
            found.append(row)
        return found

    # Events and the agent's turns

    @staticmethod
    def public_event(row: dict[str, Any]) -> dict[str, Any]:
        """An event as the API shows it."""
        return {name: row[name] for name in EVENT_FIELDS}

    @staticmethod
    def turn_running(project: dict[str, Any]) -> bool:
        """Whether the project has a turn whose worker was heard from lately."""
        seen = project.get("turn_seen_at")
        if not project.get("turn_id") or not seen:
            return False
        return (datetime.now(timezone.utc) - datetime.fromisoformat(seen)).total_seconds() < TURN_STALE_SECONDS

    def events(self, user: User, project_id: str, after: int = 0) -> dict[str, Any]:
        """The project's events after the one numbered `after`, up to 500, and whether a turn is running.

        The project is read before the events, so a page told no turn is
        running has every event of the last one, its `turn_end` included.
        """
        project = self.owned_project(user, project_id)
        rows = self.store.rows(
            "project_events", project_id=f"eq.{project['id']}", id=f"gt.{int(after)}", order="id.asc", limit="500"
        )
        return {"events": self.shown_events(rows), "running": self.turn_running(project)}

    @staticmethod
    def event_files(row: dict[str, Any]) -> list[dict[str, Any]]:
        """The files an event of the log shows, each kept by its path in the bucket.

        A `preview`'s items and an interactive card's files (`SIGNED_FILES`),
        the results under a call (`tool_end`'s `media`), and the files of the
        entry a `library` event carries.
        """
        data = row["data"]
        if row["kind"] in SIGNED_FILES:
            return data.get(SIGNED_FILES[row["kind"]], [])
        if row["kind"] == "tool_end":
            return data.get("media", [])
        if row["kind"] == "library":
            return data.get("asset", {}).get("media", [])
        return []

    def shown_events(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Events as the API shows them, every file in them under a link signed for this reading.

        The log keeps a file by its path in the bucket, never by a link: a
        link expires within the hour, and a conversation is what a person
        scrolls back through the next day. So each page of events is signed
        as it is read, in one request for all of its files (`event_files`). A
        preview's or a card's file, or a call's result, that is gone is left
        out; a library entry keeps its place with no link, as the library
        shows it.
        """
        paths = [item["path"] for row in rows for item in self.event_files(row)]
        links = self.store.sign(LIBRARY_BUCKET, paths, SIGNED_URL_SECONDS) if paths else {}
        shown = []
        for row in rows:
            event, data = self.public_event(row), row["data"]
            if row["kind"] in SIGNED_FILES:
                held = SIGNED_FILES[row["kind"]]
                items = [
                    {**{key: value for key, value in item.items() if key != "path"}, "url": links[item["path"]]}
                    for item in data.get(held, [])
                    if item["path"] in links
                ]
                event["data"] = {**data, held: items}
            elif row["kind"] == "tool_end" and "media" in data:
                media = [{"kind": item["kind"], "url": links[item["path"]]} for item in data["media"] if item["path"] in links]
                event["data"] = {**data, "media": media}
            elif row["kind"] == "library" and "asset" in data:
                event["data"] = {**data, "asset": self.public_asset(data["asset"], links)}
            shown.append(event)
        return shown

    def add_event(self, project_id: str, turn_id: str | None, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        """Append an event to a project's log."""
        row = self.store.insert("project_events", {"project_id": project_id, "turn_id": turn_id, "kind": kind, "data": data})
        return self.public_event(row)

    def send_message(self, user: User, project_id: str, text: str, ui: dict[str, Any] | None = None) -> str:
        """Start the agent's turn on the user's project with this message, hand it to a job, and return its ID.

        `ui` locks in an interactive card the agent showed, `{ui_id, value}`:
        the card has to be one of the project's `ui` events, and its state is
        kept on the turn's `user_message` event as it was sent. A message
        that locks a card in may have no words of its own.

        Raises:
            Refused: 503 while no agent is configured or its job cannot be started, 400 for an empty
                message or a `ui` that is not a card and its state, 404 for a card the project never
                showed, 413 for a message over `MESSAGE_LIMIT` or a state over
                `UI_VALUE_LIMIT_BYTES`, 409 while another turn runs.
        """
        if not self.config.agent:
            raise Refused(503, "The agent is not switched on yet.")
        text = text.strip()
        if not text and ui is None:
            raise Refused(400, "Write a message first.")
        if len(text) > MESSAGE_LIMIT:
            raise Refused(413, "That message is too long.")
        project = self.owned_project(user, project_id)
        locked, card = self.locked_card(project, ui) if ui is not None else (None, {})
        kind = self.chosen_kind(project, card, locked["value"]) if locked else None
        turn_id = self.store.rpc(
            "moody_begin_turn",
            p_project=project["id"],
            p_user=user.id,
            p_text=text,
            p_stale_seconds=TURN_STALE_SECONDS,
            p_ui=locked,
        )
        if kind is not None:
            # After the turn is the project's and before its job reads the project: the turn begins knowing its kind
            self.set_kind(project, kind)
        try:
            self.jobs.turn(project["id"], turn_id)
        except Exception as error:
            # Whatever the job runner raised, the turn must not hold the project
            self.add_event(project["id"], turn_id, "error", {"message": "The agent could not be started. Try again."})
            self.store.rpc("moody_end_turn", p_project=project["id"], p_turn=turn_id)
            raise Refused(503, "The agent could not be started. Try again.") from error
        return turn_id

    def locked_card(self, project: dict[str, Any], ui: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """A message's `ui` as the turn's first event keeps it (the card's ID and the state it was locked in with), and the card.

        Raises:
            Refused: 400 for a `ui` without a card's ID or whose state is not JSON, 413 for a state
                over `UI_VALUE_LIMIT_BYTES`, 404 for a card that is no `ui` event of the project.
        """
        ui_id = ui.get("ui_id")
        if not isinstance(ui_id, str) or not ui_id or "value" not in ui:
            raise Refused(400, "A locked-in card is its ui_id and its value.")
        try:
            size = len(json.dumps(ui["value"], allow_nan=False).encode())
        except (TypeError, ValueError):
            raise Refused(400, "A card's value is JSON.") from None
        if size > UI_VALUE_LIMIT_BYTES:
            raise Refused(413, "That card's value is too large.")
        shown = self.store.rows("project_events", project_id=f"eq.{project['id']}", kind="eq.ui")
        card = next((row["data"] for row in shown if row["data"].get("ui_id") == ui_id), None)
        if card is None:
            raise Refused(404, "This project has no such card.")
        return {"ui_id": ui_id, "value": ui["value"]}, card

    def answer_approval(self, user: User, project_id: str, approval_id: str, decision: str) -> bool:
        """Record the person's answer to an approval the agent of their project waits on; returns whether it stands.

        An approval is answered once: the answer does not stand where another
        was recorded first, which is also what a wait that ran out is
        (`moody_resolve_approval`). `always` is kept for the tool among the
        project's permissions by the same function.

        Raises:
            Refused: 400 for an answer that is none of `APPROVAL_DECISIONS`, 404 for an approval the
                project's agent never asked for.
        """
        if decision not in APPROVAL_DECISIONS:
            raise Refused(400, f"An approval is answered with one of {', '.join(APPROVAL_DECISIONS)}.")
        project = self.owned_project(user, project_id)
        standing = self.store.rpc(
            "moody_resolve_approval", p_project=project["id"], p_approval=approval_id, p_decision=decision
        )
        return standing == decision

    def connectors(self, user: User, project_id: str) -> list[dict[str, Any]]:
        """The services the agent of the user's project can use, or could once the person connects them.

        Each is `{id, name, kind, state, detail}`, derived from what the
        deployment is configured with and what the person connected:
        generation through fal, GitHub and the project's repository, the
        loop's web search, and, for a project whose discipline uses Unreal
        Engine, the Epic link its editor is licensed through. A service the
        deployment is not configured for is `off`.
        """
        project = self.owned_project(user, project_id)
        found = [
            {
                "id": "fal", "name": "fal", "kind": "generation",
                "state": "connected" if self.config.generation else "off",
                "detail": "Image and video generation." if self.config.generation else "Generation is not configured on this deployment.",
            }
        ]
        github = self.github_status(user)
        if not github["configured"]:
            state, detail = "off", "GitHub is not configured on this deployment."
        elif not github["connected"]:
            state, detail = "available", "Connect GitHub to link a repository to this project."
        elif project["github_repo"]:
            state, detail = "connected", f"{project['github_repo']}, as {github.get('login', '')}; the agent saves to a branch of its own."
        else:
            state, detail = "available", f"Connected as {github.get('login', '')}; no repository is linked to this project yet."
        found.append({"id": "github", "name": "GitHub", "kind": "repository", "state": state, "detail": detail})
        found.append(
            {
                "id": "web", "name": "Web search", "kind": "search",
                "state": "connected" if self.config.agent else "off",
                "detail": "The agent searches the web and reads pages." if self.config.agent else "The agent is not switched on yet.",
            }
        )
        if "unreal" in self.catalog.disciplines.get(project["discipline"], {}).get("engines", []):
            epic = self.epic_status(user)
            if not epic["configured"]:
                state, detail = "off", "The Epic connection is not configured on this deployment."
            elif not epic["connected"]:
                state, detail = "available", "Connect the GitHub account linked to Epic to bring your own copy of the Unreal Editor."
            elif epic.get("linked"):
                state, detail = "connected", f"{epic.get('login', '')} is linked to Epic: an Unreal engine starts with your copy of the editor."
            else:
                state, detail = "available", epic.get("detail") or f"{epic.get('login', '')} is not linked to Epic yet."
            found.append({"id": "epic", "name": "Epic Games", "kind": "license", "state": state, "detail": detail})
        return found

    def stop_turn(self, user: User, project_id: str) -> bool:
        """Ask the running turn of the user's project to stop; returns whether one was running."""
        project = self.owned_project(user, project_id)
        return bool(
            self.store.rpc(
                "moody_stop_turn", p_project=project["id"], p_user=user.id, p_stale_seconds=TURN_STALE_SECONDS
            )
        )

    # GitHub

    def github_connection(self, user_id: str) -> dict[str, Any] | None:
        """The user's GitHub connection, if they made one."""
        rows = self.store.rows("github_connections", user_id=f"eq.{user_id}")
        return rows[0] if rows else None

    @staticmethod
    def sealed_grant(secret: str, grant: Grant) -> dict[str, Any]:
        """A grant as a connection's row keeps it: each token sealed, and when each expires, from now."""
        moment = datetime.now(timezone.utc)

        def after(seconds: int | None) -> str | None:
            return (moment + timedelta(seconds=seconds)).isoformat() if seconds is not None else None

        return {
            "token_encrypted": seal(secret, grant.token),
            "refresh_token_encrypted": seal(secret, grant.refresh_token) if grant.refresh_token else None,
            "token_expires_at": after(grant.expires_in),
            "refresh_expires_at": after(grant.refresh_token_expires_in),
            "scope": grant.scope,
            "updated_at": moment.isoformat(),
        }

    def github_token(self, user_id: str, lasting: int = TOKEN_MARGIN_SECONDS) -> str | None:
        """The user's GitHub App user token, unsealed, good for at least `lasting` seconds more; nothing unconnected.

        A token closer to its expiry than that is refreshed first, and the new pair stored before
        the token is handed out. GitHub retires a refresh token once it is used, so a refresh that
        loses a race with another (two engines starting at once) reads the pair the other stored.
        A token that does not expire (the app's expiring tokens switched off) is used as it is.

        Raises:
            Refused: 409 where GitHub no longer takes the connection, which the user connects again;
                502 where GitHub did not answer the refresh.
        """
        connection = self.github_connection(user_id)
        token = unseal(self.config.secret_key, connection["token_encrypted"]) if connection else None
        if connection is None or token is None:
            return None
        expires = connection.get("token_expires_at")
        if not expires or (datetime.fromisoformat(expires) - datetime.now(timezone.utc)).total_seconds() >= lasting:
            return token
        sealed = connection.get("refresh_token_encrypted")
        refresh = unseal(self.config.secret_key, sealed) if sealed else None
        if refresh is None:
            raise Refused(409, "Moody's access to GitHub has expired. Connect GitHub again.")
        try:
            grant = self.github.refresh(self.config.github_app_client_id, self.config.github_app_client_secret, refresh)
        except GitHubError as error:
            again = self.github_connection(user_id)
            if again is not None and again["token_encrypted"] != connection["token_encrypted"]:
                renewed = unseal(self.config.secret_key, again["token_encrypted"])
                if renewed is not None:
                    return renewed
            if error.status in (400, 401):
                raise Refused(409, "GitHub no longer accepts this connection. Connect GitHub again.") from error
            raise Refused(502, f"GitHub did not renew Moody's access: {error.message}") from error
        except httpx.HTTPError as error:
            raise Refused(502, "GitHub did not answer. Try again in a moment.") from error
        self.store.update(
            "github_connections", self.sealed_grant(self.config.secret_key, grant), user_id=f"eq.{user_id}"
        )
        return grant.token

    def github_status(self, user: User) -> dict[str, Any]:
        """Whether GitHub can be connected, and the account the user connected."""
        connection = self.github_connection(user.id)
        status: dict[str, Any] = {"configured": self.config.github, "connected": connection is not None}
        if connection:
            status.update(login=connection["login"], avatar_url=connection["avatar_url"])
        return status

    def site_page(self, url: str) -> bool:
        """Whether a URL is a page of the site, the only place GitHub's callbacks send anyone back to.

        It has to be the site's address itself or continue it with a path,
        query, or fragment: a prefix alone would let `https://site.example.evil`
        through for a site at `https://site.example`.
        """
        site = self.config.site_url.rstrip("/")
        if not site or not url.startswith(site) or any(character in url for character in "\\\r\n\t "):
            return False
        return len(url) == len(site) or url[len(site)] in "/?#"

    def callback_url(self, api_url: str, flow: str = "github") -> str:
        """Where GitHub sends a user back to: this API's callback of the flow, which its app names too."""
        return f"{(self.config.api_url or api_url).rstrip('/')}/v1/{flow}/callback"

    def github_connect(self, user: User, return_to: str, api_url: str) -> str:
        """The address of the GitHub App's authorization page, where the user lets it act for them.

        Raises:
            Refused: 503 while no GitHub App is configured, 400 for a `return_to` that is not a page of the site.
        """
        if not self.config.github:
            raise Refused(503, "GitHub is not switched on yet.")
        if not self.site_page(return_to):
            raise Refused(400, "return_to has to be a page of this site.")
        self.me(user)
        state = sign_state(self.config.secret_key, user.id, return_to)
        return self.github.authorize_url(self.config.github_app_client_id, self.callback_url(api_url), state)

    def github_install(self, user: User, return_to: str) -> str:
        """The address of the GitHub App's installation page, for a repository the picker does not list.

        There the user installs the app on their account or an organization, picking its
        repositories, or, in an organization that keeps installing to its owners, asks them to;
        the owner approves once for everyone. The state is signed as connecting's is, so where
        GitHub brings it back to the callback the user returns to the page they left.

        Raises:
            Refused: as `github_connect` does.
        """
        if not self.config.github:
            raise Refused(503, "GitHub is not switched on yet.")
        if not self.site_page(return_to):
            raise Refused(400, "return_to has to be a page of this site.")
        return self.github.install_url(
            self.config.github_app_slug, sign_state(self.config.secret_key, user.id, return_to)
        )

    def github_callback(self, code: str, state: str, error: str, api_url: str, setup_action: str = "") -> str:
        """Finish a connection GitHub sent a user back from, and return the page to send them on to.

        GitHub comes here from its authorization page, and from the app's installation page,
        since the app asks for the user's authorization during installation. The second does not
        always carry Moody's state: GitHub does not return a state when it starts the
        authorization itself, and an owner approving a member's request arrives from GitHub's own
        email. Without a state signed here nobody is known to connect, so such an arrival is sent
        to the studio with what happened (`setup_action`) and its code is never exchanged; the
        user who asked is already connected, and the installation's repositories reach their
        token as they are.

        Raises:
            Refused: 400 for a state this deployment did not sign, one that expired, or one naming a
                page off the site, outside an installation's return; then nothing is exchanged and
                no page is visited.
        """
        outcome = {"install": "installed", "update": "installed", "request": "requested"}.get(setup_action, "connected")
        payload = read_state(self.config.secret_key, state) if self.config.github else None
        if payload is None or not self.site_page(payload["r"]):
            if self.config.github and setup_action in INSTALL_ACTIONS and self.site_page(f"{self.config.site_url}/app/"):
                return with_query(f"{self.config.site_url.rstrip('/')}/app/", github=outcome)
            raise Refused(400, "This GitHub sign-in link is not valid. Start again from Moody.")
        if error or not code:
            return with_query(payload["r"], github=outcome if setup_action in INSTALL_ACTIONS and not error else "failed")
        try:
            grant = self.github.exchange(
                self.config.github_app_client_id, self.config.github_app_client_secret, code, self.callback_url(api_url)
            )
            account = self.github.user(grant.token)
        except (GitHubError, httpx.HTTPError):
            return with_query(payload["r"], github="failed")
        self.store.upsert(
            "github_connections",
            {
                "user_id": payload["u"],
                "login": account["login"],
                "github_id": account.get("id"),
                "name": account.get("name") or "",
                "avatar_url": account.get("avatar_url") or "",
                **self.sealed_grant(self.config.secret_key, grant),
            },
            on_conflict="user_id",
        )
        return with_query(payload["r"], github=outcome)

    def github_disconnect(self, user: User) -> dict[str, Any]:
        """Forget the user's GitHub connection and its tokens; returns what `GET /v1/github` now says.

        The authorization stays on GitHub, where the user revokes it in their settings; the Epic
        connection is its own (`epic_disconnect`).
        """
        self.store.delete("github_connections", user_id=f"eq.{user.id}")
        return self.github_status(user)

    def require_github(self, user_id: str, lasting: int = TOKEN_MARGIN_SECONDS) -> str:
        """The user's GitHub token, good for at least `lasting` seconds more (`github_token`).

        Raises:
            Refused: 503 while no GitHub App is configured, 409 where the user has not connected an account
                or has to connect it again, 502 where GitHub did not answer a refresh.
        """
        if not self.config.github:
            raise Refused(503, "GitHub is not switched on yet.")
        token = self.github_token(user_id, lasting)
        if not token:
            raise Refused(409, "Connect GitHub first.")
        return token

    @staticmethod
    def github_refusal(error: GitHubError) -> Refused:
        """What a refusal of GitHub's is to the user."""
        if error.status == 401:
            return Refused(409, "GitHub no longer accepts this connection. Connect GitHub again.")
        if error.status == 404:
            return Refused(
                404,
                "GitHub has no such repository or file, or Moody cannot reach it: its GitHub App is not installed "
                "there, or this account cannot read it.",
            )
        if error.status == 403 and "not accessible by integration" in error.message.lower():
            return Refused(
                409,
                "Moody's GitHub App may not do that in this repository: it is not installed there, or the "
                "installation does not include this repository.",
            )
        if error.status in (403, 409, 422):
            return Refused(409, f"GitHub refused: {error.message}")
        return Refused(502, f"GitHub refused: {error.message}")

    def github_repos(self, user: User) -> list[dict[str, Any]]:
        """The repositories the user can pick: those of the GitHub App's installations they reach, newest first.

        A repository whose owner has not installed the app is not among them, which is what the
        studio's install link is for (`github_install`). At most `REPO_LIMIT` are listed.
        """
        token = self.require_github(user.id)
        found: dict[str, dict[str, Any]] = {}
        try:
            for installation in self.github.installations(token):
                left = REPO_LIMIT - len(found)
                if left <= 0:
                    break
                for repo in self.github.installation_repositories(token, installation["id"], left):
                    found.setdefault(repo["full_name"], repo)
        except GitHubError as error:
            raise self.github_refusal(error) from error
        except httpx.HTTPError as error:
            raise Refused(502, "GitHub did not answer. Try again in a moment.") from error
        repos = sorted(found.values(), key=lambda repo: repo.get("updated_at") or "", reverse=True)
        return [{key: repo.get(key) for key in ("full_name", "private", "html_url", "updated_at")} for repo in repos]

    def readable_repo(self, user: User, repo: str | None, branch: str | None = None) -> tuple[str, str | None]:
        """A repository the user's GitHub App token can read, as GitHub names it, and the branch asked for.

        Reading is enough to link: a developer whose team's game they can only read still asks the
        agent about its assets. Writing is checked where it happens, since the agent writes only to a
        branch of its own (`github_save`), which needs push access and says so when it has none.
        Moody's app cannot make a repository (it asks for no administration permission), so the
        studio sends the user to GitHub's own page for a new one.

        Raises:
            Refused: 400 for a malformed name or branch or none, 403 for a repository the account cannot
                read, 404 for one GitHub does not show this token or a branch it does not have, 409
                without a GitHub connection.
        """
        if not repo:
            raise Refused(400, "Name a repository as owner/name. To make a new one, create it on GitHub, then link it.")
        if not REPO_FULL_NAME.fullmatch(repo):
            raise Refused(400, "Name the repository as owner/name.")
        if branch is not None and not BRANCH_NAME.fullmatch(branch):
            raise Refused(400, "That is not a branch name.")
        token = self.require_github(user.id)
        try:
            found = self.github.repo(token, repo)
            if not found.get("permissions", {}).get("pull"):
                raise Refused(403, "This GitHub account cannot read that repository.")
            if branch is not None and self.github.head(token, found["full_name"], branch) is None:
                raise Refused(404, f"{found['full_name']} has no branch {branch}.")
        except GitHubError as error:
            raise self.github_refusal(error) from error
        return found["full_name"], branch

    def link_repo(
        self, user: User, project_id: str, repo: str | None = None, branch: str | None = None
    ) -> dict[str, Any]:
        """Link the user's project to a repository they can read (`readable_repo`), at its default branch or `branch`.

        The branch is the one an Unreal engine clones as it starts; the agent's own branch is made
        from the default branch whatever this is.
        """
        project = self.owned_project(user, project_id)
        full_name, chosen = self.readable_repo(user, repo, branch)
        changed = self.store.update(
            "projects",
            {"github_repo": full_name, "github_branch": chosen, "updated_at": now()},
            id=f"eq.{project['id']}",
        )
        return self.public_project(changed[0])

    def unlink_repo(self, user: User, project_id: str) -> dict[str, Any]:
        """Unlink the user's project from its repository, which stays as it is on GitHub."""
        project = self.owned_project(user, project_id)
        changed = self.store.update(
            "projects", {"github_repo": None, "github_branch": None, "updated_at": now()}, id=f"eq.{project['id']}"
        )
        return self.public_project(changed[0])

    def clone_for(self, session: dict[str, Any]) -> Clone | None:
        """For an Unreal start of a project linked to a repository, what its machine clones, with a fresh token.

        The token is the user's GitHub App token, refreshed where it has less than
        `CLONE_TOKEN_SECONDS` left, so the clone and the work after it have most of its eight
        hours; a later refresh (another start, an agent's call near expiry) retires it. The
        branch is the one the project chose, else the repository's default. The name and address
        commits carry are the user's GitHub name, else login, and their GitHub-provided noreply
        address (`<id>+<login>@users.noreply.github.com`). Without GitHub configured or connected
        there is nothing to clone with; where GitHub fails, the engine starts without the clone
        rather than not at all, and says why in the job's log.
        """
        if session.get("app") != "unreal" or not session.get("project_id") or not self.config.github:
            return None
        projects = self.store.rows("projects", id=f"eq.{session['project_id']}", user_id=f"eq.{session['user_id']}")
        repo = projects[0].get("github_repo") if projects else None
        connection = self.github_connection(session["user_id"]) if repo else None
        if not repo or connection is None:
            return None
        try:
            token = self.github_token(session["user_id"], CLONE_TOKEN_SECONDS)
            if token is None:
                return None
            branch = projects[0].get("github_branch") or self.github.repo(token, repo)["default_branch"]
        except (Refused, GitHubError, httpx.HTTPError) as error:
            print(f"session {session['id']}: starting without cloning {repo}: {getattr(error, 'message', error)}")
            return None
        login = connection["login"]
        address = f"{connection['github_id']}+{login}" if connection.get("github_id") else login
        return Clone(
            repo=repo,
            branch=branch,
            name=connection.get("name") or login,
            email=f"{address}@users.noreply.github.com",
            token=token,
        )

    # Epic: the GitHub account linked to it, which the user's copy of Unreal Engine is pulled with

    def epic_connection(self, user_id: str) -> dict[str, Any] | None:
        """The user's Epic connection, if they made one."""
        rows = self.store.rows("epic_connections", user_id=f"eq.{user_id}")
        return rows[0] if rows else None

    def epic_status(self, user: User) -> dict[str, Any]:
        """Whether Epic can be connected, the GitHub account the user connected for it, and whether it is linked.

        `linked` is `epic_link`'s answer, which asks the registry, and `detail` says why it is
        unknown where it is.
        """
        connection = self.epic_connection(user.id)
        linked, detail = self.epic_link(user.id)
        status: dict[str, Any] = {"configured": self.config.epic, "connected": connection is not None, "linked": linked}
        if connection:
            status["login"] = connection["login"]
        if linked is None and connection is not None:
            status["detail"] = detail
        return status

    def epic_link(self, user_id: str) -> tuple[bool | None, str]:
        """Whether the user's Epic connection may pull Epic's image of Unreal Engine, and why not where it is not known.

        `True` and `False` are the registry's answer for the connected account (`registry_pull`),
        `False` once GitHub confirms the token is still good, since the registry refuses a token
        it does not take the same way. `None` is unknown: no Epic connected, a token GitHub no
        longer takes, or GitHub not answering; the reason says which, for the person.
        """
        connection = self.epic_connection(user_id) if self.config.epic else None
        if connection is None:
            return None, (
                "Connect Epic first, in the project's Environment panel, with the GitHub account your Epic account "
                "is linked to: the Unreal Editor comes with that Epic account."
            )
        token = unseal(self.config.secret_key, connection["token_encrypted"])
        if token is None:
            return None, "Connect Epic again, in the project's Environment panel."
        try:
            if self.github.registry_pull(connection["login"], token):
                return True, ""
            self.github.user(token)
        except GitHubError as error:
            if error.status == 401:
                return None, "GitHub no longer accepts your Epic connection. Connect Epic again."
            return None, f"GitHub refused Moody's check of your Epic link: {error.message}"
        except httpx.HTTPError:
            return None, "GitHub did not answer Moody's check of your Epic link. Try again in a moment."
        return False, ""

    def editor_license(self, user_id: str) -> tuple[bool, str]:
        """Whether the user's own copy of the Unreal Editor can be pulled for them, and what to do where it cannot.

        The answer is `epic_link`'s; where the account is not linked, it is the catalog's steps
        that link it, so the agent says the one thing the person does, at the moment they ask for
        the editor.
        """
        linked, reason = self.epic_link(user_id)
        if linked:
            return True, ""
        if linked is None:
            return False, reason
        app = self.catalog.apps["unreal"]
        steps = " ".join(f"{number}. {step}" for number, step in enumerate(app["license"]["steps"], 1))
        return False, (
            "The Unreal Editor runs on your own Epic account, and the GitHub account you connected for Epic is not "
            f"linked to one yet. {steps}"
        )

    def own_copy(self, session: dict[str, Any]) -> OwnCopy | None:
        """For a start of an app with a part on the user's own license, that part where they have linked it.

        Where the link shows, the launcher keeps the login and token of the user's Epic
        connection, which their copy is pulled with, and the copy is described; otherwise the app
        starts without it. Read at the start itself, so a session that waited in the queue starts
        with the connection the user has then, and a registry that does not answer starts the
        desktop rather than nothing.
        """
        if self.catalog.apps.get(session["app"], {}).get("status") != "byol" or not self.epic_link(session["user_id"])[0]:
            return None
        connection = self.epic_connection(session["user_id"])
        token = unseal(self.config.secret_key, connection["token_encrypted"]) if connection else None
        if connection is None or token is None:
            return None
        self.launcher.keep_registry_credential(session["user_id"], connection["login"], token)
        return OwnCopy(self.catalog.apps[session["app"]]["version"])

    def epic_connect(self, user: User, return_to: str, api_url: str) -> str:
        """The address of the Epic OAuth App's authorization page, which asks to read packages and nothing else.

        Raises:
            Refused: 503 while no Epic OAuth App is configured, 400 for a `return_to` that is not a page of the site.
        """
        if not self.config.epic:
            raise Refused(503, "Connecting Epic is not switched on yet.")
        if not self.site_page(return_to):
            raise Refused(400, "return_to has to be a page of this site.")
        self.me(user)
        state = sign_state(self.config.secret_key, user.id, return_to, flow=EPIC_FLOW)
        return self.github.authorize_url(
            self.config.epic_client_id, self.callback_url(api_url, EPIC_FLOW), state, scope=EPIC_SCOPE
        )

    def epic_callback(self, code: str, state: str, error: str, api_url: str) -> str:
        """Finish an Epic connection GitHub sent a user back from, and return the page to send them on to.

        A registry credential the launcher already keeps for the user takes the new token; a user
        who never started an app on their own license gets none from connecting.

        Raises:
            Refused: 400 for a state this deployment did not sign for this flow, one that expired, or one
                naming a page off the site; then nothing is exchanged and no page is visited.
        """
        payload = read_state(self.config.secret_key, state, flow=EPIC_FLOW) if self.config.epic else None
        if payload is None or not self.site_page(payload["r"]):
            raise Refused(400, "This sign-in link is not valid. Start again from Moody.")
        if error or not code:
            return with_query(payload["r"], epic="failed")
        try:
            grant = self.github.exchange(
                self.config.epic_client_id,
                self.config.epic_client_secret,
                code,
                self.callback_url(api_url, EPIC_FLOW),
            )
            account = self.github.user(grant.token)
        except (GitHubError, httpx.HTTPError):
            return with_query(payload["r"], epic="failed")
        self.store.upsert(
            "epic_connections",
            {
                "user_id": payload["u"],
                "login": account["login"],
                "token_encrypted": seal(self.config.secret_key, grant.token),
                "scope": grant.scope,
                "updated_at": now(),
            },
            on_conflict="user_id",
        )
        try:
            self.launcher.keep_registry_credential(payload["u"], account["login"], grant.token, create=False)
        except Exception:
            # The connection is made; the next start of an app on the user's own license writes
            # the credential again before it pulls anything
            pass
        return with_query(payload["r"], epic="connected")

    def epic_disconnect(self, user: User) -> dict[str, Any]:
        """Forget the user's Epic connection, its token, and the registry credential kept from it.

        The credential goes first, so a disconnect the launcher fails leaves the connection there
        for the user to disconnect again, rather than a token in Modal that nothing points at.
        Returns what `GET /v1/epic` now says.
        """
        self.launcher.forget_registry_credential(user.id)
        self.store.delete("epic_connections", user_id=f"eq.{user.id}")
        return self.epic_status(user)

    # Jobs

    def run_start(self, session_id: str) -> None:
        """Start a `starting` session's Sandbox and mark it running, or mark it failed with the reason."""
        rows = self.store.rows("sessions", id=f"eq.{session_id}", status="eq.starting")
        if not rows:
            return
        session = rows[0]
        tier = self.catalog.tiers[session["tier"]]
        region = session["region"] if self.config.pin_regions and session["region"] != "auto" else None
        try:
            sandbox_id = self.launcher.start(
                session, tier, region, own_copy=self.own_copy(session), clone=self.clone_for(session)
            )
        except Exception as error:
            self.store.rpc("moody_end_session", p_session=session_id, p_reason=f"start failed: {error}"[:300], p_failed=True)
            return
        started = self.store.rpc("moody_session_started", p_session=session_id, p_sandbox_id=sandbox_id)
        if not started or not started.get("id"):
            # Stopped while it was starting: nothing may be left running for it
            self.launcher.stop(sandbox_id)

    def run_stop(self, session_id: str, reason: str) -> None:
        """Stop a running session's Sandbox and close its row."""
        rows = self.store.rows("sessions", id=f"eq.{session_id}", status="eq.running")
        if not rows:
            return
        self.launcher.stop(rows[0]["sandbox_id"])
        self.store.rpc("moody_end_session", p_session=session_id, p_reason=reason, p_failed=False)

    def reconcile(self) -> dict[str, int]:
        """One round of upkeep over every open session; returns what it did, by kind.

        A Sandbox that ended with status 0 ended itself for being unused, and
        one that ended on the signal a stop sends was stopped; anything else
        is a crash, which is not charged for its last minute.
        """
        did = {"ended": 0, "out_of_credits": 0, "failed": 0, "started": 0}
        for session in self.store.rows("sessions", status="eq.running"):
            status = self.launcher.state(session["sandbox_id"])
            if status is None:
                left = self.store.rpc("moody_charge_session", p_session=session["id"], p_final=False)
                if left == 0:
                    self.jobs.stop(session["id"], "out of credits")
                    did["out_of_credits"] += 1
                continue
            reason = {0: "idle", 143: "stopped"}.get(status, f"crashed (exit {status})")
            self.store.rpc("moody_end_session", p_session=session["id"], p_reason=reason, p_failed=status not in (0, 143))
            did["ended" if status in (0, 143) else "failed"] += 1
        now = datetime.now(timezone.utc)
        for session in self.store.rows("sessions", status="eq.starting"):
            waited = (now - datetime.fromisoformat(session["claimed_at"])).total_seconds()
            if waited > START_LIMIT_SECONDS:
                self.store.rpc("moody_end_session", p_session=session["id"], p_reason="start timed out", p_failed=True)
                did["failed"] += 1
        for session in self.store.rpc("moody_claim_queued", p_capacity=self.config.capacity) or []:
            self.jobs.start(session["id"])
            did["started"] += 1
        return did
