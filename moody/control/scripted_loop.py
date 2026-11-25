# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""A stand-in for the Claude Agent SDK's client, for tests: the loop's protocol with a scripted model.

`ScriptedLoop` takes the place of `loop.sdk_loop`: it is handed the options a
turn configures the loop with and gives back a client that does, in this
process and at once, what the SDK's child process does over its pipes, as far
as a turn can tell. The model is a script: each request the loop would make
takes the next scripted reply, or the reply a step makes of the request, and
every request is recorded as the Messages API would have seen it.

What it reproduces is what was observed of the real program (`test_loop.py`
runs the same turns through it, against a scripted API):

- A reply's text and thinking arrive as stream events and then as whole
  blocks; each tool call as a block of its own.
- A tool call passes the hooks before it, then the permission rules (the
  tools the options allow unasked, else the permission callback), then runs:
  Moody's tools through the in-process server the options carry, by the SDK's
  own bridge, so their inputs are checked as the SDK checks them; the skill
  tool and the file reader on the turn's working directory; web search and
  fetch as a canned answer.
- A call of the subagent tool runs that subagent's own script, with the
  task messages, the hooks, and the forwarded blocks a subagent's work comes
  with. The calls of one reply are started together and then run in order.
- A hook after a tool may end the turn, and the hook at the turn's end may
  send the model on once more.
- The conversation is written to the options' session store as it grows, in
  the shape the SDK's own readers take, and read back from it where a turn
  resumes, so a second client of the same store goes on where the first
  stopped.

It does not reproduce the program's own prompt text around a request (its
environment note, its listing of skills and subagents), compaction, or
anything of the network.
"""

from __future__ import annotations

import copy
import itertools
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    PermissionResultAllow,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    TaskUpdatedMessage,
    TextBlock,
    ThinkingBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    project_key_for_directory,
)
from claude_agent_sdk._internal.sdk_mcp_bridge import SdkMcpBridge

PREFIX = "mcp__"
# What one request of the scripted model is counted as, which a turn's `usage` adds up
REQUEST_TOKENS = {
    "inputTokens": 100,
    "outputTokens": 20,
    "cacheReadInputTokens": 0,
    "cacheCreationInputTokens": 0,
}
REQUEST_COST = 0.001


@dataclass
class Reply:
    """One answer of the scripted model: its content blocks, as the Messages API has them, and why it stopped.

    `error` makes it a request that failed instead, of the kind the loop
    names (`rate_limit`, `server_error`). `delay` is the pause, in seconds,
    between the pieces of its text as a scripted API streams it.
    """

    content: list[dict[str, Any]]
    stop_reason: str | None = None
    error: str | None = None
    delay: float = 0.0


Step = Reply | Callable[[dict[str, Any]], Reply]


@dataclass
class Outcome:
    """How one call ended: its result block, and whether a hook after it ended the turn."""

    result: dict[str, Any]
    stops: bool = False


@dataclass
class Conversation:
    """One session as the stand-in holds it: its messages, and the entries it has written of them."""

    session_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_entry: str | None = None


class ScriptedLoop:
    """The loop with a scripted model: the factory a test gives an `Agent` in place of `loop.sdk_loop`."""

    def __init__(self) -> None:
        self.steps: list[Step] = []
        # A subagent's own steps, by its name
        self.agent_steps: dict[str, list[Step]] = {}
        self.requests: list[dict[str, Any]] = []
        self.options: list[ClaudeAgentOptions] = []
        self.clients: list[ScriptedClient] = []
        self.ids = itertools.count(1)
        # Whether the hooks at a turn's end are run: a test that is not about how a turn ends may leave them out
        self.stop_hooks = True
        # The requests the script had no reply for, which breaks a turn; a test that means it to says so
        self.ran_dry: list[dict[str, Any]] = []
        self.may_run_dry = False

    def script(self, *steps: Step) -> None:
        """Add replies for the agent's own next requests."""
        self.steps.extend(steps)

    def script_agent(self, name: str, *steps: Step) -> None:
        """Add replies for the next requests of a subagent."""
        self.agent_steps.setdefault(name, []).extend(steps)

    def __call__(self, options: ClaudeAgentOptions) -> ScriptedClient:
        self.options.append(options)
        client = ScriptedClient(self, options)
        self.clients.append(client)
        return client


class ScriptedClient:
    """One turn's client: what `loop.LoopClient` asks, answered from the script."""

    def __init__(self, loop: ScriptedLoop, options: ClaudeAgentOptions) -> None:
        self.loop = loop
        self.options = options
        self.conversation = Conversation(
            options.resume or options.session_id or str(uuid.uuid4())
        )
        self.interrupted = False
        self.bridges = {
            name: SdkMcpBridge(name, config["instance"])
            for name, config in (options.mcp_servers or {}).items()
            if isinstance(config, dict) and config.get("type") == "sdk"
        }
        self.tools: dict[str, dict[str, Any]] = {}
        self.rpc = itertools.count(1)
        self.cost = 0.0
        self.usage: dict[str, dict[str, Any]] = {}
        self.turns = 0

    @property
    def key(self) -> dict[str, str]:
        return {
            "project_key": project_key_for_directory(self.options.cwd),
            "session_id": self.conversation.session_id,
        }

    async def connect(self) -> None:
        """Read the session back where the turn resumes one, and learn the served tools."""
        if self.options.resume and self.options.session_store is not None:
            entries = await self.options.session_store.load(self.key) or []
            self.conversation.messages = [
                entry["message"]
                for entry in entries
                if entry.get("type") in ("user", "assistant")
            ]
            self.conversation.last_entry = entries[-1]["uuid"] if entries else None
        for name, bridge in self.bridges.items():
            await bridge.handle(
                {
                    "jsonrpc": "2.0",
                    "id": next(self.rpc),
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "scripted", "version": "0"},
                    },
                }
            )
            await bridge.handle(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}
            )
            listed = await bridge.handle(
                {"jsonrpc": "2.0", "id": next(self.rpc), "method": "tools/list"}
            )
            for tool in listed["result"]["tools"]:
                self.tools[f"{PREFIX}{name}__{tool['name']}"] = tool

    async def query(self, prompt: Any) -> None:
        """Take the turn's message."""
        if isinstance(prompt, str):
            await self.remember("user", prompt)
            return
        async for message in prompt:
            await self.remember("user", message["message"]["content"])

    async def interrupt(self) -> None:
        self.interrupted = True

    async def disconnect(self) -> None:
        for bridge in self.bridges.values():
            await bridge.aclose()

    async def remember(
        self, role: str, content: Any, key: dict[str, str] | None = None
    ) -> None:
        """Add a message to the conversation and write it to the session store, as a transcript's entry."""
        self.conversation.messages.append({"role": role, "content": content})
        if self.options.session_store is None:
            return
        entry = {
            "type": role,
            "uuid": str(uuid.uuid4()),
            "parentUuid": self.conversation.last_entry,
            "sessionId": self.conversation.session_id,
            "message": {"role": role, "content": copy.deepcopy(content)},
        }
        self.conversation.last_entry = entry["uuid"]
        await self.options.session_store.append(key or self.key, [entry])

    # The loop

    async def receive_response(self) -> AsyncIterator[Any]:
        """Run the scripted model until it answers without a call, a hook ends the turn, or the turn is interrupted."""
        session = self.conversation.session_id
        yield SystemMessage(
            "init",
            {
                "type": "system",
                "subtype": "init",
                "session_id": session,
                "cwd": str(self.options.cwd),
                "tools": self.offered(None),
            },
        )
        stop_reason, terminal, subtype, text = "end_turn", "completed", "success", ""
        nudged = False
        failed = False
        while True:
            if self.options.max_turns and self.turns >= self.options.max_turns:
                subtype, terminal, failed = "error_max_turns", "max_turns", True
                break
            # The loop runs the calls of the answer that reached the budget, then asks no more
            if self.options.max_budget_usd and self.cost >= self.options.max_budget_usd:
                subtype, terminal, failed = (
                    "error_max_budget_usd",
                    "budget_exhausted",
                    True,
                )
                break
            reply, message_id = self.ask(self.conversation.messages, None)
            if reply.error:
                yield AssistantMessage(
                    [TextBlock(f"API Error: {reply.error}")],
                    self.options.model or "",
                    error=reply.error,
                    message_id=message_id,
                    session_id=session,
                )
                terminal, failed, text = "api_error", True, f"API Error: {reply.error}"
                break
            async for message in self.spoken(reply, message_id, None):
                yield message
            await self.remember("assistant", reply.content)
            stop_reason = reply.stop_reason or (
                "tool_use" if self.calls(reply) else "end_turn"
            )
            text = "".join(
                block["text"] for block in reply.content if block["type"] == "text"
            )
            if stop_reason == "refusal":
                terminal, failed = "api_error", True
                break
            if not self.calls(reply):
                feedback = (
                    await self.stop_hooks(nudged) if self.loop.stop_hooks else None
                )
                if feedback is None:
                    break
                nudged = True
                await self.remember("user", f"Stop hook feedback:\n{feedback}")
                continue
            results: list[dict[str, Any]] = []
            ended = False
            started = [call for call in self.calls(reply) if call["name"] == "Agent"]
            tasks = {call["id"]: uuid.uuid4().hex[:17] for call in started}
            for call in started:
                yield self.task_started(call, tasks[call["id"]])
            for call in self.calls(reply):
                if self.interrupted or ended:
                    break
                async for item in self.run(call, None, None, tasks.get(call["id"])):
                    if isinstance(item, Outcome):
                        results.append(item.result)
                        ended = ended or item.stops
                    else:
                        yield item
            if results:
                await self.remember("user", results)
                yield UserMessage(
                    [
                        ToolResultBlock(
                            r["tool_use_id"], r["content"], r.get("is_error")
                        )
                        for r in results
                    ]
                )
            if self.interrupted:
                subtype, terminal, failed = (
                    "error_during_execution",
                    "aborted_tools",
                    True,
                )
                break
            if ended:
                terminal = "hook_stopped"
                await self.remember(
                    "assistant", [{"type": "text", "text": "No response requested."}]
                )
                break
        yield ResultMessage(
            subtype=subtype,
            duration_ms=1,
            duration_api_ms=1,
            is_error=failed,
            num_turns=self.turns,
            session_id=session,
            stop_reason=stop_reason,
            total_cost_usd=self.cost,
            result=text,
            model_usage=copy.deepcopy(self.usage),
            terminal_reason=terminal,
        )

    def offered(self, agent: str | None) -> list[str]:
        """The tools a request offers: the loop's own that are on, and the served ones, or a subagent's own list."""
        if agent is not None:
            return list(self.options.agents[agent].tools or [])
        return [*(self.options.tools or []), *self.tools]

    def ask(
        self, messages: list[dict[str, Any]], agent: str | None
    ) -> tuple[Reply, str]:
        """Make one request of the scripted model, recording it as the Messages API would have seen it."""
        loop = self.loop
        system = (
            self.options.system_prompt["prompt"]
            if agent is None
            else self.options.agents[agent].prompt
        )
        request = {
            "system": [{"type": "text", "text": system}],
            "messages": copy.deepcopy(messages),
            "tools": self.offered(agent),
            "agent": agent,
            "model": self.options.model
            if agent is None
            else self.options.agents[agent].model,
            "options": self.options,
        }
        loop.requests.append(request)
        steps = loop.steps if agent is None else loop.agent_steps.get(agent, [])
        if not steps:
            loop.ran_dry.append(request)
            raise RuntimeError(
                f"the script has no reply left for {'the agent' if agent is None else agent}"
            )
        step = steps.pop(0)
        reply = step(request) if callable(step) else step
        self.turns += 1
        model = (
            request["model"]
            if request["model"] not in (None, "inherit")
            else self.options.model
        )
        counted = self.usage.setdefault(
            model or "model", {name: 0 for name in REQUEST_TOKENS} | {"costUSD": 0.0}
        )
        for name, amount in REQUEST_TOKENS.items():
            counted[name] += amount
        counted["costUSD"] += REQUEST_COST
        self.cost += REQUEST_COST
        return reply, f"msg_{next(loop.ids):04d}"

    @staticmethod
    def calls(reply: Reply) -> list[dict[str, Any]]:
        return [block for block in reply.content if block["type"] == "tool_use"]

    async def spoken(
        self, reply: Reply, message_id: str, parent: str | None
    ) -> AsyncIterator[Any]:
        """A reply as the loop reports it: the agent's own streamed and then whole, a subagent's whole only."""
        session = self.conversation.session_id

        def stream(event: dict[str, Any]) -> StreamEvent:
            return StreamEvent(str(uuid.uuid4()), session, event)

        def whole(block: Any) -> AssistantMessage:
            return AssistantMessage(
                [block],
                self.options.model or "",
                parent_tool_use_id=parent,
                message_id=message_id,
                session_id=session,
            )

        if parent is None:
            yield stream({"type": "message_start", "message": {"id": message_id}})
        for index, block in enumerate(reply.content):
            kind = block["type"]
            if kind in ("text", "thinking"):
                words = block.get("text", block.get("thinking", ""))
                if parent is None:
                    yield stream(
                        {
                            "type": "content_block_start",
                            "index": index,
                            "content_block": {"type": kind},
                        }
                    )
                    delta = (
                        {"type": "text_delta", "text": words}
                        if kind == "text"
                        else {"type": "thinking_delta", "thinking": words}
                    )
                    yield stream(
                        {"type": "content_block_delta", "index": index, "delta": delta}
                    )
                if words:
                    yield whole(
                        TextBlock(words)
                        if kind == "text"
                        else ThinkingBlock(words, block.get("signature", ""))
                    )
                if parent is None:
                    yield stream({"type": "content_block_stop", "index": index})
            elif kind == "tool_use":
                yield whole(ToolUseBlock(block["id"], block["name"], block["input"]))
        if parent is None:
            yield stream({"type": "message_stop"})

    # One call

    async def run(
        self,
        call: dict[str, Any],
        agent_id: str | None,
        agent: str | None,
        task: str | None,
    ) -> AsyncIterator[Any]:
        """Take one call through the hooks, the permission rules, and its tool.

        Gives the messages the call produces as they happen (a subagent's
        work), and last its `Outcome`.
        """
        name, given = call["name"], call["input"]
        who = {"agent_id": agent_id, "agent_type": agent} if agent_id else {}

        def result(content: Any, failed: bool = False) -> Outcome:
            block = {
                "type": "tool_result",
                "tool_use_id": call["id"],
                "content": content,
            }
            return Outcome({**block, "is_error": True} if failed else block)

        if name not in self.offered(agent):
            yield result(f"Error: No such tool available: {name}", True)
            return
        for answer in await self.hooks(
            "PreToolUse",
            {"tool_name": name, "tool_input": given, "tool_use_id": call["id"], **who},
            call["id"],
        ):
            decided = answer.get("hookSpecificOutput", {})
            if decided.get("permissionDecision") == "deny":
                yield result(
                    f"PreToolUse:{name} hook error: {decided.get('permissionDecisionReason', '')}",
                    True,
                )
                return
        if not self.unasked(name, given):
            if self.options.can_use_tool is None:
                yield result(f"Permission to use {name} was not granted.", True)
                return
            decision = await self.options.can_use_tool(
                name,
                given,
                ToolPermissionContext(tool_use_id=call["id"], agent_id=agent_id),
            )
            if not isinstance(decision, PermissionResultAllow):
                self.interrupted = self.interrupted or decision.interrupt
                yield result(decision.message, True)
                return
        if name == "Agent":
            content, failed = None, False
            async for item in self.subagent(call, task):
                if isinstance(item, Outcome):
                    content, failed = (
                        item.result["content"],
                        bool(item.result.get("is_error")),
                    )
                else:
                    yield item
        elif name in self.tools:
            server, _, tool = name[len(PREFIX) :].partition("__")
            answer = await self.bridges[server].handle(
                {
                    "jsonrpc": "2.0",
                    "id": next(self.rpc),
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": given},
                }
            )
            content, failed = (
                answer["result"]["content"],
                bool(answer["result"].get("isError")),
            )
        else:
            content, failed = self.built_in(name, given)
        outcome = result(content, failed)
        if not failed:
            answers = await self.hooks(
                "PostToolUse",
                {
                    "tool_name": name,
                    "tool_input": given,
                    "tool_response": content,
                    "tool_use_id": call["id"],
                    **who,
                },
                call["id"],
            )
            outcome.stops = any(answer.get("continue_") is False for answer in answers)
        yield outcome

    def unasked(self, name: str, given: dict[str, Any]) -> bool:
        """Whether the permission rules let a call run without asking, as the loop's own would."""
        allowed = self.options.allowed_tools or []
        if name in allowed or name == "Agent":
            return True
        if name == "Skill":
            return given.get("skill") in (self.options.skills or [])
        if name == "Read":
            return (
                Path(self.options.cwd, given.get("file_path", ""))
                .resolve()
                .is_relative_to(Path(self.options.cwd).resolve())
            )
        return False

    def built_in(self, name: str, given: dict[str, Any]) -> tuple[Any, bool]:
        """One of the loop's own tools, as far as a test needs it."""
        if name == "Skill":
            folder = (
                Path(self.options.cwd) / ".claude" / "skills" / given.get("skill", "")
            )
            if not (folder / "SKILL.md").is_file():
                return f"Unknown skill: {given.get('skill')}", True
            body = (folder / "SKILL.md").read_text().split("\n---", 1)[-1].lstrip("-\n")
            return (
                f"Launching skill: {given['skill']}\n\nBase directory for this skill: {folder}\n\n{body}",
                False,
            )
        if name == "Read":
            path = Path(self.options.cwd, given.get("file_path", ""))
            if not path.is_file():
                return "File does not exist.", True
            return "\n".join(
                f"{number}\t{line}"
                for number, line in enumerate(path.read_text().splitlines(), 1)
            ), False
        return f"(scripted {name}: {json.dumps(given)})", False

    async def hooks(
        self, event: str, given: dict[str, Any], call_id: str | None
    ) -> list[dict[str, Any]]:
        """Run the options' hooks for one event and collect what they answer."""
        base = {
            "hook_event_name": event,
            "session_id": self.conversation.session_id,
            "cwd": str(self.options.cwd),
            "transcript_path": "",
        }
        answers = []
        for matcher in (self.options.hooks or {}).get(event, []):
            for hook in matcher.hooks:
                answers.append(await hook({**base, **given}, call_id, {"signal": None}))
        return answers

    async def stop_hooks(self, active: bool) -> str | None:
        """What the hooks at the turn's end send the model on with, or nothing where they let it end."""
        answers = await self.hooks("Stop", {"stop_hook_active": active}, None)
        return next(
            (
                answer.get("reason", "")
                for answer in answers
                if answer.get("decision") == "block"
            ),
            None,
        )

    # Subagents

    def task_started(self, call: dict[str, Any], task: str) -> TaskStartedMessage:
        given = call["input"]
        data = {
            "type": "system",
            "subtype": "task_started",
            "task_id": task,
            "tool_use_id": call["id"],
            "description": given.get("description", ""),
            "subagent_type": given.get("subagent_type"),
            "task_type": "local_agent",
            "prompt": given.get("prompt", ""),
        }
        return TaskStartedMessage(
            "task_started",
            data,
            task,
            given.get("description", ""),
            str(uuid.uuid4()),
            self.conversation.session_id,
            call["id"],
            "local_agent",
        )

    async def subagent(
        self, call: dict[str, Any], task: str | None
    ) -> AsyncIterator[Any]:
        """Run a subagent's own script to its report, reporting its task and its blocks as the loop does, then its `Outcome`."""
        given, session = call["input"], self.conversation.session_id
        agent = given.get("subagent_type")

        def outcome(content: Any, failed: bool = False) -> Outcome:
            return Outcome(
                {
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": content,
                    **({"is_error": True} if failed else {}),
                }
            )

        if agent not in (self.options.agents or {}):
            yield outcome(f"Agent type '{agent}' not found.", True)
            return
        task = task or uuid.uuid4().hex[:17]
        key = {**self.key, "subpath": f"subagents/agent-{task}"}
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": given.get("prompt", "")}
        ]
        uses, report = 0, ""
        while True:
            reply, message_id = self.ask(messages, agent)
            async for message in self.spoken(reply, message_id, call["id"]):
                yield message
            messages.append({"role": "assistant", "content": reply.content})
            report = (
                "".join(
                    block["text"] for block in reply.content if block["type"] == "text"
                )
                or report
            )
            if not self.calls(reply):
                break
            results = []
            for inner in self.calls(reply):
                uses += 1
                async for item in self.run(inner, task, agent, None):
                    if isinstance(item, Outcome):
                        results.append(item.result)
                    else:
                        yield item
                usage = {
                    "total_tokens": 120 * uses,
                    "tool_uses": uses,
                    "duration_ms": 100 * uses,
                }
                data = {
                    "type": "system",
                    "subtype": "task_progress",
                    "task_id": task,
                    "usage": usage,
                    "last_tool_name": inner["name"],
                }
                yield TaskProgressMessage(
                    "task_progress",
                    data,
                    task,
                    given.get("description", ""),
                    usage,
                    str(uuid.uuid4()),
                    session,
                    call["id"],
                    inner["name"],
                )
            messages.append({"role": "user", "content": results})
            yield UserMessage(
                [
                    ToolResultBlock(r["tool_use_id"], r["content"], r.get("is_error"))
                    for r in results
                ],
                parent_tool_use_id=call["id"],
            )
        if self.options.session_store is not None:
            entries = [
                {
                    "type": message["role"],
                    "uuid": str(uuid.uuid4()),
                    "isSidechain": True,
                    "message": message,
                }
                for message in messages
            ]
            await self.options.session_store.append(key, copy.deepcopy(entries))
        usage = {
            "total_tokens": 120 * (uses + 1),
            "tool_uses": uses,
            "duration_ms": 100 * (uses + 1),
        }
        yield TaskUpdatedMessage(
            "task_updated",
            {
                "type": "system",
                "subtype": "task_updated",
                "task_id": task,
                "patch": {"status": "completed"},
            },
            task,
            {"status": "completed"},
            "completed",
        )
        data = {
            "type": "system",
            "subtype": "task_notification",
            "task_id": task,
            "status": "completed",
            "summary": report,
            "usage": usage,
        }
        yield TaskNotificationMessage(
            "task_notification",
            data,
            task,
            "completed",
            "",
            report,
            str(uuid.uuid4()),
            session,
            call["id"],
            usage,
        )
        yield outcome(
            [
                {
                    "type": "text",
                    "text": f"[Subagent hand-back] The report follows:\n  {report}\nagentId: {task}",
                }
            ]
        )
