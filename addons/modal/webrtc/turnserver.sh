#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Runs a Modal session's TURN relay, for a WebRTC stream from inside the
# Sandbox to a browser outside it.
#
# Modal's HTTPS proxy carries HTTP and WebSockets, not the UDP WebRTC media
# travels on, but it also exposes raw TCP ports (`unencrypted_ports`). A
# browser told to use only this relay, over TCP (`?transport=tcp`,
# `iceTransportPolicy: "relay"`), sends its media down that TCP connection, and
# coturn hands it on over UDP to the WebRTC peer in the same Sandbox, whose
# host candidates are the Sandbox's own addresses. So the peer needs no TURN
# configuration of its own, and the relay reaches nothing but those addresses.
#
# The configuration is `turnserver.conf` with what only the running Sandbox
# knows appended: the session's secret, its IPv4 addresses (the address the
# relay allocates on, and the only peers it relays to), and its ports. That
# file is written where only this user reads it, so the secret is on no
# command line. A browser's credentials are minted from the same secret
# (`turn-credentials.py`).
#
# At start, each of coturn's relay threads prints `socket: Invalid argument` a
# few times: coturn opens SCTP listeners beside its TCP ones, with no option to
# leave them out, and gVisor has no SCTP. Nothing else is affected.
#
# Environment:
#   SELKIES_MODAL_TURN_SECRET    the session's secret (`start_session` makes one)
#   SELKIES_MODAL_TURN_PORT      the TCP port to listen on, the one Modal exposes (3478)
#   SELKIES_MODAL_TURN_MIN_PORT  the first UDP port of the relay's range (49152)
#   SELKIES_MODAL_TURN_MAX_PORT  the last (49183): a port for each allocation the quota allows

set -eu

say() {
  echo "selkies-modal-turnserver: $*" >&2
}

conf=/usr/local/share/selkies-modal/webrtc/turnserver.conf
runtime="${XDG_RUNTIME_DIR:-/tmp}/selkies-modal-turn"

if [ -z "${SELKIES_MODAL_TURN_SECRET-}" ]; then
  say "SELKIES_MODAL_TURN_SECRET is not set, and the relay takes no credential without it"
  exit 1
fi

# IPv4 only: a browser's relay allocation is IPv4, and a TURN relay reaches no
# peer of the other family.
set --
for address in $(hostname -I); do
  case "${address}" in
    *:* | 127.*) ;;
    *) set -- "$@" "${address}" ;;
  esac
done
if [ "$#" -eq 0 ]; then
  say "the Sandbox has no IPv4 address to relay on"
  exit 1
fi

umask 077
mkdir -p "${runtime}"
{
  cat "${conf}"
  echo "listening-port=${SELKIES_MODAL_TURN_PORT:-3478}"
  echo "min-port=${SELKIES_MODAL_TURN_MIN_PORT:-49152}"
  echo "max-port=${SELKIES_MODAL_TURN_MAX_PORT:-49183}"
  echo "relay-ip=$1"
  for address in "$@"; do
    echo "allowed-peer-ip=${address}"
  done
  echo "static-auth-secret=${SELKIES_MODAL_TURN_SECRET}"
  echo "userdb=${runtime}/turndb"
  echo "pidfile=${runtime}/turnserver.pid"
} > "${runtime}/turnserver.conf"

say "relaying on $1, to$(printf ' %s' "$@") only, from TCP port ${SELKIES_MODAL_TURN_PORT:-3478}"
exec turnserver -c "${runtime}/turnserver.conf"
