---
name: cutroom
description: Edit video by code in the Cut Room, an engine with no application to click. Map footage (a frame for every second, scene cuts, a transcript with word times), find the moments in it, cut vertical clips with captions and a hook, cut horizontal explainers under a narration with subtitles, a headline, and music, lay and master voices, mute swearing, check the result, and fit it to a size, all with commands. Use it whenever a turn's state says a video edited by code is made in the Cut Room, which is the default for Social Media and Education videos, and whenever footage has to be cut, captioned, voiced, or measured without a timeline.
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.

  This skill is adapted from the skills of gtavi-claudecode
  (drive-narrated-clips, clip-cutter, moment-finder, rule-check, multilang,
  viral-clips, and twitch-reaction), the project the Cut Room's scripts come
  from, and incorporates work covered by the following copyright and
  permission notice:

      MIT License

      Copyright (c) 2026 Bodila51

      Permission is hereby granted, free of charge, to any person obtaining a copy
      of this software and associated documentation files (the "Software"), to deal
      in the Software without restriction, including without limitation the rights
      to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
      copies of the Software, and to permit persons to whom the Software is
      furnished to do so, subject to the following conditions:

      The above copyright notice and this permission notice shall be included in all
      copies or substantial portions of the Software.

      THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
      IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
      FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
      AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
      LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
      OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
      SOFTWARE.
-->

# Cut Room

The Cut Room is a machine with FFmpeg, speech-to-text, a voice-mastering chain, and a set of
scripts that each do one step of an edit. There is no timeline and no window to click: every
edit is a command you run with `engine_exec`, and what a command prints is what you know.

Two things follow from that, and they shape every recipe here.

- **You cannot watch or hear.** You read contact sheets, check frames, transcripts, and levels.
  The person watches and listens. Measure everything you can, look at frames with `preview` and
  `look: true`, and tell the person what they have to judge by ear.
- **Everything is a default.** The settings below are the ones a maker of these videos settled
  on over many revisions, so start from them. Every one is a parameter: when the person's
  material or their word calls for another look, length, layout, or level, change it, and say
  in a line what you changed and why. Their rules outrank this file.

The detail is in two references. Read the one a step needs before you run it:

| Reference | Read it before |
|---|---|
| [references/commands.md](references/commands.md) | your first command, and whenever you need a script's parameters, what it prints, or what its failures mean |
| [references/cutting.md](references/cutting.md) | choosing what to keep, where a clip starts, how to frame it, and how to lay voices, for a vertical clip or an explainer |

## When this applies

The turn's state names the Cut Room (`cutroom`) as where a video edited by code is made, or the
person has footage to cut, caption, voice, translate, or measure and no need of a timeline. It
is the default way a Social Media or an Education video is made.

Not here: which kind of video to make, the hook's wording, the script, and the words of the
post are the `video` skill's. A film cut shot by shot with color and a mix is FilmCraft's
(`filmcraft`). Music and sound made from nothing are `generate_audio`'s or SoundCraft's. A
video composed from type and animation with no footage is HyperFrames' (`hyperframes`), where
the person has switched it on.

## The loop

1. **Map before you cut.** Never cut footage you have not read: sheets, scene cuts, level,
   transcript.
2. **Propose** what you would keep and why, in the person's words, with the times.
3. **Ask** only what is theirs: which moment, which hook, which voice, whether it posts.
   `ask_user(question, options, recommended)`, one decision a question.
4. **Voice first, then the cut.** The narration sets the length; the footage is fitted to it.
5. **Cut, check, look.** Run the cut, run `cutroom check`, then look at frame 1 and a sheet of
   check frames yourself.
6. **Show** with `preview` and a `version`, say what to listen for, and record the cut and the
   rule behind every change the person asks for.

Checkpoints, always asked first: starting the engine (the page asks), any generated voice,
music, or picture and its cost, replacing a version the person approved, and anything that
leaves the studio. Nothing here posts anywhere.

## The engine

```text
engine_start("cutroom", "cpu")
```

The `cpu` tier is the one to use: the scripts run on the CPU, and nothing here was measured on
a GPU tier. It starts in under ten seconds. Its Screen shows a log of every `cutroom` command
as it runs, which is all there is to watch; finished cuts reach the person as previews.

```text
engine_exec(engine_id, "cutroom")                 lists the scripts, a line each
engine_exec(engine_id, "cutroom cut --help")      one script's parameters
engine_exec(engine_id, "cutroom versions")        what the image holds, each part with its source
```

- `cutroom NAME ...` runs in the project folder whatever directory you are in, so **every path
  you give a script is relative to the project folder**: `footage/a.mp4`, `jobs/<id>`.
- Any other command starts in the home directory. Begin it with
  `cd "$(selkies-modal-project)" && ` to work in the project folder.
- `engine_exec` waits five minutes at most. A cut and its check take about six times the
  clip's length together, so anything over forty seconds of output, and every batch, runs as a
  job you start and then ask about:

```text
engine_exec(engine_id, "selkies-modal-job start cut-01 -- cutroom cut jobs/<id> --pick 1 --layout blur --hook 'TEXT'")
engine_exec(engine_id, "selkies-modal-job status cut-01")     running, done, or failed (exit N)
engine_exec(engine_id, "selkies-modal-job log cut-01")        what it printed
```

What goes where in the project folder:

```text
library/<tag>/        what engine_import brought: footage, voice takes, music, art
footage/              footage you downloaded or joined
jobs/<name>-<hash>/   one source's work: transcript.json, candidates.md, edits/<clip>.mp4 .ass .json
narration/<name>/     a laid narration: voice.wav, voice_warm.wav, lines.json
edits/                horizontal cuts and their copies fitted to a size
sheets/<name>/        contact sheets and check frames
```

## The recipes

Each line is one `engine_exec` command. Parameters, units, and outputs are in commands.md.

### 1. Bring the footage in

```text
engine_import(engine_id, ["@gameplay"])                       -> library/gameplay/01-<name>.mp4
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && mkdir -p footage && curl -fsSL -o footage/clip.mp4 '<a direct link to a file>'")
engine_exec(engine_id, "cutroom join library/a/01-a.mov library/b/01-b.mov --out footage/both.mp4")
```

Footage the person uploaded is in the library; `engine_import` copies it in. A direct link to a
file downloads with curl. Several recordings are joined first, and `join` prints the second
each one starts at in the joined file.

### 2. Map it

```text
engine_exec(engine_id, "cutroom sheet footage/clip.mp4")
engine_exec(engine_id, "cutroom sheet footage/clip.mp4 --every 0.5 --start 9 --end 12 --tile 6x1 --out sheets/close")
engine_exec(engine_id, "cutroom moments footage/clip.mp4 --top 8")
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && cat jobs/<id>/candidates.md")
engine_exec(engine_id, "cutroom words footage/clip.mp4 --start 10 --end 20")
```

`sheet` prints the scene cuts, black stretches, and the level, and writes
`sheets/<name>/sheet_01.jpg`, one frame a second with its time: look at it
(`preview(engine_id, path="sheets/clip/sheet_01.jpg", caption=..., look=true)`). `moments`
transcribes the whole source, scores every second, and writes the candidates; its first line is
the job folder every later step takes. A level near silence means nobody speaks, and a
transcript of it is invented words.

### 3. A vertical clip

```text
engine_exec(engine_id, "cutroom cut jobs/<id> --pick 1 --layout focus --name <clip> --segments '10.0-18.5,0.5-3.0@2,20.0-24.5' --focus '0:0.5,4:0.62,8.49:0.62,8.5:0.5' --hook 'This fractal never ENDS'")
engine_exec(engine_id, "cutroom sheet jobs/<id>/edits/<clip>.mp4 --at 0.2,3,9,13 --out sheets/<clip>")
engine_exec(engine_id, "cutroom check jobs/<id>/edits/<clip>.mp4 --caption '<the words of the post>'")
```

1080 by 1920, 30 frames a second, captions word by word from the transcript, the hook above a
4:5 window for the whole clip, at -14 LUFS. `--segments` are the parts kept, in source seconds,
joined with jump cuts (`a-b@2` twice as fast, `@0.5` a half-speed replay); `--focus` is where
the window looks over time. Leave `--segments` and `--focus` out and name a `--layout`
(`blur`, the default, `fill`, `facecam`, `react`) for a moment cut whole. The cut mutes every
swear it hears and listens to its own result again.

With voices laid over the footage (reactions, a narrator), lay them first and give the cut
their lines and their track; the footage's own sound stays under them at 30 percent:

```text
engine_exec(engine_id, "cutroom narrate reactions.json --out narration/reactions")
engine_exec(engine_id, "cutroom cut jobs/<id> --pick 1 --layout focus --name <clip> --segments '10.0-18.5' --focus '0:0.5' --lines narration/reactions/lines.json --lines-time output --voice narration/reactions/voice.wav --bed-gain 0.3 --hook 'Nobody expected the ZOOM'")
```

A presenter with a webcam over a screen: `--layout react --cam auto --title 'TEXT'` puts the
face on top, the screen below, and the title on the seam.

### 4. A horizontal explainer

```text
engine_exec(engine_id, "cutroom narrate narration.json --out narration/explainer")
engine_exec(engine_id, "cutroom vo_master narration/explainer/voice.wav narration/explainer/voice_warm.wav --preset studio_warm")
engine_exec(engine_id, "cutroom words library/line-01/01-take.wav --lang en --offset 0.3")
engine_exec(engine_id, "cutroom explainer --src footage/clip.mp4 --segments '0-9@3,10-18.5,20-28' --lines narration/explainer/lines.json --voice narration/explainer/voice_warm.wav --title-words 'EDITED@1.74,BY@2.48,|CODE@2.76' --title-end 4.0 --music library/bed/01-bed.mp3 --out edits/explainer_base.mp4")
engine_exec(engine_id, "cutroom check edits/explainer_base.mp4 --size 1920x1080")
```

1920 by 1080: the parts at their speeds with a speed badge over the fast ones, a subtitle a
sentence, the headline thrown word by word at the seconds `words` printed, music ducked under
the mastered voice. An opening with a sign that pops in on a word, and a copy fitted to a size:

```text
engine_exec(engine_id, "cutroom key library/sign/01-sign.png art/sign.png")
engine_exec(engine_id, "cutroom reveal edits/explainer_base.mp4 edits/explainer.mp4 --sign art/sign.png@0.3 --end 1.6")
engine_exec(engine_id, "cutroom check edits/explainer.mp4 --size 1920x1080 --ass edits/explainer_base.ass")
engine_exec(engine_id, "cutroom fit edits/explainer.mp4 edits/explainer_page.mp4 --mb 18.2")
```

The same parts and voice as a vertical cut, once the horizontal one is approved:

```text
engine_exec(engine_id, "cutroom cut jobs/<id> --pick 1 --layout focus --name explainer_vertical --segments '0-9@3,10-18.5,20-28' --focus '0:0.5' --lines narration/explainer/lines.json --lines-time output --voice narration/explainer/voice_warm.wav --bed-gain 0.2 --hook 'How the Cut Room works'")
```

### 5. Measure and check

```text
engine_exec(engine_id, "cutroom levels edits/explainer.mp4 --spans '4.4-8.8,13-18'")
engine_exec(engine_id, "cutroom check <clip>.mp4 [--size 1920x1080] [--caption 'post text'] [--lang es] [--rules rules.md]")
```

`levels` prints the integrated loudness, the true peak, and the RMS level of each stretch you
name: one where the voice speaks and one where only the music plays tell you how far under the
voice the music sits. `check` prints PASS or FAIL a line and ends with status 1 on any FAIL. Fix
the cause of a failed check and run it again; never argue with it, and never report a clip
whose check you did not read.

### 6. Another language

```text
engine_exec(engine_id, "cutroom translate jobs/<id> --pick 1 --sentences")
engine_exec(engine_id, "cutroom translate jobs/<id> --pick 1 --lang es --text translations/es.json --voice")
```

`--sentences` prints the clip's hook and sentences as JSON. Translate them yourself, write the
same shape to a file in the project folder, and give it back with `--text`. `--voice` has a
stock voice speak the translated hook over the first 2.5 seconds.

## The settled numbers

Start from these. Each is a parameter of the script named; commands.md has the rest.

| What | Value | Where |
|---|---|---|
| Vertical clip | 1080 by 1920, 30 fps, 15 to 20 s, 30 at most | `cut` |
| Explainer | 1920 by 1080, 30 fps, 30 to 45 s | `explainer` |
| Loudness of a finished cut | -14 LUFS, true peak under -1.5 dB | `cut`, `explainer` |
| Loudness of a mastered voice | -16 LUFS, dry, preset `studio_warm` | `vo_master` |
| The footage's own sound under voices | 0.3 in a clip, 0.2 in an explainer | `--bed-gain` |
| Music under a narration | 0.16, ducked further while the voice speaks; about 10 dB under it | `--music-gain` |
| Reaction voices | spoken 1.25 times as fast (1.3 for a montage), a color a speaker: `FFFFFF`, `8FE6FF`, `FF9AD2` | `narrate` |
| Captions | capitals, three words at most, the spoken word yellow, centered at 1420 px in the focus layout | `cut` |
| Captions against text in the footage | 1180 to sit above it, 1540 to sit below it | `--cap-y` |
| Hook | above the window for the whole clip in the focus layout; 2.6 s in the others | `--hook-secs` |
| Speed | walking, menus, and editor work at 2 to 4 times with a badge; the point itself at 1; small text at 0.5 | `--segments a-b@N` |
| Explainer subtitles | a sentence at a time, 84 characters at most, raised 150 px to clear an interface | `explainer` |
| An opening reveal | signs pop in over 0.28 s on their words, gone by 4.0 s; the narration starts at 4.0 | `reveal` |
| A copy for a 20 MB limit | 18.2 MB, two passes | `fit --mb` |
| A swear | muted from 0.25 s before the word; left out of captions, never starred | `cut` |

## Taste

The rules a cut is held to. cutting.md has each with its reason and how to do it.

- **Frame 1 is the hook's subject, moving.** Start the clip where the subject first appears;
  cut the seconds before it.
- **Cut only where the footage cuts.** A segment starts and ends on a scene cut `sheet` printed,
  never in the middle of a shot. Skip black.
- **Every key word lands on its shot.** When a voice names a thing, that thing is on screen.
- **No dead seconds.** Two seconds in which nothing changes become a jump cut or a speed-up.
- **End on the payoff, at its peak.** No outro.
- **Nothing the viewer needs is cropped.** A face, the action, text in the footage: move the
  window with `--focus`, the captions with `--cap-y`, or drop the shot.
- **A caption says what was said.** Where the footage shows its own subtitles, write the lines
  out and pass them with `--lines`; a wrong caption is worse than none.
- **The voice is on top.** Music and the footage's sound sit well under it, and you prove it
  with `levels`, since you cannot hear it.
- **No swear word is heard or read**, in the language the clip is in. Give `--lang` its
  language: listening for the wrong one hears swears nobody said and mutes clean dialogue.

## Cost and time

The engine costs the `cpu` tier's credits for every minute it runs, working or not. Start it
when there is footage to map, and stop it (`engine_stop`) when the cuts are approved or you
are waiting on the person for more than a few minutes; the project folder keeps everything,
and a new engine opens on it in seconds. Nothing in the engine costs anything else: the scripts
call no paid service. Voices, music, and pictures are `generate_audio`'s and
`generate_image`'s, priced by their own tools; quote them before you make them.

Measured on the `cpu` tier, with a 30 s 1080p source, over two runs:

| Step | Time |
|---|---|
| Starting the engine | under 10 s |
| `sheet` of a 30 s source | 6 s |
| `moments`, with the transcript, of a 30 s source | 6 s |
| `words` for one take or ten seconds | 7 to 9 s |
| `narrate`, `vo_master`, `key`, `chime`, `levels` | 1 to 3 s each |
| `cut`, a 14 s vertical clip with its own swear check | 85 to 115 s |
| `cut`, an 8.5 s clip under narration | 60 s |
| `cut --layout react`, a 10 s clip, camera found by itself | 70 to 85 s |
| `check` of a 14 to 20 s cut | 50 to 100 s |
| `explainer`, 19.5 s with music and a headline | 55 to 75 s |
| `reveal` over it | 15 to 19 s |
| `fit`, two passes over 19.5 s | 14 to 17 s |
| `join` of 42 s of 1080p | 24 s |
| `clean`, 30 s | 35 s |

Most of a cut's time is the swear check, which listens to the result with two speech models.
Say before a batch how long it will take: about six times a clip's length for the cut, and
about four times for its check.

## What is not possible yet

- **YouTube refuses the engine.** `cutroom moments <a YouTube address>` fails with "Sign in to
  confirm you're not a bot" from the engine's address. Ask the person for the file, or for a
  link to a file. Addresses of other sites yt-dlp reads may work; one of archive.org did.
- **A link to a file in someone's cloud drive was not tried.** A direct link to a file works
  with curl. If a drive's link downloads a page instead of the video, `cutroom sheet` will say
  it cannot read it: ask for an upload.
- **Nothing speaks here.** `narrate` lays takes that exist. Generate each line with
  `generate_audio` (`kind: "speech"`), keep it in the library, and bring it in with
  `engine_import`.
- **Machine translation is refused from the engine's address** (`translate --langs`): translate
  the sentences yourself and pass them with `--text`.
- **`translate` follows only a clip cut whole from its transcript**, with the blur, fill, or
  facecam layout. A clip with jump cuts or laid voices is translated by cutting it again with
  translated `--lines`.
- **The vertical cutter has no music, headline, or speed badge.** Those are the explainer's. A
  vertical version of an explainer carries its voice and captions only.
- **`reveal` takes one or two signs**, laid over a horizontal video.
- **The face finder needs a face that stays put**: a webcam box over a screen. A presenter
  filling the frame is answered `none`, and the cut falls back to the blur layout and says so.
- **Nothing is posted.** The person posts. You hand over the file and the words.
- **You do not hear.** Every choice between sounds, and every "does this sound right", is the
  person's.

## Hand-offs

**In.** Footage, voice takes, music, and art arrive as library entries: `engine_import(engine_id,
tags)` copies each entry's media to `library/<tag>/NN-<name>` and answers with the paths.
Generated speech and music are `generate_audio`'s (`save_to` a library section, then import by
tag); a sign or a logo for an overlay is `generate_image`'s, asked for on a flat pure green
background, or magenta when the art is green, and cut out here with `cutroom key`. From another
running engine, `engine_send(from_engine_id, path, engine_id)` carries a file across; from a
folder of the project that an earlier engine wrote, it is simply there.

**Out.** A finished cut is an H.264 MP4 with AAC sound. Confirm it with
`engine_files(engine_id, "jobs/<id>/edits")` before anything depends on it.

- To the person: `preview` with a `version`, and the words of the post beside it.
- To FilmCraft, for a cut that goes on with color, a mix, or other shots: copy the master into
  the hand-off folder, then start FilmCraft, which opens on the folder and imports it. A
  FilmCraft that is already running gets it with `engine_send`.

```text
engine_exec(engine_id, "cd \"$(selkies-modal-project)\" && mkdir -p handoff/cutroom-to-filmcraft && cp edits/explainer.mp4 handoff/cutroom-to-filmcraft/explainer-v1.mp4")
```

- To the library, as the piece's kept version: that is the `video` skill's step, with
  `library_upsert` and the person's approval.

## Show your work

The person sees the conversation, not your commands. Show:

```text
preview(engine_id, path="sheets/clip/sheet_01.jpg", caption="The footage, a frame a second", look=true)
preview(engine_id, path="sheets/<clip>/frames.jpg", caption="Frame 1 and three more of the cut", look=true)
preview(engine_id, path="jobs/<id>/edits/<clip>.mp4", caption="The clip with the new hook; listen for the voices over the music", version="Rough cut")
preview(engine_id, paths=["edits/explainer_v1.mp4", "edits/explainer_v2.mp4"], caption="Before and after the music came down", compare=true)
```

- A contact sheet or check frames with `look: true` is how you see the footage and your cut.
  Make check frames with `cutroom sheet <file> --at <seconds>`: always frame 1, the frame a hook
  or a title lands on, and one of every caption position you changed.
- A finished cut goes with a `version` ("Rough cut", "v2"), so the person's Latest panel plays
  it. Check frames and sheets are steps, not versions: give them no `version`.
- `preview` tells you the file's length, size, loudness, and peak. They should agree with
  `cutroom levels`.
- Say in the caption what changed and what to listen for. One preview a stage, not a command.
