"""I3: Slot/Tab width from one photo (iPhone or webcam) with an ArUco marker as the scale reference.

Method: detect the 4x4 ArUco marker (known side, mm) -> homography from its corners to a metric
plane -> rectify the whole photo to a top-down image at a fixed px/mm -> segment the part ->
take the cross-section at mid-length along the part's long axis -> the material spans give the tab
width (one span) or the slot opening (gap between two spans). It is the same cross-section rule
used to measure the CAD meshes (sim/cad.py).

Status: validated on SYNTHETIC rendered photos only (validate_synthetic). Physical accuracy must be
measured against caliper readings (PHY-03) before any reading is trusted; until then a result is
a PHYSICAL_CAPTURE measurement with UNVALIDATED accuracy, never VERIFIED_PHYSICAL.
"""
from __future__ import annotations
from pathlib import Path

import cv2
import numpy as np

DICT = cv2.aruco.DICT_4X4_50
MARKER_ID = 7


def _detector():
    prm = cv2.aruco.DetectorParameters()
    prm.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX   # v2: sub-pixel marker corners
    return cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(DICT), prm)


def _subpixel_edges(profile, fg, bg):
    """v2: positions where the intensity profile crosses the 50% level between part and background,
    linearly interpolated (sub-pixel). Returns the crossing positions in pixel units."""
    level = (fg + bg) / 2.0
    d = profile - level
    idx = np.nonzero(np.sign(d[:-1]) != np.sign(d[1:]))[0]
    return [i + d[i] / (d[i] - d[i + 1]) for i in idx if d[i] != d[i + 1]]


def make_marker_sheet(path, marker_mm: float = 20.0, dpi: int = 600) -> Path:
    """Printable sheet: one ArUco marker of `marker_mm` with a 50 mm check ruler. Print at 100% and
    check the ruler with the caliper; the measured marker side is what should be used."""
    pxmm = dpi / 25.4
    W, H = int(90 * pxmm), int(70 * pxmm)
    sheet = np.full((H, W), 255, np.uint8)
    side = int(round(marker_mm * pxmm))
    mk = cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(DICT), MARKER_ID, side)
    x0, y0 = int(10 * pxmm), int(10 * pxmm)
    sheet[y0:y0 + side, x0:x0 + side] = mk
    ry = int(50 * pxmm)
    cv2.line(sheet, (x0, ry), (x0 + int(50 * pxmm), ry), 0, max(1, int(0.3 * pxmm)))
    for k in range(0, 51, 5):
        x = x0 + int(k * pxmm); cv2.line(sheet, (x, ry - int((3 if k % 10 == 0 else 1.5) * pxmm)), (x, ry), 0, max(1, int(0.2 * pxmm)))
    cv2.putText(sheet, f'QualityRelay ArUco id {MARKER_ID} - {marker_mm:g} mm - print at 100%, check 50 mm ruler',
                (x0, int(62 * pxmm)), cv2.FONT_HERSHEY_SIMPLEX, 0.09 * pxmm / 5, 0, max(1, int(0.15 * pxmm)))
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), sheet)
    return path


def measure_part_width(img_bgr, marker_mm: float = 20.0, px_per_mm: float = 20.0, part_is_dark: bool | None = None) -> dict:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    corners, ids, _ = _detector().detectMarkers(gray)
    if ids is None or MARKER_ID not in ids.flatten():
        return dict(status='NO_MARKER', note=f'ArUco 4x4 id {MARKER_ID} not found; print the marker sheet and keep it in the same plane as the part')
    c = corners[list(ids.flatten()).index(MARKER_ID)].reshape(4, 2).astype(np.float32)
    s = marker_mm * px_per_mm
    # place the marker's metric square in a large canvas so the whole part fits
    pad = 140 * px_per_mm
    dst = np.float32([[pad, pad], [pad + s, pad], [pad + s, pad + s], [pad, pad + s]])
    Hm = cv2.getPerspectiveTransform(c, dst)
    size = int(2 * pad + s)
    rect = cv2.warpPerspective(gray, Hm, (size, size), flags=cv2.INTER_LINEAR, borderValue=int(np.median(gray)))
    # mask the marker (and its quiet zone) out, then segment
    m0 = int(pad - 0.3 * s); m1 = int(pad + 1.3 * s)
    work = rect.copy(); work[m0:m1, m0:m1] = int(np.median(rect))
    blur = cv2.GaussianBlur(work, (5, 5), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if part_is_dark is None:  # the part is the minority class
        part_is_dark = (th == 0).mean() < 0.5
    mask = (th == 0) if part_is_dark else (th == 255)
    mask = cv2.morphologyEx(mask.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n < 2:
        return dict(status='NO_PART', note='no part segmented; use a contrasting background')
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    part = (lab == k).astype(np.uint8)
    cnts, _ = cv2.findContours(part, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    (cx, cy), (w, h), ang = cv2.minAreaRect(max(cnts, key=cv2.contourArea))
    if w < h:
        ang += 90; w, h = h, w
    # rotate so the long axis is horizontal, then read the mid-length cross-section(s)
    M = cv2.getRotationMatrix2D((cx, cy), ang, 1.0)
    rot = cv2.warpAffine(part * 255, M, (size, size), flags=cv2.INTER_NEAREST)
    rot_gray = cv2.warpAffine(rect.astype(np.float32), M, (size, size), flags=cv2.INTER_LINEAR, borderValue=float(np.median(rect)))
    ys, xs = np.nonzero(rot)
    x_min, x_max = xs.min(), xs.max()
    fg = float(np.median(rot_gray[rot > 0])); bg = float(np.median(rot_gray[(rot == 0)]))
    widths, kinds = [], []
    for frac in np.linspace(0.42, 0.58, 9):  # nine nearby sections; median is robust to a burr
        x = int(x_min + frac * (x_max - x_min))
        col = rot[:, x] > 0
        idx = np.nonzero(col)[0]
        if len(idx) == 0:
            continue
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        spans = [(r[0], r[-1] + 1) for r in runs if len(r) > 2]
        prof = rot_gray[:, max(0, x - 2):x + 3].mean(axis=1)
        y_lo, y_hi = max(0, spans[0][0] - 8) if spans else 0, min(size, spans[-1][1] + 8) if spans else size
        e = [y_lo + v for v in _subpixel_edges(prof[y_lo:y_hi], fg, bg)]
        if len(spans) == 2 and len(e) == 4:
            widths.append((e[2] - e[1]) / px_per_mm); kinds.append('slot_opening')
        elif len(spans) == 1 and len(e) == 2:
            widths.append((e[1] - e[0]) / px_per_mm); kinds.append('tab_width')
    if not widths:
        return dict(status='NO_SECTION')
    kind = max(set(kinds), key=kinds.count)
    vals = [w_ for w_, k_ in zip(widths, kinds) if k_ == kind]
    marker_px = float(np.mean([np.linalg.norm(c[i] - c[(i + 1) % 4]) for i in range(4)]))
    return dict(status='MEASURED', kind=kind, width_mm=round(float(np.median(vals)), 3),
                length_mm=round(float((x_max - x_min) / px_per_mm), 2), photo_px_per_mm=round(marker_px / marker_mm, 2),
                accuracy='UNVALIDATED_ON_REAL_PHOTOS (synthetic MAE in docs); compare with caliper before trusting',
                source_tier='PHYSICAL_CAPTURE')


# ---- synthetic validation ----------------------------------------------------------------------------

def render_synthetic(kind: str, width_mm: float, rng, photo_px_per_mm=15.0, outer_mm=None):
    """Top-down scene in mm drawn at 40 px/mm, then a random camera homography, blur and noise."""
    R = 40.0
    W, H = int(160 * R), int(110 * R)
    img = np.full((H, W), 205, np.uint8)
    x0, y0 = 50 * R, 30 * R
    if kind == 'tab':
        cv2.rectangle(img, (int(x0), int(y0)), (int(x0 + 60 * R), int(y0 + width_mm * R)), 45, -1)
    else:
        outer = outer_mm or width_mm + 12.0
        cv2.rectangle(img, (int(x0), int(y0)), (int(x0 + 60 * R), int(y0 + outer * R)), 45, -1)
        g0 = y0 + (outer - width_mm) / 2 * R
        cv2.rectangle(img, (int(x0 + 12 * R), int(g0)), (int(x0 + 60 * R) + 2, int(g0 + width_mm * R)), 205, -1)
    side = int(20 * R)
    mk = cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(DICT), MARKER_ID, side)
    mx, my = int(12 * R), int(30 * R)
    img[my - int(2 * R):my + side + int(2 * R), mx - int(2 * R):mx + side + int(2 * R)] = 255
    img[my:my + side, mx:mx + side] = mk
    # random camera: scale to the target photo resolution + mild perspective / rotation
    s = photo_px_per_mm / R
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    jitter = rng.uniform(-0.06, 0.06, (4, 2)) * [W, H]
    dst = (src + jitter) * s
    dst -= dst.min(axis=0) - 20
    Hc = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
    out_w, out_h = int(dst[:, 0].max() + 20), int(dst[:, 1].max() + 20)
    photo = cv2.warpPerspective(img, Hc, (out_w, out_h), flags=cv2.INTER_AREA, borderValue=205)
    photo = cv2.GaussianBlur(photo, (3, 3), rng.uniform(0.3, 1.0))
    photo = np.clip(photo + rng.normal(0, 4, photo.shape), 0, 255).astype(np.uint8)
    return cv2.cvtColor(photo, cv2.COLOR_GRAY2BGR)


def validate_synthetic(n=40, seed=0, photo_px_per_mm=15.0):
    rng = np.random.default_rng(seed); errs = []; fails = 0
    cases = [('tab', 19.8), ('tab', 20.0), ('tab', 20.3), ('slot', 20.7), ('slot', 21.0), ('slot', 21.2)]
    for i in range(n):
        kind, wmm = cases[i % len(cases)]
        wmm = wmm + rng.uniform(-0.15, 0.15)
        r = measure_part_width(render_synthetic(kind, wmm, rng, photo_px_per_mm))
        expect = 'tab_width' if kind == 'tab' else 'slot_opening'
        if r.get('status') != 'MEASURED' or r['kind'] != expect:
            fails += 1; continue
        errs.append(r['width_mm'] - wmm)
    e = np.abs(errs)
    return dict(origin='SIMULATED', n=n, photo_px_per_mm=photo_px_per_mm, failures=fails,
                mae_mm=round(float(e.mean()), 4) if len(e) else None, p95_abs_err_mm=round(float(np.percentile(e, 95)), 4) if len(e) else None,
                bias_mm=round(float(np.mean(errs)), 4) if errs else None, pass_bar='MAE <= 0.10 mm at >= 12 px/mm')
