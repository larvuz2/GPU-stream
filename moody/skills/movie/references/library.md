<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# The library: entries, tags, and reference images

How a film's characters, environments, props, logos, and looks become library entries with
reference images that keep them the same in every shot. Everything here is the library tools and
`generate_image`: no engine runs for any of it. The calls below were run through the control
plane's tools with fal stood in, so their names, parameters, answers, and refusals are as
written; the wording of prompts is in prompting.md.

## Sections

Set them once the brief is settled, in the order the person should see them:

```text
set_library_sections(sections=["Characters", "Environments", "Props", "Logos", "Look", "Tests", "Shots", "Archive"])
```

| Section | Holds |
|---|---|
| Characters | Each character, and each view or variant of one that shots reference |
| Environments | Each place at each time of day the story uses, and its reverse angle |
| Props | Objects the story turns on. A commercial has Products instead, first in the list |
| Logos | The title, the production's mark, and marks that appear in the film's world. A commercial has Brand: the real logo files, colors, and type |
| Look | The style frames and the approved style line (`@look`) |
| Tests | Stills and clips that test entries together and in motion |
| Shots | Every kept take |
| Archive | Candidates that were not chosen and looks that were replaced, so the person can find them again |

Add a section when the work needs one: Wardrobe when costumes change, Music for tracks the
person supplies, References for what research found. A section that still has entries stays in
the list even if you leave it out. The turn's state lists the sections and every entry.

## Tags

`@` and a short lowercase name of letters, digits, and dashes. Unique in the project, never
reused for something else, and fixed once made: no tool changes a tag.

| Entry | Tag | Example |
|---|---|---|
| A character | the name | `@mara` |
| A view or variant of one | the base, then what differs | `@mara-face`, `@mara-wet`, `@mara-age8` |
| A candidate look | the base, `-look-`, a letter | `@mara-look-b` |
| An environment | the place, then the time | `@kitchen-night` |
| Its reverse angle | the base, `-reverse` | `@kitchen-night-reverse` |
| A prop or product | the name | `@locket`, `@bottle` |
| A logo | `logo-`, then which | `@logo-title` |
| The style | `@look`; a candidate direction `@look-`, then its name | `@look-noir` |
| A test | `test-`, then what it tests | `@test-mara-kitchen` |
| A take | scene, shot, take | `@s01-sh20-t2` |

## The calls

**List before you write**, so there is never a second `@mara`:

```text
library_list(section="Characters")
  -> {"sections": [...], "entries": [{"id", "section", "name", "tag", "description", "metadata",
      "media": [{"kind": "image", "name": "..."}]}]}
```

**Make or change an entry:**

```text
library_upsert(section="Characters", name="Mara", tag="@mara",
  description="Mara, 34, close-cropped black hair, an oval face, a small scar through the left eyebrow, red knee-length raincoat",
  metadata={"role": "protagonist", "approved": false})
  -> {"id": "...", "tag": "@mara", "section": "Characters", "name": "Mara", "created": true}
```

- The entry with that tag is changed; without one it is made.
- `section` and `name` are required and are set to what you pass. To change only the metadata of
  an entry, pass its own section and name. To move an entry to another section, pass its tag and
  name with the new section.
- `description` is replaced only when you give one. `metadata` is merged into what the entry
  has, so send only the fields you change.
- The name reaches the image and video models with every reference to the entry ("@Image1 is
  Mara."), so name an entry for what it is.

**Generate a picture into an entry:**

```text
generate_image(prompt="...", references=["@mara-look-b"], aspect_ratio="16:9", save_to={"tag": "@mara"})
  -> Generated 1 image. Saved to @mara (Characters) as its newest media.
     {"model": "...", "saved_to": "@mara", "seed": ..., "cost_usd": ...}
```

- `save_to` names an existing entry by `tag`, or makes one from `section`, `name`, and `tag` (and
  `description`). Without `save_to` the picture is shown and not kept, and nothing can reference
  it later.
- **A reference to a tag sends the newest image of that entry.** Every image you save into an
  entry replaces its reference. So keep `count` at 1 for anything saved: with more, all of them
  land in one entry and only the last can be referenced.
- `aspect_ratio`, the `model` choices, and the most references a call takes are in the tool's
  parameters. The default model is for anything that becomes a reference; `model: "cheap"` is for
  exploration that will be thrown away.

What a refusal looks like, and what to do:

| The answer | Do |
|---|---|
| `@locket has no image to use as a reference yet.` | Generate or ask for that entry's image first |
| `No library entry is tagged @ghost.` | Check the tag with `library_list`; make the entry |
| `No library entry is tagged @nobody; give a section and a name to make it.` | Add `section` and `name` to `save_to` |
| `That model takes at most N references.` | Send fewer; two to four is the working range |
| `INVALID_INPUT ...` | A parameter is outside the tool's schema (a `count` above 4, an aspect ratio it does not list): fix it and call again |

## What a reference image must be

One subject, on a plain mid-gray or other plain ground, in even soft light, with no text and
nothing cropped. It ends with the film's style line, like every prompt.

- **A character:** a turnaround sheet (front, three-quarter, profile, and back in one 16:9
  image, full body, the same clothes in every view) is the entry's reference. A face close-up
  (1:1) is an entry of its own, for close shots.
- **An environment:** the empty establishing wide at the film's aspect ratio, with the time of
  day and the key light stated. The reverse angle, for scenes shot both ways, is an entry of its
  own made with the first as its reference.
- **A prop or product:** clean views on plain ground, and one in a hand for scale as its own
  entry when shots need it.
- **A logo:** the mark flat and centered on plain white or black, no mock-up. It is a concept:
  see [Logos](#logos).

## A character, from description to approved reference

Each step is one checkpoint or one call. The same order makes an environment or a prop, with the
views above.

1. **Describe.** Write the entry with its one-sentence description and `approved: false`
   (`library_upsert`, as above). The sentence was settled with the person in the brief.
2. **Candidates.** Two to four looks that differ within the description (the face, the hair, the
   bearing), each in its own call and its own entry, so the pick has a tag of its own:

   ```text
   generate_image(prompt="<portrait prompt>", aspect_ratio="3:4",
     save_to={"section": "Archive", "name": "Mara, look A", "tag": "@mara-look-a"})
   generate_image(prompt="<portrait prompt>", aspect_ratio="3:4",
     save_to={"section": "Archive", "name": "Mara, look B", "tag": "@mara-look-b"})
   ```

3. **The pick.** Show the candidates as a gallery card the person picks from (`show_ui` with
   `waits: true`; the `cards` skill has the components), or ask with `ask_user` and the tags as
   options. None of them: change the description with the person and make new candidates.
4. **The sheet.** With the pick as the only reference, generate the turnaround sheet into the
   character's own entry, with `look: true` so you can check that every view is there. It is
   now what `@mara` sends to every prompt:

   ```text
   generate_image(prompt="Character turnaround sheet of @mara-look-b, the same woman as the reference, ...",
     references=["@mara-look-b"], aspect_ratio="16:9", save_to={"tag": "@mara"})
   ```

5. **The face**, as its own entry made from the sheet:

   ```text
   generate_image(prompt="Close-up portrait of @mara, the same woman as the reference, ...", references=["@mara"],
     aspect_ratio="1:1", save_to={"section": "Characters", "name": "Mara, face", "tag": "@mara-face"})
   ```

6. **Approval.** Ask the person whether this is Mara. On yes:

   ```text
   library_upsert(section="Characters", name="Mara", tag="@mara",
     metadata={"approved": true, "picked_from": "@mara-look-b"})
   library_upsert(section="Characters", name="Mara, face", tag="@mara-face",
     metadata={"variant_of": "@mara", "approved": true})
   library_upsert(section="Archive", name="Mara, look A", tag="@mara-look-a", metadata={"status": "rejected"})
   ```

   On no: say what you will change, generate the sheet again into the same entry (the new one
   becomes the reference), and ask again.

Steps 2, 4, and 5 are the job of the `character-design` subagent (`production-design` for a
place, a prop, or a logo), one per entry, several at once. Steps 1, 3, and 6 are yours, because
they are the person's decisions. Give a design subagent the entry's tag, name, and description,
the style line, the aspect ratio, the stage (candidates, or sheets from a named pick), and how
many images it may make.

## Variants

A variant is the same subject with one thing changed: wardrobe, age, an injury, an expression,
the time of day. Make it from the approved entry as the reference, change one thing, and say
what stays:

```text
generate_image(prompt="@mara, the same woman, same hair and face, now soaked from rain, ...", references=["@mara"],
  save_to={"section": "Characters", "name": "Mara, soaked", "tag": "@mara-wet"})
library_upsert(section="Characters", name="Mara, soaked", tag="@mara-wet", metadata={"variant_of": "@mara", "approved": false})
```

Never save a variant into the base entry: it would become the base's reference.

## Logos

A film's Logos section holds its title treatment, the production's mark, and marks that exist
in its world (the name on a van, a shop sign). An image model draws letters unreliably, so:

- A generated logo is a concept to choose a direction from. Keep the words out of the prompt
  where they do not have to be there, and tell the person the letters may be wrong.
- A logo that has to be exact is supplied by the person (they add the file to the entry in the
  Library panel) or drawn as vector artwork in a vector engine, which is that engine's skill.
- The title on screen is set in the edit, not generated into a shot.

## The person's own pictures

A photograph of a real actor, product, or place, or a brand's logo file, becomes a reference the
same way as a generated one. Ask for it with a card that has an upload (the `cards` skill): it
answers with the library entry the file became, whose newest image it is. Or make the entry
with `library_upsert` and ask the person to add the file to it in the Library panel. Look at
what they brought with `library_look` before you describe it. Before using a real person's
likeness or a brand's mark, ask whose it is and whether they may use it.

## Metadata by kind

Every entry has `approved` (false until the person approves its reference image) and `scenes`
(where it appears, once the breakdown exists). A variant has `variant_of`. The rest, by kind:

**Character:**

```json
{
  "role": "protagonist",
  "age": 34,
  "face": "oval face, dark brown eyes, small scar through the left eyebrow",
  "hair": "close-cropped black hair",
  "build": "slim, 1.70 m",
  "skin": "warm olive",
  "wardrobe": "@mara-raincoat",
  "voice": "low, unhurried, slight rasp",
  "personality": "guarded, dry humor",
  "arc": "from waiting to leaving",
  "scenes": ["S01", "S03", "S07"],
  "approved": false
}
```

**Wardrobe** (section Wardrobe, when costumes change): `{"worn_by": "@mara", "items": "red
knee-length raincoat, gray knit, black jeans, ankle boots", "state": "wet", "scenes": [...],
"variant_of": "@mara-raincoat", "approved": false}`.

**Environment:**

```json
{
  "int_ext": "INT",
  "time_of_day": "night",
  "era": "present day",
  "place": "small apartment kitchen, third floor, rain on a single window",
  "palette": "tungsten amber practicals against blue window light",
  "lighting": "one pendant lamp over the counter, cold spill from the window",
  "key_features": ["counter facing the window", "back door on the left wall"],
  "screen_direction": "window is camera right in the master",
  "scenes": ["S01", "S04"],
  "approved": false
}
```

**Prop:** `{"owner": "@mara", "scale": "3 cm oval", "material": "tarnished silver", "condition":
"hinge loose", "story": "holds the only photo of her brother", "scenes": [...], "approved":
false}`.

**Product** (commercials): `{"brand": "...", "variant": "...", "must_keep": ["label text", "logo
placement", "cap color"], "hero_angle": "three-quarter front", "claims": ["only what the brand
can substantiate"], "approved": false}`. Text on a label is drawn by the model and may come out
wrong: plan pack shots so the real label can be laid over in the edit.

**Brand** (commercials): logo files, colors as hex, type families, the end-card layout.

**Look:** `{"style_line": "...", "medium": "...", "palette": "...", "light": "...", "approved":
false}`. The approved one is `@look`, and its `style_line` is the sentence every prompt ends
with.

**Music** (section Music): the tracks the person supplies or licenses, with `{"bpm": ...,
"license": "...", "cues": ["S01 in", "S03 out"]}`.

## Keeping it in order

After a batch of new entries, and before the shot list is locked, hand the library to the
`librarian` subagent with these conventions (this file's Sections, Tags, and Metadata by kind)
and what changed. It moves entries to their sections, fills metadata that follows from facts in
hand, and reports what only you or the person can settle: two entries for one thing, an entry
without a picture, an unapproved entry a scene uses. No tool deletes an entry, changes a tag, or
removes a picture: the person does that in the Library panel, and what is superseded is marked
`status: "rejected"` and moved to Archive.

With a repository linked, the bible documents mirror the library after each approval
(`bible/characters.md`, `bible/environments.md`, `bible/props.md`): one section per entry with
its tag, description, and metadata.
