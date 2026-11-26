<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Prompting with references

How a prompt names its references, the camera language that steers a shot, worked prompts for
stills and shots in every format, and how to fix a result. It serves every `generate_image` and
`generate_video` call, whoever makes it. Which entries exist and how they are made is library.md;
tests, the shot list, and takes are shots.md.

## How references reach the model

You pass library tags in `references` and write the same tags in the prompt. The control plane
sends each tag's newest image (for a video call, a take's video or a track's audio where the
entry has no image), in the order of `references`, and rewrites the prompt for the model, which
knows references only by position:

```text
references: ["@mara", "@kitchen-night"]
prompt:     "Medium shot. @mara turns from the window of @kitchen-night. Static camera."

the model reads:
"Medium shot. @Image1 turns from the window of @Image2. Static camera.

@Image1 is Mara. @Image2 is Kitchen, night."
```

A take given as a reference becomes `@Video1`, and audio `@Audio1`, each kind counted on its own.
So:

1. Write every reference's tag in the prompt where it belongs. A tag in `references` that the
   prompt never names is an image the model was not told what to do with.
2. List `references` in the order the tags first appear in the prompt.
3. Introduce each tag once with its entry's description, word for word: "@mara, a 34-year-old
   woman with close-cropped black hair in a red raincoat". Then refer to it by tag, never by a
   new nickname.
4. A tag that is not in `references` stays in the prompt as plain text and means nothing to the
   model: reference it or describe it in words.

The most references one call takes is in each tool's `references` parameter, and a call over it
is refused with the number. Two to four per shot is the working range: the characters in frame,
the place, and the prop the shot is about. Every extra reference competes for the model's
attention.

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
to make in the edit, generate at normal speed and retime there.

## Stills: worked prompts

**Character candidate** (no references, `aspect_ratio: "3:4"`, one call per candidate, each saved
under a tag of its own; vary the face, the hair, or the bearing between them, inside the
description):

```text
Portrait photograph of Mara, a 34-year-old woman with close-cropped black hair, an oval face,
dark brown eyes and a small scar through her left eyebrow, wearing a red knee-length raincoat.
Neutral expression, looking at the camera. Soft even studio light, plain mid-gray background,
85mm, natural skin texture.
```

**Turnaround sheet** (`references: ["@mara-look-b"]`, the candidate the person picked;
`aspect_ratio: "16:9"`; saved into `@mara`, whose reference it becomes):

```text
Character turnaround sheet of @mara-look-b, the same woman as the reference, full body, four views
side by side on a plain mid-gray background: front, three-quarter left, profile left, back.
Same red knee-length raincoat, gray knit, black jeans, ankle boots in every view. Even soft
light, no shadows on the background, no text, no props.
```

**Face** (`references: ["@mara"]`, `aspect_ratio: "1:1"`, saved as `@mara-face`): "Close-up portrait of @mara,
the same woman as the reference, three-quarter view, neutral expression, soft key light from the
left, plain gray background. Keep every facial feature identical."

**Expression or wardrobe variant** (`references: ["@mara"]`, saved as an entry of its own such as
`@mara-wet`): change one thing and say what stays: "... the same woman, same hair and face, now
soaked from rain, raincoat dark with water, hair plastered to her forehead."

**Environment plate** (no people, at the film's aspect ratio):

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

**Vertical show hook** (`["@ava", "@ballroom"]`, 5 s, 9:16, 720p):

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

**Continuing a shot:** give the previous take's tag as a reference, where it reaches the model as
`@Video1`, and say what continues: "Continuing @s01-sh20-t1: @jonas steps inside and closes the
door behind him ...". The seconds of the take you pass are billed with the seconds generated.

## Fixing a take

| Problem | Fix |
|---|---|
| The face drifts from the reference | Fewer references; add the face entry (`@mara-face`) as a reference; repeat the description word for word; a closer shot size |
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

## What the tools take

The aspect ratios, the resolutions, the model choices, the shortest and longest clip, and the
most references are in the parameters of `generate_image` and `generate_video`, and a call
outside them is refused with the limit. Prices are in the skill's "Cost and time". Every prompt
here ends with the film's style line (`@look`'s `style_line`), the same words in every call.
