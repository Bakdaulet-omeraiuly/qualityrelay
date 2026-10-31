"""One collaboration case, end to end, with the no-request control run alongside.

    FIND_MISSING_EVIDENCE -> REQUEST_EVIDENCE -> EVIDENCE_RESPONSE -> (bus VERIFY)
      -> HYPOTHESIS_UPDATE -> PROPOSE_INSPECTION -> DECISION_PROPOSAL

The result carries the five 'real collaboration, not theatre' criteria from the research plan
(section 3.4) evaluated on the actual trace, so a run that was theatre says so about itself.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from ..safe_mesh import evaluate
from ..lineage import effective_source_count
from ..roles import ROLES
from .peer_protocol import PeerBus
from .belief import BeliefModel
from .messages import SOURCE_FAMILY
from .planner import RequestPlanner, DeterministicPlanner, PlannerUnavailable, HYPOTHESES, REASON_FOR  # noqa: F401 (re-export)

# What safe_mesh needs for a PASS_REVIEW, in the order a quality role would ask for it.
NEEDED_KINDS = ('PI_IMAGE', 'CAD_IMAGE', 'CALIPER', 'ASSEMBLY')
RETRYABLE = {'REJECT_REQUEST'}  # a mis-addressed request may be re-sent to the right owner; nothing else repeats


@dataclass
class CaseResult:
    case_id: str
    requester: str
    origin: str
    decision: dict
    control_decision: dict
    decision_changed: bool
    belief_prior: float
    belief_final: float
    belief_path: list[dict]
    requests: int
    request_outcomes: dict
    cost_charged: float
    independent_sources_before: int
    independent_sources_after: int
    proposal: dict
    criteria: dict
    trace: dict
    narrative: list[str]
    planner: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class CollaborationEngine:
    def __init__(self, bus: PeerBus, belief: BeliefModel, planner: RequestPlanner | None = None, max_rounds: int = 8):
        self.bus, self.belief = bus, belief
        self.planner = planner or DeterministicPlanner()
        self.max_rounds = max_rounds

    def run_case(self, case_id: str, *, requester: str = 'quality_inspector', peer_requests: bool = True,
                 budget: float = 1.0, deadline_ms: float = 1500.0, origin: str = 'TEST_FIXTURE') -> CaseResult:
        bus, tr = self.bus, self.bus.trace
        store = bus.store(requester)
        initial = store.evidence_for_decision()
        control = evaluate(case_id, initial, bus.station_keys, now=bus.now)
        sources_before = effective_source_count(_roots(initial)) if initial else 0

        belief = self.belief.prior if hasattr(self.belief, 'prior') else 0.5
        prior = belief
        path: list[dict] = [{'step': 'prior', 'belief': belief}]
        # the requester's own observations also move belief; they are not 'requests'
        for e in sorted(initial, key=lambda x: x.observed_at):
            s = _own_summary(e)
            belief, note = self.belief.update(belief, s)
            path.append({'step': f'own:{e.kind}', 'belief': belief, 'note': note})

        missing = [k for k in NEEDED_KINDS if k not in store.visible_kinds()]
        bus.send(bus.make('FIND_MISSING_EVIDENCE', requester, requester, case_id,
                          {'hypotheses': list(HYPOTHESES), 'have': [e.event_id for e in initial], 'missing': missing}))

        outcomes: dict[str, str] = {}
        history: list[dict] = []
        remaining = budget
        peers = {k: r for k, r in bus.ownership.items() if r in bus.stores and r != requester}
        for kind in missing:
            if kind not in peers: outcomes[kind] = 'NOT_REQUESTED'  # nobody on this bus owns it
        rounds = 0
        while peer_requests and rounds < self.max_rounds:
            rounds += 1
            state = {'case_id': case_id, 'requester_role': requester, 'role_domain': ROLES[requester].domain,
                     'entitled_sources': list(ROLES[requester].required_sources), 'hypotheses': list(HYPOTHESES),
                     'visible_evidence': _visible(store), 'missing_kinds': [k for k in missing if k not in store.visible_kinds()],
                     'peers': peers, 'requests_so_far': list(history), 'budget_remaining': round(remaining, 4),
                     'request_cost': bus.request_cost, 'belief': round(belief, 6)}
            try:
                action = self.planner.next_action(state)
            except PlannerUnavailable as ex:
                tr.event('PLANNER_STOPPED', planner=self.planner.name, detail=str(ex))
                break
            finally:
                usage = getattr(self.planner, 'last_usage', None)
                if usage: tr.event('LLM_CALL', planner=self.planner.name, round=rounds, **usage)
            if action is None or action.get('action') == 'finish':
                tr.event('PLANNER_FINISHED', planner=self.planner.name, reason=(action or {}).get('reason', ''))
                break
            problem = _validate(action, state, history, requester, bus)
            if problem:
                tr.event('PROPOSAL_REJECTED', planner=self.planner.name, proposal=action, reason=problem)
                continue
            kind, owner = action['requested_kind'], action['recipient_role']
            if remaining < bus.request_cost:
                outcomes.setdefault(kind, 'NOT_REQUESTED')
                tr.event('PLANNER_STOPPED', planner=self.planner.name, detail=f'budget {remaining:.4f} < request cost {bus.request_cost}')
                break
            req = bus.make('REQUEST_EVIDENCE', requester, owner, case_id,
                           {'requested_kind': kind, 'reason_code': action['reason_code'], 'hypotheses': list(action['hypotheses']),
                            'existing_evidence_ids': [e.event_id for e in store.evidence_for_decision()],
                            'existing_source_roots': sorted(store.known_roots()),
                            'max_cost': round(min(remaining, bus.request_cost), 4), 'deadline_ms': deadline_ms,
                            'proposed_by': self.planner.name})
            reply = bus.send(req)
            if reply is None:  # REQUEST_EVIDENCE always yields a reply; guard narrows the type
                raise RuntimeError('peer bus returned no reply to REQUEST_EVIDENCE')
            outcomes[kind] = reply.body['outcome']
            remaining -= reply.body['cost_charged']
            history.append({'kind': kind, 'recipient': owner, 'outcome': reply.body['outcome'], 'reason': reply.body['reason'],
                            'summaries': [{k: s_[k] for k in ('event_id', 'verdict', 'source_root', 'verification_status', 'new_source')}
                                          for s_ in reply.body['summaries']]})
            for s in reply.body['summaries']:
                before = belief
                belief, note = self.belief.update(belief, s)
                bus.send(bus.make('HYPOTHESIS_UPDATE', requester, requester, case_id,
                                  {'belief_before': before, 'belief_after': belief, 'note': note,
                                   'basis_event_ids': [s['event_id']], 'new_source_roots': [s['source_root']] if s['new_source'] else []},
                                  correlation_id=req.message_id))
                path.append({'step': f'peer:{kind}', 'belief': belief, 'note': note, 'event_id': s['event_id']})

        proposal = self.belief.propose(belief, budget=remaining)
        bus.send(bus.make('PROPOSE_INSPECTION', requester, requester, case_id, proposal))

        final_evidence = store.evidence_for_decision()
        decision = evaluate(case_id, final_evidence, bus.station_keys, now=bus.now)
        changed = (decision.state != control.state) or (decision.reasons != control.reasons)
        bus.send(bus.make('DECISION_PROPOSAL', requester, 'safety_governance' if 'safety_governance' in bus.stores else requester, case_id,
                          {'state': decision.state, 'reasons': list(decision.reasons), 'evidence_ids': list(decision.evidence_ids),
                           'control_state': control.state, 'control_reasons': list(control.reasons), 'decision_changed': changed}))
        sources_after = effective_source_count(_roots(final_evidence)) if final_evidence else 0

        granted = [k for k, o in outcomes.items() if o == 'GRANTED']
        criteria = {
            'information_asymmetry': bool(missing),
            'targeted_request': bool(peer_requests and outcomes) and all(
                e['body'].get('hypotheses') and e['body'].get('reason_code') for e in tr.entries
                if e['type'] == 'MESSAGE' and e['kind'] == 'REQUEST_EVIDENCE'),
            'new_verified_source': sources_after > sources_before,
            'behavior_change': changed or abs(belief - path[len(initial)]['belief']) > 1e-9,  # peers moved belief, or the decision moved
            'control_run_present': True,
        }
        criteria['genuine_collaboration'] = all(criteria.values()) and bool(granted)
        return CaseResult(case_id=case_id, requester=requester, origin=origin, decision=decision.to_dict(),
                          control_decision=control.to_dict(), decision_changed=changed, belief_prior=prior,
                          belief_final=belief, belief_path=path, requests=len([o for o in outcomes.values() if o != 'NOT_REQUESTED']),
                          request_outcomes=outcomes, cost_charged=round(bus.cost_charged, 4),
                          independent_sources_before=sources_before, independent_sources_after=sources_after,
                          proposal=proposal, criteria=criteria, trace=tr.to_dict(), narrative=tr.narrative(),
                          planner=(self.planner.describe() if hasattr(self.planner, 'describe') else {'planner': self.planner.name}))


def _validate(action: dict, state: dict, history: list[dict], requester: str, bus) -> str | None:
    """Schema-level checks on a planner proposal before it becomes a signed message. The ACL
    (entitlement, ownership) is deliberately left to the bus so a mis-addressed request shows up
    in the trace as a real REJECT_REQUEST, exactly as it would for any other sender."""
    if action.get('action') == 'invalid':
        return f"planner output invalid: {action.get('error')}"
    if action.get('action') != 'request':
        return f"unknown planner action {action.get('action')!r}"
    kind, owner = action.get('requested_kind'), action.get('recipient_role')
    if kind not in SOURCE_FAMILY:
        return f'unknown evidence kind {kind!r}'
    if owner not in bus.stores or owner == requester:
        return f'recipient {owner!r} is not a peer on this bus'
    if kind not in state['missing_kinds']:
        return f'{kind} is not missing from the requester view'
    if any(h['kind'] == kind and h['outcome'] not in RETRYABLE for h in history):
        return f'{kind} was already requested ({[h["outcome"] for h in history if h["kind"] == kind]}); no repeats'
    reason, hyps = action.get('reason_code'), action.get('hypotheses')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 64:
        return 'reason_code must be a non-empty string <= 64 chars'
    if not isinstance(hyps, list) or not hyps or any(h not in HYPOTHESES for h in hyps):
        return f'hypotheses must be a non-empty subset of {list(HYPOTHESES)}'
    return None


def _visible(store) -> list[dict]:
    """The requester's own view: its observations plus granted summaries. Never another store."""
    own = [{'event_id': e.event_id, 'kind': e.kind, 'verdict': e.verdict, 'origin': e.origin, 'source_root': e.source_root,
            'calibration_id': e.calibration_id, 'held_by': 'self'} for e in store.own]
    got = [{k: s[k] for k in ('event_id', 'kind', 'verdict', 'origin', 'source_root', 'calibration_id', 'verification_status')} | {'held_by': 'peer'}
           for s in store.received]
    return own + got


def _roots(evidence) -> list[dict]:
    return [{'event_id': e.event_id, 'source_root': e.source_root,
             'parent_source_roots': e.payload.get('parent_source_roots', [])} for e in evidence]


def _own_summary(e) -> dict:
    return {'event_id': e.event_id, 'kind': e.kind, 'verdict': e.verdict, 'calibration_id': e.calibration_id,
            'source_root': e.source_root, 'verification_status': 'VERIFIED', 'new_source': True}
