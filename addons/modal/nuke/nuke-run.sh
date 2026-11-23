#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Runs the workspace's Nuke without its window, for a render or a script:
#
#     nuke-run -x comp.nk 1-48       render a script's Write nodes, frames 1 to 48
#     nuke-run -t build.py           run Python in Nuke
#
# It asks Foundry for an interactive license (`-i`): a login license for one
# person, the trial's among them, carries no render license, which Nuke asks
# for by default without a window and is refused. Arguments go to Nuke as
# given, after that one.
set -eu
# The image's copy first (sandbox.py's nuke_image), then the workspace's own
nuke=""
for root in /opt/nuke "${SELKIES_MODAL_WORKSPACE:?the image sets it}/.apps/nuke"; do
  [ -n "${nuke}" ] || nuke="$(find "${root}" -mindepth 2 -maxdepth 2 -type f -perm -u+x \
    -regex '.*/Nuke[0-9]+\.[0-9]+' 2> /dev/null | sort -V | tail -n 1)"
done
if [ -z "${nuke}" ]; then
  echo "nuke-run: Nuke is not installed in this workspace yet; open a Nuke session to set it up" >&2
  exit 1
fi
export QTWEBENGINE_DISABLE_SANDBOX=1
exec "${nuke}" -i "$@"
