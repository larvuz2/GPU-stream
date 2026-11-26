<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Building

Something that stands on a site: a house, a cabin, a studio in a garden, a pavilion, an
extension. The site decides more than anything else (where the sun is, where one arrives, what
one looks at), so the opening finds out what there is of it.

## The opening card

Say one line ("Let's design it. First, where does it start?") and show:

```json
{
  "title": "Where does it start?",
  "components": {"type": "pick", "id": "start", "columns": 3, "options": [
    {"value": "site", "label": "I have a site", "note": "A plot, photos, or a survey", "icon": ["000111111000", "001111111100", "011100001110", "011000000110", "011000000110", "011100001110", "001111111100", "000111111000", "000011110000", "000011110000", "000001100000", "000001100000"]},
    {"value": "existing", "label": "An existing building", "note": "To extend, convert, or rework", "icon": ["000011000000", "000111100000", "001100110000", "011000011000", "111111110000", "010000100110", "010000100110", "010000111111", "010000111111", "010000100110", "011111100110", "000000000000"]},
    {"value": "idea", "label": "Just an idea", "note": "No site yet. We choose a setting", "icon": ["000011110000", "000100001000", "001000000100", "001000000100", "001000000100", "000100001000", "000010010000", "000011110000", "000010010000", "000011110000", "000001100000", "000000000000"]}]},
  "instant": true,
  "waits": true
}
```

It answers `{"start": "site"}`, `"existing"`, or `"idea"`. Their own words in place of a click
are the brief: go on from them.

| The answer | Your next turn |
|---|---|
| `site` | The card below, as written. |
| `existing` | The card below with its title "The building as it is", its upload labeled "A plan or photos of it", and its last field asking "What should change, and why?". |
| `idea` | No upload. Ask on one card what it is and for whom (the same field), and where it would stand, as a `select` of settings that differ (in a city street, in a suburb, in open country, on a coast, in mountains, in a forest), opened on the one their words suggest. |

```json
{
  "title": "The site",
  "components": {"type": "stack", "children": [
    {"type": "upload", "id": "site", "label": "A photo, a survey, or a plan of the plot", "accept": "any", "section": "Site"},
    {"type": "field", "id": "place", "label": "Where is it?", "placeholder": "A town or a region is enough"},
    {"type": "field", "id": "about", "label": "What should stand there, and for whom?",
     "placeholder": "A cabin for two, a studio in the garden, a house for a family of five", "lines": 2, "required": true}]},
  "submit": "Start from here",
  "waits": true
}
```

The upload answers with the library entry the file became (`{"tag": "@...", "name": "...",
"kind": "image"}`), or null. One file fits on the card; tell the person that more photos go on
that entry in the Library panel. `library_look(tags=[<its tag>])` shows you a picture they
brought; a survey or a plan in a format you are not shown is asked about in words.

## What to learn, in order

Each is one turn, and each is easy to answer. Skip what they already said, and decide what a
professional would decide.

1. **The site and the program**, from the cards above: where it is, what stands there now, what
   is wanted and for whom. Where the place is real, hand `research` its climate, the sun's path
   through the year, and what is typically built there, while you go on.
2. **The size**, on one card whose controls open on what you would choose for this program. Work
   out the starting area from the rooms the program needs, and say in the line before the card
   what that area holds. Use the units the person uses; where they have used none, use meters
   and say so.

   ```json
   {
     "title": "The size of it",
     "components": {"type": "stack", "children": [
       {"type": "slider", "id": "area", "label": "Floor area", "min": 15, "max": 400, "step": 5, "value": 90, "unit": "m\u00b2"},
       {"type": "segmented", "id": "floors", "label": "Floors", "options": [
         {"value": 1, "label": "One"}, {"value": 2, "label": "Two"}, {"value": 3, "label": "Three"}], "value": 1},
       {"type": "segmented", "id": "roof", "label": "Roof", "options": [
         {"value": "flat", "label": "Flat"}, {"value": "pitched", "label": "Pitched"}, {"value": "open", "label": "You propose"}], "value": "open"},
       {"type": "slider", "id": "pictures", "label": "Budget for pictures", "min": 1, "max": 30, "step": 1, "value": 5, "unit": "$"}]},
     "submit": "Set the size",
     "waits": true
   }
   ```

3. **The direction**, shown. Three ideas for this site and this program, as the skill's
   "Pictures before engines" says, each saved under a tag, then:

   ```json
   {
     "title": "Three directions",
     "components": {"type": "pick", "id": "direction", "columns": 2, "options": [
       {"value": "@idea-court", "label": "The court", "note": "One floor around a sheltered garden", "image": "idea-court"},
       {"value": "@idea-bar", "label": "The long bar", "note": "A narrow house along the slope, every room to the view", "image": "idea-bar"},
       {"value": "@idea-tower", "label": "The small tower", "note": "Three small floors, a tiny footprint", "image": "idea-tower"},
       {"value": "none", "label": "None of these", "note": "I'll say what to change"}]},
     "submit": "Develop this one",
     "waits": true,
     "media": [{"tag": "@idea-court"}, {"tag": "@idea-bar"}, {"tag": "@idea-tower"}]
   }
   ```

   On "none", ask what to change and make three more that change that one thing. A mix ("the
   court, in the tower's timber") is one more picture with both tags as references.
4. **The sizes, in numbers.** Write the program as a short table in your message: each room with
   its area and what it must sit next to, the footprint's main dimensions, the floor-to-floor
   height. Ask "Are these the sizes to draw?" with "Draw these", "Change a room", "Bigger",
   "Smaller", and recommend the first. This is the checkpoint before the first engine: a plan
   drawn from sizes nobody agreed is redrawn.
5. **What they need at the end**, only where it is still open: a drawing set, renders to show, a
   board, a scene to walk through. It decides which later stages run.

Then close the brief: write it back in six lines or fewer, set the plan
(`update_plan`), and save it (`github_save`, where a repository is linked). Mention once that
connecting a repository (Environment panel, Connect GitHub) keeps the brief and the decisions
outside the studio; it is an offer, never a step the work waits for.

## The default path

| Stage | Who | First engine |
|---|---|---|
| Brief, directions, sizes | You; `research` for the place | None |
| The plan, then elevations or a section where wanted, on sheets | You with the `cadcraft` skill, or the CADCraft agent | CADCraft, when the sizes are agreed |
| Massing without materials, from the drawing | The Blender agent, with the `blender` skill | Blender, when the plan is approved |
| Sun, sky, and materials from the chosen direction | The Blender agent | The same engine |
| The final exterior and interior frames, and an orbit as a clip | The Blender agent | The same engine, on the tier its skill names for final renders |
| The board | You with the `photocraft` skill | PhotoCraft |

While CADCraft draws, nothing else has to wait: hand `research` what the place asks of a
building like this one, and prepare the materials as library entries (one close picture each)
so the model has them when it starts.

## The person's decisions

Where it stands and what it holds, the direction, the sizes, the plan, each change to the plan,
the materials, the views to render, and what is issued. The `cadcraft` skill lists its own
checkpoints, and they hold here.

## Cost

Nothing until the three directions, which are about ten cents. Pictures stay inside the budget
set on the size card. The first engine is CADCraft, on the tier without a GPU; the renders are
the larger cost, and the `blender` skill has their tiers and times.

## What is not possible yet

- **The site is not surveyed by you.** Its levels, boundaries, and orientation are what the
  person or their survey says. Ask for north and for one measured dimension before drawing on a
  plan they brought.
- **Local rules are leads, not checks.** Setbacks, heights, and what may be built are looked up
  with their source and marked "to confirm with the local authority".
- Everything the skill lists under the same heading.
