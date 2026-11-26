<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.

  This file is adapted from the skills of gtavi-claudecode (the dev diaries of
  drive-narrated-clips), generalized from one game's diaries to any explainer,
  and incorporates work covered by the following copyright and permission
  notice:

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

# Education

A video that shows how something works or how it was made: an explainer, a tutorial, a dev
diary. One idea, shown on screen and said in a calm voice, by someone talking to their peers.
The default way to make one is by code, in the engine the turn's state names for a video edited
by code: the person's recording is cut to the narration, sped up where nothing has to be read,
and subtitled. This is a starting point, and the person's own rules replace any of it.

## The opening card

What they have to show decides how the video is built. One line ("An explainer. What do we have
to show?"), then one card that asks and, where they have a recording, takes it:

```json
{
  "title": "What do we have to show?",
  "components": {"type": "stack", "children": [
    {"type": "pick", "id": "material", "columns": 3, "options": [
      {"value": "recording", "label": "I have a recording", "note": "A screen, a game, or the real thing", "icon": ["111111111111", "100000000001", "100010000001", "100011000001", "100011100001", "100011000001", "100010000001", "100000000001", "111111111111", "000001100000", "000111111000", "000000000000"]},
      {"value": "notes", "label": "I have notes", "note": "A script, or what each part shows", "icon": ["000000000000", "011111111110", "010000000010", "010111111010", "010000000010", "010111111010", "010000000010", "010111100010", "010000000010", "011111111110", "000000000000", "000000000000"]},
      {"value": "topic", "label": "Just the topic", "note": "We find the pictures together", "icon": ["000011110000", "000100001000", "001000000100", "001000000100", "001000000100", "000100001000", "000010010000", "000010010000", "000011110000", "000000000000", "000011110000", "000001100000"]}]},
    {"type": "upload", "id": "footage", "label": "Drop the recording here", "accept": "video", "section": "Footage",
     "when": {"material": "recording"}},
    {"type": "field", "id": "link", "label": "Or paste a link to it", "when": {"material": "recording"}}]},
  "submit": "Start",
  "waits": true
}
```

It answers with `material`, and for a recording with `footage` (the library entry the file
became, `{"tag", "name", "kind"}`, or null) and `link` (their words, or empty).

| The answer | Your next turn |
|---|---|
| `recording` | Go on with the file or the link. A link is fetched by the engine where its skill says it can; where it cannot, ask for the file. Ask in the same turn for a note of what each part shows, if they have one: a sentence a clip is enough, and the script is written from it. |
| `notes` | Ask them to paste the notes, then ask whether there is footage to go with them. |
| `topic` | Ask for it in one line, and offer three videos it could be, each one idea with a title. The pictures are then recorded by them, or generated (the `movie` skill), or composed as type and diagrams. |

## What to learn, in order

1. **The material**, from the opening.
2. **The one idea.** From the recording and the notes, offer three videos it could be, each a
   title that says what changed or how it works ("How you pick your next map", "We reworked how
   chests open"). One idea a video: a second idea is a second video.
3. **Who it talks to, and where it posts.** Decide both from what they said (developer to
   developer on a forum, a teacher to beginners on a video site) and say so. Ask only when it
   is open.
4. **The voice**, by ear: the script's first line in three voices on a card whose tiles play
   (the `sound` subagent makes them), or their own recorded narration, uploaded.
5. **The opening and the close**, once, for a series: how every video starts and ends, so the
   series is recognized in its first seconds.

Decide yourself, and report: where the footage is sped up, the subtitle style, the music level,
and file names.

## Rules that hold unless the person changes them

These came from a person who makes these videos, as corrections to work they were shown. Start
from them, and replace any of them with the rule your person gives.

- **Horizontal first.** The video is made at 1920 by 1080 and approved. Only then is the
  vertical version made, and both are delivered.
- **The script is written first, and says only what the footage and the notes show.** Reasoning
  about a design is fine. A detail nobody showed or wrote down is not: do not invent how
  something works.
- **One idea a video**, 30 to 45 seconds unless they ask for longer.
- **A calm, plain voice, peer to peer, as a tip.** One voice, unhurried. Never the voice of an
  advertisement.
- **Speed respects what must be read.** Walking, menus, and work in an editor run at two to four
  times speed, with a badge on screen that says so. The thing the video is about runs at normal
  speed. Small text on screen runs at half speed, or holds, so it can be read.
- **The voice is on top.** Music is quiet background under it and drops further while it
  speaks. The recording's own sound sits lower still.
- **It ends with a question** the viewer can answer in a comment.
- **The first three or four seconds are memorable and the same every time**: a spoken welcome,
  the series' name on screen as it is said, and a short sound on the reveal.

## The default pipeline

| Step | What happens | Who | The person decides |
|---|---|---|---|
| 1. Bring it in | Start the engine the state names, the first engine of the project, when there is a recording to map. `engine_import` copies it in | You | The start, on the page's approval |
| 2. Map it | A frame for every second with its time, the cuts, and whether anyone speaks | The engine's operator | Nothing |
| 3. Outline | The idea as four to eight parts: what is shown (which seconds of the recording, at what speed) and the one sentence said over it | You | The outline |
| 4. Script and voice | The narration written, generated, and mastered before the cut, because the voice sets the video's length and the footage is fitted to it | You write; `sound` generates; the operator masters | The voice, by ear |
| 5. Cut | The parts at their speeds under the voice; a subtitle a sentence, clear of anything the recording shows at the bottom; the headline thrown on screen word by word as it is said; quiet music | The operator | Nothing |
| 6. Check | Every sentence is on screen with the picture it names; text can be read; no swear word is heard or shown; the levels | The operator, then you with `preview` and `look: true` | Nothing |
| 7. Show | `preview` with a `version`, the words to post beside it, and what to judge by ear | You | Approval of the horizontal cut, and what to change |
| 8. Vertical | The approved cut reframed to 9:16 | The operator | Approval |

The engine's own skill (`cutroom` or `hyperframes`, whichever the state names) has the commands
of steps 2 and 4 to 8.

### The outline and the script

- A recording of making something is usually pairs: the work (in an editor, a tool, a
  workshop), then the result (the thing tried out). Cut each pair as the work at speed, then
  the result at normal speed, and put the sentence that names the change on the result.
- A sentence a part. Short sentences, said the way one person tells another. Where the notes
  give a term, use their term.
- End with one tip the viewer can use and one question for the comments.
- Spoken words are written in normal case, as they are said. A name the voice reads wrong is
  written the way it sounds in the spoken text and correctly in the subtitle. Confirm what was
  said with a transcript of the finished voice.
- `review` checks a script against the notes and the map before a voice is generated: every
  sentence has to point at seconds of the recording that show it.

### The voice

- A stock voice from `generate_audio`, `kind: "speech"`, with the delivery in `style` (calm,
  friendly, unhurried, talking to peers), the same voice for every video of a series.
- Or the person's own narration, recorded and uploaded.
- **A cloned voice needs the right to the recordings.** Before a voice is made from recordings
  of a real person, with any tool, ask once and plainly whether the person has that speaker's
  agreement and the right to use those recordings. No clone is made before they say yes.
- A narration voice is mastered dry, with no room sound, by the engine. Keep the takes of a
  series' opening line and reuse them, so every video opens with the same sound.

### The review

You check frames and measured levels. You do not hear, so the person listens to every video:
tell them, with each one, what to listen for (the voice over the music, a name that may be
misread, the opening). Their answer is usually a short message of changes. Then:

1. Say the changes back as a numbered list, in the same turn in which you start on them.
2. Render the same video again with only those changes, keeping the voice takes it has.
3. Check it again, and show it as the next version (`version: "v2"`), with one line on what
   changed.
4. **Keep the rule.** A change that is a rule ("no title in the corner", "the headline bigger",
   "music lower") is written into the project's rules at once, as the `studio` skill says, so
   the next video follows it without being told.

### The words of the post

An explainer posts with a title and a body, not a short caption: the title says the one idea,
the body says in two or three sentences what was done and why, and it ends with the question
the video ends with. Write it in the language of the place it posts.

## The person's decisions

The idea, the outline, the voice, the opening of a series, the horizontal cut by ear, the
vertical version after it, cloning a voice, and every post.

## Cost

Engine time, from the first mapping to the last check, at the tier the engine's skill names.
The narration, the music, and any generated picture for the series' name cost by the result,
and each result says what it cost; a series pays for its opening, its music, and its art once.
Stop the engine when a video is shown and the person is listening.

## What is not possible yet

- **You do not hear.** Levels are measured and words are transcribed; how it sounds is the
  person's to judge, every time.
- **`generate_audio` speaks in the voices its `voice` parameter lists.** It takes no recording
  to copy a voice from.
- **Nothing is posted for the person.**
- **Facts beyond the recording need a source.** Where the video explains something the footage
  and the notes do not show, hand `research` the claim before it is said.
- **What the engine can fetch, cut, and render is its skill's to say.**

## The two engines

Which engine edits by code is the person's setting, and the turn's state names it. Use that
one, by its own skill (`cutroom` or `hyperframes`), and do not ask them to choose. The two
differ in what they are good at: the Cut Room cuts existing footage with FFmpeg, which is what
a recording fitted to a narration needs; HyperFrames composes a video from HTML, CSS, and
animation with footage as one of its layers, which is what an explainer of type, diagrams, and
motion needs. Where the engine the state names is the poor fit for what they asked, say so in a
line, name the setting (Settings, Video editing), and do the job with it.
