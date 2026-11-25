#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Sends the JSON requests on standard input, one per line, to the session's
# PhotoCraft over its control channel, and prints each reply on a line of its
# own, as PhotoCraft wrote it:
#
#     echo '{"method": "engine.execute", "params": {"command": "doc.info"}}' | selkies-modal-photocraft
#     {"id":null,"ok":true,"result":{...}}
#
# A request is `{"method", "params"?, "id"?}` (docs/control-protocol.md in
# PhotoCraft). PhotoCraft serves a connection only once it has authenticated,
# which this does for each request by PhotoCraft's challenge: the two sides
# exchange nonces and prove to each other, by an HMAC-SHA256 over them keyed
# with the session's PHOTOCRAFT_CONTROL_TOKEN, that they hold it. The token so
# never crosses the socket, where the single `auth {token}` frame PhotoCraft
# also accepts would hand it to whatever process took the port before
# PhotoCraft did, and it is read from the environment rather than a command
# line, where any process of the Sandbox could read it. Each request has a
# connection of its own, since PhotoCraft closes one it has left idle for 30 s
# and one whose request it refused as too large, which would lose the requests
# behind it.
#
# The first argument is how many seconds to wait, 60 unless given: for
# PhotoCraft to listen, which it does a few seconds after its window opens,
# and then for each reply. The status is 0 when every request was answered
# `ok`, 1 when one was refused (its reply says why), 2 for a line that is not
# a JSON object, which is not sent, 3 when what listens on the port did not
# prove it holds the token or refused this side's proof, and 124 when
# PhotoCraft did not answer in time, which ends the run.
set -u

port="${PHOTOCRAFT_CONTROL_PORT:?the image sets it}"
: "${PHOTOCRAFT_CONTROL_TOKEN:?the session sets it}"
wait_seconds="${1:-60}"

# Prints the proof of one side of the challenge: the lowercase hex HMAC-SHA256,
# keyed with the token's 64 characters, of `<label>\n<client nonce>\n<server nonce>`.
proof() {
  printf '%s\n%s\n%s' "$1" "$2" "$3" |
    python3 -c 'import hashlib, hmac, os, sys
print(hmac.new(os.environ["PHOTOCRAFT_CONTROL_TOKEN"].encode(), sys.stdin.buffer.read(), hashlib.sha256).hexdigest())'
}

# Sends one request on a connection it authenticates first, and prints the
# reply. Returns 0 with a reply, 3 while PhotoCraft does not listen yet or
# serves as many connections as it takes, 4 when the two sides did not prove
# the token to each other, and 124 when a request that was taken got no reply
# in time.
send() {
  local nonce reply server
  exec 3<> "/dev/tcp/127.0.0.1/${port}" || return 3
  nonce="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
  printf '{"id":"challenge","method":"auth.challenge","params":{"clientNonce":"%s"}}\n' "${nonce}" >&3
  if ! IFS= read -r -t "${wait_seconds}" reply <&3; then
    exec 3<&-
    return 3
  fi
  case "${reply}" in
    *'"connection limit reached"'*)
      exec 3<&-
      return 3
      ;;
  esac
  server="$(jq -r '.result.serverNonce // empty' <<< "${reply}" 2> /dev/null)"
  if [ -z "${server}" ] ||
    [ "$(jq -r '.result.serverProof // empty' <<< "${reply}")" != "$(proof 'photocraft-control-v1 server' "${nonce}" "${server}")" ]; then
    exec 3<&-
    return 4
  fi
  printf '{"id":"auth","method":"auth","params":{"proof":"%s"}}\n' "$(proof 'photocraft-control-v1 client' "${nonce}" "${server}")" >&3
  if ! IFS= read -r -t "${wait_seconds}" reply <&3 || [ "$(jq -r '.result.authenticated' <<< "${reply}" 2> /dev/null)" != "true" ]; then
    exec 3<&-
    return 4
  fi
  printf '%s\n' "$1" >&3
  if ! IFS= read -r -t "${wait_seconds}" reply <&3; then
    exec 3<&-
    return 124
  fi
  exec 3<&-
  printf '%s\n' "${reply}"
}

status=0
while IFS= read -r line || [ -n "${line}" ]; do
  [ -n "${line//[[:space:]]/}" ] || continue
  if ! request="$(jq -ec 'if type == "object" then . else error end' <<< "${line}" 2> /dev/null)"; then
    jq -cn --arg line "${line}" '{ok: false, error: "not a JSON object, so not sent: \($line)"}'
    status=2
    continue
  fi
  deadline=$((SECONDS + wait_seconds))
  while :; do
    reply="$(send "${request}" 2> /dev/null)"
    sent=$?
    [ "${sent}" -eq 3 ] && [ "${SECONDS}" -lt "${deadline}" ] || break
    sleep 0.5
  done
  case "${sent}" in
    0) ;;
    3)
      echo "selkies-modal: PhotoCraft is not ready on 127.0.0.1:${port} after ${wait_seconds} s" >&2
      exit 124
      ;;
    4)
      echo "selkies-modal: what listens on 127.0.0.1:${port} did not authenticate as this session's PhotoCraft" >&2
      exit 3
      ;;
    *)
      echo "selkies-modal: PhotoCraft did not answer within ${wait_seconds} s" >&2
      exit 124
      ;;
  esac
  printf '%s\n' "${reply}"
  [ "$(jq -r '.ok' <<< "${reply}")" = "true" ] || [ "${status}" -ne 0 ] || status=1
done
exit "${status}"
