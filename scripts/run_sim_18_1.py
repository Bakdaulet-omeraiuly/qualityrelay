#!/usr/bin/env python
"""Run the registered SIM-01..07 experiment (docs/research/SIM_18_1_REGISTRATION.md).

Writes examples/results/sim_18_1/: scenario_manifest.json, factory_summary.csv,
factory_contrasts.csv, roi.json, hold_all.json, scale.json, capacity_plan.json,
api/simulation_runs.json, charts/*.svg (+ the CSV each chart is drawn from).
Everything is SIMULATED. Same commit -> same files except manifest timestamps/runtime.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, platform, subprocess, sys, time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17.sim import charts, SOURCE_TIER, MODEL_VERSION  # noqa: E402
from qualityrelay17.sim.cad import cad_catalogue, nominal_design, adapter_status  # noqa: E402
from qualityrelay17.sim.economics_sim import roi_monte_carlo, derived_hold_cost, ASSUMPTIONS  # noqa: E402
from qualityrelay17.sim.engine import calibrate_part_model  # noqa: E402
from qualityrelay17.sim.experiment import (run_grid, summarise, contrast, api_record, cfg_name, CONFIGS, BASELINE,  # noqa: E402
                                           PRODUCT, FACTOR_CONTRASTS)
from qualityrelay17.sim.optimization import plan_capacity, solver_status  # noqa: E402
from qualityrelay17.sim.scenarios import GRID, MULTI, scale_scenario, BY_ID  # noqa: E402


def _git(*a):
    try:
        return subprocess.check_output(['git', *a], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return 'UNKNOWN'


def _csv(path, rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20)
    ap.add_argument('--scale-seeds', type=int, default=10)
    ap.add_argument('--out', default=str(ROOT / 'examples' / 'results' / 'sim_18_1'))
    a = ap.parse_args()
    out = Path(a.out); (out / 'charts').mkdir(parents=True, exist_ok=True); (out / 'api').mkdir(exist_ok=True)
    commit, dirty = _git('rev-parse', 'HEAD'), bool(_git('status', '--porcelain'))
    started = time.time()
    seeds = list(range(a.seeds))
    main_sc = list(GRID) + list(MULTI)
    res = run_grid(main_sc, seeds)
    hold_all = run_grid([BY_ID['F01']], seeds, configs=(('hold_all', 'fifo'),))['F01'][('hold_all', 'fifo')]
    scale_sc = [scale_scenario(k) for k in (6, 10, 50)]
    t0 = time.time()
    scale = run_grid(scale_sc, list(range(a.scale_seeds)), configs=(BASELINE, PRODUCT))
    scale_wall = time.time() - t0

    summary_rows, contrast_rows, roi, api_rows, truth = [], [], {}, [], {}
    for sc in main_sc:
        r = res[sc.sid]
        truth[sc.sid] = [o['truth_sha256'] for o in r[BASELINE]]
        for cfg in CONFIGS:
            summary_rows.append(dict(scenario=sc.sid, title=sc.title, config=cfg_name(cfg),
                                     **{k: round(v, 5) if isinstance(v, float) else v for k, v in summarise(r[cfg]).items()}))
            api_rows += [api_record(o, f'sim18.1/{sc.sid}/{cfg_name(cfg)}/s{o["seed"]}') for o in r[cfg]]
        for A, B, q in FACTOR_CONTRASTS:
            c = contrast(r[A], r[B])
            row = dict(scenario=sc.sid, a=cfg_name(A), b=cfg_name(B), question=q)
            for k in ('good_per_hour', 'escapes_per_1000_shipped', 'cost_per_good_unit', 'profit_per_hour',
                      'scrapped_good_parts', 'holds', 'hold_inventory_part_hours'):
                row[f'{k}_diff'] = round(c[k]['mean'], 5); row[f'{k}_ci95'] = c[k]['ci95']
            row.update(c['verdict'])
            contrast_rows.append(row)
        printers = sum(s.printers for s in sc.sites)
        roi[sc.sid] = roi_monte_carlo(r[BASELINE], r[PRODUCT], draws=2000, printers=printers)
        roi[sc.sid].pop('assumptions')
    _csv(out / 'factory_summary.csv', summary_rows)
    _csv(out / 'factory_contrasts.csv', contrast_rows)
    (out / 'roi.json').write_text(json.dumps(dict(status='SCENARIO_OUTCOME_NOT_MEASURED_SAVINGS', comparison=f'{cfg_name(PRODUCT)} vs {cfg_name(BASELINE)}',
                                                  assumptions={k: dict(low=v[0], mode=v[1], high=v[2], unit=v[3], note=v[4]) for k, v in ASSUMPTIONS.items()},
                                                  by_scenario=roi), indent=1, sort_keys=True, default=str))
    base_f01 = res['F01'][BASELINE]
    ha = dict(origin=SOURCE_TIER, scenario='F01', seeds=seeds, hold_all=summarise(hold_all), rules_fifo=summarise(base_f01),
              derived_hold_cost_at_modes=derived_hold_cost(),
              note='Gate-A B7 holds every part at registered prices; here every part goes through the real Review station.')
    (out / 'hold_all.json').write_text(json.dumps(ha, indent=1, sort_keys=True))
    sc_out = {}
    for sc in scale_sc:
        stations = int(sc.sid[2:])
        sc_out[sc.sid] = dict(stations=stations, n_pairs=sc.n_pairs, operators=sc.operators,
                              **{cfg_name(cfg): summarise(scale[sc.sid][cfg]) for cfg in (BASELINE, PRODUCT)},
                              product_vs_baseline=contrast(scale[sc.sid][PRODUCT], scale[sc.sid][BASELINE])['verdict'],
                              truth_sha256_seed0=scale[sc.sid][BASELINE][0]['truth_sha256'])
    (out / 'scale.json').write_text(json.dumps(dict(origin=SOURCE_TIER, tiers=sc_out), indent=1, sort_keys=True))
    cap = {str(t): plan_capacity(t) for t in (60, 120, 240, 480)}
    (out / 'capacity_plan.json').write_text(json.dumps(dict(origin=SOURCE_TIER, plans=cap), indent=1, sort_keys=True, default=str))
    (out / 'api' / 'simulation_runs.json').write_text(json.dumps(api_rows, indent=1, sort_keys=True))

    # ---- charts (+ the data table each is drawn from) ----
    label = lambda sid: f'{sid} {BY_ID[sid].title[:30]}'  # noqa: E731
    gph_rows = [(label(sc.sid), {cfg_name(BASELINE): summarise(res[sc.sid][BASELINE])['good_per_hour'],
                                 cfg_name(PRODUCT): summarise(res[sc.sid][PRODUCT])['good_per_hour']}) for sc in main_sc]
    (out / 'charts' / 'good_per_hour.svg').write_text(charts.dot_plot(
        gph_rows, [(cfg_name(BASELINE), 'rules + FIFO (today)', 1), (cfg_name(PRODUCT), 'bayes + optimised pairing', 2)],
        'Good assemblies per hour by scenario', 'good assemblies / hour (mean of 20 seeds)',
        'SIMULATED - toy generator, illustrative timings. Not a factory measurement.'))
    _csv(out / 'charts' / 'good_per_hour.csv', [dict(scenario=l, **d) for l, d in gph_rows])
    roi_rows = [(label(sid), r['delta_profit_per_hour']['p05'], r['delta_profit_per_hour']['p50'], r['delta_profit_per_hour']['p95'])
                for sid, r in roi.items()]
    (out / 'charts' / 'delta_profit_interval.svg').write_text(charts.interval_plot(
        roi_rows, 'Change in profit per hour, product vs today (90% interval)', 'delta profit / hour (cu), assumptions x seeds Monte Carlo',
        'SIMULATED SCENARIO OUTCOME - illustrative prices; not a measured or proven saving.'))
    _csv(out / 'charts' / 'delta_profit_interval.csv', [dict(scenario=l, p05=a_, p50=b_, p95=c_) for l, a_, b_, c_ in roi_rows])
    ha_rows = [('rules + FIFO', ha['rules_fifo']['good_per_hour']), ('hold everything (Gate-A B7)', ha['hold_all']['good_per_hour'])]
    (out / 'charts' / 'hold_all_throughput.svg').write_text(charts.bar_plot(
        ha_rows, 'Holding everything through a real review station (F01)', 'good assemblies / hour',
        'SIMULATED - one review station, 45 s per held part (illustrative).'))
    _csv(out / 'charts' / 'hold_all_throughput.csv', [dict(policy=l, good_per_hour=v) for l, v in ha_rows])
    sc_rows = [(f'{v["stations"]} stations', {cfg_name(BASELINE): v[cfg_name(BASELINE)]['good_per_hour'],
                                              cfg_name(PRODUCT): v[cfg_name(PRODUCT)]['good_per_hour']}) for v in sc_out.values()]
    (out / 'charts' / 'scale.svg').write_text(charts.dot_plot(
        sc_rows, [(cfg_name(BASELINE), 'rules + FIFO', 1), (cfg_name(PRODUCT), 'bayes + optimised', 2)],
        'Throughput by number of production stations', 'good assemblies / hour', 'SIMULATED - scale tiers SC06/SC10/SC50.'))
    _csv(out / 'charts' / 'scale.csv', [dict(tier=l, **d) for l, d in sc_rows])

    code = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / 'qualityrelay17' / 'sim').glob('*.py')) + [Path(__file__)]}
    manifest = dict(
        origin=SOURCE_TIER, model_version=MODEL_VERSION, registration='docs/research/SIM_18_1_REGISTRATION.md',
        git_commit=commit, dirty_before_run=dirty, python=platform.python_version(),
        started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)), runtime_s=round(time.time() - started, 1),
        scale_wall_s=round(scale_wall, 2), seeds=seeds, scale_seeds=list(range(a.scale_seeds)),
        scenarios={sc.sid: sc.as_dict() for sc in main_sc + scale_sc + [BY_ID['F01']]},
        truth_sha256_by_scenario_seed=truth, part_model=asdict(calibrate_part_model()),
        cad=dict(nominal=nominal_design(), catalogue=cad_catalogue()), adapters=adapter_status(), solvers=solver_status(),
        code_sha256=code, physical_calibration='NOT_AVAILABLE (no PHY-03 caliper records yet)')
    (out / 'scenario_manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True, default=str))
    print(f"done in {manifest['runtime_s']} s; dirty_before_run={dirty}")


if __name__ == '__main__':
    main()
