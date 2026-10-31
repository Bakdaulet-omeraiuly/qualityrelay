# CAPE: Capacity-Aware Provenance-Constrained Evidence Acquisition

**Project:** QualityRelay 18.x / SAFE-MESH  
**Status:** **PROPOSED RESEARCH METHOD — NOT IMPLEMENTED OR VALIDATED**  
**Date:** 31 October 2026  
**Research and simulation owner:** Bakdaulet (`Bakdaulet-omeraiuly`)  
**Agent protocol/backend owner:** adilnurgg  
**Physical measurements, specimen preparation, sorter and presentation owner:** HyorinmaruK

## 1. Scientific claim and novelty boundary

### Research question

> Under distributed, partially dependent, and uncertain manufacturing-quality evidence, can a decentralized team select source-specific peer queries and physical inspections that minimize **total production loss** while meeting explicit safety, inspection-capacity, and authorization constraints?

**Hypothesis, not a discovery:** CAPE may outperform capacity-blind NetVOI, entropy-only information gain, fixed inspection rules, multi-agent voting, and unstructured debate **under conditions in which inspection stations are congested and unique evidence is distributed among authorized specialists**.

CAPE is a proposed combination of known ideas; Bayesian decision theory, active inspection, queue-aware scheduling, evidence provenance, and multi-agent communication all have prior art. Novelty must be established with a documented literature comparison, a sufficiently specific algorithm, ablations, and reproducible evidence. Do not advertise a first-ever invention, a validated factory saving, or a proven performance advantage.

**Related systems:**

- **EVIDENCE-MESH:** authenticated, permissioned sharing, provenance and dependence relationships.
- **V-DER / CAIR:** existing decision-focused and camera-active inspection proposals; CAPE should extend, compare with, and reuse their validated components, not silently rename them.
- **SAFE-MESH:** independent, deterministic safety/authority and physical-action verification gate; CAPE does not supersede it.
- **Digital Factory / discrete-event simulation:** predicts queue and capacity externalities of additional inspection actions.
- **LLM specialists:** propose hypotheses and targeted evidence requests; they do **not** compute ungrounded probabilities or authorize machine control.

## 2. Why this problem matters

A locally informative caliper reinspection can have large system-level cost when the caliper station is saturated. In the Digital Twin PR #3, the author reports a **simulated** 99.8% caliper utilization under a VOI policy with extensive retakes; this is an illustrative, model-dependent observation and must be reproduced on the reviewed merge commit before being called a verified baseline. It motivates queue-aware inspection rather than claiming CAPE already fixes the bottleneck.

Likewise, three agent summaries derived from one photo are not three independent measurements. Evidence correlation, stale calibration, shared lighting, mismatched CAD revisions and station outages must be represented explicitly.

## 3. Mathematical formulation

Let the current **authorized and verified** observation state be `D_t`, including source-root lineage, calibration, provenance, timestamps, case ID, active station queues and capacities.

- `h`: latent true quality state (e.g., OK, visible defect, clearance defect, both).
- `a`: final safe action allowed by the independent safety gate (`HOLD`, `PASS_REVIEW`, `REJECT_REVIEW` before any physical approval).
- `q`: candidate action to obtain evidence: query a peer's authorized existing record, retake caliper, reshoot phone/Pi photo, test assembly, etc.
- `y`: possible observed result of `q`.
- `L(a,h)`: predefined outcome loss (scrap, escape, rework, hold).
- `c_direct(q)`: one-time actual incremental execution, cloud/tool/message and human costs.
- `c_delay(q,D_t)`: **marginal system-wide queue and throughput cost**, estimated from a calibrated discrete-event simulator or measured capacity model; not just inspection service time.
- `c_risk(q,D_t)`: independently specified risk cost, when defensible; hard safety rules are not monetized away.
- `B`: hard per-case budget, with service-capacity, deadline and approval constraints.

Current Bayes decision risk is

`R(D_t) = min_{a in A_safe(D_t)} E[L(a,h) | D_t]`.

A capacity-aware net value for candidate query `q` is

`CAPE(q | D_t) = R(D_t) - E_y[R(D_t union verified(q,y))] - c_direct(q) - c_delay(q,D_t) - c_risk(q,D_t)`.

Select the highest positive-value **feasible** query only if:

1. The sender and recipient are authenticated and scoped to the requested evidence.
2. The returned source will be **new and decision-relevant** (or explicitly beneficial remeasurement); lineage/dedup is checked; no free bonus for copied photos.
3. The expected outcome model `P(y | D_t,q)` and posteriors are calibrated or marked uncertain.
4. The inspection device and queues have enough capacity; safety constraints and deadlines permit the action.
5. The true incremental costs are charged **exactly once**, including messages, LLM tokens, retakes, human reviews and delays.

If no query is feasible or positive-value, stop acquisition and pass to SAFE-MESH for HOLD/review. A mandatory safety inspection may still be required even if CAPE is negative; the safety gate is outside the optimization's authority.

### Avoiding circularity and double counting

Queue-delay costs are **externalities**. When a factory simulation already produces time-based loss in the final objective, do not separately add the same delay cost again. For online planning, `c_delay` is an approximation to *marginal* system-wide future loss; in offline benchmark evaluation, use the realized DES cost accounting once.

Do not double count:
- sensor evidence already acquired before `t` as a newly purchased observation;
- a peer reply and its source sensor acquisition as two sensor purchases;
- multiple transformed scores sharing `source_root`;
- hold inventory cost and the same labor/delay component if the accounting already includes it.

## 4. Concrete candidate inspections and shared data contract

Sample candidate actions:

| Action | Novel evidence source | Typical bottleneck | Possible caveat |
|---|---|---|---|
| Request CAD revision from Design Agent | Versioned design evidence not previously visible | Peer availability / network | If same CAD revision already read, no new source |
| Ask Process Agent for print/production log | Station-level machine evidence | Request latency | Must not expose other suppliers' raw data |
| Caliper retake | New verified physical measurement | Single caliper queue | Correlated calibration bias; high utilization |
| New-angle phone image | New photo under controlled pose | Operator / camera | Shared lighting and same underlying specimen |
| Raspberry Pi reinspection | Independent camera capture | Edge compute / camera time | Common-mode environmental errors |
| Physical assembly check | Ground-truth-like fit attempt | Assembly station / operator | Mechanical fit != complete quality ground truth |

Standard message envelope fields: `message_id, case_id/specimen_id, kind, sender_role, recipient_role, request_reason, evidence_kind, source_root, source_event_ids, observed_at, station_id, calibration_id, origin, cost_budget, deadline, signature, correlation_group, schema_version`. Identities and tool permissions are verified server-side, never trusted from LLM prose.

## 5. Proposed algorithm (pseudocode, not code shipped yet)

```python
for case in incoming_cases:
    state = authorized_evidence_view(case)
    while state.rounds < MAX_ROUNDS:
        belief = calibrated_fusion(state.evidence, state.lineage, state.sensor_context)
        if safety_gate.immediate_hold_required(case, state):
            break
        candidates = allowed_peer_and_physical_inspections(
            case, state.roles, state.permissions, state.budget, state.queues
        )
        scores = []
        for q in candidates:
            outcomes = calibrated_predictive_outcomes(q, belief, state)
            expected_postrisk = sum(
                p * bayes_safe_risk(update_belief(belief, q, y))
                for (y, p) in outcomes
            )
            marginal_delay = twin.estimate_marginal_delay_cost(
                q, state.factory_load, state.queues
            )
            net_value = (
                bayes_safe_risk(belief)
                - expected_postrisk
                - direct_incremental_cost(q)
                - marginal_delay
            )
            scores.append((q, net_value))
        q_star = best_feasible_positive(scores)
        if q_star is None:
            break
        response = await authenticated_query_or_inspection(q_star)
        state.append_verified_response_or_failure(response)
        state.charge_actual_cost_once(response)
    decision = safety_gate.review_for_human_authorization(case, state.evidence)
    record_full_audit(case, decision, state)
```

The queue model must depend on observable load and be calibrated against physical station timings. Do **not** pass simulation ground truth to agents. Recompute `P(y | D_t,q)` after each actual new observation; a static one-step menu is not fully adaptive.

## 6. Core experimental design

### Baselines — same safety gate and cost policy

- B0: Conservative fixed inspection rules.
- B1: Entropy-only information gain (IG).
- B2: Standard calibrated cost-aware NetVOI without capacity.
- B3: Capacity-aware NetVOI **without peer communication or provenance handling** (simulation only).
- B4: Structured peer evidence requests with fixed inspection order.
- B5: One LLM specialist with matched information access and action budget.
- B6: Multi-agent majority vote with matched initial observations.
- B7: **CAPE + EVIDENCE-MESH + SAFE-MESH**.
- B8: Full-information single-agent reference (separate oracle-information upper bound, NOT a cost-matched competitor).

Other than the explicitly upper-bound baseline, all policies must face the **same available sensor actions, budgets, costs, simulation seeds, hardware capacity and safety enforcement**. Avoid leaking simulator latent defect labels into any model's evidence.

### Required ablations

- Without capacity term.
- Without peer requests.
- Without provenance-aware deduplication (**SIMULATION ONLY; never bypass physical security**).
- Without specialist role prompts (single general prompt).
- Without dynamic belief updates.
- Without adaptive VOI (fixed inspection schedule).
- Without measured real-time station queue observations.

### Stress conditions

Single vs multiple caliper resources; low vs high line utilization; rare vs common defects; correlated camera misclassification; repeated photo root; missing CAD revision; shifted lighting; stale sensors; device offline; network delay; wrong-role requests; expensive LLM calls; physical HOLD/reinspection backlog; capacity fluctuations.

### Primary metrics

1. **Unsafe PASS**: per defective units and separately per all processed units (keep denominator explicit).
2. **Realized total operational cost per 1,000 parts**, with sensor, request, LLM, inspection, rework, scrap, waiting, downtime, human approval and amortization items disclosed individually.
3. **Throughput and end-to-end cycle-time distribution** (`p50/p95`); system stability at station utilization.
4. **New unique decision-critical source discovery**, not number of messages.
5. **Safety invariants**: unauthorized physical actuation count, incorrectly accepted repeated/replayed evidence, missing-ACK events.

Secondary: hold/false-hold rate, precision/recall by defect class, cost per correctly resolved part, confidence calibration/Brier score, calibration drift, message/token overhead, deadline failures, physical sorter confirmation accuracy.

### Statistical protocol

- Freeze policies, cost model, safety thresholds and hypotheses *before* the final evaluation.
- Train/calibrate/test on disjoint part IDs, print batches and camera sessions.
- Paired common-random-number seeds for DES runs; cluster/bootstrap intervals over independently generated batches/runs.
- Report point estimates, confidence intervals, sample sizes, and failed/negative experiments.
- For real prototypes, measure actual service times and physical ground truth with HyorinmaruK; label all synthetic outcomes as `SIMULATED`.
- Implement capacity regimes in which CAPE plausibly helps **and** regimes in which it should rationally reduce to standard VOI. Include a strong queue-aware OR/operations research baseline to distinguish contributions from straightforward dispatch optimization.
- Benchmark agent collaboration separately from LLM model choice; OpenAI, Anthropic and Nebius are interchangeable adapters to evaluate, not the claimed invention.

## 7. Implementation ownership and phased tasks

### Bakdaulet — scientific ownership, all simulation

- **CAPE-SCI-01:** Fix pre-existing `voi_driven` and `structured_request_lite` inspection/request cost mismatches first, and add regression tests. Never use invalid previously advertised savings as baseline proof.
- **CAPE-SCI-02:** Implement `qualityrelay17/cape.py` as a pure deterministic candidate scoring engine with injectable calibrated outcome, cost and queue models.
- **CAPE-SCI-03:** Extend the event-driven Digital Factory DES to expose queue length, resource utilization, marginal waiting loss and simulation-consistent realized costs. Consider multi-factory scenarios as later scaling tests.
- **CAPE-SCI-04:** Model shared sensor error, source-root dependence and calibration uncertainty; compare robust/conservative posterior updates against independence assumptions.
- **CAPE-SCI-05:** Build B0–B8 baselines, ablations, scenario generation, paired-seed manifests, statistical plots, cost breakdowns and `CAPACITY_AWARE_RESEARCH_RESULTS.md` with honest negative findings.
- **CAPE-SCI-06:** Integrate physical timings and measurements received from HyorinmaruK for validation; keep measured, assumed and simulated values distinguishable.

### adilnurgg — distributed agent protocol, API and cloud

- **CAPE-BACK-01:** Implement role-scoped peer query / response / timeout/deny workflow, permission checks, replay resistance and provenance lineage. Persist per-case actual request cost and latency.
- **CAPE-BACK-02:** Expose signed, appropriately authorized source summaries and per-station live queue metrics; do not expose full raw evidence to all agents.
- **CAPE-BACK-03:** Integrate CAPE's candidate scoring as a deterministic tool, not a free-form LLM decision; Nebius/OpenAI/Claude providers may be swapped for benchmarking.
- **CAPE-BACK-04:** Expose simulation and CAPE trace views in the website; keep live physical, replayed and simulated sources distinct.
- **CAPE-BACK-05:** Keep independent hardware command approval, HOLD fallback and bin ACK verification; no LLM direct GPIO.
- **CAPE-BACK-06:** Maintain CI and fault-injection tests for source lineage, auth, cost-accounting consistency, queue telemetry and worker failure.

### HyorinmaruK — physical equipment and presentation only

- **CAPE-PHY-01:** Prepare Slot/Tab specimens, CAD revisions, reference photos, two-camera mounting, calibrated caliper and physical assembly/sorting equipment.
- **CAPE-PHY-02:** Time each physical inspection, reinspection, station handoff, sorting and human review; provide source IDs and uncertainty.
- **CAPE-PHY-03:** Produce sensor-verified physical sorter logs, including HOLD and failure paths; run supervised hardware safety tests.
- **CAPE-PHY-04:** Present actual physical evidence and benchmark limitations clearly, without describing hypothetical savings as real results.

## 8. Acceptance criteria / release gate

**Gate 0 — math & provenance:** old cost accounting fixed; signed/verified provenance, all independent sensor purchases charged once, no double counting; tests pass.

**Gate 1 — adaptive acquisition:** a real verified peer reply or new inspection result changes the proposed action in a reproducible case; a duplicate source does not increase confidence.

**Gate 2 — queue-aware behavior:** at equal sensor quality, increasing congestion changes the optimal admissible query where the model predicts it should. At near-zero utilization and zero marginal delay, CAPE matches capacity-blind VOI (within numerical tolerance).

**Gate 3 — honest benchmark:** B0–B8, pre-registered ablations and stress cases run under matched budgets and capacities; report any losses vs simple rules; no invented gains.

**Gate 4 — physical and safety:** source-authenticated device evidence; human approval before sorter action; independent ACK; physical measurements logged and separated from simulated outputs.

**Gate 5 — reproducibility:** fixed seeds, configuration/model versions, dependency pins, clean run manifests, GitHub CI, per-case cost ledger and independent review.

## 9. Prior work and limits

- Li, Naito, Shirado, *Systematic Failures in Collective Reasoning under Distributed Information in Multi-Agent LLMs*, ICML 2026: distributed information causes coordination failures; structured protocols can help. https://proceedings.mlr.press/v306/li26ej.html
- Anindya, *From digital shadows to assured intervention: a systematic review of embodiment, authority, and assurance in manufacturing quality digital twins*, Journal of Engineering and Applied Science (28 Oct 2026): 235-study review; no reviewed paper demonstrated a fully governed adaptive QA intervention chain **within that review's scope**. https://link.springer.com/article/10.1186/s44147-026-01295-x
- Existing QualityRelay studies and code: `docs/research/COLLECTIVE_17_1_BAKDAULET.md`, `qualityrelay17/vder.py`, `qualityrelay17/factory.py`, `qualityrelay17/safe_mesh.py`.
- CAPE combines established concepts; this document is **not** a patentability, priority, or literature-exhaustiveness assertion. Before external scientific novelty claims, run a broader scholarly search of inspection POMDPs, constrained Bayesian experimental design, queue-aware decision making, active perception, cost-sensitive diagnosis and distributed sensor fusion.

## 10. Fast next step

Start with a **two-choice counterexample** where the most accurate caliper retake is cheaper than a peer query at low utilization but more expensive once marginal queue delay is included. Unit-test the switch, then run identical seeds through the actual DES and verify that the predicted benefit tracks realized cost without hidden sensor charges. This single test distinguishes CAPE's central mechanism from an architectural diagram.
