#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# The HyperFrames CLI of the release this machine runs, installed as
# /usr/local/bin/hyperframes:
#
#     hyperframes init my-video --non-interactive
#     hyperframes render my-video -o renders/my-video.mp4
#     hyperframes --version
#
# The arguments are the CLI's own, passed on untouched; `hyperframes --help`
# is upstream's help for the release in use.
#
# In a session it first waits for the session's update (`hyperframes-release
# update`, release.sh), which runs once as the session starts and is bounded
# in time, so no command runs on one release while another is being switched
# in; after that the wait is nothing. Outside a session, as when the image is
# built, it runs the release that is linked and asks for no update.
#
# Each run's command line is added to the session's log, which the session's
# screen shows until a preview is on it (autostart).

ROOT="/opt/hyperframes"
LOG="${HYPERFRAMES_LOG:-/tmp/selkies-modal/hyperframes.log}"
# The CLI reports its use to its makers unless told not to, offers its own updates, and installs skills into the
# home. Here nothing is reported, and the release and its skills are this machine's to settle (release.sh)
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_NO_UPDATE_CHECK=1 HYPERFRAMES_SKIP_SKILLS=1

if [ "${SELKIES_MODAL_APP-}" = hyperframes ]; then
  # A little longer than the update's own bound, which therefore ends first and records why
  timeout "$((${HYPERFRAMES_UPDATE_SECONDS:-120} + 30))" hyperframes-release update >> "${LOG}" 2>&1
  printf '$ hyperframes %s\n' "$*" >> "${LOG}" 2> /dev/null
fi

exec node "${ROOT}/current/node_modules/hyperframes/bin/hyperframes.mjs" "$@"
