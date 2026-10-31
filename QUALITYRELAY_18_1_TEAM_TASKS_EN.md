# QualityRelay 18 → 18.1 — Final Three-Person Task Board

**Date:** October 31, 2026  
**Source:** `QualityRelay_18_31OCT_v2.zip` and `QualityRelay_18_AUDIT_KK.md` (October 31 audit).  
**Objective:** Deliver a scientifically honest, end-to-end demonstration: physical part → two cameras/CAD/caliper → real agent collaboration and adaptive inspection → SAFE-MESH → authorized sorter → independent physical acknowledgment (ACK) → fair benchmark and factory economics.

> **IMPORTANT: This document is a TASK BOARD and definition of acceptance, not a report of completed work.** The October 31 audit reported **111/111 Python tests passing**, but this does **not** establish that live GPU training, two physical cameras, LLM integration, the servo mechanism, or factory trials are complete. Two cost-accounting errors were found in previous benchmarks. Although the archive is labeled 18, multiple internal package labels still say 17.0.

## CAPE research addendum — 31 October 2026

**New proposed research method:** **CAPE — Capacity-Aware Provenance-Constrained Evidence Acquisition**. Detailed mathematical design, scientific baselines, negative-result policy and acceptance gates: [CAPE research specification](docs/research/CAPE_CAPACITY_AWARE_EVIDENCE_ACQUISITION.md).

**Novelty is a hypothesis, not a proven discovery.** CAPE explores whether source-root-aware, permissioned decentralized evidence acquisition combined with *marginal factory queue/capacity costs* can outperform standard VOI and conservative rules under comparable safety conditions. Keep SAFE-MESH as the independent physical-action safety gate. CAPE extends V-DER/CAIR; it is not a replacement or a claim that Bayesian VOI, queueing theory or distributed agents were invented here.

### Additional priority tasks (not yet done)

- [ ] **CAPE-01 — Bakdaulet:** Fix P0 sensor and peer-request cost-accounting errors; add regression tests preventing double charges or free inspected evidence.
- [ ] **CAPE-02 — Bakdaulet:** Implement deterministic capacity-aware NetVOI with a discrete-event factory queue model; run low/high utilization switching tests and scientifically fair B0–B8 baselines/ablations.
- [ ] **CAPE-03 — Bakdaulet:** Evaluate actual throughput, p95 cycle time, unsafe PASS, hold, total factory cost and confidence intervals; report *negative* as well as positive results. Keep synthetic and physical results labeled separately.
- [ ] **CAPE-04 — adilnurgg:** Supply authenticated, scoped peer-request/reply traces, source-root DAG, per-call communication and LLM costs, and real queue telemetry to the CAPE scientific tool. Expose its output through API and web; LLMs cannot compute or override safety decisions.
- [ ] **CAPE-05 — adilnurgg:** Compare compatible OpenAI/Claude/Nebius provider adapters separately from the collaboration protocol and maintain the independent SAFE-MESH approval/ACK boundary.
- [ ] **CAPE-06 — HyorinmaruK:** Physical specimens, camera/caliper calibration, empirical service-time measurements, supervised sorter ACK tests and presentation; **no simulation, Digital Twin coding, cloud or backend assignment**.

**Acceptance:** demonstrate a case where an authorized new source changes the inspection plan; duplicate source evidence does not count twice; increasing queue congestion changes the admissible optimal inspection when appropriate; in an uncongested limit CAPE reduces to standard NetVOI; combined benchmark and physical test reports never overstate demonstrated savings.

---

## 0. Ownership — final, mandatory allocation

| Person / GitHub | Owns | Strict scope boundary |
|---|---|---|
| **Bakdaulet** (`Bakdaulet-omeraiuly`) | **Scientific research + Computer Vision AI + ALL Simulation / Digital Factory + Optimization / ROI + Scientific Benchmarking** | **Bakdaulet exclusively owns the simulation engine, models, scenarios, and scientific results. No Google Cloud deployment responsibility.** |
| **adilnurgg** | **Backend + real multi-agent collaboration + EVIDENCE-MESH / SAFE-MESH + API / Web UI integration + Cybersecurity + Nebius / Google Cloud + CI** | **Owns all server infrastructure, inter-agent/network communication, and web integration. Physical assembly is not his main responsibility.** |
| **HyorinmaruK** | **PHYSICAL WORK ONLY** (Mechanical Engineering, CAD/STL, 3D printing, physical camera setup, caliper ground truth, ESP32/servo/sensor bench) **AND presentation / pitch / live physical demonstration** | **Does NOT own simulation/Digital Twin code, web/backend, Google Cloud, Nebius, VOI, or scientific benchmark programming.** |

When modules meet, ownership does not move. Each owner supplies the necessary data or interface: HyorinmaruK hands off physical measurements to Bakdaulet; Bakdaulet supplies simulator outputs to adilnurgg for web/API exposure; adilnurgg coordinates the authorized physical command protocol with HyorinmaruK's hardware.

---

## 1. Bakdaulet — AI Research, Vision, ALL Simulation / Digital Factory (OWNER)

### P0 — Fix errors that invalidate scientific conclusions

- [ ] **SCI-01 — Fair cost accounting:** In `qualityrelay17/factory.py` and `economics.py`, charge exactly once for every consumed sensor observation, caliper retake, peer request, communication, LLM/tool call, human inspection, and associated time. The `voi_driven` policy must not consume three sensor signals while paying for only one or two.
- [ ] **SCI-02 — Peer-request cost:** Include `structured_request_lite`'s `request_cost_paid` in actual total cost. Keep inspection charges separate from request charges. A zero-cost request is permissible only if explicitly configured as zero-cost.
- [ ] **SCI-03 — Re-run benchmarks:** After repairing accounting, compare `conservative_rules`, `collective_fusion`, `structured_request_lite`, and `voi_driven` with identical random seeds, lots, samples, and inspection budgets. Do not repeat old “27% savings” or other savings claims without revalidation.
- [ ] **SCI-04 — Report negative results:** If the proposed method ties or loses against a proper baseline, report that transparently. Do not advertise a cost-only win when unsafe PASS risk increases.

### P0 — Demonstrate real collective intelligence scientifically

- [ ] **SCI-05 — B0–B7 benchmark:** Following `docs/research/COLLECTIVE_17_1_BAKDAULET.md`, compare single-rule control, single agent with equal information, isolated specialists, majority vote, structured requests, VOI without negotiation, collaboration + VOI, full SAFE-MESH, and relevant ablations. Report any centralized full-information upper bound separately rather than silently giving it privileged information.
- [ ] **SCI-06 — Adaptive VOI:** For each part, recompute posterior belief / uncertainty after *each new observation*, then dynamically select the next inspection. A fixed `if` chain is not adaptive Value of Information. Modules: `vder.py`, `benchmark.py`, `factory.py`.
- [ ] **SCI-07 — Ablations:** Test communication OFF, VOI OFF, lineage OFF, duplicate correlated photos ON, Pi offline, camera disagreement, noisy caliper, and constrained inspection budget. Each request trace must expose the new fact obtained and any resulting decision change.
- [ ] **SCI-08 — Metrics:** Report unsafe PASS, false HOLD/REJECT, conditional risk, inspection count, actual peer-request count, latency, message/compute cost, cost per good unit, throughput, and uncertainty/confidence intervals. Use paired seeds, part-/lot-level splits, and a reproducibility manifest.

### P0 — ALL Simulation and Digital Factory (Bakdaulet only)

- [ ] **SIM-01 — Factory engine:** Extend `digital_line.py`, using FactorySimPy or SimPy as appropriate. Model stations Slot → Tab → Phone Vision → Pi Vision → Metrology → Assembly → Sorting, including machines, buffers, queues, failures, rework, transport time, batches, part genealogy, and operator constraints.
- [ ] **SIM-02 — Scenario generator:** Include nominal manufacturing, process drift, warping, cracks, camera noise, missing observations, network partition, station failure, quality bottleneck, and cost shock. Persist random seeds and ground-truth scenario parameters.
- [ ] **SIM-03 — Digital Twin and sim-to-real:** Use Trimesh/CadQuery for CAD geometry simulation. Add optional Isaac Sim, Omniverse Replicator, Warp/Newton adapters where compatible. Calibrate against physical measurements and keep **SIMULATED ≠ VERIFIED_PHYSICAL** explicit throughout.
- [ ] **SIM-04 — Economic simulation:** Model scrap, rework, inspection, HOLD inventory, transport, downtime, LLM/GPU/cloud usage, maintenance, and equipment amortization as separately disclosed assumptions. Compare baseline versus QualityRelay total cost, ROI, payback, and uncertainty intervals. Do not label scenario outcomes as proven real-factory savings.
- [ ] **SIM-05 — Optimization:** Provide a SciPy/OR-Tools CPU baseline for matching and scheduling; optionally add NVIDIA cuOpt when available. Enforce mathematical feasibility and safety constraints. The CPU baseline must remain functional without GPUs.
- [ ] **SIM-06 — Multi-factory experiments:** Implement at least reproducible stress tests for separated supplier sites, limited peer evidence, delayed station events, and scale from 6 to 10 to 50 simulated stations.
- [ ] **SIM-07 — Dashboard data:** Deliver API response schemas, plots, CSV and JSON experiment outputs to adilnurgg. **Bakdaulet owns simulation computation; adilnurgg owns wiring those results into the web interface and backend.**

### P1 — Computer Vision and NVIDIA research

- [ ] **VISION-01:** Implement calibrated Photo↔Photo registration, glare/lighting stress tests, reference images indexed by part ID and viewpoint, anomaly masks, and calibration/threshold evaluation.
- [ ] **VISION-02:** Implement Photo↔CAD/STL 2D projections, silhouette and feature comparisons. Report tolerances in millimeters only after calibration and validation against caliper ground truth; never equate raw pixels with millimeters.
- [ ] **VISION-03:** Receive independently captured Phone/Pi datasets from HyorinmaruK. Split data **by physical part and lot** and check leakage/duplicates and provenance of ground-truth labels.
- [ ] **VISION-04:** If NVIDIA GPU credits are active, train a compact anomaly detector with Anomalib/TAO where practical; evaluate on held-out real 3D-printed parts. Investigate Hailo-8L model conversion/compilation and share deployment feasibility with adilnurgg. **H100 is not an RTX GPU for Isaac Sim.**
- [ ] **VISION-05:** Compare trained vision models against a no-training OpenCV baseline; record FLOPs/latency and failure modes. Respect MVTec AD's noncommercial dataset terms; prioritize original images for future industrial use.

**Bakdaulet deliverables:** Corrected scientific code; working factory simulator; `scenario_manifest.json`; reproducible benchmarks; vision evaluation report; ROI assumptions and plots; concise evidence-backed results for HyorinmaruK's pitch.

**Bakdaulet — definition of done:** All observed sensor/request costs are accounted for; the next inspection is truly adaptive; B0–B7 and ablations are repeatable; simulations reproduce under a fixed seed; all findings clearly distinguish `SIMULATED` from `VERIFIED_PHYSICAL`.

---

## 2. adilnurgg — Backend, Agents, Security, Website / Cloud (OWNER)

### P0 — Secure hardware API and physical safety

- [ ] **BACK-01 — Fix the signing oracle:** In `api.py` endpoints `/hardware/caliper-reading` and `/hardware/bin-ack`, verify the real sending station identity before accepting data. Never sign unchecked client-supplied `station_id` or measurements. Use mutual authentication or a per-device signed envelope, nonce, timestamp/TTL, replay protection, ACL, and a distinct trusted-gateway identity.
- [ ] **BACK-02 — Verified evidence ledger:** Only station-authenticated readings may become candidates for `VERIFIED_PHYSICAL`; also require a separate documented human/instrument ground-truth verification procedure. Keep raw unsigned measurements at `PHYSICAL_CAPTURE` or `UNVERIFIED` status.
- [ ] **BACK-03 — Sorter event binding:** Bind `action_id ↔ specimen_id ↔ station_id ↔ requested_bin ↔ actual_bin ↔ unique sensor_event_id ↔ timestamp`. Enforce idempotency, nonces, TTL, and rejection of duplicate acknowledgments. A detected object inside a bin does **not** automatically prove it is the correct specimen.
- [ ] **BACK-04 — Safety enforcement:** A PASS recommended by an LLM/AI must never directly drive GPIO. Require human-approved actions, mechanical/electrical interlocks, default HOLD, emergency stop and hardware disable gate, timeouts, and safe behavior under power loss.

### P0 — Genuine decentralized collaboration

- [ ] **AGENT-01 — Typed negotiation protocol:** `REQUEST_EVIDENCE → RESPONSE_EVIDENCE → VERIFY → UPDATE_BELIEF → PROPOSE_INSPECTION → DECISION_REVIEW`. Include authenticated request IDs, sender/receiver roles, access policies, reasons, evidence roots, request costs, and deadlines.
- [ ] **AGENT-02 — Private context per specialist:** Give Phone, Pi, CAD, Metrology, Assembly, Process, Risk, and other roles different scoped views and permissions. Do not allow them to silently inspect another role's raw data; require authenticated evidence requests.
- [ ] **AGENT-03 — Explainable interaction traces:** Store message-level provenance; rejected, missing, and timed-out responses; before/after belief; chosen inspection; and decision changes. Expose JSON traces and a web dashboard trace viewer.
- [ ] **AGENT-04 — Nebius live smoke test:** Validate actual credentials/permissions, a named deployed model, genuine tool calls, server-side tool allowlists, and token/latency/cost logging. **21 roles do not imply 21 separate running models.** Show actual active roles and report `NOT_CONFIGURED` when credentials are absent.
- [ ] **AGENT-05 — Evidence lineage DAG:** Do not count two scores from the same underlying photo as independent sources. Trace all lineage ancestors. Stale, duplicate, unsigned, or mixed-origin evidence should trigger HOLD/review as required by policy.

### P0 — LLM stack and deployment plan for all 21 roles (adilnurgg owns this)

**Architectural decision:** Keep the 21 specialist role definitions already present in `qualityrelay17/roles.py`; do **not** train or host 21 separate LLMs. Use one verified, tool-calling Nebius Token Factory model as the shared stateless reasoning backend, while each role retains a distinct **server-enforced** evidence scope, tool allowlist, system prompt, budget, and auditable identity. Normally select **2–7 relevant roles per specimen**; do not invoke all 21 on every part. The individual agents must own/receive different evidence, not merely be differently named prompts that all see the same database.

#### Exact recommended technology stack (candidate, not yet a verified live integration)

| Layer | Choose | Reason and validation |
|---|---|---|
| LLM provider | **Nebius Token Factory** OpenAI-compatible API at `https://api.tokenfactory.nebius.com/v1/` | Already matches `qualityrelay17/nebius.py`; fetch `GET /v1/models` with the team's key and test a real tool call. Token Factory access is distinct from the shared Nebius H100 allocation. |
| Default LLM candidate | **`zai-org/GLM-5.3-Flash`** | Currently listed by Nebius for agentic tool calling at lower cost. Confirm **this exact model ID** appears under the team's credentials and actually completes our JSON/tool schemas; do not hard-code availability as a fact. |
| Lower-cost fallback candidate | **`Qwen/Qwen3-30B-A3B-Instruct-2507`** | For smaller text/tool tasks, subject to live access and loop/tool-call reliability tests. |
| High-complexity escalation candidate | **`zai-org/GLM-5.3`** | Use only for selected hard diagnoses with token/cost caps; compare with the default on held-out cases. |
| LLM API client | **Python `openai` SDK** with explicit `base_url` and environment variable `NEBIUS_API_KEY` | Existing adapter already follows this pattern; no credentials in repository or logs. |
| Per-agent state-machine | **LangGraph** (`langgraph`) *or a fully equivalent documented custom async state machine* | Durable step transitions: observe → identify missing evidence → peer request → verify → hypothesis update → proposed inspection → decision review; checkpoint per case, never expose global raw evidence to all nodes. |
| Cross-agent transport | **NATS JetStream** (`nats-py`), after first in-process contract tests | Signed typed messages, durable delivery, retries, idempotency and timeouts. NATS is transport, not authorization or the source of truth. Run roles as separately authorized workers to demonstrate genuinely distributed evidence. |
| Validated messages | **Pydantic** JSON schemas; FastAPI for external routes | Reject forged identities, invalid payloads, missing/duplicate source roots and unauthorized role-to-tool requests before any LLM tool execution. |
| Audit and evidence | Append-only event log + **PostgreSQL** (or existing storage adapter during MVP) | Store case_id, event_id, source_root, station origin, message request/response, model ID, tool calls, tokens, cost, latency and policy verdict. No indiscriminate raw data sharing. |
| Safety | Existing `qualityrelay17/safe_mesh.py` and device-authenticated physical gateway | LLM output is advice only. It cannot authorize PASS on hardware, emit GPIO commands, override HOLD, or approve its own action. |
| Visual intelligence | Bakdaulet's calibrated Computer Vision/CAD models | Vision scores, defect maps and measurements arrive as cited evidence; never assume the text LLM is the calibrated defect detector. |

#### Individual tasks and acceptance gates

- [ ] **LLM-01 — Entitlement and model verification:** set `NEBIUS_API_KEY` as a secret, not in Git; query `GET /v1/models`, record which of the candidate models the team can use, and perform one real text + JSON tool-call roundtrip. Capture a redacted run manifest with date, model ID and tool-call validity. Without entitlement, return `NOT_CONFIGURED`, not fake AI output.
- [ ] **LLM-02 — Build the 21-role configuration:** extend `roles.py` with role-specific prompts, required sources, server-owned tool permissions, max rounds and max spend. Define clear owner-only evidence views for CAD/Design, Phone/Pi Vision, Metrology, Assembly, Process, Risk/Safety, Maintenance, Economics, Inspection Planner and remaining specialists. Preserve the **21 registered role names**, which are engineering roles rather than 21 independent foundation models.
- [ ] **LLM-03 — Real reasoning loop:** extend `nebius.py` / `agent_tools.py` to validate model-produced function calls, execute only allowlisted read/inspection-planning tools, return signed/verified evidence summaries, and persist the complete multi-turn tool transcript. Start with Quality Inspector, Metrology Engineer, Design Geometry and Inspection Planner; expand role coverage after integration.
- [ ] **LLM-04 — Authenticated peer messaging:** create structured `REQUEST_EVIDENCE`, `EVIDENCE_RESPONSE`, `REQUEST_DENIED`, `TIMEOUT`, `HYPOTHESIS_UPDATE`, `PROPOSE_INSPECTION` and `DECISION_PROPOSAL` envelopes with message_id, case_id, sender/recipient identity, desired evidence kind, reason, source roots, deadline, cost and approval status. A distinct worker must answer from data unavailable to the requester before the request.
- [ ] **LLM-05 — Proper decentralization and lineage:** each specialist has scoped storage/permissions; do not emulate collaboration by handing one orchestrator all raw evidence. Enforce role authorization in server code, deduplicate by `source_root`, and prohibit replay or stale evidence. A shared broker or model API is allowed as infrastructure, but it must not be the all-knowing decision authority.
- [ ] **LLM-06 — Adaptive, budgeted activation:** use verified evidence gaps and Bakdaulet's **measured** NetVOI/CAIR planner to activate only useful specialists; bound tokens, inspection charges, time and number of rounds. Never let LLM free-text invent sensitivity, posteriors or money amounts. Record both LLM compute cost and inspection-request cost exactly once.
- [ ] **LLM-07 — Observable collaboration demo:** show a case where Quality Inspector initially lacks a caliper/CAD revision, requests it from a peer, receives a **new permitted independent source**, revises the belief or inspection plan, and obtains a safety-gated verdict; export a JSON trace and render the step sequence in the web dashboard.
- [ ] **LLM-08 — Scientific baselines:** run an identical held-out case set for (a) conservative rules, (b) one full-context LLM (separate privileged-information bound), (c) one role under the same distributed information budget, (d) independent voting, (e) structured evidence exchange, and (f) structured exchange + adaptive NetVOI + SAFE-MESH. Keep model, prompt budgets, data availability, inspection prices and safety gate comparable where applicable. Bakdaulet owns experimental design/results; adilnurgg provides live traces and per-call costs.
- [ ] **LLM-09 — Failure and adversarial tests:** reject hallucinated evidence IDs, missing provenance, forged role credentials, duplicate messages, prompt injection in CAD metadata, forbidden tools, stale readings, API failure, excessive tool rounds and network partitions; leave the part on `HOLD` when critical evidence is not verified.
- [ ] **LLM-10 — Cloud and reproducibility:** adilnurgg owns service deployment, optional NATS/PostgreSQL containers, TLS, logs, key rotation, rate limits and budget ceilings. Pin dependencies and record prompt hashes, model name, schema version, model response validity and source_tier (`SIMULATED` versus verified physical). Integrate with GitHub Actions unit tests; run a separately labeled opt-in live Nebius integration check.

**Minimum live acceptance demo:** `Quality Inspector → REQUEST_EVIDENCE → Metrology Engineer → EVIDENCE_RESPONSE → VERIFY source_root/ACL → UPDATE_BELIEF → Inspection Planner (measured NetVOI) → SAFE-MESH HOLD/PASS_REVIEW → human authorization if any physical action`. This must show **real API calls**, a real new source and its cost. A typed simulated test is useful but cannot be labeled a live 21-agent deployment.

**Implementation pointers:** existing `qualityrelay17/roles.py`, `nebius.py`, `agent_tools.py`, `safe_mesh.py`; scientific design in `docs/architectures/02_SPECIALIST_LLM_AGENTS.md` and `docs/research/COLLECTIVE_17_1_BAKDAULET.md`.

**Official/open-source references:** Nebius API: https://api.tokenfactory.nebius.com/docs ; Nebius model catalog: https://nebius.com/services/token-factory/models/glm-models-inference ; https://nebius.com/services/token-factory/models/qwen-models-inference ; examples: https://github.com/nebius/token-factory-cookbook ; LangGraph: https://github.com/langchain-ai/langgraph ; NATS: https://docs.nats.io/concepts/jetstream and https://github.com/nats-io/nats.py . Check library versions and licenses before pinning.

### P0 — Integration and release engineering

- [ ] **API-01:** Expose Bakdaulet's simulator results through `/simulation/*`, `/benchmark/*`, and `/economics/*`. Include `source_tier`, `seed`, `model_version`, `run_id`, and `assumption_set` in responses.
- [ ] **WEB-01:** Implement three clearly separated views: **Live Physical Inspection**, **Digital Factory Simulation**, and **Agent Collaboration & Benchmark**. Never blend physical and synthetic outcomes without labels. **adilnurgg owns frontend, backend, website, and cloud integration.**
- [ ] **CLOUD-01:** Own Google Cloud/backend deployment, Nebius integration, secrets management, HTTPS, access logging, and spend caps. Neither Bakdaulet nor HyorinmaruK owns Google Cloud deployment.
- [ ] **REL-01:** Reconcile release labels in root files, README, and API as version `18.1`; regenerate `RELEASE_VALIDATION.json` based on a new actual run; repair the broken/missing SHA256 manifest entries and verify all packaged hashes.
- [ ] **REL-02:** Configure `.github/workflows/tests.yml` for linting, types, schemas, security checks, and tests. Add PR reviews, two-review rules for safety/auth/actuation changes, GitHub issues, and an ownership board.
- [ ] **REL-03:** Maintain a versioned upstream dependency/license manifest, pinned Python requirements, and honest adapter statuses (`WORKING`, `TESTED`, `NOT_CONFIGURED`). Do **not** claim that all eight NVIDIA services are already running.

**adilnurgg deliverables:** Authenticated peer-negotiation protocol; secure device API; evidence/event ledger; connected website and APIs; CI, GitHub board, release manifest; cloud deployment runbook.

**adilnurgg — definition of done:** One specialist requests and receives genuinely new source-root evidence from another; the trace shows whether the decision changed; tests reject replays, forged identities, and duplicate messages; physical and simulated records have explicit source tiers; CI passes.

---

## 3. HyorinmaruK — PHYSICAL ENGINEERING + PRESENTATION ONLY (OWNER)

### P0 — Physical bench and specimens

- [ ] **PHY-01 — CAD/STL and printing:** Design real Slot/Tab components and a controlled-defect set with varied dimensions. Provide printable CAD/STL revisions and part/lot/print IDs; label printed specimens and perform physical assembly/fit tests.
- [ ] **PHY-02 — Camera rig:** Build stable mounts for a phone and Raspberry Pi/Hailo camera, with controlled lighting, scale markers, fixed camera geometry, wiring, power, and cable management. **Bakdaulet trains the vision model; HyorinmaruK does not.**
- [ ] **PHY-03 — Measurements:** Collect repeated digital-caliper measurements, gauge repeatability data, measurement uncertainty, units, timestamps, operator identity, and calibration references. Supply a separate ground-truth record for each physical specimen.
- [ ] **PHY-04 — Physical sorter:** Assemble the ESP32-S3, servo, IR/bin sensors, wiring, emergency stop/power cut, and controlled sorting mechanism. Agree on action/specimen ID matching with adilnurgg. Validate firmware behavior on the physical bench without assuming ownership of cloud/backend services.
- [ ] **PHY-05 — Physical acceptance tests:** Execute E02, E07, E12, E13 and tests for camera independence, wrong-bin outcomes, duplicate/replayed messages, and a complete real-part demonstration. Keep photo/video, raw logs, and explicit `PASS/FAIL` records for every test.
- [ ] **PHY-06 — Physical dataset handoff:** Deliver independent Phone/Pi image captures, part/lot IDs, caliper readings, assembly results, and actual bin sensor events to Bakdaulet (vision/simulation) and adilnurgg (backend/API), using the same canonical IDs.

### P0 — Presentation and demonstration

- [ ] **PITCH-01:** Prepare a 3–5-minute pitch and live physical demo. Explain a concrete defect, the fact that the 21 agents are **roles**, SAFE-MESH safety gating, scientific benchmarking, and business ROI only to the extent that results are experimentally validated or clearly described as scenarios.
- [ ] **PITCH-02:** Prepare the demo sequence: normal part → photo/CAD/caliper → agent requests evidence → HOLD/retest → human approval → physical sorting → sensor ACK. Clearly distinguish live operations from prerecorded fallbacks.
- [ ] **PITCH-03:** Produce slides and rehearse. Use scientific tables from Bakdaulet, agent traces/web screenshots from adilnurgg, and physical bench photos. Do not present untrained NVIDIA models, untested live LLM integrations, or synthetic ROI as proven achievements.
- [ ] **PITCH-04:** Provide two demo fallbacks: if a camera/network fails, use a clearly marked prerecorded example; if the servo is unsafe, show SAFE-MESH HOLD/recommendation without physical actuation.

**HyorinmaruK deliverables:** Printed physical parts; stable camera bench; calibrated measurements; physical sorter rig; photos, videos, test evidence; slides and rehearsed pitch.

**HyorinmaruK — definition of done:** Two actual camera captures and caliper ground truth join on the same physical part ID; sorter ACK is physically verified or the actuator is safely disabled; records are auditable; presentation claims match the evidence.

**Explicitly NOT HyorinmaruK's tasks:** Digital Twin, factory simulation, SimPy, scenario generation, ROI modeling, scientific benchmark code, VOI algorithms, Computer Vision model training, Google Cloud/Nebius deployment, and website/backend implementation.

---

## 4. Shared integration contract — all three people

Minimum common event fields for physical, simulated, and agent-generated messages:

```json
{
  "event_id": "unique-event-id",
  "specimen_id": "slot-or-tab-unique-id",
  "lot_id": "production-lot-id",
  "station_id": "phone|pi|caliper|assembly|sorter|virtual-station",
  "source_tier": "SIMULATED|PHYSICAL_CAPTURE|VERIFIED_PHYSICAL",
  "observed_at": "ISO-8601 timestamp",
  "source_root": "original-sensor-or-generator-id",
  "parent_source_roots": [],
  "cad_revision": "rev-id",
  "calibration_id": "calibration-record-id-or-null",
  "uncertainty": null,
  "run_id": "benchmark-or-physical-session-id",
  "signature": "verified-device-signature-or-null"
}
```

This is a **minimal alignment example**; adilnurgg must approve the final JSON Schema and station-identity policy. A `SIMULATED` record must never be promoted into a signed physical reading. A self-declared device ID is not trusted identity. The presence of a signature alone is not sufficient ground-truth verification; real physical truth requires a separate documented procedure.

**Required handoffs:**

1. **HyorinmaruK → Bakdaulet:** CAD/STL models, specimen/lot labels, both camera datasets, caliper truth, physical assembly outcomes, sorter results.
2. **Bakdaulet → adilnurgg:** Vision scores, anomaly maps, uncertainty, simulator/scenario/benchmark JSON, itemized cost assumptions, evidence requirements.
3. **adilnurgg → HyorinmaruK:** Authenticated station message formats, authorized sorter commands, physical ACK contract, and hardware integration-test instructions.
4. **adilnurgg → Bakdaulet:** Genuine request/response traces, timestamps, costs, and ACL outcomes for benchmarks/ablations.
5. **Bakdaulet → HyorinmaruK:** Scientific comparisons, confidence intervals, and presentation-approved claims.

---

## 5. Priority order for the next implementation phase (P0 → P1 → P2)

| Order | Task | Owner | Acceptance condition |
|---|---|---|---|
| 1 | Shared IDs and contracts; device authentication; replay protection | **adilnurgg** | Forged, duplicate, or unauthorized readings are rejected in tests |
| 2 | Fair VOI/request/sensor cost accounting | **Bakdaulet** | Re-run 30 × 1,000 cases with reconciled charges |
| 3 | Printed parts, independent camera captures, calibrated ground truth | **HyorinmaruK** | Physical evidence set and repeatability logs exist |
| 4 | Actual REQUEST/RESPONSE/VERIFY/UPDATE collaboration loop | **adilnurgg** | Trace shows new evidence and a documented decision change |
| 5 | Digital Factory, scenarios, and cost simulator | **Bakdaulet** | Same-seed reproducibility across benchmark policies |
| 6 | Scientific baselines, ablations, and vision evaluation | **Bakdaulet** | B0–B7 results, intervals, leakage-safe evaluation |
| 7 | Secure integrated API, UI, CI, release verification | **adilnurgg** | Browser end-to-end demonstration and passing pipeline |
| 8 | Physical sorter interlock and independently verified bin ACK | **HyorinmaruK** (hardware) + **adilnurgg** (auth/API) | Physical bin proof and replay rejection; otherwise HOLD |
| 9 | Slides, live bench rehearsal, and scientific claim review | **HyorinmaruK** (presentation), evidence owners contribute | No unsupported GPU/LLM/ROI claims; working fallback |
| 10 | Eight NVIDIA adapters and multi-factory extensions | **Bakdaulet** (science/sim), **adilnurgg** (integration) | Only call an adapter operational once verified in a live test |

**P2 capabilities stay on the architectural roadmap:** Omniverse/Isaac Sim, Replicator, cuOpt, PhysicsNeMo, DeepStream, Cosmos, Metropolis VSS, and Warp/Newton remain individually tracked research/integration adapters. Mark each as `NOT_CONFIGURED` until verified; unavailable NVIDIA services must not block the safe CPU-based main workflow.

---

## 6. Final demonstration — joint definition of done

- [ ] **Unified trace:** One real `specimen_id` appears in station observations, agent requests, decisions, and sorter events.
- [ ] **Two independent cameras:** Phone and Pi produce independent capture events; copies of a single photo are not counted as independent evidence.
- [ ] **Real collaboration:** Agent A requests evidence, Agent B returns genuinely new permitted evidence, and Agent A updates its belief; this is visible in the trace UI.
- [ ] **Adaptive VOI:** The next inspection changes based on newly received information, with its full cost included in accounting.
- [ ] **Safety:** Stale, unsigned, conflicting, uncalibrated, or forged-ACK evidence → HOLD/PENDING. No actuation without manual approval.
- [ ] **Fair experiment:** Equal information/budget/seeds where appropriate; all sensor, request, retake, and compute costs accounted for; uncertainty intervals reported.
- [ ] **Simulation:** Bakdaulet's Digital Factory remains clearly distinct from physical ground truth, with reproducible scenarios and disclosed ROI assumptions.
- [ ] **Release integrity:** CI passes, consistent release/version labels, valid SHA256 manifest, no repository secrets.
- [ ] **Honest claims:** 21 roles ≠ 21 live LLM models; eight NVIDIA adapters ≠ eight running systems; simulated ROI ≠ demonstrated factory savings; passing unit tests ≠ physical safety certification.
- [ ] **Presentation:** HyorinmaruK delivers slides and a physical demonstration that accurately distinguishes real and simulated evidence.

## 7. Submission structure — one monorepo

```text
qualityrelay/
  qualityrelay17/             # implementation modules; reconcile the release to 18.1
  schemas/                    # adilnurgg: event and safety API contracts
  firmware/                   # HyorinmaruK: physical firmware and bench integration
  examples/cad/stl/           # HyorinmaruK: printable mechanical artifacts
  examples/physical/          # HyorinmaruK: physical captures and ground truth (privacy review)
  docs/research/              # Bakdaulet: benchmarking, simulation, vision, cost
  docs/engineering/           # adilnurgg: CI, security, deployment
  web/                        # adilnurgg: UI integration consuming Bakdaulet's simulation outputs
  slides/                     # HyorinmaruK: pitch and demonstration assets
  tests/                      # each owner authors their tests; adilnurgg integrates CI
  .github/workflows/          # adilnurgg: test and release checks
```

**Release policy:** No single person may self-merge safety-critical changes. Authentication and physical actuation changes require review from other owners. If hardware/LLM/GPU services have not been tested live, mark them `NOT_CONFIGURED`; the main scientific demonstration must still run on the CPU baseline.