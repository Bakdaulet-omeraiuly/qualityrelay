# Team-of-three, optional fourth participant, and GitHub integration

## Owners (user-approved)
| Account | Module owner | Branch areas | Gates |
|---|---|---|---|
| **Bakdaulet-omeraiuly** | Research, scientific engine V-DER/CAIR/EWMA, calibration, NVIDIA vision research, benchmarking, model hypotheses, economic experiments | `qualityrelay17/{vder,benchmark,factory,digital_line,vision,matching,economics}.py`, `docs/research` | Claims + data validation; **NO Google Cloud responsibility** |
| **adilnurgg** | Agent backend, Nebius, Google Cloud API/infrastructure, evidence mesh, security, identity, authorization, actuation interface | `qualityrelay17/{contracts,ledger,safe_mesh,nebius,agent_tools,api}.py`, `schemas`, cloud | API reviews and access controls |
| **HyorinmaruK** (mechanical engineer) | Mechanical CAD/STL, print specimens, two cameras/lighting, physical validation, sorter, site UX, **Google Cloud deployment**, presentation | `cad`, `web`, `docs/architectures/03`, `07`, physical test | Physical proof report and final slides |
| **Fourth optional teammate** | Independent QA/reliability, queue simulation, multi-factory connector, external repo integration, CI; no overwrite on current owners | `tests`, `docs/research/EXPERIMENT_PROTOCOL.md`, adapters | No merging safety-critical code alone |

## GitHub layout
Use one monorepo; keep current upstream repos separate (`/vendor` should contain no unreviewed copied code):
```
qualityrelay/
  qualityrelay17/       # our own new algorithm, simulation, agent & API code
  web/                  # single dashboard, phone camera web inputs
  docs/architectures/   # 12 module-specific plans
  docs/research/        # hypotheses and transparent benchmark
  schemas/              # event schema and API contracts
  tests/                # contract/failure/provenance tests
  legacy/               # original owned archives; exclude if public if privacy unclear
```

## Branches and review
`main` protected, 1 review for ordinary PR, 2 reviews for actuation/auth/safety code changes. Branches `science/vder-calibration`, `backend/evidence-mesh`, `mechanical/dual-camera-cad`, `qa/regression`. CI: Python unit tests, static schema checks, dependency vulnerability scan, and generated manifest diff. A team member cannot merge their own change to release PASS authority alone.

## Shared interface checklist
`event_id`, `specimen_id`, `lot_id`, `station_id`, `source_root`, `observed_at`, `origin`, `calibration_id`, `model_version`, `signature`, `parent_source_roots`, `cad_revision`, `operator_verification`, `uncertainty` standardized across services. UI only shows verified provenance. Every physically confirmed route recorded by separate unique sensor ACK.

## Deployment
Two Google Cloud accounts maximum for team as disclosed in event-provided resource deck; GCP provisioning managed solely by adilnurgg and HyorinmaruK. Bakdaulet can submit reproducible benchmark outputs, no GCP setup obligations. Nebius Scientific AI: one application per team. Store authorized keys only as secrets. Sponsor accounts may expire after weekend; export GitHub source and measured run manifests before deletion.

## Integration order
1. Merge contracts and unit tests.
2. Real phone capture, reference compare and manual caliper capture.
3. CAD silhouette and Pi independent capture.
4. Two separately authorized station services; conflict HOLD demonstrated.
5. Physical sorter staging+ACK, only if verified operator control is possible.
6. Factory simulation + benchmarks + ROI, and public demo.
7. NVIDIA/RTX plugins and live Nebius with explicit entitlement/credit gates.
8. Physical validation and slides chaired by HyorinmaruK; Bakdaulet signs statistical claims.
