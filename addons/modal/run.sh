#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Runs a command in the session's environment, as the launcher's `exec` does:
# the display, the sound server, and the GL selection the entrypoint settled,
# read from the file every service of the session reads them from. The command
# counts as use of the session for as long as it runs, so a render started this
# way is not cut short by the idle timeout (session.sh). Modal runs it as root,
# and it runs the command as the session's user, as session.sh runs the session.

if [ "$(id -u)" -eq 0 ]; then
  exec setpriv --reuid=1000 --regid=1000 --init-groups -- "$0" "$@"
fi

env_file="${XDG_RUNTIME_DIR:-/tmp/runtime-ubuntu}/container-env"
if [ ! -f "${env_file}" ]; then
  echo "selkies-modal: the session has not written its environment yet" >&2
  exit 1
fi
# shellcheck disable=SC1090  # written by container-entrypoint.sh at startup
. "${env_file}"

(while touch "${SELKIES_MODAL_ACTIVITY_FILE}"; do sleep 10; done) &
keeper=$!
"$@"
status=$?
kill "${keeper}" 2> /dev/null
exit "${status}"
