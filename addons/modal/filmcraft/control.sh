#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Sends the JSON requests on standard input, one per line, to the session's
# FilmCraft over its control channel, and prints each reply on a line of its
# own, as FilmCraft wrote it:
#
#     echo '{"method": "engine.execute", "params": {"command": "sequence.inspect"}}' | selkies-modal-filmcraft
#     {"id":null,"ok":true,"result":{...}}
#
# A request is `{"method", "params"?, "id"?}` (docs/control-protocol.md in
# FilmCraft); this adds the session's FILMCRAFT_CONTROL_TOKEN to each, read
# from the environment rather than the command line, where any process of the
# Sandbox could read it. Each request has a connection of its own, since
# FilmCraft closes one after refusing a request, which would lose the requests
# behind it.
#
# The first argument is how many seconds to wait, 60 unless given: for
# FilmCraft to listen and be ready, which it is a few seconds after its window
# opens, and then for each reply. The status is 0 when every request was
# answered `ok`, 1 when one was refused (its reply says why), 2 for a line that
# is not a JSON object, which is not sent, and 124 when FilmCraft did not
# answer in time, which ends the run.
set -u

port="${FILMCRAFT_CONTROL_PORT:?the image sets it}"
: "${FILMCRAFT_CONTROL_TOKEN:?the session sets it}"
wait_seconds="${1:-60}"

# Sends one request and prints the reply. Returns 0 with a reply, 3 while
# FilmCraft does not listen yet or is still starting, and 124 when a request
# that was taken got no reply in time.
send() {
  local reply
  exec 3<> "/dev/tcp/127.0.0.1/${port}" || return 3
  printf '%s\n' "$1" >&3
  if ! IFS= read -r -t "${wait_seconds}" reply <&3; then
    exec 3<&-
    return 124
  fi
  exec 3<&-
  case "${reply}" in
    *'"FilmCraft is still starting; send the request again"'*) return 3 ;;
  esac
  printf '%s\n' "${reply}"
}

status=0
while IFS= read -r line || [ -n "${line}" ]; do
  [ -n "${line//[[:space:]]/}" ] || continue
  if ! request="$(jq -ec 'if type == "object" then . + {token: env.FILMCRAFT_CONTROL_TOKEN} else error end' <<< "${line}" 2> /dev/null)"; then
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
      echo "selkies-modal: FilmCraft is not ready on 127.0.0.1:${port} after ${wait_seconds} s" >&2
      exit 124
      ;;
    *)
      echo "selkies-modal: FilmCraft did not answer within ${wait_seconds} s" >&2
      exit 124
      ;;
  esac
  printf '%s\n' "${reply}"
  [ "$(jq -r '.ok' <<< "${reply}")" = "true" ] || [ "${status}" -ne 0 ] || status=1
done
exit "${status}"
