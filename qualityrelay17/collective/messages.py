"""Typed, role-signed messages (research plan section 3.2 / 3.3).

Sender and recipient are established by the signature the bus verifies, never by text inside
the message. A message with a bad signature is not 'from' anyone.
"""
from __future__ import annotations
import hashlib, hmac, json
from dataclasses import dataclass, field, asdict
from ..contracts import Evidence

SCHEMA_VERSION = '17.1'
KINDS = ('FIND_MISSING_EVIDENCE', 'REQUEST_EVIDENCE', 'EVIDENCE_RESPONSE', 'HYPOTHESIS_UPDATE',
         'PROPOSE_INSPECTION', 'DECISION_PROPOSAL')
# Technical outcomes of a request. These are facts about the exchange, never negative measurements.
OUTCOMES = ('GRANTED', 'REJECT_REQUEST', 'TIMEOUT', 'SENSOR_FAILURE', 'STALE_EVIDENCE', 'DUPLICATE_SOURCE', 'BAD_SIGNATURE')

# Evidence kind -> the required_sources family in roles.py that entitles a role to ask for it.
SOURCE_FAMILY = {'PHONE_IMAGE': 'VISION', 'PI_IMAGE': 'VISION', 'CAD_IMAGE': 'CAD', 'CALIPER': 'METROLOGY',
                 'ASSEMBLY': 'METROLOGY', 'PROCESS': 'PROCESS'}

# Payload fields a peer may see in a summary. Raw image bytes/paths etc. never cross roles.
ADMISSIBLE_PAYLOAD = {'measurement_mm', 'uncertainty_mm', 'unit', 'validated', 'threshold_mm'}


@dataclass(frozen=True)
class Message:
    message_id: str
    case_id: str            # specimen_id
    kind: str
    sender_role: str
    recipient_role: str
    sent_at: float
    body: dict = field(default_factory=dict)
    correlation_id: str = ''   # the REQUEST this answers / follows; '' for an originating message
    schema_version: str = SCHEMA_VERSION
    signature: str = ''

    def __post_init__(self):
        if self.kind not in KINDS: raise ValueError(f'unknown message kind {self.kind!r}')
        if self.kind == 'EVIDENCE_RESPONSE' and self.body.get('outcome') not in OUTCOMES:
            raise ValueError('EVIDENCE_RESPONSE needs a technical outcome')

    def unsigned(self) -> dict:
        d = asdict(self); d.pop('signature'); return d

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.unsigned(), sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)


def sign_message(m: Message, role_key: str) -> Message:
    return Message(**{**m.unsigned(), 'signature': hmac.new(role_key.encode(), m.digest().encode(), hashlib.sha256).hexdigest()})


def message_valid(m: Message, role_keys: dict[str, str]) -> bool:
    key = role_keys.get(m.sender_role)
    return bool(key and m.signature and hmac.compare_digest(sign_message(m, key).signature, m.signature))


def admissible_summary(e: Evidence, *, verification_status: str, new_source: bool) -> dict:
    """What a requester is allowed to learn about a peer's evidence: identifiers, provenance,
    verdict, uncertainty -- not the raw observation. (Plan section 3.3 response fields.)"""
    return {'event_id': e.event_id, 'kind': e.kind, 'station_id': e.station_id, 'origin': e.origin,
            'observed_at': e.observed_at, 'source_root': e.source_root,
            'parent_source_roots': list(e.payload.get('parent_source_roots', []) or []),
            'calibration_id': e.calibration_id, 'model_version': e.model_version, 'verdict': e.verdict,
            'uncertainty': e.payload.get('uncertainty_mm'), 'unit': e.payload.get('unit'),
            'payload': {k: v for k, v in e.payload.items() if k in ADMISSIBLE_PAYLOAD},
            'verification_status': verification_status, 'new_source': new_source}
