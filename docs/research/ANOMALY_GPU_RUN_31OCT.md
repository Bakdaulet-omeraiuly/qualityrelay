# Anomaly detector — first NVIDIA GPU run, 31 October 2026

**Owner:** Bakdaulet. **Hardware:** Brev, GCP `g2-standard-4:nvidia-l4:1` — NVIDIA L4 24 GB, driver
580.178.04, CUDA 12.4, torch 2.6.0+cu124, $0.85/h. **Code:** `qualityrelay17/anomaly.py` at commit
`d05bd2c` (branch `science/anomaly-pipeline`; the instance received a `git archive` tarball,
sha256 `85243117…38ef`, so `git_commit` in the manifests reads `UNKNOWN` — the tarball hash is the
provenance). **Manifests:** `docs/research/runs/<run_id>/run_manifest.json` (Resource-ledger
format) + `metrics.json`; full console log `docs/research/runs/brev_l4_run_31oct.log`.

Three runs, one after the other, ~4.5 min of GPU time in total (ledger `total_spend` ≈ $0.06;
instance uptime ≈ 15 min ≈ $0.21). Instance stopped afterwards.

| Run | Data | Tier | Train / test | Size · epochs | Image AUROC | Pixel AUROC | Export |
|---|---|---|---|---|---|---|---|
| `…052135Z-synthetic-cad-s0` | our STL silhouettes + synthetic chip/hole/stringing/warp | **SIMULATED** | 400 / 200 (100 defect) | 256 · 50 | **0.880** | 0.797 | teacher+student ONNX ok |
| `…052332Z-mvtec-s0` | MVTec AD `screw` (HF mirror `foersben/mvtec-ad`) | **EXTERNAL_DATASET** | 320 / 160 (119 defect) | 256 · 100 | **0.948** | 0.882 | ok |
| `…052528Z-mvtec-s0` | MVTec AD `bottle` (same mirror) | **EXTERNAL_DATASET** | 209 / 83 (63 defect) | 256 · 100 | **1.000** | 0.983 | ok |

## What these numbers mean — and do not

- **They mean the pipeline is real:** STFPM trains on an NVIDIA GPU, scores held-out defects,
  exports two ONNX graphs with recorded hashes, and the manifest carries hardware, spend, data
  hash and seed. `bottle` at 1.000 / `screw` at 0.948 are in the neighbourhood of the published
  STFPM numbers for those categories (bottle 1.00, screw ~0.97–0.99 at full resolution with
  longer training) — i.e. the implementation is not broken. Not a new result; MVTec AD is a
  public benchmark and this is a minimal re-implementation.
- **They say nothing about our printed parts.** No `PHYSICAL_CAPTURE` run exists. The
  synthetic-cad row is silhouettes of our STLs with hand-made defect geometry; its per-type
  scores show exactly where a silhouette model is blind: `warp` (score 0.53 vs good 0.45) is barely
  separated, `stringing` (1.02) and `chip` (0.92) are easy. Real PLA defects do not look like this.
- **MVTec AD is CC BY-NC-SA 4.0** — non-commercial research use only; the mirror carries the
  original `license.txt` and `readme.txt`. Cite MVTec if a number is shown.
- The two MVTec runs used **no held-out seed sweep and no hyper-parameter search** — one seed
  (0), the defaults in `TrainConfig`. Variance across seeds is unmeasured.

## Honest comparison to the night-before plan ("fine-tune on H100 + our captured prints")

| Planned | Done | Gap |
|---|---|---|
| H100 | L4 ($0.85/h) — sufficient; H100 would have been waste | none that matters |
| MVTec AD | 2 of 15 categories (screw, bottle) | run the rest only if a slide needs it |
| our captured prints | **none captured yet** (HyorinmaruK's station not built when this ran) | the only gap that matters |
| hand to Hailo-8L | ONNX exported, compile steps written, **not compiled or run on a Pi** | adilnurgg/HyorinmaruK, `ANOMALY_MODEL_HANDOFF.md` |

## Next (only when captures exist)
```bash
python scripts/train_anomaly.py --data captured --root data/prints --epochs 100 --size 256 \
    --provider brev --instance-type "g2-standard-4:nvidia-l4:1" --price-per-hour 0.85
```
Folder layout `data/prints/good/*.png`, `data/prints/defect/*.png`; ≥ 30 good images from the
Pi camera under the demo lighting, with the specimen IDs logged per `EXPERIMENT_PROTOCOL.md`.
Report at tier `PHYSICAL_CAPTURE`, and only after a second person labelled the defects.
