# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""A project's agent: one turn of Claude working with tools, run as a job the message route spawns.

A turn is a loop over the Messages API. Each request carries the project's
whole conversation (`agent_messages`), the model answers with text and tool
calls, the tools run, their results go back, and the loop ends when the model
answers without a call, asks the person something (`ask_user`), is stopped, or
reaches `MAX_STEPS`. As it goes it appends events to the project's log in the
order things happen (`text`, `tool_start`, `tool_end`, `ask`, `plan`,
`library`, `engine`, `error`), and the database ends the turn with `turn_end`
(`lathe_end_turn`), so the page that polls the log sees the whole turn.

The conversation is append-only, because the model's reasoning depends on it.
The model thinks before it answers, and each thinking block is bound to the
conversation that produced it: the top-level system prompt, the tools, and
every message before it. A request that changed any of these would lose that
reasoning, so:

- The system prompt is the same for every turn of a project. It holds what
  cannot change (the discipline and format, the engines, how to work, and the
  skills of `lathe/skills` that fit the discipline), and the tools are a fixed
  list. What changes between turns (the name, the plan, the library, the
  engines, GitHub) is a `system` message appended at the start of each turn,
  after the person's message.
- A message is never rewritten once the model has answered past it. What a
  turn leaves unanswered is completed by the next: a call the turn ended
  before running is answered as not run, and `ask_user`'s call is answered
  with the person's reply, which is how a question becomes the next turn's
  start. A project-state message no answer followed is the one thing dropped.
- Where a deploy changes the system prompt (a skill edited), the request asks
  the API to drop the thinking blocks that no longer match rather than refuse
  them (`prefix_mismatch_behavior: drop_block`).

The model is `LATHE_AGENT_MODEL`, Claude Fable 5.2 by default, the most capable
model, which always thinks; effort is `high`. Its requests are streamed (a turn
can think for minutes) with each tool's input streamed as it is written
(`eager_input_streaming`), so every input is checked against its tool's schema
before the tool runs. A request the model's safety classifiers decline is
retried on the API's own fallback model (`fallbacks: "default"`), and the
progress notes the model writes between tool calls come back as short
`thinking` blocks (`display: "updates"`), shown as `text` events. The system
prompt and the conversation are cached (`cache_control`), so a turn's later
requests pay for the new messages only.

The turn's worker beats every `HEARTBEAT_SECONDS` on a thread of its own
(`lathe_turn_alive`), which both shows the turn is alive, so a turn whose
worker died does not hold the project, and tells it when the person asked it
to stop; the loop, a running generation, and an engine's start each look at
that answer between steps.

Every tool acts as the project's user, through `Sessions`, so the agent of one
user's project reaches nothing of another's.

A project's repository may be a whole team's, shared by everyone who works on
the game, so the agent reads it freely and writes only to a branch of its own
(`tool_github_save`): `lathe/`, the project's name as a slug, and the first
eight characters of the project's id, made from the default branch's head the
first time a file is saved. The id is what makes the branch this project's:
teammates who each link a project named after the game to the same repository
get a branch each, and a branch someone else made never ends in this
project's id, so the agent never writes to one. It is also how the branch is
found again (`own_branch`), since the project keeps no record of it: by the
id it ends in, whatever the project is called now. Nothing the agent does
writes to the default branch, and the person brings its work in with a pull
request from the compare link the save gives back.
"""

from __future__ import annotations

import base64
import json
import re
import shlex
import threading
import time
import traceback
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol
from urllib.parse import quote

import anthropic

from generation import (
    VIDEO_LONGEST,
    video_kilotokens,
    IMAGE_ASPECT_RATIOS,
    IMAGE_MODELS,
    IMAGE_REFERENCES,
    VIDEO_ASPECT_RATIOS,
    VIDEO_MODELS,
    VIDEO_REFERENCES,
    VIDEO_RESOLUTIONS,
    Fal,
    GenerationStopped,
    Generator,
    image_arguments,
    video_arguments,
)
from github_client import GitHubError
from service import (
    LIBRARY_BUCKET,
    OPEN,
    PLAN_STATUSES,
    SIGNED_URL_SECONDS,
    STARTABLE,
    Catalog,
    Refused,
    Sessions,
    User,
    clean_sections,
    normal_tag,
    safe_name,
)
import unreal

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = "claude-fable-5-2"
EFFORT = "high"
MAX_TOKENS = 64000
BETAS = [
    # Retry a request the model's safety classifiers decline on the API's own fallback model
    "server-side-fallback-2026-07-01",
    # Let a request drop thinking blocks a changed system prompt invalidated rather than fail
    "thinking-binding-controls-2026-08-01",
    # Return the model's notes between tool calls, which `display: "updates"` asks for
    "thinking-display-updates-2026-08-18",
]
MAX_STEPS = 60
HEARTBEAT_SECONDS = 20
ENGINE_START_SECONDS = 300
ENGINE_POLL_SECONDS = 3
EXEC_SECONDS = 300
OUTPUT_LIMIT = 20000
READ_LIMIT = 100000
IMAGE_SECONDS = 300
VIDEO_SECONDS = 1200
# Where an engine mounts the user's workspace, unless its environment says otherwise
WORKSPACE = "/home/ubuntu/workspace"
# The agent's branches in a repository: this, the project's name as a slug, and the start of its id
BRANCH_PREFIX = "lathe/"
# Paths unreal_assets gives of one kind asked for, and of each kind when none is
ASSET_PATHS_ONE_KIND = 250
ASSET_PATHS_EACH = 15


class TurnStopped(Exception):
    """The person stopped the turn, or it is no longer the project's."""


class ModelError(Exception):
    """The model could not be asked, with what to tell the person."""


@dataclass
class Reply:
    """One answer of the model: its content blocks, as the API sent them, and why it stopped."""

    content: list[dict[str, Any]]
    stop_reason: str | None


class Model(Protocol):
    """The Messages API as the loop uses it, which a test stands in for with a scripted model."""

    def respond(
        self,
        system: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        on_block: Callable[[dict[str, Any]], None],
        alive: Callable[[], bool],
    ) -> Reply:
        """Ask the model to continue the conversation, handing each finished content block to `on_block`.

        Raises:
            TurnStopped: `alive` said to stop while the answer streamed.
            ModelError: the API could not be reached or refused the request.
        """


def as_dict(block: Any) -> dict[str, Any]:
    """A content block as the API sent it, ready to store and send back unchanged."""
    return block.to_dict(mode="json", exclude_none=True)


class Claude:
    """The Messages API through the Anthropic SDK, streamed."""

    def __init__(self, key: str, model: str) -> None:
        self.client = anthropic.Anthropic(api_key=key, max_retries=4)
        self.model = model

    def respond(
        self,
        system: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        on_block: Callable[[dict[str, Any]], None],
        alive: Callable[[], bool],
    ) -> Reply:
        """Stream one answer, handing over each content block as it completes.

        A tool input the SDK cannot parse at all ends the stream with a
        `ValueError` before its block completes, so there is no call to
        answer; the request is made again, twice at most.
        """
        for attempt in range(3):
            try:
                with self.client.beta.messages.stream(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    messages=messages,
                    tools=tools,
                    thinking={
                        "type": "adaptive",
                        "display": "updates",
                        "block_binding": {"prefix_mismatch_behavior": "drop_block"},
                    },
                    output_config={"effort": EFFORT},
                    cache_control={"type": "ephemeral"},
                    fallbacks="default",
                    betas=BETAS,
                ) as stream:
                    for event in stream:
                        if event.type == "content_block_stop":
                            on_block(as_dict(event.content_block))
                        if not alive():
                            raise TurnStopped()
                    message = stream.get_final_message()
                return Reply(content=[as_dict(block) for block in message.content], stop_reason=message.stop_reason)
            except ValueError as error:
                if attempt == 2:
                    raise ModelError("The model's tool call could not be read. Send a message to try again.") from error
            except anthropic.RateLimitError as error:
                raise ModelError("The model is busy right now. Try again in a minute.") from error
            except anthropic.APIStatusError as error:
                raise ModelError(f"The model refused the request ({error.status_code}): {error.message}") from error
            except anthropic.APIConnectionError as error:
                raise ModelError("The model could not be reached. Try again.") from error
        raise ModelError("The model could not be asked.")


# Skills


@dataclass(frozen=True)
class Skill:
    """A skill of `lathe/skills/<name>/SKILL.md`: its name, the disciplines it is for, and its text."""

    name: str
    description: str
    disciplines: frozenset[str]
    body: str


def skills_directory() -> Path:
    """Where the skills are: beside this module in the deployed image, `lathe/skills` in the repository."""
    for candidate in (HERE / "skills", HERE.parent / "skills"):
        if candidate.is_dir():
            return candidate
    return HERE / "skills"


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


def read_skills(directory: Path) -> list[Skill]:
    """Every skill under a directory, in name order, each with the reference files it links to.

    A skill says which disciplines it is for with a `disciplines` line in its
    front matter (`disciplines: media, animation`); one that does not is for
    the disciplines that use the engine it is named after, and one named after
    no engine is for every discipline (`skills_for`). The other Markdown files
    of a skill's directory (its `references/`) follow its text under their
    paths, which is where its links to them lead: the agent has no tool to
    open a file, so what a skill tells it to read has to be in the prompt.
    """
    skills = []
    for path in sorted(directory.glob("*/SKILL.md")):
        fields, body = front_matter(path.read_text())
        disciplines = frozenset(
            part.strip().lower() for part in fields.get("disciplines", "").strip("[]").split(",") if part.strip()
        )
        references = [
            f"## {reference.relative_to(path.parent).as_posix()}\n\n{reference.read_text().strip()}"
            for reference in sorted(path.parent.rglob("*.md"))
            if reference != path
        ]
        skills.append(
            Skill(path.parent.name, fields.get("description", ""), disciplines, "\n\n".join([body.strip(), *references]))
        )
    return skills


def skills_for(skills: list[Skill], catalog: Catalog, discipline: str) -> list[Skill]:
    """The skills that fit a discipline."""
    engines = set(catalog.disciplines.get(discipline, {}).get("engines", []))
    return [
        skill
        for skill in skills
        if discipline in skill.disciplines
        or (not skill.disciplines and (skill.name in engines or skill.name not in catalog.apps))
    ]


# Prompts


def system_prompt(catalog: Catalog, project: dict[str, Any], skills: list[Skill], tiers: frozenset[str]) -> str:
    """The project's system prompt, the same text for every turn of the project: nothing in it changes with the work.

    It is built from the project's discipline and format, the catalog, the
    machine tiers the deployment switched on, and the skills, so a deploy that
    changes one of those changes it, which the request's `drop_block` absorbs.
    """
    brand = catalog.data["brand"]
    discipline = catalog.disciplines.get(project["discipline"], {"name": project["discipline"], "blurb": "", "engines": []})
    engines = []
    for app_id in discipline.get("engines", []):
        app = catalog.apps.get(app_id)
        if app is None:
            continue
        status = {
            "available": "can be started",
            "team": "can be started by the team's accounts only, with the user's own license",
            "byol": "can be started once the person has linked their own license for it; starting it says how if not",
        }.get(app["status"], "not available yet")
        engines.append(f"- `{app['id']}`, {app['name']}: {app['tagline']} ({status})")
    other = [
        f"- `{app['id']}`, {app['name']}: {app['tagline']}"
        for app in catalog.data["apps"]
        if app["status"] in STARTABLE and app["id"] not in discipline.get("engines", [])
    ]
    machines = [
        f"- `{tier['id']}`, {tier['name']}: {tier['blurb']} {tier['credits_per_minute']} "
        f"credit{'s' if tier['credits_per_minute'] != 1 else ''} a minute."
        for tier in catalog.data["tiers"]
        if tier["id"] in tiers
    ]
    folder = f"{WORKSPACE}/projects/{project['id']}"
    sections = [
        f"""You are the agent of {brand} Studio. You work with one person on one creative project, and you make it with
them step by step: you plan, write, generate images and video, open creative engines on cloud machines and drive
them, and you ask the person at every decision that is theirs to make.

# The project

Discipline: {discipline['name']}. {discipline.get('blurb', '')}
Format: {project['format'] or 'not chosen yet'}.

The engines of this discipline:
{chr(10).join(engines) or '- none yet'}

Other engines that can be started:
{chr(10).join(other) or '- none'}

The machines an engine runs on (`tier`):
{chr(10).join(machines)}

# How you work

- The person decides what is theirs: the story, the look, which take to keep, what to spend. Ask with `ask_user`
  and two to five short options. Asking ends your turn, and their answer comes back as that call's result. Decide
  the craft questions yourself, as a professional would, and say what you chose.
- Keep the plan current with `update_plan`: a few concrete tasks, one of them active at a time.
- The library holds what the project is made of: characters, environments, props, products, shots, or whatever
  sections it needs (`set_library_sections`). Each entry has a tag such as `@mara`, and the person and the
  prompts name entries by their tags. Write an entry with `library_upsert` before you generate media for it.
- `generate_image` and `generate_video` take library tags as references, so the same character looks the same
  in every shot; mention each reference's tag in the prompt where it appears. Save what you generate to the entry
  it belongs to (`save_to`). The person sees each result in the conversation; ask before you build on one.
- An engine runs on a cloud machine and costs the person credits every minute it runs. Start one when the work
  needs it and stop it when that work is done; do not leave one running at the end of a turn unless the person is
  using it. The person watches a running engine in the Screen panel. Every engine of this project opens in the
  project's folder, `{folder}`, which they share; `engine_import` copies library entries into its `library`
  folder.
- `github_save` keeps the project's documents in the GitHub repository the person linked, on a branch of your own
  (`lathe/...`), never on its default branch or a branch someone else made; give the person the branch and the
  compare link it returns, where they open a pull request. `github_read` reads the default branch, or your branch
  with `ref: agent`.
- The project's state (its name, plan, library, engines, and GitHub link) arrives as a system message at the start
  of each turn. Trust it over what you remember of earlier turns.
- Before you start, say in a line what you are about to do; brief updates while you work help the person follow
  along. Close with a short recap that stands on its own: what you did, what you found, and what is next.

# Communicating clearly

Write for an intelligent reader who has not seen your tool calls or your reasoning. Put the key point first, use
plain words in full sentences, and do not use a term you made up during the work. Keep messages short: the person
is making something with you, not reading a report.""",
    ]
    for skill in skills:
        header = f"# Skill: {skill.name}\n\nThe skill's reference files, which it links to, follow its text under their paths."
        sections.append("\n\n".join(part for part in (header, skill.description, skill.body) if part))
    return "\n\n".join(sections)


# Tools: each one's definition for the model, a title for the page, and its implementation (`Agent.tool_<name>`)


def tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """A tool's definition for the Messages API, its input streamed as it is written."""
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": properties, "required": required},
        "eager_input_streaming": True,
    }


STRING = {"type": "string"}
STRINGS = {"type": "array", "items": {"type": "string"}}
ENGINE_ID = {"type": "string", "description": "The engine's id, from engine_list or engine_start."}
SAVE_TO = {
    "type": "object",
    "description": (
        "The library entry the results are added to, as its newest media: an existing entry by its tag, or a new "
        "one by section and name (and a tag). Without it the results are shown but not kept in the library."
    ),
    "properties": {"tag": STRING, "section": STRING, "name": STRING, "description": STRING},
}
TOOLS = [
    tool(
        "ask_user",
        "Ask the person a question whose answer is theirs to give, with options they can pick. This ends your turn: "
        "their answer, an option or their own words, comes back as this call's result when they reply.",
        {
            "question": {"type": "string", "description": "The question, in a sentence or two."},
            "options": {**STRINGS, "description": "Two to five short answers to pick from."},
        },
        ["question", "options"],
    ),
    tool(
        "update_plan",
        "Replace the project's plan, which the person sees in the Plan panel. Give every task, in order, each with "
        "its status; keep one task active while you work on it.",
        {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "A short stable id, kept when the task changes."},
                        "title": STRING,
                        "status": {"type": "string", "enum": list(PLAN_STATUSES)},
                    },
                    "required": ["title", "status"],
                },
            }
        },
        ["items"],
    ),
    tool(
        "set_library_sections",
        "Set the library's sections, in the order the person sees them, such as Characters, Environments, Props. A "
        "section that still has entries stays, after the ones given.",
        {"sections": STRINGS},
        ["sections"],
    ),
    tool(
        "library_list",
        "List the library's entries, or one section's: each entry's id, section, name, tag, description, metadata, "
        "and its media files.",
        {"section": STRING},
        [],
    ),
    tool(
        "library_upsert",
        "Add an entry to the library, or change the one with this tag (an untagged entry is found by section and "
        "name). Metadata is merged into what the entry has.",
        {
            "section": STRING,
            "name": STRING,
            "tag": {"type": "string", "description": "How prompts name it, like @mara: letters, digits, - and _."},
            "description": {"type": "string", "description": "What it is and how it looks, for prompts and people."},
            "metadata": {"type": "object", "description": "Anything else worth keeping, as JSON."},
        },
        ["section", "name"],
    ),
    tool(
        "generate_image",
        "Generate images on fal. With references, their tags' images guide the result (a character sheet, a "
        "location, a product): write each reference's tag in the prompt where it belongs, and it reaches the model "
        "as @Image1, @Image2, in the order of `references`. Returns the model used, the seed, and fal's cost estimate.",
        {
            "prompt": STRING,
            "references": {
                **STRINGS,
                "description": f"Library tags whose images to use, at most {IMAGE_REFERENCES['best']} "
                f"({IMAGE_REFERENCES['cheap']} with the cheap model).",
            },
            "aspect_ratio": {"type": "string", "enum": list(IMAGE_ASPECT_RATIOS)},
            "count": {"type": "integer", "minimum": 1, "maximum": 4, "description": "How many images, 1 to 4."},
            "model": {
                "type": "string",
                "enum": list(IMAGE_MODELS),
                "description": "best: Nano Banana Pro, the default. cheap: Seedream 5.5, for drafts and many variations.",
            },
            "save_to": SAVE_TO,
        },
        ["prompt"],
    ),
    tool(
        "generate_video",
        "Generate a video shot on fal with Seedance 2.5 reference-to-video. Each reference tag's image (or video or "
        "audio) is the reference for that character, place, or thing: write the tags in the prompt, and they reach "
        "the model as @Image1, @Video1, and so on, in the order of `references`. Returns the model used, the seed, "
        "and fal's cost estimate.",
        {
            "prompt": STRING,
            "references": {**STRINGS, "description": f"Library tags to use as references, at most {VIDEO_REFERENCES}."},
            "duration_seconds": {"type": "integer", "minimum": 4, "maximum": 30, "description": "Left out: chosen by the model."},
            "aspect_ratio": {"type": "string", "enum": list(VIDEO_ASPECT_RATIOS)},
            "resolution": {"type": "string", "enum": list(VIDEO_RESOLUTIONS["standard"])},
            "model": {
                "type": "string",
                "enum": list(VIDEO_MODELS),
                "description": "standard: Seedance 2.5, the default. fast: Seedance 2.5 Flash, quicker and cheaper, "
                "480p or 720p. draft: a 480p preview from Seedance 2.5.",
            },
            "save_to": SAVE_TO,
        },
        ["prompt"],
    ),
    tool(
        "engine_start",
        "Start an engine for this project on a cloud machine and wait until it runs. It costs the person credits "
        "every minute until it is stopped.",
        {
            "app": {"type": "string", "description": "The engine's id, such as filmcraft or blender."},
            "tier": {"type": "string", "description": "The machine tier's id, such as cpu."},
        },
        ["app", "tier"],
    ),
    tool("engine_list", "List this project's open engines.", {}, []),
    tool("engine_stop", "Stop one of this project's engines, which ends its cost.", {"engine_id": ENGINE_ID}, ["engine_id"]),
    tool(
        "engine_screenshot",
        "See what a running engine's screen shows now, as the person sees it.",
        {"engine_id": ENGINE_ID},
        ["engine_id"],
    ),
    tool(
        "engine_exec",
        "Run a shell command in a running engine, as its user, in its environment, and get its exit status and "
        f"output. It may run for {EXEC_SECONDS // 60} minutes.",
        {"engine_id": ENGINE_ID, "command": {"type": "string", "description": "A bash command."}},
        ["engine_id", "command"],
    ),
    tool(
        "engine_import",
        "Copy library entries' media into a running engine, under the project folder's library/<tag>/ folders.",
        {"engine_id": ENGINE_ID, "tags": STRINGS},
        ["engine_id", "tags"],
    ),
    tool(
        "filmcraft",
        "Call a method of FilmCraft's command channel in a running FilmCraft engine: the same commands its interface "
        "runs. Returns FilmCraft's answer.",
        {"engine_id": ENGINE_ID, "method": STRING, "params": {"type": "object"}},
        ["engine_id", "method"],
    ),
    tool(
        "github_save",
        "Save a text file to the project's GitHub repository in one commit, creating or replacing it, on the agent's "
        "own branch (lathe/<project>-<id>), which is made from the default branch the first time. It never writes to "
        "the default branch or to a branch the agent did not make. Returns the branch and a compare link, where the "
        "person opens a pull request.",
        {
            "path": {"type": "string", "description": "A path in the repository, like script/mara.fountain."},
            "content": STRING,
            "message": {"type": "string", "description": "The commit message."},
        },
        ["path", "content", "message"],
    ),
    tool(
        "github_read",
        "Read a text file of the project's GitHub repository, or list a folder ('' for the top).",
        {
            "path": STRING,
            "ref": {
                "type": "string",
                "enum": ["default", "agent"],
                "description": "default: the repository's default branch, what the team has (the default). "
                "agent: the agent's own branch, what it saved.",
            },
        },
        ["path"],
    ),
    tool(
        "unreal_assets",
        "List the assets of the Unreal project in the linked GitHub repository, from the repository alone, with no "
        "engine running: the .uproject's engine version (EngineAssociation) and plugins, every kind's count, and the "
        "paths, by kind. Kinds are read from each asset's name (Epic's naming conventions) and folder, not from the "
        "editor's Asset Registry. Also says whether the repository stores its binaries with Git LFS.",
        {
            "kind": {"type": "string", "enum": list(unreal.KINDS), "description": "Only assets of this kind."},
            "path": {
                "type": "string",
                "description": "Only assets inside this folder of the repository, like Content/Characters.",
            },
        },
        [],
    ),
]
TOOL_NAMES = [definition["name"] for definition in TOOLS]
SCHEMAS = {definition["name"]: definition["input_schema"] for definition in TOOLS}
JSON_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
}


def invalid(schema: dict[str, Any], value: Any, where: str = "input") -> str | None:
    """What is wrong with a value for a schema of the tools' own kinds, or nothing.

    A tool's input is streamed as the model writes it and parsed leniently, so
    a call cut short can arrive as a well-formed but incomplete object; this
    check is what keeps such a call from running.
    """
    expected = schema.get("type")
    if expected and (
        not isinstance(value, JSON_TYPES[expected]) or (expected in ("integer", "number") and isinstance(value, bool))
    ):
        return f"{where} should be {'an' if expected[0] in 'aeiou' else 'a'} {expected}"
    if "enum" in schema and value not in schema["enum"]:
        return f"{where} should be one of {', '.join(map(str, schema['enum']))}"
    if "minimum" in schema and value < schema["minimum"] or "maximum" in schema and value > schema["maximum"]:
        return f"{where} should be from {schema.get('minimum')} to {schema.get('maximum')}"
    if expected == "array":
        for index, item in enumerate(value):
            problem = invalid(schema.get("items", {}), item, f"{where}[{index}]")
            if problem:
                return problem
    if expected == "object":
        for name in schema.get("required", []):
            if name not in value:
                return f"{where} is missing {name}"
        for name, item in value.items():
            if name in schema.get("properties", {}):
                problem = invalid(schema["properties"][name], item, f"{where}.{name}")
                if problem:
                    return problem
    return None


def echoable(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """An answer's blocks as they go back to the API: after a fallback, what the declining model left is dropped.

    Where the model's classifiers declined partway through an answer and the
    fallback model went on, the blocks before the last `fallback` block that
    are not text (thinking, tool calls, anything unknown) are the declined
    model's and are not sent back, while the `fallback` blocks stay where
    they are, as the API checks the thinking around them by their place.
    """
    boundary = max((index for index, block in enumerate(content) if block.get("type") == "fallback"), default=-1)
    return [
        block
        for index, block in enumerate(content)
        if index >= boundary or block.get("type") in ("text", "fallback")
    ]


def replace_tags(prompt: str, labels: dict[str, str]) -> str:
    """A prompt with each tag written in it replaced by its label, longest tags first so `@mara-young` is not `@mara`."""
    for tag in sorted(labels, key=len, reverse=True):
        prompt = re.sub(re.escape(tag) + r"(?![A-Za-z0-9_-])", labels[tag], prompt, flags=re.IGNORECASE)
    return prompt


def repository_path(path: str) -> str:
    """A path in a repository, without leading or doubled slashes.

    Raises:
        Refused: 400 for a path that climbs out of the repository.
    """
    parts = [part for part in path.strip().split("/") if part]
    if any(part in (".", "..") for part in parts) or len("/".join(parts)) > 255:
        raise Refused(400, "That is not a path in the repository.")
    return "/".join(parts)


def agent_branch(project: dict[str, Any]) -> str:
    """The branch a project's agent makes in its repository: `lathe/<name as a slug>-<the id's first eight characters>`."""
    letters = unicodedata.normalize("NFKD", project["name"]).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", letters).strip("-")[:40].rstrip("-") or "project"
    return f"{BRANCH_PREFIX}{slug}-{project['id'][:8]}"


@dataclass
class Result:
    """What a tool gives back: the model's result, the page's summary, whether it worked, and media to show."""

    content: str | list[dict[str, Any]]
    summary: str
    ok: bool = True
    media: list[dict[str, Any]] = field(default_factory=list)


class Turn:
    """One turn of one project: who it acts for, its events, and its heartbeat."""

    def __init__(self, sessions: Sessions, project: dict[str, Any], turn_id: str, heartbeat_seconds: float) -> None:
        self.sessions = sessions
        self.project = project
        self.turn_id = turn_id
        profile = sessions.me(User(id=project["user_id"], email=""))
        self.user = User(id=project["user_id"], email=profile["email"])
        self.stopped = threading.Event()
        self.done = threading.Event()
        self.heartbeat_seconds = heartbeat_seconds
        self.heart = threading.Thread(target=self._beat_until_done, daemon=True)

    @property
    def project_id(self) -> str:
        return self.project["id"]

    def beat(self) -> bool:
        """Say the turn is alive and learn whether it should go on."""
        if not self.sessions.store.rpc("lathe_turn_alive", p_project=self.project_id, p_turn=self.turn_id):
            self.stopped.set()
        return not self.stopped.is_set()

    def alive(self) -> bool:
        """Whether the turn should go on, as its last heartbeat learned."""
        return not self.stopped.is_set()

    def _beat_until_done(self) -> None:
        while not self.done.wait(self.heartbeat_seconds):
            try:
                self.beat()
            except Exception:
                # A missed beat is retried at the next; only a long run of them lets the turn be taken over
                traceback.print_exc()

    def event(self, kind: str, data: dict[str, Any]) -> None:
        """Append an event of this turn to the project's log."""
        self.sessions.add_event(self.project_id, self.turn_id, kind, data)


class Agent:
    """The loop and its tools, over a `Sessions` for the projects' data and engines.

    Each tool is a method `tool_<name>` whose keyword arguments are its
    input's fields, checked against its schema before it is called (`call`);
    what it does is its definition's description in `TOOLS`, and it answers
    with a `Result` or raises `Refused` with what to tell the model.
    """

    def __init__(self, sessions: Sessions, model: Model, generator: Generator | None, skills: list[Skill]) -> None:
        self.sessions = sessions
        self.model = model
        self.generator = generator
        self.skills = skills
        self.heartbeat_seconds: float = HEARTBEAT_SECONDS

    @classmethod
    def for_deployment(cls, sessions: Sessions) -> Agent:
        """The agent as the deployment configures it: its model, fal where there is a key, and the skills."""
        config = sessions.config
        return cls(
            sessions,
            Claude(config.anthropic_key, config.agent_model or DEFAULT_MODEL),
            Fal(config.fal_key) if config.fal_key else None,
            read_skills(skills_directory()),
        )

    @property
    def store(self) -> Any:
        return self.sessions.store

    def run(self, project_id: str, turn_id: str) -> None:
        """Run one turn of a project, which the database ends with `turn_end` however the loop ends.

        A turn that is no longer the project's by the time its job runs (it
        was stopped, or the project deleted) is left alone.
        """
        rows = self.store.rows("projects", id=f"eq.{project_id}")
        if not rows or rows[0]["turn_id"] != turn_id:
            return
        turn = Turn(self.sessions, rows[0], turn_id, self.heartbeat_seconds)
        turn.heart.start()
        try:
            self.converse(turn)
        except Exception:
            # The person learns the turn failed; the operator gets the traceback in the function's log
            traceback.print_exc()
            turn.event("error", {"message": "Something went wrong on our side, and this turn stopped."})
        finally:
            turn.done.set()
            self.store.rpc("lathe_end_turn", p_project=project_id, p_turn=turn_id)

    # The loop

    def converse(self, turn: Turn) -> None:
        """Ask the model, run the tools it calls, and go on until it is done, asks, or is stopped."""
        opening = self.store.rows("project_events", turn_id=f"eq.{turn.turn_id}", kind="eq.user_message")
        if not opening:
            return
        history = self.open_turn(turn, opening[0]["data"]["text"])
        system = [
            {
                "type": "text",
                "text": system_prompt(
                    self.sessions.catalog,
                    turn.project,
                    skills_for(self.skills, self.sessions.catalog, turn.project["discipline"]),
                    self.sessions.config.tiers,
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ]
        for _ in range(MAX_STEPS):
            if not turn.beat():
                return
            try:
                reply = self.model.respond(system, history, TOOLS, lambda block: self.show(turn, block), turn.alive)
            except TurnStopped:
                return
            except ModelError as error:
                turn.event("error", {"message": str(error)})
                return
            if reply.stop_reason == "refusal":
                turn.event("error", {"message": "The model declined to go on with this. Try asking another way."})
                return
            content = echoable(reply.content)
            if not content:
                return
            self.append(turn, history, "assistant", content)
            if reply.stop_reason == "pause_turn":
                continue
            calls = [block for block in content if block.get("type") == "tool_use"]
            if not calls:
                return
            results, ended = self.run_tools(turn, calls, cut_off=reply.stop_reason == "max_tokens")
            if results:
                self.append(turn, history, "user", results)
            if ended:
                return
        turn.event("error", {"message": "This turn reached its limit of steps. Send a message to go on."})

    def show(self, turn: Turn, block: dict[str, Any]) -> None:
        """Put a finished block of the model's answer in the log: its text, and the notes it writes between tools."""
        words = block.get("text") if block.get("type") == "text" else block.get("thinking") if block.get("type") == "thinking" else None
        if words and words.strip():
            turn.event("text", {"text": words})

    def append(self, turn: Turn, history: list[dict[str, Any]], role: str, content: Any) -> None:
        """Add a message to the conversation, stored first."""
        self.store.insert(
            "agent_messages", {"project_id": turn.project_id, "turn_id": turn.turn_id, "role": role, "content": content}
        )
        history.append({"role": role, "content": content})

    def open_turn(self, turn: Turn, text: str) -> list[dict[str, Any]]:
        """The conversation with this turn's message added, and the project's state after it.

        A call of the last answer that has no result yet gets one here: the
        person's message where it was `ask_user`, "not run" otherwise. Where
        the last turn left some results of that answer (it asked while other
        calls ran), they are completed in the same message, which the model
        has not seen, so nothing it saw changes.
        """
        rows = self.store.every("agent_messages", project_id=f"eq.{turn.project_id}", order="id.asc")
        # Project states no answer followed: their turn ended before the model replied
        while rows and rows[-1]["role"] == "system":
            self.store.delete("agent_messages", id=f"eq.{rows[-1]['id']}")
            rows.pop()
        last = max((index for index, row in enumerate(rows) if row["role"] == "assistant"), default=None)
        calls = (
            [block for block in rows[last]["content"] if block.get("type") == "tool_use"]
            if last is not None and isinstance(rows[last]["content"], list)
            else []
        )
        after = rows[last + 1 :] if last is not None else []
        answered = {
            block.get("tool_use_id") for row in after if isinstance(row["content"], list) for block in row["content"]
        }
        missing = [call for call in calls if call["id"] not in answered]
        history = [{"role": row["role"], "content": row["content"]} for row in rows]
        if missing:
            results: list[dict[str, Any]] = []
            replied = False
            for call in missing:
                if call["name"] == "ask_user" and not replied:
                    results.append({"type": "tool_result", "tool_use_id": call["id"], "content": text})
                    replied = True
                else:
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": call["id"],
                            "content": "Not run: the turn ended before this call ran.",
                            "is_error": True,
                        }
                    )
            if not replied:
                results.append({"type": "text", "text": text})
            if len(after) == 1 and isinstance(after[0]["content"], list):
                content = [*after[0]["content"], *results]
                self.store.update("agent_messages", {"content": content}, id=f"eq.{after[0]['id']}")
                history[-1]["content"] = content
            else:
                self.append(turn, history, "user", results)
        else:
            self.append(turn, history, "user", text)
        self.append(turn, history, "system", self.state(turn))
        return history

    def state(self, turn: Turn) -> str:
        """The project as it is now, for the system message that starts a turn."""
        project = turn.project
        github = self.sessions.github_status(turn.user)
        if project["github_repo"]:
            linked = f"linked to {project['github_repo']}"
        elif github["connected"]:
            linked = "not linked to a repository yet; the person links one in the Environment panel"
        else:
            linked = "not connected; the person connects GitHub in the Environment panel"
        plan = [f"- [{item['status']}] {item['title']} (id {item['id']})" for item in project["plan"]]
        entries = []
        for row in self.sessions.project_assets(project):
            kinds = [item["kind"] for item in row["media"]]
            files = ", ".join(f"{kinds.count(kind)} {kind}" for kind in dict.fromkeys(kinds)) or "no media"
            entries.append(f"- {row['tag'] or '(untagged)'}: {row['name']} ({row['section']}; {files})")
        engines = [
            f"- {engine['id']}: {self.sessions.catalog.apps.get(engine['app'], {}).get('name', engine['app'])}, "
            f"{engine['status']}, tier {engine['tier']}"
            for engine in self.sessions.engines(turn.user, project["id"])
            if engine["status"] in OPEN
        ]
        credits = self.sessions.me(turn.user)["credits"]
        return "\n".join(
            [
                "The project's state at the start of this turn:",
                f"Name: {project['name']}",
                f"GitHub: {linked}",
                f"Generation: {'available' if self.generator else 'not configured on this deployment'}",
                f"Credits the person has: {credits}",
                "Plan:",
                *(plan or ["- (empty)"]),
                f"Library sections: {', '.join(project['library_sections']) or '(none)'}",
                "Library entries:",
                *(entries or ["- (none)"]),
                "Open engines:",
                *(engines or ["- (none)"]),
            ]
        )

    def run_tools(
        self, turn: Turn, calls: list[dict[str, Any]], cut_off: bool
    ) -> tuple[list[dict[str, Any]], bool]:
        """Run an answer's calls in order and return their results and whether the turn ends here.

        It ends at an `ask_user`, whose result is the person's reply, and when
        the turn is stopped; either way the calls not run are answered at the
        start of the next turn (`open_turn`).
        """
        results: list[dict[str, Any]] = []
        asked = False
        for call in calls:
            if not turn.alive():
                return results, True
            if cut_off:
                results.append(self.failure(call, "Your answer was cut off at the output limit before this call was "
                                                  "complete. Make it again with less in one call."))
            elif call["name"] == "ask_user" and not asked and not invalid(SCHEMAS["ask_user"], call.get("input")):
                turn.event("ask", {"question": call["input"]["question"], "options": call["input"]["options"]})
                asked = True
            elif call["name"] == "ask_user" and asked:
                results.append(self.failure(call, "Ask one question at a time; ask this one after the person answers."))
            else:
                results.append(self.call(turn, call))
        return results, asked

    @staticmethod
    def failure(call: dict[str, Any], message: str) -> dict[str, Any]:
        """A call's result that says it was not run, and why."""
        return {"type": "tool_result", "tool_use_id": call["id"], "content": message, "is_error": True}

    def call(self, turn: Turn, call: dict[str, Any]) -> dict[str, Any]:
        """Run one call with its `tool_start` and `tool_end` events, and return its result for the model."""
        if call["name"] not in SCHEMAS:
            return self.failure(call, f"There is no tool {call['name']}.")
        arguments = call.get("input")
        problem = invalid(SCHEMAS[call["name"]], arguments)
        if problem:
            return self.failure(
                call, json.dumps({"INVALID_INPUT": problem, "input": arguments}) + " Make the call again with valid input."
            )
        turn.event("tool_start", {"call_id": call["id"], "tool": call["name"], "title": self.title(call["name"], arguments)})
        try:
            result: Result = getattr(self, f"tool_{call['name']}")(turn, **arguments)
        except Refused as refused:
            result = Result(refused.message, refused.message, ok=False)
        except GitHubError as error:
            refused = self.sessions.github_refusal(error)
            result = Result(refused.message, refused.message, ok=False)
        except (GenerationStopped, TurnStopped):
            result = Result("Stopped by the person.", "Stopped", ok=False)
        except Exception as error:
            # A tool that fails tells the model why, and the operator gets the traceback
            traceback.print_exc()
            result = Result(f"{type(error).__name__}: {error}", (str(error) or type(error).__name__)[:200], ok=False)
        ended = {"call_id": call["id"], "ok": result.ok, "summary": result.summary}
        if result.media:
            ended["media"] = result.media
        turn.event("tool_end", ended)
        outcome = {"type": "tool_result", "tool_use_id": call["id"], "content": result.content}
        if not result.ok:
            outcome["is_error"] = True
        return outcome

    def title(self, name: str, arguments: dict[str, Any]) -> str:
        """A short line that says what a call does, for the page."""
        apps = self.sessions.catalog.apps
        app = apps.get(arguments.get("app", ""), {}).get("name", arguments.get("app", ""))
        count = arguments.get("count", 1)
        return {
            "update_plan": "Updating the plan",
            "set_library_sections": "Arranging the library",
            "library_list": "Reading the library",
            "library_upsert": f"Saving {arguments.get('tag') or arguments.get('name', '')} to the library",
            "generate_image": f"Generating {count} image{'s' if count != 1 else ''}",
            "generate_video": "Generating a video",
            "engine_start": f"Starting {app}",
            "engine_list": "Checking the engines",
            "engine_stop": "Stopping an engine",
            "engine_screenshot": "Looking at the screen",
            "engine_exec": "Running a command",
            "engine_import": f"Importing {', '.join(arguments.get('tags', []))}",
            "filmcraft": f"FilmCraft: {arguments.get('method', '')}",
            "github_save": f"Saving {arguments.get('path', '')} to the agent's branch on GitHub",
            "github_read": f"Reading {arguments.get('path', '') or 'the repository'} from "
            f"{'the agent' if arguments.get('ref') == 'agent' else 'the default'} branch on GitHub",
            "unreal_assets": f"Listing the Unreal project's {arguments.get('kind') or 'assets'}"
            + (f" in {arguments['path']}" if arguments.get("path") else ""),
        }.get(name, name)

    # Plan and library

    def tool_update_plan(self, turn: Turn, items: list[dict[str, Any]]) -> Result:
        plan = [
            {"id": str(item.get("id") or index + 1)[:40], "title": item["title"][:200], "status": item["status"]}
            for index, item in enumerate(items[:50])
        ]
        self.store.update("projects", {"plan": plan}, id=f"eq.{turn.project_id}")
        turn.project["plan"] = plan
        turn.event("plan", {"items": plan})
        done = sum(item["status"] == "done" for item in plan)
        return Result("The plan is updated.", f"{len(plan)} tasks, {done} done")

    def tool_set_library_sections(self, turn: Turn, sections: list[str]) -> Result:
        kept = [row["section"] for row in self.sessions.project_assets(turn.project)]
        chosen = clean_sections([*sections, *kept])
        self.store.update("projects", {"library_sections": chosen}, id=f"eq.{turn.project_id}")
        turn.project["library_sections"] = chosen
        turn.event("library", {"sections": chosen})
        return Result(f"The library's sections are now: {', '.join(chosen)}.", ", ".join(chosen) or "No sections")

    def tool_library_list(self, turn: Turn, section: str | None = None) -> Result:
        rows = [
            row
            for row in self.sessions.project_assets(turn.project)
            if section is None or row["section"].lower() == section.lower()
        ]
        entries = [
            {
                **{key: row[key] for key in ("id", "section", "name", "tag", "description", "metadata")},
                "media": [{"kind": item["kind"], "name": item["name"]} for item in row["media"]],
            }
            for row in rows
        ]
        listing = {"sections": turn.project["library_sections"], "entries": entries}
        return Result(json.dumps(listing), f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")

    def tool_library_upsert(
        self,
        turn: Turn,
        section: str,
        name: str,
        tag: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Result:
        row, created = self.sessions.upsert_asset(turn.project, section, name, tag, description, metadata)
        turn.event("library", {"asset": self.sessions.shown_assets([row])[0]})
        label = row["tag"] or row["name"]
        return Result(
            json.dumps({"id": row["id"], "tag": row["tag"], "section": row["section"], "name": row["name"], "created": created}),
            f"{'Added' if created else 'Updated'} {label} in {row['section']}",
        )

    # Generation

    def require_generator(self) -> Generator:
        if self.generator is None:
            raise Refused(503, "Image and video generation is not configured on this deployment.")
        return self.generator

    def save_target(self, turn: Turn, save_to: dict[str, Any] | None) -> dict[str, Any] | None:
        """The library entry results go to: by its tag, or made from a section and name; nothing for nothing.

        It is found before anything is generated, so a wrong `save_to` costs no generation.
        """
        if not save_to:
            return None
        tag = save_to.get("tag")
        if tag:
            tagged = [row for row in self.sessions.project_assets(turn.project) if row["tag"] == normal_tag(tag)]
            if tagged:
                return tagged[0]
        if save_to.get("section") and save_to.get("name"):
            row, _ = self.sessions.upsert_asset(
                turn.project, save_to["section"], save_to["name"], tag, save_to.get("description"), None
            )
            return row
        if tag:
            raise Refused(404, f"No library entry is tagged {tag}; give a section and a name to make it.")
        raise Refused(400, "save_to names an entry by its tag, or gives a section and a name for a new one.")

    def references(self, turn: Turn, tags: list[str], kinds: tuple[str, ...]) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
        """Each tag's entry, the media of it that serves as its reference (the first of `kinds` it has), and a signed link to it.

        Raises:
            Refused: 404 for a tag no entry has, 409 for an entry with no media of those kinds.
        """
        rows = self.sessions.assets_by_tags(turn.project, tags)
        chosen = []
        for row in rows:
            item = next(
                (item for kind in kinds for item in row["media"] if item["kind"] == kind),
                None,
            )
            if item is None:
                raise Refused(409, f"{row['tag']} has no {' or '.join(kinds)} to use as a reference yet.")
            chosen.append((row, item))
        links = self.store.sign(LIBRARY_BUCKET, [item["path"] for _, item in chosen], SIGNED_URL_SECONDS) if chosen else {}
        return [(row, item, links[item["path"]]) for row, item in chosen]

    def keep(
        self, turn: Turn, urls: list[str], target: dict[str, Any] | None, stem: str
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Store generated files in the library bucket: in the target entry where there is one, else beside the project.

        Returns the entry as changed and the files as the page shows them.
        """
        generator = self.require_generator()
        project = turn.project
        paths = []
        for url in urls:
            data, content_type = generator.download(url)
            extension = PurePosixPath(url.split("?")[0]).suffix[:6] or ".bin"
            name = f"{stem}-{uuid.uuid4().hex[:6]}{extension}"
            if target is not None:
                target = self.sessions.store_media(project, target, data, content_type, name)
                paths.append((target["media"][0]["path"], target["media"][0]["kind"]))
            else:
                path = f"{project['user_id']}/{project['id']}/generations/{uuid.uuid4().hex[:12]}-{name}"
                self.store.upload(LIBRARY_BUCKET, path, data, content_type)
                paths.append((path, content_type.split("/")[0]))
        links = self.store.sign(LIBRARY_BUCKET, [path for path, _ in paths], SIGNED_URL_SECONDS)
        if target is not None:
            turn.event("library", {"asset": self.sessions.shown_assets([target])[0]})
        return target, [{"kind": kind, "url": links.get(path)} for path, kind in paths]

    @staticmethod
    def labeled(prompt: str, chosen: list[tuple[dict[str, Any], dict[str, Any], str]]) -> tuple[str, dict[str, list[str]]]:
        """A prompt with each reference's tag written as its place among its kind (`@Image1`), and the URLs in that order.

        The models name references only by position; the entry's name is
        added after the prompt so the model also knows what each one is.
        """
        urls: dict[str, list[str]] = {"image": [], "video": [], "audio": []}
        labels = {}
        for row, item, url in chosen:
            urls[item["kind"]].append(url)
            labels[row["tag"]] = f"@{item['kind'].capitalize()}{len(urls[item['kind']])}"
        text = replace_tags(prompt, labels)
        if chosen:
            text += "\n\n" + " ".join(f"{labels[row['tag']]} is {row['name']}." for row, _, _ in chosen)
        return text, urls

    @staticmethod
    def generated(
        noun: str,
        endpoint: str,
        media: list[dict[str, Any]],
        target: dict[str, Any] | None,
        seed: Any,
        cost: float | None,
    ) -> Result:
        """What a generation tool gives back: where the results went, for the model, and a line for the page."""
        made = f"{len(media)} {noun}{'s' if len(media) != 1 else ''}"
        if target is None:
            kept = "Not saved to the library; generate again with save_to to keep a result."
        else:
            kept = f"Saved to {target['tag'] or target['name']} ({target['section']}) as its newest media."
        facts = {"model": endpoint, "saved_to": target and (target["tag"] or target["name"]), "seed": seed, "cost_usd": cost}
        summary = made + (f" saved to {target['tag'] or target['name']}" if target else "")
        return Result(
            f"Generated {made}. {kept} The person sees the results in the conversation.\n{json.dumps(facts)}",
            summary + (f", about ${cost:.2f}" if cost is not None else ""),
            media=media,
        )

    def tool_generate_image(
        self,
        turn: Turn,
        prompt: str,
        references: list[str] | None = None,
        aspect_ratio: str = "auto",
        count: int = 1,
        model: str = "best",
        save_to: dict[str, Any] | None = None,
    ) -> Result:
        generator = self.require_generator()
        if len(references or []) > IMAGE_REFERENCES[model]:
            raise Refused(400, f"That model takes at most {IMAGE_REFERENCES[model]} references.")
        chosen = self.references(turn, references or [], ("image",))
        target = self.save_target(turn, save_to)
        text, urls = self.labeled(prompt, chosen)
        endpoint, arguments = image_arguments(model, text, urls["image"], aspect_ratio, count)
        output = generator.run(endpoint, arguments, turn.alive, IMAGE_SECONDS)
        stem = ((target or {}).get("tag") or "image").lstrip("@")
        target, media = self.keep(turn, [image["url"] for image in output["images"]], target, stem)
        cost = generator.cost(endpoint, {"image": len(media), "unit": len(media)})
        return self.generated("image", endpoint, media, target, output.get("seed"), cost)

    def tool_generate_video(
        self,
        turn: Turn,
        prompt: str,
        references: list[str] | None = None,
        duration_seconds: int | None = None,
        aspect_ratio: str = "auto",
        resolution: str = "720p",
        model: str = "standard",
        save_to: dict[str, Any] | None = None,
    ) -> Result:
        generator = self.require_generator()
        if len(references or []) > VIDEO_REFERENCES:
            raise Refused(400, f"A video takes at most {VIDEO_REFERENCES} references.")
        if model == "draft":
            resolution = "480p"
        if duration_seconds and duration_seconds > VIDEO_LONGEST[model]:
            raise Refused(400, f"The {model} model makes clips of at most {VIDEO_LONGEST[model]} seconds; use fast for longer.")
        if resolution not in VIDEO_RESOLUTIONS[model]:
            raise Refused(400, f"The {model} model makes {' or '.join(VIDEO_RESOLUTIONS[model])}; use standard for {resolution}.")
        chosen = self.references(turn, references or [], ("image", "video", "audio"))
        target = self.save_target(turn, save_to)
        text, urls = self.labeled(prompt, chosen)
        endpoint, arguments = video_arguments(model, text, urls, duration_seconds, aspect_ratio, resolution)
        output = generator.run(endpoint, arguments, turn.alive, VIDEO_SECONDS)
        stem = ((target or {}).get("tag") or "video").lstrip("@")
        target, media = self.keep(turn, [output["video"]["url"]], target, stem)
        units = {"video": 1.0}
        if duration_seconds:
            units["second"] = float(duration_seconds)
            units["1000 token"] = video_kilotokens(resolution, aspect_ratio, duration_seconds)
        return self.generated("video", endpoint, media, target, output.get("seed"), generator.cost(endpoint, units))

    # Engines

    def app_name(self, app: str) -> str:
        return self.sessions.catalog.apps.get(app, {}).get("name", app)

    def engine_sandbox(self, turn: Turn, engine_id: str) -> tuple[dict[str, Any], str]:
        """One of the project's engines and its Sandbox.

        Raises:
            Refused: 404 for an engine that is not this project's, 409 for one that is not running.
        """
        row = self.sessions.project_engine(turn.user, turn.project_id, engine_id)
        if row["status"] != "running":
            raise Refused(409, f"That engine is {row['status']}, not running.")
        return row, row["sandbox_id"]

    def tool_engine_start(self, turn: Turn, app: str, tier: str) -> Result:
        engine = self.sessions.start_engine(turn.user, turn.project_id, app, tier, "auto")
        turn.event("engine", {"engine": engine})
        deadline = time.monotonic() + ENGINE_START_SECONDS
        while engine["status"] == "starting":
            engine = self.sessions.public(self.sessions.owned(turn.user, engine["id"]))
            if engine["status"] != "starting":
                turn.event("engine", {"engine": engine})
            elif time.monotonic() > deadline:
                break
            elif not turn.alive():
                raise TurnStopped()
            else:
                time.sleep(ENGINE_POLL_SECONDS)
        name = self.app_name(app)
        notes = {
            "running": "It runs, and the person can watch it in the Screen panel.",
            "queued": "Every machine is in use, so it waits in a queue; check engine_list in a while.",
            "starting": "It is still starting; check engine_list in a while.",
        }
        reason = engine.get("end_reason") or ""
        return Result(
            json.dumps({**engine, "note": notes.get(engine["status"], f"It did not start: {reason}")}),
            f"{name} is {engine['status']}" + (f": {reason}" if engine["status"] == "failed" else ""),
            ok=engine["status"] in ("running", "queued", "starting"),
        )

    def tool_engine_list(self, turn: Turn) -> Result:
        engines = [
            {key: engine[key] for key in ("id", "app", "tier", "status", "started_at", "queue_position")}
            for engine in self.sessions.engines(turn.user, turn.project_id)
            if engine["status"] in OPEN
        ]
        running = sum(engine["status"] == "running" for engine in engines)
        return Result(json.dumps(engines), f"{running} running" if engines else "No engines open")

    def tool_engine_stop(self, turn: Turn, engine_id: str) -> Result:
        self.sessions.project_engine(turn.user, turn.project_id, engine_id)
        self.sessions.stop(turn.user, engine_id)
        # As the stop left it: ended where it had no machine yet, still running while its stop job runs
        engine = self.sessions.public(self.sessions.owned(turn.user, engine_id))
        turn.event("engine", {"engine": engine})
        return Result(json.dumps(engine), f"Stopped {self.app_name(engine['app'])}")

    def tool_engine_screenshot(self, turn: Turn, engine_id: str) -> Result:
        row, sandbox = self.engine_sandbox(turn, engine_id)
        picture = self.sessions.launcher.screenshot(sandbox)
        path = f"{turn.project['user_id']}/{turn.project_id}/screens/{uuid.uuid4().hex[:12]}.jpg"
        self.store.upload(LIBRARY_BUCKET, path, picture, "image/jpeg")
        link = self.store.sign(LIBRARY_BUCKET, [path], SIGNED_URL_SECONDS).get(path)
        return Result(
            [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(picture).decode()}},
                {"type": "text", "text": f"{self.app_name(row['app'])}'s screen now."},
            ],
            "Screenshot",
            media=[{"kind": "image", "url": link}],
        )

    def tool_engine_exec(self, turn: Turn, engine_id: str, command: str) -> Result:
        _, sandbox = self.engine_sandbox(turn, engine_id)
        status, output = self.sessions.launcher.exec(sandbox, command, EXEC_SECONDS)
        shown = output if len(output) <= OUTPUT_LIMIT else f"[the first {len(output) - OUTPUT_LIMIT} characters left out]\n{output[-OUTPUT_LIMIT:]}"
        return Result(f"exit status {status}\n{shown}", f"Exit status {status}", ok=status == 0)

    def tool_engine_import(self, turn: Turn, engine_id: str, tags: list[str]) -> Result:
        _, sandbox = self.engine_sandbox(turn, engine_id)
        rows = self.sessions.assets_by_tags(turn.project, tags)
        links = self.sessions.links(rows)
        folder = f"{WORKSPACE}/projects/{turn.project_id}/library"
        lines = ["set -e"]
        files = []
        for row in rows:
            for index, item in enumerate(row["media"]):
                # Numbered from the oldest, so a file keeps its name when newer media are added
                target = f"{folder}/{row['tag'].lstrip('@')}/{len(row['media']) - index:02d}-{safe_name(item['name'])}"
                lines.append(f"mkdir -p {shlex.quote(str(PurePosixPath(target).parent))}")
                lines.append(f"curl -fsSL --max-time 600 -o {shlex.quote(target)} {shlex.quote(links[item['path']])}")
                files.append(target)
        if not files:
            return Result("Those entries have no media to import.", "Nothing to import")
        status, output = self.sessions.launcher.exec(sandbox, "\n".join(lines), EXEC_SECONDS)
        if status != 0:
            raise RuntimeError(f"the copy stopped with status {status}: {output[-500:]}")
        return Result(
            json.dumps({"folder": folder, "files": files}),
            f"{len(files)} file{'s' if len(files) != 1 else ''} in the project's library folder",
        )

    def tool_filmcraft(self, turn: Turn, engine_id: str, method: str, params: dict[str, Any] | None = None) -> Result:
        row, sandbox = self.engine_sandbox(turn, engine_id)
        if row["app"] != "filmcraft":
            raise Refused(409, "That engine is not FilmCraft.")
        answer = self.sessions.launcher.filmcraft(sandbox, method, params)
        text = json.dumps(answer)
        return Result(text if len(text) <= OUTPUT_LIMIT else text[:OUTPUT_LIMIT] + " [cut]", f"{method} done")

    # GitHub

    def repository(self, turn: Turn) -> tuple[str, str]:
        """The project's repository and the token that reaches it.

        Raises:
            Refused: 409 where the person has not connected GitHub or linked the project.
        """
        token = self.sessions.require_github(turn.user.id)
        repo = turn.project["github_repo"]
        if not repo:
            raise Refused(409, "This project is not linked to a GitHub repository; the person links one in the Environment panel.")
        return token, repo

    def own_branch(self, turn: Turn, token: str, repo: str) -> str | None:
        """The agent's branch in the project's repository, if it made one: the one that ends in the project's id."""
        suffix = f"-{turn.project_id[:8]}"
        branches = self.sessions.github.branches_under(token, repo, BRANCH_PREFIX)
        return next((branch for branch in branches if branch.endswith(suffix)), None)

    def tool_github_save(self, turn: Turn, path: str, content: str, message: str) -> Result:
        token, repo = self.repository(turn)
        where = repository_path(path)
        if not where:
            raise Refused(400, "Name the file to save.")
        github = self.sessions.github
        found = github.repo(token, repo)
        if not found.get("permissions", {}).get("push"):
            raise Refused(
                403,
                f"This GitHub account cannot push to {repo}, so the agent cannot keep a branch of its own there and "
                "saved nothing. Reading the repository still works; to save, the repository's owner gives this "
                "account write access.",
            )
        base = found["default_branch"]
        branch = self.own_branch(turn, token, repo)
        made = branch is None
        if branch is None:
            head = github.head(token, repo, base)
            if head is None:
                raise Refused(409, f"{repo} has no commit on {base} to branch from yet.")
            branch = agent_branch(turn.project)
            github.create_branch(token, repo, branch, head)
        commit = github.save(token, repo, where, content, message.strip() or f"Update {where}", branch)
        compare = f"{found['html_url']}/compare/{quote(base)}...{quote(branch)}?expand=1"
        return Result(
            json.dumps(
                {
                    "repo": repo,
                    "branch": branch,
                    "branch_made_now": made,
                    "default_branch": base,
                    "path": where,
                    "commit": commit.get("html_url"),
                    "compare": compare,
                    "note": f"Saved on {branch}, not on {base}, which is unchanged. Tell the person the branch and "
                    f"give them the compare link, where they open a pull request to bring it into {base}.",
                }
            ),
            f"Committed {where} to {branch}" + (", a new branch" if made else ""),
        )

    def tool_github_read(self, turn: Turn, path: str, ref: str = "default") -> Result:
        token, repo = self.repository(turn)
        where = repository_path(path)
        branch = None
        if ref == "agent":
            branch = self.own_branch(turn, token, repo)
            if branch is None:
                raise Refused(404, f"The agent has no branch in {repo} yet: nothing has been saved there.")
        found = self.sessions.github.read(token, repo, where, ref=branch)
        side = f" on {branch}" if branch else ""
        if "entries" in found:
            return Result(
                "\n".join(found["entries"]) or "(empty)", f"{len(found['entries'])} entries in {where or repo}{side}"
            )
        text = found["text"]
        return Result(text if len(text) <= READ_LIMIT else text[:READ_LIMIT] + "\n[cut]", f"{len(text)} characters{side}")

    # Unreal Engine

    def tool_unreal_assets(self, turn: Turn, kind: str | None = None, path: str | None = None) -> Result:
        token, repo = self.repository(turn)
        folder = repository_path(path or "")
        github = self.sessions.github
        base = github.repo(token, repo)["default_branch"]
        head = github.head(token, repo, base)
        if head is None:
            raise Refused(409, f"{repo} has no commit on {base} yet, so it holds no Unreal project.")
        entries, whole = github.files(token, repo, head)
        files = [entry["path"] for entry in entries if entry["type"] == "blob"]
        project, others = unreal.find_project(files, folder)
        if project is None:
            raise Refused(
                404,
                f"{repo} has no .uproject within {unreal.PROJECT_DEPTH} folders of its top"
                + (f" for {folder}" if folder else "")
                + ("" if whole else ", as far as GitHub could list it")
                + ", so it holds no Unreal project this tool can read.",
            )
        facts = unreal.read_project(github.read(token, repo, project, ref=head)["text"])
        home = unreal.parent(project)
        attributes = [name for name in dict.fromkeys([".gitattributes", f"{home}/.gitattributes".lstrip("/")]) if name in files]
        lfs = sorted(
            {pattern for name in attributes for pattern in unreal.lfs_patterns(github.read(token, repo, name, ref=head)["text"])}
        )
        found = unreal.survey(files, project, folder, kind, ASSET_PATHS_ONE_KIND if kind else ASSET_PATHS_EACH)
        notes = [
            "Kinds are read from names in the repository: each asset's prefix under Epic's recommended asset naming "
            f"conventions ({unreal.EPIC_NAMING}), the community style guides where Epic's page names none "
            f"({unreal.STYLE_GUIDE}, {unreal.LOOMAN_GUIDE}), and its folder's name as a second hint. A team's own "
            "names can differ; the exact class of each asset comes from the editor's Asset Registry once an Unreal "
            "engine runs on this project.",
            f"The repository stores {', '.join(lfs)} with Git LFS: Git holds a pointer for each, so every path is "
            "here, and their content comes with an LFS clone."
            if lfs
            else "No .gitattributes stores files with Git LFS: the binary assets are in Git itself.",
        ]
        if any(listed["more"] for listed in found["assets"].values()):
            notes.append("A kind's `more` counts its paths left out; ask for that kind, or a folder, to see them.")
        if found["world_partition_files"]:
            notes.append(
                f"{found['world_partition_files']} files are World Partition's one-file-per-actor data of the maps "
                "(__ExternalActors__, __ExternalObjects__), not counted as assets."
            )
        if not whole:
            notes.append("GitHub's listing of the repository was too large to finish, so these counts are of part of it.")
        answer = {
            "repo": repo,
            "branch": base,
            "project": {"file": project, **facts, "project_plugins": found["project_plugins"]},
            "other_projects": others,
            "content_roots": found["content_roots"],
            "git_lfs": lfs,
            "counts": {kind: found["counts"][kind]} if kind else found["counts"],
            "assets": found["assets"],
            "notes": notes,
        }
        if kind:
            summary = f"{found['counts'][kind]} {kind}"
        else:
            counts = ", ".join(f"{count} {name}" for name, count in found["counts"].items() if count)
            summary = f"{sum(found['counts'].values())} assets: {counts}"
        return Result(json.dumps(answer), (summary + ("" if whole else ", in part of the repository"))[:200])
