# Nebius LLM, Scientific AI, GPU

**Owner:** adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Resource classes
1. Scientific AI platform (team-scoped notebook/agent+ hosted scientific models): access assigned by event credentials, one request/team.
2. Nebius Cloud Academy 16 H100 GPU **shared across entire event**, with possible queues.
3. Nebius Token Factory OpenAI-compatible inference API: model access depends on the team's provisioned token.
Do NOT equate access to one with access to all three.

## Inference contract
Model ID loaded from authenticated live `/v1/models`, API key from env, 15-second timeout, bounded rounds, role-specific tool schema, test recorded costs. Never store keys or prompts containing raw proprietary factory files in the artifact. Model text never accepted as metrology, financial truth or authorization.

## Reproducibility
Save model ID, prompt/schema hash, temperature, random seed where supported, token usage and exact evidence set. When LLM unavailable, use deterministic safety rule fallback. Compare no LLM vs single LLM vs 2-7 specialists vs 21 roles under budget. Track hallucination and tool use validity as primary safety metrics.

## Current code
`nebius.py` provides opt-in adapter; not called using actual credentials here. The user's earlier 14.2 package contains a richer legacy LLM tool loop; align its tests/contracts before replacing, and verify live 2026 model API differences.

## Acceptance
At least one authorized real inference with recorded model/version and exact evidence, and an outage demonstration preserving HOLD behavior before claiming deployed integration.

