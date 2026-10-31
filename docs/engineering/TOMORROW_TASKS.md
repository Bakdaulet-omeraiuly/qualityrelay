# Tomorrow — 1 November, final day

What's new in this ZIP since last night, and what each owner should do with it. Everything
below follows `TEAM_OWNERSHIP_AND_GITHUB.md`'s existing module ownership and review rules —
nothing here should be merged to `main` without the normal review, including these changes.

## What was added tonight (needs your review, not just your trust)

| File | Change | Owner to review |
|---|---|---|
| `qualityrelay17/factory.py` | New `voi_driven` policy wiring `vder.action_scores()` into the comparator (answers H2) | **Bakdaulet** |
| `qualityrelay17/benchmark.py` | `voi_driven` added to `run_benchmark`'s policy set + paired diff vs `conservative_rules` | **Bakdaulet** |
| `qualityrelay17/hardware_ingest.py` (new) | Converts raw ESP32/Pi sensor payloads into signed `Evidence` | **adilnurgg** |
| `qualityrelay17/api.py` | Two new endpoints: `POST /hardware/caliper-reading`, `POST /hardware/bin-ack` | **adilnurgg** |
| `firmware/esp32_station/*.ino` (new) | Reference sketches for the slot/tab station and the isolated bin-ACK sensor | **HyorinmaruK** |
| `tests/test_voi_integration.py`, `tests/test_hardware_ingest.py`, additions to `tests/test_api.py` | New tests; full suite is 102/102 passing | whoever reviews the above |

**Important, read before you touch the VOI numbers:** a first pass of `voi_driven` was
withholding the already-free clearance measurement unless it happened to pick a caliper
retake, which made it look unfairly worse than the fixed-rule baselines. That's fixed now
(clearance is always free, matching the other three policies), and a quick 10-seed run shows
`voi_driven` matching `conservative_rules`'s unsafe-pass rate (0.0031 vs 0.003, difference
`[0.0, 0.0003]` — essentially noise) at **~27% lower mean cost and ~22% fewer holds**. That is
directionally the result H2 hopes for — **it is not a validated finding.** The sensitivity/
specificity/cost values are still my illustrative placeholders, the prior heuristic is still
ad hoc, and this was one exploratory run, not the pre-registered protocol. Bakdaulet: calibrate
or replace those placeholders and re-run under `EXPERIMENT_PROTOCOL.md`'s actual seed/scenario
plan before this goes on a slide as a result rather than "the wiring now works."

> **Bakdaulet, 31 Oct:** superseded. The paragraph above is kept for the record; the "~27%"
> number must not be quoted anywhere — see my section below and
> `docs/research/PROTOCOL_RUN_31OCT_RESULTS.md` for what replaced it.

## Bakdaulet — scientific engine (status 31 Oct, branch `science/vder-calibration`)

1. **Done — reviewed and replaced, not merged as-is.** The night-before `voi_driven` had three
   defects (loss scale ≠ benchmark costs; "recapture" re-read the same bit; invented prior and
   likelihoods). Rewritten: `calibration.py` estimates sens/spec/priors on held-out seeds,
   `vder.two_axis_action_scores` scores one-step NetVOI on `economics.Costs`, `factory.py`
   draws fresh recapture/retake observations from a second RNG stream (17.0 columns
   byte-identical, regression-tested). `entropy_driven` added as the cost-blind ablation.
   The "~27% lower cost" exploratory number is void — it was computed against a mismatched
   objective with no fresh evidence.
2. **Done — pre-registered and run.** `docs/research/PROTOCOL_REGISTRATION_31OCT.md`
   (committed before the run, decision rules fixed), `scripts/run_protocol.py`, 13 scenarios ×
   30 seeds × 1000, results + verdicts in `docs/research/PROTOCOL_RUN_31OCT_RESULTS.md` and
   `examples/results/protocol_31oct/manifest.json`. Use only numbers from that file on a slide,
   with the scenario ID and `SIMULATED` tier.
3. **Decided — not ported.** Recorded with reasons in
   `docs/architectures/04_SCIENTIFIC_ENGINE_VDER_CAIR.md` (the 5.0 archive has EWMA design
   text only, no code; the generator has no drift; no live time series yet).
4. **Done on the GPU, minus our own prints.** `qualityrelay17/anomaly.py` +
   `scripts/train_anomaly.py` (STFPM ResNet-18, teacher/student ONNX for Hailo, Resource-ledger
   manifest per run) ran on a Brev **NVIDIA L4** ($0.85/h, ~$0.3 total): synthetic-cad
   `SIMULATED` image AUROC 0.880; MVTec `screw` 0.948 and `bottle` 1.000 (`EXTERNAL_DATASET`,
   CC BY-NC-SA). Manifests `docs/research/runs/`, write-up and caveats
   `docs/research/ANOMALY_GPU_RUN_31OCT.md`. **Still missing: a `PHYSICAL_CAPTURE` run** — needs
   HyorinmaruK's Pi images (`data/prints/good|defect/`); one command, see the write-up. Hailo
   compile not attempted (adilnurgg). The other seven NVIDIA adapters stay `NOT_CONFIGURED`.

5. **18.1 science P0 (branch `science/18-1-p0`).** SCI-01/02 cost accounting fixed (peer
   requests were never charged); SCI-03 re-run: `voi_driven` verdicts unchanged, the 17.1
   request slice's "cheaper" result reversed. SCI-05..08: Gate-A B0..B7 + ablations, 14
   registered scenarios, pre-registered. **Primary result NEGATIVE**: at default prices B7 holds
   every part; it beats B0 only when holds are priced as review labour or messages are cheap.
   Pitch-approved claims: `docs/research/COLLECTIVE_GATE_A_RESULTS_31OCT.md` section 4.

6. **18.1 SIM-01..07 (branch `science/18-1-sim`).** Digital factory engine (own DES, Slot/Tab,
   CONWIP, failures, operators, review/rework, multi-site), 18 scenarios with truth hashes, CAD
   widths measured from STL, SciPy pairing + MILP capacity plan, Monte Carlo ROI, API records +
   proposed schema for adilnurgg (`docs/research/sim_api/`). Product config safer + cheaper per
   good unit in 15/15 scenarios, throughput kept in only 4/15; hold-all cuts throughput 82%.
   Pitch claims: `docs/research/SIM_18_1_RESULTS.md`.

Reviewer for this branch: adilnurgg or HyorinmaruK (one review per `TEAM_OWNERSHIP_AND_GITHUB.md`;
no safety/actuation code touched).

## adilnurgg — backend, mesh, security

1. Provision `HARDWARE_STATION_KEYS` in `api.py` with real per-station secrets (currently
   empty by design — both new endpoints 503 until you do this). Agree on the station ID list
   with HyorinmaruK first (`slot`, `tab`, `sorter`, plus vision stations once wired).
2. Review `hardware_ingest.py` for anything that should route through `EvidenceLedger.append`
   automatically rather than just returning a signed object from the API — right now the two
   new endpoints sign but don't persist; decide if that's the right boundary or if persistence
   belongs in this layer.
3. Wire `bin_ack_evidence`'s returned `event_id` through to
   `actuation.SorterInterlock.acknowledge(action_id, actual_bin, sensor_event_id)` — that's the
   one remaining connection between "sensor fired" and "route confirmed."
4. Run E12/E13 from `PHYSICAL_TEST_PLAYBOOK.md` against your actual `SorterInterlock` once
   HyorinmaruK has the bin sensor built — confirm the mismatch/duplicate rejection you already
   coded actually holds under a real sensor's timing and bounce, not just unit-test timing.

## HyorinmaruK — mechanical, physical test, presentation

1. Run the repeatability screen (`PHYSICAL_TEST_PLAYBOOK.md` §1) **before** wiring anything
   else — it decides your real `uncertainty_mm`, which the firmware currently sends as a
   placeholder `0.05`.
2. Build the slot/tab station per `esp32_station.ino` and the isolated bin sensor per
   `bin_sensor.ino`. Decide now whether the potentiometer is Tier A (fault-injection dial,
   today) or Tier B (real mechanical linkage, only if time remains) — see the playbook's
   honesty note before committing to Tier B.
3. Run the five physical acceptance tests in the playbook (E02, E07, E12, E13, and the
   isolation check) at least twice each before the judges see any of it.
4. Own the demo script: lead with `safe_mesh.py` rejecting a duplicated/stale/mixed-origin
   evidence set first — it's your most concrete, already-working result, and it's a better
   opener than the VOI number, which is still exploratory (see above).
5. Presentation: be explicit on stage about which evidence tier each shown result is
   (`SIMULATED` vs `PHYSICAL_CAPTURE` vs `VERIFIED_PHYSICAL`) — your own `STATUS_AND_GATES.md`
   already has the language for this, use it verbatim rather than improvising softer claims
   under demo pressure.

## Fourth teammate (if confirmed) — QA/reliability

1. Add a property-based test for `vder.action_scores` (monotonicity: raising `prior` should
   never lower `expected_loss` for a fixed action; `expected_entropy` must stay in `[0,1]`) —
   the existing tests check specific values, not the space around them.
2. Try to break the new hardware endpoints: malformed ADC values, specimen IDs with injection-
   style characters, replayed `event_id`s — add whatever you find to `tests/test_hardware_ingest.py`.
3. Keep `docs/research/EXPERIMENT_PROTOCOL.md`'s per-run manifest requirement honest — confirm
   every benchmark run anyone shows tomorrow actually has its seed/commit/params logged, not
   just the ones that looked good.

## End-of-day go/no-go (same spirit as `STATUS_AND_GATES.md`)

- If `HARDWARE_STATION_KEYS` isn't provisioned by early afternoon, the live hardware loop
  becomes a recorded fallback clip — decide that explicitly, don't discover it on stage.
- If the Tier-B potentiometer linkage isn't screened and passing by the time you need to
  freeze features, fall back to Tier A. A working dial beats a half-trusted sensor.
- Don't let "run the full pre-registered protocol" slip past the point where there's no time
  left to rehearse — a smaller honest result you can explain beats a bigger one you ran once
  and didn't have time to sanity-check.
