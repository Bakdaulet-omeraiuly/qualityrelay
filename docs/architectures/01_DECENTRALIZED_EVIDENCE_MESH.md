# Decentralized Evidence Mesh

**Owner:** adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Research purpose
Keep ownership of raw factory data at its source while allowing separately authorized evidence requests. The network must allow local continuity when Chief Engineer or upstream cloud inference disappears.

## Data layout
- Slot station: measurements W, calibration, SPC, lot ID, process metadata.
- Tab station: T, process profile, print/machine run, tolerance and instrument checks.
- Assembly station: W−T compatibility, minimum clearance, pairing records.
- Phone Vision station: photo hashes, camera pose, model version, frame quality, anomalies.
- Pi Vision station: separately captured images, local queue, independent model outputs.
- Sorter station: approved request, physical actuator request and independent route acknowledgment.
- Shared router: immutable pointer/event transport **without authority** to issue metrology, modify measurements or release PASS.

## Protocol and constraints
Use signed events with event_id, specimen_id, station_id, observed_at, source_root, calibration_id, origin, model_version, payload hash, parent hashes, authorization and signature. Peer requests must reference authorized schemas; `chief_readonly` only receives allowlisted summaries. Network downtime causes PARTIAL_COVERAGE, not inferred false measurements. On reconnection, replay idempotently against event IDs and enforce TTL, bounded queues, watermark progress, clock skew allowances and digest checks.

## Trust assumptions
HMAC attests that a keyed station emitted a message; it cannot verify that the sensor is uncompromised or that the physical object is genuine. Prefer device-bound keys, rotation, TLS, inventory identifiers, event replay protection and authenticated operator binding in future factory pilot. Do not call this a blockchain.

## Implemented here
`contracts.py`, `ledger.py`, `safe_mesh.py`. Event collection in one process is **not** a proven real network mesh; original QualityRelay 15 dual-station code provides two-process/two-SQLite reference in `legacy/`.

## Scientific test
Inject missing phone, missing Pi, stale station response, cloned images, tampered signatures, replay, Chief failure, dropped router events. Report both decision quality and the amount of useful service retained, not availability alone.

## Acceptance
- Denied raw unauthorized read; snapshots signed; no duplicate event insertion.
- Every PASS_REVIEW contains enough current verified modalities, never a physical PASS.
- Offline operation does not silently reuse stale cross-station state.

