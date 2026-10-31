# QualityRelay Visual Inspection Integrations — Open-Source Feature Pack

**Status:** Implemented CPU visualization + model-output adapters + tested offline CLI. **NOT** a trained new defect detector, live website endpoint, physically validated quality decision, or sorter controller.

**Owner:** Bakdaulet (Computer Vision / research). Integration handoff: adilnurgg (API/Web). Physical photographs, specimens and calibration: HyorinmaruK.

## 1. What we can legally reuse

| Source | Useful capabilities | Licensing | Actual integration |
|---|---|---|---|
| [Roboflow Supervision](https://github.com/roboflow/supervision) | Model-agnostic bounding boxes, annotation, detection/tracking/evaluation | MIT for the library; upstream model terms remain separate | Optional real `sv.Detections` and `sv.BoxAnnotator` support via `--renderer supervision` |
| [Roboflow Inference](https://github.com/roboflow/inference) | Structured model predictions and server inference patterns | Apache-2.0 for **core** code, separately licensed model architectures/weights, commercial Enterprise functionality | **Parser of previously produced Roboflow prediction JSON**; no cloud calls or model deployed by this patch |
| [Anomalib](https://github.com/open-edge-platform/anomalib) | PatchCore, EfficientAD, STFPM, anomaly masks and heatmaps | Apache-2.0 code; weights and datasets have separate terms | Accept real HxW `.npy` score maps exported from an Anomalib model or our existing STFPM for visual review |
| [OpenCV](https://opencv.org/license/) | Reference comparison, heatmap overlay, component boxes, image quality gates | Apache-2.0 for OpenCV >=4.5 | Executable local photo-to-photo difference, regions, overlays and blur/exposure heuristics |
| [MVTec AD](https://www.mvtec.com/research-teaching/datasets/mvtec-ad) | Benchmark images, anomaly masks, pixel-level evaluation | CC BY-NC-SA 4.0, **noncommercial** data | **Not copied or downloaded**. Optional separate research only; not licensed for commercial resale |
| Instrumental, UnitX, Elementary, Siemens Inspekto | Root-cause timelines, camera inspection views, interactive dashboards | Commercial/proprietary: no general right to reuse their internals | **Design references only**, no assets/code copied |

**We did not clone commercial software, pretrained weights, Roboflow Universe models, or third-party datasets into this repository.** The public license of a framework does **not** determine the license of arbitrary models that run on it. Review Roboflow model licenses, in particular GPL/AGPL/commercial conditions, before choosing a weight for a service.

## 2. Implemented artifacts

- `qualityrelay17/inspection_visuals.py`: CPU-only functions `image_quality`, `reference_difference`, `candidate_regions`, `model_anomaly_map`, `roboflow_predictions`, `overlay_heatmap`, `draw_candidate_boxes`.
- `scripts/inspect_visual.py`: local CLI with modes `reference`, `anomaly-map`, and `roboflow-json`.
- `tests/test_inspection_visuals.py`: 7 new local tests, including actual CLI outputs.
- `requirements-vision-optional.txt`: optional Supervision renderer. Core vision still uses `requirements-demo.txt`; no new mandatory GPU deps.

Each CLI run outputs **`report.json`, `heatmap.png`, and `boxes.png`**.

### Reference photo vs live photo (OpenCV baseline)

```bash
python -m pip install -r requirements-demo.txt
python scripts/inspect_visual.py \
  --mode reference \
  --reference data/reference/slot_good_top.png \
  --reference-event-id reference-slot-v3 --reference-root ref-photo-root-v3 \
  --live data/captures/slot_007_top.png \
  --specimen-id slot-007 --event-id phone-slot-007 --source-root phone-photo-root-007 \
  --station-id PHONE --source-tier PHYSICAL_CAPTURE --aligned \
  --out runs/visual/slot-007
```

**IMPORTANT:** `--aligned` is a *user assertion* that the images are already registered, not an alignment solver. Uncontrolled lighting, pose, optics and calibration can produce false positives or hide defects. This baseline does not measure a 0.1-mm clearance.

### Model-produced heatmap (current STFPM, Anomalib PatchCore/EfficientAD, etc.)

Export an **actually computed** HxW anomaly map to `score_map.npy` from a trained model. The current QualityRelay STFPM pipeline exposes `anomaly_maps(teacher, student, x, out_size)`. No model is trained or loaded by this visualization tool.

```bash
python scripts/inspect_visual.py \
  --mode anomaly-map \
  --live data/captures/slot_007_top.png \
  --anomaly-map runs/stfpm/score_map.npy --model-id stfpm-run-2026-10-31 \
  --raw-threshold 0.45 \
  --specimen-id slot-007 --event-id phone-slot-007 --source-root phone-photo-root-007 \
  --station-id PHONE --source-tier PHYSICAL_CAPTURE \
  --out runs/visual/slot-007-stfpm
```

**Example threshold 0.45 is arbitrary, NOT calibrated.** Set thresholds using held-out physical part/lot/session splits; record the checkpoint, version, model score distribution, calibration dataset and actual ground truth. Anomalib training remains in a separate environment to avoid dependency conflicts with the current Brev STFPM pipeline.

### Roboflow Inference result normalization (no actual API invocation)

Save a real Roboflow-style prediction JSON, where `x,y` are box center coordinates in pixels:

```json
{"predictions":[{"x":220,"y":130,"width":44,"height":25,"confidence":0.81,"class":"scratch"}]}
```

```bash
python scripts/inspect_visual.py \
  --mode roboflow-json \
  --live data/captures/slot_007_top.png --predictions-json predictions.json \
  --model-id external-roboflow-version \
  --specimen-id slot-007 --event-id phone-slot-007 --source-root phone-photo-root-007 \
  --station-id PHONE --source-tier PHYSICAL_CAPTURE \
  --out runs/visual/slot-007-roboflow
```

This mode **does not run Roboflow Inference or transmit an image**. It converts existing predictions into QualityRelay candidate regions. `raw_model_confidence` is an unverified score, not a calibrated probability.

### Optional Supervision annotation renderer

```bash
python -m pip install -r requirements-vision-optional.txt
# append --renderer supervision to any CLI example
```

Supervision is only a rendering adapter here; optional package unavailability does not block the default OpenCV output.

## 3. Source provenance and SAFE-MESH boundary

Every report contains `specimen_id`, `image_event_id`, `station_id`, `source_root`, `source_tier`, `method`, `derived_from`, warnings and uncalibrated candidate regions. Report status is `UNVERIFIED_VISUAL_CANDIDATE`. It can return `REVIEW_REQUIRED` or `RECAPTURE_REQUIRED`, **never automatic PASS**.

- Different model maps from **one original image** share one source root. They are correlated derivatives, not independent phone/Pi sources.
- A report from `PHYSICAL_CAPTURE` is **not** equivalent to independently verified metrology or an authenticated sensor record.
- No code in this patch signs physical evidence, authorizes a sorter, emits ESP32 commands or bypasses `safe_mesh.py`.
- The photo-to-CAD registration, calibrated geometry and real two-camera inference remain separate tasks from `docs/architectures/03_DUAL_VISION_AND_CAD.md`.

## 4. Team handoff and remaining work

**Bakdaulet:** Compare held-out current STFPM versus separately validated Anomalib PatchCore/EfficientAD, photo-reference and CAD silhouettes; evaluate image/pixel metrics, uncertainties, cross-batch shifts, and shared illumination errors. CAPE may consume *validated* evidence and costed inspections; never infer monetary loss from arbitrary raw heatmap color.

**adilnurgg:** Expose authenticated upload-limited `/vision/*` preview routes and web gallery; show region boxes/heatmaps with `source_tier` and provenance; use actual trusted model-worker calls if available. Keep the sensor-authenticated physical gateway and SAFE-MESH entirely separate. This patch itself is **CLI + reusable library, not the live website**.

**HyorinmaruK:** Produce labeled images of printed parts and reference CAD revisions, controlled two-camera calibration/lighting, independent caliper truth and physical timing measurements. Presentation must distinguish model predictions from verified defects.

**Not implemented yet:** train or load an external PatchCore/EfficientAD checkpoint, connect to Roboflow Cloud, implement automatic image registration/CAD compliance, deploy Hailo inference, integrate into web UI, or validate classification accuracy on real specimens.

## 5. Tests

```bash
python -m pytest -q tests/test_inspection_visuals.py
python -m pytest -q
```

Local verification on QualityRelay 18 source baseline: **7 new tests passed; 118 total tests passed** (the baseline had 111). Running GitHub CI after integrating this branch and other open PRs is a separate required verification step. Model benchmarks and physical camera validation have **not** been performed by these tests.

**Novelty boundary:** The new library is a practical visual-inspection integration, not CAPE's proposed scientific discovery. Our original research remains provenance-aware multiagent evidence acquisition, capacity-aware inspection and safety-verified action—not the heatmap or bounding boxes themselves.
