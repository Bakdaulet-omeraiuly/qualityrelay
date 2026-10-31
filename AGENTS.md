# QualityRelay repository instructions

Read the files in `.kiro/steering/` and `.kiro/specs/manual-track-demo/` before changing code for the physical demonstration.

## Non-negotiable rules

- Preserve existing user changes and historical archives.
- Do not claim physical validation, Hailo/NVIDIA inference, automated conveyor operation, or industrial readiness without corresponding evidence.
- Default to HOLD whenever required evidence is missing, stale, duplicated, malformed, uncalibrated, or contradictory.
- A camera score is not a millimetre measurement or calibrated probability.
- A digital-caliper value becomes verified only after operator confirmation and a recorded instrument/calibration context.
- An LLM, image model, or browser script must never directly actuate the servo.
- Route commands must pass through deterministic validation, be staged, and require a physical button press before movement.
- Never power a servo or motor from an ESP32 GPIO or 3.3 V pin.
- Never connect a DC motor directly to an ESP32. A future powered conveyor requires a compatible driver, supply, stop switch, sensors, and fault states.
- Keep secrets, raw private images, local serial-port names, and machine-specific settings out of committed source.
- Hardware-in-loop tests are local/manual. Kiro Web must label them NOT RUN until the user supplies the results.

## Implementation priorities

1. Preserve and pass the existing automated suite.
2. Add deterministic session/state and evidence models.
3. Add two-camera browser workflow and manual caliper confirmation.
4. Add a mocked serial transport and full automated tests.
5. Add the real local serial adapter behind configuration.
6. Add human-confirmed servo routing.
7. Add optional arrival acknowledgement only after `action_id` correlation and idempotency exist.

Do not begin a motorized conveyor implementation unless the user explicitly changes the approved scope.
