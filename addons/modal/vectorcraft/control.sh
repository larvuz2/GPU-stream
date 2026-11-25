#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Sends the JSON requests on standard input, one per line, to the session's
# VectorCraft over its control channel, and prints each reply on a line of its
# own, as VectorCraft wrote it:
#
#     echo '{"method": "engine.execute", "params": {"command": "document.info"}}' | selkies-modal-vectorcraft
#     {"id":null,"ok":true,"result":{...}}
#
# A request is `{"method", "params"?, "id"?}` (docs/control-protocol.md in
# VectorCraft). Each has a connection of its own, since VectorCraft closes one
# after a line it does not take as a request, which would lose the requests
# behind it.
#
# Every connection opens with the sign-in VectorCraft's channel is given on its
# main branch: an `auth` request carrying the session's
# VECTORCRAFT_CONTROL_TOKEN, read from the environment rather than the command
# line, where any process of the Sandbox could read it. The release the image
# pins, 0.24.1, has no sign-in yet and answers it as an unknown method, which
# is skipped here, so that release's channel is guarded by where it listens
# alone: the Sandbox's loopback, in a Sandbox of one person. A release that
# reads the token refuses a connection without it, and that refusal is printed
# as the request's reply.
#
# Requests wait for the session to have brought the project's documents back
# (`resume.sh` makes SELKIES_MODAL_VECTORCRAFT_READY then), since VectorCraft
# answers before they are open; `resume.sh`'s own requests, which do that work,
# say so with SELKIES_MODAL_VECTORCRAFT_RESUMING and go at once. The wait is
# bounded, so a session whose helper died still answers.
#
# The first argument is how many seconds to wait, 60 unless given: for
# VectorCraft to listen, which it does a few seconds after its window opens,
# and then for each reply. The status is 0 when every request was answered
# `ok`, 1 when one was refused (its reply says why), 2 for a line that is not a
# JSON object, which is not sent, and 124 when VectorCraft did not answer in
# time, which ends the run.
set -u

port="${VECTORCRAFT_CONTROL_PORT:?the image sets it}"
: "${VECTORCRAFT_CONTROL_TOKEN:?the session sets it}"
wait_seconds="${1:-60}"
sign_in="$(jq -cn '{id: "auth", method: "auth", params: {token: env.VECTORCRAFT_CONTROL_TOKEN}}')"

# How long a request waits for the documents to be back, at most
READY_SECONDS=30
if [ -z "${SELKIES_MODAL_VECTORCRAFT_RESUMING-}" ]; then
  ready="${SELKIES_MODAL_VECTORCRAFT_READY:?the image sets it}"
  limit=$((wait_seconds < READY_SECONDS ? wait_seconds : READY_SECONDS))
  while [ ! -e "${ready}" ] && [ "${SECONDS}" -lt "${limit}" ]; do
    sleep 0.2
  done
fi

# Signs in, sends one request, and prints the reply. Returns 0 with a reply, 3
# while VectorCraft does not listen yet, and 124 when a request that was taken
# got no reply in time.
send() {
  local signed reply
  exec 3<> "/dev/tcp/127.0.0.1/${port}" || return 3
  printf '%s\n%s\n' "${sign_in}" "$1" >&3
  if ! IFS= read -r -t "${wait_seconds}" signed <&3; then
    exec 3<&-
    return 124
  fi
  case "${signed}" in
    *'"ok":true'* | *"unknown method \`auth\`"*) ;;
    *)
      exec 3<&-
      printf '%s\n' "${signed}"
      return 0
      ;;
  esac
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
      echo "selkies-modal: VectorCraft is not ready on 127.0.0.1:${port} after ${wait_seconds} s" >&2
      exit 124
      ;;
    *)
      echo "selkies-modal: VectorCraft did not answer within ${wait_seconds} s" >&2
      exit 124
      ;;
  esac
  printf '%s\n' "${reply}"
  [ "$(jq -r '.ok' <<< "${reply}")" = "true" ] || [ "${status}" -ne 0 ] || status=1
done
exit "${status}"
