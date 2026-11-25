# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Interactive cards: the catalog, the check a card passes, and the tool that shows one.

The catalog is `moody/ui.json`, the file the app renders from, so what is held
here is that the two cannot drift: every kind of property the catalog uses has
a check, a card that uses every component passes, and the tool's reference
names all of them. The check is held by what it tells the model, since a
refusal is only worth as much as what it lets the model fix: each case is a
card with one mistake and the words its problem has to carry. Run with
`pytest moody/control`.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from genui import ID, Check, Invalid, MediaRequest, card, catalog, media_requests

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
        ['options[0] (option) has no property "img"', 'Did you mean "image"?'],
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
    assert inputs["warmth"] == "slider" and len(inputs) == 16
    plain, none = shown(components={"type": "image", "src": "shot"})
    assert plain["submit"] is None and plain["waits"] is False and none == {}


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
    for name, spec in CATALOG.adjustments.items():
        assert f"{name} {spec['min']}..{spec['max']}" in reference
    assert "finishes: original, clay, metal, gloss, wire." in reference
