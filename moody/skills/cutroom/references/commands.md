<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# The Cut Room's commands

Every script, with its parameters, what it writes, what it prints, and what a failure means.
Each is run as `engine_exec(engine_id, "cutroom NAME ...")`, in the project folder, so every
path is relative to that folder. `cutroom NAME --help` prints a script's own parameters on the
engine you are driving, which is the truth if this file and the engine ever differ.

Times are seconds, with decimals. Positions on a frame are pixels from the top left of the
output. A fraction is 0 to 1 of the picture's width or height.

## Reading footage

### `sheet`: contact sheets, scene cuts, black, level

```text
cutroom sheet VIDEO [--out sheets/NAME] [--every 1] [--start S --end E] [--tile 8x8] [--width 320] [--scene 0.3]
cutroom sheet VIDEO --at 2.3,3.3,4.85 [--out sheets/NAME] [--width 480]
```

| Parameter | Meaning |
|---|---|
| `--every` | seconds between frames; 1 maps a whole video, 0.5 reads a stretch closely |
| `--start`, `--end` | the stretch of the source, in its seconds |
| `--tile` | columns by rows of frames on one sheet; more frames than that make more sheets |
| `--scene` | how much the picture has to change to count as a cut; lower finds more |
| `--at` | check frames at these seconds on one picture, instead of sheets |

Writes `sheets/<name>/sheet_01.jpg`, `sheet_02.jpg`, and `footage.json`; with `--at`,
`sheets/<name>/frames.jpg`. Each frame carries its second in the source in its corner. Prints:

```text
{"video": "footage/test.mp4", "duration": 30.0, "start": 0.0, "end": 30.0,
 "sheets": ["sheets/test/sheet_01.jpg"], "every": 1.0,
 "scene_cuts": [10.0, 20.0], "black": [],
 "sound": {"mean_db": -24.3, "max_db": -5.8, "lufs": -17.4}}
```

`scene_cuts` are the seconds a new shot starts: the only places to start or end a segment.
`black` is each stretch of black as `[start, end]`. `sound` is null for a file with no sound;
a mean far below -40 dB is a recording in which nobody speaks. With `--at` it prints
`sheets/<name>/frames.jpg (4x2)`, the grid's columns by rows.

Fails with `ffmpeg failed: ...` and FFmpeg's words for a file it cannot read, which is also
what a download that saved a web page instead of a video looks like.

### `moments`: a transcript and the moments worth cutting

```text
cutroom moments SOURCE [--top 8] [--min 15] [--max 40] [--chat chat.json] [--max-minutes 90]
```

`SOURCE` is a file or a web address yt-dlp reads. `--min` and `--max` bound a moment's length
in seconds; `--max-minutes` is how much of a long address is downloaded. Prints:

```text
job: jobs/test-7273873a
2 candidates -> jobs/test-7273873a/candidates.md
```

The job folder is what `cut` and `translate` take. In it: `transcript.json`
(`[{"w": "Welcome", "s": 0.85, "e": 1.45}, ...]`), `candidates.json`, `candidates.md`, and for
an address `source.mp4`. `candidates.md` reads:

```text
## 1. 0:10-0:18 (8s) score 3.97
why: loudness spike, hype words
> Wait, what is that? No way, look at this fractal zoom.
```

The number after `##` is what `--pick` takes. A job is made once: run `moments` again on the
same source and it reuses the sound and the transcript. To cut a stretch that is not a
candidate, give `cut` any `--pick` with `--start` and `--end`, or with `--segments`.

Fails with `command failed (1): ... yt_dlp ...` and the site's words where an address is
refused.

### `words`: every word and when it is said

```text
cutroom words MEDIA [--lang en] [--model medium] [--start S --end E] [--offset 0] [--vad] [--out words.json]
```

Prints the language and one word a line, `start  end  word`, in the media's own seconds:

```text
language: en (1.00)  words: 11
   0.30    0.72  This
   0.72    0.94  is
```

`--offset` adds seconds to every time: give it the second a narration take starts on the
timeline, and the times printed are the output's, ready for `explainer --title-words` and
`reveal --sign`. `--lang` forces the language (leave it out and the model guesses, printing
how sure it is). `--model small` is quicker and hears less. `--out` writes the words in the
transcript's form.

### `clean`: the swears heard in a file

```text
cutroom clean MEDIA [--lang en]
```

Prints each as `(start, end, 'word')` and a count. It is what `cut` and `check` listen with.

### `facecam`: where a presenter's webcam is

```text
cutroom facecam VIDEO [--start S --end E] [--json out.json] [--debug out.jpg]
```

Prints one line, ending in the box as `--cam x:y:w:h` fractions:

```text
cam: bottom-right 25% x 44% (confidence 1.0; face stable in 12/12 frames, ...) -> --cam 0.733:0.525:0.250:0.444
```

or `no webcam found (...) -> use the blur layout`. `--debug` writes a frame with the box drawn
on it: look at it once before trusting an automatic crop. A line starting `[ WARN:` is the
picture library's own and means nothing here.

### `levels`: loudness, peak, and the level of stretches

```text
cutroom levels FILE [--spans "4.4-8.8,13-18"]
```

```text
{"file": "edits/explainer.mp4", "lufs": -13.6, "lra": 15.8, "true_peak_db": -0.7,
 "mean_db": -18.4, "max_db": -0.7,
 "spans": [{"start": 4.4, "end": 8.8, "rms_db": -15.8}, {"start": 13.0, "end": 18.0, "rms_db": -28.4}]}
```

`lufs` is the integrated loudness, `true_peak_db` the highest peak. A span where the voice
speaks against a span where only music plays is how far under the voice the music is: here 12.6
dB.

## Making sound

### `narrate`: lay spoken takes on a timeline

```text
cutroom narrate SPEC.json --out narration/NAME
```

The spec is a file you write into the project folder:

```text
{
 "gap": 0.1,
 "tempo": 1.25,
 "speakers": {"A": {"color": "FFFFFF"}, "B": {"color": "8FE6FF"}, "C": {"color": "FF9AD2"}},
 "lines": [
  {"at": 0.1, "who": "A", "audio": "library/r1/01-take.wav", "text": "Wait, what is that?", "caption": "Wait… what is THAT?"},
  {"at": 2.0, "who": "C", "audio": "library/r2/01-take.wav", "text": "No way!", "caption": ""},
  {"audio": "library/r3/01-take.wav", "text": "It just keeps going."}
 ]
}
```

| Key | Meaning |
|---|---|
| `audio` | the take, a path in the project folder; required for every line |
| `text` | what the take says; the caption unless `caption` is given |
| `caption` | what is shown; `""` makes a shout or a laugh that needs none and may overlap others |
| `at` | the output second the line starts; left out, right after the line before it |
| `who` | a speaker of `speakers`, for its caption color (and its own `tempo`) |
| `tempo` | speed, pitch kept: for the spec, a speaker, or one line |
| `gap` | seconds left after a captioned line before the next may start |
| `master` | true runs an older broadcast chain with a little room over the track; prefer `vo_master` |

Writes `<out>/voice.wav` (48 kHz mono), `<out>/lines.json`, and `<out>/cache/` (each take,
trimmed, kept by its content, so laying again is free and sounds the same). Prints where each
line landed, which is how you learn the narration's length:

```text
  0.10-  1.09  Wait… what is THAT?
  2.00-  2.44  (no caption)
voice: narration/reactions/voice.wav (7.3s)
```

A captioned line never overlaps another: one whose `at` is too early is moved after the line
before it, and the printed time shows it. Fails with `no such take: PATH` for a missing file,
and `a line has no audio` for a line without one.

### `vo_master`: a studio voice

```text
cutroom vo_master IN.wav OUT.wav [--preset studio_warm]
```

Presets: `studio_warm` (no pitch change; the default), `studio_deep` (one semitone lower),
`studio_deeper` (two), `broadcast` (EQ and compression only). The result is 48 kHz mono at -16
LUFS, dry. Prints the output's path. Measure before and after with `levels`.

### `chime`: the sound of a reveal

```text
cutroom chime sfx/reveal_chime.wav [--seconds 3]
```

A synthesized three-second chime, the same every time. `reveal` makes it by itself unless told
otherwise, so you need this only to use the sound elsewhere.

## Cutting

### `cut`: a vertical clip

```text
cutroom cut jobs/<id> --pick N [--name STEM] [--layout blur|fill|focus|facecam|react]
    [--start S --end E] [--segments "a-b,c-d@2"] [--focus "t:cx,t:cx"]
    [--hook "TEXT"] [--hook-secs S] [--captions word|bubble|none] [--cap-y PX] [--font "Archivo Black"]
    [--lines lines.json] [--lines-time source|output] [--voice voice.wav] [--bed-gain 0.3]
    [--cam auto|x:y:w:h] [--title "TEXT"] [--title-style box|outline] [--title-secs S]
    [--trim-bottom 0.15] [--lang en] [--allow-profanity]
```

| Parameter | Meaning |
|---|---|
| `--pick` | the candidate's number; its start and end unless `--start`, `--end`, or `--segments` say otherwise |
| `--name` | the output's file stem; `clip_<pick>` unless given. Give every clip its own |
| `--layout` | `blur` (default): the whole picture over a blurred copy. `fill`: cropped to fill. `focus`: a 4:5 window over the blurred copy, 1350 px tall from y 320, hook above. `facecam`: the camera on the top 38%. `react`: the face on a 730 px panel on top, the screen below |
| `--segments` | parts kept, in source seconds, in the order they play; `@2` twice as fast, `@0.5` half speed. Captions from the transcript follow them |
| `--focus` | focus layout: `output second:center x` keyframes, x from 0 (left) to 1; the window glides between them. Two keyframes 0.01 s apart switch hard, which is what a jump cut wants |
| `--hook` | the line on the white box at the top; 3 to 9 words fit. `--hook-secs`: seconds it stays, 0 for the whole clip (the focus layout's default; 2.6 elsewhere) |
| `--captions` | `word`: three words at a time, the spoken one yellow. `bubble`: each group once in a white bubble. `none` |
| `--cap-y` | the captions' center, px from the top. Defaults: fill 1380, blur 1460, focus 1420, facecam 1120, react 1560 |
| `--font` | the caption and hook face; Inter Black unless given, Archivo Black is also installed |
| `--lines` | captions written out, `[[start, end, "text", "RRGGBB"?], ...]`: the footage's own subtitles word for word (source seconds), or `narrate`'s `lines.json` with `--lines-time output` |
| `--voice` | a narration track laid over the clip, with the footage's own sound under it at `--bed-gain` |
| `--cam` | facecam and react: `auto` finds the webcam; else its box as fractions |
| `--title` | react layout: the title on the seam, `box` (black on a white band) or `outline` (white with a black outline, for 3 to 6 words) |
| `--trim-bottom` | drop this fraction of the source's bottom first: burned-in subtitles, a caption bar |
| `--lang` | the language spoken, for the swear check |
| `--allow-profanity` | keeps swears in sound and captions; only on the person's word |

Writes `jobs/<id>/edits/<name>.mp4`, `.ass` (the captions), `.json` (its facts), and with
`--segments` `<name>.src.mp4` (the joined parts). Prints:

```text
clean: heard [], captions [], muted []
jobs/test-7273873a/edits/fractal.mp4
```

`heard` is each swear found in the sound and `muted` the windows silenced. After the render it
listens again; `clean: still heard [...]` means it muted more and made the sound again, up to
four times, and `clean: WARNING swears still heard after 4 rounds; do not post this clip` means
exactly that. `skipped: no presenter's face over the screen in this moment` is the react layout
refusing footage without a webcam box: pick another moment or another layout.
`facecam: no stable face found (...), using the blur layout` is the facecam layout falling back.

### `explainer`: a horizontal explainer

```text
cutroom explainer --src FOOTAGE --segments "a-b@3,c-d" --lines narration/NAME/lines.json
    --voice narration/NAME/voice_warm.wav --out edits/NAME.mp4
    [--title-words "THE@4.72,CLOWN@5.18,|GOT@5.66,MEANER@5.92" --title-end 7.0]
    [--title "TEXT" --title-start S] [--tag "TEXT"]
    [--music FILE --music-gain 0.16] [--bed-gain 0.2] [--lang en]
```

| Parameter | Meaning |
|---|---|
| `--segments` | as for `cut`; a part faster than 1 gets a yellow badge, "3× SPEED", while it plays |
| `--lines`, `--voice` | what `narrate` wrote, the voice mastered. Each line is shown as sentence subtitles |
| `--title-words` | a headline thrown word by word: each `WORD@second`, `|` before a word starts a new line, all gone at `--title-end`. 232 px, gold with a brown outline. A narration line that starts while it is up gets no subtitle |
| `--title`, `--tag` | a small title at the top left for 4.6 s from `--title-start`, and a label above it. Off unless given |
| `--music` | looped under everything at `--music-gain`, faded in and out, ducked while the voice speaks |
| `--bed-gain` | the footage's own sound |

Writes the video, `<out>.ass`, and `<out>.src.mp4`. Prints, after listening to the result:

```text
edits/explainer_base.mp4 19.5s, fast parts [(0.0, 3.0, 3.0)], swears heard: none
```

Status 1 where a swear is heard: find it with `clean`, and change the take or the footage.

### `reveal`: an opening with signs

```text
cutroom reveal IN.mp4 OUT.mp4 --sign art/first.png@1.9 [--sign art/second.png@2.75] --end 4.0
    [--chime auto|FILE|none] [--chime-gain 0.6]
```

Each sign is a picture with transparency and the second it pops in. One sits in the middle;
two are stacked, the first at y 300 and 880 px wide, the second at y 780 and 1060 px wide. The
video behind is dimmed and blurred until `--end`. The chime starts with the last sign. Prints
the output's path. `IN` has to be 1920 by 1080.

### `key`: cut a picture out of green or magenta

```text
cutroom key IN.png OUT.png [--color auto|green|magenta] [--low 40] [--high 120]
```

Prints `art/sign.png 1200x400 keyed from green`. A pixel is opaque below `--low` of the key
color and clear above `--high`. Fails saying the corners are neither green nor magenta when
the background is not flat: pass `--color`, or have the art made again on a flat one.

### `join`: several recordings as one source

```text
cutroom join FIRST SECOND [MORE...] --out footage/both.mp4
```

```text
{"out": "footage/both.mp4", "size": "1920x1080",
 "clips": [{"clip": "footage/test.mp4", "offset": 0.0, "seconds": 30.0},
           {"clip": "footage/stream.mp4", "offset": 30.0, "seconds": 12.0}]}
```

A second read off the second clip's own sheet is `offset` later in the joined source.

### `fit`: a copy at a chosen size

```text
cutroom fit MASTER.mp4 OUT.mp4 [--mb 18.2] [--audio-kbps 160] [--preset slow]
```

Prints `edits/explainer_page.mp4 3100k 8010727 bytes (8.0 MB)`: the video bit rate it used and
the size written. Aim a little under a limit. It refuses a target that leaves the picture under
150 kb/s.

### `translate`: a clip in another language

```text
cutroom translate jobs/<id> --pick N [--name STEM] --sentences
cutroom translate jobs/<id> --pick N [--name STEM] --lang es --text translations/es.json [--voice] [--hashtags "#a #b"]
```

`--sentences` prints what to translate:

```text
{"hook": "This fractal never ENDS", "sentences": ["Wait, what is that?", "No way, look at this fractal zoom."]}
```

Write the same shape, translated, with as many sentences, and pass it with `--text` and its
`--lang`. Writes `edits/<name>_<lang>.mp4`, `.ass`, and `<name>_<lang>.post.md` (the translated
hook as post text). `--voice` adds a stock voice speaking the hook, for `es`, `pt`, `de`, `ru`,
`fr`, `it`, `pl`, `tr`, `ja`, `ko`, `ar`, and `hi`. Fails naming the two counts when the file's
sentences do not match the clip's.

## Checking

### `check`: the final check

```text
cutroom check CLIP.mp4 [--size 1080x1920] [--caption "post text"] [--lang en] [--rules rules.md]
    [--lufs -17:-13] [--ass CAPTIONS.ass] [--allow-profanity]
```

```text
PASS  resolution 1080x1920  [1080x1920]
PASS  fps about 30  [30.00]
PASS  has audio
PASS  duration 7-60s (default)  [14.3s]
PASS  loudness -17 to -13 LUFS  [-13.8 LUFS]
PASS  no swearing in the audio
PASS  no swearing in the captions
PASS  no swearing in hook and post caption
PASS  rules file  [none given, defaults used (NOT a rules check)]
RESULT: PASS
```

Status 1 on any FAIL. `--size 1920x1080` for a horizontal cut. `--caption` is the words of the
post, which are read for swears and for what the rules ask. `--ass` names the captions where
they are not beside the clip under its own name (a `reveal`'s output: the `.ass` of the video
it was laid over). `--rules` is a text file with any of these lines, for a platform's or a
campaign's terms:

```text
min_seconds: 15
max_seconds: 60
required_hashtags: #a #b
required_mention: @someone
banned_terms: free download, giveaway
```

The check passes what it measures. That the hook is true, the crop keeps what matters, and the
voice sounds right are yours and the person's to judge.

## Long commands

`engine_exec` gives a command five minutes. Longer work is a job:

```text
selkies-modal-job start NAME -- cutroom cut jobs/<id> --pick 1 --layout blur --hook 'TEXT'
selkies-modal-job status NAME        NAME  running|done|failed (exit N)  started <time>  <command>
selkies-modal-job status             every job
selkies-modal-job log NAME           the last 40 lines it printed
selkies-modal-job stop NAME
```

A job keeps the engine awake while it runs, and its log is kept with the workspace. Names are
letters, digits, `.`, `_`, `-`.
