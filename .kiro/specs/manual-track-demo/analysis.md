# Pre-implementation analysis (Kiro, 2026-10-31)

Status: **awaiting approval**. No backend/firmware code has been changed yet.

## Baseline (task 2)

- Command: `python -m pytest -q` in the Kiro Web sandbox (Python 3.11, no package index access).
- Result: **81 passed**, 2 modules not collected: `tests/test_api.py` (12 tests) and `tests/test_actuation_agents_vision.py` (18 tests) because `fastapi`, `pydantic`, `numpy`, `opencv`, `trimesh` cannot be installed here.
- The suite defines 111 test functions. `RELEASE_VALIDATION.json` (88 passed) and `docs/engineering/TOMORROW_TASKS.md` (102/102) are both stale. The full count must be confirmed on a machine with `requirements-demo.txt` installed.
- Consequence: any FastAPI route tests written here will be skipped in the sandbox (`pytest.importorskip`) and must be run locally. Core logic will be stdlib-only so it is tested here.

## Scope confirmation

Manually pushed carrier; one ESP32 drives only the final servo diverter; physical button is the final movement authority; no conveyor, motor, or motor driver. Arrival sensing (second ESP32, `bin_sensor.ino`) stays optional and disabled.

## Contradictions and gaps

1. **HOLD routing vs. staging precondition.** R7 refuses staging unless the session is REVIEW_READY, while the design's state diagram moves sessions with missing evidence to a `HOLD` *state*. A HOLD specimen still has to be physically routed to the HOLD bin. Proposal: HOLD is a *decision* carried by REVIEW_READY (`decision ∈ {HOLD, PASS_REVIEW, CONFIRMED_REJECT}`); a separate `FAULT` state covers transport errors.
2. **Origin tier vs. fake-transport mode.** `SorterInterlock.stage()` requires `origin == VERIFIED_PHYSICAL`, but R13 requires a usable simulation mode, and manual caliper evidence starts as `PHYSICAL_CAPTURE`. Missing: the rule that promotes `PHYSICAL_CAPTURE → VERIFIED_PHYSICAL` (proposal: operator confirmation + instrument ID + calibration ID). Proposal: TEST_FIXTURE/SIMULATED sessions may stage only on the fake transport; the real transport accepts only VERIFIED_PHYSICAL.
3. **Decision vocabulary differs in three places.** `contracts.Decision` uses `CONFIRMED_REJECT_REVIEW`, the design uses `CONFIRMED_REJECT`, `SorterInterlock` expects `AUTHORIZED_PASS` / `CONFIRMED_REJECT`. Needs one mapping: `PASS_REVIEW` + recorded human authorization → `AUTHORIZED_PASS`.
4. **`safe_mesh.evaluate()` does not fit this line.** It hard-codes `PHONE_IMAGE` + `PI_IMAGE` + `CAD_IMAGE` + `ASSEMBLY`, never returns a REJECT state, and requires per-station HMAC keys (currently unprovisioned, so every real event fails `BAD_SIGNATURE`). Webcam A records the caliper display; it is not a second inspection view of the specimen and must not satisfy the two-camera rule. Proposal: a new `demo_policy.py` that reuses `contracts`/signature/freshness checks and adds kinds for caliper-display image, vision image, and fit; `safe_mesh.py` stays unchanged. Signing key for the demo comes from an environment variable, never committed.
5. **Fit is required for PASS (R5/R6) but single specimens have no pair.** Run C and any lone tab can then never PASS. Needs a decision: always require fit (conservative, recommended) or only for pair sessions.
6. **Measurement acceptance is undefined.** R6 says "configured measurement acceptance" but no nominal/tolerance table, plausible bounds (R3), or repeatability limit exists. Build guide asks for 3 readings; R3 models one value. Proposal: per-specimen-ID nominal from `print_manifest.csv`, tolerance and bounds from config, 3 readings stored, uncertainty = recorded repeatability.
7. **OCR does not exist in the repository.** `ocr_candidate_mm` can only be typed or left empty for now.
8. **No image-upload pattern exists.** The current UI processes images only in the browser. `UploadFile` needs `python-multipart`, which is not a dependency. Proposal: browser computes SHA-256 and dimensions; JSON submits metadata plus an optional size-limited base64 still saved under ignored `data/captures/`.
9. **Image quality checks do not exist.** `vision.compare_reference` needs pose-aligned grayscale and numpy/cv2. Proposal: simple browser-side quality flags (too dark, too uniform/blurred) labeled uncalibrated; backend records them.
10. **Freshness window.** `max_age_s = 600` default; a manual run with three readings and a fit test can exceed 10 minutes and silently HOLD. Make it explicit configuration.
11. **State naming overclaims.** `GATE_MOVED` is reported by firmware after `diverter.write()`. A hobby servo has no position feedback. Proposal: name it `GATE_REPORTED` (matches RouteAction state) or document the meaning.
12. **Two overlapping state machines.** Session states (`ROUTE_STAGED → WAITING_PHYSICAL_CONFIRMATION → GATE_MOVED`) and RouteAction states (`STAGED → SERIAL_SENT → WAITING_BUTTON → GATE_REPORTED`) need one explicit mapping.
13. **HOLD recovery is unspecified.** "Corrective actions may return to the last safe state" has no defined actions. Proposal: explicit `recapture` / `remeasure` endpoints that return to MEASURED or LOADED with an audit entry; never automatic.

## Unsafe actuator paths found in the current firmware

1. **The gate stays at the last angle.** After a PASS move the flap keeps pointing at PASS. If the next specimen's stage fails or expires and the operator advances the part, it lands in PASS without any decision. Proposal: return to HOLD after a configurable dwell (e.g. 5 s) and on every expiry/boot.
2. **A new letter replaces a pending route** and restarts the timer. The backend's "one outstanding action" is not enforced on the device. Proposal: refuse new stage while pending (`BUSY`), require explicit `C` cancel.
3. **Opening the serial port resets most ESP32 boards** (DTR/RTS). A bridge that writes immediately after `open()` loses the command. The bridge must wait for a ready line before staging and treat an unexpected ready line as FAULT.
4. **Angle limits are not enforced** (R10). Add compile-time checks (0–180°, distinct, configurable safe min/max).
5. **Status is human-readable only.** Proposal: add versioned machine lines (`QR1 READY`, `QR1 STAGED P`, `QR1 MOVED P 35`, `QR1 EXPIRED`, `QR1 BUSY`, `QR1 NOSTAGE`) while keeping the existing text.
6. **No local indication of the staged route** on the device. The operator relies on the screen; an LED per route is a cheap improvement (optional).
7. Board note: GPIO32 does not exist/should not be used on many ESP32-S3 modules (flash/PSRAM pins).

Security: the API has no authentication. It must bind to 127.0.0.1, accept only `application/json` (no CORS middleware, so cross-site pages cannot send preflighted requests), and never expose a raw serial endpoint.

## Planned files (for approval)

Create:

| File | Purpose | Tasks |
|---|---|---|
| `qualityrelay17/config.py` | env-driven demo config (mode, capture dir, transport fake/serial, port, baud, timeouts, tolerances) | 4 |
| `qualityrelay17/demo_session.py` | `DemoSession`, states, transition validator, audit log | 5, 9 |
| `qualityrelay17/manual_metrology.py` | operator-confirmed caliper readings, OCR mismatch | 6 |
| `qualityrelay17/camera_ingest.py` | capture metadata, digest, source identity, quality flags | 7 |
| `qualityrelay17/fit_evidence.py` | fit-test records | 8 |
| `qualityrelay17/demo_policy.py` | deterministic HOLD / PASS_REVIEW / CONFIRMED_REJECT | 13, 14 |
| `qualityrelay17/sorter_transport.py` | `SorterTransport` protocol, fake transport, pyserial transport, firmware line parser | 23, 24, 28–31 |
| `qualityrelay17/sorter_service.py` | action IDs, one outstanding action, timeouts, wraps `SorterInterlock` | 25, 34 |
| `qualityrelay17/demo_api.py` | `/demo/...` APIRouter (Pydantic models) | 11, 12, 26 |
| `web/demo.html` | operator workflow with two webcams | 16–21 |
| `requirements-hardware.txt` | `pyserial` only | 28 |
| `tests/test_demo_session.py`, `test_manual_metrology.py`, `test_camera_ingest.py`, `test_demo_policy.py`, `test_sorter_transport.py`, `test_sorter_service.py`, `test_demo_api.py` | automated tests (API test skips without FastAPI) | 10, 15, 22, 27, 31, 35 |

Modify:

| File | Change |
|---|---|
| `qualityrelay17/api.py` | include `/demo` router; serve `web/demo.html` and the visualizer; existing endpoints unchanged |
| `qualityrelay17/contracts.py` | add new `Kind` literals only |
| `firmware/manual_sorter/esp32_manual_sorter.ino` | items 1–5 above, behavior otherwise preserved |
| `.gitignore`, `.env.example` | runtime/hardware exclusions and new variables (additive) |
| `README_START_HERE.md`, `CLAIMS_AND_OPEN_WORK.md`, `tasks.md` | docs and honest status |
| `RELEASE_VALIDATION.json`, `FILE_SHA256_MANIFEST.json` | regenerated last (task 42) |

Unchanged: `legacy/`, `safe_mesh.py`, `hardware_ingest.py`, existing `/hardware/*` endpoints, `web/index.html` (link only).

## Already delivered in this pass

- `web/manual_track_visualizer.html`: offline virtual line, wiring steps, firmware emulator.
- `docs/engineering/MANUAL_TRACK_STEP_BY_STEP.md`: connection order, bench tests, run procedure, blank H1–H11 checklist (tasks 37–40 partially, manual parts).
- `docs/engineering/templates/manual_track_run_log.csv`: run log header.

## Decisions needed

1. Approve the plan above (or trim it to specific waves).
2. Fit test always required for PASS? (recommended: yes)
3. Firmware: auto-return to HOLD after a move, and refuse re-stage while pending? (recommended: yes)
4. Measurement tolerance for the demo (proposal: ±0.15 mm around CAD nominal, max 3-reading spread 0.05 mm, placeholders until the repeatability screen is done).
5. Image handling: hash + metadata + optional local still under `data/captures/` (recommended) vs. metadata only.
