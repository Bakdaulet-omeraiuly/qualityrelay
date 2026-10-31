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

## Bakdaulet — scientific engine

1. Review and, if you agree with the approach, merge the `voi_driven` wiring in
   `factory.py`/`benchmark.py`. If you don't agree with the placeholder sensitivity/
   specificity/cost values or the prior heuristic, replace them — you own this file.
2. Run the actual pre-registered protocol (30 seeds × 1000, the scenario grid in
   `EXPERIMENT_PROTOCOL.md`), not just my 10-seed exploratory check, before reporting any
   number publicly.
3. Decide whether the EWMA/SPC and truncated-normal clearance-risk math from the 5.0 archive
   (explicitly *not* in this 17.0 runtime per `04_SCIENTIFIC_ENGINE_VDER_CAIR.md`) is worth
   porting back in, or whether the team is intentionally scoping down to the binary VOI +
   surface-defect framing. Either is defensible — just make the choice explicit in the doc,
   not by default.
4. If GPU time is spent on anything, make it this: fine-tune a small anomaly-detection model
   (MVTec AD + your own captured prints) on one H100, hand the result to adilnurgg/HyorinmaruK
   for Hailo-8L deployment. Skip the other seven NVIDIA adapters — `STATUS_AND_GATES.md`
   already correctly marks them `NOT_CONFIGURED`, and that's fine to stay true.

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
