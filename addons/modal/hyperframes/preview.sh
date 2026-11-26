#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Puts a HyperFrames project's live preview on the session's screen, installed
# as /usr/local/bin/hyperframes-preview:
#
#     hyperframes-preview DIR [PORT]    start the preview of the project in DIR and show it
#     hyperframes-preview --stop        close the browser and stop every preview
#
# The preview is the CLI's own studio (`hyperframes preview`), a local web
# server that reloads the composition as its files change, kept running in the
# background after this command returns. What shows it is Chrome for Testing,
# opened as one window with no browser chrome on the session's display, which
# the window manager makes fill the screen: the person watching the engine sees
# the composition and its timeline while the agent edits the files.
#
# Chrome keeps its own sandbox: a Modal Sandbox lets the session's user make
# the user namespaces it is built on, so no flag turns it off here. `--kiosk`
# shows the page with no window frame or address bar. The line a Chrome for
# Testing puts over every window to say what it is stays: no flag removes it.
#
# One preview is shown at a time: starting one stops the preview that was
# running, since the CLI refuses a port another preview holds rather than
# moving it, and replaces the browser window. The browser's profile is a
# folder of the session's own and goes with it.

set -u

CHROME="/opt/hyperframes/chrome/chrome"
STATE="/tmp/selkies-modal"
PID_FILE="${STATE}/hyperframes-preview.pid"
PROFILE="${STATE}/hyperframes-preview-profile"

close_browser() {
  [ -f "${PID_FILE}" ] || return 0
  kill "$(cat "${PID_FILE}")" 2> /dev/null
  rm -f "${PID_FILE}"
}

if [ "${1-}" = "--stop" ]; then
  close_browser
  hyperframes preview --kill-all
  exit $?
fi

# The browser itself, as this script starts it detached below: its process ID is kept for close_browser
if [ "${1-}" = "--browser" ]; then
  echo "$$" > "${PID_FILE}"
  exec "${CHROME}" --no-first-run --no-default-browser-check --user-data-dir="${PROFILE}" --kiosk --app="$2"
fi

dir="${1:?usage: hyperframes-preview DIR [PORT] | --stop}"
port="${2:-3002}"
[ -d "${dir}" ] || {
  echo "hyperframes-preview: no such project folder: ${dir}" >&2
  exit 1
}
# The folder as the machine resolves it, which is how the CLI names a project given by a relative path, so that
# `hyperframes preview DIR --status` finds this preview from the project folder
dir="$(cd "${dir}" && pwd -P)"
url="http://127.0.0.1:${port}"

hyperframes preview --kill-all > /dev/null 2>&1
hyperframes preview "${dir}" --port "${port}" --background --no-open || exit 1
for _ in $(seq 1 60); do
  curl -fsS -o /dev/null -m 2 "${url}/" 2> /dev/null && break
  sleep 0.5
done
curl -fsS -o /dev/null -m 2 "${url}/" || {
  echo "hyperframes-preview: the preview did not answer at ${url}" >&2
  exit 1
}

close_browser
mkdir -p "${STATE}"
setsid -f "$0" --browser "${url}" > "${STATE}/hyperframes-preview.log" 2>&1
echo "preview of ${dir} at ${url}, shown on the session's screen"
