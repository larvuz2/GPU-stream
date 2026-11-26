<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Product

Something made, not built: a chair, a shelf, a lamp, a handle, an enclosure, a part. How it is
made decides its form (what a printer can bridge, what a sheet can be cut into, what a joint
needs), so the opening asks that before anything is drawn.

## The opening card

Say one line ("Let's design it. First, how will it be made?") and show:

```json
{
  "title": "How will it be made?",
  "components": {"type": "pick", "id": "made", "columns": 2, "options": [
    {"value": "print", "label": "3D printed", "note": "On a printer you can reach", "icon": ["000001100000", "000111111000", "011111111110", "000111111000", "000001100000", "011000000110", "000110011000", "000001100000", "011000000110", "000110011000", "000001100000", "000000000000"]},
    {"value": "cut", "label": "Cut from sheet", "note": "Laser, router, or by hand", "icon": ["111111111111", "100000000001", "101111000001", "101001000001", "101001001101", "101111010011", "100000010011", "100000001101", "100000000001", "101010101011", "100000000001", "111111111111"]},
    {"value": "workshop", "label": "Built in a workshop", "note": "Wood, metal, upholstery", "icon": ["000000000000", "011111111000", "011111111100", "011111111100", "011100111000", "000000111000", "000000111000", "000000111000", "000000111000", "000000111000", "000000111000", "000000000000"]},
    {"value": "open", "label": "Not decided", "note": "Show me the object first", "icon": ["000001100000", "000001100000", "000011110000", "000011110000", "011111111110", "111111111111", "011111111110", "000011110000", "000011110000", "000001100000", "000001100000", "000000000000"]}]},
  "instant": true,
  "waits": true
}
```

It answers `{"made": "print"}`, `"cut"`, `"workshop"`, or `"open"`. Their own words in place
of a click are the brief: go on from them.

| The answer | What it fixes, and what you ask next |
|---|---|
| `print` | The printer's bed and its material limit the size and the walls. Ask for the bed's size and the material on the card below. |
| `cut` | The sheet's thickness is the design's module: every slot and tab is that wide. Ask for the material and its thickness on the card below. |
| `workshop` | Stock sizes and joints. Ask for the material on the card below, and who builds it, in one line. |
| `open` | Nothing yet. Go to the card below without the making details, show the object first, and come back to how it is made before any drawing. |

## What to learn, in order

Each is one turn. Skip what they already said.

1. **The object**, on one card that opens on what their words suggest. Fit the material options
   and the size's range to the way it is made.

   ```json
   {
     "title": "The object",
     "components": {"type": "stack", "children": [
       {"type": "field", "id": "what", "label": "What is it, and what does it have to do?",
        "placeholder": "A stool that stacks, a wall hook for a bicycle, a lamp for a desk", "lines": 2, "required": true},
       {"type": "upload", "id": "drawing", "label": "A drawing or a sketch of it, if you have one", "accept": "any", "section": "Drawings"},
       {"type": "number", "id": "size", "label": "Its largest dimension", "min": 1, "max": 300, "step": 1, "value": 45, "unit": "cm"},
       {"type": "select", "id": "material", "label": "Material", "options": [
         "Plywood", "Solid wood", "Steel", "Aluminum", "Acrylic", "PLA", "PETG", "You propose"], "value": "You propose"},
       {"type": "slider", "id": "pictures", "label": "Budget for pictures", "min": 1, "max": 20, "step": 1, "value": 3, "unit": "$"}]},
     "submit": "Start",
     "waits": true
   }
   ```

   Where they gave a drawing, start from it: a DXF or a DWG is opened in CADCraft as drawn,
   and a PDF or a photo of a sketch goes under a new drawing to draw over (the `cadcraft`
   skill, "Starting from a drawing the person brought"). Read its sizes back, and go to the
   concepts only if they want other ways the thing could be; a drawing they are settled on
   goes straight to its dimensions.
2. **What it must fit**, in one question where it applies: the thing it holds or mounts to, with
   its measured size (a 28 mm tube, a 13-inch laptop, a wall stud). A part that has to fit
   another is designed from that dimension, so ask for it before any picture.
3. **The concept**, shown. Three concepts that differ in idea (how it stands, how it joins, what
   it is made of), in the skill's "Pictures before engines": the same three-quarter view on a
   plain backdrop, with something familiar for scale where size matters. Then:

   ```json
   {
     "title": "Three concepts",
     "components": {"type": "pick", "id": "concept", "columns": 2, "options": [
       {"value": "@idea-fold", "label": "One folded sheet", "note": "A single piece, bent twice", "image": "idea-fold"},
       {"value": "@idea-slot", "label": "Slotted together", "note": "Three flat parts, no fasteners", "image": "idea-slot"},
       {"value": "@idea-frame", "label": "A frame and a seat", "note": "Four legs, two rails, a top", "image": "idea-frame"},
       {"value": "none", "label": "None of these", "note": "I'll say what to change"}]},
     "submit": "Develop this one",
     "waits": true,
     "media": [{"tag": "@idea-fold"}, {"tag": "@idea-slot"}, {"tag": "@idea-frame"}]
   }
   ```

4. **The dimensions, in numbers.** Write the overall size, the thickness of each part, and the
   one or two dimensions that carry the function (the seat's height, the hook's opening). Ask
   "Are these the sizes to draw?" and recommend yours. This is the checkpoint before the first
   engine.
5. **What they need at the end**: a file to print or cut, a drawing to hand to a maker, a
   picture to show. It decides which later stages run.

Then close the brief as the skill's stages go: written back in six lines or fewer, the plan
set, the brief saved.

## The default path

| Stage | Who | First engine |
|---|---|---|
| Brief, concepts, dimensions | You | None |
| The part drawing: outline, features, the dimensions and tolerances that matter, on a sheet | You with the `cadcraft` skill, or the CADCraft agent | CADCraft, when the dimensions are agreed |
| The cutting file (DXF) for a part cut from sheet | The same stage, checked for the process | The same engine |
| The solid from the drawing, and the file to print (STL) | The Blender agent, by the `cadcraft` skill's hand-off | Blender |
| The object on a backdrop: three views and a turntable | The Blender agent, with the `blender` skill | Blender on the tier its skill names for the step |
| A model the person turns in the conversation | You: the `cards` skill's `model` component shows a GLB the engine exported | None beyond the export |

A product is checked against how it is made before anything is issued: the `cadcraft` skill's
checks for the process (kerf and tab width for cutting, wall thickness and overhangs for
printing). Read them before you draw, not after.

## The person's decisions

What it is and what it must fit, how it is made, the concept, the dimensions, the material and
its thickness, and the file that goes to a machine or a maker.

## Cost

Nothing until the three concepts, about ten cents. The first engine is CADCraft, on the tier
without a GPU. A file to cut needs no other engine; a file to print, or a picture of the
object, needs Blender.

## What is not possible yet

- **No solid modeling in the drawing engine.** CADCraft is two-dimensional: a solid is made in
  Blender from the drawing, and it is a mesh. No STEP or IGES file comes out of either, so a
  part for a machine shop that asks for one is delivered as a dimensioned drawing.
- **Nothing is simulated.** No load, no stress, no fit under tolerance is computed: say what a
  chair or a hook was sized by (a rule of thumb, a stock section), and that it is untested
  until someone builds one.
- **A printer or a cutter is not driven from here.** You deliver the file and the settings to
  check; the person, or their maker, runs the machine.
- Everything the skill lists under the same heading.
