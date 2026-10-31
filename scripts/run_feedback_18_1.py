#!/usr/bin/env python
"""I1/I6: closed-loop printer correction vs none (docs/research/INNOVATIONS_REGISTRATION_31OCT.md)."""
from __future__ import annotations
import json, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qualityrelay17.sim.experiment import _cell, contrast, summarise  # noqa: E402
from qualityrelay17.sim.scenarios import BY_ID  # noqa: E402

SCEN, SEEDS = ['F01', 'F02', 'F03', 'M05'], list(range(20))


def main():
    out = ROOT / 'examples' / 'results' / 'innovations_31oct'; out.mkdir(parents=True, exist_ok=True)
    jobs = [(BY_ID[s], seed, 'bayes', 'fifo', dict(feedback=fb)) for s in SCEN for fb in ('none', 'ewma') for seed in SEEDS]
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(_cell, jobs, chunksize=4))
    by = {}
    for (job, (key, o)) in zip(jobs, res):
        by.setdefault((job[0].sid, job[4]['feedback']), []).append(o)
    report = {}
    for s in SCEN:
        a, b = sorted(by[(s, 'ewma')], key=lambda o: o['seed']), sorted(by[(s, 'none')], key=lambda o: o['seed'])
        c = contrast(a, b)
        report[s] = dict(title=BY_ID[s].title, ewma=summarise(a), none=summarise(b),
                         diff={k: v for k, v in c.items() if k != 'verdict'}, verdict=c['verdict'],
                         corrections_mean=mean(o['corrections'] for o in a), cusum_alarms_mean=mean(o['cusum_alarms'] for o in b),
                         first_alarm_s_median=sorted(o['first_alarm_s'] or 1e9 for o in b)[len(b) // 2])
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    (out / 'feedback.json').write_text(json.dumps(dict(origin='SIMULATED', registration='docs/research/INNOVATIONS_REGISTRATION_31OCT.md',
                                                       git_commit=commit, dirty_before_run=dirty, seeds=SEEDS, results=report), indent=1, sort_keys=True, default=str))
    for s, r in report.items():
        print(s, r['verdict'], 'gph', round(r['diff']['good_per_hour']['mean'], 1), r['diff']['good_per_hour']['ci95'], 'esc', round(r['diff']['escapes_per_1000_shipped']['mean'], 2),
              'scrapGood', round(r['diff']['scrapped_good_parts']['mean'], 2), 'corr', r['corrections_mean'], 'alarm@', r['first_alarm_s_median'])


if __name__ == '__main__':
    main()
