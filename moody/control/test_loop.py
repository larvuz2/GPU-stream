# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The agent's turns on the real loop, with only the model scripted.

Every turn here runs the Claude Agent SDK as it ships: its client, the
`claude` program it bundles as a child process, the in-process server Moody's
tools are served from, the loop's own hooks and permission callback, and its
session store over the in-memory database of `test_api.py`. The one stand-in
is the Anthropic API (`scripted_api.py`), which the program is pointed at.
So what is held here is what `test_api.py` cannot hold with its stand-in for
the whole SDK: that the real program does with Moody's configuration what the
agent counts on.

- Moody's tools run, and the program's own file and shell tools are not
  offered to the model at all.
- The program's process has the Anthropic key and the turn's directories in
  its environment and nothing else of the process that started it.
- A subagent's steps reach the conversation, each marked as its own.
- A session resumes in a process that has nothing of the first but the
  database's rows.
- A question ends the turn and leaves no process behind.
- A step the person approves waits for their answer, and for no longer than
  configured.
- Stopping a turn interrupts the program while it is answering.
- A skill is loaded when it is opened, with its reference file, and nothing
  else of the machine can be read.
- A deploy that changes the prompt or a tool reaches the next turn of a
  session that began before it.
- The pictures a tool hands over reach the model as pictures.
- A turn stops at its person's own limit of steps or of spending, and says
  which.
- A project that was asked its kind begins its first turn knowing it.

The tests are skipped, with the reason, where the bundled program is not
there or does not start (an install of the SDK for another platform). Run as
a program, this file is one turn of the test that resumes a session in a
fresh process.
"""

from __future__ import annotations

import base64
import json
import os
import pickle
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent import SPECS, TOOL_NAMES, Agent
from api import create_app
from definitions import operators, read_agents, read_skills
from loop import PREFIX, bundled_cli, sdk_loop
from scripted_api import ScriptedAPI, system_text
from scripted_loop import Reply
from service import Sessions
from test_api import (
    ALICE,
    CATALOG,
    FakeFal,
    FakeGitHub,
    FakeLauncher,
    FakeStore,
    InlineJobs,
    answering,
    auth,
    config,
    events,
    jpeg_size,
    kinds,
    looks,
    message,
    new_project,
    reply,
    say,
    start_engine,
    tools_shown,
    use,
    with_config,
    write_definitions,
)

# What a request's system prompt contains, by whose it is
AGENT, RESEARCH, OPERATOR = (
    "You are the Moody agent",
    "RESEARCH-PROMPT",
    "OPERATOR-PROMPT",
)
# The program's own tools the agent keeps, as the Messages API is given them
KEPT = ["Agent", "Read", "Skill", "WebFetch", "WebSearch"]


def program() -> str | None:
    """Why the loop's program cannot run here, or nothing where it can."""
    try:
        path = bundled_cli()
        ran = subprocess.run(
            [path, "--version"],
            env={"PATH": os.defpath, "HOME": "/nonexistent"},
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        return f"the Claude Agent SDK's bundled program does not start here: {error}"
    return (
        None
        if ran.returncode == 0
        else f"the Claude Agent SDK's bundled program exits with {ran.returncode}: {ran.stderr[:200]}"
    )


UNRUNNABLE = program()
pytestmark = [
    pytest.mark.skipif(UNRUNNABLE is not None, reason=UNRUNNABLE or ""),
    # pytest resets the filter `loop` installs for the warning its module explains
    pytest.mark.filterwarnings("ignore::claude_agent_sdk.CanUseToolShadowedWarning"),
]


def backend(
    folder: Path,
    api_url: str,
    store: FakeStore | None = None,
    loop_root: Path | None = None,
    key: str = "sk-ant-scripted",
) -> SimpleNamespace:
    """The Studio's backend on the real loop: the stand-ins of `test_api.py` for everything but the SDK.

    `api_url` is where the loop's program reaches the Messages API, empty for
    Anthropic's own, which `key` is then a real key for (`trial.py`).
    """
    skills_folder, agents_folder = write_definitions(folder)
    store, launcher, jobs, github, fal = (
        store or FakeStore(),
        FakeLauncher(),
        InlineJobs(),
        FakeGitHub(),
        FakeFal(),
    )
    settings = config(
        anthropic_key=key,
        anthropic_base_url=api_url,
        fal_key="fal-test",
        loop_root=str(loop_root or folder / "loop"),
        approval_seconds=20,
        turn_budget_usd=5.0,
        turn_limit=30,
    )
    sessions = Sessions(settings, CATALOG, store, launcher, jobs, github)
    jobs.sessions = sessions
    skills, agents = read_skills(skills_folder), read_agents(agents_folder)
    derived = operators(agents_folder, CATALOG, skills)
    agent = Agent(sessions, sdk_loop, fal, skills, agents, derived)
    agent.heartbeat_seconds = 0.2
    agent.approval_poll_seconds = 0.05
    jobs.agent = agent
    app = create_app(sessions, settings, CATALOG, skills, agents, derived)
    return SimpleNamespace(
        app=app,
        sessions=sessions,
        store=store,
        launcher=launcher,
        jobs=jobs,
        github=github,
        fal=fal,
        agent=agent,
        tmp=folder,
    )


@pytest.fixture
def studio(tmp_path: Path) -> SimpleNamespace:
    """The backend with the real loop, and the scripted API its program asks."""
    api = ScriptedAPI()
    made = backend(tmp_path, api.url)
    with TestClient(made.app) as client:
        made.client, made.model = client, api
        yield made
    api.close()
    assert not api.ran_dry, "a turn asked the model for more than the test scripted"
    assert api.others == [], "the program asked the API for something beside messages"
    assert not children(), "a turn left a process behind"


def children() -> list[int]:
    """The processes this one has started that are still running: the loop's program, while a turn runs."""
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            fields = Path(f"/proc/{entry}/stat").read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if int(fields[1]) == os.getpid() and fields[0] != "Z":
            found.append(int(entry))
    return found


def environment(pid: int) -> dict[str, str]:
    """The environment a process was started with."""
    raw = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    return dict(item.decode().split("=", 1) for item in raw if item)


def results(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The tool results the newest user message of a request carries, by call, each with its text as one string."""
    user = next(
        m
        for m in reversed(body["messages"])
        if m["role"] == "user" and isinstance(m["content"], list)
    )
    found = {}
    for block in user["content"]:
        if block["type"] == "tool_result":
            content = block["content"]
            text = (
                content
                if isinstance(content, str)
                else "".join(part.get("text", "") for part in content)
            )
            found[block["tool_use_id"]] = {**block, "text": text}
    return found


def spoken(body: dict[str, Any]) -> str:
    """Everything a request's conversation says, as one text."""
    return json.dumps(body["messages"])


def messages(body: dict[str, Any]) -> list[str]:
    """What the person said in a request's conversation, in order: the text each turn's project state follows.

    The program puts a turn's message after the results the turn before left
    unanswered, in one message, so an answer to a question directly follows
    the question's own result.
    """
    found = []
    for entry in body["messages"]:
        blocks = (
            entry["content"]
            if entry["role"] == "user" and isinstance(entry["content"], list)
            else []
        )
        for before, after in zip(blocks, blocks[1:]):
            if (
                before["type"] == "text"
                and after["type"] == "text"
                and after["text"].startswith("<project_state>")
            ):
                found.append(before["text"])
    return found


def test_a_turn_runs_moodys_tools_and_the_model_is_offered_none_of_the_programs_file_or_shell_tools(
    studio, monkeypatch
):
    client, model = studio.client, studio.model
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_never")
    monkeypatch.setenv("MOODY_SECRET_KEY", "seals-never")
    film = new_project(client)
    private = studio.tmp / "private.txt"
    private.write_text("NEVER-ATTACHED-7391")
    upsert = use(
        "library_upsert",
        section="Characters",
        name="Mara",
        tag="@mara",
        description="A lighthouse keeper",
    )
    plan = use(
        "update_plan", items=[{"id": "bible", "title": "Bible", "status": "active"}]
    )
    seen: dict[str, Any] = {}

    def after_the_tools(body: dict[str, Any]) -> Reply:
        (child,) = children()
        seen.update(
            environment=environment(child),
            command=Path(f"/proc/{child}/cmdline")
            .read_bytes()
            .split(b"\0")[0]
            .decode(),
        )
        return reply(say("Mara is in the library."))

    model.script(
        AGENT,
        reply(
            {"type": "thinking", "thinking": "Start with the bible.", "signature": ""},
            say("Setting up the library."),
            upsert,
            plan,
        ),
        after_the_tools,
    )
    assert (
        message(
            client, film["id"], f"Make a film about Mara. See @{private} and /compact"
        ).status_code
        == 202
    )

    log = events(client, film["id"])
    assert log["running"] is False
    assert [e["kind"] for e in log["events"]] == [
        "user_message",
        "thinking",
        "text",
        "tool_start",
        "library",
        "tool_end",
        "tool_start",
        "plan",
        "tool_end",
        "text",
        "usage",
        "turn_end",
    ]
    assert [(title, ok) for title, _, ok in tools_shown(client, film["id"])] == [
        ("Saving @mara to the library", True),
        ("Updating the plan", True),
    ]
    library = client.get(
        f"/v1/projects/{film['id']}/library", headers=auth("alice-token")
    ).json()
    assert [asset["tag"] for asset in library["assets"]] == ["@mara"]
    usage = next(e["data"] for e in log["events"] if e["kind"] == "usage")
    assert (
        usage["input_tokens"] == 200
        and usage["output_tokens"] == 40
        and usage["cost_usd"] > 0
        and usage["agents"] == 0
    )

    first, second = model.asked(AGENT)
    offered = [tool["name"] for tool in first["tools"]]
    assert offered == [*KEPT, *sorted(f"{PREFIX}{name}" for name in TOOL_NAMES)], (
        "Moody's tools, and of the program's own only these"
    )
    assert not {"Bash", "Write", "Edit", "Glob", "Grep", "NotebookEdit"} & set(offered)
    assert first["model"] == "claude-fable-5-2" and first["thinking"] == {
        "type": "adaptive",
        "display": "summarized",
    }
    assert first["output_config"] == {"effort": "high"} and first["stream"] is True
    served = {tool["name"]: tool for tool in first["tools"]}
    assert (
        "Start an engine for this project"
        in served[f"{PREFIX}engine_start"]["description"]
    )
    assert served[f"{PREFIX}engine_start"]["input_schema"]["required"] == [
        "app",
        "tier",
    ]
    words, state = first["messages"][0]["content"]
    assert words["text"] == f"Make a film about Mara. See @{private} and /compact", (
        "the person's words are sent as they wrote them"
    )
    assert state["text"].startswith(
        "<project_state>\nThe project's state at the start of this turn:"
    )
    assert "NEVER-ATTACHED-7391" not in spoken(first) + spoken(second), (
        "a path in a message is not a file the program attaches"
    )
    assert "Moody agent" in system_text(
        first
    ) and "FILMCRAFT-SKILL-TEXT" not in system_text(first) + spoken(first)
    told = results(second)
    assert (
        json.loads(told[upsert["id"]]["text"])["tag"] == "@mara"
        and told[plan["id"]]["text"] == "The plan is updated."
    )

    # The program's process: the key, the turn's own directories, the loop's switches, and nothing of this process
    child = seen["environment"]
    assert seen["command"] == bundled_cli()
    assert (
        child["ANTHROPIC_API_KEY"] == "sk-ant-scripted"
        and child["ANTHROPIC_BASE_URL"] == model.url
    )
    assert sorted(child) == sorted(
        [
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_BASE_URL",
            "HOME",
            "TMPDIR",
            "PATH",
            "PWD",
            "CLAUDE_CONFIG_DIR",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
            "CLAUDE_CODE_DISABLE_CLAUDE_MDS",
            "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS",
            "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS",
            "ENABLE_TOOL_SEARCH",
            "CLAUDE_CODE_ENTRYPOINT",
            "CLAUDE_AGENT_SDK_VERSION",
            "CLAUDE_CODE_SDK_READS_SESSION_STATE",
        ]
    ), "every variable the program has is one the turn named"
    assert child["PWD"] == str(studio.tmp / "loop" / film["id"]) and child[
        "HOME"
    ] != os.environ.get("HOME")
    assert not Path(child["HOME"]).exists() and not Path(child["PWD"]).exists(), (
        "the turn's directories are gone with it"
    )

    # The conversation is in the database as the program wrote it, and nowhere else
    session = studio.store.tables["projects"][film["id"]]["agent_session"]
    rows = [
        row
        for row in studio.store.tables["agent_transcripts"].values()
        if row["session_id"] == session
    ]
    assert [
        row["entry"]["type"]
        for row in rows
        if row["entry"]["type"] in ("user", "assistant")
    ][:2] == ["user", "assistant"]
    assert "Mara is in the library." in json.dumps([row["entry"] for row in rows])


def test_a_subagents_steps_show_in_the_conversation_each_marked_as_its_own(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    films = use(
        "Agent",
        subagent_type="research",
        description="Find lighthouse films",
        prompt="Find three films set in lighthouses.",
    )
    survey = use(
        "Agent",
        subagent_type="research",
        description="Survey the library",
        prompt="List what the library holds.",
    )
    listing = use("library_list")

    def research(body: dict[str, Any]) -> Reply:
        job = spoken(body)
        if "REPORT" in job or '"tool_result"' in job:
            return reply(
                say(
                    "REPORT: the library is empty."
                    if "library holds" in job
                    else "REPORT: three films."
                )
            )
        if "library holds" in job:
            return reply(
                {"type": "thinking", "thinking": "Look first.", "signature": ""},
                say("Reading the library."),
                listing,
            )
        return reply(say("REPORT: three films."))

    model.script(
        AGENT, reply(say("Two jobs out."), films, survey), reply(say("Both are back."))
    )
    model.script(RESEARCH, research, research, research)
    assert message(client, film["id"], "Research lighthouses").status_code == 202

    log = events(client, film["id"])["events"]
    cards = [e["data"] for e in log if e["kind"] == "agent"]
    by_task = {card["task"]: card["agent_id"] for card in cards}
    assert (
        set(by_task) == {"Find lighthouse films", "Survey the library"}
        and len(set(by_task.values())) == 2
    )
    assert len({card["group"] for card in cards}) == 1, (
        "the two subagents were started by one step"
    )
    assert all(
        (card["name"], card["title"]) == ("research", "Research agent")
        for card in cards
    )
    surveyor = by_task["Survey the library"]
    states = [
        (card["state"], card["activity"], card["detail"])
        for card in cards
        if card["agent_id"] == surveyor
    ]
    assert states[0] == ("working", "thinking", "") and states[-1][:2] == (
        "completed",
        "satisfied",
    )
    assert ("working", "searching", "Reading the library") in states, (
        "the card follows the tool the subagent runs"
    )
    last = [card for card in cards if card["agent_id"] == surveyor][-1]
    assert last["tokens"] > 0 and last["seconds"] >= 0

    theirs = [
        (
            e["kind"],
            e["data"].get("text") or e["data"].get("tool") or e["data"].get("ok"),
        )
        for e in log
        if e["data"].get("agent_id") == surveyor and e["kind"] != "agent"
    ]
    assert theirs == [
        ("thinking", "Look first."),
        ("text", "Reading the library."),
        ("tool_start", "library_list"),
        ("tool_end", True),
        ("text", "REPORT: the library is empty."),
    ]
    own = [
        e["data"]["text"]
        for e in log
        if e["kind"] == "text" and "agent_id" not in e["data"]
    ]
    assert own == ["Two jobs out.", "Both are back."]
    assert next(e["data"] for e in log if e["kind"] == "usage")["agents"] == 2

    asked = model.asked(RESEARCH)
    assert len(asked) == 3 and {body["model"] for body in asked} == {
        "claude-sonnet-5-5"
    }, "a subagent runs on its tier's model"
    assert sorted(tool["name"] for tool in asked[0]["tools"]) == [
        "WebFetch",
        "WebSearch",
        f"{PREFIX}library_list",
        f"{PREFIX}library_upsert",
    ]
    assert "You research. RESEARCH-PROMPT" in system_text(
        asked[0]
    ) and "Your last message is your report" in system_text(asked[0])
    assert "Two jobs out." not in spoken(asked[0]), (
        "a subagent knows nothing of the conversation that handed it its job"
    )
    back = results(model.asked(AGENT)[-1])
    assert (
        "REPORT: three films." in back[films["id"]]["text"]
        and "REPORT: the library is empty." in back[survey["id"]]["text"]
    )
    assert "Reading the library." not in spoken(model.asked(AGENT)[-1]), (
        "only a subagent's report returns to the agent"
    )
    kept = {row["subpath"] for row in studio.store.tables["agent_transcripts"].values()}
    assert kept == {
        "",
        *(f"subagents/agent-{agent_id}" for agent_id in by_task.values()),
    }


def test_a_question_ends_the_turn_and_holds_no_process_and_the_answer_resumes_the_session(
    studio,
):
    client, model = studio.client, studio.model
    film = new_project(client)
    question = use(
        "ask_user",
        question="Color or black and white?",
        options=["Color", "Black and white"],
        recommended="Black and white",
    )
    model.script(AGENT, reply(say("One thing first."), question))
    began = time.monotonic()
    assert message(client, film["id"], "Make a film about Mara").status_code == 202
    assert time.monotonic() - began < 60 and children() == [], (
        "the turn is over and its process gone while the question waits"
    )
    log = events(client, film["id"])
    assert log["running"] is False and len(model.asked(AGENT)) == 1, (
        "the model is not asked again until the person answers"
    )
    assert [e["kind"] for e in log["events"]] == [
        "user_message",
        "text",
        "tool_start",
        "ask",
        "tool_end",
        "usage",
        "turn_end",
    ]
    assert next(e["data"] for e in log["events"] if e["kind"] == "ask") == {
        "question": "Color or black and white?",
        "options": ["Color", "Black and white"],
        "recommended": "Black and white",
    }
    assert not any(e["kind"] == "error" for e in log["events"])

    model.script(AGENT, reply(say("Black and white it is.")))
    message(client, film["id"], "Black and white")
    resumed = model.asked(AGENT)[-1]
    assert "One thing first." in spoken(
        resumed
    ) and "The question is with the person now" in spoken(resumed)
    assert messages(resumed) == ["Make a film about Mara", "Black and white"], (
        "the answer is the next message of the same conversation"
    )
    answer = resumed["messages"][-2]["content"]
    assert [block["type"] for block in answer] == [
        "tool_result",
        "text",
        "text",
    ] and answer[0]["tool_use_id"] == question["id"], (
        "and follows the question's own result"
    )
    assert kinds(client, film["id"])[-3:] == ["text", "usage", "turn_end"]


def test_a_deploy_that_changes_the_prompt_or_a_tool_reaches_the_next_turn_of_a_session_begun_before_it(
    studio, monkeypatch
):
    client, model = studio.client, studio.model
    film = new_project(client)
    model.script(AGENT, reply(say("One.")))
    message(client, film["id"], "First")
    before = model.asked(AGENT)[-1]
    plan = f"{PREFIX}update_plan"
    assert "`t4`" in system_text(before)

    with_config(studio, tiers=frozenset({"cpu"}))
    monkeypatch.setitem(
        SPECS["update_plan"],
        "description",
        SPECS["update_plan"]["description"] + " DEPLOYED-DESCRIPTION",
    )
    schema = SPECS["engine_stop"]["input_schema"]
    monkeypatch.setitem(
        SPECS["engine_stop"],
        "input_schema",
        {
            **schema,
            "properties": {**schema["properties"], "deployed": {"type": "string"}},
        },
    )
    model.script(AGENT, reply(say("Two.")))
    message(client, film["id"], "Second")
    after = model.asked(AGENT)[-1]
    tools = {tool["name"]: tool for tool in after["tools"]}
    assert messages(after) == ["First", "Second"], "the session is the same one"
    assert "`t4`" not in system_text(after), (
        "the prompt is the one the code that runs the turn builds"
    )
    assert "DEPLOYED-DESCRIPTION" in tools[plan]["description"]
    assert "deployed" in tools[f"{PREFIX}engine_stop"]["input_schema"]["properties"]
    assert (
        "DEPLOYED-DESCRIPTION"
        not in {tool["name"]: tool for tool in before["tools"]}[plan]["description"]
    )


@looks
def test_the_pictures_the_agent_asks_to_look_at_reach_the_model_as_pictures(
    studio, media
):
    client, model = studio.client, studio.model
    studio.fal.files = media
    film = new_project(client)
    call = use("generate_image", prompt="A lamp, two ways", count=2, look=True)
    model.script(AGENT, reply(call), reply(say("Seen.")))
    message(client, film["id"], "A lamp")
    content = results(model.asked(AGENT)[1])[call["id"]]["content"]
    # The program keeps each picture as a file of its own, in the turn's private directory, and says where
    kept = [
        part
        for part in content
        if part["type"] == "text" and part["text"].startswith("[Image: source: ")
    ]
    assert len(kept) == 2 and all("/config/projects/" in part["text"] for part in kept)
    content = [part for part in content if part not in kept]
    assert [part["type"] for part in content] == [
        "text",
        "image",
        "text",
        "image",
        "text",
    ]
    assert [part["text"] for part in content if part["type"] == "text"][:2] == [
        "image 1 of 2",
        "image 2 of 2",
    ]
    pictures = [part["source"] for part in content if part["type"] == "image"]
    assert {(source["type"], source["media_type"]) for source in pictures} == {
        ("base64", "image/jpeg")
    }
    assert [jpeg_size(base64.b64decode(source["data"])) for source in pictures] == [
        (1280, 720)
    ] * 2


def test_a_project_asked_its_kind_begins_its_first_turn_knowing_it(studio):
    client, model = studio.client, studio.model
    made = client.post(
        "/v1/projects",
        headers=auth("alice-token"),
        json={"name": "Reel", "discipline": "media"},
    ).json()["project"]
    (card,) = [e["data"] for e in events(client, made["id"])["events"]]
    assert (card["instant"], card["sets"]) == (True, "format") and model.requests == []
    model.script(AGENT, reply(say("A social video. What is it about?")))
    locked = client.post(
        f"/v1/projects/{made['id']}/messages",
        headers=auth("alice-token"),
        json={
            "text": "",
            "ui": {"ui_id": card["ui_id"], "value": {"format": "Social Media"}},
        },
    )
    assert locked.status_code == 202
    body = model.asked(AGENT)[0]
    assert messages(body) == [
        '[The person chose this project\'s kind on the card "What kind of video are you making?": Social Media]'
    ], "a message that is only the choice reaches the model as the line that says it"
    assert "Kind: Social Media" in spoken(
        body
    ) and "Its kinds: Film & TV" in system_text(body)
    assert kinds(client, made["id"]) == [
        "ui",
        "user_message",
        "text",
        "usage",
        "turn_end",
    ]


def test_a_session_resumes_in_a_fresh_process_that_has_nothing_of_the_first_but_the_database(
    tmp_path,
):
    state, root = tmp_path / "database.pickle", tmp_path / "loop"

    def turn(phase: str) -> dict[str, Any]:
        home = tmp_path / f"home-{phase}"
        home.mkdir()
        clean = {
            "PATH": os.environ.get("PATH", os.defpath),
            "HOME": str(home),
            "TMPDIR": str(home),
            # Where this file is and where the agent's modules are, which an image may keep apart
            "PYTHONPATH": os.pathsep.join(
                dict.fromkeys(
                    str(Path(found).parent)
                    for found in (__file__, sys.modules[Agent.__module__].__file__)
                )
            ),
        }
        ran = subprocess.run(
            [
                sys.executable,
                __file__,
                phase,
                str(state),
                str(root),
                str(home / "definitions"),
            ],
            env=clean,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert ran.returncode == 0, ran.stdout + ran.stderr
        return json.loads(ran.stdout.splitlines()[-1])

    first = turn("first")
    assert (
        first["kinds"][-4:] == ["ask", "tool_end", "usage", "turn_end"]
        and first["transcript_rows"] > 0
    )
    assert not root.exists() or not any(root.iterdir()), (
        "the first process left no file of the conversation behind"
    )
    second = turn("second")
    assert second["session"] == first["session"] and second["pid"] != first["pid"]
    assert second["words"] == ["Remember the word HELIOTROPE.", "What was the word?"]
    assert (
        "I will remember HELIOTROPE." in second["conversation"]
        and "Which color?" in second["conversation"]
    )
    assert (
        second["kinds"][-3:] == ["text", "usage", "turn_end"]
        and second["answer"] == "The word was HELIOTROPE."
    )


def test_a_step_the_person_approves_waits_for_their_answer_and_no_longer_than_configured(
    studio,
):
    client, model = studio.client, studio.model
    film = new_project(client, asks=True)
    start = use("engine_start", app="filmcraft", tier="cpu")
    model.script(
        AGENT,
        reply(say("Opening FilmCraft."), start),
        reply(say("FilmCraft runs.")),
        reply(say("It stays open: the cut is next.")),
    )
    waiter = answering(studio, film["id"], "once")
    message(client, film["id"], "Cut the film")
    waiter.join()
    log = events(client, film["id"])["events"]
    assert [e["kind"] for e in log] == [
        "user_message",
        "text",
        "tool_start",
        "approval",
        "approval_result",
        "engine",
        "engine",
        "tool_end",
        "text",
        "text",
        "usage",
        "turn_end",
    ], "the engine is open at the end, so the turn is told once"
    asked = next(e["data"] for e in log if e["kind"] == "approval")
    assert (asked["tool"], asked["title"]) == (
        "engine_start",
        "Starting FilmCraft",
    ) and len(studio.launcher.started) == 1
    assert not results(model.asked(AGENT)[1])[start["id"]].get("is_error")
    assert f"{PREFIX}engine_start" in [
        tool["name"] for tool in model.asked(AGENT)[0]["tools"]
    ], "the tool is offered; running it is what is asked about"

    with_config(studio, approval_seconds=0.3)
    again = use("engine_start", app="filmcraft", tier="cpu")
    model.script(
        AGENT,
        reply(again),
        reply(say("I wanted to open a second FilmCraft. Say when to go ahead.")),
        reply(say("The first stays open for the cut.")),
    )
    message(client, film["id"], "Open another")
    log = events(client, film["id"])["events"]
    assert [e["data"]["decision"] for e in log if e["kind"] == "approval_result"] == [
        "once",
        "expired",
    ]
    told = results(model.asked(AGENT)[-2])[again["id"]]
    assert (
        told["is_error"]
        and "did not answer in time" in told["text"]
        and len(studio.launcher.started) == 1
    )
    ends = [e["data"] for e in log if e["kind"] == "tool_end"]
    assert (ends[-1]["ok"], ends[-1]["summary"]) == (False, "Not approved") and log[-1][
        "kind"
    ] == "turn_end"


def test_stopping_a_turn_interrupts_the_program_while_it_answers(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    long = " ".join(f"Shot {number}: the lamp turns." for number in range(1, 200))
    model.script(
        AGENT, Reply([{"type": "text", "text": long}, use("library_list")], delay=0.05)
    )

    def stop_once_writing() -> None:
        """Stop the turn as the person would once they see the answer being written: its first snapshot is in the log."""
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            rows = list(studio.store.tables["project_events"].values())
            if any(
                row["kind"] == "text" and row["project_id"] == film["id"]
                for row in rows
            ):
                client.post(
                    f"/v1/projects/{film['id']}/stop", headers=auth("alice-token")
                )
                return
            time.sleep(0.01)

    stopper = threading.Thread(target=stop_once_writing)
    stopper.start()
    message(client, film["id"], "Write the shot list")
    stopper.join()
    log = events(client, film["id"])
    assert log["running"] is False and len(model.asked(AGENT)) == 1 and children() == []
    assert [e["kind"] for e in log["events"]][-2:] == ["usage", "turn_end"] and not any(
        e["kind"] in ("error", "tool_start") for e in log["events"]
    )
    written = [e["data"] for e in log["events"] if e["kind"] == "text"]
    assert (
        written
        and all(data["partial"] for data in written[:-1])
        and len({data["block"] for data in written}) == 1
    ), "the answer was shown while it was written, each snapshot replacing the last"
    assert long.startswith(written[-1]["text"]) and len(written[-1]["text"]) < len(long)


def test_a_skill_is_loaded_when_it_is_opened_and_nothing_else_of_the_machine_can_be_read(
    studio,
):
    client, model = studio.client, studio.model
    film = new_project(client)
    opening = use("skill", skill="filmcraft")
    private = studio.tmp / "private.txt"
    private.write_text("NEVER-READ-5518")
    reads: dict[str, dict[str, Any]] = {}

    def follow(body: dict[str, Any]) -> Reply:
        base = re.search(
            r"Base directory for this skill: (\S+?)\\n", spoken(body)
        ).group(1)
        reads.update(
            reference=use("read", file_path=f"{base}/references/color.md"),
            host=use("read", file_path=str(private)),
            climb=use("read", file_path=f"{base}/../../../../{private.name}"),
            other=use(
                "read",
                file_path=str(studio.tmp / "skills" / "songwriting" / "SKILL.md"),
            ),
            fetch=use(
                "web_fetch",
                url="http://169.254.169.254/latest/meta-data/",
                prompt="What is here?",
            ),
            unoffered=use("skill", skill="songwriting"),
        )
        return reply(*reads.values())

    model.script(AGENT, reply(opening), follow, reply(say("Graded.")))
    message(client, film["id"], "Grade the film")
    first, second, third = model.asked(AGENT)
    listed = spoken(first)
    assert (
        "- filmcraft: Editing films in FilmCraft." in listed
        and "studio-basics" in listed
    ), "a skill's description is in context from the start"
    assert (
        "songwriting" not in listed
        and "FILMCRAFT-SKILL-TEXT" not in listed + system_text(first)
    )
    assert "FILMCRAFT-SKILL-TEXT" in spoken(
        second
    ) and "FILMCRAFT-REFERENCE-TEXT" not in spoken(second), "its text when it is opened"
    told = results(third)
    assert "FILMCRAFT-REFERENCE-TEXT" in told[reads["reference"]["id"]]["text"], (
        "a reference file when the text sends the agent to it"
    )
    for refused in ("host", "climb", "other"):
        assert (
            told[reads[refused]["id"]]["is_error"]
            and "Only the files of a skill can be read"
            in told[reads[refused]["id"]]["text"]
        ), refused
    assert (
        told[reads["fetch"]["id"]]["is_error"]
        and "Only public web addresses" in told[reads["fetch"]["id"]]["text"]
    )
    assert told[reads["unoffered"]["id"]]["is_error"]
    assert "NEVER-READ-5518" not in spoken(third)
    assert [title for title, _, ok in tools_shown(client, film["id"]) if ok] == [
        "Opening the filmcraft skill",
        "Reading color.md",
    ]


def test_a_turn_that_would_end_with_an_engine_open_is_told_so_once_by_the_real_hook(
    studio,
):
    client, model = studio.client, studio.model
    film = new_project(client)
    engine = start_engine(studio, film["id"])
    stop = use("engine_stop", engine_id=engine["id"])
    model.script(
        AGENT,
        reply(say("The cut is done.")),
        reply(stop),
        reply(say("Stopped FilmCraft.")),
    )
    message(client, film["id"], "Cut it")
    asked = model.asked(AGENT)
    assert len(asked) == 3 and f"- {engine['id']}: FilmCraft, running" in spoken(
        asked[1]
    )
    assert (
        "engine_stop" in spoken(asked[1])
        and "- " + engine["id"] not in spoken(asked[0]).split("</project_state>")[-1]
    )
    assert studio.launcher.stopped == ["sb-1"]
    assert kinds(client, film["id"])[-7:] == [
        "text",
        "tool_start",
        "engine",
        "tool_end",
        "text",
        "usage",
        "turn_end",
    ]


def test_a_turn_the_model_could_not_finish_says_so_and_holds_nothing(
    studio, monkeypatch
):
    client, model = studio.client, studio.model
    film = new_project(client)
    told = lambda: [
        e["data"]["message"]
        for e in events(client, film["id"])["events"]
        if e["kind"] == "error"
    ]
    # The program tries a failed request again, ten times by its own default; the deployment can hand it another
    # count, as it can hand it a proxy's address, by naming the variable
    monkeypatch.setenv("CLAUDE_CODE_MAX_RETRIES", "0")
    with_config(studio, loop_env=frozenset({"CLAUDE_CODE_MAX_RETRIES"}))
    model.script(AGENT, Reply([], error="authentication_failed"))
    message(client, film["id"], "Hello")
    assert told() == ["The agent's model is not available right now."] and kinds(
        client, film["id"]
    )[-3:] == ["error", "usage", "turn_end"]
    assert not any(
        "API Error" in e["data"].get("text", "")
        for e in events(client, film["id"])["events"]
    )


def test_a_turn_stops_at_its_persons_own_limits_and_says_which(studio):
    client, model = studio.client, studio.model
    film = new_project(client)
    limits = lambda **changes: client.patch(
        "/v1/me", headers=auth("alice-token"), json=changes
    )
    wrong = lambda: [
        e["data"] for e in events(client, film["id"])["events"] if e["kind"] == "error"
    ]

    assert limits(turn_limit=2).status_code == 200
    model.script(AGENT, reply(use("library_list")), reply(use("library_list")))
    message(client, film["id"], "Loop")
    assert wrong() == [
        {
            "message": "This turn reached your limit of 2 steps and stopped. You can change the limit in your "
            "settings. Send a message to go on.",
            "limit": "steps",
        }
    ]
    assert (
        len(model.asked(AGENT)) == 2 and events(client, film["id"])["running"] is False
    )

    assert limits(turn_limit=None, turn_budget_usd=0.0001).status_code == 200
    model.script(AGENT, reply(say("Listing."), use("library_list")))
    message(client, film["id"], "Spend")
    assert wrong()[-1] == {
        "message": "This turn reached your spending limit of $0.0001 and stopped. You can change the limit in your "
        "settings. Send a message to go on.",
        "limit": "budget",
    }
    log = events(client, film["id"])["events"]
    assert len(model.asked(AGENT)) == 3, (
        "the answer that reached the budget is the last one asked for"
    )
    assert [e["kind"] for e in log][-5:] == [
        "tool_start",
        "tool_end",
        "error",
        "usage",
        "turn_end",
    ], "its call still runs"
    assert log[-2]["data"]["cost_usd"] > 0.0001


def one_turn(phase: str, state: Path, root: Path, definitions: Path) -> dict[str, Any]:
    """One turn of the resume test, in a process of its own: the database is a file read before it and written after."""
    api = ScriptedAPI()
    store = pickle.loads(state.read_bytes()) if state.exists() else None
    made = backend(definitions, api.url, store, root)
    with TestClient(made.app) as client:
        if phase == "first":
            film = new_project(client)
            api.script(
                AGENT,
                reply(
                    say("I will remember HELIOTROPE."),
                    use(
                        "ask_user",
                        question="Which color?",
                        options=["Blue", "Red"],
                        recommended="Blue",
                    ),
                ),
            )
            message(client, film["id"], "Remember the word HELIOTROPE.")
        else:
            (film,) = client.get("/v1/projects", headers=auth("alice-token")).json()[
                "projects"
            ]
            api.script(AGENT, reply(say("The word was HELIOTROPE.")))
            message(client, film["id"], "What was the word?")
        body = api.asked(AGENT)[-1]
        log = events(client, film["id"])["events"]
        report = {
            "pid": os.getpid(),
            "session": made.store.tables["projects"][film["id"]]["agent_session"],
            "kinds": [event["kind"] for event in log],
            "transcript_rows": len(made.store.tables["agent_transcripts"]),
            "conversation": spoken(body),
            "words": messages(body),
            "answer": next(
                (
                    event["data"]["text"]
                    for event in reversed(log)
                    if event["kind"] == "text"
                ),
                "",
            ),
            "ran_dry": len(api.ran_dry),
            "user": ALICE.id,
        }
    api.close()
    state.write_bytes(pickle.dumps(made.store))
    return report


if __name__ == "__main__":
    print(
        json.dumps(
            one_turn(
                sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
            )
        )
    )
