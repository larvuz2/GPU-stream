# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Interactive cards: the catalog, the check a card passes, and the tool that shows one.

The catalog is `moody/ui.json`, the file the app renders from, so what is held
here is that the two cannot drift: every kind of property the catalog uses has
a check, a card that uses every component passes, and the tool's reference
names all of them. The check is held by what it tells the model, since a
refusal is only worth as much as what it lets the model fix: each case is a
card with one mistake and the words its problem has to carry.

The tool is called as a turn calls it, over the fakes of `test_api.py`: a
card's files are the project's own and are signed at each reading of the log,
a card that is not valid costs no read of any file, and one that waits says
the turn ends. The cards skill is held to the catalog too: every call it
writes out passes the check. Run with `pytest moody/control`.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent import (
    TOOL_NAMES,
    TOOLS,
    Agent,
    Turn,
    read_skills,
    skills_directory,
    skills_for,
)
from api import create_app
from genui import ID, Check, Invalid, MediaRequest, card, catalog, media_requests
from service import Refused, Sessions
from test_api import (
    ALICE,
    PNG,
    FakeLauncher,
    FakeStore,
    InlineJobs,
    ScriptedLoop,
    auth,
    config,
    events,
    new_project,
    probe,
    start_engine,
)
from test_api import CATALOG as PRODUCTS

CATALOG = catalog()
# The files the sample card carries, by name, each with its kind
MEDIA = {
    "shot": "image",
    "graded": "image",
    "mara": "image",
    "theo": "image",
    "cut": "video",
    "theme": "audio",
    "robot": "model",
}
# A card that uses every component of the catalog, as a look board for one shot might
SAMPLE: dict[str, Any] = {
    "type": "stack",
    "children": [
        {
            "type": "text",
            "text": "Shot 3 at warmth {warmth} with {grain} grain",
            "tone": "heading",
        },
        {
            "type": "tabs",
            "id": "view",
            "children": [
                {
                    "type": "tab",
                    "label": "Grade",
                    "children": [
                        {
                            "type": "compare",
                            "before": "shot",
                            "after": "shot",
                            "adjust": {
                                "warmth": "$warmth",
                                "grain": "$grain",
                                "fade": 12,
                            },
                        },
                        {
                            "type": "row",
                            "children": [
                                {
                                    "type": "slider",
                                    "id": "warmth",
                                    "label": "Warmth",
                                    "min": -100,
                                    "max": 100,
                                    "value": 20,
                                },
                                {"type": "slider", "id": "grain", "label": "Grain"},
                                {
                                    "type": "number",
                                    "id": "frames",
                                    "label": "Hold",
                                    "min": 1,
                                    "max": 240,
                                    "value": 24,
                                    "unit": "f",
                                },
                            ],
                        },
                        {
                            "type": "image",
                            "src": "graded",
                            "caption": "The grade so far",
                            "adjust": {"vignette": 30},
                            "when": {"vignette_on": True},
                        },
                        {"type": "toggle", "id": "vignette_on", "label": "Vignette"},
                    ],
                },
                {
                    "type": "tab",
                    "label": "Cast",
                    "value": "cast",
                    "children": [
                        {
                            "type": "pick",
                            "id": "lead",
                            "options": [
                                {"value": "mara", "label": "Mara", "image": "mara"},
                                {"value": "theo", "image": "theo", "note": "Older"},
                            ],
                        },
                        {
                            "type": "gallery",
                            "items": [
                                "mara",
                                {"src": "cut", "caption": "The animatic"},
                            ],
                        },
                        {
                            "type": "field",
                            "id": "note",
                            "label": "Anything to change?",
                            "lines": 3,
                        },
                        {
                            "type": "checkboxes",
                            "id": "keep",
                            "options": ["Coat", "Scar", "Lantern"],
                            "value": ["Coat"],
                        },
                    ],
                },
                {
                    "type": "tab",
                    "label": "Plan",
                    "children": [
                        {
                            "type": "grid",
                            "columns": 2,
                            "children": [
                                {
                                    "type": "table",
                                    "id": "cut_shot",
                                    "columns": ["Shot", "Lens", "Seconds"],
                                    "rows": [["1A", "35mm", 4], ["1B", "85mm", 2.5]],
                                    "pick": "many",
                                    "value": ["1B"],
                                },
                                {
                                    "type": "chart",
                                    "kind": "share",
                                    "data": [
                                        {"label": "Cast", "value": 1200},
                                        {"label": "Sets", "value": 800},
                                    ],
                                    "unit": "$",
                                    "highlight": "$area",
                                },
                            ],
                        },
                        {
                            "type": "select",
                            "id": "area",
                            "label": "Spend",
                            "options": ["Cast", "Sets"],
                            "value": "Sets",
                        },
                        {
                            "type": "segmented",
                            "id": "aspect",
                            "options": ["16:9", "2.39:1", "4:3"],
                        },
                        {
                            "type": "reorder",
                            "id": "order",
                            "options": [
                                {"value": "s1", "label": "Harbor"},
                                {"value": "s2", "label": "Lighthouse"},
                            ],
                        },
                        {
                            "type": "swatches",
                            "label": "Dusk",
                            "colors": [
                                "#1b1f3b",
                                {"color": "#e0a458", "label": "Lantern"},
                            ],
                        },
                        {
                            "type": "color",
                            "id": "accent",
                            "value": "#e0a458",
                            "suggest": ["#e0a458", "#1b1f3b"],
                        },
                    ],
                },
            ],
        },
        {"type": "video", "src": "cut", "loop": True, "when": {"view": "cast"}},
        {"type": "audio", "src": "theme", "label": "The theme, bars 1 to 8"},
        {
            "type": "model",
            "id": "angle",
            "src": "robot",
            "finish": "$finish",
            "color": "$accent",
            "spin": True,
        },
        {"type": "select", "id": "finish", "options": list(CATALOG.data["finishes"])},
        {
            "type": "upload",
            "id": "track",
            "label": "The track",
            "accept": "audio",
            "section": "Music",
            "required": True,
        },
        {
            "type": "layers",
            "id": "comp",
            "layers": [
                {"name": "Sky", "src": "shot"},
                {"name": "Mara", "src": "mara", "opacity": 80, "blend": "screen"},
            ],
        },
    ],
}


def problems(spec: Any, media: dict[str, str] | None = None) -> list[str]:
    """What the check finds wrong with a card's tree."""
    check = Check(CATALOG, MEDIA if media is None else media)
    try:
        check.run(spec)
    except Invalid as invalid:
        return invalid.problems
    return []


def changed(path: list[Any], value: Any = None, drop: bool = False) -> dict[str, Any]:
    """The sample card with one place changed: the value at a path of keys and indexes replaced, or removed."""
    spec = copy.deepcopy(SAMPLE)
    target: Any = spec
    for step in path[:-1]:
        target = target[step]
    if drop:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return spec


def used(spec: Any) -> set[str]:
    """The components a card's tree uses."""
    if isinstance(spec, list):
        return set().union(*map(used, spec)) if spec else set()
    if isinstance(spec, dict):
        return ({spec["type"]} if "type" in spec else set()) | used(list(spec.values()))
    return set()


def test_every_property_of_the_catalog_is_of_a_kind_the_check_knows():
    def specs(properties: dict[str, dict[str, Any]]):
        for spec in properties.values():
            yield spec
            while isinstance(spec.get("of"), dict):
                spec = spec["of"]
                yield spec

    everything = [
        *CATALOG.components.values(),
        *CATALOG.shapes.values(),
        {"props": CATALOG.data["common"]},
    ]
    for entry in everything:
        for spec in specs(entry["props"]):
            assert hasattr(Check, f"kind_{spec['kind']}") or spec["kind"] == "nodes", (
                spec
            )
            assert (
                not isinstance(spec.get("of"), str) or spec["of"] in CATALOG.shapes
            ), spec
            if spec["kind"] == "enum":
                assert CATALOG.values(spec), spec
            if spec["kind"] == "media":
                assert set(spec["kinds"]) <= set(CATALOG.data["media_kinds"]), spec
    for name, entry in CATALOG.components.items():
        assert entry["group"] in ("layout", "content", "input") and entry["doc"], name
        assert set(entry.get("inside", [])) <= set(CATALOG.components), name
        answers = "id" in entry["props"]
        assert answers == ("input" in entry), (
            f"{name} says what it answers with exactly when it can have an id"
        )
        assert (
            entry["props"].get("id", {}).get("required", False)
            != entry.get("optional_id", False)
            or not answers
        ), name
    for shape in CATALOG.shapes.values():
        assert shape.get("short", next(iter(shape["props"]))) in shape["props"]


def test_a_card_that_uses_every_component_passes_and_its_inputs_are_its_ids():
    assert used(SAMPLE) == set(CATALOG.components), (
        "the sample is what holds every component to the check"
    )
    check = Check(CATALOG, MEDIA)
    check.run(SAMPLE)
    assert check.inputs == {
        "view": "tabs",
        "warmth": "slider",
        "grain": "slider",
        "frames": "number",
        "vignette_on": "toggle",
        "lead": "pick",
        "note": "field",
        "keep": "checkboxes",
        "cut_shot": "table",
        "area": "select",
        "aspect": "segmented",
        "order": "reorder",
        "accent": "color",
        "angle": "model",
        "finish": "select",
        "track": "upload",
        "comp": "layers",
    }
    assert all(ID.fullmatch(given) for given in check.inputs)


GRADE, CAST, PLAN = (
    ["children", 1, "children", index, "children"] for index in range(3)
)
MISTAKES = [
    # What is wrong, the card, and what the problem has to say
    (
        "a component that does not exist",
        changed([*GRADE, 1, "children", 0, "type"], "slidr"),
        [
            "components.children[1].children[0].children[1].children[0]",
            'no component "slidr"',
            'Did you mean "slider"?',
            "The components are: stack, row",
        ],
    ),
    (
        "a property the component does not take",
        changed([*GRADE, 1, "children", 0, "labels"], "Warmth"),
        [
            "(slider)",
            'no property "labels"',
            'Did you mean "label"?',
            "It takes: id, label, min, max, step, value, unit, when",
        ],
    ),
    (
        "a missing required property",
        changed([*GRADE, 3, "label"], drop=True),
        ["(toggle)", 'is missing "label"'],
    ),
    (
        "a value of the wrong type",
        changed([*GRADE, 1, "children", 0, "max"], "100"),
        ["(slider).max should be a number", 'it is "100"'],
    ),
    (
        "a number out of its range",
        changed([*PLAN, 0, "columns"], 9),
        ["(grid).columns should be from 1 to 4; it is 9"],
    ),
    (
        "a value outside an enumeration",
        changed([*PLAN, 0, "children", 1, "kind"], "pie"),
        ["(chart).kind should be one of bar, line, area, share", '"pie"'],
    ),
    (
        "a file the card does not carry",
        changed([*GRADE, 2, "src"], "grade"),
        [
            '(image).src names the media "grade"',
            'Did you mean "graded"?',
            "Its media are: shot, graded, mara",
            "Add the file to `media`",
        ],
    ),
    (
        "a file of the wrong kind",
        changed([*GRADE, 2, "src"], "theme"),
        ['(image).src needs an image, but the media "theme" is an audio'],
    ),
    (
        "a binding to an input that is not there",
        changed([*GRADE, 0, "adjust", "warmth"], "$warm"),
        [
            '(compare).adjust.warmth follows the input "warm"',
            'Did you mean "warmth"?',
            "The ids are: view, warmth, grain",
        ],
    ),
    (
        "a text that shows an input that is not there",
        changed(["children", 0, "text"], "Warmth {heat}"),
        ['(text).text follows the input "heat"'],
    ),
    (
        "a condition on an input that is not there",
        changed(["children", 2, "when"], {"tab": "cast"}),
        ['(video).when follows the input "tab"'],
    ),
    (
        "a condition that compares in no known way",
        changed(["children", 2, "when"], {"view": {"above": 3}}),
        [
            "(video).when.view should be a value, a list of values, or one of {not: value}"
        ],
    ),
    (
        "two inputs under one id",
        changed([*GRADE, 1, "children", 2, "id"], "warmth"),
        [
            '(number): the id "warmth" is already taken by components.children[1].children[0].children[1].children[0] (slider)',
            "every input needs its own",
        ],
    ),
    (
        "an id that is not one",
        changed([*GRADE, 1, "children", 2, "id"], "Frames Held"),
        ["(number).id should be a short id of lowercase letters"],
    ),
    (
        "a starting value outside the range",
        changed([*GRADE, 1, "children", 0, "value"], 140),
        ["(slider): value (140) should lie from min (-100) to max (100)"],
    ),
    (
        "a range that is upside down",
        changed([*GRADE, 1, "children", 2, "max"], 0),
        ["(number): min (1) should be below max (0)"],
    ),
    (
        "a starting choice that is no option",
        changed([*PLAN, 1, "value"], "Music"),
        ['(select).value should be one of its options: "Cast", "Sets"'],
    ),
    (
        "one choice where the answer is always a list",
        changed([*CAST, 3, "value"], "Coat"),
        ['(checkboxes).value should be a list; it is "Coat"'],
    ),
    (
        "one choice where many are picked",
        changed([*PLAN, 0, "children", 0, "value"], "1B"),
        ["(table).value should be a list of the values chosen at first"],
    ),
    (
        "many choices where one is picked",
        changed([*CAST, 0, "value"], ["mara"]),
        ["(pick).value should be one value, not a list"],
    ),
    (
        "two options of one value",
        changed([*PLAN, 2, "options"], ["16:9", "16:9"]),
        [
            "(segmented).options: option values should each be different",
            '"16:9" is there more than once',
        ],
    ),
    (
        "too many options for the component",
        changed([*PLAN, 2, "options"], [str(n) for n in range(6)]),
        ["(segmented).options should have from 2 to 5 items; it has 6"],
    ),
    (
        "a row with a cell missing",
        changed([*PLAN, 0, "children", 0, "rows", 1], ["1B", "85mm"]),
        ["(table).rows[1] has 2 cells for 3 columns"],
    ),
    (
        "an adjustment that does not exist",
        changed([*GRADE, 0, "adjust"], {"warmness": 10}),
        ['no adjustment "warmness"', "The adjustments are: brightness, contrast"],
    ),
    (
        "an adjustment past its range",
        changed([*GRADE, 0, "adjust", "fade"], 300),
        ["(compare).adjust.fade should be from 0 to 100; it is 300"],
    ),
    (
        "a tab outside tabs",
        changed(
            ["children", 3],
            {
                "type": "tab",
                "label": "Loose",
                "children": [{"type": "text", "text": "x"}],
            },
        ),
        ["(tab) belongs directly inside tabs"],
    ),
    (
        "something that is not a tab inside tabs",
        changed(
            ["children", 1, "children"],
            [*SAMPLE["children"][1]["children"], {"type": "text", "text": "x"}],
        ),
        ["components.children[1].children[3] (text): a tabs holds only tab components"],
    ),
    (
        "a color that is not one",
        changed([*PLAN, 5, "value"], "amber"),
        ["(color).value should be a color as #rrggbb"],
    ),
    (
        "an item of a list that is not its shape",
        changed([*PLAN, 0, "children", 1, "data", 0], {"label": "Cast"}),
        ['data[0] (point) is missing "value"'],
    ),
    (
        "a list item with a property it does not take",
        changed([*CAST, 0, "options", 0, "img"], "mara"),
        ['options[0] (tile) has no property "img"', 'Did you mean "image"?'],
    ),
    (
        "a kind of file an upload does not take",
        changed(["children", 6, "accept"], "sound"),
        [
            "(upload).accept should be one of any, audio, image, video",
            '"sound"',
        ],
    ),
    (
        "a child that is not a component",
        changed(["children", 0], "Shot 3"),
        ['components.children[0] should be a component: an object with a "type"'],
    ),
]


@pytest.mark.parametrize(
    ("spec", "says"),
    [pytest.param(spec, says, id=what) for what, spec, says in MISTAKES],
)
def test_a_problem_names_the_component_the_property_and_what_was_expected(spec, says):
    found = problems(spec)
    assert len(found) == 1, found
    for words in says:
        assert words in found[0], found[0]


def test_every_problem_of_a_card_is_reported_at_once_up_to_the_limit():
    limit = CATALOG.limits["problems"]
    two = problems(
        {
            "type": "stack",
            "children": [{"type": "slider"}, {"type": "image", "src": "nowhere"}],
        }
    )
    assert len(two) == 2 and "(slider) is missing" in two[0] and "(image).src" in two[1]
    many = {
        "type": "stack",
        "children": [{"type": "toggle", "id": f"t{n}"} for n in range(limit + 5)],
    }
    with pytest.raises(Invalid) as refused:
        Check(CATALOG, {}).run(many)
    assert len(refused.value.problems) == limit and refused.value.more == 5
    message = refused.value.message
    assert (
        message.startswith("The card was not shown. Fix this and call show_ui again:")
        and message.count("\n- ") == limit + 1
    )
    assert message.endswith("and 5 more of the same kind.")


def test_a_card_is_bounded_in_its_components_its_depth_and_its_size():
    limits = CATALOG.limits
    wide = {
        "type": "stack",
        "children": [{"type": "grid", "children": [{"type": "text", "text": "x"}] * 50}]
        * 3,
    }
    assert any(
        f"over the {limits['nodes']} one may have" in one for one in problems(wide)
    )
    deep: dict[str, Any] = {"type": "text", "text": "x"}
    for _ in range(limits["depth"]):
        deep = {"type": "stack", "children": [deep]}
    assert problems(deep) == [
        f"components{'.children[0]' * limits['depth']} (text) is nested deeper than {limits['depth']} levels; flatten the layout."
    ]
    heavy = {"type": "text", "text": "x" * limits["spec_bytes"]}
    assert problems(heavy) == [
        f"components is {len(json.dumps(heavy))} bytes, over the {limits['spec_bytes']} a card may be. Show less in one card: "
        "fewer options or rows, or two cards."
    ]
    assert (
        f"keep it under {limits['text_chars']}"
        in problems({"type": "text", "text": "x" * (limits["text_chars"] + 1)})[0]
    )
    long_list = {
        "type": "select",
        "id": "one",
        "options": [str(n) for n in range(limits["list_items"] + 1)],
    }
    assert (
        f"should have from 1 to {limits['list_items']} items" in problems(long_list)[0]
    )


def shown(**given: Any) -> tuple[dict[str, Any], dict[str, str]]:
    """A card as `show_ui` would make it of these arguments."""
    arguments = {
        "title": "The look of shot 3",
        "components": None,
        "html": None,
        "submit": None,
        "waits": False,
        "height": None,
        **given,
    }
    return card(CATALOG, "ui-1", media=MEDIA, **arguments)


def refusal(**given: Any) -> str:
    with pytest.raises(Invalid) as refused:
        shown(**given)
    return refused.value.message


def test_a_components_card_becomes_an_event_with_its_tree_and_its_inputs():
    data, inputs = shown(components=SAMPLE, submit=" Lock in this look ", waits=True)
    assert data == {
        "ui_id": "ui-1",
        "title": "The look of shot 3",
        "kind": "components",
        "submit": "Lock in this look",
        "waits": True,
        "spec": SAMPLE,
    }
    assert inputs["warmth"] == "slider" and len(inputs) == 17
    assert "instant" not in data, "only an instant card says so"
    plain, none = shown(components={"type": "image", "src": "shot"})
    assert plain["submit"] is None and plain["waits"] is False and none == {}


def test_a_card_that_asks_opens_on_the_values_it_gives_and_needs_none():
    bare = {
        "type": "stack",
        "children": [
            {"type": "pick", "id": "lead", "options": ["Mara", "Iris"]},
            {"type": "segmented", "id": "mood", "options": ["Dusk", "Noon"]},
            {"type": "slider", "id": "grain"},
            {"type": "toggle", "id": "loop", "label": "Loop"},
            {"type": "field", "id": "note", "required": True},
        ],
    }
    # Nothing chosen and nothing set: the card opens on each input's own default, and the person chooses
    data, inputs = shown(components=bare, submit="Lock it in", waits=True)
    assert data["spec"] == bare
    assert list(inputs) == ["lead", "mood", "grain", "loop", "note"]

    given = copy.deepcopy(bare)
    for child, value in zip(given["children"], ("Iris", "Noon", 40, True, "A line")):
        child["value"] = value
    assert shown(components=given, submit="Lock it in")[0]["spec"] == given

    # A value the card opens on has to be one the input can hold
    given["children"][1]["value"] = "Dawn"
    assert '(segmented).value should be one of its options: "Dusk", "Noon"' in refusal(
        components=given, submit="Lock it in"
    )


def test_an_html_card_is_bounded_and_has_to_report_its_value_to_be_locked_in():
    limits = CATALOG.limits
    page = "<canvas id=c></canvas><script>c.onclick = () => moody.setState({taps: 1})</script>"
    data, inputs = shown(html=page, submit="Keep this", height=480)
    assert data == {
        "ui_id": "ui-1",
        "title": "The look of shot 3",
        "kind": "html",
        "submit": "Keep this",
        "waits": False,
        "html": page,
        "height": 480,
    }
    assert inputs == {}
    assert (
        shown(html="<p>Nothing to send back</p>")[0]["height"]
        == limits["height_default"]
    )
    assert "never calls moody.setState or moody.submit" in refusal(
        html="<p>No bridge</p>", submit="Keep this"
    )
    heavy = "<!-- " + "x" * limits["html_bytes"] + " -->"
    assert (
        f"html is {len(heavy)} bytes, over the {limits['html_bytes']} a card's document may be"
        in refusal(html=heavy)
    )
    assert f"from {limits['height_min']} to {limits['height_max']}" in refusal(
        html=page, height=limits["height_max"] + 1
    )
    assert "html should be the card's document" in refusal(html="  ")


ICON = [
    "00111100",
    "01000010",
    "10100101",
    "10000001",
    "10100101",
    "10011001",
    "01000010",
    "00111100",
]


def kinds_card(**pick: Any) -> dict[str, Any]:
    """A card of one pick whose tiles are pixel icons, as the card that asks a project's kind is."""
    return {
        "type": "pick",
        "id": "kind",
        "label": "What are we making?",
        "options": [
            {"value": "Film & TV", "icon": ICON, "note": "A story told in scenes"},
            {"value": "Music Videos", "icon": ICON},
            "Other",
        ],
        **pick,
    }


def test_a_tile_shows_a_pixel_icon_that_is_a_square_of_zeros_and_ones():
    limits = CATALOG.limits
    assert problems(kinds_card()) == []
    widest = ["1" * limits["icon_max"]] * limits["icon_max"]
    assert problems(kinds_card(options=[{"value": "a", "icon": widest}])) == []

    def said(icon: Any) -> str:
        (found,) = problems(kinds_card(options=[{"value": "a", "icon": icon}, "b"]))
        assert found.startswith("components (pick).options[0].icon "), found
        return found

    asked = f"{limits['icon_min']} to {limits['icon_max']} rows of as many characters, each 0 or 1"
    assert asked in said("camera") and 'it is "camera"' in said("camera")
    assert asked in said(ICON[:7]) and "it has 7 rows" in said(ICON[:7])
    assert "it has 17 rows" in said(["1" * 17] * 17)
    ragged = [*ICON[:3], "1000001", *ICON[4:]]
    assert "8 rows of 8 characters each; row 4 has 7" in said(ragged)
    drawn = [*ICON[:1], "0#....#0", *ICON[2:]]
    assert 'should hold only 0 and 1; row 2 is "0#....#0"' in said(drawn)
    assert "has no cell filled" in said(["0" * 8] * 8)


def test_a_tile_shows_one_of_a_picture_an_icon_and_a_sound():
    sounds = {
        "type": "pick",
        "id": "cue",
        "options": [
            {"value": "a", "label": "A · Harbor", "audio": "theme"},
            {"value": "b", "label": "B · Market", "audio": "theme", "note": "Faster"},
        ],
        "value": "a",
    }
    assert problems(sounds) == []
    both = copy.deepcopy(sounds)
    both["options"][0]["icon"] = ICON
    assert problems(both) == [
        "components (pick).options[0] (tile) has icon and audio, but a tile shows one of image, icon, audio. Keep one."
    ]
    picture = copy.deepcopy(sounds)
    picture["options"][1]["audio"] = "mara"
    assert problems(picture) == [
        'components (pick).options[1].audio needs an audio, but the media "mara" is an image.'
    ]
    # Icons and sounds are a pick's: the options of any other input are words
    plain = {
        "type": "segmented",
        "id": "cue",
        "options": [{"value": "a", "icon": ICON}, "b"],
    }
    (found,) = problems(plain)
    assert 'options[0] (option) has no property "icon"' in found


def test_an_instant_card_is_one_single_choice_and_has_no_lock_in_button():
    data, inputs = shown(components=kinds_card(), instant=True, waits=True)
    assert data["instant"] is True and data["submit"] is None and data["waits"] is True
    assert inputs == {"kind": "pick"}
    held = {
        "type": "stack",
        "children": [{"type": "text", "text": "Pick one."}, kinds_card()],
    }
    assert shown(components=held, instant=True)[0]["instant"] is True, (
        "what is not an input does not count"
    )
    two = {"type": "segmented", "id": "length", "options": ["Short", "Long"]}
    assert shown(components=two, instant=True)[0]["instant"] is True

    assert "instant is true and there is a submit label" in refusal(
        components=kinds_card(), instant=True, submit="Go"
    )
    assert "instant is for a components card" in refusal(
        html="<button onclick='moody.submit(1)'>One</button>", instant=True
    )
    assert "instant should be true or false" in refusal(
        components=kinds_card(), instant="yes"
    )
    several = {
        "type": "stack",
        "children": [kinds_card(), {"type": "field", "id": "note"}],
    }
    assert (
        "instant is for a card whose one input is a single choice (segmented or pick); this card has 2 inputs: "
        "kind, note. Give submit instead, or ask for the one choice alone."
    ) in refusal(components=several, instant=True)
    assert "this card has none" in refusal(
        components={"type": "text", "text": "Hello"}, instant=True
    )
    assert (
        'instant needs the card\'s one input to be a single choice (segmented or pick); "grain" is a slider'
        in refusal(components={"type": "slider", "id": "grain"}, instant=True)
    )
    assert 'instant needs a single choice, but "kind" takes many' in refusal(
        components=kinds_card(many=True), instant=True
    )
    # A card that waits needs a way to answer, which instant is
    assert (
        "Give submit (or instant, for a card of one choice), or leave waits out."
        in refusal(components=kinds_card(), waits=True)
    )


def test_a_card_is_one_kind_has_a_title_and_waits_only_with_a_way_to_answer():
    assert "exactly one of components" in refusal()
    assert "exactly one of components" in refusal(components=SAMPLE, html="<p>both</p>")
    assert "title should say what the card is" in refusal(title=" ", components=SAMPLE)
    assert f"keep it under {CATALOG.limits['title_chars']}" in refusal(
        title="x" * 200, components=SAMPLE
    )
    assert "waits is true but there is no submit label" in refusal(
        components=SAMPLE, waits=True
    )
    assert "submit should be the lock-in button's label" in refusal(
        components=SAMPLE, submit="x" * 80
    )
    assert refusal(components={"type": "slider"}).startswith(
        "The card was not shown. Fix this and call show_ui again:\n- components (slider) is missing"
    )


def test_a_cards_files_are_named_by_tag_or_engine_file_each_under_a_name_of_its_own():
    asked = media_requests(
        CATALOG,
        [
            {"tag": "@Mara"},
            {"tag": "theo", "name": "lead", "kind": "video"},
            {"engine_id": "e-1", "path": "previews/Shot 03 graded.png"},
            {
                "engine_id": "e-1",
                "path": "handoff/blender-to-moody/robot.glb",
                "name": "robot",
            },
        ],
    )
    assert asked == [
        MediaRequest("mara", tag="@Mara"),
        MediaRequest("lead", tag="theo", kind="video"),
        MediaRequest(
            "shot-03-graded", engine_id="e-1", path="previews/Shot 03 graded.png"
        ),
        MediaRequest(
            "robot", engine_id="e-1", path="handoff/blender-to-moody/robot.glb"
        ),
    ]
    assert media_requests(CATALOG, []) == []

    def refused(items: Any) -> str:
        with pytest.raises(Invalid) as invalid:
            media_requests(CATALOG, items)
        return invalid.value.message

    assert 'media[1]: the name "mara" is already another file\'s' in refused(
        [{"tag": "@mara"}, {"engine_id": "e", "path": "a/mara.png"}]
    )
    assert (
        'media[0] should name one file: a library entry by "tag", or an engine\'s file'
        in refused([{"name": "x"}])
    )
    assert "media[0] should name one file" in refused(
        [{"tag": "@mara", "engine_id": "e", "path": "a.png"}]
    )
    assert "media[0].name should be a short name" in refused(
        [{"tag": "@mara", "name": "The Lead"}]
    )
    assert "media[0].kind should be one of image, video, audio, model, file" in refused(
        [{"tag": "@mara", "kind": "picture"}]
    )
    assert "media[0] should be an object" in refused(["@mara"])
    assert f"over the {CATALOG.limits['media']} a card may carry" in refused(
        [{"tag": f"@t{n}"} for n in range(CATALOG.limits["media"] + 1)]
    )
    assert "media should be a list" in refused({"tag": "@mara"})


def test_a_file_is_what_its_names_ending_says():
    kinds = {
        name: CATALOG.kind_of(name)
        for name in (
            "frame.PNG",
            "cut.mp4",
            "theme.m4a",
            "robot.glb",
            "plan.pdf",
            "README",
        )
    }
    assert kinds == {
        "frame.PNG": "image",
        "cut.mp4": "video",
        "theme.m4a": "audio",
        "robot.glb": "model",
        "plan.pdf": "file",
        "README": "file",
    }


def test_the_tools_reference_is_written_from_the_catalog():
    reference = CATALOG.reference()
    for name, entry in CATALOG.components.items():
        line = next(
            line for line in reference.splitlines() if line.startswith(f"- {name}(")
        )
        assert entry["doc"] in line and all(prop in line for prop in entry["props"])
    assert (
        "- slider(id*, label, min=0, max=100, step=1, value, unit): A number the person drags. Answer: a number."
        in reference
    )
    assert (
        '- model(id, src*, azimuth=35, elevation=15, finish~="original", color~, spin~=false)'
        in reference
    )
    assert "- option {value*, label, image, note}" in reference
    assert "- tile {value*, label, image, icon, audio, note}" in reference
    assert (
        '- upload(id*, label, accept="any", section, required=false): A file the person drops or picks'
        in reference
    )
    for name, spec in CATALOG.adjustments.items():
        assert f"{name} {spec['min']}..{spec['max']}" in reference
    assert "finishes: original, clay, metal, gloss, wire." in reference


# The tool, over the service with every outside party stood in for (`test_api.py`'s fakes)


@pytest.fixture
def stage() -> SimpleNamespace:
    """A project's backend with an agent whose tools are called directly, as a turn would call them."""
    store, launcher, jobs = FakeStore(), FakeLauncher(), InlineJobs()
    sessions = Sessions(
        config(anthropic_key="sk-ant-test"), PRODUCTS, store, launcher, jobs
    )
    jobs.sessions = sessions
    agent = Agent(sessions, ScriptedLoop(), None, [])
    with TestClient(create_app(sessions, sessions.config, PRODUCTS)) as client:
        yield SimpleNamespace(
            client=client,
            sessions=sessions,
            store=store,
            launcher=launcher,
            agent=agent,
        )


def turn_of(stage: SimpleNamespace, project_id: str) -> Turn:
    """A turn of a project, as the worker that runs one would hold it."""
    row = stage.store.rows("projects", id=f"eq.{project_id}")[0]
    return Turn(stage.sessions, row, "turn-card", 3600)


def library_entry(
    stage: SimpleNamespace,
    project_id: str,
    name: str,
    files: list[tuple[str, bytes, str]],
) -> dict[str, Any]:
    """A library entry tagged with its name, holding these files, the last one newest."""
    base = f"/v1/projects/{project_id}/library"
    entry = stage.client.post(
        base,
        headers=auth("alice-token"),
        json={"section": "Characters", "name": name, "tag": name},
    ).json()["asset"]
    for file in files:
        posted = stage.client.post(
            f"{base}/{entry['id']}/media",
            headers=auth("alice-token"),
            files={"file": file},
        )
        assert posted.status_code == 200, posted.text
    return entry


def cards(stage: SimpleNamespace, project_id: str) -> list[dict[str, Any]]:
    """The cards the page is shown, in order."""
    log = events(stage.client, project_id)["events"]
    return [event["data"] for event in log if event["kind"] == "ui"]


LOOK = {
    "type": "stack",
    "children": [
        {
            "type": "compare",
            "before": "shot",
            "after": "shot",
            "adjust": {"warmth": "$warmth"},
        },
        {"type": "image", "src": "mara"},
        {"type": "slider", "id": "warmth", "label": "Warmth", "min": -100, "max": 100},
    ],
}


def test_show_ui_is_a_tool_whose_definition_carries_the_catalog():
    definition = next(tool for tool in TOOLS if tool["name"] == "show_ui")
    schema = definition["input_schema"]
    assert schema["required"] == ["title"]
    assert set(schema["properties"]) == {
        "title",
        "components",
        "html",
        "submit",
        "waits",
        "media",
        "height",
        "instant",
    }
    assert (
        "segmented or pick, not many" in schema["properties"]["instant"]["description"]
    )
    assert schema["properties"]["components"]["description"] == CATALOG.reference()
    assert "moody.setState" in schema["properties"]["html"]["description"]
    assert str(CATALOG.limits["media"]) in schema["properties"]["media"]["description"]


def test_a_card_shows_library_and_engine_files_under_links_signed_at_each_reading(
    stage,
):
    client, store, launcher, agent = (
        stage.client,
        stage.store,
        stage.launcher,
        stage.agent,
    )
    film = new_project(client)
    library_entry(
        stage,
        film["id"],
        "Mara",
        [("mara.png", b"\x89PNG mara", "image/png"), ("walk.mp4", b"mp4", "video/mp4")],
    )
    engine = start_engine(stage, film["id"])
    launcher.answers.append(probe("previews/shot03.png", 240_000, PNG))
    turn = turn_of(stage, film["id"])

    result = agent.tool_show_ui(
        turn,
        title="The look of shot 3",
        components=LOOK,
        submit="Lock in this look",
        waits=True,
        media=[
            {"tag": "@mara"},
            {"name": "shot", "engine_id": engine["id"], "path": "previews/shot03.png"},
        ],
    )
    assert result.ok and result.ends_turn is True
    assert result.summary == "Showed The look of shot 3"
    told = json.loads(result.content)
    assert told["kind"] == "components" and told["files"] == ["mara", "shot"]
    assert told["answers_with"] == {"warmth": "slider: a number"}
    assert "Your turn ends here" in told["note"]

    (kept,) = [
        row["data"]
        for row in store.tables["project_events"].values()
        if row["kind"] == "ui"
    ]
    folder = f"{ALICE.id}/{film['id']}"
    assert [(file["name"], file["kind"]) for file in kept["media"]] == [
        ("mara", "image"),
        ("shot", "image"),
    ]
    entry_file, engine_file = (file["path"] for file in kept["media"])
    assert entry_file.endswith("-mara.png") and "/previews/" not in entry_file
    assert engine_file.startswith(f"{folder}/previews/") and engine_file.endswith(
        "-shot03.png"
    )
    assert store.files[engine_file] == (b"bytes of shot03.png", "image/png")
    assert all("url" not in file for file in kept["media"]), (
        "the log keeps paths, never links"
    )

    (shown,) = cards(stage, film["id"])
    assert shown["ui_id"] == told["ui_id"] and shown["spec"] == LOOK
    assert (shown["submit"], shown["waits"]) == ("Lock in this look", True)
    assert [set(file) for file in shown["media"]] == [{"name", "kind", "url"}] * 2
    for file, path in zip(shown["media"], (entry_file, engine_file)):
        assert file["url"] == f"https://storage.example.test/{path}?token=signed"

    # A file that is gone is left out of the card, which then shows its placeholder
    del store.files[engine_file]
    assert [file["name"] for file in cards(stage, film["id"])[0]["media"]] == ["mara"]
    assert any(
        "rm -rf /tmp/moody-preview/" in command for _, command in launcher.commands
    )


def test_a_card_that_is_not_valid_is_refused_before_any_file_is_read(stage):
    client, store, launcher, agent = (
        stage.client,
        stage.store,
        stage.launcher,
        stage.agent,
    )
    film = new_project(client)
    library_entry(stage, film["id"], "Mara", [("mara.png", b"\x89PNG", "image/png")])
    engine = start_engine(stage, film["id"])
    turn = turn_of(stage, film["id"])
    files = [
        {"tag": "@mara"},
        {"name": "shot", "engine_id": engine["id"], "path": "previews/shot03.png"},
    ]
    commands = len(launcher.commands)

    wrong = copy.deepcopy(LOOK)
    wrong["children"][2]["labels"] = "Warmth"
    wrong["children"][1]["src"] = "shot03"
    with pytest.raises(Refused) as refused:
        agent.tool_show_ui(
            turn, title="The look", components=wrong, submit="Lock in", media=files
        )
    assert refused.value.status == 400
    message = refused.value.message
    assert message.startswith(
        "The card was not shown. Fix this and call show_ui again:"
    )
    assert '(slider) has no property "labels". Did you mean "label"?' in message
    assert (
        '(image).src names the media "shot03"' in message
        and "Its media are: mara, shot." in message
    )
    assert launcher.reads == [] and len(launcher.commands) == commands, (
        "no file was read to say so"
    )
    assert cards(stage, film["id"]) == [] and not any(
        "/previews/" in path for path in store.files
    )

    with pytest.raises(Refused, match="media\\[0\\] should name one file"):
        agent.tool_show_ui(
            turn, title="The look", components=LOOK, media=[{"name": "shot"}]
        )
    with pytest.raises(
        Refused, match='needs an image, but the media "shot" is a video'
    ):
        clip = [
            {"tag": "@mara"},
            {"name": "shot", "engine_id": engine["id"], "path": "previews/cut.mp4"},
        ]
        agent.tool_show_ui(turn, title="The look", components=LOOK, media=clip)
    assert launcher.reads == []


def test_a_cards_files_are_only_the_projects_own(stage):
    client, agent = stage.client, stage.agent
    film = new_project(client)
    other = new_project(client, token="bob-token")
    library_entry(stage, film["id"], "Mara", [("walk.mp4", b"mp4", "video/mp4")])
    library_entry(stage, film["id"], "Theo", [])
    theirs = start_engine(stage, other["id"], token="bob-token")
    turn = turn_of(stage, film["id"])
    picture = {"type": "image", "src": "shot"}

    def refused(
        media: list[dict[str, Any]], components: dict[str, Any] = picture
    ) -> Refused:
        with pytest.raises(Refused) as raised:
            agent.tool_show_ui(
                turn, title="A frame", components=components, media=media
            )
        return raised.value

    assert refused([{"name": "shot", "tag": "@iris"}]).status == 404
    assert (
        "@theo has no file yet" in refused([{"name": "shot", "tag": "@theo"}]).message
    )
    assert (
        "@mara has no image yet"
        in refused([{"name": "shot", "tag": "@mara", "kind": "image"}]).message
    )
    engine_file = {
        "name": "shot",
        "engine_id": theirs["id"],
        "path": "previews/frame.png",
    }
    assert refused([engine_file]).status == 404, (
        "another user's engine does not exist for this project"
    )
    mine = start_engine(stage, film["id"])
    outside = {"name": "shot", "engine_id": mine["id"], "path": "../../other/frame.png"}
    assert "outside the project's folder" in refused([outside]).message
    # An entry with no picture gives the file it has, which the card's component may not take
    assert (
        'needs an image, but the media "shot" is a video'
        in refused([{"name": "shot", "tag": "@mara"}]).message
    )
    assert cards(stage, film["id"]) == []


def test_an_html_card_carries_its_document_and_a_model_file_is_stored_as_it_is(stage):
    client, launcher, agent = stage.client, stage.launcher, stage.agent
    film = new_project(client)
    engine = start_engine(stage, film["id"], app="blender")
    launcher.answers.append(
        probe(
            "handoff/blender-to-moody/pip.glb", 130_000, {"streams": [], "format": {}}
        )
    )
    turn = turn_of(stage, film["id"])
    page = "<canvas id=c></canvas><script>c.onclick = () => moody.setState({taps: 1})</script>"

    result = agent.tool_show_ui(
        turn,
        title="Pip, turning",
        html=page,
        submit="Keep this",
        height=300,
        media=[{"engine_id": engine["id"], "path": "handoff/blender-to-moody/pip.glb"}],
    )
    assert (
        result.ends_turn is False
        and "Go on meanwhile" in json.loads(result.content)["note"]
    )
    (shown,) = cards(stage, film["id"])
    assert (shown["kind"], shown["html"], shown["height"], shown["waits"]) == (
        "html",
        page,
        300,
        False,
    )
    assert "spec" not in shown
    (model,) = shown["media"]
    assert (model["name"], model["kind"]) == ("pip", "model") and model["url"].endswith(
        "-pip.glb?token=signed"
    )
    commands = [command for _, command in launcher.commands]
    assert not any(
        " -c:v " in command or " -c:a " in command for command in commands
    ), "a model is not re-encoded"

    plain = agent.tool_show_ui(
        turn,
        title="A model to turn",
        components={"type": "model", "src": "pip"},
        media=[{"engine_id": engine["id"], "path": "handoff/blender-to-moody/pip.glb"}],
    )
    assert (
        "no lock-in button" in json.loads(plain.content)["note"]
        and plain.ends_turn is False
    )
    with pytest.raises(Refused, match="never calls moody.setState or moody.submit"):
        agent.tool_show_ui(
            turn, title="Nothing to send", html="<p>Hello</p>", submit="Keep this"
        )


def test_an_instant_card_is_shown_and_its_choice_comes_back_as_any_lock_does(stage):
    client, agent = stage.client, stage.agent
    film = new_project(client)
    turn = turn_of(stage, film["id"])
    result = agent.tool_show_ui(
        turn,
        title="What are we making?",
        components=kinds_card(),
        instant=True,
        waits=True,
    )
    assert result.ends_turn is True
    told = json.loads(result.content)
    assert told["answers_with"] == {
        "kind": "pick: the option's value, or a list of them with many"
    }
    assert (
        "when they choose, their next message carries what they chose" in told["note"]
    )
    (card_shown,) = cards(stage, film["id"])
    assert card_shown["instant"] is True and card_shown["submit"] is None
    assert card_shown["spec"]["options"][0]["icon"] == ICON

    going = agent.tool_show_ui(
        turn,
        title="How long?",
        instant=True,
        components={"type": "segmented", "id": "length", "options": ["Short", "Long"]},
    )
    assert (
        going.ends_turn is False
        and "may choose whenever they like" in json.loads(going.content)["note"]
    )
    with pytest.raises(Refused, match="instant needs a single choice"):
        agent.tool_show_ui(
            turn, title="Which ones?", components=kinds_card(many=True), instant=True
        )
    assert len(cards(stage, film["id"])) == 2


def test_a_card_is_titled_for_the_page_by_what_it_shows(stage):
    film = new_project(stage.client)
    turn = turn_of(stage, film["id"])
    assert (
        stage.agent.title(turn, "show_ui", {"title": "The look of shot 3"})
        == "Showing The look of shot 3"
    )
    assert stage.agent.title(turn, "show_ui", {}) == "Showing a card"


def test_the_deployed_image_carries_the_catalog_and_the_module_that_reads_it():
    source = (Path(__file__).resolve().parent / "app.py").read_text()
    assert '"genui.py"' in source and '"/root/ui.json"' in source


# The skill


def skill_examples() -> list[dict[str, Any]]:
    """Every `show_ui` call the cards skill writes out in full."""
    text = (skills_directory() / "cards" / "SKILL.md").read_text()
    return [
        json.loads(block)
        for block in re.findall(r"```json\n(.*?)```", text, flags=re.DOTALL)
    ]


def test_the_cards_skill_is_read_for_every_project_and_names_only_what_exists():
    skills = read_skills(skills_directory())
    skill = next(skill for skill in skills if skill.name == "cards")
    for discipline in PRODUCTS.disciplines:
        assert "cards" in [
            one.name for one in skills_for(skills, PRODUCTS, discipline)
        ], discipline
    named = set(
        re.findall(
            r"`(show_ui|ask_user|preview|update_plan|(?:engine|library|generate)_[a-z_]+)`",
            skill.body,
        )
    )
    assert {"show_ui", "ask_user", "preview"} <= named and named <= set(TOOL_NAMES)
    typed = set(re.findall(r'"type": "([a-z]+)"', skill.body))
    assert typed <= set(CATALOG.components), typed - set(CATALOG.components)
    assert {
        "compare",
        "slider",
        "pick",
        "tabs",
        "reorder",
        "layers",
        "model",
        "table",
        "chart",
        "audio",
    } <= typed | set(re.findall(r"`([a-z]+)`", skill.body))
    limits = CATALOG.limits
    for number in ("nodes", "depth", "spec_bytes", "list_items", "media", "html_bytes"):
        assert f"{limits[number]:,}" in skill.body, (
            f"the skill states the catalog's {number}"
        )


def test_every_card_the_cards_skill_writes_out_passes_the_check():
    examples = skill_examples()
    assert len(examples) == 4 and sum("html" in example for example in examples) == 1
    for example in examples:
        asked = media_requests(CATALOG, example.get("media", []))
        files = {
            one.name: one.kind or (CATALOG.kind_of(one.path) if one.path else "image")
            for one in asked
        }
        data, inputs = card(
            CATALOG,
            "ui-skill",
            example["title"],
            example.get("components"),
            example.get("html"),
            example.get("submit"),
            example.get("waits", False),
            example.get("height"),
            files,
            example.get("instant", False),
        )
        # Each asks for an answer, by its button or by its one choice, and waits for it
        assert (
            bool(data["submit"]) != bool(data.get("instant")) and data["waits"] is True
        )
        assert inputs or data["kind"] == "html", example["title"]
