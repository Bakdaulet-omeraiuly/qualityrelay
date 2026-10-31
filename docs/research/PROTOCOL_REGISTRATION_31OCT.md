# Pre-registration — synthetic VOI protocol run, 31 October 2026

**Owner:** Bakdaulet (scientific engine). **Status:** registered BEFORE the run; the git commit
that adds this file is the registration timestamp. Results go in a separate file
(`PROTOCOL_RUN_31OCT_RESULTS.md`) written only after `scripts/run_protocol.py` has finished.
Anything not written here and later reported is **exploratory**, and must be labelled so.

Everything below is `origin = SIMULATED`. The generator is `factory.seeded_scenario`; costs are
assumptions (`economics.Costs`). Nothing here is a factory measurement.

## What changed in the engine before this run (and why)

The `voi_driven` wiring added on the night of 30→31 Oct had three defects that made its
exploratory "~27% lower cost" number uninterpretable. All three are fixed in the same branch as
this registration, before any registered run:

1. **Loss-scale mismatch.** `vder` scored actions with `false_pass=100 / false_hold=3 /
   inspection 1.0–3.0`, while the benchmark scored outcomes with
   `Costs(escaped_defect=150, hold=2.0, inspection=0.5)`. The policy optimised one objective
   and was graded on another. Now the VOI step reads its loss parameters from the same `Costs`
   instance the benchmark uses.
2. **No fresh information.** "phone_recapture" re-read the same `phone_suspect` bit it already
   had for free, so the "action" bought nothing. The generator now draws independent recapture /
   retake observations from a **second RNG stream** (primary columns are byte-identical to 17.0 —
   checked by `tests/test_scientific_engine.py` against `tests/fixtures/policy_snapshot_17_0.json`).
   Recaptures share the common-mode camera flip of the original frame, so correlated-camera
   scenarios also stress the recapture independence assumption, as 17.1 §4.3 requires.
3. **Ad hoc prior / placeholder likelihoods.** `prior = 0.03·4^votes` and sens/spec
   `0.75/0.85/0.80/0.88/0.95/0.97` were invented. Likelihoods are now **estimated on a held-out
   calibration lot** (`calibration.estimate_likelihoods`, seeds 1000–1009, never used for test)
   and frozen into the run manifest with their counts and Wilson intervals. The old placeholder
   set is kept as `LIKELIHOODS_PLACEHOLDER_17_0` only for the mis-specification ablation.

## Policies under comparison (same rows, same seeds, same free evidence)

| Policy | 17.1 ladder | Free evidence | Extra action | Role in this run |
|---|---|---|---|---|
| `conservative_rules` | B0 | phone, Pi, caliper | none | **reference** for every paired difference |
| `phone_only`, `metrology_only` | — | one source | none | weak single-source controls |
| `safe_mesh_reference` | — | phone, Pi, caliper | none (+cost on disagreement) | 17.0 negative result, kept |
| `collective_fusion` | B3 | phone, Pi, caliper | none | calibrated fusion; **= `voi_driven` minus adaptive step** (ablation) |
| `structured_request_lite` | B5-lite | phone, caliper | one targeted Pi request | 17.1 Gate-A slice, unchanged logic |
| `voi_driven` | B6 | phone, Pi, caliper | ≤1 action chosen by **NetVOI** (expected-loss, cost-aware) | **the registered hypothesis** |
| `entropy_driven` | B6 − cost_awareness | phone, Pi, caliper | ≤1 action chosen by max expected entropy reduction | ablation (17.1 §5.2) |

`voi_driven` and `entropy_driven` use identical posteriors, identical candidate actions
(`phone_recapture`, `pi_recapture`, `caliper_retake`, `NO_ACTION`), identical fresh draws and
identical hold threshold; they differ **only** in the selection criterion. Hold threshold for all
posterior-based policies is the Bayes break-even `hold / (hold + escaped_defect)` from `Costs`.

Oracle columns (`safe`, `surface_defect`, `true_clearance`, `slot`, `tab`, `shared_camera_flip`)
are read only by the evaluator and the calibration estimator, never by a policy.

## Seeds and sizes

- Test: seeds **0–29**, **1000** specimens each, per scenario (the 17.0 registered size).
- Calibration: seeds **1000–1009**, 1000 each, same scenario parameters as the test lot it
  serves (a held-out lot from the same process), except where a scenario says otherwise.
- Bootstrap: 2000 draws, seed 12577, cluster = seed (unchanged from `benchmark.py`).

## Scenario grid (fixed now)

| ID | process_shift_mm | camera_noise | shared_camera_noise | network_outage | Likelihoods | Costs |
|---|---|---|---|---|---|---|
| S01 baseline | 0.10 | 0.04 | 0.00 | 0.05 | calibrated (same scenario) | default |
| S02 no shift | 0.00 | 0.04 | 0.00 | 0.05 | calibrated | default |
| S03 large shift | 0.20 | 0.04 | 0.00 | 0.05 | calibrated | default |
| S04 noisier cameras | 0.10 | 0.10 | 0.00 | 0.05 | calibrated | default |
| S05 very noisy cameras | 0.10 | 0.15 | 0.00 | 0.05 | calibrated | default |
| S06 correlated cameras | 0.10 | 0.04 | 0.05 | 0.05 | calibrated | default |
| S07 strongly correlated | 0.10 | 0.04 | 0.15 | 0.05 | calibrated | default |
| S08 outage-heavy | 0.10 | 0.04 | 0.00 | 0.20 | calibrated | default |
| S09 shift + noise | 0.20 | 0.10 | 0.00 | 0.05 | calibrated | default |
| S10 noise + correlation | 0.10 | 0.10 | 0.10 | 0.05 | calibrated | default |
| S11 placeholder likelihoods | 0.10 | 0.04 | 0.00 | 0.05 | `LIKELIHOODS_PLACEHOLDER_17_0` | default |
| S12 calibration drift | 0.10 | 0.10 | 0.00 | 0.05 | calibrated at **S01** (stale) | default |
| S13 industry cost ratios | 0.10 | 0.04 | 0.00 | 0.05 | calibrated | `INDUSTRY_GROUNDED_COSTS` |

## Endpoints

Primary (paired per seed vs `conservative_rules`, 95% cluster bootstrap over seeds):
1. unsafe-pass rate per all units (count / 1000);
2. total cost per 1000 specimens;
3. released-good rate (throughput guard — an always-HOLD policy must not look good).

Secondary: mean holds, mean inspections, action distribution for `voi_driven`/`entropy_driven`,
rate at which the fresh action flipped the disposition, Brier score of each policy's reported
`p_unsafe` against the oracle `safe` label (where the policy reports one), calibration
estimates with intervals.

## Decision rules (written before running)

For `voi_driven` vs `conservative_rules` **in S01**:
- **Non-inferior on safety** if the upper bound of the 95% CI of the paired unsafe-pass-rate
  difference is ≤ **+0.001** (one extra escape per 1000 specimens).
- **Cheaper** if the 95% CI of the paired cost difference lies entirely **below 0**.
- **Throughput preserved** if the 95% CI of the paired released-good-rate difference has lower
  bound ≥ **−0.01**.

Only if all three hold may the slide say "in the synthetic generator, cost-aware VOI matched the
conservative rule on safety at lower cost". If any fails, the result is reported as negative or
inconclusive, with the numbers. The same three rules are then applied, descriptively, to every
other scenario; no scenario is dropped after the fact.

For the ablation: if `entropy_driven` does **not** cost more than `voi_driven` at equal or worse
safety, the "cost-aware selection matters" claim is **not** supported by this run.

## What this run cannot show

That any of this transfers to a physical lot; that the likelihood model is right for real cameras;
that the cost structure resembles any factory. It can only show whether, under a declared
generator and declared costs, the decision-theoretic step behaves as the mathematics says it
should, and whether that behaviour survives the declared stressors.
