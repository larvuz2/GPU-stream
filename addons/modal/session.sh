#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# The main process of a Selkies session in a Modal Sandbox: it provisions the
# session's token, starts the image's own entrypoint beneath it, and ends the
# Sandbox once the session has gone unused, which is what stops its billing.
#
# Modal bills a Sandbox until its main process exits, and its own idle timeout
# counts an open connection as use, so a tab left open on another screen keeps
# a GPU running to the Sandbox's lifetime. This script is that main process
# instead, and it measures use as the session sees it:
#
# - Input. On the X11 backend the display's idle counter restarts on every key
#   and pointer event Selkies injects, whichever page sent it. The Wayland
#   backend's input reaches no counter a process outside the compositor can
#   read, so there a connected page counts as use.
# - Commands. The launcher touches the activity file for each command it runs
#   in the session, so an agent working with no page open keeps it alive.
# - Transfers. A file still being downloaded or uploaded into the workspace.
#
# With neither for SELKIES_MODAL_IDLE_TIMEOUT seconds (600 unless set; 0 never
# ends it), the entrypoint is stopped and this script exits. The count starts
# when the Sandbox does, so a link nobody opens ends it as well.
#
# Modal starts every container as root, whatever user its image names. The
# session is the image's own user's, as under any other runtime: the home, the
# package database, and the display's access list are that user's. So this
# script does what only root can, handing the workspace Volume's mount point to
# that user, and then runs itself again as that user.
#
# The token arrives in SELKIES_MODAL_SESSION_TOKEN and becomes the session token
# table Selkies reads at start (SELKIES_TOKENS_FILE), so the session is in
# secure mode from its first request and the launcher needs no call into it
# before handing out the link. The image names that file and the activity file
# (SELKIES_MODAL_ACTIVITY_FILE), which is where the launcher's commands find
# them too, and the file this script's process ID goes in
# (SELKIES_MODAL_PID_FILE): terminating a Sandbox kills it outright, so the
# launcher stops a session by signaling this script, which ends it the way the
# idle timeout does, with Blender's scene and CADCraft's drawings kept.

set -u

SESSION_USER=1000
if [ "$(id -u)" -eq 0 ]; then
  if [ -n "${SELKIES_MODAL_WORKSPACE-}" ]; then
    chown "${SESSION_USER}:${SESSION_USER}" "${SELKIES_MODAL_WORKSPACE}" ||
      echo "selkies-modal: ${SELKIES_MODAL_WORKSPACE} stays root's, so the session cannot save into it" >&2
  fi
  exec setpriv --reuid="${SESSION_USER}" --regid="${SESSION_USER}" --init-groups -- "$0" "$@"
fi

ENV_FILE="${XDG_RUNTIME_DIR:-/tmp/runtime-ubuntu}/container-env"
IDLE_TIMEOUT="${SELKIES_MODAL_IDLE_TIMEOUT:-600}"
CHECK_INTERVAL=15

say() {
  echo "selkies-modal: $*"
}

case "${SELKIES_MODAL_SESSION_TOKEN-}" in
  '' | *[!A-Za-z0-9_-]*)
    say "SELKIES_MODAL_SESSION_TOKEN has to be a URL-safe token" >&2
    exit 1
    ;;
esac
if [ -z "${SELKIES_MASTER_TOKEN-}" ]; then
  say "SELKIES_MASTER_TOKEN is not set, so the session would be open to anyone with its address" >&2
  exit 1
fi
if [ -z "${SELKIES_TOKENS_FILE-}" ] || [ -z "${SELKIES_MODAL_ACTIVITY_FILE-}" ] || [ -z "${SELKIES_MODAL_PID_FILE-}" ]; then
  say "SELKIES_TOKENS_FILE, SELKIES_MODAL_ACTIVITY_FILE, and SELKIES_MODAL_PID_FILE name the files this session keeps; the image sets them" >&2
  exit 1
fi
case "${IDLE_TIMEOUT}" in
  '' | *[!0-9]*)
    say "SELKIES_MODAL_IDLE_TIMEOUT has to be a number of seconds" >&2
    exit 1
    ;;
esac

(
  umask 077
  mkdir -p "${SELKIES_TOKENS_FILE%/*}" "${SELKIES_MODAL_ACTIVITY_FILE%/*}" &&
    printf '{"%s": {"role": "controller", "slot": null}}\n' "${SELKIES_MODAL_SESSION_TOKEN}" > "${SELKIES_TOKENS_FILE}" &&
    : > "${SELKIES_MODAL_ACTIVITY_FILE}" &&
    echo "$$" > "${SELKIES_MODAL_PID_FILE}"
) || exit 1
unset SELKIES_MODAL_SESSION_TOKEN

# Where an application keeps its settings or sign-in in the home, which is the
# image's and goes with the Sandbox, those directories are links into the
# workspace instead (SELKIES_MODAL_PERSIST, paths relative to the home, which
# the image names). What the image put there itself is copied across the first
# time, without replacing what the workspace already holds.
for path in ${SELKIES_MODAL_PERSIST-}; do
  kept="${SELKIES_MODAL_WORKSPACE}/.home/${path}"
  mkdir -p "${kept}" "$(dirname "${HOME}/${path}")"
  if [ -d "${HOME}/${path}" ] && [ ! -L "${HOME}/${path}" ]; then
    cp -an "${HOME}/${path}/." "${kept}/"
    rm -rf "${HOME:?}/${path}"
  fi
  ln -sfn "${kept}" "${HOME}/${path}"
done

/etc/container-entrypoint.sh &
SESSION_PID=$!

# Has Blender quit, and keeps the scene it writes on its way out (quit.blend,
# what File > Recover > Last Session opens) under this Sandbox's name, for the
# next session's Blender to open (blender/session.py). Quitting is what makes
# Blender write that scene as its own recovery reads it back; the name is what
# keeps a Blender the window manager starts again here from taking it for
# another session's.
keep_scene() {
  [ "${SELKIES_MODAL_APP-}" = blender ] || return 0
  echo 'bpy.ops.wm.quit_blender()' | timeout 20 selkies-modal-blender 10 > /dev/null 2>&1 || return 1
  for _ in $(seq 1 50); do
    pgrep -x blender > /dev/null || break
    sleep 0.2
  done
  rm -f "${SELKIES_MODAL_BLENDER_RECOVERY}"/resume-*.blend
  mv "${SELKIES_MODAL_BLENDER_RECOVERY}/quit.blend" "${SELKIES_MODAL_BLENDER_RECOVERY}/resume-${MODAL_SANDBOX_ID}.blend"
}

# Has CADCraft save the drawings with unsaved changes (cadcraft/keep.sh), run
# in the session's environment, where its control channel's token is found.
keep_drawings() {
  [ "${SELKIES_MODAL_APP-}" = cadcraft ] || return 0
  timeout 20 selkies-modal-run selkies-modal-cadcraft-keep
}

# Stops the entrypoint and exits with the given status, once Blender has kept
# its scene and CADCraft its drawings. s6-svscan takes its services down on
# SIGTERM; a session that outlasts the wait goes with the Sandbox, which ends
# when this process does.
end_session() {
  keep_scene || say "Blender did not keep its scene; its last auto-save is what the workspace has"
  keep_drawings || say "CADCraft did not save its drawings; its last autosave is what the project folder has"
  kill -TERM "${SESSION_PID}" 2> /dev/null
  for _ in $(seq 1 20); do
    kill -0 "${SESSION_PID}" 2> /dev/null || break
    sleep 0.5
  done
  exit "$1"
}
trap 'end_session 143' TERM INT

# A variable of the session's environment, as the entrypoint settled it: the
# backend it names may not be the one asked for, since a Wayland session whose
# compositor cannot reach the GPU starts as X11.
session_env() {
  [ -f "${ENV_FILE}" ] || return 1
  # shellcheck disable=SC1090  # written by container-entrypoint.sh at startup
  (. "${ENV_FILE}" && printf '%s' "${!1-}")
}

# Seconds since the display last took input, where a counter says.
input_idle_seconds() {
  local display ms
  [ "$(session_env SELKIES_WAYLAND)" = "false" ] || return 1
  display="$(session_env DISPLAY)" || return 1
  ms="$(DISPLAY="${display}" timeout 5 xprintidle 2> /dev/null)" || return 1
  printf '%s' "$((ms / 1000))"
}

page_connected() {
  curl -fsS -m 5 -H "Authorization: Bearer ${SELKIES_MASTER_TOKEN}" \
    "http://127.0.0.1:${SELKIES_PORT:-8080}${SELKIES_SUBFOLDER:+/${SELKIES_SUBFOLDER}}/api/sessions" 2> /dev/null | grep -q '"connected_at"'
}

# Whether a file is still arriving in the workspace: a download in Firefox or an
# upload from the page, both of which write into a `.part` file until they are
# whole. An installer of several gigabytes takes longer than the idle timeout
# with no input at all.
transfer_running() {
  find "${SELKIES_MODAL_WORKSPACE}" -maxdepth 2 -name '*.part' -newermt "$((CHECK_INTERVAL * 2)) seconds ago" \
    -print -quit 2> /dev/null | grep -q .
}

# Seconds since the session was last used: the smaller of the input counter and
# the activity file's age.
idle_seconds() {
  local now idle input
  if { [ "$(session_env SELKIES_WAYLAND)" = "true" ] && page_connected; } || transfer_running; then
    touch "${SELKIES_MODAL_ACTIVITY_FILE}"
  fi
  now="$(date +%s)"
  idle="$((now - $(stat -c %Y "${SELKIES_MODAL_ACTIVITY_FILE}")))"
  if input="$(input_idle_seconds)" && [ "${input}" -lt "${idle}" ]; then
    idle="${input}"
  fi
  printf '%s' "${idle}"
}

if [ "${IDLE_TIMEOUT}" -eq 0 ]; then
  say "no idle timeout; the session runs until it is stopped or the Sandbox's lifetime ends"
else
  say "the session ends after ${IDLE_TIMEOUT} s without input or a command"
fi

while kill -0 "${SESSION_PID}" 2> /dev/null; do
  # In the background and waited for, so the trap runs on a signal at once
  # rather than after the sleep.
  sleep "${CHECK_INTERVAL}" &
  wait $!
  [ "${IDLE_TIMEOUT}" -gt 0 ] || continue
  idle="$(idle_seconds)"
  if [ "${idle}" -ge "${IDLE_TIMEOUT}" ]; then
    say "no input or command for ${idle} s; ending the session"
    end_session 0
  fi
done

wait "${SESSION_PID}"
status=$?
say "the session's entrypoint exited with status ${status}"
exit "${status}"
