# Assured Physical Sorting and Robot State Machine

**Owner:** HyorinmaruK + adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Hardware boundary
ESP32-S3 board, servo-driven sorting gate, power isolation, chute sensor/beam-break (if available). Servo moves sorting gate, NEVER digital-caliper jaws. Physical routing occurs only after an authenticated bounded request and operator review. A physical STOP switch is required before an actual production pilot.

## Non-negotiable action-state machine
`PROPOSED -> REVIEWED -> AUTHORIZED -> STAGED -> COMMAND_SENT -> SENSOR_ACK -> VERIFIED` (or `HOLD/FAULT/TIMEOUT`). A unit is only counted as physically routed after unique sensor confirmation. Separate inspected parts, confirmed defective parts and physically rejected parts. Match IDs and ensure idempotent replay. No repeated command on retry without observing physical state.

## Current reference
`actuation.py` implements only approval, stage and acknowledgement bookkeeping. It sends ZERO GPIO/servo messages; do not present it as live robot integration. ESP32 firmware and secure transport remain TODO. An LLM is never allowed to call actuation tool or assign final hardware PASS.

## Experiments
Sensor disappears, gate moves partially, wrong bin, duplicate acknowledgment, staged action without authority, unplugged network, loss of power after gate movement, counter drift. Use external independent observation to score route success and reconcile inventory.

## Acceptance
- HOLD default and no unattended physical PASS.
- A single specimen cannot increment two terminal bin counters.
- Hardware operation entirely behind separate authenticated authorization service.

