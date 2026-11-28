#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# v2 as a session runs it, installed as /usr/local/bin/v2 in front of the
# program itself (/opt/v2/bin/v2, install.sh):
#
#     v2 init                                    make the folder a v2 project
#     v2 save -m TITLE --prompt TEXT --change TEXT   save a version
#     v2 log                                     list the versions
#     v2 comments                                list the comments left on the versions page
#     v2 restore vN                              bring the folder back to a version
#
# The arguments are v2's own, passed on untouched (`v2 --help` is upstream's
# help), with one exception: the commands that work with v2.video, its maker's
# site, are refused with status 2 and one line saying why. `push` uploads every
# saved version there and `publish` opens it to anyone with the link, and the
# others (`login`, `logout`, `unpublish`, `clone`, `update`) serve those two or
# fetch from the same place. A project's files stay in its workspace, so none
# of them runs here, whatever the notes `v2 init` writes into a project's
# AGENTS.md say about them.
#
# V2_SERVER, the address those commands and the check for a newer release
# reach, is pointed at the discard port of the machine itself, where nothing
# listens: a request this wrapper does not foresee is refused there instead of
# leaving. The versions page (`v2 diff`, versions.sh) is served on the
# machine's loopback and nowhere else.

for word in "$@"; do
  case "${word}" in
    -*) continue ;;
    login | logout | push | publish | unpublish | clone | update)
      echo "v2: ${word} is not available in this engine: it reaches v2.video, outside Moody, and a project is not sent there" >&2
      exit 2
      ;;
  esac
  break
done

export V2_SERVER="http://127.0.0.1:9"
exec /opt/v2/bin/v2 "$@"
