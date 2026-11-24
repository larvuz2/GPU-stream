# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Image and video generation on fal.ai, through its queue API.

A generation takes from seconds (an image) to minutes (a video), longer than an
HTTP request should be held open, so each one is submitted to fal's queue and
polled: `POST https://queue.fal.run/<model>` answers at once with the request's
`status_url` and `response_url`, which are followed as given, since fal builds
them from the model's owner and app without the endpoint's subpath. A request
fal reports failed is `COMPLETED` with an `error`.

The models, each checked against its schema on fal
(`fal.ai/api/openapi/queue/openapi.json?endpoint_id=<id>`), are a short choice
the agent makes per call:

- Images (`IMAGE_MODELS`): `best`, Google's Nano Banana Pro, from a prompt
  (`fal-ai/nano-banana-pro`) or guided by up to 14 reference images (its
  `/edit`); `cheap`, ByteDance's Seedream 5.5 (`bytedance/seedream/v5.5/...`),
  which takes up to 10 and a size class where the other takes an aspect ratio.
- Video (`VIDEO_MODELS`): `standard`, ByteDance's Seedance 2.5
  reference-to-video (up to 30 reference images); `fast`, its Flash variant,
  480p or 720p; `draft`, Seedance 2.5's own 480p preview (`draft: true`), since
  fal has no separate draft endpoint.

Every model names its references in the prompt by position, `@Image1`,
`@Image2`, `@Video1`, in the order their URLs are given (`video_arguments`,
`image_arguments`).

What a generation cost is fal's to say: its pricing API gives each model's
price per unit (`Fal.cost`), which times the units a call made (images, or
seconds of video) is the estimate shown; where the unit is not one a call
counts, fal's own per-call estimate stands in.

Polling asks the caller whether to go on (`alive`), so a turn that is stopped
cancels what it queued rather than paying for it to finish.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Protocol

import httpx

QUEUE_URL = "https://queue.fal.run"
PLATFORM_URL = "https://api.fal.ai/v1"
# A choice's models: from a prompt alone, and with reference images
IMAGE_MODELS = {
    "best": ("fal-ai/nano-banana-pro", "fal-ai/nano-banana-pro/edit"),
    "cheap": ("bytedance/seedream/v5.5/text-to-image", "bytedance/seedream/v5.5/edit"),
}
IMAGE_REFERENCES = {"best": 14, "cheap": 10}
VIDEO_MODELS = {
    "standard": "bytedance/seedance-2.5/reference-to-video",
    "fast": "bytedance/seedance-2.5/flash/reference-to-video",
    "draft": "bytedance/seedance-2.5/reference-to-video",
}
VIDEO_RESOLUTIONS = {"standard": ("480p", "720p", "1080p"), "fast": ("480p", "720p"), "draft": ("480p",)}
VIDEO_REFERENCES = 30
IMAGE_ASPECT_RATIOS = ("auto", "21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4", "2:3", "9:16")
VIDEO_ASPECT_RATIOS = ("auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
# Seedream takes a size class, not a ratio: each ratio's nearest
SEEDREAM_SIZES = {
    "auto": "auto_2K",
    "21:9": "landscape_16_9",
    "16:9": "landscape_16_9",
    "3:2": "landscape_4_3",
    "4:3": "landscape_4_3",
    "5:4": "landscape_4_3",
    "1:1": "square_hd",
    "4:5": "portrait_4_3",
    "3:4": "portrait_4_3",
    "2:3": "portrait_4_3",
    "9:16": "portrait_16_9",
}
POLL_SECONDS = 3.0


class GenerationStopped(Exception):
    """The turn that asked for a generation was stopped while it ran; the request was canceled."""


class Generator(Protocol):
    """What the agent's generation tools need of fal, which a test stands in for."""

    def run(self, model: str, arguments: dict[str, Any], alive: Callable[[], bool], limit_seconds: float) -> dict[str, Any]:
        """Run one generation to its end and return fal's result for it."""

    def download(self, url: str) -> tuple[bytes, str]:
        """A result's bytes and their content type."""

    def cost(self, model: str, units: dict[str, float]) -> float | None:
        """What fal says a call made of these units costs, in dollars, or nothing where it does not say."""


def image_arguments(
    choice: str, prompt: str, urls: list[str], aspect_ratio: str, count: int
) -> tuple[str, dict[str, Any]]:
    """The model and the input of an image generation, its references given as URLs."""
    plain, edit = IMAGE_MODELS[choice]
    if choice == "cheap":
        arguments: dict[str, Any] = {"prompt": prompt, "num_images": count, "image_size": SEEDREAM_SIZES[aspect_ratio]}
    else:
        arguments = {"prompt": prompt, "num_images": count, "aspect_ratio": aspect_ratio, "resolution": "2K"}
    arguments["output_format"] = "png"
    if urls:
        arguments["image_urls"] = urls
    return (edit if urls else plain), arguments


def video_arguments(
    choice: str,
    prompt: str,
    urls: dict[str, list[str]],
    duration_seconds: int | None,
    aspect_ratio: str,
    resolution: str,
) -> tuple[str, dict[str, Any]]:
    """The model and the input of a video generation, its references given as URLs by kind."""
    arguments: dict[str, Any] = {
        "prompt": prompt,
        "duration": str(duration_seconds) if duration_seconds else "auto",
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
    }
    if choice == "draft":
        arguments["draft"] = True
    for kind, given in urls.items():
        if given:
            arguments[f"{kind}_urls"] = given
    return VIDEO_MODELS[choice], arguments


class Fal:
    """fal's queue API and pricing API with a key (`FAL_KEY`)."""

    def __init__(self, key: str) -> None:
        self.http = httpx.Client(timeout=60, headers={"Authorization": f"Key {key}"})
        # Results are public files on fal's storage: fetched without the key, which goes only to fal's APIs
        self.files = httpx.Client(timeout=300, follow_redirects=True)
        self.prices: dict[str, tuple[float, str]] = {}

    def run(self, model: str, arguments: dict[str, Any], alive: Callable[[], bool], limit_seconds: float) -> dict[str, Any]:
        """Submit a generation and poll it until it ends.

        Raises:
            GenerationStopped: `alive` said to stop; the request was canceled.
            RuntimeError: fal refused the request, reported it failed, or it outlasted `limit_seconds`.
        """
        submitted = self.http.post(f"{QUEUE_URL}/{model}", json=arguments)
        if submitted.status_code >= 400:
            raise RuntimeError(f"fal refused the request: {self._reason(submitted)}")
        queued = submitted.json()
        deadline = time.monotonic() + limit_seconds
        while True:
            if not alive():
                self.http.put(queued["cancel_url"])
                raise GenerationStopped()
            status = self.http.get(queued["status_url"]).json()
            if status.get("status") == "COMPLETED":
                break
            if time.monotonic() > deadline:
                self.http.put(queued["cancel_url"])
                raise RuntimeError(f"fal did not finish within {int(limit_seconds)} seconds")
            time.sleep(POLL_SECONDS)
        if status.get("error"):
            raise RuntimeError(f"fal could not generate it: {status['error']}")
        result = self.http.get(queued["response_url"])
        if result.status_code >= 400:
            raise RuntimeError(f"fal could not generate it: {self._reason(result)}")
        return result.json()

    def download(self, url: str) -> tuple[bytes, str]:
        """A result's bytes and their content type, from fal's storage."""
        response = self.files.get(url)
        response.raise_for_status()
        return response.content, response.headers.get("content-type", "application/octet-stream").split(";")[0]

    def cost(self, model: str, units: dict[str, float]) -> float | None:
        """fal's estimate of a call's cost: its price per unit times the call's units of that kind.

        `units` counts what the call made by unit name (`image`, `second`); a
        model priced in another unit is estimated by fal from past calls. The
        estimate is something to show, never something a generation waits
        on, so a pricing API that does not answer leaves it out.
        """
        try:
            if model not in self.prices:
                response = self.http.get(f"{PLATFORM_URL}/models/pricing", params={"endpoint_id": model})
                response.raise_for_status()
                price = response.json()["prices"][0]
                self.prices[model] = (float(price["unit_price"]), str(price["unit"]).lower().rstrip("s"))
            unit_price, unit = self.prices[model]
            if unit in units:
                return round(unit_price * units[unit], 4)
            response = self.http.post(
                f"{PLATFORM_URL}/models/pricing/estimate",
                json={"estimate_type": "historical_api_price", "endpoints": {model: {"call_quantity": 1}}},
            )
            response.raise_for_status()
            return round(float(response.json()["total_cost"]), 4)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _reason(response: httpx.Response) -> str:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None
        return str(detail or response.text[:300] or response.status_code)
