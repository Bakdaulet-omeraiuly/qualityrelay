"""SIM experiment runner pieces: factorial grid, paired contrasts, API-shaped records (SIM-07)."""
from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor
from statistics import mean

from ..benchmark import paired_cluster_bootstrap_ci
from . import SOURCE_TIER, MODEL_VERSION
from .economics_sim import run_cost, modes
from .engine import run_factory, calibrate_part_model

CONFIGS = (('rules', 'fifo'), ('rules', 'optimized'), ('bayes', 'fifo'), ('bayes', 'optimized'))
BASELINE = ('rules', 'fifo')
PRODUCT = ('bayes', 'optimized')
FACTOR_CONTRASTS = ((PRODUCT, BASELINE, 'product configuration vs today'),
                    (('bayes', 'fifo'), BASELINE, 'policy effect (fifo pairing)'),
                    (('rules', 'optimized'), BASELINE, 'pairing effect (rules policy)'),
                    (PRODUCT, ('bayes', 'fifo'), 'pairing effect (bayes policy)'))
_MODEL = None


def cfg_name(cfg):
    return f'{cfg[0]}+{cfg[1]}'


def _cell(args):
    global _MODEL
    sc, seed, pol, pr = args
    if _MODEL is None:
        _MODEL = calibrate_part_model()
    out = run_factory(sc, seed, pol, pr, model=_MODEL, keep_log=(seed == 0))
    a = modes()
    platform = (pol, pr) != BASELINE and pol != 'hold_all'
    printers = sum(s.printers for s in sc.sites)
    c = run_cost(out, a, platform=platform, printers=printers,
                 inter_site_per_part=0.5 if len(sc.sites) > 1 else 0.0)
    out['cost_at_modes'] = c
    out['escapes_per_1000_shipped'] = 1000 * out['escaped'] / out['shipped'] if out['shipped'] else 0.0
    return (sc.sid, pol, pr, seed), out


def run_grid(scenarios, seeds, configs=CONFIGS, workers=None):
    jobs = [(sc, s, p, r) for sc in scenarios for (p, r) in configs for s in seeds]
    res = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for key, out in ex.map(_cell, jobs, chunksize=4):
            sid, p, r, s = key
            res.setdefault(sid, {}).setdefault((p, r), []).append(out)
    for sid in res:
        for cfg in res[sid]:
            res[sid][cfg].sort(key=lambda o: o['seed'])
    return res


METRICS = {
    'good_per_hour': lambda o: o['good_per_hour'],
    'escapes_per_1000_shipped': lambda o: o['escapes_per_1000_shipped'],
    'scrapped_good_parts': lambda o: o['scrapped_good_parts'],
    'holds': lambda o: o['part_holds'] + o['pair_holds'],
    'hold_inventory_part_hours': lambda o: o['hold_inventory_part_hours'],
    'operator_hours': lambda o: o['operator_seconds'] / 3600,
    'downtime_h': lambda o: o['downtime_s'] / 3600,
    'mean_cycle_s': lambda o: o['mean_cycle_s'],
    'cost_per_good_unit': lambda o: o['cost_at_modes']['cost_per_good_unit'],
    'profit_per_hour': lambda o: o['cost_at_modes']['profit_per_hour'],
}


def summarise(runs):
    return {k: mean(f(o) for o in runs) for k, f in METRICS.items()} | dict(
        conservation_ok=all(o['conservation_ok'] for o in runs), n_seeds=len(runs),
        stale_evidence_holds=mean(o['holds_stale_evidence'] for o in runs),
        local_reinspections=mean(o['local_reinspections'] for o in runs))


def contrast(runs_a, runs_b):
    if [o['seed'] for o in runs_a] != [o['seed'] for o in runs_b]:
        raise ValueError('unpaired')
    if any(x['truth_sha256'] != y['truth_sha256'] for x, y in zip(runs_a, runs_b)):
        raise ValueError('paired runs saw different parts')
    out = {}
    for k, f in METRICS.items():
        d = [f(x) - f(y) for x, y in zip(runs_a, runs_b)]
        out[k] = dict(mean=mean(d), ci95=paired_cluster_bootstrap_ci(d) if len(d) > 1 else [d[0], d[0]])
    base_gph = mean(METRICS['good_per_hour'](o) for o in runs_b)
    out['verdict'] = dict(
        safety_non_inferior=out['escapes_per_1000_shipped']['ci95'][1] <= 1.0,
        throughput_preserved=out['good_per_hour']['ci95'][0] >= -0.02 * base_gph,
        cheaper_per_good_unit=out['cost_per_good_unit']['ci95'][1] < 0)
    out['verdict']['better_on_all_three'] = all(out['verdict'].values())
    return out


def api_record(o, run_id, assumption_set='economics_sim.ASSUMPTIONS@modes'):
    """API-01 shape for adilnurgg's /simulation/* endpoints (schema: docs/research/sim_api/)."""
    keep = ('scenario', 'policy', 'pairing', 'makespan_s', 'shipped', 'shipped_good', 'escaped', 'good_per_hour',
            'mean_cycle_s', 'p95_cycle_s', 'part_holds', 'pair_holds', 'holds_stale_evidence', 'scrapped_parts',
            'hold_inventory_part_hours', 'downtime_s', 'conservation_ok', 'truth_sha256', 'calibration_id', 'cad_revision')
    return dict(source_tier=SOURCE_TIER, seed=o['seed'], model_version=MODEL_VERSION, run_id=run_id,
                assumption_set=assumption_set, **{k: o[k] for k in keep},
                cost_per_good_unit=o['cost_at_modes']['cost_per_good_unit'],
                profit_per_hour=o['cost_at_modes']['profit_per_hour'])
