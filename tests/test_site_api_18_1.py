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


def test_visual_inspection_registered_reference_finds_a_scratch(tmp_path, monkeypatch):
    import base64, cv2, numpy as np
    from qualityrelay17.sim import api_routes
    from qualityrelay17.vision_measure import render_synthetic
    monkeypatch.setattr(api_routes, 'REFS', tmp_path)
    enc = lambda im: 'data:image/jpeg;base64,' + base64.b64encode(cv2.imencode('.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()).decode()  # noqa: E731
    rng = np.random.default_rng(4)
    ref = render_synthetic('tab', 20.0, rng, 20)
    assert c.post('/sim/vision/inspect', json=dict(lane='tab', action='compare', image_b64=enc(ref))).status_code == 409
    assert c.post('/sim/vision/inspect', json=dict(lane='tab', action='set_reference', image_b64=enc(ref))).json()['reference_saved']
    live = render_synthetic('tab', 20.0, rng, 20, defect_mm=(30, 6, 4, 2))
    r = c.post('/sim/vision/inspect', json=dict(lane='tab', action='compare', image_b64=enc(live))).json()
    assert r['report']['evidence_status'] == 'UNVERIFIED_VISUAL_CANDIDATE' and r['report']['requires_safe_mesh_and_human_review']
    assert any(x['x1'] <= 460 and x['x2'] >= 440 and x['y1'] <= 240 and x['y2'] >= 230 for x in r['report']['regions'])
    assert r['heatmap'].startswith('data:image/jpeg') and r['anomaly_model']['status'] == 'NOT_CONFIGURED'
    rf = '{"predictions":[{"x":100,"y":80,"width":30,"height":20,"confidence":0.7,"class":"crack"}]}'
    r2 = c.post('/sim/vision/inspect', json=dict(lane='tab', action='roboflow', image_b64=enc(live), roboflow_json=rf)).json()
    assert len(r2['report']['regions']) == 1 and r2['report']['regions'][0]['model_class_unverified'] == 'crack'
    nomarker = enc(np.full((200, 300, 3), 180, np.uint8))
    assert c.post('/sim/vision/inspect', json=dict(lane='tab', action='compare', image_b64=nomarker)).status_code == 422


def test_capture_protocol_fields_names_and_log(tmp_path, monkeypatch):
    import base64, csv, cv2, numpy as np
    from qualityrelay17.sim import api_routes
    from qualityrelay17.vision_measure import render_synthetic
    monkeypatch.setattr(api_routes, 'PRINTS', tmp_path / 'prints')
    img = render_synthetic('tab', 20.2, np.random.default_rng(2), 25)
    b64 = 'data:image/jpeg;base64,' + base64.b64encode(cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()).decode()
    assert c.post('/sim/vision/capture', json=dict(lane='tab', label='defect', image_b64=b64)).status_code == 422  # defect needs a type
    assert c.post('/sim/vision/capture', json=dict(lane='tab', label='good', image_b64=b64, specimen_id='bad id!')).status_code == 422
    r = c.post('/sim/vision/capture', json=dict(lane='tab', label='defect', defect_type='warp', specimen_id='P07', image_b64=b64)).json()
    name = r['saved'].split('/')[-1]
    assert '_warp_P07_tab_' in name and name[6] == '_' and (tmp_path / 'prints' / 'defect').exists()
    r2 = c.post('/sim/vision/capture', json=dict(lane='tab', label='good', purpose='measurement', specimen_id='P08', caliper_mm=20.2, image_b64=b64)).json()
    assert '/measure/' in r2['saved'] and abs(r2['photo_minus_caliper_mm']) < 0.2
    rows = list(csv.DictReader(open(tmp_path / 'prints' / 'capture_log.csv')))
    assert [x['specimen_id'] for x in rows] == ['P07', 'P08'] and rows[0]['label_checked_by'] == '' and rows[1]['caliper_mm'] == '20.2'


def test_physical_calibration_from_measurement_logger_csv(tmp_path, monkeypatch):
    import csv
    from qualityrelay17.sim import api_routes
    from qualityrelay17.sim.physical_data import load_measurements, calibrate, physical_scenario
    from qualityrelay17.sim.scenarios import BY_ID
    hdr = 'timestamp_iso,specimen_id,manual_id,part_type,feature,location,reading_no,value_mm,nominal_mm,deviation_mm,unit,instrument_id,calibration_id,operator_id,method,image_file,image_sha256,evidence_tier,notes'.split(',')
    rows = []
    for sid, man, kind, feat, vals in [('S-GOOD-01', 'S-GOOD', 'slot', 'slot_inner_width', [21.26, 21.24, 21.25]),
                                       ('S-NOM-01', 'S-NOM', 'slot', 'slot_inner_width', [21.07, 21.05, 21.06]),
                                       ('T-NOM-01', 'T-NOM', 'tab', 'width', [20.08, 20.10, 20.09]),
                                       ('T-RISK-01', 'T-RISK', 'tab', 'width', [20.41, 20.39, 20.40])]:
        for i, v in enumerate(vals):
            rows.append(dict(zip(hdr, ['2026-10-31T20:00', sid, man, kind, feat, 'mid', i + 1, v, '', '', 'mm', 'cal-1', 'c1', 'op', 'caliper_manual', '', '', 'OPERATOR_CONFIRMED', ''])))
    rows.append(dict(zip(hdr, ['t', 'T-NOM-01', 'T-NOM', 'tab', 'width', 'mid', 9, 25.0, '', '', 'mm', '', '', '', 'camera_uncalibrated', '', '', 'SIMULATED', ''])))  # ignored tier
    (tmp_path / 'm').mkdir(); f = tmp_path / 'm' / 'log.csv'
    with open(f, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=hdr); w.writeheader(); w.writerows(rows)
    cal = calibrate(load_measurements(f))
    assert cal['status'] == 'FITTED_FROM_PHYSICAL_RECORDS'
    assert abs(cal['fits']['slot']['bias_mm'] - 0.055) < 1e-6 and abs(cal['fits']['tab']['bias_mm'] - 0.095) < 1e-6
    assert 0.009 < cal['caliper_repeatability_sd_mm'] < 0.011
    sc = physical_scenario(BY_ID['F01'], cal)
    assert sc.sid == 'F01-PHYS' and abs(sc.sites[0].printer_bias_mm - 0.075) < 1e-6 and sc.sites[0].caliper_sd_mm < 0.02
    monkeypatch.setattr(api_routes, 'MEASUREMENTS', tmp_path / 'm')
    d = c.get('/sim/physical/summary').json()
    assert d['calibration']['status'] == 'FITTED_FROM_PHYSICAL_RECORDS' and len(d['calibration']['specimens']) == 4
    assert c.get('/sim/physical/page/measurement_logger').status_code == 200
    assert c.get('/sim/physical/page/../../AGENTS').status_code == 404
