# Requirements: QualityRelay manual-track physical demonstration

## R1 — Demonstration session

**User story:** As an operator, I want one session per physical specimen so measurements, images, decisions, and routing cannot be mixed between parts.

- WHEN an operator creates a session, THE SYSTEM SHALL assign a unique session ID and require a unique specimen ID.
- WHEN an event is submitted for a different specimen or completed session, THE SYSTEM SHALL reject it without changing session state.
- WHEN the operator views a session, THE SYSTEM SHALL show current station, evidence availability, decision status, staged route, and actual route status separately.

## R2 — Ordered station flow

**User story:** As an operator, I want the interface to follow the physical line order.

- WHEN a new session starts, THE SYSTEM SHALL begin at LOAD.
- WHEN required evidence for the current station is accepted, THE SYSTEM SHALL enable the next station.
- WHEN a station is skipped or submitted out of order, THE SYSTEM SHALL reject the transition and keep or place the session in HOLD.
- WHEN the carrier moves physically, THE SYSTEM SHALL require the operator to confirm the station transition; it shall not infer movement from elapsed time.

## R3 — Manual caliper evidence

**User story:** As a quality operator, I want to record a real digital-caliper value with context and confirmation.

- WHEN the operator submits a caliper reading, THE SYSTEM SHALL require value in millimetres, operator ID, instrument ID, calibration/reference ID, uncertainty/repeatability value, and explicit confirmation.
- WHEN Webcam A supplies an image or OCR candidate, THE SYSTEM SHALL store it as supporting evidence and require the operator-confirmed number separately.
- WHEN OCR and operator values differ, THE SYSTEM SHALL HOLD the session and show the discrepancy.
- WHEN no operator confirmation exists, THE SYSTEM SHALL NOT mark metrology verified.
- WHEN a value is outside configured plausible bounds, THE SYSTEM SHALL reject it and retain an audit entry.

## R4 — Two distinct camera sources

**User story:** As a reviewer, I want camera evidence to retain source identity.

- WHEN cameras are configured, THE SYSTEM SHALL allow the operator to select distinct device IDs for `CALIPER-CAM-A` and `VISION-CAM-B`.
- WHEN the same device or identical image digest is presented as both sources, THE SYSTEM SHALL flag shared-source evidence and HOLD.
- WHEN a capture is accepted, THE SYSTEM SHALL record specimen ID, camera ID, session ID, timestamp, image digest, image dimensions, and quality result.
- WHEN camera permission is unavailable, a device disconnects, or image quality is unusable, THE SYSTEM SHALL HOLD and request recapture.
- THE SYSTEM SHALL label visual scores uncalibrated and SHALL NOT convert them to millimetres or defect probability.

## R5 — Fit evidence

**User story:** As an operator, I want to record the actual slot/tab fit separately from dimensional and visual evidence.

- WHEN a fit test is performed, THE SYSTEM SHALL record pair IDs, predefined criterion, operator, and PASS/FAIL/INDETERMINATE outcome.
- WHEN the fit result is INDETERMINATE or absent, THE SYSTEM SHALL prevent automatic PASS.
- THE SYSTEM SHALL retain the raw fit result without overwriting it with a model prediction.

## R6 — Deterministic review decision

**User story:** As a safety reviewer, I want missing or contradictory evidence to fail safely.

- WHEN required metrology, vision, fit, identity, freshness, or signature evidence is missing or invalid, THE SYSTEM SHALL decide HOLD.
- WHEN any required source indicates uncertainty or disagreement, THE SYSTEM SHALL decide HOLD or request human review.
- WHEN PASS is proposed, THE SYSTEM SHALL require configured measurement acceptance, usable vision evidence, fit confirmation, and explicit human authorization.
- WHEN REJECT is proposed from a visual candidate, THE SYSTEM SHALL require human-confirmed nonconformance; otherwise it SHALL use HOLD.
- THE SYSTEM SHALL not allow an LLM response to set the final route directly.

## R7 — Route staging

**User story:** As an operator, I want to stage a route without immediately moving hardware.

- WHEN an authorized review produces PASS, HOLD, or REJECT, THE SYSTEM SHALL create a unique `action_id` and stage the corresponding P, H, or R command.
- WHEN an `action_id` is duplicated, THE SYSTEM SHALL reject the duplicate without emitting a second serial command.
- WHEN the session is not in REVIEW_READY or the origin is not verified physical/human reviewed, THE SYSTEM SHALL refuse staging.
- WHEN a route is staged, THE SYSTEM SHALL display WAITING FOR PHYSICAL CONFIRMATION.

## R8 — Local serial bridge

**User story:** As a developer, I want hardware IO isolated behind a testable adapter.

- THE SYSTEM SHALL define a serial transport interface and provide fake and real implementations.
- WHEN automated tests run, THE SYSTEM SHALL use the fake transport and require no physical serial device.
- WHEN real transport is disabled or unconfigured, THE SYSTEM SHALL refuse hardware IO and report a clear local-configuration error.
- WHEN a valid route is staged locally, THE SYSTEM SHALL write only P, H, or R at 115200 baud to the configured port.
- WHEN serial open/write/read fails or times out, THE SYSTEM SHALL set route state FAULT/HOLD and SHALL NOT retry movement automatically.

## R9 — Physical confirmation

**User story:** As an operator, I want a physical button to remain the final movement authority.

- WHEN the ESP32 receives P, H, or R, THE FIRMWARE SHALL stage the target without moving the servo.
- WHEN the physical button is pressed within the stage timeout, THE FIRMWARE SHALL move to the configured angle once and consume the staged route.
- WHEN the timeout expires, THE FIRMWARE SHALL discard the staged route and not move.
- WHEN the button is pressed without a staged route, THE FIRMWARE SHALL not move.
- THE APPLICATION SHALL distinguish command staged, physical confirmation observed, gate movement reported, and specimen arrival acknowledged.

## R10 — Servo safety and configuration

- THE DOCUMENTATION SHALL require an external regulated servo supply and common signal ground.
- THE DOCUMENTATION SHALL prohibit servo power from ESP32 GPIO/3.3 V.
- WHEN angle configuration is invalid or outside a safe configured range, THE FIRMWARE OR LOCAL BRIDGE SHALL refuse it.
- THE SYSTEM SHALL start with HOLD as the neutral demonstration position.
- THE SYSTEM SHALL not implement powered-conveyor motor control in this scope.

## R11 — Optional arrival acknowledgement

**User story:** As a reviewer, I want requested route and actual arrival kept separate.

- WHEN optional bin sensing is enabled, THE SYSTEM SHALL require `action_id`, specimen ID, actual bin, unique sensor event ID, and station ID.
- WHEN actual bin differs from staged bin, THE SYSTEM SHALL raise ROUTE_MISMATCH and SHALL not increment the requested-bin count.
- WHEN a sensor event or action acknowledgement is replayed, THE SYSTEM SHALL ignore it idempotently.
- WHEN no arrival acknowledgement exists, THE SYSTEM SHALL show route unconfirmed rather than infer success.
- This requirement MAY remain disabled in the first milestone but its API shall not claim completion.

## R12 — Audit and evidence tiers

- WHEN any session event occurs, THE SYSTEM SHALL append an immutable audit entry with actor/source, timestamp, session ID, specimen ID, event type, and parent IDs.
- WHEN a record is simulated, test-fixture, physical capture, or verified physical, THE SYSTEM SHALL display the corresponding tier.
- WHEN evidence is derived from another capture, THE SYSTEM SHALL retain source lineage and not count it as an independent sensor.
- THE SYSTEM SHALL keep runtime captures, secrets, and machine-specific serial configuration outside version control.

## R13 — Operator interface

- THE INTERFACE SHALL present the line in order: Load, Caliper, Vision, Review, Route, Confirm, Arrival.
- THE INTERFACE SHALL show only actions valid for the current state.
- THE INTERFACE SHALL show missing evidence and HOLD reasons in plain language.
- THE INTERFACE SHALL provide separate controls for capture, operator confirmation, evaluation, route staging, and status refresh.
- THE INTERFACE SHALL remain usable when real hardware is disabled by using clearly labeled simulation/fake-transport mode.

## R14 — Verification

- THE AUTOMATED SUITE SHALL test normal transitions, every invalid transition, duplicate IDs, missing cameras, identical images, OCR mismatch, serial failure, timeout, duplicate route, and route mismatch.
- THE AUTOMATED SUITE SHALL not require webcam, serial, ESP32, servo, or network hardware.
- THE PROJECT SHALL provide a manual local checklist for camera selection, caliper capture, serial connection, physical button, gate angles, and three-bin routing.
- KIRO WEB SHALL NOT mark manual hardware checks passed without results supplied by the user.
