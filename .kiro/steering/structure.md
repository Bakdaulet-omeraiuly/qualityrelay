---
inclusion: always
---

# Project structure guidance

Inspect the actual repository before applying this proposed structure. Reuse existing modules when their ownership and abstractions fit.

## Existing important locations

- `qualityrelay17/api.py`: FastAPI reference API and current hardware-ingest endpoints.
- `qualityrelay17/contracts.py`: evidence/decision contracts and signatures.
- `qualityrelay17/safe_mesh.py`: conservative deterministic review policy.
- `qualityrelay17/actuation.py`: staging and acknowledgement bookkeeping; currently no hardware IO.
- `qualityrelay17/hardware_ingest.py`: placeholder ADC and bin-ack evidence adapters.
- `qualityrelay17/vision.py`: uncalibrated OpenCV/CAD baseline.
- `qualityrelay17/ledger.py`: evidence persistence reference.
- `web/index.html`: current static UI.
- `firmware/esp32_station/`: current ESP32 reference sketches.
- `tests/`: existing automated suite.
- `examples/cad/stl/`: printable specimen geometry.

## Proposed additions

- `qualityrelay17/demo_session.py`: physical-demo state machine and session models.
- `qualityrelay17/manual_metrology.py`: operator-confirmed digital-caliper evidence creation.
- `qualityrelay17/camera_ingest.py`: image metadata/hash/quality handling without pretending calibration.
- `qualityrelay17/sorter_transport.py`: serial transport protocol, fake adapter, and real pyserial adapter.
- `qualityrelay17/sorter_service.py`: validates/stages route actions and consumes firmware responses.
- `qualityrelay17/config.py`: environment-driven local hardware configuration if no suitable config module exists.
- `firmware/manual_sorter/esp32_manual_sorter.ino`: human-confirmed servo firmware.
- `data/`: runtime-only captures/databases/logs; ignored by Git.
- Tests mirroring each new module plus API integration tests.

## API namespace

Prefer a dedicated `/demo/` namespace rather than silently changing existing research endpoints:

- `POST /demo/sessions`
- `GET /demo/sessions/{session_id}`
- `POST /demo/sessions/{session_id}/load`
- `POST /demo/sessions/{session_id}/caliper`
- `POST /demo/sessions/{session_id}/camera/{camera_id}`
- `POST /demo/sessions/{session_id}/fit`
- `POST /demo/sessions/{session_id}/evaluate`
- `POST /demo/sessions/{session_id}/route/stage`
- `GET /demo/sessions/{session_id}/route/status`
- `POST /demo/sessions/{session_id}/route/ack` only after correlation is implemented.

Keep files cohesive. Do not put serial IO, image decoding, policy decisions, and UI route handling into one module.
