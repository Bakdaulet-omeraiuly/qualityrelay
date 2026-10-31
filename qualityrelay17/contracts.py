"""Typed evidence and decisions; schema boundary, not a calibrated industrial safety system."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Literal
import hashlib, hmac, json

Origin = Literal['SIMULATED','TEST_FIXTURE','PHYSICAL_CAPTURE','VERIFIED_PHYSICAL']
Kind = Literal['PHONE_IMAGE','PI_IMAGE','CAD_IMAGE','CALIPER','ASSEMBLY','ROUTE_ACK','PROCESS']

@dataclass(frozen=True)
class Evidence:
    event_id: str
    specimen_id: str
    station_id: str
    kind: Kind
    origin: Origin
    source_root: str # image digest or instrument event ID; determines shared lineage
    observed_at: float
    verdict: str  # clear/suspect/unusable/verified/pass/fail; never treat text as proof
    payload: dict = field(default_factory=dict)
    model_version: str = 'reference-0'
    calibration_id: str = ''
    signature: str = ''

    def unsigned(self) -> dict:
        d=asdict(self); d.pop('signature'); return d

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.unsigned(),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def sign_evidence(e: Evidence, key: str) -> Evidence:
    return Evidence(**{**e.unsigned(), 'signature': hmac.new(key.encode(), e.digest().encode(), hashlib.sha256).hexdigest()})


def signature_valid(e: Evidence, keys: dict[str,str]) -> bool:
    secret=keys.get(e.station_id)
    return bool(secret and hmac.compare_digest(sign_evidence(e,secret).signature,e.signature))


@dataclass(frozen=True)
class Decision:
    specimen_id: str
    state: Literal['HOLD','PASS_REVIEW','CONFIRMED_REJECT_REVIEW']
    reasons: tuple[str,...]
    evidence_ids: tuple[str,...]
    action_requested: str | None = None
    evidence_coverage: float=0.0
    mode: Literal['SIMULATED','TEST_FIXTURE','PHYSICAL_CAPTURE','VERIFIED_PHYSICAL']='TEST_FIXTURE'

    def to_dict(self): return asdict(self)
