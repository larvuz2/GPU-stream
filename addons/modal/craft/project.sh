#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Prints the session's project folder, made if it is not there yet, for an
# application's autostart to open in:
#
#     folder="$(selkies-modal-project)"
#
# The folder is SELKIES_MODAL_PROJECT, a path relative to the workspace
# (`projects/<id>`), else `projects/default`. Every engine of one project opens
# in the same folder, so what one writes the others read. A value that is not a
# folder inside the workspace (absolute, or with a `.` or `..` part) is set
# aside for `projects/default`, saying so on standard error.
set -eu

workspace="${SELKIES_MODAL_WORKSPACE:-${HOME}}"
project="${SELKIES_MODAL_PROJECT:-projects/default}"
case "/${project}/" in
  //* | */../* | */./*)
    echo "selkies-modal: SELKIES_MODAL_PROJECT=${project} is not a folder inside the workspace; opening projects/default" >&2
    project="projects/default"
    ;;
esac
folder="${workspace}/${project%/}"
mkdir -p "${folder}"
printf '%s\n' "${folder}"
