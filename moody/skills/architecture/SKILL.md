---
name: architecture
description: Start and steer an Architecture project by its kind. Open it before your first reply in an Architecture project. The project's format is its kind (Building, Interior, or Product), and each kind opens with one card of its own and follows the same order of work: the brief first, the idea shown as generated pictures before any engine runs, the sizes agreed in numbers, then the drawing in CADCraft, the model, light, and renders in Blender, a presentation board in PhotoCraft, and a walkable scene in Unreal Engine where the person wants one. It holds what each kind means, the rule for the first turn, which skill owns each stage, how to prompt and price the pictures, and what a generated picture can and cannot promise about a design.
disciplines: architecture
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Starting a design by its kind

A person who starts an Architecture project has told the studio what they are designing, on the
card the project opened with. That one answer decides how you open. This skill is the map: what
each kind means, the card each opens with, the order the work goes in, and which skill owns each
stage. The reference of the kind has the rest, and the craft is in the skills it sends you to.

## When this applies

An Architecture project. Your instructions give its format, which is its kind. Open this skill
before your first reply, then read the kind's reference before you write that reply.

If the format is "not chosen yet", the person wrote to you before picking a kind, and the card
that asks it is still open above. Read their words. Where they say what they are designing, take
the nearest kind, say in a line which you took, and open with its card. Where they do not, ask
in one sentence what they are designing and point to the card.

## The kinds

| Kind | What it is | Starts from | Reference |
|---|---|---|---|
| Building | A house, a cabin, a studio, a pavilion, an extension: something that stands on a site | The site and who it is for, then three ideas as pictures, then the plan | [references/building.md](references/building.md) |
| Interior | A room, an apartment, a shop, a fit-out: a space that exists, changed inside | The room as it is, then three looks as pictures, then the layout | [references/interior.md](references/interior.md) |
| Product | Furniture, a lamp, an object, a part: something made, not built | How it will be made, then three concepts as pictures, then the drawing | [references/product.md](references/product.md) |

A format this table does not list is read as the nearest of the three, and you say in a line
which you took: a garden, a stand, or a small bridge as a Building; a stage set or a display as
an Interior.

## The first turn

1. **The kind is known.** Do not ask it again, and do not ask whether they are sure.
2. **Open with the kind's card.** One line that says what you are about to design together, then
   the opening card as its reference writes it, with the words fitted to anything they already
   said. The card asks the one thing that decides how the work starts. Every card in a
   reference is written as the arguments of one `show_ui` call; the `cards` skill has the
   components and what comes back from each.
3. **Nothing else in that turn.** No list of questions, no plan, no generation, no engine. The
   person should be one click away from the work moving.
4. **Skip the card when it is already answered.** Someone whose first message is their plot,
   their drawing, their photos, or their dimensions has opened the project themselves: act on
   what they brought.

## When they already have a drawing

Many people arrive with something: a floor plan from an architect, a layout they drew
themselves, a part from another program, a sketch on paper. They start from it, and each
kind's opening offers that way in.

| What they have | What happens to it |
|---|---|
| A DXF or a DWG | Opened in CADCraft as it was drawn, with its layers and dimensions, and worked on from there |
| An SVG | Opened as outlines, then brought to real size from one known dimension |
| A PDF, a scan, a photo of a sketch | Placed under a new drawing as a picture, and the plan is drawn over it from the sizes they state |
| A 3D model (GLB, OBJ, FBX, STL) | Opened in Blender; the `blender` skill has the formats and what each keeps |

The file goes into the project's library from the card or the Library panel, and the
`cadcraft` skill ("Starting from a drawing the person brought") has every step from there:
copying it to the engine, reading it back, checking one size with the person before anything
is built on it. Their file is never changed: the work is done on a copy. What a picture cannot
give is size, so a plan traced from a photo is a sketch until one dimension is confirmed.

## The order of the work

Every kind goes through the same stages. Each has one owner, and none starts an engine before
the stage that cannot be done without it.

| Stage | What the person sees and decides | Who | Engine |
|---|---|---|---|
| Brief | The brief written back in six lines or fewer | You; `research` for a place, a climate, or a precedent | None |
| Directions | Three ideas as pictures, and the one to develop | You, with `generate_image` | None |
| Sizes | The numbers that fix the design: areas, main dimensions, what sits next to what | You | None |
| Drawing | The plan at real size, dimensioned, on a sheet | You with the `cadcraft` skill, or the CADCraft agent | CADCraft |
| Model and light | The massing without materials, then the light, then the materials | You with the `blender` skill, or the Blender agent | Blender |
| Views | The final frames, and an orbit or a walk as a clip | The Blender agent | Blender |
| Board | The sheet they present: views, plan, palette, a few words | You with the `photocraft` skill | PhotoCraft |
| Walkable scene | The design to walk through | You with the `unreal` skill | Unreal Engine |

- **This order is a default.** A stage the person does not want is skipped, and one they need
  first comes first: a render with no drawing set, a drawing with no render, a board from
  pictures alone. Say in a line what you left out and why. Their own rules for their work
  outrank this table.
- **Needed work does not wait.** Someone who brings a DXF or a DWG, a model, or a measured
  sketch starts at that stage ("When they already have a drawing"): open the engine that reads
  it, as the `studio` skill says.
- **The drawing is the source of every size.** Once a drawing exists, a dimension changes there
  first and the model follows it, by the hand-off the `cadcraft` skill describes. A model edited
  on its own stops agreeing with the sheets someone will build from.
- **A tier is fixed when an engine starts.** The model, its light, its materials, and draft
  renders run on the tier without a GPU; the `blender` skill says which steps want a GPU tier
  (final interiors, clips). Moving there is saving, `engine_stop`, and `engine_start` on the
  other tier, where the project's folder waits. Starting and stopping are yours: an engine's
  agent drives the engine it is given and cannot change it.
- **One stage, one result, one decision.** End each stage on something the person can see (a
  picture, a sheet, a frame) and the one decision it needs. The `studio` skill ("Keeping the
  project moving") has the rule and its limits.
- An engine's skill is read before the first command to that engine, not before. If a skill
  named in the table is not among yours, the engine's own screen and `engine_exec` are what you
  have: say so, and do the simpler version of the stage.

## Pictures before engines

The fastest way to find what someone wants is to show them three things that are not it. Before
any drawing, show the idea as generated pictures. They cost cents and take seconds, where an
engine costs by the minute.

- **A direction is an idea about the design**, not a rendering style: its form, its main
  material, how it meets its site or its room, how light enters. Three directions differ in
  idea. Three colors of one house are one direction.
- **One call and one library entry per direction**, so each has a tag the person and later
  prompts can name:

  ```text
  generate_image(prompt="<what it is and its size, in plain words>. <the form>. <the main materials>. <the site or the room, the season>. <the light and the time of day>. <the view>. Architectural photograph, realistic materials and construction.",
    aspect_ratio="3:2", model="cheap",
    save_to={"section": "Concepts", "name": "<Two or three words>", "tag": "@idea-<short-name>",
      "description": "<the idea in one sentence>"})
  ```

- **The view is part of the prompt**, and the same in all three, so the person compares designs
  and not camera angles: for a building, "seen at eye level from the approach, the whole
  building in frame"; for an interior, "seen from the doorway at eye height, a wide lens"; for a
  product, "three-quarter view on a plain backdrop, soft studio light".
- **Write what is fixed into every prompt**: the number of floors, a flat or a pitched roof, the
  room's window wall, the object's size against something familiar. A model does not keep to
  numbers, so describe proportion in words ("long and low", "taller than it is wide").
- **No names of living architects, designers, studios, or of other people's buildings and
  products.** Describe the qualities instead: "board-marked concrete, deep window reveals", not
  a name.
- `model: "cheap"` for directions, which are explorations. The default model for the chosen
  direction's hero picture, and for views that have to match it: pass the chosen entry's tag in
  `references` and name the tag in the prompt.
- **Show the three on one card** to pick from, with a way out. The kind's reference has the
  card. A pick is recorded on the entry (`library_upsert` with `metadata: {"approved": true}`),
  and the others stay in the library as what was not chosen.
- Where you have to judge a picture before you show it (a building with no door, a chair with
  five legs), generate with `look: true`. Do not look at what you only pass on.

**Say once what a picture is.** A generated picture is an idea of the design, not the design: it
has no dimensions, its proportions are not to scale, and it can show a span or a cantilever
nobody could build. Never read a size off a picture, and never promise that the drawing will
match it exactly. What the person chooses with it is a direction; the sizes come next, in
numbers.

## The library

The library holds what the pictures and the model are made from. A project starts with the
sections of its kind and you add what the work needs (`set_library_sections`):

| Section | Holds | Used for |
|---|---|---|
| Site, or Room | What exists: the person's photos, a survey, a plan of the shell | References for pictures that have to sit in the real place |
| Concepts | The directions, and the one chosen | The reference every later picture names |
| Materials | One entry per material of the palette, with a close picture and its name | References for pictures; textures for the model (`engine_import` copies entries into the project's `library` folder) |
| Views | The generated views worth keeping | The board, and the brief for the renders |

A render is a file of the project's folder, not a library entry: show it with `preview`, and
give the frames the person may present a `version` ("Exterior v1"), so the newest is always at
hand beside the conversation.

## Cost and time

Nothing in an opening costs anything: cards, questions, and words are free.

- **Pictures.** These are fal's list prices, read on its model pages on 2026-11-25: $0.15 an
  image with the default model, and $0.03 to $0.04 with `model: "cheap"`, plus $0.012 for each
  reference image. Every result carries fal's own estimate (`cost_usd`); where it differs, quote
  from it. Three directions are about ten cents. Say what you are about to make and what it
  costs in the line before you make it, agree a budget for pictures on the kind's size card,
  and keep a running total. 1 credit is $0.01 where the studio bills in credits.
- **Engines** cost credits by the minute, by tier; your instructions list the tiers. Drafting in
  CADCraft runs on the tier without a GPU. For Blender, its skill says which tier a step needs
  and how long it takes. Say the tier, its price a minute, and your estimate before each
  `engine_start`, and stop an engine when its stage is done.
- Each reference says where its kind first spends and where its first engine starts.

## What is not possible yet

- **You are not the architect or the engineer of record.** Structure, fire, energy,
  accessibility, and planning rules are for a licensed professional to check and sign. You check
  what a drawing can show (dimensions that close, clearances, areas: the `cadcraft` skill's
  checks), and you say plainly what nobody has checked. A rule you looked up is a lead with its
  source, never a confirmation that the design complies.
- **A picture has no scale**, and a plan cannot be read off a photograph: a measured drawing
  needs at least one known dimension.
- **No building information model.** A wall in the drawing is lines, not an object that knows
  its material; quantities are what you measure, and nothing prices the design.
- **You cannot change the project's kind.** The card the project opened with sets it. When the
  work turns out to be another kind, work as that kind and say so; the label stays.
- **Unreal Engine's editor runs on the person's own Epic account**, and an engine your
  instructions list as not available yet cannot be started. Offer what can be done now.
