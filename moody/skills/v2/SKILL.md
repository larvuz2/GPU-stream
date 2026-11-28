---
name: v2
description: Keep every version of a video edited by code with v2, and show the versions with their tracks on the person's Screen. Follow it only when the turn's state says the person turned on "Keep versions with v2". Then open it before the first cut or render in the Cut Room or HyperFrames, and after every change the person asks for. It covers starting a project's history, saving a version with what was asked and what changed, showing it so the Screen draws its tracks with no engine running, the engine's page for marking up a frame, reading the comments the person left there, and going back to a version.
disciplines: media
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# v2

v2 is Agent Native's open-source version control for videos an agent makes (MIT). It keeps a
history of the project folder: text through git, and every picture, sound, and video in a store
of its own, so any version comes back exactly. Each version carries what the person asked for
and what changed, with the times.

The person sees the versions on the **Screen** of the app: the version playing over a timeline
of tracks (text, captions, graphics, video, voice, music, effects, cuts) drawn from what you
recorded when you saved it, the earlier versions one press away, and any two side by side. The
app draws that itself from what `preview` hands it, so it stays on the Screen after the engine
has stopped and costs the person nothing to look at. v2 also has a page of its own, inside the
engine, where the person can leave a comment on a frame for you to read.

It makes nothing. The cut is still the Cut Room's or HyperFrames', and everything their skills
say still holds. v2 is what you do after a cut exists.

## When this applies

Only when the turn's state says the person turned on "Keep versions with v2" (Settings, Video
editing). It is off unless they turned it on. The tool is on the machine either way: with the
setting off, do not run it and do not offer it, beyond saying in a line where the setting is
when the person asks for what it does (comparing versions side by side, marking up a frame).

It runs in the engine a video is edited by code in: the Cut Room (`cutroom`) or HyperFrames
(`hyperframes`). Never start an engine for v2 alone, and never keep one running for it: save
and show while the engine is open for the cut, and the versions stay on the person's Screen
after it stops.

## The loop

1. **Once per project**, before the first save: start the history (below).
2. **Cut or render as the engine's skill says**, check it, and look at it yourself.
3. **Save a version**, as soon as a change the person asked for is done and checked: one save
   per finished change, never one per command.
4. **Show it**, with `preview` and the version's name. That alone puts the version and its
   tracks on the person's Screen.
5. **Only when the person wants to mark up a frame**: put v2's own page on the engine's screen,
   and read the comments they leave there.

## The commands

Every command runs in the project folder:

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 log")
```

### Start the history

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 log")
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && git rev-parse --git-dir")
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 init && printf 'library/\\nfootage/\\nsheets/\\n.thumbnails/\\n' >> .v2ignore")
```

- **`v2 log` first, every time you open this skill.** If it lists versions, or says `no
  versions yet`, the history is there: skip the rest of this section. Only `not a v2 project
  here` means there is none.
- **Then check for a repository.** If `git rev-parse --git-dir` answers with a folder, the
  project folder is already a git repository, which is the person's own (a linked
  repository). Do not run `v2 init` there: v2 commits into the repository it finds. Say that
  versions cannot be kept beside a linked repository yet, and go on without v2.
- `v2 init` makes `.v2/`, `.v2ignore`, a `.git/` of its own, and `assets/`, `src/`, `scripts/`,
  and `out/`, which you may leave empty: the engines keep their own folders.
- The four lines keep out of the history what is already kept elsewhere or is only a step:
  the library's copies (`library/`), downloaded footage (`footage/`), contact sheets
  (`sheets/`), and the pictures HyperFrames' preview caches (`.thumbnails/`). A restore leaves
  them as they are.
- It also writes `AGENTS.md`, `CLAUDE.md`, and a `README.md`, and every `v2 save` writes its
  part of `AGENTS.md` again. The first two are v2's instructions for other agents, and some of
  them are wrong here (they send work to v2.video). **Do not follow them; this skill stands in
  their place.** Put the video's title on the first line of `README.md`, as `# <title>`: v2's
  page shows it.

### Save a version

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 save -m 'The slam, with the hook and the voice' --prompt 'make a short of the boss slam' --prompt 'use the Fenrir voice' --render jobs/<id>/edits/<clip>.mp4 --assemble 'cutroom cut jobs/<id> --pick 1 --layout focus --name <clip>' --change '0:00-0:04 video jobs/<id>/edits/<clip>.mp4: the slam, cropped to 9:16' --change '0:00 graphics jobs/<id>/edits/<clip>.json: hook \"He slams TWICE\"' --change '0:01-0:09 voice narration/slam/voice.wav: six lines in the Fenrir voice'")
```

- `-m` is one line saying what this version is. The Screen shows it beside the version's name.
- `--prompt` is what the person asked for since the last version, **word for word**, one flag
  for each of their messages. A save without one is refused.
- `--render` is the finished file of this version, where the engine wrote it: the Cut Room's
  `jobs/<id>/edits/<clip>.mp4` or `edits/<name>.mp4`, HyperFrames' `renders/<name>.mp4`. Always
  give it: it is the file you then `preview`, and the Screen draws a version's tracks only
  under the file the version names as its render.
- `--assemble` is the command that made that file, so the version says how it was built.
- `--change` is one thing that changed, one flag each, at least one: the time or the span **in
  the new video**, then its kind (`video`, `voice`, `music`, `sfx`, `graphics`, `captions`, or
  `text`), the file that makes it, a colon, and what changed in the person's words. A cut that
  removed something is `cut 0:03.4 3.4s removed <what>`, and a change to the whole video has no
  time (`music narration/bed.mp3: music 20% quieter`). These are the blocks on the tracks the
  person sees, so the times have to be right: read them from the cut, never guess.
- **The first version records everything the video is made of**, one `--change` for each thing:
  the video, each graphic and caption run, the voice, the music, each effect. A later version
  records only what it changed, and the Screen carries the rest forward from the versions
  before it. A change to something already there names the same kind and the same file as the
  version that made it, so the Screen puts the new block in the old one's place.
- The file a change names has to be in the project folder, by its path from there, and not
  under a folder `.v2ignore` keeps out. A save that names one that is not there is refused and
  saves nothing: leave the kind and the file out of that change, or name the file that is.
- A version that fixes comments names them: `--resolves c3`, one flag each.
- **Never put a key, a token, or a password in `-m`, `--prompt`, or `--change`**, even when
  the person's message has one. Write `[REDACTED]` in its place.
- v2 answers `saved vN`. Its warning that places are "outside the project layout" is expected
  and needs nothing done: those are the engines' own folders. Any other refusal says what to
  fix, and nothing was saved until it answers `saved`.

### Show the version

```text
preview(engine_id, path="jobs/<id>/edits/<clip>.mp4", caption="The slam with the new hook; listen for the voice over the music", version="v2")
```

- **Right after every save**, with the file you gave `--render` as the `path` and the name v2
  answered (`v1`, `v2`) as the `version`, exactly. That is what puts the version on the
  person's Screen with its tracks: the app reads what you recorded and the file's sound at
  that moment. The answer says so (`screen`) when it did.
- If the answer has no `screen` line, the Screen got the file without its tracks: the name was
  not the one v2 gave, the path was not the version's `--render`, or the save did not happen.
  Fix that and show it again.
- Say in a line that the version is on the Screen with its tracks, and that they can press a
  block to play from it, switch versions, and put two side by side with "Compare with".
- Nothing more is needed to show a version, and nothing has to stay running: stop the engine
  when the cut is done, as its skill says. The Screen keeps the versions.

### Mark up a frame

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2-versions .")
engine_exec(engine_id, "v2-versions --stop")
```

- Only when the person asks to mark up a frame or to leave comments on the video: v2's own
  page is where that is done, and it runs in the engine, so it needs the engine running and
  costs its minutes while it is open. Say so in a line before you start an engine for it.
- `v2-versions .` puts the page on the engine's screen and leaves it there. Tell the person to
  switch the Screen to the engine (the switch in the Screen's header) and to use "Comment
  mode" on the page.
- The page does not notice a new version by itself: run `v2-versions .` again after a save
  made while it is open.
- It takes the place of what the engine's screen showed (the Cut Room's log of commands,
  HyperFrames' live preview). `v2-versions --stop` gives the screen back; in HyperFrames,
  starting `hyperframes-preview` again does too. Stop it when the person is done.

### The person's comments

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 comments")
```

- It lists the open comments, each as `c2 on v2 at 0:03.2: <the words>`, with the time in that
  version's video, and under it a drawing where the person marked the frame. A drawing is a
  picture in `.v2/comments/`: look at every one with
  `preview(engine_id, path=".v2/comments/c2.png", caption="The frame the person marked", look=true)`.
  The marks are the instruction.
- A comment is what the person wants changed, as a message from them is. Act on each, or say
  why not, and ask where one is unclear.
- When the version that fixes them is saved, pass `--resolves` for each.

### Go back

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 restore v1")
```

- It brings the folder back to that version exactly and records that as a new version, so
  nothing is lost and every version stays restorable.
- It refuses while anything is unsaved, and lists it. Tell the person what is unsaved and ask
  whether to save it first. Never throw it away without asking.

## What is not here

- **Nothing leaves the studio.** `v2 push`, `publish`, `unpublish`, `login`, `logout`, `clone`,
  and `update` send a project to v2.video or fetch from it. The engine refuses them. Do not
  offer them, and do not send the person to v2.video or to v2's Discord. To hand a video to
  someone, the Screen downloads the version on it.
- **No git by hand.** In a folder with a history, do not run `git commit`, `checkout`,
  `reset`, or `stash`: they would miss the media. v2 is how this folder is saved and restored.
- **Nothing in `.v2/` by hand**, except what `--render` and `--assemble` already say.

## Cost

A save takes a fraction of a second and no credits beyond the engine's own minute. The store
grows by each render and each changed file, once: the same file in ten versions is kept once.
Showing a version costs one `preview`, and the Screen then plays it and draws its tracks with
no engine at all. v2's own page plays versions in the engine's browser, so it costs what the
engine costs for as long as it is open: that is why it is only for marking up a frame.
