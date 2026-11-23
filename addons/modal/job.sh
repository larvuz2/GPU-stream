#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Runs a long command in a session in the background, as a job an agent starts
# and checks on rather than waits for:
#
#     selkies-modal-job start shot010 -- nuke-run -x shot010.nk 1-48
#     selkies-modal-job status [NAME]
#     selkies-modal-job log NAME
#     selkies-modal-job stop NAME
#
# `selkies-modal exec` would hold the caller for as long as the render runs, and
# the session's idle timeout (session.sh) would end it while nobody touches the
# page. A job is detached from the command that started it and counts as use of
# the session for as long as it runs, so it is not cut short. Its output,
# status, and exit code are files in the workspace (`jobs/NAME`), which a
# machine that ends with the session leaves behind for the next to read.

set -u

JOBS="${SELKIES_MODAL_WORKSPACE:?the image sets it}/jobs"
mkdir -p "${JOBS}"

usage() {
  echo "usage: selkies-modal-job start NAME -- COMMAND... | status [NAME] | log NAME | stop NAME" >&2
  exit 2
}

valid_name() {
  case "$1" in '' | *[!A-Za-z0-9._-]*) echo "selkies-modal-job: a job name is letters, digits, . _ -" >&2; exit 2 ;; esac
}

describe() {
  local dir=$1 name state
  name="$(basename "${dir}")"
  state="$(cat "${dir}/state" 2> /dev/null || echo unknown)"
  if [ "${state}" = running ] && ! kill -0 "$(cat "${dir}/pid" 2> /dev/null)" 2> /dev/null; then
    state="lost (the machine it ran on ended)"
  fi
  printf '%s\t%s\tstarted %s\t%s\n' "${name}" "${state}" "$(cat "${dir}/started" 2> /dev/null)" "$(cat "${dir}/command" 2> /dev/null)"
}

case "${1-}" in
  start)
    [ "${3-}" = "--" ] && [ "$#" -ge 4 ] || usage
    name=$2
    valid_name "${name}"
    shift 3
    dir="${JOBS}/${name}"
    if [ -f "${dir}/pid" ] && kill -0 "$(cat "${dir}/pid")" 2> /dev/null; then
      echo "selkies-modal-job: ${name} is already running" >&2
      exit 1
    fi
    rm -rf "${dir}"
    mkdir -p "${dir}"
    printf '%s\n' "$*" > "${dir}/command"
    date -u +%Y-%m-%dT%H:%M:%SZ > "${dir}/started"
    echo running > "${dir}/state"
    # In a session of its own (setsid), so it outlives the exec that started it
    setsid "$0" run "${dir}" "$@" < /dev/null > /dev/null 2>&1 &
    echo $! > "${dir}/pid"
    echo "started ${name}; its output is ${dir}/log"
    ;;
  status)
    if [ -n "${2-}" ]; then
      valid_name "$2"
      [ -d "${JOBS}/$2" ] || { echo "selkies-modal-job: no job named $2" >&2; exit 1; }
      describe "${JOBS}/$2"
    else
      for dir in "${JOBS}"/*/; do [ -d "${dir}" ] && describe "${dir%/}"; done
    fi
    ;;
  log)
    valid_name "${2-}"
    tail -n "${LINES:-40}" "${JOBS}/$2/log"
    ;;
  run)
    # The job itself, as `start` runs it: the command, counted as use while it runs
    dir=$2
    shift 2
    (while touch "${SELKIES_MODAL_ACTIVITY_FILE}"; do sleep 10; done) &
    keeper=$!
    "$@" > "${dir}/log" 2>&1
    status=$?
    kill "${keeper}" 2> /dev/null
    echo "${status}" > "${dir}/exit"
    if [ "${status}" -eq 0 ]; then echo "done" > "${dir}/state"; else echo "failed (exit ${status})" > "${dir}/state"; fi
    date -u +%Y-%m-%dT%H:%M:%SZ > "${dir}/ended"
    ;;
  stop)
    valid_name "${2-}"
    pid="$(cat "${JOBS}/$2/pid" 2> /dev/null)" || { echo "selkies-modal-job: no job named $2" >&2; exit 1; }
    kill -- "-${pid}" 2> /dev/null || kill "${pid}" 2> /dev/null
    echo "stopped" > "${JOBS}/$2/state"
    echo "stopped $2"
    ;;
  *) usage ;;
esac
