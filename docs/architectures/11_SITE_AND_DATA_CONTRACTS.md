# One Website, Separate Research Services

**Owner:** adilnurgg + HyorinmaruK  
**Status:** research design + partial reference implementation; see status below.

## Website tabs
Factory Overview; Phone Scan; Pi Station; CAD Compare; Metrology; Agent Evidence Room; Simulation Lab; Smart Matching; Economics & ROI; Scientific Benchmark; Audit; Settings & Permissions.

## Boundaries
Frontend (Next.js or static HTML) is NOT the source of truth. API gateway authenticates, rate limits, tags source origins. The station-specific local DBs and offline queues persist without website. FastAPI can expose read-only summaries. Separate actuation service needs human auth and physical interlocks; no web browser event directly moves servo.

## Core contracts
`POST /evidence` signed bounded event; `GET /specimens/{id}/review` safely summarized decision; `POST /inspections/rank` VOI candidates; `POST /simulations` seeded job; `GET /runs/{id}` manifest; `POST /actions/{id}/approve` privileged human only; `POST /sorter/acks` hardware route confirmation; `GET /audit`. The NEW demo API only implements `/health`, `/demo`, `/simulation/compare`, `/research/claims` — no claim other endpoints exist.

## Visualization integrity
Show badge physical/synthetic/test fixture; upstream and downstream event IDs; when camera inference ran on CPU baseline vs trained NVIDIA; last calibration timestamp; actual model; staff review pending. If data missing show UNKNOWN/HOLD rather than zero risk. Physics/financial results show units and confidence intervals, no invented precision.

## Deployment
Only adilnurgg and HyorinmaruK own Google Cloud. The ScienceClaw GCP accounts are temporary, max two per team and auto-delete event Sunday night (per supplied PDF). Persist original source and run manifests to GitHub before account expiry. Production needs TLS, authorization, secure secrets, tenancy isolation and retention policies; the demo API alone is not safe for Internet exposure.

