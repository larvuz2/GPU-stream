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
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import httpx

IDLE_SECONDS = 600
LIFETIME_SECONDS = 8 * 3600
READY_SECONDS = 120
# A session still `starting` after this long has lost its job
START_LIMIT_SECONDS = 300
OPEN = ("queued", "starting", "running")
SESSION_FIELDS = (
    "id",
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

    @property
    def supabase(self) -> bool:
        """Whether a Supabase project is configured at all."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def billing(self) -> bool:
        """Whether payments can be taken."""
        return bool(self.stripe_key and self.stripe_webhook_secret)


class Catalog:
    """The apps, tiers, regions, and credit packs on offer, read from `lathe/catalog.json`.

    The site reads the same file, so what a page shows and what the service
    accepts and charges are one definition.
    """

    def __init__(self, path: Path) -> None:
        self.data: dict[str, Any] = json.loads(path.read_text())
        self.apps = {app["id"]: app for app in self.data["apps"]}
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


class Launcher(Protocol):
    """The part of `addons/modal/sandbox.py` this service drives, which a test stands in for."""

    def start(self, session: dict[str, Any], tier: dict[str, Any], region: str | None) -> str:
        """Start the session's Sandbox, wait until it streams, and return the Sandbox's ID."""

    def state(self, sandbox_id: str) -> int | None:
        """The Sandbox's exit status, or nothing while it runs."""

    def link(self, sandbox_id: str) -> str:
        """A fresh link that opens the session."""

    def stop(self, sandbox_id: str) -> None:
        """End the session, keeping the scene Blender has open."""

    def blender_python(self, sandbox_id: str, code: str) -> tuple[int, str]:
        """Run Python in the session's Blender and return its status and output."""

    def screenshot(self, sandbox_id: str) -> bytes:
        """The session's screen as a PNG."""


class Jobs(Protocol):
    """Work that outlasts a request: starting and stopping a Sandbox."""

    def start(self, session_id: str) -> None:
        """Have `Sessions.run_start` run for this session."""

    def stop(self, session_id: str, reason: str) -> None:
        """Have `Sessions.run_stop` run for this session."""


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


class Sessions:
    """Everything a user can do, and the upkeep that runs without them."""

    def __init__(self, config: Config, catalog: Catalog, store: Store, launcher: Launcher, jobs: Jobs) -> None:
        self.config = config
        self.catalog = catalog
        self.store = store
        self.launcher = launcher
        self.jobs = jobs
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
        session = {field: row[field] for field in SESSION_FIELDS}
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

    def start(self, user: User, app: str, tier: str, region: str) -> dict[str, Any]:
        """Record a new session for the user and hand its start to a job, or leave it queued.

        Raises:
            Refused: 400 for an app, tier, or region that is not on offer, 402 without the credits
                for a first minute, 409 at the user's session limit or for a tier that is switched off.
        """
        if self.catalog.apps.get(app, {}).get("status") != "available":
            raise Refused(400, "That app is not available yet.")
        if tier not in self.catalog.tiers or region not in self.catalog.regions:
            raise Refused(400, "Unknown tier or region.")
        if tier not in self.config.tiers:
            raise Refused(409, "That tier is not switched on yet. Pick another one.")
        self.me(user)
        row = self.store.rpc(
            "lathe_request_session",
            p_user=user.id,
            p_app=app,
            p_tier=tier,
            p_region=region,
            p_credits_per_minute=self.catalog.tiers[tier]["credits_per_minute"],
            p_capacity=self.config.capacity,
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
        return {field: row[field] for field in ("id", "name", "prefix", "created_at", "last_used_at")}

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
