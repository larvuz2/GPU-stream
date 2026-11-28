#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Puts v2 into a session image, each step run once as the image is built
# (sandbox.py, `with_v2`):
#
#     install.sh build COMMIT GO_VERSION GO_SHA256 NODE_VERSION NODE_SHA256
#     install.sh verify
#
# v2 (github.com/agentnativeinc/v2, MIT) keeps the versions of a video an agent
# makes, the text through Git and the media in a store of its own, and serves
# a page on which a person watches a version, compares two, and leaves
# comments at a moment of the video. It is one Go program with that page
# embedded, and it runs Git and FFmpeg, which are the base image's.
#
# - `build` makes the program from its source at one commit, since the image
#   takes nothing its maker's site hands out. Everything the build needs is
#   fetched into one temporary folder, where the tools also keep their caches
#   and temporary files, and goes with it when the step ends, so the layer
#   keeps the program and nothing it was built with: Go's and Node.js's own
#   Linux builds, each checked against the hash its publisher lists (go.dev,
#   nodejs.org); the source, fetched by the commit's own name and refused
#   unless the checkout answers with it; the page's packages, as the source's
#   lockfile names them and with no package's install script run; and Go's
#   modules, held to the source's `go.sum`. The build's own Node.js is fetched
#   even where the image has one, so every image is built by the same steps
#   on the same tools, and the program comes out the same file whichever image
#   builds it. What stays is /opt/v2/bin/v2, the source's license at
#   /opt/v2/LICENSE, and the commit at /opt/v2/COMMIT.
#
#   No version is linked in, so the program reports `dev`, and for `dev` it
#   skips the check for a newer release it otherwise makes once a day, the one
#   request it sends without being asked.
# - `verify` fails the build unless the command a session runs (run.sh, at
#   /usr/local/bin/v2) answers as that build, refuses a command that reaches
#   the maker's site, and, as the session's user in a temporary folder, makes
#   a project, saves a version with a clip in it, lists it, and serves the
#   versions page; and unless the browser that page is shown in
#   (versions.sh) finds every library it links.
set -eu

HOME_DIR="/opt/v2"
REPOSITORY="https://github.com/agentnativeinc/v2"
CHROME="/opt/hyperframes/chrome/chrome"

# Downloads $1 to $2 and fails unless its SHA-256 is $3.
fetch() {
  curl -fsSL --retry 3 -o "$2" "$1"
  echo "$3  $2" | sha256sum -c - > /dev/null || {
    echo "v2: $1 does not have the checksum $3" >&2
    exit 1
  }
}

case "${1-}" in
  build)
    commit="$2"
    go_version="$3"
    go_sha256="$4"
    node_version="$5"
    node_sha256="$6"
    work="$(mktemp -d)"
    trap 'rm -rf "${work}"' EXIT
    fetch "https://go.dev/dl/go${go_version}.linux-amd64.tar.gz" "${work}/go.tar.gz" "${go_sha256}"
    fetch "https://nodejs.org/dist/v${node_version}/node-v${node_version}-linux-x64.tar.xz" "${work}/node.tar.xz" "${node_sha256}"
    mkdir "${work}/node"
    tar -xzf "${work}/go.tar.gz" -C "${work}"
    tar -xJf "${work}/node.tar.xz" -C "${work}/node" --strip-components=1

    git init -q "${work}/source"
    git -C "${work}/source" fetch -q --depth 1 "${REPOSITORY}" "${commit}"
    git -C "${work}/source" checkout -q FETCH_HEAD
    at="$(git -C "${work}/source" rev-parse HEAD)"
    [ "${at}" = "${commit}" ] || {
      echo "v2: the source is at ${at}, not at the pinned ${commit}" >&2
      exit 1
    }

    export PATH="${work}/go/bin:${work}/node/bin:${PATH}"
    # Every cache under the folder that goes, Node.js's compile cache among them, which it keeps in the temporary
    # folder; and no toolchain but the one fetched above
    mkdir "${work}/tmp"
    export HOME="${work}/home" TMPDIR="${work}/tmp" npm_config_cache="${work}/npm"
    export GOPATH="${work}/gopath" GOCACHE="${work}/gocache" GOTOOLCHAIN=local GOFLAGS=-mod=readonly CGO_ENABLED=0
    (cd "${work}/source/web" && npm ci --ignore-scripts --no-audit --no-fund && npx --no-install vite build)
    (cd "${work}/source" && go build -trimpath -o "${work}/v2" ./cmd/v2)

    install -D -m 755 "${work}/v2" "${HOME_DIR}/bin/v2"
    install -m 644 "${work}/source/LICENSE" "${HOME_DIR}/LICENSE"
    printf '%s\n' "${commit}" > "${HOME_DIR}/COMMIT"
    echo "v2: built ${commit} with Go ${go_version} and Node.js ${node_version}, $(stat -c %s "${HOME_DIR}/bin/v2") bytes"
    ;;
  verify)
    as_user="setpriv --reuid=1000 --regid=1000 --init-groups env HOME=/home/ubuntu"
    for kept in LICENSE COMMIT; do
      [ -s "${HOME_DIR}/${kept}" ] || {
        echo "v2: ${HOME_DIR}/${kept}, the source's license and the commit built, is not there" >&2
        exit 1
      }
    done
    said="$(${as_user} v2 --version)"
    [ "${said}" = "v2 version dev" ] || {
      echo "v2: the build has to report itself as dev, which is what keeps it from asking for releases; it says: ${said}" >&2
      exit 1
    }
    refused=0
    ${as_user} v2 push > /dev/null 2>&1 || refused=$?
    [ "${refused}" -eq 2 ] || {
      echo "v2: push has to be refused with status 2, and ended with ${refused}" >&2
      exit 1
    }
    [ -x "${CHROME}" ] || {
      echo "v2: the browser the versions page is shown in is not at ${CHROME}" >&2
      exit 1
    }
    missing="$(ldd "${CHROME}" 2> /dev/null | grep 'not found' || true)"
    [ -z "${missing}" ] || {
      echo "v2: ${CHROME} lacks libraries:" >&2
      echo "${missing}" >&2
      exit 1
    }
    proof="$(${as_user} mktemp -d)"
    trap 'rm -rf "${proof}"' EXIT
    # shellcheck disable=SC2016  # the script is the session user's shell's to expand
    ${as_user} sh -eu -c '
      cd "$1"
      v2 init
      ffmpeg -loglevel error -f lavfi -i testsrc2=size=320x180:rate=24:duration=1 -pix_fmt yuv420p out/final.mp4
      v2 save -m "the proof clip" --prompt "prove that a version saves" --change "video out/final.mp4: a second of test picture"
      v2 log | grep -q "^v1 "
      v2 diff --no-open --port 3010 > diff.log 2>&1 &
      server=$!
      answered=""
      for _ in $(seq 1 40); do
        if curl -fsS -m 2 http://127.0.0.1:3010/api/versions 2> /dev/null | grep -q "\"version\":\"v1\""; then
          answered=1
          break
        fi
        sleep 0.25
      done
      page=""
      [ -z "${answered}" ] || page="$(curl -fsS -m 2 http://127.0.0.1:3010/ || true)"
      kill "${server}"
      case "${page}" in
        *"<html"*) ;;
        *)
          echo "v2: the versions page did not answer:" >&2
          cat diff.log >&2
          exit 1
          ;;
      esac
    ' sh "${proof}"
    echo "v2: $(cat "${HOME_DIR}/COMMIT") saves a version and serves its page as the session's user"
    ;;
  *)
    sed -n '/^#     install.sh/s/^#     //p' "$0" >&2
    exit 2
    ;;
esac
