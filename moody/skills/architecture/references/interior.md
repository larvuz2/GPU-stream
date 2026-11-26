<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Interior

A space that exists, changed inside: a room, an apartment, a shop, an office, a fit-out. The
shell is fixed (its walls, its windows, its height), so the opening finds out how well the shell
is known. A layout drawn in a room of the wrong size helps nobody.

## The opening card

Say one line ("Let's design it. First, what do we have of the room?") and show:

```json
{
  "title": "What do we have of the room?",
  "components": {"type": "stack", "children": [
    {"type": "pick", "id": "have", "columns": 2, "options": [
      {"value": "plan", "label": "A plan or a drawing", "note": "A file, a scan, or a sketch with sizes", "icon": ["001111110000", "001000011000", "001000010100", "001000011110", "001000000010", "001011110010", "001000000010", "001011110010", "001000000010", "001011100010", "001000000010", "001111111110"]},
      {"value": "photos", "label": "Photos", "note": "And a few measurements", "icon": ["000000000000", "111111111111", "100000000001", "100000001101", "100000001101", "100010000001", "100111000101", "101111101111", "111111111111", "100000000001", "111111111111", "000000000000"]},
      {"value": "measures", "label": "Only the measurements", "note": "Length, width, height", "icon": ["000000000000", "000000000000", "000000000000", "111111111111", "100100100101", "100100100101", "100000100001", "100000000001", "111111111111", "000000000000", "000000000000", "000000000000"]},
      {"value": "nothing", "label": "Nothing yet", "note": "A room I imagine", "icon": ["000001100000", "000001100000", "000011110000", "000011110000", "011111111110", "111111111111", "011111111110", "000011110000", "000011110000", "000001100000", "000001100000", "000000000000"]}]},
    {"type": "upload", "id": "file", "label": "Drop it here", "accept": "any", "section": "Room",
     "when": {"have": ["plan", "photos"]}}]},
  "submit": "Start",
  "waits": true
}
```

It answers `{"have": "plan", "file": {"tag": "@...", "name": "...", "kind": "image"}}`, or with
`"file": null` where they gave none. Where they chose a plan or photos and gave no file, ask
for it in one line. One file fits on the card; more photos go on that entry in the Library
panel.

| The answer | What you have, and what you still need |
|---|---|
| `plan` | The shell, once one dimension on it is confirmed. Start from it: a DXF or a DWG is opened in CADCraft as drawn, and a PDF, a scan, or a photo of a sketch goes under a new drawing to draw over (the `cadcraft` skill, "Starting from a drawing the person brought"). Where the plan is already their layout and not only the empty room, read it back and develop it instead of proposing one. Ask which way is north and where the door is, if the plan does not say. |
| `photos` | The feel of the room and where its windows are (`library_look` shows you a picture), but no sizes. Ask for the measurements on the card below. |
| `measures` | Go to the card below. |
| `nothing` | A room you propose: ask what it is for, and open the card below on a size that fits the use. |

## What to learn, in order

Each is one turn. Skip what they already said.

1. **The room's measurements**, on one card that opens on what you know or would assume. Use the
   units the person uses; where they have used none, use meters and say so.

   ```json
   {
     "title": "The room",
     "components": {"type": "stack", "children": [
       {"type": "row", "children": [
         {"type": "number", "id": "length", "label": "Length", "min": 1, "max": 50, "step": 0.05, "value": 5.2, "unit": "m"},
         {"type": "number", "id": "width", "label": "Width", "min": 1, "max": 50, "step": 0.05, "value": 3.8, "unit": "m"},
         {"type": "number", "id": "height", "label": "Ceiling", "min": 2, "max": 10, "step": 0.05, "value": 2.6, "unit": "m"}]},
       {"type": "segmented", "id": "windows", "label": "Windows are on", "options": [
         {"value": "long", "label": "A long wall"}, {"value": "short", "label": "A short wall"},
         {"value": "two", "label": "Two walls"}, {"value": "none", "label": "No windows"}], "value": "long"},
       {"type": "field", "id": "fixed", "label": "What has to stay?",
        "placeholder": "The radiator under the window, the kitchen's water point, the piano"}]},
     "submit": "This is the room",
     "waits": true
   }
   ```

   A room that is not a rectangle is described in words after the card; draw what they say and
   show it before you rely on it.
2. **What it is for, and for whom**, in one question with your proposal: who uses the room, at
   what times of day, what has to fit (a table for eight, a bed and a desk, forty covers).
3. **The look**, shown. Three looks for this room, in the skill's "Pictures before engines":
   the same view from the doorway in all three, the window wall where it really is, the photo
   they brought as a reference where there is one (name its tag in the prompt). Then:

   ```json
   {
     "title": "Three looks for the room",
     "components": {"type": "pick", "id": "look", "columns": 2, "options": [
       {"value": "@idea-warm", "label": "Warm and low", "note": "Oak, linen, lamps at table height", "image": "idea-warm"},
       {"value": "@idea-bright", "label": "Bright and bare", "note": "White plaster, one strong color, daylight", "image": "idea-bright"},
       {"value": "@idea-dark", "label": "Dark and close", "note": "Deep green walls, brass, pools of light", "image": "idea-dark"},
       {"value": "none", "label": "None of these", "note": "I'll say what to change"}]},
     "submit": "Develop this one",
     "waits": true,
     "media": [{"tag": "@idea-warm"}, {"tag": "@idea-bright"}, {"tag": "@idea-dark"}]
   }
   ```

4. **The palette.** From the chosen look, propose four to six materials and colors, each a
   library entry in Materials with one close picture, and show them on a card to confirm or
   change. Use the default model here: these pictures are references for everything after.
5. **The layout, in numbers**: what goes where, with the clearances that decide it (the passage
   behind a chair, the door's swing, the distance from sofa to screen). Ask "Is this the layout
   to draw?" and recommend yours. This is the checkpoint before the first engine.
6. **The budget for pictures**, where it is still open: say what you have spent, and ask once
   how far to go.

Then close the brief as the skill's stages go: written back in six lines or fewer, the plan
set, the brief saved.

## The default path

| Stage | Who | First engine |
|---|---|---|
| Brief, looks, palette, layout in numbers | You | None |
| The plan of the room with its furniture, dimensioned, on a sheet | You with the `cadcraft` skill, or the CADCraft agent | CADCraft, when the layout is agreed, or at once where they brought a DXF or a DWG |
| The room built from the plan, then its light, then the palette's materials | The Blender agent, with the `blender` skill | Blender, when the plan is approved |
| The frames: the view from the door, and one or two more | The Blender agent | Blender on the tier its skill names for a final interior |
| The board: views, plan, palette | You with the `photocraft` skill | PhotoCraft |

An interior is judged by its light. Ask which hour the room matters most at, and render that
hour first.

## The person's decisions

What the room is for, its measurements, the look, the palette, the layout, each piece that is
bought or built, the views to render, and what is issued.

## Cost

Nothing until the three looks, about ten cents; the palette's entries at the default model are
$0.15 each. The first engine is CADCraft, on the tier without a GPU, unless they brought a
drawing to open.

## What is not possible yet

- **Photos do not give sizes.** Never take a dimension from a photograph. A layout from photos
  alone is a sketch until the room is measured, and you say so on it.
- **Furniture in a picture is not a product one can buy.** Describe pieces by their size and
  their material; do not name a brand or promise that a piece exists.
- Everything the skill lists under the same heading.
