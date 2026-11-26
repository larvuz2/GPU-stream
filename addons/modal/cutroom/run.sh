#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# The one way to run a script of the Cut Room, from any directory, installed
# as /usr/local/bin/cutroom:
#
#     cutroom                       lists the scripts, each with its first line
#     cutroom NAME --help           a script's own usage
#     cutroom NAME [ARGUMENTS...]   runs /opt/cutroom/scripts/NAME.py
#     cutroom versions              what the image holds, each part with its source and checksum
#
# A script runs with the image's own Python environment (/opt/cutroom/venv) in
# the session's project folder (`craft/project.sh`), whatever directory the
# caller is in, so every path a recipe gives is relative to that folder and
# what a script writes is where the project's other engines look. CUTROOM_HOME
# names another folder to work in.
#
# Each run is also written to the session's log, the command first and then
# what it printed, which is what the session's screen shows (autostart): a
# person watching the engine sees what the agent is running. The exit status
# is the script's own.

set -u -o pipefail

HOME_DIR="/opt/cutroom"
LOG="${CUTROOM_LOG:-/tmp/selkies-modal/cutroom.log}"

list() {
  echo "usage: cutroom NAME [ARGUMENTS...]   (cutroom NAME --help for one script; cutroom versions for the image)"
  for script in "${HOME_DIR}"/scripts/*.py; do
    name="$(basename "${script}" .py)"
    # What the scripts share is a module, not a command
    [ "${name}" = common ] && continue
    # The summary is the first line of the module docstring, which follows the license header
    summary="$(sed -n 's/^"""\(.*\)$/\1/p' "${script}" | head -n 1)"
    printf '  %-10s %s\n' "${name}" "${summary%\"\"\"}"
  done
}

case "${1-}" in
  '' | -h | --help | help)
    list
    exit 0
    ;;
  versions)
    cat "${HOME_DIR}/provenance.txt"
    exit 0
    ;;
esac

name="$1"
shift
script="${HOME_DIR}/scripts/${name}.py"
case "${name}" in
  *[!a-z_]* | common) script="" ;;
esac
if [ -z "${script}" ] || [ ! -f "${script}" ]; then
  echo "cutroom: no script named ${name}" >&2
  list >&2
  exit 2
fi

folder="${CUTROOM_HOME:-$(selkies-modal-project)}" || exit 1
cd "${folder}" || exit 1

mkdir -p "$(dirname "${LOG}")" 2> /dev/null
if ! { printf '\n$ cutroom %s %s\n' "${name}" "$*" >> "${LOG}"; } 2> /dev/null; then
  exec "${HOME_DIR}/venv/bin/python" "${script}" "$@"
fi
PYTHONUNBUFFERED=1 "${HOME_DIR}/venv/bin/python" "${script}" "$@" 2>&1 | tee -a "${LOG}"
status="${PIPESTATUS[0]}"
printf '[exit %s]\n' "${status}" >> "${LOG}"
exit "${status}"
