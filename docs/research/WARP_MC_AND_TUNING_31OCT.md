# NVIDIA Warp rare-event Monte Carlo + post-hoc SIM tuning (Bakdaulet, 31 Oct)

Everything here is **SIMULATED**. Part 2 is **EXPLORATORY_POST_HOC**: it never replaces the
registered results in `SIM_18_1_RESULTS.md` or `COLLECTIVE_GATE_A_RESULTS_31OCT.md`.

## 1. NVIDIA Warp: the rare-event metric at 10⁷ parts per scenario

**Why.** Unsafe PASS happens 1–4 times per 1000 parts. The 30×1000 CPU benchmarks therefore
left wide intervals on the one metric that matters most.

**What.** `qualityrelay17/gpu/warp_mc.py` runs the Level-0 part generator and three decision
rules as Warp kernels:
- B0 = conservative rules;
- F = factory `collective_fusion`;
- B1 = Gate-A calibrated single agent, with a Gaussian caliper posterior and lineage.

The kernels run on Warp's CPU backend here; the same code targets CUDA on an NVIDIA GPU.

**Proof that it computes the same thing** (`tests/test_warp_mc.py`, in CI when warp-lang is
installed):
- decisions equal the CPU code **part for part** on seeded inputs, for all three policies, with
  outages and duplicated frames;
- the Warp generator matches the CPU generator in distribution;
- per-part paired counters reproduce the policy differences exactly.

**Run.** `python scripts/run_warp_mc.py --device cpu --parts 10000000`. That is 8 scenarios ×
10⁷ parts on an Apple CPU, about 9.4 M parts/s, ~1 s per scenario. Data are in
`examples/results/warp_mc/cpu/`. **The GPU run is pending:** both a restarted and a fresh Brev L4
instance were reachable over TCP, but SSH timed out at the banner from this network. Both
instances were stopped or deleted (≈$0.3–0.5 spent).

Unsafe PASS per 1000 parts (10⁷ parts each; paired 95% CI vs B0):

| scenario | B0 rules | F fusion (binary caliper) | B1 calibrated | B1 − B0 | F − B0 |
|---|---|---|---|---|---|
| S01 nominal | 3.34 | 3.51 | **0.37** | −2.96 [−3.00, −2.93] | **+0.17 [+0.17, +0.18]** |
| S02 drift 0.25 mm | 25.36 | 26.70 | 1.41 | −23.9 [−24.0, −23.9] | +1.34 |
| S04 shared lighting | 10.50 | 11.05 | 8.04 | −2.47 | +0.54 |
| S05 duplicated photo | 4.46 | 4.70 | 1.37 | −3.09 | +0.23 |
| S06 Pi offline | 0 (holds all) | 3.51 | 2.39 | **+2.39** | +3.51 |
| S08 noisy caliper | 5.78 | 6.09 | 3.24 | −2.54 | +0.30 |

**What the scale bought:**
- The B1 advantage is now pinned to ±0.04/1000.
- **New: the factory `collective_fusion` reference is slightly *less* safe than the rule in
  every scenario** (+0.17 … +1.34/1000; +3.5 in S06, where the rule holds everything). Thresholding the caliper to a bit throws away
  near-tolerance information. The calibrated Gaussian version (B1) fixes this. The 30k-part CPU
  runs could not resolve the effect.
- The between-lot SE (100 lots) equals the per-part SE, consistent with independent parts in
  this generator.
- Caveat: more parts tighten the interval of a **simulated** estimate. They do not make the toy
  generator more realistic.

## 2. Post-hoc tuning of the two knobs SIM flagged

**Design, fixed before running** (`scripts/tune_sim_18_1.py`):
- Tune on seeds 100–119, over F01/F02/F03/F08/M01/M05.
- **One global setting** for every scenario.
- Selection rule: pooled escapes must be ≤ those of bayes+FIFO; among those, pick the highest
  mean good/h relative to bayes+FIFO.
- Evaluate the chosen setting on the registered seeds 0–19 against rules+FIFO, using the
  registered decision rules.

Data: `examples/results/sim_18_1_tuning/tuning.json`.

**Pairing batch/timeout.** Grid: batch k ∈ {2, 4, 8} × timeout ∈ {none, 60, 180, 600 s}.
- **Chosen: k = 2, timeout 60 s**, giving 1.006 × bayes+FIFO good/h.
- There is a real trade-off. Bigger batches match better (k = 8, no timeout: 1.53 escapes/1000)
  but wait longer (0.94 × good/h).
- **On the evaluation seeds,** "better on all three" goes from **4/15 → 5/15** scenarios: it gains
  F01, F10 and M03, and loses F04 and F05 (which now just miss the throughput rule).
- The multi-site throughput loss shrinks from about −15% to −2%. Under drift/warping (F02/F03)
  the loss is still −6 … −9%, though escapes stay lower in all 15 scenarios.
- **Conclusion:** a modest improvement, not a fix. The policy's extra pair holds are what cost
  throughput, not the pairing.

**Evidence deadline under latency (M04, report only; SAFE-MESH policy owner: adilnurgg).**

| deadline | stale holds/run | good/h (bayes) | cost/good unit (bayes) | escapes/1000 (bayes / rules) |
|---|---|---|---|---|
| 120 s (current) | 285 | 50.3 | 3.22 | 2.4 / 2.4 |
| 300 s | 4 | 52.0 | 2.84 | 2.4 / 4.0 |
| 600–1200 s | 0 | 51.5 | 2.84 | 2.4 / 3.6 |

- About 300 s removes ~99% of stale holds and cuts cost per good unit by 12%, with **no safety
  change for the calibrated policy**.
- For the rule, the stale holds were incidentally catching defects: its escapes rise when the
  deadline is relaxed.
- Recommendation for adilnurgg: set the deadline from the measured evidence latency (plus margin),
  not a fixed 120 s, and pair a relaxed deadline with the calibrated policy only.
