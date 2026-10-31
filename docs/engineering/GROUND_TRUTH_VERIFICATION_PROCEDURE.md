# Ground-truth verification procedure (BACK-02)

**Who runs it:** a provisioned human operator (HyorinmaruK at the bench, or any team member who holds an
operator token). **Who owns the code:** adilnurgg (`qualityrelay17/verification.py`, `ledger.py`, `api.py`).

## What this procedure is for

A station-authenticated reading tells you *which device sent this number*. It does not tell you that the
number is right. `VERIFIED_PHYSICAL` means **both**: the reading came from an authenticated, calibrated
station, **and** a person checked the same physical part independently and the check agreed.

The server enforces this as follows:

- No station, ingest adapter, model or LLM can write `VERIFIED_PHYSICAL`. `EvidenceLedger.append` refuses it.
- A reading's *stored* origin never changes. Its *effective* origin (`GET /evidence/{event_id}/status`)
  becomes `VERIFIED_PHYSICAL` only after an agreeing check is recorded under one of the procedures below.
- A reading is a **candidate** only if all of these hold: the stored origin is `PHYSICAL_CAPTURE`; it arrived
  through a verified device envelope (BACK-01) from the same station it names; its gateway signature still
  verifies; and it has a `calibration_id`. Anything else stays `PHYSICAL_CAPTURE`, has status `UNVERIFIED`,
  and the verify call is refused with `409`. That covers unsigned and raw readings, imports from before
  BACK-02, and readings with no calibration id.
- A disagreeing check is recorded as `DISPUTED` and **latches**. A later agreeing check does not clear it.
  Take a new reading instead.
- PASS and REJECT routes need at least one cited `VERIFIED_PHYSICAL` record and no cited `DISPUTED` one
  (`api.evidence_gate`). A HOLD route needs only an authenticated physical capture of the same specimen.

## Before you start

1. Get an operator token: `python scripts/provision_station_keys.py --operators <yourname>`, then
   `--show-operator-token <yourname>` to print it once. Keep it out of chat, docs and git.
2. Run the repeatability screen first (`PHYSICAL_TEST_PLAYBOOK.md` section 1). The station's `uncertainty_mm`
   must come from that screen. If it does not, the agreement test below means nothing.
3. Choose a reference instrument other than the station's own sensor. For Tier A, where the station value
   is typed in from a caliper, use a **different** caliper or a gauge block, and if possible a different
   person from whoever produced the station reading.

## GT-CAL-01

**Independent reference-instrument re-measurement.** Applies to `CALIPER` evidence.

1. Find the reading: `GET /evidence/{event_id}/status`. Check that `candidate_for_verified_physical` is `true`.
2. Pick up the physical part. Read its label or QR code. This value is your `observed_specimen_id`. Never
   copy it from the screen. If it differs from the reading's `specimen_id`, the server refuses the check,
   because a check of a different part proves nothing.
3. Measure the same feature with the reference instrument. Record:
   - `reference_value_mm`: your reading.
   - `reference_uncertainty_mm`: the reference instrument's own repeatability (sample standard deviation over
     10 reseated reads) or its certificate value, whichever is larger.
   - `reference_instrument_id`: its serial or asset number.
   - `reference_calibration_id`: its certificate or check id. "none" is allowed but will be visible in the audit.
4. Do this within **24 hours** of the original reading. The server refuses older readings, because the part
   may have changed (warping, wear).
5. Submit:

   ```
   curl -X POST http://<server>:8000/evidence/<event_id>/verify \
     -H "Authorization: Bearer $QR_OPERATOR_TOKEN" -H "Content-Type: application/json" \
     -d '{"procedure_id":"GT-CAL-01","observed_specimen_id":"S-7","reference_value_mm":20.01,
          "reference_uncertainty_mm":0.01,"reference_instrument_id":"mitutoyo-500-196-SN123",
          "reference_calibration_id":"cert-2026-07","notes":"second operator, gauge-block checked"}'
   ```

**Agreement test (recorded in full):** `|station − reference| ≤ k · √(u_station² + u_reference²)`, with
`k = 2` (about 95 % coverage if both errors are roughly normal). Pass → `CONFIRMED`. Fail → `DISPUTED`.
The response records the difference, the band and `k`, so any reviewer can recompute the result.

## GT-VIS-01

**Human visual inspection against a drawing or reference specimen.** Applies to `PHONE_IMAGE`, `PI_IMAGE`,
`CAD_IMAGE` and `ASSEMBLY` evidence.

1. Same specimen-identity step as GT-CAL-01: read the label from the part itself.
2. Inspect the part (not the image) against the drawing or a known-good reference specimen, under the
   lighting written down in the station's calibration record.
3. Submit `{"procedure_id":"GT-VIS-01","observed_specimen_id":...,"observed_verdict":"clear"}`, using the same
   verdict vocabulary as the evidence (`clear` / `suspect` / `unusable`, or `pass` / `fail` for ASSEMBLY).
   If your verdict equals the recorded verdict → `CONFIRMED`. Otherwise → `DISPUTED`.

No upload path for these image kinds is device-authenticated today, so in practice none of them is a
candidate yet. The procedure is written down now so that the rule is already in place when those
stations get envelopes.

## What this does **not** establish

- It is not an MSA or gauge R&R study. One agreeing check verifies one reading, not the instrument.
- It does not prove the operator is honest. It records **who** checked, **with what**, and **when**, in an
  append-only table, so the claim can be audited and challenged.
- Synthetic, simulated and `TEST_FIXTURE` records are never candidates. The rehearsal script's checks use the
  reading itself as the "reference". They exercise the server path and are labelled `TEST_FIXTURE` in
  their notes.
