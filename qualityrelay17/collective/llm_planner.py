"""LLM-backed RequestPlanner over any OpenAI-format chat-completions endpoint (task board AGENT-04).

One class serves every OpenAI-compatible provider; a provider is just base_url + key + model:
    OpenAI   openai_planner_from_env()
    Nebius   nebius_planner_from_env()   base_url https://api.tokenfactory.nebius.com/v1/, tool_choice='auto'

What the model gets: the requester role's scope, its OWN visible evidence as admissible summaries,
the outcomes of its requests so far, the peers that own each kind, and the budget. Nothing else --
no other role's store, no raw payloads, no keys.
What the model can do: call exactly one of two tools, request_evidence or finish. Its proposal is
validated by the engine and the bus; it never signs, never supplies event ids, never decides.
What gets logged: provider, model, tokens in/out, latency, and USD cost per call (only when prices
are configured -- this module never guesses a price). A per-run SpendGuard stops runaway loops.
"""
from __future__ import annotations
import json, os, time
from collections.abc import Mapping
from dataclasses import dataclass
from .planner import PlannerUnavailable, HYPOTHESES
from .messages import SOURCE_FAMILY

REQUESTABLE_KINDS = tuple(SOURCE_FAMILY)


@dataclass
class SpendGuard:
    max_calls: int = 12
    max_total_tokens: int = 60_000
    max_usd: float | None = 0.50
    calls: int = 0
    total_tokens: int = 0
    usd: float = 0.0

    def before_call(self):
        if self.calls >= self.max_calls:
            raise PlannerUnavailable(f'LLM spend cap: {self.calls} calls reached max_calls={self.max_calls}')
        if self.total_tokens >= self.max_total_tokens:
            raise PlannerUnavailable(f'LLM spend cap: {self.total_tokens} tokens reached max_total_tokens={self.max_total_tokens}')
        if self.max_usd is not None and self.usd >= self.max_usd:
            raise PlannerUnavailable(f'LLM spend cap: ${self.usd:.4f} reached max_usd={self.max_usd}')

    def record(self, tokens: int, usd: float | None):
        self.calls += 1; self.total_tokens += tokens
        if usd is not None: self.usd += usd

    def summary(self) -> dict:
        return {'calls': self.calls, 'total_tokens': self.total_tokens, 'usd': round(self.usd, 6),
                'caps': {'max_calls': self.max_calls, 'max_total_tokens': self.max_total_tokens, 'max_usd': self.max_usd}}


SYSTEM_PROMPT = """You are the {role} role (domain: {domain}) in a manufacturing quality-inspection mesh.
You are working on specimen {case_id}. You can only see the evidence listed in the user message.

Decide the ONE next step:
- call request_evidence to ask a peer role for one missing evidence kind, or
- call finish when more evidence would not change the outcome, nothing useful is left to ask for, or the budget cannot cover another request.

Rules:
- Only request kinds whose source family you are entitled to: {entitled}.
- Address the request to the peer that owns that kind (see "peers").
- Give a short UPPER_SNAKE_CASE reason_code and the hypotheses the evidence helps tell apart.
- Every request costs {request_cost} from the remaining budget, even if it fails.
- A request that came back TIMEOUT, SENSOR_FAILURE, STALE_EVIDENCE, DUPLICATE_SOURCE or BAD_SIGNATURE produced no usable evidence; do not repeat it.
- Never invent event ids, measurements or verdicts. You cannot approve, release, reject or move any part; a separate deterministic safety gate decides."""


def _tools(state: dict) -> list[dict]:
    recipients = sorted(set(state['peers'].values())) or ['none']
    return [
        {'type': 'function', 'function': {
            'name': 'request_evidence',
            'description': 'Ask one peer role for one missing evidence kind for this specimen.',
            'parameters': {'type': 'object', 'additionalProperties': False,
                           'required': ['requested_kind', 'recipient_role', 'reason_code', 'hypotheses'],
                           'properties': {
                               'requested_kind': {'type': 'string', 'enum': list(REQUESTABLE_KINDS)},
                               'recipient_role': {'type': 'string', 'enum': recipients},
                               'reason_code': {'type': 'string', 'maxLength': 64},
                               'hypotheses': {'type': 'array', 'minItems': 1, 'items': {'type': 'string', 'enum': list(HYPOTHESES)}}}}}},
        {'type': 'function', 'function': {
            'name': 'finish',
            'description': 'Stop requesting evidence for this specimen.',
            'parameters': {'type': 'object', 'additionalProperties': False, 'required': ['reason'],
                           'properties': {'reason': {'type': 'string', 'maxLength': 200}}}}},
    ]


class OpenAICompatiblePlanner:
    def __init__(self, *, client, model: str, provider: str, price_in_per_mtok: float | None = None,
                 price_out_per_mtok: float | None = None, guard: SpendGuard | None = None,
                 tool_choice: str = 'required', extra_create_kwargs: dict | None = None, temperature: float = 0.0):
        if not model: raise ValueError('model name is required; pick one from the provider catalog')
        self.client, self.model, self.provider = client, model, provider
        self.price_in, self.price_out = price_in_per_mtok, price_out_per_mtok
        self.guard = guard or SpendGuard()
        self.tool_choice, self.extra, self.temperature = tool_choice, dict(extra_create_kwargs or {}), temperature
        self.name = f'{provider}:{model}'
        self.last_usage: dict | None = None

    def describe(self) -> dict:
        return {'planner': 'llm', 'provider': self.provider, 'model': self.model,
                'priced': self.price_in is not None and self.price_out is not None, 'spend': self.guard.summary()}

    def _cost(self, pin: int, pout: int) -> float | None:
        if self.price_in is None or self.price_out is None: return None
        return (pin * self.price_in + pout * self.price_out) / 1_000_000

    def next_action(self, state: dict) -> dict | None:
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT.format(
                        role=state['requester_role'], domain=state['role_domain'], case_id=state['case_id'],
                        entitled=', '.join(state['entitled_sources']), request_cost=state['request_cost'])},
                    {'role': 'user', 'content': json.dumps(_visible_state(state), sort_keys=True)}]
        return _parse(self.complete(messages, _tools(state)))

    def complete(self, messages: list[dict], tools: list[dict]):
        """One guarded, logged chat-completions call; returns the raw response. Shared by every task
        that uses this planner (collective engine, Gate-A policies), so caps and cost apply to all."""
        self.last_usage = None
        self.guard.before_call()
        t0 = time.perf_counter()
        try:
            resp = self.client.chat.completions.create(model=self.model, messages=messages, tools=tools,
                                                       tool_choice=self.tool_choice, temperature=self.temperature, **self.extra)
        except Exception as ex:  # network, auth, quota, model-not-found: a technical stop, never an observation
            raise PlannerUnavailable(f'{self.provider} call failed: {type(ex).__name__}: {str(ex)[:200]}') from ex
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        u = getattr(resp, 'usage', None)
        pin, pout = int(getattr(u, 'prompt_tokens', 0) or 0), int(getattr(u, 'completion_tokens', 0) or 0)
        cost = self._cost(pin, pout)
        self.guard.record(pin + pout, cost)
        self.last_usage = {'provider': self.provider, 'model': self.model, 'prompt_tokens': pin, 'completion_tokens': pout,
                           'latency_ms': latency_ms, 'cost_usd': None if cost is None else round(cost, 6)}
        return resp


def _visible_state(state: dict) -> dict:
    """Exactly what the model may see. Built from the requester's own view only."""
    return {k: state[k] for k in ('case_id', 'requester_role', 'hypotheses', 'visible_evidence', 'missing_kinds',
                                  'peers', 'requests_so_far', 'budget_remaining', 'request_cost', 'belief')}


def _parse(resp) -> dict:
    msg = resp.choices[0].message
    calls = getattr(msg, 'tool_calls', None) or []
    if not calls:
        return {'action': 'finish', 'reason': f'no tool call; model said: {(msg.content or "")[:200]}'}
    call = calls[0]
    name = call.function.name
    try:
        args = json.loads(call.function.arguments or '{}')
        if not isinstance(args, dict): raise ValueError('arguments are not an object')
    except (ValueError, TypeError) as ex:
        return {'action': 'invalid', 'error': f'unparseable tool arguments: {ex}', 'raw': str(call.function.arguments)[:300]}
    if name == 'finish':
        return {'action': 'finish', 'reason': str(args.get('reason', ''))[:200]}
    if name == 'request_evidence':
        return {'action': 'request', **{k: args.get(k) for k in ('requested_kind', 'recipient_role', 'reason_code', 'hypotheses')}}
    return {'action': 'invalid', 'error': f'unknown tool {name!r}', 'raw': str(args)[:300]}


# ---------------------------------------------------------------------------------------- providers
def _float(env: Mapping[str, str], k: str) -> float | None:
    v = (env.get(k) or '').strip()
    return float(v) if v else None


def _guard(env: Mapping[str, str]) -> SpendGuard:
    return SpendGuard(max_calls=int(env.get('LLM_MAX_CALLS_PER_RUN') or 12),
                      max_total_tokens=int(env.get('LLM_MAX_TOKENS_PER_RUN') or 60_000),
                      max_usd=_float(env, 'LLM_MAX_USD_PER_RUN') if (env.get('LLM_MAX_USD_PER_RUN') or '').strip() else 0.50)


def openai_planner_from_env(env: Mapping[str, str] | None = None, *, client=None) -> tuple[OpenAICompatiblePlanner | None, dict]:
    """Returns (planner or None, status). Status never contains the key."""
    env = os.environ if env is None else env
    key, model = (env.get('OPENAI_API_KEY') or '').strip(), (env.get('OPENAI_MODEL') or '').strip()
    missing = [n for n, v in (('OPENAI_API_KEY', key), ('OPENAI_MODEL', model)) if not v]
    if missing:
        return None, {'provider': 'openai', 'state': 'NOT_CONFIGURED', 'missing': missing}
    if client is None:
        from openai import OpenAI
        base_url = (env.get('OPENAI_BASE_URL') or '').strip() or None
        client = OpenAI(api_key=key, base_url=base_url, timeout=20, max_retries=1)
    extra: dict[str, bool | str] = {'parallel_tool_calls': False}
    # GPT-5.x reasoning models reject function tools on /v1/chat/completions unless reasoning_effort='none'.
    # Blank = not sent, so models that do not know the parameter are unaffected.
    effort = (env.get('OPENAI_REASONING_EFFORT') or '').strip()
    if effort:
        extra['reasoning_effort'] = effort
    planner = OpenAICompatiblePlanner(client=client, model=model, provider='openai',
                                      price_in_per_mtok=_float(env, 'OPENAI_PRICE_INPUT_PER_MTOK'),
                                      price_out_per_mtok=_float(env, 'OPENAI_PRICE_OUTPUT_PER_MTOK'),
                                      guard=_guard(env), tool_choice='required', extra_create_kwargs=extra)
    status = {'provider': 'openai', 'state': 'CONFIGURED_NOT_VERIFIED', 'model': model, 'priced': planner.describe()['priced']}
    return planner, status


NEBIUS_BASE_URL = 'https://api.tokenfactory.nebius.com/v1/'


def nebius_planner_from_env(env: Mapping[str, str] | None = None, *, client=None) -> tuple[OpenAICompatiblePlanner | None, dict]:
    """Nebius Token Factory: same class, OpenAI-format endpoint. tool_choice='auto' and no
    parallel_tool_calls, since open-weight models on the catalog do not all accept those.
    Status never contains the key."""
    env = os.environ if env is None else env
    key, model = (env.get('NEBIUS_API_KEY') or '').strip(), (env.get('NEBIUS_MODEL') or '').strip()
    missing = [n for n, v in (('NEBIUS_API_KEY', key), ('NEBIUS_MODEL', model)) if not v]
    if missing:
        return None, {'provider': 'nebius', 'state': 'NOT_CONFIGURED', 'missing': missing}
    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=NEBIUS_BASE_URL, timeout=20, max_retries=1)
    planner = OpenAICompatiblePlanner(client=client, model=model, provider='nebius',
                                      price_in_per_mtok=_float(env, 'NEBIUS_PRICE_INPUT_PER_MTOK'),
                                      price_out_per_mtok=_float(env, 'NEBIUS_PRICE_OUTPUT_PER_MTOK'),
                                      guard=_guard(env), tool_choice='auto')
    status = {'provider': 'nebius', 'state': 'CONFIGURED_NOT_VERIFIED', 'model': model, 'priced': planner.describe()['priced']}
    return planner, status


# provider name -> factory(env) -> (planner | None, status).
PROVIDERS = {'openai': openai_planner_from_env, 'nebius': nebius_planner_from_env}
