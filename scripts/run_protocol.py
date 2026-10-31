#!/usr/bin/env python
"""Run the pre-registered 31 Oct synthetic protocol (docs/research/PROTOCOL_REGISTRATION_31OCT.md).

Writes examples/results/protocol_31oct/:
  manifest.json      -- commit, timestamp, code hashes, grid, seeds, costs, decision-rule verdicts
  S01.json ... S13.json -- full run_benchmark output per scenario (incl. per-seed records)
  summary.csv        -- one row per (scenario, policy)
  paired.csv         -- one row per (scenario, comparison, metric) with CI

Everything is origin=SIMULATED. Re-running on the same commit reproduces the files exactly.
"""
from __future__ import annotations
import csv, hashlib, json, platform, subprocess, sys, time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17.benchmark import run_benchmark, ALIASES  # noqa: E402
from qualityrelay17.calibration import estimate_likelihoods  # noqa: E402
from qualityrelay17.economics import Costs, INDUSTRY_GROUNDED_COSTS  # noqa: E402
from qualityrelay17.factory import LIKELIHOODS_PLACEHOLDER_17_0, POLICIES  # noqa: E402

TEST_SEEDS = range(0, 30)
CAL_SEEDS = range(1000, 1010)
N = 1000
BASE = dict(shift=0.10, camera_noise=0.04, shared_camera_noise=0.0, network_outage=0.05)

# Fixed in the registration document. Do not edit after the run.
GRID = {
    'S01': ('baseline', dict(BASE)),
    'S02': ('no shift', dict(BASE, shift=0.0)),
    'S03': ('large shift', dict(BASE, shift=0.20)),
    'S04': ('noisier cameras', dict(BASE, camera_noise=0.10)),
    'S05': ('very noisy cameras', dict(BASE, camera_noise=0.15)),
    'S06': ('correlated cameras', dict(BASE, shared_camera_noise=0.05)),
    'S07': ('strongly correlated cameras', dict(BASE, shared_camera_noise=0.15)),
    'S08': ('outage-heavy', dict(BASE, network_outage=0.20)),
    'S09': ('shift + noise', dict(BASE, shift=0.20, camera_noise=0.10)),
    'S10': ('noise + correlation', dict(BASE, camera_noise=0.10, shared_camera_noise=0.10)),
    'S11': ('placeholder likelihoods (mis-specification ablation)', dict(BASE)),
    'S12': ('calibration drift: S01 calibration applied to S04 conditions', dict(BASE, camera_noise=0.10)),
    'S13': ('industry cost ratios', dict(BASE)),
}

# Decision rules, verbatim from the registration.
SAFETY_MARGIN = 0.001
THROUGHPUT_MARGIN = -0.01


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args):
    try:
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return 'UNKNOWN'


def verdict(out, alias='voi'):
    unsafe_ci = out[f'paired_unsafe_pass_rate_{alias}_minus_rules_cluster_bootstrap_95']
    cost_ci = out[f'paired_cost_difference_{alias}_minus_rules_cluster_bootstrap_95']
    rel_ci = out[f'paired_released_good_rate_{alias}_minus_rules_cluster_bootstrap_95']
    return {
        'non_inferior_on_safety': unsafe_ci[1] <= SAFETY_MARGIN,
        'cheaper': cost_ci[1] < 0,
        'throughput_preserved': rel_ci[0] >= THROUGHPUT_MARGIN,
        'unsafe_ci': unsafe_ci, 'cost_ci': cost_ci, 'released_good_ci': rel_ci,
    }


def main(out_dir: Path = ROOT / 'examples' / 'results' / 'protocol_31oct'):
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    # Record tree state BEFORE this run writes anything, otherwise the run's own output
    # files make every run look dirty.
    git_commit, git_dirty = _git('rev-parse', 'HEAD'), bool(_git('status', '--porcelain'))
    timings = {}
    s01_cal = estimate_likelihoods(seeds=CAL_SEEDS, n=N, process_shift_mm=BASE['shift'], camera_noise=BASE['camera_noise'],
                                   network_outage=BASE['network_outage'], shared_camera_noise=BASE['shared_camera_noise'])
    summary_rows, paired_rows, verdicts = [], [], {}
    for sid, (label, params) in GRID.items():
        kwargs = dict(seeds=TEST_SEEDS, n_per_seed=N, calibration_seeds=CAL_SEEDS, **params)
        if sid == 'S11':
            kwargs['likelihoods'] = LIKELIHOODS_PLACEHOLDER_17_0
        elif sid == 'S12':
            kwargs['likelihoods'] = s01_cal
        elif sid == 'S13':
            kwargs['costs'] = INDUSTRY_GROUNDED_COSTS
        t0 = time.time()
        out = run_benchmark(**kwargs)
        out['scenario_id'] = sid
        out['scenario_label'] = label
        timings[sid] = round(time.time() - t0, 2)  # kept out of S*.json so results stay byte-reproducible
        (out_dir / f'{sid}.json').write_text(json.dumps(out, indent=1, sort_keys=True))
        verdicts[sid] = {'voi_driven': verdict(out, 'voi'), 'entropy_driven': verdict(out, 'entropy'),
                         'collective_fusion': verdict(out, 'fusion')}
        for policy, s in out['summary'].items():
            summary_rows.append({'scenario': sid, 'label': label, 'policy': policy, **{k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in s.items()}})
        for key, val in out.items():
            if key.startswith('paired_') and not key.endswith('_95') and isinstance(val, float):
                ci_key = next((k for k in out if k.endswith('_cluster_bootstrap_95') and k.replace('_cluster_bootstrap_95', '').replace('_rate_', '_rate_difference_') == key), None)
                ci = out.get(ci_key) if ci_key else None
                paired_rows.append({'scenario': sid, 'comparison': key, 'mean_difference': val,
                                    'ci95_low': ci[0] if ci else '', 'ci95_high': ci[1] if ci else ''})
        print(f'{sid} {label}: {timings[sid]}s  voi={verdicts[sid]["voi_driven"]}', flush=True)

    with (out_dir / 'summary.csv').open('w', newline='') as fh:
        keys = sorted({k for r in summary_rows for k in r}, key=lambda k: (k not in ('scenario', 'label', 'policy'), k))
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(summary_rows)
    with (out_dir / 'paired.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['scenario', 'comparison', 'mean_difference', 'ci95_low', 'ci95_high']); w.writeheader(); w.writerows(paired_rows)

    manifest = {
        'origin': 'SIMULATED',
        'protocol': 'docs/research/PROTOCOL_REGISTRATION_31OCT.md',
        'protocol_sha256': _sha(ROOT / 'docs' / 'research' / 'PROTOCOL_REGISTRATION_31OCT.md'),
        'git_commit': git_commit,
        'git_dirty_before_run': git_dirty,
        'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)),
        'elapsed_s': round(time.time() - started, 1),
        'elapsed_s_by_scenario': timings,
        'python': sys.version.split()[0], 'platform': platform.platform(),
        'code_sha256': {f: _sha(ROOT / 'qualityrelay17' / f) for f in ('factory.py', 'vder.py', 'benchmark.py', 'calibration.py', 'economics.py')},
        'test_seeds': list(TEST_SEEDS), 'calibration_seeds': list(CAL_SEEDS), 'n_per_seed': N,
        'policies': list(POLICIES), 'aliases': ALIASES,
        'costs_default': asdict(Costs()), 'costs_industry': asdict(INDUSTRY_GROUNDED_COSTS),
        'grid': {sid: {'label': label, **params} for sid, (label, params) in GRID.items()},
        'decision_rules': {'safety_margin_upper_ci': SAFETY_MARGIN, 'cost_ci_entirely_below_zero': True,
                           'throughput_lower_ci_at_least': THROUGHPUT_MARGIN},
        'verdicts': verdicts,
        'analysis_status': 'PRE_REGISTERED',
        'hardware': 'laptop CPU, no GPU, no cloud',
    }
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
    print(f'wrote {out_dir} in {manifest["elapsed_s"]}s; commit {manifest["git_commit"]} dirty_before_run={manifest["git_dirty_before_run"]}')


if __name__ == '__main__':
    main()
