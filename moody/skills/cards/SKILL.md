---
name: cards
description: Answer with an interactive card when the person should see, try, and decide rather than read and reply. A look tuned by sliders over the frame itself, a lead picked from portraits, a style chosen from boards, a poster taken apart into layers, a 3D model turned to its hero angle, a storyboard put in order, a budget read off a chart, or a small application of your own. Covers when a card beats a question or a preview, how to write one with show_ui, the catalog of components with worked examples, how to recommend the answer every card opens on, when to write custom HTML and its rules, and what comes back when the person locks a card in.
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
| A decision made by looking, hearing, comparing, ordering, or tuning | `show_ui` with `submit` |
| Something to explore that sends nothing back: a model to turn, a chart to read | `show_ui` without `submit` |

A card earns its place when the choice is a value on a scale (how warm, how loud, how long), a
pick among things that have to be seen (faces, frames, palettes), an order, an angle, or several
settings that only make sense together. It does not when the answer is a word: do not put a yes
or no in a card. Do not use a card as an intake form either. Questions about the project go one at
a time, in the conversation.

## The loop

1. **Have the real material first.** Generate the candidates, render the frame, export the model.
   A card over a placeholder asks about nothing.
2. **Decide what you would answer.** Every card that asks carries your recommendation (see
   [Recommend an answer](#recommend-an-answer)).
3. **Say in a line what locking in will do**: "Lock in the look and I grade the whole scene to
   match." The person should know the consequence before they touch a slider.
4. **Show the card.** `waits: true` when you cannot go on without the answer: your turn ends, and
   the person's locked-in values start the next one. Leave `waits` out when you can keep working;
   the card stays answerable, and its values arrive in a later message of theirs.
5. **Act on exactly what came back**, record it (the plan, the library entry's metadata), and say
   what you did. Then show the real result (see [Show your work](#show-your-work)).

One card waits at a time. A card that was locked in cannot be reopened: to revisit a choice, show
a new card. Recommend what they chose then, unless you now think otherwise, and say which it is.

## Recommend an answer

A card with `submit` puts a decision to the person, and you never put a decision to them without
the answer you would give. Whatever the card is about (a filter, a grade, the shadows, a motion, a
3D angle, an order), it opens on your recommendation. The page marks the option you chose with a
quiet "(recommended)", says beside the lock-in button that the card is as you recommend, and once
the person changes anything keeps your answer in sight with one click back to it. Locking the card
in untouched is the person saying yes.

The reason is the person's time and your job. They came to you for taste, so a card that opens
blank, at zero, or on whichever option was written first hands the weighing back to them. With a
recommendation, agreeing costs one click, disagreeing starts from something considered, and they
learn how you see their film.

How a card states it (the properties marked `!` in the tool's reference):

- **An input that chooses** names the option in `recommended`: a `select`, `segmented`, or `pick`
  by the option's `value`; `checkboxes`, a `pick` with `many`, or a `table` with `pick: "many"` by
  a list of them; `tabs` with an id by the tab's `value`; a `table` with an id by the row's first
  cell. Do not write "(recommended)" into a label yourself: the page adds it.
- **An input that sets a value** starts at it: `value` on a `slider`, `number`, `toggle`, `color`,
  or `field` (`""` where you would leave the field empty), the written order of a `reorder`'s
  options, `azimuth` and `elevation` on a `model` with an id, and each layer's `visible` and
  `opacity` on `layers` with an id.
- **An `html` card** opens its document on the answer and calls `moody.recommend(value)` with it
  (see [Custom HTML](#custom-html)).

A card with `submit` that leaves one of these out is not shown, and the result says which. A card
without `submit` decides nothing and needs none.

How to recommend well:

- **From the brief and the project's taste**, not from the middle of the scale. Read what the
  person asked for, what the library's references look like, and what they locked in before: a
  film they called quiet and dusty gets grain and a low-contrast grade, not the default.
- **One answer.** Recommend the option you would ship if they never replied. With several to
  choose, recommend the exact set, and with an order, the order.
- **Say why in a line where the reason matters**: a muted `text` near the choice, in your own
  voice and specific to this project. "I'd cast Mara: her guarded look carries the night scenes,
  and her silhouette reads at thumbnail size." A slider nudged two points needs no sentence.
  Options keep their `note` for what each one is; the line is for why yours.
- **Leave room either side.** Set a slider's range so your value is not at an end, or the person
  cannot try "a little more".
- **Be honest when it is close.** Still pick one, and say it is a near call and what would tip it.
- **A required input opens answered.** A required field or pick that opens empty would leave the
  card unable to be locked in as it opens, so it is refused: recommend a name, a line, a pick. A
  follow-up shown only on a condition (`when`) may open empty, since it is out of view until the
  person leaves your recommendation.

## What comes back

The person's next message carries the card's answer.

- A `components` card answers with an object of your input ids: `{"warmth": 30, "grain": 82}`.
  The tool's result lists what each id answers with. In short: a slider or number, a number; a
  select, segmented, or pick, the option's `value` (a list with `many`); checkboxes, a list of
  values; a toggle, true or false; a field, the words; a color, `#rrggbb`; a reorder, the values
  in the person's order; tabs with an id, the open tab's `value`; a table with an id, the first
  cell of each picked row; a model with an id, `{"azimuth", "elevation", "zoom"}`; layers with an
  id, `{"selected", "layers": {name: {"visible", "opacity"}}}`.
- An `html` card answers with whatever its document last passed to `moody.setState`, or to
  `moody.submit`.

Choose ids and option values you will want to read: `warmth`, `lead`, `"neon-noir"`, not `s1`. The
person may also answer in words instead of locking in; then their words are the answer, and
nothing they left on the card counts. Never act on a value they did not send. Values equal to
what you recommended mean they agreed; any that differ are where their taste parts from yours, so
note it for the next recommendation.

## Recipes

The tool's own definition lists every component and property, so this section is how to combine
them. A card is one component, usually a `stack`, with the rest in `children`. Inputs have an
`id`. A property marked `~` in the tool's reference can follow an input as `"$id"`; one marked `!`
states your recommendation; a text shows an input's value as `{id}`; any component takes `when` to
appear only while a condition holds.

### A look, tuned over the frame

The frame is an engine's file here; a library entry would be `{"tag": "@market"}`. `compare` puts
the untouched frame left of a divider and the adjusted one right of it, and each adjustment
follows a slider. The sliders start at the look you recommend, and a line says why.

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
      {"type": "slider", "id": "vignette", "label": "Vignette", "value": 25}]},
    {"type": "text", "tone": "muted", "text": "I'd keep it warm with some grain: the brief is lantern light, and grain hides the noise in the shadows."}]},
  "submit": "Lock in this look",
  "waits": true,
  "media": [{"name": "shot", "engine_id": "ENGINE", "path": "previews/shot03.png"}]
}
```

### A pick among candidates, with room for a note

`pick` shows each option as its picture and opens on the one you recommend. The note field is
optional, so it opens empty.

```json
{
  "title": "Cast the lead",
  "components": {"type": "stack", "children": [
    {"type": "pick", "id": "lead", "label": "Who carries the film?", "recommended": "mara", "options": [
      {"value": "mara", "label": "Mara", "image": "mara", "note": "Night courier. Guarded, quick."},
      {"value": "iris", "label": "Iris", "image": "iris", "note": "Street musician. Hopeful."},
      {"value": "theo", "label": "Theo", "image": "theo", "note": "Repairman. Has seen it all."}]},
    {"type": "text", "tone": "muted", "text": "I'd cast Mara: her guarded look carries the night scenes, and her silhouette reads at thumbnail size."},
    {"type": "field", "id": "note", "label": "Anything to change about them?", "lines": 2, "value": ""}]},
  "submit": "Cast this lead",
  "waits": true,
  "media": [{"tag": "@mara"}, {"tag": "@iris"}, {"tag": "@theo"}]
}
```

### Directions as boards

`tabs` with an `id` makes the open tab the answer, so each direction gets a whole board: its
references, its palette, a line on what it means. Give each tab a `value` you will read, and name
the direction you would take in `recommended`: the card opens on that board.

```json
{
  "title": "An art style for the film",
  "components": {"type": "stack", "children": [
    {"type": "tabs", "id": "style", "recommended": "neon-noir", "children": [
      {"type": "tab", "label": "Neon noir", "value": "neon-noir", "children": [
        {"type": "gallery", "columns": 2, "items": ["noir_street", {"src": "noir_towers", "caption": "Towers lost in fog"}]},
        {"type": "swatches", "label": "Palette", "colors": ["#0d0b1a", "#3b2a6b", {"color": "#e8a04a", "label": "Sodium"}]},
        {"type": "text", "tone": "muted", "text": "High contrast, long lenses, light from signs and windows only."}]},
      {"type": "tab", "label": "Storybook", "value": "storybook", "children": [
        {"type": "gallery", "columns": 2, "items": ["book_island", "book_robot"]},
        {"type": "swatches", "label": "Palette", "colors": ["#1c1410", "#8a4b2a", "#e9a03b"]}]}]},
    {"type": "segmented", "id": "push", "label": "How far to push it", "options": ["Subtle", "Balanced", "Bold"], "recommended": "Balanced"}]},
  "submit": "Go with this style",
  "waits": true,
  "media": [{"name": "noir_street", "tag": "@market-street"}, {"name": "noir_towers", "tag": "@spire-city"},
            {"name": "book_island", "tag": "@island"}, {"name": "book_robot", "tag": "@pip"}]
}
```

### The other shapes, in a line each

- **An order**: `{"type": "reorder", "id": "order", "options": [{"value": "s1", "label": "The market wakes", "image": "s1", "note": "Wide, 6s"}, ...]}`, written in the order you recommend.
- **Layers**: `{"type": "layers", "id": "poster", "layers": [{"name": "Sky", "src": "sky"}, {"name": "Lanterns", "src": "lanterns", "blend": "screen", "opacity": 80}]}`, the first at the bottom, each with the `visible` and `opacity` you recommend. Each layer is a picture of the full canvas with transparency.
- **A 3D model**: `{"type": "model", "id": "angle", "src": "pip", "azimuth": 35, "elevation": 12, "finish": "$finish", "spin": true}` beside a `segmented` whose id is `finish`, whose options are finishes, and whose `recommended` is the one you would render. `azimuth` and `elevation` are the angle you recommend. The file is a `.glb`: export one from Blender into the project's folder and name it in `media`.
- **A table to pick from, and a chart that follows it**: a `table` with `id`, `pick: "many"`, and `recommended` listing the first cells of the rows you would pick, and a `chart` whose `highlight` is `"$<the table's id>"` and whose labels are the rows' first cells. `kind` is `bar` to compare, `line` or `area` over an ordered axis, `share` for the parts of one whole (six at most).
- **Sound**: `{"type": "audio", "src": "cue", "label": "A · Slow harbor pad"}` plays a file with its waveform; two of them over a `segmented` asks which, with yours in `recommended`.
- **A follow-up only where it applies**: `{"type": "field", "id": "instead", "required": true, "value": "", "when": {"cue": "neither"}}`.

## Custom HTML

Write `html` when the card needs logic of its own: a simulation, sound made or processed in the
browser (Web Audio), a drawing surface, a timeline to scrub, a gesture the catalog has no control
for. Do not write it to restyle what the catalog already does; a `components` card is checked,
accessible, and a tenth of the tokens.

The document runs in a sandboxed frame. It cannot reach the network or the page, and anything it
tries to load from an address (a script from a CDN, a web font, an image by URL, a `fetch`) fails.
Everything is inline, and files come through `media`.

- **`window.moody`** is there before your script runs: `moody.recommend(value)`, `moody.state`,
  `moody.locked`, `moody.media.<name>` (an address for an `img`, `audio`, or `video` element),
  `await moody.load(name)` (the file's bytes as an `ArrayBuffer`, for `decodeAudioData` or reading
  pixels), `moody.setState(value)`, and `moody.submit(value)`.
- **Open on your recommendation and say so**: with `submit`, the first thing the script does is
  `moody.recommend(value)`, with the same shape of value it will report later. After that call
  `moody.state` is the value to draw: your recommendation the first time, and the person's last
  value when the card is shown again. The page then tells the person the card is as you
  recommend, and once they change it offers "Back to the recommendation", which starts your
  document again. So the document's own first state has to be the recommendation: never open on
  zero and expect the person to find your answer. A card whose document never calls it is not
  shown.
- **Mark it in the document**: after the option, the preset, or the readout that is yours, write
  the words `<span class="moody-recommended">(recommended)</span>`; the class gives them the quiet
  tone the page uses. Hide the words while the value differs where they sit beside a value.
- **Report on every change**: call `moody.setState(value)` whenever the person changes something.
  The lock-in button sends the last value, or your recommendation if they changed nothing. Use
  `moody.submit(value)` only for a gesture that is itself the answer, such as a double-click on
  the chosen frame. It is ignored unless the person is in the card.
- **Make the value small, named JSON** you will want to read: `{"low": 3, "mid": -2, "high": 4}`.
- **When `moody.locked` is true** (or on the window's `moodylock` event) show the value and
  disable the controls.
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
  "html": "<style>.tap{display:flex;align-items:center;gap:12px;flex-wrap:wrap}output{font:600 28px var(--moody-mono)}p{margin:8px 0 0;color:var(--moody-muted);font-size:12px}</style><div class=\"tap\"><button id=\"tap\" type=\"button\">Tap</button><output id=\"bpm\"></output><span>beats a minute <span id=\"mark\" class=\"moody-recommended\">(recommended)</span></span></div><p>I'd cut at 124: it lands a beat on every fourth stride of the run. Tap at least four times to set your own.</p><script>const mine={bpm:124};moody.recommend(mine);const taps=[];const out=document.getElementById('bpm');const mark=document.getElementById('mark');const button=document.getElementById('tap');const show=(bpm)=>{out.textContent=String(bpm);mark.hidden=bpm!==mine.bpm};show(moody.state.bpm);button.disabled=moody.locked;button.addEventListener('click',()=>{const now=performance.now();if(taps.length&&now-taps[taps.length-1]>2500)taps.length=0;taps.push(now);if(taps.length>=4){const bpm=Math.round(60000*(taps.length-1)/(now-taps[0]));show(bpm);moody.setState({bpm:bpm});}});addEventListener('moodylock',()=>{button.disabled=true});</script>",
  "height": 140,
  "submit": "Cut to this tempo",
  "waits": true
}
```

## Taste

- **One decision per card.** Six inputs is a good ceiling. Two decisions are two cards, or one
  card now and a question later.
- **Real media, never a stand-in.** The frame they are grading is the frame.
- **Recommend, every time** ([Recommend an answer](#recommend-an-answer)): the person should be
  able to lock the card in untouched, and know why you would.
- **Ranges where every position is plausible.** A warmth slider that only looks right between 10
  and 30 should not run from -100 to 100.
- **Their words, with units**: "Hold" with `unit: "s"`, not `duration_frames`.
- **A label names the thing**: "Warmth", "The lead", "The opening's frames". The page tells the
  person what they changed by these labels ("You changed: Warmth, Grain"), so an instruction
  such as "Drag to reorder" belongs in a line of text, not in a label.
- **The button says what happens**: "Lock in this look", "Cast this lead", never "Submit".
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
- **No uploads from the person in a card**, and nothing a card stores survives it.
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
