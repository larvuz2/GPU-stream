<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Mixing, mastering, delivery, and picture

A mix is built in an order, and each step has a number you can read back. You cannot hear the
session: your ears are the bounce's reply (`lufs`, `peak_db`, `true_peak_db`), ffmpeg's meters
through `engine_exec`, and the person, who hears the stream. Measure, change one thing, measure
again, and ask them to listen at every checkpoint.

## The order

1. **Organize.** Name and color tracks, order them (drums, bass, harmony, leads, vocals,
   effects returns, master), mark the sections.
2. **Gain stage.** Faders down, then a static balance.
3. **Pan.**
4. **EQ** to make room, **compression** to control, in that order per track.
5. **Sends:** one reverb and one delay return for the whole mix.
6. **Automation:** rides, fades, mutes, section changes.
7. **Master:** a limiter to the delivery's loudness, then the bounce and its check.

Save after each (`session.save {}`).

## Gain staging and the static balance

- Leave headroom: with every fader up and nothing on the master, the mix should peak between
  -10 and -6 dBFS. A bounce with the master's limiter bypassed tells you (`peak_db`). Louder
  than that, pull every source down by the same amount (their `level` parameters or faders),
  not the master.
- Build from the most important element. Songs: kick, then bass against it, then snare, then
  the lead or vocal, then harmony, then everything else tucked under. Podcasts: the host's
  voice at its target, everything else against it. Cues: the element that carries the scene.
- Starting faders that have worked here for a synth arrangement, to adjust from: drums -5,
  bass -7, keys or pad -9 to -12, lead -8, texture bed -16 to -24, reverb return -3 to -8.
- Check each part alone only to find a problem; judge it in the mix. To measure one track,
  `mix.solo {tracks: [name], value: true}`, bounce a section, `mix.clear_solos {}`.
- A fader is a decision, not a fix: if a part needs more than ±6 dB from where it started, its
  sound or arrangement is the problem (writing.md).

## Panning and width

- **Center:** kick, bass, snare, lead vocal, lead instrument. Low frequencies stay mono.
- **Sides:** doubled parts opposite each other, hats slightly off center (±0.2), harmony and
  pads wide, percussion and ear candy placed by hand, effects returns full width.
- A stereo track's two pans set its width (soundcraft-commands.md, trap 5): `-1, 1` is full
  width, `-0.7, 0.7` narrower, `-0.3, 0.6` narrower and leaning right, `0, 0` mono.
- A mono track at center is 3 dB down in each speaker, by the pan law; hard panned it is not.
- Balance the sides: something on the left wants an answer on the right.
- Check mono: `ffmpeg -i mix.wav -ac 1 mono.wav` and measure it. A mix that loses more than
  about 3 LU in mono has phase trouble, usually a chorus or a wide pad: narrow it.

## EQ

Cut to make room before you boost to add; narrow cuts, wide boosts; 2-4 dB moves, rarely more.
`eq_7band` has a high-pass, a low shelf, three bells, a high shelf, and a low-pass.

| Range | What lives there | Typical move |
|---|---|---|
| below 30-40 Hz | rumble, nothing musical | high-pass everything that is not the kick or bass |
| 40-100 Hz | kick's weight, bass's bottom | give it to one of them; high-pass the rest at 80-150 Hz |
| 100-250 Hz | warmth, body | too much is boom; a small cut on bass or keys clears it |
| 250-500 Hz | mud, boxiness | the usual cut, 2-4 dB, on pads, keys, guitars, room-heavy voices |
| 500 Hz-2 kHz | body of most instruments, honk at 800-1000 | cut harmony here to seat a vocal |
| 2-5 kHz | presence, attack, intelligibility | a small boost on the lead; cut competing parts; too much is harsh |
| 5-8 kHz | sibilance, hat and snare crack | `de_esser` on a voice rather than an EQ cut |
| 8-16 kHz | air, sheen | a gentle high shelf on the lead or the overheads; low-pass dark parts at 8-12 kHz |

Starting points, as `mix.insert {track, plugin: "eq_7band", params}`:

| Source | Params |
|---|---|
| Bass | `hpf_on: 1, hpf_freq: 32, low_mid_freq: 250, low_mid_gain: -2.5` |
| Keys or pad | `hpf_on: 1, hpf_freq: 160, low_mid_freq: 350, low_mid_gain: -2, high_shelf_gain: -2` (when a lead needs the top) |
| Lead synth | `hpf_on: 1, hpf_freq: 200, high_mid_freq: 3000, high_mid_gain: 2` |
| Spoken voice | `hpf_on: 1, hpf_freq: 80, low_mid_freq: 300, low_mid_gain: -3, high_mid_freq: 4000, high_mid_gain: 2, high_shelf_gain: 1.5` |
| Sung voice | `hpf_on: 1, hpf_freq: 100, low_mid_freq: 250, low_mid_gain: -2, high_mid_freq: 3500, high_mid_gain: 2, high_shelf_freq: 10000, high_shelf_gain: 2` |
| Texture bed | `hpf_on: 1, hpf_freq: 120, lpf_on: 1, lpf_freq: 9000` |
| Music under dialogue | `mid_freq: 2500, mid_gain: -4, mid_q: 0.8` (a pocket where speech is understood) |

**Kick and bass** share 40-120 Hz. Decide which is lower: a deep kick (60 Hz) with a bass
high-passed at 50 and focused at 100-200, or a sub bass with a kick whose weight is at 90-110.
Sidechain compression, the usual way to make the bass give way to the kick, is not in
SoundCraft: shorten the bass note that lands with a kick, or automate the bass's volume down
3-4 dB for the first 16th under each kick where it matters.

## Compression

A compressor lowers what goes over `threshold` by `ratio`, starting within `attack` and
recovering within `release`; `makeup` restores the level. Set the threshold so it works on the
loud notes only, and judge by what a bounce of the soloed track does to `peak_db` against
`lufs`: the gap between them (the crest) should narrow by a few dB, not collapse.

| Source | threshold | ratio | attack ms | release ms | Why |
|---|---|---|---|---|---|
| Bass | -20 | 4 | 25 | 120 | evens notes; slow attack keeps the pluck |
| Kick or snare (punch) | -15 | 4 | 20-30 | 80-120 | lets the hit through, then holds the body |
| Drums bus (glue) | -18 | 2-3 | 30 | 100-200 | 2-4 dB of reduction; `mix: 50` for parallel |
| Spoken voice | -22 | 3 | 5-10 | 100-150 | steady level; then a de-esser |
| Sung voice | -20 | 3-4 | 5-15 | 80-200 | two gentle compressors beat one hard one |
| Keys, pads | -18 | 2 | 20 | 200 | usually none: they are already even |
| Mix bus (glue) | -14 | 1.5-2 | 30 | 200-300 | 1-2 dB at most, or leave it out |

Fast attacks (under 5 ms) dull transients; fast releases (under 50 ms) on bass distort. A
synthesized part with fixed velocities needs no compressor: fix levels at the notes instead.
`expander_gate` (threshold just above the noise, `range: 20-40`) cleans room noise between
phrases of a voice; `saturator` (`drive: 3-6`, `mix: 40-60`) adds harmonics that make a bass or
drum audible on small speakers.

## Reverb and delay

Put them on returns (soundcraft-commands.md, "An effect return"), `mix: 100` on the return's
plug-in, and send to them: one space for the whole mix makes the parts sound together.

- **Reverb.** `plate_reverb` for voices, snares, keys (`decay: 1.5-2.5`); `room_reverb` for
  drums and to give dry synths a place (`decay: 0.4-1.2`). Pre-delay 20-40 ms keeps the source
  in front. Always `low_cut: 200-300` and `damping: 6000-8000`: low and bright reverb is what
  clouds a mix. Decay follows tempo: at a fast tempo, shorter. Sends: lead -12 to -8, harmony
  -14 to -10, snare -16, drums as a whole -20, bass and kick none.
- **Delay.** `mod_delay` with `time` from the tempo (8th `30000 / bpm` ms, dotted 8th `45000 /
  bpm`, quarter `60000 / bpm`), `feedback: 20-35`, `lpf: 4000-6000` so the repeats sit behind.
  A throw is automation of the send's level (`send_a_level`) up for one word or note.
- **Dry and close** reads as intimate and modern; **wet and far** as large and distant. Dialogue
  and podcasts stay nearly dry.
- The tail outlasts the last note: every bounce's `end` goes 2-4 seconds past the last clip.

## Automation

Static mixes sound flat. Automate, in this order of value: the lead's level phrase by phrase
(1-3 dB rides), section lifts (the chorus's harmony +1.5 dB, the verse's pad down), fades in
and out, effect throws, and filter sweeps. An instrument's own parameters (the synth's `cutoff`)
cannot be automated: put an `eq_7band` on the track with `lpf_on: 1` and automate
`plugin:a:lpf_freq` instead.

**Ducking music under a voice**, without a sidechain, from the voice's own clips. Verified here:
a 14 dB dip measured under each stretch of speech.

1. `edit.strip_silence_preview {tracks: ["VO"], start: 0, end: <session end>, threshold_db:
   -45, min_length_ms: 400}` returns the ranges that hold speech.
2. For each range `[a, b]`, four points on the music's `volume`: the full level at `a - ramp`,
   the ducked level at `a`, the ducked level at `b`, the full level at `b + ramp`, with `ramp`
   0.3-0.5 s (14400-24000 samples). Merge ranges closer together than 1 s so the music does
   not pump between sentences.
3. Depth: 10-14 dB under speech for a podcast bed, 6-8 dB under dialogue in a film mix, and the
   2-4 kHz pocket in the music's EQ.

## The master and loudness

One processor on the master does the delivery's job: `mix.insert {track: "Master 1", plugin:
"maximizer", params: {threshold: 0, ceiling: -1.5, release: 80}}`. Then walk `threshold` down
until the bounce's `lufs` reads the target (soundcraft-commands.md, "Hitting a loudness
target"). If the limiter has to take more than about 6 dB, the mix is too quiet or too dynamic
going in: raise the track levels, compress the peaky parts, and try again.

| Delivery | Integrated loudness | True peak | Notes |
|---|---|---|---|
| Spotify, YouTube, Tidal, Amazon Music | -14 LUFS | -1 dBTP (-2 if louder than -14) | Spotify's own guidance; louder masters are turned down |
| Apple Music | -16 LUFS | -1 dBTP | Sound Check; a -14 master is turned down 2 dB |
| One master for all streaming | -14 LUFS | -1 dBTP | the common choice |
| Club and DJ files | -9 to -7 LUFS | -1 dBTP | not normalized on playback; ask |
| Podcast (Apple Podcasts) | -16 LUFS (±1), stereo | -1 dBTP | -19 LUFS for a mono file is the common equivalent |
| Social video (TikTok, Reels, Shorts) | -14 LUFS | -1 dBTP | matches FilmCraft's presets |
| European broadcast (EBU R 128) | -23 LUFS | -1 dBTP | |
| US broadcast (ATSC A/85) | -24 LKFS | -2 dBTP | |
| Film or series for a streamer | -27 LKFS dialogue-gated | -2 dBTP | the final mix happens against picture; you deliver stems |
| Music stem or cue for a film edit | not normalized: peaks -6 to -3 dBFS | | the editor sets its level under dialogue |
| Sound effect | peaks around -3 dBFS | | full scale is the editor's to use |

Loudness is not quality: a quieter master with its transients intact sounds better after the
platform's normalization than a crushed loud one. The maximizer's ceiling is a sample peak and
true peaks run 0.2-0.6 dB over it: set `ceiling: -1.5` for a -1 dBTP delivery and read
`true_peak_db` in the reply.

## Export settings

| Deliverable | Format |
|---|---|
| Master for streaming or a distributor | WAV, 24-bit, the session's rate (44.1 or 48 kHz); 16-bit 44.1 kHz only where asked (dither is on by default) |
| Master for picture, stems for a film | WAV, 24-bit, **48 kHz**, starting at the cue's first frame |
| Podcast episode | WAV master, then MP3 (mono 96-128 kbps or stereo 128-192 kbps) or M4A made with ffmpeg |
| Listening copy | MP3 320 kbps or M4A 256 kbps made with ffmpeg |
| Stems | WAV 24-bit, all the same start and length, the master's limiter bypassed |
| Archive | the session (`project.scraft`, `Audio Files/`), plus FLAC of the master |

The checklist before a file is called delivered:

1. `mix.clear_solos {}`; no track muted by accident; the right sections in range.
2. `end` covers the tail. Start at bar 1 (or the cue's sync point), not at the first note.
3. Bounce; read `lufs` and `true_peak_db` against the target.
4. `engine_exec`: ffprobe for codec, rate, channels, and duration; `silencedetect` to see it is
   not silent and has no hole (`ffmpeg -i f.wav -af silencedetect=noise=-50dB:d=1 -f null -`).
5. Tell the person the path, the numbers, and anything that missed. Play it for them
   (`transport.play`) before calling it final.

## Stems

Stems are the mix split into a few files that sum back to it: for a song, drums, bass, music
(harmony), leads, vocals, effects; for a film, **dialogue, music, and effects** (DME), and
within music often rhythm, low, harmony, melody. `file.bounce_stems {dir, start, end}` writes
one per audio and instrument track, each through its sends and returns, named `<session> -
<track>.wav`.

- Bypass the master's limiter first (`mix.insert_bypass {track: "Master 1", slot: 0, value:
  true}`), bounce, and switch it back. Checked here: the stems then sum to the unlimited mix.
- One stem per group rather than per track: route the group's tracks to a bus and an aux
  (a submix) and bounce the bus (`file.bounce_mix {source: "Drums", …}`), or solo the group and
  bounce the mix.
- Same `start` and `end` for all, so they line up when dropped at one position.
- A 3 min 49 s session's four stems took 31 s; many tracks of a long session can pass
  SoundCraft's 90-second limit for one request. Bounce in groups or by section if it does.

## To picture

Scoring or sound for a film cut in FilmCraft, in the same project folder.

1. **Get the picture.** The film's export (H.264 MP4 or ProRes MOV; FilmCraft's `file.exportMedia`
   writes it into the project folder) with its dialogue. `engine_files` to find it, then
   `file.import_video {path, at: 0}`: picture on a Video track, its sound on `<name> audio` as
   the guide track. Keep the guide at -6 to -10 and never in a bounce (mute it before bouncing).
2. **Match the film.** `setup.session {frame_rate: "24"}` (the reply of the import gives the
   movie's `frame_rate`); 48 kHz is already the session's rate. Bar 1 is the picture's first
   frame, so a bounce from 0 lines up at the head of the edit.
3. **Spot it** with the person: where music starts and stops, what each cue does (tension,
   release, pace, place), and the hit points (a cut, a look, an impact). Mark each:
   `markers.add {name: "1M1 in", at: {seconds: 12.5}}`. The film's own timings come from its
   shot list, from FilmCraft's `sequence.inspect` (clip starts in seconds) if the edit is open,
   or from the movie itself.
4. **Tempo from the hits.** A tempo puts a beat every `60 / bpm` seconds. To land a downbeat on
   two hits `d` seconds apart, choose a bar count `n` and a meter of `b` beats: `bpm = 60 x n x
   b / d`. Example: hits at 12.5 s and 28.5 s, 16 s apart; 8 bars of 4/4 gives 120 BPM, 6 bars
   gives 90. Pick the one that fits the scene's pace. Start the cue so a bar line meets the
   first hit (`event.tempo {bpm, at}`), and change tempo or add a 2/4 or 3/4 bar (`event.meter`)
   to catch a hit that falls between.
5. **Write under dialogue.** Leave 1-4 kHz to the voices: low, sustained, and sparse while
   people speak; movement and melody in the gaps. Enter and exit on cuts or under sound, with a
   fade or a held note, not mid-line.
6. **Deliver** into `score/` in the project folder: `score/<cue>-mix.wav` (48 kHz, 24-bit, from
   0 or from the cue's marked start), stems beside it, not normalized, peaks -6 to -3 dBFS, and
   `score/cues.md` listing each cue's start time, length, tempo, and files. Then FilmCraft
   imports them (`file.import {paths}`), places them at the listed starts, and makes the final
   mix against dialogue and effects at the film's loudness target.

SoundCraft does not export video and does not know FilmCraft's project: the hand-off is files
and times. Two engines running at once do not see each other's new files, so `engine_send`
carries them across (SKILL.md, "Working with the other engines").

## Podcasts and voice

- **Edit first:** remove false starts and long pauses in `shuffle` mode (`edit.cut` closes the
  gap), tighten pauses to 0.3-0.6 s, and crossfade every cut (5-20 ms, `equal power`). There is
  no transcript: find the cuts by the waveform's silences (`edit.strip_silence_preview`) and by
  the person's notes and times.
- **Chain per voice:** `eq_7band` (the spoken voice row), `expander_gate` if the room is noisy,
  `compressor` (-22, 3:1), `de_esser` (`freq: 6000`), in that order.
- **Match the speakers** to each other: bounce each soloed over the same stretch and bring their
  `lufs` within 1 LU with `clip.gain` or the fader.
- **Music and idents:** theme in at full level, ducked under the first words; beds 20-25 dB
  under speech or out.
- **Master:** maximizer to -16 LUFS, ceiling -1.5; MP3 with ffmpeg.

## Where SoundCraft has no equivalent yet

| Usual practice | In SoundCraft |
|---|---|
| Sidechain compression, ducking by a key input | volume automation from the voice's or kick's own positions |
| Multiband compression, dynamic EQ | static EQ and automation |
| Linear-phase or matching EQ, mid-side processing | not there; width by the two pans |
| Convolution reverb, impulse responses | the plate and room algorithms |
| Pitch correction, vocal tuning | not there; `pitch_shifter` moves a whole clip |
| Noise reduction, spectral repair | `expander_gate` and EQ only; clean the file elsewhere first |
| Reference-track matching, spectrum view from the API | ffmpeg meters on a reference file beside your bounce |
| Metering of loudness range and short-term loudness | `ffmpeg … ebur128` on the bounce |
| MP3, AAC, Opus export | ffmpeg from the WAV |
| Mastering chain presets | one maximizer, and your judgment |
