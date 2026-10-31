# Dependencies, licences and adapter statuses (REL-03)

Owner: adilnurgg. Source of truth: `THIRD_PARTY_MANIFEST.json` (versioned: `manifest_version`, `release`, `reviewed_on`, `reviewed_by`; schema in `schemas/third_party_manifest.schema.json`). CI's `dependencies` job enforces everything below.

## Three files, three jobs

| File | Says | Edited by |
|---|---|---|
| `requirements-*.txt` | Supported version ranges per purpose: demo, dev/CI, optional, GPU, vision | Hand |
| `requirements-lock.txt` | Exact transitive pins of demo + dev for Linux x86_64. Resolved at Python 3.11 and checked to install on 3.13. **CI installs only this.** | `python scripts/check_dependencies.py lock` (network) |
| `THIRD_PARTY_MANIFEST.json` | Reviewed licence of every requirement, the licence string its wheel reports, separately installed upstream components, and every adapter's status with evidence | Hand; `lock` updates `pinned` |

To add or bump a dependency:
1. Edit the range in the right `requirements-*.txt`.
2. Add or update the `python_packages` entry: reviewed SPDX `license`, plus `license_metadata` exactly as `check_dependencies.py env --report` prints it.
3. Run `lock` and commit all three files.

`requirements-lock.txt` is on the two-review list (`.github/safety-paths.txt`), because it defines what actually gets installed.

## What CI checks

`check` (offline):
- Every requirement has a manifest entry with the same range, and there are no stale entries.
- Every lock pin satisfies its range, and the manifest's `pinned` matches the lock.
- Every adapter's evidence is valid:
  - **WORKING** needs a committed run artifact and tests.
  - **TESTED** needs tests whose required packages are in the lock. Otherwise those tests would `importorskip` in CI, and that doesn't count as tested.
  - Every cited file must exist.

`env` (after installing the lock):
- The installed environment is exactly the lock.
- Every installed licence is known.
- No licence matches the deny list (GPL, AGPL, SSPL, BUSL, Commons Clause, non-commercial). LGPL and MPL are allowed for installed libraries.
- For reviewed packages, the licence string in the wheel hasn't changed since review. An upstream relicense fails CI until someone re-reviews it.
- The `installed-licenses` artifact on each CI run lists all ~70 installed distributions with their licences.

At review on 31 Oct, everything installed was permissive or MPL-2.0 (`certifi`, `pathspec`, `tqdm`; file-level copyleft, used unmodified). No package had an unknown licence.

## Adapter statuses

| Status | Meaning | Required evidence |
|---|---|---|
| `WORKING` | Ran on its real backend outside unit tests | A committed run artifact (manifest JSON) recording where it ran, plus tests |
| `TESTED` | Wired, and CI tests exercise it with offline stand-ins (fake client, fixtures, CPU) | Tests that actually run in CI |
| `NOT_CONFIGURED` | Not wired, not installed, or no credentials or hardware | None. Nothing is claimed. |

Every adapter also has a `scope` that says exactly what its status covers. `GET /integrations` serves the whole registry; `GET /integrations/nvidia` serves the NVIDIA slots. Both read the manifest and never probe a live service.

State on 31 Oct 2026: **1 WORKING, 5 TESTED, 16 NOT_CONFIGURED.**

- **NVIDIA (the eight plan slots).** "Warp/Newton" is split because only Warp is used.
  - **`warp` is WORKING, CPU backend only.** Evidence: `examples/results/warp_mc/cpu/manifest.json` (warp 1.18.0, macOS arm64) and `tests/test_warp_mc.py`. CI now installs `warp-lang`; before REL-03 those tests were silently skipped in CI. It has never run on a CUDA GPU.
  - **`newton`, `cuopt`, `isaac_sim`, `replicator`, `physicsnemo`, `deepstream`, `cosmos`, `metropolis_vss` are NOT_CONFIGURED.** We do not claim that eight NVIDIA services are running. `tests/test_dependencies.py` fails if a second slot becomes WORKING without evidence, or if the website's "Not claimed" card stops matching the registry.
- **LLM: TESTED.** This covers the `openai_planner`, `nebius_planner` and `nebius_entitlement` adapters. They are fake-client tested, with no live call recorded. They become WORKING when a Gate B / LLM-01 run manifest is committed.
- **Hardware: TESTED in software only.** This covers `esp32_station` (signed ingest) and `esp32_sorter` (interlock + ACK binding). The E12/E13 rehearsal artifacts are simulate-mode `TEST_FIXTURE`. No physical run exists.
- **`vision.anomaly_stfpm`: NOT_CONFIGURED in this repo.** `ANOMALY_MODEL_HANDOFF.md` reports L4 runs on 31 Oct, but the run manifests it cites (`docs/research/runs/`) are not committed, and CI does not install torch. Committing those manifests is the way to upgrade it to WORKING.
- **Everything else is NOT_CONFIGURED:** Pi/Hailo, TAO, Anomalib, the supervision renderer, OR-Tools, FactorySimPy, Google Cloud.

`sim/cad.py` and `sim/optimization.py` have their own import-time status helpers. Those helpers report `WORKING` when a library merely imports, and they add an `INSTALLED_NOT_WIRED` state. They are simulation-internal and owned by Bakdaulet. The manifest is the authoritative status for anything shown as an integration.

## Upgrading a status

1. Commit the evidence: a run manifest under `examples/results/` or `docs/research/runs/` with origin, environment and git commit. For TESTED, commit tests that run in CI.
2. Change `status`, `scope` and `evidence` in the manifest. `check` refuses the change without that evidence.
3. If an NVIDIA slot changes, update the "Not claimed" card in `web/index.html` too; a test pins the two together.
