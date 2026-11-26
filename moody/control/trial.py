# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""A trial of the agent's loop inside the control plane's image, as a throwaway Modal app.

`modal run moody/control/trial.py::scripted` runs the agent on Modal the way
`agent_turn` runs it (the control plane's image, the same CPU and memory),
with the model scripted (`scripted_api.py`), no Secret attached, and the
database the in-memory one of `test_api.py`. It says how long a worker takes
to start and each turn to run, how much memory the worker and the loop's
program reached, and whether four things hold there:

- Moody's tools run, and the program offers none of its own file or shell
  tools.
- A subagent's steps show in the conversation, marked as its own.
- A question ends the turn and holds no machine: no process of the loop is
  left and the project runs no turn while the person decides.
- The answer resumes the session on a machine that has nothing of the first
  but the database's rows. The two halves run in two functions, so in two
  containers, and the rows travel between them through this program.

It then runs the suites of `test_loop.py` and `test_api.py` in the same image.

`modal run moody/control/trial.py::real` runs the same four checks with a real
model: the worker's Anthropic key comes from the Modal Secret `moody`
(`ANTHROPIC_API_KEY`), nothing is scripted, and each turn asks the model in
words for what the check needs to see. It spends a few model calls and starts
no engine, and says what each turn cost. `--model` names the model the agent
runs on for the trial, the deployment's default where left out. Whatever else the Secret holds is in those workers' environment
and, as in the deployment, does not reach the loop's program (`loop.py`).

`modal run moody/control/trial.py::opening_turn --discipline architecture
--kind Building` asks what no script can: whether the agent follows a skill.
It runs the first turn of a project opened by its kind with a real model and
the repository's own skills and subagents, and reads it: the opening skill and
the kind's reference opened, one card that waits at the end, and nothing spent
but the model's tokens, of which it says the price.

The checks read the conversation the page would be shown, the project's
events, which is the same in both modes; what the model was sent is read only
where it is scripted. This file is not part of the deployed image.
"""

from __future__ import annotations

import json
import os
import pickle
import resource
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, AsyncIterator

import modal

import app as control

HERE = Path(__file__).resolve().parent
# Where the test modules stand in the image: beside a copy of the catalog, as they stand to it in the repository
SUITE = Path("/root/suite")
TESTS = (
    "conftest.py",
    "test_api.py",
    "test_loop.py",
    "scripted_api.py",
    "scripted_loop.py",
)
PYTEST = "pytest==9.1.1"
# Where a turn's working directory is made, on both machines: the loop keys a session by that path
LOOP_ROOT = "/tmp/moody-trial-loop"
SECRET, KEY = "moody", "ANTHROPIC_API_KEY"
# The variable a worker reads the model of a real trial from, where one was named
MODEL = "MOODY_TRIAL_MODEL"
# The program's own tools the agent keeps, as the program names them when it starts (`Task` is its subagent tool)
KEPT = {"Task", "Agent", "Read", "Skill", "WebFetch", "WebSearch"}
WORD = "HELIOTROPE"
# What the first turn of `opening_turn` may spend on the model, and how many steps it may take
OPENING_BUDGET_USD, OPENING_STEPS = 1.0, 15
# What each turn asks of the model. A scripted model answers as a model that does what it is asked would
PROMPTS = {
    "tools": "Write the plan with update_plan: two tasks, 'Storyboard' active and 'Cut' pending. Then tell me in one "
    "sentence whether you have any tool that reads or writes files or runs commands on a machine.",
    "subagent": "Hand this job to the research agent: list what this project's library holds with library_list and "
    "report how many entries it has. Then tell me that number.",
    "question": f"Remember the word {WORD}. Then, before anything else, ask me with ask_user which of two colors I "
    "want: Blue or Red.",
    "answer": "Blue. Which word did I ask you to remember? Answer with that word.",
}

app = modal.App("moody-trial-loop")
image = (
    control.carried(control.packages.pip_install(PYTEST))
    .add_local_file(HERE / "app.py", "/root/app.py")
    .add_local_file(HERE.parent / "catalog.json", str(SUITE / "catalog.json"))
)
for module in TESTS:
    image = image.add_local_file(HERE / module, str(SUITE / "control" / module))
worker: dict[str, Any] = {
    "image": image,
    "cpu": control.AGENT_TURN_CPUS,
    "memory": control.AGENT_TURN_MEMORY_MB,
    "timeout": 1800,
}


class Heard:
    """The SDK's client, with what the program says of itself when it starts kept for the report."""

    def __init__(self, inner: Any, kept: list[dict[str, Any]]) -> None:
        self.inner, self.kept = inner, kept

    async def connect(self) -> None:
        await self.inner.connect()

    async def query(self, prompt: Any) -> None:
        await self.inner.query(prompt)

    async def receive_response(self) -> AsyncIterator[Any]:
        from claude_agent_sdk import SystemMessage

        async for item in self.inner.receive_response():
            if isinstance(item, SystemMessage) and item.subtype == "init":
                self.kept.append(item.data)
            yield item

    async def interrupt(self) -> None:
        await self.inner.interrupt()

    async def disconnect(self) -> None:
        await self.inner.disconnect()


class Trial:
    """The Studio's backend on the real loop for one half of the trial, and the checks made of it.

    The backend is `test_loop.backend`: everything but the SDK is the stand-in
    of `test_api.py`, and the database is the one handed in, or a new one. With
    `own_definitions` the agent has the repository's skills and subagents, as a
    deployment's has, in place of the few the suite writes for itself.
    """

    def __init__(self, real: bool, state: bytes | None, own_definitions: bool = False) -> None:
        folder = SUITE / "control" if SUITE.is_dir() else HERE
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
        began = time.monotonic()
        import test_loop
        from definitions import agents_directory, skills_directory
        from loop import sdk_loop
        from scripted_api import ScriptedAPI

        self.import_seconds = round(time.monotonic() - began, 2)
        self.real, self.suite = real, test_loop
        self.api = None if real else ScriptedAPI()
        self.heard: list[dict[str, Any]] = []
        self.made = test_loop.backend(
            Path(tempfile.mkdtemp(prefix="moody-trial-")),
            self.api.url if self.api else "",
            pickle.loads(state) if state else None,
            Path(LOOP_ROOT),
            key=os.environ[KEY] if real else "sk-ant-scripted",
            model=os.environ.get(MODEL, "") if real else "",
            definitions=(skills_directory(), agents_directory()) if own_definitions else None,
        )
        self.made.agent.loop = lambda options: Heard(sdk_loop(options), self.heard)
        self.checks: list[dict[str, Any]] = []
        self.turns: dict[str, float] = {}
        # What each turn's `usage` event said it took: tokens in and out, and the model's price for them
        self.spent: dict[str, dict[str, Any]] = {}

    def script(self, marker: str, *steps: Any) -> None:
        """What the scripted model answers next to requests under a system prompt; nothing where the model is real."""
        if self.api:
            self.api.script(marker, *steps)

    def turn(self, client: Any, project_id: str, name: str) -> list[dict[str, Any]]:
        """Send one of `PROMPTS` and run its turn to the end: the events it wrote, with its duration kept."""
        from test_api import events, message

        before = len(events(client, project_id)["events"])
        began = time.monotonic()
        sent = message(client, project_id, PROMPTS[name])
        self.turns[name] = round(time.monotonic() - began, 2)
        if sent.status_code != 202:
            raise RuntimeError(
                f"the message was refused: {sent.status_code} {sent.text}"
            )
        wrote = events(client, project_id)["events"][before:]
        used = next((e["data"] for e in wrote if e["kind"] == "usage"), {})
        self.spent[name] = {key: used.get(key, 0) for key in ("input_tokens", "output_tokens", "cost_usd")}
        return wrote

    def check(self, name: str, ok: bool, saw: Any) -> None:
        """Record one check with what was seen, which is what a failure is read from."""
        self.checks.append({"name": name, "ok": bool(ok), "saw": saw})

    def report(self, sent: float, arrived: float, **more: Any) -> dict[str, Any]:
        """What this half measured, beside its checks."""
        if self.api:
            self.check(
                "the scripted model was asked for nothing but what was scripted, and only for messages",
                not self.api.ran_dry and self.api.others == [],
                {"ran_dry": len(self.api.ran_dry), "others": self.api.others},
            )
            self.api.close()
        return {
            "host": socket.gethostname(),
            "task": os.environ.get("MODAL_TASK_ID", ""),
            "python": sys.version.split()[0],
            "start_seconds": round(arrived - sent, 2),
            "import_seconds": self.import_seconds,
            "turn_seconds": self.turns,
            "turn_usage": self.spent,
            "worker_peak_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            // 1024,
            "program_peak_mib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            // 1024,
            "program": self.heard[-1].get("claude_code_version")
            if self.heard
            else None,
            "model": self.heard[-1].get("model") if self.heard else None,
            "checks": self.checks,
            **more,
        }


def opening(real: bool, sent: float) -> dict[str, Any]:
    """The first half: Moody's tools, a subagent, and a question that ends the turn. The database's rows return."""
    arrived = time.time()
    trial = Trial(real, None)
    from fastapi.testclient import TestClient
    from loop import PREFIX
    from test_api import events, new_project, reply, say, use

    suite, made = trial.suite, trial.made
    with TestClient(made.app) as client:
        project_id = new_project(client)["id"]

        plan = [
            {"id": "storyboard", "title": "Storyboard", "status": "active"},
            {"id": "cut", "title": "Cut", "status": "pending"},
        ]
        trial.script(
            suite.AGENT,
            reply(use("update_plan", items=plan)),
            reply(say("No: I have no such tool.")),
        )
        log = trial.turn(client, project_id, "tools")
        offered = trial.heard[-1].get("tools", []) if trial.heard else []
        ended = [e["data"] for e in log if e["kind"] == "tool_end"]
        trial.check(
            "Moody's tools run",
            any(e["kind"] == "plan" for e in log)
            and bool(ended)
            and all(end["ok"] for end in ended),
            [
                (
                    e["kind"],
                    e["data"].get("tool")
                    or e["data"].get("summary")
                    or e["data"].get("message"),
                )
                for e in log
            ],
        )
        others = sorted(name for name in offered if not name.startswith(PREFIX))
        trial.check(
            "and the program offers none of its own file or shell tools",
            bool(offered)
            and set(others) <= KEPT
            and sum(name.startswith(PREFIX) for name in offered) > 0,
            others,
        )
        if trial.api:
            named = sorted(
                tool["name"] for tool in trial.api.asked(suite.AGENT)[0]["tools"]
            )
            trial.check(
                "nor does the request the model is sent",
                sorted(name for name in named if not name.startswith(PREFIX))
                == suite.KEPT,
                [name for name in named if not name.startswith(PREFIX)],
            )

        job = use(
            "Agent",
            subagent_type="research",
            description="Count the library",
            prompt="List the library with library_list and report how many entries it has.",
        )
        trial.script(
            suite.AGENT,
            reply(say("Asking the research agent."), job),
            reply(say("The library holds 0 entries.")),
        )
        trial.script(
            suite.RESEARCH,
            reply(use("library_list")),
            reply(say("The library is empty: 0 entries.")),
        )
        log = trial.turn(client, project_id, "subagent")
        cards = [e["data"] for e in log if e["kind"] == "agent"]
        steps = [
            e["data"]
            for e in log
            if e["kind"] == "tool_start" and e["data"].get("agent_id")
        ]
        trial.check(
            "a subagent's steps show in the conversation, marked as its own",
            bool(cards)
            and cards[0]["name"] == "research"
            and cards[-1]["activity"] == "satisfied"
            and any(
                step["tool"] == "library_list"
                and step["agent_id"] == cards[0]["agent_id"]
                for step in steps
            ),
            {
                "cards": [
                    (card["name"], card["state"], card["activity"]) for card in cards
                ],
                "steps": [step["tool"] for step in steps],
            },
        )

        trial.script(
            suite.AGENT,
            reply(
                say(f"I will remember {WORD}."),
                use(
                    "ask_user",
                    question="Which color?",
                    options=["Blue", "Red"],
                    recommended="Blue",
                ),
            ),
        )
        log = trial.turn(client, project_id, "question")
        kinds = [e["kind"] for e in log]
        project = made.store.tables["projects"][project_id]
        trial.check(
            "a question ends the turn",
            "ask" in kinds and kinds[-1] == "turn_end" and "error" not in kinds,
            kinds,
        )
        trial.check(
            "and holds no machine: no process of the loop is left and the project runs no turn",
            suite.children() == [] and project["turn_id"] is None,
            {"processes": suite.children(), "turn": project["turn_id"]},
        )
        errors = [
            e["data"]
            for e in events(client, project_id)["events"]
            if e["kind"] == "error"
        ]
        trial.check("no turn wrote an error", errors == [], errors)
    return trial.report(
        sent,
        arrived,
        project=project_id,
        session=project["agent_session"],
        state=pickle.dumps(made.store),
    )


def closing(real: bool, sent: float, before: dict[str, Any]) -> dict[str, Any]:
    """The second half, on another machine: the answer resumes the session from the database's rows."""
    arrived = time.time()
    trial = Trial(real, before["state"])
    from fastapi.testclient import TestClient
    from test_api import reply, say

    suite, made, project_id = trial.suite, trial.made, before["project"]
    with TestClient(made.app) as client:
        trial.script(suite.AGENT, reply(say(f"Blue it is. The word was {WORD}.")))
        log = trial.turn(client, project_id, "answer")
        said = " ".join(
            e["data"]["text"]
            for e in log
            if e["kind"] == "text" and not e["data"].get("partial")
        )
        project = made.store.tables["projects"][project_id]
        trial.check(
            "the answer resumes the session on a machine that has nothing of the first but the database",
            project["agent_session"] == before["session"]
            and WORD in said
            and (socket.gethostname(), os.environ.get("MODAL_TASK_ID", ""))
            != (before["host"], before["task"])
            and not os.path.exists(os.path.join(LOOP_ROOT, ".first")),
            {
                "said": said[:200],
                "session": project["agent_session"],
                "first": before["session"],
                "host": socket.gethostname(),
                "first_host": before["host"],
            },
        )
        if trial.api:
            words = suite.messages(trial.api.asked(suite.AGENT)[-1])
            trial.check(
                "the model is sent the whole conversation, the answer last",
                words
                == [
                    PROMPTS["tools"],
                    PROMPTS["subagent"],
                    PROMPTS["question"],
                    PROMPTS["answer"],
                ],
                [word[:40] for word in words],
            )
    return trial.report(sent, arrived)


@app.function(**worker)
def first(real: bool, sent: float) -> dict[str, Any]:
    """`opening`, in a worker of its own. It leaves a mark the second half must not find: its disk is not the first's."""
    report = opening(real, sent)
    Path(LOOP_ROOT).mkdir(parents=True, exist_ok=True)
    Path(LOOP_ROOT, ".first").write_text(report["task"])
    return report


@app.function(**worker)
def second(real: bool, sent: float, before: dict[str, Any]) -> dict[str, Any]:
    """`closing`, in another worker."""
    return closing(real, sent, before)


@app.function(**worker)
def first_turn(sent: float, discipline: str, kind: str) -> dict[str, Any]:
    """`started`, in a worker."""
    return started(sent, discipline, kind)


@app.function(**worker)
def suites() -> dict[str, Any]:
    """Run the control plane's suites in the image, each on its own: how it ended, and the end of what it printed."""
    found = {}
    for module in ("test_loop.py", "test_api.py"):
        began = time.monotonic()
        ran = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-rs",
                str(SUITE / "control" / module),
            ],
            capture_output=True,
            text=True,
            cwd="/root",
        )
        found[module] = {
            "exit": ran.returncode,
            "seconds": round(time.monotonic() - began, 1),
            "tail": (ran.stdout + ran.stderr)[-1500:],
        }
    return found


def started(sent: float, discipline: str, kind: str) -> dict[str, Any]:
    """A project opened by its kind, on the repository's own skills and a real model: what the first turn did.

    This is the check a skill's guide asks for and nothing scripted can make:
    whether the agent follows the skill. The project is made without a kind,
    as a Create shortcut makes it, the card the control plane wrote is locked
    on `kind`, and the turn that follows is read: did the agent open the
    discipline's opening skill and that kind's reference, end on a card that
    waits, and spend nothing but the model's tokens. Engines and generation
    are stand-ins, and the turn may spend at most `OPENING_BUDGET_USD`.
    """
    arrived = time.time()
    trial = Trial(True, None, own_definitions=True)
    from fastapi.testclient import TestClient
    from test_api import CATALOG, auth, events

    with TestClient(trial.made.app) as client:
        headers = auth("alice-token")
        client.patch("/v1/me", headers=headers, json={"turn_budget_usd": OPENING_BUDGET_USD, "turn_limit": OPENING_STEPS})
        project_id = client.post("/v1/projects", headers=headers, json={"name": "Untitled", "discipline": discipline}).json()["project"]["id"]
        asked = next(e["data"] for e in events(client, project_id)["events"] if e["kind"] == "ui")
        began = time.monotonic()
        answer = {"text": f"{kind}.", "ui": {"ui_id": asked["ui_id"], "value": {asked["sets"]: kind}}}
        locked = client.post(f"/v1/projects/{project_id}/messages", headers=headers, json=answer)
        trial.turns["opening"] = round(time.monotonic() - began, 2)
        if locked.status_code != 202:
            raise RuntimeError(f"the kind was refused: {locked.status_code} {locked.text}")
        log = [e for e in events(client, project_id)["events"] if e["turn_id"] is not None]
    used = next((e["data"] for e in log if e["kind"] == "usage"), {})
    trial.spent["opening"] = {key: used.get(key, 0) for key in ("input_tokens", "output_tokens", "cost_usd")}
    steps = [e["data"] for e in log if e["kind"] == "tool_start"]
    titles = [step.get("title", "") for step in steps]
    cards = [e["data"] for e in log if e["kind"] == "ui"]
    skill = CATALOG.disciplines[discipline].get("opening_skill", "")
    reference = "-".join(word for word in "".join(c if c.isalnum() else " " for c in kind.lower()).split())
    trial.check(f"the agent opened the {skill} skill", f"Opening the {skill} skill" in titles, titles)
    trial.check(f"and read {reference}.md", f"Reading {reference}.md" in titles, titles)
    trial.check(
        "the turn ended on one card that waits for its answer",
        len(cards) == 1 and cards[0]["waits"] and log[-1]["kind"] == "turn_end",
        [(card["title"], card["waits"]) for card in cards],
    )
    spending = [step["tool"] for step in steps if step["tool"].startswith(("generate_", "engine_"))]
    trial.check("nothing was generated and no engine was touched", not spending, spending)
    errors = [e["data"] for e in log if e["kind"] == "error"]
    trial.check("the turn wrote no error", not errors, errors)
    return trial.report(
        sent,
        arrived,
        steps=titles,
        said=" ".join(e["data"]["text"] for e in log if e["kind"] == "text" and not e["data"].get("partial")),
        cards=[{key: card.get(key) for key in ("title", "instant", "submit", "spec")} for card in cards],
    )


def show(title: str, report: dict[str, Any]) -> int:
    """Print one half's report, and return how many of its checks failed."""
    print(
        f"\n{title}: worker {report['task'] or report['host']}, Python {report['python']}, "
        f"program {report['program']}, model {report['model']}"
    )
    print(
        f"  worker start {report['start_seconds']} s, imports {report['import_seconds']} s, turns {report['turn_seconds']}"
    )
    print(
        f"  peak memory: worker {report['worker_peak_mib']} MiB, the loop's program {report['program_peak_mib']} MiB"
    )
    for name, used in report["turn_usage"].items():
        print(
            f"  turn {name}: {used['input_tokens']} tokens in, {used['output_tokens']} out, ${used['cost_usd']}"
        )
    for check in report["checks"]:
        print(
            f"  {'ok  ' if check['ok'] else 'FAIL'} {check['name']}"
            + ("" if check["ok"] else f" -> {check['saw']}")
        )
    return sum(not check["ok"] for check in report["checks"])


def show_opening(title: str, report: dict[str, Any]) -> int:
    """Print a first turn's report with what the agent did, said, and showed, and return how many checks failed."""
    failed = show(title, report)
    print(f"  steps: {report['steps']}")
    print(f"  said: {report['said']}")
    for card in report["cards"]:
        print(f"  card: {card['title']!r}, instant {card['instant']}, button {card['submit']!r}")
        print(f"    {json.dumps(card['spec'])[:1500]}")
    return failed


def run(one: Any, two: Any, real: bool) -> int:
    """Both halves in their workers, the second handed the first's rows: how many checks failed."""
    before = one.remote(real, time.time())
    failed = show("first half", before)
    failed += show("second half", two.remote(real, time.time(), before))
    return failed


@app.local_entrypoint()
def scripted() -> None:
    """The four checks with the model scripted and no Secret, then the suites in the image."""
    failed = run(first, second, False)
    for module, result in suites.remote().items():
        print(
            f"\n{module}: exit {result['exit']} in {result['seconds']} s\n{result['tail']}"
        )
        failed += result["exit"] != 0
    if failed:
        raise SystemExit(f"{failed} failed")


@app.local_entrypoint()
def real(model: str = "") -> None:
    """The four checks with a real model, the key from the Modal Secret `moody`.

    `--model` names the agent's model for the trial (`claude-haiku-5-5` to see
    that the key, the worker, and the loop meet for a few cents); left out, it
    is the deployment's default.
    """
    secrets = [modal.Secret.from_name(SECRET, required_keys=[KEY])]
    if model:
        secrets.append(modal.Secret.from_dict({MODEL: model}))
    failed = run(
        first.with_options(secrets=secrets), second.with_options(secrets=secrets), True
    )
    if failed:
        raise SystemExit(f"{failed} failed")


@app.local_entrypoint()
def opening_turn(discipline: str = "architecture", kind: str = "", model: str = "") -> None:
    """A project of `discipline` opened as `kind` with a real model and the repository's skills: its first turn.

    `kind` is the discipline's first where left out. `--model` names the
    agent's model, the deployment's default where left out. The turn starts
    no engine and generates nothing, and may spend `OPENING_BUDGET_USD` at most.
    """
    catalog = json.loads((HERE.parent / "catalog.json").read_text())
    formats = next(entry["formats"] for entry in catalog["disciplines"] if entry["id"] == discipline)
    secrets = [modal.Secret.from_name(SECRET, required_keys=[KEY])]
    if model:
        secrets.append(modal.Secret.from_dict({MODEL: model}))
    chosen = kind or formats[0]
    report = first_turn.with_options(secrets=secrets).remote(time.time(), discipline, chosen)
    if show_opening(f"{discipline}, opened as {chosen}", report):
        raise SystemExit("the opening did not go as its skill says")


if __name__ == "__main__":
    # Both halves in this process and no Modal: for working on the checks themselves
    half = opening(False, time.time())
    sys.exit(
        show("first half", half)
        + show(
            "second half",
            closing(False, time.time(), {**half, "host": "", "task": "-"}),
        )
    )
