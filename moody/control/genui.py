# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Interactive cards: the catalog of what a card is made of, and the check a card passes before it is shown.

The agent answers with a card through one tool, `show_ui`, in one of two
kinds. A `components` card is a tree of the components `moody/ui.json`
defines, which the app renders itself; an `html` card is a document the agent
wrote, which the app runs in a sandboxed frame. Either way the card's event
(`ui` in `moody/STUDIO.md`) is written only once the card is known to render,
so the person never meets a broken one and the model is told what to fix
instead.

`moody/ui.json` is the one definition of the catalog. This module reads it
for three things, and the app reads the same file to render
(`moody/web/src/studio/ui`), so the tool's reference, the check, and the
renderers cannot drift apart:

- `reference` writes the catalog as the few lines the tool's definition
  carries: every component with its properties, the adjustments a picture
  takes, and the shorthand of each list item.
- `Check` walks a card's tree against the catalog. Every component's
  properties are checked by their `kind` (a string, a number in a range, one
  of an enumeration, the name of a file the card carries, a pixel icon, a
  list of a named shape, a condition, a map of adjustments), ids are
  collected, and whatever
  follows an input (`"$id"` in a bindable property, `{id}` in a text, a key of
  `when`) has to name one that exists. The rules that span properties are
  written against the properties, never against a component's name (a
  starting value lies between `min` and `max`, a chosen option is one of
  `options`, a row has a cell per column), so a new component is an entry in
  the catalog and nothing here.
- `limits` bounds a card: its nodes and depth, the size of its tree and of an
  `html` document, the files it carries. A limit is catalog data, changed
  there.

A problem is a sentence the model can act on: where it is in the tree, which
component and property, what was expected, and the nearest name where one was
misspelled. A card with several problems is refused with all of them, up to
`limits.problems`, so it is fixed in one more call rather than one per
mistake.

A card with a `submit` label locks when its button is pressed. A card may be
`instant` instead: it has no button, and choosing locks it at once. That is
only sound where the choice is all there is to set, so the check allows it for
a `components` card whose one input is a single choice: a component the
catalog marks `instant`, not taking several.

A card names the files it shows in `media`, each by a library tag or by a
file an engine wrote in the project's folder (`media_requests`); the
components refer to them by name, and the check knows each one's kind before
any file is read, so a card that would be refused costs no upload.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

HERE = Path(__file__).resolve().parent
KINDS = ("components", "html")
# An input's id, which is also how a text and a binding name it
ID = re.compile(r"[a-z][a-z0-9_]{0,31}")
# A media file's name within its card
MEDIA_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
# A bindable property's value that follows an input: `$` and the input's id
BINDING = re.compile(r"\$([a-z][a-z0-9_]{0,31})")
# An input's value shown in a text
PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]{0,31})\}")
COLOR = re.compile(r"#[0-9a-fA-F]{6}")
# The one comparison a `when` entry may make in place of naming a value
COMPARISONS = ("not", "gt", "lt", "has")
# What an `html` card's document calls to report or lock in its value
BRIDGE_CALLS = ("moody.setState", "moody.submit")
# The longest value of an option or a cell
VALUE_CHARS = 200
SCALARS = (str, int, float, bool)


def catalog_path() -> Path:
    """Where the catalog is: beside this module in the deployed image, `moody/ui.json` in the repository."""
    for candidate in (HERE / "ui.json", HERE.parent / "ui.json"):
        if candidate.is_file():
            return candidate
    return HERE / "ui.json"


@dataclass(frozen=True)
class UiCatalog:
    """The catalog of `moody/ui.json`: components, the shapes of their list items, adjustments, and limits."""

    data: dict[str, Any]

    @classmethod
    def read(cls, path: Path) -> UiCatalog:
        return cls(json.loads(path.read_text()))

    @property
    def components(self) -> dict[str, dict[str, Any]]:
        return self.data["components"]

    @property
    def shapes(self) -> dict[str, dict[str, Any]]:
        return self.data["shapes"]

    @property
    def limits(self) -> dict[str, int]:
        return self.data["limits"]

    @property
    def adjustments(self) -> dict[str, dict[str, Any]]:
        return self.data["adjustments"]

    def properties(self, component: str) -> dict[str, dict[str, Any]]:
        """Every property a component takes: its own, then the ones every component takes."""
        return {**self.components[component]["props"], **self.data["common"]}

    def values(self, spec: dict[str, Any]) -> list[Any]:
        """What an enumerated property may be: its own list, or the catalog's list or table it names."""
        values = spec["values"]
        return list(self.data[values]) if isinstance(values, str) else values

    def kind_of(self, name: str) -> str:
        """What a file is to a card, by its name's ending: one of `media_kinds`, and `file` for anything else."""
        ending = PurePosixPath(name).suffix.lower()
        return next(
            (
                kind
                for kind, endings in self.data["media_kinds"].items()
                if ending in endings
            ),
            "file",
        )

    def signature(self, properties: dict[str, dict[str, Any]]) -> str:
        """Properties as one line: `*` after a required one, `~` after one that can follow an input, `=` a default."""
        return ", ".join(
            name
            + ("*" if spec.get("required") else "")
            + ("~" if spec.get("bind") else "")
            + (
                f"={json.dumps(spec['default'])}"
                if "default" in spec and not spec.get("required")
                else ""
            )
            for name, spec in properties.items()
        )

    def reference(self) -> str:
        """The catalog as the tool's definition carries it: a line per component, then the vocabulary they share."""
        lines = [
            'A card is one component: {"type": name, ...properties}, with others in `children`. An input has an `id`, '
            'and the card\'s answer is {id: value}. Marks: * required, ~ also takes "$id" to follow that input live, '
            "= the default. A text shows an input's value as {id}. Every component also takes `when`: "
            + self.data["common"]["when"]["doc"],
        ]
        for group in dict.fromkeys(
            entry["group"] for entry in self.components.values()
        ):
            lines.append(f"{group.capitalize()}:")
            for name, entry in self.components.items():
                if entry["group"] == group:
                    answer = f" Answer: {entry['input']}." if "input" in entry else ""
                    lines.append(
                        f"- {name}({self.signature(entry['props'])}): {entry['doc']}{answer}"
                    )
        lines.append("List items:")
        for name, shape in self.shapes.items():
            lines.append(
                f"- {name} {{{self.signature(shape['props'])}}}: {shape['doc']}"
            )
        ranges = ", ".join(
            f"{name} {spec['min']}..{spec['max']}"
            for name, spec in self.adjustments.items()
        )
        lines.append(f'`adjust` is {{name: number | "$id"}} over: {ranges}.')
        for enumeration in ("finishes", "blends"):
            lines.append(f"{enumeration}: {', '.join(self.data[enumeration])}.")
        return "\n".join(lines)


@cache
def catalog() -> UiCatalog:
    """The catalog, read once per process."""
    return UiCatalog.read(catalog_path())


class Invalid(Exception):
    """A card the catalog does not allow: every problem found, each a sentence the model can act on."""

    def __init__(self, problems: list[str], more: int = 0) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems
        self.more = more

    @property
    def message(self) -> str:
        """The refusal as the model reads it."""
        rest = f"\n- and {self.more} more of the same kind." if self.more else ""
        return (
            "The card was not shown. Fix this and call show_ui again:\n"
            + "\n".join(f"- {one}" for one in self.problems)
            + rest
        )


def article(noun: str) -> str:
    """A noun with its indefinite article."""
    return f"{'an' if noun[0] in 'aeiou' else 'a'} {noun}"


def nearest(name: Any, known: list[str]) -> str:
    """A hint for a name that is not one of the known ones: the closest of them, where one is close."""
    close = difflib.get_close_matches(str(name), known, n=1, cutoff=0.6)
    return f' Did you mean "{close[0]}"?' if close else ""


def stored_kind(catalog: UiCatalog, item: dict[str, Any]) -> str:
    """What a library entry's file is to a card: what its name's ending says, else what the library holds it as."""
    named = catalog.kind_of(item.get("name", ""))
    return named if named != "file" else item.get("kind", "file")


def key(value: Any) -> str:
    """A value as it compares to another: by its JSON, so 1, true, and "1" stay three values."""
    return json.dumps(value, sort_keys=True)


class Check:
    """One walk of a card's tree against the catalog, collecting what is wrong with it (`problems`).

    `media` is the card's files by name, each with its kind; `inputs` ends as
    the component of each id.
    """

    def __init__(self, catalog: UiCatalog, media: dict[str, str]) -> None:
        self.catalog = catalog
        self.media = media
        self.problems: list[str] = []
        self.inputs: dict[str, str] = {}
        # Each input as the card wrote it, by its id
        self.written: dict[str, dict[str, Any]] = {}
        # Where each id was defined, to name it when another component takes the same one
        self.defined: dict[str, str] = {}
        # What follows an input, to resolve once every id is known: where, and the id
        self.follows: list[tuple[str, str]] = []
        self.nodes = 0

    def problem(self, text: str) -> None:
        self.problems.append(text)

    def wrong(self, where: str, expected: str, value: Any) -> None:
        """A value of the wrong type."""
        shown = json.dumps(value)
        self.problem(
            f"{where} should be {expected}; it is {shown if len(shown) <= 60 else shown[:57] + '...'}."
        )

    def unknown(self, where: str, name: str, known: list[str]) -> None:
        """A property the component or item does not take."""
        self.problem(
            f'{where} has no property "{name}".{nearest(name, known)} It takes: {", ".join(known)}.'
        )

    # The tree

    def node(self, value: Any, where: str, depth: int, parent: str | None) -> None:
        """Check one component and everything under it."""
        components = self.catalog.components
        if not isinstance(value, dict) or not isinstance(value.get("type"), str):
            self.problem(
                f'{where} should be a component: an object with a "type", such as {{"type": "text", "text": "..."}}.'
            )
            return
        name = value["type"]
        if name not in components:
            self.problem(
                f'{where}: there is no component "{name}".{nearest(name, list(components))} The components are: {", ".join(components)}.'
            )
            # Its id still counts as one, so that what follows it is not reported as a second problem of the same mistake
            self.define(value, f"{where} ({name})", name)
            return
        here = f"{where} ({name})"
        self.nodes += 1
        if depth > self.catalog.limits["depth"]:
            self.problem(
                f"{here} is nested deeper than {self.catalog.limits['depth']} levels; flatten the layout."
            )
            return
        entry = components[name]
        if "inside" in entry and parent not in entry["inside"]:
            self.problem(
                f"{here} belongs directly inside {' or '.join(entry['inside'])}."
            )
        properties = self.catalog.properties(name)
        self.define(value, here, name)
        for given in value:
            if given != "type" and given not in properties:
                self.unknown(here, given, list(properties))
        for prop, spec in properties.items():
            if prop not in value:
                if spec.get("required"):
                    self.problem(
                        f'{here} is missing "{prop}"'
                        + (f": {spec['doc']}" if "doc" in spec else ".")
                    )
            elif spec["kind"] == "nodes":
                self.children(spec, value[prop], f"{where}.{prop}", depth, name)
            else:
                self.prop(spec, value[prop], f"{here}.{prop}")
        self.consistent(properties, value, here)

    def define(self, value: dict[str, Any], here: str, component: str) -> None:
        """Note a component's id as an input's, refusing one another component took."""
        given = value.get("id")
        if not isinstance(given, str) or not ID.fullmatch(given):
            return
        if given in self.defined:
            self.problem(
                f'{here}: the id "{given}" is already taken by {self.defined[given]}; every input needs its own.'
            )
        else:
            self.defined[given] = here
            self.inputs[given] = component
            self.written[given] = value

    def children(
        self, spec: dict[str, Any], value: Any, where: str, depth: int, parent: str
    ) -> None:
        """Check a component's children, which may be limited to some components (`only`)."""
        if not isinstance(value, list) or not value:
            self.wrong(where, "a list of at least one component", value)
            return
        for index, child in enumerate(value):
            only = spec.get("only")
            if (
                only
                and isinstance(child, dict)
                and child.get("type") in self.catalog.components
                and child["type"] not in only
            ):
                self.problem(
                    f"{where}[{index}] ({child['type']}): a {parent} holds only {' or '.join(only)} components; put this inside one."
                )
            else:
                self.node(child, f"{where}[{index}]", depth + 1, parent)

    # A property, by its kind

    def prop(self, spec: dict[str, Any], value: Any, where: str) -> None:
        """Check one property's value against its definition."""
        if (
            spec.get("bind")
            and isinstance(value, str)
            and (bound := BINDING.fullmatch(value))
        ):
            self.follows.append((where, bound[1]))
            return
        getattr(self, f"kind_{spec['kind']}")(spec, value, where)

    def bindable(self, spec: dict[str, Any], expected: str) -> str:
        """What a property expects, said with the binding it also takes."""
        return (
            f'{expected}, or "$id" to follow an input' if spec.get("bind") else expected
        )

    def kind_string(self, spec: dict[str, Any], value: Any, where: str) -> None:
        limit = self.catalog.limits["text_chars"]
        if not isinstance(value, str):
            self.wrong(where, self.bindable(spec, "a string"), value)
        elif len(value) > limit:
            self.problem(f"{where} is {len(value)} characters; keep it under {limit}.")

    def kind_text(self, spec: dict[str, Any], value: Any, where: str) -> None:
        self.kind_string(spec, value, where)
        if isinstance(value, str):
            self.follows.extend((where, name) for name in PLACEHOLDER.findall(value))

    def kind_number(self, spec: dict[str, Any], value: Any, where: str) -> None:
        whole = spec["kind"] == "integer"
        if isinstance(value, bool) or not isinstance(
            value, int if whole else (int, float)
        ):
            self.wrong(
                where,
                self.bindable(spec, "a whole number" if whole else "a number"),
                value,
            )
        elif ("min" in spec and value < spec["min"]) or (
            "max" in spec and value > spec["max"]
        ):
            self.problem(
                f"{where} should be from {spec.get('min', 'any')} to {spec.get('max', 'any')}; it is {value}."
            )

    kind_integer = kind_number

    def kind_boolean(self, spec: dict[str, Any], value: Any, where: str) -> None:
        if not isinstance(value, bool):
            self.wrong(where, self.bindable(spec, "true or false"), value)

    def kind_enum(self, spec: dict[str, Any], value: Any, where: str) -> None:
        values = self.catalog.values(spec)
        if value not in values:
            self.problem(
                f"{where} should be one of {', '.join(values)}; it is {json.dumps(value)}.{nearest(value, values)}"
            )

    def kind_id(self, spec: dict[str, Any], value: Any, where: str) -> None:
        if not isinstance(value, str) or not ID.fullmatch(value):
            self.wrong(
                where,
                "a short id of lowercase letters, digits, and _ that starts with a letter, like warmth",
                value,
            )

    def kind_media(self, spec: dict[str, Any], value: Any, where: str) -> None:
        kinds = spec["kinds"]
        wanted = " or ".join(
            article(kind) if index == 0 else kind for index, kind in enumerate(kinds)
        )
        if not isinstance(value, str):
            self.wrong(where, f"the name of {wanted} in the card's media", value)
        elif value not in self.media:
            carried = (
                f"Its media are: {', '.join(self.media)}."
                if self.media
                else "It carries none."
            )
            self.problem(
                f'{where} names the media "{value}", which this card does not carry.{nearest(value, list(self.media))} '
                f"{carried} Add the file to `media`, by a library tag or an engine's file."
            )
        elif self.media[value] not in kinds:
            self.problem(
                f'{where} needs {wanted}, but the media "{value}" is {article(self.media[value])}.'
            )

    def kind_color(self, spec: dict[str, Any], value: Any, where: str) -> None:
        if not isinstance(value, str) or not COLOR.fullmatch(value):
            self.wrong(where, self.bindable(spec, "a color as #rrggbb"), value)

    def kind_icon(self, spec: dict[str, Any], value: Any, where: str) -> None:
        """Check a pixel icon: a square of rows of `0` and `1`, of a side within the catalog's limits."""
        low, high = self.catalog.limits["icon_min"], self.catalog.limits["icon_max"]
        asked = f'a pixel icon: {low} to {high} rows of as many characters, each 0 or 1, such as ["00111100", "01000010", ...]'
        if not isinstance(value, list) or not all(
            isinstance(row, str) for row in value
        ):
            self.wrong(where, asked, value)
            return
        side = len(value)
        uneven = next(
            (index for index, row in enumerate(value) if len(row) != side), None
        )
        marked = next(
            (index for index, row in enumerate(value) if set(row) - {"0", "1"}), None
        )
        if not low <= side <= high:
            self.problem(f"{where} should be {asked}; it has {side} rows.")
        elif uneven is not None:
            self.problem(
                f"{where} should be a square: {side} rows of {side} characters each; row {uneven + 1} has {len(value[uneven])}."
            )
        elif marked is not None:
            self.problem(
                f"{where} should hold only 0 and 1; row {marked + 1} is {json.dumps(value[marked])}."
            )
        elif not any("1" in row for row in value):
            self.problem(f"{where} has no cell filled: draw the icon with 1s.")

    def kind_value(self, spec: dict[str, Any], value: Any, where: str) -> None:
        if not isinstance(value, SCALARS):
            self.wrong(where, "a string, a number, or true or false", value)
        elif isinstance(value, str) and len(value) > VALUE_CHARS:
            self.problem(
                f"{where} is {len(value)} characters; keep a value under {VALUE_CHARS}."
            )

    def kind_any(self, spec: dict[str, Any], value: Any, where: str) -> None:
        """A value whose shape depends on another property, which `consistent` checks."""

    def kind_list(self, spec: dict[str, Any], value: Any, where: str) -> None:
        if not isinstance(value, list):
            self.wrong(where, "a list", value)
            return
        least, most = (
            spec.get("min_items", 1 if spec.get("required") else 0),
            spec.get("max_items", self.catalog.limits["list_items"]),
        )
        if not least <= len(value) <= most:
            self.problem(
                f"{where} should have from {least} to {most} items; it has {len(value)}."
            )
            return
        of = spec["of"]
        for index, item in enumerate(value):
            if isinstance(of, str):
                self.shape(of, item, f"{where}[{index}]")
            else:
                self.prop(of, item, f"{where}[{index}]")

    def shape(self, name: str, value: Any, where: str) -> None:
        """Check one item of a list against its shape; a bare value stands for the shape's `short` property."""
        shape = self.catalog.shapes[name]
        properties = shape["props"]
        if not isinstance(value, dict):
            if "short" not in shape or isinstance(value, list):
                self.wrong(
                    where,
                    f"{article(name)}: an object with {', '.join(properties)}",
                    value,
                )
                return
            value = {shape["short"]: value}
        for given in value:
            if given not in properties:
                self.unknown(f"{where} ({name})", given, list(properties))
        for prop, spec in properties.items():
            if prop in value:
                self.prop(spec, value[prop], f"{where}.{prop}")
            elif spec.get("required"):
                self.problem(f'{where} ({name}) is missing "{prop}".')
        # What an item shows in one place, it shows one of
        either = shape.get("one_of", [])
        given = [prop for prop in either if prop in value]
        if len(given) > 1:
            self.problem(
                f"{where} ({name}) has {' and '.join(given)}, but {article(name)} shows one of {', '.join(either)}. Keep one."
            )

    def kind_when(self, spec: dict[str, Any], value: Any, where: str) -> None:
        if not isinstance(value, dict) or not value:
            self.wrong(where, 'a condition such as {"mode": "night"}', value)
            return
        for given, condition in value.items():
            self.follows.append((where, given))
            if isinstance(condition, dict):
                if len(condition) != 1 or next(iter(condition)) not in COMPARISONS:
                    self.wrong(
                        f"{where}.{given}",
                        f"a value, a list of values, or one of {', '.join(f'{{{c}: value}}' for c in COMPARISONS)}",
                        condition,
                    )
                elif not isinstance(next(iter(condition.values())), SCALARS):
                    self.wrong(
                        f"{where}.{given}",
                        "a comparison with a string, a number, or true or false",
                        condition,
                    )
            elif isinstance(condition, list):
                if not condition or not all(
                    isinstance(one, SCALARS) for one in condition
                ):
                    self.wrong(
                        f"{where}.{given}",
                        "a list of the values that show the component",
                        condition,
                    )
            elif not isinstance(condition, SCALARS):
                self.wrong(
                    f"{where}.{given}", "the value that shows the component", condition
                )

    def kind_adjust(self, spec: dict[str, Any], value: Any, where: str) -> None:
        adjustments = self.catalog.adjustments
        if not isinstance(value, dict):
            self.wrong(
                where, 'adjustments such as {"warmth": "$warmth", "grain": 20}', value
            )
            return
        for name, amount in value.items():
            if name not in adjustments:
                self.problem(
                    f'{where}: there is no adjustment "{name}".{nearest(name, list(adjustments))} The adjustments are: {", ".join(adjustments)}.'
                )
            elif isinstance(amount, str) and (bound := BINDING.fullmatch(amount)):
                self.follows.append((f"{where}.{name}", bound[1]))
            else:
                self.kind_number(
                    {"kind": "number", "bind": True, **adjustments[name]},
                    amount,
                    f"{where}.{name}",
                )

    # Rules that span properties, written against the properties so that they hold for any component that has them

    def consistent(
        self, properties: dict[str, dict[str, Any]], value: dict[str, Any], here: str
    ) -> None:
        """Check what a component's properties have to agree on."""

        def number(prop: str) -> float | None:
            given = value.get(prop, properties.get(prop, {}).get("default"))
            return (
                given
                if isinstance(given, (int, float)) and not isinstance(given, bool)
                else None
            )

        low, high, start, step = (
            number("min"),
            number("max"),
            number("value"),
            number("step"),
        )
        if low is not None and high is not None and low >= high:
            self.problem(f"{here}: min ({low}) should be below max ({high}).")
        elif (
            start is not None
            and "value" in value
            and (
                (low is not None and start < low) or (high is not None and start > high)
            )
        ):
            self.problem(
                f"{here}: value ({start}) should lie from min ({low}) to max ({high})."
            )
        if step is not None and step <= 0:
            self.problem(f"{here}: step should be above 0; it is {step}.")
        allowed: list[Any] | None = None
        if isinstance(value.get("options"), list):
            options = [
                option.get("value") if isinstance(option, dict) else option
                for option in value["options"]
            ]
            allowed = [option for option in options if isinstance(option, SCALARS)]
            self.distinct(allowed, f"{here}.options", "option values")
        elif isinstance(value.get("rows"), list) and isinstance(
            value.get("columns"), list
        ):
            rows = [row for row in value["rows"] if isinstance(row, list)]
            for index, row in enumerate(rows):
                if len(row) != len(value["columns"]):
                    self.problem(
                        f"{here}.rows[{index}] has {len(row)} cells for {len(value['columns'])} columns."
                    )
            allowed = [row[0] for row in rows if row and isinstance(row[0], SCALARS)]
            if "id" in value:
                self.distinct(
                    allowed,
                    f"{here}.rows",
                    "first cells, which are what a picked row answers with",
                )
        if allowed is not None and "value" in value and "value" in properties:
            listed = properties["value"]["kind"] == "list"
            many = listed or value.get("many") is True or value.get("pick") == "many"
            chosen = value["value"]
            if many != isinstance(chosen, list):
                # A value that is always a list was already checked as one
                if not listed:
                    self.problem(
                        f"{here}.value should be {'a list of the values chosen at first' if many else 'one value, not a list'}."
                    )
            elif any(
                key(one) not in map(key, allowed)
                for one in (chosen if many else [chosen])
            ):
                self.problem(
                    f"{here}.value should be {'among' if many else 'one of'} its {'options' if 'options' in value else 'rows'}: {', '.join(map(key, allowed))}."
                )
        tabs = (
            [
                child
                for child in value.get("children", [])
                if isinstance(child, dict) and child.get("type") == "tab"
            ]
            if isinstance(value.get("children"), list)
            else []
        )
        if tabs and "id" in value:
            self.distinct(
                [tab.get("value", tab.get("label")) for tab in tabs],
                f"{here}.children",
                "tab values",
            )

    def distinct(self, values: list[Any], where: str, what: str) -> None:
        """Refuse values that repeat where each has to tell one choice from another."""
        keys = [key(value) for value in values]
        twice = next((value for value in values if keys.count(key(value)) > 1), None)
        if twice is not None:
            self.problem(
                f"{where}: {what} should each be different; {json.dumps(twice)} is there more than once."
            )

    # The whole card

    def single_choice(self) -> str | None:
        """Why the card cannot be instant, or `None` where its one input is a single choice."""
        allowed = instant_inputs(self.catalog)
        kinds = " or ".join(allowed)
        if len(self.inputs) != 1:
            has = (
                f"{len(self.inputs)} inputs: {', '.join(self.inputs)}"
                if self.inputs
                else "none"
            )
            return (
                f"instant is for a card whose one input is a single choice ({kinds}); this card has {has}. "
                "Give submit instead, or ask for the one choice alone."
            )
        ((given, component),) = self.inputs.items()
        if component not in allowed:
            return (
                f'instant needs the card\'s one input to be a single choice ({kinds}); "{given}" is {article(component)}. '
                "Give submit instead."
            )
        if self.written[given].get("many") is True:
            return f'instant needs a single choice, but "{given}" takes many. Give submit instead, or leave many out.'
        return None

    def run(self, spec: Any) -> None:
        """Check a card's tree and what in it follows which input.

        Raises:
            Invalid: with every problem found, up to the catalog's `problems`.
        """
        limits = self.catalog.limits
        size = len(json.dumps(spec))
        if size > limits["spec_bytes"]:
            raise Invalid(
                [
                    f"components is {size} bytes, over the {limits['spec_bytes']} a card may be. Show less in one card: fewer options or rows, or two cards."
                ]
            )
        self.node(spec, "components", 1, None)
        if self.nodes > limits["nodes"]:
            self.problem(
                f"The card has {self.nodes} components, over the {limits['nodes']} one may have. Show less in one card."
            )
        for where, followed in self.follows:
            if followed not in self.inputs:
                known = (
                    f"The ids are: {', '.join(self.inputs)}."
                    if self.inputs
                    else "No component has an id yet."
                )
                self.problem(
                    f'{where} follows the input "{followed}", but no component has that id.{nearest(followed, list(self.inputs))} {known}'
                )
        if self.problems:
            shown = list(dict.fromkeys(self.problems))
            raise Invalid(
                shown[: limits["problems"]], max(0, len(shown) - limits["problems"])
            )


@dataclass(frozen=True)
class MediaRequest:
    """One file a card asks for: the name its components know it by, and where it comes from."""

    name: str
    # A library entry's tag, or an engine and a path in the project's folder on it
    tag: str | None = None
    engine_id: str | None = None
    path: str | None = None
    # Which of an entry's files, or what the engine's file is, where the name's ending does not say
    kind: str | None = None


def media_requests(catalog: UiCatalog, items: Any) -> list[MediaRequest]:
    """What a card's `media` asks for, each file under the name its components use.

    A file is a library entry by its `tag`, or an engine's file by
    `engine_id` and `path`. Its name is given, or is the tag without its `@`,
    or the file's name without its ending.

    Raises:
        Invalid: for an item that is neither, more files than a card may carry, or two under one name.
    """
    limits = catalog.limits
    kinds = [*catalog.data["media_kinds"], "file"]
    if not isinstance(items, list):
        raise Invalid(
            [
                'media should be a list such as [{"tag": "@mara"}, {"engine_id": "...", "path": "previews/frame.png"}].'
            ]
        )
    if len(items) > limits["media"]:
        raise Invalid(
            [
                f"media has {len(items)} files, over the {limits['media']} a card may carry. Show the ones that matter."
            ]
        )
    problems: list[str] = []
    requests: list[MediaRequest] = []
    for index, item in enumerate(items):
        where = f"media[{index}]"
        if not isinstance(item, dict):
            problems.append(
                f'{where} should be an object: {{"tag": "@mara"}} for a library entry, or {{"engine_id": "...", "path": "..."}} for an engine\'s file.'
            )
            continue
        tag, engine_id, path, kind = (
            item.get(field) for field in ("tag", "engine_id", "path", "kind")
        )
        from_library = isinstance(tag, str) and bool(tag.strip("@ "))
        from_engine = (
            isinstance(engine_id, str)
            and isinstance(path, str)
            and bool(engine_id)
            and bool(path)
        )
        if from_library == from_engine:
            problems.append(
                f'{where} should name one file: a library entry by "tag", or an engine\'s file by "engine_id" and "path".'
            )
            continue
        stem = tag.strip("@ ") if from_library else PurePosixPath(path).stem
        name = item.get(
            "name", re.sub(r"[^a-z0-9_-]+", "-", stem.lower()).strip("-")[:48]
        )
        if not isinstance(name, str) or not MEDIA_NAME.fullmatch(name):
            problems.append(
                f"{where}.name should be a short name of lowercase letters, digits, - and _, like hero; it is {json.dumps(name)}."
            )
        elif any(name == other.name for other in requests):
            problems.append(
                f'{where}: the name "{name}" is already another file\'s; give this one a "name" of its own.'
            )
        elif kind is not None and kind not in kinds:
            problems.append(
                f"{where}.kind should be one of {', '.join(kinds)}; it is {json.dumps(kind)}."
            )
        else:
            requests.append(
                MediaRequest(
                    name,
                    tag if from_library else None,
                    engine_id if from_engine else None,
                    path if from_engine else None,
                    kind,
                )
            )
    if problems:
        raise Invalid(
            problems[: limits["problems"]], max(0, len(problems) - limits["problems"])
        )
    return requests


def card(
    catalog: UiCatalog,
    ui_id: str,
    title: Any,
    components: Any,
    html: Any,
    submit: Any,
    waits: Any,
    height: Any,
    media: dict[str, str],
    instant: Any = False,
) -> tuple[dict[str, Any], dict[str, str]]:
    """A card's `ui` event without its files, and its inputs by id, once it is known to render.

    `media` is the card's files by name, each with its kind. The event
    carries `spec` for a `components` card and `html` (with `height`, the
    frame's first height in pixels) for an `html` one, and `instant` for a
    card that locks on its one choice.

    Raises:
        Invalid: for a card that is not exactly one of the two kinds, one the catalog does not
            allow, one over a limit, one that waits for an answer it gives no way to send, or an
            instant card that is anything but one single choice.
    """
    limits = catalog.limits
    problems: list[str] = []
    if not isinstance(title, str) or not title.strip():
        problems.append("title should say what the card is, in a few words.")
    elif len(title) > limits["title_chars"]:
        problems.append(
            f"title is {len(title)} characters; keep it under {limits['title_chars']}."
        )
    if submit is not None and (
        not isinstance(submit, str)
        or not submit.strip()
        or len(submit) > limits["submit_chars"]
    ):
        problems.append(
            f"submit should be the lock-in button's label, up to {limits['submit_chars']} characters, such as Lock in this look."
        )
    if not isinstance(instant, bool):
        problems.append("instant should be true or false.")
    elif instant and submit is not None:
        problems.append(
            "instant is true and there is a submit label, but an instant card has no lock-in button: the choice itself "
            "locks it. Give one of the two."
        )
    elif instant and html is not None:
        problems.append(
            "instant is for a components card whose one input is a single choice. An html card locks on a gesture of "
            "its own by calling moody.submit(value), under a submit label."
        )
    if waits and submit is None and instant is not True:
        problems.append(
            "waits is true but there is no submit label, so the person could never lock the card in. Give submit (or "
            "instant, for a card of one choice), or leave waits out."
        )
    if (components is None) == (html is None):
        problems.append(
            "Give exactly one of components (a tree from the catalog) and html (a document of your own)."
        )
    if problems:
        raise Invalid(problems)
    data: dict[str, Any] = {
        "ui_id": ui_id,
        "title": title.strip(),
        "kind": KINDS[0] if html is None else KINDS[1],
        "submit": submit.strip() if submit else None,
        "waits": bool(waits),
    }
    if html is None:
        check = Check(catalog, media)
        check.run(components)
        if instant:
            refused = check.single_choice()
            if refused is not None:
                raise Invalid([refused])
            data["instant"] = True
        return {**data, "spec": components}, check.inputs
    if not isinstance(html, str) or not html.strip():
        raise Invalid(
            [
                "html should be the card's document: markup with its style and script inline."
            ]
        )
    size = len(html.encode())
    if size > limits["html_bytes"]:
        raise Invalid(
            [
                f"html is {size} bytes, over the {limits['html_bytes']} a card's document may be. Make it lighter: generate "
                "what it draws in script rather than writing it out, and carry pictures and sound as `media`, not inline."
            ]
        )
    if submit is not None and not any(call in html for call in BRIDGE_CALLS):
        raise Invalid(
            [
                f"The card has a submit label, but its document never calls {' or '.join(BRIDGE_CALLS)}, so there would be "
                "nothing to send back. Call moody.setState(value) whenever the person changes something."
            ]
        )
    if height is not None and (
        isinstance(height, bool)
        or not isinstance(height, int)
        or not limits["height_min"] <= height <= limits["height_max"]
    ):
        raise Invalid(
            [
                f"height should be the frame's first height in pixels, from {limits['height_min']} to {limits['height_max']}."
            ]
        )
    return {**data, "html": html, "height": height or limits["height_default"]}, {}


DESCRIPTION = (
    "Answer with an interactive card in the conversation: something the person sees, plays with, and locks in, where "
    "prose or a list of options would make them imagine it. Give `components`, a tree of the catalog's components "
    "(which covers most cards with no code), or `html`, a document of your own run in a sandboxed frame (for what the "
    "catalog cannot express). With `submit`, the card has a lock-in button of that label, and pressing it sends the "
    "card's values back to you as the person's next message; `waits: true` also ends your turn until they do. For "
    "one choice among a few, `instant: true` in place of `submit` makes the choice itself lock the card: one click "
    "and it is sent. A card that is not valid is not shown, and the result says what to fix."
)
HTML_REFERENCE = (
    "The card's document, or a fragment of one, with its style and script inline; it runs in a sandboxed frame with no "
    "network, no storage, and no access to the page. `window.moody` is there before your script runs: `moody.state` "
    "(null at first; the value last set, or locked in, when the card is shown again), `moody.locked` (true once locked "
    "in: show the value and change nothing), `moody.media.<name>` (an address for an img, audio, or video element), "
    "`await moody.load(name)` (the file's bytes as an ArrayBuffer, for decoding sound or reading pixels), "
    "`moody.setState(value)` (call it whenever the person changes something: the lock-in button sends the last value), "
    "and `moody.submit(value)` (locks in at once, for a card whose own gesture is the answer). Values are JSON. The "
    "frame's height follows the document. Use the theme's CSS variables so it looks like the conversation: "
    "--moody-bg, --moody-surface, --moody-line, --moody-fg, --moody-muted, --moody-lime (the person's action or "
    "selection), --moody-lavender (yours), --moody-font, --moody-mono; buttons, sliders, selects, and text inputs are "
    "already styled."
)


def instant_inputs(catalog: UiCatalog) -> list[str]:
    """The components that can be the one input of an instant card."""
    return [name for name, entry in catalog.components.items() if entry.get("instant")]


def properties(catalog: UiCatalog) -> dict[str, Any]:
    """The properties of `show_ui`'s input, the catalog's reference among them."""
    limits = catalog.limits
    return {
        "title": {
            "type": "string",
            "description": "What the card is, in a few words; its heading.",
        },
        "components": {"type": "object", "description": catalog.reference()},
        "html": {"type": "string", "description": HTML_REFERENCE},
        "submit": {
            "type": "string",
            "description": "The lock-in button's label, such as Lock in this look. Left out: the card sends nothing back, "
            "unless it is instant.",
        },
        "instant": {
            "type": "boolean",
            "description": "Lock the card as soon as the person chooses, with no lock-in button. Only for a components card "
            f"whose one input is a single choice ({' or '.join(instant_inputs(catalog))}, not many). Leave submit out.",
        },
        "waits": {
            "type": "boolean",
            "description": "End your turn here until the person locks the card in. Needs submit or instant.",
        },
        "media": {
            "type": "array",
            "description": f"The files the card shows, up to {limits['media']}, which components name by `name` and an html "
            'card reads from `moody.media`: {"tag": "@mara"} for a library entry\'s picture (its `kind` picks another of its '
            'files), or {"engine_id": "...", "path": "previews/frame.png"} for a file an engine wrote in the project\'s '
            "folder. `name` is the tag without its @, or the file's name without its ending, unless given.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "tag": {"type": "string"},
                    "engine_id": {"type": "string"},
                    "path": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": [*catalog.data["media_kinds"], "file"],
                    },
                },
            },
        },
        "height": {
            "type": "integer",
            "description": f"An html card's first height in pixels, {limits['height_min']} to {limits['height_max']}; it then follows the document.",
        },
    }
