"""Hidden-truth environment for the B0..B7 comparison (17.1 Gate A: `observe(role)` /
`step(action)`, evaluator truth never reachable from an agent).

A case is one simulated specimen. Its latent truth (surface defect, true clearance, safe) is
kept in `_truth` and read ONLY by `score()`. Agents interact through `capture()` (direct
sensor read by a single agent) or `request()` (typed REQUEST_EVIDENCE to the role that owns
the sensor; RESPONSE_EVIDENCE or TIMEOUT comes back). Every call is charged exactly once into
`inspections` / `peer_requests` and timed into `latency_s` (SCI-01/02/08).

Message and evidence records use the shared integration-contract field names
(QUALITYRELAY_18_1_TEAM_TASKS_EN.md section 4); `signature` is None because nothing here is
a physical device -- the authenticated transport is adilnurgg's AGENT-01/BACK-01.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict, replace
from random import Random

from ..economics import Costs
from ..factory import seeded_scenario
from .belief import MAX_DRAWS

OWNER = {'phone': 'phone_agent', 'pi': 'pi_agent', 'caliper': 'metrology_agent'}
STATION = {'phone': 'phone', 'pi': 'pi', 'caliper': 'caliper'}
# Seconds; ILLUSTRATIVE ASSUMPTIONS taken from digital_twin.TwinTiming (first capture /
# recapture) plus two message-level assumptions. Not measured.
SERVICE_S = {('phone', 0): 5.0, ('phone', 1): 5.0, ('pi', 0): 6.0, ('pi', 1): 5.0, ('caliper', 0): 7.0, ('caliper', 1): 7.0}
MESSAGE_RTT_S = 0.5
TIMEOUT_S = 2.0
DECISION_S = 1.0
_THIRD_STREAM_SALT = 0xC011EC71


@dataclass(frozen=True)
class CollectiveScenario:
    sid: str
    title: str
    process_shift_mm: float = 0.10
    camera_noise: float = 0.04
    network_outage: float = 0.05        # P(Pi edge station unreachable for this part)
    shared_camera_noise: float = 0.0    # common-mode lighting error shared by every camera frame
    caliper_sigma_mm: float = 0.05      # TRUE instrument noise in this scenario
    duplicate_photo_p: float = 0.0      # P(the "Pi capture" is a re-upload of the phone frame)
    budget: int = 6                     # max sensor observations per part, same for every adaptive policy
    costs: Costs = field(default_factory=Costs)

    def generator_kwargs(self):
        return dict(process_shift_mm=self.process_shift_mm, camera_noise=self.camera_noise,
                    network_outage=self.network_outage, shared_camera_noise=self.shared_camera_noise)

    def as_dict(self):
        return asdict(self)


def make_cases(n: int, seed: int, sc: CollectiveScenario):
    """Same seed + scenario -> identical cases for every policy (paired design).
    The first two captures per sensor are the factory.seeded_scenario columns (so the B0 rule
    here sees exactly what conservative_rules sees); the third comes from a separate stream."""
    rows = seeded_scenario(n, seed, **sc.generator_kwargs())
    rng = Random(_THIRD_STREAM_SALT ^ (int(seed) * 0x2545F491))
    cases = []
    for i, r in enumerate(rows):
        flip = r['shared_camera_flip']
        phone = [r['phone_suspect'], r['phone_recapture_suspect'],
                 bool(r['surface_defect'] ^ (rng.random() < sc.camera_noise) ^ flip)]
        pi = [r['pi_suspect'], r['pi_recapture_suspect'],
              bool(r['surface_defect'] ^ (rng.random() < sc.camera_noise) ^ flip)]
        third_caliper = r['true_clearance'] + rng.gauss(0, 0.05)
        if abs(sc.caliper_sigma_mm - 0.05) < 1e-12:
            caliper = [r['measured_clearance'], r['retake_clearance'], third_caliper]
        else:
            caliper = [r['true_clearance'] + rng.gauss(0, sc.caliper_sigma_mm) for _ in range(MAX_DRAWS)]
        sid = r['specimen_id']
        roots = {k: [f'{sid}/{k}/{j}' for j in range(MAX_DRAWS)] for k in ('phone', 'pi', 'caliper')}
        duplicate = rng.random() < sc.duplicate_photo_p
        if duplicate:  # the Pi "frame" is the phone frame re-uploaded: same bits, same root
            pi[0] = phone[0]
            roots['pi'][0] = roots['phone'][0]
        cases.append(dict(
            specimen_id=sid, lot_id=f'lot-{seed}', seed=seed,
            draws={'phone': phone, 'pi': pi, 'caliper': caliper}, roots=roots,
            pi_available=not r['network_down'], duplicate_pi=duplicate,
            _truth=dict(safe=r['safe'], surface_defect=r['surface_defect'], true_clearance=r['true_clearance'])))
    return cases


class CollectiveEnv:
    def __init__(self, case: dict, *, run_id: str = 'sim'):
        self._case = case
        self.run_id = run_id
        self.evidence: list[dict] = []
        self.trace: list[dict] = []
        self.used = {'phone': 0, 'pi': 0, 'caliper': 0}
        self.unreachable: set[str] = set()
        self.inspections = 0
        self.peer_requests = 0
        self.latency_s = 0.0
        self._n_events = 0

    # -- what an agent may see -----------------------------------------------------------
    def observe(self, role: str):
        """Role-scoped view (AGENT-02 shape): the decider sees the evidence delivered to it;
        a specialist sees only the evidence of the sensor it owns."""
        if role == 'quality_agent':
            return list(self.evidence)
        return [e for e in self.evidence if OWNER[e['kind']] == role]

    def available(self, budget: int):
        """kind -> next capture index, for sensors not exhausted, not known-unreachable, within budget."""
        if self.inspections >= budget:
            return {}
        return {k: i for k, i in self.used.items() if i < MAX_DRAWS and k not in self.unreachable}

    def station_up(self, kind: str) -> bool:
        """Station health a directly-wired single agent can see (B0/B1/B6). Not the reading."""
        return kind != 'pi' or self._case['pi_available']

    # -- actions -----------------------------------------------------------------------
    def _event_id(self):
        self._n_events += 1
        return f"{self.run_id}/{self._case['specimen_id']}/e{self._n_events}"

    def _read(self, kind: str) -> dict:
        idx = self.used[kind]
        self.used[kind] += 1
        self.inspections += 1
        self.latency_s += SERVICE_S[(kind, min(idx, 1))]
        root = self._case['roots'][kind][idx]
        own_root = f"{self._case['specimen_id']}/{kind}/{idx}"
        ev = dict(event_id=self._event_id(), specimen_id=self._case['specimen_id'], lot_id=self._case['lot_id'],
                  station_id=STATION[kind], kind=kind, index=idx, value=self._case['draws'][kind][idx],
                  source_tier='SIMULATED', source_root=root,
                  parent_source_roots=[] if root == own_root else [root],
                  calibration_id=None, uncertainty=None, run_id=self.run_id, signature=None, owner_role=OWNER[kind])
        self.evidence.append(ev)
        return ev

    def capture(self, kind: str):
        """Direct read by a single agent wired to every sensor. Caller must check station_up."""
        if not self.station_up(kind):
            raise RuntimeError('capture on a station that is down')
        ev = self._read(kind)
        self.trace.append(dict(type='INSPECT', sender='single_agent', receiver=STATION[kind], kind=kind,
                               index=ev['index'], value=ev['value'], source_root=ev['source_root'],
                               parent_source_roots=ev['parent_source_roots'], event_id=ev['event_id']))
        return ev

    def request(self, kind: str, *, requester: str = 'quality_agent', reason: str = ''):
        """REQUEST_EVIDENCE -> owner. Charged one peer_request whatever happens. Returns the
        evidence, or None on TIMEOUT (which is never turned into a 'clear' reading)."""
        self.peer_requests += 1
        self.latency_s += MESSAGE_RTT_S
        req_id = self._event_id()
        self.trace.append(dict(type='REQUEST_EVIDENCE', request_id=req_id, sender=requester, receiver=OWNER[kind],
                               kind=kind, index=self.used[kind], reason=reason))
        if kind == 'pi' and not self._case['pi_available']:
            self.latency_s += TIMEOUT_S
            self.unreachable.add('pi')
            self.trace.append(dict(type='TIMEOUT', request_id=req_id, sender=OWNER[kind], receiver=requester, kind=kind))
            return None
        ev = self._read(kind)
        self.trace.append(dict(type='RESPONSE_EVIDENCE', request_id=req_id, sender=OWNER[kind], receiver=requester,
                               kind=kind, index=ev['index'], value=ev['value'], source_root=ev['source_root'],
                               parent_source_roots=ev['parent_source_roots'], event_id=ev['event_id']))
        return ev


def score(env: CollectiveEnv, hold: bool) -> dict:
    """EVALUATOR ONLY -- the one place `_truth` is read."""
    safe = env._case['_truth']['safe']
    return dict(outcome='hold' if hold else ('pass' if safe else 'escaped_defect'),
                unsafe_pass=int(not hold and not safe), false_hold=int(hold and safe), truly_safe=safe)
