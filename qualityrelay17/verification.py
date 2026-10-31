"""Ground-truth verification rules (task board BACK-02). Pure functions, no I/O.

`VERIFIED_PHYSICAL` is never written by a station, an ingest adapter, a model or an LLM. It is a
*derived* tier: a stored PHYSICAL_CAPTURE record becomes VERIFIED_PHYSICAL only when

  1. it was station-authenticated at ingest (the BACK-01 envelope proved the sending device, and
     the proven station equals the record's station_id),
  2. its gateway signature still verifies with that station's server-only key,
  3. it carries a calibration_id, and
  4. an authenticated human operator recorded an independent check under one of the documented
     procedures below (docs/engineering/GROUND_TRUTH_VERIFICATION_PROCEDURE.md) and the check
     AGREED with the reading.

A check that disagrees is recorded as DISPUTED and latches: the reading never becomes
VERIFIED_PHYSICAL afterwards, a new reading is needed. Unauthenticated or unsigned readings stay at
their stored tier (PHYSICAL_CAPTURE) with verification status UNVERIFIED and are not candidates.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

PROCEDURE_DOC = 'docs/engineering/GROUND_TRUTH_VERIFICATION_PROCEDURE.md'
COVERAGE_K = 2.0                 # ~95 % agreement band for the instrument cross-check
DEFAULT_MAX_AGE_S = 24 * 3600    # a check long after capture no longer tests the same part state


@dataclass(frozen=True)
class Procedure:
    procedure_id: str
    title: str
    kinds: frozenset[str]
    required_fields: tuple[str, ...]
    doc_section: str


PROCEDURES: dict[str, Procedure] = {p.procedure_id: p for p in (
    Procedure('GT-CAL-01', 'Independent reference-instrument re-measurement',
              frozenset({'CALIPER'}),
              ('reference_value_mm', 'reference_uncertainty_mm', 'reference_instrument_id', 'reference_calibration_id'),
              f'{PROCEDURE_DOC}#gt-cal-01'),
    Procedure('GT-VIS-01', 'Human visual inspection against drawing / reference specimen',
              frozenset({'PHONE_IMAGE', 'PI_IMAGE', 'CAD_IMAGE', 'ASSEMBLY'}),
              ('observed_verdict',),
              f'{PROCEDURE_DOC}#gt-vis-01'),
)}


class VerificationRefused(Exception):
    """Preconditions failed: nothing is recorded. `status` is the HTTP code the API should use."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail); self.status, self.detail = status, detail


def candidate_problems(row: dict, *, auth_station: str | None, signature_ok: bool) -> list[str]:
    """Why a stored record cannot be a VERIFIED_PHYSICAL candidate (empty list = it can)."""
    out = []
    if row.get('origin') != 'PHYSICAL_CAPTURE':
        out.append(f"origin {row.get('origin')!r} is not PHYSICAL_CAPTURE")
    if not auth_station:
        out.append('NOT_STATION_AUTHENTICATED')
    elif auth_station != row.get('station_id'):
        out.append('AUTHENTICATED_STATION_MISMATCH')
    if not signature_ok:
        out.append('GATEWAY_SIGNATURE_INVALID')
    if not row.get('calibration_id'):
        out.append('NO_CALIBRATION_ID')
    return out


def evaluate(row: dict, *, auth_station: str | None, signature_ok: bool, request: dict, verifier_id: str,
             station_ids: set[str], now: float, max_age_s: float = DEFAULT_MAX_AGE_S) -> dict:
    """Return the verification record to append (outcome CONFIRMED or DISPUTED), or raise
    VerificationRefused if the request may not be recorded at all."""
    proc = PROCEDURES.get(request.get('procedure_id', ''))
    if proc is None:
        raise VerificationRefused(422, f"unknown procedure_id; one of {sorted(PROCEDURES)}")
    if not verifier_id or verifier_id in station_ids:
        raise VerificationRefused(403, 'verifier must be an authenticated human operator, not a station identity')
    problems = candidate_problems(row, auth_station=auth_station, signature_ok=signature_ok)
    if problems:
        raise VerificationRefused(409, 'not a VERIFIED_PHYSICAL candidate: ' + ', '.join(problems))
    if row.get('kind') not in proc.kinds:
        raise VerificationRefused(422, f"{proc.procedure_id} does not apply to {row.get('kind')} evidence")
    missing = [f for f in proc.required_fields if request.get(f) in (None, '')]
    if missing:
        raise VerificationRefused(422, f'{proc.procedure_id} requires {missing}')
    if request.get('observed_specimen_id') != row.get('specimen_id'):
        # The verifier attests which physical part they checked; a check of another part proves nothing here.
        raise VerificationRefused(409, 'observed_specimen_id does not match the evidence specimen')
    age = now - float(row.get('observed_at', 0))
    if age > max_age_s:
        raise VerificationRefused(409, f'reading is {int(age)} s old; checks must happen within {int(max_age_s)} s of capture')

    record = {'event_id': row['event_id'], 'specimen_id': row['specimen_id'], 'procedure_id': proc.procedure_id,
              'procedure_doc': proc.doc_section, 'verifier_id': verifier_id, 'verified_at': now,
              'evidence_digest': row.get('digest', ''), 'notes': str(request.get('notes') or '')[:500]}
    if proc.procedure_id == 'GT-CAL-01':
        m, u = row['payload'].get('measurement_mm'), row['payload'].get('uncertainty_mm')
        r, ur = float(request['reference_value_mm']), float(request['reference_uncertainty_mm'])
        if not isinstance(m, (int, float)) or not isinstance(u, (int, float)) or u < 0 or ur < 0:
            raise VerificationRefused(422, 'reading or reference has no usable value/uncertainty')
        band = COVERAGE_K * math.sqrt(u * u + ur * ur)
        diff = abs(m - r)
        record.update(reference_value_mm=r, reference_uncertainty_mm=ur,
                      reference_instrument_id=str(request['reference_instrument_id']),
                      reference_calibration_id=str(request['reference_calibration_id']),
                      measurement_mm=m, uncertainty_mm=u, abs_difference_mm=round(diff, 6),
                      agreement_band_mm=round(band, 6), coverage_k=COVERAGE_K,
                      outcome='CONFIRMED' if diff <= band else 'DISPUTED')
    else:  # GT-VIS-01
        observed = str(request['observed_verdict'])
        record.update(observed_verdict=observed, recorded_verdict=row.get('verdict'),
                      outcome='CONFIRMED' if observed == row.get('verdict') else 'DISPUTED')
    return record


def effective_tier(row: dict, *, auth_station: str | None, signature_ok: bool, verifications: list[dict]) -> dict:
    """Derived view. Never mutates the stored record; its stored origin stays what was ingested."""
    problems = candidate_problems(row, auth_station=auth_station, signature_ok=signature_ok)
    outcomes = [v['outcome'] for v in verifications]
    if problems:
        status = 'UNVERIFIED'
    elif 'DISPUTED' in outcomes:
        status = 'DISPUTED'       # latches; a later CONFIRMED does not override a recorded disagreement
    elif 'CONFIRMED' in outcomes:
        status = 'CONFIRMED'
    else:
        status = 'AWAITING_GROUND_TRUTH'
    return {'event_id': row['event_id'], 'specimen_id': row['specimen_id'], 'kind': row.get('kind'),
            'station_id': row.get('station_id'), 'stored_origin': row.get('origin'),
            'station_authenticated': bool(auth_station) and auth_station == row.get('station_id'),
            'candidate_for_verified_physical': not problems, 'candidate_problems': problems,
            'verification_status': status,
            'effective_origin': 'VERIFIED_PHYSICAL' if status == 'CONFIRMED' else row.get('origin'),
            'verifications': verifications}
