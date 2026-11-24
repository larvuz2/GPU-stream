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
# Then the client's clone dialog is made to offer the session's folder
# (SELKIES_MODAL_CLONE_DIR, which github.sh sets) before the folder the client
# last cloned into: Desktop Plus otherwise offers that, or Documents/GitHub, and
# keeps no setting for it outside its own browser storage. The change is to one
# function of its bundled code, found by its shape: a version whose code is not
# that shape fails the build here, rather than offering the wrong folder.
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

python3 - /usr/lib/desktop-plus/resources/app/renderer.js << 'EOF'
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as file:
    code = file.read()
# async function uE(e){return(e?localStorage.getItem(hE(e)):null)||await lE()}: the folder the clone
# dialog offers, the account's last one, else the last one, else Documents/GitHub
shape = re.compile(
    r"(async function \w+\((\w+)\)\{return)(\(\2\?localStorage\.getItem\(\w+\(\2\)\):null\)\|\|await \w+\(\)\})"
)
code, count = shape.subn(r"\1 process.env.SELKIES_MODAL_CLONE_DIR||\3", code)
if count != 1:
    sys.exit(f"install.sh: the clone dialog's default folder is not where this expects in {path} ({count} found)")
with open(path, "w", encoding="utf-8") as file:
    file.write(code)
EOF
