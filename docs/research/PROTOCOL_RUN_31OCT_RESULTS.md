# Results — pre-registered synthetic VOI protocol, 31 October 2026

> **Correction (18.1 SCI-02, later 31 Oct):** `structured_request_lite`'s peer-request cost was
> reported but not charged in this run. Re-run with corrected accounting, same seeds:
> `examples/results/protocol_31oct_rerun_18_1/`. Every `voi_driven` verdict below is unchanged;
> the request slice's cost comparisons reverse (now more expensive than fusion in 12/12
> scenarios). See `COLLECTIVE_GATE_A_RESULTS_31OCT.md` section 2. Original files kept unedited.

**Owner:** Bakdaulet. **Tier:** `SIMULATED`, every number. **Registration:**
`PROTOCOL_REGISTRATION_31OCT.md` (committed before the run). **Artefacts:**
`examples/results/protocol_31oct/` — `manifest.json` (commit, code hashes, verdicts), `S01.json` …
`S13.json` (full output incl. per-seed records), `summary.csv`, `paired.csv`. Reproduce with
`python scripts/run_protocol.py` on the manifest's commit; the run is deterministic.

All paired differences are **policy − `conservative_rules`**, mean over 30 seeds × 1000
specimens, 95% cluster-bootstrap CI over seeds. "Unsafe" is escapes per 1000 specimens.

## 1. Registered primary test (S01 baseline): **the "cheaper at matched safety" claim is NOT supported**

| Endpoint | `voi_driven` − rules | Registered rule | Verdict |
|---|---|---|---|
| unsafe-pass rate | **−1.53 / 1000** [−2.13, −0.93] | upper CI ≤ +1.0 | ✅ non-inferior (in fact safer) |
| total cost / 1000 | **+25.0** [−66.7, +116.2] | CI entirely < 0 | ❌ not cheaper |
| released-good rate | **+0.104** [+0.100, +0.107] | lower CI ≥ −0.01 | ✅ preserved (improved) |

Raw S01 counts (30 000 specimens): rules 106 escapes, 197.5 holds/1000, 3000 inspections/1000,
cost 2424.9; `voi_driven` 60 escapes, 95.4 holds, 3918.5 inspections, cost 2450.0.

So the slide may **not** say "VOI cut cost at matched safety". What S01 does show, on
pre-registered endpoints: at statistically indistinguishable cost, one-step cost-aware VOI
released 10.4 pp more good parts and let through 1.5 fewer defective parts per 1000 than the
conservative OR-rule. It bought that by paying for a second caliper reading on **84.5 %** of
specimens (pi recapture 7.4 %, no action 8.2 %), and the fresh evidence flipped the disposition
on 7.4 % of specimens.

**Why it buys a retake almost always — and why that is a limitation, not a feature.** The caliper
is modelled as a *binary* flag (reading < 0.5 mm) with held-out-estimated sensitivity 0.787 /
specificity 0.993. A clean flag leaves a 0.43 % dimensional-miss probability; at an escape cost of
150 that is 0.65 expected loss, and a 0.5-cost retake with independent noise reduces it to ~0.15.
The arithmetic says "measure twice" for nearly every part, so the policy degenerates into a fixed
double-measurement rule on that axis rather than a targeted one. The obvious fix is a continuous
caliper likelihood (how *close* to tolerance the reading was), which would concentrate retakes
on near-tolerance parts. That is **not** in this run; it is the first exploratory item below.
**Update, later on 31 Oct:** the Level-1 digital twin (`DIGITAL_TWIN_RUN_31OCT.md`) shows what this
costs in time — the retakes drive the Caliper station to 99.8 % utilisation and cycle time to 24×
the rule's. Cost-neutral on paper, infeasible on a one-caliper line.

## 2. All scenarios — `voi_driven` vs `conservative_rules` (descriptive, same rules applied)

| ID | Scenario | Δ unsafe /1000 [CI] | Δ cost /1000 [CI] | Δ released-good [CI] | Safety · Cost · Throughput |
|---|---|---|---|---|---|
| S01 | baseline | −1.53 [−2.13, −0.93] | +25.0 [−66.7, +116.2] | +0.104 [0.100, 0.107] | ✅ ❌ ✅ |
| S02 | no shift | +0.27 [+0.13, +0.43] | **−145.7** [−168.9, −121.5] | +0.112 [0.108, 0.115] | ✅ ✅ ✅ |
| S03 | large shift 0.20 | **−10.1** [−11.4, −8.8] | **−1155.8** [−1343.7, −967.2] | +0.019 [0.016, 0.022] | ✅ ✅ ✅ |
| S04 | camera noise 0.10 | −1.77 [−2.37, −1.20] | +44.5 [−42.4, +128.0] | +0.033 [0.030, 0.035] | ✅ ❌ ✅ |
| S05 | camera noise 0.15 | −1.47 [−1.97, −0.97] | +56.4 [−21.1, +130.6] | +0.029 [0.027, 0.032] | ✅ ❌ ✅ |
| S06 | shared camera noise 0.05 | −2.03 [−2.67, −1.43] | +32.0 [−60.5, +119.4] | +0.035 [0.033, 0.038] | ✅ ❌ ✅ |
| S07 | shared camera noise 0.15 | −1.63 [−2.30, −1.00] | +59.7 [−37.6, +154.1] | +0.032 [0.029, 0.034] | ✅ ❌ ✅ |
| S08 | outage 0.20 | −0.80 [−1.37, −0.20] | **−117.0** [−204.2, −30.5] | +0.229 [0.225, 0.233] | ✅ ✅ ✅ |
| S09 | shift 0.20 + noise 0.10 | **−9.00** [−10.2, −7.8] | **−1034.9** [−1216.0, −861.4] | +0.017 [0.015, 0.020] | ✅ ✅ ✅ |
| S10 | noise 0.10 + shared 0.10 | −1.57 [−2.17, −1.00] | +46.2 [−39.6, +128.9] | +0.030 [0.027, 0.032] | ✅ ❌ ✅ |
| S11 | placeholder likelihoods | +0.27 [+0.10, +0.47] | −44.1 [−70.5, −14.1] | +0.042 [0.039, 0.044] | ✅ ✅ ✅ *(hollow — see §4)* |
| S12 | stale S01 calibration on S04 world | −0.33 [−1.13, +0.40] | +48.2 [−71.0, +159.2] | +0.180 [0.176, 0.185] | ✅ ❌ ✅ |
| S13 | industry cost ratios | **+0.80 [+0.53, +1.10]** | **−392.3** [−422.5, −358.3] | +0.108 [0.105, 0.112] | **❌** ✅ ✅ |

Reading: across the camera-noise and camera-correlation family (S04–S07, S10) the picture is the
same as S01 — safer and higher-throughput, not cheaper. VOI is cheaper **and** safer where the
dimensional axis dominates (S03, S09: process shift makes clearance failures common and the
fixed rule cannot adapt) and where the fixed rule wastes holds on `network_down` (S08 — a weak
reason, since no policy here loses evidence when the network is down; the generator only sets a
flag). In S02 the dimensional prior is tiny (0.18 %), retakes stop paying, VOI acts on 7.6 % of
parts only, and the cost saving comes with +0.27 escapes/1000 — inside the margin, not zero.

## 3. Ablations (pre-registered)

**B7 − cost_awareness: `voi_driven` vs `entropy_driven`.** Same posteriors, same candidate
actions, same fresh draws, same threshold; only the selection criterion differs. `entropy_driven`
buys an action on 100 % of parts (always 4000 inspections/1000). `voi_driven` is cheaper in **all
13 scenarios** with CIs excluding zero (S01: −40.8 [−42.1, −39.5] at identical escapes, 60 vs 60).
Where safety differs it goes both ways: S04/S06 VOI safer (−0.6, −0.7 /1000), S11/S13 VOI less
safe (+2.3 /1000). **Supported:** cost-aware selection does something entropy selection does not —
it stops.

**B7 − adaptive_step: `voi_driven` vs `collective_fusion`.** Identical posteriors, no purchase.
S01: cost +69.2 [−35.9, +170.9] (n.s.), unsafe **−1.80 /1000** [−2.50, −1.10]. The adaptive step
buys safety for a non-significant amount of money at baseline. In S03/S09 `collective_fusion` (and
`structured_request_lite`) **collapse to always-HOLD** (released-good = 0.000; 1000 holds/1000)
because the dimensional prior rises to 11.5 % and the combined posterior clears the threshold on
every part — the throughput guard in the registration exists exactly for this, and it fired.
`voi_driven` does not collapse there: it buys the retake and releases 71.9 % of good parts.

## 4. Calibration matters, in both directions

- **S11 (invented 17.0 likelihoods):** `voi_driven` chose `NO_ACTION` on **100 %** of specimens
  — the placeholder sensitivities made every test look worthless, so the policy silently became
  `collective_fusion`. Its "✅ ✅ ✅" row is therefore hollow: the mechanism was switched off, not
  vindicated. This is the concrete reason the exploratory "~27 % cheaper" figure from the
  night-before note is void.
- **S12 (stale calibration):** likelihoods estimated at camera noise 0.04 applied to a 0.10 world.
  The policy over-trusts the cameras, releases far more (+18.0 pp vs +3.3 pp for the correctly
  calibrated S04 run) and still lands non-inferior on safety here (−0.33 [−1.13, +0.40]). Brier is
  flat (0.0269 vs 0.0268), so Brier alone would not have caught the drift — the released-good
  jump is the warning sign. Do not read "survived one drift scenario" as "robust to drift".
- Held-out estimates vs generator truth at S01: phone sens/spec 0.967/0.961, Pi 0.941/0.958
  (generator: 0.96/0.96); caliper 0.787/0.993; priors 6.49 % / 1.99 %. Counts and Wilson
  intervals are in each scenario JSON under `calibration`.

## 5. S13 is the most important negative row

Under the published 1-10-100 cost ratios (`INDUSTRY_GROUNDED_COSTS`: escape 100, hold 5,
inspection 1), the Bayes threshold moves from 1.3 % to 4.8 %, retakes stop paying (inspections
3074/1000), and `voi_driven` releases more aggressively: **+0.80 escapes/1000 [+0.53, +1.10]**,
upper bound above the registered +1.0 margin → **fails safety**, while saving 392/1000 in modelled
cost. Nothing is broken; this is the loss function doing what it was told. The lesson for the
deck: **the cost table is a safety-relevant input.** Whoever sets `escaped_defect` and `hold` is
setting the escape rate. That must be the factory's quality owner, with the margin written down —
not a default in `economics.py`.

## 6. Also confirmed in passing

- The 17.0 negative result is reproduced to the digit: `safe_mesh_reference` − rules cost
  **+37.93** [36.43, 39.37], unsafe 0.0 — the second RNG stream left the 17.0 columns untouched.
- `structured_request_lite` (Pi requested on ~90 % of parts) is cheaper than `collective_fusion`
  in every scenario (S01: −48.1) at identical dispositions, as the integration note reported —
  unchanged by recalibration except in S13, where the higher threshold makes its one-bit band
  miss and it stops requesting entirely (inspections 2000/1000, +2.93 escapes/1000 vs rules).

## 7. What may be said on stage (and what may not)

May: "In a declared synthetic generator with held-out-calibrated likelihoods, one-step cost-aware
VOI released 10 pp more good parts and let 1.5 fewer defects per 1000 through than the conservative
OR-rule at statistically the same modelled cost; it was cheaper only where clearance failures
dominate or the rule wastes holds on outages; cost-aware selection beat entropy selection on cost
in all 13 scenarios; and under industry cost ratios it traded safety for cost and failed our
pre-set margin. Everything is `SIMULATED`."

May not: any factory number; "VOI reduces cost"; anything from the 10-seed exploratory note; any
claim that the likelihoods describe a real camera.

## 8. Exploratory follow-ups (NOT part of this run; label as such if attempted)

1. Continuous caliper likelihood (reading distance to tolerance) → targeted retakes instead of
   near-universal ones; re-run S01 under the same seeds and report alongside, not instead.
2. Multi-step (non-myopic) purchase with a per-part budget; compare against the one-step policy.
3. A safety-constrained variant: minimise cost subject to posterior escape probability ≤ a fixed
   bound, instead of a pure expected-loss trade — this is how a quality owner would actually
   want to express S13's lesson.
4. Physical: replace `calibration.py`'s synthetic table with repeatability-screen data from
   HyorinmaruK's caliper station (EXPERIMENT_PROTOCOL.md §Data collection) before any
   `PHYSICAL_CAPTURE`-tier number is shown.
