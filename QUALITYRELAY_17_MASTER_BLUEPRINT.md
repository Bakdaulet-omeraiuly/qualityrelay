# QUALITYRELAY 17.0 — SAFE-MESH
## Fully Decentralized Scientific Manufacturing Intelligence & Assured Digital Factory

**Authoring status:** 30 October 2026 research release · Complete implementation blueprint + limited runnable reference · Team of 3 (+1 optional) · Physical-camera validation NOT YET DONE

> **Scientific integrity statement:** This is a proposed research program and engineering reference, **not** a peer-reviewed discovery, certified factory product, validated NVIDIA model, live Nebius deployment or demonstrated cost reduction. The current synthetic SAFE-MESH reference **does not outperform** conservative rules. Deliverable status and evidence tiers are enumerated below. Preserve null results.

### One-sentence thesis
Can independently governed station agents combine correlated evidence from **two independent cameras, CAD geometry, caliper metrology and production history**, choose a low-cost informative inspection, and safely verify physical sorter interventions with **no increase in unsafe part releases** compared with equally informed centralized or conservative baselines?

### User-approved immutable requirements
- Architecture priority: **fully decentralized station authority**. Chief Engineer exists ONLY as centralized/hybrid **comparison or optional advisory mode**; it must not be a production single point of failure.
- **21 specialist LLM roles** with server-validated tool scopes; only relevant roles execute per task.
- **Phone camera and independent Raspberry Pi + Hailo-8L camera**; phone Photo↔Photo reference comparison, both visual defect evidence, CAD/STL↔camera projected geometry, and caliper manually verified measurement plus optional LCD OCR.
- **CAD is design expectation, not automatically measured truth**. Two analyses from the SAME source photograph are correlated; no double counting.
- Manufacturing path: 3D printing → metrology → vision → assembly → physically confirmed sorter (PASS/HOLD/CONFIRMED REJECT).
- **V-DER, CAIR, EVIDENCE-MESH, lineage/provenance, PACE safety gate, SAFE-MESH**, simulation-to-reality, multi-factory Digital Twin, smart matching, ROI and safety benchmarking.
- NVIDIA eight optional modules (Isaac/Omniverse, Replicator, cuOpt, PhysicsNeMo, DeepStream, Cosmos, VSS, Warp/Newton) and Nebius models integrated via versioned adapters; CPU baseline always runs without them.
- **Google Cloud owners exclusively `adilnurgg` and `HyorinmaruK`; Bakdaulet has no Google Cloud tasks.** HyorinmaruK (mechanical engineer) leads physical validation, sorter/vision hardware and pitch.
- **GPU resources described by organizers are available to request, NOT verified active in our accounts**. One RTX GPU needed for Isaac Sim; H100 not supported for ray-traced Isaac Sim.
- Use MIT/Apache and other approved GitHub libraries **with exact license/model-card and pin reviews**; do not bundle them as if our own IP.

## Navigation

1. Executive choices, truthfulness, and reproducibility
2. Target real-world workflow and website UX
3. Scientific mathematical model and new hypothesis
4. Experimental comparison, statistics and safety constraints
5. Architecture documentation — 12 independently designed subsystems
6. GPU, NVIDIA, Nebius and ScienceClaw implementation
7. GitHub external library adoption and license audit
8. Three-member team and optional fourth; release gates
9. Live demo, accepted evidence tiers and unanswered work
10. Legacy preservation and sources

---

# 1. The system, the WHY, and what is already real

**Manufacturing problem.** The slot and tab can each meet local tolerances while their assembly clearance is too small; different actors own measurements. A camera may detect a chip while a caliper confirms correct thickness. Another camera may disagree because of lighting or noise. Plain voting and uncalibrated photo diffs are not enough; incorrect PASS can be costly or dangerous.

**Product.** One web site displays a common audit and simulation interface, but underneath, station services are independent actors with distinct credentials, local data, bounded tools and event lineage. Browser centrality DOES NOT imply centralized manufacturing control. The operator always controls physical actuation.

**Original contributions to IMPLEMENT AND TEST (NOT claimed as proven novelty):**

1. **Evidence lineage without double counting:** every datum is linked to source roots. Derived CAD/photo projections and multiple specialist interpretations from the same photo are correlated.
2. **Decision-focused active inspection:** choose another view, caliper repeat, revised CAD or station summary when its estimated reduction in expected decision loss justifies time and cost. Baseline Bayesian VOI is established prior art; the claimed contribution must be the audited decentralized interaction under safety constraints.
3. **Minority evidence / missing evidence protection:** one substantiated anomaly is not overwritten by majority model votes; missing, stale or wrong-revision information triggers HOLD or bounded local operation.
4. **Governed physical intervention:** decision, authorized approval, idempotent servo operation and independent sensor ACK in a traceable chain.
5. **Twin-to-factory accountability:** uncertainty/camera shift/costs and post-action outcomes are measured separately for simulated and physical runs.

**Evidence levels:** `DESIGN_ONLY`, `EXECUTED_TEST_FIXTURE`, `SIMULATED`, `PHYSICAL_CAPTURE`, `VERIFIED_PHYSICAL`. A test fixture cannot silently upgrade to industrial validation. 

## Single website paths

- `/`: live summary and provenance panel (demo currently static research interface)
- `/inspection/phone`: camera capture/photo-to-photo, calibration, operator-confirmed caliper reading
- `/inspection/pi`: independent edge vision evidence and network status
- `/cad`: CAD revision, STL projection, feature/contour mismatch and uncertainty
- `/factory`: station queues, lots, discrete-event engine, digital factory 3D optional RTX plugin
- `/agents`: role-specific evidence request, argument/result trace and bounded Nebius tool calls
- `/simulation`: seeded factory experiments, adversarial sensor/camera/connection tests
- `/optimization`: selective assembly, batch match, inspections, production cost and cuOpt fallback
- `/sorter`: stage/approve/verify physical route; no automatic hardware commands without safety gateway
- `/research`: baselines, preregistered runs, CIs, source hashes and explicit negative findings

These are **target website routes**. The runnable prototype presently implements only the single landing page and limited FastAPI research endpoints; see `docs/engineering/STATUS_AND_GATES.md`.

# 2. Physical demonstration: exactly what the operator sees

1. HyorinmaruK prints Slot A and Tab B (plus chipped, warped, narrow, wide, nominal samples) using provided 5.0 STL geometry and records all CAD revisions. Use two camera stands and repeatable lighting/background.
2. Operator registers specimen ID and blind ground-truth record (held out from LLM) then performs manual digital caliper measurement. Webcam/phone optional OCR reads LCD but **does not independently validate the caliper**; decimal and unit are confirmed by human.
3. Phone Vision Agent uses calibrated photo reference and optionally constrained CAD orthographic projection. Its outputs are defect hypotheses, feature deltas, uncertainty and source identifiers, not guaranteed millimeter measurements.
4. Pi Vision Agent acquires independent physical capture using Pi + Hailo-8L (if available). Without actual Pi/hardware, show `UNAVAILABLE` and **do not present simulated camera as real**.
5. Station agents fetch authorized summaries and log raw-source lineage, CAD revision, timestamp and uncertainty. Safety rules prevent correlated photo interpretations from being treated as independent votes.
6. Scientific engine computes local-tolerance assembly risk, proposes optional V-DER/CAIR additional measurement and ranks plans based on measured/assumed cost.
7. If phone and Pi disagree, image unusable, CAD revision mismatched, measurement unconfirmed, or proof missing: HOLD. If a human authorizes, sorter gate routes the specimen; IR beam or camera reports independent ACK.
8. UI reports inspected, confirmed-nonconforming, and physically rejected **as three different counters**. Replayed events can never increment counts twice.

**Servo controls sorting gate only, NOT caliper jaws.** Mechanical interlocks, servo travel limits, emergency-stop and on-device arming are required before connecting real actuation. The bundled Python reference does not actuate hardware.

# 3. Scientific method: formal hypotheses and decision mathematics

## 3.1 Assembly clearance risk

Let slot width `W`, tab thickness `T`, and clearance `C = W - T`. For accepted parts, quantity of interest is `P(C < c_min | W in slot_spec AND T in tab_spec, evidence)`. In the independent untruncated Normal illustrative baseline, `mu_C = mu_W - mu_T` and `sigma_C^2 = sigma_W^2 + sigma_T^2 - 2*rho*sigma_W*sigma_T`; the production benchmark **must condition on acceptance**, via truncated-distribution Monte Carlo or numerical integration and declare process correlation and uncertainty. Avoid pretending 3D printer output is Normal without calibration.

The original 5.0 sample is deliberately challenging: Slot 20.5–21.5 mm, Tab 19.5–20.5 mm, minimum clearance 0.5 mm. Individually accepted Slot 20.5 and Tab 20.5 give zero clearance, violating assembly functional requirement. These are design exercise values, NOT measured factory parameters.

## 3.2 Expected value of information

For current evidence `E`, action `a`, future observation `Y`, possible decisions `d`, true state `s` and loss `L(d,s)`:

`R(E) = min_d E[L(d,s) | E]`

`VOI(a | E) = R(E) - E_Y[R(E,Y) | E] - inspection_cost(a)`

A positive estimated VOI only justifies proposing an inspection after feasibility and safety checks. Estimating likelihoods from unvalidated LLM opinions does not create calibrated probabilities. Compare against entropy/information-gain inspection, cheaper heuristics, always-inspect and conservative rules. Source-derived evidence must be grouped to avoid naive independence assumptions.

## 3.3 Evidence lineage and provenance

Each event contains `event_id, specimen_id, station_id, source_root, parent_source_roots, origin, observed_at, model_version, CAD_revision, calibration_id, uncertainty, signature`. The graph collapses repeated source root / known derived descendants before treating observations as independent. Strong claims require **probabilistic dependencies** or joint calibration; graph-based deduplication alone does not solve unknown correlation.

## 3.4 Safety-constrained economics

Choose policy `pi` to minimize `E(total_cost | pi)` subject to `Pr(unsafe_PASS | pi) <= epsilon` and a minimum acceptable-unit throughput. `epsilon` must be determined with safety stakeholder approval; a run that HOLDs everything is not a meaningful winner. Compare paired policies on **same scenarios, same seeds, same measurement budget and appropriate model capability**. GPU/API and labor costs must be included for realistic ROI.

## 3.5 What counts as a scientific discovery?

A novel acronym or more agents does NOT prove novelty. A legitimate contribution requires comparison to prior art, a mechanism that outperforms strong baselines in a specific regime, interpretable failure conditions, reproducible calibrated measurements, uncertainty intervals, independent test lots and scientific review. Publish negative findings.

# 4. Reproducible scientific finding NOW

The shipped reference simulation uses **30 seeds × 1000 simulated specimens per seed**. This is NOT a factory trial. With the current fixed conservative decision gate:

- Conservative rules: unsafe PASS = 106/30,000 (0.3533%), mean assumed cost = 2424.93 per 1000-part simulated run.
- SAFE-MESH reference: same unsafe PASS = 106/30,000, mean cost = 2462.87; extra average cost **+37.93** simulated currency units per 1000-part run.
- 95% paired cluster-bootstrap interval for additional cost approximately **[36.43, 39.37]** units; no superiority over rules is shown.
- These numbers are conditional on the toy simulator/cost coefficients. They are neither a validated real-world prediction nor evidence that the methodology will always underperform.

To create a result worth submitting: implement a truly *adaptive* inspection policy with calibrated conditional likelihood and cheaper relevant probes; include conservative controls at matching safety, then measure held-out physical and shifted-distribution performance. If no benefit, report a negative result without inflating ROI.

# 5. Independently specified architecture modules

Each module is independently documented and gated below. Source files remain separately available in `docs/architectures/` for parallel GitHub work.


---

## MODULE — `01_DECENTRALIZED_EVIDENCE_MESH.md`

# Decentralized Evidence Mesh

**Owner:** adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Research purpose
Keep ownership of raw factory data at its source while allowing separately authorized evidence requests. The network must allow local continuity when Chief Engineer or upstream cloud inference disappears.

## Data layout
- Slot station: measurements W, calibration, SPC, lot ID, process metadata.
- Tab station: T, process profile, print/machine run, tolerance and instrument checks.
- Assembly station: W−T compatibility, minimum clearance, pairing records.
- Phone Vision station: photo hashes, camera pose, model version, frame quality, anomalies.
- Pi Vision station: separately captured images, local queue, independent model outputs.
- Sorter station: approved request, physical actuator request and independent route acknowledgment.
- Shared router: immutable pointer/event transport **without authority** to issue metrology, modify measurements or release PASS.

## Protocol and constraints
Use signed events with event_id, specimen_id, station_id, observed_at, source_root, calibration_id, origin, model_version, payload hash, parent hashes, authorization and signature. Peer requests must reference authorized schemas; `chief_readonly` only receives allowlisted summaries. Network downtime causes PARTIAL_COVERAGE, not inferred false measurements. On reconnection, replay idempotently against event IDs and enforce TTL, bounded queues, watermark progress, clock skew allowances and digest checks.

## Trust assumptions
HMAC attests that a keyed station emitted a message; it cannot verify that the sensor is uncompromised or that the physical object is genuine. Prefer device-bound keys, rotation, TLS, inventory identifiers, event replay protection and authenticated operator binding in future factory pilot. Do not call this a blockchain.

## Implemented here
`contracts.py`, `ledger.py`, `safe_mesh.py`. Event collection in one process is **not** a proven real network mesh; original QualityRelay 15 dual-station code provides two-process/two-SQLite reference in `legacy/`.

## Scientific test
Inject missing phone, missing Pi, stale station response, cloned images, tampered signatures, replay, Chief failure, dropped router events. Report both decision quality and the amount of useful service retained, not availability alone.

## Acceptance
- Denied raw unauthorized read; snapshots signed; no duplicate event insertion.
- Every PASS_REVIEW contains enough current verified modalities, never a physical PASS.
- Offline operation does not silently reuse stale cross-station state.



---

## MODULE — `02_SPECIALIST_LLM_AGENTS.md`

# 21 Engineering Specialists and Nebius Reasoning

**Owner:** adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Scientific design
One executable model can serve 21 specialist roles with distinct system prompts, allowlisted tools, data domains, evidence requirements and bounded conversation depth. Twenty-one roles **do not mean 21 trained models** or 21 calls per specimen. Evaluate 1–7 relevant roles, then an explicit scientific comparator with single full-context LLM.

## Existing role registry
`qualityrelay17/roles.py` reuses and preserves the 21 roles from the user's 14.2 artifact. Each role includes `name`, `domain`, `tools`, `required_sources`. This copy is original team-owned code, not a third-party model checkpoint. New work: role selection should be driven by verified missing evidence, tool usefulness and budget, not number of agents.

## Allowed tool loop
1. Resolve legitimate caller identity and its role.
2. Inject only summarized authorized evidence with immutable event IDs, source origin and age.
3. Ask LLM for a tool call from the advertised role allowlist.
4. Validate role *again on server*; reject unrecognized tools or hallucinated IDs.
5. Execute deterministic tool; sanitize result; append tool-call response.
6. Iterate under max tool calls/latency/token spend; require a structured, grounded recommendation.
7. `safe_mesh` determines HOLD/PASS_REVIEW independently from LLM prose.
8. Never give LLM servo GPIO, factory-write APIs or operator approval credentials.

## Security and evaluation
Use prompt-injection test documents, model disagreements, missing evidence, forged event IDs, permission boundary crossing, wrong CAD revision and timeouts. Measure unsupported claims, evidence recall, distinct actionable suggestions, tool validity and spend per specimen. Include **no LLM** rules-only baseline and **single LLM** baseline. If LLM contributes no measurable lift, it should not gate production.

## Nebius integration
Official API: `https://api.tokenfactory.nebius.com/v1/`; select model from your own live `/v1/models` catalog. `nebius.py` contains an opt-in real model adapter. No live credential has been supplied or called here. Event Nebius Scientific AI notebook, shared H100, and Token Factory are separate resources; verify entitlements separately. Never log API keys.

## Acceptance
- All 21 roles have tool ACL and explicit needed sources.
- Disabled/offline LLM yields a safe status rather than imaginary reasoning.
- Multiple agents do not increase confidence by voting on a duplicated image.



---

## MODULE — `03_DUAL_VISION_AND_CAD.md`

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



---

## MODULE — `04_SCIENTIFIC_ENGINE_VDER_CAIR.md`

# Scientific Engine: Bayesian, V-DER, CAIR, EWMA

**Owner:** Bakdaulet  
**Status:** research design + partial reference implementation; see status below.

## Definitions
`H`: hidden defect/process hypothesis. `E`: current provenance-constrained evidence. `a`: possible next inspection action (photo recapture, Pi angle change, caliper, CAD review, human). `d`: disposition. `L(d,H)`: asymmetric loss, with unsafe releases costing more than unnecessary HOLD.

### Expected-loss decision inspection
Select `argmin_a [ cost(a) + E_{y | E,a} min_d E_{H|E,y,a} L(d,H) ]`, including NO_ACTION. Enforce latency and inspection budgets; if model likelihoods are uncalibrated, do not pretend this formula yields optimal physical decisions. Compare against entropy-based Information Gain and fixed measurement priority. Our `vder.py` is the *existing* Bayesian value-of-information core written as an educational implementation, not a proven mathematical discovery.

## Additional scientific core
- EWMA/SPC process drift (use frozen calibration mean/sigma; do not fit only five live points).
- Monte Carlo probability of W−T under local acceptance truncation; independence/correlation assumptions must be tested.
- Fault hypotheses stable/slot shift/tab shift/both shift; posteriors updated only from allowed current evidence; missing-source likelihood absent, never imputed without separate model.
- Calibration of probabilities by Brier score, reliability curves, group-wise holdout and sensitivity to incorrect assumptions.
- CAIR: choose next camera pose/lighting vs caliper retake by calibrated *decision value*, explicitly accounting for time cost.
- Subgroup checks for low contrast, reflective surfaces, lot change, printer change and network outage.

## Experimental failure modes
Rare unsafe passes cause wide confidence intervals; ordinary accuracy hides safety errors. A cautious always-HOLD baseline may attain zero unsafe PASS but zero throughput. Therefore predefine BOTH unsafe PASS and released-good throughput at equal budget. Use paired runs and confidence intervals; no claim without experiments.

## Current code
`vder.py` exact binary pedagogical VOI. `factory.py` replayable seeded production scenarios. The 5.0 archive preserves the original Monte Carlo/EWMA architecture but those complete calibrated implementations are not present in the NEW 17 reference runtime.

## Acceptance
- All assumptions/version IDs saved in run manifest.
- Retake/no-action candidates explicit.
- Oracle and centralized full-information are separately labeled upper-bound comparators, not strawman baselines.



---

## MODULE — `05_DIGITAL_FACTORY_TWIN.md`

# Multi-line Digital Factory / Discrete Event Simulation

**Owner:** Bakdaulet + 4th engineer  
**Status:** research design + partial reference implementation; see status below.

## Factory ontology
Workcell, machine, operator, supplier, lot, specimen, geometry revision, production step, metrology, vision, assembly, sorter, rework station, quarantine, quality plan, financial ledger. Each station has service time, capacity, maintenance mode, input buffer, output buffer, variability distribution and failure events.

## Three simulation fidelities
**Level 0 (implemented):** seeded specimen stream and multiple inspection policies in `factory.py`. Includes distribution shifts, two imperfect camera observations, partial network availability, and physical-safe true outcomes. Fast CPU benchmark. No conveyor physics or real visual imagery.
**Level 1 (integration recipe):** SimPy/FactorySimPy discrete event simulation of buffers, machines, queue length, cycle times, blocked/starved stations, WIP, scrapping and inspection routing. Each simulation event has virtual timestamp and origin SIMULATED.
**Level 2 (NVIDIA plugin):** Isaac Sim/Omniverse 3D workcells, photoreal sensors, mechanical chute geometry, and Replicator domain randomization. Needs an RTX GPU with RT cores; Nebius H100 alone cannot render Isaac Sim. Scene artifacts in USD and source CAD tracked by revision.

## Multi-factory extension
Scale by independent suppliers with separate data ownership and schema contracts. Simulate communication asymmetry and loss of coordinator, sample heterogeneous measurement precision, drift and supply delay. Do not claim simulated site is a certified digital twin without calibrated, continually updated physical mapping and VVUQ.

## Verification and Validation
Verify discrete event conservation (input = good+hold+scrap+WIP), determinism under seeded replay, no impossible negative WIP or duplicate unit IDs. Validate each service-time and defect distribution against REAL logs if a factory agrees to pilot. Disclose simulation-to-real gap and confidence intervals.

## GitHub reuse
https://github.com/simpx/simpy ; https://github.com/FactorySimPy/FactorySimPy ; https://github.com/isaac-sim/IsaacSim ; https://github.com/NVIDIA/warp ; https://github.com/newton-physics/newton . Their licenses and additional assets must be checked at version pinning time.

## Acceptance
- One physical Slot/Tab production story mirrors one simulated line.
- At least 3 seeded fault scenarios and common random numbers across policy baselines.
- Report inventory, WIP, cycle time and throughput with all origin labels.



---

## MODULE — `06_OPTIMIZATION_AND_ECONOMICS.md`

# cuOpt / Smart Matching / Cost Intelligence

**Owner:** Bakdaulet + adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Decision variables
- Pair accepted Slot lot samples with compatible Tab lot samples.
- Select which parts undergo manual metrology, photo retake, expert review or quarantine.
- Schedule production with queue/shift/tool/throughput constraints and cost budgets.
- Budget for cloud GPU, caliper labor, quality escapes and rework.

## Safety-constrained objective
Minimize `inspection + rework + internal scrap + expected escaped defects + downtime + operational deployment` subject to verified quality and capacity constraints. Unsafe PASS must also be reported as a **separate** constraint/metric; risk-cost alone may create unacceptable tradeoffs. If evidence is insufficient, optimizing production must not override HOLD.

## Code and performance
`matching.py` implements exact subset dynamic programming for <=12 pairs as reproducible CPU baseline. Larger scale: compare OR-Tools CPU MIP/CP-SAT and NVIDIA cuOpt GPU (supported MIP limitations; do not assume globally optimal proof). `economics.py` ensures one terminal outcome per specimen to avoid double counting. `factory.py` compares only simulated/assumed cost, not actual savings.

## Measurement protocol
Use paired same-lot runs. Record cost assumptions for each organization; label assumed vs observed costs. Report net incremental savings after GPU bills, inference fees, integration and monitoring, not just reduced scrap. Include sensitivity analysis for defect escape severity and HOLD costs.

## Licensing and infrastructure
https://github.com/NVIDIA/cuopt (Apache 2.0, NVIDIA GPU required); https://github.com/google/or-tools (verify exact license/version before integration). Do not bundle their source in this ZIP; use dependency documentation and reproducible install manifests.

## Acceptance
- Never route unsafe unit to PASS because it reduces cost.
- Baseline OR-Tools/cuOpt use same exact objective and constraints.
- Distinguish measured savings, simulated savings and assumptions in all charts.



---

## MODULE — `07_PHYSICAL_SORTER_AND_ASSURANCE.md`

# Assured Physical Sorting and Robot State Machine

**Owner:** HyorinmaruK + adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Hardware boundary
ESP32-S3 board, servo-driven sorting gate, power isolation, chute sensor/beam-break (if available). Servo moves sorting gate, NEVER digital-caliper jaws. Physical routing occurs only after an authenticated bounded request and operator review. A physical STOP switch is required before an actual production pilot.

## Non-negotiable action-state machine
`PROPOSED -> REVIEWED -> AUTHORIZED -> STAGED -> COMMAND_SENT -> SENSOR_ACK -> VERIFIED` (or `HOLD/FAULT/TIMEOUT`). A unit is only counted as physically routed after unique sensor confirmation. Separate inspected parts, confirmed defective parts and physically rejected parts. Match IDs and ensure idempotent replay. No repeated command on retry without observing physical state.

## Current reference
`actuation.py` implements only approval, stage and acknowledgement bookkeeping. It sends ZERO GPIO/servo messages; do not present it as live robot integration. ESP32 firmware and secure transport remain TODO. An LLM is never allowed to call actuation tool or assign final hardware PASS.

## Experiments
Sensor disappears, gate moves partially, wrong bin, duplicate acknowledgment, staged action without authority, unplugged network, loss of power after gate movement, counter drift. Use external independent observation to score route success and reconcile inventory.

## Acceptance
- HOLD default and no unattended physical PASS.
- A single specimen cannot increment two terminal bin counters.
- Hardware operation entirely behind separate authenticated authorization service.



---

## MODULE — `08_NVIDIA_EIGHT_TECH_ADAPTERS.md`

# NVIDIA Eight-Technology Integration Plan

**Owner:** Team (specialized owners)  
**Status:** research design + partial reference implementation; see status below.

## Integration matrix
| NVIDIA technology | Input / output contract | Deployment target | What actually gets built |
|---|---|---|---|
| Isaac Sim + Omniverse | CAD/URDF -> USD stage -> photoreal observations | RTX RT-core GPU | 3D factory + camera + sorter scene plugin |
| Omniverse Replicator | USD scene + randomization -> labeled images/masks | same RTX host | train/test synthetic defect generation and metadata |
| cuOpt | mathematical assignment/scheduling -> feasible plan | CUDA GPU | matching and cost optimization; CPU fallback |
| PhysicsNeMo | real FEA/simulation fields -> surrogate prediction | NVIDIA CUDA GPU | phase-2 uncertainty-aware, never unvalidated PLA stress oracle |
| DeepStream | camera/RTSP -> tracked events + track ID | NVIDIA GPU/Jetson | multi-stream tracking; not Pi Hailo runtime |
| Cosmos | scene conditions -> synthetic image/video/world model outputs | compatible NVIDIA GPU | robustness augmentation only; not metrology ground truth |
| Metropolis VSS | video clips + events -> search/verified alerts | substantial NVIDIA GPU service | query manufacturing incidents by specimen and time |
| Warp + Newton | geometry/forces -> sorter collision/contact simulation | supported GPU | gate mechanics and actuator stress/test adapter |

## Avoid duplicate integrations
Isaac Sim already contains Replicator; Warp powers Newton; DeepStream integrates well with VSS. Define adapter interface rather than launching eight independent GPU servers. CPU-only reproducible science MUST remain possible if GPU resources are exhausted.

## GPU reality
NVIDIA shared H100 can train many CV/physics models but cannot serve RTX ray tracing demanded by Isaac Sim. Brev offers GPU options, but sponsor credit is finite; check actual available instance GPU and driver against ISAAC compatibility checker. A Pi Hailo-8L requires model conversion (HEF), not CUDA.

## License reality
cuOpt and PhysicsNeMo have Apache-2.0 source; NVIDIA Warp Apache-2.0; Cosmos OpenMDW-1.1 special terms; Isaac Sim source Apache-2.0, additional Kit/assets licensing and redistribution restrictions; DeepStream source Apache-2.0, documentation CC BY 4.0, NVIDIA binaries use separate SDK EULA; VSS blueprint code Apache-2.0 with asset/third-party exceptions. Model checkpoints and datasets can have different licenses. See `docs/engineering/THIRD_PARTY_REUSE.md`.

## Minimum acceptance per plugin
`availability()`, `health()`, `resource_budget()`, `run(config,run_id)`, `status`, `output_provenance`, `fallback`, exact software version, explicit not-run result if unavailable. Never silently substitute a mock while showing branded NVIDIA inference.



---

## MODULE — `09_NEBIUS_RESEARCH_CLOUD.md`

# Nebius LLM, Scientific AI, GPU

**Owner:** adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Resource classes
1. Scientific AI platform (team-scoped notebook/agent+ hosted scientific models): access assigned by event credentials, one request/team.
2. Nebius Cloud Academy 16 H100 GPU **shared across entire event**, with possible queues.
3. Nebius Token Factory OpenAI-compatible inference API: model access depends on the team's provisioned token.
Do NOT equate access to one with access to all three.

## Inference contract
Model ID loaded from authenticated live `/v1/models`, API key from env, 15-second timeout, bounded rounds, role-specific tool schema, test recorded costs. Never store keys or prompts containing raw proprietary factory files in the artifact. Model text never accepted as metrology, financial truth or authorization.

## Reproducibility
Save model ID, prompt/schema hash, temperature, random seed where supported, token usage and exact evidence set. When LLM unavailable, use deterministic safety rule fallback. Compare no LLM vs single LLM vs 2-7 specialists vs 21 roles under budget. Track hallucination and tool use validity as primary safety metrics.

## Current code
`nebius.py` provides opt-in adapter; not called using actual credentials here. The user's earlier 14.2 package contains a richer legacy LLM tool loop; align its tests/contracts before replacing, and verify live 2026 model API differences.

## Acceptance
At least one authorized real inference with recorded model/version and exact evidence, and an outage demonstration preserving HOLD behavior before claiming deployed integration.



---

## MODULE — `10_SECURITY_VVUQ_AND_RESEARCH.md`

# Assurance, Calibration, Scientific Validation and Security

**Owner:** Bakdaulet + 4th engineer  
**Status:** research design + partial reference implementation; see status below.

## Core assurance chain
Evidence acquisition -> identity/provenance -> calibration/quality -> authorization -> diagnosis/inspection proposal -> independent safety gate -> human approval -> physical actuation -> independent route acknowledgement -> evidence-based audit. Never omit a state in production claims.

## VVUQ principles
Verification: tests show the code implements its declared mathematics and contracts.
Validation: independent physical measurements show it addresses the real manufacturing problem.
Uncertainty quantification: image reliability, metrology repeatability, process prior drift, model class uncertainty, data shift and confidence intervals.

## Registered comparisons
- Phone-only, Pi-only, caliper-only, photo/photo-only, CAD/photo-only.
- Rule-based conservative multimodal fusion; Bayesian fusion with correlation; SAFE-MESH with V-DER; single LLM; 21-role planned system.
- Centralized full-information oracle (clearly upper bound); centralized restricted-information parity; decentralized.
- With and without each component: lineage, minority dissent, active inspection, dual camera, human gate, network outage.

## Key metrics
False PASS with exact interval; false HOLD; good throughput; inspection per part; 95% calibration CI; expected cost and service levels; attack success; physical route mismatch; replay duplicates; wall-clock latency. Highlight that zero observed unsafe PASS on 20 parts does NOT prove low true unsafe-pass probability.

## Negative controls
No camera model trained: baseline must not be mislabeled as NVIDIA. No Pi device: Pi process mocked must be labeled TEST_FIXTURE. Synthetic images must not count as real images; screenshot of video is not independent measurement. Hidden test lot/source split, no leakage from same part train->test.

## Novelty claim discipline
The user team proposes integration of correlation-aware evidence + active decision-focused inspection + assured intervention across decentralized factory sensors. The methods exist individually; our relative contribution is unproven until a comparable study shows a reproducible new tradeoff. Follow the 2026 235-study EAA digital twin review and HiddenBench multiagent failures as motivation, not as proof of novelty.



---

## MODULE — `11_SITE_AND_DATA_CONTRACTS.md`

# One Website, Separate Research Services

**Owner:** adilnurgg + HyorinmaruK  
**Status:** research design + partial reference implementation; see status below.

## Website tabs
Factory Overview; Phone Scan; Pi Station; CAD Compare; Metrology; Agent Evidence Room; Simulation Lab; Smart Matching; Economics & ROI; Scientific Benchmark; Audit; Settings & Permissions.

## Boundaries
Frontend (Next.js or static HTML) is NOT the source of truth. API gateway authenticates, rate limits, tags source origins. The station-specific local DBs and offline queues persist without website. FastAPI can expose read-only summaries. Separate actuation service needs human auth and physical interlocks; no web browser event directly moves servo.

## Core contracts
`POST /evidence` signed bounded event; `GET /specimens/{id}/review` safely summarized decision; `POST /inspections/rank` VOI candidates; `POST /simulations` seeded job; `GET /runs/{id}` manifest; `POST /actions/{id}/approve` privileged human only; `POST /sorter/acks` hardware route confirmation; `GET /audit`. The NEW demo API only implements `/health`, `/demo`, `/simulation/compare`, `/research/claims` — no claim other endpoints exist.

## Visualization integrity
Show badge physical/synthetic/test fixture; upstream and downstream event IDs; when camera inference ran on CPU baseline vs trained NVIDIA; last calibration timestamp; actual model; staff review pending. If data missing show UNKNOWN/HOLD rather than zero risk. Physics/financial results show units and confidence intervals, no invented precision.

## Deployment
Only adilnurgg and HyorinmaruK own Google Cloud. The ScienceClaw GCP accounts are temporary, max two per team and auto-delete event Sunday night (per supplied PDF). Persist original source and run manifests to GitHub before account expiry. Production needs TLS, authorization, secure secrets, tenancy isolation and retention policies; the demo API alone is not safe for Internet exposure.



---

## MODULE — `12_MULTI_FACTORY_INTEROPERABILITY.md`

# Industrial Data, Supplier Boundaries, Digital Thread

**Owner:** adilnurgg + 4th engineer  
**Status:** research design + partial reference implementation; see status below.

## Scale path
Factory -> line -> workcell -> station -> event -> specimen -> lot -> CAD revision. Integrate CAD/STL, CSV caliper records, QMS results, PLC/MES/ERP read-only adapters, RTSP camera events, and OPC UA/MQTT where specifically authorized. Keep event identifiers stable across systems.

## Contract governance
Document schema version, decimal units, timezone, origin, privacy labels and nominal tolerances per part revision. Cross-factory supplier agents share only approved quality summary; no raw vendor bill of materials, private camera frames or fabrication recipes without an agreement. Support temporal view of design -> plan -> execution -> inspection.

## Fallback and rollout
Offline local inspection must continue in bounded HOLD mode; factory federation is optional. Site integration begins with read-only shadow mode, followed by test-only approvals and then tightly supervised action. Do not market as plug-and-play into unknown safety-critical manufacturing lines.

## Validation
Test wrong-unit conversions, stale CAD rev, same serial from two suppliers, duplicated dispatch, lost reconciliation events, cross-tenant access, timezone drift and incompatible ontology. Track integration labor as part of ROI.



# 6. Engineering, GPU and GitHub reuse plans


---

## ENGINEERING — `GPU_AND_SPONSOR_EXECUTION_PLAN.md`

# GPU and sponsor execution plan — QualityRelay 17.0

**Team context:** User reports relevant hackathon accounts exist. **Account existence ≠ redeemed credits ≠ running GPU instance.** Nothing in this package tests private accounts, credentials, quotas, invite status, credit balances or instance availability. Confirm individually from authorized consoles. Never put token/API keys or event-only links in Git.

## Compute split: use the RIGHT GPU for the job

| Resource | Allocated in hackathon PDF | Workloads | Hard restrictions |
|---|---|---|---|
| NVIDIA Brev | $150 credit per registered participant; 3 participants could hold $450 across separate accounts | RT-capable RTX instance for Isaac Sim/Replicator; alternatively CUDA model training; cuOpt | Credits **not** automatically pooled into one account. GPU selection, availability, hourly pricing must be checked before boot. Stop idle instance. |
| Nebius Cloud AI | Shared event pool of 16 H100 GPUs; recommendation <=1 GPU/team/job | Vision training, batch LLM experiments, physics ML (if validated data), scientific benchmark | All teams share; queue possible, no guaranteed exclusive H100. H100 does NOT meet Isaac Sim RT requirement. |
| NVIDIA DGX Spark / Dell GB10 | Five on-site units, permission via event NVIDIA channel | Local experiments and eligible small-model inference | Access not guaranteed; model and driver compatibility must be verified. |
| Nebius Scientific AI | Team credential set, scientific models and research tools | Optional scientific inference/experimentation | One request per team, model suitability separate from claims of industrial accuracy. |
| Claude API | $100 credits/registered participant | Alternate LLM baseline | Event-only claim instructions; not a Claude subscription. |
| OpenAI API | $50 grant under stated redemption rules | Alternate single agent baseline | API credits, not ChatGPT subscription. |
| Google Cloud | Up to two temporary accounts per team | Site hosting/back-end, CPU event simulations, object store | **Only adilnurgg and HyorinmaruK own Google Cloud tasks.** Temporary accounts expire after event. |

## Compute topologies

1. **Local/CPU reproducible:** web + FastAPI + numpy/scipy + OpenCV baseline + geometry renderer + seeded factory simulator. This MUST continue if GPUs or APIs are unavailable.
2. **Nebius H100:** controlled training of a candidate anomaly detector, benchmark runs, optional science tool. Export versioned ONNX/weights only if license and compatibility verified. Host at server-side; do not leak keys to phone browser.
3. **Brev RTX:** USD scene, Isaac Sim, Replicator, randomization for camera pose, lighting and defect geometry. Verify exact GPU with Isaac Sim Compatibility Checker; require RT Cores and appropriate RAM/VRAM/driver.
4. **Brev/H100 compatible CUDA:** NVIDIA cuOpt installation for GPU scheduling/matching. Compare with CPU exact DP (small problems) and OR-Tools on identical objective/constraints. Avoid claiming cuOpt proves MIP optimality; current MIP support is evolving.
5. **Edge Pi + Hailo-8L:** independently deploy compatible compiled model; Hailo is not CUDA and not an NVIDIA GPU; never assume a CUDA checkpoint runs there without conversion/validation.

## First 30-minute account check (owners)

- `adilnurgg`: verify Nebius tenant invite and H100 job entitlement, quota, API calls and permitted models. Use the user-registered account; never paste credentials into public issues.
- `HyorinmaruK`: verify NVIDIA Brev credits and RTX-compatible GPU availability; use hardware photos and Pi camera as offline demo fallback; own any Google Cloud front-end deployment.
- `Bakdaulet`: design exact training/validation and 30-seed scientific benchmark; no Google Cloud administration. GPU runs are research tasks, not GCP chores.

## Resource ledger

For EVERY run, record `run_id, provider, instance_type, GPU_model, gpu_count, driver, CUDA, docker_digest, tool_version, price_per_hour, start/end, total_spend, dataset_hash, model_hash, seed, git_commit, source_origin`. Show model unavailability rather than a fake result.

## Infrastructure cost in ROI

`operational_savings = avoided_scrap + avoided_rework + avoided_inspections + avoided_downtime - additional_review - GPU/API - cloud_storage - hardware_amortization - false_holds - integration_cost`. Costs must use user-supplied factory assumptions or measured values. Never publish estimated cloud credits as realized factory savings.

## Current product documentation (recheck before install)

- Isaac Sim system requirements: https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html (H100/A100 no RT Cores, unsupported)
- NVIDIA cuOpt: https://github.com/NVIDIA/cuopt (CUDA 12/13, Linux; verify selected versions)
- Brev: https://brev.nvidia.com/
- NVIDIA Cosmos: https://github.com/NVIDIA/cosmos (OpenMDW-1.1 in repository; license at installed revision)

## ScienceClaw organizer-only PDFs

Resource amounts are extracted from user-supplied `PDF - ScienceClaw Compute.pdf` and `PDF - Hardware Summary.pdf`. Special redemption links and individual login details are deliberately NOT copied into this public package. Hardware is limited, first-come-first-served: 15 ESP32-S3, 10 ESP32-S3 cameras, 5 Pi5 + Hailo-8L, 5 Pi cameras, 5 electronics bundles, etc. Availability not guaranteed.


---

## ENGINEERING — `THIRD_PARTY_REUSE.md`

# External GitHub projects, license and deployment review (30 October 2026)

**Principle:** This ZIP does **not** repackage third-party repositories, commercial weights, datasets, NVIDIA binaries or credentials. We provide verified upstream links, interface contracts, application points and install commands. Clone into your own environment and pin a reviewed commit. Licensing summaries are not legal advice; verify actual installed artifact and its transitive dependencies.

| Repo / source | License context | QualityRelay adapter | Priority / restrictions |
|---|---|---|---|
| [OpenCV](https://github.com/opencv/opencv) | Apache-2.0 for >=4.5.0 ([official](https://opencv.org/LICENSE/)) | Camera calibration, alignment, contours, photo/photo | P0; no self-calibrated mm claims |
| [Trimesh](https://github.com/mikedh/trimesh) | MIT ([license](https://github.com/mikedh/trimesh/blob/main/LICENSE.md)) | STL load, 2D projections, geometry metadata | P0; project STLs under correct view |
| [CadQuery](https://github.com/CadQuery/cadquery) | Apache-2.0 ([README](https://github.com/CadQuery/cadquery)) | Native parametric 3D parts | P1; OCCT deps verify |
| [SimPy](https://github.com/simpx/simpy) | MIT ([license](https://github.com/simpx/simpy/blob/master/LICENSE.rst)) | Discrete-event factory scheduling | P0/P1; package version review |
| [FactorySimPy](https://github.com/FactorySimPy/FactorySimPy) | MIT ([README](https://github.com/FactorySimPy/FactorySimPy)) | Machines, buffers, conveyors, splitters | P1; small project, verify maintenance |
| [Anomalib](https://github.com/open-edge-platform/anomalib) | Apache-2.0 ([license](https://github.com/open-edge-platform/anomalib/blob/main/LICENSE)) | PatchCore/EfficientAD industrial anomaly baseline | P1; model weights and datasets separately |
| [OR-Tools](https://github.com/google/or-tools) | Verify pinned source/build license | CPU matching/scheduling baseline | P1; hard to compare GPU without same model |
| [Hailo Model Zoo](https://github.com/hailo-ai/hailo_model_zoo) | Verify source, model & hardware toolchain separately | Hailo-8L independent local vision | P1; compatible branch/HEF only |
| [Nebius Cookbook](https://github.com/nebius/token-factory-cookbook) | Verify individual recipe license | LLM tool-calling client and live model catalog | P0; credits and secrets required |
| [NVIDIA TAO](https://github.com/NVIDIA-TAO) | Toolkit source Apache-2.0; pretrained NGC weights separate | Train image comparison/anomaly models | P1; verified weights, reproducible split |
| [NVIDIA cuOpt](https://github.com/NVIDIA/cuopt) | Apache-2.0 ([official](https://www.nvidia.com/en-us/ai-data-science/products/cuopt/get-started/)) | GPU decision optimization | P1; supported CUDA GPU; MIP optimal proof not guaranteed |
| [Isaac Sim](https://github.com/isaac-sim/IsaacSim) | Apache-2.0 source; additional Omniverse Kit/assets separate terms | 3D robot/sorter/camera scene | P1; **RTX RT core GPU**, NOT H100; redistribution caveat |
| [Replicator](https://developer.nvidia.com/isaac/sim) | Isaac/Omniverse relevant terms | Synthetic labeled defect/lighting images | P1; avoid correlated synthetic leakage |
| [NVIDIA Warp](https://github.com/NVIDIA/warp) | Apache-2.0 ([README](https://github.com/NVIDIA/warp)) | Physical collision/sorter model | P2; choose validated solver settings |
| [Newton Physics](https://github.com/newton-physics/newton) | Verify pinned repo and assets | Robotics contact/actuation | P2; not another production certifier |
| [PhysicsNeMo](https://github.com/NVIDIA/physicsnemo) | Apache-2.0 ([README](https://github.com/NVIDIA/physicsnemo)) | Physics ML surrogate and uncertainty | P2; requires validated FE ground truth |
| [DeepStream](https://github.com/NVIDIA/DeepStream) | Source Apache-2.0; docs CC-BY-4.0; binaries separate SDK EULA | NVIDIA GPU multi-stream tracking | P2; Pi/Hailo is **not** DeepStream host |
| [NVIDIA Cosmos](https://github.com/NVIDIA/cosmos) | OpenMDW-1.1 special source/weight terms | Robustness images/videos | P2; never use as measurement truth |
| [VSS Blueprint](https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization) | Repo Apache-2.0 with 3rd-party & asset exceptions | Video search, incident explanation | P2; large GPU/messaging footprint |

## Robust integration workflow
1. Open the upstream repo and `LICENSE`, model card, and release notes on installation day.
2. Record commit SHA, package version, Python/CUDA driver, hardware, license, download URL in `third_party.lock.yaml` (template below).
3. Isolate external packages as Docker images/optional extras. Do not let one NVIDIA library constrain the CPU scientific core.
4. Store third-party license notices with shipped **code**, not automatically copy all licenses for repos that were never bundled.
5. Compare trained weights on a dataset where part IDs/lots do not appear across train/test.
6. If license, GPU, time or access is blocked, fail to `UNAVAILABLE` and retain truthful baseline.

## Example dependency lock record
```yaml
component: nvidia-cuopt
upstream: https://github.com/NVIDIA/cuopt
revision: TO_BE_PINNED_FROM_VERIFIED_RELEASE
license_reviewed_by: TODO
license_date: TODO
hardware_compatibility: TODO
installed: false
external_artifact_included_in_zip: false
```

## Datasets
[MVTec AD](https://www.mvtec.com/research-teaching/datasets/mvtec-ad) has a **CC BY-NC-SA 4.0** noncommercial restriction. Do not integrate its images into a commercial factory SaaS without separate authorization. Use independently captured 3D printed parts and self-authored CAD for proprietary training. Public benchmarks can support noncommercial academic comparisons under their terms.


---

## ENGINEERING — `INTEGRATION_HANDOFF_CONTRACTS.md`

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


---

## ENGINEERING — `TEAM_OWNERSHIP_AND_GITHUB.md`

# Team-of-three, optional fourth participant, and GitHub integration

## Owners (user-approved)
| Account | Module owner | Branch areas | Gates |
|---|---|---|---|
| **Bakdaulet-omeraiuly** | Research, scientific engine V-DER/CAIR/EWMA, calibration, NVIDIA vision research, benchmarking, model hypotheses, economic experiments | `qualityrelay17/{vder,benchmark,factory,digital_line,vision,matching,economics}.py`, `docs/research` | Claims + data validation; **NO Google Cloud responsibility** |
| **adilnurgg** | Agent backend, Nebius, Google Cloud API/infrastructure, evidence mesh, security, identity, authorization, actuation interface | `qualityrelay17/{contracts,ledger,safe_mesh,nebius,agent_tools,api}.py`, `schemas`, cloud | API reviews and access controls |
| **HyorinmaruK** (mechanical engineer) | Mechanical CAD/STL, print specimens, two cameras/lighting, physical validation, sorter, site UX, **Google Cloud deployment**, presentation | `cad`, `web`, `docs/architectures/03`, `07`, physical test | Physical proof report and final slides |
| **Fourth optional teammate** | Independent QA/reliability, queue simulation, multi-factory connector, external repo integration, CI; no overwrite on current owners | `tests`, `docs/research/EXPERIMENT_PROTOCOL.md`, adapters | No merging safety-critical code alone |

## GitHub layout
Use one monorepo; keep current upstream repos separate (`/vendor` should contain no unreviewed copied code):
```
qualityrelay/
  qualityrelay17/       # our own new algorithm, simulation, agent & API code
  web/                  # single dashboard, phone camera web inputs
  docs/architectures/   # 12 module-specific plans
  docs/research/        # hypotheses and transparent benchmark
  schemas/              # event schema and API contracts
  tests/                # contract/failure/provenance tests
  legacy/               # original owned archives; exclude if public if privacy unclear
```

## Branches and review
`main` protected, 1 review for ordinary PR, 2 reviews for actuation/auth/safety code changes. Branches `science/vder-calibration`, `backend/evidence-mesh`, `mechanical/dual-camera-cad`, `qa/regression`. CI: Python unit tests, static schema checks, dependency vulnerability scan, and generated manifest diff. A team member cannot merge their own change to release PASS authority alone.

## Shared interface checklist
`event_id`, `specimen_id`, `lot_id`, `station_id`, `source_root`, `observed_at`, `origin`, `calibration_id`, `model_version`, `signature`, `parent_source_roots`, `cad_revision`, `operator_verification`, `uncertainty` standardized across services. UI only shows verified provenance. Every physically confirmed route recorded by separate unique sensor ACK.

## Deployment
Two Google Cloud accounts maximum for team as disclosed in event-provided resource deck; GCP provisioning managed solely by adilnurgg and HyorinmaruK. Bakdaulet can submit reproducible benchmark outputs, no GCP setup obligations. Nebius Scientific AI: one application per team. Store authorized keys only as secrets. Sponsor accounts may expire after weekend; export GitHub source and measured run manifests before deletion.

## Integration order
1. Merge contracts and unit tests.
2. Real phone capture, reference compare and manual caliper capture.
3. CAD silhouette and Pi independent capture.
4. Two separately authorized station services; conflict HOLD demonstrated.
5. Physical sorter staging+ACK, only if verified operator control is possible.
6. Factory simulation + benchmarks + ROI, and public demo.
7. NVIDIA/RTX plugins and live Nebius with explicit entitlement/credit gates.
8. Physical validation and slides chaired by HyorinmaruK; Bakdaulet signs statistical claims.


---

## ENGINEERING — `STATUS_AND_GATES.md`

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
| Evidence signatures & ACL | runnable SQLite + HMAC reference | PKI, transport TLS, real station network, queue replay |
| Scientific VOI | binary V-DER reference | likelihood calibration, new model claims not proven |
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


---

## ENGINEERING — `HACKATHON_RESOURCES.md`

# ScienceClaw sponsor hardware & compute mapping

Source: uploaded `PDF - ScienceClaw Compute.pdf` (14 pages) and `PDF - Hardware Summary.pdf` (1 page), as supplied by the user. All availability is subject to event rules/actual provision; don't infer credits were claimed.

| Grant / hardware | Document value / restriction | Intended workload |
|---|---|---|
| NVIDIA Brev | $150 GPU credits **per registered teammate**; 3 teammates => $450 potential total | NVIDIA vision training/cuOpt/compatible RTX Isaac host |
| Nebius Scientific AI Platform | ONE team access credential request, 65 scientific models mentioned | Research agent notebook; not required to run safe deterministic QA |
| Nebius H100 | 16 H100 **shared event-wide**, queued capacity | Scientific training/simulation, no RTX Isaac Sim rendering |
| Claude API | $100 each; event-specific sign-up link must not be publicly shared | Comparative LLM baseline, optional |
| OpenAI API | $50 grant via event registration | Additional single-model baseline, optional |
| Google AI Studio | Tier-1 Gemini API access | Baseline agent, model comparison; entitled key only |
| Google Cloud | temporary compute: 32 vCPUs per account; up to 2 accounts per team; expires Sunday night | Site backend, archived reproducible runs |
| On-site DGX Spark GB10 | 5 systems, request via organizers/Discord | Model experiments if reservation granted |
| Raspberry Pi 5 + Hailo-8L | 5 sets in shared pool | independent Pi visual evidence |
| Raspberry Pi camera | 5 in shared pool | capture Pi station image |
| ESP32-S3 camera boards | 10 in shared pool | alternative edge camera station |
| ESP32-S3 boards | 15 in shared pool | optional servo control |
| Electronics kits, breadboards, jumper wires | very limited | servo, sensor and route confirmation |
| 3D printers | available on site in limited quantity | user-authored slot/tab components |

**Hardware fallback:** Phone camera + webcam OCR (manual caliper confirmation) are enough for an honest dual-mode imaging prototype if Pi kit unavailable; but do NOT claim physically independent Pi evidence until actual Pi camera captures it. Lack of sorter hardware => stage-only simulation.

**Security:** event-specific sign-up URLs and keys should not be shipped or exposed in this ZIP. Ask sponsor staff for help if links are lost. The archive includes no private credentials.


# 7. Research sources and falsifiable experiment program


---

## RESEARCH — `PRIOR_ART_AND_RESEARCH_QUESTIONS.md`

# Scientific prior art, precise gap and proposed tests

**Do not claim:** we read 10,000 studies, invented Bayesian VOI, invented provenance/signatures, invented multi-agent manufacturing, proved industrial cost savings or attained L5 maturity. Earlier QualityRelay 9.0 includes **a retrieval script**, not a completed 10,000-item screened corpus. The citation list below was individually checked through public research pages; it is not a systematic review.

## Key externally verifiable work
1. Hedberg et al. (2021), [Defining requirements for integrating information between design, manufacturing, and inspection](https://www.nist.gov/publications/defining-requirements-integrating-information-between-design-manufacturing-and) — real integration experiment did not fully link all digital-thread information. Relevance: strong factory provenance and CAD revision crosswalking.
2. Frechette, Shao, Pease (2026), [NIST Digital Twins Workshops Summary Report](https://www.nist.gov/publications/digital-twins-workshops-summary-report) — interoperability, VVUQ, cybersecurity, workforce readiness gaps. Relevance: test assumptions, not visual demo alone.
3. Anindya (2026), [From digital shadows to assured intervention](https://link.springer.com/article/10.1186/s44147-026-01295-x) — systematic review of 235 selected manufacturing quality digital twins; no reviewed study integrated a full assured intervention chain. This is a claim about that review's corpus, **not a proof that no systems exist anywhere**.
4. Li, Naito, Shirado (ICML 2026), [Systematic Failures in Collective Reasoning under Distributed Information in Multi-Agent LLMs](https://proceedings.mlr.press/v306/li26ej.html) — HiddenBench: 30.1% distributed vs 80.7% full-context single agent in reported evaluation, showing structured communication failure. These values are NOT QualityRelay performance.
5. [MVTec Anomaly Detection dataset](https://www.mvtec.com/research-teaching/datasets/mvtec-ad) — industrial baseline, >5,000 images, noncommercial/share-alike dataset terms. Relevance: pretrain/testing methodology, not factory-specific acceptance.
6. [ReinAD, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/file/1bdcb065d40203a00bd39831153338bb-Paper-Datasets_and_Benchmarks_Track.pdf) — benchmark real-world distribution shift limitations; check full protocol before borrowing numerical comparisons.
7. [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim/) — simulation/Replicator is existing scientific infrastructure, not a new research invention.
8. [NVIDIA PhysicsNeMo](https://github.com/NVIDIA/physicsnemo) — physics-ML framework; a pretrained surrogate is not validated for our PLA specimens.

## Research gap that we can actually test
Proposed hypothesis: For independently authorized multi-factory camera+CAD+metrology evidence, **provenance-constrained active acquisition plus separately governed physical intervention** improves one or more operational dimensions relative to matched conservative and centralized baselines **without increasing unsafe PASS**. Do not assume improvement just because more agents are added.

## Five falsifiable hypotheses
- H1 **Lineage:** Reused frame or derived CAD/photo result cannot count twice as independent modality. Measure confidence calibration/error vs naive Bayes/voting.
- H2 **Decision action:** V-DER/CAIR reduces excess inspection time at matched unsafe-pass tolerance vs fixed rule / entropy selection.
- H3 **Decentralized governance:** Under random link loss, local station can process bounded safe operations and reconcile correctly after reconnect.
- H4 **Sim-to-real:** Models trained on Replicator/physical photographs maintain performance under held-out new camera angle, printer, filament, and light; quantify failure (not just success).
- H5 **Assured physical action:** Operator-approved state machine + independent bin sensor reduces duplicated/lost sort events vs unverified servo command.

## Comparator matrix
| Variant | Same evidence budget? | Same model and core? | Main question |
|---|---|---|---|
| P0 Conservative rules | Yes | N/A | Can simpler logic achieve same safety? |
| P1 Single full-context model | Yes | Same entitled model | Are specialists needed? |
| P2 Multi-agent naive voting | Yes | Same weights | Does collaboration add value? |
| P3 Centralized all-access baseline | No (oracle), clearly label | Same deterministic math | Upper-bound reference only |
| P4 Centralized matched access | Yes | Same math | Does topology matter? |
| P5 SAFE-MESH no V-DER | Yes | Same math | Does lineage/dissent help? |
| P6 SAFE-MESH + V-DER/CAIR | Yes | Same math | Value of active inspection? |
| P7 + governed physical feedback | Yes | Same math | Does action assurance reduce event mismatch? |

## Primary endpoints
Unsafe PASS probability with Wilson/cluster bootstrap CI; acceptable-unit throughput; inspection $/part; physical route audit mismatch; calibrated Brier score; communication bytes, latency and queue occupancy. Comparisons must be **paired** (same underlying latent defect and camera/noise draws), with pre-registered seeds and thresholds, and a no-benefit/null result reported transparently.

## Formal definitions
- `unsafe_PASS` means physically bad specimen (blind independent ground truth) is authorized as PASS.
- `HOLD` is an uncertainty management decision, not scrap.
- `CONFIRMED_REJECT` needs independent nonconformance or qualified engineer approval.
- `risk` requires assumptions and calibrated posteriors. Softmax scores are not validated probabilities.
- `discovered` requires literature novelty verification, independent results and appropriate publication/review; a named acronym is not discovery.


---

## RESEARCH — `EXPERIMENT_PROTOCOL.md`

# Pre-registerable scientific protocol

## Endpoints and unit of analysis
Unit = unique 3D printed specimen + unique lot. Do not split frames of the SAME specimen between train and test. Primary: unsafe-pass rate under matched good-unit release throughput and inspection budget. Secondary: false HOLD, inspection seconds, cost per good unit, Brier, ECE, claim traceability, physical route mismatch. Include CIs and raw counts.

## Data collection
Print nominal, close-tolerance, tight-risk, visually chipped, stringing, warping samples with unique QR/ID (not identifying human subject). Use CAD revision and physical caliper record; repeated stable gauge checks (at least 10) for within-operator repeatability, plus another operator/instrument if available. Collect phone and Pi images independently with logged lighting, distance and angle, not screenshots of each other. Two ground-truth human assessors adjudicate crack/assembly fit; document disagreement.

## Physically independent ground truth
Blind measurement and actual fit test separate from model predictions. For barely perceptible 0.1mm shift, report measurement uncertainty instead of confidently assigning a label by camera. Distinguish nominal design geometry, printed geometry and observed fitness.

## Synthetic data
Use predetermined controlled hidden variables. Register 30 seeds × 1000 parts quick baseline and, if available, more runs with uncertainty analysis; identical seeds for every model. Vary printer drift, part tolerance distribution, sensor noise, camera correlation, cross-station evidence missingness and physical sorter verification errors. Cost parameters are assumptions until independently measured.

## Safeguards against misleading claims
- A model that holds everything has zero unsafe PASS: therefore also constrain good part release/throughput.
- Negative result must be published. Older 9.0 toy V-DER vs Information Gain differences were near zero; new reference also shows cost disadvantage, not significant improvement.
- HMAC signature does not make sensor evidence true; it only protects envelope integrity under a secret.
- Simulated cost savings are not factory savings. Include GPU cloud cost, human setup and downtime.
- A low-quality photo is `UNUSABLE`, not a 'good' or 'bad' vote.

## Test matrix and experiments
| ID | Stimulus | Expected safe outcome |
|---|---|---|
| E01 | phone clear; Pi suspect; caliper within tolerance | HOLD, explanation includes Pi evidence |
| E02 | Pi offline; old Pi image available | HOLD stale, local station retains operations |
| E03 | same photo duplicated as 2 sensor inputs | do not claim two independent observations |
| E04 | CAD rev incorrect | HOLD and request correct reference |
| E05 | visually normal, oversize tab | HOLD dimensional failure |
| E06 | crack visible, dimension okay | HOLD, expert verification |
| E07 | image blurred | recapture, no defect certainty |
| E08 | classifier OOD lighting and printer | detect distribution shift / abstain |
| E09 | LLM invents event ID | rejected explanation, no actuation |
| E10 | Chief Engineer unavailable | peer-local bounded service continues |
| E11 | servo request without operator | denied, zero hardware command |
| E12 | correct software route, wrong physical bin | discrepancy alert, no false count |
| E13 | two identical sensor ACK IDs | one verified count |
| E14 | false assumption that image is calibrated | hold pending calibration |
| E15 | simulation images mislabeled as real | ingestion rejects or flags mixed provenance |

## Reporting
Create per-run JSON manifest (code commit, model, seed, timestamp, origin, scenario, hyperparameters, cloud/hardware, exact policies, costs) and raw CSV rows, export plots as PNG if needed. Do not overwrite after seeing results; mark preregistered vs exploratory analysis. Run robustness on unseen lot/printer and compare family-wise uncertainties across tests.


# 8. Transparent implementation claims and planned research agent work


---

## PROJECT — `CLAIMS_AND_OPEN_WORK.md`

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
| NVIDIA 8 technologies actively integrated | **NOT CONFIGURED** | 8 explicit stubs, license/resource docs |
| Physical servo sorter | **NOT CONNECTED** | stage/approval/ACK state machine, no GPIO command |
| Physical industrial cost savings | **NOT MEASURED** | assumptions-only simulation economics |
| A new scientific discovery was demonstrated | **NO** | hypotheses not yet supported vs matched conservative rules |
| 10,000 scientific papers screened | **NO** | older retrieval program, not completed corpus |
| Web research demonstration | Implemented local front end | FastAPI + HTML, no credentials needed |

**Publishable result criterion:** preregistered hypotheses, reproducible methods, baselines, independent lot-level physical data, appropriate uncertainty intervals, nontrivial improvement over conservative baseline, evidence of contribution not explained by policy differences, independent review. Inventing a named acronym is not sufficient.


---

## PROJECT — `RESEARCH_AGENT_INSTRUCTIONS.md`

# Coding-agent collaboration rules (Codex, Claude Code, etc.)

## Task scope
Use the checked-in `QUALITYRELAY_17_MASTER_BLUEPRINT.md` as plan. Never claim an external NVIDIA plugin is active based on an adapter stub. Preserve all legacy originals. Open PRs per architecture owner. Do not merge external code without licensing/commit review.

## Safety-first constraints
- No invented measurements, physical experiment results, simulator performance, cost savings, statistical significance or novelty.
- Do not let LLM text actuate hardware, release PASS, set calibrated risk, or overwrite source records.
- Every evidence source has a root capture/instrument ID; derived CAD/photo model output can depend on the same source and is **not** another independent sensor.
- No shadow promotion: phone-mode Pi emulation is TEST_FIXTURE, not physical Hailo inference.
- Any uncertainty => HOLD and request reinspection, never silently green.

## Useful commands
```bash
pip install -r requirements-demo.txt
python -m pytest -q
python -m qualityrelay17.demo
uvicorn qualityrelay17.api:app --host 127.0.0.1 --port 8000
```

## PR acceptance template
- Purpose/research hypothesis
- Owned modules changed
- Traceability to source, external refs and license
- Tests introduced and exact results
- What was actually physically tested
- New assumptions and limitations
- Security/physical action review status
- Reproducible run manifest (commit, seed, model, inputs)


# 9. Source reference and legacy preservation

The original 5.0's 33 files are preserved **byte-identically** in `legacy/ORIGINAL_5_0_33_FILES.zip`. It includes the physical STL specimen concepts, measurement tolerances, schema, 30-hour milestones and original scientific plan. The newest 15.0 original ZIP plus original 7.1–14.2 files are separately preserved in `legacy/` for audit; 5.0 remains the specification baseline, never silently overwritten.

## Prior research and physics references
- NIST 2021 integration requirements: https://www.nist.gov/publications/defining-requirements-integrating-information-between-design-manufacturing-and
- NIST 2026 Digital Twins workshops: https://www.nist.gov/publications/digital-twins-workshops-summary-report
- ICML 2026 multi-agent distributed information failures: https://proceedings.mlr.press/v306/li26ej.html
- 2026 manufacturing QA review, 235 papers: https://link.springer.com/article/10.1186/s44147-026-01295-x
- MVTec dataset license restrictions: https://www.mvtec.com/research-teaching/datasets/mvtec-ad
- NVIDIA Isaac Sim system requirements (no H100): https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html
- NVIDIA cuOpt: https://github.com/NVIDIA/cuopt
- NVIDIA Cosmos source/model license: https://github.com/NVIDIA/cosmos

## User-provided organizer resources
`PDF - ScienceClaw Compute.pdf` and `PDF - Hardware Summary.pdf` describe grants and shared equipment. They are **not shipped** inside the public code ZIP to avoid redistributing event-only access instructions; resource quantities and limitations are paraphrased in `docs/engineering/GPU_AND_SPONSOR_EXECUTION_PLAN.md`. Do not copy event-specific claiming links to public repositories.

## 10,000-paper study clarification
The older 9.0 ZIP contains a bibliographic retrieval **program**. It is not a completed systematic review of 10,000 read and evaluated scientific papers. This release cites the individually checked relevant foundation, and provides an explicit future review protocol; do not fabricate screening counts.

## How to run
```bash
python -m pip install -r requirements-demo.txt
python -m pytest -q
python -m qualityrelay17.demo
uvicorn qualityrelay17.api:app --host 127.0.0.1 --port 8000
```

For a cloud deploy, separate the public demo API from industrial OT networks, implement authentication, TLS, key/identity management, rate limits, user rights and confirmed actuation gateway. This example does not deploy or operate a real factory.
