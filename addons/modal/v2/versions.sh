#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Puts the versions page of a v2 project on the session's screen, installed as
# /usr/local/bin/v2-versions:
#
#     v2-versions DIR [PORT]    serve the versions of the project in DIR and show them
#     v2-versions --stop        close the browser and stop the server
#
# The page is v2's own (`v2 diff`): every saved version to watch, two side by
# side to compare, and comments left at a moment of the video, which
# `v2 comments` then lists for the agent. v2 serves it on the machine's
# loopback only and answers no request named for another host, so it is
# reached from the session's own browser and from nowhere else. This command
# starts that server in the background, where it outlives the command, waits
# until it answers with the project's versions, and shows it in the session's
# one browser window (`selkies-modal-kiosk`, hyperframes/kiosk.sh), which
# fills the screen: the person watching the engine sees the versions and marks
# what to change.
#
# One project's versions are served at a time: starting again ends the server
# that was running and starts one for DIR, on PORT (3010 unless given). A
# version saved while the page is open appears when the page is loaded again,
# which showing it again does. The window is taken from whatever page had it,
# as a HyperFrames preview takes it from this one; `--stop` ends the server
# and closes the window only while it still shows the versions.
#
# The server's process ID is only believed while it names v2's own program.
# What the server prints is kept in /tmp/selkies-modal/v2-versions.log, and
# where it ends before answering (a folder that is no v2 project, a port
# another program holds) its own words are this command's error, and the
# window is closed if it showed the versions that are no longer served. Where
# the browser cannot show the page, the server is ended again, so a command
# that failed leaves nothing running.

set -u

PROGRAM="/opt/v2/bin/v2"
STATE="/tmp/selkies-modal"
PID_FILE="${STATE}/v2-versions.pid"
LOG="${STATE}/v2-versions.log"

# The process ID of the server this command started, where it still runs.
server() {
  local pid
  pid="$(cat "${PID_FILE}" 2> /dev/null)" || return 1
  [ "$(readlink "/proc/${pid}/exe" 2> /dev/null)" = "${PROGRAM}" ] || return 1
  echo "${pid}"
}

# Ends that server and returns once it is gone, so the port is free for the next.
stop_server() {
  local pid
  pid="$(server)" || {
    rm -f "${PID_FILE}"
    return 0
  }
  kill "${pid}" 2> /dev/null
  for _ in $(seq 1 50); do
    kill -0 "${pid}" 2> /dev/null || break
    sleep 0.1
  done
  kill -KILL "${pid}" 2> /dev/null
  rm -f "${PID_FILE}"
}

if [ "${1-}" = "--stop" ]; then
  selkies-modal-kiosk v2-versions --close
  stop_server
  exit 0
fi

# The server itself, as this script starts it detached below: its process ID is kept for stop_server
if [ "${1-}" = "--serve" ]; then
  echo "$$" > "${PID_FILE}"
  cd "$2" && exec v2 diff --no-open --port "$3"
  exit 1
fi

dir="${1:?usage: v2-versions DIR [PORT] | --stop}"
port="${2:-3010}"
[ -d "${dir}" ] || {
  echo "v2-versions: no such project folder: ${dir}" >&2
  exit 1
}
dir="$(cd "${dir}" && pwd)"
url="http://127.0.0.1:${port}"

stop_server
mkdir -p "${STATE}"
setsid -f "$0" --serve "${dir}" "${port}" > "${LOG}" 2>&1 < /dev/null

# The server has to run both before and after the answer: one that found the port held by another program ends
# at once, and the page answering there is that program's
answered=""
for _ in $(seq 1 150); do
  pid="$(cat "${PID_FILE}" 2> /dev/null)"
  if [ -n "${pid}" ]; then
    kill -0 "${pid}" 2> /dev/null || break
    if server > /dev/null && curl -fsS -o /dev/null -m 2 "${url}/api/versions" 2> /dev/null && server > /dev/null; then
      answered=1
      break
    fi
  fi
  sleep 0.2
done
[ -n "${answered}" ] || {
  echo "v2-versions: the versions page did not answer at ${url}; v2 said:" >&2
  tail -n 5 "${LOG}" >&2
  stop_server
  selkies-modal-kiosk v2-versions --close
  exit 1
}

selkies-modal-kiosk v2-versions "${url}/" || {
  stop_server
  exit 1
}
echo "versions of ${dir} at ${url}, shown on the session's screen"
