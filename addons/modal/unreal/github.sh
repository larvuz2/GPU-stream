#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# The Unreal session's GitHub client, Desktop Plus, as the session runs it:
# from its start, its start menu entry (desktop-plus.desktop), and Firefox,
# which hands it the end of a GitHub sign-in (firefox-policies.json):
#
#     selkies-modal-unreal-github [ARGUMENTS...]
#     selkies-modal-unreal-github --clone-folder
#
# What it sets up first, every time, since any of the three may come first:
#
# - The sign-in is kept, as on any Linux desktop, in the Secret Service, which
#   here is GNOME's keyring daemon with its login keyring in
#   ~/.local/share/keyrings, a folder of the workspace (SELKIES_MODAL_PERSIST).
#   There is no login to unlock it with, so it is unlocked with a fixed
#   password: the keyring is as private as the workspace it is in, and no more.
#   Unlocking a daemon that already runs only unlocks it again.
# - Desktop Plus keeps its settings, its list of repositories, and its logs in
#   ~/.config/Desktop Plus. That is a link to ~/.desktop-plus, the name the
#   session keeps in the workspace (SELKIES_MODAL_PERSIST takes names without
#   spaces).
# - Git keeps the name and address commits carry in ~/.config/git/config, also
#   kept, which `git config --global` writes to while no ~/.gitconfig exists.
# - The clone dialog offers the clone folder (SELKIES_MODAL_CLONE_DIR, which
#   the image's Desktop Plus reads; install.sh): the project folder when the
#   session has one (SELKIES_MODAL_PROJECT, `selkies-modal-project`), else the
#   workspace's `projects`. `--clone-folder` prints it, made if missing.
# - A session started for a project linked to a GitHub repository has the
#   repository (LATHE_GIT_REPO) and a token that reads and writes it
#   (LATHE_GIT_TOKEN) in its environment, and clones it (clone.py). The client
#   fetches and pushes it with that token, without its own sign-in, through an
#   `Authorization` header Git sends to that repository's address alone
#   (`http.<url>.extraHeader`), given in the client's environment
#   (GIT_CONFIG_COUNT), so it is in no file. A credential helper, which is how
#   the session's own Git reaches the token, cannot reach the client's: the
#   client runs every Git it starts with the helpers cleared and only its own
#   in their place, and its own answers github.com from its signed-in accounts
#   alone, never asking another helper for a GitHub host. Unlike a helper's
#   answer, the header goes with every request, so a token GitHub refuses,
#   once it expires after eight hours, is refused for that repository even
#   where the client has signed in itself; the session's lifetime is that long.
set -u

KEYRING_PASSWORD=selkies-modal

clone_folder() {
  if [ -n "${SELKIES_MODAL_PROJECT-}" ]; then
    selkies-modal-project
  else
    folder="${SELKIES_MODAL_WORKSPACE:-${HOME}}/projects"
    mkdir -p "${folder}" && printf '%s\n' "${folder}"
  fi
}

# Adds the header that carries the session's token to the repository's two
# addresses, with and without `.git`, to the Git configuration in the
# environment.
token_header() {
  case "${LATHE_GIT_REPO-}" in
    */*/* | *[!A-Za-z0-9._/-]*) return 0 ;;
    ?*/?*) ;;
    *) return 0 ;;
  esac
  [ -n "${LATHE_GIT_TOKEN-}" ] || return 0
  header="Authorization: Basic $(printf 'x-access-token:%s' "${LATHE_GIT_TOKEN}" | base64 -w0)"
  count="${GIT_CONFIG_COUNT:-0}"
  for url in "https://github.com/${LATHE_GIT_REPO}.git" "https://github.com/${LATHE_GIT_REPO}"; do
    export "GIT_CONFIG_KEY_${count}=http.${url}.extraHeader" "GIT_CONFIG_VALUE_${count}=${header}"
    count=$((count + 1))
  done
  export GIT_CONFIG_COUNT="${count}"
}

if [ "${1-}" = "--clone-folder" ]; then
  clone_folder
  exit
fi

printf '%s' "${KEYRING_PASSWORD}" | gnome-keyring-daemon --unlock --components=secrets --daemonize > /dev/null 2>&1 ||
  echo "selkies-modal: the keyring did not start, so a GitHub sign-in is not kept" >&2

mkdir -p "${HOME}/.config/git" "${HOME}/.desktop-plus"
[ -e "${HOME}/.config/Desktop Plus" ] || ln -s "${HOME}/.desktop-plus" "${HOME}/.config/Desktop Plus"
[ -e "${HOME}/.gitconfig" ] || [ -e "${HOME}/.config/git/config" ] || : > "${HOME}/.config/git/config"

SELKIES_MODAL_CLONE_DIR="$(clone_folder)" || exit 1
export SELKIES_MODAL_CLONE_DIR
token_header
exec desktop-plus "$@"
