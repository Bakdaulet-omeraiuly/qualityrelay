# Physical demo overview (imported from HyorinmaruK/PhysicalQualityRelay)

PhysicalQualityRelay combines the audited QualityRelay 17 SAFE-MESH research package with a buildable, manually advanced physical inspection demonstration.

The recommended demonstration is:

`LOAD → CALIPER + WEBCAM A → VISION + WEBCAM B → DECISION → HUMAN CONFIRMATION → SERVO DIVERTER → PASS / HOLD / REJECT`

Start here:

- [Project overview and software setup](../../README_START_HERE.md)
- [Exact physical build, wiring, equipment, printing, and test guide](MANUAL_TRACK_SERVO_SORTER_BUILD_GUIDE.md)
- [Step-by-step connection and run checklist](MANUAL_TRACK_STEP_BY_STEP.md)
- [Virtual line, wiring, and firmware emulator](../../web/manual_track_visualizer.html) (open the file in a browser; simulation only)
- [Physical build: breadboard holes and jumper types, bench layout, bench test, 3D-print list](../../web/physical_build_guide.html) (open the file in a browser)
- [Tabletop demo: one-spot manual walkthrough and video storyboard](../../web/tabletop_demo.html) (open the file in a browser)
- [Measurement logger: caliper readings → CSV, with optional ESP32 capture](../../web/measurement_logger.html) (open the file in a browser) · [schema and handoff](MEASUREMENT_LOGGING.md)
- [Kiro Web handoff](../../KIRO_START_PROMPT.md)
- [Physical demo requirements](../../.kiro/specs/manual-track-demo/requirements.md)
- [ESP32 manual-sorter firmware](../../firmware/manual_sorter/esp32_manual_sorter.ino)
- [Printable test specimens](../../examples/cad/stl/), [all specimens in one Formlabs print](../../examples/cad/formlabs/), and [servo sorter parts](../../examples/cad/sorter/)

The transport is manual. One ESP32 is used only for the final servo diverter, so a powered conveyor, motor driver, and multiple ESP32 boards are not required for the first demonstration. This is a research prototype, not an industrial safety system or certified inspection product.
