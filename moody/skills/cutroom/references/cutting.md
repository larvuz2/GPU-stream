<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.

  This file is adapted from the skills of gtavi-claudecode
  (drive-narrated-clips, viral-clips, clip-cutter, and twitch-reaction), and
  incorporates work covered by the following copyright and permission notice:

      MIT License

      Copyright (c) 2026 Bodila51

      Permission is hereby granted, free of charge, to any person obtaining a copy
      of this software and associated documentation files (the "Software"), to deal
      in the Software without restriction, including without limitation the rights
      to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
      copies of the Software, and to permit persons to whom the Software is
      furnished to do so, subject to the following conditions:

      The above copyright notice and this permission notice shall be included in all
      copies or substantial portions of the Software.

      THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
      IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
      FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
      AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
      LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
      OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
      SOFTWARE.
-->

# Cutting in the Cut Room

How to turn what the footage's map says into the parameters of a cut: what to keep, where a
clip starts, how to frame it, and how voices are laid. The rules are a maker's, settled over
many revisions of real clips; each has its reason, so you can tell when one does not apply.
Which moment and which hook are the `video` skill's to choose with the person; this file is
how the choice becomes a command.

## Reading the map

Run `sheet` and `moments` first (commands.md). Then, with the sheet in front of you
(`preview` with `look: true`), write down before you cut:

- **Where the subject first appears.** The clip starts there. Seconds before it are cut.
- **Which seconds are dead.** Two seconds where nothing changes become a jump cut, or a
  speed-up when the viewer has to see that time passed.
- **Where the payoff peaks.** The clip ends there, with no outro.
- **Where the action sits, left to right, over time.** That is the `--focus` track.
- **Text the footage shows**: a title card, a sign, the interface's own subtitles, a health
  bar. A vertical crop cuts wide text in half, and captions land on low text.
- **Black**: `sheet` lists it. No segment includes it.

One sheet at a frame a second shows the whole. Read the stretches you mean to keep again at
`--every 0.5`: a cut point chosen from one-second frames is half a second off.

`moments` scores loudness and words. It does not see. A candidate is a place to look, and the
moment you cut is the one the sheet shows is worth it.

## Segments

`--segments "a-b,c-d@2,e-f@0.5"` is the edit: the parts kept, in the order they play.

- **Start and end every part on a scene cut** from `sheet`'s `scene_cuts`, or just inside one:
  a part that starts 0.05 s after a cut never shows a frame of the shot before it.
- **Order is yours.** Parts need not follow the source's order: open on the most striking shot,
  then go back.
- **Speed**: `@2` to `@4` for walking, menus, typing, and work in an editor (the explainer
  badges it); `@0.5` to replay the key moment or to let small text be read.
- **A loop**: end on the part the clip opened with.
- Add up `(b - a) / speed` over the parts for the clip's length. `explainer` prints it; `cut`
  writes it as `end` in the clip's `.json`.

From several recordings, `join` them and add each clip's `offset` to the seconds read off its
own sheet.

## The window

The focus layout shows a 4:5 window of a 16:9 source, so it shows 45% of the picture's width.
`--focus "t:cx,..."` says where its center is, in output seconds.

- One keyframe, `0:0.5`, holds the window in the middle.
- A glide follows something that moves: `0:0.5,4:0.62`.
- At a jump cut the window should switch, not glide: put two keyframes 0.01 s apart at the
  cut's output second, `8.49:0.62,8.5:0.5`. The output second of a cut is the sum of the
  lengths of the parts before it.
- Check it: `sheet <clip> --at` the second after each switch, and look. The subject of the hook
  is inside the window in frame 1 and never cropped out.

Other layouts: `blur` shows the whole picture small, for footage whose action spans the
frame; `fill` crops to the middle, for footage framed in the center; `react` and `facecam`
are for a presenter with a webcam over a screen.

## Captions and the hook

- **From the transcript** by default. Read `words` or `candidates.md` first: a transcript of
  speech over music has wrong words, and a wrong caption is worse than none.
- **From lines you write** (`--lines`) when the footage shows its own subtitles: copy them
  exactly, swears included, as `[[start, end, "text"], ...]` in source seconds. The swears are
  left out of the captions by the cut, and their times help it mute the sound.
- **From a narration** (`--lines narration/<name>/lines.json --lines-time output`) when voices
  are laid over the footage.
- **Move them off the footage's own text**: `--cap-y 1180` sits above a title card's text,
  `--cap-y 1540` below a large sign. `--trim-bottom 0.15` removes burned-in subtitles at the
  bottom of the source before anything else.
- **The hook** is 3 to 9 words, sentence case, with capitals on one or two words for emphasis.
  It says what the viewer is about to see, and the clip shows it. In the focus layout it stays
  for the whole clip; elsewhere 2.6 s unless `--hook-secs` says otherwise.

## Voices over footage

The narration sets the length. Generate the lines, lay them, read the times `narrate`
prints, then choose segments that add up to it.

**Reactions**, for footage watched for fun: two or three voices reacting to exactly what is on
screen, never a narrator selling it.

- A line is one to six words, one reaction a shot. `"tempo": 1.25` for the spec (1.3 for a
  montage): people who are excited talk fast.
- Give each speaker a caption color in `speakers`: `FFFFFF`, `8FE6FF`, `FF9AD2` read apart on
  any footage.
- `"caption": ""` is a shout or a laugh: it may overlap the others and shows no words.
- `at` puts a line on its shot. Work it out from the segments: the part the line reacts to
  starts at the sum of the parts before it.
- The spoken `text` is in normal case, as it is said; a speech model may spell out a word in
  capitals. The capitals for emphasis go in `caption`.
- The footage's own sound stays under the voices at `--bed-gain 0.3`.

**One narrator**, for an explainer: calm, one sentence a part, saying only what the footage
shows.

- Master the laid track before the cut: `vo_master ... --preset studio_warm`. Use the mastered
  file as `--voice`.
- `--bed-gain 0.2` for the footage's sound, and music at `--music-gain 0.16`. Then prove the
  voice is on top: `levels --spans` over a stretch with speech and a gap without it. A voice
  about 10 dB over the music is the level that was settled on.
- Confirm what the voice said: `words narration/<name>/voice_warm.wav --lang en`. A name read
  wrong is written the way it sounds in `text` and correctly in `caption`, and the take is
  generated again.
- Keep the takes of a series' opening line in the library and lay the same files every time,
  so every video opens with the same sound.

## An explainer's shape

What was settled on for a recording of work with a narrator, 30 to 45 s:

1. **An opening the series owns**, to 4.0 s: the first shot is four energetic seconds of the
   result, dimmed behind one or two signs that pop in on the voice's words (`reveal`). The
   narration proper starts at 4.0 s.
2. **A headline**, thrown word by word as the voice says it (`--title-words`), gone after
   about 2.5 s. Take each word's second from `words <the take> --offset <its at>`.
3. **Pairs**: the work at speed (`@3` or `@4`, badged), then its result at normal speed, with
   the sentence that names the change landing on the result.
4. **A close**: one question for the comments over a last second of the result.

No tag and no small title unless the person wants them (`--tag`, `--title`): the headline is
the title. Subtitles sit 150 px up, clear of an interface's lower edge; look at a check frame
where the footage has something at the bottom.

A sign for the opening is a picture with transparency. Have it generated on a flat pure green
background with no shadow (magenta when the art has green in it), bring it in, and
`key` it. Look at the cut-out over the footage's first frame before you use it.

## A presenter with a webcam

`--layout react --cam auto --title "TEXT"`: the face fills a panel on top, the screen the
rest, and the title sits on the seam for the whole clip.

- Run `facecam <video> --debug sheets/cam.jpg` first and look at the box. Wrong, or `none`:
  give `--cam x:y:w:h` yourself, as fractions of the picture.
- `--title-style box` is black text on a white band, for a sentence; `outline` is white with a
  black outline, for three to six words.
- `--captions bubble` shows what is said in a white bubble; `none` leaves the title alone.
- The title says what happened on screen. It never puts words in the presenter's mouth.

## After the cut

1. `check`. Read every line. A FAIL is fixed at its cause.
2. `sheet <clip> --at`: frame 1 (0.1), the second the hook or the headline is fully in, one
   frame for each caption position, the last second. Look with `preview` and `look: true`.
3. `levels`, with `--spans` wherever a voice sits over music or footage.
4. Show it, with a `version` and what to listen for.

A change the person asks for is made by running the same command with that one thing changed.
Keep the command of every version in the project's notes: it is the edit.
