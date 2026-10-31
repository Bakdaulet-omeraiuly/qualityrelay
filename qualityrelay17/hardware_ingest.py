"""Reference adapter: turn raw ESP32 / Raspberry Pi sensor payloads into signed Evidence.

Calibration constants below are placeholders for a specific potentiometer/photoresistor
wiring. Measure your own ADC-to-mm curve and repeatability before trusting these numbers
-- see docs/engineering/PHYSICAL_TEST_PLAYBOOK.md for the exact procedure.

Origin is always PHYSICAL_CAPTURE: this module never promotes anything. VERIFIED_PHYSICAL is
derived later, and only for station-authenticated, calibrated readings with an agreeing recorded
human/instrument check (verification.py, BACK-02; GROUND_TRUTH_VERIFICATION_PROCEDURE.md).

Boundary (decided 31 Oct, TOMORROW_TASKS item 2): this module is a pure transform --
raw payload in, signed Evidence out, no I/O, no state. It deliberately does NOT append to
EvidenceLedger. Persistence and replay rejection (409 on a repeated event_id) live in
api.py's endpoints via HARDWARE_LEDGER, so that (a) these functions stay unit-testable
without a database, (b) a refused reading (ValueError here) can never leave a row behind,
and (c) there is exactly one place that decides what counts as "recorded".
"""
from __future__ import annotations
import time
from .contracts import Evidence, sign_evidence


def potentiometer_to_mm(adc_value: int, *, adc_max: int = 4095,
                         mm_min: float = 18.0, mm_max: float = 22.0) -> float:
    """Linear ADC-to-millimetre map. Replace with your OWN fitted curve
    (measure >= 5 known positions against a real caliper) before using live."""
    if not 0 <= adc_value <= adc_max:
        raise ValueError('adc_value out of range for this board')
    if mm_max <= mm_min:
        raise ValueError('mm_max must exceed mm_min')
    fraction = adc_value / adc_max
    return round(mm_min + fraction * (mm_max - mm_min), 4)


def caliper_evidence(*, event_id: str, specimen_id: str, station_id: str, adc_value: int,
                      uncertainty_mm: float, calibration_id: str, key: str,
                      adc_max: int = 4095, mm_min: float = 18.0, mm_max: float = 22.0) -> Evidence:
    """Signed CALIPER evidence from a raw potentiometer reading.

    uncertainty_mm MUST come from your own repeatability screen (>= 10 reseated reads on
    the same specimen), never a guessed number -- that screen is step 1 of
    docs/engineering/PHYSICAL_TEST_PLAYBOOK.md for exactly this reason.
    """
    if uncertainty_mm < 0:
        raise ValueError('uncertainty_mm must be >= 0')
    measurement_mm = potentiometer_to_mm(adc_value, adc_max=adc_max, mm_min=mm_min, mm_max=mm_max)
    e = Evidence(
        event_id=event_id, specimen_id=specimen_id, station_id=station_id,
        kind='CALIPER', origin='PHYSICAL_CAPTURE',
        source_root=f'adc:{station_id}:{adc_value}', observed_at=time.time(), verdict='verified',
        payload={'measurement_mm': measurement_mm, 'uncertainty_mm': round(uncertainty_mm, 4),
                 'unit': 'mm', 'validated': True, 'sensor': 'precision_potentiometer_adc'},
        calibration_id=calibration_id,
    )
    return sign_evidence(e, key)


def thermistor_process_evidence(*, event_id: str, specimen_id: str, station_id: str,
                                 temperature_c: float, key: str) -> Evidence:
    """Signed PROCESS evidence from the thermistor -- a physically real covariate for
    *why* a dimension might drift (thermal expansion), not a defect verdict by itself."""
    if not -20 <= temperature_c <= 120:
        raise ValueError('temperature_c outside plausible sensor range; check wiring/divider')
    e = Evidence(
        event_id=event_id, specimen_id=specimen_id, station_id=station_id,
        kind='PROCESS', origin='PHYSICAL_CAPTURE',
        source_root=f'thermistor:{station_id}', observed_at=time.time(), verdict='clear',
        payload={'temperature_c': round(temperature_c, 2), 'sensor': 'ntc_thermistor_divider'},
    )
    return sign_evidence(e, key)


def bin_ack_evidence(*, event_id: str, specimen_id: str, station_id: str, bin_name: str,
                      photoresistor_blocked: bool, key: str) -> Evidence:
    """Signed ROUTE_ACK from the photoresistor + 4N35 independent bin sensor.

    This path is deliberately separate from the actuation COMMAND path (actuation.py) --
    the 4N35 gives real galvanic isolation between 'we told the sorter to move' and
    'something was independently sensed arriving'. It is the sensor-side half of H5 /
    E12 / E13 in EXPERIMENT_PROTOCOL.md, feeding actuation.SorterInterlock.acknowledge()
    as its sensor_event_id -- never a replacement for operator approval.
    """
    if not photoresistor_blocked:
        raise ValueError('no part detected at bin; refusing to manufacture an acknowledgment')
    e = Evidence(
        event_id=event_id, specimen_id=specimen_id, station_id=station_id,
        kind='ROUTE_ACK', origin='PHYSICAL_CAPTURE',
        source_root=f'ldr4n35:{station_id}:{bin_name}', observed_at=time.time(), verdict='verified',
        payload={'bin': bin_name, 'sensor': 'photoresistor_4n35_isolated'},
    )
    return sign_evidence(e, key)
