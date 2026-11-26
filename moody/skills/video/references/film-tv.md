<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Film & TV

A story told in scenes: a short film, a pilot or an episode, a trailer, a proof of concept. It is
generated shot by shot from a library of characters and places, and cut on a timeline. The
production itself is the `movie` skill, unchanged; this file is how such a project opens and
what you learn before that skill takes over.

## The opening card

The first thing that decides the work is where the story comes from. Say one line ("Let's make
it. First, where does the story come from?") and show:

```json
{
  "title": "Where does the story come from?",
  "components": {"type": "pick", "id": "story", "columns": 3, "options": [
    {"value": "script", "label": "I have a script", "note": "Or a treatment, or a few pages", "icon": ["000000000000", "001111110000", "001000011000", "001000010100", "001000011110", "001011100010", "001000000010", "001011111010", "001000000010", "001011111010", "001000000010", "001111111110"]},
    {"value": "idea", "label": "I have an idea", "note": "A line or two is enough", "icon": ["000011110000", "000100001000", "001000000100", "001000000100", "001000000100", "000100001000", "000010010000", "000010010000", "000011110000", "000000000000", "000011110000", "000001100000"]},
    {"value": "scratch", "label": "Start from scratch", "note": "I pitch three, you pick", "icon": ["000001000000", "000001000000", "000011100000", "011111111100", "000011100000", "000001000000", "000001000100", "000000000100", "000000011111", "000000000100", "000000000100", "000000000000"]}]},
  "instant": true,
  "waits": true
}
```

It answers `{"story": "script"}`, `"idea"`, or `"scratch"`. Their own words in place of a click
are the idea: go on from them.

| The answer | Your next turn |
|---|---|
| `script` | Ask for it in one line: "Paste it here, as much as you have." Read all of it, then answer as the `movie` skill's story.md says ("When they bring a script"): the logline you hear, the cast, the places, the running time, what cannot be filmed as written. |
| `idea` | Ask for it in one line. When it comes, write it back as a logline with two sharper variations, and ask which is the film (`ask_user`, your pick as `recommended`). |
| `scratch` | Pitch at once: three loglines that differ in genre and tone, each a film of a few minutes. Ask which to make, with "Three more, another direction" as the way out. Do not ask what genre they like first: three pitches find that out faster. |

## What to learn, in order

Each is one turn, and each is easy to answer. Skip what they already said.

1. **The story**, from the opening: a logline they chose.
2. **The main characters.** Propose the cast the story needs, two to four people, each with a
   name, an age, one sentence of how they look, and what they want. Ask "Is this the cast?"
   with "Yes, this cast", "Change someone", "Add or remove a character", and recommend yours.
3. **The art style**, shown. Hand `art-direction` the story, the cast, and the aspect ratio, and
   show its three style frames on a card to pick from. A style they describe in words is
   confirmed with one frame. The `movie` skill has both.
4. **The size of the film**, on one card whose controls open on what you would choose for this
   story. Compute the budget's starting value from the length and the prices in the `movie`
   skill's "Cost and time", and say in the line before the card what that budget covers.

   ```json
   {
     "title": "The size of the film",
     "components": {"type": "stack", "children": [
       {"type": "segmented", "id": "length", "label": "Length", "options": [
         {"value": 60, "label": "1 min"}, {"value": 120, "label": "2 min"},
         {"value": 300, "label": "5 min"}, {"value": 600, "label": "10 min"}], "value": 120},
       {"type": "segmented", "id": "frame", "label": "Frame", "options": [
         {"value": "16:9", "label": "Widescreen"}, {"value": "21:9", "label": "Scope"},
         {"value": "9:16", "label": "Vertical"}], "value": "16:9"},
       {"type": "slider", "id": "budget", "label": "Generation budget", "min": 20, "max": 400, "step": 10,
        "value": 100, "unit": "$"}]},
     "submit": "Set the size",
     "waits": true
   }
   ```

5. **Who it is for**, only where the story leaves it open (a film for children, a festival
   short, a pitch for a series). Otherwise decide it and say so.

Then close the brief as the `movie` skill says: write it back in six lines or fewer, set the
plan and the library's sections, and save it. Mention once that connecting a repository
(Environment panel, Connect GitHub) keeps the script and the plans outside the studio; it is an
offer, never a step the work waits for.

## The default pipeline

The `movie` skill's, stage by stage, with its table of who does what:

| Stage | Who | First engine |
|---|---|---|
| Story: beats, script, breakdown | You; `story` for a draft or a breakdown; `research` for facts | None |
| Library: each character, place, prop, and logo | `character-design` and `production-design`, one per entry, at the same time; `librarian` afterwards | None |
| Animation tests | `animation` | None |
| Shot list | You; `review` before the lock | None |
| Shots | `animation`, one per scene | None |
| Edit | You with the `filmcraft` skill, or the FilmCraft agent | FilmCraft, when the first scene's takes are selected and the person says to assemble |

The story and the library run together from the moment the brief is settled, so the person sees
their characters while the script is still being written.

For television, the unit is the episode: a series has one bible (the library and the style line
serve every episode) and one script per episode, with a cold open and a question at its end
(story.md, "Episode"). For a trailer, skip the full script: choose the six to twelve moments
that sell the story, and make those shots.

## The person's decisions

The logline, the cast, the style, each character's and place's look, whether the tests hold in
motion, the shot list with its budget, which takes to keep, and each stage of the edit. The
`movie` skill lists them as checkpoints.

## Cost

Nothing until the first style frames. From there it is generation alone until the edit: stills
for the library, a few seconds of tests, then the shots, which are most of the money. The prices
and the rule for quoting them are in the `movie` skill's "Cost and time".

## What is not possible yet

- **A script comes as text in the conversation.** You have no tool that reads the words of a
  document in the library, so a script that was uploaded as a file is asked for again as text.
- Everything the `movie` skill lists under the same heading: text drawn by an image model is
  unreliable, a take cannot be regenerated sharper, and no tool deletes a library entry.
