# Innovations 1–5: pre-registration (Bakdaulet, 31 Oct evening)

Committed BEFORE each run. Everything is `SIMULATED` unless a section says otherwise.

## I1. Closed-loop printer correction (EWMA) + I6 root-cause alarms (CUSUM)
- **Mechanism:** after each supplier caliper reading, the process residual (measured − nominal −
  applied offset, clipped to ±0.2 mm) updates an EWMA (λ 0.1) per (site, part kind). Outside a
  0.05 mm dead band the printer offset is set to −EWMA (minimum step 0.02 mm). A two-sided CUSUM
  (k 0.5σ, h 5σ) on the same residuals raises alarms.
- **Parameters:** fixed after one seed-0 smoke run (λ 0.2 / dead band 0.03 chased noise in F01;
  disclosed).
- **Design:** bayes + FIFO, feedback none vs ewma. Same parts (latent-width truth hash), seeds 0..19.
  Scenarios F01 (nominal: must not hurt), F02 (drift), F03 (warping), M05 (supplier bias).
- **Rules** (same as SIM): safety (escape CI ≤ +1/1000), throughput (good/h CI ≥ −2%), cost
  (cost/good CI < 0). Claim "feedback helps" only where all three hold. F01 is the do-no-harm check.

## I2. Conformal risk control of the false-PASS rate
- **Method:** conformal risk control (Angelopoulos et al., 2022). Pick the largest p_unsafe
  threshold λ with (n/(n+1))·R̂(λ) + 1/(n+1) ≤ α, where R = P(part unsafe AND passed). Target
  α = 0.002 (2/1000).
- **Calibration:** 10 000 held-out parts (seeds 2000–2009) with simulated ground truth. Physically,
  this needs verified labels; that is stated, not assumed.
- **Test:** 30 lots × 1000 (seeds 0..29) on S01 (exchangeable), S04 (shared lighting) and S02
  (drift), calibrated on S01 versus recalibrated per scenario. Report the realised false-PASS rate
  with its CI and the throughput cost. Expectation stated in advance: the guarantee holds when
  calibration and test are exchangeable, and may break under shift.

## I3. Width from an iPhone photo with an ArUco marker
- **Synthetic validation only** in this session (rendered images with known mm, perspective, blur,
  noise). The pass bar is set now: mean absolute error ≤ 0.10 mm at ≥ 12 px/mm. Physical
  validation against the caliper is pending (PHY-03).

## I4. Importance sampling for rare escapes (NVIDIA Warp)
- Tilt the surface-defect and camera-error probabilities in the kernel and re-weight by the
  likelihood ratio. Success = the same estimate (within CI) as the naive 10⁷ run, with a smaller CI
  at equal parts.

## I5. Correlated-camera (common-mode) posterior
- Mixture likelihood with a common-flip probability c, estimated on held-out calibration lots.
  Compare its unsafe-PASS against B1 (independent cameras) on S04 and S01, using the Warp kernel,
  paired, 10⁷ parts. A win on S04 must not cost more than 1/1000 on S01.
