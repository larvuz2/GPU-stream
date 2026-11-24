# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""What Lathe does for a user, whoever asks: the web API and the MCP endpoint both call this.

A session is a row in Supabase and a Sandbox on Modal, and this module keeps the
two in step. The row moves only through the database's own functions
(`lathe/supabase/migrations`), each one transaction, so the rules about
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

Lathe Studio adds projects around that. A project is a row its user owns, and
every route that names one finds it through the user first (`owned_project`),
so another user's project, its library, its events, and its engines are a 404
here, never a filter a caller could widen. An engine is a session started for
a project: the same credits, queue, and capacity, opened in the project's
folder of the user's workspace. The library's entries are rows of the project
and their files objects of a private Storage bucket, handed out only as signed
links that expire. What the agent does in a project arrives as an append-only
log of events the page polls (`events`), and a message to the agent claims the
project's one turn in the database before a job runs it (`send_message`,
`agent.py`). The user's GitHub account is connected through an OAuth App whose
token is kept sealed (`github_client.py`).

An app of status `byol` runs on a license the user brings, checked before it
starts. Unreal Engine's is the user's Epic account, which Epic links to a
GitHub account: the session starts only while the user's connected GitHub
account shows that link (`epic_link`), and its image is pulled from Epic's
registry with that user's own GitHub login and token, since Epic's license
lets each user have their copy but not Lathe hand one copy around
(`lathe/UNREAL.md`). The launcher keeps that credential as the user's own
registry credential (`Launcher.keep_registry_credential`), written again at
every start of the app and when the user connects GitHub again, and forgotten
when they disconnect it; it is never kept beside a session or used for another
user's image.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx

from github_client import GitHub, GitHubError, read_state, reads_packages, seal, sign_state, unseal

IDLE_SECONDS = 600
LIFETIME_SECONDS = 8 * 3600
READY_SECONDS = 120
# A session still `starting` after this long has lost its job
START_LIMIT_SECONDS = 300
OPEN = ("queued", "starting", "running")
# The catalog statuses an app can be started under: anyone's, the team's, or on the user's own license
STARTABLE = ("available", "team", "byol")
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
API_KEY_PREFIX = "lathe_"
# A turn not heard from for this long has lost its worker (`agent.py` beats every 20 seconds)
TURN_STALE_SECONDS = 120
LIBRARY_BUCKET = "library"
SIGNED_URL_SECONDS = 3600
MEDIA_LIMIT_BYTES = 200 * 1024 * 1024
MESSAGE_LIMIT = 20000
PROJECT_FIELDS = (
    "id",
    "name",
    "discipline",
    "format",
    "pinned",
    "created_at",
    "updated_at",
    "github_repo",
    "library_sections",
    "plan",
)
ASSET_FIELDS = ("id", "section", "name", "tag", "description", "metadata", "created_at", "updated_at")
EVENT_FIELDS = ("id", "turn_id", "kind", "data", "created_at")
PLAN_STATUSES = ("pending", "active", "done", "blocked")
SECTION_LIMIT = 30
TAG_BODY = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
REPO_NAME = re.compile(r"[A-Za-z0-9._-]{1,100}")
REPO_FULL_NAME = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}")


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
    # The GitHub OAuth App users connect their accounts through
    github_client_id: str = ""
    github_client_secret: str = ""
    # Signs GitHub's `state` and seals the tokens it grants; any long random string
    secret_key: str = ""
    # The accounts, by email in lowercase, that may start apps of status `team`
    team_emails: frozenset[str] = field(default_factory=frozenset)
    # Nuke sessions that may be open at once across all users: the seats its license has
    nuke_seats: int = 2
    # The API's own address, where it differs from the one a request arrives at
    api_url: str = ""

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
        """Whether users can connect GitHub accounts."""
        return bool(self.github_client_id and self.github_client_secret and self.secret_key)


class Catalog:
    """The disciplines, apps, tiers, regions, and credit packs on offer, read from `lathe/catalog.json`.

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
        self, session: dict[str, Any], tier: dict[str, Any], region: str | None, own_copy: OwnCopy | None = None
    ) -> str:
        """Start the session's Sandbox, wait until it streams, and return the Sandbox's ID.

        `own_copy` is given for an app the user brings the license of, whose image is pulled with
        the registry credential kept for the session's user.
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

    def stop(self, sandbox_id: str) -> None:
        """End the session, keeping the scene Blender has open."""

    def blender_python(self, sandbox_id: str, code: str) -> tuple[int, str]:
        """Run Python in the session's Blender and return its status and output."""

    def screenshot(self, sandbox_id: str) -> bytes:
        """The session's screen as a JPEG."""

    def exec(self, sandbox_id: str, command: str, timeout: int) -> tuple[int, str]:
        """Run a shell command in the session's environment, as its user, and return its status and output."""

    def filmcraft(self, sandbox_id: str, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Call a method of FilmCraft's command channel in the session and return its answer.

        Raises:
            RuntimeError: FilmCraft refused the call or did not answer, with why.
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


def default_sections(discipline: str, project_format: str) -> list[str]:
    """The library sections a new project starts with: a film's cast and world, a commercial's products and shots."""
    if discipline != "media":
        return []
    if project_format == "Commercial":
        return ["Products", "Shots"]
    return ["Characters", "Environments", "Props"]


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
            user_id = self.store.rpc("lathe_use_api_key", p_key_hash=hash_key(credential))
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
            "lathe_ensure_profile", p_user=user.id, p_email=user.email, p_signup_credits=self.catalog.signup_credits
        )
        return {
            "id": profile["id"],
            "email": profile["email"],
            "credits": profile["credits"],
            "max_sessions": profile["max_sessions"],
        }

    # Sessions

    def public(self, row: dict[str, Any]) -> dict[str, Any]:
        """A session as the API shows it: no Sandbox ID, and its place in the queue while it waits."""
        session = {name: row[name] for name in SESSION_FIELDS}
        session["queue_position"] = (
            self.store.rpc("lathe_queue_position", p_session=row["id"]) if row["status"] == "queued" else None
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

        An app of status `team` is for the accounts `LATHE_TEAM_EMAILS` names,
        since its license is the user's own (Nuke's is per person), and Nuke
        has as many seats open at once as `LATHE_NUKE_SEATS` says, counted by
        the database with the capacity (`lathe_request_session`). An app of
        status `byol` starts for a user whose own license for it is linked
        (`require_own_license`).

        Raises:
            Refused: 400 for an app, tier, or region that is not on offer, or a tier without the GPU
                the app needs (`requires_gpu`: Unreal's editor renders only on one), 402 without the credits
                for a first minute, 403 for a team app outside the team or an own license that is
                not linked, 409 at the user's session limit, with every seat of the app taken, for a
                tier that is switched off, or while the link cannot be checked.
        """
        offered = self.catalog.apps.get(app, {})
        if offered.get("status") not in STARTABLE:
            raise Refused(400, "That app is not available yet.")
        if tier not in self.catalog.tiers or region not in self.catalog.regions:
            raise Refused(400, "Unknown tier or region.")
        if tier not in self.config.tiers:
            raise Refused(409, "That tier is not switched on yet. Pick another one.")
        if offered.get("requires_gpu") and not self.catalog.tiers[tier]["gpu"]:
            raise Refused(400, f"{offered['name']} needs a GPU. Pick a tier with one.")
        if offered["status"] == "byol":
            self.require_own_license(user.id, offered)
        profile = self.me(user)
        if offered["status"] == "team" and (profile["email"] or user.email).lower() not in self.config.team_emails:
            raise Refused(403, f"{offered['name']} is open to the team's accounts only.")
        row = self.store.rpc(
            "lathe_request_session",
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

    def link(self, user: User, session_id: str) -> str:
        """A fresh link to the user's running session.

        Raises:
            Refused: 409 while the session is not running.
        """
        row = self.owned(user, session_id)
        if row["status"] != "running":
            raise Refused(409, "This session is not running.")
        return self.launcher.link(row["sandbox_id"])

    def stop(self, user: User, session_id: str) -> dict[str, Any]:
        """Stop the user's session: at once where it has no Sandbox yet, through a job where it has."""
        row = self.owned(user, session_id)
        if row["status"] == "running":
            self.jobs.stop(row["id"], "stopped")
        elif row["status"] in OPEN:
            row = self.store.rpc("lathe_end_session", p_session=row["id"], p_reason="stopped", p_failed=False)
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
                "lathe_add_credits",
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

    def create_project(self, user: User, name: str, discipline: str, project_format: str) -> dict[str, Any]:
        """Make a project of one of the catalog's disciplines, in one of its formats, with that format's first sections.

        Raises:
            Refused: 400 for a discipline the catalog does not have, or a format its discipline does not.
        """
        offered = self.catalog.disciplines.get(discipline)
        if offered is None:
            raise Refused(400, "Unknown discipline.")
        if project_format and project_format not in offered["formats"]:
            raise Refused(400, f"{offered['name']} has no format {project_format!r}.")
        self.me(user)
        row = self.store.insert(
            "projects",
            {
                "user_id": user.id,
                "name": " ".join(name.split())[:120] or "Untitled project",
                "discipline": discipline,
                "format": project_format,
                "library_sections": default_sections(discipline, project_format),
            },
        )
        return self.public_project(row)

    def update_project(
        self,
        user: User,
        project_id: str,
        name: str | None = None,
        pinned: bool | None = None,
        library_sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """Rename the user's project, pin or unpin it, or set its library's sections.

        Pinning leaves `updated_at` as it was, so a project keeps its place
        among the recent ones when it is pinned.

        Raises:
            Refused: 400 for a name that is blank.
        """
        row = self.owned_project(user, project_id)
        changes: dict[str, Any] = {}
        if name is not None:
            cleaned = " ".join(name.split())[:120]
            if not cleaned:
                raise Refused(400, "A project needs a name.")
            changes["name"] = cleaned
        if library_sections is not None:
            changes["library_sections"] = clean_sections(library_sections)
        if changes:
            changes["updated_at"] = now()
        if pinned is not None:
            changes["pinned"] = pinned
        if not changes:
            return self.public_project(row)
        return self.public_project(self.store.update("projects", changes, id=f"eq.{row['id']}")[0])

    def delete_project(self, user: User, project_id: str) -> None:
        """Delete the user's project, with its turn ended, its engines stopped, and its library's files removed."""
        row = self.owned_project(user, project_id)
        self.store.rpc("lathe_stop_turn", p_project=row["id"], p_user=user.id, p_stale_seconds=0)
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

    def engines(self, user: User, project_id: str) -> list[dict[str, Any]]:
        """The project's open engines, then its ten most recent that are over."""
        row = self.owned_project(user, project_id)
        scope = {"user_id": f"eq.{user.id}", "project_id": f"eq.{row['id']}", "order": "created_at.desc"}
        active = self.store.rows("sessions", **scope, status=f"in.({','.join(OPEN)})")
        over = self.store.rows("sessions", **scope, status="in.(ended,failed)", limit="10")
        return [self.public(session) for session in active + over]

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

    # The library

    def public_asset(self, row: dict[str, Any], links: dict[str, str]) -> dict[str, Any]:
        """A library entry as the API shows it, its files as the signed links given."""
        asset = {name: row[name] for name in ASSET_FIELDS}
        asset["media"] = [
            {"kind": item["kind"], "url": links.get(item["path"]), "name": item["name"]} for item in row["media"]
        ]
        asset["thumbnail_url"] = next((item["url"] for item in asset["media"] if item["kind"] == "image"), None)
        return asset

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
        return {"events": [self.public_event(row) for row in rows], "running": self.turn_running(project)}

    def add_event(self, project_id: str, turn_id: str | None, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        """Append an event to a project's log."""
        row = self.store.insert("project_events", {"project_id": project_id, "turn_id": turn_id, "kind": kind, "data": data})
        return self.public_event(row)

    def send_message(self, user: User, project_id: str, text: str) -> str:
        """Start the agent's turn on the user's project with this message, hand it to a job, and return its ID.

        Raises:
            Refused: 503 while no agent is configured or its job cannot be started, 400 for an empty
                message, 413 for one over `MESSAGE_LIMIT`, 409 while another turn runs.
        """
        if not self.config.agent:
            raise Refused(503, "The agent is not switched on yet.")
        text = text.strip()
        if not text:
            raise Refused(400, "Write a message first.")
        if len(text) > MESSAGE_LIMIT:
            raise Refused(413, "That message is too long.")
        project = self.owned_project(user, project_id)
        turn_id = self.store.rpc(
            "lathe_begin_turn",
            p_project=project["id"],
            p_user=user.id,
            p_text=text,
            p_stale_seconds=TURN_STALE_SECONDS,
        )
        try:
            self.jobs.turn(project["id"], turn_id)
        except Exception as error:
            # Whatever the job runner raised, the turn must not hold the project
            self.add_event(project["id"], turn_id, "error", {"message": "The agent could not be started. Try again."})
            self.store.rpc("lathe_end_turn", p_project=project["id"], p_turn=turn_id)
            raise Refused(503, "The agent could not be started. Try again.") from error
        return turn_id

    def stop_turn(self, user: User, project_id: str) -> bool:
        """Ask the running turn of the user's project to stop; returns whether one was running."""
        project = self.owned_project(user, project_id)
        return bool(
            self.store.rpc(
                "lathe_stop_turn", p_project=project["id"], p_user=user.id, p_stale_seconds=TURN_STALE_SECONDS
            )
        )

    # GitHub

    def github_connection(self, user_id: str) -> dict[str, Any] | None:
        """The user's GitHub connection, if they made one."""
        rows = self.store.rows("github_connections", user_id=f"eq.{user_id}")
        return rows[0] if rows else None

    def github_token(self, user_id: str) -> str | None:
        """The user's GitHub token, unsealed, if they connected an account."""
        connection = self.github_connection(user_id)
        return unseal(self.config.secret_key, connection["token_encrypted"]) if connection else None

    def github_status(self, user: User, epic: bool = False) -> dict[str, Any]:
        """Whether GitHub can be connected, and the account the user connected.

        With `epic`, also whether that account is linked to Epic (`epic_linked`, from `epic_link`),
        which asks GitHub, so the API's GitHub routes ask for it and the agent's prompt does not.
        """
        connection = self.github_connection(user.id)
        status: dict[str, Any] = {"configured": self.config.github, "connected": connection is not None}
        if connection:
            status.update(login=connection["login"], avatar_url=connection["avatar_url"])
        if epic:
            status["epic_linked"] = self.epic_link(user.id)[0]
        return status

    def epic_link(self, user_id: str) -> tuple[bool | None, str]:
        """Whether the user's GitHub account is linked to an Epic account, and why not where it is not known.

        `True` and `False` are GitHub's answer for the connected account. `None` is unknown: no
        GitHub connected, one connected before Lathe asked for `read:packages` (which reading
        Epic's images takes, so it has to be connected again), a token GitHub no longer takes, or
        GitHub not answering; the reason says which, for the person.
        """
        connection = self.github_connection(user_id) if self.config.github else None
        if connection is None:
            return None, "Connect GitHub first: Unreal Engine runs on the Epic account your GitHub account is linked to."
        token = unseal(self.config.secret_key, connection["token_encrypted"])
        if token is None or not reads_packages(connection.get("scope") or ""):
            return None, "Connect GitHub again, so Lathe can check your Epic link and pull the engine with your account."
        try:
            return self.github.epic_access(token), ""
        except GitHubError as error:
            if error.status == 401:
                return None, "GitHub no longer accepts this connection. Connect GitHub again."
            return None, f"GitHub refused Lathe's check of your Epic link: {error.message}"
        except httpx.HTTPError:
            return None, "GitHub did not answer Lathe's check of your Epic link. Try again in a moment."

    def require_own_license(self, user_id: str, app: dict[str, Any]) -> None:
        """Refuse an app of status `byol` until the user's own license for it is linked.

        The one such license checked is Unreal Engine's Epic account; any other app of the status
        is refused, since nothing here can check its license.

        Raises:
            Refused: 403 with the steps that link it, 409 while the link cannot be checked, 400 for an
                app whose license this service cannot check.
        """
        if app["id"] != "unreal":
            raise Refused(400, "That app is not available yet.")
        linked, reason = self.epic_link(user_id)
        if linked is None:
            raise Refused(409, reason)
        if not linked:
            steps = " ".join(f"{number}. {step}" for number, step in enumerate(app["license"]["steps"], 1))
            raise Refused(
                403, f"{app['name']} runs on your own Epic account, and your GitHub account is not linked to one. {steps}"
            )

    def own_copy(self, session: dict[str, Any]) -> OwnCopy:
        """Have the launcher keep the user's GitHub login and token for a start of their own copy, and describe it.

        Written at the start itself, so a session that waited in the queue starts with the
        connection the user has then.

        Raises:
            Refused: 409 for a user whose GitHub connection is gone or no longer opens.
        """
        connection = self.github_connection(session["user_id"])
        token = unseal(self.config.secret_key, connection["token_encrypted"]) if connection else None
        if connection is None or token is None:
            raise Refused(409, "Connect GitHub again: the engine is pulled with your own GitHub account.")
        self.launcher.keep_registry_credential(session["user_id"], connection["login"], token)
        return OwnCopy(self.catalog.apps[session["app"]]["version"])

    def site_page(self, url: str) -> bool:
        """Whether a URL is a page of the site, the only place GitHub's callback sends anyone back to.

        It has to be the site's address itself or continue it with a path,
        query, or fragment: a prefix alone would let `https://site.example.evil`
        through for a site at `https://site.example`.
        """
        site = self.config.site_url.rstrip("/")
        if not site or not url.startswith(site) or any(character in url for character in "\\\r\n\t "):
            return False
        return len(url) == len(site) or url[len(site)] in "/?#"

    def callback_url(self, api_url: str) -> str:
        """Where GitHub sends a user back to: this API's callback, which the OAuth App names too."""
        return f"{(self.config.api_url or api_url).rstrip('/')}/v1/github/callback"

    def github_connect(self, user: User, return_to: str, api_url: str) -> str:
        """The address of GitHub's page that asks the user to connect their account.

        Raises:
            Refused: 503 while no OAuth App is configured, 400 for a `return_to` that is not a page of the site.
        """
        if not self.config.github:
            raise Refused(503, "GitHub is not switched on yet.")
        if not self.site_page(return_to):
            raise Refused(400, "return_to has to be a page of this site.")
        self.me(user)
        state = sign_state(self.config.secret_key, user.id, return_to)
        return self.github.authorize_url(self.config.github_client_id, self.callback_url(api_url), state)

    def github_callback(self, code: str, state: str, error: str, api_url: str) -> str:
        """Finish a connection GitHub sent a user back from, and return the page to send them on to.

        A registry credential the launcher already keeps for the user takes the new token; a user
        who never started an app on their own license gets none from connecting.

        Raises:
            Refused: 400 for a state this deployment did not sign, one that expired, or one naming a
                page off the site; then nothing is exchanged and no page is visited.
        """
        payload = read_state(self.config.secret_key, state) if self.config.github else None
        if payload is None or not self.site_page(payload["r"]):
            raise Refused(400, "This GitHub sign-in link is not valid. Start again from Lathe.")
        if error or not code:
            return with_query(payload["r"], github="failed")
        try:
            grant = self.github.exchange(
                self.config.github_client_id, self.config.github_client_secret, code, self.callback_url(api_url)
            )
            account = self.github.user(grant.token)
        except (GitHubError, httpx.HTTPError):
            return with_query(payload["r"], github="failed")
        self.store.upsert(
            "github_connections",
            {
                "user_id": payload["u"],
                "login": account["login"],
                "avatar_url": account.get("avatar_url") or "",
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
        return with_query(payload["r"], github="connected")

    def github_disconnect(self, user: User) -> dict[str, Any]:
        """Forget the user's GitHub connection, its token, and the registry credential kept from it.

        The credential goes first, so a disconnect the launcher fails leaves the connection there
        for the user to disconnect again, rather than a token in Modal that nothing points at.
        Returns what `GET /v1/github` now says.
        """
        self.launcher.forget_registry_credential(user.id)
        self.store.delete("github_connections", user_id=f"eq.{user.id}")
        return self.github_status(user, epic=True)

    def require_github(self, user_id: str) -> str:
        """The user's GitHub token.

        Raises:
            Refused: 503 while no OAuth App is configured, 409 where the user has not connected an account.
        """
        if not self.config.github:
            raise Refused(503, "GitHub is not switched on yet.")
        token = self.github_token(user_id)
        if not token:
            raise Refused(409, "Connect GitHub first.")
        return token

    @staticmethod
    def github_refusal(error: GitHubError) -> Refused:
        """What a refusal of GitHub's is to the user."""
        if error.status == 401:
            return Refused(409, "GitHub no longer accepts this connection. Connect GitHub again.")
        if error.status == 404:
            return Refused(404, "GitHub has no such repository or file, or this account cannot reach it.")
        if error.status in (403, 409, 422):
            return Refused(409, f"GitHub refused: {error.message}")
        return Refused(502, f"GitHub refused: {error.message}")

    def github_repos(self, user: User) -> list[dict[str, Any]]:
        """The repositories the user's GitHub account can reach, most recently updated first."""
        token = self.require_github(user.id)
        try:
            repos = self.github.repos(token)
        except GitHubError as error:
            raise self.github_refusal(error) from error
        return [{key: repo[key] for key in ("full_name", "private", "html_url", "updated_at")} for repo in repos]

    def link_repo(
        self, user: User, project_id: str, repo: str | None = None, create: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Link the user's project to a repository they can read, an existing one or a new one of theirs.

        Reading is enough to link: a developer whose team's game they can only read still asks the
        agent about its assets. Writing is checked where it happens, since the agent writes only to a
        branch of its own (`github_save`), which needs push access and says so when it has none.

        Raises:
            Refused: 400 for a malformed repository name or neither, 403 for a repository the account
                cannot read, 409 without a GitHub connection or for a name GitHub refuses.
        """
        project = self.owned_project(user, project_id)
        token = self.require_github(user.id)
        try:
            if create is not None:
                if not REPO_NAME.fullmatch(create.get("name") or ""):
                    raise Refused(400, "A repository name is letters, digits, dots, dashes, and underscores.")
                full_name = self.github.create_repo(token, create["name"], bool(create.get("private", True)))["full_name"]
            elif repo:
                if not REPO_FULL_NAME.fullmatch(repo):
                    raise Refused(400, "Name the repository as owner/name.")
                found = self.github.repo(token, repo)
                if not found.get("permissions", {}).get("pull"):
                    raise Refused(403, "This GitHub account cannot read that repository.")
                full_name = found["full_name"]
            else:
                raise Refused(400, "Name a repository, or one to create.")
        except GitHubError as error:
            raise self.github_refusal(error) from error
        changed = self.store.update("projects", {"github_repo": full_name, "updated_at": now()}, id=f"eq.{project['id']}")
        return self.public_project(changed[0])

    def unlink_repo(self, user: User, project_id: str) -> dict[str, Any]:
        """Unlink the user's project from its repository, which stays as it is on GitHub."""
        project = self.owned_project(user, project_id)
        changed = self.store.update("projects", {"github_repo": None, "updated_at": now()}, id=f"eq.{project['id']}")
        return self.public_project(changed[0])

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
            if self.catalog.apps.get(session["app"], {}).get("status") == "byol":
                sandbox_id = self.launcher.start(session, tier, region, own_copy=self.own_copy(session))
            else:
                sandbox_id = self.launcher.start(session, tier, region)
        except Exception as error:
            self.store.rpc("lathe_end_session", p_session=session_id, p_reason=f"start failed: {error}"[:300], p_failed=True)
            return
        started = self.store.rpc("lathe_session_started", p_session=session_id, p_sandbox_id=sandbox_id)
        if not started or not started.get("id"):
            # Stopped while it was starting: nothing may be left running for it
            self.launcher.stop(sandbox_id)

    def run_stop(self, session_id: str, reason: str) -> None:
        """Stop a running session's Sandbox and close its row."""
        rows = self.store.rows("sessions", id=f"eq.{session_id}", status="eq.running")
        if not rows:
            return
        self.launcher.stop(rows[0]["sandbox_id"])
        self.store.rpc("lathe_end_session", p_session=session_id, p_reason=reason, p_failed=False)

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
                left = self.store.rpc("lathe_charge_session", p_session=session["id"], p_final=False)
                if left == 0:
                    self.jobs.stop(session["id"], "out of credits")
                    did["out_of_credits"] += 1
                continue
            reason = {0: "idle", 143: "stopped"}.get(status, f"crashed (exit {status})")
            self.store.rpc("lathe_end_session", p_session=session["id"], p_reason=reason, p_failed=status not in (0, 143))
            did["ended" if status in (0, 143) else "failed"] += 1
        now = datetime.now(timezone.utc)
        for session in self.store.rows("sessions", status="eq.starting"):
            waited = (now - datetime.fromisoformat(session["claimed_at"])).total_seconds()
            if waited > START_LIMIT_SECONDS:
                self.store.rpc("lathe_end_session", p_session=session["id"], p_reason="start timed out", p_failed=True)
                did["failed"] += 1
        for session in self.store.rpc("lathe_claim_queued", p_capacity=self.config.capacity) or []:
            self.jobs.start(session["id"])
            did["started"] += 1
        return did
