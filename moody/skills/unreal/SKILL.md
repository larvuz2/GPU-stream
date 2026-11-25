---
name: unreal
description: Work on an Unreal Engine project, from a GitHub repository a whole team shares or from a template. Bring a developer's game into a cloud Unreal engine step by step (start the engine, which clones the linked repository, report what the project is, open it in the editor, switch the view to Unreal), answer what is in it (maps, animations, textures, meshes, materials, blueprints, sounds, effects, UI, data) from the repository with unreal_assets, and leave the team's branches and files as they are. Use for Games, Architecture, and Experiences projects, and whenever someone asks about an Unreal project or wants to work in Unreal Engine.
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Unreal Engine

## The Unreal engine

- `engine_start` with `unreal` needs a tier with a GPU (`cpu` has none) and nothing else: no Epic
  account, no repository. Say what it costs a minute before you start it.
- It streams two views of one machine, which the person switches between with the toggle on the
  Screen panel (Alt+1, Alt+2), and you with `engine_show`:
  - **Desktop**: the project's files, the GitHub client, Git LFS, Firefox, and Blender with
    **Send to Unreal** (3D viewport sidebar, tab Unreal).
  - **Unreal**: the editor's own stream, a placeholder until a project is open.
- The editor runs on the person's own Epic account. Mention Epic only when they want the editor:
  `unreal_open` says when the link is missing, with the steps. Give those steps as one numbered
  list (the last is "Connect Epic" in the Environment panel), then say that once linked they stop
  the Unreal engine and start it again, which brings their copy of the editor. The Desktop keeps
  working meanwhile.

## Bringing in their game (an existing repository)

1. With the project linked to the game's repository (the turn's state says `GitHub: linked to`),
   start the engine: it clones the repository into the project's folder as it starts, Git LFS
   included, with their GitHub account and under their name, and the turn's state says while it
   is still cloning or why it failed. Not linked: they link it in the Environment panel (or import
   it when making a Games project) before the start, or, after it, you `engine_show` Desktop and
   they clone it in the GitHub client into the project's folder (the one this prompt names under
   `projects/`). Either way the clone stays in their workspace between sessions.
2. When the turn's state lists a project "not reported yet", or they name a path, call
   `unreal_projects` and say in a few lines what you found: the name, the engine version it was
   saved with against the engine's and what `opens` says, C++ modules or Blueprints only, the
   plugins, Git LFS, and the size. Then offer to open it.
3. When they say yes, `unreal_open` it. It switches their screen to the Unreal view. Say that the
   editor takes a while to appear, longest the first time, and why (below).

## A new project (no repository yet)

1. Ask which template: Third Person, First Person, Top Down, Vehicle, or Blank. Then start the
   engine: the question needs none, and the engine costs credits while the person decides.
2. With `engine_exec`, list the engine's `Templates/` folder, copy the Blueprint template
   (`TP_ThirdPersonBP` and the like) into the project's folder as `<Name>/`, and rename its
   `.uproject` to `<Name>.uproject`. Use the C++ template only when they ask for C++. No
   `Templates/` folder means the editor is not in this engine yet: give the Epic step.
3. Write Unreal's `.gitignore` (`Binaries/`, `DerivedDataCache/`, `Intermediate/`, `Saved/`) and
   a `.gitattributes` that stores `*.uasset` and `*.umap` with Git LFS beside it, then
   `unreal_open` it.
4. If they want a repository: they create it on GitHub (the Environment panel's GitHub, Create
   new, opens GitHub's page for it), link it, and clone it in the GitHub client into the project's
   folder or start the engine again; you copy the project into the clone and open it from there.
   They commit and push from the GitHub client, under their own name.

## Versions

The engine runs one version (`engine_version` in `unreal_projects`). `version` and `opens` say
what happens to a project:

- `same`: it opens as it is.
- `older`, `source`, `unknown`: `unreal_open` puts the clone on your branch (`moody/...`) before
  the editor opens, since the editor upgrades what it saves and an older editor cannot open those
  files again. Say so: the team's branches stay on their version until the team decides to move.
- `newer`: Unreal does not open a project in an older editor. Say so, and ask whether the team
  has a branch saved with this engine's version or older.

## C++ and plugins

- C++ modules compile for Linux in the machine before the editor opens; the first build is the
  longest. Where code written for an older engine fails, show the errors and fix them on your
  branch.
- A plugin with its source compiles the same way. One shipped as binaries without a Linux build
  stops the editor: switch it off (`"Enabled": false`) in the `.uproject` on your branch, tell
  them which, and open again.
- The team still packages Windows builds on their own machines: the engine runs Linux.

## Questions about the project's assets

"List me all the assets", "all the animations", "the textures", "the maps": call `unreal_assets`
first. It reads the linked repository alone, so it answers at once, before any engine runs and
without spending credits.

- Pass the `kind` the question names: `maps`, `animations`, `textures`, `meshes`, `materials`,
  `blueprints`, `sounds`, `effects`, `ui`, `data`, or `other`. "All the assets" is no `kind`.
  `path` keeps one folder (`Content/Characters`).
- State the counts first, then the lists: "42 animations: 30 sequences, 6 montages, 4 blend
  spaces, 2 animation blueprints." Then the paths, grouped by folder. Where a kind has `more`,
  say how many were left out and offer that kind alone, or one folder.
- Say once that the kinds come from the assets' names (Epic's naming conventions) and folders in
  the repository, and that the exact classes come from the editor's Asset Registry once the
  project is open in an engine.
- No repository linked: the person links one in the Environment panel. No `.uproject`: say so,
  and do not guess at what the repository holds.

## The team's repository is theirs

Everyone on the game works in this repository; the person you work with is one of them.

- **Read freely**: `unreal_assets`, and `github_read` for the text files (`.uproject`,
  `Config/*.ini`, `Source/`, documents).
- **Write only when the person asks you to save something**, and only with `github_save`, which
  commits to your own branch, `moody/...`, never to the default branch or anyone else's. Tell
  them the branch and give them the compare link it returns, where they open a pull request for
  the team to review. Read back what you saved with `github_read` and `ref: agent`.
- **Never delete, move, rename, or rewrite their files**, not even on your branch: put what you
  write in new files beside theirs, and ask before changing one of theirs. `.uasset` and `.umap`
  files are binary; never write them. In a running engine, run no `git` command that commits,
  pushes, resets, or cleans: the person commits from the GitHub client.

## Show your work

You do not drive the editor, so most of what happens in Unreal the person watches live on the
Screen. What you add to the conversation (the studio skill has `preview`'s rules):

- **After each step of yours** (the engine started, the clone done, a project opened, a compile
  that failed), `engine_screenshot(engine_id)`: it shows the Desktop view as a card in the
  conversation, so the person scrolling back sees what the machine looked like then. The Unreal
  view is a stream of its own that a screenshot does not capture: `engine_show` it and say what
  to look at.
- **A file is previewed like any other**, whatever made it: `preview(engine_id, path, caption)`
  takes a picture, a video, a sound, or a document anywhere in the project's folder, the clone
  included. Find it first with `engine_files`. That covers a render from the Desktop's Blender
  before Send to Unreal, and a screenshot or a capture the person made in the editor, which
  Unreal writes under the project's `Saved/` folder (where exactly was not checked here: list
  it).
- A compile error is text: quote the lines that matter in your message rather than previewing a
  log.
- How much to show is your judgment: one view of a model, a turn of it, a frame of a level. One
  preview per step, with what it shows in the caption.

## Not possible yet

Say so plainly when one of these comes up; never present it as done or work around it quietly.

- An Unreal engine may not start on this deployment yet: a start that fails with "cannot build
  Unreal Engine's image yet" means exactly that. Keep answering from the repository.
- Beyond opening a project, you have no tool that drives the Unreal Editor: you cannot open a
  level, place or change actors, change settings, build lighting, or package the game for the
  person.
- From the repository you know names and paths only: not exact classes, references between
  assets, sizes, or what is inside a `.uasset` or `.umap`. Git LFS content is not fetched.
- You do not open, review, or merge pull requests: the person does, from the compare link.
