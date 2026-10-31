# 18.1 science P0 results: fair cost accounting + Gate-A B0..B7 (Bakdaulet, 31 Oct)

Everything below is **SIMULATED** (toy generator, deterministic mock agents, illustrative
prices). No LLM, no physical part, no factory. 30 simulated lots are not 30 factories.

Registration: `COLLECTIVE_GATE_A_REGISTRATION.md` (committed before the run, `8a864eb`).
Data: `examples/results/collective_gate_a/` (registered, clean tree),
`examples/results/collective_gate_a_exploratory/` (post hoc), and
`examples/results/protocol_31oct_rerun_18_1/` (SCI-03). Reproduce:
`python scripts/run_collective_eval.py` (~60 s), `--exploratory` (~30 s). A second run on a clean
tree gave byte-identical result files.

## 1. SCI-01/02: cost-accounting audit and fix

- **Found:** `structured_request_lite` reported `request_cost_paid` but `economics.calculate`
  never added it to the total cost. Every 17.1 "selective request is cheaper" number was
  computed with free messages.
- **Checked:** `voi_driven` was already charged 3 + 1 per purchase (fixed in PR #1). Every
  factory policy now lists the signals it consumed, and `calculate` refuses a row whose
  charge differs from that list, or a request-capable row that hides `peer_requests`.
- **Fixed:** inspections, peer requests and compute calls are separate cost lines.
  `Costs.peer_request = 0.3` (illustrative; 0 only when set explicitly), and
  `Costs.compute_call = 0` because every agent here is a mock.

## 2. SCI-03/04: re-run of the 31 Oct protocol with corrected accounting

13 scenarios × 30 seeds × 1000, same seeds as the original run (S13, industry costs, makes 0 requests, so only S01..S12 can change). **Only
`structured_request_lite` costs changed. Every `voi_driven` verdict is identical**
(`manifest.json` verdict blocks compare equal).

| Comparison (paired, per lot of 1000) | old accounting | corrected |
|---|---|---|
| request − fusion, cost | cheaper in 12/12 scenarios (−48 … −110) | **more expensive in 12/12** (+125 … +223) |
| request − rules, cost | cheaper in 12/12 | **more expensive in 9/12** (CI above 0); S08 CI includes 0; still cheaper only in S03 and S09 |

`structured_request_lite` also requests Pi evidence for **90%** of parts at S01 (the one-bit
phone signal problem already noted in its docstring), so "selective" does not describe it.
**Retract** any statement that the 17.1 request slice saves money.

## 3. Gate-A B0..B7 (SCI-05..08)

**Design:** hidden-truth environment, three captures per sensor per part, typed
REQUEST/RESPONSE/TIMEOUT messages, and belief recomputed from the ledger after every
observation. The caliper enters as a continuous Gaussian posterior and lineage dedupe
works by `source_root`. Selection uses two-step look-ahead VOI, with a deterministic
SAFE-MESH hard gate. B4, B7-specialist_roles and B7-structured_protocol are
`NOT_CONFIGURED` (they need an LLM).

### 3.1 Primary scenario S01 (registered prices): NEGATIVE

| policy | unsafe PASS /1000 | released good | false HOLD | obs/part | requests/part | cost/unit | cost/good unit |
|---|---|---|---|---|---|---|---|
| B0 rules | 3.53 | 0.799 | 0.131 | 2.95 | 0 | 2.40 | 3.00 |
| B1 single agent, fixed set, Bayes | **0.50** | 0.808 | 0.121 | 2.95 | 0 | **1.93** | 2.39 |
| B2 upper bound (all 9 captures) | 0.07 | 0.895 | 0.026 | 8.85 | 0 | 4.64 | 5.19 |
| B3 majority vote | 21.73 | 0.915 | 0.005 | 2.95 | 0 | 4.86 | 5.31 |
| B5 structured, fixed order | 2.73 | 0.858 | 0.067 | 2.22 | 2.23 | 2.47 | 2.88 |
| B6 single agent + VOI | 2.77 | 0.853 | 0.072 | 1.94 | 0 | 1.68 | 1.96 |
| **B7 SAFE-MESH + VOI** | 0 | **0.000** | 1.000 | 0 | 0 | 2.00 | — |
| B7 − cost_awareness (entropy) | 2.83 | 0.897 | 0.025 | 2.30 | 2.31 | 2.47 | 2.75 |

**Verdict.** At the registered prices B7 holds every part without inspecting: HOLD (2.0)
costs less than the cheapest plan that could clear a part, since each requested observation
costs 0.5 + 0.3. This is the Bayes-optimal answer to that cost table, and it was disclosed
before the run. B7 vs B0 passes safety and cost and **fails throughput** (−0.799 released
good). **The research gate is not met.** The real defect is in the cost model: a HOLD is
priced as if the part were not lost or delayed. That is an SIM-04 input, not something the
policy should patch.

### 3.2 Where B7 does work: pre-declared price sensitivity S11..S13

| scenario | B7 vs B0 cost/unit | unsafe-rate diff [95% CI] | released-good diff | all 3 rules |
|---|---|---|---|---|
| S11 messages 0.05 | −0.63 [−0.78, −0.46] | −0.0008 [−0.0018, +0.0004] | +0.053 | **yes** |
| S12 hold 5.0 | −0.33 [−0.47, −0.17] | −0.0007 [−0.0017, +0.0005] | +0.065 | **yes** |
| S13 hold 5.0 + messages 0.05 | −0.81 [−0.95, −0.66] | −0.0006 [−0.0016, +0.0005] | +0.066 | **yes** |

In those scenarios, decomposed with the registered contrasts:
- **Adaptive VOI contribution (B7 vs B5):** cheaper in all three (−0.12 … −0.19/unit), with
  equal safety. Throughput is preserved but is 0.5 pp lower in S11. This is the one
  mechanism whose ablation shrinks the advantage, as the gate requires.
- **Price of decentralisation (B7 vs B6):** B7 costs exactly its message bill more
  (+0.096/unit at 0.05 per message, +0.58 at 0.3), with identical safety. In this mock world,
  splitting ownership across roles adds no information. Roles only add messages.
- **Communication + fusion vs voting (B5 vs B3):** unsafe −19/1000 and −2.2 … −3.0/unit, at
  −5 pp throughput. Majority voting lets two clear cameras outvote the caliper.
- **Adaptive vs fixed, single agent (B6 vs B1):** cheaper and +4.4 pp throughput, but
  **+2.3 unsafe/1000** (fails the safety rule). Saving observations costs safety.
- **Hard gate (B7 vs B7−hard_gate) and provenance (B7 vs B7−provenance):** zero difference.
  VOI already reads phone + caliper before any PASS, and it never asks for the Pi frame, so
  duplicated frames never reach it (exploratory X01/X03: 0 duplicates received). Lineage is
  verified mechanistically by tests, not by an effect size.
- **Cost awareness (B7 vs entropy):** cheaper by 0.1/unit at S11/S12, but −3.6 … −4.4 pp
  throughput. Not a clean win.

### 3.3 Unregistered secondary observations (labelled as such)

- **B1 vs B0** (same three readings, calibrated Bayes instead of an OR rule) is the most
  robust result: lower unsafe PASS **and** lower cost in 13/14 scenarios. The exception is
  S06 (Pi always offline), where B0 holds everything and B1 releases parts at
  +2.7 unsafe/1000. In S02 (drift) B1 is far safer, but throughput is −9.5 pp.
- **Correlated cameras (S04):** even the upper bound B2 has 8.5 unsafe/1000, worse than B1.
  Re-reading cameras that share a lighting error makes the independence-assuming posterior
  overconfident. This is the 17.1 sec 4.3 warning, now measured.
- **Out-of-calibration stress (S03 noisy cameras, S08 noisy caliper):** every adaptive
  policy's unsafe rate rises to 5–11/1000. They trust the frozen nominal calibration.

## 4. Claims the pitch may use (Bakdaulet signs these; HyorinmaruK, use only these)

1. "With honest accounting, the earlier 'selective peer request saves money' result reversed.
   We published the correction." (§2)
2. "In simulation, a calibrated Bayesian fusion of the same three sensors had about 7× fewer
   unsafe passes than the fixed rule and was cheaper (S01: 0.5 vs 3.5 per 1000)." Say
   `SIMULATED` and "toy generator". (§3.3, secondary)
3. "Our full SAFE-MESH + VOI agent fails its own pre-registered gate at our default prices,
   because it rationally holds everything. It wins only when holding is priced realistically
   or messages are cheap, and multi-agent ownership adds only message cost in this mock
   world." (§3.1, §3.2)

**Do not say:** "21 agents collaborate", "VOI saves X%", "collective intelligence beats a single
agent", or any number without its scenario ID and `SIMULATED`.

## 5. Not done in this PR (honest status of the 18.1 board, Bakdaulet section)

- SCI-05 B4 and two ablations: `NOT_CONFIGURED`. They need a live LLM (adilnurgg AGENT-04).
- SCI-07 "camera disagreement" is covered by S03/S04; "Pi offline" by S06/S07.
- SIM-01..07: not started in this PR (the level-1 twin is PR #3). Next: hold/lost-throughput
  cost (SIM-04 fixes §3.1's root cause), scenario manifest (SIM-02), and station scaling
  (SIM-06).
- VISION-01..05: blocked on HyorinmaruK's physical captures (PHY-06). The GPU run status is
  unchanged (`ANOMALY_GPU_RUN_31OCT.md`).
