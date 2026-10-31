# Agents: what exists, what is missing, plan for 1 Nov (Bakdaulet)

Status: **PLAN**. Nothing below is run yet. All results will be `SIMULATED` unless a physical
run exists. Related: concept text (31 Oct, Kazakh), `CAPE_CAPACITY_AWARE_EVIDENCE_ACQUISITION.md`,
`COLLECTIVE_GATE_A_RESULTS_31OCT.md`, `PRIOR_ART_AND_RESEARCH_QUESTIONS.md`.

## 1. The six concept agents vs the code today

| Concept agent | What is inside (no LLM) | Code today | Gap |
|---|---|---|---|
| Vision | anomaly model (STFPM) / reference compare / ArUco width | `anomaly.py`, `vision.py`, `vision_measure.py`, `inspection_visuals.py` | no agent interface; not trained on our parts (VISION-01..05 blocked on photos) |
| Metrology | caliper Gaussian posterior, repeatability, calibration | `calibration.py`, `sim/physical_data.py`, `experiments/belief.py` | same; physical fit waits for HyorinmaruK's CSV |
| Process | EWMA printer feedback + CUSUM alarms (I1) | `sim/engine.py` (inside the simulator only) | not a standalone agent; only proposes in sim |
| Assembly | pair gate P(unsafe) + risk pairing (= selective assembly) | `matching.py`, `sim/engine.py`, `safe_mesh.py` | no agent interface |
| Cost | Bayes decision + two-step VOI, cost table | `economics.py`, `experiments/collective_baselines.py` (B7) | HOLD is priced as free (root cause of the Gate-A negative) |
| Learning | active-learning ranking (I9), conformal recalibration (I2) | `sim/api_routes.py` `/vision/suggest`, `experiments/conformal.py` | no promote/rollback gate (champion/challenger) |

Already shared by all: typed `Evidence`/`Decision` (`contracts.py`), local append-only ledger with
ACL (`ledger.py`), deterministic SAFE-MESH hard gate (`safe_mesh.py`), bounded tool permissions
(`agent_tools.py`, `roles.py`; the 21 role names are a registry, not 21 trained models).
Transport between stations and the authenticated backend are **adilnurgg's** (AGENT-01/BACK-01,
`adilnur-branch`); do not duplicate them.

## 2. Why the agent result is negative today, and what would make decentralisation matter

Gate-A (registered) found two things:
1. B7 (SAFE-MESH + VOI) holds every part at the registered prices, because a HOLD is priced at
   2.0 with no throughput loss. Under SIM-04 the real cost of holding is lost output once review
   saturates (hold-all: -82% good/h).
2. B7 vs B6: "splitting ownership across roles adds no information. Roles only add messages."
   In the mock world every agent could see everything, so decentralisation can only cost.

So decentralisation needs conditions where it changes the information or its price. Three are
standard in the literature and real on a line:
- **D1 bandwidth / data volume:** raw images are large; a station can send a 100-byte summary
  (score, calibrated probability, provenance) instead. Central fusion must ship raw frames.
- **D2 link outage:** the central server or network is down for a period. A central policy must
  HOLD; station agents can still decide on local evidence when that is safe under the α cap.
- **D3 local drift known only locally:** a camera/caliper drifts; the station agent recalibrates
  itself (EWMA / conformal on its own confirmed outcomes) while the central model stays frozen
  until a retrain.

## 3. Plan for 1 Nov, in priority order

### P1 Science: "where decentralisation pays" (registered before running) ~3 h
- **Fix the hold price** properly: HOLD cost = review labour + delay, and review capacity from the
  DES (CAPE idea, first simple version): when review is saturated, extra holds cost lost output.
- **Scenarios:** S01 baseline + D1, D2, D3 (+ D1+D3), each with pre-declared parameters.
- **Policies:** B0 isolated rules, B1 central Bayes fusion (all raw data shipped), B2 upper
  bound, B6 central VOI, B7 decentralised VOI (+ local recalibration for D3), B7-minus-each.
- **Metrics:** unsafe PASS/1000 with α = 2/1000 as a **hard** limit (reported first), released
  good, false HOLD, inspections/part, messages/part, **bytes sent/part**, cost/good unit, time to
  first CUSUM alarm (D3).
- **Decision rules (fixed before the run):** decentralisation "pays" in a scenario only if B7 meets
  α, is not worse on released good (CI), and is cheaper or sends fewer bytes than B1/B6 (CI).
  Report every scenario, including the ones where it does not pay.

### P2 Engineering: explicit agents with one interface ~2 h
- `qualityrelay17/agents/`: `Agent.observe(evidence) / propose() / request(kind) / respond(req)`,
  six thin wrappers over the existing modules, each declaring `inside = model|statistic|rule`,
  version and calibration id. No new science, no LLM.
- **Learning agent champion/challenger gate:** a new model/calibration is promoted only if it is
  better on a held-out set by a pre-set margin, else the old one stays (rollback). Tests.
- The Process agent only **proposes** set-point changes in sim; nothing actuates (AGENTS.md).

### P3 Demo: "Agents" view in the Studio ~2 h
- For a selected part: the message sequence (Vision → Metrology request → response → Cost agent
  VOI → SAFE-MESH gate → decision) with each value, price and the reason, from the B7 trace.
- P1 chart: per scenario, unsafe vs cost vs bytes for central vs decentralised, `SIMULATED`.

### P4 Only with adilnurgg: separate processes over his transport (optional)
Run station agents as separate local processes over AGENT-01/BACK-01 and check that decisions
equal the in-process B7. His ownership; ask first.

## 4. Pitch wording (until P1 results exist)

May say: "Each station agent is a small model, a statistic or a rule, not an LLM." "Agents
exchange typed, signed evidence; missing or conflicting evidence means HOLD." "In simulation, our
first full agent failed its own pre-registered gate; we found the cause (holds priced as free)
and are testing where decentralisation actually pays."

Do not say: "decentralised agents beat a central system", "21 agents", any saving without
scenario ID and `SIMULATED`, or that the agents run on separate devices (until P4 exists).
