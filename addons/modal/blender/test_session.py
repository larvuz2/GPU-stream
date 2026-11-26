# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""How Blender's side of a session answers the requests in its spool, held without a Blender.

`session.py` is loaded as Blender loads it, with a stand-in for `bpy` that has
only what loading and answering touch: the timers it registers with, an
override that changes nothing, and no windows. What is tested is the spool: a
request is run, answered, and removed, and a request its sender took back does
not end the serving. `unreal/test_bridge.py` runs the same module in a real
Blender where one is installed.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SESSION = Path(__file__).resolve().parent / "session.py"


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The module, loaded in a session's environment whose spool is empty."""
    tokens = tmp_path / "tokens"
    tokens.write_text("")
    monkeypatch.setenv("SELKIES_MODAL_BLENDER_SPOOL", str(tmp_path / "spool"))
    monkeypatch.setenv("SELKIES_MODAL_BLENDER_RECOVERY", str(tmp_path / "recovery"))
    monkeypatch.setenv("MODAL_SANDBOX_ID", "sb-test")
    monkeypatch.setenv("SELKIES_TOKENS_FILE", str(tokens))
    stand_in = SimpleNamespace(
        context=SimpleNamespace(
            window_manager=SimpleNamespace(windows=[]),
            preferences=SimpleNamespace(filepaths=SimpleNamespace(temporary_directory="")),
            temp_override=lambda **_: contextlib.nullcontext(),
        ),
        app=SimpleNamespace(timers=SimpleNamespace(register=lambda *_, **__: None)),
    )
    monkeypatch.setitem(sys.modules, "bpy", stand_in)
    spec = importlib.util.spec_from_file_location("blender_session", SESSION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_request_is_run_answered_and_removed(session: ModuleType) -> None:
    request = session.SPOOL / "1-1.py"
    request.write_text("print(6 * 7)")
    assert session.serve() == session.POLL_SECONDS
    assert json.loads(request.with_suffix(".json").read_text()) == {"ok": True, "output": "42\n", "error": None}
    assert sorted(path.name for path in session.SPOOL.iterdir()) == ["1-1.json"]


def test_a_request_that_raises_is_answered_with_its_traceback(session: ModuleType) -> None:
    request = session.SPOOL / "1-1.py"
    request.write_text("raise ValueError('no such object')")
    session.serve()
    answer = json.loads(request.with_suffix(".json").read_text())
    assert answer["ok"] is False and "ValueError: no such object" in answer["error"]


def test_a_request_taken_back_while_it_ran_leaves_no_answer_and_serving_goes_on(session: ModuleType) -> None:
    gone = session.SPOOL / "1-1.py"
    # The sender gives up while its code runs: the code stands in for it by removing its own request
    gone.write_text(f"import os; os.remove({str(gone)!r}); print('late')")
    waiting = session.SPOOL / "2-1.py"
    waiting.write_text("print('next')")
    assert session.serve() == session.POLL_SECONDS, "a timer whose function raises is dropped by Blender"
    assert sorted(path.name for path in session.SPOOL.iterdir()) == ["2-1.json"], "nothing is left of the request nobody waits for"
    assert json.loads(waiting.with_suffix(".json").read_text())["output"] == "next\n"


def test_a_request_taken_back_before_its_turn_is_skipped(session: ModuleType) -> None:
    first, second = session.SPOOL / "1-1.py", session.SPOOL / "2-1.py"
    # The second sender gives up while the first request runs
    first.write_text(f"import os; os.remove({str(second)!r}); print('first')")
    second.write_text("print('never')")
    assert session.serve() == session.POLL_SECONDS
    assert sorted(path.name for path in session.SPOOL.iterdir()) == ["1-1.json"]
