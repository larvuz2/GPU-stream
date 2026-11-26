<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Editing: Premiere craft in FilmCraft

What editors rely on in Adobe Premiere Pro, how to do each in FilmCraft through
`engine.execute`, and where FilmCraft has no equivalent yet. FilmCraft follows Premiere's
panels, menus, and keys, but names its features in its own words: Premiere's Lumetri Color is
**Color Grading** (effect id `lumetri`), Essential Sound keeps its name. Commands and their
parameters are in filmcraft-commands.md; every recipe here was run against FilmCraft 0.20.1
unless it says otherwise. Times below are seconds unless a key says ticks.

## The map

| Craft | Premiere | FilmCraft | Status |
|---|---|---|---|
| Three-point editing | Source In/Out, Program In, Insert (`,`) / Overwrite (`.`) | `source.open`, `markers.markIn/markOut`, `source.insert` / `source.overwrite` | same |
| Direct placement | drag to timeline | `timeline.place` with `sourceIn`, `duration`, `time` | agent-native, preferred |
| Lift / extract | `;` / `'` | `sequence.lift` / `sequence.extract` | same |
| Ripple, roll, slip, slide | trim tools, Trim mode | `timeline.trim` (`mode: "ripple"`), `timeline.roll`, `timeline.slip`, `timeline.slide` | same |
| J and L cuts | unlink or Alt-drag the audio edit | `timeline.roll` on the audio pair with `followLinks: false` | same |
| Razor / add edit | `Cmd+K` | `timeline.razor`, `sequence.addEdit` | same |
| Transitions | Effects panel, `Cmd+D` | `sequence.applyVideoTransition` / `applyAudioTransition`, `sequence.setTransition` | same; timeline fade handles not yet |
| Speed, freeze frames | Speed/Duration, Frame Hold | `clip.speedDuration` (frame blending, optical flow), `clip.frameHold`, `clip.insertFrameHoldSegment` | same; optical flow on the CPU |
| Keyframed motion | Effect Controls | `effects.setParam` with `keyframe`, `effects.setInterpolation` | same; no on-screen transform handles (not needed by an agent) |
| Adjustment layers | New Item, Adjustment Layer | `file.newAdjustmentLayer` + `timeline.place` on a top track | same |
| Nesting | Nest | `clip.nest`, or place a sequence item | same |
| Correct, match, look | Lumetri Basic, Color Match, Creative | `lumetri` params, `lumetri.applyMatch`, `lumetri.applyPreset` / `look` / `lumetri.setLook` | same; grading runs on the CPU |
| Scopes | Lumetri Scopes | `scopes.read` returns numbers | better for an agent |
| Auto ducking | Essential Sound, Ducking | `essentialSound.set` + `essentialSound.generateDucking` | same |
| Loudness match | Essential Sound, Auto-Match | `essentialSound.autoMatch` | same |
| Remix (music to length) | Remix | `clip.remix` | same; needs music with a clear beat |
| Loudness-normalized export | Media Encoder, Loudness Normalization | `file.exportMedia` `loudnessLufs` | same; measured to 0.1 LU |
| Titles | Essential Graphics, Type tool | `graphics.newText`, `graphics.set` | same; `.mogrt` templates are not read (FilmCraft uses `.fcgt`) |
| Captions | Captions track, Transcribe | `captions.*`; transcription needs a source build | speech-to-text is off in release builds |
| Auto Reframe | Auto Reframe Sequence | `auto_reframe` effect per clip | heuristic, per clip; no sequence-wide command |
| Scene edit detection | Scene Edit Detection | `clip.sceneEditDetection` | same |
| Export presets | Media Encoder presets | `file.exportMedia {preset}`, `export.presets.list` | 45 built in, including TikTok, Reels, Shorts |

## Assembly from generated takes

Generated takes carry a second or more of setup at the head and drift at the tail. Place only
the action:

1. `timeline.place {item, track: "V1", audioTrack: "A1", seconds: <cut point>, sourceIn:
   {"seconds": <action start>}, duration: {"seconds": <cut length>}}`; picture and sound land
   linked. `items: [id, ...]` places several back to back in one undo step.
2. `clip.fitToFrame {clips: [...]}` for every take not at the sequence size (720p in a 1080p
   sequence plays at native size otherwise).
3. Mark each scene's start with `markers.add {target: "program", seconds, name: "S01", color}`.
4. Report the running time (`sequence.inspect` `duration` in ticks) against the target.

## Three-point editing

Two points on one side, one on the other, and FilmCraft computes the fourth:

```text
source.open {item}
markers.markIn  {target: "source", seconds: 1.0}
markers.markOut {target: "source", seconds: 3.0}    Out includes its frame: 1.0-3.0 s is 49 frames at 24 fps
markers.markIn  {target: "program", seconds: 2.0}
source.overwrite {}                                 or source.insert {} to push later clips right
markers.clearInOut {target: "program"}
```

Overwrite replaces what is there; insert ripples everything after it later on sync-locked
tracks. Lift leaves a gap, extract closes it.

## Trims

- **Ripple** (`timeline.trim {clip, edge: "in"|"out", mode: "ripple", deltaFrames}`): shortens or
  lengthens a shot and moves everything after it. The pacing tool of the rough cut.
- **Roll** (`timeline.roll {left, right, deltaFrames}`): moves a cut point, total length kept.
  The picture-lock tool: find the frame where the action lands.
- **Slip** (`timeline.slip {clip, deltaFrames}`): same position and length, different part of the
  take. Use it to pick the best moment of a generated take without changing the edit.
- **Slide** (`timeline.slide {clip, deltaFrames}`): moves a shot between its neighbors, which
  absorb the change.

Trims are limited by the media: a take with no frames beyond its out point cannot be extended.
Generate with handles.

## J and L cuts

A split edit lets sound lead or trail picture, the most important habit in dialogue editing.
Roll only the audio edit:

```text
timeline.roll {left: <A's audio clip>, right: <B's audio clip>, deltaFrames: 12, followLinks: false}
```

Positive moves the sound cut later than the picture cut (an L cut: we keep hearing A over B's
picture); negative moves it earlier (a J cut: we hear B before we see B). 6-18 frames at 24 fps
is the usual range. Verified: the picture cut stayed at frame 96 while the sound cut moved to 108.
Both clips need audio beyond the cut (handles), and a short crossfade
(`sequence.applyAudioTransition {clip, effect: "constant_power", frames: 4, edge: "in"}`) hides
the join.

## Match cuts and cutting on action

- **Cut on action.** End the outgoing shot a few frames into a movement (a turn, a door opening)
  and start the incoming shot at the same point of the movement; the motion carries the eye
  across the cut. Find the frames by stepping (`playhead.step {frames}`) and looking (Program
  frame through `ui.screenshot {panel: "Program"}`), then `timeline.roll` the cut onto them.
- **Match cut.** Two shots joined by shape, motion, or sound (a locket closing to a door
  closing). With generated film, plan it in the shot list: the second shot's prompt repeats the
  first one's composition ("centered, filling the frame, same circular shape"), and the edit
  joins them where the shapes overlap.
- **Cut on a look.** A character looks off screen, cut to what they see, then back to the reaction.
- **Match frame** (`sequence.matchFrame`, F) is a different tool: it opens the source of the
  clip under the playhead at the same frame.

## Pacing by genre

| Genre or format | Average shot | Notes |
|---|---|---|
| Vertical show | 1.5-3 s | a cut or a new piece of information every few seconds; hold the cliffhanger face |
| Commercial | 1-2.5 s | slower for luxury, faster for energy drinks; the pack shot holds 2-3 s |
| Action | 1-2 s | wider shots longer, impacts shortest |
| Comedy | 2-4 s | hold for the reaction; cut on the laugh's peak, not after |
| Drama | 3-6 s | let the performance play; cut on looks |
| Horror, thriller | 4-10 s then very short | long holds to build, a burst of short cuts at the scare |
| Contemplative, art film | 6 s and up | the shot is the event |

Rhythm matters more than the average: vary shot lengths, and slow down before a turn so the
turn lands.

## Transitions

Straight cuts by default. `sequence.applyVideoTransition {clip, effect, frames, edge, align}`
with `effect` an id from `effects.list {kind: "VideoTransition"}`:

| Use | Effect | Frames at 24 fps |
|---|---|---|
| Time passes, memory, softening a jump | `cross_dissolve` | 12-24 |
| End of a sequence or chapter | `dip_to_black` | 18-36 |
| Flash, impact, memory flash | `dip_to_white` | 4-12 |
| Fade in from or out to black at the head and tail | `cross_dissolve` at a free edge | 12-36 |

`align: "center"` straddles the cut and needs handles on both sides; `"start"` or `"end"` keeps
it on one side. Titles fade the same way: a transition at their free edges.

## Speed, holds, and motion

- Slow motion: `clip.speedDuration {clips, speed: 50, ripple: false, interpolation:
  "opticalFlow"}` (smooth, CPU-heavy), or `frameBlending` for speed.
- Freeze frame: `clip.insertFrameHoldSegment {clip, seconds: 2}` at the playhead, for the
  cliffhanger beat or a title over the frozen image.
- Push-in on a still moment: two `effects.setParam {clip, effect: "motion", param: "scale",
  value, keyframe: true, time: <timeline ticks>}` (100 at the head, 108-115 at the tail), then
  `effects.setInterpolation {..., mediaTime, interpolation}` with `easeOut` on the first
  keyframe and `easeIn` on the last. A slow push says "listen"; keep it under 15% over a shot.

## Adjustment layers

One effect over many clips, changed in one place:

```text
file.newAdjustmentLayer {seconds: <sequence length>}         -> {item}
timeline.place {item, track: "V2" (above the picture), seconds: 0, duration: {"seconds": <length>}}
effects.apply {clips: [<adjustment clip>], effect: "lumetri"}
effects.setParam {clip, effect: "lumetri", param: "look", value: "Warm Film"}
```

Use one for the film's look, one for a scene's flashback treatment, one for a film grain
(`noise`) or vignette pass. Titles go on a track above the look so they are not graded.

## Nesting

`timeline.select {clips: [...]}` then `clip.nest {name: "S01"}` turns those clips into one clip
that holds a sequence (`{clips, sequence}` comes back). Placing a sequence item with
`timeline.place {item: <sequence id>}` nests it too. Use nesting to:

- deliver cutdowns: place the finished 16:9 sequence in a 1080x1920, 1080x1350, or 1080x1080
  sequence, `clip.fillFrame`, then set `motion` `position` to keep the subject (verified: a 16:9
  nest fills 4:5 at 125%, 9:16 at 266.7%);
- treat a scene as one unit for a look, a speed change, or a move.

`edit.undo` right after `clip.nest` restores the separate clips.

## Color: correct, match, look

The order a colorist works in, done with the Color Grading effect (`lumetri`):

1. **Correct each shot** toward neutral: `exposure` (-5 to 5 stops), `temperature` and `tint`
   (-100 to 100) for white balance, `contrast`, `highlights`, `shadows`, `whites`, `blacks`,
   `saturation` (100 is unchanged). Check with `scopes.read {scopes: ["waveform"], time}`:
   blacks just above 0%, highlights below 100%, faces in the middle of the luma waveform
   (roughly 40-70% depending on the skin and the light), and `stats.saturation` not shouting.
2. **Match within a scene** to its hero shot: `lumetri.applyMatch {clip, referenceTime: <ticks
   of the hero frame>, faceDetection: true}`. The reply's `distanceBefore` and `distanceAfter`
   say how far it closed the gap. Generated shots of one scene often differ in color temperature;
   this pass makes them one scene.
3. **Look over everything** on an adjustment layer: a preset (`lumetri.applyPreset {name, clips}`,
   list with `lumetri.presets`: Cinematic, Film Emulation, Monochrome, Technical folders), the
   built-in `look` choices (`Teal & Orange`, `Warm Film`, `Cool Blue`, `Bleach Bypass`, `Faded
   Matte`, `Monochrome`, `Golden Hour`, `Night`) at `look_intensity` 30-60, or a LUT
   (`lut.import {path}`, then `lumetri.setLook {clip, lut: "lib:<id>"}`). Finish with
   `vignette_amount` around -0.5 to -1.5 if the frame wants it.

Protect skin: if the look pushes faces off, pull them back with `hsl_on` and the HSL Secondary
keys rather than weakening the whole look.

## Sound

The mix, in the order it is built:

1. **Dialogue.** `essentialSound.setType {clips, type: "dialogue"}`, then
   `essentialSound.autoMatch {clips}` (default target -23 LUFS per clip, set `target` to change
   it). Generated speech can carry hiss or a metallic edge: try `essentialSound.set {key:
   "repair.noise.on", value: true}` and listen before and after.
2. **Ambience** under every scene (`type: "ambience"`), so no cut lands in silence; the
   generated takes' own ambience often does this, so check each cut for a drop.
3. **Music.** `type: "music"`, then ducking against dialogue:

   ```text
   essentialSound.set {clips: [music], values: {"ducking.enabled": true,
     "ducking.against": ["Dialogue"], "ducking.reduceDb": -18, "ducking.fadeS": 0.5}}
   essentialSound.generateDucking {clips: [music]}
   ```

   It writes Volume keyframes and bridges short pauses (a 1 s gap between lines stays ducked).
   After it, change the music's overall level with `clip.audioGain {clips, mode: "adjust",
   db}`, not the Volume `level`, which is now animated. `clip.remix {clip, seconds}` retimes a
   music track to the cut's length by rearranging it along its beats, keeping its intro and
   outro; it needs music with a clear beat.
4. **Crossfades** of 2-6 frames at every audio cut that clicks (`constant_power`).
5. **The Mix.** A limiter as the last insert: `mixer.addInsert {strip: "Mix", effect:
   "hard_limiter"}`, then `mixer.setInsert {strip: "Mix", slot: <slot>, params: {max: -1.0}}`
   (-2.0 for broadcast and streaming specs). Note the key is `params`; other keys are ignored.

### Loudness targets

| Delivery | Integrated | True peak | Source |
|---|---|---|---|
| YouTube, Vimeo, web | -14 LUFS | -1 dBTP | YouTube normalizes playback to about -14 LUFS |
| TikTok, Instagram Reels, YouTube Shorts | -14 LUFS | -1 dBTP | no published target; FilmCraft's presets use -14 |
| European broadcast (EBU R 128) | -23 LUFS | -1 dBTP | EBU R 128 |
| US broadcast (ATSC A/85) | -24 LKFS | -2 dBTP | ATSC A/85 |
| Netflix and similar streamers | -27 LKFS dialogue-gated (±2 LU) | -2 dBTP | Netflix sound mix specification |

Hit the integrated target at export with `loudnessLufs` (the TikTok, Reels, and Shorts presets
already set -14); the limiter keeps the peaks. Verified with ffmpeg's EBU R 128 meter: an export
with `loudnessLufs: -14` measured -14.0 LUFS.

## Titles

`graphics.newText {text, size, seconds, time, track}` makes a graphic clip (`track` is a
0-based video track index; leave it out to go above the clips at that time), then
`graphics.set {clip, props: {font, font_style, size, fill_color, tracking, align, position}}`.
`position` is in sequence pixels, the alignment point on the first baseline.

- Main title: centered, generous tracking (50-100), fade in and out with 12-18 frame dissolves.
- Lower third: name and role, bottom left inside the title-safe area (about 10% in from the
  edges), on screen 3-5 s.
- Vertical: keep text between about 250 px from the top and 400 px from the bottom of a
  1080x1920 frame and away from the right edge, where the platforms put their buttons.
- End card for an ad: logo, line, call to action, held 2-3 s; use the real logo file from the
  Brand section, never a generated one.

## Captions

FilmCraft's release builds have no speech-to-text, so captions come from the script, timed to
the cut:

```text
captions.newTrack {format: "Subtitle", name: "English", language: "en"}     -> {track}
captions.add {track: "C1", text: "You kept it.", seconds: 4.2, durationSeconds: 1.8}
captions.setStyle {track: "C1", font: "Inter", fontStyle: "SemiBold", size: 52,
  anchor: "bottom", margin: 0.12, background: true}
```

Common subtitle practice: at most two lines of about 42 characters, at least about a second on
screen and long enough to read at 17-20 characters a second, split at phrase boundaries, never
across a cut when it can be avoided. A vertical show burns captions in (`burnCaptions: true` at
export) at a larger size (`size` 60-72) with `margin` 0.2-0.25, above the platform's own caption
area. Deliver a sidecar too where the platform takes one (`captionSidecar: "srt"`, or
`captions.export {path, format}`).

## Delivery

| Delivery | Sequence | Export |
|---|---|---|
| YouTube 16:9 | 1920x1080 | `{path, preset: "YouTube 1080p Full HD", loudnessLufs: -14, range: "entire", wait: true}` |
| Vimeo | 1920x1080 | `preset: "Vimeo 1080p Full HD"` (two-pass) |
| Master for archive or a colorist | any | `preset: "Apple ProRes 422 HQ"`, or `"H.264 High 10 Master"` |
| TikTok, Reels, Shorts | 1080x1920 | `preset: "TikTok 1080×1920"`, `"Instagram Reels 1080×1920"`, `"YouTube Shorts 1080×1920"` (-14 LUFS built in), `burnCaptions: true` |
| Square or 4:5 social | 1080x1080 or 1080x1350 | `{format: "h264", bitrateKbps: 8000, loudnessLufs: -14}` at the sequence size |
| Mix as a file | any | `preset: "Waveform Audio 48 kHz 24-bit"` |
| Tracks for an audio post house | any | `file.exportAaf {path, audio: "embedded", handles: <frames>}` or `file.exportOmf {path}` |
| A still for the poster | any | `file.exportFrame {path, time, target: "program"}` |

Preset names carry a multiplication sign (`×`), not the letter x: copy them from
`export.presets.list`. Exports write where `path` says; put them in the project folder's
`exports/` with a version (`cut1_v03.mp4`). After `wait: true` the reply's `result` names the
encoder, frame count, and time; check `offlineMedia` is empty and `warnings` says nothing new.

## Where FilmCraft has no equivalent yet

From FilmCraft's own docs (`docs/gaps.md`, `docs/target-app-parity.md`, `docs/keyboard.md`)
and this skill's runs:

- **Speech to text** is off in release builds (gaps.md G19): no Transcribe, text-based editing,
  or automatic captions; build captions from the script.
- **Generative tools** Premiere has (Generative Extend, Object Mask, Firefly media) do not
  exist (G12); Seedance's extension and editing tasks are the studio's equivalent, outside the
  editor.
- **Auto Reframe** is a per-clip heuristic effect (`auto_reframe`), not a sequence command;
  reframe cutdowns by nesting and positioning instead.
- **Timeline fade handles** are proposed (PR #1635), not merged: fades are transitions at free
  edges, audio fades are Volume keyframes.
- **Essential Graphics templates** (`.mogrt`) are not read; FilmCraft has its own `.fcgt`.
- **Plugins** (VST3, Audio Units, OpenFX) are not hosted (G11).
- **Delivery codecs**: no AV1 export, and H.265 only through a hardware encoder (NVENC on
  Windows, VideoToolbox on macOS; not on Linux), so Linux engines deliver H.264 or ProRes (G13).
- **Premiere projects** (`.prproj`) do not open (G2); exchange timelines as FCP7 XML, AAF, or
  OpenTimelineIO (`file.exportInterchange`).
- **Effects depth** (G18): Warp Stabilizer is 2-D, Morph Cut has no face tracking.
- **On-screen controls** (transform handles in the Program monitor) are missing (ui-parity.md),
  which matters to people, not to an agent that sets parameters.
