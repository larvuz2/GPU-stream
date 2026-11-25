#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Has the session's CADCraft save every drawing with unsaved changes, run as
# the session ends (session.sh), by the idle timeout or `down`, so that the
# next session on the project folder opens the work as it was left.
#
# CADCraft keeps unsaved changes only as the autosave it writes every SAVETIME
# minutes, which its next start offers for recovery as a drawing without a
# file name; whatever was drawn since the last one would go with the Sandbox.
# Saving is what loses nothing: a drawing with a file is saved to it, CADCraft
# keeping the file's previous contents beside it as `<name>.bak` (its ISAVEBAK),
# which is the way back for a person who did not mean to keep the changes, and
# a drawing never saved goes into the project folder under its title
# (`Drawing2.dxf`), or that title and the time where such a file exists. The
# drawing that was in front is left the newest file, which is the one the next
# session opens (`cadcraft/autostart`).
#
# Prints one line per drawing saved. The status is 0 when every one was, and
# the control client's otherwise (`cadcraft/control.sh`).
set -u

folder="$(selkies-modal-project)" || exit 1

# Sends one request and prints its result; CADCraft is up, so the wait is short.
ask() {
  local reply
  reply="$(selkies-modal-cadcraft 5 <<< "$1")" || return
  jq -c '.result' <<< "${reply}"
}

# Runs one command with its JSON parameters.
run() {
  ask "$(jq -cn --arg command "$1" --argjson params "$2" '{method: "engine.execute", params: {command: $command, params: $params}}')"
}

documents="$(ask '{"method": "ui.inspect"}')" || exit
status=0
front=""
while IFS= read -r document; do
  index="$(jq -r '.index' <<< "${document}")"
  path="$(jq -r '.path // empty' <<< "${document}")"
  run document.switch "{\"index\": ${index}}" > /dev/null || status=$?
  if [ -n "${path}" ]; then
    run qsave '{}' > /dev/null || status=$?
  else
    path="${folder}/$(jq -r '.title' <<< "${document}" | tr -c 'A-Za-z0-9._\n-' '_').dxf"
    [ ! -e "${path}" ] || path="${path%.dxf}-$(date +%Y%m%d-%H%M%S).dxf"
    run saveas "$(jq -cn --arg path "${path}" '{path: $path}')" > /dev/null || status=$?
  fi
  echo "selkies-modal: kept ${path}"
  [ "$(jq -r '.active' <<< "${document}")" != "true" ] || front="${path}"
done < <(jq -c '.session.documents[] | select(.dirty)' <<< "${documents}")
[ -z "${front}" ] || touch "${front}"
exit "${status}"
