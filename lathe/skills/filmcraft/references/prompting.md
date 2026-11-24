<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Prompting with references

How a prompt names its references, the camera language that steers a shot, worked prompts for
stills and shots in every format, how to fix a bad take, and the models with their limits and
prices as fal lists them (checked 2026-11-24 on each model's page,
`https://fal.ai/models/<model id>/llms.txt`).

## How references reach the model

You pass library tags in `references` and write the same tags in the prompt. Seedance (and
FLUX.2) know references by position, per media kind: `@Image1`, `@Image2`, ... in the order of
the model's `image_urls`, `@Video1`, ... for `video_urls`, `@Audio1`, ... for `audio_urls`. The
control plane is to send each tag's media in the order of `references` and put the model's name
in place of each tag in the prompt (Lathe Studio's plan has the tags name the references). Write
prompts that work whichever way the names arrive:

1. List `references` in the order the tags first appear in the prompt.
2. Introduce each tag once with its canonical description: "@mara, a 34-year-old woman with
   close-cropped black hair in a red raincoat". The words carry identity if a name does not.
3. Then refer to it by tag or by the description, never by a new nickname.

What the agent writes:

```text
references: ["@mara", "@kitchen-night", "@locket"]
prompt: "Medium close-up, eye level, 50mm. @mara, a 34-year-old woman with close-cropped
black hair in a red raincoat, stands at the counter of @kitchen-night, a small apartment
kitchen at night lit by one amber pendant lamp, rain on the window behind her. She turns
@locket, a small tarnished silver locket, over in her fingers ..."
```

What Seedance should read once the tags are mapped: the same prompt with `@Image1`, `@Image2`,
`@Image3` in place of the three tags, and `image_urls` in that order. A tag whose entry holds a
video (a previous take) becomes `@Video1`; one holding audio becomes `@Audio1`. If a tool result
shows the prompt reached the model with the tags unchanged, the descriptions are what carry the
identity: keep them in.

Limits per call:

| Model | Images | Videos | Audio | Total | Notes |
|---|---|---|---|---|---|
| Seedance 2.5 (and US) | 30 | 10 | 10 | 50 | videos 1.8-30.2 s each, 30.2 s combined, 24-60 fps |
| Seedance 2.5 Flash | 10 | 5 | 5 | | |
| Seedance 2.0, Fast, Mini | 9 | 3 | 3 | 12 | videos 2-15 s combined; one image or video required |
| Nano Banana Pro edit | 14 | | | 14 | |
| Seedream 5.5 edit | 10 | | | 10 | more than 10: only the last 10 are used |

Two to four references per shot is the working range: the characters in frame, the place, and
the prop the shot is about. Every extra reference competes for the model's attention.

## Prompt anatomy for a shot

In this order, 40-120 words, present tense, concrete nouns and verbs:

1. **Frame:** size, angle, lens. "Close-up, slightly low angle, 85mm."
2. **Subject and action:** who (tag and description) does what, one action with a clear start
   and end inside the duration.
3. **Place and light:** where (tag), time of day, the key light and its direction.
4. **Camera move:** one move, or "static, locked off".
5. **Style line:** the film's look in one sentence, identical in every shot of the project.
6. **Dialogue:** `She says quietly: "You said you'd come back."` One or two sentences per shot.
7. **Sound:** what we hear besides speech. "Rain on glass, a kettle starting to hiss."

Leave out what the references already show (the color of her coat when @mara is a reference is
fine to repeat as identity; a paragraph of costume detail is not), negations ("no people" works
less well than "empty"), and on-screen text (add it in the edit).

## Camera language

| Shot sizes | |
|---|---|
| Extreme wide (EWS) | the place dominates, figures tiny |
| Wide / full (WS, FS) | whole body with room around it |
| Medium (MS) | waist up |
| Medium close-up (MCU) | chest up |
| Close-up (CU) | face fills the frame |
| Extreme close-up (ECU) | eyes, a mouth, a hand on the locket |
| Insert | an object detail that tells the story |
| Two-shot, over-the-shoulder (OTS) | two people; past one's shoulder to the other's face |

| Angles | |
|---|---|
| Eye level | neutral |
| Low angle | power, threat, heroism |
| High angle | vulnerability, surveillance |
| Overhead / top-down | pattern, isolation, a product on a table |
| Dutch (tilted) | unease, use rarely |
| Point of view (POV) | through a character's eyes |

| Moves | |
|---|---|
| Static, locked off | stillness, tension, dialogue |
| Push-in / dolly in | growing importance or realization |
| Pull-back / dolly out | reveal, isolation |
| Pan, tilt | follow or reveal along an axis |
| Tracking / truck | move alongside the subject |
| Crane or jib up / down | open or close a scene |
| Handheld | urgency, documentary |
| Gimbal follow | smooth pursuit behind or ahead of a character |
| Orbit / arc | around a subject at a turning point |
| Whip pan | energy, a hard transition |
| Rack focus | move attention from one plane to another |

**Lens.** 14-24mm wide (space, distortion close up); 35mm (natural, dialogue masters); 50mm
(eye-like); 85mm (portraits, soft background); 135mm and longer (compression, voyeurism); macro
(product detail); anamorphic (oval bokeh, horizontal flares, a scope look with 21:9).

**Depth of field.** "Shallow depth of field, background soft" isolates; "deep focus" keeps the
room in play.

**Light.** Key, fill, rim; motivated by a practical (lamp, window, screen); golden hour, blue
hour, overcast soft light, hard midday sun; high-key (bright, low contrast, ads and comedy),
low-key (dark, contrasty, thriller); neon and mixed color temperatures for night city.

**Motion and time.** "Slow motion" and "time-lapse" are understood; for speed changes you plan
to make in the edit, generate at normal speed and retime with `clip.speedDuration`.

## Stills: worked prompts

**Character look development** (no references, `aspect_ratio: "3:4"`, `count: 4`):

```text
Portrait photograph of Mara, a 34-year-old woman with close-cropped black hair, an oval face,
dark brown eyes and a small scar through her left eyebrow, wearing a red knee-length raincoat.
Neutral expression, looking at the camera. Soft even studio light, plain mid-gray background,
85mm, natural skin texture.
```

**Turnaround sheet** (`references: ["@mara"]`, `aspect_ratio: "16:9"`, `count: 2`, saved to the
entry):

```text
Character turnaround sheet of @mara, the same woman as the reference, full body, four views
side by side on a plain mid-gray background: front, three-quarter left, profile left, back.
Same red knee-length raincoat, gray knit, black jeans, ankle boots in every view. Even soft
light, no shadows on the background, no text, no props.
```

**Face sheet** (`references: ["@mara"]`, `aspect_ratio: "1:1"`): "Close-up portrait of @mara,
the same woman as the reference, three-quarter view, neutral expression, soft key light from the
left, plain gray background. Keep every facial feature identical."

**Expression or wardrobe variant** (`references: ["@mara"]`): change one thing and say what
stays: "... the same woman, same hair and face, now soaked from rain, raincoat dark with water,
hair plastered to her forehead."

**Environment plate** (no people, at the delivery aspect):

```text
Empty small apartment kitchen at night, third floor. A single amber pendant lamp over a worn
wooden counter, a window on the right with rain streaks and blurred city lights, a back door
on the left wall. Wide establishing view from the doorway at eye level, 24mm. Cinematic,
muted palette of amber and blue, no people.
```

Then the reverse angle with `references: ["@kitchen-night"]`: "The same kitchen as the
reference, seen from the window looking back toward the back door ..."

**Prop or product sheet:** "Product photograph of @locket, the same object as the reference:
front, open, and side views on a plain light-gray background, soft box lighting, macro detail
of the engraving, no hands." Add one "held between a thumb and forefinger for scale".

**Composite test** (before spending on video): `references: ["@mara", "@kitchen-night"]`,
"@mara standing at the counter of @kitchen-night, medium shot ..." If identity or place drifts
here, it will drift in video.

## Shots: worked prompts

**Drama, establishing** (`["@mara", "@kitchen-night"]`, 6 s, 16:9, 720p):

```text
Wide shot, eye level, 24mm. @mara, a 34-year-old woman with close-cropped black hair in a red
raincoat, stands alone at the counter of @kitchen-night, a small apartment kitchen at night,
her back half to us, rain running down the window beyond her. Slow push-in. Cinematic, muted
amber and blue, soft film grain. Rain on glass, the hum of the refrigerator.
```

**Drama, dialogue single with lip-sync** (`["@jonas", "@kitchen-night"]`, 5 s):

```text
Medium shot, eye level, 35mm. @jonas, a man in his forties, soaked through, a fresh cut above
his left eye, stands in the open back door of @kitchen-night, rain behind him in the dark. He
stops, catches his breath, and says flatly: "You kept it." Static camera. Cinematic, muted
amber and blue, soft film grain. Rain loud through the open door.
```

**Reaction close-up** (`["@mara", "@locket"]`, 5 s, 1080p):

```text
Close-up, slightly low angle, 85mm, shallow depth of field. @mara, a 34-year-old woman with
close-cropped black hair in a red raincoat, does not look up; her fingers close slowly around
@locket, a small tarnished silver locket. She says quietly: "You said you'd come back." Static
camera. Cinematic, muted amber and blue, soft film grain. Rain on glass.
```

**Vertical drama hook** (`["@ava", "@ballroom"]`, 5 s, 9:16, 720p):

```text
Close-up, eye level, 50mm, vertical frame, face in the upper middle. @ava, a young woman in a
white satin gown with her hair pinned up, in @ballroom, a crowded chandelier-lit ballroom,
turns sharply toward the camera as a glass of red wine splashes across her dress. She gasps,
then her face hardens. Static camera. Glossy, high-contrast, saturated drama look. The crowd
goes silent; a single gasp.
```

**Commercial hero** (`["@bottle", "@studio-sweep"]`, 5 s, 16:9, 1080p):

```text
Close-up product shot, three-quarter front, 100mm macro. @bottle, a frosted glass bottle with
a matte black cap, stands on @studio-sweep, a seamless warm-white set. Water droplets bead and
run down the glass; a slow orbit left reveals the side. Soft overhead key, crisp rim light
outlining the bottle. Premium, clean, minimal. A soft low whoosh.
```

Plan the label to be replaced: models redraw text unreliably. Lay the real label or the end card
over the pack shot in the edit.

**Insert** (`["@locket"]`, 4 s): "Extreme close-up, overhead, macro. @locket, a small tarnished
silver locket, lies open in a palm; inside, a faded photograph of a boy. Static. ..."

**Multi-shot take** (when the person wants the model to cut, or for a montage; 10-15 s): "Shot
1: wide ... Cut to shot 2: close-up ... Cut to shot 3: ..." Keep each part to one action; you
can still cut inside it in the edit.

**Continuing a shot** (Seedance 2.5): give the previous take's tag as a reference and say what
continues: "Continuing @s01-sh20-t1: @jonas steps inside and closes the door behind him ...".
Input video seconds are billed with the output.

## Fixing a take

| Problem | Fix |
|---|---|
| The face drifts from the reference | Fewer references; add the face sheet; repeat the canonical description; a closer shot size |
| Two characters blend | One reference image per character, both described with their difference ("the older man", "the woman in red"); stage them apart in the frame |
| Wrong or extra camera move | Put the move right after the frame line; one move only; "static, locked off" when none |
| Extra people appear | "@mara alone in the frame"; describe the empty space |
| Garbled text or logos | Remove text from the prompt; add it in the edit |
| Hands or objects morph | Simplify the action, keep hands still or out of frame, a wider or tighter size |
| Too static, nothing happens | One strong verb with a start and end inside the duration |
| Lip-sync off | Shorter line, closer shot, the speaker facing the camera |
| The look drifts between shots | The same style line in every prompt; fix the rest in the grade |
| The action is too fast for the duration | Lengthen by a second or two, or cut the action into two shots |

Change one thing per retake and say which, so the person learns with you what moves the result.

## Models and prices

**Video** (reference-to-video on fal). Seconds are of generated video unless noted.

| Model id | Duration | Resolutions | Price |
|---|---|---|---|
| `bytedance/seedance-2.5/reference-to-video` | auto, 4-30 s | 480p, 720p, 1080p, 4k | $0.2205, $0.4730, $1.164, $1.840 per s |
| `bytedance/seedance-2.5/us/reference-to-video` | same | same | same |
| `bytedance/seedance-2.5/flash/reference-to-video` | auto, 4-30 s | 480p, 720p | $0.1345, $0.3024 per s |
| `bytedance/seedance-2.0/reference-to-video` | auto, 4-15 s | 480p to 4k | $0.014 per 1,000 tokens (720p about $0.30 per s) |
| `bytedance/seedance-2.0/fast/reference-to-video` | auto, 4-15 s | 480p, 720p | $0.2419 per s at 720p |
| `bytedance/seedance-2.0/mini/reference-to-video` | auto, 4-15 s | 480p, 720p | $0.007 per 1,000 tokens (720p about $0.15 per s) |

- Tokens are width x height x (input video seconds + output seconds) x 24 / 1024; 720p is 21,600
  tokens a second. With any video reference, Seedance 2.5 bills the whole request at $0.0128 per
  1,000 tokens at 480p and 720p (about $0.28 per second of input plus output at 720p); Flash and
  the 2.0 tiers multiply by about 0.6 and also count the input seconds.
- Aspect ratios on all: `auto`, `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`.
- Seedance 2.5 also takes `task` (`reference`, `editing` of a reference video, `extension` of
  one, or `auto`), `draft` (a 480p preview whose `draft_id` `bytedance/seedance-2.5/draft/complete`
  renders at 1080p or 4K within 14 days, the same take), `return_last_frame`, `seed`, and
  `generate_audio` (on by default, same price). Use them when the control plane exposes them;
  `generate_video` today takes the prompt, references, duration, aspect ratio, and resolution.

**Images** (multi-reference editing on fal):

| Model id | References | Price | Best for |
|---|---|---|---|
| `fal-ai/nano-banana-pro/edit` | 14 | $0.15 per image (4K x2) | character sheets, composites, identity across variants |
| `fal-ai/nano-banana-2/edit` | 14 | $0.08 per image (0.5K x0.75, 2K x1.5, 4K x2) | the same at lower cost |
| `bytedance/seedream/v5.5/edit` | 10 | $0.03 (1K-1.5K) or $0.0405 (2K) plus $0.012 per reference, per image | volume look development, transparent-background prop sheets |
| `fal-ai/flux-2-pro/edit` | not stated | $0.03 first megapixel, $0.015 each further (inputs count) | photoreal products; names references `@Image1` |
| `fal-ai/flux-2-max/edit` | not stated | $0.07 first megapixel, $0.03 each further | the same, highest fidelity |
| `openai/gpt-image-2.6/sunburst/edit` | 16 | token-priced | tight, scoped edits over many rounds |

Text-to-image versions exist for each (`fal-ai/nano-banana-pro`, `bytedance/seedream/v5.5/
text-to-image`, ...) for look development without references.
