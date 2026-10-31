"""AGENT-01: typed, role-signed messages; sender identity comes from the signature."""
import pytest
from qualityrelay17.collective.messages import Message, sign_message, message_valid, KINDS, admissible_summary
from qualityrelay17.collective.peer_protocol import PeerBus
from qualityrelay17.collective.trace import Trace
from qualityrelay17.demo import example_evidence

KEYS = {'quality_inspector': 'k-q' * 8, 'metrology_engineer': 'k-m' * 8}


def msg(kind='REQUEST_EVIDENCE', sender='quality_inspector', body=None, mid='m1'):
    return Message(message_id=mid, case_id='TAB-B12', kind=kind, sender_role=sender, recipient_role='metrology_engineer',
                   sent_at=1000.0, body=body if body is not None else {'requested_kind': 'CALIPER', 'reason_code': 'X', 'hypotheses': ['h']})


def test_all_six_kinds_exist_and_unknown_kind_rejected():
    assert set(KINDS) == {'FIND_MISSING_EVIDENCE', 'REQUEST_EVIDENCE', 'EVIDENCE_RESPONSE', 'HYPOTHESIS_UPDATE', 'PROPOSE_INSPECTION', 'DECISION_PROPOSAL'}
    with pytest.raises(ValueError):
        msg(kind='FREEFORM_CHAT')


def test_response_requires_technical_outcome():
    with pytest.raises(ValueError):
        msg(kind='EVIDENCE_RESPONSE', body={'summaries': []})
    msg(kind='EVIDENCE_RESPONSE', body={'outcome': 'TIMEOUT', 'summaries': []})


def test_signature_roundtrip_and_tamper():
    m = sign_message(msg(), KEYS['quality_inspector'])
    assert message_valid(m, KEYS)
    tampered = Message(**{**m.unsigned(), 'body': {**m.body, 'requested_kind': 'PI_IMAGE'}, 'signature': m.signature})
    assert not message_valid(tampered, KEYS)


def test_sender_identity_is_the_signature_not_the_text():
    forged = sign_message(msg(sender='quality_inspector'), KEYS['metrology_engineer'])  # claims Quality, signed by Metrology
    assert not message_valid(forged, KEYS)
    unsigned = msg()
    assert not message_valid(unsigned, KEYS)


def _bus():
    ev, station_keys, now = example_evidence()
    bus = PeerBus(role_keys=KEYS, station_keys=station_keys, ownership={'CALIPER': 'metrology_engineer'}, now=now, trace=Trace(now=now))
    bus.register('quality_inspector', [e for e in ev if e.kind == 'PHONE_IMAGE'])
    bus.register('metrology_engineer', [e for e in ev if e.kind == 'CALIPER'])
    return bus


def test_bus_rejects_forged_sender_and_records_it():
    bus = _bus()
    forged = sign_message(msg(), KEYS['metrology_engineer'])
    with pytest.raises(PermissionError):
        bus.send(forged)
    assert bus.trace.entries[-1]['signature_valid'] is False
    assert 'REJECTED' in bus.trace.narrative()[-1]


def test_bus_rejects_duplicate_message_id():
    bus = _bus()
    m = bus.make('REQUEST_EVIDENCE', 'quality_inspector', 'metrology_engineer', 'TAB-B12',
                 {'requested_kind': 'CALIPER', 'reason_code': 'X', 'hypotheses': ['h']})
    bus.send(m)
    with pytest.raises(ValueError, match='duplicate message id'):
        bus.send(m)


def test_admissible_summary_never_leaks_raw_payload():
    ev, _, _ = example_evidence()
    e = next(x for x in ev if x.kind == 'CALIPER')
    e2 = type(e)(**{**e.unsigned(), 'payload': {**e.payload, 'raw_image_path': '/secret.png', 'private_note': 'x'}, 'signature': e.signature})
    s = admissible_summary(e2, verification_status='VERIFIED', new_source=True)
    assert 'raw_image_path' not in s['payload'] and 'private_note' not in s['payload']
    assert s['payload']['measurement_mm'] == 20.1 and s['source_root'] == e.source_root
