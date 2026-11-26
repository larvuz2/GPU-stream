#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Which release of the HyperFrames CLI a machine runs, installed as
# /usr/local/bin/hyperframes-release:
#
#     hyperframes-release install VERSION   put a release on the machine, whole or not at all
#     hyperframes-release build VERSION...  at image build: the first that installs is the image's own
#     hyperframes-release update            as a session starts: move to the release to run, once
#     hyperframes-release status            print what runs and why, as JSON
#
# Every other engine's application is pinned in the launcher. This one follows
# its upstream, at the word of the person the product is built for: a session
# takes the newest release of the `hyperframes` npm package as it starts, so
# what upstream adds is there the same day. What that risks is that a release
# nobody here has run renders differently, or not at all. Three things bound
# the risk:
#
# - A release is used only once all of it is there and it renders here: the
#   CLI answers with its own version, its skills are in place, the headless
#   browser that release was tested with is downloaded, and half a second of
#   the release's own starting project comes out as a video file (`install`,
#   `renders`). A release that fails any of these is never switched to, at a
#   session's start or at an image's build, where the launcher names the
#   release these files were proven against as the one to build with instead.
# - The update has a bound of time (HYPERFRAMES_UPDATE_SECONDS, 120), of
#   which the registry has 15 s to name the newest release. A registry that
#   does not answer, a download that stalls, or an install that fails leaves
#   the session on the release its image was built with, which the image's
#   build proved (`install.sh verify`), and says why in the status.
# - A deployment holds every session on one release with
#   MOODY_HYPERFRAMES_VERSION: a version such as 0.9.97, or `built` for the
#   image's own, which asks the network nothing.
#
# A release is a folder of its own, /opt/hyperframes/releases/VERSION: the
# CLI as npm installed it, and `skills`, the skills of that same release. The
# three core skills ship inside the npm package; the rest of the published set
# is read from the repository at the release's tag (`v<version>`, which is what
# the CLI's own `skills update` installs from), with only the `skills` folder
# fetched. Where the repository cannot be reached the core skills stand alone
# and the status says so. `current` is a link to the release in use and
# `built` to the image's; /opt/hyperframes/skills is `current/skills`, so the
# skills an agent reads are always those of the CLI it runs.
#
# `update` runs once a session, whoever asks first: the session's autostart,
# or the `hyperframes` command (run.sh), which waits for it, so a command
# never runs on one release while another is being switched in. It is a no-op
# after that, and a second caller waits for the first under a lock.

set -u -o pipefail

ROOT="/opt/hyperframes"
RELEASES="${ROOT}/releases"
STATE="/tmp/selkies-modal"
DONE="${STATE}/hyperframes-update.done"
LOCK="${STATE}/hyperframes-update.lock"
STATUS="${ROOT}/status.json"
BOUND="${HYPERFRAMES_UPDATE_SECONDS:-120}"
REPOSITORY="https://github.com/heygen-com/hyperframes"
# The CLI reports its use to its makers unless told not to; installing a release reports nothing
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_NO_UPDATE_CHECK=1 HYPERFRAMES_SKIP_SKILLS=1
REGISTRY=()
[ -z "${MOODY_HYPERFRAMES_REGISTRY-}" ] || REGISTRY=(--registry "${MOODY_HYPERFRAMES_REGISTRY}")

say() {
  echo "hyperframes: $*"
}

is_version() {
  [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
}

cli() {
  node "${RELEASES}/$1/node_modules/hyperframes/bin/hyperframes.mjs" "${@:2}"
}

# The name of the release a link points at, or nothing.
linked() {
  local target
  target="$(readlink "${ROOT}/$1" 2> /dev/null)" || return 1
  basename "${target}"
}

# Points a link at a release in one step, so no command ever finds it missing.
point() {
  ln -sfn "releases/$2" "${ROOT}/.$1.new" && mv -T "${ROOT}/.$1.new" "${ROOT}/$1"
}

# The skills of a release beyond the core ones its package carries: the
# `skills` folder of the repository at the release's tag, and nothing else of it.
all_skills() {
  local version=$1 into=$2 clone
  clone="$(mktemp -d)"
  if GIT_LFS_SKIP_SMUDGE=1 git clone --quiet --depth 1 --filter=blob:none --sparse \
    --branch "v${version}" "${REPOSITORY}" "${clone}" 2> /dev/null &&
    git -C "${clone}" sparse-checkout set skills 2> /dev/null && [ -d "${clone}/skills" ]; then
    cp -a "${clone}/skills/." "${into}/"
    rm -rf "${clone}"
    return 0
  fi
  rm -rf "${clone}"
  return 1
}

# Whether a release renders on this machine: half a second of the project its
# own `init` writes, to a video file that is there afterwards. Says the end of
# what the CLI printed where it does not.
renders() {
  local version=$1 proof status=1
  proof="$(mktemp -d)" || return 1
  if (cd "${proof}" && cli "${version}" init proof --non-interactive &&
    cli "${version}" render proof --quality draft --end 0.5 --quiet -o "${proof}/proof.mp4") > "${proof}/log" 2>&1 &&
    [ -s "${proof}/proof.mp4" ]; then
    status=0
  else
    tail -n 5 "${proof}/log" >&2
  fi
  rm -rf "${proof}"
  return "${status}"
}

install() {
  local version=$1 dir said
  is_version "${version}" || {
    say "${version} is not a release such as 0.9.97" >&2
    return 2
  }
  dir="${RELEASES}/${version}"
  [ -f "${dir}/.complete" ] && return 0
  rm -rf "${dir}"
  mkdir -p "${dir}/skills"
  npm install --prefix "${dir}" --no-audit --no-fund --loglevel=error "${REGISTRY[@]}" "hyperframes@${version}" || return 1
  said="$(cli "${version}" --version 2> /dev/null)"
  [ "${said}" = "${version}" ] || {
    say "release ${version} answers ${said:-nothing} for its version" >&2
    return 1
  }
  cp -a "${dir}/node_modules/hyperframes/dist/skills/." "${dir}/skills/" || return 1
  [ -f "${dir}/skills/hyperframes/SKILL.md" ] || {
    say "release ${version} carries no hyperframes skill" >&2
    return 1
  }
  if all_skills "${version}" "${dir}/skills"; then
    echo all > "${dir}/.skills"
  else
    echo core > "${dir}/.skills"
  fi
  cli "${version}" browser ensure || return 1
  renders "${version}" || {
    say "release ${version} did not render its own starting project" >&2
    return 1
  }
  touch "${dir}/.complete"
}

# Writes what runs and why. Arguments: running, built, newest, held, reason, seconds.
write_status() {
  jq -n --arg running "$1" --arg built "$2" --arg newest "$3" --arg held "$4" --arg reason "$5" \
    --argjson seconds "$6" --arg skills "$(cat "${RELEASES}/$1/.skills" 2> /dev/null || echo core)" \
    --arg checked "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{running: $running, built: $built, newest: (if $newest == "" then null else $newest end),
      held: (if $held == "" then null else $held end), updated: ($running != $built), skills: $skills,
      reason: $reason, seconds: $seconds, checked_at: $checked}' > "${STATUS}.new" &&
    mv "${STATUS}.new" "${STATUS}"
}

update() {
  local built want target newest="" held="" reason started left failed
  mkdir -p "${STATE}"
  exec 9> "${LOCK}"
  flock 9
  [ -f "${DONE}" ] && return 0
  started="$(date +%s)"
  built="$(linked built)" || {
    say "the image has no release" >&2
    return 1
  }
  want="${MOODY_HYPERFRAMES_VERSION:-latest}"
  target="${built}"
  case "${want}" in
    built)
      held="${built}"
      reason="held on the image's release"
      ;;
    latest)
      newest="$(timeout 15 npm view "${REGISTRY[@]}" hyperframes version 2> /dev/null)"
      failed=$?
      if is_version "${newest}"; then
        target="${newest}"
        reason="the newest release"
      elif [ "${failed}" -eq 124 ]; then
        newest=""
        reason="the registry did not answer within 15 s, so the image's release runs"
      else
        newest=""
        reason="the registry named no newest release, so the image's release runs"
      fi
      ;;
    *)
      if is_version "${want}"; then
        held="${want}"
        target="${want}"
        reason="held on ${want}"
      else
        reason="MOODY_HYPERFRAMES_VERSION=${want} is not a release, so the image's release runs"
      fi
      ;;
  esac
  if [ "${target}" != "${built}" ] && [ ! -f "${RELEASES}/${target}/.complete" ]; then
    say "installing release ${target} (the image has ${built})"
    left="$((BOUND - ($(date +%s) - started)))"
    failed=124
    [ "${left}" -lt 1 ] || {
      timeout "${left}" "$0" install "${target}"
      failed=$?
    }
    if [ "${failed}" -ne 0 ]; then
      rm -rf "${RELEASES:?}/${target}"
      if [ "${failed}" -eq 124 ]; then
        reason="release ${target} was not installed within ${BOUND} s, so the image's release runs"
      else
        reason="release ${target} could not be installed, so the image's release runs"
      fi
      target="${built}"
    fi
  fi
  point current "${target}"
  write_status "${target}" "${built}" "${newest}" "${held}" "${reason}" "$(($(date +%s) - started))"
  say "running release ${target}: ${reason}"
  touch "${DONE}"
}

case "${1-}" in
  install)
    install "${2-}"
    ;;
  build)
    for version in "${@:2}"; do
      if install "${version}"; then
        point built "${version}" && point current "${version}" && ln -sfn current/skills "${ROOT}/skills" &&
          write_status "${version}" "${version}" "" "" "the release the image was built with" 0
        exit $?
      fi
      rm -rf "${RELEASES:?}/${version}"
    done
    exit 1
    ;;
  update)
    update
    ;;
  status)
    cat "${STATUS}"
    ;;
  *)
    sed -n '/^#     hyperframes-release/s/^#     //p' "$0" >&2
    exit 2
    ;;
esac
