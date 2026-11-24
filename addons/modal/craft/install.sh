#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Installs an ArtCraft application's Linux release into the session image, run
# once as the image is built, through `selkies-privileged-files run`
# (sandbox.py), as every package layer on the base image is:
#
#     install.sh filmcraft 0.20.1 <sha256 of filmcraft-0.20.1-linux-x86_64.deb>
#
# The release is the Debian package from the application's GitHub release,
# checked against the hash its SHA256SUMS.txt publishes before apt sees it, and
# installed with apt so that the windowing and graphics libraries it loads at
# run time come with it. Beside it:
#
# - zenity, which the application's file dialogs fall back to where no desktop
#   portal answers, as none does in a session;
# - xprintidle, which reads the display's idle counter for the idle timeout
#   (session.sh).
set -eu

app="$1"
version="$2"
sha256="$3"
package="${app}-${version}-linux-x86_64.deb"

download="$(mktemp -d)"
curl -fsSL -o "${download}/${package}" "https://github.com/storytold/${app}/releases/download/v${version}/${package}"
echo "${sha256}  ${download}/${package}" | sha256sum -c -

apt-get update
apt-get install --no-install-recommends -y "${download}/${package}" zenity xprintidle
apt-get clean
rm -rf /var/lib/apt/lists/* "${download}"
