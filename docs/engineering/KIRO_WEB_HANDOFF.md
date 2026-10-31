# QualityRelay Kiro Web handoff

This repository already contains the Kiro Web steering, specification, firmware, physical build guide, and CAD assets. Connect the repository to Kiro Web so it can read them from the `main` branch.

The bundle supplies:

- `.kiro/steering/`: persistent product, technology, structure, and physical-demo context.
- `.kiro/specs/manual-track-demo/requirements.md`: testable requirements.
- `.kiro/specs/manual-track-demo/design.md`: architecture and interfaces.
- `.kiro/specs/manual-track-demo/tasks.md`: ordered implementation work.
- `AGENTS.md`: always-on safety and truthfulness rules.
- `KIRO_START_PROMPT.md`: the initial prompt to paste into a Kiro Web Spec-mode session.
- `docs/engineering/MANUAL_TRACK_SERVO_SORTER_BUILD_GUIDE.md`: the physical build guide.
- `firmware/manual_sorter/`: the human-confirmed servo prototype.
- `examples/cad/`: the printable specimen files, source, and manifest.

## Kiro Web workflow

1. Connect this repository in Kiro Web.
2. Open a **Spec mode** session.
3. Paste the contents of `KIRO_START_PROMPT.md`.
4. Ask Kiro to analyze the supplied requirements for contradictions and gaps.
5. Review and approve `requirements.md`, then `design.md`, before executing tasks.
6. Let Kiro implement through the task list in dependency order.
7. Run webcam, serial-port, ESP32, servo, and physical-routing checks locally. Kiro Web runs in a cloud sandbox and must not claim that local hardware tests passed.

## Intended result

The application coordinates this line:

`LOAD → CALIPER + WEBCAM A → VISION + WEBCAM B → DECISION → SERIAL STAGE → PHYSICAL BUTTON → SERVO DIVERTER → PASS/HOLD/REJECT`

Transport remains a manually pushed carrier. The ESP32 operates only the final diverter. A second ESP32 and independent bin-arrival sensing are a later optional phase.
