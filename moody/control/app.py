# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Moody's control plane as a Modal app: `modal deploy moody/control/app.py`.

Five functions, one image. `api` serves the web API and the MCP endpoint
(`api.py`). `start_job` and `stop_job` do the seconds-long work a request hands
off, each in a container of its own so a request never holds one, and
`agent_turn` runs one turn of a project's agent (`agent.py`), which can take
minutes. `reconcile` runs once a minute and is the service's upkeep
(`Sessions.reconcile`). `check` is for an operator: it starts and stops one
session the way the service does.

Everything the deployment is configured with is the environment of the Modal
Secret `moody`, read once per container (`config`). The Supabase secret key,
the Anthropic and fal keys, the GitHub App's and the Epic OAuth App's client
secrets, and the secret that seals GitHub's tokens live only there; Modal's own credentials are the function's identity,
so this app starts Sandboxes without holding a Modal token.

The Sandboxes are the launcher's (`addons/modal/sandbox.py`), which this image
carries beside the code that calls it, with the scripts the session image is
built from: the image a session runs is defined in one place, and the Sandbox
this service starts is the one `selkies-modal up` starts (`launcher.py`). The
agent's skills (`moody/skills`) are carried too, read when a turn starts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import modal

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SKILLS = HERE.parent / "skills"
# A turn's worker may run this long; a turn is a few model calls, a few generations, and an engine's start
AGENT_TURN_SECONDS = 3600

app = modal.App("moody-control")
secret = modal.Secret.from_name("moody")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(str(HERE / "requirements.txt"))
    .add_local_dir(REPO / "addons" / "modal", "/root/launcher", ignore=["**/__pycache__", "*.md", "requirements.txt"])
    .add_local_file(HERE.parent / "catalog.json", "/root/catalog.json")
    .add_local_file(HERE.parent / "ui.json", "/root/ui.json")
)
for module in ("service.py", "api.py", "agent.py", "launcher.py", "generation.py", "github_client.py", "unreal.py", "genui.py"):
    image = image.add_local_file(HERE / module, f"/root/{module}")
if SKILLS.is_dir():
    image = image.add_local_dir(SKILLS, "/root/skills")


def config() -> Any:
    """The deployment's configuration, from the Secret's environment."""
    from service import Config

    return Config(
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_key=os.environ.get("SUPABASE_SECRET_KEY", ""),
        stripe_key=os.environ.get("STRIPE_SECRET_KEY", ""),
        stripe_webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
        site_url=os.environ.get("MOODY_SITE_URL", "").rstrip("/"),
        capacity=int(os.environ.get("MOODY_CAPACITY", "10")),
        tiers=frozenset(filter(None, os.environ.get("MOODY_TIERS", "cpu").split(","))),
        pin_regions=os.environ.get("MOODY_PIN_REGIONS", "true").lower() == "true",
        anthropic_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        agent_model=os.environ.get("MOODY_AGENT_MODEL", ""),
        fal_key=os.environ.get("FAL_KEY", ""),
        github_app_client_id=os.environ.get("GITHUB_APP_CLIENT_ID", ""),
        github_app_client_secret=os.environ.get("GITHUB_APP_CLIENT_SECRET", ""),
        github_app_slug=os.environ.get("GITHUB_APP_SLUG", ""),
        epic_client_id=os.environ.get("EPIC_GITHUB_CLIENT_ID", ""),
        epic_client_secret=os.environ.get("EPIC_GITHUB_CLIENT_SECRET", ""),
        secret_key=os.environ.get("MOODY_SECRET_KEY", ""),
        team_emails=frozenset(
            email.strip().lower() for email in os.environ.get("MOODY_TEAM_EMAILS", "").split(",") if email.strip()
        ),
        nuke_seats=int(os.environ.get("MOODY_NUKE_SEATS", "2")),
        api_url=os.environ.get("MOODY_API_URL", "").rstrip("/"),
        preview_limit_bytes=megabytes("MOODY_PREVIEW_MAX_MB", 50),
        preview_original_bytes=megabytes("MOODY_PREVIEW_ORIGINAL_MAX_MB", 8),
        preview_files=int(os.environ.get("MOODY_PREVIEW_MAX_FILES", "12")),
        transfer_limit_bytes=megabytes("MOODY_TRANSFER_MAX_MB", 4096),
    )


def megabytes(name: str, default: int) -> int:
    """A size the environment gives in megabytes, in bytes."""
    return int(os.environ.get(name, str(default))) * 1024 * 1024


class ModalJobs:
    """The service's `Jobs`: each one a call of a function of this app, which outlives the request that made it."""

    def start(self, session_id: str) -> None:
        start_job.spawn(session_id)

    def stop(self, session_id: str, reason: str) -> None:
        stop_job.spawn(session_id, reason)

    def turn(self, project_id: str, turn_id: str) -> None:
        agent_turn.spawn(project_id, turn_id)


def sessions() -> Any:
    """The service, or nothing while no Supabase project is configured."""
    from launcher import ModalLauncher
    from service import Catalog, Sessions, Store

    settings = config()
    if not settings.supabase:
        return None
    store = Store(settings.supabase_url, settings.supabase_key)
    return Sessions(
        settings, Catalog(Path("/root/catalog.json")), store, ModalLauncher(site_url=settings.site_url), ModalJobs()
    )


@app.function(image=image, secrets=[secret], timeout=600)
def start_job(session_id: str) -> None:
    """Start one session's Sandbox (`Sessions.run_start`)."""
    sessions().run_start(session_id)


@app.function(image=image, secrets=[secret], timeout=600)
def stop_job(session_id: str, reason: str) -> None:
    """Stop one session's Sandbox (`Sessions.run_stop`)."""
    sessions().run_stop(session_id, reason)


@app.function(image=image, secrets=[secret], timeout=AGENT_TURN_SECONDS)
def agent_turn(project_id: str, turn_id: str) -> None:
    """Run one turn of a project's agent (`agent.Agent.run`)."""
    from agent import Agent

    Agent.for_deployment(sessions()).run(project_id, turn_id)


@app.function(image=image, secrets=[secret], schedule=modal.Period(minutes=1), timeout=300)
def reconcile() -> None:
    """One round of upkeep, logged where it did anything."""
    service = sessions()
    if service is None:
        return
    did = service.reconcile()
    if any(did.values()):
        print(f"reconcile: {did}")


@app.function(image=image, secrets=[secret], timeout=900)
def check(gpu: str = "") -> dict[str, Any]:
    """Start, use, and stop one session the way the service does, and report what happened.

    For an operator, after a deploy or a change of tiers:
    `modal run moody/control/app.py::check`, with `--gpu T4` to try a GPU. It
    needs no Supabase project, and its workspace is a directory of its own.
    """
    import time

    from launcher import ModalLauncher

    launcher = ModalLauncher()
    session = {"id": f"check-{int(time.time())}", "user_id": "check", "app": "blender"}
    tier = {"gpu": gpu or None, "cpu": 2, "memory_gb": 4}
    started = time.monotonic()
    sandbox_id = launcher.start(session, tier, None)
    report: dict[str, Any] = {"sandbox": sandbox_id, "ready_seconds": round(time.monotonic() - started, 1)}
    try:
        report["link_host"] = launcher.link(sandbox_id).split("/")[2]
        report["blender"] = launcher.blender_python(
            sandbox_id, "import bpy, os\nprint(bpy.app.version_string, os.environ['SELKIES_MODAL_WORKSPACE'])"
        )
        report["workspace_files"] = launcher.blender_python(
            sandbox_id, "import os\nprint(sorted(os.listdir(os.environ['SELKIES_MODAL_WORKSPACE'])))"
        )[1].strip()
        report["screenshot_bytes"] = len(launcher.screenshot(sandbox_id))
    finally:
        launcher.stop(sandbox_id)
    report["exit_status"] = launcher.state(sandbox_id)
    return report


@app.function(image=image, secrets=[secret])
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def api() -> Any:
    """The web API and the MCP endpoint."""
    from api import create_app
    from service import Catalog

    return create_app(sessions(), config(), Catalog(Path("/root/catalog.json")))


@app.local_entrypoint()
def main(gpu: str = "") -> None:
    """`modal run moody/control/app.py`: run `check` and print its report."""
    print(check.remote(gpu))
