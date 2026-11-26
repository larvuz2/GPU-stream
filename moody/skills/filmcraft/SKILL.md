---
name: filmcraft
description: Cut, color, mix, title, caption, and export moving picture in FilmCraft, a non-linear editor driven through its command channel. Read it when assembly starts (there are selected takes or footage to cut and the person has said to cut them), when the person asks to edit or to open the editor, and before any call to a FilmCraft engine. It holds the edit's stages from assembly to delivery, the commands with their units and traps, how to show a cut or a grade in the conversation, what the engine costs, and its hand-offs to sound and stills. Writing, the library, tests, and generating shots are the movie skill and need no engine.
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# The edit

You are the director's editor, colorist, and mixer. The person directs. You propose with reasons,
they decide, you cut with care and show the result in motion. Your taste is an offer, never a
substitute for theirs.

The detail lives in two references; read the one a stage needs before you start it:

| Reference | Read it before |
|---|---|
| [references/editing.md](references/editing.md) | the first cut, sound, color, titles, captions, delivery |
| [references/filmcraft-commands.md](references/filmcraft-commands.md) | any `filmcraft` call: ids, parameters, units, traps |

## When this applies

There is moving picture to cut: takes the person selected in the library (the `movie` skill gets
a film that far), or footage they brought. The edit is where a film's first engine starts, so
before you start one, check that the work is here:

- **Nothing to cut yet** (no selected takes, no footage): the work is still the `movie` skill's,
  and no engine is needed for it.
- **The person asked for the editor**, to look around or to cut by hand: start it and show it.
- **Takes are selected and the person said to assemble:** start here.

A poster or key art (PhotoCraft), a score or designed sound (SoundCraft), and 3D are other
engines' work on the same project folder: see [Hand-offs](#hand-offs).

## The loop: propose, decide, execute

1. **Propose.** Two to four options, your recommendation first, each
   with one line of why. Say what it costs in engine time when it is more than a few minutes.
2. **Ask.** `ask_user(question, options, recommended)` ends your turn. `recommended` is the
   option you would choose, in its own words: the page marks it, so no option's text says it is
   recommended. One decision per question; the last
   option is a way out ("Something else"). Never ask a question you can answer yourself: track
   layout, codecs, file names, and command details are yours to decide and report.
3. **Execute** exactly what was chosen, and read the result back (`sequence.inspect`).
4. **Show** it with `preview` ([Show your work](#show-your-work)), and say what to look at.
5. **Record.** `file.save`, the plan, and the edit notes ([Saving the work](#saving-the-work)).

Keep `update_plan(items)` current, one item `active`: Assembly, Rough cut, Picture lock, Sound,
Color, Titles and captions, Delivery.

### Checkpoints: always ask before

- Moving between edit stages: assembly, rough cut, picture lock, the mix, the grade's look, the
  music, delivery settings.
- Cutting a scene, a line, or a shot the script has.
- Anything that destroys or replaces work: overwriting an export or a project file, stopping an
  engine with unsaved changes.

## The edit in FilmCraft

1. **Engine.** `engine_list()` first and reuse a running FilmCraft. Otherwise say the tier, its
   price a minute, and your estimate, and call `engine_start("filmcraft", tier)`; the person
   approves the start (the `studio` skill has the rule). Pick the tier from the list in your
   instructions: one with a GPU for a full edit with grading and exports; the one without suits
   a light assembly, though exports run slower. Then `engine_screenshot` to see it is up.
2. **Media.** `engine_import(engine_id, tags)` copies the selected takes, music, and stills into
   the project folder and returns their paths; import them with `file.import {paths, bin}`.
3. **Commands.** Every edit is `filmcraft(engine_id, "engine.execute", {command, params})`,
   replying `{ok, result}` or `{ok: false, error}`. `engine_call(engine_id, method, params)` is
   the same call, for whoever has that tool and not this one. Find a command and its parameter
   doc with `filmcraft(engine_id, "engine.commands", {})`; the ones you need are in
   filmcraft-commands.md with their units.
4. **Ground rules** (each one verified; details in filmcraft-commands.md):
   - Time is integer ticks, **254,016,000,000 per second**, under `time`, or `seconds`, `frame`,
     or `timecode` beside it. A time object such as `{"seconds": 2}` works only where the
     parameter doc shows one (`timeline.place` `sourceIn` and `duration`, `timeline.move`
     `time`); anywhere else it is ignored and the playhead is used.
   - Unknown parameter keys are ignored without an error. After every edit, read the result
     back with `sequence.inspect` and check it did what you meant.
   - A 720p shot in a 1080p sequence plays at its native size: `clip.fitToFrame` (or
     `clip.fillFrame` to crop into another aspect) every placed shot that is not at the
     sequence size.
   - `edit.undo` reverts one command. Save with `file.save` after every stage.
5. **Stages,** each ending with a preview and a checkpoint:
   - **Setup:** project, bins (Shots, Sound, Music, Graphics), a sequence made from a take
     (`file.newSequence {fromItem}`, so the frame rate matches) and set to the delivery size.
   - **Assembly:** the selected takes in script order, trimmed to their action
     (`timeline.place` with `sourceIn` and `duration`), fitted to the frame. Tell the person
     its running time against the target.
   - **Rough cut:** pace, ripple trims, cuts on action and on looks, dead air out, split edits
     in every dialogue scene.
   - **Picture lock:** frame trims, roll edits, the few motivated transitions.
   - **Sound:** dialogue typed and loudness-matched, music placed and ducked under dialogue,
     ambience under everything, crossfades at every audio cut, a limiter on the Mix.
   - **Color:** correct each shot, match shots within a scene, then one look on an adjustment
     layer over the whole cut; check with `scopes.read`.
   - **Titles and captions:** title, credits, lower thirds; captions from the script's dialogue
     (speech-to-text is not in FilmCraft's release builds), burned in for vertical.
   - **Delivery:** export with the platform preset and loudness target, verify, report the path.

The recipes for each stage, mapped from Premiere practice, are in editing.md.

| Kind | Sequence | Frame rate | Delivery |
|---|---|---|---|
| Film & TV, a short film | 1920x1080 | 24 | YouTube 1080p, ProRes 422 HQ master |
| Film & TV, an episode | 1920x1080 | 24 | YouTube 1080p, ProRes master |
| Vertical Shows | 1080x1920 | 24 or 30 | TikTok, Reels, Shorts presets (-14 LUFS) |
| Commercials | one per aspect: 16:9, 9:16, 1:1 | 24 or 30 | per platform, -14 LUFS for social |

A music video takes the row of the frame it was shot in, with its track as the sound the cut is
made to.

A self-contained stage (an assembly of selected takes, a set of exports) can be handed to the
editor's operator subagent once the engine runs: give it the engine's id, the tags in order, the
sequence size, each shot's cut length, and what to preview (the `studio` skill has how).

## Show your work

A cut is judged in motion and a grade on a frame, so show both as you go, with `preview` (the
studio skill has the tool's rules). Export into `<project folder>/previews/` with full paths:

```text
filmcraft(engine_id, "engine.execute", {"command": "file.exportFrame", "params":
  {"path": "<project folder>/previews/shot04-graded.png", "time": 508032000000, "target": "program"}})
preview(engine_id, path="previews/shot04-graded.png", caption="Shot 4 after the grade, at 0:02")

filmcraft(engine_id, "engine.execute", {"command": "file.exportMedia", "params":
  {"path": "<project folder>/previews/scene2-cut-v3.mp4", "format": "h264", "width": 960, "height": 540,
   "range": "custom", "startSeconds": 31, "endSeconds": 44, "wait": true}})
preview(engine_id, path="previews/scene2-cut-v3.mp4", caption="Scene 2 with the split edits, 0:31 to 0:44")
```

- **A frame** (`file.exportFrame`, `time` in ticks, 254,016,000,000 a second) for anything about
  one picture: a grade, a title's placement, a reframe. Two frames of the same time, before and
  after, go in one preview with `compare: true`.
- **A range** (`file.exportMedia` with `range: "custom"` and `startSeconds`, `endSeconds`) for
  anything about time: a cut, a transition, a music edit, the pace of a scene. Which range is
  your judgment for the moment: one transition with a second either side, one scene, or the
  whole cut (`range: "entire"`) when the whole is the question. There is no fixed length.
- Render previews small unless quality is the point: half the sequence size and H.264 is enough
  to judge a cut, and it exports fast (72 frames of 960x540 in half a second on a CPU engine,
  where full 1080p ran at about 10 frames a second). For a grade or a title, export at full size.
- A ProRes or other mezzanine export previews too: the tool shows a light H.264 copy and leaves
  the file alone.
- Preview at the end of each stage and before each checkpoint, with a caption that says what
  changed; not after every command. `look: true` hands you the frame, or four frames of a range,
  when you need to check your own work first.

## Taste

**Cutting.** Cut on action, on a look, or when the shot has told its information. Hold a reaction
long enough to land. A straight cut is the default; a dissolve says time passed; a dip to black
ends a chapter; skip novelty transitions unless the style asks for them. Hear the next line
before you see its speaker (a J cut). Cut music at its phrase changes, not on every beat.

**Sound.** Dialogue first and always intelligible; music ducked under it; never dead silence
under picture. One loudness target per delivery.

**Color.** Correct before you grade. Protect skin tones. One look per film, applied once over the
cut. Keep shadow detail for phone screens.

**Titles.** One or two type families. Text never over a face, always inside the safe area, on
screen long enough to read twice.

**Honesty.** Say plainly what failed, what FilmCraft cannot do yet, and what you are unsure of.

## Cost and time

The engine costs credits every minute it runs, by its tier; your instructions list the tiers and
their prices. Say the tier, the price a minute, and your estimate before you start it.

- Start the engine when there is something to cut, and stop it (`engine_stop(engine_id)`, after
  `file.save`) when the person goes away to decide or the stage's work is done. A new engine
  opens on the same project folder.
- A retake or a missing shot is generated without the editor. When that wait is long, save,
  stop the engine, generate, then start the editor again and import the new take.
- Exports: FilmCraft's software H.264 export ran at about 10 frames a second at 1080p on four
  cores; try `hardwareEncoding: "auto"` on a GPU engine. Say how long an export will take before
  you start it.

## Saving the work

`file.save` after every stage keeps the project in the project folder. With a repository linked,
keep the cut's decisions with the film's other documents: `github_save("edit/notes.md", content,
message)` with the cut decisions, the music cues, and the export settings and paths. It commits
to your own branch, never the default one.

## What is not possible yet

editing.md ends with the full list ("Where FilmCraft has no equivalent yet"). The ones a person
meets first:

- **Speech to text** is off in FilmCraft's release builds: captions are written from the
  script's dialogue, not transcribed.
- **Generating inside the editor** does not exist: a new or longer shot is a new
  `generate_video` take (the `movie` skill), imported like the others.
- **Delivery codecs:** a Linux engine delivers H.264 or ProRes; no AV1, and no H.265.

## Hand-offs

Work moves as files in the project folder, in `handoff/<from>-to-<to>/`, as the `studio` skill
says. FilmCraft's side:

- **In.** Library entries (takes, stills, music the person supplied) come with
  `engine_import(engine_id, tags)`. A score or designed sound made in SoundCraft arrives as
  files with a cue list; the `soundcraft` skill says where it puts them and at which times they
  start. Confirm each file with `engine_files(engine_id, path)` before `file.import`.
- **Out, a frame for a poster.** `file.exportFrame` into `handoff/filmcraft-to-photocraft/`; the
  `photocraft` skill has the recipe from there.
- **Out, the cut for a score.** `file.exportMedia` of the locked cut with its dialogue, as one
  movie file in the project folder, with the frame rate and the times that matter (scene starts,
  hits); the `soundcraft` skill has what it needs and how it imports it.
- Read the receiving engine's skill before you promise a route, and `file.save` before another
  engine opens what you exported.

## Credits

FilmCraft's own documentation (`docs/agents.md`, `docs/control-protocol.md`, `docs/captions.md`,
`docs/gaps.md`) and command registry define the commands used here. From
storytold/craft-ai-integrations: its gateway's find, describe, then call discovery, which
`engine.commands` follows here. storytold/craft-skills holds no skills yet; its shared agent
rules explain why FilmCraft's labels avoid other products' names (Premiere's Lumetri Color is
"Color Grading", effect id `lumetri`).
