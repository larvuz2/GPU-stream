#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Builds the Cut Room's session image, one step per layer, each run once as the
# image is built (sandbox.py, `cutroom_image`):
#
#     install.sh packages
#     install.sh python LOCK
#     install.sh fonts INTER_VERSION INTER_SHA256 ARCHIVO_COMMIT ARCHIVO_SHA256 ARCHIVO_LICENSE_SHA256
#     install.sh whisper NAME REVISION MODEL_SHA256
#     install.sh yunet REVISION SHA256
#     install.sh verify
#
# Every version and checksum is the launcher's (the `CUTROOM_` constants of
# sandbox.py), so a pin moves in one place. What each step puts where:
#
# - `packages`, through `selkies-privileged-files run` as every package layer
#   on the base image is: Python's venv module, xprintidle for the idle timeout
#   (session.sh), and xterm, in which the session shows its log (autostart).
#   FFmpeg is the base image's own, which is pinned by the base's digest.
# - `python`: a virtual environment at /opt/cutroom/venv with exactly the
#   wheels LOCK names, each checked against its hash (`--require-hashes`) and
#   none built from source.
# - `fonts`: Inter's static OpenType faces from the release archive of
#   github.com/rsms/inter, into /usr/share/fonts/opentype/inter (where the
#   distribution's own package puts them, and where explainer.py measures
#   Inter Black from), and Archivo Black from github.com/google/fonts at one
#   commit, into /usr/share/fonts/truetype/archivo-black. Both are under the
#   SIL Open Font License 1.1, whose text goes beside each as it requires.
# - `whisper`: one CTranslate2 conversion of OpenAI's Whisper from
#   huggingface.co/Systran/faster-whisper-NAME at REVISION, into
#   /opt/cutroom/models/faster-whisper-NAME, where the scripts load it from, so
#   no session fetches a model. The weights are checked against MODEL_SHA256.
# - `yunet`: the face detector the webcam finder runs, from
#   huggingface.co/opencv/face_detection_yunet at REVISION.
# - `verify`: fails the build unless FFmpeg has every filter and encoder the
#   scripts call, fontconfig finds both families, the packages import, and a
#   speech model loads from the image.
#
# What was installed is listed in /opt/cutroom/provenance.txt, one line per
# part with its source and checksum.
set -eu

HOME_DIR="/opt/cutroom"
MODELS="${HOME_DIR}/models"
PROVENANCE="${HOME_DIR}/provenance.txt"
INTER_FONTS="/usr/share/fonts/opentype/inter"
ARCHIVO_FONTS="/usr/share/fonts/truetype/archivo-black"

# Downloads $1 to $2 and fails unless its SHA-256 is $3.
fetch() {
  curl -fsSL --retry 3 -o "$2" "$1"
  echo "$3  $2" | sha256sum -c - > /dev/null || {
    echo "cutroom: $1 does not have the checksum $3" >&2
    exit 1
  }
}

record() {
  mkdir -p "${HOME_DIR}"
  printf '%s\n' "$*" >> "${PROVENANCE}"
}

case "${1-}" in
  packages)
    apt-get update
    apt-get install --no-install-recommends -y python3-venv xprintidle xterm
    apt-get clean
    rm -rf /var/lib/apt/lists/*
    ;;
  python)
    lock="$2"
    python3 -m venv "${HOME_DIR}/venv"
    "${HOME_DIR}/venv/bin/pip" install --disable-pip-version-check --no-cache-dir --no-compile \
      --require-hashes --only-binary :all: -r "${lock}"
    record "python packages: PyPI wheels, each by the hash in $(basename "${lock}") (sha256 $(sha256sum "${lock}" | cut -d ' ' -f 1))"
    ;;
  fonts)
    inter_version="$2"
    inter_sha256="$3"
    archivo_commit="$4"
    archivo_sha256="$5"
    archivo_license_sha256="$6"
    download="$(mktemp -d)"
    inter_url="https://github.com/rsms/inter/releases/download/v${inter_version}/Inter-${inter_version}.zip"
    fetch "${inter_url}" "${download}/inter.zip" "${inter_sha256}"
    mkdir -p "${INTER_FONTS}" "${ARCHIVO_FONTS}"
    python3 - "${download}/inter.zip" "${INTER_FONTS}" << 'PY'
import sys
import zipfile
from pathlib import Path

archive, target = zipfile.ZipFile(sys.argv[1]), Path(sys.argv[2])
for name in archive.namelist():
    if name == "LICENSE.txt" or (name.startswith("extras/otf/Inter-") and name.endswith(".otf")):
        (target / Path(name).name).write_bytes(archive.read(name))
PY
    archivo_url="https://raw.githubusercontent.com/google/fonts/${archivo_commit}/ofl/archivoblack"
    fetch "${archivo_url}/ArchivoBlack-Regular.ttf" "${ARCHIVO_FONTS}/ArchivoBlack-Regular.ttf" "${archivo_sha256}"
    fetch "${archivo_url}/OFL.txt" "${ARCHIVO_FONTS}/OFL.txt" "${archivo_license_sha256}"
    chmod 644 "${INTER_FONTS}"/* "${ARCHIVO_FONTS}"/*
    fc-cache -f
    rm -rf "${download}"
    record "font Inter ${inter_version} (SIL OFL 1.1): ${inter_url} sha256 ${inter_sha256}, extras/otf/Inter-*.otf in ${INTER_FONTS}"
    record "font Archivo Black (SIL OFL 1.1): ${archivo_url}/ArchivoBlack-Regular.ttf sha256 ${archivo_sha256}, in ${ARCHIVO_FONTS}"
    ;;
  whisper)
    name="$2"
    revision="$3"
    model_sha256="$4"
    target="${MODELS}/faster-whisper-${name}"
    url="https://huggingface.co/Systran/faster-whisper-${name}/resolve/${revision}"
    mkdir -p "${target}"
    for file in config.json tokenizer.json vocabulary.txt; do
      curl -fsSL --retry 3 -o "${target}/${file}" "${url}/${file}"
    done
    fetch "${url}/model.bin" "${target}/model.bin" "${model_sha256}"
    record "speech model faster-whisper-${name} (MIT): ${url} model.bin sha256 ${model_sha256}, in ${target}"
    ;;
  yunet)
    revision="$2"
    sha256="$3"
    url="https://huggingface.co/opencv/face_detection_yunet/resolve/${revision}"
    mkdir -p "${MODELS}"
    fetch "${url}/face_detection_yunet_2023mar.onnx" "${MODELS}/face_detection_yunet_2023mar.onnx" "${sha256}"
    curl -fsSL --retry 3 -o "${MODELS}/face_detection_yunet.LICENSE" "${url}/LICENSE"
    record "face detector YuNet (MIT): ${url}/face_detection_yunet_2023mar.onnx sha256 ${sha256}, in ${MODELS}"
    ;;
  verify)
    filters="$(ffmpeg -hide_banner -filters 2> /dev/null)"
    for filter in subtitles rubberband loudnorm ebur128 sidechaincompress acompressor alimiter deesser afftdn \
      aecho atempo adelay amix silenceremove dynaudnorm boxblur overlay select showinfo tile drawtext blackdetect; do
      echo "${filters}" | grep -q " ${filter} " || {
        echo "cutroom: this FFmpeg has no ${filter} filter" >&2
        exit 1
      }
    done
    encoders="$(ffmpeg -hide_banner -encoders 2> /dev/null)"
    for encoder in libx264 aac; do
      echo "${encoders}" | grep -q " ${encoder} " || {
        echo "cutroom: this FFmpeg has no ${encoder} encoder" >&2
        exit 1
      }
    done
    for family in "Inter:style=Black" "Inter:style=SemiBold" "Inter:style=ExtraBold" "Archivo Black"; do
      fc-match "${family}" file | grep -q -e "${INTER_FONTS}" -e "${ARCHIVO_FONTS}" || {
        echo "cutroom: fontconfig does not find ${family}" >&2
        exit 1
      }
    done
    "${HOME_DIR}/venv/bin/python" - << 'PY'
from importlib import import_module
from importlib.metadata import version

import cv2
from faster_whisper import WhisperModel

for module in ("deep_translator", "edge_tts", "numpy", "pedalboard", "PIL", "requests", "yt_dlp"):
    import_module(module)
for name in ("small", "medium"):
    WhisperModel(f"/opt/cutroom/models/faster-whisper-{name}", device="cpu", compute_type="int8")
cv2.FaceDetectorYN.create("/opt/cutroom/models/face_detection_yunet_2023mar.onnx", "", (320, 320), 0.7, 0.3, 5000)
packages = ("faster-whisper", "numpy", "opencv-python-headless", "pillow", "pedalboard", "yt-dlp", "requests",
            "deep-translator", "edge-tts")
print("cutroom:", ", ".join(f"{name} {version(name)}" for name in packages))
PY
    record "ffmpeg: $(ffmpeg -hide_banner -version | head -n 1), the base image's"
    ;;
  *)
    sed -n '/^#     install.sh/s/^#     //p' "$0" >&2
    exit 2
    ;;
esac
