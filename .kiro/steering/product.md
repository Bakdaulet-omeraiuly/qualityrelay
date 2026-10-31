---
inclusion: always
---

# Product overview

## Product

QualityRelay is a research-grade manufacturing evidence and decision prototype. The physical demonstration moves labeled 3D-printed slot/tab specimens through measurement, vision, governed review, and a human-authorized sorting gate.

## Demonstration goal

Make one complete physical specimen journey visible and auditable:

1. Load a labeled specimen in a manually pushed carrier.
2. Stop at a digital-caliper station.
3. Capture the caliper display with Webcam A and require operator confirmation of the numeric value.
4. Stop at a visual-inspection station and capture the specimen with Webcam B.
5. Combine measurement, visual, fit, provenance, and availability evidence in a deterministic safety policy.
6. Stage PASS, HOLD, or REJECT without moving hardware.
7. Require a physical button press.
8. Move an ESP32-controlled servo diverter to the selected bin.
9. Optionally correlate an independent arrival-sensor event with the staged action.

## Target users

- Demonstration operator.
- Quality/manufacturing engineer reviewing evidence.
- Team member maintaining backend, frontend, or embedded firmware.
- Judge observing how evidence and physical action remain separated and auditable.

## Success criteria

- The operator can see the active specimen and station.
- Raw caliper values, operator confirmation, both camera sources, and fit outcome remain distinguishable.
- Missing or conflicting evidence produces HOLD.
- PASS cannot be emitted solely from a camera or LLM response.
- A route is staged before hardware is involved.
- Servo movement requires physical confirmation.
- The recorded actual route is not silently inferred from the requested route.
- Every result is labeled as simulated, test fixture, physical capture, or verified physical.

## Explicit non-goals

- No powered conveyor in the approved scope.
- No servo-driven caliper jaws.
- No claim that RGB images measure 0.1 mm.
- No trained Hailo/NVIDIA model unless compatible weights and real execution evidence are later supplied.
- No unattended production PASS.
- No industrial certification, ROI, or factory-readiness claim.
- No deployment of a raw serial or actuator endpoint to the public internet.
