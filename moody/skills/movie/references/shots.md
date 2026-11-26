<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Tests and shots

How approved library entries are proved in motion, how a script becomes a shot list, and how the
shots are generated and kept. Everything here is `generate_video`, `generate_image`, and the
library tools: no engine runs for any of it. The calls were run through the control plane's
tools with fal stood in; prompt wording is in prompting.md and the entries are library.md's.

## The call

```text
generate_video(prompt="...", references=["@mara", "@kitchen-night"], duration_seconds=4,
  aspect_ratio="16:9", resolution="480p",
  save_to={"section": "Tests", "name": "Test: Mara in the kitchen", "tag": "@test-mara-kitchen"})
  -> Generated 1 video. Saved to @test-mara-kitchen (Tests) as its newest media.
     {"model": "...", "saved_to": "@test-mara-kitchen", "seed": ..., "cost_usd": ...}
```

- The person approves each call on the page before it runs, unless they chose to always allow
  it. A declined call answers with a refusal: do not repeat it.
- Always give `duration_seconds`. Left out, the model chooses the length, and the price is not
  known before the call.
- The shortest clip, the longest for each `model` choice, and the resolutions each makes are in
  the tool's parameters. A call outside them is refused with the way out, such as "The standard
  model makes clips of at most 14 seconds; use fast for longer." or "The fast model makes 480p
  or 720p; use standard for 1080p."
- An entry given as a reference sends its newest image; a take, which has no image, sends its
  video.
- Without `save_to` the clip is shown and not kept. Keep every test and every take.

## The first animation tests

Run them as soon as one main character and one place are approved, before the shot list. Their
question is whether the look holds when it moves; a pretty test is not the goal.

1. **A still of them together**, which costs cents and fails first if the entries do not sit in
   one picture:

   ```text
   generate_image(prompt="@mara standing at the counter of @kitchen-night, medium shot, ...",
     references=["@mara", "@kitchen-night"], aspect_ratio="16:9", model="cheap",
     save_to={"section": "Tests", "name": "Still test: Mara in the kitchen", "tag": "@test-mara-kitchen-still"})
   ```

2. **Motion tests**, one generation each, saved to Tests:

   | Test | What the prompt asks for | What it proves |
   |---|---|---|
   | Each main character | A medium shot on plain ground or in the place: one simple action (turns, takes two steps, looks up), static camera | The face and clothes stay the reference's while moving |
   | The key place | The empty place, one slow camera move | The place keeps its layout and light |
   | A character in the place | The first shot of the film, or its most typical one | The two hold together, and the style line survives motion |
   | A spoken line, when the film has dialogue | A close shot, the speaker facing the camera, one short sentence | The voice and the lip-sync |

3. **Settings.** The `model` the shots will use, because a test on another model says nothing
   about the shots; that model's lowest resolution; 4 or 5 seconds; the film's aspect ratio.
4. **Show them together** and ask one question, with what to look for: the face against the
   sheet, hands, the clothes, the light, whether the motion is the action asked for. Options:
   "It holds: plan the shots", "Fix a character", "Fix the place", "Change the look". Recommend
   the first when nothing drifted, and otherwise the fix for what did.
5. **A test that fails is fixed at the entry**, not by rewording the shot:

   | What drifted | Go back to |
   |---|---|
   | A face or clothes | That character's sheet: a clearer turnaround, or the face entry as a second reference |
   | The place | Its plate: fewer loose objects, the light stated, the reverse angle for the other direction |
   | The style | The style line: shorter and more concrete, the medium named first |
   | Two characters blend | Their descriptions: make the difference between them a visible one |

Approve a low-resolution test as a direction, never as the shot: a new call at a higher
resolution is a new take, not the same take sharper. The `animation` subagent runs a set of
tests as one job; give it the tags, the table's rows you want, the style line, the aspect ratio,
the model, and the number of clips it may make.

## The shot list (`shotlist.md`)

It needs the locked script and its breakdown (story.md). One row per shot; the id is the scene
and a shot number in tens, so inserts fit between (`S01-SH10`, `S01-SH15`, `S01-SH20`). The tag
of a take is the id and the take, lowercase: `@s01-sh20-t2`.

| Shot | Beat | Size | Angle | Lens | Move | Action | Dialogue | References | Gen s | Cut s | Aspect | Res | Takes | Selected |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01-SH10 | Setup | WS | eye level | 24mm | slow push-in | Mara alone at the counter, rain on the window | - | @mara @kitchen-night @locket | 6 | 4 | 16:9 | 720p | 1 | - |
| S01-SH20 | Inciting | MS | eye level, door in background | 35mm | static | The back door opens; Jonas stops in the doorway | JONAS: "You kept it." | @jonas @kitchen-night | 5 | 3 | 16:9 | 720p | 1 | - |
| S01-SH30 | Reaction | CU | slightly low | 85mm | static | Mara does not look up, closes her hand on the locket | MARA: "You said you'd come back." | @mara @kitchen-night | 5 | 3.5 | 16:9 | 1080p | 2 | - |

Add the totals under the table: shots, generated seconds per resolution, takes, and the cost at
the prices in the skill's "Cost and time". That total is the number the person approves when the
list is locked.

### Coverage

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

### Continuity (`continuity.md`)

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

### Before the lock

Check the list yourself, or hand it to the `review` subagent with this list as its standard:

- Every tag under References is a library entry that has an image and `approved: true`.
- Each shot's references are only what is in its frame, four at most.
- `Gen s` is the cut length plus a second of handle each side, no shorter than the tool's
  shortest clip and no longer than the model's longest.
- `Res` is one the chosen model makes.
- Dialogue is one or two sentences a shot.
- Screen direction and eyelines agree with the continuity sheet across each scene.
- Every important beat has one alternative angle.
- The totals add up, and the cost is seconds times the price at each resolution.

Then ask the person to lock the list and its budget.

## Generating the shots

- **One generation, one shot.** A shot is one camera setup. A prompt that cuts ("cut to") is for
  a montage, or when the person wants the model to cut; otherwise you keep the cut.
- **References: only what is in the frame**, listed in the order the prompt first names them.
  The prompt names each by its tag and repeats its description (prompting.md).
- **Duration:** the cut length plus a second of handle each side. Several short beats from one
  setup come from one longer take, cut apart in the edit.
- **Aspect ratio:** the delivery's. For a commercial delivered in two, generate the hero shots
  in each and reframe the rest in the edit.
- **Resolution:** the lowest for tests, the middle one for working shots, the highest for hero
  shots and 16:9 finals.
- **Sound.** The video model generates sound effects, ambience, and lip-synced speech with the
  picture. Write the line in the prompt as it should be spoken; that production sound is the
  dialogue track in the edit. Music comes later.
- **Continuity.** The same tags and descriptions every time, the continuity sheet checked before
  each call, screen direction kept (the 180-degree rule). A shot that must flow out of the one
  before takes that take's tag as a reference, and the seconds of that take are billed too.
- **One scene, one batch.** Generate one take of every shot of a scene, review them with the
  person, then retake only the shots that need it. The `animation` subagent takes a scene as one
  job, several scenes at once; give it the scene's rows, the continuity sheet, the style line,
  the model, and the takes allowed per shot.

## Takes

Save every take, then record what made it, so a retake changes one known thing:

```text
generate_video(prompt="Wide shot, eye level, 24mm. @mara, ..., stands alone at the counter of @kitchen-night, ...",
  references=["@mara", "@kitchen-night"], duration_seconds=6, aspect_ratio="16:9", resolution="720p",
  save_to={"section": "Shots", "name": "S01 SH10 T1", "tag": "@s01-sh10-t1"})
library_upsert(section="Shots", name="S01 SH10 T1", tag="@s01-sh10-t1",
  metadata={"scene": "S01", "shot": "S01-SH10", "take": 1, "prompt": "...", "references": ["@mara", "@kitchen-night"],
            "duration_s": 6, "resolution": "720p", "model": "...", "seed": ..., "cost_usd": ..., "status": "candidate"})
```

- `status` is `candidate`, `selected`, or `rejected`. The person selects; you recommend. Set
  `selected` on their word, and write the tag into the shot list's Selected column.
- **Reviewing a take.** `look: true` on the call, or `library_look` afterwards, hands you four
  frames of the clip: check the face against the sheet, hands, and text. Frames show no motion
  and no sound, so tell the person what is theirs to check: the movement, physics, screen
  direction, the line as spoken. Never present a take as fine on its facts alone.
- **A retake** changes one thing and says which (prompting.md, "Fixing a take"). It is a new
  take with a new tag; the old one stays as `rejected`.
- Generated files are kept only in the library: a clip made without `save_to` is not there for
  the edit.

## Budget sheet (`README.md`)

```markdown
## Budget

| Stage | Approved | Spent | Notes |
|---|---|---|---|
| Library (stills) | $15 | $6.40 | 3 characters, 2 environments, 1 prop |
| Animation tests (lowest resolution) | $10 | $5.29 | 6 tests of 4 s |
| Shots | $80 | $0 | 22 shots, 2 heroes at the highest resolution |
| Total | $105 | $11.69 | |
```

Spent is the sum of the `cost_usd` each result reported.
