---
inclusion: auto
name: physical-demo
description: Apply when building or modifying the QualityRelay manual track, camera stations, caliper workflow, ESP32 serial bridge, servo diverter, physical evidence, or hardware tests.
---

# Physical demonstration context

## Physical layout

- Base: approximately 800 × 250 mm.
- Manual carrier: approximately 75 × 45 mm for 60 mm coupons.
- Track: 700–800 mm rails with carrier width + 2–3 mm clearance.
- Approximate station centers: load 80 mm, caliper 250 mm, vision 450 mm, decision 600 mm, diverter 700 mm.
- Bins: PASS left, HOLD center, REJECT right.
- Transport is manual; the operator pushes the carrier between hard stops.

## Cameras

- `CALIPER-CAM-A`: Logitech webcam aimed at the digital-caliper display.
- `VISION-CAM-B`: separate Logitech webcam at a fixed top/oblique inspection pose.
- Webcam A provides a visual record/OCR candidate; the operator-confirmed number is authoritative.
- Webcam B provides uncalibrated visual anomaly evidence.
- Every capture needs specimen ID, camera ID, session ID, timestamp, image digest, and capture conditions.
- Do not reuse one image as two sources.

## Servo wiring

- Servo signal: example GPIO 13; verify exact board pinout.
- Servo positive: external regulated supply matched to servo voltage.
- Servo ground: external supply ground.
- External ground connected to ESP32 GND for signal reference.
- Confirmation button: GPIO 32 to GND using `INPUT_PULLUP`.
- ESP32 USB: local computer/powered hub.
- Optional 470–1000 µF capacitor across servo supply near the servo.
- Never power the servo from ESP32 3.3 V or a GPIO.

## Serial protocol

Initial prototype uses 115200 baud and single-character commands:

- `P`: stage PASS position.
- `H`: stage HOLD position.
- `R`: stage REJECT position.

Firmware stages a valid command, waits up to 15 seconds, and moves only on a physical button edge. It prints status messages. The application must never treat writing `P/H/R` as proof that the gate moved or that the specimen arrived.

## Demo state machine

`CREATED → LOADED → MEASURED → VISION_CAPTURED → REVIEW_READY → ROUTE_STAGED → WAITING_PHYSICAL_CONFIRMATION → GATE_MOVED → ROUTED`

Optional later states:

`ROUTED → ARRIVAL_ACKED`

Any invalid order, timeout, missing evidence, camera failure, serial failure, or contradiction goes to HOLD/FAULT without an automatic retry command.

## Main scenarios

1. Comfortable/good specimen: complete evidence, human-reviewed PASS, route to PASS.
2. Tight/uncertain specimen: dimensional or fit uncertainty, route to HOLD.
3. Visible anomaly: visual candidate plus human-confirmed nonconformance; route to REJECT, otherwise HOLD.
4. Camera missing/degraded: HOLD and request recapture.

## Current archive gaps Kiro must preserve or close honestly

- Current hardware station keys are unprovisioned.
- Existing ADC-to-mm range is a placeholder and is not the manual caliper path.
- Existing bin acknowledgement has no `action_id` correlation.
- Existing bin endpoint does not call `SorterInterlock.acknowledge()`.
- Existing hardware endpoint responses are not automatically persisted.
- Existing `actuation.py` emits no GPIO/servo commands.
- Current top-level UI does not provide the complete two-webcam/session workflow.
- Release manifest/test metadata are stale and must be regenerated only after final changes.

Do not hide these gaps. Close them through explicit tasks or label the related capability not implemented.
