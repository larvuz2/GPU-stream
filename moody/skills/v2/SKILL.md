---
name: v2
description: Keep every version of a video edited by code with v2, and show the versions on the engine's Screen. Follow it only when the turn's state says the person turned on "Keep versions with v2". Then open it before the first cut or render in the Cut Room or HyperFrames, and after every change the person asks for. It covers starting a project's history, saving a version with what was asked and what changed, the page of versions on the Screen (watch one, compare two, mark up a frame), reading the comments the person left there, and going back to a version.
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
and what changed, with the times. Its page shows every version to watch, to compare with an
earlier one side by side, and to mark up with comments on a frame, which you can then read.

It makes nothing. The cut is still the Cut Room's or HyperFrames', and everything their skills
say still holds. v2 is what you do after a cut exists.

## When this applies

Only when the turn's state says the person turned on "Keep versions with v2" (Settings, Video
editing). It is off unless they turned it on. The tool is on the machine either way: with the
setting off, do not run it and do not offer it, beyond saying in a line where the setting is
when the person asks for what it does (comparing versions side by side, marking up a frame).

It runs in the engine a video is edited by code in: the Cut Room (`cutroom`) or HyperFrames
(`hyperframes`). Never start an engine for v2 alone. Saving happens while the engine is open
for the cut; the page is for while the person is looking at the Screen.

## The loop

1. **Once per project**, before the first save: start the history (below).
2. **Cut or render as the engine's skill says**, check it, and look at it yourself.
3. **Save a version**, as soon as a change the person asked for is done and checked: one save
   per finished change, never one per command.
4. **Show it twice.** `preview` with a `version`, as always, which is what the conversation and
   the Latest panel play with no engine running. And the versions page on the Screen, which is
   where two versions are compared and a frame is marked up.
5. **When the person says they left comments**, or asks for the next version: read them, act on
   each, and name the ones a version fixes when you save it.

## The commands

Every command runs in the project folder:

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 log")
```

### Start the history

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 log")
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && git rev-parse --git-dir")
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 init && printf 'library/\\nfootage/\\nsheets/\\n' >> .v2ignore")
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
- The three lines keep out of the history what is already kept elsewhere or is only a step:
  the library's copies (`library/`), downloaded footage (`footage/`), and contact sheets
  (`sheets/`). A restore leaves them as they are.
- It also writes `AGENTS.md`, `CLAUDE.md`, and a `README.md`. The first two are v2's
  instructions for other agents, and some of them are wrong here (they send work to v2.video).
  **Do not follow them; this skill stands in their place.** Put the video's title on the first
  line of `README.md`, as `# <title>`: the page shows it.

### Save a version

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2 save -m 'The slam, with the hook and the voice' --prompt 'make a short of the boss slam' --prompt 'use the Fenrir voice' --render jobs/<id>/edits/<clip>.mp4 --assemble 'cutroom cut jobs/<id> --pick 1 --layout focus --name <clip>' --change '0:00-0:04 video jobs/<id>/edits/<clip>.mp4: the slam, cropped to 9:16' --change '0:00 graphics jobs/<id>/edits/<clip>.json: hook \"He slams TWICE\"' --change '0:01-0:09 voice narration/slam/voice.wav: six lines in the Fenrir voice'")
```

- `-m` is one line saying what this version is. The page shows it as the version's name.
- `--prompt` is what the person asked for since the last version, **word for word**, one flag
  for each of their messages. A save without one is refused.
- `--render` is the finished file of this version, where the engine wrote it: the Cut Room's
  `jobs/<id>/edits/<clip>.mp4` or `edits/<name>.mp4`, HyperFrames' `renders/<name>.mp4`. It is
  what the page plays.
- `--assemble` is the command that made that file, so the version says how it was built.
- `--change` is one thing that changed, one flag each, at least one: the time or the span **in
  the new video**, then its kind (`video`, `voice`, `music`, `sfx`, `graphics`, `captions`, or
  `text`), the file that makes it, a colon, and what changed in the person's words. A cut that
  removed something is `cut 0:03.4 3.4s removed <what>`, and a change to the whole video has no
  time (`music narration/bed.mp3: music 20% quieter`). These are the marks on the page's
  timeline, so the times have to be right: read them from the cut, never guess.
- The file a change names has to be in the project folder, by its path from there, and not
  under a folder `.v2ignore` keeps out. A save that names one that is not there is refused and
  saves nothing: leave the kind and the file out of that change, or name the file that is.
- A version that fixes comments names them: `--resolves c3`, one flag each.
- **Never put a key, a token, or a password in `-m`, `--prompt`, or `--change`**, even when
  the person's message has one. Write `[REDACTED]` in its place.
- v2 answers `saved vN`. Its warning that places are "outside the project layout" is expected
  and needs nothing done: those are the engines' own folders. Any other refusal says what to
  fix, and nothing was saved until it answers `saved`.

### Show the versions

```text
preview(engine_id, path="jobs/<id>/edits/<clip>.mp4", caption="The slam with the new hook; listen for the voice over the music", version="v2")
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && v2-versions .")
engine_exec(engine_id, "v2-versions --stop")
```

- Give `preview` the same name v2 gave the version (`v1`, `v2`), so the conversation, the
  Latest panel, and the page say the same thing.
- `v2-versions .` puts the page on the engine's Screen and leaves it there. Say in a line that
  the Screen now shows every version, and that they can compare two with "Compare with…" and
  leave a comment on a frame in "Comment mode".
- It takes the place of what the Screen showed (the Cut Room's log of commands, HyperFrames'
  live preview). `v2-versions --stop` gives the Screen back; in HyperFrames, starting
  `hyperframes-preview` again does too.
- The page needs the engine running. Do not keep an engine open only to show it: before you
  stop the engine, say that the versions are kept and that the Latest panel still plays them.

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
  someone, the Latest panel downloads it.
- **No git by hand.** In a folder with a history, do not run `git commit`, `checkout`,
  `reset`, or `stash`: they would miss the media. v2 is how this folder is saved and restored.
- **Nothing in `.v2/` by hand**, except what `--render` and `--assemble` already say.

## Cost

A save takes a fraction of a second and no credits beyond the engine's own minute. The store
grows by each render and each changed file, once: the same file in ten versions is kept once.
The page plays versions in the engine's browser, so it costs what the engine costs while it
is open and nothing more.
