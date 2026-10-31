"""Interlock <- ledger wiring: a sensor_event_id must be a recorded ROUTE_ACK (task item 3)."""
import pytest
from qualityrelay17.actuation import SorterInterlock, RouteRequest
from qualityrelay17.ledger import EvidenceLedger
from qualityrelay17.hardware_ingest import bin_ack_evidence

KEY = 'test-only-sorter-key-' + 'z' * 32


def req(**kw):
    return RouteRequest(**{'action_id': 'a1', 'specimen_id': 'p1', 'bin': 'HOLD', 'decision': 'HOLD', **kw})


def ack(ledger, event_id='ack-1', specimen='p1', bin_name='HOLD'):
    e = bin_ack_evidence(event_id=event_id, specimen_id=specimen, station_id='sorter',
                         bin_name=bin_name, photoresistor_blocked=True, key=KEY)
    ledger.append(e, authenticated_station='sorter')
    return e.event_id


@pytest.fixture
def wired():
    led = EvidenceLedger()
    return led, SorterInterlock(sensor_lookup=led.get_event, evidence_gate=lambda r: [])


def test_recorded_sensor_event_confirms_route(wired):
    led, s = wired; s.stage(req(), 'human')
    assert s.acknowledge('a1', 'HOLD', ack(led))['status'] == 'PHYSICAL_ROUTE_CONFIRMED'
    assert s.status('a1')['state'] == 'CONFIRMED'


def test_unrecorded_sensor_event_is_refused(wired):
    led, s = wired; s.stage(req(), 'human')
    with pytest.raises(ValueError, match='not recorded'):
        s.acknowledge('a1', 'HOLD', 'made-up-by-caller')
    assert s.status('a1')['state'] == 'STAGED'


def test_sensor_event_for_other_specimen_is_refused(wired):
    led, s = wired; s.stage(req(), 'human')
    eid = ack(led, specimen='p2')
    with pytest.raises(ValueError, match='different specimen'):
        s.acknowledge('a1', 'HOLD', eid)


def test_sensor_event_bin_must_match_reported_bin(wired):
    led, s = wired; s.stage(req(), 'human')
    eid = ack(led, bin_name='PASS')
    with pytest.raises(ValueError, match='does not match reported bin'):
        s.acknowledge('a1', 'HOLD', eid)  # caller claims HOLD, sensor saw PASS


def test_e12_misroute_latches_fault_and_blocks_recovery(wired):
    led, s = wired; s.stage(req(bin='PASS', decision='AUTHORIZED_PASS'), 'human')
    wrong = ack(led, event_id='ack-wrong', bin_name='HOLD')
    with pytest.raises(ValueError, match='route mismatch'):
        s.acknowledge('a1', 'HOLD', wrong)
    st = s.status('a1')
    assert {k: st[k] for k in ('action_id', 'state', 'expected_bin', 'actual_bin', 'sensor_event_id', 'fault')} == {
        'action_id': 'a1', 'state': 'FAULTED', 'expected_bin': 'PASS', 'actual_bin': 'HOLD',
        'sensor_event_id': 'ack-wrong', 'fault': 'ROUTE_MISMATCH'}
    right = ack(led, event_id='ack-right', bin_name='PASS')
    with pytest.raises(ValueError, match='faulted'):
        s.acknowledge('a1', 'PASS', right)  # moving the part afterwards does not un-fault it
    with pytest.raises(ValueError, match='duplicate action id'):
        s.stage(req(bin='PASS', decision='AUTHORIZED_PASS'), 'human')  # must re-stage under a new id


def test_e13_one_sensor_event_confirms_at_most_one_action(wired):
    led, s = wired
    s.stage(req(action_id='a1'), 'human'); s.stage(req(action_id='a2'), 'human')
    eid = ack(led)
    assert s.acknowledge('a1', 'HOLD', eid)['status'] == 'PHYSICAL_ROUTE_CONFIRMED'
    with pytest.raises(ValueError, match='already consumed'):
        s.acknowledge('a2', 'HOLD', eid)
    assert s.acknowledge('a1', 'HOLD', eid)['status'] == 'DUPLICATE_ACK_IGNORED'


def test_pending_for_specimen_is_oldest_first(wired):
    led, s = wired
    s.stage(req(action_id='old'), 'human'); s.stage(req(action_id='new', specimen_id='p9'), 'human'); s.stage(req(action_id='newer'), 'human')
    assert [r.action_id for r in s.pending_for_specimen('p1')] == ['old', 'newer']


def test_status_unknown():
    assert SorterInterlock().status('nope')['state'] == 'UNKNOWN'


def test_concurrent_bounce_edges_confirm_exactly_once():
    """Two rising edges for one arrival, handled on two threads (FastAPI threadpool). The ledger
    lookup inside acknowledge() blocks on I/O, which is exactly where a second thread can slip
    past the 'already acked?' check. Must yield one confirmation, never two."""
    import threading, time
    led = EvidenceLedger()
    slow = lambda eid: (time.sleep(0.05), led.get_event(eid))[1]  # widen the race window
    s = SorterInterlock(sensor_lookup=slow, evidence_gate=lambda r: [])
    s.stage(req(bin='PASS', decision='AUTHORIZED_PASS'), 'human')
    ids = [ack(led, event_id=f'edge-{i}', bin_name='PASS') for i in range(4)]
    results, errors = [], []
    def worker(eid):
        try: results.append(s.acknowledge('a1', 'PASS', eid)['status'])
        except ValueError as ex: errors.append(str(ex))
    ts = [threading.Thread(target=worker, args=(e,)) for e in ids]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert results.count('PHYSICAL_ROUTE_CONFIRMED') == 1, (results, errors)
    assert len(s.used_sensor_events) == 1
