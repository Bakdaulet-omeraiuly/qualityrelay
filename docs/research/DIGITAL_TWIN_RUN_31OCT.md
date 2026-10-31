# Level-1 digital twin — first run, 31 October 2026

**Owner:** Bakdaulet (taken over from the Digital Twin Lead, who owns physical test + presentation).
**Tier:** `SIMULATED`, every number. **Code:** `qualityrelay17/digital_twin.py`, runner
`scripts/run_digital_twin.py`. **Artefacts:** `examples/results/digital_twin_31oct/` —
`manifest.json`, `<scenario>.json` (per-seed records, paired CIs), `summary.csv`.

## What the twin is
The 05 architecture doc asked for Level 1: buffers, queues, WIP, cycle time, throughput, ≥ 3
seeded fault scenarios, common random numbers across policies, conservation checks, every event
`SIMULATED`. 17.0 had two unconnected pieces — the inspection policies (`factory.py`, *what* is
decided) and a flow-shop line (`digital_line.py`, *when*). The twin joins them:

`Print(×2) → Phone_Vision → Pi_Vision → Caliper → [visit the policy paid for] → Decision → Sorting → Review (HOLD only)`

A VOI recapture re-queues the part at a camera station, a caliper retake at Caliper, every HOLD
occupies the single Review (quarantine) operator. Same seed ⇒ same specimens **and** same
service-time noise for every policy, so a difference between policies is the policy, not the
dice. Service times are **illustrative assumptions** (`TwinTiming`, echoed in every output as
`ILLUSTRATIVE_ASSUMPTION`): arrivals every 10 s, Phone 5 s, Pi 6 s, Caliper 7 s, recapture 5 s,
retake 7 s, Review 45 s, one Review operator. The line mirrors the physical Slot/Tab demo
station-for-station (acceptance 1). V&V in `tests/test_digital_twin.py`: conservation
(pass + hold + escaped = n, WIP ends at 0), deterministic replay, unique IDs, no negative
waits, dispositions identical to `factory.apply_policy`, CRN verified on the Print station.

Two modelling errors were found and fixed *by running it*, not assumed away: (1) the inherited
`digital_line` defaults (arrival 8 s, one 18 s printer) saturated the line before any policy
mattered — now two printers at 0.9 utilisation; (2) `digital_line`'s "process parts in arrival
order" shortcut is wrong once a part can revisit a station, so the core is a real event-driven
DES with per-station FIFO queues.

## Baseline (10 seeds × 1000 parts, means; Δ = policy − `conservative_rules`, 95 % cluster-bootstrap CI over seeds)

| Policy | Cycle time (s) | p95 (s) | Throughput /h | Mean / max WIP | Holds | Unsafe /1000 | Δ cycle [CI] |
|---|---|---|---|---|---|---|---|
| `conservative_rules` | **82.4** | 288 | 352 | 8.1 / 15.4 | 201.9 | 3.0 | — |
| `collective_fusion` | **62.9** | 156 | 357 | 6.2 / 12.2 | 157.9 | 3.1 | **−19.5 [−27.1, −12.9]** |
| `structured_request_lite` | 62.2 | — | 357 | — / 12.2 | 157.9 | 3.1 | −20.2 [−27.8, −13.6] |
| `voi_driven` | **2000** | 3660 | 275 | 153 / 293 | 97.5 | 1.9 | **+1918 [+1864, +1974]** |
| `entropy_driven` | 2123 | 3831 | 272 | 160 / 305 | 97.5 | 1.9 | +2040 [+1987, +2089] |

### The finding the cost benchmark could not see
`voi_driven` is the *safest* policy here (1.9 escapes/1000) and in the cost benchmark it looked
cost-neutral. On the line it is **operationally infeasible**: its near-universal caliper retake
(85 % of parts, see `PROTOCOL_RUN_31OCT_RESULTS.md` §1) drives the **Caliper station to 99.8 %
utilisation** (mean wait ≈ 1000 s), cycle time 24× the rule's, max WIP 293 parts. `Costs.inspection
= 0.5` has no notion of station time or capacity, so the expected-loss optimum buys a retake that
the line cannot serve. Nothing in the VOI mathematics is wrong; the cost table is incomplete.

Conversely `collective_fusion` — identical posteriors, no purchases — is **24 % faster** than the
rule at the same inspection load, purely by holding 44 fewer parts per 1000: the Review operator
drops from 96 % to 81 % utilisation and the queue in front of quarantine shrinks (p95 cycle 288 →
156 s). Its one extra escape per 10 000 parts is the price; whether that is acceptable is the
quality owner's call, not ours.

## Fault scenarios (means over 10 seeds; cycle time in s, Δ vs rules with CI)

| Scenario | `conservative_rules` | `collective_fusion` | `voi_driven` | What it shows |
|---|---|---|---|---|
| large_shift (0.20 mm) | 492 | **17 868** (+17 376 [+17 266, +17 491]), 1000/1000 holds, 79 parts/h | 1682 (+1190) | fusion/request collapse to always-HOLD (dimensional prior 11.5 %) — the Review queue makes the safety-only pathology visible as a dead line |
| noisy_correlated_cameras | 883 | **555** (−328 [−362, −292]) | 1674 (+791) | rule's 329 holds saturate Review; fusion holds 37 fewer |
| outage_heavy (20 %) | 851 | **63** (−787 [−910, −672]) | 2000 (+1150) | rule HOLDs on every network drop → Review bottleneck; fusion ignores the flag (no evidence is actually lost in the generator) |
| tight_review (90 s) | 920 | **424** (−496 [−543, −443]) | 2014 (+1094) | with a slower reviewer every hold costs double; fewer holds = shorter line |
| inspection_cost_x10 (`Costs.inspection` 0.5 → 5.0) | 82 | 63 | **63 (= fusion)**, 157.9 holds, 3.1 unsafe | priced at 5.0 VOI buys **nothing** and becomes fusion; entropy ignores price and stays at 2123 s |

Reading `inspection_cost_x10`: the cost table is also a **capacity knob**. At 0.5 VOI retakes
everything and jams the caliper; at 5.0 it retakes nothing and gives up its safety gain. The
useful setting is in between and depends on the station's free capacity — i.e. inspection cost
should be a function of current queue state (a capacity-aware VOI), which is exactly the
coupling between decision theory and the digital twin that neither module had alone.

## Acceptance against the 05 doc
- One physical Slot/Tab story mirrors one simulated line — **yes**, station-for-station.
- ≥ 3 seeded fault scenarios, common random numbers across policies — **6 scenarios, CRN tested**.
- Inventory/WIP, cycle time, throughput with origin labels — **yes**, all `SIMULATED`.
- Conservation, determinism, no negative WIP / duplicate IDs — **tested** (18 tests).
- Validate service times against real logs — **not possible yet**; nothing here is a measurement.

## Exploratory follow-ups (not run; label as such)
1. Capacity-aware VOI: `inspection_cost = Costs.inspection + λ·(queue length at that station)`, re-run
   the baseline and `tight_review`; look for the knee between 0.5 and 5.0.
2. Continuous caliper likelihood (targeted retakes) — same fix helps both the cost benchmark and
   the line.
3. Replace `TwinTiming` with the stopwatch numbers from HyorinmaruK's repeatability screen and
   station build; re-run; report the sim-to-real gap.
