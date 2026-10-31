# Anomaly model: GPU run and Hailo-8L handoff (Bakdaulet → adilnurgg / HyorinmaruK)

**Status 31 Oct:** pipeline written and smoke-tested locally (Mac, Apple MPS, `SIMULATED` data).
**No NVIDIA GPU run has happened yet.** Nothing below is a result until a `run_manifest.json`
with `GPU_model` ≠ `NONE` and the stated `source_origin` exists.

## What exists
- `qualityrelay17/anomaly.py` — STFPM (student–teacher feature pyramid matching, ResNet-18,
  BMVC 2021). Teacher frozen ImageNet; student trained on GOOD images only; anomaly = feature
  discrepancy. Chosen because it exports as **two plain CNNs** — Hailo can compile that; a
  PatchCore memory bank it cannot.
- `scripts/train_anomaly.py` — CLI. Data sources and tiers:
  `synthetic-cad` → `SIMULATED` (our STL silhouettes + synthetic chip/hole/stringing/warp),
  `mvtec --root <category>` → `EXTERNAL_DATASET`, `captured --root <dir>` → `PHYSICAL_CAPTURE`.
- Every run writes `runs/anomaly/<run_id>/run_manifest.json` in the **Resource-ledger** format
  from `GPU_AND_SPONSOR_EXECUTION_PLAN.md` (provider, instance, GPU, driver, CUDA, price/h,
  start/end, spend, dataset hash, model hash, seed, commit, tier), plus `metrics.json`,
  `teacher.onnx`, `student.onnx`, `student.pt`, `test_scores.npy`.
- Local smoke result (for the record, **not a claim**): synthetic-cad, 96 px, 96 train / 48 test,
  8 epochs on MPS → image AUROC 0.84, pixel AUROC 0.91. Synthetic defects on synthetic
  silhouettes; says the code runs, nothing about PLA parts.

## GPU run (Brev, L4 or A100 is enough — H100 not needed)
```bash
# on the instance (Ubuntu + CUDA image)
git clone https://github.com/Bakdaulet-omeraiuly/qualityrelay.git && cd qualityrelay
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-core.txt opencv-python-headless numpy trimesh
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124   # match image CUDA
pip install onnx

# 1) sanity on synthetic data (minutes)
python scripts/train_anomaly.py --data synthetic-cad --epochs 50 --size 256 --n-train 400 \
    --provider brev --instance-type "<as shown in Brev console>" --price-per-hour <USD/h from console>

# 2) MVTec AD category (download first; CC BY-NC-SA 4.0 — non-commercial, cite it)
#    https://www.mvtec.com/company/research/datasets/mvtec-ad  -> extract to data/mvtec/<category>
python scripts/train_anomaly.py --data mvtec --root data/mvtec/screw --epochs 100 --size 256 \
    --provider brev --instance-type "..." --price-per-hour ...

# 3) our prints, once HyorinmaruK has captures: data/prints/good/*.png, data/prints/defect/*.png
python scripts/train_anomaly.py --data captured --root data/prints --epochs 100 --size 256 ...
```
Copy the resulting `run_manifest.json` into `docs/research/runs/` if the run is cited anywhere.
**Stop the instance when done** — Brev bills by the hour.

## Hailo-8L handoff (owner: adilnurgg for the Pi, HyorinmaruK for the station)
Unverified by me — I have no Hailo toolchain here. Steps per Hailo's public Dataflow Compiler
docs; check each against the installed version:
1. Inputs: `teacher.onnx` + `student.onnx`, static `[1,3,S,S]`, opset 17, ImageNet
   normalisation baked **outside** the graph (the Pi code must normalise the same way:
   `(x/255 - mean)/std`, grayscale replicated to 3 channels).
2. `hailo parser onnx teacher.onnx` / `student.onnx` → `.har`.
3. Quantise with a calibration set of **good** images from the same source as training
   (≥ 64 images); `hailo optimize --calib-set-path ...`.
4. `hailo compiler` → `.hef` for Hailo-8L. Run both nets on the Pi, compute the per-pixel
   discrepancy (`0.5·‖norm(t)−norm(s)‖²` summed over the three levels, upsampled) and the image
   score (max of the Gaussian-blurred map) in numpy — exactly as `anomaly.anomaly_maps` /
   `evaluate` do, so Pi scores are comparable to the GPU evaluation.
5. Report the Pi result at the tier of its **data**, never higher; a quantised model's AUROC
   must be re-measured on the Pi, not copied from the GPU run.

## What this does not give us
A validated defect detector for our parts. It gives a reproducible way to get one if (a) GPU
time and (b) labelled captures of our prints exist. Until then the camera path stays the
OpenCV pixel-difference baseline described in `STATUS_AND_GATES.md`.
