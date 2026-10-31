# Initial Kiro Web prompt

Implement the QualityRelay manual-track physical demonstration using the repository's existing code and the supplied Kiro steering/spec files.

First read:

- `AGENTS.md`
- `.kiro/steering/product.md`
- `.kiro/steering/tech.md`
- `.kiro/steering/structure.md`
- `.kiro/steering/physical-demo.md`
- `.kiro/specs/manual-track-demo/requirements.md`
- `.kiro/specs/manual-track-demo/design.md`
- `.kiro/specs/manual-track-demo/tasks.md`
- `docs/engineering/MANUAL_TRACK_SERVO_SORTER_BUILD_GUIDE.md`
- `firmware/manual_sorter/esp32_manual_sorter.ino`

Then inspect the actual repository and reconcile the supplied design with the existing APIs, tests, package structure, and frontend. Do not invent files or capabilities that are not present.

Before implementation:

1. Analyze the requirements for contradictions, missing acceptance criteria, unsafe actuator paths, and conflicts with the existing code.
2. Report the exact files you plan to modify or create.
3. Preserve existing behavior and historical archives.
4. Confirm that the scope remains a manually advanced carrier with one ESP32 controlling only a final servo diverter.

Implement the approved tasks in dependency order. Use mocked camera/serial transports for automated tests, and keep real USB/ESP32 tests explicitly manual. Never report physical tests as passed from the Kiro Web cloud sandbox.

The target operator flow is:

`LOAD → manual caliper + Webcam A → visual inspection + Webcam B → deterministic decision → staged P/H/R serial command → physical confirmation button → servo diverter → PASS/HOLD/REJECT → optional correlated arrival ACK`

Do not implement a powered conveyor in this scope.
