#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Builds the HyperFrames session image, one step per layer, each run once as
# the image is built (sandbox.py, `hyperframes_image`):
#
#     install.sh packages
#     install.sh node VERSION SHA256
#     install.sh chrome VERSION SHA256
#     install.sh verify
#
# The versions and checksums are the launcher's (the `HYPERFRAMES_` constants
# of sandbox.py). What each step puts where:
#
# - `packages`, through `selkies-privileged-files run` as every package layer
#   on the base image is: the shared libraries a Chrome needs to start, which
#   the renderer's headless one and the preview's windowed one both load;
#   xprintidle for the idle timeout (session.sh); and xterm, in which the
#   session shows its log (autostart). FFmpeg, Git, and curl are the base
#   image's own.
# - `node`: Node.js's own Linux build, checked against the hash nodejs.org
#   publishes, at /opt/hyperframes/node, with `node`, `npm`, and `npx` linked
#   into /usr/local/bin.
# - `chrome`: Chrome for Testing, Google's build of Chrome for automated use,
#   checked against the hash given, at /opt/hyperframes/chrome. It is the
#   browser the live preview opens in on the session's screen, and the versions
#   page of v2 (kiosk.sh); the Cut Room's image runs this step and `packages`
#   for that page alone (sandbox.py, `cutroom_tools`). The renderer's headless
#   browser is not this one: the HyperFrames CLI downloads the build each of
#   its releases was tested with (release.sh).
# - `verify`: fails the build unless Node runs, both browsers find every
#   library they link, and the CLI the image was built with answers with its
#   version and lists its skills. Run after the release is installed.
#
# The HyperFrames CLI itself is not installed here. It is the one part of the
# image that follows its upstream instead of a pin: release.sh installs a
# release, at build and again as a session starts.
set -eu

HOME_DIR="/opt/hyperframes"

# Downloads $1 to $2 and fails unless its SHA-256 is $3.
fetch() {
  curl -fsSL --retry 3 -o "$2" "$1"
  echo "$3  $2" | sha256sum -c - > /dev/null || {
    echo "hyperframes: $1 does not have the checksum $3" >&2
    exit 1
  }
}

# Fails where a program links a library the image lacks, naming each.
linked() {
  missing="$(ldd "$1" 2> /dev/null | grep 'not found' || true)"
  [ -z "${missing}" ] || {
    echo "hyperframes: $1 lacks libraries:" >&2
    echo "${missing}" >&2
    exit 1
  }
}

case "${1-}" in
  packages)
    apt-get update
    apt-get install --no-install-recommends -y \
      xprintidle xterm unzip xz-utils \
      libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 libxkbcommon0 \
      libatspi2.0-0t64 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
      libcairo2 libasound2t64 libgtk-3-0t64 libxshmfence1
    apt-get clean
    rm -rf /var/lib/apt/lists/*
    ;;
  node)
    version="$2"
    sha256="$3"
    download="$(mktemp -d)"
    fetch "https://nodejs.org/dist/v${version}/node-v${version}-linux-x64.tar.xz" "${download}/node.tar.xz" "${sha256}"
    mkdir -p "${HOME_DIR}/node"
    tar -xJf "${download}/node.tar.xz" -C "${HOME_DIR}/node" --strip-components=1
    rm -rf "${download}"
    for program in node npm npx; do
      ln -sf "${HOME_DIR}/node/bin/${program}" "/usr/local/bin/${program}"
    done
    node --version
    ;;
  chrome)
    version="$2"
    sha256="$3"
    download="$(mktemp -d)"
    fetch "https://storage.googleapis.com/chrome-for-testing-public/${version}/linux64/chrome-linux64.zip" \
      "${download}/chrome.zip" "${sha256}"
    unzip -q "${download}/chrome.zip" -d "${download}"
    mkdir -p "${HOME_DIR}"
    rm -rf "${HOME_DIR}/chrome"
    mv "${download}/chrome-linux64" "${HOME_DIR}/chrome"
    rm -rf "${download}"
    ;;
  verify)
    as_user="setpriv --reuid=1000 --regid=1000 --init-groups env HOME=/home/ubuntu"
    node --version
    linked "${HOME_DIR}/chrome/chrome"
    shell="$(${as_user} hyperframes browser path | tail -n 1)"
    [ -x "${shell}" ] || {
      echo "hyperframes: the CLI's headless browser is not in the image (it says: ${shell})" >&2
      exit 1
    }
    linked "${shell}"
    built="$(basename "$(readlink "${HOME_DIR}/built")")"
    said="$(${as_user} hyperframes --version)"
    [ "${said}" = "${built}" ] || {
      echo "hyperframes: built with ${built}, but the CLI says ${said}" >&2
      exit 1
    }
    [ -f "${HOME_DIR}/skills/hyperframes/SKILL.md" ] || {
      echo "hyperframes: the release's skills are not at ${HOME_DIR}/skills" >&2
      exit 1
    }
    skills=""
    for skill in "${HOME_DIR}"/skills/*/; do
      skills="${skills} $(basename "${skill}")"
    done
    echo "hyperframes: CLI ${built}, skills:${skills}"
    ;;
  *)
    sed -n '/^#     install.sh/s/^#     //p' "$0" >&2
    exit 2
    ;;
esac
