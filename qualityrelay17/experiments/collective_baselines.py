"""B0..B7 of docs/research/COLLECTIVE_17_1_BAKDAULET.md section 5.1, plus the section 5.2
ablations that can be run without a live LLM. Deterministic mock agents (Gate A): every
decision is computed by checked Python (posterior, cost, ranking, threshold), no LLM.

| ID | here | what differs |
|---|---|---|
| B0 | `B0_rules` | fixed OR-rule on phone/Pi/caliper, Pi down -> HOLD (= factory.conservative_rules) |
| B1 | `B1_single_agent_fixed` | one agent wired to every sensor, reads the fixed set once, calibrated Bayes fusion |
| B2 | `B2_full_information_upper_bound` | reads EVERY available capture, ignores budget -- context only, its information price is shown |
| B3 | `B3_majority_vote` | three specialists vote from their own first reading, majority (tie -> HOLD), no requests |
| B4 | -- | free-form LLM chat: NOT_CONFIGURED (needs a live model backbone, Gate B) |
| B5 | `B5_structured_fixed` | decider requests evidence from owners via typed messages in a FIXED order, SAFE-MESH hard gate |
| B6 | `B6_single_agent_voi` | one agent wired to every sensor, adaptive VOI (2-step look-ahead), no messages, no hard gate |
| B7 | `B7_safe_mesh_voi` | decider requests evidence from owners, adaptive VOI prices each request (inspection + message), hard gate |

Ablations of B7, one axis each: `-peer_exchange` (decider sees only its own caliper),
`-provenance` (no source_root dedupe -- simulation only), `-cost_awareness` (entropy selector),
`-hard_gate`. `B7 - adaptive_VOI` is B5 by construction. `-specialist_roles` and
`-structured_protocol` need an LLM backbone: NOT_CONFIGURED.

Fairness (17.1 sec 5.1): every policy draws from the same capture pool, pays the same price per
observation, and the adaptive ones share one budget. B7 pays for messages B6 does not need --
that is the measured price of decentralised ownership, not a handicap to hide.
"""
from __future__ import annotations

from .belief import (belief_from, p_unsafe, risk, hold_threshold, lookahead_value, entropy_choice,
                     TOLERANCE_MM, MAX_DRAWS)
from .collective_env import CollectiveEnv, score, DECISION_S

NOT_CONFIGURED = {
    'B4_free_form_chat': 'needs a live LLM backbone with token/latency logging (Gate B, AGENT-04)',
    'B7-specialist_roles': 'needs an LLM backbone: one generic prompt vs role prompts',
    'B7-structured_protocol': 'needs an LLM backbone: typed requests replaced by free chat',
}
ENTROPY_STOP_BITS = 0.01


def _disp(p, costs):
    return 'HOLD' if p >= hold_threshold(costs) else 'PASS_REVIEW'


def _acquire(env: CollectiveEnv, kind, *, via_peer, model, dedupe, costs, reason='', net_value=None):
    before, _, _ = belief_from(env.evidence, model, dedupe=dedupe)
    roots_before = {e['source_root'] for e in env.evidence}
    ev = env.request(kind, reason=reason) if via_peer else env.capture(kind)
    after, _, _ = belief_from(env.evidence, model, dedupe=dedupe)
    pb, pa = p_unsafe(before), p_unsafe(after)
    env.trace.append(dict(
        type='UPDATE_BELIEF', kind=kind, reason=reason,
        net_value=None if net_value is None else round(net_value, 6),
        new_independent_fact=bool(ev is not None and ev['source_root'] not in roots_before),
        duplicate_of_existing_root=bool(ev is not None and ev['source_root'] in roots_before),
        p_unsafe_before=round(pb, 6), p_unsafe_after=round(pa, 6),
        disposition_before=_disp(pb, costs), disposition_after=_disp(pa, costs)))
    return ev


def gate_reasons(env: CollectiveEnv, model, *, dedupe=True):
    """SAFE-MESH hard gate for a PASS_REVIEW recommendation (17.1 sec 4.2). Python, not VOI:
    it applies even when no test 'pays for itself'."""
    state, ns, nd = belief_from(env.evidence, model, dedupe=dedupe)
    reasons = []
    if ns == 0:
        reasons.append('NO_INDEPENDENT_SURFACE_EVIDENCE')
    if nd == 0:
        reasons.append('NO_DIMENSIONAL_EVIDENCE')
    elif nd == 1 and abs(state[1] - TOLERANCE_MM) < 2 * model.sigma_meas_mm:
        reasons.append('NEAR_TOLERANCE_SINGLE_READING')
    if env.unreachable and ns < 2:
        reasons.append('PEER_TIMEOUT_REDUCED_SURFACE_EVIDENCE')
    return reasons


def _gate_fix(reasons, cand):
    for r in reasons:
        if r in ('NO_DIMENSIONAL_EVIDENCE', 'NEAR_TOLERANCE_SINGLE_READING') and 'caliper' in cand:
            return 'caliper'
        if r in ('NO_INDEPENDENT_SURFACE_EVIDENCE', 'PEER_TIMEOUT_REDUCED_SURFACE_EVIDENCE'):
            for k in ('phone', 'pi'):
                if k in cand:
                    return k
    return None


def _finish(env, sc, model, *, dedupe, gate, extra=None):
    costs = sc.costs
    state, _, _ = belief_from(env.evidence, model, dedupe=dedupe)
    p = p_unsafe(state)
    reasons = gate_reasons(env, model, dedupe=dedupe) if gate else []
    hold = p >= hold_threshold(costs) or bool(reasons)
    return _record(env, hold, p=p, gate=reasons, extra=extra)


def _record(env, hold, *, p=None, gate=(), extra=None):
    upd = [t for t in env.trace if t['type'] == 'UPDATE_BELIEF']
    flips = [t for t in upd if t['disposition_before'] != t['disposition_after']]
    rec = dict(specimen_id=env._case['specimen_id'], inspections=env.inspections,
               observations=[f"{e['kind']}{e['index']}" for e in env.evidence],
               peer_requests=env.peer_requests,
               timeouts=sum(t['type'] == 'TIMEOUT' for t in env.trace),
               latency_s=round(env.latency_s + DECISION_S, 3),
               p_unsafe=None if p is None else round(p, 6), hard_gate=list(gate),
               flips_with_new_fact=sum(t['new_independent_fact'] for t in flips),
               flips_without_new_fact=sum(not t['new_independent_fact'] for t in flips),
               duplicates_received=sum(t['duplicate_of_existing_root'] for t in upd),
               **score(env, hold))
    if extra:
        rec.update(extra)
    return rec


# ---- B0, B1, B2, B3: fixed evidence sets ---------------------------------------------

def _read_fixed(env, model, sc, *, dedupe=True):
    for k in ('phone', 'pi', 'caliper'):
        if env.station_up(k):
            _acquire(env, k, via_peer=False, model=model, dedupe=dedupe, costs=sc.costs, reason='FIXED_SET')


def B0_rules(env, sc, model):
    _read_fixed(env, model, sc)
    v = {e['kind']: e['value'] for e in env.evidence}
    hold = (not env.station_up('pi')) or v.get('phone') or v.get('pi') or v['caliper'] < TOLERANCE_MM
    return _record(env, bool(hold))


def B1_single_agent_fixed(env, sc, model):
    _read_fixed(env, model, sc)
    return _finish(env, sc, model, dedupe=True, gate=False)


def B2_full_information_upper_bound(env, sc, model):
    for k in ('phone', 'pi', 'caliper'):
        while env.station_up(k) and env.used[k] < MAX_DRAWS:
            _acquire(env, k, via_peer=False, model=model, dedupe=True, costs=sc.costs, reason='ALL_AVAILABLE')
    return _finish(env, sc, model, dedupe=True, gate=False)


def B3_majority_vote(env, sc, model):
    _read_fixed(env, model, sc)
    votes = [bool(e['value']) if e['kind'] != 'caliper' else e['value'] < TOLERANCE_MM for e in env.evidence]
    hold = 2 * sum(votes) >= len(votes)  # majority of available voters; a tie holds
    return _record(env, hold)


# ---- B5: structured requests, fixed order ----------------------------------------------

FIXED_ORDER = ('caliper', 'phone', 'pi', 'caliper', 'phone', 'pi', 'caliper', 'phone', 'pi')


def B5_structured_fixed(env, sc, model, *, dedupe=True, gate=True):
    costs = sc.costs; t = hold_threshold(costs)
    for kind in FIXED_ORDER:
        cand = env.available(sc.budget)
        if not cand:
            break
        state, _, _ = belief_from(env.evidence, model, dedupe=dedupe)
        p = p_unsafe(state)
        reasons = gate_reasons(env, model, dedupe=dedupe) if gate else []
        if env.evidence and not reasons and (p < t / 2 or p > 0.5):
            break  # fixed confidence-band stop rule
        if kind in cand:
            _acquire(env, kind, via_peer=True, model=model, dedupe=dedupe, costs=costs, reason='FIXED_ORDER')
    return _finish(env, sc, model, dedupe=dedupe, gate=gate)


# ---- B6, B7 and ablations: adaptive VOI ------------------------------------------------

def _adaptive(env, sc, model, *, via_peer, dedupe, gate, selector='voi', allowed=None):
    costs = sc.costs; t = hold_threshold(costs)
    unit = costs.inspection + (costs.peer_request if via_peer else 0.0)
    price = lambda kind: unit  # noqa: E731
    while True:
        state, _, _ = belief_from(env.evidence, model, dedupe=dedupe)
        cand = env.available(sc.budget)
        if not via_peer:
            cand = {k: i for k, i in cand.items() if env.station_up(k)}
        if allowed is not None:
            cand = {k: i for k, i in cand.items() if k in allowed}
        p = p_unsafe(state)
        if selector == 'voi':
            v, kind = lookahead_value(state, cand, price, model, costs, min(2, sc.budget - env.inspections))
            net = risk(p, costs) - v
        else:
            net, kind = entropy_choice(state, cand, model)
            if net < ENTROPY_STOP_BITS:
                kind = None
        if kind is None:
            if gate and p < t:
                reasons = gate_reasons(env, model, dedupe=dedupe)
                fix = _gate_fix(reasons, cand) if reasons else None
                if fix:
                    _acquire(env, fix, via_peer=via_peer, model=model, dedupe=dedupe, costs=costs,
                             reason='HARD_GATE:' + reasons[0])
                    continue
            break
        _acquire(env, kind, via_peer=via_peer, model=model, dedupe=dedupe, costs=costs,
                 reason='VOI' if selector == 'voi' else 'ENTROPY', net_value=net)
    return _finish(env, sc, model, dedupe=dedupe, gate=gate)


def B6_single_agent_voi(env, sc, model):
    return _adaptive(env, sc, model, via_peer=False, dedupe=True, gate=False)


def B7_safe_mesh_voi(env, sc, model):
    return _adaptive(env, sc, model, via_peer=True, dedupe=True, gate=True)


def B7_minus_peer_exchange(env, sc, model):
    return _adaptive(env, sc, model, via_peer=False, dedupe=True, gate=True, allowed={'caliper'})


def B7_minus_provenance(env, sc, model):
    return _adaptive(env, sc, model, via_peer=True, dedupe=False, gate=True)


def B7_minus_cost_awareness(env, sc, model):
    return _adaptive(env, sc, model, via_peer=True, dedupe=True, gate=True, selector='entropy')


def B7_minus_hard_gate(env, sc, model):
    return _adaptive(env, sc, model, via_peer=True, dedupe=True, gate=False)


POLICIES = {
    'B0_rules': B0_rules,
    'B1_single_agent_fixed': B1_single_agent_fixed,
    'B2_full_information_upper_bound': B2_full_information_upper_bound,
    'B3_majority_vote': B3_majority_vote,
    'B5_structured_fixed': B5_structured_fixed,
    'B6_single_agent_voi': B6_single_agent_voi,
    'B7_safe_mesh_voi': B7_safe_mesh_voi,
    'B7-peer_exchange': B7_minus_peer_exchange,
    'B7-provenance': B7_minus_provenance,
    'B7-cost_awareness': B7_minus_cost_awareness,
    'B7-hard_gate': B7_minus_hard_gate,
}
UPPER_BOUND = {'B2_full_information_upper_bound'}
