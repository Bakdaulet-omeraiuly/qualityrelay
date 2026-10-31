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

