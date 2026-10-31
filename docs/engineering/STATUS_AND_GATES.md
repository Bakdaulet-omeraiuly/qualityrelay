# Exact implementation status — 17.0 reference, 30 October 2026

| Capability | Actual state in this ZIP | What remains to do |
|---|---|---|
| 21 specialist role names | 21 copied from user's own 14.2 code + server tool gate | Distinct live LLM role evaluations, prompt injection tests |
| Nebius LLM | Opt-in real API code; not invoked live | Team key entitlement, chosen model, live evaluation, credit logs |
| NVIDIA eight products | Documented, isolated NOT_CONFIGURED adapters | GPU setup, model weights, asset terms, scientific benchmarking |
| Phone/Pi two stations | 15.0 historical two-process reference bundled | Actual independent physical captures and validation |
| Photo/photo | runnable OpenCV pixel-diff **baseline** | lighting/pose registration and validated detection model |
| Photo/CAD | runnable STL orthographic 2D silhouette raster helper | camera registration, calibrated features, multi-angle 3D |
| Metrology | evidence verifies manual confirmed readings | actual caliper protocol / OCR / uncertainty |
| Hardware ingestion | reference FastAPI endpoints (`/hardware/caliper-reading`, `/hardware/bin-ack`) + ESP32 firmware sketches added 31 Oct, unit-tested | `HARDWARE_STATION_KEYS` loaded from env / git-ignored `.env` via `scripts/provision_station_keys.py` (31 Oct, `slot`/`tab`/`sorter`); unprovisioned stations still 503; accepted readings persisted to `HARDWARE_LEDGER` (in-memory unless `HARDWARE_LEDGER_PATH`), replays 409; zero live sensor readings captured, repeatability screen not yet run — see `PHYSICAL_TEST_PLAYBOOK.md` |
| Evidence signatures & ACL | runnable SQLite + HMAC reference | PKI, transport TLS, real station network, queue replay |
| Scientific VOI | two-axis one-step NetVOI (`vder.two_axis_action_scores`) on the benchmark's own cost scale; likelihoods **estimated on held-out synthetic seeds** (`calibration.py`), frozen in run manifests; `voi_driven` buys genuinely fresh recapture/retake observations (second RNG stream); `entropy_driven` cost-blind ablation; `collective_fusion` (B3) and `structured_request_lite` (B5-lite) rewired to the same calibration/threshold. **Pre-registered 13-scenario × 30-seed × 1000 protocol run on 31 Oct** — registration `docs/research/PROTOCOL_REGISTRATION_31OCT.md`, results and verdicts `docs/research/PROTOCOL_RUN_31OCT_RESULTS.md`, manifest `examples/results/protocol_31oct/`. EWMA/SPC explicitly **not** ported (decision recorded in `docs/architectures/04`) | physical likelihood table (synthetic calibration is not camera calibration), multi-step/non-myopic planning, the full B0-B7 ladder with live LLM agents (Gates B-D of the 17.1 plan), any transfer claim to real lots |
| Smart Matching | exact DP <=12 | cuOpt / OR-Tools larger instances, capacity constraints |
| Factory line | seeded 6-stage, multi-line event schedule (`digital_line.py`) **+ Level-1 digital twin (31 Oct, `digital_twin.py`)**: event-driven FIFO queues, WIP, cycle time, throughput, Review/quarantine station, inspection policies coupled in, CRN across policies, 6 fault scenarios, conservation tests — `docs/research/DIGITAL_TWIN_RUN_31OCT.md` | measured station times (all current timings are `ILLUSTRATIVE_ASSUMPTION`), finite buffers / blocking, capacity-aware VOI |
| Economics | assumptions-based cost categories | real factory price/costs and external pilot |
| Safety actuation | staging+ACK logic, no servo GPIO; ACK now requires a ledger-recorded ROUTE_ACK (31 Oct), E12 latches FAULTED, E13 single-count, interlock transitions locked (concurrent-edge race found and fixed by `scripts/rehearse_e12_e13.py`, 31 Oct); `/actuation/stage` + `/actuation/{id}` reference endpoints; HTTP-level bounce/reboot rehearsal passes (TEST_FIXTURE, no sensor) | authenticated staging, signed hardware gateway, physical interlock, live E12/E13 run |
| Site | static research dashboard + FastAPI research endpoint | identity/TLS/production site and real camera upload |
| Research | scientific prior art and benchmark report | physical validation, statistical advantage, peer review |

## Evidence tiers
`DESIGN_ONLY` = architecture/design; `EXECUTED_TEST_FIXTURE` = unit/integration tests; `SIMULATED` = generated run; `PHYSICAL_CAPTURE` = camera images actually captured but not independently verified; `VERIFIED_PHYSICAL` = calibration/measurement + independent human review. **No tiers may be silently promoted.**

## What makes 'industrial ready' a future claim
Third-party cyber review; metrology MSA/gauge R&R; physical operating envelope; operator training and E-stop; deterministic rollback; independent measured false-accept rate; audit/export; compliance with application-specific standards; OT/MES integration tested in shadow mode; factory sponsor signature; support/maintenance plan. None of these are automatically proven by demo unit tests.
