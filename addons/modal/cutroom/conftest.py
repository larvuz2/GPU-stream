# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Puts the Cut Room's scripts on the path for the tests beside this file.

The scripts import one another by name (`from common import ...`), since each
is run as a file of one folder (`run.sh`). pytest reads this before it
imports a test module, so the tests import the scripts the same way.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
