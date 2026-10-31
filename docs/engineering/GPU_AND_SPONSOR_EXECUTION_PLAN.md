# GPU and sponsor execution plan — QualityRelay 17.0

**Team context:** User reports relevant hackathon accounts exist. **Account existence ≠ redeemed credits ≠ running GPU instance.** Nothing in this package tests private accounts, credentials, quotas, invite status, credit balances or instance availability. Confirm individually from authorized consoles. Never put token/API keys or event-only links in Git.

## Compute split: use the RIGHT GPU for the job

| Resource | Allocated in hackathon PDF | Workloads | Hard restrictions |
|---|---|---|---|
| NVIDIA Brev | $150 credit per registered participant; 3 participants could hold $450 across separate accounts | RT-capable RTX instance for Isaac Sim/Replicator; alternatively CUDA model training; cuOpt | Credits **not** automatically pooled into one account. GPU selection, availability, hourly pricing must be checked before boot. Stop idle instance. |
| Nebius Cloud AI | Shared event pool of 16 H100 GPUs; recommendation <=1 GPU/team/job | Vision training, batch LLM experiments, physics ML (if validated data), scientific benchmark | All teams share; queue possible, no guaranteed exclusive H100. H100 does NOT meet Isaac Sim RT requirement. |
| NVIDIA DGX Spark / Dell GB10 | Five on-site units, permission via event NVIDIA channel | Local experiments and eligible small-model inference | Access not guaranteed; model and driver compatibility must be verified. |
| Nebius Scientific AI | Team credential set, scientific models and research tools | Optional scientific inference/experimentation | One request per team, model suitability separate from claims of industrial accuracy. |
| Claude API | $100 credits/registered participant | Alternate LLM baseline | Event-only claim instructions; not a Claude subscription. |
| OpenAI API | $50 grant under stated redemption rules | Alternate single agent baseline | API credits, not ChatGPT subscription. |
| Google Cloud | Up to two temporary accounts per team | Site hosting/back-end, CPU event simulations, object store | **Only adilnurgg and HyorinmaruK own Google Cloud tasks.** Temporary accounts expire after event. |

## Compute topologies

1. **Local/CPU reproducible:** web + FastAPI + numpy/scipy + OpenCV baseline + geometry renderer + seeded factory simulator. This MUST continue if GPUs or APIs are unavailable.
2. **Nebius H100:** controlled training of a candidate anomaly detector, benchmark runs, optional science tool. Export versioned ONNX/weights only if license and compatibility verified. Host at server-side; do not leak keys to phone browser.
3. **Brev RTX:** USD scene, Isaac Sim, Replicator, randomization for camera pose, lighting and defect geometry. Verify exact GPU with Isaac Sim Compatibility Checker; require RT Cores and appropriate RAM/VRAM/driver.
4. **Brev/H100 compatible CUDA:** NVIDIA cuOpt installation for GPU scheduling/matching. Compare with CPU exact DP (small problems) and OR-Tools on identical objective/constraints. Avoid claiming cuOpt proves MIP optimality; current MIP support is evolving.
5. **Edge Pi + Hailo-8L:** independently deploy compatible compiled model; Hailo is not CUDA and not an NVIDIA GPU; never assume a CUDA checkpoint runs there without conversion/validation.

## First 30-minute account check (owners)

- `adilnurgg`: verify Nebius tenant invite and H100 job entitlement, quota, API calls and permitted models. Use the user-registered account; never paste credentials into public issues.
- `HyorinmaruK`: verify NVIDIA Brev credits and RTX-compatible GPU availability; use hardware photos and Pi camera as offline demo fallback; own any Google Cloud front-end deployment.
- `Bakdaulet`: design exact training/validation and 30-seed scientific benchmark; no Google Cloud administration. GPU runs are research tasks, not GCP chores.

## Resource ledger

For EVERY run, record `run_id, provider, instance_type, GPU_model, gpu_count, driver, CUDA, docker_digest, tool_version, price_per_hour, start/end, total_spend, dataset_hash, model_hash, seed, git_commit, source_origin`. Show model unavailability rather than a fake result.

## Infrastructure cost in ROI

`operational_savings = avoided_scrap + avoided_rework + avoided_inspections + avoided_downtime - additional_review - GPU/API - cloud_storage - hardware_amortization - false_holds - integration_cost`. Costs must use user-supplied factory assumptions or measured values. Never publish estimated cloud credits as realized factory savings.

## Current product documentation (recheck before install)

- Isaac Sim system requirements: https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html (H100/A100 no RT Cores, unsupported)
- NVIDIA cuOpt: https://github.com/NVIDIA/cuopt (CUDA 12/13, Linux; verify selected versions)
- Brev: https://brev.nvidia.com/
- NVIDIA Cosmos: https://github.com/NVIDIA/cosmos (OpenMDW-1.1 in repository; license at installed revision)

## ScienceClaw organizer-only PDFs

Resource amounts are extracted from user-supplied `PDF - ScienceClaw Compute.pdf` and `PDF - Hardware Summary.pdf`. Special redemption links and individual login details are deliberately NOT copied into this public package. Hardware is limited, first-come-first-served: 15 ESP32-S3, 10 ESP32-S3 cameras, 5 Pi5 + Hailo-8L, 5 Pi cameras, 5 electronics bundles, etc. Availability not guaranteed.
