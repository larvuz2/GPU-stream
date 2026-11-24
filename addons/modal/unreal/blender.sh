#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Blender in the Unreal session, as its start menu entry (blender.desktop) runs
# it: in the session's project folder, which its half of the bridge to the
# editor writes into, with the Send to Unreal add-on enabled (`--addons`, for
# this Blender, whatever its saved preferences say) and the session's script,
# which keeps Blender's recovery files in the workspace and runs the Python the
# launcher hands it (blender/session.py), and which the editor's Send to
# Blender reaches it through.
#
# The add-on is in a scripts folder of the image's own (BLENDER_SYSTEM_SCRIPTS,
# which Blender searches beside its bundled scripts), not in the user's add-ons
# in the workspace, so the image's version is the one that runs.
folder="$(selkies-modal-project)" || exit 1
cd "${folder}" || exit 1
export BLENDER_SYSTEM_SCRIPTS=/usr/local/share/selkies-modal/unreal/blender
exec blender --addons send_to_unreal --python /usr/local/share/selkies-modal/blender-session.py "$@"
