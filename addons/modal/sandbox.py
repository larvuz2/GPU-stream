# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Run Blender in a Selkies session on a Modal Sandbox and hand back its link.

Modal runs the container on a GPU and carries the one port of the WebSocket
transport to the browser; everything in the session is the base container's
own. `up` builds or reuses the image (Blender layered over the base image this
tree publishes), starts a Sandbox whose main process is `session.sh`, waits
until Selkies listens, and prints a link carrying two credentials:

- Modal's connect token, in the query (`_modal_connect_token`), which Modal's
  proxy takes for the right to reach the Sandbox at all and answers with a
  cookie, so the page's later requests and its socket pass too.
- The Selkies session token, in the fragment (`#token=`), which no request line
  carries. The session is in secure mode, so nothing streams without it.

Neither is kept on this side: a later `url` asks Modal for a new connect token
and reads the session token back out of the Sandbox, which takes the Modal
credentials that started it.

What a session costs is bounded three ways. It ends itself once it has gone
unused (`session.sh`), the Sandbox's lifetime ends it regardless, and `up` for
a session that is running returns that one rather than starting a second. Work
saved under `WORKSPACE` is on a Modal Volume and outlives every Sandbox.

A stream that has to leave by another way than Modal's HTTPS proxy, which
carries HTTP and WebSockets only, takes a raw TCP port Modal exposes
(`start_session`'s `tcp_ports`, reached at `tcp_address`). WebRTC is such a
stream: its media is UDP, so it goes through a TURN relay in the Sandbox
(`with_turn`), which the browser reaches over that TCP port.

An application's own interface is reached from inside the Sandbox, the one
place it listens: Blender runs the Python it finds in a spool directory
(`blender_python`), and FilmCraft answers JSON requests on a control channel
bound to the Sandbox's loopback, for the session's own token only
(`filmcraft_call`). Neither is exposed beyond the Sandbox, so driving one takes
the Modal credentials that started it, as a link does. An Unreal session
describes the projects cloned into its workspace the same way
(`unreal_projects`), and has a second page beside its desktop on a port of its
own, the Unreal view (`unreal_view_link`). One started for a project linked to
a GitHub repository, given it and a token for it in a Secret of the start's own
(`start_session`'s `secrets`), clones it by itself and says how far it is
(`clone_status`).

This is Python because Modal's Python SDK is the interface the image
definition, the Sandbox, and the connect token are reached through.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path, PurePosixPath
from secrets import token_hex, token_urlsafe
from typing import Any

import modal
from modal.stream_type import StreamType

HERE = Path(__file__).resolve().parent

APP_NAME = "selkies"
VOLUME_NAME = "selkies-workspace"

# The base container built from this tree's `addons/base`, by digest: a tag
# moves with every push, and Modal caches an image by the reference it is given.
BASE_IMAGE = (
    "ghcr.io/selkies-project/selkies/base"
    "@sha256:5e9d022ae2e3864ab436deac365b3e8351d64bb6d8991aaf80fd5be27dac42eb"
)
BLENDER_VERSION = "5.2.4"
BLENDER_SHA256 = "2fd14c50987426897ba60237ee996edf2b4151f4b1a72a460ca20be58c1d2d86"
# FilmCraft's and PhotoCraft's Debian packages from their GitHub releases, and the hash each
# release's SHA256SUMS.txt lists for it
FILMCRAFT_VERSION = "0.20.1"
FILMCRAFT_SHA256 = "5667c7505c91d2ad9de3c4acb15cb02fc9f138fae74dce9c7c5f08bc29edb3a8"
PHOTOCRAFT_VERSION = "0.23.1"
PHOTOCRAFT_SHA256 = "baabdcdbe46df2f72ccf6ecc2e98be00fbc33dbd4c1cd9426362a89a4b95f673"
VECTORCRAFT_VERSION = "0.24.1"
VECTORCRAFT_SHA256 = "ae6733083d2819efe980d76d41d1908d40fe487bb9a5e7679292b53fd8dc49d7"
CRAFT_RELEASES = {
    "filmcraft": (FILMCRAFT_VERSION, FILMCRAFT_SHA256),
    "photocraft": (PHOTOCRAFT_VERSION, PHOTOCRAFT_SHA256),
    "vectorcraft": (VECTORCRAFT_VERSION, VECTORCRAFT_SHA256),
}
# The Unreal session's GitHub client: Desktop Plus, a fork of GitHub Desktop kept current with it
# that publishes Linux packages; its Debian package and the SHA-256 its GitHub release lists for it
DESKTOP_PLUS_VERSION = "3.6.12.0"
DESKTOP_PLUS_SHA256 = "91ac51e9f338ea4a6d8aa41ddbf547d7437eabc8bb8750955a9a10b8f8a23d87"
# Epic's development images, and where the editor is in them and in a session
UNREAL_ENGINE_IMAGE = "ghcr.io/epicgames/unreal-engine"
UNREAL_ENGINE_SOURCE = "/home/ue4/UnrealEngine"
UNREAL_ROOT = "/opt/unreal"

PORT = 8080
WORKSPACE = "/home/ubuntu/workspace"
TOKENS_FILE = "/tmp/selkies-modal/tokens.json"
ACTIVITY_FILE = "/tmp/selkies-modal/activity"
PID_FILE = "/tmp/selkies-modal/pid"
BLENDER_SPOOL = "/tmp/selkies-modal/blender"
SHARE = "/usr/local/share/selkies-modal"
# FilmCraft's and PhotoCraft's control channels, which each binds on the Sandbox's loopback only
FILMCRAFT_CONTROL_PORT = 9876
PHOTOCRAFT_CONTROL_PORT = 7878
# VectorCraft's control channel, on the Sandbox's loopback only as well, and the file that says the
# session has brought the project's documents back (vectorcraft/resume.sh)
VECTORCRAFT_CONTROL_PORT = 7979
VECTORCRAFT_READY_FILE = "/tmp/selkies-modal/vectorcraft-ready"
# The TCP port a session's TURN relay listens on (webrtc/turnserver.sh), exposed with `tcp_ports`
TURN_PORT = 3478
# The Unreal view, the Unreal session's second page beside the desktop (unreal/view/view.sh)
UNREAL_VIEW_PORT = 8090
# Where an Unreal session's clone of its repository says how far it is (unreal/clone.py)
UNREAL_CLONE_STATUS = "/tmp/selkies-modal/unreal-clone.json"

# What the session is, whoever starts it. Modal terminates TLS and its connect
# token guards the address, so Selkies serves plain HTTP with no login of its
# own beside the session token. WebRTC has no UDP path through Modal's proxy,
# so the transport is not offered and no TURN server is started for it.
SESSION_ENV = {
    "SELKIES_ENABLE_HTTPS": "false",
    "SELKIES_ENABLE_BASIC_AUTH": "false",
    "SELKIES_MODE": "websockets",
    "SELKIES_ENABLE_DUAL_MODE": "false",
    "SELKIES_WM": "true",
    "SELKIES_APP_RESTART": "true",
    "SELKIES_TOKENS_FILE": TOKENS_FILE,
    "SELKIES_MODAL_ACTIVITY_FILE": ACTIVITY_FILE,
    "SELKIES_MODAL_PID_FILE": PID_FILE,
    "SELKIES_MODAL_WORKSPACE": WORKSPACE,
    # Where the page's uploads land and its downloads come from: the directory that outlives the
    # Sandbox, where the server's own default is the desktop of a home that does not
    "SELKIES_FILE_MANAGER_PATH": WORKSPACE,
}

# What each application's session adds to it.
APP_ENV = {
    "blender": {
        "SELKIES_MODAL_APP": "blender",
        "SELKIES_MODAL_BLENDER_SPOOL": BLENDER_SPOOL,
        # Blender's preferences, add-ons, and extensions, and its auto-saves and last scene, on
        # the Volume with the work they belong to
        "BLENDER_USER_RESOURCES": f"{WORKSPACE}/.blender",
        "SELKIES_MODAL_BLENDER_RECOVERY": f"{WORKSPACE}/.blender/autosave",
    },
    "nuke": {
        "SELKIES_MODAL_APP": "nuke",
        # Nuke's settings, and the sign-in Foundry's login license keeps, kept in the workspace
        # (session.sh)
        "SELKIES_MODAL_PERSIST": ".nuke .local/share/Foundry FoundryLicensing",
        "NUKE_PATH": f"{SHARE}/nuke",
        # The desktop, whose taskbar keeps Nuke, Firefox, and the setup's windows in reach
        "SELKIES_DESKTOP": "true",
    },
    "filmcraft": {
        "SELKIES_MODAL_APP": "filmcraft",
        # The control channel; its token is the session's own (start_session)
        "FILMCRAFT_CONTROL_PORT": str(FILMCRAFT_CONTROL_PORT),
        # The window draws through Mesa's Vulkan in software (lavapipe) on every machine: a
        # Sandbox has no render node, so NVIDIA's Vulkan cannot present into the display and
        # OpenGL is Mesa's software rasterizer too. Vulkan is still what reaches the GPU where
        # there is one, for the export renderer, beside NVDEC and NVENC; OpenGL is left out.
        "WGPU_BACKEND": "vulkan",
    },
    "photocraft": {
        "SELKIES_MODAL_APP": "photocraft",
        # The control channel; its token is the session's own (start_session)
        "PHOTOCRAFT_CONTROL_PORT": str(PHOTOCRAFT_CONTROL_PORT),
    },
    "vectorcraft": {
        "SELKIES_MODAL_APP": "vectorcraft",
        # The control channel; the token a release with a sign-in takes is the session's own (start_session)
        "VECTORCRAFT_CONTROL_PORT": str(VECTORCRAFT_CONTROL_PORT),
        "SELKIES_MODAL_VECTORCRAFT_READY": VECTORCRAFT_READY_FILE,
    },
    "unreal": {
        "SELKIES_MODAL_APP": "unreal",
        # The desktop, whose taskbar keeps the GitHub client, Firefox, and Blender in reach
        "SELKIES_DESKTOP": "true",
        # Modal mounts NVIDIA's graphics libraries only with this, and the editor renders through
        # them (Vulkan, off screen)
        "NVIDIA_DRIVER_CAPABILITIES": "all",
        # The GitHub client's settings and sign-in (the keyring it keeps its token in) and Git's own
        # settings, kept in the workspace (session.sh; unreal/github.sh names the client's folder)
        "SELKIES_MODAL_PERSIST": ".desktop-plus .local/share/keyrings .config/git",
        "SELKIES_MODAL_UNREAL_VIEW_PORT": str(UNREAL_VIEW_PORT),
        "SELKIES_MODAL_UNREAL_CLONE_STATUS": UNREAL_CLONE_STATUS,
        # Blender beside the editor, as the blender app keeps it, so the editor's Send to Blender
        # reaches its spool
        "SELKIES_MODAL_BLENDER_SPOOL": BLENDER_SPOOL,
        "BLENDER_USER_RESOURCES": f"{WORKSPACE}/.blender",
        "SELKIES_MODAL_BLENDER_RECOVERY": f"{WORKSPACE}/.blender/autosave",
    },
}
APPS = tuple(APP_ENV)


def say(message: str) -> None:
    """Print progress to stderr, which leaves stdout to what a command returns."""
    print(f"selkies-modal: {message}", file=sys.stderr, flush=True)


def blender_install() -> tuple[str, str]:
    """The Dockerfile steps that put Blender and the idle counter's reader on the base image.

    One layer, which the Blender and Unreal sessions both start with, so the
    Unreal desktop takes the one the Blender session already built from Modal's
    cache.
    """
    series = BLENDER_VERSION.rsplit(".", 1)[0]
    archive = f"https://download.blender.org/release/Blender{series}/blender-{BLENDER_VERSION}-linux-x64.tar.xz"
    return (
        "RUN selkies-privileged-files run sh -c '"
        "apt-get update && apt-get install --no-install-recommends -y xprintidle && "
        "apt-get clean && rm -rf /var/lib/apt/lists/*'",
        f"RUN curl -fsSL -o /tmp/blender.tar.xz {archive} && "
        f"echo '{BLENDER_SHA256}  /tmp/blender.tar.xz' | sha256sum -c - && "
        "mkdir -p /opt/blender && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 && "
        "rm -f /tmp/blender.tar.xz && ln -s /opt/blender/blender /usr/local/bin/blender",
    )


def session_image(app: str = "blender") -> modal.Image:
    """The base container with an application, the idle counter's reader, and this integration's scripts.

    Modal builds every layer as root whatever user an image names, while the base
    keeps its package database the session user's, so that `sudo apt-get` works
    inside a session. Package layers therefore go through
    `selkies-privileged-files run`, which runs them as that user under fakeroot
    the way an in-session install does.

    Blender is the release archive from blender.org, checked against the hash
    blender.org publishes for it. Nuke is not in the image at all: Foundry hands
    it out behind a login and a license its user accepts, so the session
    installs it into the workspace once that user has (`nuke/setup.sh`); the
    image carries what that takes, Firefox among it (`nuke/install-deps.sh`).
    FilmCraft and PhotoCraft are the Debian packages of their GitHub releases,
    each checked against the hash its release publishes (`craft/install.sh`),
    with what finds the session's project folder (`craft/project.sh`); FilmCraft
    adds the client of its control channel (`filmcraft/control.sh`). Unreal's
    is the desktop its editor runs beside, without the editor
    (`unreal_desktop`); `unreal_image` is the same desktop with the editor.
    """
    if app == "unreal":
        return with_session(unreal_desktop(modal.Image.from_registry(BASE_IMAGE)), app)
    if app in CRAFT_RELEASES:
        version, sha256 = CRAFT_RELEASES[app]
        image = (
            modal.Image.from_registry(BASE_IMAGE)
            .add_local_file(HERE / "craft" / "install.sh", f"{SHARE}/craft/install.sh", copy=True)
            .dockerfile_commands(f"RUN selkies-privileged-files run sh {SHARE}/craft/install.sh {app} {version} {sha256}")
            .add_local_file(HERE / "craft" / "project.sh", "/usr/local/bin/selkies-modal-project", copy=True)
            .add_local_file(HERE / app / "autostart", "/etc/xdg/openbox/autostart", copy=True)
        )
        if app == "filmcraft":
            image = image.add_local_file(HERE / "filmcraft" / "control.sh", "/usr/local/bin/selkies-modal-filmcraft", copy=True)
        elif app == "vectorcraft":
            # The client of its control channel, and what brings a project's documents back at start
            image = image.add_local_file(
                HERE / "vectorcraft" / "control.sh", "/usr/local/bin/selkies-modal-vectorcraft", copy=True
            ).add_local_file(HERE / "vectorcraft" / "resume.sh", "/usr/local/bin/selkies-modal-vectorcraft-resume", copy=True)
    elif app == "nuke":
        image = (
            modal.Image.from_registry(BASE_IMAGE)
            # Not under /tmp: a file copied there leaves the directory root's alone
            .add_local_file(HERE / "nuke" / "install-deps.sh", f"{SHARE}/nuke/install-deps.sh", copy=True)
            .dockerfile_commands(f"RUN selkies-privileged-files run sh {SHARE}/nuke/install-deps.sh")
            .add_local_file(HERE / "nuke" / "firefox-policies.json", "/etc/firefox/policies/policies.json", copy=True)
            .add_local_file(HERE / "nuke" / "autostart", "/etc/xdg/openbox/autostart", copy=True)
            .add_local_file(HERE / "nuke" / "rc.xml", "/etc/xdg/openbox/rc.xml", copy=True)
            .add_local_file(HERE / "nuke" / "setup.sh", "/usr/local/bin/selkies-modal-nuke", copy=True)
            .add_local_file(HERE / "nuke" / "nuke.desktop", "/usr/local/share/applications/nuke.desktop", copy=True)
            .add_local_file(HERE / "nuke" / "nuke-run.sh", "/usr/local/bin/nuke-run", copy=True)
            .add_local_file(HERE / "nuke" / "menu.py", f"{SHARE}/nuke/menu.py", copy=True)
            .add_local_file(HERE / "nuke" / "init.py", f"{SHARE}/nuke/init.py", copy=True)
        )
    else:
        image = (
            modal.Image.from_registry(BASE_IMAGE)
            .dockerfile_commands(*blender_install())
            .add_local_file(HERE / "blender" / "autostart", "/etc/xdg/openbox/autostart", copy=True)
            .add_local_file(HERE / "blender" / "session.py", f"{SHARE}/blender-session.py", copy=True)
            .add_local_file(HERE / "blender" / "run-python.sh", "/usr/local/bin/selkies-modal-blender", copy=True)
        )
    return with_session(image, app)


def with_session(image: modal.Image, app: str) -> modal.Image:
    """`image` with what every session runs on: its main process, its command runners, and its environment.

    These are the last layers of every session image, so a change to them
    rebuilds only themselves, never the application under them.
    """
    return (
        image.add_local_file(HERE / "session.sh", "/usr/local/bin/selkies-modal-session", copy=True)
        .add_local_file(HERE / "run.sh", "/usr/local/bin/selkies-modal-run", copy=True)
        .add_local_file(HERE / "job.sh", "/usr/local/bin/selkies-modal-job", copy=True)
        .env({**SESSION_ENV, **APP_ENV[app]})
        .entrypoint([])
    )


def unreal_desktop(image: modal.Image) -> modal.Image:
    """The desktop an Unreal session works on, layered over `image`: the base, or the base with the editor.

    A studio's developer works the way they do on their own machine: they sign
    in to GitHub in a GitHub client, clone their team's repository, and open its
    `.uproject`. So the session is the Selkies desktop (`SELKIES_DESKTOP`), and
    it starts on that client:

    - **GitHub.** Desktop Plus, a fork of GitHub Desktop kept current with it
      (`unreal/install.sh` says why it rather than the older Linux fork), with
      Git LFS, which Unreal repositories keep their assets in. Its sign-in
      opens in Firefox, comes back to it through the URL scheme Firefox hands
      it, and is kept in GNOME's keyring in the workspace (`unreal/github.sh`),
      so it is done once. Its clone dialog offers the session's projects folder.
    - **The line of instructions.** At start, while that folder holds no
      Unreal project yet, one line over the client says to sign in and clone
      the game there (`unreal/autostart`).
    - **The team's repository, cloned at start.** A session given a GitHub
      repository and a token for it (`start_session`'s `secrets`) clones it
      into the project folder in the background, Git LFS's files included, or
      brings an earlier clone up to date where nothing local is in the way,
      and opens it in the client when it is there (`unreal/clone.py`,
      `clone_status`). The token reaches the session's Git through a credential
      helper (`unreal/git-credential.sh`) and the client's through a header in
      its environment (`unreal/github.sh`), and no file of the workspace keeps
      it. The client's bundled code is changed to open that clone without
      asking and without its welcome, and to ask to initialize Git LFS only
      where the clone does not have it already (`unreal/desktop-plus.py`).
    - **Finding the project.** `selkies-modal-unreal-projects` describes every
      `.uproject` in the workspace (`unreal_projects`).
    - **The Unreal view.** A second page on its own port (`unreal_view_link`),
      which an s6 service serves: a page saying Unreal is not open yet, until
      an editor streams there (`unreal/view/view.sh`).
    - **Opening a project.** `selkies-modal-unreal-open` starts the editor off
      screen with its own stream, where the image has it (`unreal_image`), and
      otherwise says it is not installed (`unreal/open.sh`).
    - **Blender**, as the blender app has it, with the Send to Unreal add-on
      enabled (`unreal/blender.sh`).

    The layers are ordered by how often they change: Blender and the packages,
    then the small files. `image` is the base for the desktop alone, and the
    base with the editor for `unreal_image`, so the editor, the largest layer by
    far, sits under everything else and nothing above it fetches it again.
    """
    unreal = HERE / "unreal"
    return (
        image.dockerfile_commands(*blender_install())
        .add_local_file(unreal / "install.sh", f"{SHARE}/unreal/install.sh", copy=True)
        .dockerfile_commands(
            f"RUN selkies-privileged-files run sh {SHARE}/unreal/install.sh {DESKTOP_PLUS_VERSION} {DESKTOP_PLUS_SHA256}",
            # Git LFS's filters for every repository, whichever Git clones it
            "RUN git lfs install --system --skip-repo",
        )
        .add_local_file(unreal / "desktop-plus.py", f"{SHARE}/unreal/desktop-plus.py", copy=True)
        .dockerfile_commands(f"RUN python3 -I {SHARE}/unreal/desktop-plus.py /usr/lib/desktop-plus/resources/app/renderer.js")
        .add_local_file(unreal / "firefox-policies.json", "/etc/firefox/policies/policies.json", copy=True)
        .add_local_file(unreal / "mimeapps.list", "/etc/xdg/mimeapps.list", copy=True)
        .add_local_file(unreal / "desktop-config", "/etc/xdg/selkies-desktop/config", copy=True)
        .add_local_file(unreal / "rc.xml", "/etc/xdg/openbox/rc.xml", copy=True)
        .add_local_file(unreal / "desktop-plus.desktop", "/usr/local/share/applications/desktop-plus.desktop", copy=True)
        .add_local_file(unreal / "blender.desktop", "/usr/local/share/applications/blender.desktop", copy=True)
        .add_local_file(unreal / "autostart", "/etc/xdg/openbox/autostart", copy=True)
        .add_local_file(unreal / "github.sh", "/usr/local/bin/selkies-modal-unreal-github", copy=True)
        .add_local_file(unreal / "blender.sh", "/usr/local/bin/selkies-modal-unreal-blender", copy=True)
        .add_local_file(unreal / "projects.py", "/usr/local/bin/selkies-modal-unreal-projects", copy=True)
        .add_local_file(unreal / "clone.py", "/usr/local/bin/selkies-modal-unreal-clone", copy=True)
        .add_local_file(unreal / "git-credential.sh", "/usr/local/bin/selkies-modal-unreal-git-credential", copy=True)
        .add_local_file(unreal / "open.sh", "/usr/local/bin/selkies-modal-unreal-open", copy=True)
        .add_local_file(unreal / "view" / "view.sh", "/usr/local/bin/selkies-modal-unreal-view", copy=True)
        .add_local_file(unreal / "view" / "serve.py", f"{SHARE}/unreal/view/serve.py", copy=True)
        .add_local_file(unreal / "view" / "index.html", f"{SHARE}/unreal/view/index.html", copy=True)
        .add_local_file(unreal / "view" / "run", "/etc/service/unreal-view/run", copy=True)
        .add_local_file(unreal / "view" / "finish", "/etc/service/unreal-view/finish", copy=True)
        # The bridge: Blender's add-on, and the editor's side, which the editor finds on UE_PYTHONPATH
        .add_local_file(unreal / "send_to_unreal.py", f"{SHARE}/unreal/send_to_unreal.py", copy=True)
        .add_local_file(unreal / "unreal_import.py", f"{SHARE}/unreal/unreal_import.py", copy=True)
        .add_local_file(unreal / "send_to_blender.py", f"{SHARE}/unreal/send_to_blender.py", copy=True)
        .add_local_file(unreal / "init_unreal.py", f"{SHARE}/unreal/init_unreal.py", copy=True)
        .add_local_file(unreal / "DefaultRemoteControl.ini", f"{SHARE}/unreal/DefaultRemoteControl.ini", copy=True)
        .add_local_file(HERE / "craft" / "project.sh", "/usr/local/bin/selkies-modal-project", copy=True)
        .add_local_file(HERE / "blender" / "session.py", f"{SHARE}/blender-session.py", copy=True)
        .add_local_file(HERE / "blender" / "run-python.sh", "/usr/local/bin/selkies-modal-blender", copy=True)
        .run_commands(
            # s6 runs as the session's user and writes its state into the services' folder and beside
            # each service, so both stay that user's, as the base image has them; adding the view's
            # files hands the folder to root
            "chown 1000:1000 /etc/service && chown -R 1000:1000 /etc/service/unreal-view",
            # Blender finds the add-on in a scripts folder of its own; a link, so the add-on still
            # finds the editor's half beside it
            f"mkdir -p {SHARE}/unreal/blender/addons && "
            f"ln -sfn ../../send_to_unreal.py {SHARE}/unreal/blender/addons/send_to_unreal.py",
        )
    )


def engine_layer(reference: str, source: str, registry_secret: modal.Secret) -> modal.Image:
    """The base image with one directory of a container image copied to `UNREAL_ROOT`, pulled with `registry_secret`.

    `unreal/fetch-engine.sh` streams `source` out of `reference` with crane,
    logged in with the Secret's `REGISTRY_USERNAME` and `REGISTRY_PASSWORD`,
    which no layer keeps. The layer is the user's own: Modal keys it by the
    Secret it was built with, so a user's named Secret keeps it cached for them.
    """
    return (
        modal.Image.from_registry(BASE_IMAGE)
        .add_local_file(HERE / "unreal" / "fetch-engine.sh", f"{SHARE}/unreal/fetch-engine.sh", copy=True)
        .dockerfile_commands(
            f"RUN sh {SHARE}/unreal/fetch-engine.sh {reference} {source} {UNREAL_ROOT}", secrets=[registry_secret]
        )
    )


def unreal_image(registry_secret: modal.Secret, version: str) -> modal.Image:
    """The Unreal session image of one user: the Unreal desktop with the editor of `version` in `UNREAL_ROOT`.

    The editor is Epic's development image of that version
    (`ghcr.io/epicgames/unreal-engine:dev-slim-<version>`), pulled with the
    user's own registry credential, `registry_secret`, a GitHub login and token
    of an account linked to Epic: Epic's license keeps each user on their own
    copy (`moody/UNREAL.md`). It is the image's first layer above the base,
    about 40 GB, so the desktop and the scripts over it change without fetching
    it again.

    Raises:
        ValueError: `version` is not a version number such as 5.8.4.
    """
    if not re.fullmatch(r"\d+\.\d+(\.\d+)?", version):
        raise ValueError(f"{version!r} is not an Unreal Engine version such as 5.8.4")
    engine = engine_layer(f"{UNREAL_ENGINE_IMAGE}:dev-slim-{version}", UNREAL_ENGINE_SOURCE, registry_secret)
    return with_session(unreal_desktop(engine), "unreal")


def with_turn(image: modal.Image) -> modal.Image:
    """`image` with the TURN relay that carries a WebRTC stream out of the Sandbox over TCP.

    The relay is coturn, which the base image carries for Selkies' own WebRTC
    mode; this adds its configuration and two commands. `selkies-modal-turnserver`
    starts it on `TURN_PORT`, relaying to the Sandbox's own addresses only, and
    `selkies-modal-turn-credentials HOST:PORT` prints the ICE server a browser
    uses, with credentials minted from the session's secret, where `HOST:PORT`
    is what `tcp_address` returns for that port. The session exposes the port
    when it is started with `tcp_ports=(TURN_PORT,)`. Nothing starts the relay
    on its own: the application whose stream needs it does (`webrtc/turnserver.sh`).

    The files are layered on the image rather than put in every session's, so
    an image without the relay, such as Nuke's with its copy of Nuke over it,
    keeps the layers Modal has cached.
    """
    return (
        image.add_local_file(HERE / "webrtc" / "turnserver.conf", f"{SHARE}/webrtc/turnserver.conf", copy=True)
        .add_local_file(HERE / "webrtc" / "turnserver.sh", "/usr/local/bin/selkies-modal-turnserver", copy=True)
        .add_local_file(HERE / "webrtc" / "turn-credentials.py", "/usr/local/bin/selkies-modal-turn-credentials", copy=True)
    )


def nuke_image(workspace: str | None) -> modal.Image:
    """The Nuke session image, with the Nuke the workspace installed copied into it where there is one.

    Nuke run from the workspace reads its files from the Volume, which a new
    machine fetches as Nuke asks for them: measured on a T4, Nuke took over seven
    minutes to open. Copied into the image, it is read from Modal's image cache
    instead. The copy is the workspace's own install, whose license its user
    accepted (`nuke/setup.sh`), into the account's own private image; it is
    rebuilt when the workspace has a newer Nuke, which names the step, and the
    session takes this copy where it has one (`/opt/nuke`).
    """
    image = session_image("nuke")
    if not workspace:
        return image
    volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
    try:
        entries = volume.listdir(f"/{workspace}/.apps/nuke")
    except modal.exception.NotFoundError:
        return image
    versions = sorted(
        (PurePosixPath(entry.path).name for entry in entries if PurePosixPath(entry.path).name.startswith("Nuke")),
        key=lambda name: [int(part) for part in re.findall(r"\d+", name)],
    )
    if not versions:
        return image
    return image.run_commands(
        f"mkdir -p /opt/nuke && cp -a /mnt/nuke/{versions[-1]} /opt/nuke/",
        volumes={"/mnt/nuke": volume.with_mount_options(sub_path=f"/{workspace}/.apps/nuke", read_only=True)},
    )


def find_session(name: str) -> modal.Sandbox | None:
    """The running session of that name, if there is one."""
    try:
        return modal.Sandbox.from_name(APP_NAME, name)
    except modal.exception.NotFoundError:
        return None


def session_link(sandbox: modal.Sandbox) -> str:
    """A link that opens the session, with a new connect token and the session's own token.

    Reading the token counts as use of the session: a link is asked for by
    someone about to open it.
    """
    process = sandbox.exec("sh", "-c", 'touch "$SELKIES_MODAL_ACTIVITY_FILE" && cat "$SELKIES_TOKENS_FILE"')
    table = process.stdout.read()
    if process.wait() != 0:
        raise SystemExit(f"selkies-modal: the session's token could not be read: {process.stderr.read().strip()}")
    token = next(iter(json.loads(table)))
    credentials = sandbox.create_connect_token(port=PORT)
    return f"{credentials.url}/?_modal_connect_token={credentials.token}#token={token}"


def start_session(
    app: modal.App,
    name: str,
    *,
    gpu: str | None,
    cpu: float | tuple[float, float],
    memory: int,
    idle_seconds: int,
    lifetime_seconds: int,
    env: dict[str, str] | None = None,
    region: str | None = None,
    workspace: str | None = None,
    tags: dict[str, str] | None = None,
    image: modal.Image | None = None,
    application: str = "blender",
    extra_secrets: tuple[str, ...] = (),
    secrets: list[modal.Secret] | None = None,
    tcp_ports: tuple[int, ...] = (),
) -> modal.Sandbox:
    """Start a session's Sandbox and return it at once, before Selkies listens.

    The session's tokens are made here and reach the Sandbox as a Modal Secret;
    nothing else holds them. Beside Selkies' two are the tokens of FilmCraft's
    and PhotoCraft's control channels, which each takes as 64 hex characters
    and every request on FilmCraft's carries (`filmcraft_call`), and the secret
    the TURN relay mints its credentials with (`with_turn`). VectorCraft's is
    made too, for the release that reads one (`vectorcraft/control.sh`). They
    are made for every session, since a caller holding a built image does not
    say which application it is, and a session of another application leaves
    them unread.

    `tcp_ports` are ports of the Sandbox Modal exposes as raw TCP, each at a
    public address of its own (`tcp_address`), beside the HTTPS port the link
    reaches through Modal's proxy. Modal admits any address to them, with no
    connect token, so what listens on one authenticates by itself, as the TURN
    relay does.

    `workspace` mounts one directory of the Volume in place of all of it, which
    is what keeps one user's files out of another's session where a service
    starts sessions for many. `cpu` takes a
    request, or a request and a limit, as Modal bills whichever of the request
    and the use is higher. `image` is the session image where the caller holds
    one already built, which a service does so that no request waits on a build;
    otherwise it is `application`'s. `extra_secrets` names Modal Secrets whose
    variables the session gets too, such as the Google Drive access rclone
    reads (`RCLONE_CONFIG_...`), and `secrets` are Secret objects to the same
    end, made for this start, such as the repository an Unreal session clones
    and the token it clones it with (`MOODY_GIT_REPO`, `MOODY_GIT_BRANCH`,
    `MOODY_GIT_TOKEN`, `MOODY_GIT_NAME`, `MOODY_GIT_EMAIL`; `unreal/clone.py`).

    Raises:
        modal.exception.AlreadyExistsError: A session of that name is running.
    """
    volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
    if workspace is not None:
        volume = volume.with_mount_options(sub_path=workspace)
    credentials = modal.Secret.from_dict(
        {
            "SELKIES_MASTER_TOKEN": token_urlsafe(32),
            "SELKIES_MODAL_SESSION_TOKEN": token_urlsafe(32),
            "FILMCRAFT_CONTROL_TOKEN": token_hex(32),
            "PHOTOCRAFT_CONTROL_TOKEN": token_hex(32),
            "VECTORCRAFT_CONTROL_TOKEN": token_hex(32),
            "SELKIES_MODAL_TURN_SECRET": token_urlsafe(32),
        }
    )
    return modal.Sandbox.create(
        "/usr/local/bin/selkies-modal-session",
        app=app,
        name=name,
        image=image or session_image(application),
        gpu=gpu,
        cpu=cpu,
        memory=memory,
        region=region,
        timeout=lifetime_seconds,
        env={**(env or {}), "SELKIES_MODAL_IDLE_TIMEOUT": str(idle_seconds)},
        secrets=[credentials, *(secrets or ()), *(modal.Secret.from_name(name) for name in extra_secrets)],
        volumes={WORKSPACE: volume},
        tags=tags or {},
        readiness_probe=modal.Probe.with_tcp(PORT),
        unencrypted_ports=list(tcp_ports),
    )


def tcp_address(sandbox: modal.Sandbox, port: int) -> tuple[str, int]:
    """The public host and port that reach one of a running session's `tcp_ports`.

    Modal picks both when the Sandbox starts, so they are asked for, not
    known ahead, and they last as long as the Sandbox. What arrives there is
    the bytes a client sent, with no TLS of Modal's around them.

    Raises:
        KeyError: The session was started with other `tcp_ports`, but not that one.
    """
    return sandbox.tunnels()[port].tcp_socket


def stop_session(sandbox: modal.Sandbox, wait_seconds: int = 45) -> None:
    """End a session the way its idle timeout does, then end its Sandbox whatever became of that.

    Terminating a Sandbox kills it where it stands, with Blender's open scene.
    The session's own way out has Blender keep that scene first (`session.sh`),
    so the session is signaled to take it and given `wait_seconds` to finish.
    """
    sandbox.exec("sh", "-c", 'kill -TERM "$(cat "$SELKIES_MODAL_PID_FILE")"').wait()
    deadline = time.monotonic() + wait_seconds
    while sandbox.poll() is None and time.monotonic() < deadline:
        time.sleep(1)
    sandbox.terminate(wait=True)


def blender_python(sandbox: modal.Sandbox, code: str, wait_seconds: int = 120) -> tuple[int, str]:
    """Run Python inside the session's Blender and return its status and what it printed.

    The status is `run-python.sh`'s: 0 when the code ran to its end, 1 with its
    traceback after what it printed when it raised, 124 when Blender did not
    answer within `wait_seconds`.
    """
    process = sandbox.exec("/usr/local/bin/selkies-modal-run", "selkies-modal-blender", str(wait_seconds))
    try:
        process.stdin.write(code)
        process.stdin.write_eof()
        process.stdin.drain()
    except modal.exception.Error:
        # The command ended before it read anything; its status and output say why
        pass
    output = process.stdout.read()
    status = process.wait()
    return status, output + process.stderr.read()


def filmcraft_requests(sandbox: modal.Sandbox, requests: str, wait_seconds: int) -> modal.container_process.ContainerProcess:
    """Hand JSON requests, one per line, to the session's FilmCraft and return the process printing its replies.

    The requests go from inside the Sandbox, the only place the control
    channel listens and its token is: `filmcraft/control.sh` adds the token to
    each and prints each reply on a line of its own, and runs as a command of
    the session, so it counts as use while it waits.
    """
    process = sandbox.exec("/usr/local/bin/selkies-modal-run", "selkies-modal-filmcraft", str(wait_seconds), bufsize=1)
    try:
        process.stdin.write(requests)
        process.stdin.write_eof()
        process.stdin.drain()
    except modal.exception.Error:
        # The command ended before it read anything; its status and output say why
        pass
    return process


def filmcraft_call(sandbox: modal.Sandbox, method: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    """Send one request on the session's FilmCraft control channel and return its result.

    `method` and `params` are those of FilmCraft's control protocol:
    `engine.execute` with `{"command", "params"}` runs any of its commands, and
    the `ui.*` methods read and drive its window. `timeout` is how many seconds
    to wait for FilmCraft to be ready, which it is a few seconds after its
    window opens, and then for the reply. FilmCraft gives up on a reply itself
    after 60 s, so a long export is started without `wait` and followed with
    the `jobs.list` command.

    The result is the reply's `result`, an object for most methods; a result
    that is not one, such as the list `jobs.list` returns, comes back as
    `{"result": ...}`.

    Raises:
        RuntimeError: FilmCraft refused the request, with its message, or did not answer within `timeout`.
    """
    request = json.dumps({"id": 1, "method": method, "params": params or {}})
    process = filmcraft_requests(sandbox, request + "\n", timeout)
    output = process.stdout.read()
    status = process.wait()
    if not output.strip():
        raise RuntimeError(f"FilmCraft did not answer: {process.stderr.read().strip() or f'status {status}'}")
    reply = json.loads(output.splitlines()[-1])
    if not reply.get("ok"):
        raise RuntimeError(reply.get("error") or output.strip())
    result = reply.get("result")
    return result if isinstance(result, dict) else {"result": result}


def vectorcraft_requests(sandbox: modal.Sandbox, requests: str, wait_seconds: int) -> modal.container_process.ContainerProcess:
    """Hand JSON requests, one per line, to the session's VectorCraft and return the process printing its replies.

    The requests go from inside the Sandbox, the only place the control
    channel listens and the session's token is: `vectorcraft/control.sh` signs
    in on a connection of its own for each, where the release takes a sign-in,
    and prints each reply on a line of its own. It runs as a command of the
    session, so it counts as use while it waits.
    """
    process = sandbox.exec("/usr/local/bin/selkies-modal-run", "selkies-modal-vectorcraft", str(wait_seconds), bufsize=1)
    try:
        process.stdin.write(requests)
        process.stdin.write_eof()
        process.stdin.drain()
    except modal.exception.Error:
        # The command ended before it read anything; its status and output say why
        pass
    return process


def vectorcraft_call(sandbox: modal.Sandbox, method: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    """Send one request on the session's VectorCraft control channel and return its result.

    `method` and `params` are those of VectorCraft's control protocol:
    `engine.execute` with `{"command", "params"}` runs any of its commands,
    `document.inspect` reads the document, `app.open` opens a file, and the
    `ui.*` methods read and drive its window. `timeout` is how many seconds to
    wait for VectorCraft to listen, which it does a few seconds after its
    window opens, and then for the reply. VectorCraft gives up on a reply
    itself after 60 s. The paths a request names are read against the
    session's project folder, the only folder the channel may read and write
    (`vectorcraft/autostart`).

    The result is the reply's `result`, an object for most methods; a result
    that is not one, such as the null a command that returns nothing answers
    with, comes back as `{"result": ...}`.

    Raises:
        RuntimeError: VectorCraft refused the request, with its message, or did not answer within `timeout`.
    """
    request = json.dumps({"id": 1, "method": method, "params": params or {}})
    process = vectorcraft_requests(sandbox, request + "\n", timeout)
    output = process.stdout.read()
    status = process.wait()
    if not output.strip():
        raise RuntimeError(f"VectorCraft did not answer: {process.stderr.read().strip() or f'status {status}'}")
    reply = json.loads(output.splitlines()[-1])
    if not reply.get("ok"):
        raise RuntimeError(reply.get("error") or output.strip())
    result = reply.get("result")
    return result if isinstance(result, dict) else {"result": result}


def unreal_projects(sandbox: modal.Sandbox) -> list[dict[str, Any]]:
    """The Unreal projects in an Unreal session's workspace, as `selkies-modal-unreal-projects` describes them.

    One entry per `.uproject`, with its path and name, the engine it was saved
    with (`engine_association` as the file has it; `engine_version` where that
    is a version such as 5.4), its C++ modules, its enabled plugins and whether
    each has its source in the project's `Plugins` folder, its repository with
    whether Git LFS is used and its files fetched, and its size
    (`unreal/projects.py` documents every field). Asking counts as use of the
    session, as any command run in it does.

    Raises:
        RuntimeError: The session has no such command (another application's) or it failed, with what it said.
    """
    process = sandbox.exec("/usr/local/bin/selkies-modal-run", "selkies-modal-unreal-projects")
    output = process.stdout.read()
    if process.wait() != 0:
        raise RuntimeError(f"the session's Unreal projects could not be read: {process.stderr.read().strip()}")
    return json.loads(output)


def clone_status(sandbox: modal.Sandbox) -> dict[str, Any]:
    """How far an Unreal session's clone of its GitHub repository is, as `selkies-modal-unreal-clone --status` says.

    `state` is `cloning`, `done` (the clone is in `path`, a folder of the
    workspace, whether or not it could be updated), or `failed`; `detail` is
    one line saying what happened or is happening, with Git LFS's progress
    while its files arrive, and why where the clone is not there or was left
    as it was. `path` is null until the clone has started. Asking does not
    count as use of the session, so a page polling it does not keep an
    abandoned session running; the clone itself counts while it runs
    (`unreal/clone.py`).

    Raises:
        RuntimeError: The session was given no repository, or has no such command (another application's).
    """
    process = sandbox.exec("/usr/local/bin/selkies-modal-unreal-clone", "--status")
    output = process.stdout.read()
    if process.wait() != 0:
        raise RuntimeError(f"the session's clone status could not be read: {process.stderr.read().strip()}")
    return json.loads(output)


def unreal_view_link(sandbox: modal.Sandbox) -> str:
    """A link that opens an Unreal session's Unreal view, the page beside its desktop, with a new connect token.

    The view is its own port (`UNREAL_VIEW_PORT`), so its link is a connect
    token of its own, which is the only credential it takes: what serves it, a
    page until the editor streams and the editor's player after
    (`unreal/view/view.sh`), has no login of its own. Asking for it counts as
    use of the session, as asking for the desktop's link does.
    """
    sandbox.exec("sh", "-c", 'touch "$SELKIES_MODAL_ACTIVITY_FILE"').wait()
    credentials = sandbox.create_connect_token(port=UNREAL_VIEW_PORT)
    return f"{credentials.url}/?_modal_connect_token={credentials.token}"


def screenshot(sandbox: modal.Sandbox) -> bytes:
    """The session's screen as a JPEG no wider than 1280 pixels, small enough to hand to a model.

    Selkies takes the picture (`/api/screenshot`, a PNG at the display's size),
    asked from inside the Sandbox with the master token that never leaves it.

    Raises:
        RuntimeError: Selkies or the conversion refused, with what it said.
    """
    process = sandbox.exec(
        "sh",
        "-c",
        'curl -fsS -m 20 -H "Authorization: Bearer $SELKIES_MASTER_TOKEN" '
        '"http://127.0.0.1:${SELKIES_PORT:-8080}/api/screenshot" | '
        # The comma is escaped for ffmpeg, which otherwise reads it as the end of the filter
        "ffmpeg -loglevel error -i pipe:0 -vf 'scale=min(1280\\,iw):-2' -q:v 4 -f mjpeg pipe:1 | base64 -w0",
    )
    picture = process.stdout.read()
    if process.wait() != 0 or not picture:
        raise RuntimeError(f"no screenshot: {process.stderr.read().strip()}")
    return base64.b64decode(picture)


def drive_sign_in(sandbox: modal.Sandbox, wait_seconds: int) -> str:
    """Have the person at a session sign in to Google in its Firefox, and return the token rclone was granted.

    rclone's own sign-in (`rclone authorize drive`) waits on the Sandbox's
    loopback for Google to send the person back, so the sign-in happens in the
    session's Firefox, the one browser that reaches that address: nothing is
    pasted, and no key file exists, which is what an organization that forbids
    service account keys leaves. The token carries a refresh token, with which
    rclone stays signed in until the person revokes its access in their Google
    account.

    The sign-in gets a Firefox window of its own, on a profile of its own, which
    is closed once the sign-in is over: a command `selkies-modal-run` runs has
    no way into a Firefox the session already has open, so asking that one for
    a tab starts a second Firefox that waits on its profile instead. It starts
    in a process session of its own (`setsid`), since the session counts a
    command `selkies-modal-run` runs as use for as long as it runs.

    Raises:
        SystemExit: rclone did not start a sign-in, or nobody finished it within `wait_seconds`.
    """
    process = sandbox.exec(
        "/usr/local/bin/selkies-modal-run",
        "timeout",
        str(wait_seconds),
        "rclone",
        "authorize",
        "drive",
        "--auth-no-open-browser",
        bufsize=1,
    )
    said = []
    for line in process.stderr:
        said.append(line)
        sign_in = re.search(r"http://127\.0\.0\.1:\d+/auth\?state=[\w-]+", line)
        if sign_in:
            break
    else:
        process.wait()
        raise SystemExit(f"selkies-modal: rclone started no sign-in: {''.join(said).strip()}")
    browser = "/tmp/selkies-modal-sign-in"
    sandbox.exec(
        "/usr/local/bin/selkies-modal-run",
        "sh",
        "-c",
        'rm -rf "$1" && mkdir -p "$1" && '
        'setsid -f sh -c \'echo $$ > "$1.pid"; exec firefox --no-remote --profile "$1" --new-window "$2"\' sh "$1" "$2" '
        "> /dev/null 2>&1",
        "sh",
        browser,
        sign_in.group(0),
    ).wait()
    say(f"Google's sign-in is open in a Firefox window on the session; waiting up to {wait_seconds // 60} min for it")
    output = process.stdout.read()
    status = process.wait()
    sandbox.exec("sh", "-c", 'kill "$(cat "$1.pid")"; rm -rf "$1" "$1.pid"', "sh", browser).wait()
    token = re.search(r"--->\n(.+)\n<---End paste", output)
    if status != 0 or not token:
        reason = "nobody signed in in time" if status == 124 else f"rclone ended with status {status}"
        raise SystemExit(f"selkies-modal: Google Drive is not connected: {reason}")
    return token.group(1)


def up(args: argparse.Namespace) -> int:
    """Start the session, or return the one already running under that name, and print its link."""
    sandbox = find_session(args.name)
    if sandbox is not None:
        say(f"{args.name} is already running as {sandbox.object_id}")
        print(session_link(sandbox))
        return 0

    app = modal.App.lookup(APP_NAME, create_if_missing=True)
    started = time.monotonic()
    workspace = f"/{args.workspace}" if args.workspace else None
    image = (nuke_image(args.workspace) if args.app == "nuke" else session_image(args.app)).build(app)
    say(f"image {image.object_id} ready after {time.monotonic() - started:.0f} s")

    started = time.monotonic()
    sandbox = start_session(
        app,
        args.name,
        gpu=None if args.gpu == "none" else args.gpu,
        cpu=args.cpu,
        memory=args.memory,
        idle_seconds=round(args.idle_minutes * 60),
        lifetime_seconds=round(args.lifetime_hours * 3600),
        env=dict(item.split("=", 1) for item in args.env),
        workspace=workspace,
        extra_secrets=tuple(args.secret),
        tags={"session": args.name, "gpu": args.gpu, "app": args.app},
        image=image,
        tcp_ports=tuple(args.tcp_port),
    )
    where = "without a GPU" if args.gpu == "none" else f"on {args.gpu}"
    say(f"{args.name} is {sandbox.object_id} {where}; waiting for Selkies")
    sandbox.wait_until_ready(timeout=args.ready_timeout)
    say(
        f"Selkies listens after {time.monotonic() - started:.0f} s; the session ends after "
        f"{args.idle_minutes:g} min unused, or {args.lifetime_hours:g} h in all"
    )
    for port in args.tcp_port:
        host, public = tcp_address(sandbox, port)
        say(f"TCP port {port} is reached at {host}:{public}")
    if args.app == "unreal":
        say(f"the Unreal view is {unreal_view_link(sandbox)}")
    print(session_link(sandbox))
    return 0


def url(args: argparse.Namespace) -> int:
    """Print a new link to a running session, or to an Unreal session's Unreal view."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    print(unreal_view_link(sandbox) if args.view == "unreal" else session_link(sandbox))
    return 0


def ls(_args: argparse.Namespace) -> int:
    """List the running sessions."""
    app = modal.App.lookup(APP_NAME, create_if_missing=True)
    for sandbox in modal.Sandbox.list(app_id=app.app_id):
        tags = sandbox.get_tags()
        print(f"{tags.get('session', '?')}\t{tags.get('gpu', '?')}\t{sandbox.object_id}")
    return 0


def run(args: argparse.Namespace) -> int:
    """Run a command in the session's environment and return its status."""
    command = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    if not command:
        raise SystemExit("selkies-modal: exec takes a command after --")
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    process = sandbox.exec(
        "/usr/local/bin/selkies-modal-run", *command, stdout=StreamType.STDOUT, stderr=StreamType.STDOUT
    )
    return process.wait()


def blender(args: argparse.Namespace) -> int:
    """Run the Python on standard input inside the session's Blender and print what it printed."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    status, output = blender_python(sandbox, sys.stdin.read(), args.wait)
    sys.stdout.write(output)
    return status


def filmcraft(args: argparse.Namespace) -> int:
    """Send the JSON requests on standard input, one per line, to the session's FilmCraft and print each reply."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    process = filmcraft_requests(sandbox, sys.stdin.read(), args.wait)
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
    status = process.wait()
    sys.stderr.write(process.stderr.read())
    return status


def vectorcraft(args: argparse.Namespace) -> int:
    """Send the JSON requests on standard input, one per line, to the session's VectorCraft and print each reply."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    process = vectorcraft_requests(sandbox, sys.stdin.read(), args.wait)
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
    status = process.wait()
    sys.stderr.write(process.stderr.read())
    return status


def down(args: argparse.Namespace) -> int:
    """Stop a session, which ends its billing; its workspace stays."""
    sandbox = find_session(args.name)
    if sandbox is None:
        say(f"no session named {args.name} is running")
        return 0
    stop_session(sandbox)
    say(f"{args.name} ({sandbox.object_id}) stopped")
    return 0


def build(args: argparse.Namespace) -> int:
    """Build an application's image without starting a session, so the next `up` starts from Modal's cache."""
    app = modal.App.lookup(APP_NAME, create_if_missing=True)
    started = time.monotonic()
    image = session_image(args.app).build(app)
    say(f"image {image.object_id} ready after {time.monotonic() - started:.0f} s")
    return 0


def drive_login(args: argparse.Namespace) -> int:
    """Connect Google Drive through a person's sign-in in a session, and keep the access as a Modal Secret.

    The Secret holds the remote `gdrive` as rclone reads it from the
    environment (`RCLONE_CONFIG_GDRIVE_...`), rooted at the folder `--folder`
    names or at the account's own drive, so a session started with `--secret`
    copies to and from it with no setup. A folder reaches what was shared with
    the account however it was shared, in a shared drive, in someone's own
    drive, or by its link, where a shared drive takes membership of it. The
    access is tried from the session before it is kept, and what the folder
    holds is printed: a sign-in that reaches nothing replaces no Secret that
    worked.
    """
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    values = {
        "RCLONE_CONFIG_GDRIVE_TYPE": "drive",
        "RCLONE_CONFIG_GDRIVE_SCOPE": "drive",
        "RCLONE_CONFIG_GDRIVE_ROOT_FOLDER_ID": args.folder,
        "RCLONE_CONFIG_GDRIVE_TOKEN": drive_sign_in(sandbox, round(args.wait_minutes * 60)),
    }
    check = sandbox.exec(
        "/usr/local/bin/selkies-modal-run",
        "rclone",
        "lsf",
        "--max-depth",
        "1",
        "gdrive:",
        secrets=[modal.Secret.from_dict(values)],
    )
    listing = check.stdout.read()
    if check.wait() != 0:
        raise SystemExit(f"selkies-modal: signed in, but Google Drive refused: {check.stderr.read().strip()}")
    modal.Secret.objects.create(args.secret, values, allow_existing=True)
    modal.Secret.from_name(args.secret).update(values)
    say(f"Google Drive is connected as the Secret {args.secret}; a session started with --secret {args.secret} has it as gdrive:")
    sys.stdout.write(listing)
    return 0


def workspace_directory(value: str) -> str:
    """A `--workspace` argument: a directory of the Volume, as words joined by slashes."""
    parts = value.strip("/").split("/")
    if not all(part and part not in (".", "..") and part.replace("-", "").replace("_", "").isalnum() for part in parts):
        raise argparse.ArgumentTypeError(f"{value!r} is not a directory name like team/nuke")
    return "/".join(parts)


def environment_assignment(value: str) -> str:
    """An `--env` argument, which has to be `NAME=value`."""
    if "=" not in value or value.startswith("="):
        raise argparse.ArgumentTypeError(f"{value!r} is not NAME=value")
    return value


def parser() -> argparse.ArgumentParser:
    """The command line: one subcommand per verb, each naming its session with `--name`."""
    top = argparse.ArgumentParser(prog="selkies-modal", description=__doc__.splitlines()[0])
    commands = top.add_subparsers(dest="verb", required=True)

    def command(name: str, handler, summary: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=summary, description=summary)
        sub.set_defaults(handler=handler)
        return sub

    def named(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument("--name", default="blender", help="the session's name (default: %(default)s)")
        return sub

    start = named(command("up", up, "Start a session, or return the one running, and print its link."))
    start.add_argument("--app", choices=APPS, default="blender", help="the application the session runs (default: %(default)s)")
    start.add_argument(
        "--workspace",
        type=workspace_directory,
        # Not "": argparse runs a string default through `type`, which refuses it
        default=None,
        help="the directory of the workspace Volume the session keeps its files in (default: all of it)",
    )
    start.add_argument(
        "--gpu",
        default="T4",
        help="a GPU type Modal offers, such as T4, L4, or A10, or none to render and encode in software (default: %(default)s)",
    )
    start.add_argument("--cpu", type=float, default=2.0, help="CPU cores reserved; more are used as needed (default: %(default)s)")
    start.add_argument("--memory", type=int, default=4096, help="MiB of memory reserved (default: %(default)s)")
    start.add_argument(
        "--idle-minutes", type=float, default=10.0, help="end the session after this long unused; 0 never (default: %(default)s)"
    )
    start.add_argument(
        "--lifetime-hours", type=float, default=8.0, help="end the session after this long whatever it is doing, 24 at most (default: %(default)s)"
    )
    start.add_argument("--ready-timeout", type=int, default=600, help="seconds to wait for Selkies to listen (default: %(default)s)")
    start.add_argument(
        "--secret",
        action="append",
        default=[],
        metavar="NAME",
        help="a Modal Secret whose variables the session gets, such as the Drive access rclone reads; repeatable",
    )
    start.add_argument(
        "--tcp-port",
        action="append",
        default=[],
        type=int,
        metavar="PORT",
        help="a port of the session Modal exposes as raw TCP, open to any address, at a public address up prints; repeatable",
    )
    start.add_argument(
        "--env",
        action="append",
        default=[],
        type=environment_assignment,
        metavar="NAME=value",
        help="a variable for the session, such as SELKIES_DESKTOP=true or SELKIES_ENCODER=av1enc; repeatable",
    )
    link = named(command("url", url, "Print a new link to a running session."))
    link.add_argument(
        "--view",
        choices=("desktop", "unreal"),
        default="desktop",
        help="the page the link opens: the desktop, or an Unreal session's Unreal view (default: %(default)s)",
    )
    command("ls", ls, "List the running sessions.")
    execute = named(command("exec", run, "Run a command in a session's environment."))
    execute.add_argument("arguments", nargs=argparse.REMAINDER, metavar="-- command", help="the command and its arguments")
    script = named(command("blender", blender, "Run the Python on standard input inside a session's Blender."))
    script.add_argument("--wait", type=int, default=120, help="seconds to wait for Blender to answer (default: %(default)s)")
    control = named(
        command("filmcraft", filmcraft, "Send the JSON requests on standard input, one per line, to a session's FilmCraft.")
    )
    control.add_argument(
        "--wait", type=int, default=60, help="seconds to wait for FilmCraft to be ready and for each reply (default: %(default)s)"
    )
    vector = named(
        command("vectorcraft", vectorcraft, "Send the JSON requests on standard input to a session's VectorCraft control channel.")
    )
    vector.add_argument("--wait", type=int, default=60, help="seconds to wait for VectorCraft to answer (default: %(default)s)")
    named(command("down", down, "Stop a session."))
    drive = named(
        command("drive-login", drive_login, "Connect Google Drive by a sign-in in a session's Firefox, kept as a Modal Secret.")
    )
    drive.add_argument(
        "--folder", default="", metavar="ID", help="the Drive folder gdrive: opens on, from its address (default: the account's own drive)"
    )
    drive.add_argument("--secret", default="gdrive", help="the Modal Secret to keep the access in (default: %(default)s)")
    drive.add_argument(
        "--wait-minutes", type=float, default=10.0, help="how long the sign-in stays open (default: %(default)s)"
    )
    image = command("build", build, "Build an application's image without starting a session.")
    image.add_argument("--app", choices=APPS, default="blender", help="the application (default: %(default)s)")
    return top


def main() -> int:
    """Parse the command line and run its subcommand.

    What Modal refuses (no token, a GPU on an account without a payment method,
    a quota) is the user's to act on, so it is printed as Modal words it rather
    than as a traceback.
    """
    args = parser().parse_args()
    try:
        return args.handler(args)
    except modal.exception.Error as error:
        raise SystemExit(f"selkies-modal: {error}") from None


if __name__ == "__main__":
    sys.exit(main())
