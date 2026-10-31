# Gate-A B0..B7 comparison: pre-registration (Bakdaulet, 31 Oct, 18.1 SCI-05..08)

**Status:** committed BEFORE the full run. Code: `qualityrelay17/experiments/`. Runner:
`scripts/run_collective_eval.py`. Everything is `SIMULATED`; deterministic mock agents only
(17.1 Gate A). No LLM, no physical data.

## What is being compared

B0..B7 and ablations as defined in `docs/research/COLLECTIVE_17_1_BAKDAULET.md` section 5,
mapped in the docstring of `qualityrelay17/experiments/collective_baselines.py`.
`B4` (free-form chat), `B7-specialist_roles` and `B7-structured_protocol` need a live LLM
backbone and are reported as `NOT_CONFIGURED`. `B2` is a context-only upper bound (reads every
capture, ignores budget); its information price is shown and it is never a "winner".

## Fixed design

- Test lots: seeds 0..29, 1000 parts each. Calibration: held-out nominal seeds 1000..1009, the
  same calibration for every scenario (S02..S08, S14 are therefore out-of-calibration stresses).
- Paired: within a (scenario, seed) every policy sees identical parts and an identical pool of
  captures (3 per sensor), pays identical prices, and adaptive policies share one budget (6
  observations unless the scenario says otherwise).
- Prices: registered `economics.Costs()` (inspection 0.5, peer_request 0.3, hold 2.0,
  escaped 150) unless the scenario overrides them. Every observation and every request
  (including timed-out ones) is charged once (SCI-01/02).
- Scenarios S01..S14: `qualityrelay17/experiments/scenarios.py`. **Primary scenario: S01 with
  registered costs.** S11..S13 are a pre-declared cost sensitivity, not a search for a
  favourable price.

## Pre-run observation that shaped this registration (disclosed, not hidden)

A 5-lot smoke run during development showed that at the registered prices B7 holds every part
without inspecting (holding = 2.0 is cheaper than paying 0.8 per requested observation), so it
releases nothing. This is the Bayes-optimal response to the registered cost table, and it is
reported as such, not patched. S11..S13 were added to locate where that stops being true.
No other results were looked at before this registration.

## Contrasts and decision rules (per scenario, cluster bootstrap over the 30 lots, 95%)

Contrasts: `qualityrelay17/experiments/collective_eval.py::CONTRASTS`.
- **Non-inferior on safety:** upper CI of the unsafe-PASS rate difference (A - B) <= +0.001.
- **Cheaper:** upper CI of the cost-per-unit difference < 0.
- **Throughput preserved:** lower CI of the released-good rate difference >= -0.01.

A claim "A beats B" requires all three. A cost win with a safety or throughput failure is
reported as a failure (SCI-04). 30 simulated lots are not 30 factories.

## Research gate (17.1 sec 6)

B7 counts as a positive Gate-A result only if, in S01, it passes all three rules against B0
**and** at least one registered ablation (provenance, cost_awareness, adaptive VOI = B5)
removes or shrinks the advantage. Otherwise the result is published as negative, with the
scenarios in which B7 does or does not help.
