# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The service's `Launcher` over the real thing: Modal Sandboxes through `addons/modal/sandbox.py`.

The Sandbox a session runs in is the launcher's, so a session the service
starts is the one `selkies-modal up` starts. What the service adds is where:
every session mounts its user's own directory of the workspace Volume
(`/users/<user id>`), and an engine of a project opens in that project's folder
of it (`SELKIES_MODAL_PROJECT=projects/<project id>`), so the engines of one
project read and write the same files.

Each app's session image is defined once per container and reused, so no start
waits on a definition another start already made; Modal itself caches what
the definitions build. Nuke's is the exception: it is the image `nuke_image`
makes from the user's own install in their workspace, defined at each start,
since the install a user just made has to be in their next session.

Modal is imported where it is used, so the service's tests can stand in for
the launcher module and run without Modal installed. FilmCraft's command
channel (`filmcraft_call`) is looked up on the launcher module when it is
called, so a launcher without it still starts every other app.
"""

from __future__ import annotations

import sys
from typing import Any

from service import IDLE_SECONDS, LIFETIME_SECONDS, READY_SECONDS

LAUNCHER_DIR = "/root/launcher"
FILMCRAFT_SECONDS = 60


class ModalLauncher:
    """Starts, links, stops, and acts in session Sandboxes.

    `launcher` is the `sandbox` module of `addons/modal` and `app` the Modal
    app its Sandboxes belong to; both are looked up where not given.
    """

    def __init__(self, launcher: Any = None, app: Any = None) -> None:
        if launcher is None:
            sys.path.insert(0, LAUNCHER_DIR)
            import sandbox as launcher
        if app is None:
            import modal

            app = modal.App.lookup(launcher.APP_NAME, create_if_missing=True)
        self.launcher = launcher
        self.app = app
        self.images: dict[str, Any] = {}

    @staticmethod
    def sandbox(sandbox_id: str) -> Any:
        import modal

        return modal.Sandbox.from_id(sandbox_id)

    def image(self, session: dict[str, Any]) -> Any:
        """The session image of the session's app: this container's for most apps, the user's own for Nuke."""
        app = session.get("app") or "blender"
        if app == "nuke":
            return self.launcher.nuke_image(f"users/{session['user_id']}")
        if app not in self.images:
            self.images[app] = self.launcher.session_image(app)
        return self.images[app]

    def start(self, session: dict[str, Any], tier: dict[str, Any], region: str | None) -> str:
        """Start the session's Sandbox in its user's own directory of the workspace and wait until it streams.

        A Sandbox that does not come up is ended before the failure is
        reported, so a start that fails leaves nothing running.
        """
        project = session.get("project_id")
        tags = {"lathe_session": session["id"], "lathe_user": session["user_id"]}
        if project:
            tags["lathe_project"] = project
        sandbox = self.launcher.start_session(
            self.app,
            f"lathe-{session['id']}",
            gpu=tier["gpu"],
            # Reserved, and the most it may use: Modal bills the higher of the reservation and the use
            cpu=(tier["cpu"], tier["cpu"] * 2),
            memory=tier["memory_gb"] * 1024,
            idle_seconds=IDLE_SECONDS,
            lifetime_seconds=LIFETIME_SECONDS,
            env={"SELKIES_MODAL_PROJECT": f"projects/{project}"} if project else None,
            region=region,
            workspace=f"/users/{session['user_id']}",
            tags=tags,
            image=self.image(session),
            application=session.get("app") or "blender",
        )
        try:
            sandbox.wait_until_ready(timeout=READY_SECONDS)
        except Exception:
            sandbox.terminate()
            raise
        return sandbox.object_id

    def state(self, sandbox_id: str) -> int | None:
        return self.sandbox(sandbox_id).poll()

    def link(self, sandbox_id: str) -> str:
        return self.launcher.session_link(self.sandbox(sandbox_id))

    def stop(self, sandbox_id: str) -> None:
        self.launcher.stop_session(self.sandbox(sandbox_id))

    def blender_python(self, sandbox_id: str, code: str) -> tuple[int, str]:
        return self.launcher.blender_python(self.sandbox(sandbox_id), code)

    def screenshot(self, sandbox_id: str) -> bytes:
        return self.launcher.screenshot(self.sandbox(sandbox_id))

    def exec(self, sandbox_id: str, command: str, timeout: int) -> tuple[int, str]:
        """Run a bash command in the session's environment (`selkies-modal-run`), which counts as use of it."""
        process = self.sandbox(sandbox_id).exec(
            "/usr/local/bin/selkies-modal-run", "bash", "-c", command, timeout=timeout
        )
        output = process.stdout.read()
        status = process.wait()
        return status, output + process.stderr.read()

    def filmcraft(self, sandbox_id: str, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Call FilmCraft's command channel in the session (`filmcraft_call`).

        Raises:
            RuntimeError: FilmCraft refused or did not answer, or this launcher has no command channel.
        """
        call = getattr(self.launcher, "filmcraft_call", None)
        if call is None:
            raise RuntimeError("This deployment's launcher has no FilmCraft command channel yet.")
        return call(self.sandbox(sandbox_id), method, params, timeout=FILMCRAFT_SECONDS)
