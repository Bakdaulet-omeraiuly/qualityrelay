# Innovations I1–I9: results (Bakdaulet, 31 Oct evening)

Registration: `INNOVATIONS_REGISTRATION_31OCT.md` (committed before each run). Data:
`examples/results/innovations_31oct/`. Everything is **SIMULATED** unless marked otherwise. Tests:
`pytest` 255 passed.

## Scientific

### I1. Self-correcting factory: inspection → printer feedback (EWMA). **Positive.**
- **Design:** bayes + FIFO with feedback vs without, 20 paired seeds, the SIM decision rules.

| scenario | good/h | escapes /1000 shipped | good parts scrapped / run | cost / good unit | all 3 rules |
|---|---|---|---|---|---|
| F01 nominal (do-no-harm check) | 198.5 → 197.9 | 1.94 → 2.07 (CI includes 0) | 0.4 → 0.5 | 1.456 → 1.475 | no (neutral, as hoped) |
| F02 drift 0.15 mm/h | **154.4 → 195.1** | **4.96 → 2.59** | 3.85 → 0.60 | 2.035 → 1.568 | **yes** |
| F03 warping burst | 175.0 → 187.9 | 3.52 → 2.48 | 1.55 → 0.95 | 1.773 → 1.576 | yes |
| M05 supplier bias +0.15 mm | 66.0 → 66.5 | **5.38 → 2.60** | 1.55 → 0.60 | 3.294 → 2.815 | yes |

- **Root-cause alarms (I6, CUSUM):** the median first alarm came at about 39 min under drift
  and about 5 min for the biased supplier. Nominal runs mostly raise no alarm.
- **Disclosed:** the controller gain was lowered after a seed-0 smoke run showed it chasing noise
  in F01.

### I2. Statistical guarantee on false PASS (conformal risk control). **Positive, with an honest limit.**
- **Expectation guarantee:** at target 2/1000, averaged over 20 independent calibration sets of
  10 000 parts, the realised false-PASS rate was:
  - S01: **1.67 [1.40, 1.95]**;
  - S02, recalibrated: 2.06 [1.94, 2.18], at the target.
  - It also turns spare safety into throughput: released good 0.809 → 0.843 at S01.
- **Per-batch (PAC, δ 0.1) variant:** 5% of calibration sets exceeded the target (≤ δ, as
  guaranteed). It still releases more good parts than the Bayes threshold at S01 (0.828 vs 0.809).
- **Limit:**
  - Calibrating on nominal data and deploying under drift breaks the guarantee: 6.7/1000.
  - Under shared camera lighting (S04), no threshold meets 2/1000, so the method holds everything.
  - That is the correct signal that the probability model is wrong there (see I5).

### I4. Importance sampling for rare escapes (NVIDIA Warp). **Limited.**
- **Unbiased:** the estimates match the naive 10⁷-part run (tested).
- **Variance reduction:** about 3× only where the surface-defect mode dominates (S04).
- **Where it does not help:** for the dimension-driven escapes at S01, tilting the defect and
  camera rates gives no gain, and a naive clearance tilt makes the variance worse (0.1–0.2×).
- **Next:** a better proposal (e.g. cross-entropy-tuned) is the next step, not a result.

### I5. Common-mode camera model. **Trade-off.**
- **Fit:** the mixture likelihood with a shared-flip probability, fitted by MLE on labelled
  held-out lots, recovers c = 0.15 at S04 and c = 0 at S01.
- **S04:** unsafe PASS 8.09 → **7.11 /1000** (±0.05), but released good falls 0.689 → 0.624.
- **S01:** identical to the independent model (no cost).
- **Reading:** it is safer only because it trusts camera agreement less, which costs throughput.

## Technological

### I3. Width from an iPhone photo (ArUco marker). **Works on synthetic photos; physical validation pending.**
- **Method:** a printable marker sheet (`examples/aruco/marker_sheet_20mm.png`) gives the scale.
  The photo is rectified, and the mid-length cross-section is read with sub-pixel edges, the same
  rule used for the CAD meshes.
- **v1 failed** the pre-set bar of MAE ≤ 0.10 mm (0.14–0.15 mm at 12–15 px/mm).
- **v2 on fresh seeds:** MAE 0.114 / **0.072 / 0.037 mm** at 12 / 15 / 25 px/mm, so the bar is met
  from 15 px/mm. An iPhone photo with the part filling the frame is about 25 px/mm.
- **Integration:** wired into the camera panel ("width from photo").
- **Label:** `UNVALIDATED` until the readings are compared with the caliper (PHY-03).

### I6. Part passport (QR)
Every part in the inspector has a QR code that reopens that exact part, run and evidence chain.
Phones on the same network need the server started with `--host 0.0.0.0`.

### I7. Plain-language explanation
- **What it is:** a deterministic, evidence-grounded explanation of each decision, built from the
  same numbers as the inspector. It includes whether the decision was right, when ground truth is
  shown.
- **LLM:** a narration layer is `NOT_CONFIGURED`. No API key is available, and untested API code
  was not added.

### I8. Live mode
- `POST /sim/live/event` (shared event-contract fields) and `GET /sim/live/stream` (Server-Sent
  Events, no new dependency).
- Physical station events flash the station in 3D and appear in the "Live station events" panel.
- They are **displayed, never acted on**, and marked `verified: false`. Authenticated ingest is
  adilnurgg's BACK-01.

### I9. Active learning for photo labelling
- `GET /sim/vision/suggest` ranks unlabelled photos by how close their measured width is to the
  clearance decision boundary.
- The most informative photos are labelled first, and photos with no marker come last.
- The camera panel shows the top three after each save.

## Not done (would be dishonest to claim)
- **Core ML on-device model:** needs a model trained on real photos first.
- **Omniverse Replicator:** needs an RTX GPU host.
- **Both** stay `NOT_CONFIGURED`.

## Claims the pitch may add (simulated, with scenario IDs)
1. "Feeding caliper measurements back into the printers cut escapes from 5.0 to 2.6 per 1000 and
   raised good output by 26% under process drift (F02)."
2. "A conformal threshold keeps false passes at or below 2 per 1000 on average when calibrated on
   the same line. If the line changes and the model no longer fits, it stops the line instead of
   guessing."
3. "Width from a single iPhone photo with a printed marker: 0.04–0.07 mm error on synthetic photos.
   Real-photo accuracy is being validated against the caliper."
