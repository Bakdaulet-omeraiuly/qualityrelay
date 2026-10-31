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
| Hardware ingestion | reference FastAPI endpoints (`/hardware/caliper-reading`, `/hardware/bin-ack`) + ESP32 firmware sketches added 31 Oct, unit-tested | `HARDWARE_STATION_KEYS` unprovisioned by design (endpoints 503), zero live sensor readings captured, repeatability screen not yet run — see `PHYSICAL_TEST_PLAYBOOK.md` |
| Evidence signatures & ACL | runnable SQLite + HMAC reference | PKI, transport TLS, real station network, queue replay |
| Scientific VOI | binary V-DER reference; wired into `factory.py`/`benchmark.py` as `voi_driven`, `collective_fusion`, AND `structured_request_lite` comparator policies (31 Oct). `collective_fusion` matches `conservative_rules`'s unsafe-pass rate while cutting cost/holds under independent-camera conditions; `structured_request_lite` is a minimal Gate-A instance of Bakdaulet's 17.1 evidence-request protocol (see `docs/research/COLLECTIVE_17_1_BAKDAULET.md` and its integration note) passing all five of his own "real collaboration, not theater" criteria on a reproducible trace | likelihood calibration, the actual pre-registered protocol run (only exploratory runs exist so far), the full B0-B7 ladder with live LLM agents (Gates B-D of the 17.1 plan), new model claims not proven |
| Smart Matching | exact DP <=12 | cuOpt / OR-Tools larger instances, capacity constraints |
| Factory line | seeded 6-stage, multi-line event schedule | queues/buffers/SimPy and accurate machine process data |
| Economics | assumptions-based cost categories | real factory price/costs and external pilot |
| Safety actuation | staging+ACK logic, no servo GPIO | signed hardware gateway, physical interlock, sensor |
| Site | static research dashboard + FastAPI research endpoint | identity/TLS/production site and real camera upload |
| Research | scientific prior art and benchmark report | physical validation, statistical advantage, peer review |

## Evidence tiers
`DESIGN_ONLY` = architecture/design; `EXECUTED_TEST_FIXTURE` = unit/integration tests; `SIMULATED` = generated run; `PHYSICAL_CAPTURE` = camera images actually captured but not independently verified; `VERIFIED_PHYSICAL` = calibration/measurement + independent human review. **No tiers may be silently promoted.**

## What makes 'industrial ready' a future claim
Third-party cyber review; metrology MSA/gauge R&R; physical operating envelope; operator training and E-stop; deterministic rollback; independent measured false-accept rate; audit/export; compliance with application-specific standards; OT/MES integration tested in shadow mode; factory sponsor signature; support/maintenance plan. None of these are automatically proven by demo unit tests.
