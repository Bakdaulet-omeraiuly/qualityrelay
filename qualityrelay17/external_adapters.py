"""Provider-neutral adapter registry (REL-03). Statuses come from THIRD_PARTY_MANIFEST.json, where each
one is backed by evidence that `scripts/check_dependencies.py check` verifies in CI:

  WORKING         ran on its real backend outside unit tests; a committed run artifact records where
  TESTED          wired, and CI tests exercise it with offline stand-ins; never run against the live thing
  NOT_CONFIGURED  not wired, not installed, or no credentials/hardware; nothing is claimed

`scope` says exactly what a status covers (e.g. Warp is WORKING on the CPU backend only).
Nothing here calls a provider; a status is a record, not a live probe."""
from __future__ import annotations
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'THIRD_PARTY_MANIFEST.json'
STATUSES = ('WORKING', 'TESTED', 'NOT_CONFIGURED')
Status = Literal['WORKING', 'TESTED', 'NOT_CONFIGURED']


@dataclass(frozen=True)
class ExternalResult:
    provider: str
    capability: str
    state: Status
    scope: str
    origin: Literal['SIMULATED', 'TEST_FIXTURE', 'PHYSICAL_CAPTURE', 'VERIFIED_PHYSICAL', 'EXTERNAL_SERVICE', 'NONE']
    evidence: dict
    warning: str


class ExternalAdapter:
    def __init__(self, entry: dict):
        self.entry = entry
        self.provider, self.capability = entry['provider'], entry['capability']

    def health(self) -> ExternalResult:
        e = self.entry
        warning = {'WORKING': 'Ran outside unit tests only within the stated scope; see evidence.artifacts.',
                   'TESTED': 'Exercised by CI tests with offline stand-ins; never run against the live service/hardware.',
                   'NOT_CONFIGURED': 'No live integration; cannot claim real provider inference or execution.'}[e['status']]
        return ExternalResult(e['provider'], e['capability'], e['status'], e['scope'], e['origin'], e['evidence'], warning)


def load_manifest(root: Path = ROOT) -> dict:
    return json.loads((Path(root) / MANIFEST).read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def adapters() -> dict[str, ExternalAdapter]:
    return {a['id']: ExternalAdapter(a) for a in load_manifest()['adapters']}


def summary() -> dict:
    out = {s: sorted(k for k, a in adapters().items() if a.entry['status'] == s) for s in STATUSES}
    return {'counts': {s: len(v) for s, v in out.items()}, 'by_status': out}


NVIDIA_ADAPTERS = {k.split('.', 1)[1]: a for k, a in adapters().items() if k.startswith('nvidia.')}
