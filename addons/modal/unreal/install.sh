#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# The packages of the Unreal session's desktop, run once as the image is built,
# through `selkies-privileged-files run` (sandbox.py), as every package layer on
# the base image is:
#
#     install.sh DESKTOP_PLUS_VERSION DESKTOP_PLUS_SHA256
#
# - The GitHub client: Desktop Plus, a fork of GitHub Desktop kept current with
#   it (3.6 now, the version a studio runs on Windows) that publishes Linux
#   packages, from its GitHub release, checked against the hash the release
#   lists. The Linux fork of GitHub Desktop people know, shiftkey/desktop,
#   installs and opens on this Ubuntu too, but its last release is 3.4.13 of
#   February 2025, two minor versions behind, with the Electron of then holding
#   the team's GitHub token, and its tracker has open sign-in failures on Ubuntu
#   and points to Desktop Plus. Both keep the sign-in in the desktop's Secret
#   Service, hence GNOME's keyring and its command-line client.
# - Git LFS, which Unreal repositories keep their assets in.
# - Firefox, from Mozilla's own repository with its signing key checked against
#   the fingerprint Mozilla publishes, for GitHub's and Epic's sign-ins. The
#   Nuke image installs it the same way; the steps are repeated rather than
#   shared, since changing the Nuke image's script rebuilds that image.
# - zenity for the session's line of instructions, and xdotool to wait for the
#   client's window before it.
#
# What the session changes in the client's bundled code is desktop-plus.py's,
# a layer of its own above this one.
set -eu

version="$1"
sha256="$2"
package="DesktopPlus-v${version}-linux-x86_64.deb"

mkdir -p /etc/apt/keyrings /etc/apt/sources.list.d /etc/apt/preferences.d
chmod 755 /etc/apt/keyrings /etc/apt/sources.list.d /etc/apt/preferences.d
fetch-verified key "https://packages.mozilla.org/apt/repo-signing-key.gpg" \
  35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3 /etc/apt/keyrings/packages.mozilla.org.asc
printf 'Types: deb\nURIs: https://packages.mozilla.org/apt\nSuites: mozilla\nComponents: main\nSigned-By: /etc/apt/keyrings/packages.mozilla.org.asc\n' \
  > /etc/apt/sources.list.d/mozilla.sources
printf 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' > /etc/apt/preferences.d/mozilla

download="$(mktemp -d)"
curl -fsSL -o "${download}/${package}" "https://github.com/desktop-plus/desktop-plus/releases/download/v${version}/${package}"
echo "${sha256}  ${download}/${package}" | sha256sum -c -

apt-get update
apt-get install --no-install-recommends -y \
  firefox git-lfs gnome-keyring libsecret-tools zenity xdotool "${download}/${package}"
apt-get clean
rm -rf /var/lib/apt/lists/* "${download}"

