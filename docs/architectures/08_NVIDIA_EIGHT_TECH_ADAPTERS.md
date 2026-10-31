# NVIDIA Eight-Technology Integration Plan

**Owner:** Team (specialized owners)  
**Status:** research design + partial reference implementation; see status below.

## Integration matrix
| NVIDIA technology | Input / output contract | Deployment target | What actually gets built |
|---|---|---|---|
| Isaac Sim + Omniverse | CAD/URDF -> USD stage -> photoreal observations | RTX RT-core GPU | 3D factory + camera + sorter scene plugin |
| Omniverse Replicator | USD scene + randomization -> labeled images/masks | same RTX host | train/test synthetic defect generation and metadata |
| cuOpt | mathematical assignment/scheduling -> feasible plan | CUDA GPU | matching and cost optimization; CPU fallback |
| PhysicsNeMo | real FEA/simulation fields -> surrogate prediction | NVIDIA CUDA GPU | phase-2 uncertainty-aware, never unvalidated PLA stress oracle |
| DeepStream | camera/RTSP -> tracked events + track ID | NVIDIA GPU/Jetson | multi-stream tracking; not Pi Hailo runtime |
| Cosmos | scene conditions -> synthetic image/video/world model outputs | compatible NVIDIA GPU | robustness augmentation only; not metrology ground truth |
| Metropolis VSS | video clips + events -> search/verified alerts | substantial NVIDIA GPU service | query manufacturing incidents by specimen and time |
| Warp + Newton | geometry/forces -> sorter collision/contact simulation | supported GPU | gate mechanics and actuator stress/test adapter |

## Avoid duplicate integrations
Isaac Sim already contains Replicator; Warp powers Newton; DeepStream integrates well with VSS. Define adapter interface rather than launching eight independent GPU servers. CPU-only reproducible science MUST remain possible if GPU resources are exhausted.

## GPU reality
NVIDIA shared H100 can train many CV/physics models but cannot serve RTX ray tracing demanded by Isaac Sim. Brev offers GPU options, but sponsor credit is finite; check actual available instance GPU and driver against ISAAC compatibility checker. A Pi Hailo-8L requires model conversion (HEF), not CUDA.

## License reality
cuOpt and PhysicsNeMo have Apache-2.0 source; NVIDIA Warp Apache-2.0; Cosmos OpenMDW-1.1 special terms; Isaac Sim source Apache-2.0, additional Kit/assets licensing and redistribution restrictions; DeepStream source Apache-2.0, documentation CC BY 4.0, NVIDIA binaries use separate SDK EULA; VSS blueprint code Apache-2.0 with asset/third-party exceptions. Model checkpoints and datasets can have different licenses. See `docs/engineering/THIRD_PARTY_REUSE.md`.

## Minimum acceptance per plugin
`availability()`, `health()`, `resource_budget()`, `run(config,run_id)`, `status`, `output_provenance`, `fallback`, exact software version, explicit not-run result if unavailable. Never silently substitute a mock while showing branded NVIDIA inference.

