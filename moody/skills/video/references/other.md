<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Other

A video none of the six kinds names: a documentary, a video essay, a wedding film, a showreel, a
pitch, a title sequence, a loop for a screen, a recap of an event. It is never made from
nothing: two answers say which of the six it borrows from, and then you work as that kind does.

## The opening card

What a video is made from decides how it is made more than what it is called. One line ("Tell me
two things and we start. First: what is it made from?"), then:

```json
{
  "title": "What is it made from?",
  "components": {"type": "pick", "id": "material", "columns": 2, "options": [
    {"value": "footage", "label": "Footage or photos I have", "note": "Shot already, or about to be", "icon": ["111111111111", "101101101101", "111111111111", "100000000001", "100001000001", "100001100001", "100001110001", "100001100001", "100001000001", "111111111111", "101101101101", "111111111111"]},
    {"value": "generated", "label": "Pictures we generate", "note": "Nothing exists yet", "icon": ["000001000000", "000001000000", "000011100000", "011111111100", "000011100000", "000001000000", "000001000100", "000000000100", "000000011111", "000000000100", "000000000100", "000000000000"]},
    {"value": "words", "label": "Words and numbers", "note": "Text, data, a talk, a deck", "icon": ["000000000000", "011111111110", "010000000010", "010111111010", "010000000010", "010111111010", "010000000010", "010111100010", "010000000010", "011111111110", "000000000000", "000000000000"]},
    {"value": "mix", "label": "A mix of these", "note": "Tell me which in a line", "icon": ["000000000000", "011111110000", "010000010000", "010000010000", "010011111111", "010010010001", "010010010001", "011110010001", "000010000001", "000010000001", "000011111111", "000000000000"]}]},
  "instant": true,
  "waits": true
}
```

## The second question

What it is for, with room for one line of their own. The line is optional: the choice alone is
enough to start.

```json
{
  "title": "What should it do?",
  "components": {"type": "stack", "children": [
    {"type": "pick", "id": "purpose", "columns": 3, "options": [
      {"value": "story", "label": "Tell a story"},
      {"value": "explain", "label": "Explain or document"},
      {"value": "sell", "label": "Sell or pitch"},
      {"value": "mood", "label": "Set a mood"},
      {"value": "occasion", "label": "Mark an occasion"}]},
    {"type": "field", "id": "what", "label": "What is it, in a line?",
     "placeholder": "A recap of our launch night, for the team"}]},
  "submit": "Start",
  "waits": true
}
```

## What it borrows from

| It should | Made from footage or photos they have | Made from generated pictures |
|---|---|---|
| Tell a story (a documentary, a portrait of a person or a place) | Film & TV's story work, the logline and the beats, found in the footage instead of written before it; then the edit on FilmCraft's timeline. No library, no shots | Film & TV, whole |
| Explain or document (a video essay, a case study, a talk) | Education, whole | Education's rule for the script (one idea, say only what is shown), with the pictures generated as the `movie` skill does |
| Sell or pitch (a pitch video, a showreel, a campaign film) | Commercials' brief (the one thing to say, the length to the second, the real logo), then the edit of their footage | Commercials, whole |
| Set a mood (a loop, a visualizer, a title sequence, an art piece) | Music Videos, when there is a track: their pictures cut to it | Music Videos with a track; without one, Film & TV's look and shots, with no script |
| Mark an occasion (a wedding, a birthday, a year in review) | Music Videos' order of work: the track first, then their footage and photos cut to it on FilmCraft's timeline | The same, with generated pictures only where they ask for them |

Words and numbers (a talk, a deck, a set of figures) become a video composed of type, diagrams,
and motion. That is edited by code, in the engine the turn's state names for it: the `video`
skill says which engine suits it and what to tell the person where theirs does not.

A mix borrows the workflow of its largest part, and brings the rest in as that workflow's
material.

## The next turn

Say in two lines what you take the video to be and how you will make it ("A three-minute recap
of the launch night, cut from your footage to one track, on a timeline."), and ask whether that
is it: "Yes, like that", "Closer to something else", recommending the first. Then read the
reference of the kind you borrowed from and go on from the step after its opening card: its
order of what to learn, its pipeline, its decisions, and its costs are now this project's.

One more thing is always open for these videos, and is asked once, when the plan is said back:
how long it runs and what screen it is for. Offer the length and the frame you would choose.

## The person's decisions

What the video is, which is settled by the second answer and their yes to your two lines, and
after that the decisions of the kind it borrowed from.

## Cost

Nothing until the first generation or the first engine, as in the kind it borrowed from. A
video cut from their own footage spends engine time only.

## What is not possible yet

- **Footage is cut, not read for meaning.** You see a recording as frames and a transcript.
  Finding the story in hours of footage is slow and costs engine time: ask the person which
  parts matter before you map everything.
- **A photo is animated in one of two ways.** On a timeline it stays itself, and can only be
  framed and moved across. As the reference of a generated shot it comes alive, and is redrawn:
  say which they are getting before a family photo is put through a model.
- The limits of the kind it borrowed from.
