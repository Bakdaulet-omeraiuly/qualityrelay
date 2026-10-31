"""18.1 SIM-01..07 verification: conservation, determinism, CRN, safety gates, optimality."""
import itertools
import json
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

from qualityrelay17.sim import charts
from qualityrelay17.sim.cad import cad_catalogue, nominal_design, calibrate_from_caliper, adapter_status
from qualityrelay17.sim.des import Env
from qualityrelay17.sim.economics_sim import run_cost, roi_monte_carlo, modes, derived_hold_cost
from qualityrelay17.sim.engine import Factory, run_factory, calibrate_part_model, POLICIES
from qualityrelay17.sim.experiment import contrast, api_record, _cell
from qualityrelay17.sim.optimization import match_batch, match_value, plan_capacity, _pair_cost
from qualityrelay17.sim.scenarios import GRID, MULTI, BY_ID, scale_scenario

MODEL = calibrate_part_model(n=200)
SMALL = 60
SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'docs/research/sim_api/simulation_response.schema.json').read_text())


def small(sid, **kw):
    return replace(BY_ID[sid], n_pairs=SMALL, **kw)


def run(sc, policy='bayes', pairing='fifo', seed=1, **kw):
    return run_factory(sc, seed, policy, pairing, model=MODEL, **kw)


# ---- SIM-03 CAD ----------------------------------------------------------------------------
def test_cad_widths_are_measured_from_meshes_and_match_the_design_names():
    widths = {c['file']: c['functional_width_mm'] for c in cad_catalogue()}
    for f, w in widths.items():
        named = float(f.rsplit('_', 1)[1].replace('.stl', '').replace('p', '.'))
        assert w == pytest.approx(named, abs=1e-6), f
    assert nominal_design()['design_clearance_mm'] == pytest.approx(1.0)


def test_physical_calibration_never_accepts_simulated_records():
    sim = [dict(source_tier='SIMULATED', kind='slot', width_mm=21.0)] * 5
    assert calibrate_from_caliper(sim)['status'] == 'NOT_AVAILABLE'
    phys = [dict(source_tier='PHYSICAL_CAPTURE', kind='slot', width_mm=w) for w in (21.01, 20.98, 21.03)]
    out = calibrate_from_caliper(phys + sim)
    assert out['status'] == 'FITTED_FROM_PHYSICAL_RECORDS' and out['rejected_non_physical'] == 5
    assert all(v in ('NOT_CONFIGURED', 'INSTALLED_NOT_WIRED', 'WORKING') for v in adapter_status().values())


# ---- DES core --------------------------------------------------------------------------------
def test_des_never_exceeds_capacity_and_replays_identically():
    def trace():
        env = Env(); r = env.resource('r', 2); log = []

        def job(i):
            yield ('acquire', {r: 1})
            assert r.in_use <= r.capacity
            log.append((i, env.now))
            yield ('timeout', 3 + i % 2)
            yield ('release', {r: 1})
        for i in range(7):
            env.process(job(i))
        env.run()
        return log, r.busy_time
    a, b = trace(), trace()
    assert a == b and a[1] == pytest.approx(sum(3 + i % 2 for i in range(7)))


def test_des_rejects_release_without_acquire():
    env = Env(); r = env.resource('r', 1)

    def bad():
        yield ('release', {r: 1})
    env.process(bad())
    with pytest.raises(RuntimeError):
        env.run()


# ---- SIM-01 engine ---------------------------------------------------------------------------
@pytest.mark.parametrize('sid', [s.sid for s in GRID] + [s.sid for s in MULTI])
def test_conservation_every_scenario(sid):
    for policy, pairing in (('rules', 'fifo'), ('bayes', 'optimized')):
        o = run(small(sid), policy, pairing)
        assert o['conservation_ok'], (sid, policy, pairing)
        assert 2 * o['shipped'] + o['scrapped_parts'] + o['leftover_unpaired'] == 2 * SMALL


def test_same_seed_same_result_and_common_random_numbers_across_configs():
    sc = small('F05')
    assert run(sc, 'rules', 'fifo', keep_log=False) == run(sc, 'rules', 'fifo', keep_log=False)
    for sid in [s.sid for s in GRID] + [s.sid for s in MULTI]:
        hashes = {run(small(sid), p, r)['truth_sha256'] for p in POLICIES for r in ('fifo', 'optimized')}
        assert len(hashes) == 1, sid


def test_partition_never_turns_into_a_clear_reading():
    sc = small('F07', partition_windows_s=((0.0, 1e9),))
    f = Factory(sc, 2, 'rules', model=MODEL); f.run()
    assert all(p['obs']['pi'][0] is None for p in f.parts if 'obs' in p and 'pi' in p['obs'])
    # rules treat a missing reading as HOLD: every part went to review
    assert f.stats['part_holds'] == 2 * SMALL


def test_stale_evidence_is_held_and_sharing_loss_forces_local_reinspection():
    assert run(small('M04'))['holds_stale_evidence'] > 0
    f = Factory(small('M03'), 1, 'bayes', model=MODEL); o = f.run()
    reached_assembly_site = sum(1 for p in f.parts if p.get('fate') != 'scrap' or 'phone_local' in p.get('obs', {}))
    assert 0 < o['local_reinspections'] <= 2 * SMALL
    assert o['local_reinspections'] >= reached_assembly_site - o['scrapped_parts']


def test_optimised_pairing_never_overrides_the_pair_gate():
    sc = small('F02', process_drift_mm_per_h=0.4)
    f = Factory(sc, 3, 'bayes', 'optimized', model=MODEL); f.run()
    t = f.costs.hold / (f.costs.hold + f.costs.escaped_defect)
    decided = [p for p in f.pairs if 'p_unsafe' in p]
    assert decided
    for p in decided:
        assert (p['decision'] == 'HOLD') == (p['p_unsafe'] >= t)


def test_hold_all_sends_every_part_to_review_and_costs_throughput():
    sc = small('F01')
    h, r = run(sc, 'hold_all'), run(sc, 'rules')
    assert h['part_reviews'] == 2 * SMALL
    assert h['good_per_hour'] < 0.5 * r['good_per_hour']


def test_drift_widens_tabs_over_time():
    f = Factory(replace(BY_ID['F02'], n_pairs=200, process_drift_mm_per_h=1.0, warp_p=0.0), 4, 'rules', model=MODEL); f.run()
    tabs = sorted((p for p in f.parts if p['kind'] == 'tab'), key=lambda p: p['part_id'])
    early = sum(p['printed_width_mm'] for p in tabs[:40]) / 40
    late = sum(p['printed_width_mm'] for p in tabs[-40:]) / 40
    assert late > early


def test_scale_tiers_have_the_declared_station_counts():
    for k in (6, 10, 50):
        s = scale_scenario(k).sites[0]
        assert s.printers + 3 * s.inspection_lines + 2 == k


# ---- SIM-05 optimisation ---------------------------------------------------------------------
def test_match_batch_is_optimal_against_brute_force():
    f = Factory(small('F02', process_drift_mm_per_h=0.4), 5, 'bayes', 'optimized', model=MODEL); f.run()
    parts = [p for p in f.parts if 'measured_mm' in p]
    S = [p for p in parts if p['kind'] == 'slot'][:6]; T = [p for p in parts if p['kind'] == 'tab'][:6]
    best = min(sum(_pair_cost(f, S[i], T[j]) for i, j in enumerate(perm)) for perm in itertools.permutations(range(6)))
    assert match_value(S, T, f, match_batch(S, T, f)) == pytest.approx(best)


def test_capacity_plan_matches_brute_force_and_respects_rho():
    for target in (60, 240):
        plan = plan_capacity(target)
        c = plan['assumptions']['costs_per_shift']
        brute = min((c['printer'] * a + c['line'] * b + c['operator'] * o, a, b, o)
                    for a in range(1, 30) for b in range(1, 30) for o in range(1, 30)
                    if all(u <= plan['assumptions']['rho_max'] + 1e-9 for u in (
                        plan['utilisation']['printer'] * plan['printers'] / a,
                        plan['utilisation']['line_bottleneck'] * plan['inspection_lines'] / b,
                        plan['utilisation']['operator'] * plan['operators'] / o)))
        assert plan['cost_per_shift'] == pytest.approx(brute[0])
        assert max(plan['utilisation'].values()) <= 0.85 + 1e-9


# ---- SIM-04 economics ------------------------------------------------------------------------
def test_cost_items_add_up_and_platform_costs_only_for_qualityrelay():
    o = run(small('F01'))
    base = run_cost(o, modes(), platform=False)
    qr = run_cost(o, modes(), platform=True)
    assert base['total_cost'] == pytest.approx(sum(base['items'].values()))
    assert set(qr['items']) - set(base['items']) == {'cloud_llm', 'platform_maintenance', 'platform_capex_amortised'}
    assert qr['profit'] < base['profit']  # same run: the platform only adds cost
    assert 0 < derived_hold_cost()['total'] < 2.0


def test_roi_requires_seed_pairing():
    a = [run(small('F01'), seed=s, keep_log=False) | {'escape_cost_units': 0} for s in (1, 2)]
    with pytest.raises(ValueError):
        roi_monte_carlo(a, list(reversed(a)), draws=10)


# ---- SIM-07 exports ---------------------------------------------------------------------------
def test_contrast_refuses_runs_on_different_parts():
    sc = small('F01')
    a = [_cell((sc, 1, 'rules', 'fifo'))[1]]
    b = [_cell((replace(sc, crack_p=0.2), 1, 'bayes', 'fifo'))[1]]
    with pytest.raises(ValueError):
        contrast(a, b)


def test_api_record_matches_the_proposed_schema():
    rec = api_record(_cell((small('F01'), 1, 'bayes', 'optimized'))[1], 'test/run')
    assert set(SCHEMA['required']) <= set(rec) <= set(SCHEMA['properties'])
    assert rec['source_tier'] == 'SIMULATED'
    assert rec['policy'] in SCHEMA['properties']['policy']['enum']


def test_charts_are_well_formed_and_labelled_simulated():
    svgs = [charts.dot_plot([('a', {'x': 1.0, 'y': 2.0})], [('x', 'X', 1), ('y', 'Y', 2)], 'T', 'v', 'SIMULATED test'),
            charts.interval_plot([('a', -1.0, 0.5, 2.0)], 'T', 'v', 'SIMULATED test'),
            charts.bar_plot([('a', 3.0), ('b', 1.0)], 'T', 'v', 'SIMULATED test')]
    for s in svgs:
        ET.fromstring(s)
        assert 'SIMULATED' in s and '<title>' in s


@pytest.mark.parametrize('sid,seed,cfg', [('F08', 7, ('rules', 'fifo')), ('F10', 8, ('rules', 'optimized')),
                                          ('F07', 14, ('bayes', 'optimized'))])
def test_full_size_runs_that_used_to_deadlock_now_complete(sid, seed, cfg):
    o = run_factory(BY_ID[sid], seed, *cfg, model=MODEL, keep_log=False)
    assert o['conservation_ok'] and o['parts'] == 2 * BY_ID[sid].n_pairs


def test_pair_timeout_releases_partial_batches_and_conserves_parts():
    sc = replace(BY_ID['M01'], n_pairs=120)
    slow = run_factory(sc, 2, 'bayes', 'optimized', model=MODEL, keep_log=False)
    fast = run_factory(sc, 2, 'bayes', 'optimized', model=MODEL, keep_log=False, batch_k=2, pair_timeout_s=60.0)
    assert fast['conservation_ok'] and slow['conservation_ok']
    assert fast['truth_sha256'] == slow['truth_sha256']
    assert fast['mean_cycle_s'] < slow['mean_cycle_s']


def test_reprint_loop_replaces_scrapped_parts_and_reinspects_them():
    sc = replace(BY_ID['F04'], n_pairs=80)  # crack burst: many scraps
    f = Factory(sc, 2, 'bayes', 'fifo', model=MODEL, reprint=True); o = f.run()
    assert o['conservation_ok'] and o['reprints'] > 0
    reprints = [p for p in f.parts if p.get('root_id')]
    assert len(reprints) == o['reprints']
    for p in reprints:
        assert p['part_id'].startswith(p['root_id'] + '-R') and p['reprints'] <= 2
        assert 'measured_mm' in p or p.get('fate') == 'scrap'   # went through metrology again
    for p in f.parts:
        if p.get('fate') == 'scrap' and p.get('reprints', 0) < 2:
            assert p.get('reprinted_as'), p['part_id']
    base = run_factory(sc, 2, 'bayes', 'fifo', model=MODEL, keep_log=False)
    assert base['truth_sha256'] == o['truth_sha256'] and base['reprints'] == 0
    assert o['shipped'] >= base['shipped']


def test_phone_only_two_lane_configuration():
    sc = replace(BY_ID['F01'], n_pairs=40, cameras=('phone',),
                 sites=(replace(BY_ID['F01'].sites[0], inspection_lines=2),))
    f = Factory(sc, 1, 'bayes', 'fifo', model=MODEL, lane_by_kind=True); o = f.run()
    assert o['conservation_ok']
    assert not any(e[2] == 'pi' for e in f.events)
    assert all(set(p['obs']) <= {'phone'} for p in f.parts if 'obs' in p)
    assert all(p['line'] == (0 if p['kind'] == 'slot' else 1) for p in f.parts)
