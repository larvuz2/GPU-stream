#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# The Git credential helper through which the session's own Git commands reach
# the GitHub token the session was started with (clone.py sets it for its
# commands alone):
#
#     git -c 'credential.https://github.com.helper=!selkies-modal-unreal-git-credential' ...
#
# Asked to `get` a credential for https://github.com, it answers with the token
# in MOODY_GIT_TOKEN, read from the environment of the Git that asks, as GitHub
# takes a GitHub App's user token over HTTPS: the user name `x-access-token`
# and the token as the password. It answers nothing for another host or
# protocol, or when the session has no token, and Git asks only once GitHub has
# refused it without one, so a public repository is read without the token at
# all. `store` and `erase` are ignored: the token is read where it is needed and
# written nowhere, so nothing in the workspace keeps it after the session.
set -u

[ "${1-}" = get ] || exit 0
[ -n "${MOODY_GIT_TOKEN-}" ] || exit 0

protocol=
host=
while IFS='=' read -r key value; do
  case "${key}" in
    '') break ;;
    protocol) protocol="${value}" ;;
    host) host="${value}" ;;
  esac
done
[ "${protocol}" = https ] && [ "${host}" = github.com ] || exit 0
printf 'username=x-access-token\npassword=%s\n' "${MOODY_GIT_TOKEN}"
