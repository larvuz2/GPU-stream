#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Runs the Python on standard input inside the session's Blender, the one the
# page shows, and prints what it printed. It hands the code to Blender through
# the spool directory blender/session.py serves, and waits for the answer: the
# first argument is how many seconds to wait, 120 unless given. The status is
# 0 when the code ran to its end, 1 with its traceback on standard error when
# it raised, and 124 when Blender did not answer in time, which leaves nothing
# behind for Blender to run later.
#
#     echo 'bpy.ops.mesh.primitive_monkey_add()' | selkies-modal-blender
set -eu

spool="${SELKIES_MODAL_BLENDER_SPOOL:?the image sets it}"
wait_seconds="${1:-120}"
request="${spool}/$(date +%s%N)-$$"

# Under another name until it is whole, so Blender never runs half a request.
# The directory is made here too: a request sent while Blender is still
# starting waits in it for Blender to begin serving.
umask 077
mkdir -p "${spool}"
cat > "${request}.tmp"
mv "${request}.tmp" "${request}.py"

deadline=$(($(date +%s) + wait_seconds))
until [ -f "${request}.json" ]; do
  if [ "$(date +%s)" -ge "${deadline}" ]; then
    rm -f "${request}.py"
    echo "selkies-modal: Blender did not answer within ${wait_seconds} s" >&2
    exit 124
  fi
  sleep 0.1
done

jq -j '.output' "${request}.json"
status=0
if [ "$(jq -r '.ok' "${request}.json")" != "true" ]; then
  jq -r '.error' "${request}.json" >&2
  status=1
fi
rm -f "${request}.json"
exit "${status}"
