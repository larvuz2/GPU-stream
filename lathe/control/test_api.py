# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The API and the MCP endpoint over the service, with Supabase and Modal stood in for.

`FakeStore` answers the calls the service makes to Supabase with the least that
keeps them true to the database's functions, whose own behavior is what the
migration's checks hold; `FakeLauncher` records what would have reached Modal.
What is tested here is this side: who a credential names, what each route and
tool returns and refuses, and that one user's sessions are invisible to
another. Run with `pytest lathe/control`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import create_app
from service import Catalog, Config, Refused, Sessions, User, hash_key

CATALOG = Catalog(Path(__file__).resolve().parent.parent / "catalog.json")
ALICE = User(id="00000000-0000-0000-0000-00000000000a", email="alice@example.test")
BOB = User(id="00000000-0000-0000-0000-00000000000b", email="bob@example.test")
TOKENS = {"alice-token": ALICE, "bob-token": BOB}


class FakeStore:
    """Supabase, as far as the service reaches into it."""

    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.keys: dict[str, dict[str, Any]] = {}
        self.ledger: list[tuple[str, int, str | None]] = []

    def user_of_token(self, token: str) -> User | None:
        return TOKENS.get(token)

    def rpc(self, function: str, **a: Any) -> Any:
        return getattr(self, function)(**a)

    def lathe_ensure_profile(self, p_user: str, p_email: str, p_signup_credits: int) -> dict[str, Any]:
        return self.profiles.setdefault(
            p_user, {"id": p_user, "email": p_email, "credits": p_signup_credits, "max_sessions": 1}
        )

    def lathe_request_session(self, p_user: str, p_app: str, p_tier: str, p_region: str, p_credits_per_minute: int, p_capacity: int) -> dict[str, Any]:
        profile = self.profiles[p_user]
        if profile["credits"] < max(p_credits_per_minute, 1):
            raise Refused(402, "out of credits")
        if sum(s["user_id"] == p_user and s["status"] in ("queued", "starting", "running") for s in self.sessions.values()) >= profile["max_sessions"]:
            raise Refused(409, "session limit")
        running = sum(s["status"] in ("starting", "running") for s in self.sessions.values())
        session = {
            "id": str(uuid.uuid4()), "user_id": p_user, "app": p_app, "tier": p_tier, "region": p_region,
            "status": "starting" if running < p_capacity else "queued", "sandbox_id": None,
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

    def rows(self, table: str, **query: str) -> list[dict[str, Any]]:
        rows = list((self.sessions if table == "sessions" else self.keys).values())
        for column, condition in query.items():
            if column in ("order", "limit"):
                continue
            operator, _, value = condition.partition(".")
            if operator == "eq":
                rows = [r for r in rows if str(r[column]) == value]
            elif operator == "in":
                rows = [r for r in rows if r[column] in value.strip("()").split(",")]
            elif operator == "is":
                rows = [r for r in rows if r[column] is None]
        return [dict(r) for r in rows]

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        row = {**row, "id": str(uuid.uuid4()), "created_at": "2026-11-21T00:00:00+00:00", "last_used_at": None, "revoked_at": None}
        self.keys[row["key_hash"]] = row
        return dict(row)

    def update(self, table: str, changes: dict[str, Any], **query: str) -> list[dict[str, Any]]:
        changed = [r for r in self.keys.values() if all(str(r[c]) == v.partition(".")[2] for c, v in query.items())]
        for row in changed:
            row.update(changes)
        return changed


class FakeLauncher:
    """Modal, as far as the service drives it: every Sandbox it was asked for, and what was done to each."""

    def __init__(self) -> None:
        self.started: list[tuple[dict[str, Any], dict[str, Any], str | None]] = []
        self.stopped: list[str] = []
        self.exits: dict[str, int] = {}
        self.fail_start = False

    def start(self, session: dict[str, Any], tier: dict[str, Any], region: str | None) -> str:
        if self.fail_start:
            raise RuntimeError("Please add a payment method to use T4 GPU sandboxes.")
        self.started.append((session, tier, region))
        return f"sb-{len(self.started)}"

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


class InlineJobs:
    """Jobs run at once, in the request that asked for them."""

    sessions: Sessions

    def start(self, session_id: str) -> None:
        self.sessions.run_start(session_id)

    def stop(self, session_id: str, reason: str) -> None:
        self.sessions.run_stop(session_id, reason)


def config(**changes: Any) -> Config:
    values: dict[str, Any] = {
        "supabase_url": "https://project.example.test", "supabase_key": "service-key", "stripe_key": "",
        "stripe_webhook_secret": "", "site_url": "https://site.example.test", "capacity": 10,
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


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_is_open_and_says_what_is_configured(world):
    client = world[0]
    assert client.get("/v1/health").json() == {"ok": True, "supabase": True, "billing": False, "tiers": ["cpu", "t4"]}


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
    assert post({"app": "unreal", "tier": "cpu"}) == 400, "an app that is coming soon"
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
