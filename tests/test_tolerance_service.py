"""Offline tests for the SentiLab tolerance-check client and the CSV script (no network)."""
import json
import shutil
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17 import tolerance_service as ts  # noqa: E402
from scripts import check_measurements_with_service as cms  # noqa: E402

CHECK_MJS = ROOT / 'collab' / 'sentilab-tolerance-check' / 'api' / 'check.mjs'
HEADER = ('timestamp_iso,specimen_id,manual_id,part_type,feature,location,reading_no,value_mm,nominal_mm,'
          'deviation_mm,unit,instrument_id,calibration_id,operator_id,method,image_file,image_sha256,'
          'evidence_tier,notes\n')


def fake(status, data, calls=None):
    def post(url, body, timeout):
        if calls is not None:
            calls.append(body)
        return status, data
    return post


def raising(exc):
    def post(url, body, timeout):
        raise exc
    return post


def test_request_body_matches_contract():
    b = ts.build_request('T-RISK-01', 'tab', 20.3049, mate=('S-RISK-01', 'slot', 20.7))
    assert b == {'part_id': 'T-RISK-01', 'part_type': 'tab', 'units': 'mm', 'dims_mm': {'width': 20.3},
                 'spec': {'nominal': 20.0, 'tol': 0.5, 'guard_band': 0.15},
                 'mate': {'part_id': 'S-RISK-01', 'dims_mm': {'slot_inner_width': 20.7}}}
    assert ts.build_request('S-1', 'slot', 21)['dims_mm'] == {'slot_inner_width': 21.0}


@pytest.mark.parametrize('args', [('X', 'pin', 1.0, None), ('T', 'tab', 20.0, ('T2', 'tab', 20.0)),
                                  ('S', 'slot', 21.0, ('S2', 'slot', 21.0))])
def test_bad_part_or_mate_type_is_rejected_before_sending(args):
    with pytest.raises(ValueError):
        ts.build_request(*args)


@pytest.mark.parametrize('verdict,disposition', [('pass', 'PASS'), ('review', 'HOLD'), ('fail', 'REJECT')])
def test_verdict_maps_to_advisory_disposition(verdict, disposition):
    v = ts.check('T', 'tab', 20.0, post=fake(200, {'verdict': verdict, 'score': 0.5, 'reasons': ['r'], 'version': '1.0'}))
    assert (v.disposition, v.verdict, v.score, v.reasons, v.service_version, v.origin) == \
        (disposition, verdict, 0.5, ('r',), '1.0', 'EXTERNAL_SERVICE')


def test_pair_fields_pass_through():
    v = ts.check('T', 'tab', 20.3, mate=('S', 'slot', 20.7),
                 post=fake(200, {'verdict': 'pass', 'score': 0.4, 'clearance_mm': 0.4, 'fit': False}))
    assert (v.disposition, v.clearance_mm, v.fit) == ('PASS', 0.4, False)


@pytest.mark.parametrize('post', [
    fake(422, {'error': 'units must be mm'}),
    fake(500, None),
    fake(200, {'verdict': 'maybe'}),
    fake(200, ['not', 'a', 'dict']),
    fake(200, {}),
    raising(urllib.error.URLError('blocked')),
    raising(TimeoutError('slow')),
    raising(ValueError('bad json')),
])
def test_anything_short_of_a_clean_answer_is_hold(post):
    v = ts.check('T', 'tab', 20.0, post=post)
    assert v.disposition == 'HOLD' and v.verdict is None and v.fit is None and v.reasons


def _node_post(url, body, timeout):
    js = (f"import('{CHECK_MJS.as_uri()}').then(m => process.stdout.write("
          f"JSON.stringify(m.evaluate({json.dumps(body)}))))")
    out = json.loads(subprocess.run(['node', '-e', js], capture_output=True, text=True, check=True, timeout=30).stdout)
    return out['status'], out['json']


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is not installed')
def test_client_against_the_vendored_service_code():
    # The same code that is deployed, run locally: the agreed example and both sides of the limits.
    pair = ts.check('T-RISK-01', 'tab', 20.30, mate=('S-RISK-01', 'slot', 20.70), post=_node_post)
    assert (pair.verdict, pair.score, pair.clearance_mm, pair.fit) == ('pass', 0.4, 0.4, False)
    assert ts.check('S-RISK-01', 'slot', 20.55, post=_node_post).disposition == 'HOLD'   # inside guard band
    assert ts.check('T-DEF-01', 'tab', 21.60, post=_node_post).disposition == 'REJECT'
    assert ts.check('S-GOOD-01', 'slot', 21.20, post=_node_post).disposition == 'PASS'


def _csv(tmp_path, rows):
    p = tmp_path / 'm.csv'
    p.write_text(HEADER + ''.join(
        f'2026-11-01T15:00:00Z,{sid},{mid},{kind},{feat},{loc},{n},{val},,,mm,CAL-1,C-1,OP1,caliper,,,{tier},\n'
        for sid, mid, kind, feat, loc, n, val, tier in rows))
    return p


def test_script_sends_only_physical_tier_functional_widths(tmp_path):
    p = _csv(tmp_path, [
        ('S-RISK-01', 'S-RISK', 'slot', 'slot_inner_width', 'left', 1, 20.72, 'OPERATOR_CONFIRMED'),
        ('S-RISK-01', 'S-RISK', 'slot', 'slot_inner_width', 'right', 1, 20.68, 'OPERATOR_CONFIRMED'),
        ('T-RISK-01', 'T-RISK', 'tab', 'width', 'mid', 1, 20.31, 'PHYSICAL_CAPTURE'),
        ('T-RISK-01', 'T-RISK', 'tab', 'width', 'tip', 1, 20.29, 'PHYSICAL_CAPTURE'),
        ('T-RISK-01', 'T-RISK', 'tab', 'thickness', 'mid', 1, 3.00, 'PHYSICAL_CAPTURE'),
        ('T-GOOD-01', 'T-GOOD', 'tab', 'width', 'mid', 1, 19.80, 'CAMERA_ESTIMATE'),
    ])
    calls = []
    rec = cms.run([p], post=fake(200, {'verdict': 'pass', 'score': 0.4, 'clearance_mm': 0.37, 'fit': False}, calls))
    assert [x['specimen_id'] for x in rec['parts']] == ['S-RISK-01', 'T-RISK-01']
    assert rec['parts'][0]['width_sent_mm'] == 20.68 and rec['parts'][1]['width_sent_mm'] == 20.31
    assert rec['pairs'] == [{'tab': 'T-RISK-01', 'slot': 'S-RISK-01', 'tab_width_mm': 20.31, 'slot_width_mm': 20.68,
                             'clearance_mm': 0.37, 'fit': False, 'answered': True, 'reasons': []}]
    assert len(calls) == 3 and all(c['units'] == 'mm' for c in calls)
    assert rec['origin'] == 'EXTERNAL_SERVICE' and len(rec['inputs'][0]['sha256']) == 64


def test_script_records_hold_when_service_is_down(tmp_path):
    p = _csv(tmp_path, [('T-NOM-01', 'T-NOM', 'tab', 'width', 'mid', 1, 20.00, 'VERIFIED_PHYSICAL')])
    rec = cms.run([p], post=raising(urllib.error.URLError('offline')))
    assert rec['parts'][0]['disposition'] == 'HOLD' and rec['parts'][0]['verdict'] is None


def test_committed_live_run_matches_the_vendored_code():
    rec = json.loads((ROOT / 'examples/results/sentilab_tolerance_check/live_run_1nov.json').read_text())
    assert rec['origin'] == 'EXTERNAL_SERVICE' and rec['service_sha256'] == \
        '753e763ef6166f752091f8830474ce06cd253d03e475735518e260ee354f84ab'
    pair = next(c for c in rec['calls'] if c['request'].get('body', {}).get('mate'))
    assert pair['response']['body']['verdict'] == 'pass' and pair['response']['body']['fit'] is False
