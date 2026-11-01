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
- [x] **SIM-08 — CNC cell demo scenario D01** *(done 1 Nov, SIMULATED only: `qualityrelay17/sim/scenarios.py` (`CNC`), `engine.py` (`control=closed_loop|audit|none`), `gcode.py`, Studio 3D Lab (CNC machines, stock crates, loader robots, caliper chamber, reject conveyor, "Loop" tab), `docs/research/CNC_DEMO_SCENARIO_D01.md`, `tests/test_sim_cnc_demo.py`. Registered F/M truth tables verified unchanged. Not done and not claimed: any real CNC, robot, conveyor or caliper; the G-code is illustrative; the baseline audit interval is an adjustable assumption.)*: Wrong tool offset from the first part, camera gate, caliper chamber for flagged parts only (every dimension vs CAD nominal), halt → measure → propose → operator approval → resume, waste accounting, and today's-practice baseline for Compare mode.

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

- [x] **BACK-01 — Fix the signing oracle** *(done 31 Oct, `qualityrelay17/station_auth.py`; per-device key on the ESP32 authenticates an `X-Station-*` envelope with nonce + 60 s timestamp window + body-hash + path binding; per-endpoint ACL; body `station_id` must equal the proven station; the server-only station key signs Evidence only after that, so it is a distinct gateway identity. Unsigned/forged/replayed/tampered/cross-path/stale requests are 401/403 in `tests/test_api.py` and over real HTTP in `scripts/rehearse_e12_e13.py`. Not covered here: TLS / server authenticity = CLOUD-01; operator auth on `/actuation/stage` = BACK-04, now done.)*: In `api.py` endpoints `/hardware/caliper-reading` and `/hardware/bin-ack`, verify the real sending station identity before accepting data. Never sign unchecked client-supplied `station_id` or measurements. Use mutual authentication or a per-device signed envelope, nonce, timestamp/TTL, replay protection, ACL, and a distinct trusted-gateway identity.
- [x] **BACK-02 — Verified evidence ledger** *(done 31 Oct in software, `qualityrelay17/verification.py` + `ledger.py`. Each ledger row stores the station the BACK-01 envelope proved. `append` refuses `VERIFIED_PHYSICAL`; the tier is derived only from an append-only `verifications` table. A row is a candidate only if it is `PHYSICAL_CAPTURE`, station-authenticated by its own station, validly gateway-signed and has a `calibration_id`. An authenticated operator then records `GT-CAL-01` (independent reference instrument, `|Δ| ≤ 2·√(u²+u_ref²)`) or `GT-VIS-01` under `docs/engineering/GROUND_TRUTH_VERIFICATION_PROCEDURE.md`, with the specimen read off the part. A disagreement is recorded as `DISPUTED` and latches. Routes: `POST /evidence/{id}/verify`, `GET /evidence/{id}/status`, `GET /evidence/procedures`. Not done: no real ground-truth check recorded yet; image stations are not device-authenticated, so image evidence cannot be a candidate yet.)*: Only station-authenticated readings may become candidates for `VERIFIED_PHYSICAL`; also require a separate documented human/instrument ground-truth verification procedure. Keep raw unsigned measurements at `PHYSICAL_CAPTURE` or `UNVERIFIED` status.
- [x] **BACK-03 — Sorter event binding** *(done 31 Oct, `actuation.py` + `ledger.route_events`. An append-only journal records every transition with the full tuple: action, specimen, dispatch and sensor station, requested and actual bin, sensor_event_id, sensed time (from the signed envelope timestamp), approval time and approver. `UNIQUE(sensor_event_id)` means one sensor event binds at most one action, across restarts. ACKs outside the action's time window are refused, including detections made before approval. Two in-flight routes for one specimen give `AMBIGUOUS_ACK` unless the ACK names an `action_id`. Identical stage retries are idempotent; a changed request reusing an id is 409. Envelope nonces are BACK-01; commands carry their own nonce and TTL. `specimen_identity` stays `NOT_PROVEN` until `POST /actuation/{id}/identity`, and a mismatch latches FAULTED. Not done: firmware still sends a placeholder specimen id, see PHYSICAL_TEST_PLAYBOOK.)*: Bind `action_id ↔ specimen_id ↔ station_id ↔ requested_bin ↔ actual_bin ↔ unique sensor_event_id ↔ timestamp`. Enforce idempotency, nonces, TTL, and rejection of duplicate acknowledgments. A detected object inside a bin does **not** automatically prove it is the correct specimen.
- [x] **BACK-04 — Safety enforcement** *(software half done 31 Oct; hardware half open. Operator bearer tokens (`operator_auth.py`) are required on stage, approve, arm, E-stop reset, identity and verify. Caller-asserted `approved`/`operator_id`/`origin` fields now get 422. LLM, agent and safe_mesh output can only `POST /actuation/propose` (no timer, no command), and machine identities can never approve. The evidence gate re-runs at approval, and a static test checks that no LLM or agent module imports the interlock. The default is HOLD. The hardware gate `ACTUATION_HARDWARE_ENABLED` is off by default, plus a runtime `arm`. The E-stop latches and needs no token to trigger: it disarms, aborts staged routes and faults any route in motion. The device's `estop_loop_ok:false` also latches it. Reset does not re-arm. Stage TTL is 600 s and ACK timeout 30 s (→ FAULTED + disarm). Only one route is in motion at a time. Pull commands are signed and expire after 10 s. A restart closes open routes as EXPIRED or FAULTED. Not done, and only possible in hardware (HyorinmaruK): a hard-wired E-stop that cuts actuator power, a guard switch, spring-return-to-HOLD, and sorter firmware implementing the contract in PHYSICAL_TEST_PLAYBOOK §4. The server still drives no GPIO.)*: A PASS recommended by an LLM/AI must never directly drive GPIO. Require human-approved actions, mechanical/electrical interlocks, default HOLD, emergency stop and hardware disable gate, timeouts, and safe behavior under power loss.

### P0 — Genuine decentralized collaboration

- [x] **AGENT-01 — Typed negotiation protocol** *(first increment 31 Oct, `qualityrelay17/collective/`: the six message kinds from the research plan section 3.2, role-signed (sender = signature, never text), correlation ids, reasons, hypotheses, evidence roots, request cost, deadline; `REJECT_REQUEST / TIMEOUT / SENSOR_FAILURE / STALE_EVIDENCE / DUPLICATE_SOURCE / BAD_SIGNATURE` are technical outcomes, never measurements. In-process bus, deterministic roles, no LLM, no network — the types are transport-independent.)*: `REQUEST_EVIDENCE → RESPONSE_EVIDENCE → VERIFY → UPDATE_BELIEF → PROPOSE_INSPECTION → DECISION_REVIEW`. Include authenticated request IDs, sender/receiver roles, access policies, reasons, evidence roots, request costs, and deadlines.
- [x] **AGENT-02 — Private context per specialist** *(31 Oct: `PeerBus` keeps one private store per role; a role sees only its own observations plus admissible summaries from granted requests, never raw payloads; entitlement = `roles.py required_sources`, ownership = station map; tests cover unentitled requester, non-owner recipient, untargeted request.)*: Give Phone, Pi, CAD, Metrology, Assembly, Process, Risk, and other roles different scoped views and permissions. Do not allow them to silently inspect another role's raw data; require authenticated evidence requests.
- [x] **AGENT-03 — Explainable interaction traces** *(31 Oct: every message with signature result and correlation id, every VERIFY outcome, belief before/after, chosen inspection, decision vs. no-request control, the plan's five "not theatre" criteria evaluated on the trace itself. JSON via `GET /research/collective/runs/{id}/traces/{part}`; narrative viewer in the web Agent Evidence Room.)*: Store message-level provenance; rejected, missing, and timed-out responses; before/after belief; chosen inspection; and decision changes. Expose JSON traces and a web dashboard trace viewer.
- [x] **AGENT-04 — Live LLM smoke test** *(done 31 Oct with OpenAI `gpt-5.6-luna`; Nebius factory implemented and tested offline, unused until a team key exists. `collective/llm_planner.py`: two tools, code validates, bus enforces ACL, safe_mesh decides; tokens/latency/cost per call; spend cap; `NOT_CONFIGURED` without keys; `GET /integrations/llm`. GPT-5.x needs `OPENAI_REASONING_EFFORT=none` to call tools on chat completions. Live evidence: LLM-01 and LLM-07 below.)*: Validate actual credentials/permissions, a named deployed model, genuine tool calls, server-side tool allowlists, and token/latency/cost logging. **21 roles do not imply 21 separate running models.** Show actual active roles and report `NOT_CONFIGURED` when credentials are absent.
- [x] **AGENT-05 — Evidence lineage DAG** *(31 Oct: the bus VERIFY step runs `lineage.lineage_groups` against what the requester already holds; a re-score of the same photo is `DUPLICATE_SOURCE`, delivered but flagged, does not move belief and does not count as a camera for `safe_mesh`; stale and bad-signature evidence is refused before delivery.)*: Do not count two scores from the same underlying photo as independent sources. Trace all lineage ancestors. Stale, duplicate, unsigned, or mixed-origin evidence should trigger HOLD/review as required by policy.

### P0 — LLM stack and deployment plan for all 21 roles (adilnurgg owns this)

**Architectural decision:** Keep the 21 specialist role definitions already present in `qualityrelay17/roles.py`; do **not** train or host 21 separate LLMs. Use one verified, tool-calling Nebius Token Factory model as the shared stateless reasoning backend, while each role retains a distinct **server-enforced** evidence scope, tool allowlist, system prompt, budget, and auditable identity. Normally select **2–7 relevant roles per specimen**; do not invoke all 21 on every part. The individual agents must own/receive different evidence, not merely be differently named prompts that all see the same database.

**Provider decision (31 Oct, adilnurgg):** the working provider is **OpenAI `gpt-5.6-luna`** (LLM-01 verified). Nebius stays implemented and optional (`--provider nebius` once a Token Factory key exists). Of the stack below, in use today: the `openai` SDK, Pydantic/FastAPI, `safe_mesh.py`, and an in-process typed bus with a JSON trace (instead of LangGraph/NATS/PostgreSQL, which stay optional and are not needed for the demo).

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

Kept: only what the demo and the science still need. Everything else is closed or deferred below, with the reason.

- [x] **LLM-01 — Entitlement and model verification** *(done 31 Oct for OpenAI: `scripts/verify_nebius_entitlement.py --provider openai --confirm-spend` -> `VERIFIED` for `gpt-5.6-luna` (text roundtrip + schema-valid tool call + final answer), redacted manifest in `examples/results/llm_01_entitlement/openai_*.json`, key fingerprint only. Same tool runs for Nebius (`--provider nebius`) when a key exists. `GET /integrations/llm` shows the last verdict per provider.)*
- [x] **LLM-07 — Observable collaboration demo** *(done 31 Oct, live: `pi_suspect` with planner `openai:gpt-5.6-luna`. Quality Inspector requests CALIPER from Metrology, ASSEMBLY from Assembly, PI_IMAGE from the Pi owner; each response VERIFIED; independent sources 2 -> 5; planner finishes; SAFE-MESH -> HOLD `VISUAL_PI_SUSPECT` vs control HOLD for missing evidence; all six "not theatre" criteria true; 4 calls, ~$0.001. Trace: `examples/results/llm_07_demo/`; rendered in the Studio Agents view. Evidence is TEST_FIXTURE; the LLM calls are live.)*
- [x] **LLM-08 — Scientific baselines (live LLM rows)** *(done 31 Oct, smoke scale: `scripts/run_llm_gate_b.py --provider openai --scenarios S11,S12,S13 --n 30`, one lot per scenario, clean tree `f3a527b`, 731 calls, $0.156, COMPLETE. `B7_llm` = B7 with the LLM replacing only the VOI selector; `B7_llm-specialist_roles` = same with a generic prompt; paired against B0/B1/B5/B6/B7 on the same SIMULATED cases. Released good 0.967 for both LLM variants vs 0.867 for B7 VOI, because the LLM buys more evidence (3.4 requests/part role prompt, 2.6-2.9 generic, vs 2.0); cost/unit higher for the role prompt in all three (S11 1.96 vs 1.37), generic below B7 only in S13 (1.60 vs 1.77). Role prompt adds requests, not outcomes. Unsafe PASS 0 for every policy: at ~1-4/1000 a 30-part lot cannot measure safety. Data: `examples/results/llm_gate_b/openai-gpt-5.6-luna-20261031T220803Z/`. Not done: B4 and B7-structured_protocol (need a free-text-to-action parser, design decision with Bakdaulet); a larger-n run if the paper needs safety intervals. Bakdaulet owns design and interpretation.)*
- [x] **LLM-09 — Failure and adversarial tests** *(done 31 Oct. Already covered: invented event ids, missing provenance, forged signatures, duplicates/replay, stale evidence, unentitled/mis-addressed requests, provider failure, spend and round caps, network partition/timeout (`tests/test_collective_*.py`, `tests/test_llm_gate_b.py`). Added `tests/test_llm_prompt_injection.py`: free-text CAD metadata never reaches the model (payload allowlist); where signed text does reach it, a model that obeys the injection cannot change the safe_mesh decision.)*

Closed or deferred (not needed for the 18.1 demo):

- **LLM-02 21-role prompts: deferred.** Gate A measured that extra roles add only message cost in this world, and the pitch must not claim 21 collaborating agents. The six roles actually used have server-side scopes in `roles.py` + `collective/`.
- **LLM-03 reasoning loop: done another way.** `collective/llm_planner.py` + engine validate every tool call, allow only `request_evidence`/`finish`, and log each call in the trace. The old `nebius.py` / `agent_tools.py` path is superseded.
- **LLM-04 peer messaging: done in-process** (AGENT-01): typed signed messages with ids, cost, deadline; REQUEST_DENIED is the `REJECT_REQUEST` outcome. Separate-process workers are Bakdaulet's optional P4.
- **LLM-05 decentralisation and lineage: done in-process** (AGENT-02/05): private per-role stores, server-side ACL, `source_root` dedupe, stale/replay refusal.
- **LLM-06 budgeted activation: done for the roles in use.** Spend caps (calls/tokens/USD), the model never produces probabilities or money, inspection and LLM costs each counted once. "Activate only useful specialists" waits on LLM-02.
- **LLM-10 cloud: moved to CLOUD-01.** Already done: CI, pinned dependencies, prompt hashes + model + call parameters in run manifests. Deployment/TLS only if the demo is hosted; NATS/PostgreSQL optional.

**Minimum live acceptance demo:** `Quality Inspector → REQUEST_EVIDENCE → Metrology Engineer → EVIDENCE_RESPONSE → VERIFY source_root/ACL → UPDATE_BELIEF → Inspection Planner (measured NetVOI) → SAFE-MESH HOLD/PASS_REVIEW → human authorization if any physical action`. This must show **real API calls**, a real new source and its cost. A typed simulated test is useful but cannot be labeled a live 21-agent deployment.

**Implementation pointers:** existing `qualityrelay17/roles.py`, `nebius.py`, `agent_tools.py`, `safe_mesh.py`; scientific design in `docs/architectures/02_SPECIALIST_LLM_AGENTS.md` and `docs/research/COLLECTIVE_17_1_BAKDAULET.md`.

**Official/open-source references:** Nebius API: https://api.tokenfactory.nebius.com/docs ; Nebius model catalog: https://nebius.com/services/token-factory/models/glm-models-inference ; https://nebius.com/services/token-factory/models/qwen-models-inference ; examples: https://github.com/nebius/token-factory-cookbook ; LangGraph: https://github.com/langchain-ai/langgraph ; NATS: https://docs.nats.io/concepts/jetstream and https://github.com/nats-io/nats.py . Check library versions and licenses before pinning.

### P0 — Integration and release engineering

- [x] **API-01** *(done 31 Oct: `qualityrelay17/results_api.py` serves the registered `examples/results/` artifacts read-only. Routes: `/simulation/{scenarios,runs,runs/{run_id},summary,scale,run}`, `/benchmark/{gate-a,gate-a/{sid},warp,warp/{sid}}` and `/economics/{assumptions,roi,roi/{sid},hold-all,capacity-plan}`. Every response carries `source_tier`, `seed`/`seeds`, `model_version`, `run_id`, `assumption_set` and `git_commit`. The legacy `/simulation/compare` and `/simulation/factory-line` routes now carry them too. Non-finite ROI values become `null`. Registered run records validate against `docs/research/sim_api/simulation_response.schema.json`. Tests: `tests/test_results_api.py`.)*: Expose Bakdaulet's simulator results through `/simulation/*`, `/benchmark/*`, and `/economics/*`. Include `source_tier`, `seed`, `model_version`, `run_id`, and `assumption_set` in responses.
- [x] **WEB-01** *(done 31 Oct: `web/index.html` + `site.js` have three top-level views. Each has its own coloured app-bar band and a single tier badge. **Live Physical Inspection** (`#physical`, badge `PHYSICAL`) lists only hardware-ledger records, via the new read-only `GET /physical/status` and `GET /physical/events`. Each row's tier is derived per row: `PHYSICAL_CAPTURE` until a recorded ground-truth check makes it `VERIFIED_PHYSICAL`. Rows show a fixed set of measurement fields, never signatures. The unauthenticated `/sim/live` feed sits on that page in its own box labelled `UNVERIFIED` and no longer lights up stations in the simulated 3D line. **Digital Factory Simulation** (`#sim`, `#sim/parts`, `#sim/results`, badge `SIMULATED`) holds the 3D Lab, CAD parts and the 15-scenario results. **Agent Collaboration & Benchmark** (`#agents`, `#agents/benchmark`, badge `TEST_FIXTURE · SIMULATED`) runs one collective case and shows the decision versus the control run, the belief path, the criteria, the NetVOI candidates and the full message trace. That page also holds Gate A and Warp. Unconfigured LLM planners are listed but cannot be selected. Old `#lab/#parts/#results/#science` links redirect. Tests are in `tests/test_api.py` (WEB-01 section). Not done: no physical records exist yet, so the physical view has only been seen in its empty state in a browser; the populated rows are covered by API tests only.)*: Implement three clearly separated views: **Live Physical Inspection**, **Digital Factory Simulation**, and **Agent Collaboration & Benchmark**. Never blend physical and synthetic outcomes without labels. **adilnurgg owns frontend, backend, website, and cloud integration.**
- [ ] **CLOUD-01:** Own Google Cloud/backend deployment, Nebius integration, secrets management, HTTPS, access logging, and spend caps. Neither Bakdaulet nor HyorinmaruK owns Google Cloud deployment.
- [x] **REL-01** *(done 31 Oct: the single release label is `qualityrelay17.__version__ = "18.1"`; `pyproject.toml`, the API title/version, `GET /health` (`release`), the README title and the regenerated `schemas/openapi_demo.json` all carry it, enforced by `tests/test_release.py`. `scripts/release_check.py all` regenerates the OpenAPI snapshot, runs pytest and writes `RELEASE_VALIDATION.json` from that run (commit, dirty flag, counts), rebuilds `FILE_SHA256_MANIFEST.json` and verifies it. The old manifest was stale for 19 of its 89 entries and missed 235 packaged files. It now covers every tracked or untracked-but-not-ignored file. Text is hashed with CRLF→LF so Windows `autocrlf` checkouts verify. The records were generated on an uncommitted tree; re-run `all` after the final release commit.)*: Reconcile release labels in root files, README, and API as version `18.1`; regenerate `RELEASE_VALIDATION.json` based on a new actual run; repair the broken/missing SHA256 manifest entries and verify all packaged hashes.
- [ ] **REL-02** *(repo half done 31 Oct; GitHub half pending a `gh` login with admin + project scope. `.github/workflows/tests.yml` now runs `lint` (ruff/pyflakes), `types` (mypy: safety/auth/actuation modules clean, 12 research modules on a documented ratchet), `schemas` (`scripts/check_schemas.py`: metaschema validity + OpenAPI drift), `security` (bandit medium+, pip-audit, tracked-secret guard) and `test` on 3.11/3.13. `review-gate.yml` is a required check that demands two non-author approvals on the head commit for any path in `.github/safety-paths.txt`; it reads the rules from the base commit. `CODEOWNERS`, PR template and issue forms are in `.github/`. `tests/test_ci_policy.py` pins all of it. `scripts/github_board.py apply|protect` creates the 50 open-task issues, the ownership Project and branch protection; not yet run. Details: `docs/engineering/CI_AND_REVIEW_POLICY.md`.)*: Configure `.github/workflows/tests.yml` for linting, types, schemas, security checks, and tests. Add PR reviews, two-review rules for safety/auth/actuation changes, GitHub issues, and an ownership board.
- [x] **REL-03** *(done 31 Oct: `THIRD_PARTY_MANIFEST.json` (versioned, schema-checked) records every Python requirement's reviewed licence and the licence string its wheel reports, 19 separately installed upstream components (none bundled), and 22 adapters with evidence-backed statuses: 1 `WORKING` (NVIDIA Warp, CPU backend only, never on CUDA), 5 `TESTED` (LLM planners/entitlement probe with fake clients; ESP32 station/sorter in software), 16 `NOT_CONFIGURED` (every other NVIDIA slot, Pi/Hailo, TAO, Anomalib, OR-Tools, GCP, …). `requirements-lock.txt` pins all 71 transitive packages; CI installs only that. CI's `dependencies` job fails on missing evidence, lock drift, unknown/denied licences or relicensing. `GET /integrations` serves the registry. Found on the way: `networkx` was an undeclared dependency (trimesh `mesh.section()` in `sim/cad.py`), and `tests/test_warp_mc.py` had always been skipped in CI. The STFPM anomaly runs reported in ANOMALY_MODEL_HANDOFF.md have no committed manifests, so that adapter stays `NOT_CONFIGURED` until they are. See `docs/engineering/DEPENDENCIES_AND_ADAPTERS.md`.)*: Maintain a versioned upstream dependency/license manifest, pinned Python requirements, and honest adapter statuses (`WORKING`, `TESTED`, `NOT_CONFIGURED`). Do **not** claim that all eight NVIDIA services are already running.

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