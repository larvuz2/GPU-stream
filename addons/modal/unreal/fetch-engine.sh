#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Copies one directory out of a container image into this one, with the
# registry credentials of the user whose image this is.
#
#   fetch-engine.sh IMAGE SOURCE_DIRECTORY TARGET_DIRECTORY
#
# The Unreal Editor reaches a Lathe image this way: Epic publishes it only in
# development images on ghcr.io/epicgames/unreal-engine, which pull with a
# GitHub token of an account linked to Epic, and its license keeps each user on
# their own copy (lathe/UNREAL.md). crane streams the image's filesystem
# straight into tar, so only the directory asked for is written, never the
# whole image. The credentials come from the build's secret as
# REGISTRY_USERNAME and REGISTRY_PASSWORD; crane's login goes to a directory
# this step deletes before it ends, so the token is in no layer of the image.
# An image that needs no login is fetched without the two set.
#
# crane is go-containerregistry's release, checked against the checksum its
# release publishes.

set -eu

image=$1
source=${2#/}
target=$3
crane_version=v0.22.1
crane_sha256=0ab7a1d6932a213aed964ce97666c3077fe691c8606413674a8b3e0b9ec4cda0

work=$(mktemp -d)
trap 'rm -rf "${work}"' EXIT
export DOCKER_CONFIG="${work}/docker"

curl -fsSL -o "${work}/crane.tar.gz" \
  "https://github.com/google/go-containerregistry/releases/download/${crane_version}/go-containerregistry_Linux_x86_64.tar.gz"
echo "${crane_sha256}  ${work}/crane.tar.gz" | sha256sum -c - > /dev/null
tar -xzf "${work}/crane.tar.gz" -C "${work}" crane

if [ -n "${REGISTRY_USERNAME-}" ]; then
  printf '%s' "${REGISTRY_PASSWORD-}" |
    "${work}/crane" auth login "${image%%/*}" --username "${REGISTRY_USERNAME}" --password-stdin > /dev/null
fi

if ! "${work}/crane" manifest "${image}" > /dev/null 2> "${work}/refused"; then
  echo "fetch-engine: ${image} cannot be pulled with these credentials: $(cat "${work}/refused")" >&2
  echo "fetch-engine: Epic's images need a GitHub account linked to an Epic account, and a token with read:packages" >&2
  exit 1
fi

mkdir -p "${work}/root" "${target}"
"${work}/crane" export "${image}" - | tar -x -C "${work}/root" "${source}"
# Everything of the directory, dot files included, into the target
(cd "${work}/root/${source}" && tar -c .) | tar -x -C "${target}"
# The session's user writes the engine's caches and saved state beside it
chown -R 1000:1000 "${target}"
echo "fetch-engine: ${source} of ${image} is in ${target}, $(du -sh "${target}" | cut -f1)"
