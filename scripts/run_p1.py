"""P1 runner: decentralised agents vs a central raw-evidence server (docs/research/P1_DECENTRALISATION_REGISTRATION.md).

    python scripts/run_p1.py            # writes examples/results/p1_decentralisation/
Everything is SIMULATED.
"""
import json, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from statistics import mean
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qualityrelay17.benchmark import paired_cluster_bootstrap_ci
from qualityrelay17.sim.engine import run_factory, calibrate_part_model
from qualityrelay17.sim.economics_sim import run_cost, modes
from qualityrelay17.sim.scenarios import BY_ID

SEEDS, N_PAIRS = range(20), 200
SCEN = {  # id: (uplink Mbit/s, outages, frame bytes)
    'P1-S0': (100.0, (), 2_000_000), 'P1-D1a': (20.0, (), 2_000_000), 'P1-D1b': (4.0, (), 2_000_000),
    'P1-D1c': (2.0, (), 2_000_000), 'P1-D2': (20.0, ((1800.0, 3600.0),), 2_000_000), 'P1-D1b-small': (4.0, (), 500_000),
}
ARMS = {'A0_isolated': ('rules', 'fifo', dict()), 'A1_central': ('bayes', 'optimized', dict(architecture='central')),
        'A2_agents': ('bayes', 'optimized', dict(agents=True))}
_M = None


def cell(args):
    global _M
    sid, arm, seed = args
    if _M is None:
        _M = calibrate_part_model()
    mbps, outages, fbytes = SCEN[sid]
    pol, pr, kw = ARMS[arm]
    if kw.get('architecture') == 'central':
        kw = dict(kw, uplink_mbps=mbps, central_outages=outages, image_bytes=fbytes)
    sc = replace(BY_ID['F01'], n_pairs=N_PAIRS)  # registered SIM camera set: phone + Pi
    o = run_factory(sc, seed, pol, pr, model=_M, keep_log=False, **kw)
    o['cost_at_modes'] = run_cost(o, modes(), platform=(arm != 'A0_isolated'), printers=4)
    o['esc1000'] = 1000 * o['escaped'] / o['shipped'] if o['shipped'] else 0.0
    return sid, arm, seed, {k: o[k] for k in ('good_per_hour', 'esc1000', 'part_holds', 'pair_holds', 'holds_stale_evidence',
                                               'holds_missing_central', 'mean_cycle_s', 'net_bytes', 'parts', 'truth_sha256',
                                               'mean_evidence_latency_s', 'shipped', 'escaped', 'conservation_ok')} | dict(
        cost_per_good_unit=o['cost_at_modes']['cost_per_good_unit'])


M = {'good_per_hour': lambda o: o['good_per_hour'], 'escapes_per_1000_shipped': lambda o: o['esc1000'],
     'holds': lambda o: o['part_holds'] + o['pair_holds'],
     'holds_missing_or_late': lambda o: o['holds_stale_evidence'] + o['holds_missing_central'],
     'mean_cycle_s': lambda o: o['mean_cycle_s'], 'bytes_per_part': lambda o: o['net_bytes'] / o['parts'],
     'evidence_latency_s': lambda o: o['mean_evidence_latency_s'], 'cost_per_good_unit': lambda o: o['cost_per_good_unit']}


def contrast(a, b):
    assert [x['truth_sha256'] for x in a] == [x['truth_sha256'] for x in b], 'unpaired parts'
    out = {}
    for k, f in M.items():
        d = [f(x) - f(y) for x, y in zip(a, b)]
        lo, hi = paired_cluster_bootstrap_ci(d)
        out[k] = dict(mean=mean(d), lo=lo, hi=hi)
    return out


def main():
    t0 = time.time()
    jobs = [(s, a, seed) for s in SCEN for a in ARMS for seed in SEEDS]
    res = {}
    with ProcessPoolExecutor() as ex:
        for sid, arm, seed, o in ex.map(cell, jobs, chunksize=4):
            res.setdefault(sid, {}).setdefault(arm, []).append((seed, o))
    for sid in res:
        for arm in res[sid]:
            res[sid][arm] = [o for _s, o in sorted(res[sid][arm])]
    out = {'origin': 'SIMULATED', 'registration': 'docs/research/P1_DECENTRALISATION_REGISTRATION.md',
           'git': subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
           'dirty_before_run': bool(subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.strip()),
           'seeds': list(SEEDS), 'n_pairs': N_PAIRS, 'scenarios': {k: dict(uplink_mbps=v[0], outages=v[1], frame_bytes=v[2]) for k, v in SCEN.items()},
           'results': {}}
    for sid in SCEN:
        R = res[sid]
        means = {arm: {k: mean(f(o) for o in R[arm]) for k, f in M.items()} | dict(conservation_ok=all(o['conservation_ok'] for o in R[arm]))
                 for arm in ARMS}
        c21, c20 = contrast(R['A2_agents'], R['A1_central']), contrast(R['A2_agents'], R['A0_isolated'])
        safe = c21['escapes_per_1000_shipped']['hi'] <= 1.0
        pays = safe and c21['good_per_hour']['lo'] > 0
        out['results'][sid] = dict(means=means, A2_minus_A1=c21, A2_minus_A0=c20,
                                   verdict=dict(safety_ok=safe, decentralisation_pays=pays))
    p = Path('examples/results/p1_decentralisation'); p.mkdir(parents=True, exist_ok=True)
    (p / 'results.json').write_text(json.dumps(out, indent=1, default=float))
    print(f'done in {time.time() - t0:.1f}s')
    for sid, r in out['results'].items():
        m, c = r['means'], r['A2_minus_A1']
        print(f"{sid:13s} good/h A0 {m['A0_isolated']['good_per_hour']:.1f} A1 {m['A1_central']['good_per_hour']:.1f} A2 {m['A2_agents']['good_per_hour']:.1f} | "
              f"d good/h {c['good_per_hour']['mean']:+.1f} [{c['good_per_hour']['lo']:+.1f},{c['good_per_hour']['hi']:+.1f}] "
              f"d esc {c['escapes_per_1000_shipped']['mean']:+.2f} [{c['escapes_per_1000_shipped']['lo']:+.2f},{c['escapes_per_1000_shipped']['hi']:+.2f}] "
              f"bytes/part A1 {m['A1_central']['bytes_per_part']/1e6:.2f}MB A2 {m['A2_agents']['bytes_per_part']:.0f}B "
              f"lat {m['A1_central']['evidence_latency_s']:.0f}s missing A1 {m['A1_central']['holds_missing_or_late']:.1f} -> {r['verdict']}")


if __name__ == '__main__':
    main()
