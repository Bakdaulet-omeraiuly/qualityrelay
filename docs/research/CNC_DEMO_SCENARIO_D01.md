# CNC cell demo scenario (D01) — what it is and what it is not

**Source tier: SIMULATED.** Everything in this scenario is produced by the discrete-event engine in
`qualityrelay17/sim/` and rendered in the Studio's 3D Lab. No CNC machine, robot, conveyor or caliper is
controlled or read. The G-code shown is illustrative text, not a post-processed program for any machine.

## The story the scenario tells

1. Two CNC machines (one per part kind) are each fed from a stock crate by a loading robot. One part per blank.
2. The shift starts with a **wrong tool offset**: slot openings come out 1.6 mm too narrow, tabs 1.6 mm too wide
   (the size of the seeded `S-DEF` / `T-DEF` specimens in `examples/cad/`). **The whole first batch is defective.**
3. The **camera gate** flags gross size errors (> 0.8 mm, 90 % sensitivity) and **counts** them. When it has counted
   **N defects among the last 2N inspected parts** (N = 5–10, default 6 on the website) the **whole line stops**: both
   machines, at the same moment, so no more blanks are cut with a bad program (`halt_scope = 'line'`).
4. **Quarantine** (`contain_suspect`): every part made with the suspect program goes to the **caliper chamber**, flagged
   or not, including parts already waiting in the pairing buffer. Parts the camera never flagged are therefore caught
   too.
5. In the chamber the **measurement agent** measures **every dimension** (slot: opening, length, height, base, rail;
   tab: width, length, height) with a digital caliper (a CMM or gauge in another factory) and writes one row per
   dimension to **`chamber_measurements.csv`**, in the same column format as the physical caliper CSV
   (`docs/engineering/templates/specimen_measurements.csv`), evidence tier `SIMULATED`. Nonconforming parts leave on
   the **reject conveyor** into the scrap bin; each is a wasted blank.
6. **CNC agent:** reads the CSV, takes the mean deviation of the functional width rows (`slot_inner_width` / `width`)
   of the quarantined parts, and rewrites the cutter-compensation (wear) line of its G-code. The change is checked
   against a ±2 mm limit, **approved by an operator** (timed work on the operator pool), **applied**, and that machine
   **restarts** at once.
7. Parts cut with the new program are in tolerance. They clear the camera, are paired slot with tab, and the robot
   **assembles the slot-and-tab toy**. Seeds 0–2, 60 pairs: 0 escaped assemblies, 60/60 shipped good.
8. **Today's line (baseline):** same parts, same camera, same chamber. The machine keeps running; the chamber
   findings reach it only at the **scheduled audit** (interval is an adjustable assumption, default 30 min).
9. **Waste is counted** from the event log: blanks consumed, scrapped parts, parts made before the correction,
   machine time lost, time stopped, time to correction. Ground-truth counts are labelled as such.

The earlier per-machine behaviour (N consecutive flags stop one machine, flagged parts only) is still available:
`replace(BY_ID['D01'], halt_scope='machine', contain_suspect=False)`.

## Engine mechanics (engine.Factory)

| Parameter | Meaning | Default |
|---|---|---|
| `control` | `none` / `closed_loop` / `audit` | `none` (registered scenarios) |
| `halt_on_flags` | line scope: camera-detected defects (among the last 2N parts) that stop every machine; machine scope: consecutive flags of one kind that stop that machine | 3 (website: 6) |
| `confirm_n` | nonconforming chamber CSV rows the CNC agent needs before it proposes a correction | 3 |
| `max_correction_mm` | a larger proposed change is **refused**: nothing changes, the machine stays stopped (FAULT) | 2.0 |
| `audit_interval_s` | today's line: when chamber findings reach the machine | 1800 |

Safeguards: only parts made with the current machine state count toward a halt or a correction (parts made before
a correction are still in the pipeline for a while); a stopped machine whose flags the chamber does not confirm
resumes without any change (`RESUMED_UNCONFIRMED`); a refused correction is never re-proposed.

Scenario fields: `halt_scope` (`machine` / `line`) and `contain_suspect` (quarantine the suspect batch); both off for every
registered scenario. A machine that is stopped while waiting for its spindle gives it back, so no blank is cut during a stop.

Events (`line_events`): `HALT` (with `scope`, and for a line stop `defects_counted`, `window`, `contained`), `CHAMBER_CONFORMING`, `CHAMBER_NONCONFORMING`, `CORRECTION_PROPOSED` (with the CSV
rows it read, the G-code before/after and diff), `CORRECTION_APPLIED`, `CORRECTION_REFUSED`, `RESUMED`, `RESUMED_UNCONFIRMED`, `AUDIT`.

## Honesty notes

- Registered scenarios F01–F10 and M01–M05 are unchanged: the demo observations come from separate part-keyed
  random streams, and the truth tables were checked bit-identical before and after this change
  (`tests/test_sim_cnc_demo.py`, `test_fault_is_in_the_truth_table_and_the_demo_streams_leave_registered_parts_untouched`).
- The six agents make the same decisions as the line in every control mode (tested); the halt/correction events are
  traced as `ALARM` / `PROPOSE_SETPOINT` / `DECISION` messages, and the engine, not an agent, decides.
- Unmeasured parts enter the pair decision as the process prior (Bayes) or as the programmed nominal (today's rule).
  This is how the scenario is defined, not a claim that a camera score is a measurement.
- "Weeks of stopped production" is **not** a result of this scenario. The baseline's detection delay is the audit
  interval, shown as an assumption in the Run panel.
- Nothing here is physical validation. See AGENTS.md.

## Reproduce

```
python - <<'EOF'
from dataclasses import replace
from qualityrelay17.sim.engine import Factory, calibrate_part_model
from qualityrelay17.sim.scenarios import BY_ID
M = calibrate_part_model()
sc = replace(BY_ID['D01'], cameras=('phone',), sites=tuple(replace(s, inspection_lines=2) for s in BY_ID['D01'].sites))
for ctrl, pol, pr in [('closed_loop', 'bayes', 'optimized'), ('audit', 'rules', 'fifo')]:
    o = Factory(sc, 0, pol, pr, model=M, reprint=True, lane_by_kind=True, control=ctrl).run()
    print(ctrl, o['waste'])
EOF
```

Studio: `#sim`, scenario `D01`, button "★ Demo: CNC cell D01" (Compare mode), right dock tab "Loop".
