---
name: unreal
description: Work on an Unreal Engine project whose GitHub repository a whole team shares. Answer what is in it (maps, animations, textures, meshes, materials, blueprints, sounds, effects, UI, data) from the repository with unreal_assets, leave the team's branches and files as they are, and open the Unreal engine, with Blender beside it, when the work needs the editor. Use for Games, Architecture, and Experiences projects, and whenever someone asks about an Unreal project's assets or wants to work in Unreal Engine.
---

<!--
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# Unreal Engine

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
  the repository, and that the exact classes come from the editor's Asset Registry once an
  Unreal engine runs.
- Name the engine version the `.uproject` asks for (`EngineAssociation`) and whether the
  repository keeps its binaries in Git LFS when that bears on the question.
- No repository linked: the person links one in the Environment panel. No `.uproject`: say so,
  and do not guess at what the repository holds.

## The team's repository is theirs

Everyone on the game works in this repository; the person you work with is one of them.

- **Read freely**: `unreal_assets`, and `github_read` for the text files (`.uproject`,
  `Config/*.ini`, `Source/`, documents).
- **Write only when the person asks you to save something**, and only with `github_save`, which
  commits to your own branch, `lathe/...`, never to the default branch or anyone else's. Tell
  them the branch and give them the compare link it returns, where they open a pull request for
  the team to review. Read back what you saved with `github_read` and `ref: agent`.
- **Never delete, move, rename, or rewrite their files**, not even on your branch: put what you
  write in new files beside theirs, and ask before changing one of theirs. `.uasset` and `.umap`
  files are binary; never write them. In a running engine, run no `git` command that commits,
  pushes, resets, or cleans.

## The Unreal engine

- `engine_start` with `unreal` needs a tier with a GPU (the machines listed above; `cpu` has
  none) and the person's GitHub account linked to their Epic account, since the engine is pulled
  with their own account under Epic's license. Starting it without the link says how to link.
- The first start pulls the engine, about 40 GB, and takes long; say so before you start it,
  with what it costs a minute. It opens the project from the linked repository.
- Blender runs beside the editor on the same machine and project folder. In Blender, **Send to
  Unreal** (3D viewport sidebar, tab Unreal) exports the selection and imports it into the open
  level; in the editor, Tools, **Send to Blender** sends the selected actors or meshes back.

## Not possible yet

Say so plainly when one of these comes up; never present it as done or work around it quietly.

- An Unreal engine may not start on this deployment yet: a start that fails with "cannot build
  Unreal Engine's image yet" means exactly that. Keep answering from the repository.
- You have no tool that drives the Unreal Editor: you cannot open a level, place or change
  actors, change settings, build lighting, or package the game for the person.
- From the repository you know names and paths only: not exact classes, references between
  assets, sizes, or what is inside a `.uasset` or `.umap`. Git LFS content is not fetched.
- You do not open, review, or merge pull requests: the person does, from the compare link.
