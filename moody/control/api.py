# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Moody's two front doors over one service: the JSON API the site calls, and the MCP endpoint an agent calls.

Both take a bearer credential and answer for the user it names
(`Sessions.authenticate`): the site sends the Supabase access token of whoever
is signed in, an agent sends an API key that user made. Neither route holds a
rule of its own; `service.py` decides, and a refusal there becomes
`{"detail": ..., "error": ...}` (the same text under both names: `detail` is
the Studio contract's, `error` what the first pages read) with its status
here, or the text of a failed tool call.

The Studio's routes (`moody/STUDIO.md`, its contract) are projects, their
library, their engines, their event log and agent (a message, which may lock
in an interactive card; the answer to an approval the agent waits on; and what
the project's agent can use: its connectors, subagents, and skills), the
GitHub connection, and the Epic connection. Two routes take no credential: GitHub's callbacks, one for
the GitHub App and one for the Epic OAuth App, which a browser reaches by
redirect and whose signed `state` names the user instead
(`Sessions.github_callback`, `Sessions.epic_callback`).

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
from fastapi import Depends, FastAPI, File, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from mcp.server.mcpserver import Context, Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel

from definitions import AgentSpec, Skill, agents_directory, agents_for, operators, read_agents, read_skills, skills_directory, skills_for
from service import Catalog, Config, Refused, Sessions, User

START_WAIT_SECONDS = 150


class NewSession(BaseModel):
    """What `POST /v1/sessions` takes."""

    app: str
    tier: str
    region: str = "auto"


class LinkChoice(BaseModel):
    """What `POST /v1/sessions/{sid}/link` takes, all of it optional: the picture to open, its desktop by default."""

    stream: str | None = None


class NewKey(BaseModel):
    """What `POST /v1/api-keys` takes."""

    name: str = ""


class Checkout(BaseModel):
    """What `POST /v1/billing/checkout` takes."""

    pack: str


class NewProject(BaseModel):
    """What `POST /v1/projects` takes; with `github_repo`, the project starts linked to it."""

    name: str = ""
    discipline: str
    format: str = ""
    github_repo: str | None = None
    github_branch: str | None = None


class ProjectChanges(BaseModel):
    """What `PATCH /v1/projects/{pid}` takes; a field left out is left as it is."""

    name: str | None = None
    pinned: bool | None = None
    library_sections: list[str] | None = None
    permissions: dict[str, Any] | None = None


class NewEngine(BaseModel):
    """What `POST /v1/projects/{pid}/engines` takes."""

    app: str
    tier: str = "cpu"
    region: str = "auto"


class Account(BaseModel):
    """What `PATCH /v1/me` takes: the limits of one turn, the name, and the settings to change.

    What is left out is left as it is, which `model_fields_set` tells from
    what is sent as `null`: a limit or a setting put back on its default, a
    name cleared. What each may be is the service's to say
    (`Sessions.change_me`), so that a value it refuses is refused in its
    words.
    """

    turn_budget_usd: Any = None
    turn_limit: Any = None
    name: Any = None
    settings: Any = None


class Message(BaseModel):
    """What `POST /v1/projects/{pid}/messages` takes: the person's words, and the card they lock in where they do."""

    text: str = ""
    ui: dict[str, Any] | None = None


class Approval(BaseModel):
    """What `POST /v1/projects/{pid}/approvals/{aid}` takes: `once`, `always`, or `deny`."""

    decision: str


class NewAsset(BaseModel):
    """What `POST /v1/projects/{pid}/library` takes."""

    section: str
    name: str
    tag: str | None = None
    description: str = ""
    metadata: dict[str, Any] = {}


class AssetChanges(BaseModel):
    """What `PATCH /v1/projects/{pid}/library/{aid}` takes; only the fields sent change, and a blank tag clears it."""

    section: str | None = None
    name: str | None = None
    tag: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None


class Connect(BaseModel):
    """What the connect and install routes take: the page of the site to come back to."""

    return_to: str


class LinkRepo(BaseModel):
    """What `POST /v1/projects/{pid}/github` takes: a repository, and the branch an engine clones where not its default."""

    repo: str | None = None
    branch: str | None = None


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


def create_app(
    sessions: Sessions | None,
    config: Config,
    catalog: Catalog,
    skills: list[Skill] | None = None,
    agents: list[AgentSpec] | None = None,
    derived: list[AgentSpec] | None = None,
) -> FastAPI:
    """The ASGI app: the `/v1` routes, and the MCP endpoint mounted beside them.

    `sessions` is nothing while no Supabase project is configured. The app then
    still answers `/v1/health`, which is how the site tells an unconfigured
    service from one that is down, and refuses the rest with 503. The skills
    and subagents a project's environment lists are read from the image's
    definitions (`definitions.py`) unless given.
    """
    if skills is None:
        skills = read_skills(skills_directory())
    if agents is None:
        agents = read_agents(agents_directory())
    if derived is None:
        derived = operators(agents_directory(), catalog, skills)
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
        return JSONResponse({"detail": error.message, "error": error.message}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def malformed(_: Request, error: RequestValidationError) -> JSONResponse:
        problem = error.errors()[0] if error.errors() else {}
        where = ".".join(str(part) for part in problem.get("loc", ())[1:]) or "the request"
        message = f"{where}: {problem.get('msg', 'not valid')}"
        return JSONResponse({"detail": message, "error": message}, status_code=422)

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
        return {
            "ok": True,
            "agent": config.agent and config.supabase,
            "github": config.github and config.supabase,
            "epic": config.epic and config.supabase,
            "generation": config.generation,
            "supabase": config.supabase,
            "billing": config.billing,
            "tiers": tiers,
        }

    @app.get("/v1/me")
    def me(who: Who) -> dict[str, Any]:
        return service().me(who)

    @app.patch("/v1/me")
    def change_me(body: Account, who: Who) -> dict[str, Any]:
        return service().change_me(who, {name: getattr(body, name) for name in body.model_fields_set})

    @app.get("/v1/sessions")
    def list_sessions(who: Who) -> dict[str, Any]:
        return {"sessions": service().list(who)}

    @app.post("/v1/sessions")
    def start_session(body: NewSession, who: Who) -> dict[str, Any]:
        return {"session": service().start(who, body.app, body.tier, body.region)}

    @app.post("/v1/sessions/{session_id}/link")
    def session_link(session_id: str, who: Who, body: LinkChoice | None = None) -> dict[str, str]:
        return {"url": service().link(who, session_id, body.stream if body else None)}

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

    # Projects

    @app.get("/v1/projects")
    def list_projects(who: Who) -> dict[str, Any]:
        return {"projects": service().projects(who)}

    @app.post("/v1/projects")
    def create_project(body: NewProject, who: Who) -> dict[str, Any]:
        project = service().create_project(
            who, body.name, body.discipline, body.format, body.github_repo, body.github_branch
        )
        return {"project": project}

    @app.get("/v1/projects/{project_id}")
    def get_project(project_id: str, who: Who) -> dict[str, Any]:
        return {"project": service().public_project(service().owned_project(who, project_id))}

    @app.patch("/v1/projects/{project_id}")
    def update_project(project_id: str, body: ProjectChanges, who: Who) -> dict[str, Any]:
        changed = service().update_project(
            who, project_id, body.name, body.pinned, body.library_sections, body.permissions
        )
        return {"project": changed}

    @app.delete("/v1/projects/{project_id}", status_code=204)
    def delete_project(project_id: str, who: Who) -> Response:
        service().delete_project(who, project_id)
        return Response(status_code=204)

    @app.get("/v1/projects/{project_id}/engines")
    def list_engines(project_id: str, who: Who) -> dict[str, Any]:
        return {"engines": service().engines(who, project_id, links=True)}

    @app.post("/v1/projects/{project_id}/engines")
    def start_engine(project_id: str, body: NewEngine, who: Who) -> dict[str, Any]:
        return {"engine": service().start_engine(who, project_id, body.app, body.tier, body.region)}

    @app.get("/v1/projects/{project_id}/engines/{session_id}/unreal-projects")
    def unreal_projects(project_id: str, session_id: str, who: Who) -> dict[str, Any]:
        return {"projects": service().unreal_projects(who, project_id, session_id)}

    # The agent

    @app.get("/v1/projects/{project_id}/events")
    def project_events(project_id: str, who: Who, after: int = 0) -> dict[str, Any]:
        return service().events(who, project_id, after)

    @app.post("/v1/projects/{project_id}/messages", status_code=202)
    def send_message(project_id: str, body: Message, who: Who) -> dict[str, str]:
        return {"turn_id": service().send_message(who, project_id, body.text, body.ui)}

    @app.post("/v1/projects/{project_id}/approvals/{approval_id}")
    def answer_approval(project_id: str, approval_id: str, body: Approval, who: Who) -> dict[str, bool]:
        return {"recorded": service().answer_approval(who, project_id, approval_id, body.decision)}

    @app.get("/v1/projects/{project_id}/environment")
    def environment(project_id: str, who: Who) -> dict[str, Any]:
        project = service().owned_project(who, project_id)
        offered = skills_for(skills, catalog, project["discipline"])
        return {
            "connectors": service().connectors(who, project_id),
            "agents": [
                {"name": one.name, "title": one.title, "description": one.description}
                for one in agents_for(agents, derived, offered, catalog, project["discipline"])
            ],
            "skills": [{"name": skill.name, "description": skill.description} for skill in offered],
        }

    @app.post("/v1/projects/{project_id}/stop")
    def stop_turn(project_id: str, who: Who) -> dict[str, bool]:
        return {"stopped": service().stop_turn(who, project_id)}

    # The library

    @app.get("/v1/projects/{project_id}/library")
    def library(project_id: str, who: Who) -> dict[str, Any]:
        return service().library(who, project_id)

    @app.post("/v1/projects/{project_id}/library")
    def create_asset(project_id: str, body: NewAsset, who: Who) -> dict[str, Any]:
        asset = service().create_asset(
            who, project_id, body.section, body.name, body.tag, body.description, body.metadata
        )
        return {"asset": asset}

    @app.post("/v1/projects/{project_id}/library/{asset_id}/media")
    def add_media(project_id: str, asset_id: str, file: Annotated[UploadFile, File()], who: Who) -> dict[str, Any]:
        data = file.file.read()
        content_type = file.content_type or "application/octet-stream"
        asset = service().add_media(who, project_id, asset_id, file.filename or "file", content_type, data)
        return {"asset": asset}

    @app.patch("/v1/projects/{project_id}/library/{asset_id}")
    def update_asset(project_id: str, asset_id: str, body: AssetChanges, who: Who) -> dict[str, Any]:
        return {"asset": service().update_asset(who, project_id, asset_id, body.model_dump(exclude_unset=True))}

    @app.delete("/v1/projects/{project_id}/library/{asset_id}", status_code=204)
    def delete_asset(project_id: str, asset_id: str, who: Who) -> Response:
        service().delete_asset(who, project_id, asset_id)
        return Response(status_code=204)

    # GitHub

    @app.get("/v1/github")
    def github_status(who: Who) -> dict[str, Any]:
        return service().github_status(who)

    @app.post("/v1/github/connect")
    def github_connect(body: Connect, request: Request, who: Who) -> dict[str, str]:
        return {"url": service().github_connect(who, body.return_to, str(request.base_url))}

    @app.post("/v1/github/install")
    def github_install(body: Connect, who: Who) -> dict[str, str]:
        return {"url": service().github_install(who, body.return_to)}

    @app.get("/v1/github/callback")
    def github_callback(
        request: Request, state: str = "", code: str = "", error: str = "", setup_action: str = ""
    ) -> Response:
        destination = service().github_callback(code, state, error, str(request.base_url), setup_action)
        return RedirectResponse(destination, status_code=303)

    @app.get("/v1/github/repos")
    def github_repos(who: Who) -> dict[str, Any]:
        return {"repos": service().github_repos(who)}

    @app.delete("/v1/github")
    def github_disconnect(who: Who) -> dict[str, Any]:
        return service().github_disconnect(who)

    @app.post("/v1/projects/{project_id}/github")
    def link_repo(project_id: str, body: LinkRepo, who: Who) -> dict[str, Any]:
        return {"project": service().link_repo(who, project_id, body.repo, body.branch)}

    @app.delete("/v1/projects/{project_id}/github")
    def unlink_repo(project_id: str, who: Who) -> dict[str, Any]:
        return {"project": service().unlink_repo(who, project_id)}

    # Epic: the GitHub account linked to it, which Unreal Engine's editor is pulled with

    @app.get("/v1/epic")
    def epic_status(who: Who) -> dict[str, Any]:
        return service().epic_status(who)

    @app.post("/v1/epic/connect")
    def epic_connect(body: Connect, request: Request, who: Who) -> dict[str, str]:
        return {"url": service().epic_connect(who, body.return_to, str(request.base_url))}

    @app.get("/v1/epic/callback")
    def epic_callback(request: Request, state: str = "", code: str = "", error: str = "") -> Response:
        destination = service().epic_callback(code, state, error, str(request.base_url))
        return RedirectResponse(destination, status_code=303)

    @app.delete("/v1/epic")
    def epic_disconnect(who: Who) -> dict[str, Any]:
        return service().epic_disconnect(who)

    app.mount("/", agent_app)
    return app
