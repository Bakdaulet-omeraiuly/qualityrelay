# Assurance, Calibration, Scientific Validation and Security

**Owner:** Bakdaulet + 4th engineer  
**Status:** research design + partial reference implementation; see status below.

## Core assurance chain
Evidence acquisition -> identity/provenance -> calibration/quality -> authorization -> diagnosis/inspection proposal -> independent safety gate -> human approval -> physical actuation -> independent route acknowledgement -> evidence-based audit. Never omit a state in production claims.

## VVUQ principles
Verification: tests show the code implements its declared mathematics and contracts.
Validation: independent physical measurements show it addresses the real manufacturing problem.
Uncertainty quantification: image reliability, metrology repeatability, process prior drift, model class uncertainty, data shift and confidence intervals.

## Registered comparisons
- Phone-only, Pi-only, caliper-only, photo/photo-only, CAD/photo-only.
- Rule-based conservative multimodal fusion; Bayesian fusion with correlation; SAFE-MESH with V-DER; single LLM; 21-role planned system.
- Centralized full-information oracle (clearly upper bound); centralized restricted-information parity; decentralized.
- With and without each component: lineage, minority dissent, active inspection, dual camera, human gate, network outage.

## Key metrics
False PASS with exact interval; false HOLD; good throughput; inspection per part; 95% calibration CI; expected cost and service levels; attack success; physical route mismatch; replay duplicates; wall-clock latency. Highlight that zero observed unsafe PASS on 20 parts does NOT prove low true unsafe-pass probability.

## Negative controls
No camera model trained: baseline must not be mislabeled as NVIDIA. No Pi device: Pi process mocked must be labeled TEST_FIXTURE. Synthetic images must not count as real images; screenshot of video is not independent measurement. Hidden test lot/source split, no leakage from same part train->test.

## Novelty claim discipline
The user team proposes integration of correlation-aware evidence + active decision-focused inspection + assured intervention across decentralized factory sensors. The methods exist individually; our relative contribution is unproven until a comparable study shows a reproducible new tradeoff. Follow the 2026 235-study EAA digital twin review and HiddenBench multiagent failures as motivation, not as proof of novelty.

