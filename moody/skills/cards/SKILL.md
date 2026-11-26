---
name: cards
description: Answer with an interactive card when the person should see, try, and decide rather than read and reply. A look tuned by sliders over the frame itself, a lead picked from portraits, a style chosen from boards, a poster taken apart into layers, a 3D model turned to its hero angle, a storyboard put in order, a budget read off a chart, or a small application of your own. Covers when a card beats a question or a preview, how to write one with show_ui, the catalog of components with worked examples, when to write custom HTML and its rules, and what comes back when the person locks a card in.
disciplines: all
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Answering with a card

Some answers are easier to make than to describe. "A bit warmer, less grain" takes three round
trips in words and one drag of a slider over the frame. `show_ui` puts a small interface in the
conversation: the person sees the real material, tries things, and presses one button to lock in
what they chose, which comes back to you as their answer.

## When this applies

Use the lightest thing that settles the matter:

| The moment | Use |
|---|---|
| One of a few answers that need no picture | `ask_user` |
| Work in progress to look at, nothing to decide | `preview` |
| One choice that sets where the work goes next: a kind, a way in, a platform | `show_ui` with `instant` |
| A decision made by looking, hearing, comparing, ordering, or tuning | `show_ui` with `submit` |
| Something the person has and you need: a track, a script, a logo, footage | `show_ui` with an `upload` |
| Something to explore that sends nothing back: a model to turn, a chart to read | `show_ui` without `submit` |

A card earns its place when the choice is a value on a scale (how warm, how loud, how long), a
pick among things that have to be seen (faces, frames, palettes), an order, an angle, or several
settings that only make sense together. It does not when the answer is a word: do not put a yes
or no in a card. Do not use a card as an intake form either. Questions about the project go one at
a time, in the conversation.

## The loop

1. **Have the real material first.** Generate the candidates, render the frame, export the model.
   A card over a placeholder asks about nothing.
2. **Say in a line what locking in will do**: "Lock in the look and I grade the whole scene to
   match." The person should know the consequence before they touch a slider.
3. **Show the card.** `waits: true` when you cannot go on without the answer: your turn ends, and
   the person's locked-in values start the next one. Leave `waits` out when you can keep working;
   the card stays answerable, and its values arrive in a later message of theirs. Where the card
   is one choice and nothing else, give `instant: true` in place of `submit`: the choice itself
   locks it, so the person answers in one press.
4. **Act on exactly what came back**, record it (the plan, the library entry's metadata), and say
   what you did. Then show the real result (see [Show your work](#show-your-work)).

One card waits at a time. A card that was locked in cannot be reopened: to revisit a choice, show
a new card that starts from the values they chose.

## What comes back

The person's next message carries the card's answer.

- A `components` card answers with an object of your input ids: `{"warmth": 30, "grain": 82}`.
  The tool's result lists what each id answers with. In short: a slider or number, a number; a
  select, segmented, or pick, the option's `value` (a list with `many`); checkboxes, a list of
  values; a toggle, true or false; a field, the words; a color, `#rrggbb`; a reorder, the values
  in the person's order; tabs with an id, the open tab's `value`; a table with an id, the first
  cell of each picked row; a model with an id, `{"azimuth", "elevation", "zoom"}`; layers with an
  id, `{"selected", "layers": {name: {"visible", "opacity"}}}`; an upload, `{"tag", "name",
  "kind"}` for the file the person gave, or null where they gave none.
- A file from an `upload` is in the project's library by the time the answer arrives: name it by
  its `tag` wherever a tool takes one, as you would any other entry.
- An `html` card answers with whatever its document last passed to `moody.setState`, or to
  `moody.submit`.

Choose ids and option values you will want to read: `warmth`, `lead`, `"neon-noir"`, not `s1`. The
person may also answer in words instead of locking in; then their words are the answer, and
nothing they left on the card counts. Never act on a value they did not send.

## Recipes

The tool's own definition lists every component and property, so this section is how to combine
them. A card is one component, usually a `stack`, with the rest in `children`. Inputs have an
`id`. A property marked `~` in the tool's reference can follow an input as `"$id"`; a text shows
an input's value as `{id}`; any component takes `when` to appear only while a condition holds. An
input opens on the `value` you give it, and once the person changes anything the card offers
"Back to default", which restores it as it opened.

### A look, tuned over the frame

The frame is an engine's file here; a library entry would be `{"tag": "@market"}`. `compare` puts
the untouched frame left of a divider and the adjusted one right of it, and each adjustment
follows a slider. Give each slider the value the card should open on.

```json
{
  "title": "The look of the night market",
  "components": {"type": "stack", "children": [
    {"type": "compare", "before": "shot", "after": "shot",
     "adjust": {"warmth": "$warmth", "contrast": "$contrast", "grain": "$grain", "vignette": "$vignette"}},
    {"type": "row", "children": [
      {"type": "slider", "id": "warmth", "label": "Warmth", "min": -100, "max": 100, "value": 18},
      {"type": "slider", "id": "contrast", "label": "Contrast", "min": -100, "max": 100, "value": 12}]},
    {"type": "row", "children": [
      {"type": "slider", "id": "grain", "label": "Grain", "value": 20},
      {"type": "slider", "id": "vignette", "label": "Vignette", "value": 25}]}]},
  "submit": "Lock in this look",
  "waits": true,
  "media": [{"name": "shot", "engine_id": "ENGINE", "path": "previews/shot03.png"}]
}
```

### A pick among candidates, with room for a note

`pick` shows each option as its picture and needs a choice before the card can be locked in.

```json
{
  "title": "Cast the lead",
  "components": {"type": "stack", "children": [
    {"type": "pick", "id": "lead", "label": "Who carries the film?", "options": [
      {"value": "mara", "label": "Mara", "image": "mara", "note": "Night courier. Guarded, quick."},
      {"value": "iris", "label": "Iris", "image": "iris", "note": "Street musician. Hopeful."},
      {"value": "theo", "label": "Theo", "image": "theo", "note": "Repairman. Has seen it all."}]},
    {"type": "field", "id": "note", "label": "Anything to change about them?", "lines": 2}]},
  "submit": "Cast this lead",
  "waits": true,
  "media": [{"tag": "@mara"}, {"tag": "@iris"}, {"tag": "@theo"}]
}
```

### Directions as boards

`tabs` with an `id` makes the open tab the answer, so each direction gets a whole board: its
references, its palette, a line on what it means. Give each tab a `value` you will read.

```json
{
  "title": "An art style for the film",
  "components": {"type": "stack", "children": [
    {"type": "tabs", "id": "style", "children": [
      {"type": "tab", "label": "Neon noir", "value": "neon-noir", "children": [
        {"type": "gallery", "columns": 2, "items": ["noir_street", {"src": "noir_towers", "caption": "Towers lost in fog"}]},
        {"type": "swatches", "label": "Palette", "colors": ["#0d0b1a", "#3b2a6b", {"color": "#e8a04a", "label": "Sodium"}]},
        {"type": "text", "tone": "muted", "text": "High contrast, long lenses, light from signs and windows only."}]},
      {"type": "tab", "label": "Storybook", "value": "storybook", "children": [
        {"type": "gallery", "columns": 2, "items": ["book_island", "book_robot"]},
        {"type": "swatches", "label": "Palette", "colors": ["#1c1410", "#8a4b2a", "#e9a03b"]}]}]},
    {"type": "segmented", "id": "push", "label": "How far to push it", "options": ["Subtle", "Balanced", "Bold"], "value": "Balanced"}]},
  "submit": "Go with this style",
  "waits": true,
  "media": [{"name": "noir_street", "tag": "@market-street"}, {"name": "noir_towers", "tag": "@spire-city"},
            {"name": "book_island", "tag": "@island"}, {"name": "book_robot", "tag": "@pip"}]
}
```

### A kind, picked in one press

For a choice that opens a path, show the options as tiles and let the press be the answer. Each
option of a `pick` may carry an `icon`: a pixel drawing as rows of `0` and `1`, a square of 8 to
16 cells. Tiles with icons are squares, two or three to a row, with the label and the note under
the icon. Draw one plain idea per icon; eight cells are enough for a shape, twelve for an object.
With `instant: true` there is no lock-in button and no `submit`, and the card may hold nothing
else to set: one `pick` without `many`, or one `segmented`. The kind of a new project is asked
this way by the conversation itself before your first turn; use the same shape for the forks
that follow it.

```json
{
  "title": "What shape is the piece?",
  "components": {"type": "pick", "id": "shape", "columns": 3, "options": [
    {"value": "vertical", "label": "Vertical", "note": "9:16, for a phone held upright",
     "icon": ["00111100", "00100100", "00100100", "00100100", "00100100", "00100100", "00111100", "00000000"]},
    {"value": "square", "label": "Square", "note": "1:1, for a feed",
     "icon": ["00000000", "01111110", "01000010", "01000010", "01000010", "01000010", "01111110", "00000000"]},
    {"value": "wide", "label": "Wide", "note": "16:9, for a screen",
     "icon": ["00000000", "00000000", "11111111", "10000001", "10000001", "11111111", "00000000", "00000000"]}]},
  "instant": true,
  "waits": true
}
```

### Sounds, compared by ear

When you have two or three takes of a sound (an effect, a voice, a cue), do not describe them:
give each option of a `pick` its `audio`, the name of one of the card's files. Each tile then
plays its take, with its waveform and position, over the control that chooses it, and starting
one stops the other, so the person hears them back to back and picks. Keep the labels short
("A · Bell") and put what differs in the note. Three takes are a comparison; six are a chore.

```json
{
  "title": "The lantern's chime",
  "components": {"type": "pick", "id": "take", "label": "Which take?", "columns": 3, "options": [
    {"value": "bell", "label": "A · Bell", "audio": "bell", "note": "Bright, rings out"},
    {"value": "gong", "label": "B · Gong", "audio": "gong", "note": "Low, slow to bloom"},
    {"value": "knock", "label": "C · Knock", "audio": "knock", "note": "Dry, a short ring"}]},
  "submit": "Use this take",
  "waits": true,
  "media": [{"name": "bell", "engine_id": "ENGINE", "path": "audio/chime-bell.wav"},
            {"name": "gong", "engine_id": "ENGINE", "path": "audio/chime-gong.wav"},
            {"name": "knock", "engine_id": "ENGINE", "path": "audio/chime-knock.wav"}]
}
```

### The other shapes, in a line each

- **An order**: `{"type": "reorder", "id": "order", "options": [{"value": "s1", "label": "The market wakes", "image": "s1", "note": "Wide, 6s"}, ...]}`.
- **Layers**: `{"type": "layers", "id": "poster", "layers": [{"name": "Sky", "src": "sky"}, {"name": "Lanterns", "src": "lanterns", "blend": "screen"}]}`, the first at the bottom. Each layer is a picture of the full canvas with transparency.
- **A 3D model**: `{"type": "model", "id": "angle", "src": "pip", "finish": "$finish", "spin": true}` beside a `segmented` whose id is `finish` and whose options are finishes. The file is a `.glb`: export one from Blender into the project's folder and name it in `media`.
- **A table to pick from, and a chart that follows it**: a `table` with `id` and `pick: "many"`, and a `chart` whose `highlight` is `"$<the table's id>"` and whose labels are the rows' first cells. `kind` is `bar` to compare, `line` or `area` over an ordered axis, `share` for the parts of one whole (six at most).
- **Sound to listen to**: `{"type": "audio", "src": "cue", "label": "A · Slow harbor pad"}` plays a file with its waveform. To choose between sounds, use tiles that play (above).
- **A file from the person**: `{"type": "upload", "id": "track", "label": "The track", "accept": "audio", "section": "Music"}` takes a file they drop or pick (`accept` is `audio`, `image`, `video`, or `any`) into the library's `section`, and shows it once it is in. Ask for a file only when they may have one, and give the other way out beside it: a `pick` of "I have it" and "Make one with me", with the `upload` shown `when` the first is chosen and a `field` for the second.
- **A follow-up only where it applies**: `{"type": "field", "id": "instead", "required": true, "when": {"cue": "neither"}}`.

## Custom HTML

Write `html` when the card needs logic of its own: a simulation, sound made or processed in the
browser (Web Audio), a drawing surface, a timeline to scrub, a gesture the catalog has no control
for. Do not write it to restyle what the catalog already does; a `components` card is checked,
accessible, and a tenth of the tokens.

The document runs in a sandboxed frame. It cannot reach the network or the page, and anything it
tries to load from an address (a script from a CDN, a web font, an image by URL, a `fetch`) fails.
Everything is inline, and files come through `media`.

- **`window.moody`** is there before your script runs: `moody.state` (null at first, your last
  value when the card is shown again), `moody.locked`, `moody.media.<name>` (an address for an
  `img`, `audio`, or `video` element), `await moody.load(name)` (the file's bytes as an
  `ArrayBuffer`, for `decodeAudioData` or reading pixels), `moody.setState(value)`, and
  `moody.submit(value)`.
- **Report on every change**: call `moody.setState(value)` whenever the person changes something,
  and once at the start if the starting values are an answer. The lock-in button sends the last
  value. Use `moody.submit(value)` only for a gesture that is itself the answer, such as a
  double-click on the chosen frame. It is ignored unless the person is in the card.
- **The document's first state is the card's default.** "Back to default" starts your document
  again from the top, so whatever it draws before the person touches it is what they return to.
- **Make the value small, named JSON** you will want to read: `{"low": 3, "mid": -2, "high": 4}`.
- **Start from `moody.state`** when it is set, and when `moody.locked` is true (or on the window's
  `moodylock` event) show the value and disable the controls.
- **Look like the conversation**: use `var(--moody-fg)`, `--moody-muted`, `--moody-line`,
  `--moody-surface`, `--moody-bg`, `--moody-lime` (what the person chose or does), `--moody-lavender`
  (yours), `--moody-font`, `--moody-mono`. Leave the page's background alone; it is clear on
  purpose. Plain `button`, `input`, `select`, and `input type="range"` are already styled.
- **Fit any width.** The card may be 300 pixels wide on a phone. Use percentages and `aspect-ratio`
  for a canvas; the frame's height follows the document.
- **Respect reduced motion**: where `matchMedia('(prefers-reduced-motion: reduce)').matches`, draw
  a still frame and offer a Play button instead of animating.
- **Use real controls with labels**, so the card works by keyboard.
- **Sound starts on a click**: create the `AudioContext` in the handler of a button.
- **Never navigate**: setting `location`, a link to follow, or a form to submit stops the card.

A whole card, small enough to read:

```json
{
  "title": "Tap the tempo of the chase",
  "html": "<style>.tap{display:flex;align-items:center;gap:12px}output{font:600 28px var(--moody-mono)}p{margin:8px 0 0;color:var(--moody-muted);font-size:12px}</style><div class=\"tap\"><button id=\"tap\" type=\"button\">Tap</button><output id=\"bpm\">--</output><span>beats a minute</span></div><p>Tap along to the cut in your head, at least four times.</p><script>const taps=[];const out=document.getElementById('bpm');const button=document.getElementById('tap');const show=(bpm)=>{out.textContent=bpm?String(bpm):'--'};show(moody.state&&moody.state.bpm);button.disabled=moody.locked;button.addEventListener('click',()=>{const now=performance.now();if(taps.length&&now-taps[taps.length-1]>2500)taps.length=0;taps.push(now);if(taps.length>=4){const bpm=Math.round(60000*(taps.length-1)/(now-taps[0]));show(bpm);moody.setState({bpm:bpm});}});addEventListener('moodylock',()=>{button.disabled=true});</script>",
  "height": 140,
  "submit": "Cut to this tempo",
  "waits": true
}
```

## Taste

- **One decision per card.** Six inputs is a good ceiling. Two decisions are two cards, or one
  card now and a question later.
- **Real media, never a stand-in.** The frame they are grading is the frame.
- **The card carries no opinion.** If you have a view, say it in a sentence of your message
  before the card.
- **Ranges where every position is plausible.** A warmth slider that only looks right between 10
  and 30 should not run from -100 to 100.
- **Their words, with units**: "Hold" with `unit: "s"`, not `duration_frames`.
- **The button says what happens**: "Lock in this look", "Cast this lead", never "Submit".
- **One press where one press is the answer.** A card that only asks which way to go is
  `instant`; a card with anything to tune or compare keeps its button, so trying costs nothing.
- **The title says what the card is**, in a few words; the consequence goes in your message.
- **Hide what does not apply** with `when` rather than showing a control that does nothing.
- **Do not ask what you can decide.** File formats, bitrates, and layer names are yours.
- **A chart is one series doing one job.** Two numbers are a sentence, not a chart.

## Cost and time

A card costs no credits. What it shows may: candidates you generate cost what generation costs,
and a file an engine wrote needs that engine running when you call `show_ui` (the file is copied
into the conversation then, so the engine can stop afterwards). A card's definition stays in the
conversation, so keep it to what the decision needs.

## What is not possible yet

- **A card cannot call you while it is open.** There is no "regenerate" inside a card: everything
  it shows is fixed when you show it, and you hear from it once, at lock-in.
- **The adjustments are the browser's approximation**, not an engine's grade. Treat the numbers as
  intent, reproduce them with the engine's own tools, and show the real result.
- **Nothing a card stores survives it**, except a file given to an `upload`, which is in the library.
- **An `html` card cannot take a file or be `instant`.** Where a gesture in it is the answer, the
  document calls `moody.submit`.
- **3D is a `.glb` only**, shown still or turning: no animation playback, no editing.
- **The `audio` component plays a file as it is.** Processing sound needs an `html` card.
- **Limits**: a card may have 120 components, 8 levels deep, in 24,000 bytes; 60 items in any
  list; 24 files; an `html` document of 200,000 bytes. A card over a limit, or one that names a
  component, property, or file that does not exist, is not shown: the result says what to fix, and
  you call `show_ui` again.

## Show your work

A locked-in look is a request, not a result. After you act on it in an engine, `preview` the
engine's own output, as a before and after pair where that helps, so the person sees what their
choice became rather than what the card's approximation suggested.
