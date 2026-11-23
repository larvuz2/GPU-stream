# Discord to the team's Claude Code session

The team talks to one Claude Code cloud session from a Discord channel, through
Hermes, and that session does the work: it starts Nuke or Blender on a Modal GPU
with `addons/modal/selkies-modal`, runs the team's scripts there, and posts what
comes out back in the channel. It is the same session every time, so it keeps
the whole conversation; files live in the team's workspace on the Modal Volume,
so they outlast any one machine.

```
Discord channel ──> Hermes ──hermes-relay──> claude -p --cloud <session>   (queues the message)
       ^                                              │
       └──────────── discord-post (as Hermes's bot) <─┘   Claude Code session -> Modal GPU
```

`claude -p --cloud` only queues a message into the session; it never brings the
reply back. So the two directions are separate: Hermes hands each message over
with `hermes-relay`, and the session answers with `discord-post`, posting as
Hermes's bot so the conversation reads as one. Each relayed message's first
line names its author and the command and channel to answer with, which is all
the session needs to know, however much of the conversation has since been
summarized.

## Setting it up

**On the machine Hermes runs on:**

1. Install Claude Code and log in as the account that owns the session:
   `claude auth login`. On a Team or Enterprise plan, an owner turns on the
   `allow_remote_sessions` policy in the Claude Code admin settings.
2. Put `hermes-relay` on Hermes's `PATH`, and set `LATHE_CLAUDE_SESSION` (the
   session's `session_...` ID or claude.ai/code URL) and
   `LATHE_DISCORD_CHANNEL_ID` (the channel's ID: Discord's developer mode, then
   right-click the channel, Copy Channel ID) in Hermes's environment.
3. Add `hermes-skill/SKILL.md` to Hermes's skills, and let Hermes answer in the
   channel only for the teammates it should.

**In the cloud environment the session runs in:**

4. Hermes's Discord bot token as a network secret for `discord.com`, with the
   `Bot` prefix. The proxy adds it to the session's requests to Discord, so the
   token is never on the session's machine.
5. `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` as environment variables (a token
   made at modal.com/settings/tokens). A session logs in to Modal through a
   file on its machine, which a machine replaced after a long idle does not
   have; these are what a fresh one starts with.

## What to expect

- **Ordered, one at a time.** Messages queue in the order they arrive; one sent
  while Claude works on a render waits for it.
- **Attachments.** Discord's links to them expire within about a day, so the
  session copies them into the workspace when it receives them.
- **Big results.** Discord takes 10 MB a file on a server without boosts;
  `discord-post` refuses anything larger, and the session shares a link to it
  in the workspace instead.
- **Usage.** Every message counts against the Claude plan of the account that
  owns the session.
- **Trust.** A relayed message reaches the session as that account's own, and
  the session acts on the account's Modal and GitHub access. Keep the channel
  private to the team, and Hermes's allow list to its members.
- **A long-lived session.** As its conversation grows, the oldest parts are
  summarized. Decisions that have to last belong in the repository or the
  workspace, not only in the chat.
