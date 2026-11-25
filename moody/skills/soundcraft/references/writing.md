<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Writing: structure, sounds, and MIDI that sounds played

What a producer decides before the mix, and how each decision becomes notes in SoundCraft. Times
are ticks, 960 to a quarter note: 16th 240, 8th 480, dotted 8th 720, quarter 960, half 1920, bar
of 4/4 3840, bar of 3/4 2880, bar of 6/8 2880 (8th-note triplet 320, 16th triplet 160).

## Tempo, key, and feel by genre

Starting points to propose, never rules. The person's references outrank the table.

| Genre | BPM | Feel | Common keys and harmony | Drums |
|---|---|---|---|---|
| Lo-fi hip hop | 70-90 | swung 8ths or 16ths, behind the beat | minor 7th and 9th chords, ii-V-I, jazz borrowings | soft kick, rimmy snare on 2 and 4, loose hats |
| Boom bap | 85-95 | swing 54-62 % on 16ths | minor, sampled chord loops | hard kick and snare, 8th hats |
| Trap | 130-150 (felt half time) | straight, hat rolls in 32nds and triplets | minor, sparse, 808 bass following the kick | snare or clap on beat 3, busy hats |
| House | 120-128 | straight, four on the floor | minor or modal, one or two chords | kick every beat, clap on 2 and 4, open hat on the off 8ths |
| Techno | 125-140 | straight, hypnotic | one note or one chord, texture over harmony | kick every beat, hats in 16ths, rides |
| Drum and bass | 165-178 | straight, syncopated | minor, long pads over fast drums | kick on 1 and the "and" of 3, snare on 2 and 4 |
| Pop | 95-125 | straight | major or relative minor, I-V-vi-IV and its rotations | kick and snare backbone, lift in the chorus |
| R&B, neo soul | 60-95 | swung, laid back | extended chords (9ths, 11ths, 13ths), chromatic passing chords | rim or snare late, ghost notes |
| Rock | 100-140 | straight, pushed | major, mixolydian, power chords | kick and snare, 8th hats or ride |
| Ambient, drone | none or 60-80 | free | modal, one tonal center, slow change | none, or pulses |
| Cinematic underscore | 60-110 (to the picture) | free or ostinato | minor, modal (dorian, aeolian), pedal tones | low hits, pulses, toms |

A key also has to fit a singer: ask for their range or a reference track before fixing it.

## Structure

A section is 4, 8, or 16 bars; something changes at every boundary, and something small changes
every 2 or 4 bars inside it. Lay the sections out as markers first (`markers.add` at each
`bars_beats` start), then fill them.

| Form | Layout (bars) | Notes |
|---|---|---|
| Pop song, 3:00-3:30 | intro 4-8, verse 16, pre-chorus 8, chorus 8-16, verse 16, pre 8, chorus 16, bridge 8, chorus 16, outro 4-8 | first chorus by 0:45-1:00; the last chorus is the biggest |
| Short-form song (social, 15-60 s) | hook 8, verse 8, hook 8 | start on the hook; no intro |
| Beat for a vocalist | intro 4, verse 16, hook 8, verse 16, hook 8, bridge 8, hook 8, outro 4 | leave the midrange open for the voice |
| House or techno track, 5-7 min | intro 16-32 (drums, DJ-mixable), build 16, drop 32, break 16-32, build 8-16, drop 32, outro 16-32 | changes every 8 or 16 bars; elements enter and leave one at a time |
| Lo-fi loop, 2-3 min | A 8, A' 8, B 8, A 8, repeated with variation | texture and small changes carry it |
| Podcast episode | cold open 15-60 s, theme 5-15 s, introduction, segments, break stings, close, theme out | theme music ducks under the first words |
| Film cue | by the picture: in on a cut or a line, out on a cut or under the next scene | see mixing.md, "To picture" |
| Sound effect | attack, body, tail; layers a few milliseconds apart | one file per effect, tails intact |

**Arrangement is subtraction.** Write the fullest section first (the last chorus, the drop), then
make the others by taking parts away. Energy comes from contrast:

- **Density.** Verse: drums, bass, one harmonic part. Chorus: add a second harmonic part, a
  counter line, wider and higher voicings, a busier hat.
- **Register.** Hold back the lowest and highest octaves until the section that should lift.
- **Rhythm.** Halve the drum pattern for a pre-chorus or a break; drop the kick for the bar
  before a chorus; a fill or a silence in the last half bar announces the change.
- **Transitions.** A riser is a note or noise whose filter opens over 2-4 bars (automate an
  `eq_7band` low-pass on its track, `plugin:a:lpf_freq`, and the track's `volume`); a downlifter falls after the hit; a crash (note 49)
  on the first beat of the new section; a reversed tail leading in (`audiosuite.process
  {process: "reverse"}` on a copy of a hit).
- **One thing at a time.** No more than three or four parts carry attention at once: a rhythm, a
  bass, a harmony, a lead. A fifth has to replace one of them.

## Choosing sounds

Decide each part's job and register before its sound; parts that share a register fight.

| Part | Register | Job |
|---|---|---|
| Sub and bass | 30-250 Hz, notes 24-48 (C1-C3) | weight and the harmony's root; mono, one note at a time |
| Kick | 45-100 Hz body, 2-5 kHz click | pulse; shares the bottom with the bass, so one of them is shorter or higher |
| Harmony (keys, pad) | 200 Hz-4 kHz, notes 48-76 | chords; leaves the bottom to the bass and the 1-4 kHz center to the voice or lead |
| Lead or voice | 250 Hz-5 kHz | the thing listened to; everything else makes room |
| Hats, shakers, air | above 6 kHz | motion and width |
| Texture (noise, room tone, foley) | wherever it does not mask | glue and place; quiet |

SoundCraft has three instruments (soundcraft-commands.md). What they do well: synthesized drums,
synth basses, pads, plucks, leads, sine and electric-piano-like keys, and any single sample
played across the keyboard. What they cannot be: a real piano, strings, guitar, or voice. For
those, ask the person for audio, generate it, or say plainly that the part will sound
synthetic. A realistic one-shot (a kick, a snare, a vocal chop, a foley hit) goes in a
`sampler` track with `play_mode: 1`.

### Patches for `subtractive_synth`

Set with `mix.instrument {track, plugin: "subtractive_synth", params}`. Waves: 0 saw, 1 square,
2 sine, 3 triangle. Each was written for a run here or follows the same parameters; adjust by
ear with the person, since you cannot hear them.

| Sound | Parameters |
|---|---|
| Round sub bass | `osc1_wave: 2, osc2_wave: 3, osc2_semitones: -12, osc2_detune: 0, osc_mix: 35, cutoff: 420, resonance: 10, filter_env_amount: 25, amp_attack: 4, amp_decay: 300, amp_sustain: 75, amp_release: 120` |
| Plucked bass | `osc1_wave: 0, osc2_wave: 1, osc2_detune: 5, cutoff: 500, resonance: 25, filter_env_amount: 60, filter_decay: 180, filter_sustain: 10, amp_attack: 2, amp_decay: 250, amp_sustain: 40, amp_release: 80` |
| Soft keys (electric-piano-like) | `osc1_wave: 3, osc2_wave: 2, osc2_detune: 9, osc_mix: 40, cutoff: 1400, resonance: 8, filter_env_amount: 20, amp_attack: 12, amp_decay: 900, amp_sustain: 45, amp_release: 700, velocity: 80` |
| Warm pad | `osc1_wave: 0, osc2_wave: 0, osc2_detune: 14, cutoff: 900, resonance: 10, filter_env_amount: 15, filter_attack: 1500, amp_attack: 800, amp_decay: 2000, amp_sustain: 80, amp_release: 2500` |
| Pluck or arp | `osc1_wave: 0, osc2_wave: 1, osc2_semitones: 12, cutoff: 1800, resonance: 30, filter_env_amount: 50, filter_decay: 120, filter_sustain: 0, amp_attack: 1, amp_decay: 220, amp_sustain: 0, amp_release: 200` |
| Mono lead | `osc1_wave: 0, osc2_wave: 1, osc2_detune: 8, cutoff: 3000, resonance: 20, glide: 60, amp_attack: 5, amp_sustain: 85, amp_release: 180` |
| 808-style bass | `osc1_wave: 2, osc2_wave: 2, osc_mix: 0, cutoff: 800, filter_env_amount: 0, glide: 80, amp_attack: 2, amp_decay: 1500, amp_sustain: 30, amp_release: 300`, with a `saturator {drive: 8}` insert so it is heard on small speakers |

A pad that should move: `chorus` after it, and slow automation of an `eq_7band` low-pass on its
track (an instrument's own parameters take no automation). A dull sound gets
`cutoff` up before it gets EQ; a harsh one gets it down.

## Harmony and voicing

Chords are written as notes, so voice them as a player would:

- **Bass takes the root**, in its own track, between notes 28 and 48. Keep thirds out of the
  bottom octave: below about note 48 (C3), intervals smaller than a fifth sound muddy.
- **Spread the chord**: root or fifth low, third and seventh in the middle (notes 52-67), color
  tones (9th, 11th, 13th) on top. Leave out the fifth before anything else, and the root from
  the keys when the bass has it.
- **Voice leading**: from one chord to the next, keep common tones where they are and move the
  other voices by the smallest step. The top note is a melody: make it move by step or stay.
- **Inversions** keep a progression in one hand position instead of jumping in parallel.
- **Range**: keep the keys' top note under the lead's range, or the lead above it.
- **A chorus lifts** by opening the voicing (the same chord an octave wider), adding the octave
  above the top note, or adding the ninth.

A worked example, the four bars run for this skill (F minor, each chord one bar, top voices held
in common): Fm9 `56 60 63 67` over bass 41; Dbmaj7 `56 60 63 65` over 37; Abmaj7 `55 60 63 68`
over 44; Eb(add9) `55 58 62 67` over 39. Three of four voices stay or move a step each change.

Common progressions (in any key): I-V-vi-IV, vi-IV-I-V, I-vi-IV-V, ii-V-I, i-VI-III-VII,
i-iv-v, i-VII-VI-VII, IVmaj7-iii7-vi7 (neo soul), i-i-iv-i with a pedal bass (underscore). Write
a cue's harmony around the scene's turn, not the bar line.

## Making MIDI sound played

A grid of identical notes sounds like a machine. Four things separate a performance from it, and
`midi.note_add` takes all four as numbers you choose.

**1. Velocity shape.** Accents carry the meter. Hats and shakers: strong on the beat (85-100),
weak on the off 8ths (55-75), weakest on the 16ths between (40-60). A backbeat snare 95-112;
ghost notes 25-45. Kick 100-118 on the downbeat, 85-100 elsewhere. Chords: the top note 5-10
louder than the inner voices, or the reverse for a darker sound; a phrase rises toward its peak
and falls away. Bass: the note on the downbeat strongest. Then add a random ±4 to ±8 to every
note so no two are equal.

**2. Timing.** Offset each note a few ticks from the grid, by role, not at random alone:

| Part | Offset in ticks (at 960 a quarter) |
|---|---|
| Kick on the downbeat | 0 to +6 (the anchor: nearly on the grid) |
| Backbeat snare, laid back | +8 to +24 (later is lazier; at 90 BPM, 10 ticks is 7 ms) |
| Hats | ±5, random |
| Bass | 0 to +8, with the kick or just behind it |
| Chord notes, rolled | each voice 10-20 ticks after the one below it (a strum or a pianist's spread) |
| Lead | ±10, phrases often start a little early and end late |
| Pushed feel (rock, punk, some dance music) | snare and hats 5-12 ticks early instead |

Keep the offsets small: beyond about 30 ticks (20 ms at 90 BPM) a note reads as a mistake
unless the whole part leans that way. One tick is `60000 / (bpm x 960)` ms.

**3. Swing.** Delay every second 8th or 16th. A swing of 50 % is straight, 66 % is triplet
swing; grooves live at 54-62 %. For 8th-note swing the off 8th moves from tick 480 to `960 x
swing`: 518 at 54 %, 557 at 58 %, 595 at 62 %, 640 at 66 %. For 16th-note swing the off 16th
moves from 240 to `480 x swing`: 259, 278, 298, 320. Either write the notes swung, or write them
straight and run `event.quantize {grid: "1/16", swing: 58, clips}` (it moved off 16ths to 60 %
of the 8th at `swing: 60`). Swing the hats and the bass together; keep the kick and snare on
their beats.

**4. Length and overlap.** Staccato parts hold 30-60 % of their grid value; legato lines overlap
the next note by 10-30 ticks (with `glide` on a mono lead, that slides); a sustained chord ends
60-240 ticks before the next so the change breathes; a bass note ends before the next kick.
`event.change_duration {legato: 0, clips}` closes the gaps of a line.

**Variation.** Write a 1- or 2-bar pattern, repeat it (`clip.loop`), then change one thing every
4th or 8th bar: an extra kick before the bar line, an open hat (46) on the last off 8th, a
snare fill in 16ths rising in velocity, a dropped beat. A part that never changes is a loop; one
that changes every bar has no pattern.

### Drum patterns

One bar of 4/4 as `pitch @ tick (velocity)`, before humanizing. Notes: 36 kick, 38 snare, 39
clap, 42 closed hat, 46 open hat, 49 crash, 51 ride.

| Groove | Kick (36) | Snare or clap | Hats |
|---|---|---|---|
| Basic backbeat | 0 (112), 1920 (104) | 38 @ 960, 2880 (104) | 42 every 480: on beats 90, off 8ths 64 |
| Boom bap, 90 BPM | 0 (112), 1440 (92), 2400 (100) | 38 @ 960, 2880 (106), late by 12-20 | 42 every 480, off 8ths swung to 557, 62-88 |
| Lo-fi, 80 BPM | 0 (110), 2400 (96), sometimes 3600 (84) | 38 @ 960, 2880 (100), late by 10-22 | 42 swung 8ths (off 8ths +150), 46 on the last off 8th every other bar |
| Four on the floor | 0, 960, 1920, 2880 (112) | 39 @ 960, 2880 (100) | 46 @ 480, 1440, 2400, 3360 (88); 42 on 16ths between at 50-60 |
| Trap, 140 BPM | 0 (115), 1440 (100), 2640 (105) | 39 @ 1920 (110) | 42 every 240 at 70-90, with a roll: 6 notes of 80 ticks rising 60 to 100 before beat 3 or 1 |
| Drum and bass, 174 BPM | 0 (112), 2400 (104) | 38 @ 960, 2880 (110) | 42 every 240, accents on the beats; ghost 38 @ 1680 and 3600 (35) |
| Half time | 0 (112), 2640 (96) | 38 @ 1920 (108) | 42 every 480 |
| 6/8 ballad (bar 2880) | 0 (110), 1440 (98) | 38 @ 1440 (100) | 42 every 480: 0 and 1440 at 90, the rest 62 |

Give the drum notes a `length_ticks` of 100-240; the drum synth plays its own decays. A fill
lasts the last 2 beats of a section: snares or toms (50, 47, 45, 43 falling) in 16ths, velocity
rising 70 to 115, landing on a crash and kick at the next bar's tick 0.

### Bass lines

- Lock to the kick: a bass note where each kick is, the root on the downbeat.
- Root, fifth, and octave carry most lines; approach the next chord's root from a step or a
  half step below in the last 8th of the bar.
- Leave rests. A line of 3-5 notes a bar with space grooves more than a full bar of 8ths.
- Lengths matter more than pitches: short notes (200-400 ticks) bounce, long notes (to the next
  note) weigh. Mix them: long on the downbeat, short on the syncopations.
- One note at a time, and nothing below note 28 (E1, 41 Hz) for speakers that have no sub.

### Melody and leads

Sing-able: mostly steps, a leap followed by a step back, a range of about a tenth. Build from a
2-bar motif: state it, repeat it, vary its end, answer it. Put the highest note once, at the
phrase's peak. Rest at the ends of phrases, where a singer would breathe. Chord tones on strong
beats, passing tones between them.

## Texture and sound effects

- **Beds** (rain, room tone, vinyl noise, crowd): long audio clips, very quiet (-25 to -35 dB
  under the music), faded in and out, high-passed around 100-150 Hz so they add air, not mud.
- **Designed effects** are layers: an attack (a click, a transient), a body (a tone or noise), a
  tail (reverb). Put each on its own track, offset by milliseconds, and bounce the range with
  its tail. Pitch a layer down (`audiosuite.process {process: "pitch_shift"}` or the sampler at
  lower notes) for size, reverse one for a lead-in, saturate for edge.
- **Synthesized sources**: the `signal_generator` AudioSuite process makes sine, square, saw,
  triangle, white noise, and pink noise clips; the synth with a fast pitch or filter envelope
  makes zaps and blips; the drum synth's toms and cymbals pitched with `tom_tune` make hits.
- **ffmpeg makes raw material** in the engine (`engine_exec`): `anoisesrc` for noise colors,
  `sine` for tones, filters such as `lowpass`, `tremolo`, and `afade`, written as a WAV into the
  project folder and imported with `file.import_audio`.
- **Name and trim every effect**: no silence before the attack, the full tail after, peaks
  around -3 dBFS, one file each, 48 kHz 24-bit WAV.
