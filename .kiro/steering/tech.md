---
inclusion: always
---

# Technology and constraints

## Existing stack

- Python package: `qualityrelay17`.
- API: FastAPI + Pydantic.
- Tests: pytest.
- Evidence: signed data contracts, HMAC reference, SQLite/ledger reference.
- Vision: OpenCV pixel-difference baseline and STL projection helper; not calibrated.
- Frontend: existing static HTML/CSS/JavaScript research dashboard.
- Firmware: Arduino-style ESP32 C++.

## Preferred additions

- Keep the existing frontend approach unless repository inspection proves a framework is already established.
- Use browser `getUserMedia`/`enumerateDevices` for two local webcam sources.
- Serve the UI from localhost or HTTPS because browser camera access requires a secure context.
- Add `pyserial` only for the local sorter bridge.
- Define a serial transport interface with a fake implementation for tests and a real implementation selected by configuration.
- Use environment variables for local serial port, baud rate, capture directory, and secrets.
- Keep captured images and runtime databases out of Git.
- Use `ESP32Servo` for the supplied prototype firmware unless the exact board/core requires another supported mechanism.

## Hardware boundary

- Kiro Web runs in a cloud sandbox and cannot operate the user's USB webcams, serial port, ESP32, servo, caliper, or bins.
- Kiro may implement and test simulated transports in the cloud.
- The user must run real camera, serial, firmware, and physical-route tests locally.
- Test reports must distinguish automated software tests from local manual hardware tests.

## Security and safety

- Same-origin local UI/API is preferred for the demonstration.
- Do not expose the serial bridge on a public interface.
- Validate route values against the closed set `PASS`, `HOLD`, `REJECT` / `P`, `H`, `R`.
- The backend may stage a serial command but must not represent button confirmation or physical arrival unless independently observed.
- Apply timeouts and idempotency to route actions.
- Default to HOLD on camera, API, serial, signature, or acknowledgement failures.
- Keep the existing separation between decision support and final human authorization.

## Quality rules

- Add type hints to new Python code.
- Use explicit models for all API payloads and state transitions.
- Keep hardware adapters behind interfaces so tests never require real devices.
- Write unit tests for validation/state logic and integration tests using fake camera/serial data.
- Never weaken existing truthfulness/status endpoints to make the demo look complete.
