# P1: where does decentralisation pay? Pre-registration (Bakdaulet, 31 Oct, before any run)

**Status:** committed BEFORE the code that runs it exists. Everything is `SIMULATED`, with
`ILLUSTRATIVE_ASSUMPTION` timings, prices, image sizes and link speeds. Plan:
`AGENTS_PLAN_1NOV.md` §3 P1.

## Question
Gate-A found that splitting the decision across agents adds only message cost when every agent
could see everything. A real line differs from that mock world in one respect we can model
honestly: **raw camera evidence is large and the plant uplink to a central server is finite and
can fail.** Does deciding at the stations (agents exchanging ~100-byte summaries over the line LAN)
beat shipping raw frames to one central decision server, and when?

## Arms (same parts, same sensor noise, same service noise: common random numbers)
| Arm | Decides where | Policy | What crosses the network |
|---|---|---|---|
| A0 `isolated` | each station alone | rules + FIFO (today) | nothing |
| A1 `central` | one central server | Bayes + optimised pairing | every camera frame (raw) + caliper readings, over the uplink |
| A2 `agents` | the six station agents | Bayes + optimised pairing | agent messages (summaries) over the line LAN |

A1 and A2 use the identical decision formula and calibration; they differ only in where the
evidence must travel. A1 is modelled as: each frame is uploaded through one shared uplink (FIFO,
transfer time = bytes x 8 / bandwidth); the part waits at its line until the central part-gate
decision is possible; if its evidence has not reached the server within the SAFE-MESH deadline
(`evidence_deadline_s` = 120 s) the decision is HOLD (missing evidence) and the part goes to expert
review; a pair decision during a server outage waits for the server up to the same deadline, then
HOLD. Uploads continue in the background after a timeout. A2 and A0 need no uplink.
**Assumption (stated, not tested):** the line LAN between stations stays up when the uplink or the
central server is down.

## Scenarios (single site F01 conditions, two cameras phone + Pi per line, as in the registered SIM)
| ID | Uplink | Central outage | Frame size |
|---|---|---|---|
| P1-S0 | 100 Mbit/s | none | 2.0 MB |
| P1-D1a | 20 Mbit/s | none | 2.0 MB |
| P1-D1b | 4 Mbit/s | none | 2.0 MB |
| P1-D1c | 2 Mbit/s | none | 2.0 MB |
| P1-D2 | 20 Mbit/s | 1800-3600 s (30 min) | 2.0 MB |
| P1-D1b-small | 4 Mbit/s | none | 0.5 MB (compressed frame, sensitivity) |

2.0 MB is a typical 12 MP JPEG; at the F01 rate (~400 parts/h, 2 frames each) the average raw load is
~3.6 Mbit/s, so D1b sits near saturation and D1c above it. These numbers were chosen from that
arithmetic, before running.

**D3 (local camera drift) is dropped, with the reason, before running.** At the registered prices the
Bayes hold threshold is hold / (hold + escape) = 2 / 152 = 1.3%. With the calibrated phone camera
(sens 0.94, prior 0.030), the precision of a flag stays above that threshold even at a 40%
false-positive rate (6.9%), so every flag is held whatever the calibration says. Online
recalibration cannot change a single decision under this cost table, so D3 could only show "no
effect". (It would also test learning, not decentralisation: a central server could learn the same.)

## Seeds, size
Seeds 0..19, 200 pairs per run, model calibrated on held-out seeds 1000..1009 (as SIM).

## Metrics (per run; paired over seeds)
Good assemblies/h, escapes per 1000 shipped (ground truth, evaluator only), holds (part + pair),
holds for missing/late evidence, mean cycle time, **network bytes per part**, mean evidence latency
(A1), cost per good unit at the SIM-04 assumption modes.

## Decision rules (fixed now), contrast A2 - A1 per scenario, cluster bootstrap 95% CI over seeds
- **Safety:** upper CI of the escape-rate difference <= +1 per 1000 shipped.
- **Decentralisation pays** in a scenario if safety holds AND the lower CI of the good/h difference
  is > 0 (strictly better throughput). Fewer bytes alone does not count as "pays".
- **No difference expected** in P1-S0 (prediction, registered): good/h, escapes and holds within CI
  of 0; only bytes differ. If S0 shows a throughput difference, that is a modelling artefact and is
  reported as such.
- A2 - A0 is reported as context with the same rules (it mixes policy and architecture).
- Every scenario is reported, including those where decentralisation does not pay.

## What this can and cannot show
It can show the conditions under which shipping raw evidence to a central decider costs throughput
or safety, and how much the summary protocol saves in bytes. It cannot show that agents are smarter
than a central server: with the same information they compute the same decision (360-run check).
