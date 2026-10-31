"""Physical caliper data (HyorinmaruK's measurement logger) -> simulator calibration + photo check.

Input: the tidy CSV written by web/measurement_logger.html (schema in
docs/engineering/MEASUREMENT_LOGGING.md: one row per reading). The functional width of a part is
`slot_inner_width` for slots and `width` for tabs, exactly what sim/cad.py measures on the meshes.

What it estimates, per part kind, from readings whose evidence tier is physical
(OPERATOR_CONFIRMED or PHYSICAL_CAPTURE):
- process bias  = mean over specimens of (specimen mean - its design nominal)
- between-specimen sd of that deviation (the printer's width scatter)
- caliper repeatability = pooled within-specimen sd of repeated readings at one location

Those three numbers replace the simulator's assumed printer bias, width scatter and caliper sigma
(`physical_scenario`). Runs with them are still SIMULATED: physically CALIBRATED, not physical results.

Photo check: joins the Studio capture log (data/prints/capture_log.csv) on specimen_id and reports
photo width - caliper width per specimen. The caliper stays authoritative (AGENTS.md); the photo
number is evaluated, never substituted.
"""
from __future__ import annotations
import csv
from dataclasses import replace
from pathlib import Path
from statistics import mean, stdev, pvariance

PHYSICAL_TIERS = {'OPERATOR_CONFIRMED', 'PHYSICAL_CAPTURE', 'VERIFIED_PHYSICAL'}
FUNCTIONAL = {'slot': 'slot_inner_width', 'tab': 'width'}
DESIGN_NOMINAL = {'S-GOOD': 21.20, 'S-NOM': 21.00, 'S-RISK': 20.70, 'S-DEF': 19.40,
                  'T-GOOD': 19.80, 'T-NOM': 20.00, 'T-RISK': 20.30, 'T-DEF': 21.60}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_measurements(paths) -> list[dict]:
    rows = []
    for p in ([paths] if isinstance(paths, (str, Path)) else paths):
        with open(p, newline='', encoding='utf-8-sig') as fh:
            rows += list(csv.DictReader(fh))
    return rows


def functional_readings(rows):
    """{specimen_id: dict(kind, nominal, readings{location: [values]})} for physical-tier functional widths."""
    out = {}
    for r in rows:
        kind = (r.get('part_type') or '').strip()
        if kind not in FUNCTIONAL or (r.get('feature') or '').strip() != FUNCTIONAL[kind]:
            continue
        if (r.get('evidence_tier') or '').strip() not in PHYSICAL_TIERS:
            continue
        v = _f(r.get('value_mm'))
        if v is None:
            continue
        sid = (r.get('specimen_id') or '').strip()
        nominal = _f(r.get('nominal_mm')) or DESIGN_NOMINAL.get((r.get('manual_id') or '').strip())
        d = out.setdefault(sid, dict(kind=kind, nominal=nominal, manual_id=(r.get('manual_id') or '').strip(), readings={}))
        d['readings'].setdefault((r.get('location') or 'overall').strip(), []).append(v)
    return out


def calibrate(rows) -> dict:
    spec = functional_readings(rows)
    fits, table = {}, []
    within = []
    for sid, d in sorted(spec.items()):
        vals = [v for vs in d['readings'].values() for v in vs]
        m = mean(vals)
        for vs in d['readings'].values():
            if len(vs) >= 2:
                within.append((len(vs) - 1, pvariance(vs) * len(vs) / (len(vs) - 1)))
        table.append(dict(specimen_id=sid, manual_id=d['manual_id'], kind=d['kind'], n=len(vals), mean_mm=round(m, 4),
                          nominal_mm=d['nominal'], deviation_mm=None if d['nominal'] is None else round(m - d['nominal'], 4),
                          spread_mm=round(max(vals) - min(vals), 4)))
    caliper_sd = (sum(df * v for df, v in within) / sum(df for df, _ in within)) ** 0.5 if within else None
    for kind in ('slot', 'tab'):
        devs = [t['deviation_mm'] for t in table if t['kind'] == kind and t['deviation_mm'] is not None]
        if len(devs) >= 2:
            sd = stdev(devs)
            between = max(0.0, sd ** 2 - (caliper_sd or 0) ** 2) ** 0.5
            fits[kind] = dict(n_specimens=len(devs), bias_mm=round(mean(devs), 4), width_sd_mm=round(between, 4))
    status = 'FITTED_FROM_PHYSICAL_RECORDS' if fits else ('INSUFFICIENT' if table else 'NOT_AVAILABLE')
    return dict(status=status, specimens=table, fits=fits, caliper_repeatability_sd_mm=None if caliper_sd is None else round(caliper_sd, 4),
                note='Simulator parameters only; runs with them remain SIMULATED (physically calibrated).')


def physical_scenario(sc, cal: dict):
    """Copy of a FactoryScenario whose single site uses the measured bias / scatter / caliper sigma.
    The engine has one bias per site, so the slot and tab biases are applied as their mean; the
    per-kind values are reported alongside."""
    if cal.get('status') != 'FITTED_FROM_PHYSICAL_RECORDS':
        raise ValueError('no physical fit available')
    f = cal['fits']
    biases = [f[k]['bias_mm'] for k in f]; sds = [f[k]['width_sd_mm'] for k in f]
    site = replace(sc.sites[0], printer_bias_mm=round(mean(biases), 4), width_sd_mm=round(max(0.01, mean(sds)), 4),
                   caliper_sd_mm=round(cal['caliper_repeatability_sd_mm'] or sc.sites[0].caliper_sd_mm, 4))
    return replace(sc, sid=sc.sid + '-PHYS', title=sc.title + ' (physically calibrated)', sites=(site,) + tuple(sc.sites[1:]))


def photo_vs_caliper(rows, capture_log) -> list[dict]:
    """Per specimen: Studio photo-measured width vs the caliper mean (functional width)."""
    spec = functional_readings(rows)
    if not Path(capture_log).exists():
        return []
    out = []
    with open(capture_log, newline='') as fh:
        for r in csv.DictReader(fh):
            sid = (r.get('specimen_id') or '').strip(); pw = _f(r.get('photo_width_mm'))
            if sid in spec and pw is not None:
                cal_mean = mean(v for vs in spec[sid]['readings'].values() for v in vs)
                out.append(dict(specimen_id=sid, file=r.get('file'), photo_mm=pw, caliper_mm=round(cal_mean, 4),
                                photo_minus_caliper_mm=round(pw - cal_mean, 4), photo_px_per_mm=_f(r.get('photo_px_per_mm'))))
    return out
