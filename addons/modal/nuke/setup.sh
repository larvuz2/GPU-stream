#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# The Nuke session's application: Nuke, installed in the workspace, or, where
# the workspace has none yet, the one-time setup that installs it there.
#
# Foundry hands Nuke out behind a login, and installing it means accepting
# Foundry's license, so both are left to the person in the session. The setup
# opens Firefox on Foundry's download page and waits for the Linux archive to
# arrive, downloaded there (into the workspace's Downloads, as the image's
# Firefox policy has it) or uploaded through the page's Files panel (into the
# workspace). It then asks whether to install it, naming Foundry's license, and
# only once that is accepted runs Foundry's installer with the flag that records
# the acceptance. Nuke goes into the workspace (`.apps/nuke`), so it is
# installed once and is there in every session after; the archive is removed
# once it has, since it takes as much room again.
#
# Nuke's settings and Foundry's sign-in are kept by the session (session.sh
# links `~/.nuke`, `~/.local/share/Foundry`, and `~/FoundryLicensing` into the
# workspace), and scripts saved in the workspace stay with it.

set -u

WORKSPACE="${SELKIES_MODAL_WORKSPACE:?the image sets it}"
APPS="${WORKSPACE}/.apps/nuke"
DOWNLOADS="${WORKSPACE}/Downloads"
LOG="${WORKSPACE}/.apps/nuke-install.log"
DOWNLOAD_PAGE="https://www.foundry.com/products/nuke-family/download"
EULA="https://www.foundry.com/eula"
TITLE="Set up Nuke"

# The setup's windows draw in software: on a GPU session GTK reaches for a
# Vulkan driver that cannot present here, and a dialog it fails in is gone
export GSK_RENDERER=cairo

mkdir -p "${APPS}" "${DOWNLOADS}"
cd "${WORKSPACE}" || exit 1

# The newest Nuke installed in the workspace: the executable named for its
# version (Nuke17.1) in the directory Foundry's installer made for it.
installed_nuke() {
  find "${APPS}" -mindepth 2 -maxdepth 2 -type f -perm -u+x -regex '.*/Nuke[0-9]+\.[0-9]+' 2> /dev/null |
    sort -V | tail -n 1
}

# Foundry's Linux archive (or its installer alone), where a download or an
# upload put it. A download still arriving has a `.part` file beside it, and
# an upload is renamed into place only once it is whole.
arrived_installer() {
  local file
  file="$(find "${WORKSPACE}" "${DOWNLOADS}" -maxdepth 1 -type f -size +1M \
    \( -name 'Nuke*-linux-x86_64*.tgz' -o -name 'Nuke*-linux-x86_64*.run' \) 2> /dev/null | sort -V | tail -n 1)"
  [ -n "${file}" ] && [ ! -e "${file}.part" ] || return 1
  printf '%s' "${file}"
}

# Opens Nuke, Foundry's licensing window first where it has no license yet,
# closing the setup's instructions where they are still open. That window is
# Chromium, whose sandbox needs namespaces a Sandbox does not grant; the
# session is itself the boundary around it.
launch() {
  [ -z "${instructions-}" ] || kill "${instructions}" 2> /dev/null
  export QTWEBENGINE_DISABLE_SANDBOX=1
  exec "$1"
}

# Unpacks Foundry's archive and runs its installer into the workspace, the
# license accepted by the person who just said so. The installer's own output
# goes to the log; what this returns is the installer's status.
install_nuke() {
  local archive=$1 work installer status
  work="${WORKSPACE}/.apps/.unpacking"
  rm -rf "${work}"
  mkdir -p "${work}"
  case "${archive}" in
    *.tgz) tar -xzf "${archive}" -C "${work}" || return 1 ;;
    *) cp "${archive}" "${work}/" || return 1 ;;
  esac
  installer="$(find "${work}" -maxdepth 2 -type f \( -name '*.run' -o -name '*-installer*' \) | head -n 1)"
  if [ -z "${installer}" ]; then
    echo "no installer found in ${archive}"
    rm -rf "${work}"
    return 1
  fi
  chmod +x "${installer}"
  # Any further question the installer asks (a subdirectory to create) is answered yes
  yes y 2> /dev/null | "${installer}" --accept-foundry-eula --prefix="${APPS}"
  status=${PIPESTATUS[1]}
  rm -rf "${work}"
  return "${status}"
}

nuke="$(installed_nuke)"
if [ -n "${nuke}" ]; then
  launch "${nuke}"
fi

firefox --new-window "${DOWNLOAD_PAGE}" > /dev/null 2>&1 &
# After Firefox's window, which would otherwise open over the instructions
timeout 30 xdotool search --sync --onlyvisible --class firefox > /dev/null 2>&1
zenity --info --no-wrap --title "${TITLE}" --ok-label "Got it" --text \
  "<b>Nuke is not installed in this workspace yet.</b>

1. In the Firefox window, sign in to Foundry and download
   <b>Nuke for Linux</b> (the .tgz file). It saves into your workspace.
   Or upload that file from your computer with the Files panel.

2. When it has arrived, you will be asked to accept Foundry's license,
   and Nuke installs itself. This happens once: it is kept for every
   session after this one." > /dev/null 2>&1 &
instructions=$!

declined=""
while :; do
  archive="$(arrived_installer)" || archive=""
  if [ -z "${archive}" ] || [ "${archive}" = "${declined}" ]; then
    sleep 3
    continue
  fi
  if ! zenity --question --no-wrap --title "${TITLE}" --ok-label "Accept and install" --cancel-label "Not now" --text \
    "Install <b>$(basename "${archive}")</b>?

Installing Nuke means you accept Foundry's End User License Agreement:
${EULA}"; then
    declined="${archive}"
    continue
  fi

  # Installing is use of the session, however long it takes without input (session.sh)
  (while touch "${SELKIES_MODAL_ACTIVITY_FILE}"; do sleep 10; done) &
  keeper=$!
  status_file="$(mktemp)"
  {
    install_nuke "${archive}" > "${LOG}" 2>&1
    echo $? > "${status_file}"
    echo 100
  } | zenity --progress --pulsate --auto-close --no-cancel --title "${TITLE}" \
    --text "Installing Nuke into your workspace. This takes a few minutes." > /dev/null 2>&1
  kill "${keeper}" 2> /dev/null
  status="$(cat "${status_file}")"
  rm -f "${status_file}"

  nuke="$(installed_nuke)"
  if [ "${status}" = 0 ] && [ -n "${nuke}" ]; then
    rm -f "${archive}"
    launch "${nuke}"
  fi
  zenity --error --no-wrap --title "${TITLE}" --text \
    "Nuke did not install (status ${status}).

What the installer said is in ${LOG}.
The download is still in your workspace: close this to be asked again." > /dev/null 2>&1
done
