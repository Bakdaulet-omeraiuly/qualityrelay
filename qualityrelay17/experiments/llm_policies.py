"""LLM-backed policies for the Gate-A environment (18.1 Gate B; AGENT-04, LLM-08).

`B7_llm` is `B7_safe_mesh_voi` with ONE substitution: the two-step VOI selector is replaced by
an LLM that, each round, either requests the next capture of one sensor from the role that owns
it, or finishes. Everything else is the registered B7 machinery, unchanged and in Python: the
belief is recomputed from the ledger (`belief_from`, lineage dedupe by source_root), the SAFE-MESH
hard gate (`gate_reasons` / `_gate_fix`, including its automatic fix-up request) and the HOLD
threshold. The model never sees `_truth`, never produces a probability, never decides HOLD/PASS.

One ablation, same model, same information, same tools, same budget:
  B7_llm                   decider prompt is the quality_inspector role (roles.py) addressing owners
  B7_llm-specialist_roles  one generic assistant prompt instead of the role prompt

Not here: B4 (free-form chat) and B7-structured_protocol (typed requests replaced by free chat).
Both need a free-text-to-action parser whose design is a research decision, so they remain
NOT_CONFIGURED in collective_baselines.

Validation: a proposal is executed only if the sensor still has a capture, its owner has not timed
out, the budget allows it, and it is addressed to that sensor's owner. Otherwise it is
PROPOSAL_REJECTED in the trace and the model is told why; after MAX_INVALID rejections the LLM is
not asked again for that part. A provider failure or spend cap sets planner_stopped on the record
and the part is decided on the evidence already held -- an evaluation containing any stopped part
is incomplete and must say so.
"""
from __future__ import annotations
import hashlib, json

from ..collective.planner import PlannerUnavailable
from ..roles import ROLES
from .belief import belief_from, p_unsafe, p_dimensional, hold_threshold, TOLERANCE_MM, MAX_DRAWS
from .collective_baselines import _acquire, _finish, _gate_fix, gate_reasons
from .collective_env import CollectiveEnv, OWNER

MAX_INVALID = 2
DECIDER_ROLE = 'quality_inspector'   # roles.py name; 'quality_agent' is its id inside CollectiveEnv
KINDS = tuple(OWNER)

_HEADER = {
    'role': ('You are the {role} role (domain: {domain}) in a manufacturing quality-inspection mesh, '
             'deciding what evidence to gather for one simulated 3D-printed specimen ({specimen_id}).\n'
             'You own no sensor. Each sensor is owned by a peer role: {owners}. You get a reading only '
             'by sending request_evidence to the role that owns that sensor.'),
    'generic': ('You are an assistant deciding what evidence to gather for one simulated 3D-printed '
                'specimen ({specimen_id}).\nSensors and the recipient to name for each: {owners}.'),
}
_RULES = """
Each round, call exactly one tool:
- request_evidence: get the next capture of one sensor, or
- finish: stop gathering evidence for this specimen.

The user message is computed by code, not by you: the readings held, the calibrated probabilities, the
safety gate's current reasons, the remaining budget and the prices. Use them; never invent or recompute numbers.
Every request costs {price} whether or not it succeeds. Releasing an unsafe part costs {escape}; holding a part costs {hold}.
Request evidence only when it could plausibly change the decision by enough to be worth its price.
Readings that share a source_root are the same capture and count once.
A request that timed out or was rejected will not succeed if repeated.
You cannot pass, hold or move the part. After you finish, a deterministic safety gate and the calibrated threshold decide."""

TOOLS = [
    {'type': 'function', 'function': {
        'name': 'request_evidence',
        'description': 'Request the next capture of one sensor from the role that owns it.',
        'parameters': {'type': 'object', 'additionalProperties': False,
                       'required': ['kind', 'recipient_role', 'reason_code'],
                       'properties': {
                           'kind': {'type': 'string', 'enum': list(KINDS)},
                           'recipient_role': {'type': 'string', 'enum': sorted(set(OWNER.values()))},
                           'reason_code': {'type': 'string', 'maxLength': 64,
                                           'description': 'short UPPER_SNAKE_CASE reason'}}}}},
    {'type': 'function', 'function': {
        'name': 'finish',
        'description': 'Stop gathering evidence for this specimen.',
        'parameters': {'type': 'object', 'additionalProperties': False, 'required': ['reason'],
                       'properties': {'reason': {'type': 'string', 'maxLength': 200}}}}},
]

POLICY_NAMES = {'role': 'B7_llm', 'generic': 'B7_llm-specialist_roles'}
PROMPT_SHA256 = {v: hashlib.sha256((_HEADER[v] + _RULES + json.dumps(TOOLS, sort_keys=True)).encode()).hexdigest()
                 for v in _HEADER}


def system_prompt(variant: str, env: CollectiveEnv, sc) -> str:
    c = sc.costs
    owners = ', '.join(f'{k} -> {r}' for k, r in OWNER.items())
    head = _HEADER[variant].format(role=DECIDER_ROLE, domain=ROLES[DECIDER_ROLE].domain,
                                   specimen_id=env._case['specimen_id'], owners=owners)
    return head + _RULES.format(price=c.inspection + c.peer_request, escape=c.escaped_defect, hold=c.hold)


def visible_state(env: CollectiveEnv, sc, model, history: list[dict]) -> dict:
    """Exactly what the model may see: the decider's own view plus numbers computed by code."""
    state, _, _ = belief_from(env.evidence, model, dedupe=True)
    p = p_unsafe(state)
    reasons = gate_reasons(env, model, dedupe=True)
    t = hold_threshold(sc.costs)
    seen, evidence = set(), []
    for e in env.observe('quality_agent'):
        reading = round(e['value'], 4) if e['kind'] == 'caliper' else ('flagged' if e['value'] else 'not_flagged')
        evidence.append(dict(event_id=e['event_id'], kind=e['kind'], capture_index=e['index'], reading=reading,
                             source_root=e['source_root'], counted=e['source_root'] not in seen))
        seen.add(e['source_root'])
    cand = env.available(sc.budget)
    return dict(
        specimen_id=env._case['specimen_id'], source_tier='SIMULATED',
        evidence=evidence,
        belief=dict(p_surface_defect=round(state[0], 6), p_clearance_below_tolerance=round(p_dimensional(state[1], state[2]), 6),
                    p_unsafe=round(p, 6), hold_threshold=round(t, 6),
                    decision_if_finished_now='HOLD' if (p >= t or reasons) else 'PASS_REVIEW',
                    safety_gate_reasons=reasons),
        caliper_tolerance_mm=TOLERANCE_MM,
        available=[dict(kind=k, next_capture_index=i, owner=OWNER[k]) for k, i in cand.items()],
        requests_so_far=history,
        budget=dict(observations_used=env.inspections, observations_max=sc.budget),
        prices=dict(per_request=sc.costs.inspection + sc.costs.peer_request, escaped_defect=sc.costs.escaped_defect,
                    hold=sc.costs.hold))


def parse(resp) -> dict:
    msg = resp.choices[0].message
    calls = getattr(msg, 'tool_calls', None) or []
    if not calls:
        return {'action': 'finish', 'reason': f'no tool call; model said: {(msg.content or "")[:200]}'}
    name = calls[0].function.name
    try:
        args = json.loads(calls[0].function.arguments or '{}')
        if not isinstance(args, dict): raise ValueError('arguments are not an object')
    except (ValueError, TypeError) as ex:
        return {'action': 'invalid', 'error': f'unparseable tool arguments: {ex}'}
    if name == 'finish':
        return {'action': 'finish', 'reason': str(args.get('reason', ''))[:200]}
    if name == 'request_evidence':
        return {'action': 'request', 'kind': args.get('kind'), 'recipient_role': args.get('recipient_role'),
                'reason_code': str(args.get('reason_code') or '')[:64]}
    return {'action': 'invalid', 'error': f'unknown tool {name!r}'}


def validate(action: dict, env: CollectiveEnv, cand: dict) -> str | None:
    kind, to = action.get('kind'), action.get('recipient_role')
    if kind not in OWNER:
        return f'unknown sensor {kind!r}'
    if kind in env.unreachable:
        return f'{OWNER[kind]} timed out earlier for this specimen'
    if env.used[kind] >= MAX_DRAWS:
        return f'no {kind} captures left'
    if kind not in cand:
        return 'observation budget exhausted'
    if to != OWNER[kind]:
        return f'{to!r} does not own {kind}; the owner is {OWNER[kind]}'
    return None


class _Log:
    def __init__(self):
        self.calls = self.prompt_tokens = self.completion_tokens = self.invalid = 0
        self.usd, self.priced, self.latency_ms = 0.0, True, 0.0
        self.stopped, self.stop_reason = False, None

    def add(self, usage: dict | None):
        self.calls += 1
        if not usage: return
        self.prompt_tokens += usage['prompt_tokens']; self.completion_tokens += usage['completion_tokens']
        self.latency_ms += usage['latency_ms']
        if usage['cost_usd'] is None: self.priced = False
        else: self.usd += usage['cost_usd']


def _ask(planner, variant, env, sc, model, history, log: _Log) -> dict:
    messages = [{'role': 'system', 'content': system_prompt(variant, env, sc)},
                {'role': 'user', 'content': json.dumps(visible_state(env, sc, model, history), sort_keys=True)}]
    resp = planner.complete(messages, TOOLS)
    log.add(planner.last_usage)
    action = parse(resp)
    env.trace.append(dict(type='LLM_CALL', planner=planner.name, prompt_variant=variant, action=action,
                          **(planner.last_usage or {})))
    return action


def run_llm_policy(env: CollectiveEnv, sc, model, planner, variant: str = 'role') -> dict:
    if variant not in _HEADER: raise ValueError(f'unknown prompt variant {variant!r}')
    costs = sc.costs; t = hold_threshold(costs)
    log = _Log(); history: list[dict] = []
    blocked = False         # provider stopped or too many invalid proposals: never ask again for this part
    model_finished = False  # the model chose finish; re-asked only if the hard gate adds evidence (as B7 re-runs VOI)
    max_calls = sc.budget + MAX_INVALID + 3
    while True:
        cand = env.available(sc.budget)
        kind = reason = None
        if cand and not blocked and not model_finished and log.calls < max_calls:
            try:
                action = _ask(planner, variant, env, sc, model, history, log)
            except PlannerUnavailable as ex:
                log.stopped, log.stop_reason, blocked = True, str(ex)[:200], True
                env.trace.append(dict(type='PLANNER_STOPPED', reason=log.stop_reason))
                action = {'action': 'finish'}
            if action['action'] in ('request', 'invalid'):
                err = action.get('error') or validate(action, env, cand)
                if err:
                    log.invalid += 1
                    env.trace.append(dict(type='PROPOSAL_REJECTED', proposal=action, reason=err))
                    history.append(dict(kind=action.get('kind'), recipient=action.get('recipient_role'),
                                        outcome='PROPOSAL_REJECTED', reason=err))
                    if log.invalid < MAX_INVALID:
                        continue
                    blocked = True
                else:
                    kind, reason = action['kind'], 'LLM:' + (action['reason_code'] or 'UNSPECIFIED')
            else:
                model_finished = True   # finish, or plain text treated as finish
        if kind is not None:
            ev = _acquire(env, kind, via_peer=True, model=model, dedupe=True, costs=costs, reason=reason)
            history.append(dict(kind=kind, recipient=OWNER[kind], outcome='TIMEOUT' if ev is None else 'GRANTED'))
            continue
        # Same step as B7 when its selector stops: the hard gate may still buy the missing evidence.
        state, _, _ = belief_from(env.evidence, model, dedupe=True)
        if p_unsafe(state) < t:
            reasons = gate_reasons(env, model, dedupe=True)
            fix = _gate_fix(reasons, cand) if reasons else None
            if fix:
                ev = _acquire(env, fix, via_peer=True, model=model, dedupe=True, costs=costs, reason='HARD_GATE:' + reasons[0])
                history.append(dict(kind=fix, recipient=OWNER[fix], outcome='TIMEOUT' if ev is None else 'GRANTED',
                                    requested_by='SAFE_MESH_HARD_GATE'))
                model_finished = False
                continue
        break
    return _finish(env, sc, model, dedupe=True, gate=True, extra=dict(
        planner=planner.name, prompt_variant=variant, compute_calls=log.calls,
        llm_prompt_tokens=log.prompt_tokens, llm_completion_tokens=log.completion_tokens,
        llm_usd=round(log.usd, 6) if log.priced else None, llm_latency_ms=round(log.latency_ms, 1),
        invalid_proposals=log.invalid, planner_stopped=log.stopped, planner_stop_reason=log.stop_reason))


def make_llm_policy(planner, variant: str = 'role'):
    """Returns a policy with the Gate-A signature (env, sc, model) -> record."""
    if variant not in _HEADER: raise ValueError(f'unknown prompt variant {variant!r}')
    def policy(env, sc, model):
        return run_llm_policy(env, sc, model, planner, variant)
    policy.__name__ = POLICY_NAMES[variant]
    return policy


# Registered Gate-A contrasts stay as they are; these are the Gate-B questions for the LLM policies.
LLM_CONTRASTS = (
    ('B7_llm', 'B7_safe_mesh_voi', 'LLM selector vs computed VOI (same belief, same gate)'),
    ('B7_llm', 'B0_rules', 'does the LLM-driven method beat the fixed rule?'),
    ('B7_llm', 'B5_structured_fixed', 'LLM selection vs fixed request order'),
    ('B7_llm', 'B7_llm-specialist_roles', 'role prompt vs one generic prompt (same model)'),
)
