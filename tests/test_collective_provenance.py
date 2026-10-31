"""AGENT-03 / AGENT-05: traces show what changed; duplicate / stale / forged evidence never
counts as a new independent source. Runs the end-to-end scenarios."""
import json
import pytest
from qualityrelay17.collective.scenarios import build, SCENARIOS
from qualityrelay17.collective.belief import illustrative, from_likelihoods


def test_every_scenario_runs_and_serializes():
    for sc in SCENARIOS:
        r = build(sc)
        d = r.to_dict(); json.dumps(d)
        assert d['origin'] == 'TEST_FIXTURE' and d['trace']['schema_version'] == '17.1' and d['narrative']


def test_genuine_collaboration_pi_suspect_raises_belief_and_holds():
    r = build('pi_suspect')
    assert r.request_outcomes['PI_IMAGE'] == 'GRANTED'
    assert r.independent_sources_after > r.independent_sources_before
    i = next(i for i, p in enumerate(r.belief_path) if p['step'] == 'peer:PI_IMAGE')
    assert r.belief_path[i]['belief'] > r.belief_path[i - 1]['belief']  # the suspect Pi reading raised belief
    assert r.decision['state'] == 'HOLD' and 'VISUAL_PI_SUSPECT' in r.decision['reasons']
    assert r.criteria['genuine_collaboration'] is True
    assert any('REQUEST_EVIDENCE PI_IMAGE' in line for line in r.narrative)


def test_control_run_without_requests_cannot_reach_pass_review():
    ctrl = build('no_requests')
    assert ctrl.requests == 0 and ctrl.cost_charged == 0.0
    assert ctrl.decision['state'] == 'HOLD' and 'MISSING_CAMERA_EVIDENCE' in ctrl.decision['reasons']
    assert ctrl.decision_changed is False and ctrl.criteria['genuine_collaboration'] is False


def test_pi_clear_reaches_pass_review_only_through_granted_requests():
    r = build('pi_clear')
    assert r.control_decision['state'] == 'HOLD' and r.decision['state'] == 'PASS_REVIEW'
    assert r.decision_changed is True
    assert all(r.request_outcomes[k] == 'GRANTED' for k in ('PI_IMAGE', 'CALIPER', 'ASSEMBLY'))
    assert 'CAD_IMAGE' not in r.request_outcomes  # CAD was already in the private view, so never requested
    assert r.cost_charged == pytest.approx(0.9)  # three charged requests at 0.3


def test_duplicate_photo_is_not_a_new_source_and_does_not_move_belief():
    r = build('pi_duplicate_photo')
    assert r.request_outcomes['PI_IMAGE'] == 'DUPLICATE_SOURCE'
    peer = [p for p in r.belief_path if p['step'] == 'peer:PI_IMAGE']
    assert peer and 'ignored' in peer[0]['note']
    # the duplicate did not add an independent source; later granted requests did
    assert any(e['type'] == 'VERIFY' and e['outcome'] == 'DUPLICATE_SOURCE' for e in r.trace['entries'])
    assert r.decision['state'] == 'HOLD' and 'MISSING_CAMERA_EVIDENCE' in r.decision['reasons']


def test_stale_and_forged_evidence_are_refused_at_verify():
    stale = build('pi_stale'); forged = build('pi_forged')
    assert stale.request_outcomes['PI_IMAGE'] == 'STALE_EVIDENCE'
    assert forged.request_outcomes['PI_IMAGE'] == 'BAD_SIGNATURE'
    for r in (stale, forged):
        assert not any(s['verification_status'] == 'VERIFIED' and s['kind'] == 'PI_IMAGE'
                       for e in r.trace['entries'] if e['type'] == 'MESSAGE' and e['kind'] == 'EVIDENCE_RESPONSE'
                       for s in e['body']['summaries'])
        assert r.decision['state'] == 'HOLD'


def test_timeout_and_offline_are_outcomes_not_negative_measurements():
    t = build('pi_timeout'); o = build('pi_offline')
    assert t.request_outcomes['PI_IMAGE'] == 'TIMEOUT' and o.request_outcomes['PI_IMAGE'] == 'SENSOR_FAILURE'
    for r in (t, o):
        assert not any(p['step'] == 'peer:PI_IMAGE' for p in r.belief_path)  # nothing pretended to be an observation
        assert 'MISSING_CAMERA_EVIDENCE' in r.decision['reasons']


def test_trace_has_message_level_provenance_and_belief_before_after():
    r = build('pi_suspect')
    msgs = [e for e in r.trace['entries'] if e['type'] == 'MESSAGE']
    assert all({'message_id', 'sender_role', 'recipient_role', 'signature_valid', 'correlation_id'} <= set(e) for e in msgs)
    upd = [e for e in msgs if e['kind'] == 'HYPOTHESIS_UPDATE']
    assert upd and all('belief_before' in e['body'] and 'belief_after' in e['body'] for e in upd)
    resp = [e for e in msgs if e['kind'] == 'EVIDENCE_RESPONSE']
    assert all(e['correlation_id'] for e in resp)  # every response points at its request
    dec = [e for e in msgs if e['kind'] == 'DECISION_PROPOSAL'][0]
    assert dec['body']['control_state'] and 'decision_changed' in dec['body']


def test_belief_interface_is_swappable():
    from qualityrelay17.calibration import Likelihoods
    lk = Likelihoods(phone_sens=.8, phone_spec=.9, pi_sens=.85, pi_spec=.9, caliper_sens=.98, caliper_spec=.98,
                     phone_recapture_sens=.8, phone_recapture_spec=.9, pi_recapture_sens=.85, pi_recapture_spec=.9,
                     caliper_retake_sens=.98, caliper_retake_spec=.98, surface_prior=.05, dimensional_prior=.05,
                     source='unit-test', calibration_id='cal-test')
    m = from_likelihoods(lk)
    assert m.prior == .05 and m.source == 'calibration:cal-test'
    b, note = m.update(.05, {'kind': 'PI_IMAGE', 'verdict': 'suspect', 'calibration_id': 'c', 'verification_status': 'VERIFIED', 'new_source': True})
    assert b > .05 and 'PI_IMAGE' in note
    assert illustrative().source == 'ILLUSTRATIVE_NOT_CALIBRATED'


def test_uncalibrated_visual_does_not_update_belief():
    m = illustrative()
    b, note = m.update(.1, {'kind': 'PI_IMAGE', 'verdict': 'suspect', 'calibration_id': '', 'verification_status': 'VERIFIED', 'new_source': True})
    assert b == .1 and 'uncalibrated' in note
