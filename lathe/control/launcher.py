# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The service's `Launcher` over the real thing: Modal Sandboxes through `addons/modal/sandbox.py`.

The Sandbox a session runs in is the launcher's, so a session the service
starts is the one `selkies-modal up` starts. What the service adds is where:
every session mounts its user's own directory of the workspace Volume
(`/users/<user id>`), and an engine of a project opens in that project's folder
of it (`SELKIES_MODAL_PROJECT=projects/<project id>`), so the engines of one
project read and write the same files. Every session also lets the site show
it in a frame (`SELKIES_FRAME_ANCESTORS`, the site's origin): the studio's Screen
panel is that frame, and Selkies otherwise allows only its own origin to frame
the client.

Each app's session image is defined once per container and reused, so no start
waits on a definition another start already made; Modal itself caches what
the definitions build. Nuke's is the exception: it is the image `nuke_image`
makes from the user's own install in their workspace, defined at each start,
since the install a user just made has to be in their next session. Unreal
Engine's is another where the user has linked Epic: the launcher's
`unreal_image` pulls Epic's image with the user's own registry credential,
defined at each start and never kept here, so one user's copy is never
another's image. Without the link, an Unreal engine is the shared
`session_image("unreal")`, the same desktop without the editor, which holds
nothing of Epic's and is kept like any other app's. The credential is a named Modal
Secret per user, `lathe-ghcr-<user id>` (`REGISTRY_USERNAME`, their GitHub
login; `REGISTRY_PASSWORD`, their token), rather than one made for each start:
the layer that pulls the engine is identified by the Secret it pulls with, and
a Secret of its own each start would pull about 40 GB again every time, where
the user's named one keeps that layer cached for them. The service writes it
before each start and when the user connects GitHub again, and deletes it when
they disconnect (`keep_registry_credential`, `forget_registry_credential`).

Modal is imported where it is used, so the service's tests can stand in for
the launcher module and run without Modal installed. FilmCraft's command
channel (`filmcraft_call`) and Unreal Engine's parts (`unreal_image`, the
Unreal view's link `unreal_view_link`, and the projects a machine found,
`unreal_projects`) are looked up on the launcher module when they are needed,
so a launcher without them still starts every other app.
"""

from __future__ import annotations

import sys
from typing import Any
from urllib.parse import urlsplit

from service import IDLE_SECONDS, LIFETIME_SECONDS, READY_SECONDS, OwnCopy

LAUNCHER_DIR = "/root/launcher"
FILMCRAFT_SECONDS = 60
REGISTRY_SECRET_PREFIX = "lathe-ghcr-"


def registry_secret(user_id: str) -> str:
    """The name of the Modal Secret that holds a user's own registry credential."""
    return f"{REGISTRY_SECRET_PREFIX}{user_id}"


def origin(url: str) -> str:
    """The origin of an http(s) URL (`https://example.com`), or an empty string for anything else."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


class ModalLauncher:
    """Starts, links, stops, and acts in session Sandboxes.

    `launcher` is the `sandbox` module of `addons/modal` and `app` the Modal
    app its Sandboxes belong to; both are looked up where not given.
    `site_url` is the site whose pages may frame a session, none where empty.
    """

    def __init__(self, launcher: Any = None, app: Any = None, site_url: str = "") -> None:
        if launcher is None:
            sys.path.insert(0, LAUNCHER_DIR)
            import sandbox as launcher
        if app is None:
            import modal

            app = modal.App.lookup(launcher.APP_NAME, create_if_missing=True)
        self.launcher = launcher
        self.app = app
        self.images: dict[str, Any] = {}
        self.frame_ancestor = origin(site_url)

    @staticmethod
    def sandbox(sandbox_id: str) -> Any:
        import modal

        return modal.Sandbox.from_id(sandbox_id)

    def image(self, session: dict[str, Any], own_copy: OwnCopy | None = None) -> Any:
        """The session image of the session's app: this container's for most apps, the user's own for Nuke and
        for Unreal on a linked account.

        Raises:
            RuntimeError: For the user's own copy of Unreal Engine, a launcher without `unreal_image`.
        """
        app = session.get("app") or "blender"
        if app == "nuke":
            return self.launcher.nuke_image(f"users/{session['user_id']}")
        if app == "unreal" and own_copy is not None:
            build = getattr(self.launcher, "unreal_image", None)
            if build is None:
                raise RuntimeError("This deployment's launcher cannot build Unreal Engine's image yet.")
            import modal

            return build(
                registry_secret=modal.Secret.from_name(registry_secret(session["user_id"])), version=own_copy.version
            )
        if app not in self.images:
            self.images[app] = self.launcher.session_image(app)
        return self.images[app]

    def start(
        self, session: dict[str, Any], tier: dict[str, Any], region: str | None, own_copy: OwnCopy | None = None
    ) -> str:
        """Start the session's Sandbox in its user's own directory of the workspace and wait until it streams.

        A Sandbox that does not come up is ended before the failure is
        reported, so a start that fails leaves nothing running. `own_copy` is
        the user's registry credential, for an app pulled with it.
        """
        project = session.get("project_id")
        env = {}
        if project:
            env["SELKIES_MODAL_PROJECT"] = f"projects/{project}"
        if self.frame_ancestor:
            env["SELKIES_FRAME_ANCESTORS"] = self.frame_ancestor
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
            env=env or None,
            region=region,
            workspace=f"/users/{session['user_id']}",
            tags=tags,
            image=self.image(session, own_copy),
            application=session.get("app") or "blender",
        )
        try:
            sandbox.wait_until_ready(timeout=READY_SECONDS)
        except Exception:
            sandbox.terminate()
            raise
        return sandbox.object_id

    def keep_registry_credential(self, user_id: str, username: str, token: str, create: bool = True) -> None:
        """Write the user's registry login and token into their own Secret, made first where `create` says to.

        Without `create`, a user with no Secret yet is left without one: connecting GitHub alone
        keeps no token in Modal.
        """
        import modal

        name = registry_secret(user_id)
        values = {"REGISTRY_USERNAME": username, "REGISTRY_PASSWORD": token}
        if create:
            # Made where missing; one that exists keeps its values until the update below
            modal.Secret.objects.create(name, values, allow_existing=True)
        else:
            try:
                modal.Secret.from_name(name).hydrate()
            except modal.exception.NotFoundError:
                return
        modal.Secret.from_name(name).update(values)

    def forget_registry_credential(self, user_id: str) -> None:
        """Delete the user's registry Secret, if they have one."""
        import modal

        modal.Secret.objects.delete(registry_secret(user_id), allow_missing=True)

    def state(self, sandbox_id: str) -> int | None:
        return self.sandbox(sandbox_id).poll()

    def link(self, sandbox_id: str) -> str:
        return self.launcher.session_link(self.sandbox(sandbox_id))

    def unreal_link(self, sandbox_id: str) -> str:
        """A link to the session's Unreal view (`unreal_view_link`).

        Raises:
            RuntimeError: This launcher has no Unreal view.
        """
        return self.unreal_part("unreal_view_link")(self.sandbox(sandbox_id))

    def unreal_projects(self, sandbox_id: str) -> list[dict[str, Any]]:
        """The `.uproject` files the session's workspace holds (`unreal_projects`).

        Raises:
            RuntimeError: This launcher cannot list them.
        """
        return self.unreal_part("unreal_projects")(self.sandbox(sandbox_id))

    def unreal_part(self, name: str) -> Any:
        """One of the launcher module's Unreal functions, which a launcher from before Unreal Engine lacks."""
        found = getattr(self.launcher, name, None)
        if found is None:
            raise RuntimeError(f"This deployment's launcher has no {name} for Unreal Engine yet.")
        return found

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
