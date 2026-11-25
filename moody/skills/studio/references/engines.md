<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Working in engines

How a running engine is driven, how work passes between engines as files of the project folder,
and how work in progress is shown in the conversation. It applies to every engine; an engine's
own skill has the commands of its application. When to start an engine at all, and when to stop
it, is the skill's "Engines only when needed".

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
- **Without its skill.** An engine from the "other engines" list may have no skill this project
  can read, so you have no verified recipe for it: say so, look before you act
  (`engine_screenshot`, and a command channel's own listing of its commands where it has one),
  take small steps, and check each result.
- An answer that is an error is the app refusing the command. Read it, fix the call, and say what
  happened if it changes the plan. Never report a step as done on an answer you did not read.

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
  previews/                 what an engine rendered to show in the conversation
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

A route is one engine's export opened by another. Its recipe, its file format, and whether it
was verified are in the skills of the two engines, under their hand-offs: read both before you
promise a route, and use their commands exactly. A route neither skill describes has no verified
recipe: say so, do the part that is possible (export the file, confirm it), and tell the person
what waits. Two routes are this skill's own:

| Route | How the work travels |
|---|---|
| The library to any engine | `engine_import(engine_id, tags)` copies the entries' media into `library/<tag>/` and returns the paths |
| Between two engines that are both running | `engine_send`, as this file's hand-offs say |

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
  exported in full, and generated pictures and video are kept in the library by the call that
  makes them (`save_to`).
- `preview` shows files of a running engine. What was generated needs no preview: it appears in
  the conversation by itself.
