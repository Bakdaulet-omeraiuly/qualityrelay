"""AGENT-02: private context per specialist; requests are checked by code, not trusted."""
from qualityrelay17.collective.peer_protocol import PeerBus
from qualityrelay17.collective.trace import Trace
from qualityrelay17.demo import example_evidence

ROLES = ['quality_inspector', 'metrology_engineer', 'design_geometry', 'additive_manufacturing_expert', 'materials_engineer']
KEYS = {r: f'key-{r}-' + 'x' * 24 for r in ROLES}
OWN = {'CALIPER': 'metrology_engineer', 'CAD_IMAGE': 'design_geometry', 'PI_IMAGE': 'additive_manufacturing_expert'}


def bus(responder=None):
    ev, station_keys, now = example_evidence()
    b = PeerBus(role_keys=KEYS, station_keys=station_keys, ownership=OWN, now=now, trace=Trace(now=now), request_cost=0.3)
    by = {e.kind: e for e in ev}
    b.register('quality_inspector', [by['PHONE_IMAGE']])
    b.register('metrology_engineer', [by['CALIPER']])
    b.register('design_geometry', [by['CAD_IMAGE']])
    b.register('additive_manufacturing_expert', [by['PI_IMAGE']], responder=responder)
    b.register('materials_engineer', [])
    return b


def ask(b, sender, recipient, kind, **extra):
    body = {'requested_kind': kind, 'reason_code': 'TEST', 'hypotheses': ['surface_defect'], 'deadline_ms': 1500, **extra}
    return b.send(b.make('REQUEST_EVIDENCE', sender, recipient, 'TAB-B12', body))


def test_roles_do_not_see_each_others_stores():
    b = bus()
    assert b.store('quality_inspector').visible_kinds() == {'PHONE_IMAGE'}
    assert b.store('quality_inspector').evidence_for_decision()[0].kind == 'PHONE_IMAGE'


def test_entitled_request_is_granted_and_delivers_summary_only():
    b = bus()
    r = ask(b, 'quality_inspector', 'metrology_engineer', 'CALIPER')
    assert r.body['outcome'] == 'GRANTED' and r.sender_role == 'metrology_engineer' and r.recipient_role == 'quality_inspector'
    s = b.store('quality_inspector').received[0]
    assert s['kind'] == 'CALIPER' and s['verification_status'] == 'VERIFIED' and set(s['payload']) <= {'measurement_mm', 'uncertainty_mm', 'unit', 'validated'}
    assert 'CALIPER' in b.store('quality_inspector').visible_kinds()


def test_requester_not_entitled_to_source_family_is_rejected():
    b = bus()
    r = ask(b, 'materials_engineer', 'metrology_engineer', 'CALIPER')  # materials_engineer: required_sources=(CERTIFICATE,)
    assert r.body['outcome'] == 'REJECT_REQUEST' and 'ACL_REQUESTER_NOT_ENTITLED' in r.body['reason']
    assert b.store('materials_engineer').received == []
    r = ask(b, 'quality_inspector', 'design_geometry', 'CAD_IMAGE')  # quality_inspector has no CAD entitlement
    assert r.body['outcome'] == 'REJECT_REQUEST'


def test_recipient_must_own_the_requested_kind():
    b = bus()
    r = ask(b, 'quality_inspector', 'metrology_engineer', 'PI_IMAGE')  # metrology does not own Pi
    assert r.body['outcome'] == 'REJECT_REQUEST' and 'RECIPIENT_NOT_OWNER' in r.body['reason']
    assert b.cost_charged == 0.0  # rejected on ACL before any cost


def test_untargeted_request_is_rejected():
    b = bus()
    r = b.send(b.make('REQUEST_EVIDENCE', 'quality_inspector', 'metrology_engineer', 'TAB-B12', {'requested_kind': 'CALIPER'}))
    assert r.body['outcome'] == 'REJECT_REQUEST' and 'UNTARGETED' in r.body['reason']


def test_deadline_timeout_is_a_technical_outcome_and_still_charged():
    b = bus(responder=lambda kind, body: ([e for e in b.store('additive_manufacturing_expert').own], 5000.0))
    r = ask(b, 'quality_inspector', 'additive_manufacturing_expert', 'PI_IMAGE', deadline_ms=1500)
    assert r.body['outcome'] == 'TIMEOUT' and r.body['summaries'] == [] and r.body['cost_charged'] == 0.3
    assert b.store('quality_inspector').received == []


def test_sensor_failure_when_owner_has_nothing():
    b = bus(responder=lambda kind, body: ([], 10.0))
    r = ask(b, 'quality_inspector', 'additive_manufacturing_expert', 'PI_IMAGE')
    assert r.body['outcome'] == 'SENSOR_FAILURE'


def test_responder_exception_is_sensor_failure_not_a_measurement():
    def boom(kind, body): raise RuntimeError('camera unplugged')
    b = bus(responder=boom)
    r = ask(b, 'quality_inspector', 'additive_manufacturing_expert', 'PI_IMAGE')
    assert r.body['outcome'] == 'SENSOR_FAILURE' and 'camera unplugged' in r.body['reason']


def test_max_cost_caps_the_charge():
    b = bus()
    r = ask(b, 'quality_inspector', 'metrology_engineer', 'CALIPER', max_cost=0.1)
    assert r.body['cost_charged'] == 0.1 and b.cost_charged == 0.1
