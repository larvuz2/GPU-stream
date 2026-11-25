# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""What a project's agent is offered beside its tools: skills and subagents, both read from files.

A skill is a directory, `moody/skills/<name>/`, whose `SKILL.md` opens with
front matter (`name`, `description`, `disciplines`, `operator_tools`) and whose
other files are what its text sends the agent to. Nothing of a skill is put in the agent's
prompt here: the loop lists each offered skill by its description and loads
its text, then a reference file, when the work calls for it (`loop.py`), so
all this module decides is which skills a project is offered (`skills_for`).

A subagent is a file, `moody/agents/<name>.md`: front matter and the system
prompt the subagent works under (`AgentSpec`, the contract's format in
`moody/STUDIO.md`). A file whose name starts with `_` is a template, not an
agent. One template is read here: `_operator.md`, from which an operator is
derived for every app that can be started (`operators`), so a new engine gains
its operator with no definition written for it. An operator reads the skill
named after its app where there is one, and that skill may name tools its
operator gets beside the template's (`operator_tools`): what drives one
engine and no other, as the tools that open an Unreal project do. Which
subagents a project is offered follows the same rule as its skills
(`agents_for`): a definition's `disciplines`, and for an operator the
disciplines that have its app among their engines or are offered its skill.
A definition's text may open with a comment, its file's license header, which
is no part of what the model reads (`prose`).

The API reads the same definitions to list a project's skills and subagents
(`GET /v1/projects/{pid}/environment`), which is why they live apart from the
agent: nothing here knows the loop or a tool's implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from service import STARTABLE, Catalog

HERE = Path(__file__).resolve().parent
# The `disciplines` a skill or a subagent names to be offered to every project
EVERY_DISCIPLINE = "all"
# The model tiers a subagent's definition may name, the first being the agent's own model
MODEL_TIERS = ("inherit", "balanced", "light")
# The template an app's operator is made from, and the tools one drives its engine with unless the template says
OPERATOR_TEMPLATE = "_operator.md"
OPERATOR_TOOLS = ("engine_*", "preview")


@dataclass(frozen=True)
class Skill:
    """A skill of `moody/skills/<name>/`: its name, what it is for, the disciplines it is for, and where it is.

    `body` is the text of its `SKILL.md` after the front matter, which the
    loop reads from `directory` when the agent opens the skill.
    `operator_tools` are the tools the operator of the engine the skill is
    named after gets beside its template's.
    """

    name: str
    description: str
    disciplines: frozenset[str]
    body: str
    directory: Path
    operator_tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentSpec:
    """A subagent as its definition gives it, before anything of the loop is known.

    `tools` are Moody's tool names, or patterns over them (`engine_*`);
    `model` is one of `MODEL_TIERS`; `prompt` is the system prompt it works
    under.
    """

    name: str
    title: str
    description: str
    disciplines: frozenset[str]
    tools: tuple[str, ...]
    skills: tuple[str, ...]
    model: str
    prompt: str


def bundled(name: str) -> Path:
    """Where a directory of definitions is: beside this module in the deployed image, under `moody/` in the repository."""
    for candidate in (HERE / name, HERE.parent / name):
        if candidate.is_dir():
            return candidate
    return HERE / name


def skills_directory() -> Path:
    """Where the skills are."""
    return bundled("skills")


def agents_directory() -> Path:
    """Where the subagents' definitions are."""
    return bundled("agents")


def front_matter(text: str) -> tuple[dict[str, str], str]:
    """A Markdown file's front matter, as `key: value` lines, and the text after it."""
    if not text.startswith("---\n"):
        return {}, text
    head, _, body = text[4:].partition("\n---")
    fields = {}
    for line in head.splitlines():
        key, colon, value = line.partition(":")
        if colon and key.strip() and not line.startswith((" ", "\t")):
            fields[key.strip()] = value.strip().strip("\"'")
    return fields, body.lstrip("-").lstrip("\n")


def listed(value: str) -> tuple[str, ...]:
    """The items of a front matter value written as a list: `a, b` or `[a, b]`."""
    return tuple(
        part.strip() for part in value.strip().strip("[]").split(",") if part.strip()
    )


def read_skills(directory: Path) -> list[Skill]:
    """Every skill under a directory, in name order.

    A skill says which disciplines it is for with a `disciplines` line in its
    front matter (`disciplines: media, animation`, or `disciplines: all` for
    every project); one that does not is for the disciplines that use the
    engine it is named after, and one named after no engine is for every
    discipline (`skills_for`).
    """
    skills = []
    for path in sorted(directory.glob("*/SKILL.md")):
        fields, body = front_matter(path.read_text())
        disciplines = frozenset(
            part.lower() for part in listed(fields.get("disciplines", ""))
        )
        skills.append(
            Skill(
                path.parent.name,
                fields.get("description", ""),
                disciplines,
                body.strip(),
                path.parent,
                listed(fields.get("operator_tools", "")),
            )
        )
    return skills


def skills_for(skills: list[Skill], catalog: Catalog, discipline: str) -> list[Skill]:
    """The skills that fit a discipline, which those for every discipline (`EVERY_DISCIPLINE`) always do."""
    engines = set(catalog.disciplines.get(discipline, {}).get("engines", []))
    return [
        skill
        for skill in skills
        if not skill.disciplines.isdisjoint((discipline, EVERY_DISCIPLINE))
        or (
            not skill.disciplines
            and (skill.name in engines or skill.name not in catalog.apps)
        )
    ]


def spec(
    name: str, fields: dict[str, str], prompt: str, tools: tuple[str, ...] = ()
) -> AgentSpec:
    """A subagent from a definition's front matter and text.

    Raises:
        ValueError: The definition names a model tier there is none of.
    """
    model = fields.get("model", "").lower() or MODEL_TIERS[0]
    if model not in MODEL_TIERS:
        raise ValueError(
            f"the subagent {name} names the model tier {model!r}; the tiers are {', '.join(MODEL_TIERS)}"
        )
    return AgentSpec(
        name=name,
        title=fields.get("title")
        or f"{name.replace('-', ' ').replace('_', ' ').capitalize()} agent",
        description=fields.get("description", ""),
        disciplines=frozenset(
            part.lower() for part in listed(fields.get("disciplines", ""))
        )
        or frozenset({EVERY_DISCIPLINE}),
        tools=listed(fields.get("tools", "")) or tools,
        skills=listed(fields.get("skills", "")),
        model=model,
        prompt=prose(prompt),
    )


def prose(text: str) -> str:
    """A definition's text as the model reads it: without the comment it opens with, its file's license header."""
    body = text.strip()
    if body.startswith("<!--"):
        _, closed, rest = body.partition("-->")
        body = rest.strip() if closed else body
    return body


def read_agents(directory: Path) -> list[AgentSpec]:
    """Every subagent a directory defines, in name order: its `<name>.md` files, the templates (`_...`) left out.

    A subagent's id is its file's stem, which its `name` line repeats; one
    that names no disciplines is for every project. A Markdown file that does
    not open with front matter defines nothing: it is the directory's own
    documentation.

    Raises:
        ValueError: A definition's `name` is not its file's stem, or its model tier is none.
    """
    agents = []
    for path in sorted(directory.glob("*.md")) if directory.is_dir() else []:
        fields, prompt = front_matter(path.read_text())
        if path.name.startswith("_") or not fields:
            continue
        if fields.get("name", path.stem) != path.stem:
            raise ValueError(
                f"{path.name} names its subagent {fields['name']!r}; a subagent's id is its file's stem"
            )
        agents.append(spec(path.stem, fields, prompt))
    return agents


def operators(
    directory: Path, catalog: Catalog, skills: list[Skill]
) -> list[AgentSpec]:
    """One operator per app that can be started, made from the directory's template.

    The template's `{app}` and `{name}` stand for the app's id and its name,
    in its description and in its prompt. An operator works with the tools
    that drive an engine (`OPERATOR_TOOLS`, unless the template lists its
    own), then those the skill named after its app names for it
    (`Skill.operator_tools`), and reads that skill; an app without a skill
    has an operator that reads none. Where each is offered is `agents_for`'s
    to say, so the template's `disciplines` are not read. Without the
    template there are no operators.
    """
    template = directory / OPERATOR_TEMPLATE
    if not template.is_file():
        return []
    fields, prompt = front_matter(template.read_text())
    named = {skill.name: skill for skill in skills}
    made = []
    for app in catalog.data["apps"]:
        if app["status"] not in STARTABLE:
            continue
        skill = named.get(app["id"])
        described = {
            **{key: value for key, value in fields.items() if key != "disciplines"},
            "title": f"{app['name']} agent",
            "skills": app["id"] if skill else "",
            "description": filled(fields.get("description", ""), app),
        }
        operator = spec(app["id"], described, filled(prompt, app), OPERATOR_TOOLS)
        extra = skill.operator_tools if skill else ()
        made.append(
            replace(operator, tools=tuple(dict.fromkeys((*operator.tools, *extra))))
        )
    return made


def filled(text: str, app: dict[str, Any]) -> str:
    """An operator template's text for one app: `{app}` its id, `{name}` its name."""
    return text.replace("{app}", app["id"]).replace("{name}", app["name"])


def agents_for(
    agents: list[AgentSpec],
    derived: list[AgentSpec],
    offered: list[Skill],
    catalog: Catalog,
    discipline: str,
) -> list[AgentSpec]:
    """The subagents a project of a discipline is offered: the defined ones that fit it, then its engines' operators.

    A defined subagent fits where its `disciplines` name the discipline or
    every one. An operator fits where its app is one of the discipline's
    engines or its app's skill is among those offered, and a definition
    written for the same name takes its place. A subagent reads only the
    skills the project is offered.
    """
    names = {skill.name for skill in offered}
    engines = set(catalog.disciplines.get(discipline, {}).get("engines", []))
    chosen = [
        agent
        for agent in agents
        if not agent.disciplines.isdisjoint((discipline, EVERY_DISCIPLINE))
    ]
    taken = {agent.name for agent in chosen}
    chosen += [
        agent
        for agent in derived
        if (agent.name in names or agent.name in engines) and agent.name not in taken
    ]
    return [
        AgentSpec(
            **{
                **agent.__dict__,
                "skills": tuple(skill for skill in agent.skills if skill in names),
            }
        )
        for agent in chosen
    ]


def matching(patterns: tuple[str, ...], names: list[str]) -> list[str]:
    """The names a definition's tool list selects, in the names' own order: each entry a name or a pattern over them.

    Raises:
        ValueError: An entry selects nothing, which is a tool that does not exist.
    """
    for pattern in patterns:
        if not any(fnmatchcase(name, pattern) for name in names):
            raise ValueError(f"no tool is named {pattern}")
    return [
        name
        for name in names
        if any(fnmatchcase(name, pattern) for pattern in patterns)
    ]
