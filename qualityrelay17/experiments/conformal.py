"""I2: conformal risk control of the false-PASS rate (Angelopoulos et al., 2022, 'Conformal Risk
Control'). Score = the calibrated posterior P(unsafe) of the Gate-A B1 policy. Choose the largest
threshold lam such that (n/(n+1)) * R_hat(lam) + B/(n+1) <= alpha with B = 1, where
R(lam) = P(part unsafe AND p_unsafe < lam), a monotone loss bounded by 1. Under exchangeability of
calibration and test parts, E[R(lam_hat)] <= alpha. Distribution shift breaks that, and the
experiment shows it. SIMULATED; physical use needs verified labels for the calibration set.
"""
from __future__ import annotations
from math import sqrt

import numpy as np
from scipy.special import erf

from ..factory import seeded_scenario
from .belief import BeliefModel, calibrate_belief_model


def scores(rows, m: BeliefModel):
    """Vectorised B1 posterior P(unsafe) (phone + Pi when its station is up; Gaussian caliper)."""
    phone = np.array([r['phone_suspect'] for r in rows], bool)
    pi = np.array([r['pi_suspect'] for r in rows], bool)
    up = ~np.array([r['network_down'] for r in rows], bool)
    y = np.array([r['measured_clearance'] for r in rows], float)
    unsafe = ~np.array([r['safe'] for r in rows], bool)

    def upd(p, sens, spec, f):
        ld = np.where(f, sens, 1 - sens); lg = np.where(f, 1 - spec, spec)
        return p * ld / (p * ld + (1 - p) * lg)
    ps = upd(np.full(len(rows), m.surface_prior), m.phone_sens, m.phone_spec, phone)
    ps = np.where(up, upd(ps, m.pi_sens, m.pi_spec, pi), ps)
    s2 = m.sigma_meas_mm ** 2; v = m.clearance_prior_var * s2 / (m.clearance_prior_var + s2)
    mu = v * (m.clearance_prior_mean / m.clearance_prior_var + y / s2)
    pd = 0.5 * (1 + erf((0.5 - mu) / np.sqrt(2 * v)))
    return 1 - (1 - ps) * (1 - pd), unsafe


def calibrate_threshold(p, unsafe, alpha):
    """Largest lam with (n/(n+1)) * mean(unsafe & p < lam) + 1/(n+1) <= alpha."""
    n = len(p)
    order = np.argsort(p); ps, us = p[order], unsafe[order]
    cum = np.cumsum(us) / n                      # R_hat at lam just above ps[i]
    ok = (n / (n + 1)) * cum + 1 / (n + 1) <= alpha
    if not ok[0]:
        return 0.0                               # nothing can be passed with this alpha
    last = np.nonzero(ok)[0].max()
    return float(ps[last] + 1e-12) if last + 1 >= n else float((ps[last] + ps[last + 1]) / 2)


def evaluate(lam, rows_by_lot, m):
    fp, good = [], []
    for rows in rows_by_lot:
        p, u = scores(rows, m)
        fp.append(float(np.mean(u & (p < lam)))); good.append(float(np.mean(~u & (p < lam))))
    k = len(fp); mfp = float(np.mean(fp)); se = float(np.std(fp, ddof=1) / sqrt(k))
    return dict(false_pass_rate=mfp, false_pass_ci95=[mfp - 1.96 * se, mfp + 1.96 * se], released_good_rate=float(np.mean(good)))


SCENARIOS = {'S01': {}, 'S02': dict(process_shift_mm=0.25), 'S04': dict(shared_camera_noise=0.15)}


def run(alpha=0.002, cal_seeds=range(2000, 2010), test_seeds=range(30), n=1000, m: BeliefModel | None = None):
    m = m or calibrate_belief_model()
    bayes_t = 2.0 / 152.0
    cal_rows = {sid: [r for s in cal_seeds for r in seeded_scenario(n, s, **kw)] for sid, kw in SCENARIOS.items()}
    lam_nom = calibrate_threshold(*scores(cal_rows['S01'], m), alpha)
    out = dict(origin='SIMULATED', alpha=alpha, n_calibration=len(cal_rows['S01']), bayes_threshold=bayes_t,
               lambda_nominal=lam_nom, scenarios={})
    for sid, kw in SCENARIOS.items():
        lots = [seeded_scenario(n, s, **kw) for s in test_seeds]
        lam_re = calibrate_threshold(*scores(cal_rows[sid], m), alpha)
        out['scenarios'][sid] = dict(
            bayes_threshold=evaluate(bayes_t, lots, m),
            conformal_nominal_calibration=dict(lam=lam_nom, **evaluate(lam_nom, lots, m)),
            conformal_recalibrated=dict(lam=lam_re, **evaluate(lam_re, lots, m)))
    return out


def calibrate_threshold_pac(p, unsafe, alpha, delta=0.1):
    """PAC variant (Learn-then-Test style, monotone loss): largest lam whose one-sided Clopper-Pearson
    (1-delta) upper bound on R(lam) is <= alpha. Then P(R(lam_hat) <= alpha) >= 1 - delta over
    calibration sets, i.e. a per-batch guarantee instead of one in expectation."""
    from scipy.stats import beta
    n = len(p); order = np.argsort(p); ps, us = p[order], unsafe[order]
    k = np.cumsum(us)
    ucb = beta.ppf(1 - delta, k + 1, n - k)            # CP upper bound for k events in n
    ok = ucb <= alpha
    if not ok[0]:
        return 0.0
    # monotone loss: scan from the smallest threshold, stop at the first violation (fixed-sequence testing)
    first_bad = np.argmax(~ok) if (~ok).any() else n
    last = first_bad - 1
    return float(ps[last] + 1e-12) if last + 1 >= n else float((ps[last] + ps[last + 1]) / 2)
