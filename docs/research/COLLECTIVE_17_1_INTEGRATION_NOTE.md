# Integration note: what's actually built against the 17.1 plan (31 Oct, evening)

`COLLECTIVE_17_1_BAKDAULET.md` is the full research plan, kept verbatim. This note says
exactly what exists in code right now, how it maps onto that plan's B0–B7 ladder, and what
is deliberately **not** attempted before presenting — so nobody overstates either document
against the other.

## Rating both, for the record

**`collective_fusion`** (added earlier tonight): calibrated Bayesian fusion of phone+Pi
votes, beating the naive OR rule at matched safety. Real, tested, shipped. Honest limit: it
contains no *request* — every source is unconditionally present in every row. It's a
stronger ensemble, not evidence of agency.

**Bakdaulet's 17.1 plan**: correctly names that exact gap with a precise, falsifiable test
(section 3.4's five criteria: information asymmetry, targeted request, new verified source,
behavior change, no-request control) and backs it with a second paper neither of us had
cited before (Choi/Zhu/Li, NeurIPS 2025, "Debate or Vote") that specifically argues most of
multi-agent debate's apparent benefit is just majority voting in disguise — which is exactly
why a voting-only baseline (B3) has to exist before any "communication helped" claim is
credible. As a research plan this is 9.5/10 — easily the most rigorous document in this
project. As a build-by-tomorrow plan, it's 17 new files, 8 baselines, 6 ablations, live LLM
integration, and a new UI: a multi-week program, not a last-night addition. Its own Gate
structure already says as much (Gate D: "not ready for factory").

## What's actually built tonight: `structured_request_lite`

One new policy in `factory.py`, not the `qualityrelay17/collective/` package — Gate A, in
the smallest form that still passes Bakdaulet's own 5-point test:

1. **Information asymmetry** — Pi evidence is withheld by default; every other policy in
   this file reads it for free, this one doesn't.
2. **Targeted request** — issued only when the phone-only surface posterior falls near the
   Bayes-optimal decision threshold (not "ask everyone, always").
3. **New verified source** — the Pi reading, when requested, is a genuinely independent
   observation already in the data model, not fabricated.
4. **Behavior change** — `decision_flip_from_request` is tracked and tested to be nonzero;
   a request that never changes anything would be theater, and the test suite would catch it.
5. **No-request control** — compared directly against `collective_fusion` (Pi always free):
   `structured_request_lite` matches it exactly on unsafe-pass rate while asking for Pi
   evidence ~90% of the time instead of 100%, at meaningfully lower cost (paired difference
   -50.45 per 1000 parts, cluster-bootstrap CI [-53.05, -47.90] — clearly non-zero).

**One honesty finding from actually running it, documented in the code, not hidden:**
`phone_suspect` is a single boolean sensor, so the "indecisive band" either catches the
entire not-flagged cluster or none of it — there's no graded middle with a one-bit sensor.
The ~90% request rate is a real, if blunt, instance of selective asking, not the smooth
cost/value curve a continuous confidence score would give. That upgrade (a real confidence
score per camera reading, not just a boolean) is the concrete next step for whoever builds
`qualityrelay17/collective/belief_state.py` for real.

## Added 31 Oct, evening (adilnurgg): the protocol layer, `qualityrelay17/collective/`

`structured_request_lite` above is one policy inside the simulator. What Bakdaulet's plan
section 3 actually asks for is the *protocol*: typed, signed messages between roles with
private information, an ACL, deterministic verification, and a trace that can be audited
against the five "not theatre" criteria. That now exists as a package, built so the B-ladder
runner can drive it without touching the simulator:

| Plan file | Built as | Notes |
|---|---|---|
| `message_schema.py` | `collective/messages.py` + `schemas/agent_message_v17_1.schema.json` | six kinds, role HMAC signature, admissible summaries |
| `peer_protocol.py` | `collective/peer_protocol.py` (`PeerBus`) | private stores, entitlement from `roles.py`, ownership map, deadline, request cost charged on issue |
| `provenance_graph.py` | bus `VERIFY` on top of existing `lineage.py` | DUPLICATE_SOURCE / STALE_EVIDENCE / BAD_SIGNATURE before delivery |
| `belief_state.py` + `adaptive_voi.py` | `collective/belief.py` (`BeliefModel`, `ReferenceBelief`, `from_likelihoods`) | **the boundary for Bakdaulet**: swap this one object; engine, ACL, trace, API unchanged |
| `decision_trace.py` | `collective/trace.py` | message-level provenance, belief before/after, decision vs control, narrative for the Evidence Room |
| `collaboration_engine.py` | `collective/engine.py` | one case end to end + control run + criteria 3.4 evaluated on the trace |
| API 7.3 | `POST /research/collective/run`, `GET …/runs/{id}`, `…/traces/{part}`, `…/manifest` | origin `TEST_FIXTURE`; `comparison` route waits for the B-ladder runner |
| Evidence Room 7.4 | web Agent Evidence Room: scenario select + narrative + criteria | single fixture case, no improvement claimed |

What it does **not** do, deliberately: no LLM in the loop (roles are code; AGENT-04 is the
Nebius smoke test), one process (not a network), illustrative likelihoods unless
`from_likelihoods(calibration.Likelihoods)` is used, and no benchmark — eight scenarios
(`collective/scenarios.py`) show each technical outcome once. For B5/B7 the runner should
build a `PeerBus` per simulated part from the generator's rows, charge `bus.cost_charged`
into the policy's cost line (SCI-02), and read `CaseResult.criteria` per part.

## Mapping onto the B0–B7 ladder

| Bakdaulet's ID | What it needs | Status tonight |
|---|---|---|
| B0 (conservative rules) | — | Already existed in 17.0 |
| B1 (single agent, constrained) | — | Not built |
| B2 (oracle upper bound) | — | Not built |
| **B3 (independent voting, no requests)** | Same evidence, no peer requests | **`collective_fusion` is a stronger-than-naive-voting instance of this** |
| B4 (free-form chat) | — | Not built; needs live LLM (Gate B) |
| **B5 (structured requests, fixed inspection order)** | Real peer exchange on partial evidence | **`structured_request_lite` is a minimal, deterministic instance of this** |
| B6 (single agent + adaptive VOI) | — | **`voi_driven` rebuilt 31 Oct (Bakdaulet):** calibrated two-axis posterior + one-step NetVOI that buys a genuinely fresh recapture/retake on the benchmark's own cost scale; `entropy_driven` is its B7−cost_awareness ablation; `collective_fusion` is its B7−adaptive_step ablation. Single-agent, not request-based — still B6, now a real one. Pre-registered run: `PROTOCOL_RUN_31OCT_RESULTS.md` |
| B7 (full structured + adaptive VOI) | Synergy of B5 and B6 | Not built — correctly, this needs B1–B6 to exist first as controls |

## What this does NOT claim

- Not a claim that 21 agents, or any LLM, collaborated — everything above is deterministic
  Python, exactly as Bakdaulet's own Gate A calls for before touching live models.
- Not a claim that `structured_request_lite`'s ~90% request rate is "the right" rate — it's
  an artifact of a boolean sensor model, stated as such above.
- Not a replacement for the full `qualityrelay17/collective/` package — that remains the
  correct target architecture for Gates B–D, scoped for after this event if the team
  continues the project.

## Updated collective-capability self-assessment

Previously rated 6.0/10: "nothing in the running code shows agents actually collaborating
to beat a single rule." With `structured_request_lite` passing all five of Bakdaulet's own
criteria on a real, tested, reproducible trace, plus `collective_fusion` as a legitimate B3,
this moves to roughly **7.0–7.5/10**: there is now a genuine, if minimal, evidence-seeking
mechanism with a measured, honest result — not yet the full B0–B7 ladder with live agents
and ablations that would justify a higher score. Say exactly this on stage: "a minimal,
tested instance of structured evidence-seeking, not the full research program" — Bakdaulet's
own document already gives you the right language for that sentence.
