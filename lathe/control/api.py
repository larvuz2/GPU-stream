# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Lathe's two front doors over one service: the JSON API the site calls, and the MCP endpoint an agent calls.

Both take a bearer credential and answer for the user it names
(`Sessions.authenticate`): the site sends the Supabase access token of whoever
is signed in, an agent sends an API key that user made. Neither route holds a
rule of its own; `service.py` decides, and a refusal there becomes
`{"error": ...}` with its status here, or the text of a failed tool call.

The API is open to any origin. It answers only to a bearer credential, which a
browser never attaches by itself, so another site's page gains nothing by
calling it, and the site's own origin need not be known in advance.

The MCP endpoint is stateless streamable HTTP at `/mcp`: every call carries its
key, so any container can answer any call and nothing is held between them. Its
tools are the service's verbs, plus the two an agent needs to work in a
session it cannot see: running Python in the session's Blender, and a
screenshot of the result.
"""

from contextlib import asynccontextmanager
from typing import Annotated, Any

import anyio
from fastapi import Depends, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from mcp.server.mcpserver import Context, Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel

from service import Catalog, Config, Refused, Sessions, User

START_WAIT_SECONDS = 150


class NewSession(BaseModel):
    """What `POST /v1/sessions` takes."""

    app: str
    tier: str
    region: str = "auto"


class NewKey(BaseModel):
    """What `POST /v1/api-keys` takes."""

    name: str = ""


class Checkout(BaseModel):
    """What `POST /v1/billing/checkout` takes."""

    pack: str


def bearer(authorization: str | None) -> str:
    """The credential of an `Authorization: Bearer` header.

    Raises:
        Refused: 401 where there is none.
    """
    scheme, _, credential = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        raise Refused(401, "Sign in to use this.")
    return credential.strip()


def mcp_server(sessions: Sessions | None, catalog: Catalog) -> MCPServer:
    """The MCP server: one tool per thing an agent can do for the user its key names.

    Each tool is a coroutine that does its blocking work on a thread, since the
    service talks to Supabase and Modal over blocking clients and a tool that
    blocked the loop would hold every other call behind it.
    """
    brand = catalog.data["brand"]
    server = MCPServer(
        brand,
        instructions=(
            f"{brand} runs creative apps on cloud workstations that stream to the user's browser. "
            "Start a session, give the user its link so they can watch, then work in it: "
            "run_blender_python runs code in the Blender they see, and screenshot shows you the result. "
            "Sessions cost credits while they run and stop themselves after 10 idle minutes; "
            "stop_session ends one sooner. Files under /home/ubuntu/workspace persist between sessions."
        ),
    )

    async def call(context: Context, work: Any, *arguments: Any) -> Any:
        """Run one service call for the user the request's key names, off the event loop.

        A refusal is raised as the error a tool anticipates, which is the kind
        whose message reaches the model; anything else is a crash, and the SDK
        keeps its text on the server.
        """
        if sessions is None:
            raise ToolError("The service is not configured yet.")

        def run() -> Any:
            user = sessions.authenticate(bearer((context.headers or {}).get("authorization")))
            return work(user, *arguments)

        try:
            return await anyio.to_thread.run_sync(run)
        except Refused as refused:
            raise ToolError(refused.message) from None

    @server.tool()
    async def list_apps() -> dict[str, Any]:
        """List the apps that can be started and the machine tiers they run on, with prices in credits per minute."""
        return {
            "apps": [
                {"id": app["id"], "name": app["name"], "version": app["version"], "status": app["status"]}
                for app in catalog.data["apps"]
            ],
            "tiers": [
                {key: tier[key] for key in ("id", "name", "gpu", "vram_gb", "cpu", "memory_gb", "credits_per_minute")}
                for tier in catalog.data["tiers"]
            ],
            "regions": sorted(catalog.regions),
            "credit_usd": catalog.data["credit_usd"],
        }

    @server.tool()
    async def start_session(context: Context, app: str = "blender", tier: str = "cpu", region: str = "auto") -> dict[str, Any]:
        """Start a session and wait until it streams. Returns the session and a link for the user to open and watch.

        A session that had to queue comes back with status "queued" and no link;
        ask again with list_sessions and get_session_link once it runs.
        """
        session = await call(context, lambda user: sessions.start(user, app, tier, region))
        session_id = session["id"]
        with anyio.move_on_after(START_WAIT_SECONDS):
            while session["status"] == "starting":
                await anyio.sleep(2)
                session = await call(context, lambda user: sessions.public(sessions.owned(user, session_id)))
        if session["status"] == "running":
            session["link"] = await call(context, lambda user: sessions.link(user, session_id))
        return session

    @server.tool()
    async def list_sessions(context: Context) -> list[dict[str, Any]]:
        """List the user's sessions: the ones that are open, then the most recent that ended."""
        return await call(context, lambda user: sessions.list(user))

    @server.tool()
    async def get_session_link(context: Context, session_id: str) -> str:
        """Get a fresh link that opens a running session in a browser. Whoever has the link controls the session."""
        return await call(context, lambda user: sessions.link(user, session_id))

    @server.tool()
    async def stop_session(context: Context, session_id: str) -> dict[str, Any]:
        """Stop a session, which stops its billing. The scene open in Blender is kept and reopens in the next session."""
        return await call(context, lambda user: sessions.stop(user, session_id))

    @server.tool()
    async def run_blender_python(context: Context, session_id: str, code: str) -> str:
        """Run Python in the session's live Blender, the one the user is watching, and return what it printed.

        `bpy` is imported. The code runs as if from the 3D viewport, so operators
        such as bpy.ops.mesh.primitive_cube_add() work. Print what you want back.
        An exception comes back as its traceback after the output.
        """

        def run(user: User) -> str:
            status, output = sessions.launcher.blender_python(sessions.running(user, session_id), code)
            return output if status == 0 else f"{output}\n[exit status {status}]"

        return await call(context, run)

    @server.tool()
    async def screenshot(context: Context, session_id: str) -> Image:
        """Take a picture of the session's screen, to see what Blender shows."""
        picture = await call(context, lambda user: sessions.launcher.screenshot(sessions.running(user, session_id)))
        return Image(data=picture, format="jpeg")

    return server


def create_app(sessions: Sessions | None, config: Config, catalog: Catalog) -> FastAPI:
    """The ASGI app: the `/v1` routes, and the MCP endpoint mounted beside them.

    `sessions` is nothing while no Supabase project is configured. The app then
    still answers `/v1/health`, which is how the site tells an unconfigured
    service from one that is down, and refuses the rest with 503.
    """
    agent = mcp_server(sessions, catalog)
    agent_app = agent.streamable_http_app(
        json_response=True,
        stateless_http=True,
        # The endpoint is public and takes a key on every call; the check this turns off guards
        # servers on a developer's own machine against pages that reach them through DNS.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        async with agent.session_manager.run():
            yield

    app = FastAPI(title=catalog.data["brand"], lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["authorization", "content-type"]
    )

    @app.exception_handler(Refused)
    async def refused(_: Request, error: Refused) -> JSONResponse:
        return JSONResponse({"error": error.message}, status_code=error.status)

    def service() -> Sessions:
        if sessions is None:
            raise Refused(503, "The service is not configured yet.")
        return sessions

    def user(authorization: Annotated[str | None, Header()] = None) -> User:
        return service().authenticate(bearer(authorization))

    Who = Annotated[User, Depends(user)]

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        tiers = [tier["id"] for tier in catalog.data["tiers"] if tier["id"] in config.tiers]
        return {"ok": True, "supabase": config.supabase, "billing": config.billing, "tiers": tiers}

    @app.get("/v1/me")
    def me(who: Who) -> dict[str, Any]:
        return service().me(who)

    @app.get("/v1/sessions")
    def list_sessions(who: Who) -> dict[str, Any]:
        return {"sessions": service().list(who)}

    @app.post("/v1/sessions")
    def start_session(body: NewSession, who: Who) -> dict[str, Any]:
        return {"session": service().start(who, body.app, body.tier, body.region)}

    @app.post("/v1/sessions/{session_id}/link")
    def session_link(session_id: str, who: Who) -> dict[str, str]:
        return {"url": service().link(who, session_id)}

    @app.delete("/v1/sessions/{session_id}")
    def stop_session(session_id: str, who: Who) -> dict[str, Any]:
        return {"session": service().stop(who, session_id)}

    @app.get("/v1/api-keys")
    def list_keys(who: Who) -> dict[str, Any]:
        return {"keys": service().keys(who)}

    @app.post("/v1/api-keys")
    def create_key(body: NewKey, who: Who) -> dict[str, Any]:
        key, secret = service().create_key(who, body.name)
        return {"key": key, "secret": secret}

    @app.delete("/v1/api-keys/{key_id}", status_code=204)
    def revoke_key(key_id: str, who: Who) -> Response:
        service().revoke_key(who, key_id)
        return Response(status_code=204)

    @app.post("/v1/billing/checkout")
    def checkout(body: Checkout, who: Who) -> dict[str, str]:
        return {"url": service().checkout(who, body.pack)}

    @app.post("/v1/billing/webhook")
    async def stripe_webhook(request: Request) -> dict[str, bool]:
        payload = await request.body()
        signature = request.headers.get("stripe-signature", "")
        await anyio.to_thread.run_sync(service().stripe_event, payload, signature)
        return {"received": True}

    app.mount("/", agent_app)
    return app
