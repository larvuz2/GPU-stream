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
import base64
import json
import re
import secrets
import sys
import time
from pathlib import Path, PurePosixPath

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
PID_FILE = "/tmp/selkies-modal/pid"
BLENDER_SPOOL = "/tmp/selkies-modal/blender"
SHARE = "/usr/local/share/selkies-modal"

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
}
APPS = tuple(APP_ENV)


def say(message: str) -> None:
    """Print progress to stderr, which leaves stdout to what a command returns."""
    print(f"selkies-modal: {message}", file=sys.stderr, flush=True)


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
    """
    if app == "nuke":
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
        series = BLENDER_VERSION.rsplit(".", 1)[0]
        archive = f"https://download.blender.org/release/Blender{series}/blender-{BLENDER_VERSION}-linux-x64.tar.xz"
        image = (
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
            .add_local_file(HERE / "blender" / "autostart", "/etc/xdg/openbox/autostart", copy=True)
            .add_local_file(HERE / "blender" / "session.py", f"{SHARE}/blender-session.py", copy=True)
            .add_local_file(HERE / "blender" / "run-python.sh", "/usr/local/bin/selkies-modal-blender", copy=True)
        )
    return (
        image.add_local_file(HERE / "session.sh", "/usr/local/bin/selkies-modal-session", copy=True)
        .add_local_file(HERE / "run.sh", "/usr/local/bin/selkies-modal-run", copy=True)
        .add_local_file(HERE / "job.sh", "/usr/local/bin/selkies-modal-job", copy=True)
        .env({**SESSION_ENV, **APP_ENV[app]})
        .entrypoint([])
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
) -> modal.Sandbox:
    """Start a session's Sandbox and return it at once, before Selkies listens.

    The session's two tokens are made here and reach the Sandbox as a Modal
    Secret; nothing else holds them. `workspace` mounts one directory of the
    Volume in place of all of it, which is what keeps one user's files out of
    another's session where a service starts sessions for many. `cpu` takes a
    request, or a request and a limit, as Modal bills whichever of the request
    and the use is higher. `image` is the session image where the caller holds
    one already built, which a service does so that no request waits on a build;
    otherwise it is `application`'s. `extra_secrets` names Modal Secrets whose
    variables the session gets too, such as the Google Drive access rclone
    reads (`RCLONE_CONFIG_...`).

    Raises:
        modal.exception.AlreadyExistsError: A session of that name is running.
    """
    volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
    if workspace is not None:
        volume = volume.with_mount_options(sub_path=workspace)
    credentials = modal.Secret.from_dict(
        {
            "SELKIES_MASTER_TOKEN": secrets.token_urlsafe(32),
            "SELKIES_MODAL_SESSION_TOKEN": secrets.token_urlsafe(32),
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
        secrets=[credentials, *(modal.Secret.from_name(name) for name in extra_secrets)],
        volumes={WORKSPACE: volume},
        tags=tags or {},
        readiness_probe=modal.Probe.with_tcp(PORT),
    )


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
    )
    where = "without a GPU" if args.gpu == "none" else f"on {args.gpu}"
    say(f"{args.name} is {sandbox.object_id} {where}; waiting for Selkies")
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


def blender(args: argparse.Namespace) -> int:
    """Run the Python on standard input inside the session's Blender and print what it printed."""
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    status, output = blender_python(sandbox, sys.stdin.read(), args.wait)
    sys.stdout.write(output)
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
    environment (`RCLONE_CONFIG_GDRIVE_...`), on the shared drive
    `--shared-drive` names or the account's own drive, so a session started
    with `--secret` copies to and from it with no setup. The access is tried
    from the session before it is kept, and the top of the drive is printed: a
    sign-in that reaches nothing replaces no Secret that worked.
    """
    sandbox = find_session(args.name)
    if sandbox is None:
        raise SystemExit(f"selkies-modal: no session named {args.name} is running")
    values = {
        "RCLONE_CONFIG_GDRIVE_TYPE": "drive",
        "RCLONE_CONFIG_GDRIVE_SCOPE": "drive",
        "RCLONE_CONFIG_GDRIVE_TEAM_DRIVE": args.shared_drive,
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
        default="",
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
    script = named(command("blender", blender, "Run the Python on standard input inside a session's Blender."))
    script.add_argument("--wait", type=int, default=120, help="seconds to wait for Blender to answer (default: %(default)s)")
    named(command("down", down, "Stop a session."))
    drive = named(
        command("drive-login", drive_login, "Connect Google Drive by a sign-in in a session's Firefox, kept as a Modal Secret.")
    )
    drive.add_argument("--shared-drive", default="", metavar="ID", help="the shared drive to reach (default: the account's own drive)")
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
