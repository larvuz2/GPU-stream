# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# This file incorporates work covered by the following copyright and
# permission notice:
#
#   MIT License
#
#   Copyright (c) 2026 Bodila51
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in all
#   copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#   SOFTWARE.
"""Find the presenter's webcam in a video: the box it is in, or a crop around the face.

    cutroom facecam VIDEO [--start S --end E] [--json out.json] [--debug out.jpg]

`find_cam` answers one of:

- `{"mode": "cam", "box": [x, y, w, h], "face": [...], "confidence": 0..1}`:
  a webcam overlay, its box in fractions of the picture, which `cut.py` takes
  as `--cam x:y:w:h`.
- `{"mode": "face", "box": [...], "face_track": [...]}`: a stable face with
  no clean rectangle around it, and a 16:9 crop around the face.
- `{"mode": "none", "reason": ...}`: no stable face, or one so large it is a
  full-frame talking head; the caller falls back to the blur layout.

The method: YuNet finds faces in about twelve sampled frames, and the cluster
that stays at one spot in most of them is the presenter (faces in the footage
move). A rectangle is then grown around that face on a map of the edges that
survive a median over the frames: a webcam's border is a straight, static
line, so its edge is still there when the edges of moving footage have
blurred out. The rectangle is snapped to the border by where color and
motion both change (`snap_edges`).

The detector is a file of the image (`common.FACE_MODEL`); nothing is
downloaded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np
from common import FACE_MODEL

N_FRAMES = 12
# The width frames are analyzed at
MAX_W = 1280

Box = Sequence[float]
Frames = list[np.ndarray]


def model_path() -> str:
    """The face detector's file, which the image carries; the script ends where it is missing."""
    if not FACE_MODEL.exists():
        sys.exit(f"the face detector is not at {FACE_MODEL}")
    return str(FACE_MODEL)


def duration(video: str | Path) -> float:
    """A video's length in seconds as OpenCV counts its frames, or zero where it cannot."""
    cap = cv2.VideoCapture(str(video))
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.release()
    return n / fps if n > 0 else 0


def sample_frames(
    video: str | Path, start: float | None, end: float | None, n: int = N_FRAMES
) -> Frames:
    """`n` frames spread evenly between `start` and `end`, sought by time and no wider than `MAX_W`."""
    dur = duration(video)
    s = max(0.0, start or 0.0)
    e = min(end if end is not None else dur, dur) if dur else (end or s + 20)
    if e <= s:
        e = s + 1
    cap = cv2.VideoCapture(str(video))
    frames = []
    for i in range(n):
        t = s + (e - s) * (i + 0.5) / n
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if ok and f is not None:
            h, w = f.shape[:2]
            if w > MAX_W:
                f = cv2.resize(
                    f, (MAX_W, int(h * MAX_W / w)), interpolation=cv2.INTER_AREA
                )
            frames.append(f)
    cap.release()
    return frames


def detect_faces(frames: Frames) -> list[list[tuple[float, ...]]]:
    """The faces YuNet finds in each frame, as (x, y, w, h, score) in pixels."""
    det = cv2.FaceDetectorYN.create(model_path(), "", (320, 320), 0.7, 0.3, 5000)
    out = []
    for f in frames:
        h, w = f.shape[:2]
        det.setInputSize((w, h))
        _, faces = det.detect(f)
        out.append(
            []
            if faces is None
            else [tuple(map(float, r[:4])) + (float(r[14]),) for r in faces]
        )
    return out


def stable_face(dets: list[list[tuple[float, ...]]]) -> tuple[np.ndarray | None, int]:
    """The face that stays where it is: the median box of the largest cluster of detections, and its frames.

    A presenter's face is at one spot in most frames, while faces in the
    footage move. Two detections are the same face when their centers are
    within about 1.3 face widths, since people sway, and their sizes are alike.
    """
    best = None
    flat = [(i, d) for i, ds in enumerate(dets) for d in ds]
    for _, seed in flat:
        members = {}
        for i, d in flat:
            dx = (seed[0] + seed[2] / 2) - (d[0] + d[2] / 2)
            dy = (seed[1] + seed[3] / 2) - (d[1] + d[3] / 2)
            if (dx * dx + dy * dy) ** 0.5 < 1.3 * max(seed[2], d[2]) and 0.6 < d[
                2
            ] / seed[2] < 1.67:
                if i not in members or d[4] > members[i][4]:
                    members[i] = d
        if best is None or len(members) > len(best):
            best = members
    if not best:
        return None, 0
    arr = np.array(list(best.values()))
    return np.median(arr[:, :4], axis=0), len(best)


def edge_map(frames: Frames) -> tuple[np.ndarray, np.ndarray]:
    """The horizontal and vertical gradient that survives a median over the frames: the static edges.

    A webcam's border is a straight line that does not move, so its edge is
    in the median while the edges of moving footage blur out. Edges are two
    or three pixels thick after scaling, so each takes the maximum over its
    neighbors across the edge.
    """
    gs = []
    for f in frames:
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        g = cv2.GaussianBlur(g, (3, 3), 0)
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        gs.append((gx, gy))
    mx = np.median(np.abs([a for a, _ in gs]), axis=0)
    my = np.median(np.abs([b for _, b in gs]), axis=0)
    mx = np.maximum(mx, np.maximum(np.roll(mx, 1, 1), np.roll(mx, -1, 1)))
    my = np.maximum(my, np.maximum(np.roll(my, 1, 0), np.roll(my, -1, 0)))
    return mx, my


def find_rect(frames: Frames, face: Box) -> dict[str, Any]:
    """The rectangle around a face, grown outward to the strongest static straight edge on each side.

    Returns the four sides in pixels (`L`, `R`, `T`, `B`, each nothing where
    no edge was found), which were found, notes, and how many are weak. A
    side is a line that is long and unbroken over the span of the box found
    so far, which overlays and furniture are not; of the near-best lines the
    outermost is taken, since the camera's frame is outside what is in the
    room. A camera docked to a corner has the picture's border for a side.
    """
    h, w = frames[0].shape[:2]
    gx, gy = edge_map(frames)
    fx, fy, fw, fh = face
    cx, cy = fx + fw / 2, fy + fh / 2
    thr_v = max(20.0, np.percentile(gx, 99.0) * 0.35)
    thr_h = max(20.0, np.percentile(gy, 99.0) * 0.35)

    def run_len(line_mask):
        # The longest run in a line of booleans, small gaps allowed
        best = cur = gap = 0
        for v in line_mask:
            if v:
                cur += 1 + gap
                gap = 0
                best = max(best, cur)
            elif cur and gap < 4:
                gap += 1
            else:
                cur = gap = 0
        return best

    # Candidate extents: face-relative search windows
    def search(axis_edges, lo, hi, other_lo, other_hi, thr, vertical):
        """Best static edge position in [lo,hi) judged over the span [other_lo,other_hi)."""
        cands = []
        for p in range(max(lo, 1), min(hi, (w if vertical else h) - 1)):
            sl = (
                axis_edges[other_lo:other_hi, p]
                if vertical
                else axis_edges[p, other_lo:other_hi]
            )
            m = sl > thr
            if m.mean() < 0.4:
                continue
            frac = run_len(m) / max(1, other_hi - other_lo)
            if (
                frac < 0.4
            ):  # a real border is one long straight line, not text or furniture
                continue
            cands.append((p, frac * float(sl.mean())))
        if not cands:
            return None, 0
        top = max(sc for _, sc in cands)
        # near-best lines: take the outermost (the webcam frame is outside inner furniture lines)
        strong = [(p, sc) for p, sc in cands if sc >= 0.9 * top]
        ref = cx if vertical else cy
        after = lo > ref
        return max(strong, key=lambda t: t[0] if after else -t[0])

    # span used to judge vertical lines: the face's height band extended; horizontal lines: face's width band
    ys0, ys1 = int(max(0, cy - fh * 2.5)), int(min(h, cy + fh * 2.5))
    xs0, xs1 = int(max(0, cx - fw * 4)), int(min(w, cx + fw * 4))

    # sides limited to sane webcam size: box between 1.6x and 8x face width
    def sides(ys0, ys1, xs0, xs1):
        return (
            search(gx, int(cx - fw * 10), int(fx - fw * 0.1), ys0, ys1, thr_v, True),
            search(gx, int(fx + fw * 1.1), int(cx + fw * 10), ys0, ys1, thr_v, True),
            search(gy, int(cy - fh * 4.5), int(fy - fh * 0.1), xs0, xs1, thr_h, False),
            search(gy, int(fy + fh * 1.1), int(cy + fh * 4.5), xs0, xs1, thr_h, False),
        )

    (L, sL), (R, sR), (T, sT), (B, sB) = sides(ys0, ys1, xs0, xs1)
    # refine: judge each line over the full extent of the box found so far (overlays and room furniture do not span it)
    for _ in range(2):
        if None in (L, R, T, B):
            break
        (L2, sL), (R2, sR), (T2, sT), (B2, sB) = sides(T, B, L, R)
        L, R, T, B = (
            (L2 if L2 is not None else L),
            (R2 if R2 is not None else R),
            (T2 if T2 is not None else T),
            (B2 if B2 is not None else B),
        )
    # frame borders count as edges (cam docked to a corner)
    notes = []
    if L is None and fx - fw * 10 < 3:
        L = 0
        sL = 1
        notes.append("L=frame")
    if R is None and cx + fw * 10 > w - 3:
        R = w
        sR = 1
        notes.append("R=frame")
    if T is None and cy - fh * 4.5 < 3:
        T = 0
        sT = 1
        notes.append("T=frame")
    if B is None and cy + fh * 4.5 > h - 3:
        B = h
        sB = 1
        notes.append("B=frame")
    found = [x is not None for x in (L, R, T, B)]
    weak = [
        n
        for n, s, t in (
            ("L", sL, thr_v),
            ("R", sR, thr_v),
            ("T", sT, thr_h),
            ("B", sB, thr_h),
        )
        if s < 0.9 * t
    ]
    return dict(L=L, R=R, T=T, B=B, found=found, notes=notes, weak=len(weak))


SNAP_FRAMES = 20
# Pixels, at the analysis width, searched around each edge
SNAP_RANGE = 80
# Pixels a snapped edge moves inside, so no sliver of what is behind the camera remains
SNAP_SHRINK = 2


def _edge_profile(
    M: np.ndarray,
    S: np.ndarray,
    p_lo: int,
    p_hi: int,
    span: tuple[int, int],
    vertical: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Score the positions between `p_lo` and `p_hi` as a camera border, vertical or horizontal.

    `M` is the median color image and `S` the map of each pixel's change
    over time; `span` is the stretch along the line that is judged. A
    position is the first pixel after the change, compared three pixels to
    each side. Two things count: the color step holds on most pixels along
    the span, as a straight static line does, and the two sides differ in
    how they change over time, as a camera and what is behind it do.
    """
    a, b = span
    if not vertical:
        M = M.transpose(1, 0, 2)
        S = S.T
    Ms = M[a:b]
    Ss = S[a:b]
    n = Ms.shape[1]
    ps = np.arange(max(p_lo, 4), min(p_hi, n - 3))
    if len(ps) == 0:
        return ps, np.zeros(0)
    cs = np.concatenate(
        [np.zeros((Ms.shape[0], 1, 3), np.float32), np.cumsum(Ms, axis=1)], axis=1
    )
    right = (cs[:, ps + 3] - cs[:, ps]) / 3
    left = (cs[:, ps] - cs[:, ps - 3]) / 3
    step = np.abs(right - left).sum(axis=2)  # rows x candidates
    cons = (step > 24).mean(axis=0)  # fraction of the line that shows the step
    mag = np.clip(np.median(step, axis=0) / 45.0, 0, 1)
    cs2 = np.concatenate(
        [np.zeros((Ss.shape[0], 1), np.float32), np.cumsum(Ss, axis=1)], axis=1
    )
    k0 = np.clip(ps - 10, 0, n)
    k1 = np.clip(ps - 2, 0, n)
    k2 = np.clip(ps + 2, 0, n)
    k3 = np.clip(ps + 10, 0, n)
    sl = (cs2[:, k1] - cs2[:, k0]) / np.maximum(1, k1 - k0)
    sr = (cs2[:, k3] - cs2[:, k2]) / np.maximum(1, k3 - k2)
    rel = np.abs(sl - sr) / (sl + sr + 2.0)
    tcons = (rel > 0.35).mean(axis=0)
    tmag = np.clip(np.median(rel, axis=0) * 2, 0, 1)
    return ps, cons * mag + 0.6 * tcons * tmag


def snap_edges(
    frames: Frames,
    box: Box,
    search: int = SNAP_RANGE,
    shrink: int = SNAP_SHRINK,
    face: Box | None = None,
) -> tuple[int, int, int, int, dict[str, int]]:
    """A box snapped to the webcam's real border: (L, T, R, B) in pixels of the frames, and the raw edges.

    Of the strong lines near each side the one nearest the face is the
    border: a stronger line further out, such as a card of the interface or
    a window's edge, lies beyond a flat strip that is no part of the camera.
    """
    h, w = frames[0].shape[:2]
    L, T, R, B = [int(round(v)) for v in box]
    idx = np.linspace(0, len(frames) - 1, min(len(frames), SNAP_FRAMES)).astype(int)
    fs = [frames[i] for i in idx]
    M = np.median(np.array(fs), axis=0).astype(np.float32)
    S = (
        np.array([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in fs])
        .astype(np.float32)
        .std(axis=0)
    )
    M = cv2.GaussianBlur(M, (3, 3), 0)
    S = cv2.GaussianBlur(S, (3, 3), 0)
    H, W = B - T, R - L
    yspan = (int(T + 0.15 * H), int(B - 0.15 * H))
    xspan = (int(L + 0.15 * W), int(R - 0.15 * W))
    out = {}
    for name, p0, vertical, span in (
        ("L", L, True, yspan),
        ("R", R, True, yspan),
        ("T", T, False, xspan),
        ("B", B, False, xspan),
    ):
        lim = w if vertical else h
        if p0 <= 3 or p0 >= lim - 3:  # docked to the frame edge: nothing to snap
            out[name] = 0 if p0 <= 3 else lim
            continue
        ps, sc = _edge_profile(M, S, p0 - search, p0 + search + 1, span, vertical)
        if len(ps) == 0 or sc.max() < 0.25:
            out[name] = p0
            continue
        sc = (
            sc - 0.05 * np.abs(ps - p0) / search
        )  # weak prior: stay near the first estimate
        # strong plateaus (runs within 90% of the best); the cam border is the one nearest the face: a stronger line
        # further out (game UI card, window edge) lies beyond a flat dead strip that is not part of the cam
        strong = sc >= 0.9 * sc.max()
        if face is not None:
            fx, fy, fw_, fh_ = face
            lim_in = {
                "L": fx - 0.3 * fw_,
                "R": fx + 1.3 * fw_,
                "T": fy - 0.3 * fh_,
                "B": fy + 1.3 * fh_,
            }[name]
            ok = (ps < lim_in) if name in ("L", "T") else (ps > lim_in)
            if (strong & ok).any():
                strong &= ok
        idx = np.flatnonzero(strong)
        runs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
        run = runs[-1] if name in ("L", "T") else runs[0]
        # the step window is 3+3 px wide, so the true border is the center of the plateau
        out[name] = int(round((ps[run[0]] + ps[run[-1]]) / 2))
    nL = out["L"] if out["L"] <= 3 else out["L"] + shrink
    nT = out["T"] if out["T"] <= 3 else out["T"] + shrink
    nR = out["R"] if out["R"] >= w - 3 else out["R"] - shrink
    nB = out["B"] if out["B"] >= h - 3 else out["B"] - shrink
    return nL, nT, nR, nB, out


# How far the face's center may drift, as a share of the picture's width per second
FACE_MAX_DRIFT = 0.03


def _median_filter(a: np.ndarray, k: int = 5) -> np.ndarray:
    """A running median of `k` values, the ends held."""
    pad = k // 2
    p = np.pad(a, pad, mode="edge")
    return np.array([np.median(p[i : i + k]) for i in range(len(a))])


def track_face(
    video: str | Path,
    start: float | None,
    end: float | None,
    face: Box,
    fps: float = 2.0,
) -> list[dict[str, float]]:
    """The face's center and size over time, as `{t, cx, cy, size}` in fractions of the picture.

    `size` is the face's height over the picture's and `t` seconds from
    `start`. Detections near the stable face are kept and gaps filled in,
    then a median, exponential smoothing, and a limit on the drift per
    second (`FACE_MAX_DRIFT`) keep a crop that follows it from jumping.
    """
    dur = duration(video)
    s = max(0.0, start or 0.0)
    e = min(end if end is not None else dur, dur) if dur else (end or s + 20)
    if e <= s:
        e = s + 1
    n = int(min(240, max(2, round((e - s) * fps) + 1)))
    ts = np.linspace(s, e - min(0.05, (e - s) / 10), n)
    cap = cv2.VideoCapture(str(video))
    det = cv2.FaceDetectorYN.create(model_path(), "", (320, 320), 0.7, 0.3, 5000)
    fx, fy, fw, fh = face
    raw = []
    W = H = None
    ref = np.array([fx + fw / 2, fy + fh / 2, fh], float)  # px of the analysis frame
    for t in ts:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok or f is None:
            raw.append(None)
            continue
        h, w = f.shape[:2]
        sc = min(1.0, MAX_W / w)
        if sc < 1:
            f = cv2.resize(f, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
            h, w = f.shape[:2]
        W, H = w, h
        det.setInputSize((w, h))
        _, fs = det.detect(f)
        best = None
        for r in [] if fs is None else fs:
            cx, cy, hh = r[0] + r[2] / 2, r[1] + r[3] / 2, r[3]
            if (
                np.hypot(cx - ref[0], cy - ref[1]) < 1.6 * ref[2]
                and 0.6 < hh / ref[2] < 1.67
            ):
                d = np.hypot(cx - ref[0], cy - ref[1])
                if best is None or d < best[0]:
                    best = (d, cx, cy, hh)
        if best:
            raw.append(best[1:])
            ref = 0.6 * ref + 0.4 * np.array(best[1:])
        else:
            raw.append(None)
    cap.release()
    if not W or sum(r is not None for r in raw) < 2:
        return []
    ok_i = [i for i, r in enumerate(raw) if r is not None]
    arr = np.array([raw[i] for i in ok_i], float)
    rel_t = ts - s
    cx = np.interp(np.arange(n), ok_i, arr[:, 0])
    cy = np.interp(np.arange(n), ok_i, arr[:, 1])
    sz = np.interp(np.arange(n), ok_i, arr[:, 2])
    for v in (cx, cy, sz):
        v[:] = _median_filter(v, 5)
        for i in range(1, n):  # exponential smoothing
            v[i] = 0.25 * v[i] + 0.75 * v[i - 1]
    lim = FACE_MAX_DRIFT * W
    for i in range(1, n):  # slew limit: drift per second, in px
        dt = max(1e-3, rel_t[i] - rel_t[i - 1])
        for v, L_ in ((cx, lim), (cy, lim), (sz, 0.06 * max(sz[i - 1], 1))):
            d = v[i] - v[i - 1]
            m = L_ * dt
            v[i] = v[i - 1] + max(-m, min(m, d))
    return [
        {
            "t": round(float(rel_t[i]), 3),
            "cx": round(float(cx[i] / W), 4),
            "cy": round(float(cy[i] / H), 4),
            "size": round(float(sz[i] / H), 4),
        }
        for i in range(n)
    ]


def _pw(ts: Sequence[float], vs: Sequence[float]) -> str:
    """A piecewise-linear FFmpeg expression in `t`, its commas escaped for a filter graph."""
    if len(ts) == 1:
        return f"{vs[0]:.2f}"
    expr = f"{vs[-1]:.2f}"
    for i in range(len(ts) - 2, -1, -1):
        dt = max(1e-3, ts[i + 1] - ts[i])
        expr = f"if(lt(t\\,{ts[i + 1]:.3f})\\,{vs[i]:.2f}+({vs[i + 1] - vs[i]:.2f})*(t-{ts[i]:.3f})/{dt:.3f}\\,{expr})"
    return expr


def face_crop_expr(
    track: list[dict[str, float]],
    src_w: int,
    src_h: int,
    out_w: int,
    out_h: int,
    eyes_at: float = 0.40,
    head_fill: float = 0.38,
    bounds: tuple[int, int, int, int] | None = None,
) -> dict[str, Any] | None:
    """The FFmpeg crop for a face panel of `out_w`:`out_h` that follows a tracked face.

    `head_fill` is the face's height over the crop's (0.38 shows head and
    shoulders), and the eyes sit at `eyes_at` of the panel's height. The face
    is centered, never leaves the crop, and the crop never leaves the picture
    or, with `bounds`, the webcam. The answer has `w` and `h`, even and
    fixed, since FFmpeg cannot animate a crop's size, and `x` and `y` as
    expressions in `t`, seconds from the cut's start.
    """
    if not track:
        return None
    ar = out_w / out_h
    L, T, R, B = (
        bounds if bounds else (0, 0, src_w, src_h)
    )  # crop must stay inside the webcam
    bw, bh = R - L, B - T
    size = float(np.median([k["size"] for k in track])) * src_h  # face height px
    ch = min(size / head_fill, bh, bw / ar)  # too big for the cam: zoom in instead
    cw = ch * ar
    cw = max(2, int(cw) // 2 * 2)
    ch = max(2, int(round(cw / ar)) // 2 * 2)
    if ch > src_h:
        ch = src_h // 2 * 2
        cw = max(2, int(ch * ar) // 2 * 2)
    xs, ys, ts = [], [], []
    for k in track:
        fcx, fcy = k["cx"] * src_w, k["cy"] * src_h
        fh_ = k["size"] * src_h
        fw_ = 0.8 * fh_
        x = fcx - cw / 2
        y = (
            fcy - 0.12 * fh_
        ) - eyes_at * ch  # eyes sit ~0.12 face heights above the box center
        lo, hi = (
            max(L, fcx + fw_ / 2 - cw),
            min(R - cw, fcx - fw_ / 2),
        )  # keep the whole face box inside
        if lo <= hi:
            x = min(max(x, lo), hi)
        lo, hi = max(T, fcy + fh_ / 2 - ch), min(B - ch, fcy - fh_ / 2)
        if lo <= hi:
            y = min(max(y, lo), hi)
        xs.append(min(max(x, L), R - cw))
        ys.append(min(max(y, T), B - ch))
        ts.append(k["t"])
    x_e, y_e = _pw(ts, xs), _pw(ts, ys)
    return {
        "w": cw,
        "h": ch,
        "x": x_e,
        "y": y_e,
        "filter": f"crop={cw}:{ch}:{x_e}:{y_e}",
    }


def has_gameplay(
    video: str | Path,
    start: float | None,
    end: float | None,
    cam_box: Box | None,
    info: bool = False,
) -> Any:
    """Whether what is outside the camera's box is screen footage that differs from the camera's scene.

    A box that is missing or covers most of the picture is a full-screen
    camera, which has nothing outside it. A box cropped from one scene has an
    outside that matches it in color, and no hard border around it, where an
    overlay has both a border and a different scene behind it. With `info`
    the measurements come back beside the answer.
    """

    def ret(v, d):
        return (v, d) if info else v

    if not cam_box:
        return ret(False, {"why": "no cam box"})
    frames = sample_frames(video, start, end, 8)
    if len(frames) < 3:
        return ret(False, {"why": "too few frames"})
    h, w = frames[0].shape[:2]
    x, y, bw, bh = cam_box
    if bw * bh > 0.55:
        return ret(False, {"why": "cam covers the frame"})
    x0, y0, x1, y1 = int(x * w), int(y * h), int((x + bw) * w), int((y + bh) * h)
    inside = np.zeros((h, w), np.uint8)
    inside[y0:y1, x0:x1] = 255
    outside = 255 - inside
    # ignore a thin margin so the cam border does not leak into the outside histogram
    outside = cv2.erode(outside, np.ones((9, 9), np.uint8))
    hist = lambda m, hsv: cv2.normalize(
        cv2.calcHist([hsv], [0, 1, 2], m, [12, 4, 6], [0, 180, 0, 256, 0, 256]),
        None,
        1,
        0,
        cv2.NORM_L1,
    ).flatten()
    sims = []
    for f in frames:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        sims.append(
            cv2.compareHist(
                hist(inside, hsv), hist(outside, hsv), cv2.HISTCMP_BHATTACHARYYA
            )
        )
    dist = float(np.median(sims))  # 0 = same scene, 1 = nothing in common
    gray = np.array([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]).astype(
        np.float32
    )
    om = outside > 0
    content = float(gray.mean(axis=0)[om].std())  # spatial variety outside
    motion = float(
        np.abs(np.diff(gray, axis=0))[:, om].mean()
    )  # frame-to-frame change outside
    # the picture just outside the cam is a continuation of it for IRL footage: a plain-color or flat outside is not gameplay
    # an overlay has a hard straight border all around; a crop of one IRL scene is continuous across the box edge
    Mg = cv2.GaussianBlur(
        np.median(np.array(frames), axis=0).astype(np.float32), (3, 3), 0
    )
    fr_ = []
    for p, vert, (a, b) in (
        (x0, 1, (y0, y1)),
        (x1, 1, (y0, y1)),
        (y0, 0, (x0, x1)),
        (y1, 0, (x0, x1)),
    ):
        if p <= 4 or p >= (w if vert else h) - 4:
            continue  # docked to the frame edge: no border there
        m = int(0.1 * (b - a))
        a, b = a + m, b - m
        best = 0.0
        for q in range(p - 3, p + 4):
            if vert:
                s = np.abs(
                    Mg[a:b, q + 1 : q + 4].mean(1) - Mg[a:b, q - 3 : q].mean(1)
                ).sum(1)
            else:
                s = np.abs(
                    Mg[q + 1 : q + 4, a:b].mean(0) - Mg[q - 3 : q, a:b].mean(0)
                ).sum(1)
            best = max(best, float((s > 30).mean()))
        fr_.append(best)
    border = float(np.median(fr_)) if fr_ else 0.0
    has_content = content > 12 or motion > 3
    res = has_content and ((border >= 0.65 and dist > 0.38) or dist > 0.6)
    return ret(
        bool(res),
        {
            "hist_dist": round(dist, 3),
            "border": round(border, 2),
            "content": round(content, 1),
            "motion": round(motion, 2),
        },
    )


def where(box: Box) -> str:
    """Where a box sits and how large it is, in words."""
    x, y, bw, bh = box
    cx, cy = x + bw / 2, y + bh / 2
    v = "top" if cy < 0.4 else "bottom" if cy > 0.6 else "middle"
    hz = "left" if cx < 0.4 else "right" if cx > 0.6 else "center"
    return f"{v}-{hz} {round(bw * 100)}% x {round(bh * 100)}%"


def find_cam(
    video: str | Path, start: float | None = None, end: float | None = None
) -> dict[str, Any]:
    """Find the presenter's webcam in a stretch of video (the module docblock has the three answers)."""
    frames = sample_frames(video, start, end)
    if len(frames) < 4:
        return {
            "mode": "none",
            "confidence": 0.0,
            "reason": f"could only read {len(frames)} frames",
        }
    h, w = frames[0].shape[:2]
    dets = detect_faces(frames)
    face, hits = stable_face(dets)
    need = max(3, int(len(frames) * 0.5))
    total = sum(len(d) for d in dets)
    if face is None or hits < need:
        return {
            "mode": "none",
            "confidence": 0.0,
            "faces_seen": total,
            "reason": f"no face stable across frames (best cluster {hits}/{len(frames)}, need {need})",
        }
    fx, fy, fw, fh = face
    fracface = [round(fx / w, 4), round(fy / h, 4), round(fw / w, 4), round(fh / h, 4)]
    if fw / w > 0.5:
        try:
            track = track_face(video, start, end, face)
        except Exception:
            track = []
        return {
            "mode": "none",
            "confidence": 0.0,
            "face": fracface,
            "face_track": track,
            "reason": "stable face is huge (full-frame talking head, not a webcam overlay)",
        }
    stab = hits / len(frames)

    r = find_rect(frames, face)
    L, R, T, B = r["L"], r["R"], r["T"], r["B"]
    n_found = sum(r["found"])
    # snap sides near frame borders
    m = 0.01 * w
    if L is not None and L < m:
        L = 0
    if R is not None and R > w - m:
        R = w
    if T is not None and T < 0.01 * h:
        T = 0
    if B is not None and B > h - 0.01 * h:
        B = h
    ok = L is not None and R is not None and T is not None and B is not None
    if ok:
        bw, bh = R - L, B - T
        # sane webcam: smaller than 60% of frame width/height, contains the face
        contains = L <= fx and R >= fx + fw and T <= fy and B >= fy + fh
        sane = (
            0.08 < bw / w < 0.6
            and 0.08 < bh / h < 0.7
            and contains
            and bw > fw * 1.2
            and bh > fh * 1.2
        )
        if sane:
            try:
                sf = sample_frames(video, start, end, SNAP_FRAMES)
                nL, nT, nR, nB, raw = snap_edges(
                    sf if len(sf) >= 8 else frames, (L, T, R, B), face=(fx, fy, fw, fh)
                )
                if (
                    nR - nL > fw * 1.2
                    and nB - nT > fh * 1.2
                    and nL <= fx
                    and nR >= fx + fw
                    and nT <= fy
                    and nB >= fy + fh
                ):
                    L, T, R, B = nL, nT, nR, nB
                    bw, bh = R - L, B - T
                    r["notes"] = list(r["notes"]) + [f"snapped {raw}"]
            except (
                Exception
            ) as ex:  # snapping is a refinement: never lose the cam over it
                r["notes"] = list(r["notes"]) + [f"snap failed: {ex}"]
            box = [round(L / w, 4), round(T / h, 4), round(bw / w, 4), round(bh / h, 4)]
            conf = round(
                min(1.0, 0.55 + 0.25 * stab + 0.2 * (1 if n_found == 4 else 0.5)), 2
            )
            return {
                "mode": "cam",
                "box": box,
                "face": fracface,
                "confidence": conf,
                "reason": f"face stable in {hits}/{len(frames)} frames, rectangle edges found on {n_found}/4 sides {r['notes']}",
                "summary": f"cam: {where(box)}",
            }
    # fallback: tight 16:9 crop around the face (about 3x face width)
    cw = min(w, fw * 3.2)
    ch = cw * 9 / 16
    if ch < fh * 1.8:
        ch = fh * 1.8
        cw = ch * 16 / 9
    ccx, ccy = fx + fw / 2, fy + fh * 0.55
    x0 = min(max(0, ccx - cw / 2), w - cw)
    y0 = min(max(0, ccy - ch / 2), h - ch)
    box = [round(x0 / w, 4), round(y0 / h, 4), round(cw / w, 4), round(ch / h, 4)]
    conf = round(min(0.8, 0.35 + 0.4 * stab), 2)
    try:
        track = track_face(video, start, end, face)
    except Exception:
        track = []
    return {
        "mode": "face",
        "box": box,
        "face": fracface,
        "confidence": conf,
        "face_track": track,
        "reason": f"face stable in {hits}/{len(frames)} frames but no clean rectangle ({n_found}/4 sides found); face-centerd crop",
        "summary": f"face (no cam border): {where(box)}",
    }


def draw_debug(
    video: str | Path,
    res: dict[str, Any],
    out: str | Path,
    start: float | None = None,
    end: float | None = None,
) -> None:
    """Write a frame with the boxes drawn on it, to check an answer by eye."""
    frames = sample_frames(video, start, end, 3)
    if not frames:
        return
    f = frames[len(frames) // 2].copy()
    h, w = f.shape[:2]
    if res.get("box"):
        x, y, bw, bh = res["box"]
        col = (0, 255, 0) if res["mode"] == "cam" else (0, 200, 255)
        cv2.rectangle(
            f, (int(x * w), int(y * h)), (int((x + bw) * w), int((y + bh) * h)), col, 4
        )
    if res.get("face"):
        x, y, bw, bh = res["face"]
        cv2.rectangle(
            f,
            (int(x * w), int(y * h)),
            (int((x + bw) * w), int((y + bh) * h)),
            (255, 0, 0),
            2,
        )
    cv2.putText(
        f,
        f"{res['mode']} conf={res.get('confidence')}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (0, 0, 255),
        3,
    )
    cv2.imwrite(str(out), f)


def inner_edges(
    video: str | Path,
    start: float | None,
    end: float | None,
    face: Box,
    src_w: int,
    src_h: int,
    n: int = 12,
) -> tuple[int, int, int, int]:
    """The borders a webcam with no full frame does have, as (L, T, R, B) in pixels of the source.

    For a camera docked to a corner: the strongest straight line on each
    side of the face, held over sampled frames, also where the change over
    time jumps, since the camera and what is beside it move differently. A
    side with no clear line is the picture's edge.
    """
    cap = cv2.VideoCapture(str(video))
    g = []
    for k in range(n):
        cap.set(
            cv2.CAP_PROP_POS_MSEC,
            ((start or 0) + ((end or 0) - (start or 0)) * (k + 0.5) / n) * 1000,
        )
        ok, f = cap.read()
        if ok:
            g.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32))
    cap.release()
    if len(g) < 4:
        return (0, 0, src_w, src_h)
    med = np.median(np.stack(g), 0)
    H_, W_ = med.shape
    fx, fy, fw, fh = face[0] * W_, face[1] * H_, face[2] * W_, face[3] * H_
    dy = np.abs(cv2.Sobel(med, cv2.CV_32F, 0, 1, ksize=3))
    dx = np.abs(cv2.Sobel(med, cv2.CV_32F, 1, 0, ksize=3))
    # temporal: the screen and the camera change differently, so the border is also where std jumps
    sd = np.stack(g).std(0)

    def best_line(score, lo, hi):
        lo, hi = int(max(0, lo)), int(min(len(score) - 1, hi))
        if hi - lo < 3:
            return None
        seg = score[lo:hi]
        i = int(np.argmax(seg))
        m = np.median(score) + 1e-6
        return lo + i if seg[i] > 4 * m and seg[i] > 12 else None

    x0, x1 = int(max(0, fx - 2.5 * fw)), int(min(W_, fx + fw + 2.5 * fw))
    y0, y1 = int(max(0, fy - 2.0 * fh)), int(min(H_, fy + fh + 3.0 * fh))
    rows = dy[:, x0:x1].mean(1) + np.abs(np.diff(sd[:, x0:x1].mean(1), prepend=0)) * 0.5
    cols = dx[y0:y1, :].mean(0) + np.abs(np.diff(sd[y0:y1, :].mean(0), prepend=0)) * 0.5
    b = best_line(rows, fy + fh * 1.3, fy + fh * 4.0)
    t = best_line(rows, fy - fh * 2.5, fy - fh * 0.4)
    r = best_line(cols, fx + fw * 1.3, fx + fw * 4.0)
    l = best_line(cols, fx - fw * 3.0, fx - fw * 0.3)
    sx, sy = src_w / W_, src_h / H_
    L = (l + 3) * sx if l is not None else 0
    T = (t + 3) * sy if t is not None else 0
    R = (r - 2) * sx if r is not None else src_w
    B = (b - 2) * sy if b is not None else src_h
    return (int(L), int(T), int(R), int(B))


def main() -> None:
    """Find the webcam, say where it is, and write what was asked for."""
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    ap.add_argument("--json")
    ap.add_argument("--debug", help="write a JPG with the box drawn")
    a = ap.parse_args()
    res = find_cam(a.video, a.start, a.end)
    if res["mode"] == "none":
        line = f"no webcam found ({res['reason']}) -> use the blur layout"
    else:
        line = f"{res['summary']} (confidence {res['confidence']}; {res['reason']}) -> --cam {':'.join(f'{v:.3f}' for v in res['box'])}"
    print(line)
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    if a.debug:
        draw_debug(a.video, res, a.debug, a.start, a.end)


if __name__ == "__main__":
    main()
