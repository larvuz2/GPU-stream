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

This is Python because Modal's Python SDK is the interface the image
definition, the Sandbox, and the connect token are reached through.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from pathlib import Path

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

PORT = 8080
WORKSPACE = "/home/ubuntu/workspace"
TOKENS_FILE = "/tmp/selkies-modal/tokens.json"
ACTIVITY_FILE = "/tmp/selkies-modal/activity"

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
    "SELKIES_MODAL_WORKSPACE": WORKSPACE,
}


def say(message: str) -> None:
    """Print progress to stderr, which leaves stdout to what a command returns."""
    print(f"selkies-modal: {message}", file=sys.stderr, flush=True)


def session_image() -> modal.Image:
    """The base container with Blender, the idle counter's reader, and this integration's scripts.

    Modal builds every layer as root whatever user an image names, while the base
    keeps its package database the session user's, so that `sudo apt-get` works
    inside a session. The package layer therefore goes through
    `selkies-privileged-files run`, which runs it as that user under fakeroot
    the way an in-session install does. Blender is the release archive from
    blender.org, checked against the hash blender.org publishes for it.
    """
    series = BLENDER_VERSION.rsplit(".", 1)[0]
    archive = f"https://download.blender.org/release/Blender{series}/blender-{BLENDER_VERSION}-linux-x64.tar.xz"
    return (
        modal.Image.from_registry(BASE_IMAGE)
        .dockerfile_commands(
            "RUN selkies-privileged-files run sh -c '"
            "apt-get update && apt-get install --no-install-recommends -y xprintidle && "
            "apt-get clean && rm -rf /var/lib/apt/lists/*'",
            f"RUN curl -fsSL -o /tmp/blender.tar.xz {archive} && "
            f"echo '{BLENDER_SHA256}  /tmp/blender.tar.xz' | sha256sum -c - && "
            "mkdir -p /opt/blender && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 && "
            "rm -f /tmp/blender.tar.xz && ln -s /opt/blender/blender /usr/local/bin/blender",
        )
        .add_local_file(HERE / "session.sh", "/usr/local/bin/selkies-modal-session", copy=True)
        .add_local_file(HERE / "run.sh", "/usr/local/bin/selkies-modal-run", copy=True)
        .add_local_file(HERE / "blender" / "autostart", "/etc/xdg/openbox/autostart", copy=True)
        .env(SESSION_ENV)
        .entrypoint([])
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


def up(args: argparse.Namespace) -> int:
    """Start the session, or return the one already running under that name, and print its link."""
    sandbox = find_session(args.name)
    if sandbox is not None:
        say(f"{args.name} is already running as {sandbox.object_id}")
        print(session_link(sandbox))
        return 0

    app = modal.App.lookup(APP_NAME, create_if_missing=True)
    started = time.monotonic()
    image = session_image().build(app)
    say(f"image {image.object_id} ready after {time.monotonic() - started:.0f} s")

    env = dict(item.split("=", 1) for item in args.env)
    env["SELKIES_MODAL_IDLE_TIMEOUT"] = str(round(args.idle_minutes * 60))
    credentials = modal.Secret.from_dict(
        {
            "SELKIES_MASTER_TOKEN": secrets.token_urlsafe(32),
            "SELKIES_MODAL_SESSION_TOKEN": secrets.token_urlsafe(32),
        }
    )
    started = time.monotonic()
    sandbox = modal.Sandbox.create(
        "/usr/local/bin/selkies-modal-session",
        app=app,
        name=args.name,
        image=image,
        gpu=args.gpu,
        cpu=args.cpu,
        memory=args.memory,
        timeout=round(args.lifetime_hours * 3600),
        env=env,
        secrets=[credentials],
        volumes={WORKSPACE: modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)},
        tags={"session": args.name, "gpu": args.gpu},
        readiness_probe=modal.Probe.with_tcp(PORT),
    )
    say(f"{args.name} is {sandbox.object_id} on {args.gpu}; waiting for Selkies")
    sandbox.wait_until_ready(timeout=args.ready_timeout)
    say(
        f"Selkies listens after {time.monotonic() - started:.0f} s; the session ends after "
        f"{args.idle_minutes:g} min unused, or {args.lifetime_hours:g} h in all"
    )
    print(session_link(sandbox))
    return 0


def url(args: argparse.Namespace) -> int:
    """Print a new link to a running session."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    print(session_link(sandbox))
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


def down(args: argparse.Namespace) -> int:
    """Stop a session, which ends its billing; its workspace stays."""
    sandbox = find_session(args.name)
    if sandbox is None:
        say(f"no session named {args.name} is running")
        return 0
    sandbox.terminate(wait=True)
    say(f"{args.name} ({sandbox.object_id}) stopped")
    return 0


def build(_args: argparse.Namespace) -> int:
    """Build the image without starting a session, so the next `up` starts from Modal's cache."""
    app = modal.App.lookup(APP_NAME, create_if_missing=True)
    started = time.monotonic()
    image = session_image().build(app)
    say(f"image {image.object_id} ready after {time.monotonic() - started:.0f} s")
    return 0


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
    start.add_argument("--gpu", default="T4", help="a GPU type Modal offers, such as T4, L4, or A10 (default: %(default)s)")
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
        "--env",
        action="append",
        default=[],
        type=environment_assignment,
        metavar="NAME=value",
        help="a variable for the session, such as SELKIES_DESKTOP=true or SELKIES_ENCODER=av1enc; repeatable",
    )
    named(command("url", url, "Print a new link to a running session."))
    command("ls", ls, "List the running sessions.")
    execute = named(command("exec", run, "Run a command in a session's environment."))
    execute.add_argument("arguments", nargs=argparse.REMAINDER, metavar="-- command", help="the command and its arguments")
    named(command("down", down, "Stop a session."))
    command("build", build, "Build the image without starting a session.")
    return top


def main() -> int:
    """Parse the command line and run its subcommand."""
    args = parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
