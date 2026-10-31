import numpy as np

from qualityrelay17.vision_measure import measure_part_width, render_synthetic, validate_synthetic


def test_synthetic_accuracy_meets_the_bar_at_phone_resolution():
    r = validate_synthetic(n=24, seed=11, photo_px_per_mm=25)
    assert r['failures'] == 0 and r['mae_mm'] <= 0.10


def test_kind_detection_and_no_marker():
    rng = np.random.default_rng(3)
    assert measure_part_width(render_synthetic('slot', 21.0, rng, 25))['kind'] == 'slot_opening'
    assert measure_part_width(render_synthetic('tab', 20.0, rng, 25))['kind'] == 'tab_width'
    assert measure_part_width(np.full((300, 400, 3), 200, np.uint8))['status'] == 'NO_MARKER'
