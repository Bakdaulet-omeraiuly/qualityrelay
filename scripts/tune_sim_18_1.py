#!/usr/bin/env python
"""Post-hoc tuning of the two SIM knobs the registered run flagged (SIM_18_1_RESULTS.md):
optimised-pairing batch size / timeout, and the SAFE-MESH evidence deadline under latency.

Honesty design (fixed before running, stated in the output):
- TUNE on seeds 100..119; EVALUATE the single chosen setting on the registered seeds 0..19.
- ONE global pairing setting for every scenario (no per-scenario tuning).
- Selection rule: among settings whose pooled escapes/1000 on the tuning seeds are <= those of
  bayes+FIFO (optimisation must not cost safety vs no optimisation), pick the highest mean good/h
  relative to bayes+FIFO, averaged over the tuning scenarios.
- The deadline sweep only reports the trade-off. The deadline is a SAFE-MESH policy owned by
  adilnurgg, so it is not chosen here.
Labelled EXPLORATORY_POST_HOC everywhere; it never replaces the registered result.
"""
from __future__ import annotations
import json, sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17.sim.experiment import _cell, contrast, summarise  # noqa: E402
from qualityrelay17.sim.scenarios import GRID, MULTI, BY_ID  # noqa: E402

TUNE_SEEDS = list(range(100, 120))
EVAL_SEEDS = list(range(20))
TUNE_SCEN = ['F01', 'F02', 'F03', 'F08', 'M01', 'M05']
SETTINGS = [dict(batch_k=k, pair_timeout_s=t) for k in (2, 4, 8) for t in (None, 60.0, 180.0, 600.0)]
DEADLINES = (120.0, 300.0, 600.0, 1200.0)


def grid(jobs):
    with ProcessPoolExecutor() as ex:
        return list(ex.map(_cell, jobs, chunksize=4))


def collect(results):
    d = {}
    for (sid, pol, pr, seed), out in results:
        d.setdefault(sid, []).append(out)
    for v in d.values():
        v.sort(key=lambda o: o['seed'])
    return d


def esc(runs):
    shipped = sum(o['shipped'] for o in runs)
    return 1000 * sum(o['escaped'] for o in runs) / shipped


def main():
    out = ROOT / 'examples' / 'results' / 'sim_18_1_tuning'
    out.mkdir(parents=True, exist_ok=True)
    scen = {s: BY_ID[s] for s in TUNE_SCEN}
    ref = collect(grid([(scen[s], seed, 'bayes', 'fifo') for s in TUNE_SCEN for seed in TUNE_SEEDS]))
    table = []
    for st in SETTINGS:
        r = collect(grid([(scen[s], seed, 'bayes', 'optimized', st) for s in TUNE_SCEN for seed in TUNE_SEEDS]))
        rel = mean(mean(o['good_per_hour'] for o in r[s]) / mean(o['good_per_hour'] for o in ref[s]) for s in TUNE_SCEN)
        e = esc([o for s in TUNE_SCEN for o in r[s]])
        table.append(dict(setting=st, good_per_hour_vs_bayes_fifo=rel, escapes_per_1000=e,
                          per_scenario_good_per_hour={s: mean(o['good_per_hour'] for o in r[s]) for s in TUNE_SCEN}))
    e_ref = esc([o for s in TUNE_SCEN for o in ref[s]])
    admissible = [t for t in table if t['escapes_per_1000'] <= e_ref]
    chosen = max(admissible, key=lambda t: t['good_per_hour_vs_bayes_fifo']) if admissible else None

    evaluation = {}
    if chosen:
        allsc = list(GRID) + list(MULTI)
        base = collect(grid([(sc, seed, 'rules', 'fifo') for sc in allsc for seed in EVAL_SEEDS]))
        tuned = collect(grid([(sc, seed, 'bayes', 'optimized', chosen['setting']) for sc in allsc for seed in EVAL_SEEDS]))
        for sc in allsc:
            c = contrast(tuned[sc.sid], base[sc.sid])
            evaluation[sc.sid] = dict(verdict=c['verdict'],
                                      good_per_hour_diff=c['good_per_hour'], escapes_per_1000_diff=c['escapes_per_1000_shipped'],
                                      cost_per_good_unit_diff=c['cost_per_good_unit'])

    # evidence deadline trade-off under latency (M04), registered seeds, report only
    dl = {}
    for d in DEADLINES:
        sc = replace(BY_ID['M04'], evidence_deadline_s=d)
        for cfg in (('rules', 'fifo'), ('bayes', 'fifo')):
            runs = collect(grid([(sc, seed, *cfg) for seed in EVAL_SEEDS]))['M04']
            s = summarise(runs)
            dl[f'{int(d)}s|{cfg[0]}+{cfg[1]}'] = dict(good_per_hour=s['good_per_hour'], escapes_per_1000=esc(runs),
                                                      stale_evidence_holds=s['stale_evidence_holds'], mean_cycle_s=s['mean_cycle_s'],
                                                      cost_per_good_unit=s['cost_per_good_unit'])
    res = dict(status='EXPLORATORY_POST_HOC', origin='SIMULATED', tune_seeds=TUNE_SEEDS, eval_seeds=EVAL_SEEDS,
               tune_scenarios=TUNE_SCEN, selection_rule=__doc__.split('Selection rule:')[1].split('- The deadline')[0].strip(),
               bayes_fifo_escapes_per_1000_on_tuning_seeds=e_ref, settings=table, chosen=chosen,
               evaluation_vs_rules_fifo=evaluation,
               better_on_all_three=sorted(k for k, v in evaluation.items() if v['verdict']['better_on_all_three']),
               deadline_tradeoff_M04=dl)
    (out / 'tuning.json').write_text(json.dumps(res, indent=1, sort_keys=True, default=str))
    print('chosen', chosen and chosen['setting'], 'better_on_all_three', res['better_on_all_three'])


if __name__ == '__main__':
    main()
