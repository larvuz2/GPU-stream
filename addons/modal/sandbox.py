# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Run Blender in a Selkies session on a Modal Sandbox and hand back its link.

Modal runs the container on a GPU and carries the one port of the WebSocket
transport to the browser; everything in the session is the base container's
own. `up` builds or reuses the image (Blender layered over the base image this
tree publishes), starts a Sandbox whose main process is `session.sh`, waits
until Selkies listens, and prints a link carrying two credentials:

- The path the session's server answers under, a random one made for this
  session (`SELKIES_SUBFOLDER`), for the right to reach the server at all:
  outside it nothing is served, so whoever finds the Sandbox's address without
  the link meets a server that answers nothing.
- The Selkies session token, in the fragment (`#token=`), which no request line
  carries. The session is in secure mode, so nothing streams without it.

The address is a tunnel Modal opens to the session's port, and both
credentials travel in the link itself, which is what lets a page show the
session in a frame. Modal's own gate for a Sandbox, a connect token its proxy
answers with a cookie, keeps the session out of every frame: the cookie is
`SameSite=Lax`, which a browser neither stores nor sends for a document framed
by another site, so the first document arrives and every request after it is
refused. A session started without the tunnel is still reached that way
(`session_link`), and the Unreal view, whose server has no credential of its
own, always is.

Neither credential is kept on this side: a later `url` reads both back out of
the Sandbox, which takes the Modal credentials that started it.

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
(`filmcraft_call`), as SoundCraft does on its own, which takes no token
(`soundcraft_call`). None is exposed beyond the Sandbox, so driving one takes
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
import os
import re
import sys
import time
import urllib.request
from pathlib import Path, PurePosixPath
from secrets import token_hex, token_urlsafe
from typing import Any, Callable

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
# FilmCraft's, PhotoCraft's, and SoundCraft's Debian packages from their GitHub releases, and the
# hash each release's SHA256SUMS.txt lists for it
FILMCRAFT_VERSION = "0.20.1"
FILMCRAFT_SHA256 = "5667c7505c91d2ad9de3c4acb15cb02fc9f138fae74dce9c7c5f08bc29edb3a8"
PHOTOCRAFT_VERSION = "0.23.1"
PHOTOCRAFT_SHA256 = "baabdcdbe46df2f72ccf6ecc2e98be00fbc33dbd4c1cd9426362a89a4b95f673"
SOUNDCRAFT_VERSION = "0.20.1"
SOUNDCRAFT_SHA256 = "a217c7f65bb55ef4d7417f1c204244d974f25d6b779477727c440800d8256081"
# CADCraft's Debian package, by the same rule
CADCRAFT_VERSION = "0.20.1"
CADCRAFT_SHA256 = "8e6ad1f487d6cd44dbcb73cd88ef1efb52252a2071094f2c23a468a641a06faa"
VECTORCRAFT_VERSION = "0.24.1"
VECTORCRAFT_SHA256 = "ae6733083d2819efe980d76d41d1908d40fe487bb9a5e7679292b53fd8dc49d7"
# LightCraft's, from its release's SHA256SUMS.txt as theirs are
LIGHTCRAFT_VERSION = "0.21.1"
LIGHTCRAFT_SHA256 = "c91ef47bec44995d99ce58e6c748af9fa6ab1ff1c11de9e290e0b8231176dad1"
CRAFT_RELEASES = {
    "filmcraft": (FILMCRAFT_VERSION, FILMCRAFT_SHA256),
    "photocraft": (PHOTOCRAFT_VERSION, PHOTOCRAFT_SHA256),
    "soundcraft": (SOUNDCRAFT_VERSION, SOUNDCRAFT_SHA256),
    "cadcraft": (CADCRAFT_VERSION, CADCRAFT_SHA256),
    "vectorcraft": (VECTORCRAFT_VERSION, VECTORCRAFT_SHA256),
    "lightcraft": (LIGHTCRAFT_VERSION, LIGHTCRAFT_SHA256),
}
# The Cut Room's parts beside the base image's FFmpeg (`cutroom_image`, `cutroom/install.sh`). Its Python
# packages are pinned, each wheel by its hash, in `cutroom/python.lock`.
# Inter's release archive of github.com/rsms/inter and its SHA-256; SIL Open Font License 1.1
CUTROOM_INTER_VERSION = "4.1"
CUTROOM_INTER_SHA256 = "9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e"
# Archivo Black as github.com/google/fonts has it at one commit (ofl/archivoblack), with the SHA-256 of
# ArchivoBlack-Regular.ttf and of the license beside it; SIL Open Font License 1.1
CUTROOM_ARCHIVO_BLACK_COMMIT = "6ebe737e44fd64ee736bbc6feed6136a6dbfd222"
CUTROOM_ARCHIVO_BLACK_SHA256 = "dd9a89a019b4849f66ab75455fe7bdf931311042cbb0f0f97acc061539703180"
CUTROOM_ARCHIVO_BLACK_LICENSE_SHA256 = "3173acd82f8c6159b5b1037b539fcbd4edff68e65c2ea8b9412b5a5ca97b08ff"
# The speech models the scripts load, huggingface.co/Systran/faster-whisper-<name>: the revision and the
# SHA-256 of its weights (model.bin); MIT
CUTROOM_WHISPER = {
    "small": ("536b0662742c02347bc0e980a01041f333bce120", "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"),
    "medium": ("08e178d48790749d25932bbc082711ddcfdfbc4f", "9b45e1009dcc4ab601eff815b61d80e60ce3fd8c74c1a14f4a282258286b51ae"),
}
# The face detector the webcam finder runs, huggingface.co/opencv/face_detection_yunet: the revision and the
# SHA-256 of face_detection_yunet_2023mar.onnx; MIT
CUTROOM_YUNET_REVISION = "3cc26e7f1014a5ee5d74a42acee58bafc9d0a310"
CUTROOM_YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
# The HyperFrames session's parts that are pinned (`hyperframes_image`, `hyperframes/install.sh`): Node.js's
# Linux build with the hash nodejs.org's SHASUMS256.txt lists for it, and Chrome for Testing, which the live
# preview opens in, with the SHA-256 of its chrome-linux64.zip
HYPERFRAMES_NODE_VERSION = "22.23.5"
HYPERFRAMES_NODE_SHA256 = "cdeb8670a0c81f51b4dc4ac61919f9b1ad917b304bf8221eb939570663d240f8"
HYPERFRAMES_CHROME_VERSION = "158.0.8127.88"
HYPERFRAMES_CHROME_SHA256 = "59e3b43f8b3aaa292238fbdcfb36a93127debd53e212510dcdc2cc8812b4b57e"
# The HyperFrames CLI is the one part that is not pinned: an image is built with the newest release of the
# npm package `hyperframes` (`hyperframes_release`), and this is the release it is built with where the
# registry does not answer, the one these files were written and proven against
HYPERFRAMES_RELEASE = "0.9.97"
HYPERFRAMES_REGISTRY = "https://registry.npmjs.org"
# The release every HyperFrames session is held on, read from the environment of whoever defines the image (the
# control plane, or the shell `selkies-modal` runs in): a version such as 0.9.97, or `built` for the image's own.
# Unset, which is how a deployment starts, a session follows upstream (hyperframes/release.sh)
HYPERFRAMES_HELD = os.environ.get("MOODY_HYPERFRAMES_VERSION", "")
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
# SoundCraft's control channel, loopback only as well; it takes no token (`soundcraft_call`)
SOUNDCRAFT_CONTROL_PORT = 7801
# The TCP port a session's TURN relay listens on (webrtc/turnserver.sh), exposed with `tcp_ports`
TURN_PORT = 3478
# The Unreal view, the Unreal session's second page beside the desktop (unreal/view/view.sh)
UNREAL_VIEW_PORT = 8090
# Where an Unreal session's clone of its repository says how far it is (unreal/clone.py)
UNREAL_CLONE_STATUS = "/tmp/selkies-modal/unreal-clone.json"

# CADCraft's, on loopback as well
CADCRAFT_CONTROL_PORT = 9878

# VectorCraft's control channel, on the Sandbox's loopback only as well, and the file that says the
# session has brought the project's documents back (vectorcraft/resume.sh)
VECTORCRAFT_CONTROL_PORT = 7979
VECTORCRAFT_READY_FILE = "/tmp/selkies-modal/vectorcraft-ready"

# LightCraft's, loopback only as theirs are, and the port its own documentation uses
LIGHTCRAFT_CONTROL_PORT = 7980

# Where the Cut Room is installed in its image, and the log of its commands a session shows on its screen
CUTROOM_ROOT = "/opt/cutroom"
CUTROOM_LOG = "/tmp/selkies-modal/cutroom.log"

# Where HyperFrames is installed in its image, and the log a session shows on its screen until a preview is on it
HYPERFRAMES_ROOT = "/opt/hyperframes"
HYPERFRAMES_LOG = "/tmp/selkies-modal/hyperframes.log"

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
    "soundcraft": {
        "SELKIES_MODAL_APP": "soundcraft",
        # The control channel, which SoundCraft itself reads the port of
        "SOUNDCRAFT_CONTROL_PORT": str(SOUNDCRAFT_CONTROL_PORT),
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
    "cadcraft": {
        "SELKIES_MODAL_APP": "cadcraft",
        # The control channel; CADCraft makes its token itself as it starts (cadcraft/control.sh)
        "CADCRAFT_CONTROL_PORT": str(CADCRAFT_CONTROL_PORT),
        # Mesa's Vulkan in software (lavapipe), as FilmCraft draws: a Sandbox has no render node
        # with or without a GPU, and a drawing is 2D lines the CPU rasterizes at the display's rate
        "WGPU_BACKEND": "vulkan",
    },
    "vectorcraft": {
        "SELKIES_MODAL_APP": "vectorcraft",
        # The control channel; the token a release with a sign-in takes is the session's own (start_session)
        "VECTORCRAFT_CONTROL_PORT": str(VECTORCRAFT_CONTROL_PORT),
        "SELKIES_MODAL_VECTORCRAFT_READY": VECTORCRAFT_READY_FILE,
    },
    "lightcraft": {
        "SELKIES_MODAL_APP": "lightcraft",
        # The control channel, which takes no token: loopback is what guards it (lightcraft/autostart)
        "LIGHTCRAFT_CONTROL_PORT": str(LIGHTCRAFT_CONTROL_PORT),
        # As FilmCraft: the window draws through Mesa's Vulkan in software on every machine, and
        # Vulkan is what reaches a GPU where there is one, for the develop pipeline. Without one
        # LightCraft develops on the CPU, having found only a software adapter. OpenGL is left
        # out: its window was no quicker than the spread between runs on the machine without a
        # GPU, and on a GPU machine LightCraft's kernels fail to build on NVIDIA's OpenGL.
        "WGPU_BACKEND": "vulkan",
    },
    "cutroom": {
        "SELKIES_MODAL_APP": "cutroom",
        # Where every `cutroom` command writes what it ran, which the session's screen shows (cutroom/autostart)
        "CUTROOM_LOG": CUTROOM_LOG,
    },
    "hyperframes": {
        "SELKIES_MODAL_APP": "hyperframes",
        "HYPERFRAMES_LOG": HYPERFRAMES_LOG,
        # The CLI reports its use to its makers unless told not to; a person's session reports nothing
        "HYPERFRAMES_NO_TELEMETRY": "1",
        # Which release runs is the session's own to settle (hyperframes/release.sh), so the CLI neither offers
        # another nor installs skills into the home; the release's skills are at HYPERFRAMES_ROOT/skills
        "HYPERFRAMES_NO_UPDATE_CHECK": "1",
        "HYPERFRAMES_SKIP_SKILLS": "1",
        # Set only where a deployment holds its sessions on one release (HYPERFRAMES_HELD)
        **({"MOODY_HYPERFRAMES_VERSION": HYPERFRAMES_HELD} if HYPERFRAMES_HELD else {}),
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
    FilmCraft, PhotoCraft, and SoundCraft are the Debian packages of their
    GitHub releases, each checked against the hash its release publishes
    (`craft/install.sh`), with what finds the session's project folder
    (`craft/project.sh`); FilmCraft and SoundCraft each add the client of their
    control channel (`filmcraft/control.sh`, `soundcraft/control.sh`). Unreal's
    is the desktop its editor runs beside, without the editor
    (`unreal_desktop`); `unreal_image` is the same desktop with the editor.
    The Cut Room's has no application at all (`cutroom_image`), and neither
    has HyperFrames', the one image whose main part follows its upstream
    instead of a pin (`hyperframes_image`).
    """
    if app == "unreal":
        return with_session(unreal_desktop(modal.Image.from_registry(BASE_IMAGE)), app)
    if app == "cutroom":
        return with_session(cutroom_image(), app)
    if app == "hyperframes":
        return with_session(hyperframes_image(), app)
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
        if app == "photocraft":
            image = image.add_local_file(HERE / "photocraft" / "control.sh", "/usr/local/bin/selkies-modal-photocraft", copy=True)
        if app == "lightcraft":
            image = image.add_local_file(
                HERE / "lightcraft" / "control.sh", "/usr/local/bin/selkies-modal-lightcraft", copy=True
            ).add_local_file(HERE / "lightcraft" / "histogram.py", "/usr/local/bin/selkies-modal-histogram", copy=True)
        if app == "cadcraft":
            image = image.add_local_file(HERE / "cadcraft" / "control.sh", "/usr/local/bin/selkies-modal-cadcraft", copy=True)
            image = image.add_local_file(HERE / "cadcraft" / "keep.sh", "/usr/local/bin/selkies-modal-cadcraft-keep", copy=True)
        if app == "vectorcraft":
            # The client of its control channel, and what brings a project's documents back at start
            image = image.add_local_file(
                HERE / "vectorcraft" / "control.sh", "/usr/local/bin/selkies-modal-vectorcraft", copy=True
            ).add_local_file(HERE / "vectorcraft" / "resume.sh", "/usr/local/bin/selkies-modal-vectorcraft-resume", copy=True)
        if app == "soundcraft":
            image = image.add_local_file(HERE / "soundcraft" / "control.sh", "/usr/local/bin/selkies-modal-soundcraft", copy=True)
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


def cutroom_image() -> modal.Image:
    """The Cut Room's image: the base container with what editing video by code takes, and no application.

    A Cut Room session is a machine an agent drives with shell commands, so
    the image is its tools at fixed paths (`cutroom/install.sh` documents each
    step):

    - **FFmpeg** is the base image's own, pinned by the base's digest. The
      build fails unless it has every filter and encoder the scripts call:
      libass's `subtitles`, Rubber Band, `loudnorm`, and x264 among them.
    - **Python.** A virtual environment at `CUTROOM_ROOT/venv` with the wheels
      `cutroom/python.lock` names, each checked against its hash: faster-whisper,
      NumPy, OpenCV, Pedalboard, Pillow, yt-dlp, and what the scripts import
      beside them. The lock is compiled from `cutroom/python.in` for the base
      image's Python.
    - **Fonts.** Inter and Archivo Black, each from its upstream at a pinned
      version and checksum, with the SIL Open Font License beside it.
    - **Models.** The two Whisper conversions the scripts load and the face
      detector, at pinned revisions and checksums, so a session fetches none.
    - **The scripts,** `cutroom/scripts`, at `CUTROOM_ROOT/scripts`, each run
      as `cutroom NAME` from any directory (`cutroom/run.sh`).

    The session's screen is a terminal on the log of those commands
    (`cutroom/autostart`). The layers are ordered by how often they change:
    the tools (`cutroom_tools`), then the small files and the scripts, so a
    changed script rebuilds a layer of kilobytes.
    """
    cutroom = HERE / "cutroom"
    return (
        cutroom_tools()
        .add_local_file(HERE / "craft" / "project.sh", "/usr/local/bin/selkies-modal-project", copy=True)
        .add_local_file(cutroom / "autostart", "/etc/xdg/openbox/autostart", copy=True)
        .add_local_file(cutroom / "run.sh", "/usr/local/bin/cutroom", copy=True)
        .add_local_dir(cutroom / "scripts", f"{CUTROOM_ROOT}/scripts", copy=True, ignore=["**/__pycache__"])
    )


def cutroom_fonts() -> str:
    """The Dockerfile step that installs Inter and Archivo Black, pinned and checked (`cutroom/install.sh fonts`)."""
    return (
        f"RUN sh {SHARE}/cutroom/install.sh fonts {CUTROOM_INTER_VERSION} {CUTROOM_INTER_SHA256} "
        f"{CUTROOM_ARCHIVO_BLACK_COMMIT} {CUTROOM_ARCHIVO_BLACK_SHA256} {CUTROOM_ARCHIVO_BLACK_LICENSE_SHA256}"
    )


def cutroom_tools() -> modal.Image:
    """The base container with the Cut Room's packages, Python environment, fonts, and models: the heavy layers.

    They change only when a pin moves, so they are an image of their own
    under the scripts, and the last step proves them: it fails the build
    unless FFmpeg has what the scripts call and every package and model
    loads.
    """
    cutroom = HERE / "cutroom"
    install = f"sh {SHARE}/cutroom/install.sh"
    return (
        modal.Image.from_registry(BASE_IMAGE)
        .add_local_file(cutroom / "install.sh", f"{SHARE}/cutroom/install.sh", copy=True)
        .dockerfile_commands(f"RUN selkies-privileged-files run {install} packages")
        .add_local_file(cutroom / "python.lock", f"{SHARE}/cutroom/python.lock", copy=True)
        .dockerfile_commands(
            f"RUN {install} python {SHARE}/cutroom/python.lock",
            cutroom_fonts(),
            *(f"RUN {install} whisper {name} {revision} {sha256}" for name, (revision, sha256) in CUTROOM_WHISPER.items()),
            f"RUN {install} yunet {CUTROOM_YUNET_REVISION} {CUTROOM_YUNET_SHA256}",
            f"RUN {install} verify",
        )
    )


def hyperframes_release() -> str:
    """The release of the HyperFrames CLI an image defined now is built with.

    The newest release of the npm package, asked of the registry, since this
    engine follows its upstream (`hyperframes/release.sh` says why and what
    bounds the risk). A deployment that holds its sessions on one release
    (`MOODY_HYPERFRAMES_VERSION`, a version) builds with that one. Where the
    registry does not answer within five seconds, or answers with something
    that is not a version, the image is built with `HYPERFRAMES_RELEASE`, so
    defining an image never fails for want of the network.

    The version is part of the image's definition, so Modal builds the layer
    again when a new release is out and reuses it until then.
    """
    if re.fullmatch(r"\d+\.\d+\.\d+", HYPERFRAMES_HELD):
        return HYPERFRAMES_HELD
    try:
        with urllib.request.urlopen(f"{HYPERFRAMES_REGISTRY}/hyperframes/latest", timeout=5) as answer:
            newest = str(json.load(answer).get("version", ""))
    except (OSError, ValueError):
        return HYPERFRAMES_RELEASE
    return newest if re.fullmatch(r"\d+\.\d+\.\d+", newest) else HYPERFRAMES_RELEASE


def hyperframes_image() -> modal.Image:
    """The HyperFrames image: the base container with what writing a video as HTML and rendering it takes.

    HyperFrames (HeyGen's, Apache 2.0) renders a composition of HTML, CSS,
    and seekable animation by stepping a headless browser through its frames
    and encoding them with FFmpeg. A session is driven with shell commands, as
    the Cut Room is, and has one thing to watch: the live preview.

    - **Pinned**, as every engine's parts are (`hyperframes/install.sh`):
      Node.js, which the CLI runs on; Chrome for Testing, which the preview
      opens in on the session's screen (`hyperframes/preview.sh`); the
      libraries a Chrome links; and the Cut Room's fonts (`cutroom_fonts`).
      FFmpeg is the base image's.
    - **Following upstream**, the one place this engine differs: the
      HyperFrames CLI, its skills, and the headless browser each release
      renders with. The image is built with the newest release
      (`hyperframes_release`), or with `HYPERFRAMES_RELEASE` where the newest
      does not install and render in the build, and a session moves to the
      newest again as it starts, within a bound of time, falling back on the
      image's release (`hyperframes/release.sh` has the mechanism, the
      reasons, and the risk). Whoever defines the image asks the registry
      when it defines it, so a control plane that keeps an app's image for
      the life of its container builds with a new release when it next
      starts; the session's own update covers the time between.
      `hyperframes-release status` says which release a session runs. The
      folder is the session user's, so a session can install a release.

    The release's skills are at `HYPERFRAMES_ROOT/skills`, the craft an agent
    reads on the machine before it writes a composition; they are upstream's
    and are not copied into this repository. The build's last step fails
    unless the CLI answers with the version it was built with, its skills are
    there, and both browsers find their libraries.
    """
    hyperframes = HERE / "hyperframes"
    install = f"sh {SHARE}/hyperframes/install.sh"
    as_user = "setpriv --reuid=1000 --regid=1000 --init-groups env HOME=/home/ubuntu"
    # The newest release, then the proven one: the first that installs and renders is the image's (release.sh)
    releases = " ".join(dict.fromkeys((hyperframes_release(), HYPERFRAMES_RELEASE)))
    return (
        modal.Image.from_registry(BASE_IMAGE)
        .add_local_file(hyperframes / "install.sh", f"{SHARE}/hyperframes/install.sh", copy=True)
        .dockerfile_commands(
            f"RUN selkies-privileged-files run {install} packages",
            f"RUN {install} node {HYPERFRAMES_NODE_VERSION} {HYPERFRAMES_NODE_SHA256}",
            f"RUN {install} chrome {HYPERFRAMES_CHROME_VERSION} {HYPERFRAMES_CHROME_SHA256}",
        )
        .add_local_file(HERE / "cutroom" / "install.sh", f"{SHARE}/cutroom/install.sh", copy=True)
        .dockerfile_commands(cutroom_fonts())
        .add_local_file(hyperframes / "release.sh", "/usr/local/bin/hyperframes-release", copy=True)
        .add_local_file(hyperframes / "run.sh", "/usr/local/bin/hyperframes", copy=True)
        .dockerfile_commands(
            f"RUN chown 1000:1000 {HYPERFRAMES_ROOT} && {as_user} hyperframes-release build {releases}",
            f"RUN {install} verify",
        )
        .add_local_file(HERE / "craft" / "project.sh", "/usr/local/bin/selkies-modal-project", copy=True)
        .add_local_file(hyperframes / "autostart", "/etc/xdg/openbox/autostart", copy=True)
        .add_local_file(hyperframes / "preview.sh", "/usr/local/bin/hyperframes-preview", copy=True)
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
    """A link that opens the session: its tunnel's address, the path its server answers under, and its own token.

    Both credentials are read from the session, and reading them counts as
    use of it: a link is asked for by someone about to open it. A session
    that has no tunnel to its port or no path of its own is reached through
    Modal's connect token instead, which opens in a tab of its own and in no
    frame (the module's docstring).
    """
    process = sandbox.exec(
        "sh", "-c", 'touch "$SELKIES_MODAL_ACTIVITY_FILE" && printf "%s\\n" "${SELKIES_SUBFOLDER:-}" && cat "$SELKIES_TOKENS_FILE"'
    )
    answer = process.stdout.read()
    if process.wait() != 0:
        raise SystemExit(f"selkies-modal: the session's token could not be read: {process.stderr.read().strip()}")
    path, _, table = answer.partition("\n")
    token = next(iter(json.loads(table)))
    tunnel = sandbox.tunnels().get(PORT) if path.strip() else None
    if tunnel is not None:
        return f"{tunnel.url}/{path.strip()}/#token={token}"
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
    the TURN relay mints its credentials with (`with_turn`). They are made for
    every session, since a caller holding a built image does not say which
    application it is, and a session of another application leaves them unread.

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
            # The path the server answers under, which the link carries and nothing else knows (`session_link`)
            "SELKIES_SUBFOLDER": token_urlsafe(24),
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
        encrypted_ports=[PORT],
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


def soundcraft_requests(sandbox: modal.Sandbox, requests: str, wait_seconds: int) -> modal.container_process.ContainerProcess:
    """Hand JSON requests, one per line, to the session's SoundCraft and return the process printing its replies.

    The requests go from inside the Sandbox, the only place the control
    channel listens: `soundcraft/control.sh` sends each and prints each reply
    on a line of its own, and runs as a command of the session, so it counts
    as use while it waits.
    """
    process = sandbox.exec("/usr/local/bin/selkies-modal-run", "selkies-modal-soundcraft", str(wait_seconds), bufsize=1)
    try:
        process.stdin.write(requests)
        process.stdin.write_eof()
        process.stdin.drain()
    except modal.exception.Error:
        # The command ended before it read anything; its status and output say why
        pass
    return process


def soundcraft_call(sandbox: modal.Sandbox, method: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    """Send one request on the session's SoundCraft control channel and return its result.

    `method` and `params` are those of SoundCraft's control protocol:
    `engine.execute` with `{"command", "params"}` runs any of its commands,
    `session.inspect` reads the session, and the `ui.*` methods read and drive
    its window. `timeout` is how many seconds to wait for SoundCraft to
    listen, which it does as its window opens, and then for the reply.
    SoundCraft gives up on a reply itself after 90 s, and a bounce renders
    within the request that asks for it, so a long one is bounced in ranges
    that each fit.

    SoundCraft's channel takes no token, unlike FilmCraft's: it answers
    whatever reaches the Sandbox's loopback, which only a process of the
    session does.

    The result is the reply's `result`, an object for most methods; a result
    that is not one, such as the list `engine.plugins` returns, comes back as
    `{"result": ...}`.

    Raises:
        RuntimeError: SoundCraft refused the request, with its message, or did not answer within `timeout`.
    """
    request = json.dumps({"id": 1, "method": method, "params": params or {}})
    process = soundcraft_requests(sandbox, request + "\n", timeout)
    output = process.stdout.read()
    status = process.wait()
    if not output.strip():
        raise RuntimeError(f"SoundCraft did not answer: {process.stderr.read().strip() or f'status {status}'}")
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


def cadcraft_requests(sandbox: modal.Sandbox, requests: str, wait_seconds: int) -> modal.container_process.ContainerProcess:
    """Hand JSON requests, one per line, to the session's CADCraft and return the process printing its replies.

    The requests go from inside the Sandbox, the only place the control
    channel listens and its token is: `cadcraft/control.sh` adds the token
    CADCraft wrote as it started to each and prints each reply on a line of its
    own, and runs as a command of the session, so it counts as use while it
    waits.
    """
    process = sandbox.exec("/usr/local/bin/selkies-modal-run", "selkies-modal-cadcraft", str(wait_seconds), bufsize=1)
    try:
        process.stdin.write(requests)
        process.stdin.write_eof()
        process.stdin.drain()
    except modal.exception.Error:
        # The command ended before it read anything; its status and output say why
        pass
    return process


def cadcraft_call(sandbox: modal.Sandbox, method: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    """Send one request on the session's CADCraft control channel and return its result.

    `method` and `params` are those of CADCraft's control protocol:
    `engine.execute` with `{"command", "params"}` runs any of its commands,
    `cmdline.input` with `{"text"}` types at its command line as a person does,
    `drawing.inspect` reads the drawing back, and the `ui.*` methods read and
    drive its window. `timeout` is how many seconds to wait for CADCraft to be
    ready, which it is as its window opens, and then for the reply. CADCraft
    gives up on a reply itself after 60 s, saying whether the request had
    started, which the error raised here repeats (`timeout (may-have-run)`):
    the drawing is inspected before such a request is sent again.

    The result is the reply's `result`, an object for most methods; a result
    that is not one, such as the list `engine.commands` returns, comes back as
    `{"result": ...}`.

    Raises:
        RuntimeError: CADCraft refused the request, with its message, or did not answer within `timeout`.
    """
    request = json.dumps({"id": 1, "method": method, "params": params or {}})
    process = cadcraft_requests(sandbox, request + "\n", timeout)
    output = process.stdout.read()
    status = process.wait()
    if not output.strip():
        raise RuntimeError(f"CADCraft did not answer: {process.stderr.read().strip() or f'status {status}'}")
    reply = json.loads(output.splitlines()[-1])
    if not reply.get("ok"):
        state = f" ({reply['state']})" if reply.get("state") else ""
        raise RuntimeError(f"{reply.get('error') or output.strip()}{state}")
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


def lightcraft_requests(sandbox: modal.Sandbox, requests: str, wait_seconds: int) -> modal.container_process.ContainerProcess:
    """Hand JSON requests, one per line, to the session's LightCraft and return the process printing its replies.

    As `filmcraft_requests`, through `lightcraft/control.sh`: from inside the
    Sandbox, the only place the control channel listens, as a command of the
    session, so it counts as use while it waits.
    """
    process = sandbox.exec("/usr/local/bin/selkies-modal-run", "selkies-modal-lightcraft", str(wait_seconds), bufsize=1)
    try:
        process.stdin.write(requests)
        process.stdin.write_eof()
        process.stdin.drain()
    except modal.exception.Error:
        # The command ended before it read anything; its status and output say why
        pass
    return process


def lightcraft_call(sandbox: modal.Sandbox, method: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    """Send one request on the session's LightCraft control channel and return its result.

    `method` and `params` are those of LightCraft's control protocol:
    `engine.execute` with `{"command", "params"}` runs any of its commands, and
    the `ui.*` methods read and drive its window. `timeout` is how many seconds
    to wait for LightCraft to listen and then for the reply. LightCraft gives up
    on a reply itself after 60 s, so a long export is started with
    `background: true` and followed with `ui.inspect`'s `export`.

    The result is the reply's `result`, an object for most methods; a result
    that is not one, such as the list `develop.controls` returns or the `null`
    of a command with nothing to say, comes back as `{"result": ...}`.

    Raises:
        RuntimeError: LightCraft refused the request, with its message, or did not answer within `timeout`.
    """
    request = json.dumps({"id": 1, "method": method, "params": params or {}})
    process = lightcraft_requests(sandbox, request + "\n", timeout)
    output = process.stdout.read()
    status = process.wait()
    if not output.strip():
        raise RuntimeError(f"LightCraft did not answer: {process.stderr.read().strip() or f'status {status}'}")
    reply = json.loads(output.splitlines()[-1])
    if not reply.get("ok"):
        raise RuntimeError(reply.get("error") or output.strip())
    result = reply.get("result")
    return result if isinstance(result, dict) else {"result": result}


def photocraft_requests(sandbox: modal.Sandbox, requests: str, wait_seconds: int) -> modal.container_process.ContainerProcess:
    """Hand JSON requests, one per line, to the session's PhotoCraft and return the process printing its replies.

    The requests go from inside the Sandbox, the only place the control
    channel listens and its token is: `photocraft/control.sh` authenticates a
    connection for each by PhotoCraft's challenge, which proves the token to
    both sides without sending it, and prints each reply on a line of its own.
    It runs as a command of the session, so it counts as use while it waits.
    """
    process = sandbox.exec("/usr/local/bin/selkies-modal-run", "selkies-modal-photocraft", str(wait_seconds), bufsize=1)
    try:
        process.stdin.write(requests)
        process.stdin.write_eof()
        process.stdin.drain()
    except modal.exception.Error:
        # The command ended before it read anything; its status and output say why
        pass
    return process


def photocraft_call(sandbox: modal.Sandbox, method: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    """Send one request on the session's PhotoCraft control channel and return its result.

    `method` and `params` are those of PhotoCraft's control protocol:
    `engine.execute` with `{"command", "params"}` runs any of its commands,
    `app.open` and `app.save` read and write files of the project folder, the
    one folder the channel may touch, and the `ui.*` methods read and drive its
    window. `timeout` is how many seconds to wait for PhotoCraft to listen,
    which it does a few seconds after its window opens, and then for the reply.
    PhotoCraft gives up on a reply itself after 60 s without undoing what it
    started, so a long filter or save is started with `"wait": false` and
    followed with `jobs.list`.

    The result is the reply's `result`, an object for most methods; a result
    that is not one, such as the list `engine.commands` returns, comes back as
    `{"result": ...}`.

    Raises:
        RuntimeError: PhotoCraft refused the request, with its message, or did not answer within `timeout`.
    """
    request = json.dumps({"id": 1, "method": method, "params": params or {}})
    process = photocraft_requests(sandbox, request + "\n", timeout)
    output = process.stdout.read()
    status = process.wait()
    if not output.strip():
        raise RuntimeError(f"PhotoCraft did not answer: {process.stderr.read().strip() or f'status {status}'}")
    reply = json.loads(output.splitlines()[-1])
    if not reply.get("ok"):
        raise RuntimeError(reply.get("error") or output.strip())
    result = reply.get("result")
    return result if isinstance(result, dict) else {"result": result}


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
        '"http://127.0.0.1:${SELKIES_PORT:-8080}${SELKIES_SUBFOLDER:+/$SELKIES_SUBFOLDER}/api/screenshot" | '
        # The comma is escaped for ffmpeg, which otherwise reads it as the end of the filter
        "ffmpeg -loglevel error -i pipe:0 -vf 'scale=min(1280\\,iw):-2' -q:v 4 -f mjpeg pipe:1 | base64 -w0",
    )
    picture = process.stdout.read()
    if process.wait() != 0 or not picture:
        raise RuntimeError(f"no screenshot: {process.stderr.read().strip()}")
    return base64.b64decode(picture)


def read_file(sandbox: modal.Sandbox, path: str, limit: int) -> bytes:
    """A file of the session, whole, for one small enough to hold: a preview on its way to the person.

    Raises:
        RuntimeError: The file could not be read, with what the session said.
        ValueError: The file is larger than `limit` bytes; nothing of it is returned.
    """
    # One byte past the limit is asked for, so a file over it is known without reading the rest
    process = sandbox.exec("head", "-c", str(limit + 1), "--", path, text=False)
    data = process.stdout.read()
    if process.wait() != 0:
        raise RuntimeError(f"could not read {path}: {process.stderr.read().decode(errors='replace').strip()}")
    if len(data) > limit:
        raise ValueError(f"{path} is larger than {limit} bytes")
    return data


# The bytes of a transfer in hand at once: what one write to a session's command carries (its buffer takes 16 MiB),
# large enough that the round trip each write waits on does not set the pace
SEND_PIECE = 8 * 1024 * 1024
# Says what is at $1:`folder`, a file's size in bytes, or status 44 for neither
MEASURE = 'if [ -d "$1" ]; then echo folder; elif [ -f "$1" ]; then stat -c %s "$1"; else exit 44; fi'
# Writes standard input at $1 under a name of its own, moved into place only once all $2 bytes arrived
RECEIVE_FILE = (
    'set -e; mkdir -p "$(dirname "$1")"; part="$1.part-$$"; trap \'rm -f "$part"\' EXIT; cat > "$part"; '
    'got="$(stat -c %s "$part")"; [ "$got" = "$2" ] || { echo "received $got of $2 bytes" >&2; exit 1; }; '
    'mv -f "$part" "$1"'
)
# Unpacks the tar stream on standard input into the folder $1
RECEIVE_FOLDER = 'set -e; mkdir -p "$1"; tar -C "$1" -xf -'
# Write the file, or the folder as a tar stream, at $1 to standard output, as a process whose ID is kept in $2
SEND_FILE = 'echo $$ > "$2"; exec cat -- "$1"'
SEND_FOLDER = 'echo $$ > "$2"; exec tar -C "$1" -cf - .'


def send_file(
    source: modal.Sandbox,
    path: str,
    target: modal.Sandbox,
    to_path: str,
    keep_going: Callable[[], bool] | None = None,
) -> int:
    """Copy a file or a folder of one running session to a path of another, and return the bytes carried.

    Two sessions that mount the same Volume do not see what the other writes
    while both run: each sees the Volume as it was when its Sandbox started,
    and Modal refuses to reload a Volume under an application that has files
    open on it (`Sandbox.reload_volumes`), which a session's application
    always has. So the bytes go through this side instead: a command of
    `source` writes the file to its standard output, and each piece is handed,
    as it arrives, to a command of `target` that writes it at `to_path`.
    Nothing is held here but the piece in hand, so a file of any size passes
    in the memory of one piece, and nothing touches a disk on the way.

    The receiving command writes under a name of its own beside `to_path` and
    moves the file into place only once every byte arrived, so an application
    watching the folder never opens half a file and a transfer cut short
    leaves nothing behind. A folder goes as a tar stream, unpacked over
    `to_path`. Both commands run as commands of their sessions
    (`selkies-modal-run`): the file is the session user's, and a long transfer
    counts as use of both sessions. What `target` receives is in its own mount
    of the Volume, so it is committed to the Volume from there as anything
    else that session writes is, beside the copy `source` wrote.

    `keep_going` is asked between pieces; once it says no, the transfer stops
    and nothing is left at `to_path`.

    Raises:
        FileNotFoundError: `source` has no file or folder at `path`.
        InterruptedError: `keep_going` said to stop.
        RuntimeError: Either session's command failed, with what it said.
    """
    run = "/usr/local/bin/selkies-modal-run"
    measure = source.exec(run, "sh", "-c", MEASURE, "sh", path)
    found = measure.stdout.read().strip()
    if measure.wait() != 0:
        raise FileNotFoundError(path)
    pid_file = f"/tmp/selkies-modal/send-{token_hex(8)}.pid"
    if found == "folder":
        reader = source.exec(run, "sh", "-c", SEND_FOLDER, "sh", path, pid_file, text=False)
        writer = target.exec(run, "sh", "-c", RECEIVE_FOLDER, "sh", to_path, text=False)
    else:
        reader = source.exec(run, "sh", "-c", SEND_FILE, "sh", path, pid_file, text=False)
        writer = target.exec(run, "sh", "-c", RECEIVE_FILE, "sh", to_path, found, text=False)
    carried = 0
    piece = bytearray()
    stopped = broken = False

    def hand_over() -> None:
        """Send the piece in hand and wait until the writer took it, so no more than a piece is ever held."""
        nonlocal carried
        writer.stdin.write(bytes(piece))
        writer.stdin.drain()
        carried += len(piece)
        piece.clear()

    try:
        for read in reader.stdout:
            piece += read
            if len(piece) < SEND_PIECE:
                continue
            if keep_going is not None and not keep_going():
                stopped = True
                break
            hand_over()
        if not stopped and piece:
            hand_over()
        writer.stdin.write_eof()
        writer.stdin.drain()
    except modal.exception.Error:
        # The writer ended before it took everything; its own words say why, below
        broken = True
    received = writer.wait()
    if stopped or broken:
        # The reader is blocked writing to a stream nobody reads now, and would count as use of its session forever
        source.exec("sh", "-c", 'kill "$(cat "$1")"; rm -f "$1"', "sh", pid_file).wait()
    else:
        source.exec("rm", "-f", pid_file).wait()
    if stopped:
        # A file short of its size was never moved into place; a folder's unpacked part is removed
        if found == "folder":
            target.exec(run, "rm", "-rf", "--", to_path).wait()
        raise InterruptedError(f"stopped after {carried} bytes")
    if received != 0 or broken:
        said = writer.stderr.read().decode(errors="replace").strip()
        raise RuntimeError(f"could not write {to_path}: {said or f'the transfer broke after {carried} bytes'}")
    if reader.wait() != 0:
        raise RuntimeError(f"could not read {path}: {reader.stderr.read().decode(errors='replace').strip()}")
    return carried


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


def soundcraft(args: argparse.Namespace) -> int:
    """Send the JSON requests on standard input, one per line, to the session's SoundCraft and print each reply."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    process = soundcraft_requests(sandbox, sys.stdin.read(), args.wait)
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
    status = process.wait()
    sys.stderr.write(process.stderr.read())
    return status


def cadcraft(args: argparse.Namespace) -> int:
    """Send the JSON requests on standard input, one per line, to the session's CADCraft and print each reply."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    process = cadcraft_requests(sandbox, sys.stdin.read(), args.wait)
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


def lightcraft(args: argparse.Namespace) -> int:
    """Send the JSON requests on standard input, one per line, to the session's LightCraft and print each reply."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    process = lightcraft_requests(sandbox, sys.stdin.read(), args.wait)
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
    status = process.wait()
    sys.stderr.write(process.stderr.read())
    return status


def photocraft(args: argparse.Namespace) -> int:
    """Send the JSON requests on standard input, one per line, to the session's PhotoCraft and print each reply."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    process = photocraft_requests(sandbox, sys.stdin.read(), args.wait)
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
    status = process.wait()
    sys.stderr.write(process.stderr.read())
    return status


def send(args: argparse.Namespace) -> int:
    """Copy a file or a folder of one running session to another (`send_file`), and say what it carried and how fast."""
    source, target = find_session(args.name), find_session(args.to)
    for name, found in ((args.name, source), (args.to, target)):
        if found is None:
            raise SystemExit(f"selkies-modal: no session named {name} is running")
    started = time.monotonic()
    try:
        carried = send_file(source, args.path, target, args.to_path or args.path)
    except FileNotFoundError:
        raise SystemExit(f"selkies-modal: {args.name} has no {args.path}") from None
    except RuntimeError as error:
        raise SystemExit(f"selkies-modal: {error}") from None
    seconds = time.monotonic() - started
    megabytes = carried / (1024 * 1024)
    say(f"{megabytes:.1f} MB in {seconds:.1f} s, {megabytes / max(seconds, 0.001):.1f} MB/s")
    return 0


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
    sound = named(
        command("soundcraft", soundcraft, "Send the JSON requests on standard input, one per line, to a session's SoundCraft.")
    )
    sound.add_argument(
        "--wait", type=int, default=60, help="seconds to wait for SoundCraft to listen and for each reply (default: %(default)s)"
    )
    drafting = named(
        command("cadcraft", cadcraft, "Send the JSON requests on standard input, one per line, to a session's CADCraft.")
    )
    drafting.add_argument(
        "--wait", type=int, default=60, help="seconds to wait for CADCraft to be ready and for each reply (default: %(default)s)"
    )
    vector = named(
        command("vectorcraft", vectorcraft, "Send the JSON requests on standard input to a session's VectorCraft control channel.")
    )
    vector.add_argument("--wait", type=int, default=60, help="seconds to wait for VectorCraft to answer (default: %(default)s)")
    develop = named(
        command("lightcraft", lightcraft, "Send the JSON requests on standard input, one per line, to a session's LightCraft.")
    )
    develop.add_argument(
        "--wait", type=int, default=60, help="seconds to wait for LightCraft to listen and for each reply (default: %(default)s)"
    )
    control = named(
        command("photocraft", photocraft, "Send the JSON requests on standard input, one per line, to a session's PhotoCraft.")
    )
    control.add_argument(
        "--wait", type=int, default=60, help="seconds to wait for PhotoCraft to be ready and for each reply (default: %(default)s)"
    )
    carry = named(command("send", send, "Copy a file or a folder of a running session to another running session."))
    carry.add_argument("--to", required=True, metavar="NAME", help="the session that receives it")
    carry.add_argument("path", help="the file or folder, as a path in the sending session")
    carry.add_argument("to_path", nargs="?", help="where it goes in the receiving session (default: the same path)")
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
