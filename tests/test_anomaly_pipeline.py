"""Anomaly pipeline tests (Bakdaulet, 31 Oct). Data/metrics/manifest parts need only numpy+cv2;
the training smoke test needs torch and is skipped when it is absent."""
import json
from pathlib import Path

import numpy as np
import pytest

from qualityrelay17 import anomaly

STL_DIR = Path(__file__).resolve().parents[1] / 'examples' / 'cad' / 'stl'


def test_synthetic_dataset_shapes_labels_masks_and_determinism():
    a = anomaly.synthetic_cad_dataset(STL_DIR, n_train=12, n_test_good=4, n_test_defect=8, size=64, seed=3, render_px=128)
    b = anomaly.synthetic_cad_dataset(STL_DIR, n_train=12, n_test_good=4, n_test_defect=8, size=64, seed=3, render_px=128)
    assert a['train'].shape == (12, 64, 64) and a['train'].dtype == np.uint8
    assert a['test'].shape == (12, 64, 64) and a['masks'].shape == (12, 64, 64)
    assert a['labels'].tolist() == [0] * 4 + [1] * 8
    assert set(a['defect_types']) == {'good', 'chip', 'hole', 'stringing', 'warp'}
    # masks only on defects, and every defect actually changed pixels
    assert a['masks'][a['labels'] == 0].sum() == 0
    assert all(m.sum() > 0 for m in a['masks'][a['labels'] == 1])
    assert np.array_equal(a['train'], b['train']) and np.array_equal(a['test'], b['test'])
    assert anomaly.dataset_hash(a) == anomaly.dataset_hash(b)
    assert anomaly.dataset_hash(a) != anomaly.dataset_hash(
        anomaly.synthetic_cad_dataset(STL_DIR, n_train=12, n_test_good=4, n_test_defect=8, size=64, seed=4, render_px=128))


def test_synthetic_dataset_uses_only_good_or_nominal_stls():
    ds = anomaly.synthetic_cad_dataset(STL_DIR, n_train=2, n_test_good=1, n_test_defect=1, size=32, seed=0, render_px=64)
    assert ds['source_files'] and all(('good' in f or 'nominal' in f) and 'risk' not in f for f in ds['source_files'])


def test_auroc_perfect_random_and_ties():
    assert anomaly.auroc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0
    assert anomaly.auroc([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1]) == 0.0
    assert anomaly.auroc([0.5, 0.5, 0.5, 0.5], [0, 1, 0, 1]) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        anomaly.auroc([0.1, 0.2], [0, 0])


def test_manifest_has_every_ledger_field_and_honest_tier(tmp_path):
    ds = anomaly.synthetic_cad_dataset(STL_DIR, n_train=2, n_test_good=1, n_test_defect=1, size=32, seed=0, render_px=64)
    cfg = anomaly.TrainConfig(epochs=1, pretrained=False)
    m = anomaly.build_manifest(run_id='t', data_source='synthetic-cad', ds=ds, cfg=cfg, metrics={'image_auroc': 0.5},
                               export_status={}, start=0.0, end=3600.0, provider='brev', instance_type='L4', price_per_hour=0.7)
    assert all(k in m for k in anomaly.LEDGER_FIELDS)
    assert m['source_origin'] == 'SIMULATED' and m['total_spend'] == 0.7 and m['model_hash'] == 'NOT_EXPORTED'
    m2 = anomaly.build_manifest(run_id='t', data_source='synthetic-cad', ds=ds, cfg=cfg, metrics={}, export_status={}, start=0.0, end=1.0)
    assert 'UNKNOWN' in str(m2['total_spend'])


def test_folder_dataset_rejects_unknown_layout(tmp_path):
    with pytest.raises(FileNotFoundError):
        anomaly.folder_dataset(tmp_path, size=32)


def test_training_smoke_cpu_no_pretrained(tmp_path):
    pytest.importorskip('torch')
    cfg = anomaly.TrainConfig(epochs=1, batch_size=4, pretrained=False, device='cpu', seed=0)
    run_dir, manifest = anomaly.run('synthetic-cad', out_dir=tmp_path, cfg=cfg, size=64, seed=0,
                                    n_train=8, n_test_good=4, n_test_defect=4, export=True, log=lambda *_: None)
    assert (run_dir / 'run_manifest.json').exists() and (run_dir / 'metrics.json').exists()
    assert 0.0 <= manifest['metrics']['image_auroc'] <= 1.0
    assert manifest['source_origin'] == 'SIMULATED' and manifest['device_used'] == 'cpu'
    assert manifest['config']['pretrained'] is False  # recorded, so nobody mistakes this for a real result
    saved = json.loads((run_dir / 'run_manifest.json').read_text())
    assert saved['dataset_hash'].startswith('sha256:')
    assert set(manifest['export']) == {'teacher', 'student'}  # status recorded whether or not export succeeded
