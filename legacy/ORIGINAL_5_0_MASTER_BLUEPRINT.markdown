# QualityRelay 5.0 master blueprint

## 1. Executive definition

QualityRelay is a decentralized quality-coordination system for assemblies whose fit depends on measurements owned by different manufacturing stations. A slot can pass its local specification and a tab can pass its local specification while their pairing still has insufficient clearance. Each station continues to own its raw data and local decisions. Agents exchange scoped, provenance-linked evidence only when an assembly-risk query or anomaly makes collaboration useful.

The hackathon demonstration answers one narrow scientific question:

> With the same statistical core and inspection budget, what capability is gained or retained when quality evidence is coordinated across independently authorized station agents, especially when communication is intermittent?

It does **not** attempt to prove that multi-agent systems are universally better than centralized quality systems.

## 2. The manufacturing problem

Three logical stations are modeled:

1. **Slot station** produces a slot and measures slot width `W`.
2. **Tab station** produces a tab and measures tab thickness `T`.
3. **Assembly station** selects lots, observes fit outcomes, and evaluates clearance `C = W - T` against a functional minimum `c_min`.

Local part specifications are deliberately not equivalent to the assembly requirement. In the demonstration reference design:

- Slot specification: 20.5–21.5 mm.
- Tab specification: 19.5–20.5 mm.
- Functional minimum clearance: 0.5 mm.
- Nominal means: slot 21.0 mm, tab 20.0 mm.

Worst-case individually accepted parts can produce `20.5 - 20.5 = 0.0 mm`, below the functional requirement. The exact risk depends on the process distributions and the acceptance conditioning. These values are configuration assumptions for a teaching demonstration, not measured factory parameters.

## 3. User story

Before assembly, an operator selects slot lot A-07 and tab lot B-12. The assembly agent cannot calculate a current risk until it obtains sufficient, authorized summaries from both stations. It sends evidence requests. Each station returns a signed summary referencing local measurement event IDs, not its entire raw table. The assembly agent calls the deterministic compatibility engine, receives a provenance-linked risk estimate, and either:

- permits the planned pairing with its uncertainty and evidence coverage;
- recommends a server-provided alternative lot with lower estimated risk; or
- asks for the physical measurement with highest expected information gain per second.

If the slot link is taken offline, the slot station continues local measurements and queues outbound events. Peers stop receiving new slot evidence; the UI marks the current diagnosis as partial and omits the stale station likelihood from the live posterior. The audit history remains intact. On reconnection, event IDs make replay idempotent.

## 4. Why decentralized agents are justified

The system models real organizational and technical boundaries:

- Different equipment or suppliers own different raw records.
- A station has authority to measure and summarize its own process, not to read another station’s database.
- Assembly owns the relational decision: whether two lots should be paired.
- Communication can be intermittent while local production and monitoring continue.
- An append-only router moves messages but cannot fabricate a measurement, compute a diagnosis, or override a station.

If every actor reads one shared database and one global posterior, the project fails its own decentralization claim.

## 5. P0 end-to-end behavior

1. Record or seed at least five recent measurements per relevant lot and station.
2. Create a `BatchRiskQuery` for an upcoming slot–tab lot pairing.
3. Show `pending_insufficient_evidence` until authorized evidence responses arrive.
4. Calculate clearance risk with the shared deterministic engine.
5. Link every estimate to the exact evidence event IDs, code version, assumptions, and origin labels.
6. Rank server-provided physical inspection candidates by expected information gain divided by time cost.
7. Accept a real caliper entry and update the diagnosis.
8. Toggle one station link offline and show partial-evidence behavior.
9. Reconnect and reconcile queued events exactly once.
10. Export a replayable run manifest and result record.

## 6. Architecture at a glance

```text
Slot UI/tool -> Slot service + local DB ----\
                                         signed evidence events
Tab UI/tool  -> Tab service + local DB ----- event router/log ---> Assembly service + local DB -> Dashboard
                                             |                         |
                                             |                         +-> risk/diagnosis/inspection core
                                             +-> no diagnostic authority

Optional LLM adapters sit above each station's approved tools.
All numeric truth is rendered from deterministic service responses.
```

The statistical core is one versioned library reused in isolated, centralized, and decentralized conditions. This prevents a strawman baseline. Deployment and evidence access change; the mathematics does not.

## 7. Scientific core

### 7.1 Clearance risk

For independent normal slot and tab distributions before acceptance truncation:

`mu_C = mu_W - mu_T`

`sigma_C^2 = sigma_W^2 + sigma_T^2 - 2*rho*sigma_W*sigma_T`

`P(C < c_min) = Phi((c_min - mu_C) / sigma_C)`

The benchmark must condition on both parts passing their local specifications. Use deterministic Monte Carlo from truncated distributions or numerical integration. The random seed is derived from the run ID, lot pair, evidence snapshot hash, and algorithm version so identical inputs return identical outputs.

### 7.2 Local process monitoring

Each station maintains an EWMA:

`z_t = lambda*x_t + (1-lambda)*z_(t-1)`

Control limits use the standard time-varying EWMA form. `lambda = 0.2` and `L = 3` are starting configuration values, not optimized claims. Baseline process mean and sigma come from the calibration dataset; they are not estimated from only five live points.

### 7.3 Evidence-scoped diagnosis

The minimum hypothesis set is:

- `H0`: stable process; assembly failures occur at the nonzero design baseline.
- `H1`: slot mean shifted downward.
- `H2`: tab mean shifted upward.
- `H4`: both means shifted toward reduced clearance.

Optional `H3` fixture/misalignment is P3 because a credible physical mechanism and likelihood model are not available in the core sprint.

Posterior updates are performed only over evidence the calling actor has locally observed or received through authorized responses. When a station is unavailable or evidence is outside the freshness window, its likelihood term is omitted and the posterior is renormalized. The UI must show evidence coverage, such as “computed from 2 of 3 stations.”

### 7.4 Targeted inspection

For candidate action `a` and possible outcomes `y`:

`IG(a) = H[p(H|E)] - sum_y p(y|a,E) * H[p(H|E,y)]`

`score(a) = IG(a) / expected_seconds(a)`

Candidate specimen IDs come from the server. An LLM may choose among them or request no action, but cannot invent an ID. The method is an application of established Bayesian experimental design, not a new information-theory algorithm.

## 8. Requested combined demonstration scenario

`configs/scenario_combined_0p100mm.yaml` specifies:

- scenario: `combined`;
- slot mean shift: `-0.100 mm`;
- tab mean shift: `+0.100 mm`;
- slot communication: `online` at the start;
- data source: `simulated`;
- pairing policy: uniform random pairing among locally accepted parts;
- outcome status: `NOT_RUN`.

Expected qualitative observations, not claimed results:

- both local EWMAs should move toward reduced clearance, though the exact alarm timing is unknown until run;
- the joint clearance-risk estimate should tend upward relative to the frozen nominal baseline;
- evidence requests and responses should complete while the slot link is online;
- the combined hypothesis should gain support if the generated evidence matches the configured shifts;
- a targeted inspection may be proposed if expected information gain exceeds the configured threshold;
- all dashboard values must be labeled simulated and tied to the seed.

Do not promise that the collaborative system beats the isolated condition at this shift magnitude. Pilot candidate shifts first because 0.100 mm may be locally detectable depending on sigma, EWMA parameters, and run length.

## 9. Validation design

### Experiment A: collective capability under full connectivity

Compare:

- isolated station actors with peer requests disabled;
- centralized system with all raw evidence;
- QualityRelay peer evidence exchange.

Use the same core, scenario streams, inspection budget, and seeds. Primary interpretation: QualityRelay may recover much of centralized performance with less raw-data access and a traceable communication budget. Do not claim it should beat the centralized upper bound.

### Experiment B: resilience to information topology

A 2×2 design:

| Topology | Always on | Intermittent link |
|---|---|---|
| Centralized hub | upper-bound reference | hub/link degradation |
| Decentralized peer mesh | normal QualityRelay | local continuity + partial evidence + reconciliation |

The hub’s coordinator-failure test is deliberately asymmetric: a peer mesh has no single coordinator to fail. State this rather than pretending the cells are identical.

### Metrics

- fault-hypothesis accuracy on simulated ground truth;
- detection delay in units after injected change;
- assembly-risk Brier score on simulated runs only;
- number and time cost of physical/simulated inspections;
- raw records exposed across station boundaries;
- message count and bytes;
- evidence coverage at decision time;
- duplicate-event count after reconnect;
- unauthorized access attempts denied;
- physical loop completion reported descriptively, never as a calibrated percentage.

## 10. Physical evidence plan

Use a small U-slot coupon and flat tab coupon printed in white PLA. Print a safe pair, a nominal pair, and a tight-risk pair plus backups. Do not rely on CAD dimensions as ground truth. First measure one stable coupon ten times, compute repeatability standard deviation `s_r`, then choose a demonstrated clearance difference comfortably larger than measurement noise. A 3–5× `s_r` rule is a screening heuristic, not a full gauge R&R study.

Two or three physical pairings close the loop; they do not validate the predicted probability. Simulation supplies repeated, seeded ground truth. Physical and simulated metrics must be shown in separate panels.

Do not attempt a live print-redesign-reprint-refit loop. Show any corrected CAD as a next-step artifact.

## 11. Success criteria

P0 is complete only when all are true:

- one command resets the demo to a known state;
- a risk query remains pending before evidence arrives;
- unauthorized cross-station raw reads return 403 and are logged;
- the same input snapshot produces the same risk output;
- all numeric UI statements are server-rendered from structured results;
- candidate IDs are whitelisted;
- link loss changes evidence coverage visibly without deleting history;
- reconnect produces zero duplicate events;
- a physical caliper entry is stored with `origin.kind = physical`;
- a simulated benchmark record includes seed and generator version;
- no chart combines physical and simulated observations into one unlabeled metric;
- the deterministic fallback performs the complete demo without an LLM.

## 12. Milestones and cut lines

| Milestone | Active-hour deadline | Acceptance condition | Cut if missed |
|---|---:|---|---|
| M0 scope/interface freeze | H1 | schemas, role boundaries, scenario IDs fixed | remove alternative-lot and disagreement branches |
| M1 deterministic core | H6 | clearance, EWMA, diagnosis, inspection tests pass | remove Bayesian extras; keep risk + fixed inspection |
| M2 minimum viable demo | H12 | reset → query → evidence → risk → inspection → update | LLM removed from critical path |
| M3 decentralized proof | H18 | 403 test, scoped posterior, offline queue, idempotent replay | use recorded outage clip; keep live evidence exchange |
| M4 experiment freeze | H23 | pilot selects shift rule; matrix and seeds frozen | reduce to 3 seeds and label exploratory |
| M5 feature freeze | H25 | full run completes twice | no new features |
| M6 submission ready | H29 | slides, repository, manifest, backup clip, 2 rehearsals | polish only |

## 13. ScienceClaw rubric alignment

| Rubric | Evidence to show |
|---|---|
| Problem significance, 20% | relational tolerance-stack failure across data silos; preventable scrap/rework risk |
| Scientific/technical impact, 25% | prospective lot-pair risk, targeted inspection, traceable decision; results shown only after execution |
| Decentralized agency, 20% | station-local data/authority, explicit evidence requests, no decision-making router, offline local continuity |
| Collective capability, 25% | same-core comparison against isolated and centralized conditions; link-fault experiment |
| Execution/validation, 10% | functioning vertical loop, seeded experiments, physical caliper input, negative permission test, replay manifest |
| Optional collaboration bonus | another team actually reuses the event schema, replay dataset, or tool; usage is documented |

## 14. Honest closing claim template

Fill brackets only after measured runs:

> Using the same statistical core and inspection budget, QualityRelay’s independently authorized station agents evaluated an upcoming compatibility risk through selective evidence exchange, requested a targeted inspection, and retained local operation during a communication interruption. In seeded simulation, the collaborative condition [measured result with uncertainty]. In the physical demonstration, [descriptive observed loop outcome]. These results demonstrate a hackathon prototype, not industrial validation.

