# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""A version's edit: what is taken of v2's record of it, and what is not.

The record is a file the agent's commands wrote on an engine, so what is held
here is the boundary: a record describes only the file it names as its
render, and what is kept of it is the parts the page draws, each checked and
bounded. The commands themselves are run against a real project in the
engines' image builds (`addons/modal/v2`), and how a preview carries an edit
is held over the fakes of `test_api.py`. Run with `pytest moody/control`.
"""

from __future__ import annotations

import json

import edits

SHOWN = ["renders/short.mp4", "sheets/frame.png"]


def record(**changes: object) -> str:
    """A record as v2 writes one for a version whose render is the short, with the given parts in place of its own."""
    given = {
        "version": "v2",
        "message": "The slam, with the hook",
        "prompts": ["make a short of the boss slam"],
        "model": "a-model",
        "changes": [{"from": 0, "to": 4.5, "kind": "video", "src": "renders/short.mp4", "text": "the slam, cropped to 9:16"}],
        "assemble": "cutroom cut jobs/slam",
        "render": "renders/short.mp4",
        "saved_at": "2026-11-28T14:51:05Z",
    }
    return json.dumps({**given, **changes})


def test_only_a_name_v2_gives_a_version_is_asked_of_an_engine():
    assert [label for label in ("v1", "v12", "v0", "V2", "v2 final", "Rough cut", "v2; rm -rf .", "") if edits.is_version(label)] == ["v1", "v12"]
    assert "git show v12:./.v2/commit.json" in edits.record_command("/work/a project", "v12")
    assert edits.record_command("/work/a project", "v12").startswith("cd '/work/a project' && ")


def test_a_record_describes_only_the_file_it_names_as_its_render():
    render, edit = edits.edit_of(record(), SHOWN)
    assert render == "renders/short.mp4"
    assert edit == {
        "message": "The slam, with the hook",
        "prompts": ["make a short of the boss slam"],
        "changes": [{"text": "the slam, cropped to 9:16", "kind": "video", "from": 0.0, "to": 4.5, "src": "renders/short.mp4"}],
        "saved_at": "2026-11-28T14:51:05+00:00",
    }, "what v2 keeps for itself (the model, how the render was assembled) is not the page's"
    assert edits.edit_of(record(render="./renders/short.mp4"), SHOWN)[0] == "renders/short.mp4", "a path is compared as a path"
    for other in ("renders/other.mp4", "", None, 7):
        assert edits.edit_of(record(render=other), SHOWN) is None, f"a render of {other!r} is not what is shown"
    for text in ("", "ran in sb-1\n", "[]", record()[:-20]):
        assert edits.edit_of(text, SHOWN) is None, "what is no record gives no edit"


def test_what_is_kept_of_a_record_is_what_the_page_draws_and_no_more_than_it_can_hold():
    changes = [
        {"from": 1, "to": 3, "kind": "voice", "type": "added", "src": "narration/voice.wav", "text": "  six lines\nin the Fenrir voice  "},
        {"from": 3.4, "to": 3.4, "kind": "cut", "removed": 3.4, "text": "the pause"},
        {"kind": "music", "text": "music 20% quieter"},
        {"from": 9, "to": 2, "kind": "graphics", "text": "a span given backwards"},
        {"from": "0:03", "to": True, "kind": "lasers", "type": "invented", "removed": 2, "text": "nothing here is v2's"},
        {"from": 1, "to": 2, "kind": "sfx"},
        "a change that is not an entry",
    ]
    _, edit = edits.edit_of(record(changes=changes, prompts=["one", "", 5, " two\nlines "], message=None, saved_at="yesterday"), SHOWN)
    assert edit["changes"] == [
        {"text": "six lines in the Fenrir voice", "kind": "voice", "from": 1.0, "to": 3.0, "src": "narration/voice.wav", "type": "added"},
        {"text": "the pause", "kind": "cut", "from": 3.4, "to": 3.4, "removed": 3.4},
        {"text": "music 20% quieter", "kind": "music"},
        {"text": "a span given backwards", "kind": "graphics"},
        {"text": "nothing here is v2's"},
    ], "a change with no span is one to the whole video, and one with no words says nothing"
    assert edit["prompts"] == ["one", "two lines"] and edit["message"] == "" and "saved_at" not in edit

    many = [{"from": second, "to": second + 1, "kind": "text", "text": "x" * 900} for second in range(500)]
    _, edit = edits.edit_of(record(changes=many, prompts=["p" * 5000] * 90), SHOWN)
    assert len(edit["changes"]) == edits.CHANGES and len(edit["changes"][0]["text"]) == edits.TEXT_CHARACTERS
    assert len(edit["prompts"]) == edits.PROMPTS and len(edit["prompts"][0]) == edits.PROMPT_CHARACTERS


def test_a_versions_sound_is_bars_from_silence_to_full_scale():
    command = edits.bars_command("/work/a project", "renders/it's.mp4", 60.0)
    assert "asetnsamples=n=2000:" in command, "a minute at 8000 samples a second makes 240 stretches of 2000"
    assert f"head -n {edits.BARS}" in command and "'./renders/it'\"'\"'s.mp4'" in command
    key = edits.PEAK_KEY
    printed = "\n".join(["frame:0    pts:0", f"{key}=-inf", f"{key}=-6.0206", f"{key}=0.000000", f"{key}=3.5", f"{key}=nan", f"{key}=loud", "ran in sb-1"])
    assert edits.sound_bars(printed) == [0, 50, 100, 100, 0], "a peak is a share of full scale, and what is no number is no bar"
    assert edits.sound_bars(f"{key}=-3.0") == [] and edits.sound_bars("") == [], "one stretch, or none, is no waveform"
