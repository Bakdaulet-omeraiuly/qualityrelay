# CNC cell demo scenario (D01) — what it is and what it is not

**Source tier: SIMULATED.** Everything in this scenario is produced by the discrete-event engine in
`qualityrelay17/sim/` and rendered in the Studio's 3D Lab. No CNC machine, robot, conveyor or caliper is
controlled or read. The G-code shown is illustrative text, not a post-processed program for any machine.

## The story the scenario tells

1. Two CNC machines (one per part kind) are each fed from a stock crate by a loading robot. One part per blank.
2. The shift starts with a **wrong tool offset**: slot openings come out 1.6 mm too narrow, tabs 1.6 mm too wide
   (the size of the seeded `S-DEF` / `T-DEF` specimens in `examples/cad/`). The first batch is defective.
3. The **camera gate** flags gross size errors (> 0.8 mm, 90 % sensitivity) as well as surface defects. A flag sends
   the part to the **caliper chamber**; unflagged parts are **not measured** (`caliper_mode = flagged_only`).
4. In the chamber an operator measures **every dimension** (slot: opening, length, height, base, rail; tab: width,
   length, height) with a digital caliper and compares each with the CAD nominal (tolerance ±0.30 mm, illustrative).
   Nonconforming parts leave on the **reject conveyor** into the scrap bin; each is a wasted blank.
5. **Closed loop (QualityRelay):** three flags in a row stop the machine. Three confirmed chamber measurements give
   the deviation; a program change (cutter-compensation / wear line) is **proposed**, checked against a ±2 mm
   limit, **approved by an operator** (timed work on the operator pool), **applied**, and the machine **resumes**.
   Parts made afterwards clear the camera and are never measured again.
6. **Today's line (baseline):** same parts, same camera, same chamber. The machine keeps running; the chamber
   findings reach it only at the **scheduled audit** (interval is an adjustable assumption, default 30 min).
7. **Waste is counted** from the event log: blanks consumed, scrapped parts, parts made before the correction,
   machine time lost, time stopped, time to correction. Ground-truth counts are labelled as such.

## Engine mechanics (engine.Factory)

| Parameter | Meaning | Default |
|---|---|---|
| `control` | `none` / `closed_loop` / `audit` | `none` (registered scenarios) |
| `halt_on_flags` | consecutive camera flags of one kind that stop that machine | 3 |
| `confirm_n` | chamber confirmations before a correction is proposed | 3 |
| `max_correction_mm` | a larger proposed change is **refused**: nothing changes, the machine stays stopped (FAULT) | 2.0 |
| `audit_interval_s` | today's line: when chamber findings reach the machine | 1800 |

Safeguards: only parts made with the current machine state count toward a halt or a correction (parts made before
a correction are still in the pipeline for a while); a stopped machine whose flags the chamber does not confirm
resumes without any change (`RESUMED_UNCONFIRMED`); a refused correction is never re-proposed.

Events (`line_events`): `HALT`, `CHAMBER_CONFORMING`, `CHAMBER_NONCONFORMING`, `CORRECTION_PROPOSED` (with the
G-code before/after and diff), `CORRECTION_APPLIED`, `CORRECTION_REFUSED`, `RESUMED`, `RESUMED_UNCONFIRMED`, `AUDIT`.

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
