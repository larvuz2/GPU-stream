# Moody

Rent a cloud workstation that runs a creative app and streams it to a browser
tab: Blender today, with the other apps of `catalog.json` listed as coming.
Moody is a service built on this repository's Selkies session for Modal
([`addons/modal`](../addons/modal/README.md)): that integration is the Sandbox a
user works in, and this directory is everything around it.

| Part | What it is | Where it runs |
| --- | --- | --- |
| [`web/`](web) | The site: the landing page, sign-up, and the studio: a user's projects, the agent, and the engines it opens | Netlify, built from this repository (`netlify.toml`) |
| [`control/`](control) | The control plane: the API the site calls, the MCP endpoint an agent calls, the Studio's projects and their agent, and the upkeep that meters and monitors sessions | Modal (`modal deploy`) |
| [`supabase/`](supabase) | Accounts, credits, sessions, API keys, projects, their libraries and conversations, and GitHub connections | A Supabase project |
| [`catalog.json`](catalog.json) | The disciplines, apps, machine tiers, regions, prices, and the name | Read by the site and the control plane alike |
| [`skills/`](skills) | What the Studio's agent knows of a craft, one `SKILL.md` per skill | Carried into the control plane's image |
| [`agents/`](agents) | The subagents the Studio's agent hands jobs to, one definition per file | Carried into the control plane's image |

`catalog.json` is the one place to change a price, switch an app from `soon`
to `available`, or rename the service (`brand`). It is also where a
discipline's kinds are (`formats`, with the card that asks a new project's
kind: `opening`, and each kind's line, icon, and first library sections under
`kinds`), and where a setting of the app's Settings is added (`settings`).

## How a session happens

1. The user signs in on the site with Supabase Auth, which hands the browser an
   access token.
2. The studio asks the control plane for a session, with that token. The
   control plane asks Supabase who the token belongs to, then records the
   session through a database function that checks the user's credits and
   session limit and whether there is room, in one transaction.
3. A job starts a Modal Sandbox for it, with only that user's directory of the
   workspace Volume mounted, and marks the session running when Selkies
   answers. A session beyond the deployment's capacity waits in a queue and
   starts when one ends.
4. The studio asks for a link and shows it on its Screen panel: the stream, guarded by Modal's
   connect token and the Selkies session token.
5. Once a minute the control plane charges every running session, stops the
   ones whose user ran out of credits, and closes the row of every Sandbox that
   ended itself: unused for ten minutes, stopped, or crashed.

An agent does the same over MCP with an API key the user made in the
studio (Connect Claude), and has two tools more: running Python in the session's Blender,
and a screenshot of the result.

## Moody Studio

The Studio ([`STUDIO.md`](STUDIO.md), the plan and the API's contract) puts
projects around sessions. A user makes a project of a discipline of the
catalog, and talks with its agent: Claude, with tools to keep the project's
plan and library, generate images and video on fal.ai from the library's
reference images, start engines (sessions opened in the project's folder of
the user's workspace) and drive them, and save the project's documents to a
branch of its own in the GitHub repository the user linked. Each message runs one turn of the agent as a
Modal function (`agent_turn`), which writes what it does to the project's event
log as it goes; the page polls the log. The agent's loop is the Claude Agent
SDK: it hands jobs to subagents, opens a skill when the work calls for it,
asks the person before a step that costs them, and keeps the conversation as
a session in the database, so a turn resumes on any machine. The mechanism is
in the docblocks of [`control/agent.py`](control/agent.py),
[`control/loop.py`](control/loop.py), and
[`control/service.py`](control/service.py).

## Setting it up

**What to configure.** Each part below says how; this is the whole list.

1. A Supabase project with the seven migrations run, its Site URL and
   redirect URL, and the ways to sign in turned on.
2. The Modal Secret `moody`: at least `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
   `MOODY_SITE_URL`, and `MOODY_SECRET_KEY`, then whichever integrations are
   wanted (the table). The agent needs `ANTHROPIC_API_KEY` and nothing else:
   every other setting of its loop has a default.
3. A GitHub App, for "Connect GitHub": `GITHUB_APP_CLIENT_ID`,
   `GITHUB_APP_CLIENT_SECRET`, and `GITHUB_APP_SLUG`.
4. A GitHub OAuth App, for "Connect Epic": `EPIC_GITHUB_CLIENT_ID` and
   `EPIC_GITHUB_CLIENT_SECRET`.
5. The deploy, whose address is both apps' callback (`<api>/v1/github/callback`,
   `<api>/v1/epic/callback`) and `MOODY_API_URL`.
6. Netlify: `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, and
   `VITE_MOODY_API_URL`.

The order matters only in that the site needs the control plane's address and
both need the Supabase project.

**Supabase.** Create a project, open its SQL editor, and run the migrations of
[`supabase/migrations`](supabase/migrations) in the order of their names:
[`20261121000000_moody.sql`](supabase/migrations/20261121000000_moody.sql), then
[`20261124000000_studio.sql`](supabase/migrations/20261124000000_studio.sql),
which adds the Studio's tables and the private Storage bucket `library` its
media is kept in, then
[`20261125000000_github_app.sql`](supabase/migrations/20261125000000_github_app.sql),
which keeps the GitHub App's expiring tokens and adds the Epic connection, then
[`20261126000000_agent_loop.sql`](supabase/migrations/20261126000000_agent_loop.sql),
which adds what the agent's loop keeps: a project's session and its transcript
(`agent_transcripts`), and what the person no longer wants to be asked about
(`projects.permissions`), then
[`20261127000000_limits.sql`](supabase/migrations/20261127000000_limits.sql),
which lets an account set what one turn of the agent may spend and how many
steps it may take (`profiles.turn_budget_usd`, `profiles.turn_limit`), then
[`20261128000000_settings.sql`](supabase/migrations/20261128000000_settings.sql),
which keeps a person's name and the settings they changed (`profiles.name`,
`profiles.settings`), then
[`20261129000000_invites.sql`](supabase/migrations/20261129000000_invites.sql),
which adds the list of who is invited (`invites`) for a deployment open by
invitation (below). A
project that already ran the earlier ones runs
only those it has not. `github_app` deletes the GitHub connections an OAuth
App made before, whose users connect again. `agent_loop` drops
`agent_messages`, the conversation the agent replayed to the model before it
kept a session: what was said in a project stays in its event log, which the
page reads, and the first turn after the migration starts the project's
session with a recap of it. Run it with no turn running and deploy the control
plane with it, since each side needs the other. Under Authentication, set the
Site URL to the site's address and add
`<site>/app/` to the redirect URLs. Under its sign-in providers, turn on the
ways people may sign in: Google, GitHub, and email (a password or a magic
link). The sign-in dialog reads which are on from the project and offers those
and no other, so a project with Google alone shows one button. Leave "Confirm
email" on: an account's address is who it is to the team's apps and to the
invite list, which holds only while a sign-up has to prove its address.

**Opening by invitation.** With `MOODY_INVITE_ONLY` set (below), the control
plane serves an account only while its address is a row of `invites`, and
answers everything else with 403; the site shows that person a page that says
so in place of the studio. Invite someone by adding the address they sign in
with, in lowercase, in the table editor or in SQL:

```sql
insert into invites (email, credits, note) values ('mara@example.com', 300, 'first testers');
```

`credits` is what the account starts with where that is not the catalog's
`signup_credits`; leave it null for those. It is read once, when the person
first signs in. Deleting the row keeps the person out from their next sign-in,
within a minute for a page already open and at once for an API key, and leaves
their projects as they were. Nothing of the list is in this repository or in
the Secret, so inviting someone needs no deploy.

**Modal.** Edit the Secret named `moody` (the deploy below needs it to exist)
and set:

| Variable | Value |
| --- | --- |
| `SUPABASE_URL` | The project's URL |
| `SUPABASE_SECRET_KEY` | Its secret key (`sb_secret_...`; a legacy `service_role` key works too), which never leaves this Secret |
| `MOODY_TIERS` | The tier ids users may start, `cpu` unless set; add `t4,l4,a10` once the Modal account can start GPUs |
| `MOODY_CAPACITY` | Sessions that may run at once across all users, `10` unless set; more are queued |
| `MOODY_SITE_URL` | The site's address, which a finished payment returns to |
| `MOODY_PIN_REGIONS` | `false` to let Modal place every session; unset, a session whose user picked a region is pinned to it, which Modal bills at a higher rate, and one left on automatic is not |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe's, to sell credit packs; point a Stripe webhook for `checkout.session.completed` at `<api>/v1/billing/webhook` |
| `ANTHROPIC_API_KEY` | The Anthropic API key the Studio's agent runs on; without it a message to the agent is refused with 503. Its default model, Claude Fable 5.2, needs the key's organization to keep 30-day data retention (not zero data retention) |
| `MOODY_AGENT_MODEL` | The agent's model, `claude-fable-5-2` unless set; another must be one the Claude Agent SDK's program knows, since it prices a turn's budget from its own table |
| `MOODY_AGENT_MODEL_BALANCED`, `MOODY_AGENT_MODEL_LIGHT` | The models a subagent runs on when its definition says `model: balanced` or `light`, `claude-sonnet-5-5` and `claude-haiku-5-5` unless set; `inherit` is the agent's own |
| `MOODY_AGENT_FALLBACK_MODEL` | A model the loop asks instead where the agent's own is overloaded or declines a request; none unless set |
| `MOODY_AGENT_EFFORT` | How hard the model works on each step: `low`, `medium`, `high`, `xhigh`, or `max`; `high` unless set |
| `MOODY_AGENT_THINKING` | `false` to run the agent without thinking; unset, it thinks as much as a step needs and the conversation shows a summary |
| `MOODY_TURN_BUDGET_USD` | What one turn may spend on the model, in dollars as the loop prices it, for an account that has not set its own in the app; `15` unless set. Generation and engines are not in it |
| `MOODY_TURN_LIMIT` | The most steps one turn may take, for an account that has not set its own; `200` unless set |
| `MOODY_TURN_BUDGET_MAX_USD`, `MOODY_TURN_LIMIT_MAX` | The most an account may set either limit to, `100` dollars and `1000` steps unless set. A default above its ceiling runs at the ceiling. All four are positive: a deployment that wants turns to run further raises the ceilings |
| `MOODY_APPROVAL_SECONDS` | How long a step waits for the person's approval before the agent is told to end its turn and ask, `600` unless set. A waiting turn holds its worker |
| `ANTHROPIC_BASE_URL` | Where the loop reaches the Messages API where not Anthropic's own address: a proxy that holds the key, in which case `ANTHROPIC_API_KEY` is whatever the proxy takes |
| `MOODY_LOOP_ENV` | Variables of this Secret, comma-separated, the loop's program also gets (a proxy's address, a certificate bundle). It gets `ANTHROPIC_API_KEY` and nothing else of the Secret unless named here |
| `MOODY_LOOP_ROOT` | Under which a turn's working directory is made, `/tmp/moody-loop` unless set. The loop keys a project's session by that path, so changing it starts every project's conversation anew |
| `MOODY_LOOP_CLI` | The `claude` program the loop runs, where not the one the SDK's package carries |
| `FAL_KEY` | fal.ai's key, for the agent's image, video, and sound generation; without it those tools say generation is not configured |
| `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET` | The client ID and a client secret of the GitHub App users connect their accounts through (below) |
| `GITHUB_APP_SLUG` | That app's name in its address, `https://github.com/apps/<slug>`, where "Don't see your repository?" sends a user to install it |
| `EPIC_GITHUB_CLIENT_ID`, `EPIC_GITHUB_CLIENT_SECRET` | The client ID and a client secret of the OAuth App that reads packages, through which a user's own copy of Unreal Engine is pulled (below) |
| `MOODY_SECRET_KEY` | A long random string (`python -c 'import secrets; print(secrets.token_urlsafe(48))'`) that signs GitHub's `state` and encrypts the tokens GitHub grants. Changing it disconnects every GitHub and Epic connection, which their users connect again |
| `MOODY_INVITE_ONLY` | `true` to serve only the accounts the database's `invites` names (above); unset, anyone who signs in gets an account |
| `MOODY_TEAM_EMAILS` | The accounts, by email and comma-separated, that may start apps of status `team` (Nuke) |
| `MOODY_NUKE_SEATS` | Nuke sessions that may be open at once across all users, `2` unless set: the seats its license has |
| `MOODY_API_URL` | The API's own address, where GitHub's callbacks should not be built from the address a request arrives at |
| `MOODY_PREVIEW_MAX_MB` | The largest copy of a file, in megabytes, the agent's `preview` puts in a conversation, `50` unless set; a larger one is refused |
| `MOODY_PREVIEW_ORIGINAL_MAX_MB` | The size over which a preview is a lighter copy the engine encodes rather than the file itself, `8` unless set |
| `MOODY_PREVIEW_MAX_FILES` | The files one preview may show, `12` unless set |
| `MOODY_TRANSFER_MAX_MB` | The largest file or folder, in megabytes, `engine_send` carries between two running engines, `4096` unless set |

**GitHub.** "Connect GitHub" is a GitHub App's user authorization, and the
repositories a user can pick are those the app is installed on that they can
reach. On GitHub, open Settings (of the organization that should own the app,
or of a user), Developer settings, GitHub Apps, New GitHub App, and fill in:

| Field | Value |
| --- | --- |
| GitHub App name | The name users see when they authorize and install it, such as `Moody Studio` (34 characters at most, unique on GitHub). Its address, `https://github.com/apps/<slug>`, names the slug |
| Homepage URL | The site's address |
| Callback URL | `<api>/v1/github/callback`, with the API's address the deploy below prints |
| Expire user authorization tokens | On (the default): a token lasts eight hours and is renewed with a refresh token that lasts six months |
| Request user authorization (OAuth) during installation | On: whoever installs it is connected too. GitHub then sends them to the callback URL and lets no Setup URL be set |
| Enable Device Flow | Off |
| Setup URL, Redirect on update | Empty, off |
| Webhook, Active | Off: Moody reads installations when a user lists them |
| Repository permissions | Contents: Read and write. Metadata: Read-only (GitHub selects it). Everything else: No access |
| Organization and account permissions | No access |
| Where can this GitHub App be installed? | Any account, so every user and organization can install it on their own repositories |

Create it, then copy its Client ID to `GITHUB_APP_CLIENT_ID`, generate a client
secret and copy it to `GITHUB_APP_CLIENT_SECRET`, put the slug in
`GITHUB_APP_SLUG`, and set `MOODY_SECRET_KEY`. No private key is needed: the
control plane only acts as users, with their own tokens. A user connects from a
project's Environment panel; a repository the list lacks is one the app is not
installed on, and "Don't see your repository?" opens the app's installation
page, where the user installs it on their account or an organization, picking
its repositories. A member of an organization who may not install apps there
sends a request from the same page, which emails the organization's owners; an
owner approves once, and the repositories appear for everyone in it who can
reach them. The app makes no repositories (it asks for no Administration
permission): the studio sends a user to GitHub's own page for a new one.

The agent saves only to a branch of its own (`moody/...`), and an Unreal engine
of a project linked to a repository clones it as it starts: the control plane
refreshes the user's token where it has less than seven hours left and hands
it, with the repository, its branch, and the user's name and noreply address,
to that engine's Sandbox in an ephemeral Secret of its start alone. The token
is in no row, event, or log.

**Epic.** Pulling a user's own copy of Unreal Engine from
`ghcr.io/epicgames/unreal-engine` takes a token that reads packages across
GitHub, which a GitHub App's token cannot (the app is not installed on
EpicGames), so "Connect Epic" is a small OAuth App of its own that asks for
`read:packages` and nothing else. Open Settings, Developer settings, OAuth Apps,
New OAuth App, and fill in:

| Field | Value |
| --- | --- |
| Application name | The name users see when they authorize it, such as `Moody Studio: Unreal Engine` |
| Homepage URL | The site's address |
| Authorization callback URL | `<api>/v1/epic/callback` |
| Enable Device Flow | Off |

Register it, copy its Client ID to `EPIC_GITHUB_CLIENT_ID`, and generate a
client secret for `EPIC_GITHUB_CLIENT_SECRET`. The scope is asked for at each
authorization; nothing on the app sets it. An OAuth App an earlier deployment
used for `GITHUB_CLIENT_ID` asked for `repo` too: make a new one for Epic, and
delete the old one (its page, Advanced, Delete application) with any
`moody-ghcr-<user id>` Secret it left in Modal.

**Unreal Engine.** The catalog offers it as `byol`: anyone may start it, and
the editor comes once their own Epic account is linked, which the control plane
checks with Epic's registry through their Epic connection. What each user
needs:

1. An Epic Games account, which is how Epic licenses the engine to them: Epic's
   license counts every user of the editor as a licensee of their own and lets
   no one hand one copy of it around (`UNREAL.md`).
2. That account linked to their GitHub account: on epicgames.com, Account, then
   Apps and Accounts, connect GitHub, then accept the invitation to the
   EpicGames organization that GitHub emails them, within seven days.
3. That GitHub account connected in Moody with "Connect Epic", under Unreal
   Engine in the Environment panel. `GET /v1/epic` says `linked: true` once
   `ghcr.io`'s token service grants the account a pull of
   `epicgames/unreal-engine`, which it does only for an account Epic linked.

What the deployment needs: the launcher's `unreal_image(registry_secret,
version)` in `addons/modal/sandbox.py`, which pulls Epic's image with the
user's own named Modal Secret and layers the session, Blender, and the bridge on
it; until it is there, an Unreal start fails saying so. The control plane keeps
that Secret, `moody-ghcr-<user id>` (`REGISTRY_USERNAME` and
`REGISTRY_PASSWORD`, the login and token of the user's Epic connection),
writing it before each Unreal start on a linked account and when the user
connects Epic again, and deleting it when they disconnect Epic; a named Secret
keeps the layer that pulls the engine cached
per user, where one made for each start would pull it again every time. A GPU tier with NVENC: the
editor renders off screen on the GPU and streams itself. Inside the image, the
Unreal project the session opens needs the Python Editor Script Plugin and the
Remote Control API plugin, with `addons/modal/unreal/DefaultRemoteControl.ini`
in its `Config` folder, so Blender's Send to Unreal can ask the editor to import
(`addons/modal/unreal/send_to_unreal.py`). Epic should confirm this way of
offering the editor before it is offered to the public (`UNREAL.md`).

Then build the session image and deploy:

```bash
addons/modal/selkies-modal build
```

```bash
addons/modal/selkies-modal modal deploy moody/control/app.py
```

The deploy prints the API's address. A change to the Secret reaches new
containers; deploy again to have it take effect at once.

The control plane's image installs ffmpeg beside its Python packages: a turn's
worker makes with it the small pictures the agent looks at what it generated
or at the library by (`control/looking.py`). A worker without ffmpeg still
runs; a look then says no picture could be made.

**Netlify.** Connect the repository; `netlify.toml` holds the build. Set
`VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` (the project's
publishable key, `sb_publishable_...`; a legacy `anon` key works too),
and `VITE_MOODY_API_URL` (the API's address, no trailing slash), then deploy.
Without them the site still builds and shows sign-ups as opening soon.

## Checking it

```bash
addons/modal/selkies-modal modal run moody/control/app.py
```

starts one session the way the service does, runs Python in its Blender, takes
a screenshot, stops it, and prints what happened; `--gpu T4` tries a GPU. It
needs no Supabase project.

```bash
pip install -r moody/control/requirements.txt pytest && pytest moody/control
```

runs the API, the MCP endpoint, and the agent against stand-ins for Supabase,
Modal, Anthropic, fal, and GitHub: who a credential names, what each route and
tool returns and refuses, that one user's sessions, projects, and connections do not exist
for another, the agent driven by a scripted model through every tool, its
subagents, approvals, and skills, that a project made without its kind opens
on the card that asks it and the message that locks the card sets it, the
sound the agent generates by kind, an account's name and settings, that
`ask_user` ends a turn and a second
message waits for the first, that a question may name the option the agent
recommends, that a turn runs on its person's own limits and says which one
stopped it, the pictures the agent looks at its generations
and the library by (made by a real ffmpeg, so those tests skip where there is
none) and that the ffmpeg which makes them gets nothing of the worker's
environment, Nuke's gate and seats, Unreal Engine's gate on an
Epic connection the registry lets pull it and the user's own credential it is
pulled with, the GitHub App's token refreshed before it expires and its
repositories read from its installations, the clone an Unreal engine of a
linked project starts with and that no row keeps its token, and that GitHub's
callbacks refuse a state they did not sign and a page off the site.
`test_api.py` stands in for the Claude Agent SDK at its boundary
(`scripted_loop.py`) and runs in seconds. `test_loop.py` runs the SDK as it
ships, with the `claude` program its package carries as a child process and
only the Messages API scripted (`scripted_api.py`): that Moody's tools run and
the program's file and shell tools are not offered, what the program's process
has in its environment, a subagent's steps, a session resumed in a fresh
process from the database's rows, an approval answered and one that runs out,
a stop while the model answers, a skill opened on demand. Its tests skip, with
the reason, where the program cannot start.

```bash
modal run moody/control/trial.py::scripted
```

runs those turns on Modal in the control plane's image, as the throwaway app
`moody-trial-loop` with no Secret: the scripted model, two workers, the answer
to a question resuming the session on the second, then both suites inside the
image. It prints how long a worker took to start and each turn to run. `::real`
in place of `::scripted` runs the same checks with a real model and the Secret
`moody`'s `ANTHROPIC_API_KEY`, and spends a few model calls.

```bash
BLENDER=/path/to/blender pytest addons/modal/unreal
```

runs the Blender side of the bridge to Unreal in a real Blender, against a
stand-in for the editor's Remote Control API, and the way back through
Blender's own spool.

```bash
cd moody/supabase && npm install && npm test
```

applies the migrations to a Postgres that runs in the test's own process and
calls every function: what is refused and by which name, how a minute is
charged and that a balance never goes below zero, that a payment delivered
twice is credited once, that a project runs one agent turn at a time and a dead
turn does not hold it, that the agent's transcript keeps its order and a batch
sent twice is kept once, that an approval is answered once, that an account's
limits of a turn are unset until it sets them, and that the keys a browser
holds reach no row and no function.

## What is not here yet

Payments are wired but have not been run against Stripe. Regions are a
broad choice (`us`, `eu`, `ap`) the user makes; nothing measures latency to
pick one. The GPU tiers are switched off until the Modal account can start
GPUs, and the session has not been run on one.

The Studio's backend has run only against its tests' stand-ins: not yet against
Anthropic, GitHub, or Supabase Storage, and against fal only for sound, where
one instrumental, one sound effect, and one spoken line were generated
through the agent's tool. The agent's loop has run as it
ships, on Modal too, with the model scripted; no turn has been answered by a
real model, so how the model uses its subagents, skills, and approvals, what a
turn costs, and how the loop summarizes a conversation that outgrows the
model's context window are unmeasured (`trial.py::real` is the first step).
The transcript's store has run against the tests' database and the SDK's
conformance suite, not against Supabase, and neither has the read of a library
file the agent looks at (`Store.download`) or the write of an account's limits
(`PATCH /v1/me`). The agent's model and generation are
not billed in credits yet, and only an Unreal engine clones the project's
repository as it starts. The MCP endpoint has no project tools.

The GitHub App and the Epic connection have run only against stand-ins too.
Whether the registry grants an OAuth App's token a pull of Epic's image is
unchecked (GitHub's container registry documentation names only personal
access tokens (classic)), and an authorization GitHub starts during an
installation may come back without Moody's state, which the callback answers by
sending the user to the studio with nothing exchanged (`UNREAL.md`, What is
open).

Unreal Engine's editor cannot be pulled yet: nobody on the team has a GitHub
account linked to Epic to build and test `unreal_image` with. The Epic link check, the bridge to Blender, and the studio's handling of
the engine are built and tested against stand-ins (`UNREAL.md`).
