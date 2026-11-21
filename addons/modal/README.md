# Selkies on Modal

Run Blender on a cloud GPU and work in it from a browser: a
[Modal](https://modal.com) Sandbox runs the Selkies
[base container](../../docs/components/base-image.md) with Blender layered on
it, and one command hands back the link.

```bash
addons/modal/selkies-modal up
```

```text
selkies-modal: image im-... ready after 1 s
selkies-modal: blender is sb-... on T4; waiting for Selkies
selkies-modal: Selkies listens after 4 s; the session ends after 10 min unused, or 8 h in all
https://....w.modal.host/?_modal_connect_token=...#token=...
```

The first `up` or `build` builds the image, which takes a few minutes; Modal
keeps it, and a session then starts in seconds.

`selkies-modal` installs the Modal client it is written against into a virtual
environment of its own the first time it runs, so it needs only Python 3. The
client finds its token the way it does anywhere: `MODAL_TOKEN_ID` and
`MODAL_TOKEN_SECRET`, or the file `addons/modal/selkies-modal modal token new`
writes after you approve it in a browser.

| Command | What it does |
| --- | --- |
| `up` | Starts the session, or returns the one already running under that name, and prints its link |
| `url` | Prints a new link to a running session |
| `exec -- <command>` | Runs a command in the session's environment: on its display, with its GPU |
| `ls` | Lists the running sessions |
| `down` | Stops a session |
| `build` | Builds the image without starting a session |

Every command but `ls` and `build` takes `--name` (`blender` unless given), so
several sessions run side by side under names of their own.

## The link

The link carries two credentials, and a session takes both:

- `_modal_connect_token`, in the query, is Modal's: its proxy admits no request
  to the Sandbox without it, and answers the first one with a cookie that
  carries the page's later requests and its WebSocket.
- `#token=`, in the fragment, is the Selkies session token of
  [secure mode](../../docs/secure-mode.md). A browser sends a fragment to no
  server, and the client presents the token on the stream's socket.

Whoever holds the link controls the session, so share it as you would a
password. Neither token is stored outside the Sandbox: `url` asks Modal for a
new connect token and reads the session token back out of the Sandbox, which
takes the Modal credentials that started it.

## What a session costs

Modal bills a Sandbox by the second for as long as it runs, so the session
stops itself rather than wait to be stopped:

- **Unused for ten minutes** (`--idle-minutes`), it ends. Use is keyboard or
  pointer input from any page, or a command run through `exec`, for as long as
  that command runs. An open tab nobody touches is not use, and neither is a
  link nobody opened. `--idle-minutes 0` turns this off, for a render left to
  run with the page closed.
- **After eight hours** (`--lifetime-hours`, 24 at most) it ends whatever it is
  doing.
- **`up` twice** returns the session that is running instead of starting a
  second.

`--gpu` picks the GPU (`T4` unless given; `L4` and `A10` are the next steps
up, and any type Modal lists works). Modal starts a GPU only for an account
with a payment method. `--gpu none` runs the session without one, rendering
and encoding in software. `--cpu` and `--memory` are what the session
reserves, 2 cores and 4096 MiB unless given, and it uses more as Blender needs
it.

## Files

`/home/ubuntu/workspace` is the Modal Volume `selkies-workspace`, which
outlives every Sandbox: Blender starts in it, and what is saved there is there
in the next session. The rest of the filesystem is the image's and is gone when
the session ends.

## The session

The image is the base container by digest with three additions: Blender's
release archive from blender.org, checked against the hash blender.org
publishes, `xprintidle` to read the display's idle counter, and this
directory's scripts. `BASE_IMAGE`, `BLENDER_VERSION`, and `BLENDER_SHA256` at
the top of `sandbox.py` choose what it is built from, and a change to any of
them builds a new image on the next `up` or `build`.

The Selkies window manager runs Blender as the session's application,
maximized, and starts it again if it is quit. Every other
[setting](../../docs/settings.md) is the server's own and passes through
`--env`:

```bash
addons/modal/selkies-modal up --gpu L4 --env SELKIES_DESKTOP=true --env SELKIES_ENCODER=av1enc
```

`SELKIES_DESKTOP=true` starts the session on the desktop shell, with Blender in
a window of it. The transport is WebSockets, the one Modal's proxy carries;
WebRTC needs a UDP path that proxy does not offer, so it is not offered here.
