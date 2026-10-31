# Contract-driven integration: make a complex platform deliverable

## One unifying principle

All scientific, camera, synthetic, CAD and station events MUST be normalized into `EvidenceEvent` carrying a traceable `origin`. Only deterministic services may decide PASS authority. LLM outputs are non-authoritative hypotheses/tool requests, not evidence. No irreversible hardware operation without authorized operator plus separate physical acknowledgement.

## Internal interfaces

### Stations and inputs
- `POST /stations/{id}/evidence`: reserved production interface; **NOT** implemented by demo API; implementation requires station authentication, signature verification, idempotency and schema validation.
- `vision.phone.capture`: `(image, specimen_id, camera_config, calibration_id) -> defect_map, uncertainty, source_root`.
- `vision.pi.capture`: own independent sensor source with own identity. If same original photo is copied to two services, lineage must expose that dependency.
- `vision.cad_compare`: `(image_id, STL_revision, pose, calibration) -> contour/feature deltas, uncertainty`; orthographic helper in reference is NOT metrology-grade.
- `metrology.manual_or_OCR`: `(operator_verification, units, caliper_id, repeatability, specimen_id) -> verified dimension + uncertainty`.

### Scientific services
- `risk.clearance`: `(lot_a, lot_b, valid measurement events) -> probability interval conditional on local acceptance`, with fixed model version and seed.
- `inspection.rank`: `(current beliefs, candidate measurements, costs, coverage) -> rank`, compare V-DER/CAIR vs entropy and conservative rules.
- `optimization.match`: `(compatible pairs, constraints, costs) -> matching + feasibility`, CPU exact DP for tiny cases; optional cuOpt.
- `production.simulate`: `(scenario_id, seed, topology, parameters) -> per-event log, cost breakdown, metrics, origin='SIMULATED'`.

### Agent/actuation
- `agents.request_evidence`: checked allowlist and explicit actor identity; no unrestricted raw table read.
- `agents.review`: separate bounded inference and tool round limit; do not allow prompt-to-GPIO.
- `disposition.propose`: independent evidence gate; returns PASS_REVIEW/HOLD/CONFIRMED_REJECT, not GPIO command.
- `sorter.stage -> human.approve -> gpio.gateway -> sensor_ack -> reconcile`: use unique IDs, TTL, safety interlock and explicit confirm of physical routing. No ACK means PENDING, not delivered.

## Durable message envelope

Use JSON Schema in `schemas/evidence_event.schema.json`. Add (as integration maturity grows) message version, exact event timestamp, calibration ID, lot & specimen, unit, uncertainties, parent roots, source origin (`SIMULATED`, `PHYSICAL_UNVERIFIED`, `VERIFIED_PHYSICAL`), signature key id, policy id, model version, CAD revision, replay UUID, operator approval audit and retraction history. HMAC is an internal prototype integrity check, not a production identity/PKI system.

## Acceptance gates
1. Two separately authenticated camera services; each can be put offline independently.
2. Wrong CAD revision, low-quality image, corrupted signature and duplicated source -> HOLD; no false PASS.
3. Same latent simulated population, seed and inspection budget for all policies.
4. 21 roles remain defined, but default only invokes agents relevant to problem; tool calls checked server-side.
5. Reconnecting offline peer does not double-count evidence or physical parts.
6. Repeated physical caliper readings and blind fit tests; no uncalibrated mm precision claims.
7. Outputs from missing GPU/Nebius/Isaac plugins say `NOT_CONFIGURED`, never `RUN_SUCCESS`.
8. Cost simulator uses explicit assumptions; physical claimed ROI requires actual accounting/validation.

## What remains explicitly outside the demo implementation

This package does not include a production auth server, genuine peer-to-peer distributed network deployment, signed hardware GPIO gateway, trained NVIDIA model, actual Hailo inference, live Nebius credentials, Isaac Sim scene, industrial safety certificate or validated factory economics. See status matrix; none may be reported as done merely because contracts exist.
