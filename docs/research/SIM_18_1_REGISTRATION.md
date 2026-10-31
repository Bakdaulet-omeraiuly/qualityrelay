# SIM-01..07 digital-factory experiment: pre-registration (Bakdaulet, 31 Oct)

**Status:** committed BEFORE the full run. Code: `qualityrelay17/sim/`. Runner:
`scripts/run_sim_18_1.py`. Everything is `SIMULATED`, with `ILLUSTRATIVE_ASSUMPTION`
timings and prices.

## Design
- **Factorial:** policy {`rules`, `bayes`} × pairing {`fifo`, `optimized`} on identical parts,
  sensor noise, service noise and failure times (common random numbers).
  - `hold_all` (the Gate-A B7 degenerate optimum) runs on F01 only, as a feasibility check.
- **Scenarios:**
  - F01..F10 single site (`qualityrelay17/sim/scenarios.py::GRID`);
  - M01..M05 multi-site (`MULTI`);
  - SC06/SC10/SC50 station scale tiers (`scale_scenario`).
- **Seeds:** 0..19 for F and M, 0..9 for SC. The bayes part model is calibrated on held-out
  seeds 1000..1009 at nominal conditions.
- **Primary contrast** ("the product configuration vs today"): `bayes+optimized` minus
  `rules+fifo`. Factor contrasts: `bayes+fifo − rules+fifo` (policy), `rules+optimized − rules+fifo`
  (pairing).
- **Metrics:** good assemblies/h, escapes per 1000 shipped, scrapped good parts, holds, hold
  inventory, downtime, operator time, cost per good unit, and profit/h at assumption modes. For
  the product contrast only, a Monte Carlo ROI / payback over the `economics_sim.ASSUMPTIONS`
  ranges, paired with the seeds.
- **Uncertainty:** cluster bootstrap over seeds, 95%.

## Decision rules (per scenario)
- **Safety:** upper CI of the escape-rate difference <= +1 per 1000 shipped.
- **Throughput:** lower CI of the good/h difference >= −2% of the baseline good/h.
- **Economics:** upper CI of the cost-per-good-unit difference < 0.

A configuration is "better" only if all three hold. ROI is reported as a distribution with
P(QR worse) and is labelled `SCENARIO_OUTCOME_NOT_MEASURED_SAVINGS`. It is never a saving.

## Pre-run observations disclosed
- A seed-0 smoke run of every scenario was looked at while debugging. It showed that optimised
  pairing can cut throughput under the WIP cap (it holds parts while waiting for a batch). That
  observation is why the design is factorial.
- With 5 seeds, the ROI interval was dominated by 1–2 escapes per run, so seeds were raised to 20.
- Under the SIM-04 assumption modes, a HOLD's direct cost (review labour) is ~0.38 cu. That
  contradicts the "hold 5.0 = review labour" label of Gate-A S12, which will be corrected in the
  results.
