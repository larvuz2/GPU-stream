<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Pre-production: templates

Everything a shoot would prepare, adapted to generated film: the script, its breakdown, the
bible that becomes the library, the shot list that becomes generation calls, and the continuity
sheet that keeps them consistent. Each document is saved in the project's repository at the path
given; each is a checkpoint the person approves.

## Intake

Ask only what the project does not already say, one question at a time:

1. Format (from the project) and running time, or episode count and length.
2. Platform and audience: where it plays decides aspect, pacing, and loudness.
3. Tone: two or three films, shows, or ads it should feel like, and one it should not.
4. Generation budget in dollars, and whether it covers retakes.
5. Must-haves: a product, a line, a location, a deadline.

## Logline and synopsis (`beats.md`)

```markdown
# <Title>

**Logline.** When <inciting incident>, <protagonist with a flaw> must <goal> before
<stakes or ticking clock>.

**Synopsis.** One paragraph: setup, turn, escalation, climax, resolution.

**Tone.** <three adjectives>; feels like <reference>, <reference>; not like <reference>.
```

## Beat sheets by format

Percentages are of running time. A beat is one change: something is learned, decided, or lost.

**Movie (short or feature).**

| Beat | Where | What happens |
|---|---|---|
| Opening image | 0-2% | The world and the protagonist's problem in one picture |
| Setup | 2-10% | What they want, what they need, what is wrong |
| Inciting incident | 10% | The event that breaks the routine |
| Debate | 10-20% | Refusal or doubt |
| Into act two | 20-25% | They choose to act |
| Midpoint | 50% | False win or false defeat; the stakes rise |
| All is lost | 75% | The worst moment, the cost of the flaw |
| Climax | 80-95% | They act from what they learned |
| Final image | 95-100% | The opening image, changed |

**Commercial.**

| Length | Structure |
|---|---|
| 15 s | Hook (0-2 s), product as the turn (2-10 s), brand and call to action (last 3-5 s) |
| 30 s | Hook (0-3 s), desire or problem (3-10 s), product as the turn (10-20 s), proof or payoff (20-25 s), brand and call to action (25-30 s) |
| 60 s | A small story: character, want, obstacle, product, changed world, brand |

Land the product by the halfway point, show it in use, end on the pack shot or logo with the line
the person approves. Cutdowns (30 to 15 s, 16:9 to 9:16) are planned now, not discovered later.

**Episode.** Cold open (0-10%, a hook from this episode), acts one to three (or four) each ending
on a turn, a tag or stinger at the end. An A plot carries the episode; a B plot echoes its theme.
Every episode ends with a question the next one answers.

**Vertical drama.** A season of 50-100 episodes of 60-120 seconds, each one to two pages, built
backward from its last beat:

| Beat | Where | What happens |
|---|---|---|
| Hook | 0-3 s | A slap, a reveal, a line that demands a reaction |
| Escalate | 3-45 s | The conflict sharpens; one new piece of information |
| Turn | 45-80% | A reversal or a reveal |
| Cliffhanger | last 5 s | A question, a threat, or a face that changes everything; cut on it |

Big emotions, few locations, close shots, and the protagonist's status changing every few
episodes. Plan 8-15 shots per episode.

## Script (`script.fountain`)

Screenplay form in Fountain plain text: about one page per minute of screen time.

```text
INT. MARA'S KITCHEN - NIGHT

Rain against the window. MARA (34, close-cropped black hair, red raincoat still on) stands
at the counter, turning a small silver locket in her fingers.

The back door opens. JONAS (40s, soaked, a cut above one eye) stops in the doorway.

JONAS
You kept it.

MARA
(not looking up)
You said you'd come back.
```

Rules that matter for generation: describe only what a camera sees and a microphone hears;
introduce each character in capitals with the description that becomes their library entry;
keep dialogue short (lip-sync is best on one or two sentences per shot); write sound cues into
the action.

## Breakdown

One row per scene, saved at the top of `shotlist.md`:

| Scene | Heading | Pages | Characters | Wardrobe | Environment | Props | Sound | Notes |
|---|---|---|---|---|---|---|---|---|
| S01 | INT. MARA'S KITCHEN - NIGHT | 1.5 | @mara, @jonas | @mara-raincoat | @kitchen-night | @locket | rain, kettle | the cut above his eye |

Every tag in the breakdown becomes a library entry before the shot list is locked.

## Bible entries

Each entry is a library item: `library_upsert(section, name, tag, description, metadata)`. The
description is one sentence, the canonical look, reused word for word in every prompt. The bible
documents in the repository mirror the library: one section per entry with its tag, description,
and metadata.

**Character** (section Characters):

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
  "sheet_views": ["turnaround", "face"],
  "approved": false
}
```

**Wardrobe** (section Wardrobe, when costumes change): `{"worn_by": "@mara", "items": "red
knee-length raincoat, gray knit, black jeans, ankle boots", "state": "wet", "scenes": [...],
"variant_of": "@mara-raincoat", "approved": false}`.

**Environment** (section Environments):

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

**Prop** (section Props): `{"owner": "@mara", "scale": "3 cm oval", "material": "tarnished
silver", "condition": "hinge loose", "story": "holds the only photo of her brother", "scenes":
[...], "approved": false}`.

**Product** (section Products, commercials): `{"brand": "...", "variant": "...", "must_keep":
["label text", "logo placement", "cap color"], "hero_angle": "three-quarter front", "claims":
["only what the brand can substantiate"], "approved": false}`. Text on a label is drawn by the
model and may come out wrong: plan pack shots so the real label can be laid over in the edit.

**Brand** (section Brand): logo files, colors as hex, type families, the end-card layout.

**Music** (section Music): the tracks the person supplies or licenses, with `{"bpm": ...,
"license": "...", "cues": ["S01 in", "S03 out"]}`.

## Shot list (`shotlist.md`)

One row per shot; the id is the scene and a shot number in tens, so inserts fit between
(`S01-SH10`, `S01-SH15`, `S01-SH20`). The tag of a generated take is the id plus the take,
lowercase: `@s01-sh20-t2`.

| Shot | Beat | Size | Angle | Lens | Move | Action | Dialogue | References | Gen s | Cut s | Aspect | Res | Takes | Selected |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01-SH10 | Setup | WS | eye level | 24mm | slow push-in | Mara alone at the counter, rain on the window | - | @mara @kitchen-night @locket | 6 | 4 | 16:9 | 720p | 1 | - |
| S01-SH20 | Inciting | MS | eye level, door in background | 35mm | static | The back door opens; Jonas stops in the doorway | JONAS: "You kept it." | @jonas @kitchen-night | 5 | 3 | 16:9 | 720p | 1 | - |
| S01-SH30 | Reaction | CU | slightly low | 85mm | static | Mara does not look up, closes her hand on the locket | MARA: "You said you'd come back." | @mara @kitchen-night | 5 | 3.5 | 16:9 | 1080p | 2 | - |

Add the totals under the table: shots, generated seconds per resolution, takes, and the cost at
the current prices. That total is the number the person approves when the list is locked.

## Coverage patterns

| Scene type | Shots to plan |
|---|---|
| Dialogue, two people | Master wide; over-the-shoulder on A, then on B (A screen left looking right, B the reverse); close-ups of both; one insert; one reaction cutaway |
| Confrontation, vertical | Alternating close-ups, a two-shot for the turn, an extreme close-up for the cliffhanger |
| Action | Wide for geography, mediums for the action beats, close-ups for effort and impact, a point-of-view, an insert of the object |
| Arrival or reveal | Establishing wide, a character entering frame, their point of view, the reaction |
| Montage | One strong image per beat, each 1-2 s in the cut, one move direction throughout |
| Product (ad) | Hero (three-quarter, clean light), macro details (texture, mechanism), product in use (hands, face), lifestyle wide, pack shot with space for the end card |

Generated film can afford less coverage than a set but not none: one alternative angle per
important beat is what lets the edit fix pace.

## Continuity (`continuity.md`)

Per scene, checked before every shot of it is generated and again in the assembly:

```markdown
## S01 INT. MARA'S KITCHEN - NIGHT

- Time and weather: night, steady rain; window shows rain streaks, city lights blurred
- Light: pendant over the counter (warm, key from above), window (cool, camera right in the master)
- Screen direction: Mara faces the window (screen right); the back door is screen left
- Eyelines: Mara looks down at the locket until SH40, then at Jonas (screen left)
- Wardrobe: @mara-raincoat, wet shoulders; @jonas soaked, cut above the left eye
- Props: @locket in Mara's right hand; kettle on the stove from SH10, steaming from SH30
- Sound: rain throughout, kettle rising from SH30
```

## Budget sheet (`README.md`)

```markdown
## Budget

| Stage | Approved | Spent | Notes |
|---|---|---|---|
| Bible (stills) | $15 | $6.40 | 3 characters, 2 environments, 1 prop |
| Look development (480p) | $10 | $5.29 | 4 tests of 6 s |
| Shots (720p, 1080p heroes) | $80 | $0 | 22 shots, 2 heroes at 1080p |
| Total | $105 | $11.69 | |
```
