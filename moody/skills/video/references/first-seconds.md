<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.

  This file is adapted from the skills of gtavi-claudecode (hook-writer and its
  hook evidence), and incorporates work covered by the following copyright and
  permission notice:

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

# The first seconds

What holds attention at the start of a video that plays in a feed, with the source each rule
rests on, and how to write the hook that goes on screen. Read it before you choose where a clip
starts, write a hook, or plan the opening of an episode or an ad.

The evidence was researched on 2026-11-19 by the project this file is adapted from. TikTok's
figures come from its research on ads, not from ordinary posts, so treat them as direction, not
law. Confidence: H, the primary source was read; M, an abstract or a secondary source; L, not
verified. When a decision hangs on one of these, hand `research` the claim and its source to
check that it still stands.

## Rules, each with its source

1. Put the moment, or a clear promise of it, in the first 3 seconds. No intro, no logo. "Over
   63% of videos with the highest CTR highlight their key message within the first 3 seconds."
   (H, TikTok Auction Ads Creative Tips)
2. Seconds 0 to 6 decide the video. TikTok says 90% of ad recall is captured within 6 seconds.
   (H, TikTok Creative Codes)
3. Open on suspense or surprise, not on setup. Suspense early: 16% more watch time. Surprise:
   1.7 times the view-through. (H, Creative Codes)
4. Pick moments of high arousal: awe, shock, laughter, outrage. Calm or sad moments are shared
   less. (H, Berger and Milkman 2012, Journal of Marketing Research; it studied news articles,
   not video)
5. True 9:16 full screen, 1080 by 1920, with text inside the safe zone. Vertical video has a 25%
   higher 6-second watch-through. (H, Auction Ads Creative Tips)
6. Design for sound on. 90% of TikTok users call sound vital. The common claim that most people
   watch muted has no TikTok source. (H, Creative Codes)
7. A text hook in frame 1, short enough to read at once. 40% of the ads with the highest
   view-through use text overlays. (H, TikTok ads help)
8. Keep the picture changing: cuts, zooms, movement. Cut out dead seconds. (H, Creative Codes,
   code 5; no effect size given)
9. Show a person when you can: a face, close. (H, TikTok guidance; M, Ling et al. 2021, arXiv
   2111.02452)
10. Make it short enough to finish. Completion is a "strong indicator" for the For You feed, and
    21 to 34 seconds is TikTok's stated best range for in-feed ads. (H, TikTok Newsroom 2020 and
    its video advertising guide)
11. Never post a raw re-upload. TikTok: content "is ineligible for the FYF if it includes
    unoriginal or reused material without anything new". Add the title, the captions, a re-cut,
    and a framing every time. (H, TikTok Community Guidelines)
12. Judge hooks by the page's own retention numbers. No benchmark for hook rate with a published
    method exists. (L for every vendor benchmark)

## The opening, in practice

- **Second 0:** the subject of the hook is already visible, and something is moving. If the
  source needs 3 seconds to get there, cut them.
- **Second 0 to 1:** the title is on screen, 6 to 9 words, and says exactly what the viewer will
  see.
- **Second 0 to 2:** a voice. Start on the reaction or the line, not on a breath.
- **The middle:** cut every stretch where nothing changes for 2 seconds or more.
- **The end:** stop on the payoff, at its peak. No outro.

## Writing the hook

Write three options for each video, in sentence case, 3 to 9 words. Ask which with `ask_user`,
your pick as `recommended`.

What works:

- A number that is a promise: "3 things you missed in this trailer"
- A fact that surprises: "This car is hidden in plain sight"
- A situation: "When the guards chase the wrong player"
- A negation: "You can't do this in the first game"
- A question anyone can answer: "Would you survive this?"

What does not:

- Bare labels: "Funny moment", "New clip"
- "Wait for it", "You won't believe this", "Watch till the end"
- False urgency, or capitals on every word

Rules:

1. The video delivers the hook. If the hook says three things, it shows three. A hook the video
   does not pay off costs the page its viewers' trust.
2. Every fact in a hook is true and can be seen in the video. Numbers match what is shown.
3. A hook describes what happens. It never puts words in a real person's mouth: no quote they
   did not say, no opinion they did not give.
4. No swear words in a hook or a title, not even with stars.
5. One emoji at most.
6. The same hook is not used twice in a week on one page.
7. The hook on the video and the first line of the post's caption are different sentences.

## Claims not to repeat

- "An 8-second attention span": no study is behind it. (M)
- "You have exactly 3 seconds": TikTok says 3 in one place and 6 in another. What is supported:
  most exits happen very early. One small study found that about 70% of Shorts views end before
  20% of the video. (H, Vu et al. 2026, arXiv 2603.22663, not peer reviewed)
- Rules about how often to post, and about keywords in captions: no first-party source was
  found.

## Sources

- https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you
- https://ads.tiktok.com/business/library/Creative_Codes_ENG.pdf
- https://ads.tiktok.com/business/library/Auction_Ads_Creative_Tips.pdf
- https://ads.tiktok.com/help/article/creative-best-practices?lang=en
- https://www.tiktok.com/community-guidelines/en/integrity-authenticity
- https://faculty.wharton.upenn.edu/wp-content/uploads/2011/11/Virality.pdf
- https://arxiv.org/abs/2111.02452
- https://arxiv.org/html/2603.22663v1
