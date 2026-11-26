<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Music Videos

Pictures cut to one track. The track comes first, because everything else is timed to it: the
person brings it, or you make it with them. Then the pictures are designed and generated as the
`movie` skill does, and cut to the track on a timeline.

You do not hear. A sound reaches you as its facts and its waveform, never as music, so every
choice between sounds is the person's, made on a card that plays them. Say so once, plainly, and
then ask them to listen wherever a film's skill would have you look.

## The opening card

One line ("A music video starts with the track. Do you have it?"), then:

```json
{
  "title": "The track",
  "components": {"type": "pick", "id": "track", "columns": 2, "options": [
    {"value": "have", "label": "I have the track", "note": "A finished song or a demo", "icon": ["000001111111", "000001111111", "000001000001", "000001000001", "000001000001", "000001000001", "000001000001", "001111000111", "011111001111", "011111001111", "001110000110", "000000000000"]},
    {"value": "make", "label": "Make one with me", "note": "Tell me the kind of song, hear three", "icon": ["000001000000", "000001000000", "000011100000", "011111111100", "000011100000", "000001000000", "000001000100", "000000000100", "000000011111", "000000000100", "000000000100", "000000000000"]}]},
  "instant": true,
  "waits": true
}
```

## They have the track

Ask for it with one input:

```json
{
  "title": "Your track",
  "components": {"type": "upload", "id": "song", "label": "Drop the song here", "accept": "audio",
                 "section": "Music", "required": true},
  "submit": "Use this track",
  "waits": true
}
```

It answers `{"song": {"tag": "@...", "name": "...", "kind": "audio"}}`: the library entry the
file became. Then:

1. `library_look(tags=[<its tag>])` hands you its waveform. Read its shape: where it is quiet,
   where it is loud, where it stops. Tell the person what you see in a line, as shape, not as
   music.
2. Say once, without making it a question, that a song that is not theirs needs its owner's
   permission before the video is published.
3. Go on to [the pictures](#the-pictures).

## They want one made

Ask what kind of song on one card, every control opening on what you would choose from anything
they have said so far. Fit the options to them: these are a start.

```json
{
  "title": "The song",
  "components": {"type": "stack", "children": [
    {"type": "segmented", "id": "mood", "label": "Mood", "options": ["Bright", "Dreamy", "Dark", "Fierce", "Tender"],
     "value": "Dreamy"},
    {"type": "select", "id": "genre", "label": "Genre", "options": ["Pop", "Hip-hop", "Rock", "Electronic", "R&B",
     "Folk", "Latin", "Cinematic", "Lo-fi", "Something else"], "value": "Pop"},
    {"type": "segmented", "id": "tempo", "label": "Tempo", "options": ["Slow", "Mid", "Fast"], "value": "Mid"},
    {"type": "segmented", "id": "voice", "label": "Voice", "options": [
      {"value": "sung", "label": "Sung"}, {"value": "instrumental", "label": "Instrumental"}], "value": "sung"},
    {"type": "segmented", "id": "length", "label": "Length", "options": [
      {"value": 30, "label": "30 s"}, {"value": 60, "label": "1 min"}, {"value": 120, "label": "2 min"}], "value": 60},
    {"type": "field", "id": "about", "label": "What is it about?", "placeholder": "A line, or leave it to me"}]},
  "submit": "Make three versions",
  "waits": true
}
```

Then:

1. **The words, for a sung song.** Write them yourself, sized to the length, from what the song
   is about, and show them in your message. Ask "Sing these?" with "Sing these", "Change the
   words", "Make it instrumental", recommending the first. Lyrics are approved before they are
   paid for.
2. **Three versions that differ in one named way** (the arrangement, the tempo, or the voice),
   each generated into an entry of its own so the card can play each and the pick has a tag:

   ```text
   generate_audio(prompt="<genre, mood, tempo, instruments, in a sentence>", kind="music", lyrics="<the approved words>",
     seconds=60, save_to={"section": "Music", "name": "Song, version A", "tag": "@song-a"})
   ```

   An instrumental takes `instrumental: true` and no `lyrics`. The lengths the tool makes and
   its other choices are in its parameters. Three versions are a job for the `sound` subagent:
   give it the brief from the card word for word, the approved lyrics, the three tags, and the
   one way the versions should differ.
3. **The pick, by ear**, on a card whose tiles play. Write under each what makes it different,
   as you asked for it:

   ```json
   {
     "title": "Three versions of the song",
     "components": {"type": "pick", "id": "song", "columns": 2, "options": [
       {"value": "@song-a", "label": "A", "note": "Piano first, the beat comes in late", "audio": "song-a"},
       {"value": "@song-b", "label": "B", "note": "Faster, guitar-led", "audio": "song-b"},
       {"value": "@song-c", "label": "C", "note": "Sparse, the voice up front", "audio": "song-c"},
       {"value": "none", "label": "None of these", "note": "I'll say what to change"}]},
     "instant": true,
     "waits": true,
     "media": [{"tag": "@song-a", "kind": "audio"}, {"tag": "@song-b", "kind": "audio"}, {"tag": "@song-c", "kind": "audio"}]
   }
   ```

   On a pick, record it (`library_upsert` with `metadata: {"approved": true}` on the chosen
   entry and `{"status": "rejected"}` on the others, moved to Archive). On "none", ask what to
   change and make three more that change that one thing.

The same card compares anything that is heard: three takes of a sound effect, one line read by
three voices.

## The pictures

1. **The idea of the video**, as one click:

   ```json
   {
     "title": "What do we see?",
     "components": {"type": "pick", "id": "concept", "columns": 2, "options": [
       {"value": "performance", "label": "A performance", "note": "The artist, or a character, carries it"},
       {"value": "story", "label": "A story", "note": "A small film runs under the song"},
       {"value": "world", "label": "A world", "note": "Places and images that feel like the song"},
       {"value": "lyrics", "label": "The words", "note": "The lyrics on screen, designed and moving"}]},
     "instant": true,
     "waits": true
   }
   ```

   Then pitch that idea in three lines of your own and ask whether it is the video.
2. **The look**, shown as three style frames (`art-direction`), as for a film.
3. **The part to film first.** Do not plan the whole song before anything exists. Ask which 20
   to 30 seconds matter most (the chorus, usually), make that part end to end, and let it set
   the look, the pace, and the price of the rest. For a track they brought, ask where that part
   starts, in minutes and seconds; for one you generated, propose it from the lyrics.
4. **The library**, for what that part shows: the performer or the characters, the places.
5. **Tests in motion**, then the shot plan for that part: one row per shot with its start in
   the song, its length, and what the music does there. Cuts land where the music changes, and
   a faster song takes shorter shots.
6. **The shots**, then the cut.
7. **The rest of the song**, part by part, each with its budget.

## The default pipeline

| Stage | Who | First engine |
|---|---|---|
| The song: versions to compare | `sound` | None |
| The idea, the lyrics, the shot plan | You | None |
| The look | `art-direction` | None |
| The performer, the characters, the places | `character-design` and `production-design`, at the same time | None |
| Tests and shots | `animation`, a part of the song each | None |
| The cut to the track | You with the `filmcraft` skill, or the FilmCraft agent: the track on the timeline, the shots' own sound muted, cuts on the music | FilmCraft, when the first part's takes are selected |

## The person's decisions

The track, the lyrics, the idea, the look, whose face performs and that they agreed to it, the
first part's cut, the budget for the rest, and the final cut.

## Cost

- **The song.** Each version is one generation, and its result says what it cost; this skill
  states no price. Before the first, say that three versions are three generations and that each
  shows its price as it is made. From then on, quote from what the first one cost.
- **The pictures** cost by the second of the track they cover, and that is most of the money: a
  3-minute song is 180 seconds of shots, $85 at the 720p price before handles and retakes, and
  $54 with `model: "fast"` (the `movie` skill's "Cost and time" has the prices). This is why the
  first part comes first: 30 seconds proves the video for a sixth of that.
- **The edit** is engine time, from the first cut on.

## What is not possible yet

- **You cannot hear**, and no tool tells you a song's tempo, its beats, or where its chorus
  starts. The waveform shows loud and quiet; the person tells you the rest, and exact timing is
  set on the timeline in the edit.
- **A brought track's length is not known to you** until an engine opens it. Ask, or plan by its
  parts and take the length from the first preview in the edit.
- **Singing in time with the track has not been tested.** `generate_video` takes a sound as a
  reference, but whether a face then sings in sync is unproven here. Make one such shot as a
  test before a performance video is planned around it, and where it fails, show the performer
  without a close view of the mouth.
- **A generated song cannot be extended or changed.** `generate_audio` takes no sound to work
  from, so another call is another song. Ask for a song at its full length from the start.
- **A real artist's voice or name is never imitated.** Describe the qualities wanted, not whose
  they are.
