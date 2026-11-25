# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""A stand-in for the Anthropic API, for tests: a local server that answers the Messages API from a script.

The loop's real program is pointed at it (`ANTHROPIC_BASE_URL`), so a turn can
run end to end, the real SDK, the real child process, the real tools, hooks,
and session store, with only the model scripted. Each `POST /v1/messages`
takes the next scripted reply, or the reply a step makes of the request, and
is answered as the API answers: a stream of server-sent events (a message's
start, each content block's start, deltas, and stop, the message's delta and
stop), or one JSON message where the request did not ask for a stream.

The program makes requests for more than one conversation, and a script says
which it is for by what the request's system prompt contains: the agent's own
steps are scripted against a marker of its prompt, and each subagent's
against a marker of its own (`script`). A request with no tools is none of
theirs (the program summarizing a page it fetched, say) and gets a plain
answer. Every request is recorded as it was sent, body and headers, and any
other path the program asks for is recorded and answered 404, which is how a
test learns what the program needs beyond the Messages API.

A reply can be a failure (`Reply.error`), which is answered with the status
the API uses for it, and can be slowed (`Reply.delay`, between the pieces of
its text), which is how a test sees an answer while it is being written.
"""

from __future__ import annotations

import itertools
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from scripted_loop import Reply, Step

# The status and the error type the API answers each kind of failure with
FAILURES = {
    "rate_limit": (429, "rate_limit_error"),
    "overloaded": (529, "overloaded_error"),
    "server_error": (500, "api_error"),
    "authentication_failed": (401, "authentication_error"),
    "invalid_request": (400, "invalid_request_error"),
}
# How many characters of a text block one stream event carries
PIECE = 16
USAGE = {
    "input_tokens": 100,
    "output_tokens": 20,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
}


def system_text(body: dict[str, Any]) -> str:
    """A request's system prompt as one text."""
    system = body.get("system") or ""
    return (
        system
        if isinstance(system, str)
        else "\n".join(block.get("text", "") for block in system)
    )


class ScriptedAPI:
    """The Messages API on a local port, answering from scripts kept by a marker of the system prompt."""

    def __init__(self) -> None:
        self.scripts: dict[str, list[Step]] = {}
        self.requests: list[dict[str, Any]] = []
        # Requests of other paths: the method, the path, and the body where there was one
        self.others: list[tuple[str, str, Any]] = []
        # Requests the script had no reply for
        self.ran_dry: list[dict[str, Any]] = []
        self.ids = itertools.count(1)
        self.lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler())
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def script(self, marker: str, *steps: Step) -> None:
        """Add replies for the next requests whose system prompt contains `marker`."""
        self.scripts.setdefault(marker, []).extend(steps)

    def asked(self, marker: str) -> list[dict[str, Any]]:
        """The bodies of the requests made so far whose system prompt contains `marker`."""
        return [
            request["body"]
            for request in self.requests
            if marker in system_text(request["body"])
        ]

    def answer(self, body: dict[str, Any]) -> Reply:
        """The reply to one request: the next step of the script its system prompt belongs to."""
        if not body.get("tools"):
            return Reply([{"type": "text", "text": "ok"}])
        text = system_text(body)
        marker = next((marker for marker in self.scripts if marker in text), None)
        steps = self.scripts.get(marker, []) if marker is not None else []
        if not steps:
            self.ran_dry.append(body)
            return Reply([], error="server_error")
        step = steps.pop(0)
        return step(body) if callable(step) else step

    def handler(self) -> type[BaseHTTPRequestHandler]:
        api = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_: Any) -> None:
                """Nothing is printed for a request: the test reads `requests`."""

            def send_json(self, status: int, payload: dict[str, Any]) -> None:
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def event(self, name: str, data: dict[str, Any]) -> None:
                self.wfile.write(
                    f"event: {name}\ndata: {json.dumps({'type': name, **data})}\n\n".encode()
                )
                self.wfile.flush()

            def do_GET(self) -> None:
                api.others.append(("GET", self.path, None))
                self.send_json(
                    404,
                    {
                        "type": "error",
                        "error": {"type": "not_found_error", "message": "not scripted"},
                    },
                )

            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers.get("content-length", 0)))
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = {}
                if self.path.split("?")[0] != "/v1/messages":
                    api.others.append(("POST", self.path, body))
                    self.send_json(
                        404,
                        {
                            "type": "error",
                            "error": {
                                "type": "not_found_error",
                                "message": "not scripted",
                            },
                        },
                    )
                    return
                with api.lock:
                    api.requests.append(
                        {
                            "path": self.path,
                            "headers": {k.lower(): v for k, v in self.headers.items()},
                            "body": body,
                        }
                    )
                    reply = api.answer(body)
                    message_id = f"msg_{next(api.ids):06d}"
                if reply.error:
                    status, kind = FAILURES.get(reply.error, FAILURES["server_error"])
                    self.send_json(
                        status,
                        {
                            "type": "error",
                            "error": {
                                "type": kind,
                                "message": f"scripted {reply.error}",
                            },
                        },
                    )
                    return
                stop = reply.stop_reason or (
                    "tool_use"
                    if any(block["type"] == "tool_use" for block in reply.content)
                    else "end_turn"
                )
                message = {
                    "id": message_id,
                    "type": "message",
                    "role": "assistant",
                    "model": body.get("model"),
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": USAGE,
                }
                if not body.get("stream"):
                    self.send_json(
                        200, {**message, "content": reply.content, "stop_reason": stop}
                    )
                    return
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("cache-control", "no-cache")
                self.send_header("connection", "close")
                self.end_headers()
                try:
                    self.stream(reply, message, stop)
                except (BrokenPipeError, ConnectionResetError):
                    # The program closed the stream: the turn was interrupted while the answer was written
                    pass
                self.close_connection = True

            def stream(self, reply: Reply, message: dict[str, Any], stop: str) -> None:
                self.event("message_start", {"message": message})
                for index, block in enumerate(reply.content):
                    kind = block["type"]
                    if kind == "tool_use":
                        self.event(
                            "content_block_start",
                            {"index": index, "content_block": {**block, "input": {}}},
                        )
                        self.event(
                            "content_block_delta",
                            {
                                "index": index,
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": json.dumps(block["input"]),
                                },
                            },
                        )
                    elif kind in ("text", "thinking"):
                        words = block.get(kind, "")
                        empty = (
                            {"type": "text", "text": ""}
                            if kind == "text"
                            else {"type": "thinking", "thinking": "", "signature": ""}
                        )
                        self.event(
                            "content_block_start",
                            {"index": index, "content_block": empty},
                        )
                        for start in range(0, len(words), PIECE):
                            self.event(
                                "content_block_delta",
                                {
                                    "index": index,
                                    "delta": {
                                        "type": f"{kind}_delta",
                                        kind: words[start : start + PIECE],
                                    },
                                },
                            )
                            time.sleep(reply.delay)
                        if kind == "thinking":
                            self.event(
                                "content_block_delta",
                                {
                                    "index": index,
                                    "delta": {
                                        "type": "signature_delta",
                                        "signature": block.get("signature")
                                        or "c2NyaXB0ZWQ=",
                                    },
                                },
                            )
                    self.event("content_block_stop", {"index": index})
                self.event(
                    "message_delta",
                    {
                        "delta": {"stop_reason": stop, "stop_sequence": None},
                        "usage": {"output_tokens": USAGE["output_tokens"]},
                    },
                )
                self.event("message_stop", {})

        return Handler
