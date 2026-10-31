"""Sorter safety state machine. No hardware IO in this module, ever.

Task board BACK-03 (event binding) and BACK-04 (safety enforcement).

Action lifecycle
    PROPOSED   a recommendation (safe_mesh, an LLM planner, any agent). Moves nothing, has no
               timer, and can only leave this state through approve() by an authenticated human.
    STAGED     human-approved, evidence gate passed. Waits for either a manual move (bin sensor
               ACK) or dispatch to an armed sorter. Expires after stage_ttl_s.
    DISPATCHED handed to the sorter as a short-lived signed command (next_command). Must be
               acknowledged by the independent bin sensor within ack_timeout_s, else FAULTED.
    CONFIRMED  a recorded, station-authenticated ROUTE_ACK in the requested bin, sensed inside
               the action's time window. specimen_identity stays NOT_PROVEN until an operator
               confirms which part is in the bin (confirm_identity) -- an object in a bin is
               not proof it is the right specimen.
    FAULTED    latched: wrong bin (E12), ACK timeout, E-stop during motion, identity mismatch,
               restart during motion. Never auto-recovers; re-stage under a new action_id.
    EXPIRED / ABORTED   stage TTL ran out / E-stop or restart before motion.

Default is HOLD. next_command() answers HOLD unless ALL of: hardware gate enabled (deploy-time
config), armed by an operator (runtime), E-stop not latched, device reports its hardware E-stop
loop healthy and guard closed, nothing else in flight, and a STAGED action exists. A device that
loses power or network simply stops receiving commands; commands carry expires_at so a delayed
one is void. A server restart loses every in-memory action: recover() journals non-terminal ones
as EXPIRED/FAULTED, so nothing resumes moving without a fresh human approval.

Software here is NOT the safety function. Mechanical/electrical interlocks (hard-wired E-stop
cutting actuator power, guard switch, spring-return-to-HOLD mechanism) must exist in hardware;
see docs/engineering/PHYSICAL_TEST_PLAYBOOK.md section 4. This module refuses to dispatch when
the device says they are not healthy; it cannot make them healthy.
"""
from __future__ import annotations
import re, secrets, threading, time
from dataclasses import dataclass, asdict, field
from typing import Any, Callable, Optional

SensorLookup = Callable[[str], Optional[dict]]   # event_id -> stored Evidence dict (+auth_station), or None
EvidenceGate = Callable[['RouteRequest'], list]   # -> list of problems; empty = evidence sufficient
BINS = ('PASS', 'HOLD', 'REJECT')
DECISION_FOR_BIN = {'PASS': {'AUTHORIZED_PASS'}, 'REJECT': {'CONFIRMED_REJECT'}, 'HOLD': {'HOLD', 'AUTHORIZED_PASS', 'CONFIRMED_REJECT'}}
MACHINE_SOURCE = re.compile(r'^(safe_mesh|(llm|agent|ai):[\w.\-]{1,64})$')
IN_FLIGHT = ('STAGED', 'DISPATCHED')
TERMINAL = ('CONFIRMED', 'FAULTED', 'EXPIRED', 'ABORTED')


@dataclass(frozen=True)
class RouteRequest:
    action_id: str
    specimen_id: str
    bin: str
    decision: str
    recommended_by: str = 'human'              # 'human:<operator>' | 'safe_mesh' | 'llm:<provider>' | 'agent:<role>'
    evidence_ids: tuple[str, ...] = ()


@dataclass
class Action:
    request: RouteRequest
    state: str = 'PROPOSED'
    proposed_at: float = 0.0
    approved_by: str | None = None
    approved_at: float | None = None
    stage_deadline: float | None = None
    dispatched_at: float | None = None
    dispatch_station: str | None = None
    command_nonce: str | None = None
    ack_deadline: float | None = None
    actual_bin: str | None = None
    sensor_event_id: str | None = None
    sensor_station: str | None = None
    sensed_at: float | None = None
    acked_at: float | None = None
    specimen_identity: str = 'NOT_PROVEN'
    fault: str | None = None
    history: list = field(default_factory=list)

    def binding(self) -> dict:
        """The BACK-03 tuple, plus who approved it and why it is in this state."""
        r = self.request
        return {'action_id': r.action_id, 'specimen_id': r.specimen_id, 'requested_bin': r.bin, 'decision': r.decision,
                'recommended_by': r.recommended_by, 'evidence_ids': list(r.evidence_ids), 'state': self.state,
                'approved_by': self.approved_by, 'approved_at': self.approved_at, 'dispatch_station': self.dispatch_station,
                'dispatched_at': self.dispatched_at, 'actual_bin': self.actual_bin, 'sensor_event_id': self.sensor_event_id,
                'sensor_station': self.sensor_station, 'sensed_at': self.sensed_at, 'acked_at': self.acked_at,
                'specimen_identity': self.specimen_identity, 'fault': self.fault}


class SorterInterlock:
    def __init__(self, sensor_lookup: SensorLookup | None = None, *, evidence_gate: EvidenceGate | None = None,
                 journal=None, clock: Callable[[], float] = time.time, hardware_enabled: bool = False,
                 stage_ttl_s: float = 600.0, ack_timeout_s: float = 30.0, command_ttl_s: float = 10.0,
                 clock_skew_s: float = 2.0, max_open: int = 500):
        """sensor_lookup: resolves a sensor_event_id to the ledger record (api passes the ledger).
        Without one (offline unit tests) the id is trusted as given; the API always supplies one.
        evidence_gate: PASS/REJECT are refused outright without one. journal: an EvidenceLedger
        (append_route_event / sensor_event_bound / route_events) for audit + restart safety."""
        self.sensor_lookup, self.evidence_gate, self.journal, self.clock = sensor_lookup, evidence_gate, journal, clock
        self.hardware_enabled = hardware_enabled
        self.stage_ttl_s, self.ack_timeout_s, self.command_ttl_s = stage_ttl_s, ack_timeout_s, command_ttl_s
        self.clock_skew_s, self.max_open = clock_skew_s, max_open
        self.actions: dict[str, Action] = {}
        self.used_sensor_events: set[str] = set()
        self.armed = False
        self.armed_by: str | None = None
        self.estop: dict | None = None
        # One lock for every state transition. FastAPI handles bounce edges on parallel threads
        # and sensor_lookup does I/O (GIL released) between the 'already acked?' check and the
        # write, so without this two edges for one arrival can both confirm -- found by
        # tests/test_actuation_sensor_wiring.py::test_concurrent_bounce_edges_confirm_exactly_once.
        self._lock = threading.RLock()
        if journal is not None:
            self.recover()

    # ------------------------------------------------------------------ internals
    def _log(self, a: Action, kind: str, *, sensor_event_id: str | None = None, **extra):
        now = self.clock()
        a.history.append({'at': now, 'event': kind, **extra})
        if self.journal is not None:
            self.journal.append_route_event(a.request.action_id, kind, {**a.binding(), 'at': now, **extra},
                                            sensor_event_id=sensor_event_id)

    def _tick(self):
        """Apply timeouts. Called at the top of every public method, under the lock."""
        now = self.clock()
        for a in self.actions.values():
            if a.state == 'STAGED' and a.stage_deadline is not None and now > a.stage_deadline:
                a.state = 'EXPIRED'; a.fault = 'STAGE_TTL'; self._log(a, 'EXPIRED', reason='STAGE_TTL')
            elif a.state == 'DISPATCHED' and a.ack_deadline is not None and now > a.ack_deadline:
                # The command went out and no independent ACK came back: part position unknown.
                a.state = 'FAULTED'; a.fault = 'ACK_TIMEOUT'; self._log(a, 'FAULTED', reason='ACK_TIMEOUT')
                self.armed = False

    def _get(self, action_id: str) -> Action:
        a = self.actions.get(action_id)
        if a is None:
            raise ValueError('unknown action')
        return a

    @staticmethod
    def _validate(r: RouteRequest):
        if r.bin not in BINS:
            raise ValueError('bin invalid')
        if r.decision not in DECISION_FOR_BIN[r.bin]:
            if r.bin == 'PASS': raise PermissionError('PASS needs independent release authorization')
            if r.bin == 'REJECT': raise PermissionError('REJECT needs confirmed nonconformance')
            raise PermissionError('unknown decision')

    # ------------------------------------------------------------------ recommend / approve
    def propose(self, request: RouteRequest) -> dict:
        """Record a recommendation. Anything may propose; nothing moves and nothing is staged."""
        with self._lock:
            self._tick()
            self._validate(request)
            existing = self.actions.get(request.action_id)
            if existing is not None:
                if existing.request == request:
                    return {**self._status(request.action_id), 'idempotent_replay': True, 'hardware_command_emitted': False}
                raise ValueError('duplicate action id')
            if sum(a.state == 'PROPOSED' for a in self.actions.values()) >= self.max_open:
                raise ValueError('too many open proposals')
            a = Action(request=request, proposed_at=self.clock())
            self.actions[request.action_id] = a
            self._log(a, 'PROPOSED')
            return {'status': 'PROPOSED', 'action_id': request.action_id, 'hardware_command_emitted': False,
                    'next': 'an authenticated operator must approve before anything can move'}

    def approve(self, action_id: str, operator_id: str) -> dict:
        """Human approval: PROPOSED -> STAGED. operator_id must come from operator authentication
        (api.py), never from a request body. Machine identities can never approve."""
        with self._lock:
            self._tick()
            if not operator_id or MACHINE_SOURCE.match(operator_id):
                raise PermissionError('operator approval required')
            a = self._get(action_id)
            if a.state == 'STAGED' and a.approved_by == operator_id:
                return {**self._status(action_id), 'status': 'STAGED_ONLY', 'idempotent_replay': True, 'hardware_command_emitted': False}
            if a.state != 'PROPOSED':
                raise ValueError(f'action is {a.state}, not PROPOSED')
            if self.estop:
                raise PermissionError('E-stop latched; reset before approving')
            r = a.request
            if r.bin in ('PASS', 'REJECT') and self.evidence_gate is None:
                raise PermissionError(f'{r.bin} needs an evidence gate; none configured')
            if self.evidence_gate is not None:
                problems = self.evidence_gate(r)
                if problems:
                    raise PermissionError('evidence gate: ' + '; '.join(problems))
            now = self.clock()
            a.state, a.approved_by, a.approved_at, a.stage_deadline = 'STAGED', operator_id, now, now + self.stage_ttl_s
            self._log(a, 'STAGED', operator_id=operator_id)
            return {'status': 'STAGED_ONLY', 'action_id': action_id, 'hardware_command_emitted': False,
                    'stage_deadline': a.stage_deadline}

    def stage(self, request: RouteRequest, operator_id: str) -> dict:
        """One-step human route: propose + approve by the same authenticated operator."""
        with self._lock:
            if request.recommended_by == 'human':
                request = RouteRequest(**{**asdict(request), 'recommended_by': f'human:{operator_id}',
                                          'evidence_ids': tuple(request.evidence_ids)})
            existing = self.actions.get(request.action_id)
            if existing is not None and existing.request == request and existing.state == 'STAGED' and existing.approved_by == operator_id:
                self._tick()
                return {**self._status(request.action_id), 'status': 'STAGED_ONLY', 'idempotent_replay': True, 'hardware_command_emitted': False}
            if existing is not None:
                raise ValueError('duplicate action id')
            self._validate(request)
            if not operator_id:
                raise PermissionError('operator approval required')
            self.propose(request)
            try:
                return self.approve(request.action_id, operator_id)
            except Exception:
                a = self.actions.pop(request.action_id)  # refused approval leaves no half-staged action
                if self.journal is not None:
                    self.journal.append_route_event(request.action_id, 'REFUSED', {**a.binding(), 'at': self.clock()})
                raise

    # ------------------------------------------------------------------ safety controls
    def emergency_stop(self, source: str, reason: str = '') -> dict:
        """Latch. Disarm, abort everything not yet moving, fault anything in motion."""
        with self._lock:
            now = self.clock()
            if self.estop is None:
                self.estop = {'source': source, 'reason': reason[:200], 'at': now}
            self.armed, self.armed_by = False, None
            aborted, faulted = [], []
            for a in self.actions.values():
                if a.state in ('PROPOSED', 'STAGED'):
                    a.state, a.fault = 'ABORTED', 'ESTOP'; self._log(a, 'ABORTED', reason='ESTOP'); aborted.append(a.request.action_id)
                elif a.state == 'DISPATCHED':
                    a.state, a.fault = 'FAULTED', 'ESTOP_DURING_MOTION'; self._log(a, 'FAULTED', reason='ESTOP_DURING_MOTION'); faulted.append(a.request.action_id)
            return {'estop': self.estop, 'aborted': aborted, 'faulted': faulted, 'armed': False, 'hardware_command_emitted': False}

    def reset_estop(self, operator_id: str) -> dict:
        with self._lock:
            if not operator_id:
                raise PermissionError('operator required')
            was, self.estop = self.estop, None
            return {'estop': None, 'cleared': was, 'cleared_by': operator_id, 'armed': False,
                    'note': 'reset does not re-arm; arm separately after checking the cell'}

    def arm(self, operator_id: str) -> dict:
        with self._lock:
            self._tick()
            if not operator_id:
                raise PermissionError('operator required')
            if not self.hardware_enabled:
                raise PermissionError('hardware gate disabled (ACTUATION_HARDWARE_ENABLED is not set)')
            if self.estop:
                raise PermissionError('E-stop latched; reset first')
            self.armed, self.armed_by = True, operator_id
            return self.safety()

    def disarm(self, source: str) -> dict:
        with self._lock:
            self.armed, self.armed_by = False, None
            return {**self.safety(), 'disarmed_by': source}

    def safety(self) -> dict:
        with self._lock:
            self._tick()
            return {'hardware_enabled': self.hardware_enabled, 'armed': self.armed, 'armed_by': self.armed_by,
                    'estop': self.estop, 'default_position': 'HOLD',
                    'in_flight': [a.request.action_id for a in self.actions.values() if a.state in IN_FLIGHT],
                    'stage_ttl_s': self.stage_ttl_s, 'ack_timeout_s': self.ack_timeout_s, 'command_ttl_s': self.command_ttl_s}

    # ------------------------------------------------------------------ dispatch (pull model)
    def next_command(self, station_id: str, device: dict) -> dict:
        """Called by the sorter device. Returns at most one command; HOLD is the answer to
        everything else. The caller (api.py) signs the returned command for the device."""
        with self._lock:
            self._tick()
            hold = lambda reason, **kw: {'command': 'HOLD', 'reason': reason, 'hardware_command_emitted': False, **kw}
            if device.get('estop_loop_ok') is not True:
                self.emergency_stop(f'device:{station_id}', 'hardware E-stop loop open or not reported')
                return hold('HARDWARE_ESTOP')
            if self.estop:
                return hold('ESTOP_LATCHED')
            if device.get('guard_closed') is not True:
                return hold('INTERLOCK_OPEN')
            if not self.hardware_enabled:
                return hold('HARDWARE_DISABLED')
            if not self.armed:
                return hold('NOT_ARMED')
            moving = [a for a in self.actions.values() if a.state == 'DISPATCHED']
            if moving:  # one action in motion at a time, so a bin event has exactly one candidate
                return hold('AWAITING_ACK', action_id=moving[0].request.action_id)
            staged = sorted((a for a in self.actions.values() if a.state == 'STAGED'), key=lambda a: a.approved_at or 0)
            if not staged:
                return hold('NOTHING_STAGED')
            a, now = staged[0], self.clock()
            a.state, a.dispatched_at, a.dispatch_station = 'DISPATCHED', now, station_id
            a.command_nonce, a.ack_deadline = secrets.token_hex(16), now + self.ack_timeout_s
            self._log(a, 'DISPATCHED', station=station_id, command_nonce=a.command_nonce)
            return {'command': 'ROUTE', 'action_id': a.request.action_id, 'specimen_id': a.request.specimen_id,
                    'bin': a.request.bin, 'command_nonce': a.command_nonce, 'issued_at': int(now),
                    'expires_at': int(now + self.command_ttl_s), 'hardware_command_emitted': True}

    # ------------------------------------------------------------------ acknowledgment (BACK-03)
    def in_flight_for_specimen(self, specimen_id: str) -> list[RouteRequest]:
        with self._lock:
            self._tick()
            return [a.request for a in sorted(self.actions.values(), key=lambda a: a.approved_at or 0)
                    if a.state in IN_FLIGHT and a.request.specimen_id == specimen_id]

    pending_for_specimen = in_flight_for_specimen  # older name, same meaning

    def request_for(self, action_id: str) -> RouteRequest | None:
        with self._lock:
            a = self.actions.get(action_id)
            return a.request if a else None

    def _verify_sensor_event(self, a: Action, actual_bin: str, sensor_event_id: str) -> dict:
        if self.sensor_lookup is None:
            return {}
        ev = self.sensor_lookup(sensor_event_id)
        if ev is None: raise ValueError('sensor event not recorded in ledger')
        if ev.get('kind') != 'ROUTE_ACK': raise ValueError('sensor event is not a ROUTE_ACK')
        if not ev.get('auth_station') or ev.get('auth_station') != ev.get('station_id'):
            raise ValueError('sensor event was not station-authenticated')
        if ev.get('specimen_id') != a.request.specimen_id: raise ValueError('sensor event belongs to a different specimen')
        if ev.get('payload', {}).get('bin') != actual_bin: raise ValueError('sensor event bin does not match reported bin')
        return ev

    def acknowledge(self, action_id: str, actual_bin: str, sensor_event_id: str, *, sensed_at: float | None = None) -> dict:
        with self._lock:
            return self._acknowledge(action_id, actual_bin, sensor_event_id, sensed_at)

    def _acknowledge(self, action_id, actual_bin, sensor_event_id, sensed_at):
        self._tick()
        a = self._get(action_id)
        if a.state == 'CONFIRMED':
            return {'status': 'DUPLICATE_ACK_IGNORED', 'hardware_command_emitted': False}
        if a.state == 'FAULTED': raise ValueError('action faulted after route mismatch; operator must re-stage' if a.fault == 'ROUTE_MISMATCH' else f'action faulted ({a.fault}); operator must re-stage')
        if a.state in ('EXPIRED', 'ABORTED'): raise ValueError(f'action {a.state.lower()} ({a.fault}); operator must re-stage')
        if a.state == 'PROPOSED': raise ValueError('action not approved; nothing was staged')
        if not sensor_event_id: raise ValueError('physical sensor acknowledgment needed')
        if sensor_event_id in self.used_sensor_events or (self.journal is not None and self.journal.sensor_event_bound(sensor_event_id)):
            raise ValueError('sensor event already consumed by another action')  # E13
        ev = self._verify_sensor_event(a, actual_bin, sensor_event_id)
        # Time binding: an object sensed before this action was approved/dispatched (e.g. a part
        # already sitting in the bin) cannot acknowledge it, nor can one sensed after its deadline.
        if sensed_at is not None:
            start = a.dispatched_at if a.state == 'DISPATCHED' else a.approved_at
            end = a.ack_deadline if a.state == 'DISPATCHED' else a.stage_deadline
            if sensed_at < start - self.clock_skew_s: raise ValueError('sensor event predates the action window')
            if end is not None and sensed_at > end + self.clock_skew_s: raise ValueError('sensor event is after the action deadline')
        a.actual_bin, a.sensor_event_id, a.sensed_at, a.acked_at = actual_bin, sensor_event_id, sensed_at, self.clock()
        a.sensor_station = ev.get('station_id')
        self.used_sensor_events.add(sensor_event_id)
        if actual_bin != a.request.bin:  # E12: discrepancy is latched, never counted, never auto-recovered
            a.state, a.fault = 'FAULTED', 'ROUTE_MISMATCH'
            self._log(a, 'FAULTED', sensor_event_id=sensor_event_id, reason='ROUTE_MISMATCH')
            raise ValueError('route mismatch')
        a.state = 'CONFIRMED'
        self._log(a, 'CONFIRMED', sensor_event_id=sensor_event_id)
        return {'status': 'PHYSICAL_ROUTE_CONFIRMED', 'specimen_identity': a.specimen_identity, 'hardware_command_emitted': False}

    def confirm_identity(self, action_id: str, operator_id: str, observed_specimen_id: str) -> dict:
        """The bin sensor proves *an object* arrived. An operator reading the part's label/QR in
        the bin proves *which* object. A mismatch latches FAULTED."""
        with self._lock:
            if not operator_id:
                raise PermissionError('operator required')
            a = self._get(action_id)
            if a.state != 'CONFIRMED':
                raise ValueError(f'action is {a.state}; identity is checked after a confirmed route')
            if observed_specimen_id == a.request.specimen_id:
                a.specimen_identity = 'OPERATOR_CONFIRMED'
                self._log(a, 'IDENTITY_CONFIRMED', operator_id=operator_id)
            else:
                a.specimen_identity, a.state, a.fault = 'MISMATCH', 'FAULTED', 'IDENTITY_MISMATCH'
                self._log(a, 'FAULTED', operator_id=operator_id, reason='IDENTITY_MISMATCH', observed_specimen_id=observed_specimen_id)
            return self._status(action_id)

    # ------------------------------------------------------------------ status / restart
    def status(self, action_id: str) -> dict:
        with self._lock:
            self._tick()
            return self._status(action_id)

    def _status(self, action_id: str) -> dict:
        a = self.actions.get(action_id)
        if a is None:
            return {'action_id': action_id, 'state': 'UNKNOWN'}
        out: dict[str, Any] = {'action_id': action_id, 'state': a.state, 'bin': a.request.bin}
        if a.state == 'CONFIRMED':
            out.update(bin=a.actual_bin, sensor_event_id=a.sensor_event_id, specimen_identity=a.specimen_identity)
        if a.state == 'FAULTED':
            out.update(expected_bin=a.request.bin, actual_bin=a.actual_bin, sensor_event_id=a.sensor_event_id, fault=a.fault)
            out.pop('bin')
        if a.state in ('EXPIRED', 'ABORTED'):
            out['fault'] = a.fault
        out['binding'] = a.binding()
        return out

    def recover(self) -> dict:
        """After a restart: every action the journal left non-terminal is closed out safely
        (STAGED -> EXPIRED, DISPATCHED -> FAULTED); terminal ones are reloaded read-only so their
        action_ids and sensor events cannot be reused."""
        last: dict[str, dict] = {}
        for ev in self.journal.route_events():
            last[ev['action_id']] = ev
        closed = []
        for action_id, ev in last.items():
            req = RouteRequest(action_id=action_id, specimen_id=ev['specimen_id'], bin=ev['requested_bin'],
                               decision=ev['decision'], recommended_by=ev.get('recommended_by', 'human'),
                               evidence_ids=tuple(ev.get('evidence_ids') or ()))
            a = Action(request=req, state=ev['kind'] if ev['kind'] in TERMINAL else 'PROPOSED')
            for k in ('approved_by', 'approved_at', 'dispatched_at', 'dispatch_station', 'actual_bin', 'sensor_event_id',
                      'sensor_station', 'sensed_at', 'acked_at', 'specimen_identity', 'fault'):
                if ev.get(k) is not None: setattr(a, k, ev[k])
            if ev['kind'] == 'IDENTITY_CONFIRMED':
                a.state = 'CONFIRMED'
            elif ev['kind'] == 'REFUSED':
                continue
            elif ev['kind'] == 'STAGED' or ev['kind'] == 'PROPOSED':
                a.state, a.fault = 'EXPIRED', 'SERVER_RESTART'; self._log(a, 'EXPIRED', reason='SERVER_RESTART'); closed.append(action_id)
            elif ev['kind'] == 'DISPATCHED':
                a.state, a.fault = 'FAULTED', 'SERVER_RESTART_DURING_MOTION'; self._log(a, 'FAULTED', reason='SERVER_RESTART_DURING_MOTION'); closed.append(action_id)
            self.actions[action_id] = a
            if a.sensor_event_id: self.used_sensor_events.add(a.sensor_event_id)
        return {'closed_on_restart': closed}
