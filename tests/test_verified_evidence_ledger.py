"""BACK-02: VERIFIED_PHYSICAL is derived from a recorded ground-truth check of a station-authenticated
capture; unauthenticated or unsigned readings stay PHYSICAL_CAPTURE / UNVERIFIED."""
import json, sqlite3, time
import pytest
from qualityrelay17.contracts import Evidence, sign_evidence
from qualityrelay17.hardware_ingest import caliper_evidence
from qualityrelay17.ledger import EvidenceLedger
from qualityrelay17.verification import VerificationRefused

KEY = 'slot-station-key-' + 's' * 32
KEYS = {'slot': KEY}
STATIONS = {'slot', 'tab', 'sorter'}
REF = {'procedure_id': 'GT-CAL-01', 'observed_specimen_id': 'S-1', 'reference_value_mm': 20.0,
       'reference_uncertainty_mm': 0.01, 'reference_instrument_id': 'mitutoyo-500-196', 'reference_calibration_id': 'cert-2026-07'}


def reading(event_id='e1', specimen='S-1', adc=2048, u=0.03, cal='cal-1', key=KEY):
    return caliper_evidence(event_id=event_id, specimen_id=specimen, station_id='slot', adc_value=adc,
                            uncertainty_mm=u, calibration_id=cal, key=key)  # 2048 -> 20.0005 mm


def verify(led, event_id='e1', verifier='alice', now=None, **kw):
    return led.record_verification(event_id, {**REF, **kw}, verifier_id=verifier, station_keys=KEYS,
                                   station_ids=STATIONS, now=time.time() if now is None else now)


@pytest.fixture
def led():
    return EvidenceLedger()


def test_verified_physical_cannot_be_written(led):
    e = Evidence('v1', 'S-1', 'slot', 'CALIPER', 'VERIFIED_PHYSICAL', 'r', time.time(), 'verified', {})
    with pytest.raises(PermissionError, match='derived'):
        led.append(sign_evidence(e, KEY), authenticated_station='slot')


def test_authenticated_station_must_match_record(led):
    with pytest.raises(PermissionError):
        led.append(reading(), authenticated_station='tab')


def test_unauthenticated_capture_stays_unverified_and_cannot_be_promoted(led):
    led.append(reading())  # no authenticated_station: e.g. a raw/manual import
    st = led.evidence_status('e1', station_keys=KEYS)
    assert st['effective_origin'] == 'PHYSICAL_CAPTURE' and st['verification_status'] == 'UNVERIFIED'
    assert 'NOT_STATION_AUTHENTICATED' in st['candidate_problems']
    with pytest.raises(VerificationRefused) as ex:
        verify(led)
    assert ex.value.status == 409
    assert led.evidence_status('e1', station_keys=KEYS)['verifications'] == []  # nothing recorded


def test_authenticated_capture_awaits_ground_truth_until_checked(led):
    led.append(reading(), authenticated_station='slot')
    st = led.evidence_status('e1', station_keys=KEYS)
    assert st['candidate_for_verified_physical'] and st['verification_status'] == 'AWAITING_GROUND_TRUTH'
    assert st['effective_origin'] == 'PHYSICAL_CAPTURE'


def test_agreeing_instrument_check_derives_verified_physical_without_mutating_record(led):
    led.append(reading(), authenticated_station='slot')
    out = verify(led)
    v = out['verification']
    assert v['outcome'] == 'CONFIRMED' and v['verifier_id'] == 'alice' and v['procedure_doc'].endswith('#gt-cal-01')
    assert v['abs_difference_mm'] <= v['agreement_band_mm']
    assert out['status']['effective_origin'] == 'VERIFIED_PHYSICAL'
    assert led.get_event('e1')['origin'] == 'PHYSICAL_CAPTURE'  # stored tier untouched; promotion is a view


def test_disagreeing_check_is_recorded_disputed_and_latches(led):
    led.append(reading(), authenticated_station='slot')
    out = verify(led, reference_value_mm=20.5)  # 0.5 mm off; band is 2*sqrt(.03^2+.01^2) ~ 0.063
    assert out['verification']['outcome'] == 'DISPUTED'
    assert out['status']['effective_origin'] == 'PHYSICAL_CAPTURE' and out['status']['verification_status'] == 'DISPUTED'
    later = verify(led, verifier='bob')  # a later agreeing check does not erase a recorded disagreement
    assert later['verification']['outcome'] == 'CONFIRMED' and later['status']['verification_status'] == 'DISPUTED'


def test_wrong_signature_key_is_not_a_candidate(led):
    led.append(reading(key='some-other-key-' + 'k' * 32), authenticated_station='slot')
    assert 'GATEWAY_SIGNATURE_INVALID' in led.evidence_status('e1', station_keys=KEYS)['candidate_problems']


def test_uncalibrated_capture_is_not_a_candidate(led):
    led.append(reading(cal=''), authenticated_station='slot')
    with pytest.raises(VerificationRefused, match='NO_CALIBRATION_ID'):
        verify(led)


@pytest.mark.parametrize('change,status,msg', [
    ({'procedure_id': 'TRUST-ME'}, 422, 'unknown procedure'),
    ({'procedure_id': 'GT-VIS-01', 'observed_verdict': 'verified'}, 422, 'does not apply'),
    ({'reference_instrument_id': ''}, 422, 'requires'),
    ({'observed_specimen_id': 'S-2'}, 409, 'specimen'),
])
def test_incomplete_or_mismatched_requests_record_nothing(led, change, status, msg):
    led.append(reading(), authenticated_station='slot')
    with pytest.raises(VerificationRefused, match=msg) as ex:
        verify(led, **change)
    assert ex.value.status == status
    assert led.evidence_status('e1', station_keys=KEYS)['verifications'] == []


def test_station_identity_cannot_act_as_verifier(led):
    led.append(reading(), authenticated_station='slot')
    with pytest.raises(VerificationRefused) as ex:
        verify(led, verifier='slot')
    assert ex.value.status == 403


def test_check_long_after_capture_is_refused(led):
    led.append(reading(), authenticated_station='slot')
    with pytest.raises(VerificationRefused, match='old'):
        verify(led, now=time.time() + 2 * 24 * 3600)


def test_unknown_event_is_404(led):
    with pytest.raises(VerificationRefused) as ex:
        verify(led, event_id='nope')
    assert ex.value.status == 404


def test_pre_back02_ledger_file_is_migrated_and_rows_stay_unauthenticated(tmp_path):
    path = tmp_path / 'old.sqlite'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE evidence(event_id TEXT PRIMARY KEY, station_id TEXT NOT NULL, specimen_id TEXT NOT NULL, payload TEXT NOT NULL)')
    from dataclasses import asdict
    e = reading()
    db.execute('INSERT INTO evidence VALUES (?,?,?,?)', (e.event_id, e.station_id, e.specimen_id, json.dumps(asdict(e))))
    db.commit(); db.close()
    led = EvidenceLedger(str(path))
    st = led.evidence_status('e1', station_keys=KEYS)
    assert st['station_authenticated'] is False and st['verification_status'] == 'UNVERIFIED'
