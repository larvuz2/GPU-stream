<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Story: logline, beats, script, breakdown

How a film's story is written with the person and turned into the list of what the film needs.
Nothing here needs an engine or a generation: it is conversation, and documents saved to the
project's repository at the paths given. Each document is a checkpoint the person approves:
logline, then beats, then script. The breakdown is yours to make and report.

## When they bring a script

Read all of it before you reply. Then answer with:

- the logline you hear, in the form below;
- the cast, the locations, and the props that matter;
- the scene count and the estimated running time (a page of screenplay is about a minute);
- what is unclear, and what cannot be filmed as written (a take longer than `generate_video`
  makes, text that must be readable on screen), each with a fix you propose.

Ask before changing their words. Then go to the [breakdown](#breakdown).

## When you write one

Logline, then beat sheet, then script, each approved before the next. For each, offer two or
three versions that differ in idea, your recommendation first, and ask which is the film. A
finished draft can be handed to the `story` subagent once the beats are approved; give it the
logline, the cast with their library descriptions and tags, the beats, and the format's row
below, because it has none of this conversation.

## Logline and synopsis (`beats.md`)

```markdown
# <Title>

**Logline.** When <inciting incident>, <protagonist with a flaw> must <goal> before
<stakes or ticking clock>.

**Synopsis.** One paragraph: setup, turn, escalation, climax, resolution.

**Tone.** <three adjectives>; feels like <reference>, <reference>; not like <reference>.
```

## Beat sheets by format

Percentages are of running time. A beat is one change: something is learned, decided, or lost.

**Movie (short or feature).**

| Beat | Where | What happens |
|---|---|---|
| Opening image | 0-2% | The world and the protagonist's problem in one picture |
| Setup | 2-10% | What they want, what they need, what is wrong |
| Inciting incident | 10% | The event that breaks the routine |
| Debate | 10-20% | Refusal or doubt |
| Into act two | 20-25% | They choose to act |
| Midpoint | 50% | False win or false defeat; the stakes rise |
| All is lost | 75% | The worst moment, the cost of the flaw |
| Climax | 80-95% | They act from what they learned |
| Final image | 95-100% | The opening image, changed |

**Commercial.**

| Length | Structure |
|---|---|
| 15 s | Hook (0-2 s), product as the turn (2-10 s), brand and call to action (last 3-5 s) |
| 30 s | Hook (0-3 s), desire or problem (3-10 s), product as the turn (10-20 s), proof or payoff (20-25 s), brand and call to action (25-30 s) |
| 60 s | A small story: character, want, obstacle, product, changed world, brand |

Land the product by the halfway point, show it in use, end on the pack shot or logo with the line
the person approves. Cutdowns (30 to 15 s, 16:9 to 9:16) are planned now, not discovered later.

**Episode.** Cold open (0-10%, a hook from this episode), acts one to three (or four) each ending
on a turn, a tag or stinger at the end. An A plot carries the episode; a B plot echoes its theme.
Every episode ends with a question the next one answers.

**Vertical show.** A season of 50-100 episodes of 60-120 seconds, each one to two pages, built
backward from its last beat:

| Beat | Where | What happens |
|---|---|---|
| Hook | 0-3 s | A slap, a reveal, a line that demands a reaction |
| Escalate | 3-45 s | The conflict sharpens; one new piece of information |
| Turn | 45-80% | A reversal or a reveal |
| Cliffhanger | last 5 s | A question, a threat, or a face that changes everything; cut on it |

Big emotions, few locations, close shots, and the protagonist's status changing every few
episodes. Plan 8-15 shots per episode.

## Script (`script.fountain`)

Screenplay form in Fountain plain text: about one page per minute of screen time.

```text
INT. MARA'S KITCHEN - NIGHT

Rain against the window. MARA (34, close-cropped black hair, red raincoat still on) stands
at the counter, turning a small silver locket in her fingers.

The back door opens. JONAS (40s, soaked, a cut above one eye) stops in the doorway.

JONAS
You kept it.

MARA
(not looking up)
You said you'd come back.
```

Rules that matter for generation:

- Describe only what a camera sees and a microphone hears.
- Introduce each character in capitals with the description their library entry has, word for
  word. A character the script adds gets a description here that becomes their entry.
- Keep dialogue short: lip-sync is best on one or two sentences per shot.
- Write sound cues into the action.
- Keep a vertical show's episode to one or two pages, with a hook in its first seconds and a
  cliffhanger at its end.

## Breakdown

One row per scene, saved at the top of `shotlist.md`:

| Scene | Heading | Pages | Characters | Wardrobe | Environment | Props | Sound | Notes |
|---|---|---|---|---|---|---|---|---|
| S01 | INT. MARA'S KITCHEN - NIGHT | 1.5 | @mara, @jonas | @mara-raincoat | @kitchen-night | @locket | rain, kettle | the cut above his eye |

Every tag in the breakdown is a library entry with an approved reference image before the shot
list is locked. The main characters and the look are already there from the brief; the breakdown
is where the remaining characters, the places, the props, and the wardrobe changes are found.
List what the library lacks (`library_list`), with a tag and a one-sentence description for each,
and that list is the next batch of design work.

The breakdown of a locked script is a job for the `story` subagent while you work on something
else: give it the script (or its path in the repository) and the library's existing tags.
