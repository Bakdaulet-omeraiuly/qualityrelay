"""Level-1 digital twin V&V (docs/architectures/05_DIGITAL_FACTORY_TWIN.md): conservation,
determinism under seeded replay, no duplicate IDs / negative waits, common random numbers
across policies, and that the twin never changes a disposition the inspection policy made."""
import json

import pytest

from qualityrelay17 import digital_twin as dt
from qualityrelay17.factory import seeded_scenario, apply_policy, POLICIES


def test_twin_is_deterministic_under_seeded_replay():
    assert dt.run_twin(60, 3, 'conservative_rules') == dt.run_twin(60, 3, 'conservative_rules')
    assert dt.run_twin(60, 3, 'conservative_rules') != dt.run_twin(60, 4, 'conservative_rules')


@pytest.mark.parametrize('policy', POLICIES)
def test_conservation_and_sanity_every_policy(policy):
    out = dt.run_twin(80, 7, policy, network_outage=0.2)
    c = out['counts']
    assert out['origin'] == 'SIMULATED'
    assert c['pass'] + c['hold'] + c['escaped_defect'] == 80 == out['completed']
    assert out['conservation_ok'] is True and out['wip_end'] == 0
    ids = [r['specimen_id'] for r in out['routes']]
    assert len(ids) == len(set(ids)) == 80
    for r in out['routes']:
        prev_end = r['arrival']
        for v in r['visits']:
            assert v['start'] >= v['arrival'] >= prev_end - 1e-9 and v['end'] >= v['start']
            assert v['queue_wait_s'] >= 0
            prev_end = v['end']
        assert r['finish'] == pytest.approx(r['visits'][-1]['end'])
    assert out['max_wip'] >= 1 and out['mean_wip'] > 0
    assert out['throughput_per_hour'] > 0 and out['p95_cycle_time_s'] >= out['mean_cycle_time_s'] > 0
    for s in out['station_summary'].values():
        assert 0 <= s['utilization'] <= 1 and s['mean_wait_s'] >= 0


def test_twin_never_changes_the_policy_disposition():
    rows = seeded_scenario(100, 11)
    for policy in ('conservative_rules', 'voi_driven', 'structured_request_lite'):
        expected = {r['specimen_id']: r['outcome'] for r in apply_policy(rows, policy)}
        out = dt.run_twin(100, 11, policy)
        assert {r['specimen_id']: r['outcome'] for r in out['routes']} == expected


def test_common_random_numbers_across_policies():
    # Same seed -> same specimens AND same service-time noise: the Print station (first, identical
    # for every policy) must finish at identical times under every policy.
    a = dt.run_twin(50, 5, 'conservative_rules')
    b = dt.run_twin(50, 5, 'voi_driven')
    ends_a = [r['visits'][0]['end'] for r in a['routes']]
    ends_b = [r['visits'][0]['end'] for r in b['routes']]
    assert ends_a == ends_b
    assert [r['specimen_id'] for r in a['routes']] == [r['specimen_id'] for r in b['routes']]


def test_hold_routes_through_review_and_pass_does_not():
    out = dt.run_twin(120, 2, 'conservative_rules')
    for r in out['routes']:
        stations = [v['station'] for v in r['visits']]
        assert ('Review' in stations) == (r['outcome'] == 'hold')
    assert out['station_summary']['Review']['visits'] == out['counts']['hold']


def test_network_outage_skips_pi_station():
    rows = seeded_scenario(100, 9, network_outage=0.3)
    out = dt.run_twin(100, 9, 'conservative_rules', network_outage=0.3)
    down = {r['specimen_id'] for r in rows if r['network_down']}
    assert down
    for r in out['routes']:
        stations = [v['station'] for v in r['visits']]
        assert ('Pi_Vision' in stations) == (r['specimen_id'] not in down)


def test_purchased_evidence_costs_station_time():
    fusion = dt.run_twin(300, 4, 'collective_fusion')
    voi = dt.run_twin(300, 4, 'voi_driven')
    entropy = dt.run_twin(300, 4, 'entropy_driven')
    assert voi['inspection_time_s'] > fusion['inspection_time_s']
    assert entropy['inspection_time_s'] >= voi['inspection_time_s']
    bought = [r for r in voi['routes'] if r.get('extra_visits')]
    assert bought and all(any(v['extra'] for v in r['visits']) for r in bought)


def test_structured_request_visits_pi_only_when_requested():
    rows = apply_policy(seeded_scenario(200, 3), 'structured_request_lite')
    out = dt.run_twin(200, 3, 'structured_request_lite')
    req = {r['specimen_id']: r['requested_pi_evidence'] for r in rows}
    for r in out['routes']:
        assert ('Pi_Vision' in [v['station'] for v in r['visits']]) == req[r['specimen_id']]


def test_timing_assumptions_are_labelled_and_echoed():
    out = dt.run_twin(10, 1, 'conservative_rules')
    assert out['timing']['status'] == 'ILLUSTRATIVE_ASSUMPTION'
    assert out['timing']['review_s'] == dt.TwinTiming().review_s
    with pytest.raises(ValueError):
        dt.run_twin(0, 1, 'conservative_rules')
    with pytest.raises(ValueError):
        dt.run_twin(5, 1, 'no_such_policy')


def test_compare_twin_pairs_all_policies_against_rules():
    out = dt.compare_twin(80, 6)
    assert set(out['policies']) == set(POLICIES)
    assert out['policies']['conservative_rules']['counts']['pass'] + out['policies']['conservative_rules']['counts']['hold'] \
        + out['policies']['conservative_rules']['counts']['escaped_defect'] == 80
    d = out['paired_vs_conservative_rules']['voi_driven']
    for k in ('mean_cycle_time_s', 'throughput_per_hour', 'max_wip', 'unsafe_pass', 'hold', 'inspection_time_s'):
        assert k in d
    assert out['paired_vs_conservative_rules']['conservative_rules']['mean_cycle_time_s'] == 0


def test_scenario_runner_writes_files_with_cis(tmp_path):
    res = dt.run_twin_scenarios(seeds=range(3), n=40, out_dir=tmp_path,
                                scenarios={'baseline': {}, 'outage': {'network_outage': 0.3}, 'tight_review': {'review_capacity': 1, 'review_s': 120.0}})
    assert set(res['scenarios']) == {'baseline', 'outage', 'tight_review'}
    man = json.loads((tmp_path / 'manifest.json').read_text())
    assert man['origin'] == 'SIMULATED' and man['seeds'] == [0, 1, 2]
    blk = res['scenarios']['baseline']['paired_vs_rules']['voi_driven']['mean_cycle_time_s']
    assert blk['ci95'][0] <= blk['mean'] <= blk['ci95'][1]
    assert (tmp_path / 'summary.csv').exists() and (tmp_path / 'baseline.json').exists()
