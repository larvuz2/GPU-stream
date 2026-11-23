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

Set aside about twenty minutes. Steps 1 to 4 are needed; step 5 only once you
want Hermes to move footage to and from Google Drive by itself.

## 1. Give Hermes the code

On the machine Hermes runs on (it needs `git` and Python 3.10 or newer):

```bash
git clone --branch claude/peaceful-franklin-wol1mm https://github.com/larvuz2/GPU-stream ~/gpu-stream
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
cp -r ~/gpu-stream/lathe/hermes/gpu-studio ~/.hermes/skills/
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
it between your shared drive and the workspace from inside the GPU machine,
with rclone, as a Google service account (a robot user that belongs to your
Google Workspace):

1. In https://console.cloud.google.com, create a project, turn on the
   **Google Drive API**, then under IAM & Admin > Service Accounts create a
   service account, open it, and under Keys add a key of type JSON. A
   `.json` file downloads.
2. In Google Drive, open the shared drive that holds the team's folders
   ("Nuke in Cloud - Final Twist" lives in one), choose **Manage members**,
   and add the service account's email (`...@....iam.gserviceaccount.com`)
   as **Content manager**.
3. Store the key as a Modal Secret named `gdrive`, from any machine with the
   Modal key (the shared drive's ID is the part of its address after
   `/drive/folders/` when you open the shared drive itself):

   ```bash
   ~/gpu-stream/addons/modal/selkies-modal modal secret create gdrive \
     RCLONE_CONFIG_GDRIVE_TYPE=drive \
     RCLONE_CONFIG_GDRIVE_SCOPE=drive \
     RCLONE_CONFIG_GDRIVE_TEAM_DRIVE=0AEMU33wD9Aw9Uk9PVA \
     RCLONE_CONFIG_GDRIVE_SERVICE_ACCOUNT_CREDENTIALS="$(cat path/to/key.json)"
   ```

   Then delete the downloaded `.json` file.

From then on, Hermes starts machines with `--secret gdrive` and copies with
`rclone copy "gdrive:Nuke in Cloud - Final Twist/..." ...` (the manual has the
commands).

## What it costs

You pay Modal per second while a machine runs; it stops itself after 10
minutes unused. A Nuke machine on a T4 (4 cores, 16 GB) is about $1.54 an hour.
The team's Nuke install (15 GB) and work in the workspace cost $0.09 per GB a
month. The manual lists the bigger GPUs and their prices; Hermes is told to
ask before using one.
