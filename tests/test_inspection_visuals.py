"""No GPU/network/model weights needed. Validate artifacts, provenance and fail-closed limits."""
import json

import cv2
import numpy as np
import pytest

from qualityrelay17.inspection_visuals import (
    candidate_regions, draw_candidate_boxes, image_quality,
    model_anomaly_map, overlay_heatmap, reference_difference, roboflow_predictions,
)


@pytest.fixture
def imgs():
    rng = np.random.default_rng(17)
    ref = rng.integers(35, 190, size=(64, 64), dtype=np.uint8)
    live = ref.copy()
    live[20:30, 24:34] = 244
    return ref, live


BASE = dict(specimen_id='slot-7', image_event_id='phone-2', source_root='source-phone-2',
            station_id='PHONE', source_tier='SIMULATED', calibration_id='test-only')


def test_reference_candidate_regions_and_heatmap(imgs):
    ref, live = imgs
    report, raw, mask = reference_difference(ref, live, **BASE, reference_event_id='ref-1',
                                            reference_root='source-ref-1', aligned=True, threshold=40)
    assert report['method'] == 'opencv_absdiff_reference_v1'
    assert report['decision'] == 'REVIEW_REQUIRED'
    assert report['calibrated_defect_probability'] is None
    assert report['evidence_status'] == 'UNVERIFIED_VISUAL_CANDIDATE'
    assert report['derived_from'] == ['phone-2', 'ref-1']
    assert 'source-ref-1' == report['reference_root']
    assert report['signal']['difference_fraction'] > 0
    assert mask.sum() > 0
    assert report['regions'] and any(r['x1'] <= 24 < r['x2'] for r in report['regions'])
    overlay = overlay_heatmap(live, raw, mask=mask)
    assert overlay.shape == (64, 64, 3) and overlay.dtype == np.uint8
    boxed = draw_candidate_boxes(overlay, report)
    assert boxed.shape == overlay.shape
    assert np.any(boxed != overlay)


def test_reference_refuses_unaligned_or_mismatched_or_duplicate_source(imgs):
    ref, live = imgs
    kw = dict(BASE, reference_event_id='ref-1', reference_root='source-ref-1')
    with pytest.raises(ValueError, match='aligned'):
        reference_difference(ref, live, aligned=False, **kw)
    with pytest.raises(ValueError, match='shape'):
        reference_difference(ref, live[:40], aligned=True, **kw)
    with pytest.raises(ValueError, match='distinct'):
        reference_difference(ref, live, aligned=True, **dict(kw, reference_root='source-phone-2'))
    with pytest.raises(ValueError, match='source_tier'):
        reference_difference(ref, live, aligned=True, **dict(kw, source_tier='VERIFIED_PHYSICAL'))


def test_anomaly_map_uses_supplied_model_not_imaginary_inference(imgs):
    _, live = imgs
    amap = np.zeros((64, 64), dtype=np.float32)
    amap[7:16, 8:19] = 0.9
    report, raw, mask = model_anomaly_map(live, amap, **BASE,
                                          model_id='existing-STFPM-run', raw_threshold=0.45)
    assert report['derived_from'] == ['phone-2']
    assert report['decision'] == 'REVIEW_REQUIRED'
    assert report['signal']['model_id'] == 'existing-STFPM-run'
    assert report['signal']['score_is_calibrated_probability'] is False
    assert report['regions'][0]['area_px'] == 99
    assert mask.sum() == 99
    assert raw.shape == (64, 64)
    with pytest.raises(ValueError, match='non-finite'):
        model_anomaly_map(live, np.full((64,64), float('nan')), **BASE,
                          model_id='x', raw_threshold=0.3)
    with pytest.raises(ValueError, match='matching'):
        model_anomaly_map(live, np.zeros((32,32)), **BASE,
                          model_id='x', raw_threshold=0.3)


def test_roboflow_prediction_normalization_and_clipping(imgs):
    _, live = imgs
    predictions = {'predictions': [
        {'x': 31, 'y': 22, 'width': 10, 'height': 8, 'confidence': 0.91, 'class': 'chip'},
        {'x': 0, 'y': 0, 'width': 8, 'height': 8, 'confidence': 0.62, 'class': 'scratch'},
    ]}
    report, scores, mask = roboflow_predictions(live, predictions, **BASE,
                                               model_id='external-demo-v1')
    assert report['method'] == 'roboflow_prediction_adapter_v1'
    assert report['decision'] == 'REVIEW_REQUIRED'
    assert report['source_root'] == 'source-phone-2'
    assert len(report['regions']) == 2
    assert report['regions'][0]['model_class_unverified'] == 'chip'
    assert report['regions'][0]['raw_model_confidence'] == pytest.approx(0.91)
    assert np.count_nonzero(mask) > 0
    assert np.array_equal(scores.astype(np.uint8), mask)
    assert json.loads(json.dumps(report))['claim_boundary'].startswith('Visualization')
    with pytest.raises(ValueError, match='invalid prediction'):
        roboflow_predictions(live, {'predictions':[{'x':0,'y':0,'width':3,'height':1,
                                                  'confidence':1.5}]}, **BASE,model_id='x')


def test_immutable_visualization_blank_and_fail_closed_quality():
    blank = np.zeros((32, 32), dtype=np.uint8)
    overlay = overlay_heatmap(blank, np.zeros((32, 32), dtype=np.float32))
    assert np.array_equal(overlay[:,:,0], blank)
    q = image_quality(blank)
    assert 'MOSTLY_DARK' in q['warnings']
    report, _, _ = model_anomaly_map(blank, np.zeros((32, 32)), **BASE,
                                     model_id='STFPM', raw_threshold=0.1)
    assert report['decision'] == 'RECAPTURE_REQUIRED'
    with pytest.raises(ValueError, match='alpha'):
        overlay_heatmap(blank, np.zeros((32, 32)), alpha=1.5)
    with pytest.raises(ValueError, match='renderer'):
        draw_candidate_boxes(blank, report, renderer='invalid')
    assert candidate_regions(np.zeros((32, 32))) == []


def test_cli_reference_end_to_end(tmp_path, imgs, capsys):
    from scripts.inspect_visual import execute
    ref, live = imgs
    cv2.imwrite(str(tmp_path / 'reference.png'), ref)
    cv2.imwrite(str(tmp_path / 'live.png'), live)
    out = tmp_path / 'output'
    assert execute(['--mode','reference','--reference',str(tmp_path / 'reference.png'),
                    '--live',str(tmp_path / 'live.png'),'--out',str(out),
                    '--specimen-id','slot-7','--event-id','phone-2','--source-root','source-phone-2',
                    '--reference-event-id','ref-1','--reference-root','source-ref-1',
                    '--station-id','PHONE','--source-tier','SIMULATED','--aligned']) == 0
    report = json.loads((out / 'report.json').read_text())
    assert report['decision'] in ('REVIEW_REQUIRED', 'RECAPTURE_REQUIRED')
    assert (out / 'boxes.png').exists() and (out / 'heatmap.png').exists()
    assert 'REVIEW ONLY' in capsys.readouterr().out


def test_cli_anomaly_map_and_roboflow_end_to_end(tmp_path, imgs):
    from scripts.inspect_visual import execute
    _, live = imgs
    cv2.imwrite(str(tmp_path/'live.png'),live)
    amap=np.zeros((64,64),dtype=np.float32);amap[16:23,17:26]=1
    np.save(tmp_path/'map.npy',amap)
    common=['--live',str(tmp_path/'live.png'),'--specimen-id','slot-7','--event-id','phone-2',
            '--source-root','source-phone-2','--station-id','PHONE','--source-tier','SIMULATED']
    assert execute(['--mode','anomaly-map','--out',str(tmp_path/'anomaly'),
                    '--anomaly-map',str(tmp_path/'map.npy'),'--model-id','STFPM-run-1',
                    '--raw-threshold','0.5',*common])==0
    assert json.loads((tmp_path/'anomaly'/'report.json').read_text())['method'] == 'external_or_stfpm_anomaly_map_v1'
    (tmp_path/'preds.json').write_text(json.dumps({'predictions':[{'x':30,'y':30,'width':10,'height':10,'confidence':0.8,'class':'chip'}]}))
    assert execute(['--mode','roboflow-json','--out',str(tmp_path/'roboflow'),
                    '--predictions-json',str(tmp_path/'preds.json'),'--model-id','external-v1',*common])==0
    assert json.loads((tmp_path/'roboflow'/'report.json').read_text())['method'] == 'roboflow_prediction_adapter_v1'
