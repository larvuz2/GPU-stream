<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Vertical Shows

A serial drama made for a phone held upright: episodes of one to two minutes, each opening on a
hook and ending on a cliffhanger, watched one after another. It is made the way a film is, by
the `movie` skill, and this file says how it opens and where it differs.

## The opening card

One line ("A show it is. Where does it come from?"), then:

```json
{
  "title": "Where does the show come from?",
  "components": {"type": "pick", "id": "story", "columns": 3, "options": [
    {"value": "script", "label": "I have episodes", "note": "Scripts, or a bible of the show", "icon": ["000000000000", "001111110000", "001000011000", "001000010100", "001000011110", "001011100010", "001000000010", "001011111010", "001000000010", "001011111010", "001000000010", "001111111110"]},
    {"value": "idea", "label": "I have a premise", "note": "Who it is about, in a line", "icon": ["000011110000", "000100001000", "001000000100", "001000000100", "001000000100", "000100001000", "000010010000", "000010010000", "000011110000", "000000000000", "000011110000", "000001100000"]},
    {"value": "scratch", "label": "Start from scratch", "note": "I pitch three shows, you pick", "icon": ["000001000000", "000001000000", "000011100000", "011111111100", "000011100000", "000001000000", "000001000100", "000000000100", "000000011111", "000000000100", "000000000100", "000000000000"]}]},
  "instant": true,
  "waits": true
}
```

| The answer | Your next turn |
|---|---|
| `script` | Ask for the text in one line. Read all of it, and answer with the premise you hear, the leads, how many episodes there are, and how each one ends. |
| `idea` | Ask for it in one line. Write it back as the show's premise with two sharper variations, and ask which is the show. |
| `scratch` | Pitch three shows at once: for each, the premise in a line and the last image of episode one. Ask which to make, with "Three more" as the way out. |

## What to learn, in order

1. **The premise**, from the opening: who it is about, what they want, and the reversal the
   season turns on.
2. **Episode one's hook and cliffhanger.** Propose three pairs: what the first three seconds
   show, and the face, threat, or question the episode ends on. This is the show's promise, so
   it is settled before the cast.
3. **The leads**, two or three people: the one we follow, the one who stands in their way, and
   the one they want or fear. One sentence of look each, as for a film.
4. **The art style**, shown as three style frames at 9:16.
5. **The size of the season**, on one card that opens on what you would choose. Start small: a
   pilot of three episodes proves the show and its cost before a season is paid for.

   ```json
   {
     "title": "The size of the season",
     "components": {"type": "stack", "children": [
       {"type": "segmented", "id": "episodes", "label": "Episodes to make first", "options": [
         {"value": 1, "label": "1"}, {"value": 3, "label": "3"}, {"value": 10, "label": "10"}, {"value": 20, "label": "20"}],
        "value": 3},
       {"type": "segmented", "id": "length", "label": "Each episode", "options": [
         {"value": 60, "label": "60 s"}, {"value": 90, "label": "90 s"}, {"value": 120, "label": "2 min"}], "value": 90},
       {"type": "slider", "id": "budget", "label": "Generation budget", "min": 20, "max": 600, "step": 10,
        "value": 180, "unit": "$"}]},
     "submit": "Set the season",
     "waits": true
   }
   ```

## Where it differs from a film

| | A film | A vertical show |
|---|---|---|
| Frame | 16:9 or wider | 9:16. Compose center-weighted, faces in the upper middle, and keep the bottom fifth and the right edge clear: the platform's buttons and the captions sit there |
| Unit | The scene | The episode: 60 to 120 seconds, 8 to 15 shots, each 1.5 to 3 seconds in the cut |
| Shape | Beats over the whole running time | Every episode has all four: a hook in the first 3 seconds, an escalation with one new piece of information, a turn, and a cliffhanger in the last 5 seconds, cut on it |
| Written as | One script | A season outline (one line an episode: hook, turn, cliffhanger), then a script of one to two pages for each episode |
| Library | Everything the script names | Few places, and the leads' sheets and face entries first: close shots carry the show, so faces have to hold |
| Order of work | The whole film, stage by stage | Episode one end to end before any other: script, shots, and cut. What it teaches (the look in motion, the pace, the cost) sets the rest |
| Captions | Optional | Burned in, in the edit |

The beat table and the script form are in the `movie` skill's story.md ("Vertical show"); the
evidence for the first seconds is in [first-seconds.md](first-seconds.md).

## The default pipeline

| Stage | Who | First engine |
|---|---|---|
| Season outline, then episode scripts | You for the outline; `story`, one per episode, once the outline is approved | None |
| The leads and the places | `character-design` and `production-design`, at the same time | None |
| Tests: each lead in a close shot, speaking one line | `animation` | None |
| Episode one: shot list, shots | You, then `animation` | None |
| Episode one: the cut, with captions | You with the `filmcraft` skill, or the FilmCraft agent | FilmCraft, when episode one's takes are selected |
| The other episodes | `story` and `animation`, an episode each, several at once | The editor again, a batch at a time |

## The person's decisions

The premise, episode one's hook and cliffhanger, the leads' looks, the style, the season
outline, the pilot's cut, and each batch of episodes with its budget before it is generated.

## Cost

An episode's cost is its generated seconds: its length plus the handles of its shots. A
90-second episode is about 90 to 110 generated seconds, which is $43 to $52 at the 720p price
before retakes (the `movie` skill's "Cost and time" has the prices). Quote a season as episodes
times that, and ask for the budget a batch at a time.

## What is not possible yet

- **A voice that is the same in every shot is not promised.** The video model makes each shot's
  speech with its picture. Whether a lead sounds the same from shot to shot has not been tested
  here: put a spoken line in the pilot's tests, ask the person to listen for it, and decide
  together what to do if it drifts.
- **Nothing is posted for the person**, and no tool reads how an episode performed: they bring
  the numbers back.
- Everything the `movie` skill lists under the same heading.
