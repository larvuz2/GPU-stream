<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# SoundCraft commands

The commands the music and audio workflows use, with parameters as SoundCraft's command registry
gives them (`soundcraft-cli commands --json`). Checked against SoundCraft 0.20.1: the registry
lists 483 commands, and every command and recipe below was run in a SoundCraft engine through
its control channel and read back, unless a line says "not run here". Parameter docs are copied
from the registry; `?` marks an optional key, `…` an abridged list.

## Calling SoundCraft

`engine_call(engine_id, method, params)` sends one request on SoundCraft's control channel:

- `engine.execute` `{command, params}`: runs any command id and returns its result.
- `engine.commands` `{filter?}`: every command whose id or label matches, with `id`, `label`,
  `menu`, `params` (its parameter doc), `enabled`, and `shortcut`.
- `session.inspect` `{detail?: "summary"|"full"}`: the whole session (below). `full` adds every
  insert's parameters.
- `ui.inspect`: window (`Edit` or `Mix`), `playing`, `position`, `audio_device`, the status line
  (`status`), and `edit_layout` (the timeline's and each track row's rectangle, for clicking).
- `ui.set` `{window: "Edit"|"Mix"}`: shows that window.
- `ui.screenshot` `{path?}`: a PNG of SoundCraft's window, to `path` in the engine or as
  `png_base64`. `engine_screenshot(engine_id)` is the simpler way to look.
- `ui.click` `{x, y}`, `ui.key` `{key, cmd?, shift?}`, `ui.text` `{text}`, `ui.menu.invoke`
  `{path}`: the window's own input, for the few things with no command (the recovery question,
  below).

Replies are the command's result, or an error with SoundCraft's reason, such as ``bad parameters
for `mix.volume`: unknown track "Nope"``. A command through `engine.execute` never opens a
dialog. SoundCraft answers a request within 90 seconds or not at all, which no command here came
near (a 3 minute 49 second song bounced in 8 seconds).

**Finding a command.** `engine.commands {filter: "bounce"}`, then read `params`. Ids follow the
menus of the workflow SoundCraft models (File, Edit, Track, Clip, Event, AudioSuite, Options,
Setup), with `mix.*`, `midi.*`, `automation.*`, `transport.*`, and `markers.*` beside them.

**Files and the shell.** `engine_exec(engine_id, command)` runs bash in the engine, in its
environment: `mkdir -p`, `ffmpeg`, `ffprobe`, and `soundcraft-cli` are there. `engine_files(engine_id,
path?)` lists the project folder. SoundCraft's working directory is the project folder, so a
relative path such as `masters/song.wav` lands in it.

## Units and addressing

| Thing | How it is written |
|---|---|
| Position on the timeline | samples as a number (`96000`), `{"seconds": 2.5}`, or a string: `"bars_beats:5|1|000"`, `"min_secs:0:12.500"`, `"timecode:01:00:10:00"`, `"samples:48000"` |
| Bars and beats | `bar|beat|tick`, bars and beats from 1, ticks 0-959 |
| MIDI note times | **ticks from the clip's start, 960 to a quarter note**: a 16th is 240, an 8th 480, a bar of 4/4 is 3840 |
| Range | `start` and `end` (or `length`); left out, the edit selection |
| Track | its id or its name (`"Bass"`); several as `tracks: ["Bass", "Keys"]` |
| Clip, bus, marker | the id a command returned or `session.inspect` shows; tracks, clips, sources, buses, and markers share one id space |
| Insert and send slots | `0`-`9` or `"a"`-`"j"` |
| Level | dB; a fader runs -144 to +12 |
| Pan | -1 (left) to 1 (right) |
| Pitch | MIDI note numbers, 60 = middle C (C4), 69 = A 440 Hz |
| Velocity | 1-127 |

The session runs at 48,000 samples a second unless `session.new` said otherwise, and a sample
position does not move when the tempo changes; a `bars_beats` position is worked out against the
tempo map as the command runs. Set the tempo **before** making MIDI clips: `midi.new_clip` turns
its `end` into samples, and a later tempo change leaves the clip's box where it was.

## Reading state

`session.inspect` returns `name`, `path`, `dirty`, `sample_rate`, `bit_depth`, `frame_rate`,
`tempo` (`[{bpm, tick}]`), `meter`, `markers`, the buses (a key SoundCraft spells with a double s), `sources` (each with `loaded`),
`length_samples`, `selection`, `transport`, `undo` (the last step's label), and `tracks`, in
their order on screen. A track has `id`, `name`, `kind` (`audio`, `instrument`, `midi`, `aux`,
`master`, `vca`, `folder`, `video`), `format`, `volume_db`, `pan` (two values on a stereo track),
`mute`, `solo`, `input`, `output`, `instrument`, `inserts` (`plugin`, `slot`, `bypass`,
`params` with `full`), `sends`, `automation` (`param`, `points`), and `clips` (`id`, `start`,
`end`, `length`, `gain_db`, `fade_in`, `fade_out`, `notes`).

`track.inspect {track}` and `clip.inspect {clip}` return one of them; a MIDI clip's
`note_list` and `midi.notes {clip}` list its notes as `{pitch, start, length, velocity,
channel}`, `start` and `length` in ticks. `transport.status {}` gives `{playing, position}`.
`session.format_time {at: samples, format: "bars_beats"|"min_secs"|"timecode"}` converts a
position to text. `engine.plugins {}` lists every built-in processor with its parameters.

## Traps (each seen in a run)

1. **A bounce does not make its folder.** `file.bounce_mix` to `masters/x.wav` answered "audio
   I/O failed: No such file or directory" until `engine_exec(engine_id, "mkdir -p masters
   stems")`. `file.bounce_stems` and `session.save_as` make theirs.
2. **A bounce ends at the last clip's end** unless `end` says otherwise, which cuts reverb and
   delay tails and long releases. Pass `end`: the last clip's `end` plus 2-4 seconds (plus the
   reverb's decay).
3. **Mute and solo are part of a bounce.** A soloed track bounces alone; a muted track is
   missing. `mix.clear_solos {}` before every bounce, and check `mute` in `session.inspect`.
4. **Stems go through the master's inserts**, each stem by itself. With a maximizer on the
   master, every stem is pushed to the ceiling alone and they no longer sum to the mix (a drum
   stem peaked at -0.6 dBFS). Bypass the master's limiter for stems (`mix.insert_bypass`); the
   four stems then summed to the unlimited mix within 0.1 LU.
5. **A stereo track has two pans**, the left channel's and the right's (`pan: [-1, 1]`), and
   `mix.pan` sets one: `index: 0` is the left channel's, `1` the right's, `0` when left out.
   `mix.pan {tracks: ["Keys"], pan: 0}` alone leaves the right channel hard right. Set both.
6. **Notes past the clip's end are stored and silent.** A note at tick 5760 of a one-bar clip
   was accepted and never played. Make the clip as long as the part first.
7. **Out-of-range values clamp without an error**: `hpf_freq: 99999` became 2000 Hz, which
   silenced a bass. Unknown parameter ids are refused (``has no parameter(s): nope``). Read back
   what you set with `track.inspect`.
8. **The maximizer's ceiling is a sample peak**, not a true peak: `ceiling: -1.0` measured -0.77
   and -0.45 dBTP. Use `ceiling: -1.5` for a -1 dBTP delivery and read `true_peak_db` in the
   bounce's reply.
9. **A master track is named `Master 1`** whatever `name` you gave `track.new`; address it by
   that name, or `track.rename` it.
10. **`session.new` leaves the project's file.** The new session has no path, and
    `session.save {}` then fails. A project already has its session open (`project.scraft` in
    the project folder); build in it. For a second piece, `session.new`, then `session.save_as
    {path}` at once, in the project folder's top level so the next engine start finds it (it
    opens the newest `.scraft` there).
11. **The session's name is its file's name** after a save, and stems are named `<session> -
    <track>.wav`. Rename or move them with `engine_exec` to the delivery names.
12. **Nothing asks before `session.open` or `session.new` replaces unsaved work.** `session.save
    {}` first.
13. **Automation takes any parameter name and value after `plugin:<slot>:`.** A point on
    `plugin:a:nope` and a send level of 900 were both accepted. Copy parameter ids from the
    processor table, keep values in range, and read `automation` back in `track.inspect`. An
    instrument's parameters are not automatable (`plugin:instrument:cutoff` is refused).
14. **Compressed formats come in, not out.** MP3, M4A, Ogg, FLAC, AIFF, and the audio of MP4 and
    MOV import (converted to the session's rate); export is WAV, AIFF, or FLAC only. Make an MP3
    or M4A from the WAV with ffmpeg (below).

## Session and files

| Command | Params |
|---|---|
| `session.new` | `{name?: 'Untitled', sample_rate?: 48000, bit_depth?: 24, template?: blank\|demo}` |
| `session.open` | `{path}` -> `{name, tracks, missing}` (media that could not be loaded) |
| `session.save` / `session.save_as` / `session.save_copy` | `{path?, replace?: false}` / `{path, replace?: false}` |
| `setup.session` | `{frame_rate?: '24'\|'25'\|'29.97 Drop'…, bit_depth?: 16\|24\|32f, timecode_start?: position, name?}` |
| `file.import_audio` | `{path \| paths: [..], track?: target track, at?: position, new_tracks?: true}` -> `{imported: [{clip, source, track, frames, channels}]}` |
| `file.import_midi` | `{path, at?}` (not run here) |
| `file.import_video` | `{path, at?}`: a Video track for the picture (H.264, ProRes, Motion JPEG) and its audio on a new track |
| `file.export_midi` | `{path, tracks?}` |

`file.import_audio` with only `path` makes a new track named after the file. To land on a track
you made: `{path, track: "Rain", new_tracks: false, at: 0}`. A saved session keeps copies of its
audio in `Audio Files/` beside the session file and earlier saves in `Backups/`.

## Tempo, meter, key, markers

| Command | Params |
|---|---|
| `event.tempo` | `{bpm, at?: position}` -> `{bpm, tick}`; without `at`, the session's tempo from the start |
| `event.tempo_linear` | `{start?, end?, start_bpm?, end_bpm, resolution?: '1/8'}`: a ramp (not run here) |
| `event.meter` | `{numerator, denominator, at?: position}` |
| `event.add_key_change` | `{key: 'F minor', at?}` (labels the session; it transposes nothing) |
| `event.identify_beat` | `{start?, end?, bars?: 1, beats?: 0}`: sets the tempo so the selection lasts that many bars (not run here) |
| `markers.add` | `{name?, at?, start?, end?}` -> `{id, number}` |
| `markers.edit` / `markers.delete` | `{number \| id, name?, at?, …}` / `{number \| id}` |

A tempo change at bar 5 of a 96 BPM session returned `tick: 15360` (4 bars x 3840). Mark every
section (`Intro`, `Verse 1`, …) and, to picture, every hit point: the person sees them on the
ruler and you address sections by them.

## Tracks and routing

| Command | Params |
|---|---|
| `track.new` | `{count?: 1, format?: mono\|stereo\|5.1…, kind?: audio\|aux\|master\|midi\|instrument\|vca\|folder, name?, instrument?: plugin id, rows?: [objects with the same fields]}` -> `{tracks: [id]}` |
| `track.rename` / `track.delete` / `track.duplicate` | `{track, name}` / `{tracks?}` / `{tracks?, …}` |
| `track.move` | `{track, to: index}` |
| `track.color` | `{tracks?, color: [r,g,b] \| palette index}` |
| `track.input` | `{tracks?, input: none\|bus name\|hardware name}` |
| `track.output` | `{tracks?, output: main\|none\|bus name}` |
| `mix.new_bus` | `{name, format?: stereo}` -> `{bus}` |
| `track.freeze` / `track.commit` / `track.bounce` | `{tracks?}` (not run here) |

One call builds a session's tracks, in order:

```text
track.new {rows: [
  {kind: "instrument", name: "Drums", instrument: "drum_synth"},
  {kind: "instrument", name: "Bass",  instrument: "subtractive_synth"},
  {kind: "instrument", name: "Keys",  instrument: "subtractive_synth"},
  {kind: "audio", format: "stereo", name: "Rain"},
  {kind: "aux",   format: "stereo", name: "Plate"},
  {kind: "master", format: "stereo"}]}
```

**An effect return** is a bus, an aux track that listens to it, and sends into it:

```text
mix.new_bus {name: "Plate Send"}
track.input {tracks: ["Plate"], input: "Plate Send"}
mix.insert  {track: "Plate", plugin: "plate_reverb", params: {mix: 100, decay: 1.9, pre_delay: 28, low_cut: 250}}
mix.send    {track: "Keys", bus: "Plate Send", level_db: -10}
```

**A submix** (a drum bus, a dialogue bus) is the same bus and aux, with the tracks' outputs
moved onto it: `track.output {tracks: ["Kick", "Snare"], output: "Drums"}`. The aux's fader then
moves them together (a -12 dB fader lowered the bounce 12.0 LU) and its inserts process them as
one.

## Instruments

Three are built in, set as `instrument` in `track.new` or with `mix.instrument {track, plugin,
params?}`; one parameter at a time is `mix.instrument_param {track, param, value}`.

**`drum_synth`**, a synthesized kit on a General MIDI style map:

| Notes | Sound | Notes | Sound |
|---|---|---|---|
| 35, 36 | kick | 46 | open hat |
| 38, 40 | snare | 41, 43 / 45 / 47, 48 / 50 | floor, low, mid, high tom |
| 37, 39 | clap | 49, 57 | crash |
| 42, 44 | closed hat (chokes the open hat) | 51, 59 | ride |

Parameters: `level` (dB), `kick_tune`, `snare_tune`, `tom_tune` (±12 semitones), `kick_decay`
(50-2000 ms, 450), `snare_snappy` (0-100 %), `snare_decay`, `hat_decay` (20-500 ms, 80),
`open_hat_decay`, `tom_decay`, `cymbal_decay`. Other notes are silent.

**`subtractive_synth`**, two oscillators into a filter, for bass, keys, pads, and leads:
`osc1_wave`, `osc2_wave` (0 saw, 1 square, 2 sine, 3 triangle), `osc2_semitones` (±24),
`osc2_detune` (cents, 7), `osc_mix` (%), `cutoff` (20-20000 Hz, 2000), `resonance` (%),
`filter_env_amount` (±100 %), `amp_attack`, `amp_decay`, `amp_release` (ms), `amp_sustain` (%),
`filter_attack`, `filter_decay`, `filter_sustain`, `filter_release`, `glide` (ms), `velocity`
(sensitivity, %), `level` (dB, -6). Starting patches are in writing.md.

**`sampler`**, one audio file played across the keyboard: `mix.sampler_load {track, path,
params?}` -> `{frames, channels, sample_rate}`. Parameters: `root_note` (60), `transpose`,
`fine_tune`, `key_low`, `key_high`, `attack`, `decay`, `sustain`, `release`, `play_mode` (0
gate, 1 one shot), `loop_mode` (0 off, 1 forward, 2 ping-pong), `loop_start`, `loop_end` (%),
`start` (%), `velocity`, `level`. One sample to a track: a kit of samples is one instrument
track per sound, each with `play_mode: 1`.

## MIDI

| Command | Params |
|---|---|
| `midi.new_clip` | `{track, start?, end? \| length?}` -> `{clip, start, end}` (samples) |
| `midi.note_add` | `{clip, pitch, start_ticks, length_ticks?: 480, velocity?: 100, channel?: 0}` -> `{index, notes}` |
| `midi.notes` | `{clip}` -> `{notes: [{pitch, start, length, velocity}]}` |
| `midi.note_edit` | `{clip, index, pitch?, start_ticks?, length_ticks?, velocity?}` |
| `midi.note_delete` / `midi.notes_move` | `{clip, indices: [n]}` / `{clip, indices: [n], ticks?: 0, semitones?: 0}` |
| `event.quantize` | `{grid?: '1/16' \| ticks, strength?: 100, swing?: 0, clips?}` |
| `event.transpose` | `{semitones, clips?}` |
| `event.change_velocity` | `{set? \| add? \| scale? \| min?, max?, clips?}` |
| `event.change_duration` | `{set? \| add? \| scale? \| legato?: gap, clips?}` |
| `event.step_input` | `{track?, pitch?: 60 \| pitches?: [..], duration?: '1/8' \| ticks, velocity?: 100, rest?, advance?: true}` -> `{clip, next, notes}` |
| `clip.loop` | `{clips?, count?: n, length?, fill?}`: `count` is the clip plus its repeats |
| `edit.duplicate` | `{tracks?, start?, end?}`: copies the range to just after itself |

One note is one `midi.note_add`; `index` in the reply is the note's place in the clip's list,
sorted by start, so indices shift as notes are added: read `midi.notes` before editing by index.
`event.quantize {grid: "1/16", swing: 60, clips}` moved every off 16th from tick 240 to 288 (60 %
of the 8th); `strength: 50` moves notes halfway to the grid. There is no command that randomizes
timing or velocity: compute the humanized ticks and velocities yourself as you write the notes
(writing.md). A part that repeats is written once and repeated with `clip.loop {clips, count}`
or `edit.duplicate`, then varied where the arrangement asks.

## Audio clips and editing

| Command | Params |
|---|---|
| `edit.select` | `{tracks?, start?, end?, clips?}` |
| `edit.separate` | `{tracks?, at? \| start/end}`: a cut |
| `edit.cut` / `edit.clear` / `edit.copy` / `edit.paste` | `{tracks?, start?, end?}` / `{tracks?, at?}` |
| `edit.mode` | `{mode: shuffle\|slip\|spot\|grid}` |
| `edit.move_clips` | `{clips?, by?: samples, to?: position, track?}` |
| `edit.trim_clip` | `{clip, start?, end?}` |
| `edit.fades_create` | `{clip, side: in\|out, length: samples, shape?: linear\|equal power\|s-curve\|exponential\|logarithmic}` or `{tracks?, start?, end?, shape?}` over a cut for a crossfade |
| `clip.gain` | `{clips?, db \| delta_db}` |
| `edit.strip_silence_preview` | `{threshold_db?: -48, min_length_ms?: 50, pad_before_ms?: 5, pad_after_ms?: 20, tracks?, start?, end?}` -> `{tracks: [{track, ranges: [[start, end]]}]}`: the ranges that hold sound; changes nothing |
| `edit.strip_silence` | the same settings, on the edit selection, `mode?: strip\|extract\|separate` |
| `edit.space_clips` | `{clips?, gap?: samples\|{seconds}, mode?: end_to_start\|start_to_start}` |
| `edit.consolidate` | `{tracks?, start?, end?}` (not run here) |
| `audiosuite.process` | `{process: normalize\|reverse\|gain\|time_stretch\|pitch_shift\|<plugin id>…, params?, clips?}`; `normalize` takes `params: {target_db}` (-0.1) |
| `clip.conform_to_tempo` / `edit.tce_to_timeline` | stretch audio to the tempo or to a selection (not run here) |

In `slip` mode (the default) a cut leaves a gap. In `shuffle` mode `edit.cut {tracks: ["VO"],
start, end}` closes it: the clips after it moved earlier by the cut's length. Set the mode back
to `slip` afterwards. A crossfade over a cut: `edit.fades_create {tracks: ["VO"], start: cut -
1000, end: cut + 1000, shape: "equal power"}`.

## Mixer

| Command | Params |
|---|---|
| `mix.volume` | `{tracks?, db: -144..12 \| delta_db}` |
| `mix.pan` | `{tracks?, pan: -1..1, index?: 0\|1}` |
| `mix.mute` / `mix.solo` | `{tracks?, value?: bool}`; `mix.clear_solos {}`, `mix.clear_mutes {}` |
| `mix.insert` | `{track?, slot?: 0..9, plugin: id, params?: {id: value}}` -> `{slot}` |
| `mix.insert_param` / `mix.insert_params` | `{track?, slot, param, value}` / `{track?, slot, params: {id: value}}` |
| `mix.insert_bypass` / `mix.insert_remove` / `mix.insert_move` | `{track?, slot, value?}` / `{track?, slot}` / `{track?, from, to}` |
| `mix.send` | `{track?, slot?, bus: name, level_db?: 0, pre_fader?: false}` -> `{slot}` |
| `mix.send_level` / `mix.send_remove` | `{track?, slot, db?, pan?, mute?, pre_fader?}` / `{track?, slot}` |
| `mix.phase_invert` / `mix.trim` | `{tracks?, value?}` / `{tracks?, db}` |

Inserts run top to bottom, slot 0 first, before the fader; sends are after the fader unless
`pre_fader`. `mix.insert` without `slot` takes the first free one. A fader at 0 dB is unity (a
stereo file bounced at the level it came in at); a mono track panned to the center is 3 dB down
in each speaker and at full level when panned hard.

### Built-in processors

Parameter ids, with range and default. Toggles are 0 or 1; choices are the index in the list.

| Plugin | Parameters |
|---|---|
| `eq_7band` | `hpf_on`, `hpf_freq` (10-2000 Hz, 80), `hpf_slope` (0-3: 6, 12, 18, 24 dB/oct); `low_shelf_freq`/`_gain`/`_q`; `low_mid_freq` (250)/`_gain`/`_q`; `mid_freq` (1000)/`_gain`/`_q`; `high_mid_freq` (4000)/`_gain`/`_q`; `high_shelf_freq` (8000)/`_gain`/`_q`; `lpf_on`, `lpf_freq` (1000-20000, 18000), `lpf_slope`; `input_gain`, `output_gain`. Gains ±24 dB, Q 0.1-10 |
| `eq_1band` | `type` (0 peak, 1 low shelf, 2 high shelf, 3 high pass, 4 low pass, 5 notch, 6 band pass), `freq`, `gain`, `q`, `output_gain` |
| `compressor` | `threshold` (-60..0 dB, -20), `ratio` (1-100, 4), `attack` (0.01-300 ms, 10), `release` (5-3000 ms, 100), `knee` (0-24 dB, 6), `makeup` (0-40 dB), `sc_hpf_on`, `sc_hpf_freq` (20-500 Hz), `limiter`, `lookahead` (0-10 ms), `mix` (%, parallel compression) |
| `expander_gate` | `threshold` (-80..0, -40), `ratio`, `range` (0-80 dB), `attack`, `hold`, `release` |
| `de_esser` | `freq` (2000-16000 Hz, 6000), `range` (0-40 dB, 10), `threshold` (-30), `listen` |
| `maximizer` | `threshold` (-30..0 dB, 0: lower is louder), `ceiling` (-30..0, -0.3), `release` (1-1000 ms, 50) |
| `channel_strip` | gate, compressor, and four-band EQ in one: `gate_on`, `gate_threshold`, `comp_on`, `comp_threshold`, `comp_ratio`, `comp_attack`, `comp_release`, `comp_makeup`, `eq_on`, `hpf_on`, `hpf_freq`, `low_gain`/`_freq`, `mid_gain`/`_freq`/`_q`, `high_gain`/`_freq`, `input_gain`, `output_gain` |
| `room_reverb`, `plate_reverb` | `mix` (%), `pre_delay` (0-250 ms), `decay` (0.1-20 s; room 1.2, plate 2.5), `size` (%), `damping` (1000-20000 Hz), `diffusion`, `width` (%), `low_cut` (20-1000 Hz) |
| `mod_delay` | `time` (1-2000 ms, 250), `feedback` (±99 %, 30), `mix` (%), `mod_rate`, `mod_depth`, `lpf` (500-20000 Hz) |
| `chorus`, `flanger`, `phaser` | `rate` (Hz), `depth` (%), `feedback`, `mix`; chorus adds `delay`, `spread`; phaser `stages`, `center` |
| `saturator` | `drive` (0-36 dB, 6), `bias` (%), `tone` (1000-20000 Hz), `mix`, `output` |
| `lofi` | `bits` (1-24, 8), `sample_rate` (500-48000 Hz), `noise` (%), `mix` |
| `subharmonic` | `range` (0-3), `lower_gain`, `upper_gain`, `direct_gain`, `mix`, `output`, … |
| `pitch_shifter` | `semitones` (±24), `cents`, `mix` |
| `auto_pan` | `rate` (BPM), `width`, `waveform`, `link_tempo`, `duration`, … |
| `gain`, `trim`, `invert`, `dc_offset_removal`, `time_shift`, `ring_mod`, `rectifier`, `signal_generator`, `dither` | utilities; `gain {gain}` (-96..24 dB) |

The delay's `time` is milliseconds, not a note value: an 8th note is `30000 / bpm` ms, a dotted
8th `45000 / bpm`, a quarter `60000 / bpm`. `engine.plugins {}` has every parameter with its
range, and CLAP and VST3 plug-ins found on the machine load by `clap:` and `vst3:` ids
(`engine.clap_plugins {}`); a Moody engine has none installed.

## Automation

| Command | Params |
|---|---|
| `automation.set_point` | `{track?, param: volume\|pan\|mute\|send_a_level\|plugin:a:<param id>, at, value}` |
| `automation.write_range` | `{track?, param, start?, end?, value}` |
| `automation.clear` | `{track?, param?, start?, end?}` |
| `mix.automation_mode` | `{tracks?, mode: off\|read\|touch\|latch\|write\|trim}` (read is the default) |

Points are joined by straight lines and the value before the first point is the first point's:
a fade is two points (`volume` -60 at the start, -9 two bars later), a duck is four. `volume`
is dB, `pan` -1..1, `send_a_level` the send in slot a in dB, and `plugin:a:threshold` the
`threshold` of the insert in slot a. Once a track has volume automation, `mix.volume` no longer
decides its level anywhere, since the first and last points hold before and after them (a
`mix.volume` of -6 changed nothing in the bounce): move the points, or use `clip.gain` or a
`gain` insert for an overall change.

## Transport and looking

| Command | Params |
|---|---|
| `transport.play` / `transport.stop` | `{from?: position}` / `{}` |
| `transport.locate` / `transport.rtz` | `{at}` / `{}` |
| `options.loop_playback` | `{value?: bool}`, with a selection (`edit.select {start, end}`) |
| `view.zoom_fit` / `view.zoom_to_selection` | `{width_px?: 1200}` |
| `track.view` | `{tracks?, view: waveform\|notes\|volume\|pan\|…}` |

Playback is what the person hears in the stream: start it where you want them to listen
(`transport.play {from: "bars_beats:9|1|000"}`), say what to listen for, and stop it. You
cannot hear it yourself: your ears are the bounce's numbers and `engine_exec` with ffmpeg.

## Picture

| Command | Params |
|---|---|
| `file.import_video` | `{path, at?}` -> `{video: {clip, track, info: {codec, frame_rate, duration, width, height, decodable}}, audio: {clip, track}}` |
| `video.list` | `{}` -> `{videos: [{name, path, frame_rate, duration, file_found, offline}]}` |
| `video.offset` | `{track?, at: position}`: moves the picture's start (not run here) |
| `setup.session` | `{frame_rate: '24', timecode_start: "01:00:00:00"}` |

An H.264 MP4 at 24 fps imported with its picture on a Video track and its sound on a new track
`<name> audio`; `decodable` says whether SoundCraft can show the picture (H.264, ProRes, and
Motion JPEG; not HEVC). `"timecode:01:00:02:12"` addresses a frame once the frame rate and the
timecode start are set. SoundCraft shows picture; it does not export video.

## Bounce and delivery

| Command | Params |
|---|---|
| `file.bounce_mix` | `{path, format?: wav\|aiff\|flac, bit_depth?: 16\|24\|32f, start?, end?, source?: main\|bus name, normalize?: false, dither?: true, fold_down?: stereo}` -> `{path, seconds, bytes, lufs, peak_db, true_peak_db}` |
| `file.bounce_stems` | `{dir, format?, bit_depth?, start?, end?, dither?, fold_down?}` -> `{files}` |
| `file.export_clips` | `{dir, clips?, format?: wav}` (not run here) |

The reply is the meter: `lufs` is the integrated loudness (BS.1770), `true_peak_db` the true
peak. ffmpeg's EBU R 128 meter read the same file within 0.1 LU. `source: "Drums"` bounces one
bus. `normalize: true` raises the file to full scale (a peak of -0.1 dBFS), which is not a
loudness target: leave it off for deliveries. A stem is one audio or instrument track soloed,
through its sends, its auxes, and the master (trap 4); muted tracks get none.

Timings on a machine without a GPU: a 26-second mix in 1.1 s, a 3 min 49 s mix in 8 s, its four
stems in 31 s.

**Hitting a loudness target** with the master's maximizer: bounce, read `lufs`, lower
`threshold` by the difference, bounce again. From -29.5 LUFS, `threshold: -15.5` gave -14.6 and
`-16.0` gave -14.2. More than about 6 dB of that is the limiter doing a mix's job: raise the
tracks first (mixing.md).

**Compressed copies and other rates**, from the WAV, with `engine_exec`:

```bash
ffmpeg -y -i masters/song.wav -c:a libmp3lame -b:a 320k masters/song.mp3
ffmpeg -y -i masters/song.wav -c:a aac -b:a 256k masters/song.m4a
soundcraft-cli convert masters/song.wav masters/song-44k.wav --rate 44100 --bit-depth 16
```

**Checking a file** the way a delivery spec is written:

```bash
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,duration -of default=nw=1 masters/song.wav
ffmpeg -nostats -i masters/song.wav -af ebur128=peak=true -f null - 2>&1 | tail -12
```

## Undo, saving, recovery

`edit.undo {}` reverts one command and `edit.redo {}` repeats it; `engine.history {}` lists the
steps. `session.save {}` writes the session; do it after every stage, since an engine that
stops (it does when unused) keeps only what was saved.

When an engine starts on a project whose last run ended with unsaved changes, SoundCraft opens
the saved session with a **Recover Unsaved Work** question over the window, and `session.inspect`
shows the saved state. Take `engine_screenshot`: if the question is there, ask the person, then
click **Recover** or **Discard** with `ui.click {x, y}` at the button (Recover was at 890, 489
on the 1920x1080 screen), read `ui.inspect`'s `status` ("Recovered …"), and `session.save {}`.

## What SoundCraft cannot do yet

SoundCraft is pre-alpha. From its own gap list (`docs/gaps.md`) and these runs:

- **No sidechain inputs**: no compressor keyed from another track, so no sidechain "pumping"
  and no automatic ducking. Duck with volume automation (mixing.md has the recipe).
- **No MP3, AAC, or Ogg export**, and **no video export**: ffmpeg for the first, FilmCraft for
  a film with its sound.
- **Instruments are three**: a drum synth, a two-oscillator subtractive synth, and a one-sample
  sampler. No sampled piano, strings, guitars, or orchestral library, no multi-sample
  instruments, no round robins. Realistic acoustic parts come from audio the person brings or
  you generate, not from MIDI.
- **No third-party plug-ins on the engine** (CLAP and VST3 hosting exists; none are installed),
  and the built-in set has no multiband compressor, linear-phase EQ, convolution reverb, pitch
  correction, or noise reduction.
- **No speech-to-text**, so no transcript-based podcast editing; no spectral repair.
- **Recording** needs an input device the engine does not have: the person's microphone does
  not reach SoundCraft. Voice comes in as files.
- **No randomize or humanize command**, no groove templates beyond `swing`, no chord or scale
  tools: you write the notes.
- **Elastic audio is one algorithm** and unproven here; prefer setting the session's tempo to
  the audio over stretching the audio.
- **Immersive deliveries** (Dolby Atmos, ADM BWF, binaural) and **session exchange** (AAF
  export, OMF) are not there; surround bus formats exist and were not run here.
- **The control channel has no token**: it answers anything inside the engine's own machine,
  and nothing outside it.
