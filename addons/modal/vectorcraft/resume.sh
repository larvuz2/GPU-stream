#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Brings a project's VectorCraft work back when a session starts, and keeps it
# for the next one while the session runs. Started by the autostart beside
# VectorCraft, with VectorCraft's process ID and the project folder:
#
#     selkies-modal-vectorcraft-resume <pid> <folder> &
#
# VectorCraft has no option that reopens what the last session had: it keeps
# recovery copies of modified documents in its data folder (`Data Recovery`,
# in the project folder here) and offers them in a dialog at its next start,
# as after a crash. So, over the control channel (`control.sh`), once
# VectorCraft answers:
#
# 1. The recovery dialog, where it is open, is confirmed, which opens every
#    copy as a modified document named "<name> [Recovered]". A recovered
#    document has no file of its own until it is saved to one.
# 2. The newest `.vectorcraft` document in the project folder is opened,
#    unless a recovered copy is that document with its unsaved changes, which
#    then stands in for it.
# 3. SELKIES_MODAL_VECTORCRAFT_READY is made, the file `control.sh` holds
#    everyone else's requests for: VectorCraft answers a second or more before
#    its documents are back, and a caller that asked then would take a project
#    with work in it for an empty one.
# 4. Every SAVE_INTERVAL seconds VectorCraft is asked for a recovery copy of
#    each document that changed since its last one. Left alone it writes them
#    every two minutes, and a Sandbox does not end by quitting it: the idle
#    timeout, `down`, and the Sandbox's lifetime all end the process where it
#    stands, so what is on the Volume at that moment is what comes back. Asking
#    costs nothing while no document has changed, and does not count as use of
#    the session.
#
# The loop ends with the VectorCraft it was started for, so one the window
# manager starts again gets a helper of its own.
set -u

SAVE_INTERVAL=10

pid="$1"
folder="$2"
ready="${SELKIES_MODAL_VECTORCRAFT_READY:?the image sets it}"
# This script's own requests are the ones that do not wait for the file it makes
export SELKIES_MODAL_VECTORCRAFT_RESUMING=1

# Sends one request and prints the reply, waiting up to $2 seconds (60).
call() {
  printf '%s\n' "$1" | selkies-modal-vectorcraft "${2:-60}" 2> /dev/null
}

if state="$(call '{"method": "ui.inspect"}' 120)"; then
  recovered=""
  if [ "$(jq -r '.result.ui.dialog.kind // empty' <<< "${state}")" = "recovery" ]; then
    # A copy names its document as it was saved, which may be relative to the folder
    recovered="$(call '{"method": "ui.dialog.confirm"}' | jq -r '.result[]?.restored[]?.path // empty' |
      while IFS= read -r path; do (cd "${folder}" && realpath -m -- "${path}"); done)"
  fi

  newest="$(find "${folder}" -maxdepth 1 -name '*.vectorcraft' -type f -printf '%T@ %p\n' 2> /dev/null | sort -rn | head -n 1 | cut -d ' ' -f 2-)"
  if [ -n "${newest}" ] && ! grep -Fxq -- "$(realpath -m -- "${newest}")" <<< "${recovered}"; then
    call "$(jq -cn --arg path "${newest}" '{method: "app.open", params: {path: $path}}')" > /dev/null
  fi
fi
: > "${ready}"

while kill -0 "${pid}" 2> /dev/null; do
  sleep "${SAVE_INTERVAL}"
  call '{"method": "engine.execute", "params": {"command": "file.recovery.save"}}' 20 > /dev/null
done
