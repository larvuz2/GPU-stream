# Lathe

Rent a cloud workstation that runs a creative app and streams it to a browser
tab: Blender today, with the other apps of `catalog.json` listed as coming.
Lathe is a service built on this repository's Selkies session for Modal
([`addons/modal`](../addons/modal/README.md)): that integration is the Sandbox a
user works in, and this directory is everything around it.

| Part | What it is | Where it runs |
| --- | --- | --- |
| [`web/`](web) | The site: landing page, sign-up, and the dashboard a user starts sessions from | Netlify, built from this repository (`netlify.toml`) |
| [`control/`](control) | The control plane: the API the site calls, the MCP endpoint an agent calls, and the upkeep that meters and monitors sessions | Modal (`modal deploy`) |
| [`supabase/`](supabase) | Accounts, credits, sessions, and API keys | A Supabase project |
| [`catalog.json`](catalog.json) | The apps, machine tiers, regions, prices, and the name | Read by the site and the control plane alike |

`catalog.json` is the one place to change a price, switch an app from `soon`
to `available`, or rename the service (`brand`).

## How a session happens

1. The user signs in on the site with Supabase Auth, which hands the browser an
   access token.
2. The dashboard asks the control plane for a session, with that token. The
   control plane asks Supabase who the token belongs to, then records the
   session through a database function that checks the user's credits and
   session limit and whether there is room, in one transaction.
3. A job starts a Modal Sandbox for it, with only that user's directory of the
   workspace Volume mounted, and marks the session running when Selkies
   answers. A session beyond the deployment's capacity waits in a queue and
   starts when one ends.
4. The dashboard asks for a link and opens it: the stream, guarded by Modal's
   connect token and the Selkies session token.
5. Once a minute the control plane charges every running session, stops the
   ones whose user ran out of credits, and closes the row of every Sandbox that
   ended itself: unused for ten minutes, stopped, or crashed.

An agent does the same over MCP with an API key the user made in the
dashboard, and has two tools more: running Python in the session's Blender,
and a screenshot of the result.

## Setting it up

The order matters only in that the site needs the control plane's address and
both need the Supabase project.

**Supabase.** Create a project, open its SQL editor, and run
[`supabase/migrations/20261121000000_lathe.sql`](supabase/migrations/20261121000000_lathe.sql).
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
| `LATHE_PIN_REGIONS` | `true` to pin a session to the region its user picked, which Modal bills at a higher rate; unset, Modal places it |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe's, to sell credit packs; point a Stripe webhook for `checkout.session.completed` at `<api>/v1/billing/webhook` |

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
`VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (the project's public key),
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

runs the API and the MCP endpoint against stand-ins for Supabase and Modal:
who a credential names, what each route and tool returns and refuses, and
that one user's sessions do not exist for another.

```bash
cd lathe/supabase && npm install && npm test
```

applies the migration to a Postgres that runs in the test's own process and
calls every function: what is refused and by which name, how a minute is
charged and that a balance never goes below zero, that a payment delivered
twice is credited once, and that the keys a browser holds reach no row and no
function.

## What is not here yet

Payments are wired but have not been run against Stripe. Regions are a
broad choice (`us`, `eu`, `ap`) the user makes; nothing measures latency to
pick one. The GPU tiers are switched off until the Modal account can start
GPUs, and the session has not been run on one.
