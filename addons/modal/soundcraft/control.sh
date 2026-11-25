#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Sends the JSON requests on standard input, one per line, to the session's
# SoundCraft over its control channel, and prints each reply on a line of its
# own, as SoundCraft wrote it:
#
#     echo '{"method": "engine.execute", "params": {"command": "session.inspect"}}' | selkies-modal-soundcraft
#     {"id":null,"ok":true,"result":{...}}
#
# A request is `{"method", "params"?, "id"?}` (docs/control-protocol.md in
# SoundCraft). SoundCraft's channel takes no token: it listens on the
# Sandbox's loopback alone and answers whatever reaches it there, so what
# keeps it to the session is that nothing outside the Sandbox reaches that
# address. Each request has a connection of its own, since SoundCraft closes
# one after a line it does not take as a request, which would lose the
# requests behind it.
#
# The first argument is how many seconds to wait, 60 unless given: for
# SoundCraft to listen, which it does as its window opens, and then for each
# reply. The status is 0 when every request was answered `ok`, 1 when one was
# refused (its reply says why), 2 for a line that is not a JSON object, which
# is not sent, and 124 when SoundCraft did not answer in time, which ends the
# run.
set -u

port="${SOUNDCRAFT_CONTROL_PORT:?the image sets it}"
wait_seconds="${1:-60}"

# Sends one request and prints the reply. Returns 0 with a reply, 3 while
# SoundCraft does not listen yet, and 124 when a request that was taken got no
# reply in time.
send() {
  local reply
  exec 3<> "/dev/tcp/127.0.0.1/${port}" || return 3
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
      echo "selkies-modal: SoundCraft is not ready on 127.0.0.1:${port} after ${wait_seconds} s" >&2
      exit 124
      ;;
    *)
      echo "selkies-modal: SoundCraft did not answer within ${wait_seconds} s" >&2
      exit 124
      ;;
  esac
  printf '%s\n' "${reply}"
  [ "$(jq -r '.ok' <<< "${reply}")" = "true" ] || [ "${status}" -ne 0 ] || status=1
done
exit "${status}"
