#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# What listens on the Unreal view's port (SELKIES_MODAL_UNREAL_VIEW_PORT, 8090),
# the second page of an Unreal session beside its desktop, which the launcher
# links to with a connect token of its own (`unreal_view_link`). The s6 service
# `unreal-view` runs this (view/run), and restarts it whenever it exits.
#
# The port has one owner at a time, and switching the page is changing that
# owner, never the link: the state file names the server, and whoever changes it
# restarts the service (`s6-svc -r /etc/service/unreal-view`), which runs this
# again to start the other one. Modal's connect token is the page's only
# credential, so whichever server owns the port needs no login of its own.
#
# - `placeholder` (or no state): a page saying Unreal is not open yet, and to
#   clone the project on the desktop and ask the agent to open it (serve.py).
#   It asks for itself every few seconds and reloads once another server
#   answers, so an open page turns into the editor's stream by itself.
# - `player`, once `selkies-modal-unreal-open` has started an editor and the
#   image has a player: `selkies-modal-unreal-player PORT`.
#
# The player is not built yet. The plan for it, once an editor can be pulled:
#
# 1. Epic's Pixel Streaming infrastructure for the engine's version, the
#    signalling server (Wilbur) and its player page (MIT, the
#    EpicGamesExt/PixelStreamingInfrastructure branch of that version), with
#    Node.js, installed in `unreal_image` over the engine layer, and
#    `selkies-modal-unreal-player` starting it with its player on this port and
#    its streamer port on loopback (8888), where the editor's Pixel Streaming 2
#    connects (`-PixelStreamingURL`, open.sh).
# 2. The stream's media through the session's TURN relay (`with_turn`): the
#    session is started with `tcp_ports=(TURN_PORT,)`, the launcher writes the
#    relay's public address (`tcp_address`) into the Sandbox, and the player is
#    handed the ICE server `selkies-modal-turn-credentials HOST:PORT` prints
#    with `iceTransportPolicy: "relay"` (the signalling server's peer options),
#    since Modal's proxy carries the page and its WebSocket but no UDP.
# 3. A page connected to the player counts as use of the session, as input on
#    the desktop does (session.sh), so a session someone works in through the
#    Unreal view alone does not end for want of input.
set -u

port="${SELKIES_MODAL_UNREAL_VIEW_PORT:-8090}"
state="/tmp/selkies-modal/unreal/view"
share="/usr/local/share/selkies-modal/unreal/view"

if [ "$(cat "${state}" 2> /dev/null)" = player ]; then
  if command -v selkies-modal-unreal-player > /dev/null; then
    exec selkies-modal-unreal-player "${port}"
  fi
  echo "[unreal-view] the state asks for the player, which this image does not have; serving the page" >&2
fi
exec python3 -I "${share}/serve.py" "${port}" "${share}/index.html"
