"""Model-agnostic visual inspection artifacts for QualityRelay.

A CPU-only, read-only *candidate visualization* layer. No learned model or weight is
bundled; outputs are NOT calibrated defect probabilities, metrology measurements,
signed physical evidence, PASS decisions, or sorter commands. Inferences from one
photo share its source_root even when produced by multiple models.

Inspired by the optional capabilities of Roboflow Supervision, OpenCV, Anomalib,
and Roboflow Inference, without copying their source code.
"""
from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

SOURCE_TIERS = {"SIMULATED", "PHYSICAL_CAPTURE", "EXTERNAL_DATASET"}
MAX_PIXELS = 4096 * 4096
MAX_REGIONS = 50


def _image_u8(image: np.ndarray, name: str) -> np.ndarray:
    image = np.asarray(image)
    if image.dtype != np.uint8 or image.ndim not in (2, 3):
        raise ValueError(f"{name} must be a uint8 HxW or HxWx3 image")
    if image.ndim == 3 and image.shape[2] != 3:
        raise ValueError(f"{name} color image must have 3 channels")
    if min(image.shape[:2]) < 4 or image.shape[0] * image.shape[1] > MAX_PIXELS:
        raise ValueError(f"{name} has unsupported size")
    return image


def _gray(image: np.ndarray, name: str) -> np.ndarray:
    im = _image_u8(image, name)
    return cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) if im.ndim == 3 else im


def image_quality(image: np.ndarray) -> dict[str, Any]:
    """Uncalibrated heuristics for likely unusable (blurred/underexposed) captures."""
    im = _gray(image, "image")
    blur_variance = float(cv2.Laplacian(im, cv2.CV_64F).var())
    dark_fraction = float(np.mean(im <= 12))
    bright_fraction = float(np.mean(im >= 243))
    warnings = []
    if blur_variance < 15.0:
        warnings.append("LOW_EDGE_DETAIL_OR_BLUR")
    if dark_fraction > 0.75:
        warnings.append("MOSTLY_DARK")
    if bright_fraction > 0.75:
        warnings.append("MOSTLY_CLIPPED_BRIGHT")
    return {
        "blur_laplacian_variance": blur_variance,
        "dark_fraction": dark_fraction,
        "bright_fraction": bright_fraction,
        "warnings": warnings,
        "heuristics_calibrated": False,
    }


def _metadata(*, specimen_id: str, image_event_id: str, source_root: str,
              source_tier: str, station_id: str, calibration_id: str | None = None) -> dict[str, Any]:
    for key, value in (("specimen_id", specimen_id), ("image_event_id", image_event_id),
                       ("source_root", source_root), ("station_id", station_id)):
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError(f"{key} must be a nonempty identifier <=160 characters")
    if source_tier not in SOURCE_TIERS:
        raise ValueError("source_tier must be SIMULATED, PHYSICAL_CAPTURE, or EXTERNAL_DATASET")
    if calibration_id is not None and (not isinstance(calibration_id, str) or not calibration_id.strip()):
        raise ValueError("calibration_id must be nonempty or omitted")
    return {
        "specimen_id": specimen_id, "image_event_id": image_event_id,
        "station_id": station_id, "source_root": source_root,
        "source_tier": source_tier, "calibration_id": calibration_id,
    }


def _map2d(map_data: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    a = np.asarray(map_data)
    if a.ndim != 2 or a.shape != shape or a.size > MAX_PIXELS:
        raise ValueError("anomaly map must be finite HxW matching the image")
    if not np.issubdtype(a.dtype, np.number) or not np.all(np.isfinite(a)):
        raise ValueError("anomaly map contains non-finite/non-numeric values")
    return a.astype(np.float32)


def candidate_regions(mask: np.ndarray, *, min_area_px: int = 9,
                      max_regions: int = MAX_REGIONS) -> list[dict[str, Any]]:
    """Return bounding boxes around connected candidate regions, not proof of defects."""
    if not isinstance(min_area_px, int) or min_area_px < 1:
        raise ValueError("min_area_px must be a positive integer")
    if not isinstance(max_regions, int) or not 1 <= max_regions <= MAX_REGIONS:
        raise ValueError("max_regions must be 1..50")
    a = np.asarray(mask)
    if a.ndim != 2 or a.size > MAX_PIXELS or a.size == 0:
        raise ValueError("mask must be 2D with supported size")
    a = np.ascontiguousarray((a > 0).astype(np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(a, connectivity=8)
    result = []
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area >= min_area_px:
            result.append({"x1": x, "y1": y, "x2": x + w, "y2": y + h,
                           "area_px": area, "label": "CANDIDATE_ANOMALY"})
    return sorted(result, key=lambda a: (-a["area_px"], a["y1"], a["x1"]))[:max_regions]


def _report(meta: dict[str, Any], method: str, quality: dict[str, Any],
            regions: list[dict[str, Any]], *, derived_from: list[str],
            signal: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "visual-inspection-v1",
        **meta,
        "method": method,
        "derived_from": derived_from,
        "evidence_status": "UNVERIFIED_VISUAL_CANDIDATE",
        "physical_ground_truth_verified": False,
        "calibrated_defect_probability": None,
        "decision": "RECAPTURE_REQUIRED" if quality["warnings"] else "REVIEW_REQUIRED",
        "requires_safe_mesh_and_human_review": True,
        "quality": quality,
        "signal": signal,
        "regions": regions,
        "warnings": sorted(set((warnings or []) + quality["warnings"])),
        "claim_boundary": "Visualization only: not a validated defect diagnosis, dimension measurement, safety PASS, or independent evidence source.",
    }


def reference_difference(reference: np.ndarray, live: np.ndarray, *,
                         specimen_id: str, image_event_id: str, source_root: str,
                         reference_event_id: str, reference_root: str,
                         station_id: str, source_tier: str, aligned: bool,
                         calibration_id: str | None = None, threshold: int = 40,
                         min_area_px: int = 9) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    """Photo-to-photo difference after *externally established* pose alignment.

    Never silently register the images. Same lighting/pose conditions are required;
    a user assertion of alignment is not independent proof of geometric accuracy.
    """
    if not aligned:
        raise ValueError("aligned=True is required; images must be registered externally")
    meta = _metadata(specimen_id=specimen_id, image_event_id=image_event_id,
                     source_root=source_root, source_tier=source_tier,
                     station_id=station_id, calibration_id=calibration_id)
    if source_root == reference_root or not reference_root or not reference_event_id:
        raise ValueError("reference requires a distinct nonempty source root and event ID")
    if not isinstance(threshold, int) or not (0 <= threshold <= 255):
        raise ValueError("pixel threshold must be an integer in [0,255]")
    a, b = _gray(reference, "reference"), _gray(live, "live")
    if a.shape != b.shape:
        raise ValueError("reference and live image must be same registered shape")
    difference = cv2.absdiff(a, b)
    mask = (difference > threshold).astype(np.uint8)
    quality = image_quality(live)
    warnings = ["POSE_ALIGNMENT_NOT_INDEPENDENTLY_VERIFIED", "PIXEL_DIFF_SENSITIVE_TO_LIGHTING"]
    if not calibration_id:
        warnings.append("NO_CAMERA_CALIBRATION_ID")
    regions = candidate_regions(mask, min_area_px=min_area_px)
    report = _report(meta, "opencv_absdiff_reference_v1", quality, regions,
                     derived_from=[image_event_id, reference_event_id],
                     signal={"difference_fraction": float(np.mean(mask)),
                             "pixel_absdiff_threshold": threshold,
                             "pixel_score_is_probability": False}, warnings=warnings)
    report["reference_root"] = reference_root
    report["reference_event_id"] = reference_event_id
    return report, difference.astype(np.float32), mask


def model_anomaly_map(live: np.ndarray, map_data: np.ndarray, *,
                      specimen_id: str, image_event_id: str, source_root: str,
                      station_id: str, source_tier: str, model_id: str,
                      raw_threshold: float, calibration_id: str | None = None,
                      min_area_px: int = 9) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    """Visualize STFPM/Anomalib/PatchCore/EfficientAD maps from actual model inference.

    The caller must supply a real output map and identify its model. No inference is
    faked, and different scores from the same image do not become independent evidence.
    """
    meta = _metadata(specimen_id=specimen_id, image_event_id=image_event_id,
                     source_root=source_root, source_tier=source_tier,
                     station_id=station_id, calibration_id=calibration_id)
    if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 160:
        raise ValueError("model_id is required")
    if not math.isfinite(raw_threshold):
        raise ValueError("raw_threshold must be finite")
    im = _gray(live, "live")
    amap = _map2d(map_data, im.shape)
    mask = (amap >= raw_threshold).astype(np.uint8)
    regions = candidate_regions(mask, min_area_px=min_area_px)
    quality = image_quality(live)
    warnings = ["RAW_THRESHOLD_REQUIRES_HELD_OUT_CALIBRATION"]
    report = _report(meta, "external_or_stfpm_anomaly_map_v1", quality, regions,
                     derived_from=[image_event_id],
                     signal={"model_id": model_id, "raw_score_max": float(np.max(amap)),
                             "raw_score_mean": float(np.mean(amap)),
                             "raw_threshold": float(raw_threshold),
                             "score_is_calibrated_probability": False}, warnings=warnings)
    return report, amap, mask


def roboflow_predictions(live: np.ndarray, payload: dict[str, Any], *,
                         specimen_id: str, image_event_id: str, source_root: str,
                         station_id: str, source_tier: str, model_id: str,
                         calibration_id: str | None = None) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    """Normalize already-obtained Roboflow Inference bbox JSON; no network calls.

    Roboflow box x/y are box center with width/height in pixels. These are
    *untrusted model predictions*, never verified evidence or CAD measurements.
    """
    meta = _metadata(specimen_id=specimen_id, image_event_id=image_event_id,
                     source_root=source_root, source_tier=source_tier,
                     station_id=station_id, calibration_id=calibration_id)
    im = _gray(live, "live")
    h, w = im.shape
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id is required")
    if not isinstance(payload, dict) or not isinstance(payload.get("predictions"), list):
        raise ValueError("expected {'predictions': [...]} Roboflow JSON")
    predictions = payload["predictions"]
    if len(predictions) > 1000:
        raise ValueError("too many predictions")
    regions = []
    mask = np.zeros((h, w), dtype=np.uint8)
    for p in predictions:
        if not isinstance(p, dict):
            raise ValueError("prediction must be an object")
        try:
            x, y, pw, ph, conf = (float(p[k]) for k in ("x", "y", "width", "height", "confidence"))
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("prediction missing numeric bbox/confidence") from exc
        if not all(math.isfinite(v) for v in (x, y, pw, ph, conf)) or pw <= 0 or ph <= 0 or not 0 <= conf <= 1:
            raise ValueError("invalid prediction size or confidence")
        x1 = max(0, int(math.floor(x - pw / 2)))
        y1 = max(0, int(math.floor(y - ph / 2)))
        x2 = min(w, int(math.ceil(x + pw / 2)))
        y2 = min(h, int(math.ceil(y + ph / 2)))
        if x1 >= x2 or y1 >= y2:
            continue
        mask[y1:y2, x1:x2] = 1
        name = p.get("class", "unknown")
        if not isinstance(name, str):
            name = "unknown"
        regions.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "area_px": (x2 - x1) * (y2 - y1), "label": "CANDIDATE_ANOMALY",
                        "model_class_unverified": name[:100], "raw_model_confidence": conf})
    regions = sorted(regions, key=lambda v: (-v["raw_model_confidence"], -v["area_px"]))[:MAX_REGIONS]
    report = _report(meta, "roboflow_prediction_adapter_v1", image_quality(live), regions,
                     derived_from=[image_event_id],
                     signal={"model_id": model_id, "raw_prediction_count": len(predictions),
                             "confidence_is_calibrated_probability": False},
                     warnings=["MODEL_LICENSE_AND_WEIGHT_TERMS_REQUIRE_REVIEW"])
    return report, mask.astype(np.float32), mask


def overlay_heatmap(image: np.ndarray, scores: np.ndarray, *,
                    mask: np.ndarray | None = None, alpha: float = 0.5) -> np.ndarray:
    """Render a visually useful heatmap on BGR uint8 image, without changing evidence."""
    im = _image_u8(image, "image")
    if not (0 <= alpha <= 1):
        raise ValueError("alpha must be 0..1")
    bgr = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR) if im.ndim == 2 else im.copy()
    raw = _map2d(scores, im.shape[:2])
    if mask is None:
        active = raw > 0
    else:
        m = np.asarray(mask)
        if m.shape != im.shape[:2]:
            raise ValueError("mask shape mismatch")
        active = m > 0
    if not np.any(active):
        return bgr
    low, high = float(np.min(raw[active])), float(np.max(raw[active]))
    if high > low:
        normalized = np.clip((raw - low) / (high - low), 0, 1)
    else:
        normalized = np.zeros_like(raw)
        normalized[active] = 1.0 if high > 0 else 0.0
    heat = cv2.applyColorMap(np.uint8(np.round(normalized * 255)), cv2.COLORMAP_TURBO)
    blend = cv2.addWeighted(bgr, 1 - alpha, heat, alpha, 0)
    bgr[active] = blend[active]
    return bgr


def draw_candidate_boxes(image: np.ndarray, report: dict[str, Any], *,
                         renderer: str = "opencv") -> np.ndarray:
    """Annotate candidates. Renderer 'supervision' requires optional MIT package."""
    im = _image_u8(image, "image")
    canvas = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR) if im.ndim == 2 else im.copy()
    boxes = np.asarray([[r[k] for k in ("x1", "y1", "x2", "y2")]
                        for r in report["regions"]], dtype=np.int32).reshape(-1, 4)
    if renderer == "supervision":
        try:
            import supervision as sv
        except ImportError as exc:
            raise ImportError("pip install supervision to use the optional renderer") from exc
        return sv.BoxAnnotator().annotate(scene=canvas, detections=sv.Detections(xyxy=boxes))
    if renderer != "opencv":
        raise ValueError("renderer must be opencv or supervision")
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(canvas, (int(x1), int(y1)), (int(x2 - 1), int(y2 - 1)), (0, 210, 255), 2)
    return canvas
