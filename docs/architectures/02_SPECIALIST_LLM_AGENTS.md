# 21 Engineering Specialists and Nebius Reasoning

**Owner:** adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Scientific design
One executable model can serve 21 specialist roles with distinct system prompts, allowlisted tools, data domains, evidence requirements and bounded conversation depth. Twenty-one roles **do not mean 21 trained models** or 21 calls per specimen. Evaluate 1–7 relevant roles, then an explicit scientific comparator with single full-context LLM.

## Existing role registry
`qualityrelay17/roles.py` reuses and preserves the 21 roles from the user's 14.2 artifact. Each role includes `name`, `domain`, `tools`, `required_sources`. This copy is original team-owned code, not a third-party model checkpoint. New work: role selection should be driven by verified missing evidence, tool usefulness and budget, not number of agents.

## Allowed tool loop
1. Resolve legitimate caller identity and its role.
2. Inject only summarized authorized evidence with immutable event IDs, source origin and age.
3. Ask LLM for a tool call from the advertised role allowlist.
4. Validate role *again on server*; reject unrecognized tools or hallucinated IDs.
5. Execute deterministic tool; sanitize result; append tool-call response.
6. Iterate under max tool calls/latency/token spend; require a structured, grounded recommendation.
7. `safe_mesh` determines HOLD/PASS_REVIEW independently from LLM prose.
8. Never give LLM servo GPIO, factory-write APIs or operator approval credentials.

## Security and evaluation
Use prompt-injection test documents, model disagreements, missing evidence, forged event IDs, permission boundary crossing, wrong CAD revision and timeouts. Measure unsupported claims, evidence recall, distinct actionable suggestions, tool validity and spend per specimen. Include **no LLM** rules-only baseline and **single LLM** baseline. If LLM contributes no measurable lift, it should not gate production.

## Nebius integration
Official API: `https://api.tokenfactory.nebius.com/v1/`; select model from your own live `/v1/models` catalog. `nebius.py` contains an opt-in real model adapter. No live credential has been supplied or called here. Event Nebius Scientific AI notebook, shared H100, and Token Factory are separate resources; verify entitlements separately. Never log API keys.

## Acceptance
- All 21 roles have tool ACL and explicit needed sources.
- Disabled/offline LLM yields a safe status rather than imaginary reasoning.
- Multiple agents do not increase confidence by voting on a duplicated image.

