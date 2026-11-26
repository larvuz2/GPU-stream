<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Commercials

An ad: a product, a brand, or an event, at a length fixed to the second, for placements that are
named before anything is shot. It is made the way a film is, by the `movie` skill, and this file
says how it opens and where it differs.

## The opening card

What is advertised decides everything else: whether there is a real thing every shot has to
match, or a feeling to build. One line ("An ad. What is it for?"), then:

```json
{
  "title": "What is the ad for?",
  "components": {"type": "pick", "id": "subject", "columns": 3, "options": [
    {"value": "product", "label": "A product", "note": "A thing people can hold or use", "icon": ["000001100000", "000110011000", "011000000110", "100000000001", "111000000111", "100110011001", "100001100001", "100001100001", "100001100001", "011001100110", "000111111000", "000001100000"]},
    {"value": "brand", "label": "A brand or a service", "note": "A name and what it stands for", "icon": ["000000000000", "011111100000", "010000010000", "010110001000", "010110000100", "010000000010", "010000000100", "010000001000", "010000010000", "011111100000", "000000000000", "000000000000"]},
    {"value": "event", "label": "An event or a release", "note": "Something with a date", "icon": ["000100001000", "011111111110", "010100001010", "011111111110", "010000000010", "010110110010", "010110110010", "010000000010", "010110110010", "010110110010", "010000000010", "011111111110"]}]},
  "instant": true,
  "waits": true
}
```

It answers `{"subject": "product"}`, `"brand"`, or `"event"`.

## What to learn, in order

1. **What it is for**, from the opening.
2. **The thing itself**, on one card. For a product, as written here; for a brand or a service,
   leave the photo out; for an event, replace the photo with a field for its date and place.
   A photo they upload becomes the product's library entry, and its picture is the reference
   every shot follows.

   ```json
   {
     "title": "The product",
     "components": {"type": "stack", "children": [
       {"type": "field", "id": "name", "label": "What is it called?", "required": true},
       {"type": "field", "id": "promise", "label": "The one thing the ad should say", "lines": 2},
       {"type": "upload", "id": "photo", "label": "A photo of it", "accept": "image", "section": "Products"},
       {"type": "upload", "id": "logo", "label": "The logo", "accept": "image", "section": "Brand"},
       {"type": "segmented", "id": "length", "label": "Length", "options": [
         {"value": 6, "label": "6 s"}, {"value": 15, "label": "15 s"}, {"value": 30, "label": "30 s"},
         {"value": 60, "label": "60 s"}], "value": 30}]},
     "submit": "Start the ad",
     "waits": true
   }
   ```

   Each upload answers with the entry it made, `{"tag", "name", "kind"}`, or nothing where they
   skipped it. Give the entry its one-sentence description with `library_upsert`, and look at it
   yourself with `library_look` before you write a word about how the product looks.
3. **Where it runs**, as one question: "Online, widescreen", "Social feeds, vertical", "Both: a
   widescreen ad and a vertical cutdown", "Television or cinema (tell me the spec)". Recommend
   both for anything that runs online. The placements set the aspect ratios, and cutdowns are
   planned now, not found later.
4. **The idea.** Pitch three concepts at once, each as one line and the ad's structure for its
   length (the `movie` skill's story.md, "Commercial": the hook, the product as the turn, the
   proof, the brand and the call to action). Ask which to make.
5. **The look**, shown as three style frames with the product in them.
6. **The budget**, with the script: say what the ad costs at its length, and ask for the
   budget with the script's approval.

## Where it differs from a film

| | A film | A commercial |
|---|---|---|
| First in the library | The characters | The product and the brand: sections Products and Brand lead the list. A real product is never redesigned: its uploaded photo is the reference, and `production-design` builds its views from it |
| Length | About right | Exact. The script is written against a clock (second by second: picture, sound, words on screen), and the shot list's cut lengths add up to the length |
| The first seconds | A scene can build | The hook is in the first 3 seconds and the product has appeared by the halfway point ([first-seconds.md](first-seconds.md)) |
| Words on screen | Titles in the edit | Every claim, price, and date is the person's, typed by them and read back letter by letter before the final export. Say only what the brand can stand behind |
| Labels and logos | Generated as concepts | Never generated into a shot: the real label and the real logo are laid over in the edit, so plan pack shots with room for them |
| Voice and music | Whatever the shots carry | A voice-over and a music bed made with `generate_audio`, or supplied; the `sound` subagent makes versions to compare |
| Versions | One | One per placement and per length: generate the hero shots in each aspect ratio, and reframe the rest in the edit |

## The default pipeline

| Stage | Who | First engine |
|---|---|---|
| Concept and script to the second | You; `research` for the market, the competitors, and each placement's current specification | None |
| The product's views, the places, the people | `production-design` from the uploaded photo; `character-design`; at the same time | None |
| Voice-over and music, as versions to compare | `sound` | None |
| Tests: the product in motion, in the light of the ad | `animation` | None |
| Shot list, then shots | You, `review` before the lock, then `animation` | None |
| The edit: the cut at exact length, the real label and logo, the end card, voice and music, each cutdown | You with the `filmcraft` skill, or the FilmCraft agent | FilmCraft, when the takes are selected |

## The person's decisions

The concept, the script with the exact wording of every spoken line and every word on screen,
whether the generated product matches the real one, the voice, the music, the end card, the cut
at its exact length, and each cutdown.

## Cost

An ad is few seconds, so its cost is in retakes: a product has to match, and a take that gets it
wrong is paid for again. Settle the product as stills first, test it in motion at the lowest
resolution, and keep the highest resolution for the shots that show it close. A 30-second ad is
about 40 generated seconds with handles: $19 at the 720p price before retakes (the `movie`
skill's "Cost and time" has the prices).

## What is not possible yet

- **A label, a logo, or a price is not generated correctly.** Image and video models draw
  letters unreliably. The real ones go over the picture in the edit.
- **A take is whole seconds, four at least.** The exact length is made in the edit, not by the
  generation.
- **Broadcast delivery has not been verified** beyond the presets the `filmcraft` skill lists:
  for television or cinema, ask for the station's or the distributor's specification and check
  the export against it with the person.
- **A real person's likeness or voice, and another brand's marks, need permission.** Ask whose
  they are and whether the person may use them before you generate with them.
