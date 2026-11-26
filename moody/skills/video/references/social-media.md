<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.

  This file is adapted from the skills of gtavi-claudecode (viral-clips,
  drive-narrated-clips, moment-finder, clip-cutter, rule-check, multilang,
  learning-loop, and playbook), generalized from one campaign to any footage,
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

# Social Media

Short videos for a feed: made to stop a scroll in the first three seconds and to be watched to
the end. The default way to make one is by code: the footage is mapped, its best moments are
found, and each becomes a vertical clip with a hook, a voice, and captions, cut and checked by
commands in the engine the turn's state names for a video edited by code. This is a starting
point. A post that is better made another way (generated shots, a motion piece with no footage)
is made that way, and you say so.

[first-seconds.md](first-seconds.md) has the evidence for how a clip opens and the rules for its
hook. Read it before you pick a moment or write a hook.

## The opening card

One line ("Let's make something for the feed."), then one card with the three things that decide
how the work starts. Fit the platforms to what they said; these are a start.

```json
{
  "title": "A video for the feed",
  "components": {"type": "stack", "children": [
    {"type": "pick", "id": "platform", "label": "Where does it post first?", "columns": 3, "options": [
      "TikTok", "Instagram Reels", "YouTube Shorts", "X", "Reddit", "Several of these"]},
    {"type": "segmented", "id": "goal", "label": "What is it for?", "options": [
      {"value": "own", "label": "Show my work"}, {"value": "page", "label": "Grow a page"},
      {"value": "clips", "label": "Clip someone's content"}]},
    {"type": "segmented", "id": "source", "label": "What do we start from?", "options": [
      {"value": "footage", "label": "My footage"}, {"value": "link", "label": "A link"},
      {"value": "nothing", "label": "Nothing yet"}]}]},
  "submit": "Start",
  "waits": true
}
```

| `source` | Your next turn |
|---|---|
| `footage` | Ask for it with the card below. |
| `link` | Ask them to paste it, in one line. Whether the engine can fetch a link, and from where, is in its skill; where it cannot, ask for the file. |
| `nothing` | Ask what the post should show, with three ideas of your own to react to. Then the material is made first: generated shots (the `movie` skill, at 9:16 and a few seconds each), or a recording they make and bring. |

```json
{
  "title": "Your footage",
  "components": {"type": "upload", "id": "footage", "label": "Drop the video here", "accept": "video",
                 "section": "Footage", "required": true},
  "submit": "Use this footage",
  "waits": true
}
```

It answers `{"footage": {"tag": "@...", "name": "...", "kind": "video"}}`: the library entry the
file became. A file the upload refuses as too large comes as a link instead.

| `goal` | What it changes |
|---|---|
| `own` | Their own game, product, film, or work. No credit is needed. The clips show one thing honestly: never claim what the footage does not show. |
| `page` | A page that posts often. Every post is logged and read back ([What each post teaches](#what-each-post-teaches)), and the mix of posts is planned by the week. |
| `clips` | Someone else's footage. Ask whose it is and whether they may post it: clip a creator only inside their own clipping program or with their permission, credit them in the post, and add something of your own to every clip. Crediting someone is not their permission. |

## What to learn, in order

1. **Platform, purpose, and material**, from the opening.
2. **The language of the audience.** Decide it from the platform and the person's own language,
   say which you chose, and write hooks, lines, and captions in it.
3. **The moments**, once the footage is mapped: show the best three to five as frames on a card,
   each with one line of why it was picked, and ask which to cut first.
4. **The hook** of each clip: three options, your pick recommended.
5. **The voice**: the footage's own sound, friends reacting, or one narrator. Ask by ear, on a
   card whose tiles play the clip's first line in each voice (the `sound` subagent makes them).

Decide yourself, and report: the crop, the caption style, the music level, file names, and the
order of clips. When the person asks why you chose a moment, or how a clip was made, answer
plainly and in full: the reasoning is theirs to have.

## Rules that hold unless the person changes them

These came from a person who makes these videos, as corrections to work they were shown. Start
from them, and replace any of them with the rule your person gives.

- **The hook is in the first three seconds**, on screen and in the picture.
- **No swear word is heard or shown**: not in the sound, the captions, the hook, or the words of
  the post. A swear in the footage is silenced, and left out of the captions, not starred.
- **Reactions, not an advertisement.** A voice added to a clip sounds like friends watching it
  happen, never like a narrator selling it.
- **The voice is on top.** Music and the footage's own sound sit well under it.
- **15 to 20 seconds, 30 at most**, unless they ask for longer.
- **The words of the post open with a hook and end with the credit.**

## The default pipeline

| Step | What happens | Who | The person decides |
|---|---|---|---|
| 1. Bring it in | Start the engine the state names, the first engine of the project, when there is footage to map. `engine_import` copies the uploaded footage in | You | The start, on the page's approval |
| 2. Map it | A frame for every second with its time, the scene cuts, and whether anyone speaks (a transcript with word times) | The engine's operator | Nothing |
| 3. Find the moments | Candidates, each with why it scored | The operator; you choose among them by the rules below | Which to cut |
| 4. Hook | Three options a clip | You | The hook |
| 5. Voice | The lines written and generated before the cut, because the voice sets the clip's length and the footage is fitted to it | You write; `sound` generates | The voice, by ear |
| 6. Cut | 1080 by 1920: the kept parts joined with jump cuts and fitted to the voice, the hook on screen, captions word by word, voice over the bed | The operator | Nothing |
| 7. Check | The engine's check, then your own look at frame 1 and a sheet of frames | The operator, then you | Nothing |
| 8. Show | `preview` with a `version`, the words to post beside it, and what they have to judge by ear | You | Whether it posts, and what to change |
| 9. Post | The person posts it. You record it | The person | When and where |
| 10. Learn | Their numbers, read back at set times | You | What to test next |

The engine's own skill has every command of steps 2, 3, 6, and 7. Hand them to the engine's
operator as one job per clip, or one job for a batch of clips from one source, with the choices
already made: the moment's times, the hook, the lines, the language.

### Picking moments

Rank candidates by these, in order. Each is a reason a viewer stays.

1. **Frame 1 stops the scroll.** Open on the most striking image in the footage, not on a logo
   or an intro.
2. **One idea a clip.** Two clips from one source make two different promises.
3. **Every key word lands on its shot.** When the voice names a thing, the thing is on screen.
4. **It escalates.** Each shot is bigger than the last. End on the best one at its peak, or loop
   back to the opening image.
5. **High arousal.** Surprise, absurdity, danger, laughter. A calm shot is a breath before a
   reveal, never the clip.

And three that keep a clip honest and clean:

- Cut only where the source cuts, never in the middle of a shot, and jump over every stretch
  where nothing changes for two seconds. Skip fades to black.
- The subject of the hook is visible in frame 1 and never cropped out. Text the footage shows
  (a title card, a sign) is not cut in half by the vertical crop: move the window, move the
  captions off it, or skip the shot.
- Skip what a platform removes or a viewer resents: nudity and sexual content, spoilers of a
  story that is new, drama about real people, and anything whose title you cannot confirm on
  screen.

### The voice

- **The footage's own sound** when someone in it speaks and reacts: caption it from the
  transcript, and where the dialogue is on screen as subtitles, match the captions to it word
  for word. A wrong caption is worse than none. A transcript of footage in which nobody speaks
  is invented words: confirm there is speech before you trust one.
- **Reactions**, for gameplay and anything watched for fun: two or three friends reacting live
  to exactly what is on screen, in the audience's own slang. Lines of one to six words, one
  reaction a shot, spoken a quarter faster than the voice's normal pace. Shouts and laughs may
  overlap and need no caption. Each voice has its own caption color.
- **One narrator**, when the clip explains: the Education reference has that voice.
- Lines are generated with `generate_audio`, `kind: "speech"`, one voice per speaker, with how
  the line is said in `style`. Write the words in normal case, as they are said, because a
  speech model may spell out a word in capitals; the capitals for emphasis go in the caption.
  A name it says wrong is written the way it sounds in the spoken text and correctly in the
  caption.
- The footage's own music and sound stay underneath, at about a third of their level.
- Never claim a feature the footage does not show.
- **A cloned voice needs the right to the recordings.** Before a voice is made from recordings
  of a real person, with any tool, ask once and plainly whether the person has that speaker's
  agreement and the right to use those recordings. No clone is made before they say yes, and
  no real person's voice is imitated without it.

### The cut

- Vertical, 1080 by 1920, 30 frames a second. The action sits in a window framed to follow it,
  with the hook above it for the whole clip.
- Captions word by word, in capitals, up to three words at a time, the spoken word highlighted,
  inside the platform's safe area.
- A replay of the key moment at half speed, and a last shot that returns to the first image so
  the clip loops, where the moment earns them.
- Loudness normalized by the engine, the voice on top.

### The check

A clip is shown to the person only after all of these hold. Where one fails, fix its cause and
check again; do not argue with a failed check.

- No swear word is heard in the finished clip, listened to again after the cut in the clip's
  own language, or shown in its captions, its hook, or the words of the post.
- The length, the size, and that it has sound.
- The hook is on screen within the first two seconds, and its subject is in frame 1.
- Nothing is cropped that the viewer needs: a face, the action, text.
- Every fact in the hook and the post is true and can be seen.
- Someone else's footage is credited in the post, and the clip adds something of its own.

Look yourself as well: `preview` the clip's first frame and a sheet of its frames with
`look: true`. A check passes what it measures and nothing else.

### The review

You check frames and measured levels. You do not hear, so the person listens to every clip:
tell them, with each one, what to listen for (the voices over the music, a line that may be
misread, a silenced word). Their answer is usually a short message of changes. Then:

1. Say the changes back as a numbered list, in the same turn in which you start on them.
2. Render the same clip again with only those changes. Keep the voice takes it already has, so
   the voice does not change between versions unless that was the request.
3. Check it again, and show it as the next version (`version: "v2"`), with one line on what
   changed.
4. **Keep the rule.** A change that is a rule ("never that word", "music lower than this",
   "captions above the health bar") is written into the project's rules at once, as the `studio`
   skill says, so the next clip follows it without being told.

### The words of the post

Give them with every clip, ready to copy, in this order:

```text
<a hook: curiosity or tension, under 8 words, not the title that is on the video>

<a question anyone can answer in one word>

<a few hashtags for the platform>

<the credit, last, when the footage is someone else's>
```

How many hashtags, how long a caption, and what a platform currently allows change often: this
file states none. Where it matters, hand `research` the platform and the question.

## What each post teaches

A page improves by what its own posts did, never by guesses.

- **Record every post when it goes out**, as a library entry in a Posts section:

  ```text
  library_upsert(section="Posts", name="<the hook>", tag="@post-<n>", description="<the words of the post>",
    metadata={"platform": "...", "posted": "<date and time>", "format": "...", "length_s": ..., "source": "...",
              "credit": "...", "test": "<what this post tests, if anything>"})
  ```

- **Read the numbers at 12, 24, and 72 hours.** Ask the person to paste them or send a
  screenshot, and add them to the entry's metadata (`views_12h`, `views_24h`, `views_72h`,
  likes, shares, comments, saves). A number that is not available stays empty. Never guess one.
- **One test a day, one variable**: the style of hook, the length, the hour, the caption. Name
  it in `test`.
- **No verdict under 24 hours**, and the 72-hour number wins while a post is still moving.
- **Write each lesson as a rule** ("three steps beat five") into the project's rules, and read
  them before you plan the next post. Once a week: the three best and the three worst, the
  medians by format and by platform, more of what is above the median, and less of what stayed
  below it for a week.

## Other languages

One finished clip can serve other audiences: the captions and the hook translated, and a stock
voice reading the translated hook over the first seconds with the original sound lowered under
it. Translate what is there and add nothing. Read every translated line before the person
posts, and ask them about a language neither of you knows. Each language goes to its own page,
not five versions to one.

## The person's decisions

Which moments, each hook, the voice, every clip by ear before it posts, whether the clean
language rule stays, using someone else's footage, cloning a voice, and every post: they
publish, never you.

## Cost

No generation is needed to cut footage, so the cost is engine time: from the first mapping to
the last check, by the minute, at the tier the engine's skill names. Stop the engine when a
batch is checked and shown; the numbers are read back days later with no engine running.
Generated voices and music cost by the result, and each result says what it cost. Tell the
person before a batch what it will run: the engine's price a minute and your estimate of the
minutes.

## What is not possible yet

- **Nothing is posted or scheduled for the person**, and no tool reads a platform's numbers.
- **You do not hear the clip.** The check listens with speech-to-text; the person listens with
  their ears, to every clip.
- **You have no tool that hands the person a file.** They watch a clip in the conversation and
  in the Latest module. Where a preview says it shows a lighter copy, the full-quality file is
  the one in the project folder: give its path.
- **`generate_audio` speaks in the voices its `voice` parameter lists.** It takes no recording
  to copy a voice from.
- **A platform's trending sounds cannot be used**: the clip's own audio is its sound.
- **What the engine can fetch from a link, find in footage, and render is its skill's to say.**
  Promise a step only after you have read it there.

## The two engines

The Cut Room is built for this workflow: it cuts existing footage. HyperFrames composes a video
from HTML, CSS, and animation with footage as a layer, which suits a post that is mostly type
and motion and suits a long recording less. Use the one the turn's state names, and where it is
the poor fit, say so in a line and name the setting (Settings, Video editing).
