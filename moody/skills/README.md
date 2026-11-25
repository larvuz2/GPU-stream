<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Writing a skill for Moody's agent

A skill is what Moody's agent knows about doing one kind of work well: which questions to ask,
which commands to run in which order, what good looks like, what it costs, and where the edges
are. The agent's tools let it reach an engine; a skill is why what it does there is worth having.
This guide is for the people and agents who add one.

## What a skill is

A folder under `moody/skills/` with a `SKILL.md` and, where it needs them, more Markdown files it
links to:

```text
moody/skills/<name>/
  SKILL.md                 front matter, then the skill
  references/<topic>.md    detail a stage needs: a command reference, a prompting guide
```

The folder's name is the skill's name. `SKILL.md` opens with front matter:

```text
---
name: soundcraft
description: One paragraph: what the skill makes, with whom, and when to use it.
disciplines: music, media
---
```

| Field | Meaning |
|---|---|
| `name` | The skill's name, the same as its folder. The folder is what the loader reads. |
| `description` | What the agent always sees of the skill, and decides by whether to open it. Say what the skill is for and when it applies. |
| `disciplines` | Optional. Which projects read the skill; see [Which projects read a skill](#which-projects-read-a-skill). |
| `operator_tools` | Optional, in a skill named after an app. Tools that app's operator gets beside its template's (`moody/agents/_operator.md`): `operator_tools: unreal_projects, unreal_assets, unreal_open`. Each has to be a tool the agent has. |

Each field is one `key: value` line. The loader reads nothing else of YAML: no multi-line values,
no nested keys.

## How a skill is loaded

`read_skills` and `skills_for` in `moody/control/definitions.py` decide which skills a project is
offered, and the agent's loop (the Claude Agent SDK, `moody/control/loop.py`) loads them. Their
docblocks are the reference. What a writer needs to know:

- **Only the description is always in context.** At the start of a turn the skills the project is
  offered are copied, each folder whole, into the turn's working directory, and the loop lists
  them to the agent by name and `description`. Nothing else of a skill is in the prompt. So the
  description is what the agent decides by: a skill whose description does not say when it
  applies is not opened when it should be.
- **The body is loaded when the agent opens the skill**, with the loop's skill tool, and stays in
  the conversation from then on. It arrives with the skill's base directory, which is what the
  paths in its text are relative to.
- **A reference is read when the body sends the agent to it.** A link such as
  `[editing](references/editing.md)` is a path under the base directory, and the agent reads that
  file with the loop's read tool when the stage it is at needs it. Any file of the skill's folder
  can be read this way; nothing outside the offered skills' folders can, so a link that leaves the
  skill's folder leads nowhere. Say in the body when each reference is needed ("before the first
  cut, read ..."): a reference nothing points to at the right moment is not read.
- **A subagent whose definition names the skill starts with its body loaded**
  (`skills:` in `moody/agents/<name>.md`; an engine's operator reads the skill named after its
  app), and reads the references the same way.
- **So length is paid for when the skill is used**, not on every turn: the description on every
  turn of every project offered the skill, the body from the turn that opens it, a reference from
  the step that reads it. Keep the description to a paragraph, put in the body what the agent
  needs for every job the skill covers, and move what only one stage needs into a reference.
- **A change to a skill reaches a project at its next turn** after a deploy. A conversation that
  opened the skill before keeps the text it read until it opens the skill again. Do not write
  anything into a skill that changes with the work: the project's state arrives with the
  person's message each turn.

### Which projects read a skill

| The skill | Is read for |
|---|---|
| has `disciplines: media, animation` | projects of those disciplines (ids of `moody/catalog.json`, `disciplines`) |
| has `disciplines: all` | every project |
| has no `disciplines` and is named after a catalog app (`filmcraft`, `unreal`) | the disciplines whose `engines` list that app |
| has no `disciplines` and is named after no app | every project |

An engine's skill is normally named after its app and has no `disciplines` line, so the catalog
decides who reads it: add the app to a discipline's `engines` and that discipline's projects get
the skill. A skill for every project says so with `disciplines: all`, which is the one place that
is said; the loader names no skill. `moody/skills/studio` is that skill today: how a production
runs across engines.

One consequence to design for: the agent can start an engine that is not one of its discipline's,
and then that engine's skill is not among those it is offered, nor is the engine's operator. A
skill whose engine is useful beyond its disciplines lists them in `disciplines`.

## The structure that works

The sections below are the ones the existing skills converged on. Keep their order, so the agent
finds the same thing in the same place in every skill.

1. **When this applies.** The disciplines, formats, and requests the skill is for, and what is
   another skill's job, by name.
2. **The collaboration loop.** How one step goes: propose with a recommendation and a reason, ask
   with `ask_user`, execute exactly what was chosen, show the result, record it in the plan and
   the library. Name the checkpoints where the agent always asks first. A question's
   recommendation is `ask_user`'s `recommended`, which the page marks: where the skill writes out
   options, their text is only the options, and a line beside them says which one to recommend
   and when.
3. **The questions to ask first.** What only the person can answer, as questions with two to five
   short options, and what the agent decides by itself and reports.
4. **Recipes.** The work as numbered steps, each with the exact tool call: the tool, the method,
   the parameters with their units, what the answer looks like, and what a failure looks like and
   what to do then. A long command reference goes in `references/`.
5. **Taste.** The rules a professional follows that a tool does not enforce. Say them as rules
   with their reason, not as adjectives.
6. **Cost and time.** What each step spends in credits or dollars and how long it takes, and that
   the agent says so before it spends. Engines cost per minute by tier (the system prompt lists
   the tiers); a skill says which tier its work needs and when to stop the engine.
7. **What is not possible yet.** Every limit the agent would otherwise discover by failing, and
   what to offer instead. A skill never presents a missing or partial feature as working.
8. **Hand-offs.** What the engine exports for which other engine, in which format, into
   `handoff/<from app id>-to-<to app id>/` of the project's folder, and what it accepts from
   others. `moody/skills/studio` holds the convention; the engine's skill
   holds the exact recipe for its side.
9. **Show your work.** How the agent makes this engine's work in progress visible with `preview`:
   the engine's own commands that write a frame, a range, a page, or a render into `previews/` of
   the project's folder, each one already run. The skill gives the commands; how long or how
   large a preview is stays the agent's judgment for the moment, never a number in the skill.
   `moody/skills/studio` holds when to preview and how the tool behaves.

Write to the agent as "you", in the imperative, about the person as "the person". Name tools and
their parameters as they are in `TOOLS` (`moody/control/agent.py`).

## Driving an engine from a skill

- An engine with a command channel is driven with `engine_call(engine_id, method, params)`, which
  reaches the launcher's `<app id>_call` function for the app the engine runs. The skill lists the
  methods it uses, with parameters and units. FilmCraft's skill uses `filmcraft(engine_id, method,
  params)`, the same call for a FilmCraft engine.
- An engine without one is driven with `engine_exec(engine_id, command)` (a shell in the engine's
  environment) and by the person on its screen (`engine_show`, `engine_screenshot`).
- Files between engines are confirmed with `engine_files(engine_id, path)` before the next engine
  opens them. A running engine does not see what another wrote after it started:
  `engine_send(from_engine_id, path, to_engine_id)` carries the file across, and an engine started
  afterwards finds it by itself.

## Every command was run before it was written down

A skill holds only commands its writer ran, against the version of the engine the catalog starts,
and saw do what the skill says. That rule is what makes a skill worth more than a guess:

- Run each `engine_call` method with the parameters as written, and copy the names, units, and the
  shape of the answer from what came back, not from documentation or memory.
- Run each shell command in a running engine (`engine_exec`), in the project's folder.
- Where a command could not be run (the engine is not built yet, the license is missing), leave it
  out. Write the step under "What is not possible yet" instead, and say what was not verified in
  the change that adds the skill.
- When the engine's version moves, run the recipes again before the skill is called current.

## Testing a skill

1. **It loads.** `pytest moody/control` reads the real skills
   (`test_the_unreal_skill_is_read_for_the_disciplines_that_use_unreal`,
   `test_the_studio_skill_is_read_for_every_project_and_names_only_tools_the_agent_has`). Add the
   same checks for a new skill: it is chosen for the disciplines it is for and not for the others,
   and every tool it names is one the agent has.
2. **Its commands run.** Walk each recipe on a running engine, as the rule above says, and keep
   what was run with the change.
3. **The agent can follow it.** Start a project of the discipline in a deployment with the skill,
   give it the request the skill is for, and read the turn: did it ask the questions, quote the
   cost, run the recipe in order, confirm the result, and stop the engine? Where it went wrong,
   the skill was unclear; fix the skill, not the prompt.
4. **It reads well as it reaches the model.** Read the description alone, as the loop lists it:
   would the agent open the skill for the request of step 3? Then the body, then each reference at
   the stage that sends the agent to it. Cut what the agent did not need in step 3.

## Moving a skill to its own repository

The loader reads folders: any `<name>/SKILL.md` under the skills directory, with the Markdown
beside it. It does not care where a folder came from, so a skill that outgrows this repository
moves without the loader changing:

- Keep the skill's repository in the folder's shape (`SKILL.md` and `references/` at its top), so
  the checkout is the folder.
- Bring it back as `moody/skills/<name>/`, pinned to a commit: a submodule, a subtree, or a copy
  made when the control plane's image is built (`moody/control/app.py` carries `moody/skills` into
  the image as `/root/skills`).
- Keep the name. The folder's name is what matches a skill to its app in the catalog.
- Keep the skill's load test here, where the catalog and the tools it is checked against are.
