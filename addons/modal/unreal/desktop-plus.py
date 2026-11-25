#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Change four things in Desktop Plus's bundled code for the Unreal session, run once as the image is built.

    desktop-plus.py RENDERER_JS

Each change is to the code that decides one thing, found by its shape in the
bundle: a version whose code is not that shape fails the build here, rather
than doing what the session does not expect.

1. **The folder the clone dialog offers.** The session's clone folder
   (`SELKIES_MODAL_CLONE_DIR`, which `github.sh` sets) comes before the folder
   the client last cloned into. Desktop Plus otherwise offers that, or
   `Documents/GitHub`, and keeps no setting for it outside its own browser
   storage.
2. **A repository named on the command line is added.** `desktop-plus
   --cli-open=PATH` adds a Git repository at PATH to the client's list and
   selects it, where Desktop Plus asks first in its Add dialog. This is how the
   repository the session cloned for the developer (`clone.py`) comes to be in
   the client when the clone is done, with no question to answer: the list is
   in the client's IndexedDB, which nothing outside the client writes. A path
   that is not a repository still opens the dialog.
3. **Git LFS is not offered to a repository that has it.** Adding a repository
   whose attributes keep files in Git LFS asks to initialize Git LFS, whatever
   is installed, and the answer installs LFS's hooks into the repository
   (`git lfs install --force` there). A clone made where Git LFS is installed,
   as every clone in the session is (`git lfs install --system` in the image,
   which the client's own Git includes), has those hooks already, so the
   question comes only where the repository's `pre-push` hook does not run Git
   LFS yet.
4. **No welcome for a session that cloned the repository.** Where the session
   was given a repository (`MOODY_GIT_REPO`), the client opens on it rather
   than on its first-start welcome, whose steps, signing in and Git's name and
   address, the session has taken for the developer: the token and the
   identity come with the repository (`clone.py`, `github.sh`). The welcome is
   not marked as seen, so a later session of the workspace without a
   repository still shows it once.
"""

from __future__ import annotations

import re
import sys

CHANGES = (
    (
        "the clone dialog's default folder",
        # async function uE(e){return(e?localStorage.getItem(hE(e)):null)||await lE()}: the account's last
        # folder, else the last one, else Documents/GitHub
        re.compile(r"(async function \w+\((\w+)\)\{return)(\(\2\?localStorage\.getItem\(\w+\(\2\)\):null\)\|\|await \w+\(\)\})"),
        r"\1 process.env.SELKIES_MODAL_CLONE_DIR||\3",
    ),
    (
        "the command line's open-repository action",
        # "open-repository"===e.kind){const t=await Ag(e.path).then(...) ... await this.showPopup({type:Yy.AddRepository,path:t})
        re.compile(
            r'("open-repository"===(\w+)\.kind\)\{const (\w+)=await ([\w$]+)\(\2\.path\)'
            r"(?:(?!async dispatchURLAction).)*?)"
            r"(await this\.showPopup\(\{type:[\w$]+\.AddRepository,path:\3\}\))",
            re.S,
        ),
        r'\1{const $kind=(await \4(\3).catch(()=>null))?.kind;if("regular"===$kind){const[$added]=await this.addRepositories([\3]);'
        r"if($added)return void await this.selectRepository($added)}}\5",
    ),
    (
        "the question to initialize Git LFS",
        # const p=await this.isUsingLFS(d);t.push(d),p&&n.push(d)
        re.compile(r"(const (\w+)=await this\.isUsingLFS\((\w+)\))(;)"),
        r'\1&&!await require("fs/promises").readFile(require("path").join(\3.path,".git","hooks","pre-push"),"utf8")'
        r'.then($hook=>$hook.includes("git lfs pre-push"),()=>!1)\4',
    ),
    (
        "the decision to show the welcome",
        # this.showWelcomeFlow=!Oa(): the welcome until it has been seen once
        re.compile(r"(this\.showWelcomeFlow=!\w+\(\))"),
        r"\1&&!process.env.MOODY_GIT_REPO",
    ),
)


def main(path: str) -> int:
    """Make every change to the bundle at `path`, or none, and say which one did not fit."""
    with open(path, encoding="utf-8") as file:
        code = file.read()
    for name, shape, replacement in CHANGES:
        code, count = shape.subn(replacement, code)
        if count != 1:
            print(f"desktop-plus.py: {name} is not where this expects in {path} ({count} found)", file=sys.stderr)
            return 1
    with open(path, "w", encoding="utf-8") as file:
        file.write(code)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
