"""TEST_FIXTURE collaboration cases built on demo.example_evidence (origin TEST_FIXTURE, never
physical). Each scenario is one honest situation the protocol must handle, not a benchmark."""
from __future__ import annotations
import secrets
from dataclasses import replace
from ..contracts import sign_evidence
from ..demo import example_evidence
from .peer_protocol import PeerBus
from .belief import illustrative
from .engine import CollaborationEngine, CaseResult
from .trace import Trace

SCENARIOS = {
    'pi_clear': 'Pi camera agrees (clear): request yields a new independent source; decision may reach PASS_REVIEW',
    'pi_suspect': 'Pi camera disagrees (suspect): new source raises belief; HOLD with VISUAL_PI_SUSPECT',
    'pi_duplicate_photo': 'Pi "evidence" is a re-score of the phone photo (same source_root): DUPLICATE_SOURCE, belief unchanged',
    'pi_stale': 'Pi evidence is 2 hours old: STALE_EVIDENCE, not delivered',
    'pi_forged': 'Pi evidence signed with the wrong station key: BAD_SIGNATURE, not delivered',
    'pi_timeout': 'Pi responder slower than the deadline: TIMEOUT, no evidence, request still charged',
    'pi_offline': 'Pi station has nothing for this part: SENSOR_FAILURE',
    'no_requests': 'Control: same private view, peer requests disabled',
}
OWNERSHIP = {'PHONE_IMAGE': 'quality_inspector', 'PI_IMAGE': 'additive_manufacturing_expert', 'CAD_IMAGE': 'design_geometry',
             'CALIPER': 'metrology_engineer', 'ASSEMBLY': 'assembly_engineer'}
CASE_ID = 'TAB-B12'


def build(scenario: str, *, request_cost: float = 0.3, budget: float = 1.0, planner=None) -> CaseResult:
    if scenario not in SCENARIOS: raise ValueError(f'unknown scenario {scenario!r}; one of {sorted(SCENARIOS)}')
    ev, station_keys, now = example_evidence(suspect_pi=(scenario == 'pi_suspect'))
    by_kind = {e.kind: e for e in ev}
    pi = by_kind['PI_IMAGE']
    if scenario == 'pi_duplicate_photo':
        pi = sign_evidence(replace(pi, source_root=by_kind['PHONE_IMAGE'].source_root), station_keys['pi'])
    elif scenario == 'pi_stale':
        pi = sign_evidence(replace(pi, observed_at=now - 7200), station_keys['pi'])
    elif scenario == 'pi_forged':
        pi = sign_evidence(pi, 'not-the-pi-station-key')
    roles = ['quality_inspector', 'additive_manufacturing_expert', 'design_geometry', 'metrology_engineer', 'assembly_engineer', 'safety_governance']
    role_keys = {r: secrets.token_hex(16) for r in roles}
    bus = PeerBus(role_keys=role_keys, station_keys=station_keys, ownership=OWNERSHIP, now=now, trace=Trace(now=now), request_cost=request_cost)
    # information asymmetry: the quality inspector starts with phone + CAD only (plan section 7.4)
    bus.register('quality_inspector', [by_kind['PHONE_IMAGE'], by_kind['CAD_IMAGE']])
    bus.register('design_geometry', [by_kind['CAD_IMAGE']])
    bus.register('metrology_engineer', [by_kind['CALIPER']])
    bus.register('assembly_engineer', [by_kind['ASSEMBLY']])
    bus.register('safety_governance', [])
    if scenario == 'pi_offline':
        bus.register('additive_manufacturing_expert', [])
    elif scenario == 'pi_timeout':
        bus.register('additive_manufacturing_expert', [pi], responder=lambda k, b: ([pi] if k == 'PI_IMAGE' else [], 9000.0))
    else:
        bus.register('additive_manufacturing_expert', [pi])
    engine = CollaborationEngine(bus, illustrative(), planner=planner)
    return engine.run_case(CASE_ID, peer_requests=(scenario != 'no_requests'), budget=budget)
