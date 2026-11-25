#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Sends the JSON requests on standard input, one per line, to the session's
# CADCraft over its control channel, and prints each reply on a line of its
# own, as CADCraft wrote it:
#
#     echo '{"method": "cmdline.input", "params": {"text": "circle 0,0 5"}}' | selkies-modal-cadcraft
#     {"id":null,"ok":true,"result":{...}}
#
# A request is `{"method", "params"?, "id"?}` (docs/control-protocol.md in
# CADCraft); this adds the session's token to each. CADCraft makes that token
# itself each time it starts and writes it to a file only the session's user
# reads, `cadcraft-control-<port>.token` in the runtime directory, so it is
# read from there for every request, never held in the environment or on a
# command line, and a CADCraft the window manager restarted is reached with
# its new one. Each request has a connection of its own, since CADCraft closes
# one after a line it cannot read, which would lose the requests behind it.
#
# The first argument is how many seconds to wait, 60 unless given: for
# CADCraft to write its token and listen, which it does as its window opens,
# and then for each reply. The status is 0 when every request was answered
# `ok`, 1 when one was refused (its reply says why), 2 for a line that is not a
# JSON object, which is not sent, and 124 when CADCraft did not answer in time,
# which ends the run.
set -u

port="${CADCRAFT_CONTROL_PORT:?the image sets it}"
token_file="${XDG_RUNTIME_DIR:-${HOME}/.cache}/cadcraft-control-${port}.token"
wait_seconds="${1:-60}"

# Sends one request and prints the reply. Returns 0 with a reply, 3 while
# CADCraft has no token yet or does not listen, and 124 when a request that was
# taken got no reply in time.
send() {
  local request reply
  request="$(jq -ec --rawfile token "${token_file}" '. + {token: ($token | rtrimstr("\n"))}' <<< "$1")" || return 3
  exec 3<> "/dev/tcp/127.0.0.1/${port}" || return 3
  printf '%s\n' "${request}" >&3
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
  if ! jq -e 'type == "object"' <<< "${line}" > /dev/null 2>&1; then
    jq -cn --arg line "${line}" '{ok: false, error: "not a JSON object, so not sent: \($line)"}'
    status=2
    continue
  fi
  deadline=$((SECONDS + wait_seconds))
  while :; do
    reply="$(send "${line}" 2> /dev/null)"
    sent=$?
    [ "${sent}" -eq 3 ] && [ "${SECONDS}" -lt "${deadline}" ] || break
    sleep 0.5
  done
  case "${sent}" in
    0) ;;
    3)
      echo "selkies-modal: CADCraft is not ready on 127.0.0.1:${port} after ${wait_seconds} s" >&2
      exit 124
      ;;
    *)
      echo "selkies-modal: CADCraft did not answer within ${wait_seconds} s" >&2
      exit 124
      ;;
  esac
  printf '%s\n' "${reply}"
  [ "$(jq -r '.ok' <<< "${reply}")" = "true" ] || [ "${status}" -ne 0 ] || status=1
done
exit "${status}"
