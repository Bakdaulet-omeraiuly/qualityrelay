# Dual Vision + Reference Photo + CAD Compliance

**Owner:** Bakdaulet + HyorinmaruK  
**Status:** research design + partial reference implementation; see status below.

## Inputs and outputs
Input: phone photo, Pi photo, reference image(s) for same part and pose, CAD/STL revision, fiducial or geometry calibration, part ID, capture condition and (when approved) caliper measurements. Output: segmentation, image-quality estimate, reference difference, contour/feature comparison with confidence and evidence lineage, **not** a categorical dimensional proof from a freehand photo.

## Processing stages
1. Capture unique specimen/frame IDs and camera intrinsic/extrinsic metadata; phone and Pi capture independently.
2. Apply image quality gates: exposure, blur, pose, clipping, occlusion, calibration health.
3. Photo↔photo: align reference to camera frame, mask background, compare SSIM/edges/difference heatmaps; optionally evaluate Anomalib PatchCore/EfficientAD or NVIDIA TAO model (trained separately).
4. Photo↔CAD: render correct camera-angle CAD silhouette (top/front/side), compute mask IoU, contour and feature deviations, identify the expected slot width region, missing corners and silhouette warp; use explicit geometry registration. Simple convex hull alone can hide slot concavity and should **not** be reported as full CAD compliance.
5. Preserve source DAG: photo and CAD score derived from the same original image are correlated; never count as independent sensor observations.
6. Pi edge inference uses Hailo-compatible compiled weight if actually installed; otherwise honest OpenCV CPU fallback. Do not claim Hailo is CUDA.
7. Confidence from calibration sets or independent ground truth only, never invented LLM confidence.

## Measurement caveats
0.1 mm shifts require optical calibration, uncertainty budget, repeatability study and test against independent caliper/CMM. Operator-confirmed caliper reading remains the trusted dimensional reference; OCR is merely candidate text. Visible cracks do not automatically imply internal structural failure.

## Research hypothesis
Sensor fusion with matched pose + provenance + active retake should reduce unsafe releases at equal inspection cost compared with caliper-only, phone-only, Pi-only, photo↔photo-only, CAD-only and conservative rule-based multimodal fusion. An uncalibrated heatmap is not accuracy evidence.

## Implementation state
`vision.py` offers OpenCV pixel-difference baseline, silhouette IoU, coarse CAD projection; it DOES NOT ship trained NVIDIA inference, calibrated hardware or complete feature-level CAD rendering. `legacy/QualityRelay_15...zip` includes original dual-vision reference.

## Acceptance
- Independent captures and source digests for two cameras.
- Lighting shift and pose shift must lower trust / trigger recapture when out of calibration.
- Test split by *physical specimen and batch*, never adjacent frames.

