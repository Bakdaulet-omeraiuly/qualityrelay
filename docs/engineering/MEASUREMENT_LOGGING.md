# Measurement logging and the CSV handoff

Capture detailed caliper measurements of each specimen (width, length, per-side heights,
and for slots the inner width, rail widths and base length) into one CSV, so the data can
later feed an agent that proposes code or tolerance updates. This document covers the
tools and the CSV schema. It does **not** build that downstream agent.

## Tools

| Tool | What it does |
|---|---|
| [`web/measurement_logger.html`](../../web/measurement_logger.html) | Browser page: enter measurements per specimen, optionally capture a camera still (visual record only), export the CSV. Open the file directly, or serve from localhost/https for the camera and the ESP32 serial link. |
| [`docs/engineering/templates/specimen_measurements.csv`](templates/specimen_measurements.csv) | The empty CSV with the canonical header. |
| [`scripts/summarize_measurements.py`](../../scripts/summarize_measurements.py) | Standard-library summary: per specimen/feature min/max/mean/spread and deviation from nominal; flags critical dimensions outside tolerance. Writes JSON with `--json`. |
| [`firmware/measurement_station/esp32_measurement_station.ino`](../../firmware/measurement_station/esp32_measurement_station.ino) | Optional: a spare ESP32 that sends each reading to the logger over USB. |

## Honesty rules (from AGENTS.md)

- The operator-confirmed digital-caliper reading is authoritative. A camera image is a
  visual record, never a millimetre measurement.
- A reading from the ESP32 is `PHYSICAL_CAPTURE` evidence; a typed, confirmed reading is
  `OPERATOR_CONFIRMED`. Neither sets a verdict by itself.
- The summarizer and the logger only record and describe data. They change no code,
  nominal, or tolerance.

## CSV schema (tidy / long: one row per reading)

`timestamp_iso, specimen_id, manual_id, part_type, feature, location, reading_no,
value_mm, nominal_mm, deviation_mm, unit, instrument_id, calibration_id, operator_id,
method, image_file, image_sha256, evidence_tier, notes`

- `part_type`: `slot | tab | bar`.
- `feature`: `length | width | slot_inner_width | outer_width | rail_width | base_length | height`.
- `location`: `near | mid | far` (along the length), `left | right` (rails),
  `corner_FL | corner_FR | corner_BL | corner_BR` (heights), or `overall`.
- `method`: `caliper_manual | caliper_data_output | potentiometer_adc | camera_uncalibrated`.
- `nominal_mm` / `deviation_mm` are filled automatically for known parts (S-GOOD, T-RISK, …).

Excel opens the CSV directly (it is written UTF-8 with a BOM); use a pivot table to view,
say, width by location per specimen.

## Using it

**By hand (no electronics):** pick the part, type the three width positions, the length,
and the four corner heights, then "Add specimen to log". Export when done. The breadboard
tab explains that no wiring is needed for this.

**With a spare ESP32 (optional):** flash `esp32_measurement_station.ino`, click
"Connect ESP32 (USB)" in the logger (Chrome/Edge, localhost/https), and press the board's
button to send each reading. Two sensing options, detailed on the page's Breadboard tab:

- **Option A — potentiometer / linear gauge:** reliable to wire, must be calibrated, lower
  precision; reuses `potentiometer_to_mm()` in `qualityrelay17/hardware_ingest.py`.
- **Option B — digital caliper data port:** precise but experimental (~1.5 V logic, needs
  level shifting and brand-specific decoding); left as a firmware stub.

## Summarize

```bash
python3 scripts/summarize_measurements.py measurements.csv --json summary.json
```

Prints a per-specimen table and flags critical features outside the tolerance
(`--tol`, default 0.15 mm) or repeatability limit (`--spread`, default 0.05 mm).

## Handoff to a later agent (not implemented here)

A downstream agent could read the CSV (or the summary JSON), compare measured means to
`nominal_mm`, and propose updates — for example new nominal/tolerance constants or decision
thresholds. Keep the raw CSV so every proposed change traces back to real readings, and
treat any change as a proposal for human review, not an automatic re-tune of the policy.
