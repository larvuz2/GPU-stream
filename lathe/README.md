# Lathe

Rent a cloud workstation that runs a creative app and streams it to a browser
tab: Blender today, with the other apps of `catalog.json` listed as coming.
Lathe is a service built on this repository's Selkies session for Modal
([`addons/modal`](../addons/modal/README.md)): that integration is the Sandbox a
user works in, and this directory is everything around it.

| Part | What it is | Where it runs |
| --- | --- | --- |
| [`web/`](web) | The site: the landing page, sign-up, and the studio: a user's projects, the agent, and the engines it opens | Netlify, built from this repository (`netlify.toml`) |
| [`control/`](control) | The control plane: the API the site calls, the MCP endpoint an agent calls, the Studio's projects and their agent, and the upkeep that meters and monitors sessions | Modal (`modal deploy`) |
| [`supabase/`](supabase) | Accounts, credits, sessions, API keys, projects, their libraries and conversations, and GitHub connections | A Supabase project |
| [`catalog.json`](catalog.json) | The disciplines, apps, machine tiers, regions, prices, and the name | Read by the site and the control plane alike |
| [`skills/`](skills) | What the Studio's agent knows of a craft, one `SKILL.md` per skill | Carried into the control plane's image |

`catalog.json` is the one place to change a price, switch an app from `soon`
to `available`, or rename the service (`brand`).

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

## Lathe Studio

The Studio ([`STUDIO.md`](STUDIO.md), the plan and the API's contract) puts
projects around sessions. A user makes a project of a discipline of the
catalog, and talks with its agent: Claude, with tools to keep the project's
plan and library, generate images and video on fal.ai from the library's
reference images, start engines (sessions opened in the project's folder of
the user's workspace) and drive them, and save the project's documents to the
GitHub repository the user linked. Each message runs one turn of the agent as a
Modal function (`agent_turn`), which writes what it does to the project's event
log as it goes; the page polls the log. The mechanism is in the docblocks of
[`control/agent.py`](control/agent.py) and [`control/service.py`](control/service.py).

## Setting it up

The order matters only in that the site needs the control plane's address and
both need the Supabase project.

**Supabase.** Create a project, open its SQL editor, and run the migrations of
[`supabase/migrations`](supabase/migrations) in the order of their names:
[`20261121000000_lathe.sql`](supabase/migrations/20261121000000_lathe.sql), then
[`20261124000000_studio.sql`](supabase/migrations/20261124000000_studio.sql),
which adds the Studio's tables and the private Storage bucket `library` its
media is kept in. A project that already ran the first runs only the second.
Under Authentication, set the Site URL to the site's address and add
`<site>/app/` to the redirect URLs; turn on the Google and GitHub providers if
the sign-in buttons for them should work.

**Modal.** Edit the Secret named `lathe` (the deploy below needs it to exist)
and set:

| Variable | Value |
| --- | --- |
| `SUPABASE_URL` | The project's URL |
| `SUPABASE_SECRET_KEY` | Its secret key (`sb_secret_...`; a legacy `service_role` key works too), which never leaves this Secret |
| `LATHE_TIERS` | The tier ids users may start, `cpu` unless set; add `t4,l4,a10` once the Modal account can start GPUs |
| `LATHE_CAPACITY` | Sessions that may run at once across all users, `10` unless set; more are queued |
| `LATHE_SITE_URL` | The site's address, which a finished payment returns to |
| `LATHE_PIN_REGIONS` | `false` to let Modal place every session; unset, a session whose user picked a region is pinned to it, which Modal bills at a higher rate, and one left on automatic is not |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe's, to sell credit packs; point a Stripe webhook for `checkout.session.completed` at `<api>/v1/billing/webhook` |
| `ANTHROPIC_API_KEY` | The Anthropic API key the Studio's agent runs on; without it a message to the agent is refused with 503. Its default model, Claude Fable 5.2, needs the key's organization to keep 30-day data retention (not zero data retention) |
| `LATHE_AGENT_MODEL` | The agent's model, `claude-fable-5-2` unless set; another must take adaptive thinking, mid-conversation system messages, and the betas `control/agent.py` names |
| `FAL_KEY` | fal.ai's key, for the agent's image and video generation; without it those tools say generation is not configured |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | The GitHub OAuth App users connect their accounts through (below) |
| `LATHE_SECRET_KEY` | A long random string (`python -c 'import secrets; print(secrets.token_urlsafe(48))'`) that signs GitHub's `state` and encrypts the tokens GitHub grants. Changing it disconnects every GitHub account, which their users connect again |
| `LATHE_TEAM_EMAILS` | The accounts, by email and comma-separated, that may start apps of status `team` (Nuke) |
| `LATHE_NUKE_SEATS` | Nuke sessions that may be open at once across all users, `2` unless set: the seats its license has |
| `LATHE_API_URL` | The API's own address, where GitHub's callback should not be built from the address a request arrives at |

**GitHub.** On GitHub, open Settings, Developer settings, OAuth Apps, and make a
new OAuth App (under the organization that should own it, or a user). Its
homepage URL is the site's address; its authorization callback URL is
`<api>/v1/github/callback`, with the API's address the deploy below prints.
Copy its client ID to `GITHUB_CLIENT_ID`, generate a client secret and copy it
to `GITHUB_CLIENT_SECRET`, and set `LATHE_SECRET_KEY`. Users then connect their
own accounts from a project's Environment panel; the app asks for the `repo`
and `read:packages` scopes, and its token leaves the control plane only for
GitHub and as the user's own credential for pulling Unreal Engine (below).

**Unreal Engine.** The catalog offers it as `byol`: anyone may start it once
their own Epic account is linked, and the control plane checks that link
through their GitHub account. What each user needs:

1. An Epic Games account, which is how Epic licenses the engine to them: Epic's
   license counts every user of the editor as a licensee of their own and lets
   no one hand one copy of it around (`UNREAL.md`).
2. That account linked to their GitHub account: on epicgames.com, Account, then
   Apps and Accounts, connect GitHub, then accept the invitation to the
   EpicGames organization that GitHub emails them, within seven days.
3. GitHub connected in Lathe since Lathe asked for `read:packages`; an account
   connected before then is connected again. `GET /v1/github` says
   `epic_linked: true` once the account sees Epic's `EpicGames/UnrealEngine`
   repository and its images on `ghcr.io/epicgames/unreal-engine`.

What the deployment needs: the launcher's `unreal_image(registry_username,
registry_token, version)` in `addons/modal/sandbox.py`, which pulls Epic's image
with the credential the control plane hands it for that one start (the user's
GitHub login and token) and layers the session, Blender, and the bridge on it;
until it is there, an Unreal start fails saying so. A GPU tier with NVENC: the
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
addons/modal/selkies-modal modal deploy lathe/control/app.py
```

The deploy prints the API's address. A change to the Secret reaches new
containers; deploy again to have it take effect at once.

**Netlify.** Connect the repository; `netlify.toml` holds the build. Set
`VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` (the project's
publishable key, `sb_publishable_...`; a legacy `anon` key works too),
and `VITE_LATHE_API_URL` (the API's address, no trailing slash), then deploy.
Without them the site still builds and shows sign-ups as opening soon.

## Checking it

```bash
addons/modal/selkies-modal modal run lathe/control/app.py
```

starts one session the way the service does, runs Python in its Blender, takes
a screenshot, stops it, and prints what happened; `--gpu T4` tries a GPU. It
needs no Supabase project.

```bash
pip install -r lathe/control/requirements.txt pytest && pytest lathe/control
```

runs the API, the MCP endpoint, and the agent against stand-ins for Supabase,
Modal, Anthropic, fal, and GitHub: who a credential names, what each route and
tool returns and refuses, that one user's sessions and projects do not exist
for another, the agent's loop driven by a scripted model through every tool,
that its conversation only ever grows, that `ask_user` ends a turn and a second
message waits for the first, Nuke's gate and seats, Unreal Engine's gate on an
account linked to Epic and the user's own credential it is pulled with, and
that GitHub's callback refuses a state it did not sign and a page off the site.

```bash
BLENDER=/path/to/blender pytest addons/modal/unreal
```

runs the Blender side of the bridge to Unreal in a real Blender, against a
stand-in for the editor's Remote Control API, and the way back through
Blender's own spool.

```bash
cd lathe/supabase && npm install && npm test
```

applies the migrations to a Postgres that runs in the test's own process and
calls every function: what is refused and by which name, how a minute is
charged and that a balance never goes below zero, that a payment delivered
twice is credited once, that a project runs one agent turn at a time and a dead
turn does not hold it, and that the keys a browser holds reach no row and no
function.

## What is not here yet

Payments are wired but have not been run against Stripe. Regions are a
broad choice (`us`, `eu`, `ap`) the user makes; nothing measures latency to
pick one. The GPU tiers are switched off until the Modal account can start
GPUs, and the session has not been run on one.

The Studio's backend has run only against its tests' stand-ins: not yet against
Anthropic, fal, GitHub, or Supabase Storage. The agent's model and generation
are not billed in credits yet, a conversation that outgrows the model's context
window has no compaction yet, and an engine does not get the project's GitHub
repository as a credential of its session yet. The MCP endpoint has no project
tools.

Unreal Engine cannot start yet: the launcher has no `unreal_image`, since
nobody on the team has a GitHub account linked to Epic to build and test it
with. The Epic link check, the bridge to Blender, and the studio's handling of
the engine are built and tested against stand-ins (`UNREAL.md`).
