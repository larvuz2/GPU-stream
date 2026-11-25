<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# FilmCraft commands

The commands the film workflow uses, with parameters as FilmCraft's command registry defines
them (`crates/engine/src/commands.rs` and the modules beside it). Checked against FilmCraft
0.20.1: the registry lists 719 engine commands, and every recipe in this skill was run through
a headless session (`filmcraft-cli mcp`, the same engine the desktop app runs) and read back.
Parameter docs below are copied from the registry; `?` marks an optional key, `=` its default,
`…` an abridged list.

## Calling FilmCraft

`filmcraft(engine_id, method, params)` sends one request on FilmCraft's control channel:

- `engine.execute` `{command, params}`: runs any command id, UI ones included
  (`window.workspace.color`), and returns its result.
- `engine.commands` (no params): every command, with `id`, `label`, `menu`, `params` (its
  parameter doc), `enabled` now, and `shortcut`.
- `ui.screenshot` `{panel?, id?, path?}`: without `path`, returns `{pngBase64, width, height}`;
  `panel: "Program"` crops to the Program monitor.
- `ui.inspect` (no params): workspace, panels, playback, keyboard focus.
- `ui.playback` `{action: "play"|"stop"|"toggle", speed?}`: returns `{playing, playhead}`.

Replies are `{"ok": true, "result": …}` or `{"ok": false, "error": "…"}`. A command sent through
`engine.execute` never opens a dialog: it runs with the parameters given (`sequence.addTracks {}`
adds one video track; `clip.audioGain {}` answers "need `db`").

**Finding a command.** `engine.commands`, then read the entry's `params`. Search by what a
Premiere menu calls it: ids follow Premiere's menus (`clip.speedDuration` is Clip, Speed/Duration).

**Targets.** A command that acts on the selection is refused with "no clips selected" unless its
parameters name the targets under a key its doc shows (`clips: [id]`, `clip: id`, `items: [id]`,
`item: id`). Name them; it leaves the person's selection alone.

## Units and addressing

**Time** is integer ticks, 254,016,000,000 per second, exact at every common rate:

| Unit | Ticks |
|---|---|
| 1 second | 254,016,000,000 |
| 1 frame at 24 fps | 10,584,000,000 |
| 1 frame at 23.976 fps | 10,594,584,000 |
| 1 frame at 25 fps | 10,160,640,000 |
| 1 frame at 30 fps | 8,467,200,000 |
| 1 frame at 29.97 fps | 8,475,667,200 |
| 1 frame at 60 fps | 4,233,600,000 |
| 1 sample at 48 kHz | 5,292,000 |

- A time parameter `time` takes an integer. In its place you may give `seconds` (float),
  `frame` (integer, at the sequence rate), or `timecode` (`"00:00:04:00"`) as sibling keys:
  `timeline.razor {seconds: 2.5, track: "V1"}`. Prefixed forms follow the same rule
  (`captions.setTimes {startSeconds, endSeconds}`).
- An object such as `{"seconds": 2}` is accepted only where the doc shows it:
  `timeline.place` `sourceIn` and `duration`, `timeline.move` `moves[].time`. Elsewhere it is
  ignored and the command uses the playhead (verified: `timeline.razor {time: {"seconds": 1}}`
  cut at the playhead, with `ok: true`).
- **Timeline time and media time.** `effects.setParam` and `effects.addKeyframe` take `time` in
  timeline ticks. `effects.setKeyframe`, `setInterpolation`, `moveKeyframe`, and `deleteKeyframe`
  take `mediaTime`: ticks into the source, `timeline time - clip start + clip sourceIn`.
  `effects.addKeyframe` returns the `mediaTime` it used.
- Source Out marks include their frame: In at 1 s and Out at 3 s is 49 frames at 24 fps.
- A placed clip snaps to the frame grid.

**Tracks** are named `"V1"`, `"V2"`, `"A1"`, caption tracks `"C1"`, or given by id; `"new"`
adds one where the doc allows. Naming a track the sequence lacks is an error, never another
track. Graphics commands differ: their `track` is a 0-based video track index (`0` is V1), an
occupied track there is refused ("V2 is not free here"), and an index past the last track, like
no index, picks the first free track above the clips at that time.

**Picture coordinates** are sequence pixels: Motion `position` defaults to the frame center
(`[960, 540]` in 1080p), `anchor` to the clip's center in its own pixels (`[640, 360]` for a 720p
clip). Scale and opacity are percent, rotation degrees, audio levels and gains dB, colors
`"#rrggbb"`.

## Reading state

`sequence.inspect {item?}` is the source of truth after every edit:

```text
{id, name, duration, durationFrames, playhead, selection, in, out,
 settings: {width, height, frame_rate: {num, den}, sample_rate, …},
 markers: [{id, name, comment, color, start, duration, kind}],
 video: [track], audio: [track]}
track: {id, name, enabled, locked, muted, solo, syncLock,
        items: [{clip, item, name, start, end, startFrame, endFrame, duration, durationFrames,
                 sourceIn, sourceOut, speed, reverse, gainDb, link, label, enabled,
                 effects: [{effect, enabled, params: {<param>: {value, keyframes}}}]}],
        transitions: [{id, effect, from, to, start, duration, align}]}
```

`video[0]` is V1. `clip` is the clip id the commands take; `item` its project item; `link` its
linked partner (picture to sound). Effect values come back as text such as `"Float(0.3)"`,
`"Choice(1)"`, `"Vec2(Vec2 { x: 960.0, y: 540.0 })"`. `project.inspect` returns the bin tree
with item ids. Each command's own result (`{"clips": [17, 18]}`) carries the new ids.

## Traps (each seen in a run)

1. **Unknown parameter keys are ignored.** `mixer.setInsert {param: "max", value: -1}` returned
   OK and changed nothing; the doc's key is `params: {max: -1}`. `captions.setStyle
   {position: "bottom"}` did nothing; the key is `anchor`. Read back what you set.
2. **Time objects outside the documented keys fall back to the playhead** (above).
3. **Shots at another size are not scaled.** A 1280x720 take in a 1920x1080 sequence plays at
   native size on a transparent frame. `clip.fitToFrame` (150% here) or `clip.fillFrame`.
4. **Animated parameters take keyframes, not values.** After `essentialSound.generateDucking`,
   setting the music's Volume `level` writes a keyframe at the playhead; move the whole clip
   with `clip.audioGain` instead.
5. **Export preset names use `×`** (U+00D7): `"TikTok 1080×1920"`. Copy them from
   `export.presets.list`.
6. **`clip.remix` needs music with a beat.** It refuses audio with no beat (silence, noise,
   speech), music with fewer beats than a remix needs ("the music is too short to remix", seen on
   a test tone), and a target shorter than the intro and outro it keeps.

## Project and media

| Command | Params |
|---|---|
| `file.newProject` | `{"name":str}` |
| `file.open` / `file.save` / `file.saveAs` | `{"path":str}` / `{"path":str?}` / `{"path":str}` |
| `file.newBin` | `{"name":str,"parent":binId?}` -> `{bin}` |
| `file.import` | `{"paths":[str],"bin":binId?,"imageSequence":bool?,"replace":bool?}` -> `{items, errors}` in path order |
| `project.inspect` | `{}` |
| `media.status` / `media.findMissing` | `{"item":id?}` / `{}` |

Paths are the engine's own: use what `engine_import` returned, and keep exports in the same
project folder.

## Sequences

- `file.newSequence`: `{"name":str,"width":u32=1920,"height":u32=1080,"fps":f64=23.976,"sampleRate":u32=48000,"video":n=3,"audio":n=3,"mix":"Stereo|Mono|5.1|Adaptive"?,"fromItem":itemId?,"fromItems":[itemId]?,"bin":binId?}` -> `{sequence}`
- `sequence.settings`: `{"width":u32?,"height":u32?,"fps":f64?,"name":str?,…}`; with `{}` returns the settings
- `sequence.open`: `{"item":id}` (a sequence's item id)
- `sequence.addTracks`: `{"video":n=1,"audio":n=0,…}`
- `timeline.setTrack`: `{"track":"V1"|id,"locked":bool?,"syncLock":bool?,"enabled":bool?,"muted":bool?,"solo":bool?,"name":str?,"volumeDb":f64?,"pan":f64?,…}`

Match the takes' frame rate rather than assuming it: `file.newSequence {name, fromItem: <a
take>}` makes a sequence at that take's size and rate (and places it), `sequence.settings {}`
shows the rate, and `sequence.settings {width, height}` then sets the delivery size without
moving or scaling clips (`scaleMotion: true` scales them with it). `project.inspect` does not
report an item's rate.

## Placing and arranging

- `timeline.place`: `{"item":id|"items":[id] (back to back, one undo step),"track":"V1"|id|"A1" (sound only)|"new"?,"audioTrack":"A1"|id|"new"?,"time":ticks|"frame":i64|"seconds":f64,"insert":bool,"sourceIn":ticks|{"frame"|"seconds"|"timecode"}?,"duration":ticks|{"frame"|"seconds"|"timecode"}?,"video":bool=true,"audio":bool=true,"matchSequence":bool=false}` -> `{clips: [video, audio]}`
- `timeline.move`: `{"moves":[{"clip":id,"track":id|"V2"|"new","time":ticks|{"seconds":f}|{"frame":n}|{"timecode":str}}],"insert":bool,"linked":bool?,"copy":bool?}` -> `{moved}`
- `timeline.select`: `{"clips":[id],"transitions":[id]?,"add":bool,"toggle":bool,"linked":bool?}`
- `timeline.delete`: `{"clips":[id]?,"clip":id?,"ripple":bool?}`
- `edit.clear` / `edit.rippleDelete`: `{"clips":[id]?,"clip":id?}`
- `sequence.lift` / `sequence.extract`: `{}`, between the Program In and Out on targeted tracks
- `sequence.closeGap`: `{"track":"V1"|id?,"time":ticks?}`
- `timeline.razor`: `{"time":ticks,"track":"V1"|id?,"clip":id?}`, or `seconds` / `frame` / `timecode` in place of `time`
- `sequence.addEdit` / `sequence.addEditAllTracks`: `{"time":ticks?}`

`timeline.place` puts picture on `track` and sound on `audioTrack`; a placed sequence item
becomes a nested clip. `matchSequence: true` on an empty sequence first takes the clip's frame
size and rate.

## Three-point editing

- `source.open`: `{"item":id?,"clip":id?}`
- `markers.markIn` / `markers.markOut`: `{"time":ticks?,"frame":i64?,"seconds":f64?,"timecode":str?,"target":"program|source"}`
- `markers.clearInOut`: `{"target":"program|source"}`
- `source.insert` / `source.overwrite`: `{"matchSequence":bool=false}` -> `{clips}`

## Trimming

- `timeline.trim`: `{"clip":id,"edge":"in|out","mode":"regular|ripple","delta":ticks|"deltaFrames":i64,"linked":bool?}`
- `timeline.roll`: `{"left":id,"right":id,"delta":ticks|"deltaFrames":i64,"followLinks"?:bool}`
- `timeline.slip`: `{"clip":id,"delta":ticks|"deltaFrames":i64}`
- `timeline.slide`: `{"clip":id,"delta":ticks|"deltaFrames":i64}`
- `timeline.rateStretch`: `{"clip":id,"edge":"in|out","delta":ticks,"linked":bool?}`

`timeline.roll` with `followLinks: false` on two audio clips is a J or L cut. Trims stop at the
media's ends and at neighbors.

## Markers and the playhead

- `markers.add`: `{"target":"program|source","time":ticks?,"name":str?,"comment":str?,"color":label_or_hex?,"author":str?,"durationFrames":i64?}`; `seconds` works in place of `time`
- `markers.edit`: `{"target":"program|source","marker":id|"markers":[id],"name":str?,"comment":str?,"color":label_or_hex?,"kind":"comment|chapter|…"?,…}`
- `markers.exportCsv`: `{"path":str}`
- `playhead.set`: `{"time":ticks|"frame":i64|"seconds":f64|"timecode":str}`
- `playhead.step`: `{"frames":i64}`

Marker and clip colors are label names (`Violet`, `Iris`, `Caribbean`, `Lavender`, `Cerulean`,
`Forest`, `Rose`, `Mango`, `Purple`, `Blue`, `Teal`, `Magenta`, `Tan`, `Green`, `Brown`,
`Yellow`) or `#RRGGBB`.

## Transitions

- `sequence.applyVideoTransition`: `{"clip":id?,"effect":"cross_dissolve|Cross Dissolve|…"?,"frames":i64?,"edge":"in"|"out"?,"align":"center"|"start"|"end"?,"params":{param:value}?,"reverse":bool?}` -> `{transition}`
- `sequence.applyAudioTransition`: the same, with an audio `effect` (`"constant_power"`, `"constant_gain"`, …); without `effect`, both use the person's default transitions
- `sequence.setTransition`: `{"transition":id,"duration":ticks?|"frames":n?,"align":…?,"params":{…}?,"reset":bool?}`
- `sequence.removeTransition`: `{"transitions":[id]?}`

Video transition ids include `cross_dissolve`, `dip_to_black`, `dip_to_white`, `film_dissolve`,
`additive_dissolve`, `morph_cut`, `whip`, `push`, `slide`, `linear_wipe`;
`effects.list {kind: "VideoTransition"}` lists all 112.

## Effects and keyframes

- `effects.list`: `{"kind":"Video"|"Audio"|"VideoTransition"|"AudioTransition"?,"folder":str?,"detail":bool?}`
- `effects.apply`: `{"clips":[id]?,"effect":"gaussian_blur|Gaussian Blur|…"}` -> `{applied: [{clip, effect, index}]}`
- `effects.setParam`: `{"clip":id,"effect":"motion"|index,"param":str,"mask":n?,"value":num|[x,y]|"#rrggbb"|bool|path|"option name","time":ticks?,"keyframe":bool?,"merge":bool|key?,"begin":bool?}` -> `{keyframes, param, value}`
- `effects.addKeyframe`: `{"clip":id,"effect":str|index,"param":str,"mask":n?,"time":ticks?}` -> `{added, mediaTime}` (toggles)
- `effects.setKeyframe`: `{"clip":id,"effect":str|index,"param":str,"mediaTime":ticks,"value":any?,"inInfluence":0..1?,"outInfluence":0..1?}`
- `effects.setInterpolation`: `{"clip":id,"effect":str|index,"param":str,"mediaTime":ticks,"interpolation":"linear|bezier|autoBezier|continuousBezier|hold|easeIn|easeOut"}`
- `effects.deleteKeyframe`: `{"clip":id,"effect":str|index,"param":str,"mediaTime":ticks}`
- `effects.remove` / `effects.toggleEnabled`: `{"clip":id,"index":n}`
- `effects.resetParam`: `{"clip":id,"effect":str|index,"param":str}`
- `edit.pasteAttributes`: `{"clips":[id]?,"motion":bool=true,"opacity":bool=true,…,"effects":bool|[effectId]=true}` (from the last `edit.copy`)

`effect` is an id or a name, or the index from `effects.apply`. A choice parameter takes its
option name (`"Teal & Orange"`) or index. `keyframe: true` animates the parameter and writes the
keyframe at `time`; once animated, every `setParam` writes a keyframe.

Every clip carries these effects:

| Effect | Params |
|---|---|
| `motion` | `position` [x, y] px, `scale` %, `scale_width` %, `uniform_scale`, `rotation` degrees, `anchor` [x, y] px, `anti_flicker` 0-1 |
| `opacity` | `opacity` %, `blend` (26 modes by name, e.g. `"Screen"`) |
| `time_remap` | `speed` % |
| `volume` (audio) | `bypass`, `level` dB (-287.5 to 15; 0 is unchanged) |

Color Grading (`lumetri`), by section:

| Section | Params |
|---|---|
| Basic Correction | `basic_on`, `input_lut`, `temperature`, `tint` (-100 to 100), `exposure` (-5 to 5), `contrast`, `highlights`, `shadows`, `whites`, `blacks` (-100 to 100), `saturation` (0 to 200, 100 unchanged) |
| Creative | `creative_on`, `look` (`None`, `Teal & Orange`, `Warm Film`, `Cool Blue`, `Bleach Bypass`, `Faded Matte`, `Monochrome`, `Golden Hour`, `Night`), `look_lut`, `look_intensity` (0 to 200), `faded_film`, `sharpen`, `vibrance`, `creative_sat`, `shadow_tint`, `highlight_tint` |
| Curves | `curves_on`, `curve_luma`, `curve_red`, `curve_green`, `curve_blue` (points `[[0,0],[0.25,0.21],[0.75,0.82],[1,1]]`), `hue_vs_sat`, `hue_vs_hue`, `hue_vs_luma`, `luma_vs_sat`, `sat_vs_sat` |
| Color Wheels | `wheels_on`, `wheel_shadows`, `wheel_midtones`, `wheel_highlights` ([x, y]), `wheel_shadows_l`, `wheel_midtones_l`, `wheel_highlights_l` |
| HSL Secondary | `hsl_on`, `hsl_hue`, `hsl_hue_range`, `hsl_sat_min`, `hsl_luma_min`, `hsl_luma_max`, `hsl_soft`, `hsl_show_mask`, `hsl_denoise`, `hsl_blur`, `hsl_temp`, `hsl_tint`, `hsl_sat`, `hsl_hue_shift` |
| Vignette | `vignette_on`, `vignette_amount` (-5 to 5), `vignette_midpoint`, `vignette_roundness`, `vignette_feather` |

Others used here: `auto_reframe` (`preset`, `offset`, `zoom`, `aspect`: `Sequence`, `Vertical
9:16`, `Square 1:1`, `Vertical 4:5`, `Horizontal 16:9`), `noise` (`amount`, `grain_size`) for
grain, `crop`, `transform`, `gaussian_blur`, `camera_shake`; audio `hard_limiter` (`max`,
`boost`, `lookahead`, `release`), `speech_enhance`, `denoise`, `parametric_eq`, `studio_reverb`.

## Color tools

- `lumetri.presets`: `{"folder":str?}` -> `{folders, presets: [{name, folder, description}]}`
- `lumetri.applyPreset`: `{"name":str,"clips":[id]?}`
- `lumetri.applyMatch`: `{"clip":id?,"referenceTime":ticks?|"referenceFrame":n?|"referenceTimecode":str?,"faceDetection":bool=true}` -> `{distanceBefore, distanceAfter, …}`
- `lumetri.setLook` / `lumetri.setInputLut`: `{"clip":id?,"lut":"lib:<id>"|"builtin:<id>"|""?,"path":str?}`
- `lut.import`: `{"path":str,"name":str?}`
- `lumetri.setSection`: `{"clip":id?,"section":"basic"|"creative"|"curves"|"wheels"|"hsl"|"vignette","on":bool?}`
- `scopes.read`: `{"scopes":["waveform","parade","histogram","vectorscopeYuv","vectorscopeHls"]?,"waveformType":"rgb|luma|yc|ycNoChroma"?,"columns":n=8,…,"time":ticks?|"frame"|"seconds"|"timecode"}` -> `{stats: {y, r, g, b: {min, mean, max}, saturation, hueDeg}, waveform: …}` in percent

## Frame size, speed, structure

- `clip.fitToFrame` / `clip.fillFrame`: `{"clips":[id]?}` -> `{clips: [{clip, scale}]}`
- `clip.speedDuration`: `{"clips":[id]?,"speed":percent=100,"reverse":bool,"ripple":bool,"maintainPitch":bool?,"interpolation":"frameSampling|frameBlending|opticalFlow"?}`
- `clip.frameHold`: `{"clips":[id]?,"time":ticks?}`
- `clip.insertFrameHoldSegment`: `{"clip":id?,"time":ticks?,"seconds":f64=2}`
- `clip.nest`: `{"name":str?}` on the selection -> `{clips, sequence}`
- `file.newAdjustmentLayer`: `{"seconds":f64=5,"bin":binId?}` -> `{item}`
- `file.newColorMatte` / `file.newBlackVideo`: `{"color":"#rrggbb"?,"seconds":f64=5,"bin":binId?}` / `{"seconds":f64,"bin":binId?}`
- `clip.replaceFromBin`: `{"clips":[id]?,"item":id?,"keepSourceIn":bool=false}`: swap in another take, keeping the edit
- `clip.sceneEditDetection`: `{"clips":[id]?,"sensitivity":0..100=50,"minShotFrames":n=6,"applyCuts":bool=true,…}`: cut a multi-shot take at its cuts
- `clip.enable` / `clip.link` / `clip.rename`: `{"clips":[id]?}` / `{"clips":[id]?}` / `{"clip":id?,"name":str?}`

## Audio

- `essentialSound.setType`: `{"clips":[id]?,"type":"dialogue|music|sfx|ambience"}`
- `essentialSound.set`: `{"clips":[id]?,"key":str,"value":any}` or `{"values":{key:value}}`
- `essentialSound.autoMatch`: `{"clips":[id]?,"target":lufs?}` -> `{clips: [{clip, measuredLufs, targetLufs, gainDb}]}`
- `essentialSound.generateDucking`: `{"clips":[id]?}` -> `{clips: [{clip, keyframes, regions, triggers}]}`
- `essentialSound.inspect`: `{"clips":[id]?}`
- `clip.audioGain`: `{"clips":[id]?,"mode":"set|adjust|normalizeMax|normalizeAll"?,"db":f64}`
- `clip.remix`: `{"clip":id?,"seconds":f64?,…,"segments":0..100?,"variations":0..100?}`
- `mixer.inspect`: `{"time":ticks?}`
- `mixer.setStrip`: `{"strip":"A1"|"S1"|"Mix"|id,"volumeDb":f64?,"pan":f64?,"muted":bool?,"solo":bool?,…}`
- `mixer.addInsert`: `{"strip":"A1"|"S1"|"Mix"|id,"effect":str,"slot":n?,"postFader":bool?}` -> `{slot}`
- `mixer.setInsert`: `{"strip":…,"slot":n,"enabled":bool?,"postFader":bool?,"params":{id:value}?}`
- `tts.voices`: `{}`; `basic-female` and `basic-male` are built in, `kokoro-*` voices come with `tts.downloadVoices` (335 MB)
- `tts.create`: `{"text":str,"voice":str?,"pitch":"extraLow|low|default|high|extraHigh"?,"pace":0.5..2?,"time":ticks?,"track":"A1"|id?}`: a scratch narration or temp voice-over

Essential Sound keys are dotted and strict (an unknown key is refused): `ducking.enabled`,
`ducking.against` (`["Dialogue"]`), `ducking.reduceDb`, `ducking.fadeS`, `ducking.sensitivity`
(0-10), `repair.noise.on`, `repair.noise.amount` (0-10), `repair.humHz`, `clarity.eqPreset`,
`creative.reverbPreset`, `volume.levelDb`, `mute`, and `<section>.enabled`. Auto-Match's
default targets: dialogue -23, music -25, SFX -21, ambience -30 LUFS.

## Titles

- `graphics.newText`: `{"text":str="New Text","position":[x,y]?,"box":[w,h]?,"vertical":bool=false,"size":px=100,"font":str?,"fontStyle":str?,"seconds":f64=5,"track":index?,"time":ticks?}` -> `{clip, layer}`
- `graphics.setText`: `{"clip":id?,"layer":n|name?,"text":str}`
- `graphics.set`: `{"clip":id?,"clips":[id]?,"layer":n|name?,"props":{"font":"Inter","font_style":"Bold","size":120,"align":"center","tracking":50,"leading":0,"fill_color":"#ffcc00","stroke":true,"stroke_width":6,"background":true,"shadow":true,"position":[x,y],"scale":100,"rotation":0,"opacity":100,…},"time":ticks?,"keyframe":bool?}`
- `graphics.newShape`: `{"shape":"rectangle|ellipse|polygon|path","position":[x,y]?,"size":[w,h]=[400,200],"seconds":f64=5,"track":index?,"time":ticks?}`

`graphics.set` props are snake_case (`font_style`, `fill_color`); `graphics.newText` takes
`fontStyle`. Point text's `position` is its alignment point on the first baseline.

## Captions

- `captions.newTrack`: `{"format":"Subtitle|CEA-608|CEA-708|Teletext","name":str?,"language":str?}` -> `{track}`
- `captions.add`: `{"track":id|"C1"?,"text":str?,"time":ticks?,"seconds":f64?,"durationSeconds":f64=3}` -> `{caption}`
- `captions.setText`: `{"caption":id?,"text":str?,"speaker":str|null?}`
- `captions.setTimes`: `{"caption":id?,"startTime|startFrame|startSeconds|startTimecode":…,"endTime|endFrame|endSeconds|endTimecode":…}`
- `captions.setStyle`: `{"track":id|"C1","font":str?,"fontStyle":str="SemiBold"?,"size":f32?,"color":"#rrggbb[aa]"?,"background":bool?,"backgroundColor":"#rrggbbaa"?,"align":"left|center|right"?,"anchor":"top|middle|bottom"?,"margin":0..0.45?,"lineSpacing":f32?,"outline":f32?,"outlineColor":str?,"reset":bool?}`
- `captions.list`: `{"track":id|"C1"?}`
- `captions.import` / `captions.export`: `{"path":str,"name":str?,"language":str?}` / `{"path":str,"format":"srt|vtt|scc|mcc|stl|ttml|dfxp"?,"track":id|"C1"?}`

`size` is in pixels at 1080 lines, scaled to the frame; `margin` a fraction of the frame height.
Captions on one track never overlap. Transcription commands (`sequence.transcribe`,
`transcript.createCaptions`) need a build with speech to text, which release builds lack
(`transcript.models` reports `available: false`).

## Looking at the cut

- `playhead.set {seconds}` then `ui.screenshot {panel: "Program"}`: the frame as the person sees
  it. Put the playhead back if they were watching somewhere else.
- `engine_screenshot(engine_id)`: the whole app, to show the person the timeline.
- `file.exportFrame {"path":str?,"format":"png|jpeg|tiff|bmp"?,"time":ticks?,"target":"source|program"?}`:
  a still at the sequence size, written where `path` says (keep it in the project folder).
- `scopes.read {time}`: the numbers behind the picture.

## Export

- `export.presets.list`: `{"query":str?,"category":str?,"format":str?}`
- `file.exportMedia`: `{"path":str,"preset":str?,"format":"h264|hevc|prores|dnxhr|…|wav|aac|mp3"?,"width":u32?,"height":u32?,"fps":f64?,"bitrateKbps":u32?,"bitrateMode":"cbr|vbr1Pass|vbr2Pass|crf"?,"crf":0..51=23,"hardwareEncoding":"off|auto"?,"audio":bool=true,"burnCaptions":bool=false,"captionSidecar":"srt|vtt"?,"loudnessLufs":f64?,"proresProfile":…?,"sequence":id?,"range":"entire|inOut|workArea|custom"?,"startSeconds":f64?,"endSeconds":f64?,"wait":bool=false}`
- `jobs.list` / `jobs.cancel`: `{}` / `{"job":id}`

With `wait: true` the call returns when the file is written: `{job, path, result: {bytes,
encoder, frames, render_fps, seconds}, offlineMedia, warnings}`. Without it, it returns the job
at once; poll `jobs.list` (`progress`, `etaSeconds`, `finished`). Always pass `range: "entire"`
unless you mean the In/Out range. Measured on four CPU cores with the software encoder: a
10-second 1080p cut took 24 s and a 5-second 1080x1920 one 6 s; `hardwareEncoding: "auto"` asks
for NVENC on an NVIDIA engine and falls back to software with a warning. Built-in presets
include `YouTube 1080p Full HD`, `YouTube 2160p 4K Ultra HD`, `Vimeo 1080p Full HD`, `High
Quality 1080p HD`, `TikTok 1080×1920`, `Instagram Reels 1080×1920`, `YouTube Shorts 1080×1920`,
`Social Vertical 1080×1920`, `Apple ProRes 422 HQ`, `H.264 High 10 Master`, `Waveform Audio 48
kHz 24-bit`.

## Undo and saving

`edit.undo {}` reverts one command (`{"undone": "Razor"}`), `edit.redo {}` repeats it. Every
command is one undo step, including a `timeline.place` with several `items`.
`file.save {}` saves to the project's path once `file.saveAs {path}` has given it one.
