# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""A project's agent: its tools, what it is told, and one turn of it, run as a job the message route spawns.

The agent's loop is the Claude Agent SDK's (`loop.py`): it asks the model,
decides the next step, runs it, checks the result, and goes on, with
subagents, skills loaded when the work calls for them, and the conversation
summarized as it grows. Moody is everything around the loop and is here: the
tools (`TOOLS`, `Agent.tool_<name>`), the system prompt (`system_prompt`),
the project's state at the start of each turn (`Agent.state`), which skills
and subagents a project is offered (`definitions.py`), the person's approvals
(`Agent.approved`), and the turn itself (`Agent.run`, `Agent.converse`).

A turn appends events to the project's log in the order things happen
(`thinking`, `text`, `tool_start`, `tool_end`, `ask`, `plan`, `library`,
`engine`, `screen`, `preview`, `agent`, `approval`, `usage`, `error`), and the
database ends it with `turn_end` (`moody_end_turn`), so the page that polls
the log sees the whole turn. A `screen` event puts an engine, and which of its
pictures, on the person's Screen panel: the agent switches the view to what it
wants them to look at, as `unreal_open` switches to the Unreal view once the
editor opens. An event a subagent caused carries its `agent_id`
(`Turn.acting`).

A project's conversation is one session of the loop
(`projects.agent_session`), whose transcript the loop mirrors to the database
as it writes it (`transcript.py`), so the next turn resumes it on whichever
machine runs it. Nothing of the conversation is kept here. What a turn adds to
it is the person's message followed by the project's state (`Agent.prompt`):
its name, plan, library, engines, and GitHub link, which change between turns
and so are no part of the system prompt. Each open engine is listed with its
app and whether it has a command channel, under the project folder the
engines share, so the agent knows what it can drive and where files meet.
Where an Unreal engine runs, the state also lists the Unreal projects in that
engine's workspace and which of them no `unreal_projects` call of the session
has returned yet (`Agent.unreal_state`, which reads the session back for
that), and a clone of the linked repository the engine started with that is
still running or failed, so a project just cloned is brought up without being
asked; the machine is asked only when such an engine runs. A project whose
session is new but whose log is not (it began before its session, or the
session could not be resumed) starts with a recap of the log (`recap`).

A tool's definition is data (`tool`): beside its name, description, and input,
it says what the agent looks like while the tool runs (`activity`, one of the
catalog's `activities`, checked when an agent is made), whether it only reads,
so the loop may run several at once, whether the person approves it first
(`approval`), and whether only the agent itself may call it, not a subagent.
The loop checks every input against its tool's schema before the tool runs.
A tool's result may end the turn (`Result.ends_turn`): `ask_user` writes its
`ask` event and ends the turn, so no machine waits on the person, and their
answer is the next turn's message.

A tool the person approves first (starting an engine, generating video) is
not among the tools the loop may run unasked unless the project's permissions
say `always` for it. For any other call of it the loop asks, and
`Agent.approved` writes an `approval` event and waits for the person's answer
(`POST /v1/projects/{pid}/approvals/{aid}`), for `Config.approval_seconds` at
most, after which it records the approval as expired and tells the model to
end its turn and ask. The answer is recorded in the database once
(`moody_resolve_approval`), whoever is first.

The model is `MOODY_AGENT_MODEL`, Claude Fable 5.2 by default, with summarized
thinking, which the page shows; effort is configuration (`loop_settings`). A
subagent runs on the tier its definition names, which the deployment maps to
a model. What one turn may spend on the model and how many steps it may take
are its person's own settings (`Sessions.limits`), read as the turn begins;
a turn that reaches one ends with an `error` event that names the limit, so
the page can offer the setting where it tells the person.

The turn's worker beats every `HEARTBEAT_SECONDS` on a thread of its own
(`moody_turn_alive`), which both shows the turn is alive, so a turn whose
worker died does not hold the project, and tells it when the person asked it
to stop; the loop is interrupted then, and a running generation, an engine's
start, and an approval each look at that answer between their own steps.

Every tool acts as the project's user, through `Sessions`, so the agent of one
user's project reaches nothing of another's.

The agent drives every engine through the same tools. `engine_call` reaches
the command channel of whichever app the engine runs, found by the app's id
on the launcher (`Launcher.engine_call`), so a new app with a channel needs no
tool of its own; an engine without one is driven through `engine_exec` and its
screen. Work passes between engines as files in the project's folder, which
`engine_files` lists as an engine sees it. Each running engine sees that
folder as it was when it started, so what one writes reaches another that is
already running through `engine_send`, which carries the file or folder from
one machine into the other's folder; an engine started afterwards finds it
there by itself, since every machine's writes are committed to the Volume
within seconds.

The agent shows its work as it goes with `preview`: any files an engine wrote
in the project's folder, of whatever length or size the agent chose to render,
become a `preview` event, a work-in-progress card in the conversation. The
tool knows nothing of any one engine; it reads each file with ffprobe on the
engine's machine, and where a file is heavier than a conversation should carry
or in a format browsers do not play, has that machine's ffmpeg encode a
lighter copy outside the project's folder (`PREVIEW_ENCODINGS`), the original
staying where it is. What bounds it is the deployment's configuration alone
(`Config.preview_limit_bytes` and its neighbors), never a duration. The copy
is stored in the bucket under the project's `previews/` folder, apart from the
library's entries, and the event keeps its path, which each reading of the log
signs afresh (`Sessions.shown_events`). The model gets the file's facts as
text, not the pixels or the sound, which would cost tokens on every later
request of the conversation; `look` adds one small picture of each file when
it has to judge the result. `engine_screenshot` shows its picture as the same
card.

The same holds for what the agent generates and for the library: a
generation's result is its facts, and `look` on `generate_image` and
`generate_video`, or `library_look` for entries already in the library, hands
the model the same small picture of each file (`Agent.pictured`). No engine
holds those files, so the turn's own worker makes the pictures
(`looking.py`).

A project's repository may be a whole team's, shared by everyone who works on
the game, so the agent reads it freely and writes only to a branch of its own
(`tool_github_save`): `moody/`, the project's name as a slug, and the first
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
import mimetypes
import re
import shlex
import threading
import time
import traceback
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Callable, Iterator, get_args
from urllib.parse import quote

import anyio
import anyio.from_thread
from claude_agent_sdk import EffortLevel, get_session_messages_from_store, project_key_for_directory

from definitions import (
    AgentSpec,
    Skill,
    agents_directory,
    agents_for,
    matching,
    operators,
    read_agents,
    read_skills,
    skills_directory,
    skills_for,
)
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
import genui
from looking import LOOK_BYTES, NoPicture, look_arguments, picture_of
from loop import BUILT_INS, PREFIX, Brief, Loop, Settings, Subagent, ToolSpec, TurnLoop, Workspace, sdk_loop
from service import (
    DESKTOP,
    LIBRARY_BUCKET,
    MEGABYTE,
    OPEN,
    PLAN_STATUSES,
    PREVIEWS,
    SIGNED_URL_SECONDS,
    STARTABLE,
    STREAMS,
    UNREAL_VIEW,
    Catalog,
    Config,
    Refused,
    Sessions,
    User,
    clean_sections,
    normal_tag,
    safe_name,
)
from transcript import Transcript
import unreal

DEFAULT_MODEL = "claude-fable-5-2"
HEARTBEAT_SECONDS = 20
ENGINE_START_SECONDS = 300
ENGINE_POLL_SECONDS = 3
EXEC_SECONDS = 300
OUTPUT_LIMIT = 20000
READ_LIMIT = 100000
IMAGE_SECONDS = 300
VIDEO_SECONDS = 1200
# How often a call that waits for the person's approval looks for their answer
APPROVAL_POLL_SECONDS = 1.0
# What the answer to an approval may be, and what a wait that ran out is recorded as
APPROVAL_DECISIONS = ("once", "always", "deny")
APPROVAL_EXPIRED = "expired"
# The most of a project's earlier log a new session's recap carries, in events and in characters
RECAP_EVENTS = 60
RECAP_CHARACTERS = 12000
# Where an engine mounts the user's workspace, unless its environment says otherwise
WORKSPACE = "/home/ubuntu/workspace"
# The agent's branches in a repository: this, the project's name as a slug, and the start of its id
BRANCH_PREFIX = "moody/"
# Paths unreal_assets gives of one kind asked for, and of each kind when none is
ASSET_PATHS_ONE_KIND = 250
ASSET_PATHS_EACH = 15
# Entries engine_files gives of one folder
FILES_LIMIT = 500
# The exit status engine_files' listing ends with where the path is not there
NO_SUCH_PATH = 44
# One line per entry: its type, size in bytes, modification time in seconds, and name
FILES_FORMAT = r"%y\t%s\t%T@\t%f\n"
# The exit status a probe ends with for a path that is a folder, not a file
NOT_A_FILE = 45
# How long carrying a file between two engines may take
SEND_SECONDS = 1800
# Where an engine keeps the copies it encodes for a preview until they are read: outside the project's folder
PREVIEW_SCRATCH = "/tmp/moody-preview"
# The line a probe prints in place of ffprobe's answer where the engine has no ffmpeg
NO_FFMPEG = "NO-FFMPEG"
# What ffprobe is asked of a file: enough to say what it is, how long, and how large
PROBE_ENTRIES = "format=format_name,duration:stream=codec_type,codec_name,pix_fmt,width,height,sample_rate,channels"
PREVIEW_KINDS = ("image", "audio", "video", "file")
MEDIA_KINDS = PREVIEW_KINDS[:3]
# File name endings Python's table of types does not place, by the kind of media they hold
MEDIA_ENDINGS = {
    ".exr": "image", ".psd": "image", ".tga": "image", ".dpx": "image", ".hdr": "image", ".avif": "image",
    ".mxf": "video", ".mkv": "video", ".flac": "audio", ".opus": "audio", ".m4a": "audio",
}
# The file name endings a browser shows as they are, by kind; a video must also be of a codec and pixel format below
WEB_ENDINGS = {
    "image": (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif"),
    "audio": (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac"),
    "video": (".mp4", ".m4v", ".webm"),
}
WEB_VIDEO_CODECS = ("h264", "vp8", "vp9", "av1")
# 4:2:0 at 8 bits is what every browser's decoder takes; engines differ on the rest
WEB_PIXEL_FORMATS = ("yuv420p", "yuvj420p")
# The lighter copy an engine's ffmpeg encodes of each kind: its ending, its content type, what it is called, and
# ffmpeg's arguments between the input and the output. A comma inside a filter's expression is escaped for ffmpeg.
PREVIEW_ENCODINGS: dict[str, tuple[str, str, str, list[str]]] = {
    "image": (".webp", "image/webp", "a WebP", ["-frames:v", "1", "-vf", "scale=min(2048\\,iw):-2", "-c:v", "libwebp", "-q:v", "82"]),
    "audio": (".m4a", "audio/mp4", "an AAC", ["-vn", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]),
    "video": (
        ".mp4",
        "video/mp4",
        "an H.264",
        ["-vf", "scale=trunc(min(1280\\,iw)/2)*2:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt",
         "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"],
    ),
}
# The pictures one call of `library_look` hands the model at most
LOOK_PICTURES = 8
# The largest file of the library the turn's worker reads to make a picture of
LOOK_SOURCE_BYTES = 256 * MEGABYTE


class TurnStopped(Exception):
    """The person stopped the turn, or it is no longer the project's."""


# Prompts


def project_folder(project_id: str) -> str:
    """Where every engine of a project opens: the project's folder of the user's workspace, which they share."""
    return f"{WORKSPACE}/projects/{project_id}"


def system_prompt(catalog: Catalog, project: dict[str, Any], tiers: frozenset[str]) -> str:
    """The project's system prompt: what does not change with the work.

    It is built from the project's discipline and format, the catalog, and
    the machine tiers the deployment switched on. What changes between turns
    arrives with each message (`Agent.prompt`), and the skills and subagents
    the project is offered are listed by the loop, which loads a skill's text
    only when the agent opens it.
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
            "byol": "can be started by anyone; the part on the person's own license comes with it once they have "
            "linked that license, and using that part says how if not",
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
    folder = project_folder(project["id"])
    return f"""You are the {brand} agent, a person's creative assistant in {brand} Studio. You work with one person on one
creative project, and you make it with them step by step: you plan, write, generate images and video, open creative
engines on cloud machines and drive them, and you ask the person at every decision that is theirs to make.

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
  and two to five short options. Asking ends your turn: the question is shown to the person, and their answer, an
  option or their own words, is the next message you get. Decide the craft questions yourself, as a professional
  would, and say what you chose.
- Where a decision is the person's and you have a view, say which way you would go: in a question, name that
  option in `ask_user`'s `recommended`, and in a report, say it in a few words beside the decision. They work with
  you for your judgment, and with it in front of them they agree in a word or see what they are deciding
  against. Leave it out where you have no real preference. Keep interactive cards clean: a card shows the thing
  and its controls, and no recommendation is written on it.
- Keep the plan current with `update_plan`: a few concrete tasks, one of them active at a time.
- The library holds what the project is made of: characters, environments, props, products, shots, or whatever
  sections it needs (`set_library_sections`). Each entry has a tag such as `@mara`, and the person and the
  prompts name entries by their tags. Write an entry with `library_upsert` before you generate media for it.
- `generate_image` and `generate_video` take library tags as references, so the same character looks the same
  in every shot; mention each reference's tag in the prompt where it appears. Save what you generate to the entry
  it belongs to (`save_to`). The person sees each result in the conversation; ask before you build on one.
- You are told what a generation made, not shown it. Where you have to judge a result yourself (before you
  describe it, choose between candidates, build on it, or call it done), generate with `look: true`, or look at
  entries of the library with `library_look`. Do not look at what you only pass on to the person.
- An engine is a cloud machine that costs the person credits every minute it runs, so none starts unless the work
  needs it or the person asked. Planning, writing, the library, and generating images and video need no engine:
  do them first, with your own tools. Start an engine at the step that cannot be done without it (cutting the
  shots together, retouching, mixing), and stop it when that work is done; do not leave one running at the end of
  a turn unless the person is using it, and say so in a line if you do. The person watches a running engine in
  the Screen panel, and `engine_show` puts the engine and view you want them to look at there (an Unreal engine
  has two: Desktop and Unreal). Every engine of this project opens in the project's folder, `{folder}`, which they
  share; `engine_import` copies library entries into its `library` folder.
- The person approves some steps before they run: starting an engine and generating video. Call the tool when the
  work calls for it; the person is asked then, and you get the tool's result if they agree. If they decline, do
  not call it again: go on another way or ask what they want. If they do not answer in time, end your turn with
  a line that says what you were about to do and why.
- `engine_call` runs a command of an engine's own command channel, the same commands its interface runs, for every
  engine that has one; the project's state says which do. An engine without one you drive with `engine_exec`, or you
  ask the person to do the step on its screen. Work passes from one engine to another as files in the project's
  folder. An engine sees what was in the folder when it started and what it wrote itself, so a file another
  running engine wrote since is carried over with `engine_send`; `engine_files` lists the folder as an engine sees
  it, so confirm a file is there before that engine opens it.
- Show your work as you go with `preview`. After each step that changed something, and before you ask the person
  to decide, render or export what shows it with the engine's own commands (a frame, a few seconds, one section,
  or the whole piece: as much as shows the change and no more) into the project's folder, and preview it with a
  one-line caption. The person sees or hears it in the conversation; you get its facts, and `look: true` when you
  have to judge the result yourself. One preview per step: do not flood the conversation.
- `github_save` keeps the project's documents in the GitHub repository the person linked, on a branch of your own
  (`moody/...`), never on its default branch or a branch someone else made; give the person the branch and the
  compare link it returns, where they open a pull request. `github_read` reads the default branch, or your branch
  with `ref: agent`.
- Your skills hold the craft and the commands of each engine. The ones this project has are listed for you; open
  one with the Skill tool before the work it covers, not before. A skill's text names its reference files by
  their path under its base directory, and you read one with the Read tool when the step you are on needs it.
  Read reads nothing else.
- You can hand work to a subagent with the Agent tool: one job, described so that it stands on its own, since a
  subagent knows nothing of this conversation. It works with its own tools and comes back with a report, which
  the person does not see; tell them what matters of it. Hand over what is self-contained and would crowd this
  conversation (research, a survey of the library, a long run of commands in one engine), and start several in
  one step when their jobs do not depend on each other. Do yourself what is quick, and everything that needs the
  person: a subagent cannot ask them.
- Your own tools are named `mcp__moody__<name>` in your tool list; this prompt and the skills call each by its
  `<name>`.
- The project's state (its name, plan, library, engines, and GitHub link) follows the person's message at the
  start of each turn, in a `<project_state>` block that {brand} writes, not the person. Trust it over what you
  remember of earlier turns.
- Before you start, say in a line what you are about to do; brief updates while you work help the person follow
  along.

# Communicating clearly

Write for an intelligent reader who has not seen your tool calls or your reasoning. Put the key point first, use
plain words in full sentences, and do not use a term you made up during the work.

A short exchange gets a short answer in plain sentences, with no headings: the person is making something with
you, and structure on a reply of a few lines reads like paperwork. A long job (many steps, subagents, or minutes
of work) ends with a report, because the person was not watching and picks the work up from your last message
alone. Put it under short headings chosen for what there is to say, such as what was done, what there is now,
the decisions that are theirs, what you need from them, and what you do not know: a few bullets under each, the
most important first, and only the headings that have content."""


# What a subagent is told beside its own prompt
SUBAGENT_NOTE = """Your tools are named `mcp__moody__<name>` in your tool list; your instructions and the skills call each by its
`<name>`. You work for the project's agent, not for the person: you cannot ask the person anything, and they do not
see what you write. Your last message is your report to the agent. Make it stand on its own: what you did, what you
found, the ids, tags, and paths the agent needs to go on, and anything you could not do and why."""


# Tools: each one's definition for the model and the loop, a title for the page, and its implementation
# (`Agent.tool_<name>`)


def tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
    *,
    activity: str,
    reads: bool = False,
    approval: str | None = None,
    main_only: bool = False,
) -> dict[str, Any]:
    """A tool's definition: what the model is told of it, and what the loop and the page are.

    `activity` is what the agent looks like while the tool runs, one of the
    catalog's `activities`. `reads` says the tool changes nothing, so the loop
    may run it beside other such calls. `approval` is `ask` for a tool the
    person approves before it runs. `main_only` keeps a tool to the agent
    itself: a subagent is not offered it.
    """
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": properties, "required": required},
        "activity": activity,
        "read_only": reads,
        "approval": approval,
        "main_only": main_only,
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
LOOK = {
    "type": "boolean",
    "description": (
        "true to be handed one small picture of each result (an image itself, four frames of a video on one sheet), "
        "when you have to judge it yourself. Without it you get the result's facts only; library_look shows a "
        "result you saved to the library later."
    ),
}
TOOLS = [
    tool(
        "ask_user",
        "Ask the person a question whose answer is theirs to give, with options they can pick. This ends your turn: "
        "the question is shown to them, and their answer, an option or their own words, is the next message you get.",
        {
            "question": {"type": "string", "description": "The question, in a sentence or two."},
            "options": {
                **STRINGS,
                "description": "Two to five short answers to pick from. An option's text is only the option: it "
                "never says that it is recommended.",
            },
            "recommended": {
                "type": "string",
                "description": "The option you would choose for this project, where you have a view, written exactly "
                "as it is in options. The person sees it marked as your recommendation. Leave it out where you have "
                "no real preference.",
            },
        },
        ["question", "options"],
        activity="curious", main_only=True,
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
        activity="thinking",
    ),
    tool(
        "set_library_sections",
        "Set the library's sections, in the order the person sees them, such as Characters, Environments, Props. A "
        "section that still has entries stays, after the ones given.",
        {"sections": STRINGS},
        ["sections"],
        activity="processing",
    ),
    tool(
        "library_list",
        "List the library's entries, or one section's: each entry's id, section, name, tag, description, metadata, "
        "and its media files.",
        {"section": STRING},
        [],
        activity="searching", reads=True,
    ),
    tool(
        "library_look",
        "Look at library entries yourself: you are handed one small picture of each entry's newest media (an image "
        "itself, four frames of a video on one sheet, a sound's waveform). Use it to judge what was generated or "
        "uploaded before you describe it, choose between candidates, or review it. The person is shown nothing new.",
        {
            "tags": {**STRINGS, "description": "The entries' tags."},
            "each": {
                "type": "integer",
                "minimum": 1,
                "maximum": LOOK_PICTURES,
                "description": f"How many of each entry's media to look at, newest first; 1 unless given. One call "
                f"hands you at most {LOOK_PICTURES} pictures.",
            },
        },
        ["tags"],
        activity="analyzing", reads=True,
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
        activity="creating",
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
            "look": LOOK,
        },
        ["prompt"],
        activity="creating",
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
            "look": LOOK,
        },
        ["prompt"],
        activity="creating", approval="ask",
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
        activity="processing", approval="ask",
    ),
    tool("engine_list", "List this project's open engines.", {}, [], activity="searching", reads=True),
    tool("engine_stop", "Stop one of this project's engines, which ends its cost.", {"engine_id": ENGINE_ID}, ["engine_id"], activity="processing"),
    tool(
        "engine_screenshot",
        "See what a running engine's screen shows now, as the person sees it.",
        {"engine_id": ENGINE_ID},
        ["engine_id"],
        activity="analyzing",
    ),
    tool(
        "engine_exec",
        "Run a shell command in a running engine, as its user, in its environment, and get its exit status and "
        f"output. It may run for {EXEC_SECONDS // 60} minutes.",
        {"engine_id": ENGINE_ID, "command": {"type": "string", "description": "A bash command."}},
        ["engine_id", "command"],
        activity="processing",
    ),
    tool(
        "engine_show",
        "Put a running engine on the person's Screen panel, in one of the pictures it streams: Desktop (its desktop: "
        "files, the GitHub client, Firefox, Blender) or, for an Unreal engine, Unreal (the editor's own stream). Show "
        "what you want the person to look at or work in, such as Desktop to sign in to GitHub and clone their game.",
        {
            "engine_id": ENGINE_ID,
            "stream": {"type": "string", "enum": [DESKTOP, UNREAL_VIEW], "description": "Left out: Desktop."},
        },
        ["engine_id"],
        activity="processing",
    ),
    tool(
        "engine_import",
        "Copy library entries' media into a running engine, under the project folder's library/<tag>/ folders.",
        {"engine_id": ENGINE_ID, "tags": STRINGS},
        ["engine_id", "tags"],
        activity="processing",
    ),
    tool(
        "engine_call",
        "Call a method of a running engine's command channel, whichever app it runs: the same commands that app's "
        "interface runs. Returns the app's answer. An engine whose app has no command channel says so; drive that one "
        "with engine_exec, or ask the person to do the step on its screen.",
        {
            "engine_id": ENGINE_ID,
            "method": {"type": "string", "description": "The method's name, as the app's skill gives it."},
            "params": {"type": "object", "description": "The method's parameters, where it takes any."},
        },
        ["engine_id", "method"],
        activity="processing",
    ),
    tool(
        "engine_files",
        "List the project's folder, or a folder or file inside it, as a running engine sees it: each entry's name, "
        "kind (file or folder), size in bytes, and when it was last modified. Every engine of the project opens in "
        "this folder, but a running engine sees only what was there when it started and what it wrote itself, so "
        "use it to confirm a file is there on the engine that is about to open it.",
        {
            "engine_id": ENGINE_ID,
            "path": {
                "type": "string",
                "description": "A path inside the project's folder, like handoff/cadcraft-to-blender. Left out: the "
                "folder itself.",
            },
        },
        ["engine_id"],
        activity="searching", reads=True,
    ),
    tool(
        "engine_send",
        "Carry a file or a folder of the project's folder from one running engine to another running engine, which "
        "does not see what the first wrote after it started. It arrives at the same path in the receiving engine's "
        "folder unless to_path says otherwise, complete or not at all, and is on the project's storage for every "
        "engine started later. Returns its size, how long it took, and its entry as the receiving engine lists it. "
        "There is a size limit, which a refusal names.",
        {
            "from_engine_id": {"type": "string", "description": "The running engine that has the file."},
            "path": {
                "type": "string",
                "description": "The file or folder, inside the project's folder, like handoff/soundcraft-to-filmcraft/mix.wav.",
            },
            "to_engine_id": {"type": "string", "description": "The running engine that receives it."},
            "to_path": {"type": "string", "description": "Where it goes in the project's folder. Left out: the same path."},
        },
        ["from_engine_id", "path", "to_engine_id"],
        activity="processing",
    ),
    tool(
        "preview",
        "Show the person work in progress: one or more files an engine wrote in the project's folder (a frame, a "
        "range you bounced or exported, a render, a document), as a card in the conversation with your caption. "
        "What you render, and how long or large, is yours to choose with the engine's own commands; a file too heavy "
        "for a conversation, or in a format browsers do not play, is shown as a lighter copy the engine encodes, the "
        "original untouched. You get each file's facts (length, dimensions, size, and for sound its loudness and "
        "peak), not the picture or the sound; ask for those with look only when you must judge the result yourself. "
        "A preview is not kept in the library.",
        {
            "engine_id": ENGINE_ID,
            "path": {"type": "string", "description": "A file inside the project's folder, like previews/chorus.wav."},
            "paths": {**STRINGS, "description": "Several files, in the order to show them, in place of path."},
            "caption": {"type": "string", "description": "One line that says what this shows and what changed."},
            "kind": {
                "type": "string",
                "enum": list(PREVIEW_KINDS),
                "description": "What the files are. Left out: read from each file's name.",
            },
            "compare": {
                "type": "boolean",
                "description": "With exactly two files of one kind: show them as a before and after pair, before first.",
            },
            "look": {
                "type": "boolean",
                "description": "Also return a small picture of each file to you: an image itself, four frames of a "
                "video, the waveform of a sound.",
            },
        },
        ["engine_id", "caption"],
        activity="analyzing",
    ),
    tool("show_ui", genui.DESCRIPTION, genui.properties(genui.catalog()), ["title"], activity="creating", main_only=True),
    tool(
        "filmcraft",
        "Call a method of FilmCraft's command channel in a running FilmCraft engine: the same commands its interface "
        "runs. Returns FilmCraft's answer.",
        {"engine_id": ENGINE_ID, "method": STRING, "params": {"type": "object"}},
        ["engine_id", "method"],
        activity="processing",
    ),
    tool(
        "github_save",
        "Save a text file to the project's GitHub repository in one commit, creating or replacing it, on the agent's "
        "own branch (moody/<project>-<id>), which is made from the default branch the first time. It never writes to "
        "the default branch or to a branch the agent did not make. Returns the branch and a compare link, where the "
        "person opens a pull request.",
        {
            "path": {"type": "string", "description": "A path in the repository, like script/mara.fountain."},
            "content": STRING,
            "message": {"type": "string", "description": "The commit message."},
        },
        ["path", "content", "message"],
        activity="processing",
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
        activity="analyzing", reads=True,
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
        activity="searching", reads=True,
    ),
    tool(
        "unreal_projects",
        "List the Unreal projects (.uproject files) in a running Unreal engine's workspace, such as a game the person "
        "cloned there: each one's path, name, the engine version it was saved with (EngineAssociation) and how this "
        "engine opens it, its C++ modules, its plugins, whether its repository uses Git LFS, and its size.",
        {"engine_id": ENGINE_ID},
        ["engine_id"],
        activity="searching", reads=True,
    ),
    tool(
        "unreal_open",
        "Open an Unreal project of a running Unreal engine's workspace in the Unreal Editor, which streams to the "
        "engine's Unreal view, and switch the person's screen to it. A project saved with an older engine is first "
        "put on the agent's own branch in its clone, so the editor's upgrade stays off the team's branches; a newer "
        "one is refused. Where the editor cannot open (no Epic link, or an engine started before it), says why and "
        "what the person does.",
        {"engine_id": ENGINE_ID, "path": {"type": "string", "description": "The .uproject's path, from unreal_projects."}},
        ["engine_id", "path"],
        activity="processing",
    ),
]
TOOL_NAMES = [definition["name"] for definition in TOOLS]
SPECS = {definition["name"]: definition for definition in TOOLS}
# What a tool's `approval` says where the person approves each call of it, and what a project's permissions say
# where they no longer want to be asked
APPROVAL_ASK = "ask"
# How an option of a question would say that it is the recommended one, in lowercase, which the page says itself
RECOMMENDED_MARK = "(recommended"
ALWAYS = "always"


def check_activities(catalog: Catalog) -> None:
    """Hold every tool's `activity`, and the loop's own tools', to the activities the catalog names.

    Raises:
        ValueError: A tool names an activity the catalog does not have, which the page could not draw.
    """
    known = {activity["id"] for activity in catalog.data.get("activities", [])}
    named = {definition["name"]: definition["activity"] for definition in TOOLS}
    named.update({name: built_in.activity for name, built_in in BUILT_INS.items()})
    unknown = {name: activity for name, activity in named.items() if activity not in known}
    if unknown:
        raise ValueError(f"these tools name activities catalog.json does not have: {unknown}")


def loop_settings(config: Config, limits: dict[str, Any]) -> Settings:
    """What the deployment configures of the loop, and the limits of the person whose turn it runs (`Sessions.limits`).

    Raises:
        ValueError: The configured effort is none the loop knows.
    """
    if config.agent_effort not in get_args(EffortLevel):
        raise ValueError(f"MOODY_AGENT_EFFORT is {config.agent_effort!r}; the loop takes {', '.join(get_args(EffortLevel))}")
    return Settings(
        key=config.anthropic_key,
        model=config.agent_model or DEFAULT_MODEL,
        effort=config.agent_effort,
        thinking=config.agent_thinking,
        fallback_model=config.agent_fallback_model,
        budget_usd=float(limits["turn_budget_usd"]),
        turn_limit=int(limits["turn_limit"]),
        base_url=config.anthropic_base_url,
        passed=config.loop_env,
        cli=config.loop_cli,
    )


def recap(events: list[dict[str, Any]]) -> str:
    """What was said in a project before its session began, from its event log, for the session's first message.

    The person's messages, the agent's answers, and its questions, oldest
    first and the most recent kept where there is more than a recap carries.
    A block of an answer is in the log once whole, after its snapshots, and
    only the whole one is told.
    """
    lines = []
    for event in events:
        data = event["data"]
        if data.get("agent_id") or data.get("partial"):
            continue
        if event["kind"] == "user_message":
            lines.append(f"The person: {data.get('text', '')}")
        elif event["kind"] == "text":
            lines.append(f"You: {data.get('text', '')}")
        elif event["kind"] == "ask":
            advised = f"; you recommended {data['recommended']}" if data.get("recommended") else ""
            lines.append(f"You asked: {data.get('question', '')} ({' / '.join(data.get('options', []))}{advised})")
    kept: list[str] = []
    for line in reversed(lines[-RECAP_EVENTS:]):
        if sum(map(len, kept)) + len(line) > RECAP_CHARACTERS:
            break
        kept.append(line)
    return "\n".join(reversed(kept))


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


def folder_path(path: str, folder: str) -> str:
    """A path inside a project's folder, relative to it, from one given relative to it or in full.

    Raises:
        Refused: 400 for a path outside the folder.
    """
    given = PurePosixPath(path.strip() or ".")
    if given.is_absolute():
        if not given.is_relative_to(folder):
            raise Refused(400, f"That path is outside the project's folder, {folder}.")
        given = given.relative_to(folder)
    if ".." in given.parts:
        raise Refused(400, f"That path is outside the project's folder, {folder}.")
    return "" if given == PurePosixPath(".") else given.as_posix()


def listed_file(line: str) -> dict[str, Any] | None:
    """One entry of an engine's listing (`FILES_FORMAT`) as `engine_files` gives it, or nothing for another line.

    A folder has no size of its own worth giving, and anything that is neither
    a file nor a folder (a link, a socket) is `other`.
    """
    parts = line.split("\t", 3)
    if len(parts) != 4 or not parts[3]:
        return None
    kind, size, seconds, name = parts
    try:
        modified = datetime.fromtimestamp(float(seconds), timezone.utc).isoformat(timespec="seconds")
        entry = {"name": name, "kind": {"f": "file", "d": "folder"}.get(kind, "other"), "size": int(size)}
    except (ValueError, OverflowError):
        return None
    if entry["kind"] == "folder":
        del entry["size"]
    return {**entry, "modified": modified}


def readable_size(size: int) -> str:
    """A size in bytes as a person reads it: `812 KB`, `2.3 MB`, `1.4 GB`."""
    if size < MEGABYTE:
        return f"{max(1, round(size / 1024))} KB"
    if size < 1024 * MEGABYTE:
        return f"{size / MEGABYTE:.1f} MB"
    return f"{size / (1024 * MEGABYTE):.1f} GB"


def media_kind(name: str) -> str:
    """What a file is to a preview, by its name's ending: `image`, `audio`, or `video`, and `file` for anything else.

    The ending decides, not ffprobe: ffprobe finds a "video stream" in a text
    file and a "picture" in a PDF, so a file whose ending names no media is a
    plain file unless the agent says what it is.
    """
    ending = PurePosixPath(name).suffix.lower()
    guessed = MEDIA_ENDINGS.get(ending) or (mimetypes.guess_type(name)[0] or "").split("/")[0]
    return guessed if guessed in MEDIA_KINDS else "file"


def probed(output: str) -> tuple[int, dict[str, Any] | None]:
    """What an engine's probe of a file printed: the file's size, and ffprobe's answer, or nothing where it has no ffmpeg.

    A file ffprobe cannot read answers with no streams, which is an answer.

    Raises:
        RuntimeError: The output is not a probe's.
    """
    first, _, rest = output.partition("\n")
    try:
        size = int(first.strip())
    except ValueError:
        raise RuntimeError(f"the engine's probe answered {output[:200]!r}") from None
    if rest.strip() == NO_FFMPEG:
        return size, None
    try:
        answer = json.loads(rest)
    except ValueError:
        answer = {}
    return size, answer if isinstance(answer, dict) else {}


def media_stream(probe: dict[str, Any], kind: str) -> dict[str, Any]:
    """The first stream of a kind (`video`, `audio`) in ffprobe's answer, or an empty one."""
    return next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == kind), {})


def media_facts(kind: str, probe: dict[str, Any]) -> dict[str, Any]:
    """What ffprobe's answer says of a file of a kind: its length, its size on screen, and what it is encoded as.

    A picture has no length worth giving (ffprobe reports one frame's), and
    sound has no size on screen.
    """
    facts: dict[str, Any] = {}
    picture, sound = media_stream(probe, "video"), media_stream(probe, "audio")
    try:
        seconds = float(probe.get("format", {}).get("duration") or 0)
    except ValueError:
        seconds = 0.0
    if kind in ("audio", "video") and seconds > 0:
        facts["seconds"] = round(seconds, 2)
    if kind in ("image", "video") and picture.get("width") and picture.get("height"):
        facts["width"], facts["height"] = picture["width"], picture["height"]
    if kind in ("image", "video") and picture.get("codec_name"):
        facts["codec"] = picture["codec_name"]
    if kind == "audio" and sound:
        facts["codec"] = sound.get("codec_name")
    if kind in ("audio", "video") and sound.get("sample_rate"):
        facts["sample_rate"], facts["channels"] = int(sound["sample_rate"]), sound.get("channels")
    return facts


def plays_in_browser(kind: str, name: str, probe: dict[str, Any] | None) -> bool:
    """Whether a browser shows a file of a kind as it is: by its ending, and for video by its codec and pixel format.

    Without ffprobe's answer the ending is all there is to go by.
    """
    if PurePosixPath(name).suffix.lower() not in WEB_ENDINGS.get(kind, ()):
        return False
    if kind != "video" or probe is None:
        return True
    picture = media_stream(probe, "video")
    return picture.get("codec_name") in WEB_VIDEO_CODECS and picture.get("pix_fmt") in WEB_PIXEL_FORMATS


def loudness(output: str) -> dict[str, float]:
    """The integrated loudness and true peak in the summary ffmpeg's `ebur128` filter prints, as far as it has them."""
    found = {}
    for name, pattern in (("loudness_lufs", r"^\s+I:\s+(-?[\d.]+) LUFS"), ("true_peak_dbfs", r"^\s+Peak:\s+(-?[\d.]+) dBFS")):
        matches = re.findall(pattern, output, flags=re.MULTILINE)
        if matches:
            found[name] = float(matches[-1])
    return found


@dataclass
class Shown:
    """One file of a preview, ready to store: what the person is shown, and what the model is told of it."""

    # The event's item, without the path it is stored at: its kind, name, and length and size on screen where known
    item: dict[str, Any]
    data: bytes
    content_type: str
    # The name it is stored under, which ends as the copy does where one was encoded
    stored_as: str
    # The file's facts, for the model
    facts: dict[str, Any]
    # The picture `look` hands the model, where it was asked for and could be made
    picture: bytes | None = None


def agent_branch(project: dict[str, Any]) -> str:
    """The branch a project's agent makes in its repository: `moody/<name as a slug>-<the id's first eight characters>`."""
    letters = unicodedata.normalize("NFKD", project["name"]).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", letters).strip("-")[:40].rstrip("-") or "project"
    return f"{BRANCH_PREFIX}{slug}-{project['id'][:8]}"


def reported_unreal(history: list[dict[str, Any]]) -> set[str]:
    """The `.uproject` paths that a conversation's `unreal_projects` calls returned to the model.

    `history` is the session's messages as the Messages API has them, each a
    role and its content.
    """
    calls = {
        block.get("id")
        for message in history
        if message["role"] == "assistant" and isinstance(message["content"], list)
        for block in message["content"]
        if block.get("type") == "tool_use" and block.get("name") == f"{PREFIX}unreal_projects"
    }
    paths: set[str] = set()
    for message in history:
        if message["role"] != "user" or not isinstance(message["content"], list):
            continue
        for block in message["content"]:
            if block.get("type") != "tool_result" or block.get("tool_use_id") not in calls or block.get("is_error"):
                continue
            said = block.get("content")
            if isinstance(said, list):
                said = "".join(part.get("text", "") for part in said if isinstance(part, dict))
            try:
                answer = json.loads(said)
            except (TypeError, ValueError):
                continue
            projects = answer.get("projects") if isinstance(answer, dict) else None
            paths.update(project["path"] for project in projects or [] if isinstance(project, dict) and "path" in project)
    return paths


@dataclass
class Result:
    """What a tool gives back: the model's result, the page's summary, whether it worked, and media to show."""

    content: str | list[dict[str, Any]]
    summary: str
    ok: bool = True
    media: list[dict[str, Any]] = field(default_factory=list)
    ends_turn: bool = False


class Turn:
    """One turn of one project: who it acts for, its events, and its heartbeat."""

    def __init__(self, sessions: Sessions, project: dict[str, Any], turn_id: str, heartbeat_seconds: float) -> None:
        self.sessions = sessions
        self.project = project
        self.turn_id = turn_id
        profile = sessions.me(User(id=project["user_id"], email=""))
        self.user = User(id=project["user_id"], email=profile["email"])
        # What this turn may spend and how many steps it may take: its person's limits as the turn began
        self.limits: dict[str, Any] = profile["limits"]
        self.stopped = threading.Event()
        self.done = threading.Event()
        self.heartbeat_seconds = heartbeat_seconds
        self.heart = threading.Thread(target=self._beat_until_done, daemon=True)
        # Whether the turn has put a question to the person, which it does once
        self.asked = False
        # The subagent the tool running on this thread was called by, where it was one
        self.actor = threading.local()

    @property
    def project_id(self) -> str:
        return self.project["id"]

    def beat(self) -> bool:
        """Say the turn is alive and learn whether it should go on."""
        if not self.sessions.store.rpc("moody_turn_alive", p_project=self.project_id, p_turn=self.turn_id):
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

    @contextmanager
    def acting(self, agent_id: str | None) -> Iterator[None]:
        """Mark the events this thread writes meanwhile as a subagent's, where one is given."""
        self.actor.agent_id = agent_id
        try:
            yield
        finally:
            self.actor.agent_id = None

    def event(self, kind: str, data: dict[str, Any]) -> None:
        """Append an event of this turn to the project's log, as the subagent's whose tool writes it."""
        agent_id = getattr(self.actor, "agent_id", None)
        if agent_id and "agent_id" not in data:
            data = {**data, "agent_id": agent_id}
        self.sessions.add_event(self.project_id, self.turn_id, kind, data)


class Agent:
    """The agent's turns and its tools, over a `Sessions` for the projects' data and engines.

    Each tool is a method `tool_<name>` whose keyword arguments are its
    input's fields, which the loop checked against its schema before the call
    (`run_tool`); what it does is its definition's description in `TOOLS`,
    and it answers with a `Result` or raises `Refused` with what to tell the
    model. `loop` is what runs a turn: the Claude Agent SDK, or what a test
    puts in its place.
    """

    def __init__(
        self,
        sessions: Sessions,
        loop: Loop,
        generator: Generator | None,
        skills: list[Skill],
        agents: list[AgentSpec] | None = None,
        derived: list[AgentSpec] | None = None,
    ) -> None:
        check_activities(sessions.catalog)
        self.sessions = sessions
        self.loop = loop
        self.generator = generator
        self.skills = skills
        # The subagents defined in files, and the operators derived from the apps that have a skill
        self.agents = agents or []
        self.derived = derived or []
        self.heartbeat_seconds: float = HEARTBEAT_SECONDS
        self.approval_poll_seconds: float = APPROVAL_POLL_SECONDS
        # A definition that names a tool or a skill there is none of stops the agent here, not in the middle of a
        # person's turn
        known = {skill.name for skill in skills}
        for agent in (*self.agents, *self.derived):
            missing = [name for name in agent.skills if name not in known]
            if missing:
                raise ValueError(f"the subagent {agent.name} names skills there are none of: {', '.join(missing)}")
        for discipline in sessions.catalog.disciplines:
            self.subagents({"discipline": discipline}, skills_for(skills, sessions.catalog, discipline))

    @classmethod
    def for_deployment(cls, sessions: Sessions) -> Agent:
        """The agent as the deployment configures it: the loop, fal where there is a key, the skills, and the subagents."""
        skills = read_skills(skills_directory())
        return cls(
            sessions,
            sdk_loop,
            Fal(sessions.config.fal_key) if sessions.config.fal_key else None,
            skills,
            read_agents(agents_directory()),
            operators(agents_directory(), sessions.catalog, skills),
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
            self.store.rpc("moody_end_turn", p_project=project_id, p_turn=turn_id)

    # The turn

    def converse(self, turn: Turn) -> None:
        """Hand the turn's message to the loop and let it work until it is done, asks, or is stopped."""
        opening = self.store.rows("project_events", turn_id=f"eq.{turn.turn_id}", kind="eq.user_message")
        if not opening or not turn.beat():
            return
        anyio.run(self.work, turn, opening[0]["data"])

    async def work(self, turn: Turn, said: dict[str, Any]) -> None:
        """One turn on the loop: its working directory, its session, what it is told, and the run itself."""
        config, catalog, project = self.sessions.config, self.sessions.catalog, turn.project
        offered = skills_for(self.skills, catalog, project["discipline"])
        store = Transcript(self.store, turn.project_id)
        with Workspace(config.loop_root, turn.project_id) as workspace:
            session, resume = await anyio.to_thread.run_sync(self.session, turn, store, workspace)
            prompt = await anyio.to_thread.run_sync(self.prompt, turn, said, store, session, resume, workspace)
            unasked = [
                name
                for name, definition in SPECS.items()
                if definition["approval"] != APPROVAL_ASK or project["permissions"].get(name) == ALWAYS
            ]
            brief = Brief(
                system=system_prompt(catalog, project, config.tiers),
                prompt=prompt,
                tools=[
                    ToolSpec(name, definition["description"], definition["input_schema"], definition["activity"], definition["read_only"])
                    for name, definition in SPECS.items()
                ],
                unasked=unasked,
                subagents=self.subagents(project, offered),
                skills=[(skill.name, skill.directory) for skill in offered],
                session=session,
                resume=resume,
                store=store,
                workspace=workspace,
            )
            activities = {name: definition["activity"] for name, definition in SPECS.items()}
            await TurnLoop(self, turn, brief, loop_settings(config, turn.limits), activities).run(self.loop)

    def session(self, turn: Turn, store: Transcript, workspace: Workspace) -> tuple[str, bool]:
        """The loop's session that is the project's conversation, and whether it is resumed or begins now.

        A project keeps one session. It is resumed where its transcript is in
        the database under this turn's working directory, and otherwise a new
        one is named and kept before the turn runs, so what the turn writes is
        found by the next one whatever happens to this one's machine.
        """
        project = turn.project
        session = project.get("agent_session")
        key = project_key_for_directory(workspace.directory)
        if session and store.has({"project_key": key, "session_id": session}):
            return session, True
        session = str(uuid.uuid4())
        self.store.update("projects", {"agent_session": session}, id=f"eq.{turn.project_id}")
        project["agent_session"] = session
        return session, False

    def prompt(
        self, turn: Turn, said: dict[str, Any], store: Transcript, session: str, resume: bool, workspace: Workspace
    ) -> list[dict[str, Any]]:
        """The turn's message as the model reads it: the person's words, then the project's state as Moody's own block.

        Where the message locks in an interactive card, a line after the
        person's words says which card and with which values. A session that
        begins now, in a project whose log already has turns, is first told
        what was said in them (`recap`).
        """
        words = said.get("text", "")
        locked = said.get("ui")
        if locked:
            shown = self.store.rows("project_events", project_id=f"eq.{turn.project_id}", kind="eq.ui")
            title = next((row["data"].get("title", "") for row in shown if row["data"].get("ui_id") == locked["ui_id"]), "")
            words += (
                f"\n\n[The person locked in the card {json.dumps(title or locked['ui_id'])} (ui_id {locked['ui_id']}) "
                f"with these values: {json.dumps(locked.get('value'))}]"
            )

        def history() -> list[dict[str, Any]]:
            if not resume:
                return []
            messages = anyio.from_thread.run(get_session_messages_from_store, store, session, str(workspace.directory))
            return [
                {"role": message.type, "content": message.message.get("content") if isinstance(message.message, dict) else None}
                for message in messages
            ]

        state = self.state(turn, history)
        if not resume:
            earlier = self.store.every("project_events", project_id=f"eq.{turn.project_id}", order="id.asc")
            before = recap([row for row in earlier if row["turn_id"] != turn.turn_id])
            if before:
                state = (
                    "What was said in this project before this conversation, of which you remember nothing else:\n"
                    f"{before}\n\n{state}"
                )
        return [{"type": "text", "text": words}, {"type": "text", "text": f"<project_state>\n{state}\n</project_state>"}]

    def subagents(self, project: dict[str, Any], offered: list[Skill]) -> list[Subagent]:
        """The subagents a project is offered, as the loop takes them.

        A definition's tools are Moody's names or patterns over them, and may
        name the loop's own web search and fetch; a tool kept to the agent
        itself is left out, since a subagent cannot speak to the person. Its
        model is the tier its definition names, as the deployment maps it.

        Raises:
            ValueError: A definition names a tool there is none of.
        """
        config = self.sessions.config
        models = {"inherit": "inherit", "balanced": config.agent_model_balanced, "light": config.agent_model_light}
        own = [name for name, definition in SPECS.items() if not definition["main_only"]]
        named = [*own, *(name for name in BUILT_INS if name in ("web_search", "web_fetch"))]
        return [
            Subagent(
                name=agent.name,
                title=agent.title,
                description=agent.description,
                prompt=f"{agent.prompt}\n\n{SUBAGENT_NOTE}",
                tools=tuple(matching(agent.tools, named)) if agent.tools else (),
                skills=agent.skills,
                model=models[agent.model],
            )
            for agent in agents_for(self.agents, self.derived, offered, self.sessions.catalog, project["discipline"])
        ]

    def state(self, turn: Turn, history: Callable[[], list[dict[str, Any]]]) -> str:
        """The project as it is now, which follows the person's message at the start of a turn.

        `history` gives the session's messages so far, and is asked only where
        the state depends on them (`unreal_state`).
        """
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
        open_engines = [engine for engine in self.sessions.engines(turn.user, project["id"]) if engine["status"] in OPEN]
        launcher = self.sessions.launcher
        engines = [
            f"- {engine['id']}: {self.app_name(engine['app'])} (app `{engine['app']}`), {engine['status']}, "
            f"tier {engine['tier']}, "
            + (
                "has a command channel (engine_call)"
                if launcher.has_channel(engine["app"])
                else "no command channel (engine_exec, or the person on its screen)"
            )
            + (f", streaming {' and '.join(STREAMS[engine['app']])}" if engine["app"] in STREAMS else "")
            for engine in open_engines
        ]
        credits = self.sessions.me(turn.user)["credits"]
        always = sorted(name for name, value in project["permissions"].items() if value == ALWAYS)
        return "\n".join(
            [
                "The project's state at the start of this turn:",
                f"Name: {project['name']}",
                f"GitHub: {linked}",
                f"Generation: {'available' if self.generator else 'not configured on this deployment'}",
                f"Credits the person has: {credits}",
                f"The person no longer wants to be asked before: {', '.join(always) or '(nothing; they are asked each time)'}",
                "Plan:",
                *(plan or ["- (empty)"]),
                f"Library sections: {', '.join(project['library_sections']) or '(none)'}",
                "Library entries:",
                *(entries or ["- (none)"]),
                f"Project folder, which every engine of this project opens in and shares: {project_folder(project['id'])}",
                "Open engines:",
                *(engines or ["- (none)"]),
                *self.unreal_state(turn, open_engines, history),
            ]
        )

    def unreal_state(
        self, turn: Turn, engines: list[dict[str, Any]], history: Callable[[], list[dict[str, Any]]]
    ) -> list[str]:
        """What a turn's start says of the Unreal projects in each running Unreal engine's workspace.

        The machine is asked only for a running Unreal engine, once per turn, and the session is read
        back only then. A project no earlier `unreal_projects` call of the session returned is marked
        as not reported yet, with what to do about it: what the person cloned is what they want to
        talk about next. A clone the engine made as it started and has not finished, or that failed,
        is said first: until it is done the project is not there to report, and a failed one the
        person clones by hand.
        """
        lines = []
        running = [engine for engine in engines if engine["app"] == "unreal" and engine["status"] == "running"]
        reported = reported_unreal(history()) if running else set()
        for engine in running:
            clone = self.sessions.engine_clone(turn.user, turn.project_id, engine["id"])
            repo = turn.project["github_repo"] or "the linked repository"
            if clone is not None and clone["state"] == "cloning":
                lines.append(
                    f"Engine {engine['id']} is still cloning {repo} into {clone['path'] or 'the project folder'}"
                    + (f" ({clone['detail']})" if clone["detail"] else "")
                    + ". Say so if the person asks for the project; it is listed once the clone is done."
                )
            elif clone is not None and clone["state"] == "failed":
                lines.append(
                    f"Engine {engine['id']} could not clone {repo} as it started: {clone['detail'] or 'no reason given'}. "
                    "Tell the person, and that they can clone it in the Desktop view's GitHub client instead."
                )
            try:
                found = self.sessions.unreal_projects(turn.user, turn.project_id, engine["id"])
            except Refused as refused:
                lines.append(f"Unreal projects in engine {engine['id']}: not known right now ({refused.message})")
                continue
            if not found:
                lines.append(f"Unreal projects in engine {engine['id']}'s workspace: none yet.")
                continue
            fresh = [project["path"] for project in found if project["path"] not in reported]
            lines.append(f"Unreal projects in engine {engine['id']}'s workspace:")
            lines.extend(
                f"- {project['path']} ({project['name']})" + (", not reported yet" if project["path"] in fresh else "")
                for project in found
            )
            if fresh:
                lines.append(
                    "Before anything else, call unreal_projects and tell the person what you found in the ones not "
                    "reported yet (engine version, C++ or Blueprints, plugins, Git LFS), and offer to open it in Unreal."
                )
        return lines

    # What the loop asks of the agent (`loop.Host`)

    def run_tool(self, turn: Turn, name: str, arguments: dict[str, Any], call_id: str, agent_id: str | None) -> Result:
        """Run one call with its `tool_end` event, and return its result for the model.

        The call's `tool_start` is the loop's to write, as it reports the call.
        A tool kept to the agent itself is refused to a subagent, and nothing
        runs once the turn is stopped.
        """
        with turn.acting(agent_id):
            try:
                if not turn.beat():
                    raise TurnStopped()
                if agent_id and SPECS[name]["main_only"]:
                    raise Refused(409, f"Only the agent itself can use {name}. Put what you need from the person in your report.")
                result: Result = getattr(self, f"tool_{name}")(turn, **arguments)
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
            ended = {"call_id": call_id, "ok": result.ok, "summary": result.summary}
            if result.media:
                ended["media"] = result.media
            turn.event("tool_end", ended)
        return result

    def approved(self, turn: Turn, name: str, arguments: dict[str, Any], agent_id: str | None) -> tuple[bool, str]:
        """Whether a call the loop may not make unasked may run, and what the model is told where it may not.

        A tool the person approves first is asked about here, unless the
        project's permissions have come to say `always` for it since the turn
        began: an `approval` event is written and the person's answer waited
        for, which `Sessions.answer_approval` records. A wait that outlasts
        `Config.approval_seconds` is recorded as expired, unless the answer
        arrived in that same moment, in which case the answer stands. Any
        other tool that reaches this is none the agent has.
        """
        definition = SPECS.get(name)
        if definition is None:
            return False, f"There is no tool {name}."
        if definition["approval"] != APPROVAL_ASK:
            return True, ""
        project = self.store.rows("projects", id=f"eq.{turn.project_id}")
        if project and project[0]["permissions"].get(name) == ALWAYS:
            return True, ""
        approval_id = uuid.uuid4().hex
        asked = {"approval_id": approval_id, "tool": name, "title": self.title(turn, name, arguments), "detail": self.approval_detail(name, arguments)}
        with turn.acting(agent_id):
            turn.event("approval", asked)
        deadline = time.monotonic() + self.sessions.config.approval_seconds
        decision = None
        while decision is None and time.monotonic() < deadline:
            if not turn.alive():
                return False, "Stopped by the person."
            answers = self.store.rows("project_events", project_id=f"eq.{turn.project_id}", kind="eq.approval_result")
            decision = next((row["data"]["decision"] for row in answers if row["data"].get("approval_id") == approval_id), None)
            if decision is None:
                time.sleep(self.approval_poll_seconds)
        if decision is None:
            decision = self.store.rpc("moody_resolve_approval", p_project=turn.project_id, p_approval=approval_id, p_decision=APPROVAL_EXPIRED)
        if decision in ("once", ALWAYS):
            return True, ""
        if decision == APPROVAL_EXPIRED:
            return False, (
                "The person did not answer in time, so this did not run. End your turn now: say in a line what you "
                "were about to do and why, and ask them to say when to go ahead. Do not call this again in this turn."
            )
        return False, "The person declined, so this did not run. Do not call it again; go on another way, or ask what they want."

    def approval_detail(self, name: str, arguments: dict[str, Any]) -> str:
        """What an approval tells the person beyond the call's title: what it will cost them, as far as that is known."""
        catalog = self.sessions.catalog
        if name == "engine_start":
            tier = catalog.tiers.get(arguments.get("tier", ""))
            if tier is None:
                return ""
            rate = tier["credits_per_minute"]
            return f"{tier['name']}: {rate} credit{'s' if rate != 1 else ''} a minute until it is stopped."
        if name == "generate_video":
            parts = [f"{arguments.get('model', 'standard')} model"]
            if arguments.get("duration_seconds"):
                parts.append(f"{arguments['duration_seconds']} seconds")
            parts.append(arguments.get("resolution", "720p"))
            return ", ".join(parts) + "."
        return ""

    def open_engines(self, turn: Turn) -> list[str]:
        """The project's engines that are open now, each as a line for the model."""
        return [
            f"- {engine['id']}: {self.app_name(engine['app'])}, {engine['status']}"
            for engine in self.sessions.engines(turn.user, turn.project_id)
            if engine["status"] in OPEN
        ]

    def title(self, turn: Turn, name: str, arguments: dict[str, Any]) -> str:
        """A short line that says what a call does, for the page.

        A call of an engine's command channel is titled with the engine's app, which is read from
        the engine the call names; one that names no engine of the project is titled "Engine".
        """
        apps = self.sessions.catalog.apps
        engine = "Engine"
        if name == "engine_call":
            try:
                engine = self.app_name(self.sessions.project_engine(turn.user, turn.project_id, arguments["engine_id"])["app"])
            except Refused:
                pass
        app = apps.get(arguments.get("app", ""), {}).get("name", arguments.get("app", ""))
        count = arguments.get("count", 1)
        return {
            "ask_user": "Asking you",
            "update_plan": "Updating the plan",
            "set_library_sections": "Arranging the library",
            "library_list": "Reading the library",
            "library_look": f"Looking at {', '.join(arguments.get('tags', []))}",
            "library_upsert": f"Saving {arguments.get('tag') or arguments.get('name', '')} to the library",
            "generate_image": f"Generating {count} image{'s' if count != 1 else ''}",
            "generate_video": "Generating a video",
            "engine_start": f"Starting {app}",
            "engine_list": "Checking the engines",
            "engine_stop": "Stopping an engine",
            "engine_screenshot": "Looking at the screen",
            "engine_exec": "Running a command",
            "engine_show": f"Showing {arguments.get('stream') or DESKTOP} on the screen",
            "engine_import": f"Importing {', '.join(arguments.get('tags', []))}",
            "engine_call": f"{engine}: {arguments.get('method', '')}",
            "engine_files": f"Listing {arguments.get('path') or 'the project folder'}",
            "engine_send": f"Sending {PurePosixPath(arguments.get('path', '')).name or 'a file'} to another engine",
            "preview": "Preparing a preview",
            "show_ui": f"Showing {arguments.get('title') or 'a card'}",
            "filmcraft": f"{self.app_name('filmcraft')}: {arguments.get('method', '')}",
            "github_save": f"Saving {arguments.get('path', '')} to the agent's branch on GitHub",
            "github_read": f"Reading {arguments.get('path', '') or 'the repository'} from "
            f"{'the agent' if arguments.get('ref') == 'agent' else 'the default'} branch on GitHub",
            "unreal_assets": f"Listing the Unreal project's {arguments.get('kind') or 'assets'}"
            + (f" in {arguments['path']}" if arguments.get("path") else ""),
            "unreal_projects": "Looking for Unreal projects in the engine",
            "unreal_open": f"Opening {PurePosixPath(arguments.get('path', '')).stem or 'the project'} in Unreal",
        }.get(name, name)

    # The person

    def tool_ask_user(self, turn: Turn, question: str, options: list[str], recommended: str | None = None) -> Result:
        """Put a question to the person, with the option the agent would choose where it has a view, and end the turn.

        The person's answer is the next turn's message. The page marks the
        recommendation itself, so it is named apart from the options and has
        to be one of them, and an option that carries the mark in its own
        text is sent back to be written without it. A question the agent has
        no preference on carries none.

        Raises:
            Refused: 409 for a second question in one turn, 400 for a recommendation that is none of
                the options or an option that says it is recommended.
        """
        if turn.asked:
            raise Refused(409, "Ask one question at a time; ask this one after the person answers.")
        chosen = None if recommended is None else next((option for option in options if option.strip() == recommended.strip()), None)
        if recommended is not None and chosen is None:
            raise Refused(
                400,
                f"recommended has to be one of the options, written exactly as it is there: {' / '.join(options)}. "
                "Ask again with the one you would choose.",
            )
        if any(RECOMMENDED_MARK in option.lower() for option in options):
            raise Refused(
                400,
                "An option's text is only the option: take the words that say it is recommended out of it, and name "
                "that option in recommended. Ask again.",
            )
        turn.asked = True
        turn.event("ask", {"question": question, "options": options, **({} if chosen is None else {"recommended": chosen})})
        return Result(
            "The question is with the person now, and this turn is over. Their answer is the next message you get.",
            "Asked",
            ends_turn=True,
        )

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

    def tool_library_look(self, turn: Turn, tags: list[str], each: int = 1) -> Result:
        """Hand the model a picture of the newest media of each entry named, `each` of them per entry.

        Raises:
            Refused: 400 for no tag or more pictures than one call hands over, 404 for a tag no entry has.
        """
        rows = self.sessions.assets_by_tags(turn.project, tags)
        chosen = [
            (f"{row['tag']}, {item['kind']} {place} of {len(row['media'])}: {item['name']}", item)
            for row in rows
            for place, item in enumerate(row["media"][:each], start=1)
        ]
        if not rows:
            raise Refused(400, "Name the entries to look at by their tags.")
        if len(chosen) > LOOK_PICTURES:
            raise Refused(400, f"That is {len(chosen)} pictures; one call hands you at most {LOOK_PICTURES}. Look at fewer entries, or fewer of each.")
        files = []
        unread = {}
        for label, item in chosen:
            try:
                files.append((label, item["kind"], self.store.download(LIBRARY_BUCKET, item["path"], LOOK_SOURCE_BYTES)))
            except ValueError:
                unread[label] = (
                    f"It is larger than the {readable_size(LOOK_SOURCE_BYTES)} that can be looked at here; import it "
                    "into a running engine and preview it with look."
                )
        pictures, missing = self.pictured(files)
        empty = [row["tag"] for row in rows if not row["media"]]
        answer = {
            "looked_at": [label for label, _, _ in files if label not in missing],
            "no_picture": {**unread, **missing},
            "no_media": empty,
            "note": "The pictures above are yours to judge by, each after the line that names it. The person was shown nothing.",
        }
        seen = len(files) - len(missing)
        return Result(
            [*pictures, {"type": "text", "text": json.dumps(answer)}],
            f"Looked at {seen} file{'s' if seen != 1 else ''}" if seen else "Nothing could be looked at",
            ok=bool(seen),
        )

    def pictured(self, files: list[tuple[str, str, bytes]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """The pictures `look` hands the model of files this worker holds, and why any could not be made.

        Each file is its label, its kind, and its bytes. A picture follows a
        line of text that is its label, so the model knows which is which; a
        file of a kind there is no picture of, or one the worker could make
        none of (`picture_of`), is named with the reason instead.
        """
        blocks: list[dict[str, Any]] = []
        missing = {}
        for label, kind, data in files:
            if kind not in MEDIA_KINDS:
                missing[label] = "It is not an image, a video, or a sound."
                continue
            try:
                picture = picture_of(data, kind)
            except NoPicture as reason:
                missing[label] = f"No picture could be made of it: {reason}"
                continue
            blocks += [{"type": "text", "text": label}, self.picture_block(picture)]
        return blocks, missing

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
        turn.event("library", {"asset": self.sessions.kept_asset(row)})
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
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[tuple[str, str, bytes]]]:
        """Store generated files in the library bucket: in the target entry where there is one, else beside the project.

        Returns the entry as changed, the files as the log keeps them under
        the call (each by its path, which is signed when the log is read,
        `Sessions.shown_events`), and the files themselves, each with a label
        and its kind, for `look` (`pictured`).
        """
        generator = self.require_generator()
        project = turn.project
        paths = []
        files = []
        for place, url in enumerate(urls, start=1):
            data, content_type = generator.download(url)
            files.append((f"{content_type.split('/')[0]} {place} of {len(urls)}", content_type.split("/")[0], data))
            extension = PurePosixPath(url.split("?")[0]).suffix[:6] or ".bin"
            name = f"{stem}-{uuid.uuid4().hex[:6]}{extension}"
            if target is not None:
                target = self.sessions.store_media(project, target, data, content_type, name)
                paths.append((target["media"][0]["path"], target["media"][0]["kind"]))
            else:
                path = f"{project['user_id']}/{project['id']}/generations/{uuid.uuid4().hex[:12]}-{name}"
                self.store.upload(LIBRARY_BUCKET, path, data, content_type)
                paths.append((path, content_type.split("/")[0]))
        if target is not None:
            turn.event("library", {"asset": self.sessions.kept_asset(target)})
        return target, [{"kind": kind, "path": path} for path, kind in paths], files

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
        looked: tuple[list[dict[str, Any]], dict[str, str]] | None,
    ) -> Result:
        """What a generation tool gives back: where the results went, for the model, and a line for the page.

        `looked` is what `pictured` made of the results where the model asked
        to look: the pictures, which lead the result, and why any is missing.
        """
        made = f"{len(media)} {noun}{'s' if len(media) != 1 else ''}"
        if target is None:
            kept = "Not saved to the library; generate again with save_to to keep a result."
        else:
            kept = f"Saved to {target['tag'] or target['name']} ({target['section']}) as its newest media."
        facts = {"model": endpoint, "saved_to": target and (target["tag"] or target["name"]), "seed": seed, "cost_usd": cost}
        summary = made + (f" saved to {target['tag'] or target['name']}" if target else "")
        pictures, missing = looked or ([], {})
        if looked is not None:
            facts["look"] = "The pictures above are yours to judge by, each after the line that names it."
            if missing:
                facts["no_picture"] = missing
        text = f"Generated {made}. {kept} The person sees the results in the conversation.\n{json.dumps(facts)}"
        return Result(
            [*pictures, {"type": "text", "text": text}] if pictures else text,
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
        look: bool = False,
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
        target, media, files = self.keep(turn, [image["url"] for image in output["images"]], target, stem)
        cost = generator.cost(endpoint, {"image": len(media), "unit": len(media)})
        return self.generated("image", endpoint, media, target, output.get("seed"), cost, self.pictured(files) if look else None)

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
        look: bool = False,
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
        target, media, files = self.keep(turn, [output["video"]["url"]], target, stem)
        units = {"video": 1.0}
        if duration_seconds:
            units["second"] = float(duration_seconds)
            units["1000 token"] = video_kilotokens(resolution, aspect_ratio, duration_seconds)
        cost = generator.cost(endpoint, units)
        return self.generated("video", endpoint, media, target, output.get("seed"), cost, self.pictured(files) if look else None)

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
            {
                **{key: engine[key] for key in ("id", "app", "tier", "status", "started_at", "queue_position")},
                "command_channel": self.sessions.launcher.has_channel(engine["app"]),
            }
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
        name = self.app_name(row["app"])
        shown = Shown({"kind": "image", "name": "screen.jpg"}, picture, "image/jpeg", "screen.jpg", {})
        self.show_preview(turn, engine_id, f"{name}'s screen", [shown], compare=False)
        return Result([self.picture_block(picture), {"type": "text", "text": f"{name}'s screen now."}], "Screenshot")

    @staticmethod
    def picture_block(picture: bytes) -> dict[str, Any]:
        """A JPEG as the model takes one in a tool's result."""
        return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(picture).decode()}}

    # Previews

    def show_preview(self, turn: Turn, engine_id: str, caption: str, files: list[Shown], compare: bool) -> None:
        """Store a preview's files under the project's `previews/` folder and put its card in the conversation.

        The event keeps each file's path in the bucket, which a reading of the
        log signs (`Sessions.shown_events`); nothing is written to the library.
        """
        items = []
        for shown in files:
            path = f"{turn.project['user_id']}/{turn.project_id}/{PREVIEWS}/{uuid.uuid4().hex[:12]}-{safe_name(shown.stored_as)}"
            self.store.upload(LIBRARY_BUCKET, path, shown.data, shown.content_type)
            items.append({**shown.item, "path": path})
        turn.event("preview", {"engine_id": engine_id, "caption": caption, "items": items, "compare": compare})

    def tool_preview(
        self,
        turn: Turn,
        engine_id: str,
        caption: str,
        path: str | None = None,
        paths: list[str] | None = None,
        kind: str | None = None,
        compare: bool = False,
        look: bool = False,
    ) -> Result:
        """Show files of the project's folder on an engine as one work-in-progress card (`preview`).

        Every file is prepared before any is stored, so a preview one of whose
        files is refused shows nothing rather than part of itself, and the
        copies the engine encoded are removed from it whatever happened.

        Raises:
            Refused: as `engine_sandbox` and `prepared` do, and 400 for no file, more files than a
                preview may show, or a pair that is not two files of one kind.
        """
        _, sandbox = self.engine_sandbox(turn, engine_id)
        config = self.sessions.config
        folder = project_folder(turn.project_id)
        chosen = [folder_path(given, folder) for given in ([path] if path else []) + (paths or [])]
        if not chosen or not all(chosen):
            raise Refused(400, "Name the file to show, or several, inside the project's folder.")
        if len(chosen) > config.preview_files:
            raise Refused(400, f"A preview shows at most {config.preview_files} files; show the ones that matter, or make two previews.")
        if compare and len(chosen) != 2:
            raise Refused(400, "A before and after pair is exactly two files: the one before, then the one after.")
        scratch = f"{PREVIEW_SCRATCH}/{uuid.uuid4().hex[:12]}"
        try:
            files = [self.prepared(sandbox, folder, inside, kind, f"{scratch}/{index}", look) for index, inside in enumerate(chosen)]
        finally:
            self.sessions.launcher.exec(sandbox, f"rm -rf {shlex.quote(scratch)}", EXEC_SECONDS)
        if compare and files[0].item["kind"] != files[1].item["kind"]:
            raise Refused(400, "A before and after pair is two files of one kind.")
        words = caption.strip()[:300]
        self.show_preview(turn, engine_id, words, files, compare)
        answer = {
            "shown": words,
            "files": [shown.facts for shown in files],
            "note": "The person sees this as a work-in-progress card in the conversation. "
            + (
                "The pictures above are yours to judge by: an image itself, four frames of a video, a sound's waveform."
                if look
                else "You were given the facts, not the media; call again with look: true only if you must judge it yourself."
            ),
        }
        pictures = [self.picture_block(shown.picture) for shown in files if shown.picture is not None]
        kinds = [shown.item["kind"] for shown in files]
        counted = ", ".join(f"{kinds.count(one)} {one}{'s' if kinds.count(one) != 1 else ''}" for one in dict.fromkeys(kinds))
        summary = f"Showed {counted}{' as before and after' if compare else ''}: {words}"
        text = json.dumps(answer)
        return Result([*pictures, {"type": "text", "text": text}] if pictures else text, summary[:200])

    def prepared(self, sandbox: str, folder: str, inside: str, kind: str | None, scratch: str, look: bool) -> Shown:
        """One file of a preview, read from the engine: itself, or the lighter copy the engine's ffmpeg encodes of it.

        The engine is asked what the file is (`probed`), and the file is shown
        as it is where a browser shows it and it is light
        (`plays_in_browser`, `Config.preview_original_bytes`). Otherwise the
        engine encodes a copy of its kind (`PREVIEW_ENCODINGS`) outside the
        project's folder, and that is what is read. An engine without ffmpeg
        cannot encode one: there the file is shown as it is, as a plain file
        where a browser would not play it, and its facts say so. Whatever is
        shown has to fit `Config.preview_limit_bytes`; the refusal tells the
        agent to render less, since how much to render is its choice.

        Raises:
            Refused: 404 for a path that is not there, 400 for a folder or a file that is not of
                the kind given, 413 for a preview over the limit, 422 where ffmpeg could not
                encode the copy.
        """
        launcher, config = self.sessions.launcher, self.sessions.config
        name = PurePosixPath(inside).name
        target = shlex.quote(f"./{inside}")
        script = "\n".join(
            [
                f"cd {shlex.quote(folder)} 2>/dev/null && [ -e {target} ] || exit {NO_SUCH_PATH}",
                f"[ -f {target} ] || exit {NOT_A_FILE}",
                f"stat -c %s {target}",
                f"command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1 || {{ echo {NO_FFMPEG}; exit 0; }}",
                f"ffprobe -v error -print_format json -show_entries {PROBE_ENTRIES} {target} 2>/dev/null || true",
            ]
        )
        status, output = launcher.exec(sandbox, script, EXEC_SECONDS)
        if status == NO_SUCH_PATH:
            raise Refused(404, f"There is no {inside} in the project's folder on this engine. Export or render it there first.")
        if status == NOT_A_FILE:
            raise Refused(400, f"{inside} is a folder; name the files in it to show.")
        if status != 0:
            raise RuntimeError(f"the probe stopped with status {status}: {output[-500:]}")
        size, probe = probed(output)
        chosen = kind or media_kind(name)
        plays = plays_in_browser(chosen, name, probe)
        # Whether this engine's ffmpeg reads the file as its kind, and so can measure it and encode a copy
        ffmpeg = probe is not None and bool(media_stream(probe, "audio" if chosen == "audio" else "video"))
        if chosen in MEDIA_KINDS and probe is not None and not ffmpeg and not plays:
            if kind is not None:
                raise Refused(400, f"{inside} is not {'an' if chosen[0] in 'aeiou' else 'a'} {chosen} file, as far as ffprobe reads it.")
            # Named like media, but ffprobe finds none in it and no browser would show it: the file it is
            chosen = "file"
        facts: dict[str, Any] = {"path": inside, "kind": chosen, "size": readable_size(size), **media_facts(chosen, probe or {})}
        item = {"kind": chosen, "name": name, **{key: facts[key] for key in ("seconds", "width", "height") if key in facts}}
        limit = config.preview_limit_bytes
        source = f"{folder}/{inside}"
        stored_as, content_type = name, mimetypes.guess_type(name)[0] or "application/octet-stream"
        heavy = chosen in MEDIA_KINDS and (not plays or size > config.preview_original_bytes)
        if heavy and ffmpeg:
            ending, content_type, encoding, arguments = PREVIEW_ENCODINGS[chosen]
            source = f"{scratch}{ending}"
            command = shlex.join(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", f"./{inside}", *arguments, source])
            status, output = launcher.exec(
                sandbox,
                f"cd {shlex.quote(folder)} && mkdir -p {shlex.quote(str(PurePosixPath(scratch).parent))} && {command} 2>&1 "
                f"&& stat -c %s {shlex.quote(source)}",
                EXEC_SECONDS,
            )
            if status != 0:
                raise Refused(422, f"ffmpeg could not encode a preview copy of {inside}: {output.strip()[-500:] or f'status {status}'}")
            size = int(output.strip().splitlines()[-1])
            stored_as = f"{PurePosixPath(name).stem}{ending}"
            facts["shown_as"] = f"{encoding} copy of {readable_size(size)}; the original is untouched"
        elif heavy:
            facts["note"] = (
                ("This engine has no ffmpeg" if probe is None else "This engine's ffmpeg does not read the file")
                + ", so no lighter copy was encoded and nothing was measured: it is shown as it is"
                + ("." if plays else ", as a file to open, since browsers do not play it.")
            )
            if not plays:
                item = {"kind": "file", "name": name}
        if size > limit:
            raise Refused(
                413,
                f"{inside} is {readable_size(size)} as a preview, over the {readable_size(limit)} a preview may be. Render "
                "or export something lighter and preview that: a shorter range, a lower resolution, or a lower bitrate. "
                "The file itself stays where it is.",
            )
        if chosen == "audio" and ffmpeg:
            _, heard = launcher.exec(
                sandbox,
                f"cd {shlex.quote(folder)} && ffmpeg -nostdin -hide_banner -nostats -i {target} -map 0:a:0 "
                "-af ebur128=peak=true:framelog=verbose -f null - 2>&1 | grep -E '^ +(I|Peak):'",
                EXEC_SECONDS,
            )
            facts.update(loudness(heard))
        try:
            data = launcher.read_file(sandbox, source, limit)
        except ValueError:
            raise Refused(413, f"{inside} grew past the {readable_size(limit)} a preview may be while it was read.") from None
        shown = Shown(item, data, content_type, stored_as, facts)
        if look and ffmpeg and chosen in MEDIA_KINDS:
            picture = f"{scratch}-look.jpg"
            command = shlex.join(
                ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", f"./{inside}", *look_arguments(chosen, facts.get("seconds", 0)), picture]
            )
            status, output = launcher.exec(
                sandbox,
                f"cd {shlex.quote(folder)} && mkdir -p {shlex.quote(str(PurePosixPath(scratch).parent))} && {command} 2>&1",
                EXEC_SECONDS,
            )
            if status == 0:
                shown.picture = launcher.read_file(sandbox, picture, LOOK_BYTES)
            else:
                facts["look"] = f"No picture could be made of it: {output.strip()[-300:]}"
        elif look:
            facts["look"] = "There is no picture of it to give: " + (
                "it is not an image, a video, or a sound." if chosen == "file" else "this engine's ffmpeg does not read it."
            )
        return shown

    # Interactive cards

    def tool_show_ui(
        self,
        turn: Turn,
        title: str,
        components: dict[str, Any] | None = None,
        html: str | None = None,
        submit: str | None = None,
        waits: bool = False,
        media: list[dict[str, Any]] | None = None,
        height: int | None = None,
    ) -> Result:
        """Show an interactive card (`ui`), checked against the catalog before any of its files is read (`genui.py`).

        A card's files are library entries' media, kept where they are in the bucket, and files
        an engine wrote in the project's folder, brought into the bucket the way a preview's are
        (`prepared`), under the project's `previews/` folder. What each file is has to be known to
        check the card, so it is read from the entry or from the file's name first, and an
        engine's files are fetched only once the card is valid: a card that is refused costs no
        upload. The event keeps each file's path, which a reading of the log signs
        (`Sessions.shown_events`). A card that waits ends the turn (`Result.ends_turn`).

        Raises:
            Refused: 400 with what to fix for a card the catalog does not allow, 404 for a tag no
                entry has, 409 for an entry with no file of the kind wanted, 422 for an engine's
                file a browser does not show as the kind the card needs, and as `engine_sandbox`
                and `prepared` do.
        """
        catalog = genui.catalog()
        folder = project_folder(turn.project_id)
        try:
            asked = genui.media_requests(catalog, media or [])
        except genui.Invalid as invalid:
            raise Refused(400, invalid.message) from None
        # Each file as the event names it; an engine's file has where it comes from in place of a path until it is stored
        files: list[dict[str, Any]] = []
        for request in asked:
            if request.tag is not None:
                (row,) = self.sessions.assets_by_tags(turn.project, [request.tag])
                kinds = [(genui.stored_kind(catalog, item), item) for item in row["media"]]
                wanted = request.kind or ("image" if any(kind == "image" for kind, _ in kinds) else None)
                found = next(((kind, item) for kind, item in kinds if wanted in (None, kind)), None)
                if found is None:
                    raise Refused(409, f"{row['tag']} has no {wanted or 'file'} yet. Generate or upload one first, or show another entry.")
                files.append({"name": request.name, "kind": found[0], "path": found[1]["path"]})
            else:
                _, sandbox = self.engine_sandbox(turn, request.engine_id or "")
                inside = folder_path(request.path or "", folder)
                named = catalog.kind_of(inside)
                kind = request.kind or (named if named != "file" else media_kind(inside))
                files.append({"name": request.name, "kind": kind, "from": (sandbox, inside)})
        try:
            data, inputs = genui.card(
                catalog, uuid.uuid4().hex[:12], title, components, html, submit, waits, height,
                {file["name"]: file["kind"] for file in files},
            )
        except genui.Invalid as invalid:
            raise Refused(400, invalid.message) from None
        scratch = f"{PREVIEW_SCRATCH}/{uuid.uuid4().hex[:12]}"
        engines = {file["from"][0] for file in files if "from" in file}
        try:
            for index, file in enumerate(files):
                if "from" not in file:
                    continue
                sandbox, inside = file.pop("from")
                shown = self.prepared(sandbox, folder, inside, file["kind"] if file["kind"] in MEDIA_KINDS else "file", f"{scratch}/{index}", False)
                if file["kind"] in MEDIA_KINDS and shown.item["kind"] != file["kind"]:
                    raise Refused(422, f"{inside} cannot be shown as {genui.article(file['kind'])} in a browser: {shown.facts.get('note', 'it is not one')}")
                file["path"] = f"{turn.project['user_id']}/{turn.project_id}/{PREVIEWS}/{uuid.uuid4().hex[:12]}-{safe_name(shown.stored_as)}"
                self.store.upload(LIBRARY_BUCKET, file["path"], shown.data, shown.content_type)
        finally:
            for sandbox in engines:
                self.sessions.launcher.exec(sandbox, f"rm -rf {shlex.quote(scratch)}", EXEC_SECONDS)
        turn.event("ui", {**data, "media": files})
        ends = bool(waits)
        if data["submit"] is None:
            note = "The person sees the card in the conversation. It has no lock-in button, so nothing comes back from it."
        elif ends:
            note = (
                "The person sees the card in the conversation. Your turn ends here: when they lock it in, their next "
                "message carries what they chose, and you go on from it."
            )
        else:
            note = (
                "The person sees the card in the conversation and may lock it in whenever they like; what they chose then "
                "arrives in a message of theirs. Go on meanwhile."
            )
        answer = {"shown": data["title"], "ui_id": data["ui_id"], "kind": data["kind"], "files": [file["name"] for file in files], "note": note}
        if data["kind"] == genui.KINDS[0]:
            answer["answers_with"] = {given: f"{component}: {catalog.components[component]['input']}" for given, component in inputs.items()}
        return Result(json.dumps(answer), f"Showed {data['title']}"[:200], ends_turn=ends)

    def tool_engine_exec(self, turn: Turn, engine_id: str, command: str) -> Result:
        _, sandbox = self.engine_sandbox(turn, engine_id)
        status, output = self.sessions.launcher.exec(sandbox, command, EXEC_SECONDS)
        shown = output if len(output) <= OUTPUT_LIMIT else f"[the first {len(output) - OUTPUT_LIMIT} characters left out]\n{output[-OUTPUT_LIMIT:]}"
        return Result(f"exit status {status}\n{shown}", f"Exit status {status}", ok=status == 0)

    def tool_engine_show(self, turn: Turn, engine_id: str, stream: str = DESKTOP) -> Result:
        row, _ = self.engine_sandbox(turn, engine_id)
        name = self.app_name(row["app"])
        if stream not in (DESKTOP, *STREAMS.get(row["app"], ())):
            raise Refused(400, f"{name} streams its desktop only.")
        self.show_on_screen(turn, engine_id, stream)
        return Result(f"The person's Screen panel shows {name}'s {stream} view now.", f"{stream} on the screen")

    @staticmethod
    def show_on_screen(turn: Turn, engine_id: str, stream: str) -> None:
        """Have the studio put an engine, in one of its pictures, on the person's screen."""
        turn.event("screen", {"engine_id": engine_id, "stream": stream})

    def tool_engine_import(self, turn: Turn, engine_id: str, tags: list[str]) -> Result:
        _, sandbox = self.engine_sandbox(turn, engine_id)
        rows = self.sessions.assets_by_tags(turn.project, tags)
        links = self.sessions.links(rows)
        folder = f"{project_folder(turn.project_id)}/library"
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

    def channel_call(
        self, turn: Turn, engine_id: str, method: str, params: dict[str, Any] | None, only: str | None = None
    ) -> Result:
        """Call the command channel of the engine's app, or of `only` that app where a tool is one app's own.

        Raises:
            Refused: as `engine_sandbox` does, and 409 for an engine of another app than `only`, or
                one whose app has no command channel, saying how such an engine is driven.
        """
        row, sandbox = self.engine_sandbox(turn, engine_id)
        name = self.app_name(row["app"])
        if only is not None and row["app"] != only:
            raise Refused(409, f"That engine is not {self.app_name(only)}.")
        if not self.sessions.launcher.has_channel(row["app"]):
            raise Refused(
                409,
                f"This engine has no command channel: {name} is driven with engine_exec, or by the person on its "
                "screen (engine_show).",
            )
        answer = self.sessions.launcher.engine_call(sandbox, row["app"], method, params)
        text = json.dumps(answer)
        return Result(text if len(text) <= OUTPUT_LIMIT else text[:OUTPUT_LIMIT] + " [cut]", f"{name}: {method} done")

    def tool_engine_call(self, turn: Turn, engine_id: str, method: str, params: dict[str, Any] | None = None) -> Result:
        return self.channel_call(turn, engine_id, method, params)

    def tool_filmcraft(self, turn: Turn, engine_id: str, method: str, params: dict[str, Any] | None = None) -> Result:
        return self.channel_call(turn, engine_id, method, params, only="filmcraft")

    def tool_engine_files(self, turn: Turn, engine_id: str, path: str = "") -> Result:
        """List the project's folder, or a path inside it, on the engine's machine.

        The machine is asked rather than the workspace Volume read from here: what an engine has
        written is on its own mount first, and what the agent has to know is whether the engine it
        is about to tell to open a file can see it.

        Raises:
            Refused: as `engine_sandbox` does, 400 for a path outside the folder, 404 for one not there.
        """
        _, sandbox = self.engine_sandbox(turn, engine_id)
        folder = project_folder(turn.project_id)
        inside = folder_path(path, folder)
        # From ./, so a name that starts with a dash is never an option
        target = shlex.quote(f"./{inside}")
        script = "\n".join(
            [
                f"cd {shlex.quote(folder)} 2>/dev/null && [ -e {target} ] || exit {NO_SUCH_PATH}",
                f"if [ -d {target} ]; then find {target} -mindepth 1 -maxdepth 1 -printf '{FILES_FORMAT}'",
                f"else find {target} -maxdepth 0 -printf '{FILES_FORMAT}'; fi",
            ]
        )
        status, output = self.sessions.launcher.exec(sandbox, script, EXEC_SECONDS)
        where = inside or "the project folder"
        if status == NO_SUCH_PATH:
            raise Refused(
                404,
                f"There is no {inside} in the project's folder on this engine."
                if inside
                else f"The project's folder, {folder}, is not on this engine.",
            )
        if status != 0:
            raise RuntimeError(f"the listing stopped with status {status}: {output[-500:]}")
        found = sorted(filter(None, map(listed_file, output.splitlines())), key=lambda entry: entry["name"])
        listing: dict[str, Any] = {"folder": folder, "path": inside, "entries": found[:FILES_LIMIT]}
        if len(found) > FILES_LIMIT:
            listing["more"] = len(found) - FILES_LIMIT
        return Result(json.dumps(listing), f"{len(found)} entr{'y' if len(found) == 1 else 'ies'} in {where}")

    def tool_engine_send(
        self, turn: Turn, from_engine_id: str, path: str, to_engine_id: str, to_path: str | None = None
    ) -> Result:
        """Carry a file or a folder of the project's folder from one running engine of the project to another.

        Both engines are found through the project, so neither can be another
        project's or another user's. What is sent is measured on the sending
        engine first and refused over `Config.transfer_limit_bytes`, before a
        byte moves. The launcher carries it (`Launcher.send`), asking between
        pieces whether the turn still runs, and the receiving engine is then
        asked for the entry, which is what the agent is told: the proof that
        the engine about to open the file has it.

        Raises:
            Refused: as `engine_sandbox` does for either engine, 400 for one engine named twice or
                a path outside the folder, 404 for nothing at the path, 413 over the limit.
        """
        sender, source = self.engine_sandbox(turn, from_engine_id)
        receiver, target = self.engine_sandbox(turn, to_engine_id)
        if source == target:
            raise Refused(400, "That is one engine, which already has the file; name the engine that should receive it.")
        folder = project_folder(turn.project_id)
        inside = folder_path(path, folder)
        there = folder_path(to_path, folder) if to_path else inside
        if not inside or not there:
            raise Refused(400, "Name a file or a folder inside the project's folder, not the folder itself.")
        launcher = self.sessions.launcher
        quoted = shlex.quote(f"./{inside}")
        status, output = launcher.exec(
            source,
            f"cd {shlex.quote(folder)} 2>/dev/null && [ -e {quoted} ] || exit {NO_SUCH_PATH}\n"
            f"if [ -d {quoted} ]; then du -sb {quoted} | cut -f1; else stat -c %s {quoted}; fi",
            EXEC_SECONDS,
        )
        sending, receiving = self.app_name(sender["app"]), self.app_name(receiver["app"])
        if status == NO_SUCH_PATH:
            raise Refused(404, f"There is no {inside} in the project's folder on the {sending} engine.")
        try:
            size = int(output.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise RuntimeError(f"measuring {inside} stopped with status {status}: {output[-500:]}") from None
        limit = self.sessions.config.transfer_limit_bytes
        if size > limit:
            raise Refused(
                413,
                f"{inside} is {readable_size(size)}, over the {readable_size(limit)} that passes between running engines. "
                f"Send only what {receiving} needs, or a lighter export; or stop the {receiving} engine and start it "
                "again, since an engine opens on everything the project's folder holds when it starts.",
            )
        started = time.monotonic()
        try:
            carried = launcher.send(source, f"{folder}/{inside}", target, f"{folder}/{there}", turn.alive)
        except FileNotFoundError:
            raise Refused(404, f"There is no {inside} in the project's folder on the {sending} engine.") from None
        except InterruptedError:
            raise TurnStopped() from None
        seconds = round(time.monotonic() - started, 1)
        arrived = shlex.quote(f"./{there}")
        status, output = launcher.exec(
            target, f"cd {shlex.quote(folder)} && find {arrived} -maxdepth 0 -printf '{FILES_FORMAT}'", EXEC_SECONDS
        )
        entry = next(filter(None, map(listed_file, output.splitlines())), None)
        if status != 0 or entry is None:
            raise RuntimeError(f"{there} is not on the {receiving} engine after the transfer: {output[-500:]}")
        answer = {
            "sent": inside,
            "from": {"engine_id": from_engine_id, "app": sender["app"]},
            "to": {"engine_id": to_engine_id, "app": receiver["app"], "path": there},
            "bytes": carried,
            "seconds": seconds,
            "entry": {**entry, "name": there},
            "note": f"{receiving} has it at {folder}/{there} now, and it is on the project's storage for any engine "
            "started later. Open it there by that path.",
        }
        return Result(json.dumps(answer), f"{PurePosixPath(inside).name} is in {receiving}'s folder: {readable_size(size)} in {seconds:g} s")

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

    def tool_unreal_projects(self, turn: Turn, engine_id: str) -> Result:
        found = self.sessions.unreal_projects(turn.user, turn.project_id, engine_id)
        version = self.sessions.catalog.apps["unreal"]["version"]
        notes = [
            "Tell the person what you found in each: the version against this engine's and what `opens` says, C++ "
            "modules (compiled for Linux before the editor opens, the first build the longest) or Blueprints only, "
            "the plugins, and Git LFS. Then offer to open it with unreal_open.",
        ]
        if not found:
            notes = [
                "No .uproject in the workspace yet. An Unreal engine of a project linked to the game's repository "
                "clones it as it starts; otherwise the person links the repository in the Environment panel and "
                "starts Unreal again, clones it in the Desktop view's GitHub client into the project's folder, or "
                "starts a new one from a template.",
            ]
        answer = {"engine_id": engine_id, "engine_version": version, "projects": found, "notes": notes}
        summary = ", ".join(
            f"{project['name']} ({project['engine_association'] or 'no version'}"
            f"{', C++' if project['cpp_modules'] else ''})"
            for project in found
        )
        return Result(json.dumps(answer), (summary or "No Unreal project yet")[:200])

    def tool_unreal_open(self, turn: Turn, engine_id: str, path: str) -> Result:
        row = self.sessions.running_unreal(turn.user, turn.project_id, engine_id)
        where = path.strip()
        if not where.lower().endswith(".uproject") or any(character in where for character in "\0\r\n"):
            raise Refused(400, "Name the project's .uproject file, as unreal_projects gives it.")
        found = next(
            (project for project in self.sessions.unreal_projects(turn.user, turn.project_id, engine_id) if project["path"] == where),
            None,
        )
        if found is None:
            raise Refused(404, f"The engine's workspace has no {where}; unreal_projects lists the projects it has.")
        if found["version"] == "newer":
            raise Refused(409, found["opens"])
        launcher = self.sessions.launcher
        branch = None
        if found["version"] != "same":
            branch = self.agent_branch_in_clone(turn, row["sandbox_id"], where)
        status, output = launcher.exec(row["sandbox_id"], f"selkies-modal-unreal-open {shlex.quote(where)}", EXEC_SECONDS)
        said = output.strip()[-1500:] or f"exit status {status}"
        if status != 0:
            licensed, advice = self.sessions.editor_license(turn.user.id)
            if not licensed:
                return Result(
                    f"The editor did not open: {said}\n\n{advice} Then stop this Unreal engine and start it again: a "
                    "start on a linked account brings the person's own copy of the editor. Tell the person this one "
                    "step plainly; the desktop and everything in the workspace stay as they are.",
                    "The Unreal Editor needs the Epic link",
                    ok=False,
                )
            return Result(
                f"The editor did not open: {said}\n\nIf it says the editor is not installed, this engine started "
                "before the person's Epic link was in place: stop it and start Unreal again, which brings their own "
                "copy of the editor.",
                "The Unreal Editor did not open",
                ok=False,
            )
        self.show_on_screen(turn, engine_id, UNREAL_VIEW)
        notes = [found["opens"], "The person's screen is on the Unreal view, which shows a placeholder until the editor streams."]
        if branch:
            notes.append(f"The clone is on {branch}, the agent's branch, so what the editor upgrades stays off the team's branches.")
        if found["cpp_modules"]:
            notes.append(
                "Its C++ modules compile for Linux before the editor opens, the first build the longest; where code "
                "written for an older engine fails, show the errors and fix them on the agent's branch."
            )
        answer = {"opened": where, "branch": branch, "screen": UNREAL_VIEW, "output": said, "notes": notes}
        return Result(json.dumps(answer), f"{found['name']} is opening in Unreal")

    def agent_branch_in_clone(self, turn: Turn, sandbox: str, uproject: str) -> str | None:
        """Put the clone a `.uproject` is in on the agent's branch, made from where it stands; returns the branch.

        Nothing is committed or pushed: the branch is the clone's, so what the editor upgrades when
        it saves stays off the branch the developer cloned. A project outside any clone (a new one
        from a template) has no branch, and nothing.

        Raises:
            Refused: 409 where the clone cannot switch, such as to an existing branch it has changes against.
        """
        branch = agent_branch(turn.project)
        # The machine may name a project by its path in the workspace rather than from the root
        folder = shlex.quote(str((PurePosixPath(WORKSPACE) / uproject).parent))
        quoted = shlex.quote(branch)
        script = "\n".join(
            [
                "set -e",
                f"cd {folder}",
                "git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0",
                f'if [ "$(git branch --show-current)" != {quoted} ]; then',
                f"  git switch -q {quoted} 2>/dev/null || git switch -q -c {quoted}",
                "fi",
                'echo "branch=$(git branch --show-current)"',
            ]
        )
        status, output = self.sessions.launcher.exec(sandbox, script, EXEC_SECONDS)
        if status != 0:
            raise Refused(409, f"The clone could not be put on {branch}, so nothing was opened: {output.strip()[-500:]}")
        return next((line[len("branch=") :] for line in output.splitlines() if line.startswith("branch=")), None)
