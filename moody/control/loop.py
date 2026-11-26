# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The Claude Agent SDK as the agent's loop: what one turn hands it, and what it hands back as events.

The loop is Claude Code's, run as a library: the SDK starts the `claude`
program it bundles as a child process and talks to it over its standard input
and output. The child asks the model, decides the next step, and runs it; this
module is everything between that child and Moody. A turn (`TurnLoop.run`)
gives the loop its configuration (`TurnLoop.options`), sends the person's
message, and turns what comes back into the project's events.

What the loop is given:

- Moody's tools, served in process (`create_sdk_mcp_server`). A call runs the
  agent's own implementation on a thread (`TurnLoop.handle`), since the tools
  block on Supabase and Modal and the SDK calls them from its event loop. A
  tool's definition says whether it only reads, which the loop takes as leave
  to run several at once.
- None of the loop's file and shell tools. What stays on of its own tools is
  `BUILT_INS` and the subagent tool: web search, web fetch, the skill tool,
  and the file reader, which a skill's text sends the agent to its reference
  files with. Every read is checked here before it runs (`TurnLoop.before`):
  the path is made canonical and has to start with the skills' folder of the
  turn's working directory (`inside`). A fetch is refused where its address is
  not a public web address (`fetchable`), since the fetch is made from the
  machine the turn runs on.
- A working directory of the project's own (`Workspace`), holding nothing but
  a copy of the skills the project is offered, which is where the loop
  discovers them. Its path is the same on every machine, because the SDK keys
  a session's transcript by it.
- A child process that knows the Anthropic key and nothing else of the
  deployment. The SDK starts the child with the whole environment of the
  process it runs in, which here is a Modal function holding every secret of
  the deployment and the function's own Modal identity. So the program the
  SDK is pointed at is a launcher written for the turn (`Workspace.launcher`),
  which starts the real one with the variables `child_environment` names and
  no others.
- The person's words as they wrote them (`verbatim_prompts`): a message is
  text from outside, so nothing in it is read as a command of the loop or
  expanded into a file of the turn's machine.
- The system prompt and the tools' definitions as the code that runs the turn
  has them (`snapshot: False`). Left to itself the loop records both at a
  session's first request and sends that record on every later one, resumed
  turns included, so a deploy that changed the prompt, a tool's description,
  or its input would not reach a project that had already talked to its
  agent. Rendered every turn, they are the same text as the turn before
  unless a deploy changed them, which is the one time the model's cache of
  them is not reused.

What comes back, in the order the child reports it (`TurnLoop.consume`): the
answer as it is written, a block at a time, with a snapshot of a block about
once a second while it grows (`Blocks`); each tool call as it starts
(`TurnLoop.before`, which the loop runs before the tool) and ends; each
subagent as a card that follows what it is doing (`Cards`); and what the turn
cost. A tool's own events (a plan, a library entry, an engine) come from its
implementation, between its start and its end.

Three things are decided here rather than by the model. A tool whose
definition says the person approves it first is not among the tools the loop
may run unasked, so the loop asks (`TurnLoop.permit`), and the answer is the
agent's to get: it writes an `approval` event and waits for the person. A tool
whose result ends the turn (a question for the person) stops the loop after
that call (`TurnLoop.after`), so the turn's worker ends and the answer starts
the next turn on the same session. And when the loop is about to end a turn
with engines of the project still open, it is told so once
(`TurnLoop.stopping`) and goes on, to stop them or say why they stay.

`LoopClient` is the part of the SDK's client a turn uses, which is where a
test stands in for the SDK and its child process.
"""

from __future__ import annotations

import ipaddress
import json
import os
import secrets
import shlex
import shutil
import tempfile
import time
import uuid
import warnings
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Protocol
from urllib.parse import urlsplit

import anyio
import claude_agent_sdk
from claude_agent_sdk import (
    TERMINAL_TASK_STATUSES,
    AgentDefinition,
    AssistantMessage,
    CanUseToolShadowedWarning,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    SdkMcpTool,
    SessionStore,
    StreamEvent,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    TaskUpdatedMessage,
    TextBlock,
    ThinkingBlock,
    ToolAnnotations,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
)

# The SDK warns that a permission callback is not asked about the tools the loop may run unasked, which is the
# arrangement here: the callback is for the tools the person approves, and those are left out of that list
warnings.filterwarnings("ignore", category=CanUseToolShadowedWarning)

# The name Moody's tools are served under, which the loop puts before each tool's own
SERVER = "moody"
PREFIX = f"mcp__{SERVER}__"
# The loop's tool that hands a job to a subagent
SUBAGENT_TOOL = "Agent"
# The largest result of a tool, in characters, the loop keeps in the conversation rather than in a file the agent
# would have to read, which it cannot
RESULT_CHARACTERS = 400_000
# How often a block of the answer is shown again while it is still being written
SNAPSHOT_SECONDS = 1.0
# How long a call's start waits for the block that makes the call to be reported before it is written anyway
SEEN_SECONDS = 5.0
# How often a turn looks whether it was stopped
WATCH_SECONDS = 0.25
# The variables the SDK itself sets for its child, which the launcher lets through
SDK_VARIABLES = (
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_AGENT_SDK_VERSION",
    "CLAUDE_CODE_SDK_READS_SESSION_STATE",
    "PWD",
)
# The variable by which a turn's launcher knows it was started for that turn
TURN_VARIABLE = "MOODY_LOOP_TURN"
# What a subagent's task ends as, by what the loop reports
CARD_STATES = {
    "completed": "completed",
    "failed": "failed",
    "stopped": "stopped",
    "killed": "stopped",
}
# What the person is told when the model could not be asked, by the kind of failure the loop names
API_FAILURES = {
    "rate_limit": "The model is busy right now. Try again in a minute.",
    "authentication_failed": "The agent's model is not available right now.",
    "billing_error": "The agent's model is not available right now.",
    "invalid_request": "The model refused the request. Send a message to try again.",
}
API_FAILURE = "The model could not be reached. Try again."


@dataclass(frozen=True)
class BuiltIn:
    """One of the loop's own tools the agent keeps: its name there, how it looks while it runs, and its title."""

    name: str
    activity: str
    title: Callable[[dict[str, Any]], str]


def host(url: str) -> str:
    """The host of an address, or the address itself where it has none."""
    return urlsplit(url).hostname or url


# The loop's own tools that stay on, by the name Moody gives each
BUILT_INS: dict[str, BuiltIn] = {
    "web_search": BuiltIn(
        "WebSearch",
        "searching",
        lambda given: f"Searching the web for {given.get('query', '')}",
    ),
    "web_fetch": BuiltIn(
        "WebFetch", "analyzing", lambda given: f"Reading {host(given.get('url', ''))}"
    ),
    "skill": BuiltIn(
        "Skill",
        "analyzing",
        lambda given: f"Opening the {given.get('skill', '')} skill",
    ),
    "read": BuiltIn(
        "Read",
        "analyzing",
        lambda given: f"Reading {Path(given.get('file_path', '')).name or 'a file'}",
    ),
}
BUILT_IN_NAMES = {built_in.name: name for name, built_in in BUILT_INS.items()}


@dataclass(frozen=True)
class ToolSpec:
    """One of Moody's tools as the loop is told of it."""

    name: str
    description: str
    input_schema: dict[str, Any]
    activity: str
    read_only: bool


@dataclass(frozen=True)
class Subagent:
    """A subagent as the loop is given it: Moody's tool names resolved, and its model named."""

    name: str
    title: str
    description: str
    prompt: str
    tools: tuple[str, ...]
    skills: tuple[str, ...]
    model: str


@dataclass
class Brief:
    """Everything of one turn the loop is configured with."""

    system: str
    # The person's message as content blocks, the project's state after their words
    prompt: list[dict[str, Any]]
    tools: list[ToolSpec]
    # The tools the loop may run without asking
    unasked: list[str]
    subagents: list[Subagent]
    # The skills the project is offered: each a name and the directory it is copied from
    skills: list[tuple[str, Path]]
    session: str
    resume: bool
    store: SessionStore
    workspace: Workspace


@dataclass(frozen=True)
class Settings:
    """What the deployment configures of the loop (`service.Config`, by the same names)."""

    key: str
    model: str
    effort: str
    thinking: bool
    fallback_model: str
    budget_usd: float
    turn_limit: int
    base_url: str
    # Variables of the worker's own environment the child also gets, such as a proxy's address
    passed: frozenset[str]
    cli: str


class Outcome(Protocol):
    """What a tool gives back, as the agent's `Result` has it."""

    content: str | list[dict[str, Any]]
    summary: str
    ok: bool
    ends_turn: bool


class Host(Protocol):
    """What the loop asks of the agent whose turn it runs."""

    def run_tool(
        self,
        turn: Any,
        name: str,
        arguments: dict[str, Any],
        call_id: str,
        agent_id: str | None,
    ) -> Outcome:
        """Run one of Moody's tools, with its `tool_end` event, and return its result."""

    def title(self, turn: Any, name: str, arguments: dict[str, Any]) -> str:
        """A line that says what a call does, for the page."""

    def approved(
        self, turn: Any, name: str, arguments: dict[str, Any], agent_id: str | None
    ) -> tuple[bool, str]:
        """Whether a call that needs the person's approval may run, and what to tell the model where it may not."""

    def open_engines(self, turn: Any) -> list[str]:
        """The project's engines that are open now, each as a line for the model."""


class LoopClient(Protocol):
    """The part of the SDK's client a turn uses: a test stands in for the SDK and its child process here."""

    async def connect(self) -> None:
        """Start the loop's process."""

    async def query(self, prompt: Any) -> None:
        """Send the turn's message."""

    def receive_response(self) -> AsyncIterator[Any]:
        """The loop's messages up to the turn's result."""

    async def interrupt(self) -> None:
        """Stop what the loop is doing."""

    async def disconnect(self) -> None:
        """End the loop's process."""


Loop = Callable[[ClaudeAgentOptions], LoopClient]


def loop_name(tool: str) -> str:
    """A tool's name in the loop, from the name Moody gives it: one of the loop's own, or one served under `SERVER`."""
    return BUILT_INS[tool].name if tool in BUILT_INS else f"{PREFIX}{tool}"


def moody_name(tool: str) -> str | None:
    """The name Moody gives a tool of the loop, or nothing for a tool the agent does not have."""
    if tool.startswith(PREFIX):
        return tool[len(PREFIX) :]
    return BUILT_IN_NAMES.get(tool)


def bundled_cli() -> str:
    """The `claude` program the installed SDK bundles, which is the one its version was tested with.

    Raises:
        RuntimeError: This install of the SDK bundles none.
    """
    path = Path(claude_agent_sdk.__file__).resolve().parent / "_bundled" / "claude"
    if not path.is_file():
        raise RuntimeError(
            f"claude-agent-sdk {claude_agent_sdk.__version__} bundles no claude program at {path}"
        )
    return str(path)


def inside(path: str, root: Path, base: Path) -> bool:
    """Whether a path the loop is about to read, once canonical, is under a root; a relative one is taken from `base`."""
    real = os.path.realpath(os.path.join(base, path))
    return real.startswith(os.path.realpath(root) + os.sep)


def fetchable(url: str) -> bool:
    """Whether an address is one the agent may fetch: a web address whose host is not this machine or a private one.

    The check is on the address as written, which is what keeps a fetch off
    the turn's own machine and the network it sits in (a metadata service, a
    neighbor) when the model, or a page it read, names one.
    """
    parts = urlsplit(url)
    name = (parts.hostname or "").rstrip(".").lower()
    if (
        parts.scheme not in ("http", "https")
        or not name
        or name == "localhost"
        or name.endswith((".localhost", ".internal", ".local"))
    ):
        return False
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return "." in name
    return address.is_global


def child_environment(settings: Settings, workspace: Workspace) -> dict[str, str]:
    """The variables the loop's process runs with: the Anthropic key, the turn's own directories, and the loop's switches.

    The switches follow the SDK's guidance for a process that serves many
    people: no settings or memory read from the machine, no traffic but the
    model's, no work left running behind a turn's back (a subagent runs to
    its end before the step that started it returns), no subagent but the
    ones defined, and every tool's definition given to the model up front.
    """
    variables = {
        "ANTHROPIC_API_KEY": settings.key,
        "HOME": str(workspace.home),
        "TMPDIR": str(workspace.scratch),
        "PATH": os.defpath,
        "CLAUDE_CONFIG_DIR": str(workspace.config),
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
        "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
        "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",
        "ENABLE_TOOL_SEARCH": "false",
        TURN_VARIABLE: workspace.token,
    }
    if settings.base_url:
        variables["ANTHROPIC_BASE_URL"] = settings.base_url
    for name in sorted(settings.passed):
        if name in os.environ:
            variables[name] = os.environ[name]
    return variables


class Workspace:
    """The directories of one turn: the project's working directory, and a private one for the loop's process.

    The working directory is `<root>/<project id>`, the same path wherever the
    turn runs, made empty for the turn and given a copy of the project's
    skills under `.claude/skills`. Everything else the process writes (its
    configuration, its home, its temporary files) and the launcher it is
    started through are in a directory of the turn's own. Both are removed
    when the turn is over.
    """

    def __init__(self, root: str, project_id: str) -> None:
        self.directory = Path(root) / project_id
        self.private: Path | None = None
        self.token = secrets.token_hex(16)

    def __enter__(self) -> Workspace:
        shutil.rmtree(self.directory, ignore_errors=True)
        self.skills.mkdir(parents=True)
        self.private = Path(tempfile.mkdtemp(prefix="moody-turn-"))
        for directory in (self.home, self.config, self.scratch):
            directory.mkdir()
        return self

    def __exit__(self, *_: Any) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)
        if self.private is not None:
            shutil.rmtree(self.private, ignore_errors=True)

    @property
    def skills(self) -> Path:
        """Where the loop finds the project's skills, and the one folder it may read."""
        return self.directory / ".claude" / "skills"

    @property
    def home(self) -> Path:
        return self.inner("home")

    @property
    def config(self) -> Path:
        return self.inner("config")

    @property
    def scratch(self) -> Path:
        return self.inner("tmp")

    def inner(self, name: str) -> Path:
        if self.private is None:
            raise RuntimeError(
                "the turn's directories are made when its workspace is entered"
            )
        return self.private / name

    def offer(self, skills: list[tuple[str, Path]]) -> None:
        """Copy the skills the project is offered into the working directory, each whole."""
        for name, source in skills:
            shutil.copytree(source, self.skills / name)

    def launcher(self, cli: str, names: list[str]) -> str:
        """Write the program the SDK starts in place of the loop's, and return its path.

        It starts the loop's program with the named variables as it was
        handed them and nothing else: `env -i` clears the environment the SDK
        passed down. It holds names only, never a value, so the key is in no
        file. The SDK also runs it once outside the turn, to ask the program's
        version, with whatever environment this process has; started without
        the turn's own mark (`TURN_VARIABLE`), it lets no variable through at
        all.
        """
        passed = [name for name in names if name != TURN_VARIABLE]
        for name in passed:
            if not name.replace("_", "A").isalnum() or name[0].isdigit():
                raise ValueError(f"{name!r} is not a variable's name")
        script = "\n".join(
            [
                "#!/bin/sh",
                f'set -- {shlex.quote(cli)} "$@"',
                f'if [ "$(printenv {TURN_VARIABLE})" = {self.token} ]; then',
                f"    for name in {' '.join(passed)}; do",
                '        if value=$(printenv "$name"); then set -- "$name=$value" "$@"; fi',
                "    done",
                "fi",
                'exec env -i "$@"',
                "",
            ]
        )
        path = self.inner("claude")
        path.write_text(script)
        path.chmod(0o700)
        return str(path)


@dataclass
class Draft:
    """A block of the answer while it is written."""

    block: str
    kind: str
    text: str = ""
    shown_at: float = 0.0
    final: bool = False


class Blocks:
    """The agent's own answer as it streams: its text and thinking blocks, each shown while it is written.

    The loop reports the model's raw stream (`StreamEvent`) and then each
    block whole (`AssistantMessage`), the whole block arriving before the
    stream says the block is over. A block is named after its message and its
    place in it, so the page folds a later event of the same block over the
    earlier one. A snapshot is written at most once in `SNAPSHOT_SECONDS`
    while the block grows, and the whole block when it is done; a block that
    is over within that time is written once.
    """

    def __init__(
        self,
        emit: Callable[[str, dict[str, Any]], Any],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.emit = emit
        self.clock = clock
        self.message = ""
        self.drafts: dict[int, Draft] = {}
        self.extra = 0

    async def stream(self, event: dict[str, Any]) -> None:
        """Take one event of the model's stream."""
        kind = event.get("type")
        if kind == "message_start":
            self.message = event.get("message", {}).get("id") or uuid.uuid4().hex
            self.drafts = {}
        elif kind == "content_block_start":
            started = event.get("content_block", {}).get("type")
            if started in ("text", "thinking"):
                self.drafts[event["index"]] = Draft(
                    f"{self.message}:{event['index']}", started, shown_at=self.clock()
                )
        elif kind == "content_block_delta":
            draft = self.drafts.get(event.get("index"))
            delta = event.get("delta", {})
            if draft is None or draft.final:
                return
            draft.text += (
                delta.get("text", "")
                if delta.get("type") == "text_delta"
                else delta.get("thinking", "")
            )
            if self.clock() - draft.shown_at >= SNAPSHOT_SECONDS and draft.text.strip():
                draft.shown_at = self.clock()
                await self.emit(
                    draft.kind,
                    {"text": draft.text, "block": draft.block, "partial": True},
                )
        elif kind == "content_block_stop":
            draft = self.drafts.get(event.get("index"))
            if draft is not None and not draft.final:
                await self.whole(draft, draft.text)

    async def finished(self, message_id: str | None, kind: str, text: str) -> None:
        """Take a block the loop reports whole: the one being streamed where there is one, else a block of its own."""
        draft = next(
            (
                draft
                for _, draft in sorted(self.drafts.items())
                if draft.kind == kind and not draft.final
            ),
            None,
        )
        if draft is None or (message_id and message_id != self.message):
            self.extra += 1
            draft = Draft(
                f"{message_id or self.message or uuid.uuid4().hex}:whole-{self.extra}",
                kind,
            )
        await self.whole(draft, text)

    async def whole(self, draft: Draft, text: str) -> None:
        draft.final = True
        if text.strip():
            await self.emit(draft.kind, {"text": text, "block": draft.block})


@dataclass
class Card:
    """A subagent's card: who it is, the job it was handed, and what it is doing now."""

    agent_id: str
    group: str
    name: str
    title: str
    task: str
    state: str = "working"
    activity: str = "thinking"
    detail: str = ""
    seconds: float | None = None
    tokens: int | None = None
    shown: dict[str, Any] = field(default_factory=dict)

    def event(self) -> dict[str, Any]:
        """The card as an `agent` event carries it: whole, every time."""
        card = {
            "agent_id": self.agent_id,
            "group": self.group,
            "name": self.name,
            "title": self.title,
            "task": self.task,
            "state": self.state,
            "activity": self.activity,
            "detail": self.detail,
        }
        if self.seconds is not None:
            card["seconds"] = self.seconds
        if self.tokens is not None:
            card["tokens"] = self.tokens
        return card


class Cards:
    """The subagents of one turn, each a card the page shows working.

    A subagent begins as a call of the subagent tool in one of the agent's
    messages, and the loop then reports its task: started, in progress,
    ended. The calls of one message are the subagents one step started
    together, so they share a `group`, the message's id. A card's activity
    follows what the subagent is doing: thinking, the activity of the tool it
    is running, confused after a call that failed, satisfied once it is done.
    """

    def __init__(
        self, emit: Callable[[str, dict[str, Any]], Any], titles: dict[str, str]
    ) -> None:
        self.emit = emit
        self.titles = titles
        # The message each call of the subagent tool was made in
        self.groups: dict[str, str] = {}
        self.by_call: dict[str, Card] = {}
        self.by_agent: dict[str, Card] = {}

    def spawned(self, call_id: str, message_id: str | None) -> None:
        """Note the message a call of the subagent tool was made in."""
        self.groups[call_id] = message_id or call_id

    def agent_of(self, call_id: str | None) -> str | None:
        """The subagent a call of the subagent tool started, by which its own messages are told apart."""
        card = self.by_call.get(call_id or "")
        return card.agent_id if card else None

    async def started(self, message: TaskStartedMessage) -> None:
        call_id = message.tool_use_id or message.task_id
        name = message.data.get("subagent_type") or message.task_type or "agent"
        card = Card(
            message.task_id,
            self.groups.get(call_id, call_id),
            name,
            self.titles.get(name, name),
            message.description,
        )
        self.by_call[call_id] = self.by_agent[card.agent_id] = card
        await self.show(card)

    async def progressed(self, message: TaskProgressMessage) -> None:
        card = self.by_agent.get(message.task_id)
        if card is not None and card.state == "working":
            self.measure(card, message.usage)
            await self.show(card)

    async def ended(
        self, task_id: str, status: str, usage: dict[str, Any] | None = None
    ) -> None:
        card = self.by_agent.get(task_id)
        if card is None or card.state != "working":
            return
        card.state = CARD_STATES.get(status, "failed")
        card.activity = "satisfied" if card.state == "completed" else "confused"
        self.measure(card, usage)
        await self.show(card)

    async def doing(self, agent_id: str | None, activity: str, detail: str) -> None:
        """Set what a working subagent is doing now."""
        card = self.by_agent.get(agent_id or "")
        if card is not None and card.state == "working":
            card.activity, card.detail = activity, detail[:200]
            await self.show(card)

    async def close(self, state: str) -> None:
        """End every card still working, as the turn that is over left it."""
        for card in self.by_agent.values():
            await self.ended(card.agent_id, state)

    @staticmethod
    def measure(card: Card, usage: dict[str, Any] | None) -> None:
        if usage:
            card.seconds = round(usage.get("duration_ms", 0) / 1000, 1)
            card.tokens = usage.get("total_tokens", 0)

    async def show(self, card: Card) -> None:
        event = card.event()
        if event != card.shown:
            card.shown = event
            await self.emit("agent", event)


@dataclass
class Call:
    """A call the loop is about to make: who makes it, and whether the block that makes it has been reported."""

    call_id: str
    agent_id: str | None = None
    seen: anyio.Event = field(default_factory=anyio.Event)


class TurnLoop:
    """One turn on the loop: its configuration, its tools' calls, its hooks, and the events it becomes."""

    def __init__(
        self,
        host: Host,
        turn: Any,
        brief: Brief,
        settings: Settings,
        activities: dict[str, str],
    ) -> None:
        self.host = host
        self.turn = turn
        self.brief = brief
        self.settings = settings
        # How each of Moody's tools looks while it runs
        self.activities = activities
        self.blocks = Blocks(self.emit)
        self.cards = Cards(
            self.emit, {subagent.name: subagent.title for subagent in brief.subagents}
        )
        self.calls: dict[str, Call] = {}
        # Calls of Moody's tools the loop announced (its hook before a tool runs), by tool and input, for the
        # handler that runs them
        self.announced: dict[tuple[str, str], deque[Call]] = {}
        # Calls whose `tool_start` is written and whose `tool_end` is not, each with the subagent that made it
        self.open: dict[str, str | None] = {}
        # Calls after which the turn ends
        self.ending: set[str] = set()
        self.running = 0
        self.nudged = False
        self.failure: str | None = None
        self.crashed = False
        self.result: ResultMessage | None = None
        self.started = time.monotonic()
        self.client: LoopClient | None = None
        self.interrupted = False

    # What the loop is given

    def options(self) -> ClaudeAgentOptions:
        """The loop's configuration for this turn."""
        brief, settings, workspace = self.brief, self.settings, self.brief.workspace
        workspace.offer(brief.skills)
        variables = child_environment(settings, workspace)
        return ClaudeAgentOptions(
            tools=[SUBAGENT_TOOL, *(built_in.name for built_in in BUILT_INS.values())],
            allowed_tools=[
                *(loop_name(name) for name in brief.unasked),
                BUILT_INS["web_search"].name,
                BUILT_INS["web_fetch"].name,
            ],
            # A step never copies the whole conversation into a subagent: a subagent is handed one job
            disallowed_tools=[f"{SUBAGENT_TOOL}(fork)"],
            system_prompt={"type": "custom", "prompt": brief.system, "snapshot": False},
            mcp_servers={
                SERVER: create_sdk_mcp_server(
                    SERVER, tools=[self.served(tool) for tool in brief.tools]
                )
            },
            strict_mcp_config=True,
            permission_mode="default",
            can_use_tool=self.permit,
            hooks={
                "PreToolUse": [HookMatcher(hooks=[self.before], on_failure="block")],
                "PostToolUse": [HookMatcher(hooks=[self.after])],
                "Stop": [HookMatcher(hooks=[self.stopping])],
            },
            agents={
                subagent.name: AgentDefinition(
                    description=subagent.description,
                    prompt=subagent.prompt,
                    tools=[loop_name(tool) for tool in subagent.tools]
                    + ([BUILT_INS["read"].name] if subagent.skills else []),
                    skills=list(subagent.skills) or None,
                    model=subagent.model,
                )
                for subagent in brief.subagents
            }
            or None,
            skills=[name for name, _ in brief.skills],
            setting_sources=["project"],
            cwd=str(workspace.directory),
            cli_path=workspace.launcher(
                settings.cli or bundled_cli(), [*variables, *SDK_VARIABLES]
            ),
            env=variables,
            model=settings.model,
            fallback_model=settings.fallback_model or None,
            effort=settings.effort,
            thinking={"type": "adaptive", "display": "summarized"}
            if settings.thinking
            else {"type": "disabled"},
            max_turns=settings.turn_limit,
            max_budget_usd=settings.budget_usd,
            include_partial_messages=True,
            forward_subagent_text=True,
            verbatim_prompts=True,
            session_store=brief.store,
            session_store_flush="eager",
            session_id=None if brief.resume else brief.session,
            resume=brief.session if brief.resume else None,
            stderr=lambda line: print(f"loop: {line}"),
        )

    def served(self, spec: ToolSpec) -> SdkMcpTool[Any]:
        """One of Moody's tools as the in-process server offers it."""

        async def handler(arguments: dict[str, Any]) -> dict[str, Any]:
            return await self.handle(spec.name, arguments)

        return SdkMcpTool(
            name=spec.name,
            description=spec.description,
            input_schema=spec.input_schema,
            handler=handler,
            annotations=ToolAnnotations(
                readOnlyHint=spec.read_only, maxResultSizeChars=RESULT_CHARACTERS
            ),
        )

    # The turn

    async def run(self, loop: Loop) -> None:
        """Run the turn on the loop until it ends, is stopped, or fails, and write what it cost."""
        client = self.client = loop(self.options())
        try:
            await client.connect()
            await client.query(self.message())
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(self.watch)
                async for message in client.receive_response():
                    await self.consume(message)
                tasks.cancel_scope.cancel()
        except BaseException:
            self.crashed = True
            raise
        finally:
            with anyio.CancelScope(shield=True):
                await client.disconnect()
                # A tool the loop gave up on still runs to its own end, and its events belong to this turn
                while self.running:
                    await anyio.sleep(WATCH_SECONDS)
                await self.finish()

    async def message(self) -> AsyncIterator[dict[str, Any]]:
        """The turn's message as the loop takes one: the person's words and the project's state, as blocks."""
        yield {
            "type": "user",
            "message": {"role": "user", "content": self.brief.prompt},
            "parent_tool_use_id": None,
        }

    async def watch(self) -> None:
        """Interrupt the loop once the turn is stopped, which its heartbeat learns."""
        while not self.turn.stopped.is_set():
            await anyio.sleep(WATCH_SECONDS)
        await self.interrupt()

    async def interrupt(self) -> None:
        """Have the loop stop what it is doing, once."""
        if self.client is not None and not self.interrupted:
            self.interrupted = True
            await self.client.interrupt()

    async def emit(self, kind: str, data: dict[str, Any]) -> None:
        """Write an event of the turn without holding the loop's messages up for the database."""
        await anyio.to_thread.run_sync(self.turn.event, kind, data)

    async def finish(self) -> None:
        """Close what the turn left open, say why it ended where that is not the answer itself, and write its cost."""
        stopped = self.turn.stopped.is_set()
        for call_id in list(self.open):
            await self.end_call(
                call_id, False, "Stopped" if stopped else "Did not finish"
            )
        await self.cards.close("stopped" if stopped else "failed")
        result = self.result
        if not stopped and not self.crashed:
            problem = self.problem(result)
            if problem:
                await self.emit("error", problem)
        used = (result.model_usage if result else None) or {}
        await self.emit(
            "usage",
            {
                "input_tokens": sum(
                    model.get("inputTokens", 0)
                    + model.get("cacheReadInputTokens", 0)
                    + model.get("cacheCreationInputTokens", 0)
                    for model in used.values()
                ),
                "output_tokens": sum(
                    model.get("outputTokens", 0) for model in used.values()
                ),
                "cost_usd": round(
                    (result.total_cost_usd if result else None) or 0.0, 4
                ),
                "seconds": round(time.monotonic() - self.started, 1),
                "agents": len(self.cards.by_agent),
            },
        )

    def problem(self, result: ResultMessage | None) -> dict[str, Any] | None:
        """The `error` event of a turn that ended some other way than the agent finishing, or nothing.

        A turn that reached one of its person's limits says which and how
        much, and names it in `limit`, so the page can offer the setting
        beside the message.
        """
        settings = self.settings
        if result is None:
            return {
                "message": "Something went wrong on our side, and this turn stopped."
            }
        if result.subtype == "error_max_turns":
            return {
                "message": f"This turn reached your limit of {settings.turn_limit} step{'' if settings.turn_limit == 1 else 's'} and stopped. You can change "
                "the limit in your settings. Send a message to go on.",
                "limit": "steps",
            }
        if result.subtype == "error_max_budget_usd":
            return {
                "message": f"This turn reached your spending limit of ${settings.budget_usd:g} and stopped. You can "
                "change the limit in your settings. Send a message to go on.",
                "limit": "budget",
            }
        if result.stop_reason == "refusal":
            return {
                "message": "The model declined to go on with this. Try asking another way."
            }
        if self.failure is not None:
            print(
                f"loop: the model could not be asked ({self.failure}): {result.result}"
            )
            return {"message": API_FAILURES.get(self.failure, API_FAILURE)}
        if result.is_error:
            print(
                f"loop: the turn ended as {result.subtype} ({result.terminal_reason}): {result.errors or result.result}"
            )
            return {
                "message": "Something went wrong on our side, and this turn stopped."
            }
        return None

    # What comes back

    async def consume(self, message: Any) -> None:
        """Turn one message of the loop into the turn's events."""
        if isinstance(message, StreamEvent):
            await self.blocks.stream(message.event)
        elif isinstance(message, AssistantMessage):
            await self.said(message)
        elif isinstance(message, UserMessage):
            await self.answered(message)
        elif isinstance(message, TaskStartedMessage):
            await self.cards.started(message)
        elif isinstance(message, TaskProgressMessage):
            await self.cards.progressed(message)
        elif isinstance(message, TaskNotificationMessage):
            await self.cards.ended(
                message.task_id, message.status, dict(message.usage or {})
            )
        elif isinstance(message, TaskUpdatedMessage):
            if message.status in TERMINAL_TASK_STATUSES:
                await self.cards.ended(message.task_id, message.status)
        elif isinstance(message, ResultMessage):
            self.result = message

    async def said(self, message: AssistantMessage) -> None:
        """Take a block of an answer: the agent's own, or a subagent's."""
        agent_id = (
            self.cards.agent_of(message.parent_tool_use_id)
            or message.parent_tool_use_id
        )
        if message.error is not None:
            # The loop reports a failed request as text in the model's place; `finish` tells the person
            self.failure = message.error
            return
        for block in message.content:
            if isinstance(block, (TextBlock, ThinkingBlock)):
                kind, words = (
                    ("text", block.text)
                    if isinstance(block, TextBlock)
                    else ("thinking", block.thinking)
                )
                if message.parent_tool_use_id is None:
                    await self.blocks.finished(message.message_id, kind, words)
                elif words.strip():
                    await self.emit(kind, self.owned({"text": words}, agent_id))
                    await self.cards.doing(
                        agent_id,
                        "thinking",
                        "Thinking"
                        if kind == "thinking"
                        else words.strip().splitlines()[0],
                    )
            elif isinstance(block, ToolUseBlock):
                if block.name == SUBAGENT_TOOL:
                    self.cards.spawned(block.id, message.message_id)
                self.call(block.id).seen.set()

    def call(self, call_id: str) -> Call:
        """What is known of a call, from wherever it is heard of first: the block that makes it, or the hook before it."""
        return self.calls.setdefault(call_id, Call(call_id))

    async def answered(self, message: UserMessage) -> None:
        """Close the calls a message of results answers that their own tool did not close."""
        if isinstance(message.content, str):
            return
        for block in message.content:
            if (
                not isinstance(block, ToolResultBlock)
                or block.tool_use_id not in self.open
            ):
                continue
            words = (
                block.content
                if isinstance(block.content, str)
                else " ".join(
                    part.get("text", "")
                    for part in block.content or []
                    if isinstance(part, dict)
                )
            )
            if block.is_error:
                await self.cards.doing(
                    self.open[block.tool_use_id],
                    "confused",
                    words.strip() or "A call failed",
                )
            await self.end_call(
                block.tool_use_id,
                not block.is_error,
                " ".join(words.split())[:200] or "Done",
            )

    async def end_call(self, call_id: str, ok: bool, summary: str) -> None:
        """Write the `tool_end` of a call that is still open: one its own tool did not write."""
        if call_id in self.open:
            agent_id = self.open.pop(call_id)
            await self.emit(
                "tool_end",
                self.owned(
                    {"call_id": call_id, "ok": ok, "summary": summary}, agent_id
                ),
            )

    @staticmethod
    def owned(data: dict[str, Any], agent_id: str | None) -> dict[str, Any]:
        """An event's data, marked as a subagent's where it is one's."""
        return {**data, "agent_id": agent_id} if agent_id else data

    # Moody's tools

    async def handle(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run one call of one of Moody's tools on a thread and give the loop its result.

        The call is the one the loop announced for this tool and input
        (`before`), which names it and the subagent making it, and whose
        `tool_start` is written by then. A call the loop cancels (the turn
        stopped) still runs to its end here: the tools see the stop
        themselves between their own steps.
        """
        waiting = self.announced.get((name, json.dumps(arguments, sort_keys=True)))
        call = waiting.popleft() if waiting else Call(f"call_{uuid.uuid4().hex[:24]}")
        self.running += 1
        try:
            result = await anyio.to_thread.run_sync(
                self.host.run_tool,
                self.turn,
                name,
                arguments,
                call.call_id,
                call.agent_id,
            )
        finally:
            self.running -= 1
        # The tool wrote its own `tool_end`
        self.open.pop(call.call_id, None)
        if self.turn.stopped.is_set():
            # A tool's own look at the heartbeat learned of the stop before the watch did
            await self.interrupt()
        if not result.ok:
            await self.cards.doing(call.agent_id, "confused", result.summary)
        if result.ends_turn:
            self.ending.add(call.call_id)
        content = (
            [{"type": "text", "text": result.content}]
            if isinstance(result.content, str)
            else [
                {
                    "type": "image",
                    "data": block["source"]["data"],
                    "mimeType": block["source"]["media_type"],
                }
                if block.get("type") == "image"
                else {"type": "text", "text": block.get("text", "")}
                for block in result.content
            ]
        )
        return {"content": content, "is_error": not result.ok}

    # The loop's hooks

    async def before(self, given: Any, call_id: str | None, _: Any) -> dict[str, Any]:
        """Before any tool runs: refuse what the agent may not do, and write the call's `tool_start`.

        A read is of a skill's file or it is refused, and a fetch is of a
        public address. The start is written once the block that makes the
        call has been reported, so it follows the words the model wrote before
        the call; a call of the subagent tool has no start of its own, since
        its subagent's card is what the page shows. A call of Moody's tools
        is then announced to the handler that will run it.
        """
        name, arguments, agent_id = (
            given["tool_name"],
            given.get("tool_input") or {},
            given.get("agent_id"),
        )
        tool = moody_name(name)
        if name == SUBAGENT_TOOL:
            return {}
        if tool is None or (tool not in BUILT_INS and tool not in self.activities):
            return self.refusal(f"There is no tool {name}.")
        workspace = self.brief.workspace
        if tool == "read" and not inside(
            str(arguments.get("file_path", "")), workspace.skills, workspace.directory
        ):
            return self.refusal(
                "Only the files of a skill can be read: the paths its text gives, under its base directory."
            )
        if tool == "web_fetch" and not fetchable(str(arguments.get("url", ""))):
            return self.refusal("Only public web addresses can be fetched.")
        call = self.call(call_id or f"call_{uuid.uuid4().hex[:24]}")
        call.agent_id = agent_id
        with anyio.move_on_after(SEEN_SECONDS):
            await call.seen.wait()
        if tool in BUILT_INS:
            title, activity = BUILT_INS[tool].title(arguments), BUILT_INS[tool].activity
        else:
            title = await anyio.to_thread.run_sync(
                self.host.title, self.turn, tool, arguments
            )
            activity = self.activities[tool]
            self.announced.setdefault(
                (tool, json.dumps(arguments, sort_keys=True)), deque()
            ).append(call)
        self.open[call.call_id] = agent_id
        await self.emit(
            "tool_start",
            self.owned(
                {
                    "call_id": call.call_id,
                    "tool": tool,
                    "title": title,
                    "activity": activity,
                },
                agent_id,
            ),
        )
        await self.cards.doing(agent_id, activity, title)
        return {}

    @staticmethod
    def refusal(reason: str) -> dict[str, Any]:
        """A hook's answer that keeps a tool from running, with what the model is told."""
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    async def after(self, given: Any, call_id: str | None, _: Any) -> dict[str, Any]:
        """After a tool ran: end the turn where the result of one of the agent's own calls says so."""
        if call_id in self.ending and not given.get("agent_id"):
            return {
                "continue_": False,
                "stopReason": "The turn ends here: the person answers next, and their answer starts the next turn.",
            }
        return {}

    async def stopping(self, given: Any, _: str | None, __: Any) -> dict[str, Any]:
        """As the loop is about to end the turn: say once which engines are still open, so it stops them or says why not."""
        if self.nudged or given.get("stop_hook_active") or self.turn.stopped.is_set():
            return {}
        self.nudged = True
        engines = await anyio.to_thread.run_sync(self.host.open_engines, self.turn)
        if not engines:
            return {}
        return {
            "decision": "block",
            "reason": "Before this turn ends: these engines of the project are still open, and each costs the person "
            "credits every minute it runs.\n"
            + "\n".join(engines)
            + "\nStop each one the work no longer needs with "
            "engine_stop. For one that stays open, say in one line why (the person is using it, or the next step needs "
            "it). Then end your turn.",
        }

    async def permit(
        self, name: str, arguments: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Decide a call the loop may not make unasked: one of the tools the person approves, or nothing the agent has."""
        tool = name[len(PREFIX) :] if name.startswith(PREFIX) else None
        if tool is None:
            return PermissionResultDeny(
                message=f"{name} is not something this agent can do."
            )
        allowed, told = await anyio.to_thread.run_sync(
            self.host.approved, self.turn, tool, arguments, context.agent_id
        )
        if allowed:
            return PermissionResultAllow(updated_input=arguments)
        await self.end_call(context.tool_use_id or "", False, "Not approved")
        return PermissionResultDeny(message=told, interrupt=self.turn.stopped.is_set())


def sdk_loop(options: ClaudeAgentOptions) -> LoopClient:
    """The loop itself: the SDK's client, which starts the `claude` program as a child of this process."""
    return ClaudeSDKClient(options)
