"""API-01: /simulation/*, /benchmark/*, /economics/* expose the registered results with provenance."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qualityrelay17.api import app
from qualityrelay17.results_api import PROVENANCE_KEYS

c = TestClient(app)
SCHEMA = Path(__file__).resolve().parents[1] / 'docs' / 'research' / 'sim_api' / 'simulation_response.schema.json'

GET_ROUTES = ('/simulation/scenarios', '/simulation/runs', '/simulation/runs/sim18.1/F01/rules+fifo/s0',
              '/simulation/summary', '/simulation/summary?scenario=M04', '/simulation/scale',
              '/benchmark/gate-a', '/benchmark/gate-a/S01', '/benchmark/warp', '/benchmark/warp/S03',
              '/economics/assumptions', '/economics/roi', '/economics/roi/F01', '/economics/hold-all',
              '/economics/capacity-plan', '/simulation/factory-line?n=20')


def _check(d):
    for k in PROVENANCE_KEYS:
        assert k in d, k
    assert d['source_tier'] == 'SIMULATED'
    assert d['model_version'] and d['run_id'] and d['assumption_set']
    assert isinstance(d['seeds'], list)
    assert d['seed'] is None or isinstance(d['seed'], int)


@pytest.mark.parametrize('url', GET_ROUTES)
def test_every_results_route_carries_provenance(url):
    r = c.get(url)
    assert r.status_code == 200, r.text
    _check(r.json())


def test_post_routes_carry_provenance():
    d = c.post('/simulation/compare', json={'n': 30, 'seed': 42}).json()
    _check(d)
    assert d['seed'] == 42 and d['run_id'].startswith('compare/n30/s42')
    d = c.post('/simulation/run', json=dict(scenario='F02', seed=3, n_pairs=20)).json()
    _check(d)
    assert d['seed'] == 3 and d['registered'] is False and d['run_id'].startswith('adhoc/F02/bayes+optimized/s3/n20/')
    assert d['kpis']['conservation_ok']


def test_runs_filter_paginate_and_round_trip():
    d = c.get('/simulation/runs', params=dict(scenario='F01', policy='rules', pairing='fifo')).json()
    assert d['total'] == 20 and d['seeds'] == list(range(20))
    assert {r['scenario'] for r in d['runs']} == {'F01'}
    page = c.get('/simulation/runs', params=dict(limit=5, offset=5)).json()
    assert len(page['runs']) == 5 and page['total'] == 1200
    one = d['runs'][7]
    got = c.get(f"/simulation/runs/{one['run_id']}").json()
    assert got['run_id'] == one['run_id'] and got['seed'] == one['seed'] == 7
    assert c.get('/simulation/runs/sim18.1/F01/rules+fifo/s999').status_code == 404


def test_registered_run_records_match_the_proposed_schema():
    jsonschema = pytest.importorskip('jsonschema')
    schema = json.loads(SCHEMA.read_text())
    for r in c.get('/simulation/runs', params=dict(limit=50)).json()['runs']:
        jsonschema.validate(r, schema)


def test_unknown_ids_are_404_not_file_reads():
    for url in ('/simulation/summary?scenario=NOPE', '/benchmark/gate-a/S99', '/benchmark/warp/S99',
                '/benchmark/warp/..%2Fmanifest', '/benchmark/warp/manifest', '/economics/roi/NOPE'):
        assert c.get(url).status_code == 404, url


def test_non_finite_roi_values_are_null_and_json_is_strict():
    r = c.get('/economics/roi/F01')
    assert r.status_code == 200
    d = json.loads(r.text, parse_constant=lambda s: pytest.fail(f'non-finite {s} in JSON'))
    assert d['payback_months']['p95'] is None
    assert d['status'] == 'SCENARIO_OUTCOME_NOT_MEASURED_SAVINGS' and d['seeds']
    assert d['assumption_set'] == 'economics_sim.ASSUMPTIONS@triangular-MC'


def test_gate_a_and_warp_keep_the_registered_numbers():
    g = c.get('/benchmark/gate-a/S01').json()
    assert g['summary']['B7_safe_mesh_voi']['released_good_rate'] == 0.0 and 'per_seed' not in g
    assert len(g['seeds']) == 30 and g['seed'] is None
    assert 'per_seed' in c.get('/benchmark/gate-a/S01', params=dict(per_seed=True)).json()
    w = c.get('/benchmark/warp').json()
    assert w['seed'] == 2026 and {s['sid'] for s in w['scenarios']} == {f'S0{i}' for i in range(1, 9)}
