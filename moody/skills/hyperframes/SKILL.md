---
name: hyperframes
description: Make video in HyperFrames, an engine with no application to click, in which a video is written as HTML, CSS, and animation and rendered frame by frame to MP4. Start a project, bring in the library's footage, sound, and pictures, write the composition, check it, show its live preview on the engine's Screen, and render it, all with commands. Use it whenever a turn's state says a video edited by code is made in HyperFrames, which is the person's setting, and for titles, captions, charts, and motion design composed in code.
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# HyperFrames

HyperFrames is HeyGen's open-source video framework (Apache 2.0): a video is a web page whose
elements carry their times, a browser is stepped through its frames, and FFmpeg encodes them.
The engine is a machine with its command line, `hyperframes`, and nothing to click. You write
files and run commands with `engine_exec`; the person watches the composition play in a live
preview on the engine's Screen.

This skill is short on purpose. **How to write a good composition is upstream's own
knowledge, and it is on the machine**, in the skills that ship with the release the engine
runs. They change with every release, so they are not copied here: read them there, each time,
before you write.

## When this applies

The turn's state names HyperFrames (`hyperframes`) as where a video edited by code is made.
That is the person's setting (Settings, Video editing), off unless they turned it on, so do
not ask them to choose between this engine and the Cut Room. Which kind of video, its hook,
its script, and the words of the post are the `video` skill's; this skill is how the video is
built once those are decided.

HyperFrames composes: type, captions, charts, diagrams, and motion, with footage as one of its
layers. Finding the moments in a long recording is not what it does; where that is the job,
say so in a line, name the setting, and do what was asked with this engine.

## The loop

1. **Read upstream's skill for the job** on the machine (below), before the first line of HTML.
2. **Propose** the piece in the person's words: its beats, its look, its length. Ask only what
   is theirs, with `ask_user(question, options, recommended)`.
3. **Write, lint, check, look.** Write the composition, `lint` it, run `check`, and look at
   `snapshot` frames yourself with `preview` and `look: true`.
4. **Put the live preview on the Screen** and tell the person to press play.
5. **Render** when they have seen it, read the file's facts back, and show it with `preview`
   and a `version`.

Checkpoints, always asked first: starting the engine (the page asks), any generated voice,
music, or picture and its cost, replacing a version the person approved, and anything that
leaves the studio.

## The engine

```text
engine_start("hyperframes", "cpu")
engine_exec(engine_id, "hyperframes-release status")
```

The `cpu` tier renders in software and is the one that was measured. The engine follows
upstream: as it starts it takes the newest release of HyperFrames and that release's skills,
and falls back on the release its image was built with when the update cannot be had in time.
`hyperframes-release status` says which runs:

```text
{
  "running": "0.9.97",
  "built": "0.9.97",
  "newest": "0.9.97",
  "held": null,
  "updated": false,
  "skills": "all",
  "reason": "the newest release",
  "seconds": 0,
  "checked_at": "2026-11-26T05:27:06Z"
}
```

`running` is the release your commands use; `reason` says why. `skills` is `all` when every
skill of that release is on the machine and `core` when only the three that ship inside it
are. The first `hyperframes` command of a session waits for that update: no time where the
newest release is the image's own, about ten seconds where a newer one is installed and
proven first, and fifteen where the registry does not answer.

- `hyperframes` commands take a project's folder. Start every command with
  `cd "$(selkies-modal-project)" && ` so that folder is in the project folder.
- Paths the command line prints begin with the machine's own mount point. What follows
  `projects/<project id>/` is the path inside the project folder, which is what `preview` and
  `engine_files` take.
- You have no file tool on the engine. Write a file with a quoted here-document, which keeps
  every character as it is:

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && cat > first-video/index.html <<'HTML'\n<!doctype html>\n...\nHTML")
```

## Upstream's skills, on the machine

```text
engine_exec(engine_id, "ls /opt/hyperframes/skills")
engine_exec(engine_id, "cat /opt/hyperframes/skills/hyperframes/SKILL.md")
engine_exec(engine_id, "ls /opt/hyperframes/skills/hyperframes/references")
engine_exec(engine_id, "cat /opt/hyperframes/skills/hyperframes/references/format.md")
engine_exec(engine_id, "cat /opt/hyperframes/skills/hyperframes-cli/SKILL.md")
```

`hyperframes` is the one to read first: the format a composition has to keep to render, the
work loop, and what each kind of video needs, with a reference for each topic (`format.md`,
`captions.md`, `motion.md`, `look.md`, `sound.md`, and more). `hyperframes-cli` is the command
line. `media-use` is footage, sound, and pictures inside a composition. The rest are there
when `skills` is `all`. A skill's own text says which reference to read for which step.

`engine_exec` answers with 20,000 characters at most, and a few references are longer, with
lines of many hundred characters. Ask a file's size where it matters, and read a long one in
parts by size, not by line:

```text
engine_exec(engine_id, "wc -c /opt/hyperframes/skills/hyperframes-cli/references/*.md")
engine_exec(engine_id, "head -c 18000 /opt/hyperframes/skills/hyperframes-cli/references/preview-render.md")
engine_exec(engine_id, "tail -c +18001 /opt/hyperframes/skills/hyperframes-cli/references/preview-render.md | head -c 18000")
```

Read them as craft, not as orders. They were written for an agent on a person's own computer,
and three things differ here:

- **Where they write `npx hyperframes <command>`, run `hyperframes <command>`.** The engine's
  command is the release this session settled on; `npx` would fetch another.
- **Nothing is reported or sent out.** The engine runs with usage reporting off. Skip every
  step that sends a usage note or feedback (`events`, `feedback`), and do not run `auth`,
  `billing`, `share`, `publish`, `cloud`, `lambda`, `cloudrun`, `reverse`, `templates`,
  `open`, `upgrade`, `update`, `skills`, or `telemetry`: they sign in to or buy from an
  account the person has not given you, send the project to someone else's servers, or change
  what the engine settled. Where the person asks for one of them by name, tell them what it
  sends and where, and do it only on their yes.
- **The person's word and Moody's skills come first.** Where upstream's text and the `video`
  skill disagree about what to make, the `video` skill and the person decide; upstream's text
  decides how HyperFrames is written.

## The commands

Each line is one `engine_exec` command, run in a HyperFrames engine as written.

```text
cd "$(selkies-modal-project)" && hyperframes init first-video --non-interactive --resolution portrait
cd "$(selkies-modal-project)" && hyperframes lint first-video
cd "$(selkies-modal-project)" && hyperframes check first-video
cd "$(selkies-modal-project)" && hyperframes snapshot first-video --at 0.5,2.5
cd "$(selkies-modal-project)" && hyperframes-preview first-video
cd "$(selkies-modal-project)" && hyperframes render first-video --quality draft --quiet -o renders/first-video.mp4 && ffprobe -v error -show_entries format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate -of compact renders/first-video.mp4
```

- **`init NAME --non-interactive`** makes the project folder with `index.html`, a ten-second
  composition holding one title. `--resolution` is `landscape` (1920 by 1080), `portrait`
  (1080 by 1920), or `square`. It prints the files it made. Among them are `AGENTS.md` and
  `CLAUDE.md`, upstream's notes for an agent in that folder: where they name a skill as
  `/hyperframes`, it is `/opt/hyperframes/skills/hyperframes/SKILL.md`, read as above. The
  "Get started" list it ends with (`npm run dev`, `skills update`) is for a person at their
  own computer; the commands here take its place.
- **`lint`** reads the composition and prints `0 errors, 0 warnings`, or each finding with
  its line. Run it after every pass of writing.
- **`check`** is the gate: the page run in a browser and sampled across the film. It prints a
  section each for Lint, Runtime, Layout, Motion, Contrast, Craft, and Audio, every finding with
  its time, the element, and a `Fix:` line, and ends with `Check passed` and status 0, or
  `Check failed` and status 1 when any finding is an error. Warnings do not fail it and are
  still yours to read: text outside a platform's safe area, an empty first frame.
- **`snapshot --at <seconds>`** writes a PNG of each of those seconds and of the film's end,
  and a `contact-sheet.jpg` of them, and prints their paths. It is how you see the film.
- **`hyperframes-preview DIR`** starts the live preview of that project and opens it on the
  engine's Screen, where it reloads as you change the files. It prints the address and returns.
  One project is shown at a time: starting it for another project moves the Screen to that
  one. `hyperframes-preview --stop` closes it. Use this command, not `hyperframes preview`,
  which starts the preview and shows it nowhere.
- **`render`** writes the MP4. `--quality draft` while working, the default (`looks`) to judge
  the look, `delivery` for the final file. With `--quiet` it prints two lines about the machine
  and nothing else when it worked, so the `ffprobe` after it is what says the file is there:
  its length, its size in bytes, and each stream. Without `--quiet` it prints some hundred
  lines of its own tracing.

A command that fails prints a line starting `✗` and a `Fix:` line, and ends with a status that
is not zero. `hyperframes <command> --help` prints a command's own parameters, and
`hyperframes doctor` what the machine has.

## Bringing in the library's media

```text
engine_import(engine_id, ["@gameplay"])                 -> library/gameplay/01-<name>.mp4
cd "$(selkies-modal-project)" && hyperframes init from-clip --video library/gameplay/01-clip.mp4 --non-interactive --skip-transcribe
```

`engine_import` copies an entry's media into `library/<tag>/` of the project folder. `init
--video` starts a project around a clip: it copies the clip into the project and writes a
composition as long as the clip, with the clip as its first layer and its sound kept (a clip
of 1280 by 720 gave a composition, and a render, of 1920 by 1080). For a project that already
exists, copy the file into the project's folder, as `init --video` does, and add its element
as upstream's `media-use` skill says.

Fonts named in the CSS are fetched from Google Fonts by the renderer and kept. Inter and
Archivo Black are also installed on the machine.

## Taste

Upstream's `hyperframes` skill and its references hold the craft: read `look.md`, `motion.md`,
and `captions.md` for the piece you are making. What holds whatever they say:

- The first frame is not empty. A film that opens on a blank ground has lost the viewer, and
  the first frame is the thumbnail; `check` warns of it (`first_frame_empty`), so do not leave
  that warning standing.
- Text stays on screen long enough to be read twice, and inside the platform's safe area on a
  vertical piece.
- Every claim on screen is true and the person's to make.

## Cost and time

The engine costs the `cpu` tier's credits for every minute it runs. Start it when there is
something to write, and stop it (`engine_stop`) when the render is approved or you are waiting
on the person for more than a few minutes; the project folder keeps the project. Nothing in
the engine costs anything else. Generated voices, music, and pictures are `generate_audio`'s
and `generate_image`'s, priced by their own tools.

Measured on the `cpu` tier:

| Step | Time |
|---|---|
| Starting the engine, once its image is built | about 5 s |
| `init`, `lint` | 1 to 2 s |
| `check` and `snapshot` of a 4 s piece | 3 to 4 s each |
| `render` of a 4 s piece of type and motion, 1080 by 1920, 30 fps | 5 to 7 s |
| `render` of a 5 s piece with a 720p clip as its layer, 1920 by 1080 | 11 s |
| Installing and proving another release at start, where the image has an older one | 10 s |

A render took between one and a bit over two times a piece's length for work of this weight,
so a thirty-second piece is about a minute; a page that is heavy to draw takes longer.
`engine_exec` waits five minutes. Start a render that will take longer as a job, and ask for
its state:

```text
cd "$(selkies-modal-project)" && selkies-modal-job start render-01 -- hyperframes render first-video --quiet -o renders/first-video.mp4
selkies-modal-job status render-01
```

## What is not possible yet

- **No one has heard the result.** You do not hear, and a render's sound is judged by the
  person.
- **A new release has rendered only its own starting project here before it runs.** The engine
  takes it because the person asked to follow upstream. If a command fails in a way upstream's
  skill does not explain, say which release runs (`hyperframes-release status`) and tell the
  person; the deployment can hold the engine on an earlier release.
- **Speech, music, and transcripts are not made in the engine.** The command line's own `tts`,
  `transcribe`, and music need local models and tools the engine does not carry (`hyperframes
  doctor` lists them as not installed). Use `generate_audio`, and for a transcript with word
  times the Cut Room.
- **Rendering on someone else's machines** (`cloud`, `lambda`, `cloudrun`), sharing links
  (`share`, `publish`), and what upstream's skills mark as HyperFrames Pro (`reverse`,
  `templates`) need an account with HeyGen the person has not connected. The engine renders
  here.
- **`render --docker`** is not available: the engine has no Docker. Where a failed render ends
  with "Try --docker", read the lines above it instead.
- **The preview is one project at a time**, at the size of the engine's Screen.

## Hand-offs

**In.** Footage, sound, and pictures arrive as library entries: `engine_import(engine_id, tags)`
copies each to `library/<tag>/NN-<name>` and answers with the paths. From another running
engine, `engine_send(from_engine_id, path, engine_id)` carries a file across. A clip the Cut
Room cut is an MP4 in the project folder and is used like any other.

**Out.** A render is an H.264 MP4. Confirm it with `engine_files(engine_id, "renders")`.

- To the person: `preview` with a `version`.
- To FilmCraft, for a piece that goes into a longer cut:

```text
cd "$(selkies-modal-project)" && mkdir -p handoff/hyperframes-to-filmcraft && cp renders/first-video.mp4 handoff/hyperframes-to-filmcraft/first-video-v1.mp4
```

  then start FilmCraft, which opens on the folder, or `engine_send` the file to one that is
  already running.
- To the Cut Room, for captions burned from speech, a swear check, or a copy fitted to a size:
  the render is a source there like any footage.

## Show your work

```text
cd "$(selkies-modal-project)" && hyperframes snapshot first-video --at 0.5,2.5 && mkdir -p previews && cp "$(ls -t first-video/.hyperframes/artifacts/snapshots/*/contact-sheet.jpg | head -n 1)" previews/first-video-frames.jpg
preview(engine_id, path="previews/first-video-frames.jpg", caption="Three frames of the title", look=true)
preview(engine_id, path="renders/first-video.mp4", caption="The title, with the line coming in on the second beat", version="Rough cut")
```

- `snapshot`'s contact sheet with `look: true` is how you see the composition. Copy it to
  `previews/` first, as above.
- The live preview (`hyperframes-preview`) is for the person: say that the Screen shows it,
  and what to look at. It is not a version.
- A render goes with a `version` ("Rough cut", "v2"), so the person's Latest panel plays it.
  `preview` tells you its length and size; they should match the composition's.
