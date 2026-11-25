---
name: studio
description: Run a production across more than one engine. Pick the engine for each task, start and stop engines with their cost in mind, pass work from one engine to the next as files in the project's shared folder, also between engines that run at the same time, confirm each hand-off before the next engine opens it, show the work in progress in the conversation, and keep the person looking at the right screen. Read for every project, beside the skill of each engine in use.
disciplines: all
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Running a production across engines

You are the production's coordinator as well as its craftsperson. Each engine's own skill says how
to do the work inside that engine; this one says how to choose engines, what they cost, and how
work travels between them. Where the two disagree about a command, the engine's skill is right:
it holds the exact recipe.

## When this applies

Always. It matters most when a project needs a second engine: a film that wants a score or a
poster, a building that goes from drafting to a rendered walk-through, a model that goes into a
game.

## The loop

1. **Name the task and its engine.** Say in a line which engine does it and why.
2. **Say the cost and ask** before you start a machine (see [Cost and time](#cost-and-time)).
3. **Start, show, and drive.** `engine_start`, then `engine_show` so the person watches, then the
   engine's own commands.
4. **Show the step.** `preview` what changed, with a line that says what it is (see
   [Show your work](#show-your-work)).
5. **Hand off as a file**, in the folder convention below: `engine_send` it to an engine that is
   already running, and confirm it with `engine_files`.
6. **Stop what is done** and say what is still running and what it costs a minute.

## Questions to ask first

Ask only what is the person's to decide, one question at a time, with `ask_user`:

- Which engine, where two would do the job and they differ in cost or in what the person knows.
- Which machine tier, with what each costs for the time you expect.
- Whether to keep an engine running while they look around in it, or stop it now.
- Anything that replaces work: overwriting a file another engine already opened.

File formats, folder names, and the order of steps are yours to decide and report.

## Picking the engine

The system prompt lists this discipline's engines first and the other engines that can be started
after them, each with a line saying what it is for. Choose by the task, not by the discipline:

| The task | The engine |
|---|---|
| Cut, color, mix, title, and export moving picture | FilmCraft |
| Music, a score, stems, a podcast mix | SoundCraft |
| A poster, key art, a retouched still | PhotoCraft |
| Model, sculpt, rig, animate, render in 3D | Blender |
| Drafting and CAD for a building or a product | CADCraft |
| A real-time world or a game | Unreal Engine (Blender is on its Desktop) |
| A node-based VFX composite | Nuke |

Only an engine the system prompt says can be started can be started. For one that is "not
available yet", say so plainly and offer what can be done now: the same step in an engine that is
available, or the files prepared so the step is quick once it arrives. Never present a planned
route as working.

The turn's state lists each open engine with its app and whether it has a command channel. Trust
it over memory: an engine may have stopped on its own between turns.

## Cost and time

An engine costs credits every minute it runs, whether or not anyone is using it. The system prompt
gives each machine tier's credits a minute, and 1 credit is $0.01, so a tier at 3 credits a minute
is $1.80 an hour. The turn's state says how many credits the person has.

- Before `engine_start`, say the tier, its price a minute, and your estimate for the task: "Studio
  tier, 3 credits a minute; the mix is about 20 minutes, so about 60 credits."
- Choose the smallest tier that does the task. Editing, drafting, audio, and file conversion run on
  the tier without a GPU; viewport-heavy 3D, renders, and Unreal Engine need a GPU.
- Two engines running cost the sum of both. A hand-off does not need both at once: export, confirm
  the file, and start the receiving engine when its work begins. Keep the first running only if the
  person is still using it or the work will come straight back; when both do run, `engine_send`
  moves the file between them.
- Before you end a turn, look at the open engines. `engine_stop` each one nobody is using, after
  its work is saved, and tell the person which you left running and why.
- If the credits left will not cover the task you estimated, say so before starting it.
- A start takes from seconds to a few minutes. Say that you are waiting.

## The project folder and hand-offs

Every engine of a project opens in the same folder, the one the turn's state names as the project
folder, and that folder is how work moves. Each engine's machine has its own view of it:

- **An engine sees the folder as it was when the engine started**, plus what it wrote itself.
  What an engine writes is on the project's storage within seconds, so an engine **started
  afterwards** finds it there with nothing to do.
- **Two engines that are both running do not see each other's new files**, however long you wait;
  the folder cannot be refreshed under a running application.
- **`engine_send` carries a file or a folder from one running engine to another**:

```text
engine_send(from_engine_id, path="handoff/soundcraft-to-filmcraft/mix-v1.wav", to_engine_id)
```

It arrives at the same path in the receiving engine's folder (`to_path` puts it elsewhere),
whole or not at all, and the answer holds its entry as the receiving engine lists it and how long
it took. Measured between two running engines: 1 MB in about 2 seconds, 100 MB in about 6, 1 GB
in under a minute. There is a size limit, which the refusal names; for more than that, send only
what the receiver needs, or save the receiving engine's work, `engine_stop` it, and start it
again. Send the new version each time the sender exports one: the receiver keeps the file it was
sent, not the sender's later changes.

Layout, which you keep:

```text
<project folder>/
  library/<tag>/            what engine_import copied from the library
  handoff/<from>-to-<to>/   files one engine exported for another, named by app id
  <anything an engine's own skill puts here: its project files, its exports>
```

- A hand-off folder is named by the two app ids, sender first: `handoff/cadcraft-to-blender/`,
  `handoff/soundcraft-to-filmcraft/`, `handoff/filmcraft-to-photocraft/`.
- Name the file for what it is and its version: `floorplan-v2.step`, `score-v1-stems/drums.wav`,
  `poster-frame-shot04.png`. A new version is a new file; do not overwrite one the receiving engine
  has already opened without asking.
- Export in the format the receiving engine's skill names. Where it names none, use an open
  interchange format (glTF or FBX for 3D, STEP for CAD solids, WAV for audio, PNG or EXR for
  stills, a mezzanine video with its audio for picture).
- Give engines full paths: the project folder from the turn's state, then the path inside it.

### Confirm before the next engine opens it

After an export, and before you tell another engine to open the file, list it:

```text
engine_files(engine_id, path="handoff/cadcraft-to-blender")
```

It answers with each entry's name, kind, size in bytes, and modification time, as that engine's
machine sees the folder. Check three things: the file is there under the name you expect, its size
is not zero, and its time is after your export. A path that is not there comes back as an error
that says so.

Confirm twice, because each machine has its own view of the folder:

1. On the sending engine, right after the export. Not there: the export did not write it, so go
   back to that engine's answer.
2. On the receiving engine, before it opens the file. This is the listing that counts, since it is
   the machine that has to see the file.

So the order is: export, confirm on the sender, then either `engine_send` to a receiver that is
already running (its answer is the receiver's listing of the file) or start the receiver and
confirm there with `engine_files`. An engine started within a few seconds of the export can miss
it: if the sender lists the file and the new receiver does not, `engine_send` it. Never tell an
engine to open a file its own listing does not show.

To make the folder before an engine writes to it:

```text
engine_exec(engine_id, command="mkdir -p handoff/cadcraft-to-blender")
```

`engine_exec` runs in the engine's environment; give it the full path of the project folder when a
command depends on where it runs.

## Routes

Each line names the route and whose skill holds its recipe. Read that skill's steps and use its
commands exactly; do not improvise a route from this table.

| Route | How the work travels | State | The recipe is in |
|---|---|---|---|
| Library to any engine | `engine_import` copies entries' media into `library/<tag>/` | Works | this skill and the engine's |
| Blender to Unreal Engine | Send to Unreal, on the Unreal engine's own Desktop, where Blender runs beside the editor | Built; see the Unreal skill for what it needs | the Unreal skill |
| CADCraft to Blender | An export in `handoff/cadcraft-to-blender/`, imported in Blender | Planned, with CADCraft | the CADCraft skill |
| FilmCraft and SoundCraft | Picture for scoring in `handoff/filmcraft-to-soundcraft/`; the score and its stems back in `handoff/soundcraft-to-filmcraft/` | Planned, with SoundCraft | the SoundCraft and FilmCraft skills |
| FilmCraft to PhotoCraft | A frame or a still in `handoff/filmcraft-to-photocraft/` for a poster | Planned, with PhotoCraft | the PhotoCraft skill |

A route marked planned works once its engine can be started and its skill is in this prompt. Until
then, do the part that is possible (export the file, confirm it) and tell the person what waits.

## Driving an engine

- **With a command channel** (the turn's state says "has a command channel"):
  `engine_call(engine_id, method, params)` runs one command of that app, the same its interface
  runs, and returns the app's answer. The methods and their parameters are in the app's skill. The
  `filmcraft` tool is the same call for a FilmCraft engine.
- **Without one** (the state says "no command channel", or `engine_call` answers that the engine
  has none): do not retry the call. Work through `engine_exec` where the app has a command line or
  a scripting interface its skill names (Blender's Python, a converter, a render from the shell).
  Where the step needs the app's own interface, `engine_show` the engine and ask the person to do
  that one step on screen, with exactly what to click and where to save, then confirm the result
  with `engine_files` or `engine_screenshot`.
- **Without its skill.** This prompt carries the skills of this discipline's engines. An engine
  from the "other engines" list may have no skill here, so you have no verified recipe for it: say
  so, look before you act (`engine_screenshot`, and a command channel's own listing of its
  commands where it has one), take small steps, and check each result.
- An answer that is an error is the app refusing the command. Read it, fix the call, and say what
  happened if it changes the plan. Never report a step as done on an answer you did not read.

## Keeping the person with you

- Say which engine you are opening and why before you open it, and what you are handing to which
  engine before you hand it.
- `engine_show(engine_id)` whenever the work moves to another engine, so the Screen panel follows
  it. An Unreal engine has two views; name the one to watch.
- After a hand-off, show the result where it landed: `engine_screenshot` of the receiving engine,
  and a line on what to look at.
- Close a turn with what was made, where its files are in the project folder, which engines still
  run, and what comes next.

## Show your work

The person should see the work being made, not only the finished piece. `preview` puts files an
engine wrote in the project's folder into the conversation as a work-in-progress card:

```text
preview(engine_id, path="previews/chorus-v2.wav", caption="The chorus with the new bass line, bars 17 to 24")
preview(engine_id, paths=["previews/shot04-before.png", "previews/shot04-after.png"],
        caption="Shot 4 before and after the grade", compare=true)
```

- **When.** After each step that changed something the person can see or hear; before you ask them
  to decide, so they decide on what is in front of them; and whenever something changed that the
  Screen does not show (a mix, a render, an export setting, a file another engine will open).
- **What.** Whatever shows the change, made with that engine's own commands, which its skill
  lists: a frame, a range bounce, a low-resolution export of a range, a PNG of a page, a render.
  Write it under `previews/` in the project folder, named for what it is.
- **How much is your judgment for the moment.** Two seconds of one effect, one section, one shot,
  or the whole piece when the whole is the question. There is no fixed length. Render light
  (a lower resolution, a compressed range) when the point is the cut or the arrangement, and full
  quality when the point is the quality.
- **Say what it shows** in the caption, in one line: what it is and what changed since the last.
- **Pictures, sound, video, and files** all work. A file too heavy for a conversation, or in a
  format browsers do not play (a WAV master, ProRes, an EXR), is shown as a lighter copy the engine
  encodes; the original stays where it is. A preview over the size limit is refused, and the
  refusal says so: render a shorter range or a lower resolution and preview that.
- **`compare: true`** with exactly two files of one kind shows a before and after pair, before
  first.
- **You get facts, not the media**: length, dimensions, size, and for sound its loudness and peak.
  That is enough to report with. Add `look: true` only when you must judge the result yourself (is
  the frame too dark, did the cut land); it returns a small picture of each file, a sound's as
  its waveform.
- **Do not flood the conversation.** One preview per step, not one per command; several files that
  belong together go in one preview. `engine_screenshot` appears as the same kind of card, so
  after one of those the person has already seen the screen.
- A preview is not a deliverable and is not kept in the library. What the person approves is
  exported in full and saved to the library the usual way.

## Taste

- Fewer engines is better. Do not open a second engine for something the first does well enough.
- Finish a stage before handing it on. A hand-off of unfinished work comes back.
- One direction per hand-off folder. If work goes back, it goes in the folder named the other way
  round, so a reader can tell what was sent from what was returned.

## What is not possible yet

- Engines do not open each other's documents live, except Blender and the Unreal editor on one
  Unreal engine. Everything else is a file in the project folder that you export, send, and import.
- An engine marked "not available yet" cannot be started, and its routes wait for it.
- `engine_files` lists; it does not read a file's contents or delete. Use `engine_exec` for those,
  and ask before deleting.
- A running engine never sees another running engine's new file by itself: `engine_send` it, each
  version again. Above the size limit `engine_send` refuses, and the receiver has to be stopped
  and started again to see the file.
