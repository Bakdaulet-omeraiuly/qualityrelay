"""Client for the tolerance and fit rule check contributed by aneta-claude (SentiLab), ticket 3b5fc17f.

A rule check, not a model and not independent evidence: it applies our own spec to numbers we send.
Its answer is advisory evidence (origin EXTERNAL_SERVICE). safe_mesh still makes every decision, and
anything short of a clean answer (unreachable, timeout, error status, malformed reply) becomes HOLD.
Standard library only, so it adds no dependency.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

URL = 'https://qualityrelay-tolerance-check.vercel.app/api/check'
SPECS = {'tab': {'nominal': 20.0, 'tol': 0.5, 'guard_band': 0.15},
         'slot': {'nominal': 21.0, 'tol': 0.5, 'guard_band': 0.15}}
KEY = {'slot': 'slot_inner_width', 'tab': 'width'}
TO_DISPOSITION = {'pass': 'PASS', 'review': 'HOLD', 'fail': 'REJECT'}

Post = Callable[[str, dict, float], 'tuple[int, object]']


@dataclass(frozen=True)
class ServiceVerdict:
    part_id: str
    disposition: str            # advisory PASS / HOLD / REJECT for this part alone
    verdict: str | None         # the service's raw verdict; None when no clean answer came back
    score: float | None
    clearance_mm: float | None  # only when a mate was sent
    fit: bool | None
    reasons: tuple[str, ...]
    service_version: str | None
    origin: str = 'EXTERNAL_SERVICE'


def build_request(part_id: str, part_type: str, width_mm: float, mate: tuple[str, str, float] | None = None) -> dict:
    if part_type not in KEY:
        raise ValueError(f'part_type must be tab or slot, not {part_type!r}')
    body = {'part_id': part_id, 'part_type': part_type, 'units': 'mm',
            'dims_mm': {KEY[part_type]: round(float(width_mm), 2)}, 'spec': dict(SPECS[part_type])}
    if mate is not None:
        mate_id, mate_type, mate_width = mate
        if mate_type not in KEY or mate_type == part_type:
            raise ValueError('a mate must be the other part type (a tab mates a slot)')
        body['mate'] = {'part_id': mate_id, 'dims_mm': {KEY[mate_type]: round(float(mate_width), 2)}}
    return body


def _post(url: str, body: dict, timeout: float):
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except ValueError:
            return e.code, None


def _hold(part_id: str, reason: str) -> ServiceVerdict:
    return ServiceVerdict(part_id, 'HOLD', None, None, None, None, (reason,), None)


def check(part_id: str, part_type: str, width_mm: float, mate: tuple[str, str, float] | None = None, *,
          url: str = URL, timeout: float = 5.0, post: Post | None = None) -> ServiceVerdict:
    body = build_request(part_id, part_type, width_mm, mate)
    try:
        status, data = (post or _post)(url, body, timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return _hold(part_id, f'service unreachable or unreadable: {exc}')
    if status != 200 or not isinstance(data, dict) or data.get('verdict') not in TO_DISPOSITION:
        detail = data.get('error') if isinstance(data, dict) else data
        return _hold(part_id, f'no clean answer from the service (HTTP {status}): {detail!r}')
    return ServiceVerdict(
        part_id=part_id, disposition=TO_DISPOSITION[data['verdict']], verdict=data['verdict'],
        score=data.get('score'), clearance_mm=data.get('clearance_mm'), fit=data.get('fit'),
        reasons=tuple(str(r) for r in data.get('reasons', [])), service_version=data.get('version'))
