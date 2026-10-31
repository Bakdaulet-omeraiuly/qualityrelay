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

## Current code (updated 31 Oct, Bakdaulet)
`vder.py`: binary pedagogical VOI plus `two_axis_action_scores` — one-step NetVOI over the two independent fault axes the generator has (surface, dimensional), scored on the **same** `economics.Costs` the benchmark grades with. `calibration.py`: sensitivity/specificity/priors **estimated on held-out seeds** (1000–1009) and frozen into every run manifest with counts and Wilson intervals; the invented 17.0 constants survive only as `LIKELIHOODS_PLACEHOLDER_17_0` for the mis-specification ablation. `factory.py`: replayable seeded scenarios; a second RNG stream supplies the recapture/retake observations `voi_driven` can pay for, so the 17.0 columns stay byte-identical. `benchmark.py`: scenario, calibration and costs are explicit inputs echoed in the output. Protocol: `docs/research/PROTOCOL_REGISTRATION_31OCT.md` (registered before running), runner `scripts/run_protocol.py`, results `docs/research/PROTOCOL_RUN_31OCT_RESULTS.md`.

## Explicit scope decision: EWMA/SPC and truncated-normal clearance risk are NOT ported (31 Oct)
Checked, not assumed: the 5.0 archive (`legacy/ORIGINAL_5_0_33_FILES.zip`) contains the EWMA / truncated-Monte-Carlo **design text** in its blueprint (λ=0.2, L=3 starting values; conditioning on local acceptance) and no implementation — its only Python file is `cad/generate_stl.py`. So "porting back" would mean writing it new.

Decision for this event: **scope down to the binary two-axis VOI + surface-defect framing**, and do not build EWMA/SPC or the truncated-normal clearance model now. Reasons:
1. `seeded_scenario` draws specimens i.i.d. — there is no process drift over the production index, so an EWMA would alarm on nothing and prove nothing. Adding drift to the generator *and* a detector in the same night would be tuning a detector to a toy we just built.
2. There is no live time series yet. The first real one arrives when HyorinmaruK's repeatability screen and the ESP32 station produce caliper readings in sequence; EWMA parameters are supposed to come from that calibration dataset ("not from only five live points", 5.0 blueprint).
3. The clearance decision already uses the caliper reading against tolerance with a calibrated sensitivity/specificity; the truncated-normal W−T model adds value only when lots are matched by distribution rather than measured per specimen (`matching.py`'s regime), which is not on the demo path.

What this costs us: no drift-onset claim, no lot-pairing probability interval. Both are listed as future work in `CLAIMS_AND_OPEN_WORK.md`. Revisit when (a) a physical time series exists, or (b) the matching module becomes a presented result.

## Acceptance
- All assumptions/version IDs saved in run manifest.
- Retake/no-action candidates explicit.
- Oracle and centralized full-information are separately labeled upper-bound comparators, not strawman baselines.

