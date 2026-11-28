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
# background after this command returns. What shows it is the session's one
# browser window (`selkies-modal-kiosk`, kiosk.sh), which fills the screen:
# the person watching the engine sees the composition and its timeline while
# the agent edits the files.
#
# One preview is shown at a time: starting one stops the preview that was
# running, since the CLI refuses a port another preview holds rather than
# moving it, and takes the browser window from whatever page had it, another
# preview or the versions page of v2 (v2/versions.sh). A preview whose window
# another page took keeps serving until the next one starts or `--stop`, and
# `--stop` closes the window only while it still shows a preview.

set -u

if [ "${1-}" = "--stop" ]; then
  selkies-modal-kiosk hyperframes-preview --close
  hyperframes preview --kill-all
  exit $?
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

selkies-modal-kiosk hyperframes-preview "${url}" || exit 1
echo "preview of ${dir} at ${url}, shown on the session's screen"
