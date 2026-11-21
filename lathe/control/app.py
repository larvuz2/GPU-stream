# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Lathe's control plane as a Modal app: `modal deploy lathe/control/app.py`.

Four functions, one image. `api` serves the web API and the MCP endpoint
(`api.py`). `start_job` and `stop_job` do the seconds-long work a request hands
off, each in a container of its own so a request never holds one. `reconcile`
runs once a minute and is the service's upkeep (`Sessions.reconcile`). `check`
is for an operator: it starts and stops one session the way the service does.

Everything the deployment is configured with is the environment of the Modal
Secret `lathe`, read once per container (`config`). The Supabase secret key
lives only there; Modal's own credentials are the function's identity, so
this app starts Sandboxes without holding a Modal token.

The Sandboxes are the launcher's (`addons/modal/sandbox.py`), which this image
carries beside the code that calls it, with the scripts the session image is
built from: the image a session runs is defined in one place, and the Sandbox
this service starts is the one `selkies-modal up` starts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import modal

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
LAUNCHER = "/root/launcher"

app = modal.App("lathe-control")
secret = modal.Secret.from_name("lathe")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(str(HERE / "requirements.txt"))
    .add_local_dir(REPO / "addons" / "modal", LAUNCHER, ignore=["**/__pycache__", "*.md", "requirements.txt"])
    .add_local_file(HERE.parent / "catalog.json", "/root/catalog.json")
    .add_local_file(HERE / "service.py", "/root/service.py")
    .add_local_file(HERE / "api.py", "/root/api.py")
)


def config() -> Any:
    """The deployment's configuration, from the Secret's environment."""
    from service import Config

    return Config(
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_key=os.environ.get("SUPABASE_SECRET_KEY", ""),
        stripe_key=os.environ.get("STRIPE_SECRET_KEY", ""),
        stripe_webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
        site_url=os.environ.get("LATHE_SITE_URL", "").rstrip("/"),
        capacity=int(os.environ.get("LATHE_CAPACITY", "10")),
        tiers=frozenset(filter(None, os.environ.get("LATHE_TIERS", "cpu").split(","))),
        pin_regions=os.environ.get("LATHE_PIN_REGIONS", "true").lower() == "true",
    )


class ModalLauncher:
    """The service's `Launcher` over the real thing: Modal Sandboxes through `addons/modal/sandbox.py`."""

    def __init__(self) -> None:
        sys.path.insert(0, LAUNCHER)
        import sandbox as launcher
        import service

        self.launcher = launcher
        self.service = service
        self.app = modal.App.lookup(launcher.APP_NAME, create_if_missing=True)
        self.image = launcher.session_image()

    def start(self, session: dict[str, Any], tier: dict[str, Any], region: str | None) -> str:
        """Start the session's Sandbox in its user's own directory of the workspace and wait until it streams.

        A Sandbox that does not come up is ended before the failure is
        reported, so a start that fails leaves nothing running.
        """
        sandbox = self.launcher.start_session(
            self.app,
            f"lathe-{session['id']}",
            gpu=tier["gpu"],
            # Reserved, and the most it may use: Modal bills the higher of the reservation and the use
            cpu=(tier["cpu"], tier["cpu"] * 2),
            memory=tier["memory_gb"] * 1024,
            idle_seconds=self.service.IDLE_SECONDS,
            lifetime_seconds=self.service.LIFETIME_SECONDS,
            region=region,
            workspace=f"/users/{session['user_id']}",
            tags={"lathe_session": session["id"], "lathe_user": session["user_id"]},
            image=self.image,
        )
        try:
            sandbox.wait_until_ready(timeout=self.service.READY_SECONDS)
        except Exception:
            sandbox.terminate()
            raise
        return sandbox.object_id

    def state(self, sandbox_id: str) -> int | None:
        return modal.Sandbox.from_id(sandbox_id).poll()

    def link(self, sandbox_id: str) -> str:
        return self.launcher.session_link(modal.Sandbox.from_id(sandbox_id))

    def stop(self, sandbox_id: str) -> None:
        self.launcher.stop_session(modal.Sandbox.from_id(sandbox_id))

    def blender_python(self, sandbox_id: str, code: str) -> tuple[int, str]:
        return self.launcher.blender_python(modal.Sandbox.from_id(sandbox_id), code)

    def screenshot(self, sandbox_id: str) -> bytes:
        return self.launcher.screenshot(modal.Sandbox.from_id(sandbox_id))


class ModalJobs:
    """The service's `Jobs`: each one a call of a function of this app, which outlives the request that made it."""

    def start(self, session_id: str) -> None:
        start_job.spawn(session_id)

    def stop(self, session_id: str, reason: str) -> None:
        stop_job.spawn(session_id, reason)


def sessions() -> Any:
    """The service, or nothing while no Supabase project is configured."""
    from service import Catalog, Sessions, Store

    settings = config()
    if not settings.supabase:
        return None
    store = Store(settings.supabase_url, settings.supabase_key)
    return Sessions(settings, Catalog(Path("/root/catalog.json")), store, ModalLauncher(), ModalJobs())


@app.function(image=image, secrets=[secret], timeout=600)
def start_job(session_id: str) -> None:
    """Start one session's Sandbox (`Sessions.run_start`)."""
    sessions().run_start(session_id)


@app.function(image=image, secrets=[secret], timeout=600)
def stop_job(session_id: str, reason: str) -> None:
    """Stop one session's Sandbox (`Sessions.run_stop`)."""
    sessions().run_stop(session_id, reason)


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
    `modal run lathe/control/app.py::check`, with `--gpu T4` to try a GPU. It
    needs no Supabase project, and its workspace is a directory of its own.
    """
    import time

    launcher = ModalLauncher()
    session = {"id": f"check-{int(time.time())}", "user_id": "check"}
    tier = {"gpu": gpu or None, "cpu": 2, "memory_gb": 4}
    started = time.monotonic()
    sandbox_id = launcher.start(session, tier, None)
    report: dict[str, Any] = {"sandbox": sandbox_id, "ready_seconds": round(time.monotonic() - started, 1)}
    try:
        report["link_host"] = launcher.link(sandbox_id).split("/")[2]
        report["blender"] = launcher.blender_python(
            sandbox_id, "import bpy, os\nprint(bpy.app.version_string, os.environ['SELKIES_MODAL_WORKSPACE'])"
        )
        report["workspace_files"] = launcher.launcher.blender_python(
            modal.Sandbox.from_id(sandbox_id),
            "import os\nprint(sorted(os.listdir(os.environ['SELKIES_MODAL_WORKSPACE'])))",
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
    """`modal run lathe/control/app.py`: run `check` and print its report."""
    print(check.remote(gpu))
