import pytest
from qualityrelay17.hardware_ingest import (
    potentiometer_to_mm, caliper_evidence, thermistor_process_evidence, bin_ack_evidence,
)
from qualityrelay17.contracts import signature_valid

KEY = 'test-secret-do-not-use-in-real-deployment'


def test_potentiometer_linear_mapping():
    assert potentiometer_to_mm(0, mm_min=18.0, mm_max=22.0) == 18.0
    assert potentiometer_to_mm(4095, mm_min=18.0, mm_max=22.0) == 22.0
    assert 19.9 < potentiometer_to_mm(2048, mm_min=18.0, mm_max=22.0) < 20.1


def test_potentiometer_rejects_out_of_range():
    with pytest.raises(ValueError):
        potentiometer_to_mm(5000)


def test_caliper_evidence_signed_and_verifiable():
    e = caliper_evidence(event_id='evt-1', specimen_id='S-001', station_id='slot',
                          adc_value=2048, uncertainty_mm=0.03, calibration_id='cal-slot-01', key=KEY)
    assert signature_valid(e, {'slot': KEY})
    assert not signature_valid(e, {'slot': 'wrong-key'})
    assert e.origin == 'PHYSICAL_CAPTURE'
    assert e.payload['unit'] == 'mm'


def test_caliper_evidence_rejects_negative_uncertainty():
    with pytest.raises(ValueError):
        caliper_evidence(event_id='evt-2', specimen_id='S-001', station_id='slot',
                          adc_value=2048, uncertainty_mm=-0.01, calibration_id='cal-slot-01', key=KEY)


def test_thermistor_rejects_implausible_reading():
    with pytest.raises(ValueError):
        thermistor_process_evidence(event_id='evt-3', specimen_id='S-001', station_id='slot',
                                     temperature_c=999.0, key=KEY)


def test_bin_ack_requires_actual_detection():
    with pytest.raises(ValueError):
        bin_ack_evidence(event_id='evt-4', specimen_id='S-001', station_id='sorter',
                          bin_name='PASS', photoresistor_blocked=False, key=KEY)


def test_bin_ack_signed_when_detected():
    e = bin_ack_evidence(event_id='evt-5', specimen_id='S-001', station_id='sorter',
                          bin_name='PASS', photoresistor_blocked=True, key=KEY)
    assert signature_valid(e, {'sorter': KEY})
    assert e.kind == 'ROUTE_ACK'
