"""The six agents decide inside the simulated line (sim/agents.py)."""
from dataclasses import replace
import json
import pytest
from fastapi.testclient import TestClient
from qualityrelay17.api import app
from qualityrelay17.sim.engine import Factory, calibrate_part_model
from qualityrelay17.sim.scenarios import BY_ID

M = calibrate_part_model()


def _key(f):
    return [(p['pair_id'], p['decision'], p.get('p_unsafe'), p.get('fate')) for p in f.pairs]


@pytest.mark.parametrize('sid,policy,pairing,feedback', [('F01', 'bayes', 'optimized', 'none'), ('F02', 'bayes', 'fifo', 'ewma'),
                                                         ('F03', 'rules', 'fifo', 'none'), ('M03', 'bayes', 'optimized', 'none'),
                                                         ('M05', 'hold_all', 'optimized', 'ewma')])
def test_agent_decisions_equal_the_built_in_line(sid, policy, pairing, feedback):
    sc = replace(BY_ID[sid], n_pairs=60)
    kw = dict(model=M, reprint=True, lane_by_kind=True, feedback=feedback)
    a = Factory(sc, 3, policy, pairing, **kw); ra = a.run()
    b = Factory(sc, 3, policy, pairing, agents=True, **kw); rb = b.run()
    assert _key(a) == _key(b)
    assert {k: ra[k] for k in ('shipped', 'escaped', 'pair_holds', 'part_holds', 'truth_sha256')} == \
           {k: rb[k] for k in ('shipped', 'escaped', 'pair_holds', 'part_holds', 'truth_sha256')}
    assert len(b.agents.alarms) == len(a.alarms) and len(b.agents.setpoints) == len(a.corrections)


def test_agents_never_receive_ground_truth_and_every_decision_is_a_message():
    f = Factory(replace(BY_ID['F03'], n_pairs=60), 3, 'bayes', 'optimized', model=M, reprint=True, lane_by_kind=True, agents=True)
    f.run()
    x = f.agents.export()
    blob = json.dumps([m[5] for m in x['messages']])
    for leak in ('true_width', 'true_clearance', 'truly_safe', 'escaped', 'crack', 'warped'):
        assert leak not in blob
    pair_decisions = [m for m in x['messages'] if m[1] == 'DECISION' and m[5]['stage'] == 'pair']
    assert len(pair_decisions) == len(f.pairs)
    assert all(m[2] == 'cost' and m[3] == 'assembly' for m in pair_decisions)
    # Assembly learns part evidence only by asking the owners over the PeerBus: per part one request per camera + the caliper
    per_part = len(f.sc.cameras) + 1
    assert sum(1 for m in x['messages'] if m[1] == 'REQUEST_EVIDENCE' and m[2] == 'assembly') == 2 * per_part * len(f.pairs)
    assert x['total_bytes'] == sum(m[6] for m in x['messages']) > 0


def test_sim_run_reports_the_reference_check():
    d = TestClient(app).post('/sim/run', json=dict(scenario='F01', seed=0, n_pairs=20)).json()
    assert d['agents']['check']['identical'] is True and d['agents']['check']['pairs'] == len(d['pairs'])
    assert set(d['agents']['roster']) == {'vision', 'metrology', 'process', 'assembly', 'cost', 'learning', 'governance'}
    assert TestClient(app).post('/sim/run', json=dict(scenario='F01', seed=0, n_pairs=20, agents=False)).json()['agents'] is None


def test_evidence_travels_over_adilnurs_peerbus_and_forgery_means_hold():
    from qualityrelay17.contracts import Evidence
    f = Factory(replace(BY_ID['F01'], n_pairs=30), 2, 'bayes', 'optimized', model=M, agents=True)
    team = f.agents
    orig = team._request
    def tamper(bus, pid, case):  # forge the caliper record of one slot after capture
        if pid == 'S-2-000004':
            team.evidence[pid] = [Evidence(**{**e.unsigned(), 'signature': 'forged'}) if e.kind == 'CALIPER' else e for e in team.evidence[pid]]
        return orig(bus, pid, case)
    team._request = tamper
    f.run()
    x = team.export()
    assert x['protocol']['outcomes'].get('BAD_SIGNATURE') == 1 and x['protocol']['verify'].get('BAD_SIGNATURE') == 1
    pair = next(p for p in f.pairs if p['slot_id'] == 'S-2-000004')
    assert pair['decision'] == 'HOLD' and pair['reason'] == 'UNVERIFIED_EVIDENCE'
    reqs = [m for m in x['messages'] if m[1] == 'REQUEST_EVIDENCE']
    assert reqs and all(m[5]['protocol'] == 'PeerBus' and m[5]['signed'] and m[5]['roles'].startswith('assembly_engineer->') for m in reqs)
    assert any(m[1] == 'DECISION_PROPOSAL' and m[3] == 'governance' for m in x['messages'])
