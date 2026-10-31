# Scientific and implementation claims — evidence register

| Claim | Status | Evidence |
|---|---|---|
| 21 role specifications | Implemented reference | team-owned copied 14.2 roles registry, tests |
| Role-specific allowlist tools | Implemented reference | `agent_tools.py`, permission tests |
| Nebius LLM works with team API credentials | **NOT RUN** | opt-in adapter only |
| Photo/photo comparator exists | Implemented simple baseline | OpenCV / browser pixel-difference and tests |
| Photo/CAD geometry proof | **NOT CALIBRATED** | STL 2D orthographic mask helper, no pose-aware tolerance proof |
| Two physical independent camera stations working | **NOT VALIDATED** | 15.0 dual-station test fixture preserved |
| Evidence lineage and HMAC validated | Reference unit test | HMAC station envelope + lineage DAG, security limitations |
| Decentralized real deployment | **NOT DEPLOYED** | research contracts and original 15.0 separate SQLite services |
| Full virtual factory 3D NVIDIA scene | **NOT DEPLOYED** | small seeded six-stage discrete event reference |
| Level-1 digital twin (queues, WIP, cycle time, policies coupled) | **Implemented, SIMULATED, timings are assumptions** | `qualityrelay17/digital_twin.py`, `docs/research/DIGITAL_TWIN_RUN_31OCT.md`, 18 V&V tests |
| Cost-optimal VOI is operationally feasible on the demo line | **NO at current cost table** — 85 % caliper retakes saturate the Caliper station (99.8 %), cycle time 24× the rule's; at `Costs.inspection=5.0` VOI buys nothing | same |
| Calibrated fusion shortens the line vs the OR-rule at matched inspection load | Observed in simulation: −19.5 s cycle [−27.1, −12.9] per part, 24 % faster, +0.1 escapes/1000 | same |
| NVIDIA 8 technologies actively integrated | **NOT CONFIGURED** | 8 explicit stubs, license/resource docs |
| Anomaly detector trained on an NVIDIA GPU | **Done, reference-level** — STFPM on Brev L4; MVTec screw 0.948 / bottle 1.000 image AUROC (`EXTERNAL_DATASET`), own-STL synthetic 0.880 (`SIMULATED`) | `docs/research/ANOMALY_GPU_RUN_31OCT.md`, manifests in `docs/research/runs/` |
| Anomaly detector validated on our printed parts | **NOT RUN** — no `PHYSICAL_CAPTURE` images exist yet | pipeline ready: `scripts/train_anomaly.py --data captured` |
| Model deployed on Raspberry Pi + Hailo-8L | **NOT ATTEMPTED** — ONNX exported, compile steps unverified | `docs/engineering/ANOMALY_MODEL_HANDOFF.md` |
| Physical servo sorter | **NOT CONNECTED** | stage/approval/ACK state machine, no GPIO command |
| Physical industrial cost savings | **NOT MEASURED** | assumptions-only simulation economics |
| A new scientific discovery was demonstrated | **NO** | hypotheses not yet supported vs matched conservative rules |
| H2 — cost-aware VOI is cheaper than the conservative rule at matched safety (synthetic) | **NOT SUPPORTED at baseline** (cost +25 [−67, +116] per 1000); supported only in S02/S03/S08/S09; **fails safety margin under industry cost ratios (S13)** | pre-registered run `docs/research/PROTOCOL_RUN_31OCT_RESULTS.md`, `examples/results/protocol_31oct/manifest.json` |
| One-step VOI is safer / higher-throughput than the rule at equal modelled cost (synthetic) | Observed on pre-registered endpoints: −1.5 escapes/1000 [−2.1, −0.9], +10.4 pp released-good at S01 — by paying for a caliper retake on 85 % of parts (degenerate, see results §1) | same |
| Cost-aware selection beats entropy (information-gain) selection on cost | **Supported in 13/13 synthetic scenarios** (ablation B7 − cost_awareness), CIs exclude 0 | same |
| 10,000 scientific papers screened | **NO** | older retrieval program, not completed corpus |
| Web research demonstration | Implemented local front end | FastAPI + HTML, no credentials needed |
| EWMA/SPC drift detection, truncated-normal lot-pairing risk | **NOT BUILT — explicit scope decision (31 Oct)** | 5.0 archive has design text only; reasons in `docs/architectures/04_SCIENTIFIC_ENGINE_VDER_CAIR.md` |
| Likelihoods used by posterior policies are calibrated | Implemented on **synthetic** held-out seeds only | `qualityrelay17/calibration.py`, frozen in `examples/results/protocol_31oct/*.json`; no camera calibration table exists |

**Publishable result criterion:** preregistered hypotheses, reproducible methods, baselines, independent lot-level physical data, appropriate uncertainty intervals, nontrivial improvement over conservative baseline, evidence of contribution not explained by policy differences, independent review. Inventing a named acronym is not sufficient.
