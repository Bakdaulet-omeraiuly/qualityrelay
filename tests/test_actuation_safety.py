"""BACK-03 sorter event binding and BACK-04 safety enforcement on the no-IO interlock."""
import ast, pathlib
import pytest
from qualityrelay17.actuation import SorterInterlock, RouteRequest
from qualityrelay17.hardware_ingest import bin_ack_evidence
from qualityrelay17.ledger import EvidenceLedger

KEY = 'sorter-station-key-' + 'y' * 32
OK_DEVICE = {'estop_loop_ok': True, 'guard_closed': True}


class Clock:
    def __init__(self, t=1_000_000.0): self.t = t
    def __call__(self): return self.t


def req(**kw):
    return RouteRequest(**{'action_id': 'a1', 'specimen_id': 'p1', 'bin': 'PASS', 'decision': 'AUTHORIZED_PASS', **kw})


def ack(led, event_id='ack-1', specimen='p1', bin_name='PASS', authenticated=True):
    e = bin_ack_evidence(event_id=event_id, specimen_id=specimen, station_id='sorter', bin_name=bin_name,
                         photoresistor_blocked=True, key=KEY)
    led.append(e, authenticated_station='sorter' if authenticated else None)
    return e.event_id


@pytest.fixture
def cell():
    led, clk = EvidenceLedger(), Clock()
    s = SorterInterlock(sensor_lookup=led.get_event, evidence_gate=lambda r: [], journal=led, clock=clk,
                        hardware_enabled=True, stage_ttl_s=600, ack_timeout_s=30, command_ttl_s=10)
    return led, clk, s


# ---------------------------------------------------------------- BACK-04: AI never drives the sorter
def test_llm_pass_recommendation_is_only_a_proposal(cell):
    led, clk, s = cell
    s.arm('alice')
    out = s.propose(req(recommended_by='llm:openai'))
    assert out['status'] == 'PROPOSED' and out['hardware_command_emitted'] is False
    assert s.next_command('sorter', OK_DEVICE) == {'command': 'HOLD', 'reason': 'NOTHING_STAGED', 'hardware_command_emitted': False}
    with pytest.raises(PermissionError):
        s.approve('a1', 'llm:openai')  # a machine identity can never approve
    with pytest.raises(PermissionError):
        s.approve('a1', 'agent:quality_inspector')
    assert s.approve('a1', 'alice')['status'] == 'STAGED_ONLY'
    cmd = s.next_command('sorter', OK_DEVICE)
    assert cmd['command'] == 'ROUTE' and cmd['action_id'] == 'a1'
    assert s.status('a1')['binding']['recommended_by'] == 'llm:openai' and s.status('a1')['binding']['approved_by'] == 'alice'


def test_evidence_gate_vetoes_human_approval_too(cell):
    led, clk, s = cell
    s.evidence_gate = lambda r: ['no cited VERIFIED_PHYSICAL']
    s.propose(req(recommended_by='safe_mesh'))
    with pytest.raises(PermissionError, match='evidence gate'):
        s.approve('a1', 'alice')
    assert s.status('a1')['state'] == 'PROPOSED'


def test_ack_cannot_confirm_an_unapproved_proposal(cell):
    led, clk, s = cell
    s.propose(req(recommended_by='llm:openai'))
    with pytest.raises(ValueError, match='not approved'):
        s.acknowledge('a1', 'PASS', ack(led))


# ---------------------------------------------------------------- BACK-04: default HOLD, gates, E-stop
def test_default_is_hold_and_hardware_gate_blocks_arming():
    s = SorterInterlock(evidence_gate=lambda r: [])  # hardware_enabled defaults to False
    s.stage(req(), 'alice')
    assert s.next_command('sorter', OK_DEVICE)['reason'] == 'HARDWARE_DISABLED'
    with pytest.raises(PermissionError, match='hardware gate'):
        s.arm('alice')
    assert s.safety()['default_position'] == 'HOLD'


def test_not_armed_and_open_guard_both_hold(cell):
    led, clk, s = cell
    s.stage(req(), 'alice')
    assert s.next_command('sorter', OK_DEVICE)['reason'] == 'NOT_ARMED'
    s.arm('alice')
    assert s.next_command('sorter', {'estop_loop_ok': True, 'guard_closed': False})['reason'] == 'INTERLOCK_OPEN'
    assert s.next_command('sorter', {'estop_loop_ok': True})['reason'] == 'INTERLOCK_OPEN'  # not reported = open
    assert s.status('a1')['state'] == 'STAGED'


def test_hardware_estop_loop_open_latches_software_estop(cell):
    led, clk, s = cell
    s.stage(req(), 'alice'); s.arm('alice')
    assert s.next_command('sorter', {'estop_loop_ok': False, 'guard_closed': True})['reason'] == 'HARDWARE_ESTOP'
    assert s.status('a1')['state'] == 'ABORTED' and s.safety()['armed'] is False
    assert s.next_command('sorter', OK_DEVICE)['reason'] == 'ESTOP_LATCHED'  # loop closed again: still latched


def test_estop_aborts_staged_faults_dispatched_and_reset_does_not_rearm(cell):
    led, clk, s = cell
    s.stage(req(), 'alice'); s.stage(req(action_id='a2', specimen_id='p2'), 'alice'); s.arm('alice')
    assert s.next_command('sorter', OK_DEVICE)['action_id'] == 'a1'
    out = s.emergency_stop('unauthenticated', 'hand in cell')
    assert out['faulted'] == ['a1'] and out['aborted'] == ['a2']
    assert s.status('a1')['fault'] == 'ESTOP_DURING_MOTION'
    with pytest.raises(PermissionError, match='E-stop'):
        s.stage(req(action_id='a3'), 'alice')
    with pytest.raises(PermissionError, match='E-stop'):
        s.arm('alice')
    s.reset_estop('alice')
    assert s.safety()['armed'] is False and s.next_command('sorter', OK_DEVICE)['reason'] == 'NOT_ARMED'


def test_one_action_in_motion_at_a_time(cell):
    led, clk, s = cell
    s.stage(req(), 'alice'); s.stage(req(action_id='a2', specimen_id='p2'), 'alice'); s.arm('alice')
    first = s.next_command('sorter', OK_DEVICE)
    assert first['command'] == 'ROUTE' and first['expires_at'] == int(clk.t + 10) and len(first['command_nonce']) == 32
    assert s.next_command('sorter', OK_DEVICE) == {'command': 'HOLD', 'reason': 'AWAITING_ACK', 'action_id': 'a1',
                                                     'hardware_command_emitted': False}
    s.acknowledge('a1', 'PASS', ack(led), sensed_at=clk.t + 1)
    assert s.next_command('sorter', OK_DEVICE)['action_id'] == 'a2'


# ---------------------------------------------------------------- BACK-04: timeouts
def test_stage_ttl_expires_and_requires_reapproval(cell):
    led, clk, s = cell
    s.stage(req(), 'alice')
    clk.t += 601
    assert s.status('a1')['state'] == 'EXPIRED' and s.status('a1')['fault'] == 'STAGE_TTL'
    with pytest.raises(ValueError, match='expired'):
        s.acknowledge('a1', 'PASS', ack(led))


def test_ack_timeout_after_dispatch_faults_and_disarms(cell):
    led, clk, s = cell
    s.stage(req(), 'alice'); s.arm('alice'); s.next_command('sorter', OK_DEVICE)
    clk.t += 31
    assert s.status('a1')['fault'] == 'ACK_TIMEOUT' and s.safety()['armed'] is False
    with pytest.raises(ValueError, match='ACK_TIMEOUT'):
        s.acknowledge('a1', 'PASS', ack(led), sensed_at=clk.t)


# ---------------------------------------------------------------- BACK-03: binding
def test_confirmed_route_records_the_full_binding_in_the_journal(cell):
    led, clk, s = cell
    s.stage(req(evidence_ids=('cal-1',)), 'alice'); s.arm('alice'); s.next_command('sorter', OK_DEVICE)
    s.acknowledge('a1', 'PASS', ack(led), sensed_at=clk.t + 2)
    events = led.route_events('a1')
    assert [e['kind'] for e in events] == ['PROPOSED', 'STAGED', 'DISPATCHED', 'CONFIRMED']
    b = events[-1]
    assert (b['action_id'], b['specimen_id'], b['dispatch_station'], b['sensor_station'], b['requested_bin'], b['actual_bin'],
            b['sensor_event_id'], b['sensed_at']) == ('a1', 'p1', 'sorter', 'sorter', 'PASS', 'PASS', 'ack-1', clk.t + 2)
    assert b['evidence_ids'] == ['cal-1'] and b['specimen_identity'] == 'NOT_PROVEN'


def test_sensor_event_before_the_action_window_cannot_confirm(cell):
    led, clk, s = cell
    s.stage(req(), 'alice')  # approved at t; a part already in the bin was sensed at t-10
    with pytest.raises(ValueError, match='predates'):
        s.acknowledge('a1', 'PASS', ack(led), sensed_at=clk.t - 10)
    assert s.status('a1')['state'] == 'STAGED'


def test_sensor_event_after_deadline_cannot_confirm(cell):
    led, clk, s = cell
    s.stage(req(), 'alice'); s.arm('alice'); s.next_command('sorter', OK_DEVICE)
    with pytest.raises(ValueError, match='after the action deadline'):
        s.acknowledge('a1', 'PASS', ack(led), sensed_at=clk.t + 60)


def test_unauthenticated_route_ack_cannot_confirm(cell):
    led, clk, s = cell
    s.stage(req(), 'alice')
    with pytest.raises(ValueError, match='station-authenticated'):
        s.acknowledge('a1', 'PASS', ack(led, authenticated=False))


def test_object_in_bin_is_not_identity_until_operator_confirms(cell):
    led, clk, s = cell
    s.stage(req(), 'alice')
    assert s.acknowledge('a1', 'PASS', ack(led))['specimen_identity'] == 'NOT_PROVEN'
    assert s.confirm_identity('a1', 'bob', 'p1')['specimen_identity'] == 'OPERATOR_CONFIRMED'
    s.stage(req(action_id='a2', specimen_id='p2'), 'alice')
    s.acknowledge('a2', 'PASS', ack(led, event_id='ack-2', specimen='p2'))
    st = s.confirm_identity('a2', 'bob', 'p7')  # operator finds a different part in the bin
    assert st['state'] == 'FAULTED' and st['fault'] == 'IDENTITY_MISMATCH'


def test_stage_is_idempotent_for_identical_retry_only(cell):
    led, clk, s = cell
    s.stage(req(), 'alice')
    assert s.stage(req(), 'alice')['idempotent_replay'] is True
    with pytest.raises(ValueError, match='duplicate'):
        s.stage(req(bin='HOLD', decision='HOLD'), 'alice')
    with pytest.raises(ValueError, match='duplicate'):
        s.stage(req(), 'bob')  # someone else re-approving the same id is not a retry


# ---------------------------------------------------------------- BACK-04: restart / power loss
def test_server_restart_fails_safe_and_keeps_sensor_events_consumed(tmp_path):
    path = str(tmp_path / 'ledger.sqlite')
    led, clk = EvidenceLedger(path), Clock()
    mk = lambda: SorterInterlock(sensor_lookup=led.get_event, evidence_gate=lambda r: [], journal=led, clock=clk, hardware_enabled=True)
    s = mk()
    s.stage(req(action_id='done', specimen_id='p0'), 'alice'); s.acknowledge('done', 'PASS', ack(led, 'ack-0', 'p0'))
    s.stage(req(action_id='moving'), 'alice'); s.stage(req(action_id='waiting', specimen_id='p2'), 'alice')
    s.arm('alice'); assert s.next_command('sorter', OK_DEVICE)['action_id'] == 'moving'

    led2 = EvidenceLedger(path)  # power cycle: new process, same file
    s2 = SorterInterlock(sensor_lookup=led2.get_event, evidence_gate=lambda r: [], journal=led2, clock=clk, hardware_enabled=True)
    assert s2.status('moving')['fault'] == 'SERVER_RESTART_DURING_MOTION'
    assert s2.status('waiting')['state'] == 'EXPIRED'
    assert s2.status('done')['state'] == 'CONFIRMED'
    assert s2.safety()['armed'] is False and s2.next_command('sorter', OK_DEVICE)['reason'] == 'NOT_ARMED'
    with pytest.raises(ValueError, match='duplicate'):
        s2.stage(req(action_id='done', specimen_id='p0'), 'alice')
    s2.stage(req(action_id='new', specimen_id='p0'), 'alice')
    with pytest.raises(ValueError, match='already consumed'):
        s2.acknowledge('new', 'PASS', 'ack-0')  # the pre-restart sensor event stays bound to 'done'


# ---------------------------------------------------------------- structural: no AI path to actuation
def test_llm_and_agent_modules_cannot_reach_the_interlock():
    root = pathlib.Path(__file__).resolve().parent.parent / 'qualityrelay17'
    files = [*root.glob('collective/*.py'), root / 'nebius.py', root / 'llm_entitlement.py', root / 'agent_tools.py', root / 'roles.py',
             *root.glob('experiments/*.py')]
    for f in files:
        tree = ast.parse(f.read_text(encoding='utf-8'))
        names = {n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
                {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any('actuation' in m or m.endswith('api') for m in names), f'{f.name} imports {names}'
        assert 'SORTER' not in f.read_text(encoding='utf-8'), f.name
