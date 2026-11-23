# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Nuke's start in a Selkies session on Modal, run before its interface (`NUKE_PATH`), with a window or without.

A Modal Sandbox has no disk statistics for a process to read (no
`/proc/diskstats`), so `psutil.disk_io_counters()` answers nothing at all, where
Nuke Studio's status bar reads a byte count from it as it starts and stops on
the error in a dialog every launch. This answers zeros instead, which is what a
machine whose disks have done nothing would say, and leaves a machine that has
statistics as it is.

This is Python because Nuke's scripting interface is.
"""

import collections

import psutil

_FIELDS = ("read_count", "write_count", "read_bytes", "write_bytes", "read_time", "write_time")
_measured = psutil.disk_io_counters


def disk_io_counters(perdisk=False, nowrap=True):
    """psutil's own counters, or zeros where the machine has none."""
    counters = _measured(perdisk=perdisk, nowrap=nowrap)
    if counters is None and not perdisk:
        return collections.namedtuple("sdiskio", _FIELDS)(*(0 for _ in _FIELDS))
    return counters


psutil.disk_io_counters = disk_io_counters
