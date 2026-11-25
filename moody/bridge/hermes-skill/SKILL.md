---
name: claude-studio-relay
description: Hand every message in the team's studio Discord channel to the team's Claude Code session, which runs Nuke and Blender on cloud GPUs and answers in the channel itself. Use for each message posted in that channel.
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Claude studio relay

The studio channel's work is done by a Claude Code cloud session, not by you.
For every message a teammate posts in the studio channel:

1. Run `hermes-relay` with the author's display name, then the URL of each
   attachment, and the message text on standard input:

   ```bash
   hermes-relay "Maria" "https://cdn.discordapp.com/attachments/..." <<'MSG'
   Render shot_010 frames 1-48 at 2K and send me the mov.
   MSG
   ```

2. Reply in the channel with one short line: `Sent to Claude.` If the command
   prints `"ok": false` or fails, reply with its error instead.

Do not answer the request yourself, change its wording, or leave anything
out: Claude answers in the channel on its own, often minutes later. Relay only
messages from the studio channel and from the teammates Hermes allows there.
