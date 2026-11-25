# Setting up Hermes to run the team's cloud studio

Hermes runs the studio itself: a teammate sends it a direct message on
Discord, and Hermes starts a GPU machine on Modal with Nuke (or Blender), runs
the work there, and answers in the same message thread. Everything it needs is
in this repository; `gpu-studio/SKILL.md` is the manual Hermes reads. Claude
Code is not part of the daily loop: come back to it to change or fix the
studio itself.

```
teammate ──DM──> Hermes (on its own machine, with its memory)
                   │  runs addons/modal/selkies-modal
                   v
                 Modal: GPU machines (Nuke, Blender) + the team's workspace
```

This file is for you, not for Hermes. `gpu-studio/SKILL.md` is the one Hermes
reads, and step 3 puts it where Hermes finds it. Set aside about twenty
minutes. Steps 1 to 4 are needed; step 5 only once you want Hermes to move
footage to and from Google Drive by itself.

Hermes can do steps 1 and 3 itself if you send it this message:

> Run `git clone https://github.com/larvuz2/GPU-stream ~/gpu-stream`, then copy
> the folder `~/gpu-stream/moody/hermes/gpu-studio` into your skills folder
> and reload your skills. Tell me when the gpu-studio skill is loaded.

The key in step 2 and the allow list in step 4 are yours to set, in Hermes's
own files rather than in a chat.

## 1. Give Hermes the code

On the machine Hermes runs on (it needs `git` and Python 3.10 or newer):

```bash
git clone https://github.com/larvuz2/GPU-stream ~/gpu-stream
```

The repository is public, so this needs no key. To update later:
`git -C ~/gpu-stream pull`.

## 2. Give Hermes the Modal key

1. Open https://modal.com/settings/tokens and create a new token. Name it
   `hermes`. Modal shows two values, an ID (`ak-...`) and a secret (`as-...`),
   once.
2. Add them to Hermes's environment file, `~/.hermes/.env`, where Hermes keeps
   its other keys:

   ```bash
   MODAL_TOKEN_ID=ak-...
   MODAL_TOKEN_SECRET=as-...
   ```

3. Restart Hermes's gateway so it reads them, then check from Hermes's machine
   (with the same two variables exported in your shell):

   ```bash
   ~/gpu-stream/addons/modal/selkies-modal ls
   ```

   The first run installs Modal's client for itself (a minute); an empty list
   with no error means the key works. Revoke the token on the same page
   whenever you want to cut Hermes off.

## 3. Give Hermes the manual

Copy the skill into Hermes's skills folder (usually `~/.hermes/skills/`) and
reload it:

```bash
mkdir -p ~/.hermes/skills
cp -r ~/gpu-stream/moody/hermes/gpu-studio ~/.hermes/skills/
```

## 4. Let only the team in

Whoever can message Hermes can start paid GPU machines and open the team's
files, and a machine's link opens the machine to whoever holds it. In Hermes's
Discord settings, allow only your teammates' Discord user IDs to message it
(Hermes's allow list for Discord, in `~/.hermes/.env`).

Then send Hermes a direct message: "Open Nuke for me." It should answer within
a minute or two with a link; opening the link shows Nuke in the browser.

## 5. Google Drive (when you want it)

Footage should not go through Discord, which caps files at 10 MB. Hermes moves
it between the team's Drive folder and the workspace from inside the GPU machine,
with rclone, signed in as one of you. There is no key file to make: you sign
in to Google once, in a window on a Nuke machine.

1. Send Hermes a direct message: "Connect Google Drive." Hermes starts a Nuke
   machine if you have none open, sends you its link, and opens Google's
   sign-in on it.
2. Open the link. In the taskbar at the bottom, click **Sign in - Google
   Accounts** (Nuke may have opened on top of it), then **Continue** on
   Firefox's welcome box.
3. Sign in with the Google account that can open the team's folder, "Nuke in
   Cloud - Final Twist", and allow **rclone** to see and edit your Drive
   files. The window closes by itself, and Hermes says the drive is
   connected.

Hermes keeps the access as the Modal Secret `gdrive` and starts machines with
it whenever footage has to move, inside that folder. The sign-in itself
reaches what that Google account reaches in Drive, so sign in with an account
that sees only the team's folders if you want it narrower. To cut it off, remove rclone at
https://myaccount.google.com/connections; to switch accounts, ask Hermes to
connect Google Drive again.

## What it costs

You pay Modal per second while a machine runs; it stops itself after 10
minutes unused. A Nuke machine on a T4 (4 cores, 16 GB) is about $1.54 an hour.
The team's Nuke install (15 GB) and work in the workspace cost $0.09 per GB a
month. The manual lists the bigger GPUs and their prices; Hermes is told to
ask before using one.
