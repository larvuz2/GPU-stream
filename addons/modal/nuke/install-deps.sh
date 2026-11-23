#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# The packages of the Nuke session image, run once as the image is built,
# through `selkies-privileged-files run` (sandbox.py), as every package layer on
# the base image is. Nuke itself is not here: Foundry hands it out behind a
# login and a license its user accepts, so it is installed in the session, into
# the workspace (setup.sh). What is here is what that install runs on:
#
# - Firefox, from Mozilla's own repository with its signing key checked against
#   the fingerprint Mozilla publishes (as addons/desktop does), so the user can
#   sign in to Foundry and download Nuke inside the session rather than upload
#   several gigabytes through the page.
# - zenity for the setup's windows, xdotool to drive them in a test,
#   xprintidle for the idle timeout (session.sh), and rclone, which moves a
#   team's footage between Google Drive and the workspace from inside the
#   session, at the data center's speed rather than an uploader's.
# - The libraries Nuke and the Qt it ships with load from the system on Linux:
#   NUMA, GLU, the XCB extensions Qt's xcb platform opens, and what the
#   Chromium of Foundry's licensing window needs.
set -eu

mkdir -p /etc/apt/keyrings /etc/apt/sources.list.d /etc/apt/preferences.d
chmod 755 /etc/apt/keyrings /etc/apt/sources.list.d /etc/apt/preferences.d
fetch-verified key "https://packages.mozilla.org/apt/repo-signing-key.gpg" \
    35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3 /etc/apt/keyrings/packages.mozilla.org.asc
printf 'Types: deb\nURIs: https://packages.mozilla.org/apt\nSuites: mozilla\nComponents: main\nSigned-By: /etc/apt/keyrings/packages.mozilla.org.asc\n' \
    > /etc/apt/sources.list.d/mozilla.sources
printf 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' > /etc/apt/preferences.d/mozilla

apt-get update
apt-get install --no-install-recommends -y \
    firefox zenity xdotool xprintidle rclone \
    libnuma1 libglu1-mesa libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 \
    libnss3 libasound2t64 libxcomposite1 libxdamage1 libxtst6 libxrandr2 libxkbfile1 libxss1
apt-get clean
rm -rf /var/lib/apt/lists/*
