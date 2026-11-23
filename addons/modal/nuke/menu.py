# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Nuke's side of a Selkies session on Modal, run as Nuke's interface starts (`NUKE_PATH`).

A script with a name is auto-saved beside itself, which is in the workspace when
the script is, so its auto-save outlives the Sandbox with it. One that was never
saved is auto-saved into Nuke's temporary directory, which is the Sandbox's own
disk; this points that one at the workspace too, so the work of a session that
ended before its script was ever saved is there for the next. Where a Nuke
release names the preference differently, nothing is changed.

This is Python because Nuke's scripting interface is.
"""

import os

import nuke


def keep_untitled_autosaves() -> None:
    """Have a script that has no name yet auto-save into the workspace."""
    preferences = nuke.toNode("preferences")
    knob = preferences.knob("AutoSaveName") if preferences is not None else None
    if knob is None:
        return
    folder = os.path.join(os.environ["SELKIES_MODAL_WORKSPACE"], ".nuke-autosave")
    os.makedirs(folder, exist_ok=True)
    knob.setValue("[firstof [value root.name] %s/untitled].autosave" % folder)


# A preference this cannot set must not stop Nuke's start
try:
    keep_untitled_autosaves()
except Exception as error:
    print("selkies-modal: untitled scripts auto-save where Nuke puts them:", error)
