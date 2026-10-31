"""Held-out likelihood calibration for the synthetic scientific engine (Bakdaulet, 31 Oct).

Sensitivity / specificity / priors used by `factory.py`'s posterior-based policies are
ESTIMATED here on calibration seeds that are never used as test seeds, then frozen into the
run manifest with their counts and Wilson intervals. They are not read off the generator's
constants -- a policy must not know the generator -- and they are not the invented 17.0
placeholders, which survive only as `factory.LIKELIHOODS_PLACEHOLDER_17_0` for the
mis-specification ablation.

Everything here is SIMULATED. A physical calibration table (17.1 section 4.3) replaces this
module's output, not its interface.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from hashlib import sha256
from math import sqrt
import json


def wilson_interval(k, n, z=1.9599639845):
    if n < 1:
        return (0, 1)
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    radius = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return (max(0, center - radius), min(1, center + radius))


@dataclass(frozen=True)
class Likelihoods:
    phone_sens: float; phone_spec: float
    pi_sens: float; pi_spec: float
    caliper_sens: float; caliper_spec: float
    phone_recapture_sens: float; phone_recapture_spec: float
    pi_recapture_sens: float; pi_recapture_spec: float
    caliper_retake_sens: float; caliper_retake_spec: float
    surface_prior: float
    dimensional_prior: float
    source: str
    calibration_id: str
    counts: dict = field(default_factory=dict, compare=False)
    intervals: dict = field(default_factory=dict, compare=False)

    def as_dict(self):
        return asdict(self)


def _rate(k, n):
    # Jeffreys-smoothed point estimate: keeps a finite calibration lot from producing an exact
    # 0 or 1 that would make a posterior degenerate. Intervals are reported unsmoothed.
    return (k + 0.5) / (n + 1.0)


def estimate_likelihoods(seeds=range(1000, 1010), n=1000, *, tolerance_mm=0.5, **scenario) -> Likelihoods:
    """Estimate every binary test's sensitivity/specificity and both axis priors on held-out
    synthetic lots generated with `scenario` (same kwargs as factory.seeded_scenario)."""
    from .factory import seeded_scenario  # local import: factory imports this module
    seed_values = [int(s) for s in seeds]
    if not seed_values or n < 1:
        raise ValueError('calibration needs at least one seed and one specimen')
    tests = {
        'phone': ('phone_suspect', 'surface_defect'),
        'pi': ('pi_suspect', 'surface_defect'),
        'phone_recapture': ('phone_recapture_suspect', 'surface_defect'),
        'pi_recapture': ('pi_recapture_suspect', 'surface_defect'),
        'caliper': ('measured_clearance', 'true_clearance'),
        'caliper_retake': ('retake_clearance', 'true_clearance'),
    }
    tp = {k: 0 for k in tests}; fn = {k: 0 for k in tests}; tn = {k: 0 for k in tests}; fp = {k: 0 for k in tests}
    surface_defects = dimensional_defects = total = 0
    for seed in seed_values:
        for r in seeded_scenario(n, seed, **scenario):
            total += 1
            surface_defects += int(r['surface_defect'])
            dimensional_defects += int(r['true_clearance'] < tolerance_mm)
            for name, (obs, truth) in tests.items():
                if truth == 'true_clearance':
                    flagged = r[obs] < tolerance_mm; bad = r[truth] < tolerance_mm
                else:
                    flagged = bool(r[obs]); bad = bool(r[truth])
                if bad and flagged: tp[name] += 1
                elif bad: fn[name] += 1
                elif flagged: fp[name] += 1
                else: tn[name] += 1
    est = {}; counts = {}; intervals = {}
    for name in tests:
        pos, neg = tp[name] + fn[name], tn[name] + fp[name]
        est[f'{name}_sens'] = _rate(tp[name], pos)
        est[f'{name}_spec'] = _rate(tn[name], neg)
        counts[name] = {'tp': tp[name], 'fn': fn[name], 'tn': tn[name], 'fp': fp[name]}
        intervals[f'{name}_sens'] = [round(x, 6) for x in wilson_interval(tp[name], pos)]
        intervals[f'{name}_spec'] = [round(x, 6) for x in wilson_interval(tn[name], neg)]
    counts['surface_defects'] = surface_defects
    counts['dimensional_defects'] = dimensional_defects
    counts['total'] = total
    intervals['surface_prior'] = [round(x, 6) for x in wilson_interval(surface_defects, total)]
    intervals['dimensional_prior'] = [round(x, 6) for x in wilson_interval(dimensional_defects, total)]
    payload = {'seeds': seed_values, 'n': n, 'tolerance_mm': tolerance_mm, 'scenario': dict(sorted(scenario.items())),
               'estimates': {k: round(v, 10) for k, v in sorted(est.items())}}
    cal_id = 'cal-' + sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
    return Likelihoods(
        **{k: round(v, 10) for k, v in est.items()},
        surface_prior=round(_rate(surface_defects, total), 10),
        dimensional_prior=round(_rate(dimensional_defects, total), 10),
        source='HELD_OUT_SYNTHETIC_CALIBRATION', calibration_id=cal_id,
        counts=counts, intervals=intervals,
    )
