"""API-01: read-only /simulation/*, /benchmark/* and /economics/* routes over Bakdaulet's registered
simulator results (examples/results/). Every response carries the same provenance header:

  source_tier     always SIMULATED here -- nothing in these routes can produce VERIFIED_PHYSICAL
  seed / seeds    seed of a single run; for aggregates seed is null and seeds lists every seed pooled
  model_version   simulator/model identity that produced the numbers
  run_id          stable id of the run or aggregate (registered runs keep their SIM-07 run_id)
  assumption_set  which cost/scenario assumptions the numbers were computed under
  git_commit      commit the registered artifact was produced from (null for ad-hoc runs)

Artifacts are loaded from an allow-list of files, never from a request path. Non-finite floats
(e.g. payback p95 = Infinity, "never pays back") are returned as null so the JSON stays valid.
"""
from __future__ import annotations
import csv
import json
import math
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from .sim import SOURCE_TIER, MODEL_VERSION
from .sim.api_routes import RunRequest, run as _sim_run

RES = Path(__file__).resolve().parents[1] / 'examples' / 'results'
SIM = RES / 'sim_18_1'
GATE_A = RES / 'collective_gate_a'
WARP = RES / 'warp_mc' / 'cpu'
SIM_ASSUMPTIONS_MODES = 'economics_sim.ASSUMPTIONS@modes'
SIM_ASSUMPTIONS_MC = 'economics_sim.ASSUMPTIONS@triangular-MC'
PROVENANCE_KEYS = ('source_tier', 'seed', 'seeds', 'model_version', 'run_id', 'assumption_set', 'git_commit')

router = APIRouter(tags=['results-18.1 (API-01)'])


def provenance(*, run_id, model_version, assumption_set, seed=None, seeds=None, git_commit=None, **body):
    return dict(source_tier=SOURCE_TIER, seed=seed, seeds=list(seeds) if seeds is not None else ([seed] if seed is not None else []),
                model_version=model_version, run_id=run_id, assumption_set=assumption_set, git_commit=git_commit, **body)


def _finite(x):
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_finite(v) for v in x]
    return x


@lru_cache(maxsize=None)
def _json(path: Path):
    if not path.exists():
        raise HTTPException(404, f'result artifact not present: {path.relative_to(RES).as_posix()}')
    return _finite(json.loads(path.read_text()))


@lru_cache(maxsize=None)
def _csv(path: Path):
    if not path.exists():
        raise HTTPException(404, f'result artifact not present: {path.relative_to(RES).as_posix()}')
    with open(path, newline='') as fh:
        return tuple(csv.DictReader(fh))


def _sim_manifest():
    return _json(SIM / 'scenario_manifest.json')


def _sim_scenario(sid):
    m = _sim_manifest()
    if sid not in m['scenarios']:
        raise HTTPException(404, 'unknown scenario')
    return m


@lru_cache(maxsize=1)
def _runs():
    rows = _json(SIM / 'api' / 'simulation_runs.json')
    return rows, {r['run_id']: r for r in rows}


# ---- /simulation/* ------------------------------------------------------------------------------
@router.get('/simulation/scenarios')
def simulation_scenarios():
    m = _sim_manifest()
    return provenance(run_id='sim18.1/scenarios', model_version=m['model_version'], assumption_set=SIM_ASSUMPTIONS_MODES,
                      seeds=m['seeds'], git_commit=m['git_commit'], registration=m['registration'],
                      physical_calibration=m['physical_calibration'], scenarios=m['scenarios'])


@router.get('/simulation/runs')
def simulation_runs(scenario: str | None = None, policy: str | None = None, pairing: str | None = None,
                    seed: int | None = None, limit: int = Query(100, ge=1, le=2000), offset: int = Query(0, ge=0)):
    """Registered per-seed SIM-07 records (schema: docs/research/sim_api/simulation_response.schema.json)."""
    rows, _ = _runs()
    m = _sim_manifest()
    sel = [r for r in rows if (scenario is None or r['scenario'] == scenario) and (policy is None or r['policy'] == policy)
           and (pairing is None or r['pairing'] == pairing) and (seed is None or r['seed'] == seed)]
    return provenance(run_id='sim18.1/runs', model_version=m['model_version'], assumption_set=SIM_ASSUMPTIONS_MODES,
                      seed=seed, seeds=sorted({r['seed'] for r in sel}), git_commit=m['git_commit'],
                      total=len(sel), offset=offset, limit=limit, runs=sel[offset:offset + limit])


@router.get('/simulation/runs/{run_id:path}')
def simulation_run(run_id: str):
    _, by_id = _runs()
    if run_id not in by_id:
        raise HTTPException(404, 'unknown run_id')
    r = by_id[run_id]
    return dict(r, seeds=[r['seed']], git_commit=_sim_manifest()['git_commit'])


@router.get('/simulation/summary')
def simulation_summary(scenario: str | None = None):
    """Seed-averaged factory KPIs per scenario x configuration, plus the paired contrasts."""
    m = _sim_manifest() if scenario is None else _sim_scenario(scenario)
    pick = lambda rows: [dict(r) for r in rows if scenario is None or r['scenario'] == scenario]  # noqa: E731
    return provenance(run_id=f"sim18.1/summary/{scenario or 'all'}", model_version=m['model_version'],
                      assumption_set=SIM_ASSUMPTIONS_MODES, seeds=m['seeds'], git_commit=m['git_commit'],
                      summary=pick(_csv(SIM / 'factory_summary.csv')), contrasts=pick(_csv(SIM / 'factory_contrasts.csv')))


@router.get('/simulation/scale')
def simulation_scale():
    m = _sim_manifest()
    return provenance(run_id='sim18.1/scale', model_version=m['model_version'], assumption_set=SIM_ASSUMPTIONS_MODES,
                      seeds=m['scale_seeds'], git_commit=m['git_commit'], tiers=_json(SIM / 'scale.json')['tiers'])


@router.post('/simulation/run')
def simulation_run_adhoc(req: RunRequest):
    """Ad-hoc website run (same engine as /sim/run). Not part of the registered result set."""
    out = _sim_run(req)
    flags = ''.join(f for f, on in (('r', req.reprint), ('p', req.phone_only), ('2', req.two_lanes)) if on) or '-'
    return dict(out, seeds=[req.seed], assumption_set='economics.Costs@defaults', git_commit=None, registered=False,
                run_id=f'adhoc/{req.scenario}/{req.policy}+{req.pairing}/s{req.seed}/n{req.n_pairs}/{flags}')



# ---- /benchmark/* -------------------------------------------------------------------------------
def _gate_a_manifest():
    return _json(GATE_A / 'manifest.json')


def _gate_a_header(run_id, gm):
    return dict(run_id=run_id, model_version=f"collective-eval@{gm['git_commit'][:12]}",
                assumption_set=f"{gm['registration']}#scenario-costs", seeds=gm['seeds'], git_commit=gm['git_commit'])


@router.get('/benchmark/gate-a')
def benchmark_gate_a():
    gm = _gate_a_manifest()
    return provenance(**_gate_a_header('gate-a', gm), registration=gm['registration'], n_per_seed=gm['n_per_seed'],
                      belief_model=gm['belief_model'], research_gate=gm['research_gate'], verdicts=gm['verdicts'],
                      scenarios=gm['scenarios'])


@router.get('/benchmark/gate-a/{sid}')
def benchmark_gate_a_scenario(sid: str, per_seed: bool = False):
    gm = _gate_a_manifest()
    if sid not in gm['verdicts']:
        raise HTTPException(404, 'unknown scenario')
    g = _json(GATE_A / f'{sid}.json')
    body = dict(scenario=g['scenario'], n_per_seed=g['n_per_seed'], summary=g['summary'], contrasts=g['contrasts'],
                not_configured=g.get('not_configured', {}))
    if per_seed:
        body['per_seed'] = g['per_seed']
    return provenance(**_gate_a_header(f'gate-a/{sid}', gm), **body)


def _warp_manifest():
    return _json(WARP / 'manifest.json')


def _warp_header(run_id, wm):
    return dict(run_id=run_id, model_version=f"{wm['engine']}-{wm['warp_version']}@{wm['git_commit'][:12]}",
                assumption_set='warp_mc.scenario', seed=wm['seed'], git_commit=wm['git_commit'])


@router.get('/benchmark/warp')
def benchmark_warp():
    wm = _warp_manifest()
    rows = []
    for p in sorted(WARP.glob('S*.json')):
        w = _json(p)
        rows.append(dict(sid=w['scenario']['sid'], title=w['scenario']['title'], parts=w['parts'],
                         unsafe_pass_rate={k: v['unsafe_pass_rate'] for k, v in w['policies'].items()},
                         parts_per_second=w['parts_per_second']))
    return provenance(**_warp_header('warp-mc/cpu', wm), device=wm['device'], is_cuda=wm['is_cuda'],
                      parts_per_scenario=wm['parts_per_scenario'], scenarios=rows)


@router.get('/benchmark/warp/{sid}')
def benchmark_warp_scenario(sid: str):
    wm = _warp_manifest()
    path = WARP / f'{sid}.json'
    if not sid.startswith('S') or path not in set(WARP.glob('S*.json')):
        raise HTTPException(404, 'unknown scenario')
    w = _json(path)
    return provenance(**_warp_header(f'warp-mc/cpu/{sid}', wm), scenario=w['scenario'], parts=w['parts'],
                      lots=w['lots'], policies=w['policies'], paired_vs_B0=w['paired_vs_B0'],
                      truly_safe_rate=w['truly_safe_rate'], parts_per_second=w['parts_per_second'])


# ---- /economics/* -------------------------------------------------------------------------------
def _roi():
    return _json(SIM / 'roi.json')


def _econ_header(run_id, seeds=None, assumption_set=SIM_ASSUMPTIONS_MC):
    m = _sim_manifest()
    return dict(run_id=run_id, model_version=m['model_version'], assumption_set=assumption_set,
                seeds=m['seeds'] if seeds is None else seeds, git_commit=m['git_commit'])


@router.get('/economics/assumptions')
def economics_assumptions():
    r = _roi()
    return provenance(**_econ_header('sim18.1/economics/assumptions'), status='ILLUSTRATIVE_ASSUMPTIONS',
                      assumptions=r['assumptions'])


@router.get('/economics/roi')
def economics_roi():
    r = _roi()
    keep = ('delta_profit_per_hour', 'annual_delta_profit', 'roi_over_life', 'payback_months', 'p_qr_worse',
            'p_payback_within_12_months', 'draws')
    return provenance(**_econ_header('sim18.1/economics/roi'), status=r['status'], comparison=r['comparison'],
                      null_means='non-finite (e.g. payback p95 = never pays back within the draw)',
                      by_scenario={sid: {k: v.get(k) for k in keep} for sid, v in r['by_scenario'].items()})


@router.get('/economics/roi/{sid}')
def economics_roi_scenario(sid: str):
    r = _roi()
    if sid not in r['by_scenario']:
        raise HTTPException(404, 'unknown scenario')
    v = r['by_scenario'][sid]
    body = {'status': r['status'], **{k: x for k, x in v.items() if k != 'seeds'}}
    return provenance(**_econ_header(f'sim18.1/economics/roi/{sid}', seeds=v.get('seeds')), comparison=r['comparison'],
                      scenario=sid, null_means='non-finite (e.g. payback p95 = never pays back within the draw)', **body)


@router.get('/economics/hold-all')
def economics_hold_all():
    h = _json(SIM / 'hold_all.json')
    return provenance(**_econ_header('sim18.1/economics/hold-all', seeds=h['seeds'], assumption_set=SIM_ASSUMPTIONS_MODES),
                      **{k: v for k, v in h.items() if k not in ('origin', 'seeds')})


@router.get('/economics/capacity-plan')
def economics_capacity_plan():
    c = _json(SIM / 'capacity_plan.json')
    return provenance(**_econ_header('sim18.1/economics/capacity-plan', seeds=[],
                                           assumption_set='capacity_plan.plans[*].assumptions (ILLUSTRATIVE)'), plans=c['plans'])


def legacy_provenance(out: dict, *, run_id: str, assumption_set: str) -> dict:
    """Add the API-01 header to the 17.x reference simulators (/simulation/compare, /factory-line)."""
    return dict(out, source_tier=out.get('origin', SOURCE_TIER), seeds=[out['seed']],
                model_version=out.get('generator', 'unknown'), run_id=run_id, assumption_set=assumption_set,
                git_commit=None)


__all__ = ['router', 'provenance', 'legacy_provenance', 'PROVENANCE_KEYS', 'MODEL_VERSION']
