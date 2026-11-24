#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Print the ICE server a browser reaches a Modal session's TURN relay through, with credentials of its own.

The credentials are the TURN REST scheme's, which coturn checks with the
session's secret alone (`use-auth-secret` in `turnserver.conf`): the user name
holds the second the credential expires, and the password is that name signed
with the secret (HMAC-SHA1, base64). Each call mints a new pair and nothing
records it, so whatever hands one to a page (a signalling server, the
launcher) mints it when the page asks, and the secret never leaves the
Sandbox. coturn checks the expiry on every request an allocation makes,
refreshes included, so a page's credential has to outlast the time the page
stays connected; the default is the longest a Sandbox runs.

The address is the public host and port Modal gives the relay's TCP port
(`tcp_address` in `sandbox.py`), which only the launcher can ask Modal for;
the relay is reached over TCP alone, so the URL says so.

Run inside the Sandbox, where `SELKIES_MODAL_TURN_SECRET` is:

    selkies-modal-turn-credentials r123.modal.host:41234 --ttl 3600

prints `{"urls": ["turn:r123.modal.host:41234?transport=tcp"], "username": ..., "credential": ...}`,
an entry of `RTCConfiguration.iceServers` as it stands.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time

DAY = 24 * 3600


def credentials(secret: str, address: str, ttl: int) -> dict[str, object]:
    """The ICE server entry for the relay at `address`, valid for `ttl` seconds from now."""
    username = f"{int(time.time()) + ttl}:selkies-modal"
    password = base64.b64encode(hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()).decode()
    return {"urls": [f"turn:{address}?transport=tcp"], "username": username, "credential": password}


def main() -> int:
    """Parse the command line and print one ICE server entry as JSON."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("address", help="the relay's public HOST:PORT, as Modal exposes its TCP port")
    parser.add_argument("--ttl", type=int, default=DAY, help="seconds the credential stays valid (default: %(default)s)")
    args = parser.parse_args()
    secret = os.environ.get("SELKIES_MODAL_TURN_SECRET")
    if not secret:
        print("selkies-modal-turn-credentials: SELKIES_MODAL_TURN_SECRET is not set", file=sys.stderr)
        return 1
    print(json.dumps(credentials(secret, args.address, args.ttl)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
