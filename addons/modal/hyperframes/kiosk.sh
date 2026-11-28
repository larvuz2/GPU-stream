#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Shows one web page on the session's screen, installed as
# /usr/local/bin/selkies-modal-kiosk:
#
#     selkies-modal-kiosk NAME URL        show URL, in place of whatever page was shown
#     selkies-modal-kiosk NAME --close    close the window, if NAME is who opened it
#
# The page is one the session serves to itself: a HyperFrames project's live
# preview (preview.sh), or the versions page of v2 (v2/versions.sh). Each
# command that shows one names itself, and the session has one browser window,
# which belongs to whoever asked last: showing a page ends the browser that
# showed the one before and starts another on the new page, so two commands
# never put two windows on the screen, and `--close` from a command whose page
# was replaced closes nothing, so stopping one page does not take another off
# the screen.
#
# The browser is Chrome for Testing (hyperframes/install.sh), opened as one
# window with no browser chrome on the session's display, which the window
# manager makes fill the screen. Chrome keeps its own sandbox: a Modal Sandbox
# lets the session's user make the user namespaces it is built on, so no flag
# turns it off here. `--kiosk` shows the page with no window frame or address
# bar. The line a Chrome for Testing puts over every window to say what it is
# stays: no flag removes it.
#
# The browser that was showing is gone before the next one starts, since both
# keep one profile, a folder of the session's own that goes with it, and a
# Chrome that finds another still holding its profile hands that one the page
# and exits. Its process ID is only believed while it names that Chrome. A
# browser with no display to open on, as when the command is run outside the
# session's environment (`selkies-modal-run`), ends at once, so the new one is
# watched for half a second and its failure is the command's.

set -u

CHROME="/opt/hyperframes/chrome/chrome"
STATE="/tmp/selkies-modal"
PID_FILE="${STATE}/kiosk.pid"
OWNER_FILE="${STATE}/kiosk.owner"
PROFILE="${STATE}/kiosk-profile"

# Ends the browser this command started, if it still runs, and returns once it is gone.
close_browser() {
  local pid
  pid="$(cat "${PID_FILE}" 2> /dev/null)" || return 0
  rm -f "${PID_FILE}" "${OWNER_FILE}"
  [ "$(readlink "/proc/${pid}/exe" 2> /dev/null)" = "${CHROME}" ] || return 0
  kill "${pid}" 2> /dev/null
  for _ in $(seq 1 50); do
    kill -0 "${pid}" 2> /dev/null || return 0
    sleep 0.1
  done
  kill -KILL "${pid}" 2> /dev/null
}

# The browser itself, as this script starts it detached below: its process ID is kept for close_browser
if [ "${1-}" = "--browser" ]; then
  echo "$$" > "${PID_FILE}"
  exec "${CHROME}" --no-first-run --no-default-browser-check --user-data-dir="${PROFILE}" --kiosk --app="$2"
fi

name="${1:?usage: selkies-modal-kiosk NAME URL | NAME --close}"
page="${2:?usage: selkies-modal-kiosk NAME URL | NAME --close}"

if [ "${page}" = "--close" ]; then
  [ "$(cat "${OWNER_FILE}" 2> /dev/null)" = "${name}" ] && close_browser
  exit 0
fi

close_browser
mkdir -p "${STATE}"
echo "${name}" > "${OWNER_FILE}"
setsid -f "$0" --browser "${page}" > "${STATE}/kiosk.log" 2>&1 < /dev/null
for _ in $(seq 1 50); do
  [ -s "${PID_FILE}" ] && break
  sleep 0.1
done
pid="$(cat "${PID_FILE}" 2> /dev/null)"
for _ in $(seq 1 5); do
  sleep 0.1
  if [ -z "${pid}" ] || ! kill -0 "${pid}" 2> /dev/null; then
    echo "selkies-modal-kiosk: the browser did not stay open; it said:" >&2
    tail -n 5 "${STATE}/kiosk.log" >&2
    rm -f "${PID_FILE}" "${OWNER_FILE}"
    exit 1
  fi
done
