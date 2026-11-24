# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Serve the Unreal view's page until an editor streams there.

    python3 serve.py PORT PAGE

One page, at the root, read once at start; every other path is not found. The
answer is never cached and carries `X-Selkies-Modal-View: placeholder`, which
the page's own check looks for: once the port has another owner (`view.sh`),
the check sees an answer without it and the page reloads into what serves the
port now. It listens on every address, since Modal's proxy reaches the
Sandbox on its own interface, and the proxy admits only requests with the
view's connect token.

This is Python because the base image has it and its standard library serves
HTTP without anything installed.
"""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

VIEW_HEADER = "X-Selkies-Modal-View"


class Page(BaseHTTPRequestHandler):
    """Answers GET and HEAD for the root with the page, and anything else with 404."""

    page: bytes = b""

    def answer(self, body: bool) -> None:
        """Send the page, or a 404 for any other path, with its headers and, for GET, its body."""
        found = urlsplit(self.path).path in ("/", "/index.html")
        content = self.page if found else b"Not found\n"
        self.send_response(200 if found else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8" if found else "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(VIEW_HEADER, "placeholder")
        self.end_headers()
        if body:
            self.wfile.write(content)

    def do_GET(self) -> None:
        self.answer(body=True)

    def do_HEAD(self) -> None:
        self.answer(body=False)

    def log_message(self, message: str, *args: object) -> None:
        """Log nothing: the page's own check asks every few seconds."""


def main() -> int:
    """Serve the page on the port until stopped."""
    if len(sys.argv) != 3:
        print("usage: serve.py PORT PAGE", file=sys.stderr)
        return 2
    Page.page = Path(sys.argv[2]).read_bytes()
    server = ThreadingHTTPServer(("0.0.0.0", int(sys.argv[1])), Page)
    print(f"[unreal-view] the page is served on port {sys.argv[1]}", file=sys.stderr, flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
