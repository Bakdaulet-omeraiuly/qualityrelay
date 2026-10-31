"""Website routes for the 18.1 results (qualityrelay17/sim/api_routes.py)."""
from fastapi.testclient import TestClient

from qualityrelay17.api import app

c = TestClient(app)


def test_pages_and_assets_are_served():
    assert c.get('/').status_code == 200 and 'QualityRelay' in c.get('/').text
    assert c.get('/legacy').status_code == 200
    for a in ('three.module.js', 'OrbitControls.js', 'STLLoader.js', 'CSS2DRenderer.js', 'site.js', 'site.css'):
        assert c.get(f'/sim/assets/{a}').status_code == 200, a


def test_file_routes_are_allow_listed():
    assert c.get('/sim/assets/..%2F..%2Fqualityrelay17%2Fapi.py').status_code == 404
    assert c.get('/sim/assets/api.py').status_code == 404
    assert c.get('/sim/stl/../../README.md').status_code == 404
    assert c.get('/sim/charts/secret.svg').status_code == 404
    assert c.get('/sim/stl/slot_nominal_21p00.stl').status_code == 200


def test_run_returns_a_conserving_simulated_trace():
    r = c.post('/sim/run', json=dict(scenario='F02', policy='bayes', pairing='optimized', seed=1, n_pairs=30))
    d = r.json()
    assert r.status_code == 200 and d['source_tier'] == 'SIMULATED' and d['kpis']['conservation_ok']
    assert len(d['parts']) == 60 + d['kpis']['reprints']  # website runs reprint confirmed defects
    for p in d['parts']:
        assert [e[1] for e in p['events']] == sorted(e[1] for e in p['events'])
        assert all(e[2] >= e[1] for e in p['events'])
    assert c.post('/sim/run', json=dict(scenario='NOPE')).status_code == 422
    assert c.post('/sim/run', json=dict(n_pairs=10_000)).status_code == 422


def test_results_bundle_matches_the_registered_files():
    d = c.get('/sim/results').json()
    assert d['source_tier'] == 'SIMULATED'
    pv = d['factory']['product_vs_today']
    assert len(pv) == 15 and sum(x['safe'] for x in pv) == 15 and sum(x['throughput'] for x in pv) == 4
    assert d['gate_a']['summary']['B7_safe_mesh_voi']['released_good_rate'] == 0.0
    assert set(d['warp']) == {f'S0{i}' for i in range(1, 9)}


def test_photo_capture_saves_physical_capture_and_never_invents_a_score(tmp_path, monkeypatch):
    import base64
    import cv2
    import numpy as np
    from qualityrelay17.sim import api_routes
    monkeypatch.setattr(api_routes, 'PRINTS', tmp_path)
    ok, buf = cv2.imencode('.png', np.full((40, 60, 3), 128, np.uint8))
    b64 = 'data:image/png;base64,' + base64.b64encode(buf.tobytes()).decode()
    r = c.post('/sim/vision/capture', json=dict(lane='tab', label='good', image_b64=b64)).json()
    assert r['source_tier'] == 'PHYSICAL_CAPTURE' and (r['width'], r['height']) == (60, 40)
    assert r['nvidia_anomaly']['status'] == 'NOT_CONFIGURED' and 'score' not in r['nvidia_anomaly']
    assert len(list((tmp_path / 'good').glob('*.png'))) == 1
    assert c.post('/sim/vision/capture', json=dict(lane='tab', label='good', image_b64='data:image/png;base64,' + 'A' * 64)).status_code == 422
    assert c.post('/sim/vision/capture', json=dict(lane='x', label='good', image_b64=b64)).status_code == 422


def test_live_events_are_displayed_but_never_verified():
    ev = dict(event_id='e-1', specimen_id='S-0-000001', station_id='phone', observed_at='2026-10-31T20:00:00Z', lane='slot', value=False)
    r = c.post('/sim/live/event', json=ev).json()
    assert r['accepted'] and r['verified'] is False
    recent = c.get('/sim/live/recent', params={'after': r['seq'] - 1}).json()
    assert recent and recent[-1]['specimen_id'] == 'S-0-000001' and recent[-1]['verified'] is False
    assert c.post('/sim/live/event', json={**ev, 'source_tier': 'VERIFIED_PHYSICAL'}).status_code == 422
    assert c.post('/sim/live/event', json={**ev, 'station_id': 'sorter-ACK-bypass'}).status_code == 422


def test_suggest_ranks_near_boundary_first(tmp_path, monkeypatch):
    import cv2, numpy as np
    from qualityrelay17.sim import api_routes
    from qualityrelay17.vision_measure import render_synthetic
    monkeypatch.setattr(api_routes, 'PRINTS', tmp_path)
    (tmp_path / 'inbox').mkdir()
    rng = np.random.default_rng(0)
    cv2.imwrite(str(tmp_path / 'inbox' / 'a_far.png'), render_synthetic('tab', 19.6, rng, 25))
    cv2.imwrite(str(tmp_path / 'inbox' / 'b_near.png'), render_synthetic('tab', 20.45, rng, 25))
    cv2.imwrite(str(tmp_path / 'inbox' / 'c_nomarker.png'), np.full((200, 200, 3), 200, np.uint8))
    s = c.get('/sim/vision/suggest').json()['suggestions']
    assert [x['file'] for x in s] == ['b_near.png', 'a_far.png', 'c_nomarker.png']
