# QualityRelay 17.0 — SAFE-MESH Research + Engineering Package

**Status:** runnable research reference and individually documented target architecture. **Not** a complete 21-live-LLM factory system, real NVIDIA model, industrial certification, Raspberry Pi/Hailo deployment or proven scientific discovery.

## Start in three commands

```bash
cd QualityRelay_17_SAFE_MESH
python -m pip install -r requirements-demo.txt
python -m pytest -q
python -m qualityrelay17.demo
```

## Run the single prototype website

```bash
uvicorn qualityrelay17.api:app --host 127.0.0.1 --port 8000
# Open http://127.0.0.1:8000
```

`/` renders a static responsive research dashboard. `Photo / CAD Lab` locally compares two uploaded images using uncalibrated pixel difference. `Simulation Lab` runs the seeded Python backend if available. The supplied CAD projections are generated from the original user's 5.0 STL specimen models. **No uploads are stored or sent by the browser's local comparison.** When deploying HTTPS, configure real authentication, permissions, TLS, rate limiting and secure hardware controls first. The demo API has none of those production assurances.

## Layout

- `QUALITYRELAY_17_MASTER_BLUEPRINT.md`: comprehensive integrated plan with all architecture sections.
- `docs/architectures/`: 12 independently developed modules and their acceptance gates.
- `docs/research/`: verified scientific foundation, hypotheses and experiments.
- `docs/engineering/`: third-party GitHub license review, team ownership, actual status and sponsor resources.
- `qualityrelay17/`: original reference contracts, signature policy, lineage DAG, evidence ledger, VOI, matching, economics, factory simulation, no-actuation sorter state machine, Nebius adapter, FastAPI demo.
- `web/index.html`: research web frontend, no unsubstantiated live inference badges.
- `tests/`: automated safety, math, lineage, API and simulation checks.
- `examples/cad/stl/`: copied from the user's own original 5.0 package; `examples/cad/*.png`: own 2D STL silhouette renders.
- `examples/results/`: generated transparent simulation-only examples.
- `legacy/`: byte-identical preserved user-provided historical releases; see preservation audit.

## Major preserved decisions

- Primary architecture: fully **decentralized**; Chief Engineer centralized/hybrid as baselines, not compulsory boss.
- **21 specialist role registry**: same role roster as user's 14.2, protected role-to-tool contract.
- **Phone camera + Raspberry Pi camera**, each separately accountable; phone reference photo, Pi edge capture, CAD projection, caliper confirmed readings. Photograph and CAD inference derived from same image are correlated, not independently counted.
- V-DER / CAIR, Evidence-Mesh, PACE / safety gate, human-controlled physical sorter, digital factory and cost intelligence.
- NVIDIA eight integration slots (cuOpt, Isaac/Omniverse, Replicator, PhysicsNeMo, DeepStream, Cosmos, Metropolis VSS, Warp/Newton) with hardware/license caveats.
- Nebius LLM tool-calling is opt-in; no live key or entitlement presumed.
- **Bakdaulet: no Google Cloud tasks**; adilnurgg and HyorinmaruK handle GCP. HyorinmaruK owns physical validation and pitch.

## What the current benchmark really says

`examples/results/BENCHMARK_30x1000_SYNTHETIC.json`: 30 seeds x 1000 simulated specimens per seed. The present SAFE-MESH reference has same conservative rule decisions as conservative-rules, but incurs more inspection cost: **it is not better**. This honest negative result identifies the research work required: implement and calibrate adaptive active inspection, then evaluate on held-out physical lots.

**31 Oct — Level-1 digital twin (Bakdaulet).** `python scripts/run_digital_twin.py` couples the inspection policies to an event-driven line (queues, WIP, cycle time, Review station) under common random numbers; `docs/research/DIGITAL_TWIN_RUN_31OCT.md`. Headline: the cost-optimal VOI's caliper retakes saturate the Caliper station — cost-neutral on paper, 24× cycle time on the line. Timings are assumptions.

**31 Oct — pre-registered VOI protocol (Bakdaulet).** `scripts/run_protocol.py` runs 13 declared scenarios × 30 seeds × 1000 with held-out-calibrated likelihoods and decision rules fixed in advance (`docs/research/PROTOCOL_REGISTRATION_31OCT.md`). Verdicts per scenario, including the negative ones, are in `docs/research/PROTOCOL_RUN_31OCT_RESULTS.md` and `examples/results/protocol_31oct/manifest.json`. Still `SIMULATED`; still not a factory claim.

## Important restrictions

- Downloaded/open-source GitHub libraries are NOT secretly bundled. Their source and licenses belong to their owners; see `docs/engineering/THIRD_PARTY_REUSE.md`.
- Event-specific ScienceClaw credential links, API keys and proprietary weights are not included.
- No 10,000-paper literature corpus was read or downloaded; earlier 9.0 research collection script is preserved in historical archives.
- No scientific superiority, 100% safety or measured ROI claimed.

## Кысқаша (қазақша)

Бұл ZIP — QualityRelay-дің 17.0 ғылыми-инженерлік негізі. 12 архитектура жеке жазылған, 21 агент рөлі, екі камера, фото↔CAD, виртуалды зауыт, экономикалық есеп, NVIDIA/Nebius интеграция жоспары және тесті бар. Нақты зауыттық валидация мен GPU модельдерін іске қосу әлі жасалмаған. Ғылыми тиімділікті дәлелдеу үшін дайын benchmark пен физикалық сынақ жоспары бар.
