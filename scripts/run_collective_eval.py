#!/usr/bin/env python
"""Run the registered Gate-A B0..B7 grid (docs/research/COLLECTIVE_GATE_A_REGISTRATION.md).

Writes examples/results/collective_gate_a/:
  manifest.json       commit, dirty flag, code hashes, seeds, belief model, verdicts
  S01.json .. S14.json full per-scenario output (summary, contrasts, per-seed records)
  summary.csv          one row per (scenario, policy)
  contrasts.csv        one row per (scenario, contrast)
  traces_S01.json, traces_S05.json, traces_S06.json   first parts of lot 0, message-level

Everything is origin=SIMULATED. Re-running on the same commit reproduces every file except the
manifest's timestamp/runtime fields.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, platform, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17.experiments.belief import calibrate_belief_model  # noqa: E402
from qualityrelay17.experiments.collective_eval import run_scenario  # noqa: E402
from qualityrelay17.experiments.scenarios import GRID, EXPLORATORY  # noqa: E402

TRACE_SCENARIOS = {'S01', 'S05', 'S06', 'S13', 'X01'}


def _git(*args):
    try:
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return 'UNKNOWN'


def _one(args):
    sc, seeds, n = args
    model = calibrate_belief_model()
    return sc.sid, run_scenario(sc, model, seeds=seeds, n=n, keep_traces=12 if sc.sid in TRACE_SCENARIOS else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=30)
    ap.add_argument('--n', type=int, default=1000)
    ap.add_argument('--out', default=None)
    ap.add_argument('--exploratory', action='store_true', help='run the post-hoc X.. scenarios instead of the registered grid')
    a = ap.parse_args()
    grid = EXPLORATORY if a.exploratory else GRID
    a.out = a.out or str(ROOT / 'examples' / 'results' / ('collective_gate_a_exploratory' if a.exploratory else 'collective_gate_a'))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    commit, dirty = _git('rev-parse', 'HEAD'), bool(_git('status', '--porcelain'))
    started = time.time()
    seeds = list(range(a.seeds))
    with ProcessPoolExecutor() as ex:
        results = dict(ex.map(_one, [(sc, seeds, a.n) for sc in grid]))
    summary_rows, contrast_rows, verdicts = [], [], {}
    for sc in grid:
        res, traces = results[sc.sid]
        (out / f'{sc.sid}.json').write_text(json.dumps(res, indent=1, sort_keys=True))
        if traces:
            (out / f'traces_{sc.sid}.json').write_text(json.dumps(dict(origin='SIMULATED', scenario=sc.sid, traces=traces), indent=1))
        for pol, s in res['summary'].items():
            summary_rows.append(dict(scenario=sc.sid, title=sc.title, policy=pol, **{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in s.items()}))
        for c in res['contrasts']:
            contrast_rows.append(dict(scenario=sc.sid, a=c['a'], b=c['b'], question=c['question'],
                                      cost_diff=round(c['cost_per_unit_diff'], 6), cost_ci=c['cost_per_unit_diff_ci95'],
                                      unsafe_diff=round(c['unsafe_pass_rate_diff'], 6), unsafe_ci=c['unsafe_pass_rate_diff_ci95'],
                                      good_diff=round(c['released_good_rate_diff'], 6), good_ci=c['released_good_rate_diff_ci95'],
                                      **c['verdict']))
        verdicts[sc.sid] = {f"{c['a']} vs {c['b']}": c['verdict'] for c in res['contrasts']}
    for name, rows in (('summary.csv', summary_rows), ('contrasts.csv', contrast_rows)):
        with open(out / name, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    code = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / 'qualityrelay17' / 'experiments').glob('*.py')) + [ROOT / 'qualityrelay17' / 'economics.py', ROOT / 'qualityrelay17' / 'factory.py', ROOT / 'qualityrelay17' / 'calibration.py', Path(__file__)]}
    first = verdicts[grid[0].sid]
    gate = all(first['B7_safe_mesh_voi vs B0_rules'].values()) and not a.exploratory
    manifest = dict(origin='SIMULATED', registration='docs/research/COLLECTIVE_GATE_A_REGISTRATION.md',
                    git_commit=commit, dirty_before_run=dirty, python=platform.python_version(),
                    started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)), runtime_s=round(time.time() - started, 1),
                    seeds=seeds, n_per_seed=a.n, calibration_seeds=list(range(1000, 1010)),
                    belief_model=calibrate_belief_model().as_dict(), scenarios=[sc.as_dict() for sc in grid],
                    exploratory=a.exploratory,
                    code_sha256=code, verdicts=verdicts,
                    research_gate=dict(S01_B7_beats_B0_on_all_three_rules=None if a.exploratory else gate,
                                       result='EXPLORATORY_NOT_A_GATE' if a.exploratory else ('POSITIVE_CANDIDATE (check ablations)' if gate else 'NEGATIVE at S01 -- see results doc')))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
    print(json.dumps(manifest['research_gate']), f"runtime {manifest['runtime_s']}s")


if __name__ == '__main__':
    main()
