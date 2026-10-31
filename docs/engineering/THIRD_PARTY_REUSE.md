# External GitHub projects, license and deployment review (30 October 2026)

**Principle:** This ZIP does **not** repackage third-party repositories, commercial weights, datasets, NVIDIA binaries or credentials. We provide verified upstream links, interface contracts, application points and install commands. Clone into your own environment and pin a reviewed commit. Licensing summaries are not legal advice; verify actual installed artifact and its transitive dependencies.

| Repo / source | License context | QualityRelay adapter | Priority / restrictions |
|---|---|---|---|
| [OpenCV](https://github.com/opencv/opencv) | Apache-2.0 for >=4.5.0 ([official](https://opencv.org/LICENSE/)) | Camera calibration, alignment, contours, photo/photo | P0; no self-calibrated mm claims |
| [Trimesh](https://github.com/mikedh/trimesh) | MIT ([license](https://github.com/mikedh/trimesh/blob/main/LICENSE.md)) | STL load, 2D projections, geometry metadata | P0; project STLs under correct view |
| [CadQuery](https://github.com/CadQuery/cadquery) | Apache-2.0 ([README](https://github.com/CadQuery/cadquery)) | Native parametric 3D parts | P1; OCCT deps verify |
| [SimPy](https://github.com/simpx/simpy) | MIT ([license](https://github.com/simpx/simpy/blob/master/LICENSE.rst)) | Discrete-event factory scheduling | P0/P1; package version review |
| [FactorySimPy](https://github.com/FactorySimPy/FactorySimPy) | MIT ([README](https://github.com/FactorySimPy/FactorySimPy)) | Machines, buffers, conveyors, splitters | P1; small project, verify maintenance |
| [Anomalib](https://github.com/open-edge-platform/anomalib) | Apache-2.0 ([license](https://github.com/open-edge-platform/anomalib/blob/main/LICENSE)) | PatchCore/EfficientAD industrial anomaly baseline | P1; model weights and datasets separately |
| [OR-Tools](https://github.com/google/or-tools) | Verify pinned source/build license | CPU matching/scheduling baseline | P1; hard to compare GPU without same model |
| [Hailo Model Zoo](https://github.com/hailo-ai/hailo_model_zoo) | Verify source, model & hardware toolchain separately | Hailo-8L independent local vision | P1; compatible branch/HEF only |
| [Nebius Cookbook](https://github.com/nebius/token-factory-cookbook) | Verify individual recipe license | LLM tool-calling client and live model catalog | P0; credits and secrets required |
| [NVIDIA TAO](https://github.com/NVIDIA-TAO) | Toolkit source Apache-2.0; pretrained NGC weights separate | Train image comparison/anomaly models | P1; verified weights, reproducible split |
| [NVIDIA cuOpt](https://github.com/NVIDIA/cuopt) | Apache-2.0 ([official](https://www.nvidia.com/en-us/ai-data-science/products/cuopt/get-started/)) | GPU decision optimization | P1; supported CUDA GPU; MIP optimal proof not guaranteed |
| [Isaac Sim](https://github.com/isaac-sim/IsaacSim) | Apache-2.0 source; additional Omniverse Kit/assets separate terms | 3D robot/sorter/camera scene | P1; **RTX RT core GPU**, NOT H100; redistribution caveat |
| [Replicator](https://developer.nvidia.com/isaac/sim) | Isaac/Omniverse relevant terms | Synthetic labeled defect/lighting images | P1; avoid correlated synthetic leakage |
| [NVIDIA Warp](https://github.com/NVIDIA/warp) | Apache-2.0 ([README](https://github.com/NVIDIA/warp)) | Physical collision/sorter model | P2; choose validated solver settings |
| [Newton Physics](https://github.com/newton-physics/newton) | Verify pinned repo and assets | Robotics contact/actuation | P2; not another production certifier |
| [PhysicsNeMo](https://github.com/NVIDIA/physicsnemo) | Apache-2.0 ([README](https://github.com/NVIDIA/physicsnemo)) | Physics ML surrogate and uncertainty | P2; requires validated FE ground truth |
| [DeepStream](https://github.com/NVIDIA/DeepStream) | Source Apache-2.0; docs CC-BY-4.0; binaries separate SDK EULA | NVIDIA GPU multi-stream tracking | P2; Pi/Hailo is **not** DeepStream host |
| [NVIDIA Cosmos](https://github.com/NVIDIA/cosmos) | OpenMDW-1.1 special source/weight terms | Robustness images/videos | P2; never use as measurement truth |
| [VSS Blueprint](https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization) | Repo Apache-2.0 with 3rd-party & asset exceptions | Video search, incident explanation | P2; large GPU/messaging footprint |

## Robust integration workflow
1. Open the upstream repo and `LICENSE`, model card, and release notes on installation day.
2. Record commit SHA, package version, Python/CUDA driver, hardware, license, download URL in `third_party.lock.yaml` (template below).
3. Isolate external packages as Docker images/optional extras. Do not let one NVIDIA library constrain the CPU scientific core.
4. Store third-party license notices with shipped **code**, not automatically copy all licenses for repos that were never bundled.
5. Compare trained weights on a dataset where part IDs/lots do not appear across train/test.
6. If license, GPU, time or access is blocked, fail to `UNAVAILABLE` and retain truthful baseline.

## Example dependency lock record
```yaml
component: nvidia-cuopt
upstream: https://github.com/NVIDIA/cuopt
revision: TO_BE_PINNED_FROM_VERIFIED_RELEASE
license_reviewed_by: TODO
license_date: TODO
hardware_compatibility: TODO
installed: false
external_artifact_included_in_zip: false
```

## Datasets
[MVTec AD](https://www.mvtec.com/research-teaching/datasets/mvtec-ad) has a **CC BY-NC-SA 4.0** noncommercial restriction. Do not integrate its images into a commercial factory SaaS without separate authorization. Use independently captured 3D printed parts and self-authored CAD for proprietary training. Public benchmarks can support noncommercial academic comparisons under their terms.
