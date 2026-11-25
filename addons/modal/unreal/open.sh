#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Opens an Unreal project in the session's Unreal Editor, which runs off screen
# and streams itself to the Unreal view:
#
#     selkies-modal-unreal-open PATH/TO/GAME.uproject
#
# It checks, in this order, and stops at the first that fails, with a status of
# its own and what the person can do, never presenting a project as open when
# it is not:
#
#   2  The argument is not a .uproject in the workspace.
#   3  The editor is not installed in this machine. An image has it only where
#      it was built with the user's own Epic-linked GitHub credential
#      (`unreal_image` in sandbox.py); the message says how to get there.
#   4  The machine has no GPU, which the editor renders and encodes on.
#   5  The project was saved by a newer Unreal than this editor, which does not
#      open it. An older one opens, and the editor upgrades what it saves.
#   1  The editor, or the build of the project's C++ before it, exited within
#      the first START_SECONDS, with the end of its log.
#   0  It is running: building the project's C++ modules first where it has
#      any, then the editor. It runs as the session job `unreal-editor`
#      (`selkies-modal-job status|log|stop unreal-editor`), which counts as use
#      of the session for as long as it runs.
#
# The editor is Epic's own, in /opt/unreal, started on the project with:
#
# - `-RenderOffScreen`: no window, since the GPU cannot present into the
#   session's display in a Sandbox (moody/UNREAL.md); "Run the Unreal Engine
#   application headless, without any visible rendering at all on the local
#   computer" (Epic's Pixel Streaming reference).
# - Editor streaming of the Pixel Streaming 2 plugin, which Epic's "Pixel
#   Streaming in the editor" page documents with these flags:
#   `-EditorPixelStreamingStartOnLaunch=true` (needed with -RenderOffScreen),
#   `-EditorPixelStreamingRes`, `-EditorPixelStreamingUseRemoteSignallingServer=true`,
#   and `-PixelStreamingURL`, the signalling server on loopback the Unreal
#   view's player is to run (view/view.sh). The editor's embedded viewer would
#   take port 8080 on Linux, which is Selkies'.
# - Unreal MCP, Epic's MCP server in the editor (5.8, experimental), which binds
#   127.0.0.1 and has no authentication, so nothing outside the machine reaches
#   it: `-ModelContextProtocolStartServer` and `-ModelContextProtocolPort`, the
#   flags of Epic's Unreal MCP page.
# - `-EnablePlugins`, which the engine's plugin manager reads, so the plugins
#   above, Python, and the Remote Control API the Blender bridge calls run
#   without changing the team's .uproject. The Unreal MCP plugin's name is taken
#   from its console commands (`ModelContextProtocol.*`); Epic's page does not
#   spell it out, and no editor has run here yet to confirm any of this.
#
# The bridge to Blender: the editor finds `init_unreal.py` and
# `send_to_blender.py` on UE_PYTHONPATH, and the Remote Control settings Send
# to Unreal needs are written into the project's Config folder where it has no
# such file of its own, and kept out of the team's repository by the clone's
# own `.git/info/exclude`, so the GitHub client never offers them as a change.
#
# A project with C++ modules is built first with Epic's Build.sh for its
# editor target, since an editor that finds its modules missing asks to build
# them in a window nobody can see off screen.
set -u

ENGINE=/opt/unreal
EDITOR_BINARY="${ENGINE}/Engine/Binaries/Linux/UnrealEditor"
BUILD="${ENGINE}/Engine/Build/BatchFiles/Linux/Build.sh"
SHARE=/usr/local/share/selkies-modal/unreal
SIGNALLING_URL=ws://127.0.0.1:8888
MCP_PORT=8000
RESOLUTION=1920x1080
PLUGINS=PixelStreaming2,PythonScriptPlugin,RemoteControl,ModelContextProtocol
JOB=unreal-editor
START_SECONDS=20

say() {
  echo "selkies-modal-unreal-open: $*" >&2
}

# The field of a .uproject, which Unreal may write with a byte order mark
descriptor_field() {
  python3 -I -c '
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8-sig")).get(sys.argv[2])
print(value if isinstance(value, str) else len(value or []))
' "$1" "$2" 2> /dev/null
}

# The job itself, as `selkies-modal-job` runs it: the C++ build where there is
# one, then the editor in this process's place.
if [ "${1-}" = "--run" ]; then
  project=$2
  name="$(basename "${project}" .uproject)"
  if [ "$(descriptor_field "${project}" Modules)" != 0 ]; then
    echo "Building ${name}'s C++ modules for this editor"
    "${BUILD}" "${name}Editor" Linux Development "-Project=${project}" -WaitMutex || exit
  fi
  export UE_PYTHONPATH="${SHARE}${UE_PYTHONPATH:+:${UE_PYTHONPATH}}"
  exec "${EDITOR_BINARY}" "${project}" \
    -RenderOffScreen \
    -EditorPixelStreamingStartOnLaunch=true \
    "-EditorPixelStreamingRes=${RESOLUTION}" \
    -EditorPixelStreamingUseRemoteSignallingServer=true \
    "-PixelStreamingURL=${SIGNALLING_URL}" \
    -ModelContextProtocolStartServer \
    "-ModelContextProtocolPort=${MCP_PORT}" \
    "-EnablePlugins=${PLUGINS}"
fi

if [ "$#" -ne 1 ]; then
  echo "usage: selkies-modal-unreal-open PATH/TO/GAME.uproject" >&2
  exit 2
fi
# Whether the project is in the workspace is decided on the paths with every link resolved, so a
# link cannot lead out of it; the path as given, made absolute, is the one shown and opened
workspace="$(realpath -e "${SELKIES_MODAL_WORKSPACE:-${HOME}}")" || exit 2
resolved="$(realpath -e -- "$1" 2> /dev/null)" || {
  say "$1 does not exist"
  exit 2
}
case "${resolved}" in
  "${workspace}"/*.uproject) ;;
  *)
    say "$1 is not a .uproject in the workspace (${SELKIES_MODAL_WORKSPACE:-${HOME}}); selkies-modal-unreal-projects lists them"
    exit 2
    ;;
esac
project="$(realpath -s -- "$1")"
[[ "${project}" == *.uproject ]] || project="${resolved}"
name="$(basename "${project}" .uproject)"
folder="$(dirname "${project}")"

if [ ! -x "${EDITOR_BINARY}" ]; then
  cat >&2 << EOF
selkies-modal-unreal-open: the Unreal Editor is not installed in this machine yet, so ${name} was not opened.

Epic hands out the Linux editor only to people with an Epic Games account
linked to GitHub, so Moody pulls it for you, with your own GitHub account:

  1. Link your GitHub account to your Epic Games account, on
     https://www.unrealengine.com/en-US/ue-on-github, and accept the invitation
     to the EpicGames organization that GitHub then emails you.
  2. In Moody, connect GitHub again, so that Moody may read Epic's packages.
  3. Start Unreal again. That machine comes with the editor, about 40 GB,
     fetched once for you and kept for your later starts.
EOF
  exit 3
fi

if ! nvidia-smi -L > /dev/null 2>&1; then
  say "this machine has no GPU, and the Unreal Editor renders and streams on one; start Unreal on a GPU, then open ${name} again"
  exit 4
fi

engine="$(jq -r '"\(.MajorVersion).\(.MinorVersion)"' "${ENGINE}/Engine/Build/Build.version" 2> /dev/null)"
saved="$(descriptor_field "${project}" EngineAssociation)"
if [[ "${saved}" =~ ^[0-9]+\.[0-9]+$ ]]; then
  if [ "${saved}" != "${engine}" ] && [ "$(printf '%s\n%s\n' "${saved}" "${engine}" | sort -V | tail -n 1)" = "${saved}" ]; then
    say "${name} was saved with Unreal ${saved}, newer than this editor (${engine}), and Unreal does not open a project in an older editor"
    exit 5
  fi
  [ "${saved}" = "${engine}" ] ||
    say "${name} was saved with Unreal ${saved}; this editor is ${engine} and upgrades what it saves, which ${saved} cannot open again, so keep that work on a branch of its own"
else
  say "${name} names no released engine (${saved:-none}), as a source build's project does; opening it with ${engine}"
fi

# The Remote Control settings Send to Unreal needs, where the project has none of its own
config="${folder}/Config/DefaultRemoteControl.ini"
if [ ! -e "${config}" ]; then
  mkdir -p "${folder}/Config" && cp "${SHARE}/DefaultRemoteControl.ini" "${config}"
  top="$(git -C "${folder}" rev-parse --show-toplevel 2> /dev/null)"
  exclude="$(git -C "${folder}" rev-parse --path-format=absolute --git-path info/exclude 2> /dev/null)"
  if [ -n "${top}" ] && [ -n "${exclude}" ]; then
    entry="/$(realpath --relative-to="${top}" "${config}")"
    mkdir -p "$(dirname "${exclude}")"
    grep -qxF "${entry}" "${exclude}" 2> /dev/null || echo "${entry}" >> "${exclude}"
  fi
fi

selkies-modal-job start "${JOB}" -- "$0" --run "${project}" > /dev/null || exit 1
for _ in $(seq 1 "${START_SECONDS}"); do
  sleep 1
  case "$(selkies-modal-job status "${JOB}" | cut -f 2)" in
    running) ;;
    *)
      say "the editor ended as it started ($(selkies-modal-job status "${JOB}" | cut -f 2)); the end of its log:"
      LINES=30 selkies-modal-job log "${JOB}" >&2
      exit 1
      ;;
  esac
done

if [ "$(descriptor_field "${project}" Modules)" != 0 ]; then
  echo "${name} is building its C++ modules, which takes longest the first time, and then opens in the Unreal Editor ${engine}."
else
  echo "${name} is opening in the Unreal Editor ${engine}."
fi
echo "It runs as the session job ${JOB}: selkies-modal-job status ${JOB}, selkies-modal-job log ${JOB}."
echo "Unreal MCP: http://127.0.0.1:${MCP_PORT}/mcp; Remote Control: http://127.0.0.1:30010 (inside this machine only)."
if command -v selkies-modal-unreal-player > /dev/null; then
  mkdir -p /tmp/selkies-modal/unreal && echo player > /tmp/selkies-modal/unreal/view
  s6-svc -r /etc/service/unreal-view
  echo "The Unreal view shows the editor once it streams."
else
  echo "The editor streams to ${SIGNALLING_URL}, but this image has no Pixel Streaming player yet, so the Unreal view keeps its page."
fi
