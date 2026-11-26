<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Subagents of Moody's agent

A subagent is another agent the project's agent hands one job to. It works in a context of its
own, with the tools its definition lists, several at once where the jobs are independent, and
only its final report returns to the agent. The page shows each one working. This directory
holds the definitions, and this guide is for the people and agents who add one. The contract is
in `moody/STUDIO.md` ("Contract: the agent on Anthropic's loop"); how the agent decides what to
delegate is in `moody/skills/studio`.

## What a definition is

A file `moody/agents/<name>.md`: front matter, then the subagent's system prompt.

```text
---
name: research
title: Research agent
description: When the agent should hand work to it, in a sentence or two.
disciplines: all
tools: web_search, web_fetch, library_list, library_upsert
skills: movie
model: balanced
---

The subagent's system prompt.
```

| Field | Meaning |
|---|---|
| `name` | The subagent's id, the same as the file's stem. The agent delegates to it by this name. |
| `title` | What the page calls it on its card. |
| `description` | Always in the agent's context. It is the only thing the agent knows of the subagent when it decides whether to delegate, so it says what the subagent does, what to hand it, and what it will not do. |
| `disciplines` | Which projects are offered the subagent: `all`, or a list of discipline ids from `moody/catalog.json`. |
| `tools` | The tools it has: names from `TOOLS` in `moody/control/agent.py`, `web_search`, and `web_fetch`. A prefix pattern such as `engine_*` is allowed. Every entry has to match a tool the agent has. |
| `skills` | Optional. Skills it reads, by name. Only skills the project is offered reach it. |
| `model` | `inherit` (the agent's own model, the default), `balanced`, or `light`: tiers the deployment maps to models. |

Each field is one `key: value` line, as in a skill's front matter. A file whose name starts with
`_` is a template, not a subagent, and this guide, which has no front matter, defines nothing.
The loader in `moody/control` reads the definitions, and its docblock is the reference for how.

## The roster

Each is here because productions of more than one discipline need its job, and because the job
can be done from a written brief without the person. A definition's own front matter says which
tools, model tier, and disciplines it has.

| Subagent | Its job | Why it is a subagent |
|---|---|---|
| `research` | Facts and references from the web, with sources | Many searches and pages read, of which the agent needs only the findings |
| `story` | Loglines, outlines, scripts, rewrites, script breakdowns | A long draft from settled inputs, written while the look and the library are made |
| `art-direction` | Two or three visual directions as style lines and style frames | An exploration whose result is a choice for the person |
| `character-design` | One character: candidates, then the reference sheet, the face, and variants | One per character, so a cast is designed at the same time |
| `production-design` | One environment, prop, product, vehicle, or logo: candidates, then its reference set | One per entry, beside the characters |
| `librarian` | The library's sections, metadata, and consistency | Bookkeeping over every entry, which a light model does |
| `animation` | Animation tests, and the takes of one scene's shots | Slow generations, one job per test set or scene, several at once |
| `sound` | Versions of a song, takes of a sound effect, one line in several voices, the lines of a narration | Several generations whose result is a choice the person makes by ear, made while the pictures are designed |
| `review` | Work checked against its brief and a standard, findings by severity | A reader that did not make the work finds what its maker missed |

What is deliberately absent: a subagent that plans the project or talks to the person (that is
the agent itself), one that writes hooks, captions, or the words of a post (a few lines the
agent writes itself, with the person), and one per engine written by hand (the template below
makes those: mapping footage and cutting it by code is the job of that engine's operator).

## Engine operators: `_operator.md`

Every engine that can be started gets an operator without a definition of its own: the loader
derives one from `_operator.md` for each, titled with the engine's name and "agent" ("FilmCraft
agent"). It reads that engine's skill where the engine has one, and works from the application's
own scripting interface where it has none yet. In the template, `{app}` stands for the app's id
and `{name}` for its name. The operator's id and which projects are offered it are the loader's
to decide (`operators` in `moody/control/definitions.py`), so the template has no `disciplines`
line. An engine's skill can give its operator tools of its own with an `operator_tools` line in
its front matter, as the Unreal skill does for opening and listing Unreal projects.

An operator does one job in an engine that is already running: it follows the engine's skill,
shows its work with `preview`, and reports. Its tool list leaves out starting, stopping, and
showing engines and sending files between them on purpose: when an engine runs, what it costs,
and what the person looks at stay with the agent. The template names no tool that belongs to
one application, so the one list is valid for every engine; the prompt tells the operator that
`engine_call` is the same call as an application's own channel tool, and that any other tool a
skill uses is a step it leaves to the agent.

## Writing one

- **Decide whether it should exist.** A subagent earns its place when its job recurs across
  projects, can be done from a written brief, returns something that can be checked, and is
  worth a context of its own. A job that is a conversation with the person, or two tool calls,
  stays with the agent.
- **The description is for the agent, the prompt is for the subagent.** The description says
  when to delegate, what to hand over, and what the subagent never does. The prompt says how to
  do the job.
- **The narrowest tool list that does the job.** No `ask_user`, `show_ui`, or `update_plan`: a
  subagent cannot talk to the person, and the plan is the agent's. No `engine_start` or
  `engine_stop` unless starting engines is the job. A subagent that only reads has no tool that
  writes.
- **The prompt stands alone.** The subagent has its definition and the agent's brief, and
  nothing else: not the conversation, not the project's state, not a skill it does not list.
  Whatever it must know about how a tool behaves is in the prompt.
- **Say what it returns.** Every prompt ends with the report's parts: what it made and where it
  saved it, what it recommends, what it spent, and what it could not do, in the refusal's own
  words. A subagent never approves its own work and never decides for the person.
- **Name no list that lives elsewhere.** Engines, machine tiers, models, and prices are in the
  catalog and the tools' definitions: a prompt says where the subagent finds them.
- **Write for a model that follows instructions literally:** each rule once, with its reason, in
  the imperative, about the agent as "the agent" and the person as "the person". Every call in a
  prompt has a name and parameters that are in `TOOLS`, and was run before it was written down,
  as `moody/skills/README.md` says of a skill.
- **Pick the model tier by the judgment the job needs,** not by its length: `light` for
  bookkeeping, `balanced` for reading and summarizing, `inherit` where the result is creative or
  a mistake costs money.

## Checking one

1. **It loads.** Its `name` is its file's stem, its `model` is a tier, its `disciplines` are
   `all` or catalog ids, and every entry of `tools` matches a tool.
2. **Its calls run.** Walk each call of the prompt through the control plane's tools, as the
   skills' guide says.
3. **The agent can use it.** In a project of one of its disciplines, give the agent a request
   the subagent is for and read the turn: did it delegate, was its brief enough for the subagent
   to work alone, did the report let it act? Where it went wrong, the description or the prompt
   was unclear: fix that, not the agent's instructions.
