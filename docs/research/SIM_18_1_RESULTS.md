# SIM-01..07 results: digital factory, optimisation, economics (Bakdaulet, 31 Oct)

Everything is **SIMULATED**: toy part generator, and `ILLUSTRATIVE_ASSUMPTION` timings and
prices. No physical part, no factory log. ROI figures are `SCENARIO_OUTCOME_NOT_MEASURED_SAVINGS`.

- **Registration:** `SIM_18_1_REGISTRATION.md`, committed before the run.
- **Data:** `examples/results/sim_18_1/` (clean tree, commit `90ec6fe`).
- **Reproduce:** `python scripts/run_sim_18_1.py` (~55 s). A second run on a clean tree gave
  byte-identical data files; only chart labels and manifest timestamps changed.

**Two aborted runs, disclosed.** Both aborted before producing any result:
- The CRN guard fired, because drift depended on the policy-dependent print time.
  It is now keyed to production sequence.
- The conservation guard fired on a CONWIP deadlock, where one part kind held every WIP
  token. Fixed with per-kind token pools.

Both have regression tests, and the runner now refuses to write results if either guard fails.

## What was built (status per board item)

| Item | Status | Where |
|---|---|---|
| SIM-01 factory engine | **WORKING**. Own DES core (stdlib), Slot/Tab printers with batches, kit-based CONWIP, MTBF/MTTR failures, transport, shared operators, review/rework/scrap, genealogy, multi-line. Conservation and determinism are tested. SimPy/FactorySimPy are `NOT_CONFIGURED` and not needed. | `qualityrelay17/sim/des.py`, `engine.py` |
| SIM-02 scenario generator | **WORKING**. 10 fault scenarios (drift, warping, cracks, camera noise + lot lighting, missing observations, network partition, station failures, operator bottleneck, cost shock), 5 multi-site, 3 scale tiers. Seeds, every generator parameter and a per-(scenario, seed) truth SHA-256 are in `scenario_manifest.json`. | `sim/scenarios.py` |
| SIM-03 CAD / sim-to-real | **PARTIAL**. Functional widths are measured from the STL meshes (slot 21.0, tab 20.0, clearance 1.0; all 7 meshes match their names). The physical-calibration interface rejects non-physical records and returns `NOT_AVAILABLE` until PHY-03 data exists. Isaac/Replicator/Warp/Newton/CadQuery are `NOT_CONFIGURED`. | `sim/cad.py` |
| SIM-04 economics | **WORKING**. 15 separately disclosed assumptions with ranges; Monte Carlo over assumptions × seeds; ROI, payback, P(worse). | `sim/economics_sim.py`, `roi.json` |
| SIM-05 optimisation | **WORKING (CPU)**. Linear-assignment pairing checked optimal against brute force; MILP capacity plan checked against brute force. OR-Tools/cuOpt are `NOT_CONFIGURED`. | `sim/optimization.py`, `capacity_plan.json` |
| SIM-06 multi-factory / scale | **WORKING**. Two suppliers + assembly site with 15 min transport, three evidence-sharing modes and stale-evidence HOLD; scale tiers of 6/10/50 production stations. | `MULTI`, `scale_scenario`, `scale.json` |
| SIM-07 dashboard data | **WORKING**. API-shaped records with `source_tier/seed/model_version/run_id/assumption_set`, a proposed JSON Schema for adilnurgg, CSVs and 4 SVG charts (each with its CSV). | `api/simulation_runs.json`, `docs/research/sim_api/`, `charts/` |

## Results (20 seeds, cluster bootstrap 95%)

### 1. Product configuration (bayes + optimised pairing) vs today (rules + FIFO)

**Safer in 15/15 scenarios** (escape-rate CI upper bound ≤ +1/1000), and **cheaper per good
unit in 15/15**. **Throughput is preserved in only 4/15** (F04 cracks, F05 camera noise,
F06 missing observations, F07 network partition). The registered "better on all three" holds
in those **4/15**, and the claim must be scoped to them.
- **Where it loses throughput:** −1 … −8% single-site (worst: F08 station failures); about −15%
  in M01/M02/M03/M05, where optimised batching waits for 8-part batches across a 15-minute
  transport.
- **Where it wins big:** F06/F07, about +72 … +95 good/h (+56% / +95%). The rule treats a missing camera
  reading as HOLD, so it floods review. The calibrated policy fuses whatever evidence exists.
- **Escapes:** −1 … −10 per 1000 shipped. The largest reductions are under drift and warping
  (F02 −9.6, F03 −7.8).

### 2. Factor decomposition (the honest part)

- **Policy (bayes vs rules, both FIFO):**
  - always safer;
  - fails the throughput rule in 8 of 10 single-site scenarios (more pair holds); the
    exceptions are F06/F07, where it gains;
  - better on all three in 5/15 (F06, M01, M02, M03, M05).
- **Optimised pairing with the *rule's* objective is unsafe under drift.**
  - Rules+optimised vs rules+FIFO: **+4.5 escapes/1000 in F02** and **+4.6 in M05**.
  - Optimising against the rule's acceptance line packs pairs just above the measured 0.5 mm.
  - With the calibrated-risk objective, the same optimiser has *lower* mean escapes in 15/15
    (statistically clear in some, not all).
  - **Matching optimisation is only safe when its objective is calibrated risk.** This is the
    06-doc warning, now measured.
- **Optimised pairing costs throughput under CONWIP**, because parts wait for batches.
  - Bayes+optimised vs bayes+FIFO preserves throughput in only 4/15.
  - Batch size and timeout are tuning parameters, not free wins.

### 3. Multi-site (SIM-06)

- **Summary-only sharing (M02) = full sharing (M01), identical to the last digit.** The
  supplier-side gate already removes the camera information the assembly decision would use.
  In this model, raw frames need not cross sites, which matches the 12-doc data-boundary rule.
- **Sharing lost (M03):** the assembly site re-inspects every part that passed the supplier
  gate (583 of 600 parts on average).
  Throughput −12% vs M01 (rules), and operator hours +70%.
- **Evidence older than the 120 s deadline (M04):** pair holds jump from ~3 to ~285 per run and
  throughput is −25%. SAFE-MESH's "stale evidence → HOLD" works as designed, and it is
  expensive. Latency is a first-order design parameter for federation.
- **Supplier bias + worse caliper (M05):** rules escapes 8.3/1000 vs bayes+FIFO 5.4.

### 4. Gate-A follow-up: holding everything in a real factory

`hold_all` sends every part through the one Review station (45 s/part). Good/h falls
**201.5 → 36.2 (−82%)**, profit/h 865 → 120, and hold inventory rises 100× (4.8 → 487 part-hours).

The direct cost of one HOLD under the assumption modes is only **0.38 cu** (review labour).
The real cost is capacity: lost throughput once Review saturates. Two consequences for Gate-A
(`COLLECTIVE_GATE_A_RESULTS_31OCT.md`):
- **The S12 label is wrong.** Its registered title "hold priced as review labour (5.0)" is not
  supported by these assumptions. Read S12 as "HOLD = 5.0 sensitivity". The scenario code is
  left unedited because it is registered.
- **Gate-A's flat HOLD price cannot represent a capacity constraint.** The factory engine is
  the right place to judge a hold-heavy policy, and here hold-all fails.

### 5. Scale (6 → 10 → 50 production stations)

| tier | today good/h | product good/h | escapes/1000 today → product | all three rules |
|---|---|---|---|---|
| SC06 | 64.0 | 63.7 | 4.2 → 1.4 | yes |
| SC10 | 128.1 | 125.7 | 2.8 → 1.0 | no (throughput) |
| SC50 | 706.3 | 700.7 | 3.9 → 1.6 | no (throughput) |

Throughput scales about 11× from 6 to 50 stations, with operators, review and assembly scaled
alongside. All 30 scale runs (3 tiers × 10 seeds) took 5.8 s in total.

### 6. Capacity plan (SIM-05, MILP; utilisation ≤ 0.85)

60 / 120 / 240 / 480 pairs per hour need 1/2/4/8 printers, 1/1/2/3 inspection lines and
1/1/2/4 operators. **The printer is the binding constraint in every plan.**

### 7. ROI (product vs today; 2000 Monte Carlo draws over assumptions × seeds)

- **P(QR worse) ≈ 0** in F06/F07, where rules choke on missing evidence.
- **P(QR worse) 5–9%** in F02/F03 (drift, warping).
- **P(QR worse) 30–36%** in F01/F04/F10.
- **P(QR worse) 39–64%** in F05, F08, F09 and every multi-site scenario (lowest: M04).
- Point medians are dominated by **escape cost × a handful of escapes per run**. Payback looks
  like days or weeks at the median, but that is an artefact of scaling a per-hour difference to
  4000 h/year at illustrative margins. **Do not quote a payback number.** Quote P(QR worse) per
  scenario.

## Claims the pitch may use (Bakdaulet signs; HyorinmaruK, only these, always with "simulated")

1. "In our simulated Slot/Tab factory, the calibrated policy with risk-based pairing shipped
   fewer defective assemblies in all 15 scenarios. It kept throughput in 4 of them, so it is not a
   free win."
2. "When a camera reading goes missing or the network drops, a rule that treats 'missing' as
   'hold' floods review. Calibrated fusion kept about 95 more good assemblies per hour in that
   scenario."
3. "Optimising part matching against a pass/fail rule increased escapes under drift. It is safe
   only when the objective is calibrated risk."
4. "Holding everything is not 'safe and cheap'. Through one review station it cut throughput by
   82%."

**Do not say:** a payback period, an annual saving, "X% cheaper" without a scenario ID, or
anything that implies a physical or factory measurement.

## Not done / next

- **SIM-03:** physical calibration waits on PHY-03 caliper records. Run
  `calibrate_from_caliper(records)` and re-run with the fitted widths.
- **Isaac Sim / Replicator / Warp:** `NOT_CONFIGURED` (need an RTX host).
- **Pairing batch/timeout tuning** (finding 2) and **evidence-latency tuning** (M04).
- **adilnurgg:** wire `api/simulation_runs.json` behind `/simulation/*` (API-01) and review the
  proposed schema.
