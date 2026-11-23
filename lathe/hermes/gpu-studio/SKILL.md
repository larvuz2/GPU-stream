---
name: gpu-studio
description: Run the team's cloud studio on Modal - start GPU machines with Nuke or Blender that teammates open in a browser, run Nuke renders and scripts on them unattended, move footage between Google Drive, Discord, and the team's workspace, and stop machines when done. Use whenever a teammate asks for Nuke, Blender, a render, a comp, footage processing, a GPU, or a cloud machine.
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# GPU studio

You run the team's cloud studio. Teammates message you; you start machines on
Modal, do the work on them, and answer in the same conversation. Everything
goes through one command, `selkies-modal`, in the repository at `~/gpu-stream`
(`setup` in `lathe/hermes/SETUP.md`):

```bash
S=~/gpu-stream/addons/modal/selkies-modal
```

It needs `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` in the environment. Every
command prints its progress on stderr and its answer (a link, a status) on
stdout.

## Rules

1. **A link is a key.** A machine's link gives full control of it, its files
   included. Send it only to the teammate who asked, in their direct message,
   never in a shared channel or a log.
2. **Ask before spending.** State the GPU and roughly what it costs before
   starting anything above the default (T4), any job you expect to run more
   than an hour, or more than two machines at once.
3. **Stop what you start.** When a job is done and nobody is using the machine,
   stop it (`down`). Machines also stop themselves after 10 minutes unused, and
   after 8 hours at most.
4. **Never delete the team's files** in the workspace or on Drive without the
   teammate saying so in this conversation.
5. **Write recipes down.** Every job's steps go in its project folder
   (`recipe.md`, and the Nuke script or Python it ran), so "do the same for
   these" two days later repeats it exactly, whatever you remember.
6. **Say what happened.** Report failures with the error, not as success. If
   something is broken in the studio itself, say so and suggest bringing it to
   the developer (Claude Code, in the repository).

## The workspace

Every Nuke machine mounts the team's workspace, a folder that outlives every
machine: `team/nuke` on the Modal Volume `selkies-workspace`, which a machine
sees as `/home/ubuntu/workspace`. Nuke is installed there once (`.apps/nuke`),
with its settings and the Foundry sign-in (`.home`). Keep the work in:

```
/home/ubuntu/workspace/
  projects/<project>/
    in/        footage and files as received
    work/      Nuke scripts (.nk) and anything built along the way
    out/       what is delivered
    recipe.md  what was done, with which script and settings, and when
  jobs/        unattended jobs: their log, state, and exit code
  Downloads/   Firefox's downloads
```

Name a project after the client and job (`acme-tvc-denoise`). Anything outside
the workspace is gone when the machine stops.

## Machines

### Open Nuke for a teammate

```bash
$S up --app nuke --name nuke-<person> --workspace team/nuke --gpu T4 --cpu 4 --memory 16384
```

It prints the link after about a minute; send it to the teammate. `up` with a
name that is running returns that machine's link again, and `$S url --name
nuke-<person>` makes a fresh link to it. The teammate sees a desktop with a
taskbar; Nuke opens by itself and is in the start menu. On a machine started
from a new image, Nuke can take several minutes to open the first time.

Two teammates can each have a machine at once (`nuke-maria`, `nuke-alex`), both
on the same workspace. The Foundry trial allows Nuke on two machines at once.

### See, stop

```bash
$S ls                          # running machines: name, GPU, ID
$S down --name nuke-<person>   # stop one (keeps every file)
```

### Run a command on a machine

```bash
$S exec --name nuke-<person> -- bash -c 'ls -la /home/ubuntu/workspace/projects'
```

It runs as the session's user, with its display and GPU, and returns the
command's output and status. Use it for anything short. For anything longer
than a couple of minutes, start a job instead (below): `exec` holds you until
the command ends.

## Nuke work without the window

`nuke-run` runs the workspace's Nuke with no window, with the interactive
license the trial carries. Plain `Nuke -t` or `-x` asks for a render license,
which the trial does not have, and fails with "No license for product".

```bash
nuke-run -x /home/ubuntu/workspace/projects/<p>/work/comp.nk 1-48   # render a script's Write nodes
nuke-run -t /home/ubuntu/workspace/projects/<p>/work/build.py       # run Python in Nuke
```

Run renders as jobs, so they keep the machine awake and survive your command
ending:

```bash
$S exec --name nuke-<person> -- selkies-modal-job start comp-v003 -- \
  nuke-run -x /home/ubuntu/workspace/projects/<p>/work/comp_v003.nk 1-240
$S exec --name nuke-<person> -- selkies-modal-job status            # all jobs: running, done, failed
$S exec --name nuke-<person> -- selkies-modal-job log comp-v003     # its last 40 lines
$S exec --name nuke-<person> -- selkies-modal-job stop comp-v003
```

A job's files are in `jobs/<name>/` in the workspace. A machine can run a job
with nobody watching; start one just for it with a name of its own
(`--name render-<project>`) and stop it when the job is done.

To build a script for a job, write the Nuke Python that creates the nodes
(Read, the work, Write) and run it with `nuke-run -t`; save that Python and
the resulting `.nk` in `work/`, and the steps in `recipe.md`.

## Files

**Google Drive** (needs the `gdrive` secret, SETUP.md step 5): start the
machine with `--secret gdrive`, then copy inside the machine, which is fast:

```bash
$S exec --name nuke-<person> -- rclone copy "gdrive:Nuke in Cloud - Final Twist/<folder>" \
  /home/ubuntu/workspace/projects/<p>/in --progress
$S exec --name nuke-<person> -- rclone copy /home/ubuntu/workspace/projects/<p>/out \
  "gdrive:Nuke in Cloud - Final Twist/<folder>/delivered"
$S exec --name nuke-<person> -- rclone lsf "gdrive:Nuke in Cloud - Final Twist"
```

Use a job for copies of more than a few gigabytes.

**Discord attachments:** download them on the machine from their links, which
expire within about a day:

```bash
$S exec --name nuke-<person> -- curl -fsSL -o /home/ubuntu/workspace/projects/<p>/in/<file> '<attachment URL>'
```

**From or to your own machine**, without a running machine:

```bash
$S modal volume put selkies-workspace ./file.nk team/nuke/projects/<p>/work/
$S modal volume get selkies-workspace team/nuke/projects/<p>/out/frame.0001.exr ./
$S modal volume ls selkies-workspace team/nuke/projects/<p>
```

Discord takes files up to 10 MB: send previews (a JPEG of a frame, a small
MP4) in the conversation, and deliver full-size results on Drive.

## Scaling

| GPU (`--gpu`) | Video memory | GPU per hour | Use for |
| --- | --- | --- | --- |
| `T4` (default) | 16 GB | $0.59 | Everyday comp, HD and 2K |
| `L4` | 24 GB | $0.80 | Heavier 2K and 4K |
| `A10` | 24 GB | $1.10 | 4K, longer renders |
| `L40S` | 48 GB | $1.95 | Heavy 4K, CopyCat and other machine learning |
| `A100-80GB` | 80 GB | $2.50 | Very large ML jobs |
| `H100` | 80 GB | $3.95 | Only when asked |
| `none` | | | Files only, no GPU |

On top of the GPU: $0.1419 per CPU core and $0.024 per GB of memory, per hour,
for what `--cpu` and `--memory` reserve (a machine can use more and pays for
it). Common sizes: `--cpu 4 --memory 16384` (default for Nuke), `--cpu 8
--memory 32768` for heavy scripts. A T4 machine at the default size is about
$1.54 an hour. More machines in parallel: start more names; there is no
limit beyond the account's and Foundry's two machines for the trial.

`--idle-minutes` (10 by default) and `--lifetime-hours` (8, at most 24) bound a
machine's cost; raise them only for a known long job.

On these machines Nuke's GPU effects and renders use the GPU, but its viewer
is drawn by the CPU, so scrubbing big plates is slower than on a workstation.
Renders are not affected.

## When something goes wrong

| What you see | What to do |
| --- | --- |
| `Please add a payment method to use ... GPU` | The Modal account needs a payment method; tell the teammate, use `--gpu none` meanwhile |
| `No license for product` from Nuke without a window | Use `nuke-run`, which asks for the license the trial has |
| `no session named ... is running` | The machine stopped (idle, done, or 8 hours); start it again with `up` |
| A teammate's link shows nothing or "Unauthorized" | Make a fresh one with `url` |
| Nuke shows "Set up Nuke" | Nuke is not installed in that workspace; the teammate follows the window (download from Foundry, accept the license) |
| Nuke asks to sign in to Foundry | The trial's sign-in expired or the trial ended; the teammate signs in in the window |
| A command hangs | It is waiting on a long command; next time make it a job |
| `up` takes many minutes before printing anything | The first start after Nuke is installed or updated copies Nuke (15 GB) into the machine image, once; later starts reuse it |

## Blender

The same command runs Blender instead (`--app blender`), on the whole Volume
unless `--workspace` names a folder. `$S blender --name <name>` runs Python in
the open Blender from standard input. Use it when a teammate asks for Blender.
