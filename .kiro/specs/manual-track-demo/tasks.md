# Tasks: QualityRelay manual-track physical demonstration

Execute in dependency order. Do not mark local hardware tasks complete from the cloud sandbox.

## Wave 1 — Repository audit and foundations

- [ ] 1. Inspect existing modules, tests, UI, dependency files, and manifests; map each proposed component to reuse vs new files.
- [ ] 2. Run the existing automated suite without changing code; record actual baseline and resolve the stale 88/102-test metadata discrepancy.
- [ ] 3. Add runtime-data and local-hardware configuration exclusions to `.gitignore` without removing existing rules.
- [ ] 4. Add environment/config models for demo mode, capture directory, fake/real sorter transport, serial port, and baud rate; no secrets or machine paths committed.

## Wave 2 — Deterministic session and evidence models

- [ ] 5. Implement `DemoSession` and the explicit state-transition validator.
- [ ] 6. Implement manual digital-caliper evidence separate from the placeholder potentiometer ADC path.
- [ ] 7. Implement camera capture metadata, hashing, source identity, and quality-result models.
- [ ] 8. Implement fit-test evidence and validation.
- [ ] 9. Add persistence/audit integration with unique event IDs and lineage.
- [ ] 10. Add unit tests for tasks 5–9, including every invalid transition and missing/contradictory evidence case.

## Wave 3 — API and deterministic policy

- [ ] 11. Add `/demo/sessions` create/read endpoints.
- [ ] 12. Add load, caliper, camera, and fit evidence endpoints with state enforcement.
- [ ] 13. Integrate the conservative decision policy for REVIEW_READY/HOLD/PASS_REVIEW/CONFIRMED_REJECT.
- [ ] 14. Return allowed next actions, evidence coverage, evidence tier, and plain-language HOLD reasons.
- [ ] 15. Add API integration tests for ordering, validation, OCR mismatch, camera identity, identical image digests, and HOLD defaults.

## Wave 4 — Operator web workflow

- [ ] 16. Add a visible ordered line: Load → Caliper → Vision → Review → Route → Confirm → Arrival.
- [ ] 17. Add browser permission and two-distinct-camera selection with clear device labels.
- [ ] 18. Add explicit still capture for Webcam A and Webcam B; stop media tracks on teardown.
- [ ] 19. Add manual caliper form, OCR-candidate display if available, and explicit operator confirmation.
- [ ] 20. Add fit outcome form and evidence-status display.
- [ ] 21. Add evaluation action and plain HOLD reason display; never turn an uncalibrated score into millimetres/probability.
- [ ] 22. Add UI tests or deterministic browser fixtures using fake cameras/media where supported.

## Wave 5 — Sorter transport without real hardware dependency

- [ ] 23. Define `SorterTransport`, health, stage, and status result types.
- [ ] 24. Implement `FakeSorterTransport` with success, unavailable, timeout, and malformed-response modes.
- [ ] 25. Implement route staging with unique `action_id`, one outstanding action, decision/origin checks, and no immediate hardware-success claim.
- [ ] 26. Add route-stage/status endpoints and UI states: STAGED, SERIAL_SENT, WAITING_BUTTON, GATE_REPORTED, FAULT.
- [ ] 27. Add unit/integration tests for duplicate actions, invalid decisions, transport failure, timeouts, and no automatic retry.

## Wave 6 — Local real serial adapter and firmware integration

- [ ] 28. Add optional `pyserial` dependency and `SerialSorterTransport` selected only by explicit local configuration.
- [ ] 29. Parse current firmware output robustly or revise the firmware to emit a versioned machine-readable status while retaining safety behavior.
- [ ] 30. Validate only P/H/R output at 115200 baud; sanitize/log errors without secrets or device paths in public responses.
- [ ] 31. Add adapter tests using a fake/in-memory serial object; do not require a USB device.
- [ ] 32. Reconcile `firmware/manual_sorter/esp32_manual_sorter.ino` with the repository's firmware structure and document the `ESP32Servo` dependency.

## Wave 7 — Optional arrival acknowledgement

- [ ] 33. Extend bin ACK schema/firmware to include or correlate `action_id`, specimen ID, actual bin, station, and unique sensor event ID.
- [ ] 34. Persist ACK evidence and call `SorterInterlock.acknowledge()` through the service boundary.
- [ ] 35. Add mismatch, duplicate, unknown-action, and missing-sensor tests.
- [ ] 36. Keep this feature disabled/not verified if physical sensor integration is not completed.

## Wave 8 — Documentation and release validation

- [ ] 37. Add local setup instructions for two webcams, localhost/HTTPS camera access, serial configuration, and runtime directories.
- [ ] 38. Add exact servo/button/external-power wiring and warnings from the physical build guide.
- [ ] 39. Add the three main demonstration runbooks: good/PASS, uncertain/HOLD, visual anomaly/HOLD-or-confirmed-REJECT.
- [ ] 40. Add a manual hardware checklist with blank result fields; do not pre-check it.
- [ ] 41. Run all automated tests and record exact output.
- [ ] 42. Regenerate the file hash manifest and release validation metadata only from the final repository state.
- [ ] 43. Review every UI/status/README claim against actual evidence tiers and remaining gaps.

## Local user-only hardware verification

- [ ] H1. Both Logitech webcams enumerate and remain stable simultaneously.
- [ ] H2. Webcam A clearly captures the caliper display without glare.
- [ ] H3. Webcam B reproduces specimen pose and lighting.
- [ ] H4. ESP32 firmware compiles for the exact board and `ESP32Servo` version.
- [ ] H5. Servo uses external regulated power with common signal ground.
- [ ] H6. P/H/R does not move the servo before button confirmation.
- [ ] H7. Button moves the gate once; a held button does not repeat.
- [ ] H8. Timeout prevents movement.
- [ ] H9. Calibrated angles route to PASS/HOLD/REJECT without mechanical binding.
- [ ] H10. Good, uncertain, and anomaly sessions complete with saved evidence.
- [ ] H11. Optional arrival sensor correlates actual bin or remains explicitly disabled.
