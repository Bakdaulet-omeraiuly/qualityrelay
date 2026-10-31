# LLM planners for the collaboration roles (AGENT-04)

**Status 31 Oct:** OpenAI and Nebius planners implemented and tested offline
(`qualityrelay17/collective/llm_planner.py`, `tests/test_collective_llm_planner.py`,
`tests/test_llm_gate_b.py`). The same planner also drives Bakdaulet's Gate-A environment
(Gate B, below). No paid call has been made from this repo yet; no model id has been verified.

## What the LLM does, and what it cannot do

The requesting role (today: `quality_inspector`) asks a **planner**, one round at a time, for its
next move: request one missing evidence kind from a named peer, or finish.

- **Sees:** its own role scope, its own evidence as admissible summaries, outcomes of its requests
  so far, which peer owns which kind, remaining budget, current belief. Never another role's
  store, raw payloads, signatures, or keys.
- **Can do:** call `request_evidence` or `finish`. Nothing else is advertised.
- **Cannot do:** sign a message, supply event ids, approve, release, reject, or actuate. The engine
  validates each proposal (`PROPOSAL_REJECTED` in the trace), the bus applies the ACL / budget /
  deadline / VERIFY, and `safe_mesh` makes the decision. Plain prose is treated as "finish".
- **Logged per call:** provider, model, prompt and completion tokens, latency, USD cost (only if
  prices are configured; never guessed). A per-run `SpendGuard` stops on calls, tokens, or USD.
- **On provider failure or cap:** `PLANNER_STOPPED`, and the case is decided on evidence already held.

## Configure OpenAI

In the git-ignored `.env` (or the real environment, which wins):

```
OPENAI_API_KEY=...
OPENAI_MODEL=<a tool-calling model from your own account's model list>
OPENAI_PRICE_INPUT_PER_MTOK=<from the price page, optional>
OPENAI_PRICE_OUTPUT_PER_MTOK=<optional>
LLM_MAX_USD_PER_RUN=0.50
```

Check: `GET /integrations/llm` shows `CONFIGURED_NOT_VERIFIED` (no call is made). Run one case:
`POST /research/collective/run {"scenario":"pi_suspect","planner":"openai"}`, or pick "OpenAI model"
in the web Agent Evidence Room. Paid smoke test from pytest, only when you mean it:

```
RUN_LIVE_LLM=1 python -m pytest tests/test_collective_llm_planner.py -k live -s
```

## Configure Nebius

Same class, OpenAI-format endpoint `https://api.tokenfactory.nebius.com/v1/`, `tool_choice='auto'`,
no `parallel_tool_calls` (`nebius_planner_from_env`, registered as `PROVIDERS['nebius']`):

```
NEBIUS_API_KEY=...
NEBIUS_MODEL=<id from GET /v1/models under the team key; must support tool calling>
NEBIUS_PRICE_INPUT_PER_MTOK=<optional>
NEBIUS_PRICE_OUTPUT_PER_MTOK=<optional>
```

Before trusting a model: confirm the exact id is listed for the team key (LLM-01), then run the
dry-run and a tiny live Gate-B run (below).

### LLM-01 entitlement check

```
python scripts/verify_nebius_entitlement.py                    # free: GET /v1/models, which candidates are listed
python scripts/verify_nebius_entitlement.py --confirm-spend    # + text and JSON tool-call roundtrip (3 calls, max_tokens 512)
python scripts/verify_nebius_entitlement.py --confirm-spend --all-candidates
```

Candidates, in order: `zai-org/GLM-5.3-Flash`, `Qwen/Qwen3-30B-A3B-Instruct-2507`, `zai-org/GLM-5.3`
(`qualityrelay17/llm_entitlement.py`). Being listed counts as entitlement; nothing is assumed. The tool-call
roundtrip passes only if the model makes exactly one `request_evidence` call, the arguments are valid
against the schema (enums, required fields, no extra keys), and after the tool result comes back it gives a
final text answer. The manifest goes to `examples/results/llm_01_entitlement/nebius_<UTC>.json` and holds
the date, listed models, candidate entitlement, tested model, tool-call validity, tokens and latency. It
never holds the key, only a 12-hex SHA-256 fingerprint. Verdicts are `NOT_CONFIGURED`, `AUTH_FAILED`,
`MODELS_LISTED_ONLY`, `NOT_ENTITLED`, `FAILED` and `VERIFIED`. `GET /integrations/llm` reports the latest
manifest under `providers.nebius.entitlement`; it reads the file and never makes a call. Many open-weight models call tools unreliably; that
shows up as `invalid_proposals_per_part`, never as a wrong decision.

## Gate B: LLM policies in the Gate-A environment

`qualityrelay17/experiments/llm_policies.py` plugs the planner into Bakdaulet's hidden-truth
environment (`experiments/collective_env.py`). `B7_llm` is `B7_safe_mesh_voi` with one
substitution: the LLM, not two-step VOI, picks the next sensor to request from its owner (or
finishes). Belief (`belief_from`, lineage dedupe), the SAFE-MESH hard gate and the HOLD threshold
are Bakdaulet's code, unchanged. `B7_llm-specialist_roles` is the same with one generic prompt
instead of the quality_inspector role prompt. B4 and B7-structured_protocol stay NOT_CONFIGURED.

The model sees: its own evidence (kind, capture index, reading, source_root, counted-or-duplicate),
the belief numbers and gate reasons computed by code, available sensors and owners, its request
history, budget and prices. Never the hidden truth. Invalid proposals (wrong owner, exhausted
sensor, timed-out owner, bad JSON) are rejected and fed back; after 2 the model is not asked again.

```
python scripts/run_llm_gate_b.py --provider dry-run                      # scripted fake, no key, no cost
python scripts/run_llm_gate_b.py --provider nebius --scenarios S13 --n 30 --confirm-spend --max-usd 1.0
```

Each run is paired against B0, B1, B5, B6 and B7 on the same simulated cases and writes
`examples/results/llm_gate_b/<provider>-<model>-<UTC>/` (per-scenario JSON with traces,
`summary.csv`, `manifest.json` with prompt hashes, spend and completeness). A live run needs
`--confirm-spend` and runs under a hard call/token/USD cap; if the cap or the provider stops the
planner, the run is `INCOMPLETE_PLANNER_STOPPED` (exit 2). Prices from Gate A matter: at S01 the
registered B7 holds everything without inspecting, so S11 to S13 are where selection is visible.
A few dozen parts is a smoke-scale comparison, not the registered 30 x 1000 grid.

## Using both

The suggested split: Nebius plans for the agent roles; OpenAI runs the single-agent baseline (B1)
and serves as a fallback. Every trace and manifest records `provider:model`, so results from
different providers are never mixed silently. Compare providers on the same scenarios, not
across different ones.
