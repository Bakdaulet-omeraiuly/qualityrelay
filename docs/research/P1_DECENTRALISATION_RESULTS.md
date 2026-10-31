# P1 results: decentralised agents vs a central raw-evidence server (Bakdaulet, 31 Oct)

Registration: `P1_DECENTRALISATION_REGISTRATION.md` (commit `3e74f30`, before the code existed).
Run: `python scripts/run_p1.py` on clean tree `04374e0` (`dirty_before_run: false`), 8 s.
Data: `examples/results/p1_decentralisation/results.json`.

> **Re-run after integration (31 Oct, later, commit `50287e7`, clean tree):** the agents now exchange evidence over
> adilnurgg's PeerBus (role-signed messages, ACL, VERIFY), so A2's bytes were re-measured. Every other
> number is identical to the registered run (same decisions, 360-run equivalence). A2 sends
> **4,719 bytes per part** (signed requests, responses and decision proposals), not 689; A1 sends
> 4.0 MB. The tables below keep the registered run; read "689 B" as 4.7 kB for the current code. Everything is **SIMULATED**, with
illustrative timings, prices, frame sizes and link speeds. 20 seeds x 200 pairs per arm and
scenario, common random numbers (identical parts in every arm, checked by truth hash). No smoke run
was looked at before the registered run.

## Main table (means over seeds; A2 − A1 with 95% cluster-bootstrap CI)

| Scenario | good/h A0 rules | good/h A1 central | good/h A2 agents | A2 − A1 good/h | A2 − A1 escapes /1000 | bytes/part A1 → A2 | A1 holds for missing / late evidence | Verdict |
|---|---|---|---|---|---|---|---|---|
| S0 100 Mbit/s | 201.9 | 195.7 | 195.8 | +0.1 [−0.2, +0.5] | 0 [0, 0] | 4.0 MB → 689 B | 0 | does not pay (as predicted) |
| D1a 20 Mbit/s | 201.9 | 195.4 | 195.8 | +0.5 [+0.02, +1.1] | 0 [0, 0] | 4.0 MB → 689 B | 0 | pays by the rule; **negligible** (+0.2%) |
| D1b 4 Mbit/s | 201.9 | 104.4 | 195.8 | **+91.4 [+74.1, +107.0]** | 0 [0, 0] | 4.0 MB → 689 B | 40.9 / run | **pays** |
| D1c 2 Mbit/s | 201.9 | 43.2 | 195.8 | **+152.7 [+141.7, +164.1]** | 0 [0, 0] | 4.0 MB → 689 B | 155.2 / run | **pays** |
| D2 30 min outage | 201.9 | 89.7 | 195.8 | **+106.1 [+95.1, +117.4]** | 0 [0, 0] | 4.0 MB → 689 B | 50.7 / run | **pays** |
| D1b-small 4 Mbit/s, 0.5 MB frames | 201.9 | 195.3 | 195.8 | +0.5 [+0.05, +1.1] | 0 [0, 0] | 1.0 MB → 689 B | 0 | pays by the rule; **negligible** |

Escapes per 1000 shipped: A1 = A2 = 1.04 in every scenario; A0 (rules) = 3.90. Cost per good unit at
the SIM-04 assumption modes: A2 1.314; A1 1.314 (S0, D1a, D1b-small), 1.517 (D1b), 2.102 (D1c),
1.562 (D2); A0 1.729. Conservation holds in every run.

## Reading
1. **Prediction S0 confirmed.** With a fast uplink, the central server and the agents make the
   same decisions; only the bytes differ (about 850x fewer with signed PeerBus summaries; 5,800x in the registered run before the protocol carried signatures). This is the honest base
   case: decentralisation is not smarter.
2. **It pays when the uplink cannot carry raw frames.** At 4 Mbit/s the raw load (~3.6 Mbit/s
   average, bursty) saturates the link: evidence arrives 54 s late on average, 41 parts per run miss
   the 120 s SAFE-MESH deadline, are held and queue at the single review station, and good output
   halves. At 2 Mbit/s it falls to 22%. The agents, which send ~0.7 kB per part over the line LAN,
   are unaffected.
3. **A 30-minute central outage** (in a run of about an hour) halves central output; the agents keep
   deciding because the line LAN is assumed up.
4. **Safety is never traded:** escapes are identical in A1 and A2 in every scenario, because a part
   whose evidence is missing is held (SAFE-MESH), never passed.
5. **The obvious engineering fix also works:** compressing frames to 0.5 MB removes the 4 Mbit/s
   penalty (D1b-small). So the advantage is conditional on link capacity vs raw evidence volume,
   not universal.
6. D1a and D1b-small meet the registered "pays" rule only by +0.5 good/h (0.2%). We report them as
   negligible; they come from the ~2 s upload latency.

## Context: agents (Bayes) vs today's rule (A2 − A0, same in every scenario)
good/h −6.1 [−14.8, −0.4], escapes −2.85 [−4.92, −1.29] per 1000 shipped, cost per good unit
−0.415 [−0.721, −0.178]. Safer and cheaper, with ~3% lower throughput; this mixes the policy and the
architecture and matches the earlier SIM finding.

## Limits (must accompany any claim)
- The size of the D1b/D1c/D2 effect depends on modelling choices: parts wait at the line up to the
  120 s deadline, a missing-evidence hold goes to one review station (45 s), and one shared uplink.
  A different central design (local fallback at the edge) would shrink the gap, and that fallback
  *is* a form of decentralisation.
- The LAN-up assumption during an uplink outage is stated, not tested.
- Frame size and link speeds are assumptions (2 MB 12 MP JPEG; plant uplinks of 2–100 Mbit/s).
- One single-site scenario family (F01 conditions); multi-site lines were not run.

## Claim the pitch may use (with `SIMULATED`)
"In our simulated line, when the plant uplink cannot carry raw camera frames (4 Mbit/s for two
2 MB frames per part) or the central server is down for 30 minutes, station agents that exchange
~5 kB of signed summaries per part kept full output while a central raw-evidence server lost half of it, with
identical escapes. With a fast link they are equivalent; decentralisation is not smarter, it is
more robust to the network." Scenario IDs P1-D1b, P1-D2, P1-S0.
