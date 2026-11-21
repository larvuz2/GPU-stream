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
# them too.

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
if [ -z "${SELKIES_TOKENS_FILE-}" ] || [ -z "${SELKIES_MODAL_ACTIVITY_FILE-}" ]; then
  say "SELKIES_TOKENS_FILE and SELKIES_MODAL_ACTIVITY_FILE name the files this session keeps; the image sets both" >&2
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
    : > "${SELKIES_MODAL_ACTIVITY_FILE}"
) || exit 1
unset SELKIES_MODAL_SESSION_TOKEN

/etc/container-entrypoint.sh &
SESSION_PID=$!

# Stops the entrypoint and exits with the given status. s6-svscan takes its
# services down on SIGTERM; a session that outlasts the wait goes with the
# Sandbox, which ends when this process does.
end_session() {
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
    "http://127.0.0.1:${SELKIES_PORT:-8080}/api/sessions" 2> /dev/null | grep -q '"connected_at"'
}

# Seconds since the session was last used: the smaller of the input counter and
# the activity file's age.
idle_seconds() {
  local now idle input
  if [ "$(session_env SELKIES_WAYLAND)" = "true" ] && page_connected; then
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
