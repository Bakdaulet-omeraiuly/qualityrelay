import numpy as np

from qualityrelay17.experiments.conformal import calibrate_threshold, run


def test_threshold_respects_the_finite_sample_bound():
    rng = np.random.default_rng(0)
    p = rng.random(5000); unsafe = rng.random(5000) < p * 0.02
    for a in (0.001, 0.005, 0.02):
        lam = calibrate_threshold(p, unsafe, a)
        n = len(p)
        assert (n / (n + 1)) * np.mean(unsafe & (p < lam)) + 1 / (n + 1) <= a + 1e-12


def test_guarantee_holds_when_exchangeable_small():
    out = run(alpha=0.004, cal_seeds=range(2000, 2004), test_seeds=range(8), n=500)
    s01 = out['scenarios']['S01']['conformal_recalibrated']
    assert s01['false_pass_ci95'][0] <= 0.004
