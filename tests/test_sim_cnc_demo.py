"""CNC cell demo (scenario D01): camera gate, caliper chamber for flagged parts only, halt -> measure -> correct
-> approve -> resume, the audit baseline, waste accounting and the illustrative G-code. Everything is SIMULATED."""
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from qualityrelay17.api import app
from qualityrelay17.sim import gcode
from qualityrelay17.sim.cad import nominal_design
from qualityrelay17.sim.engine import Factory, calibrate_part_model, width_posterior
from qualityrelay17.sim.scenarios import BY_ID, GRID, MULTI, FUNCTIONAL_TOL_MM, draw_part, SiteConfig, FactoryScenario

M = calibrate_part_model(n=200)
D01 = replace(BY_ID['D01'], n_pairs=40, cameras=('phone',), sites=tuple(replace(s, inspection_lines=2) for s in BY_ID['D01'].sites))
WEB = dict(model=M, reprint=True, lane_by_kind=True)


def _run(control, policy='bayes', pairing='optimized', seed=0, **kw):
    f = Factory(D01, seed, policy, pairing, control=control, **WEB, **kw)
    return f, f.run()


def _types(o):
    return [e['type'] for e in o['line_events']]


def test_registered_scenarios_have_the_demo_features_off():
    for s in list(GRID) + list(MULTI):
        assert s.machine == 'printer' and s.tool_offset_fault_mm == 0.0 and s.camera_gross_dim_mm is None and s.caliper_mode == 'every_part'
    d = D01
    assert d.machine == 'cnc' and d.caliper_mode == 'flagged_only' and d.tool_offset_fault_mm == 1.6


def test_fault_is_in_the_truth_table_and_the_demo_streams_leave_registered_parts_untouched():
    design, site = nominal_design(), SiteConfig()
    base = FactoryScenario('X', 'x')
    a = draw_part(base, 1, 'slot', 7, site, 0.0, 'lot', design)
    b = draw_part(replace(base, camera_gross_dim_mm=0.8, caliper_mode='flagged_only'), 1, 'slot', 7, site, 0.0, 'lot', design)
    assert a['latent_width_mm'] == b['latent_width_mm'] and a['caliper'] == b['caliper'] and a['expert_width_mm'] == b['expert_width_mm']
    assert 'dims' in b and 'dims' not in a
    c = draw_part(replace(base, tool_offset_fault_mm=1.6), 1, 'slot', 7, site, 0.0, 'lot', design)
    t = draw_part(replace(base, tool_offset_fault_mm=1.6), 1, 'tab', 7, site, 0.0, 'lot', design)
    assert c['latent_width_mm'] == pytest.approx(a['latent_width_mm'] - 1.6)   # slot narrower
    assert t['latent_width_mm'] > draw_part(base, 1, 'tab', 7, site, 0.0, 'lot', design)['latent_width_mm']  # tab wider


def test_closed_loop_halts_measures_only_flagged_parts_corrects_with_approval_and_resumes():
    f, o = _run('closed_loop')
    assert o['conservation_ok'] and o['machine'] == 'cnc' and o['control'] == 'closed_loop'
    ty = _types(o)
    assert ty.count('HALT') == 2 and ty.count('CORRECTION_APPLIED') == 2 and ty.count('RESUMED') == 2 and 'CORRECTION_REFUSED' not in ty
    for kind in ('slot', 'tab'):
        seq = [e['type'] for e in o['line_events'] if e['kind'] == kind and e['type'] in ('HALT', 'CORRECTION_PROPOSED', 'CORRECTION_APPLIED', 'RESUMED')]
        assert seq == ['HALT', 'CORRECTION_PROPOSED', 'CORRECTION_APPLIED', 'RESUMED'], seq
    # the proposal is checked against a limit, approved by an operator (timed work on the operator pool), then applied
    prop = next(e for e in o['line_events'] if e['type'] == 'CORRECTION_PROPOSED')
    appl = next(e for e in o['line_events'] if e['type'] == 'CORRECTION_APPLIED' and e['kind'] == prop['kind'])
    assert prop['within_limits'] and prop['n_measurements'] >= 3 and appl['t'] > prop['t'] and 'operator' in appl['by']
    assert any(st == 'approval' for _a, _b, st, _k in f.events)
    # the estimate is the 1.6 mm fault (tab wider / slot narrower), so the offset cancels it
    for e in o['line_events']:
        if e['type'] == 'CORRECTION_PROPOSED':
            assert abs(abs(e['estimate_mm']) - 1.6) < 0.25 and abs(e['offset_after_mm'] + e['estimate_mm']) < 1e-9
    # the chamber measured flagged parts only; unflagged parts have no reading and no caliper event at all
    for p in f.parts:
        went = any(st == 'chamber' and k.endswith(p['part_id']) for _a, _b, st, k in f.events)
        assert went == (p['chamber'] is not None if 'chamber' in p else False) or not went
        if p.get('chamber'):
            assert p['flagged'] and p['measured_mm'] == p['chamber']['functional']['reading_mm']
            assert set(p['chamber']['dims']) >= {'length_mm', 'height_mm'} and all('deviation_mm' in d for d in p['chamber']['dims'].values())
        else:
            assert p['measured_mm'] is None
    assert not any(st == 'caliper' for _a, _b, st, _k in f.events)
    # parts made after the correction are within tolerance (ground truth, evaluator only)
    fix = o['waste']['first_correction_s']
    nominal = {'slot': f.design['slot_opening_mm'], 'tab': f.design['tab_width_mm']}
    after = [p for p in f.parts if p['t_print_s'] > fix[p['kind']]]
    assert after and all(abs(p['true_width_mm'] - nominal[p['kind']]) < FUNCTIONAL_TOL_MM + 0.4 for p in after)
    assert all(abs(p['true_width_mm'] - nominal[p['kind']]) > 1.0 for p in f.parts if p['t_print_s'] < 100)  # the first batch is defective
    w = o['waste']
    assert w['halts'] == 2 and w['corrections_applied'] == 2 and w['parts_made_before_correction'] >= 5
    assert sum(w['halted_s'].values()) > 0 and w['blanks_consumed'] == o['parts']


def test_audit_baseline_lets_the_machine_run_until_the_scheduled_audit_and_wastes_more():
    f, o = _run('audit', 'rules', 'fifo', audit_interval_s=1800.0)
    ty = _types(o)
    assert 'HALT' not in ty and 'AUDIT' in ty and ty.count('CORRECTION_APPLIED') == 2
    first = next(e for e in o['line_events'] if e['type'] == 'CORRECTION_APPLIED')
    assert first['t'] >= 1800.0 and 'audit' in first['by']
    _, q = _run('closed_loop')
    assert o['truth_sha256'] == q['truth_sha256']  # same parts (common random numbers)
    assert o['waste']['parts_made_before_correction'] > 3 * q['waste']['parts_made_before_correction']
    assert o['waste']['scrapped_parts'] > 2 * q['waste']['scrapped_parts']
    _, n = _run('none', 'rules', 'fifo')
    assert n['waste']['corrections_applied'] == 0 and n['waste']['parts_made_before_correction'] == n['parts']


def test_out_of_limit_correction_is_refused_and_the_machine_stays_stopped():
    f, o = _run('closed_loop', max_correction_mm=0.5)
    ty = _types(o)
    assert ty.count('CORRECTION_REFUSED') == 2 and 'CORRECTION_APPLIED' not in ty and 'RESUMED' not in ty
    assert all(f.machine_fault.values()) and all(f.halt[k] is not None for k in ('slot', 'tab'))
    assert not f.offset  # nothing was changed on the machine
    assert o['parts'] < 2 * D01.n_pairs  # production did stop: the rest of the shift was never made


def test_unconfirmed_flags_resume_the_machine_without_a_correction():
    # a line with a camera gate but no fault: random surface flags can stop a machine; the chamber then finds nothing
    sc = replace(D01, tool_offset_fault_mm=0.0, crack_p=0.0, camera_noise=0.6)
    f = Factory(sc, 1, 'bayes', 'optimized', control='closed_loop', halt_on_flags=2, **WEB); o = f.run()
    ty = _types(o)
    assert o['conservation_ok'] and 'HALT' in ty and 'CORRECTION_APPLIED' not in ty and 'RESUMED_UNCONFIRMED' in ty
    assert all(f.halt[k] is None for k in ('slot', 'tab'))


@pytest.mark.parametrize('control,policy,pairing', [('closed_loop', 'bayes', 'optimized'), ('audit', 'rules', 'fifo'), ('closed_loop', 'hold_all', 'fifo')])
def test_agents_match_the_line_in_the_cnc_cell(control, policy, pairing):
    key = lambda ff: [(p['pair_id'], p['decision'], p.get('p_unsafe'), p.get('fate')) for p in ff.pairs]  # noqa: E731
    a, oa = _run(control, policy, pairing)
    b = Factory(D01, 0, policy, pairing, control=control, agents=True, **WEB); ob = b.run()
    assert key(a) == key(b) and oa['waste'] == ob['waste'] and _types(oa) == _types(ob)
    assert len(b.agents.setpoints) == len(a.corrections)
    kinds = [m[1] for m in b.agents.messages]
    if control == 'closed_loop':
        assert 'PROPOSE_SETPOINT' in kinds and any(m[1] == 'DECISION' and m[5].get('stage') == 'correction' for m in b.agents.messages)
    # no CALIPER evidence or MEASUREMENT message exists for an unmeasured part (hold_all sends every part to the chamber)
    unmeasured = [p['part_id'] for p in b.parts if p['measured_mm'] is None]
    assert bool(unmeasured) == (policy != 'hold_all')
    assert not any(m[1] == 'MEASUREMENT' and m[4] in unmeasured for m in b.agents.messages)
    assert not any(e.kind == 'CALIPER' for pid in unmeasured for e in b.agents.evidence.get(pid, []))


def test_width_posterior_without_a_reading_is_the_prior():
    assert width_posterior(None, 'slot', M, 0.05) == (M.slot_mean, M.slot_var)
    mu, v = width_posterior(21.0, 'slot', M, 0.05)
    assert v < M.slot_var


def test_gcode_is_deterministic_and_the_correction_changes_only_the_wear_lines():
    d = nominal_design()
    a, b = gcode.program('tab', d, 0.0), gcode.program('tab', d, -1.64, measured_dev_mm=1.64)
    assert a == gcode.program('tab', d, 0.0) and len(a) == len(b)
    df = gcode.diff(a, b)
    assert [x['line'] for x in df] == [2, 6] and 'G10 L1 P2 R2.180' in df[1]['after'] and 'SIMULATED' in a[2]
    s = gcode.program('slot', d, +1.6)
    assert 'G10 L1 P2 R2.200' in s[5]  # a narrower slot is widened by a smaller compensated radius
    with pytest.raises(ValueError):
        gcode.diff(a, a[:-1])


def test_sim_run_exposes_the_cnc_demo_and_keeps_registered_runs_unchanged():
    c = TestClient(app)
    sc = {s['sid']: s for s in c.get('/sim/scenarios').json()}
    assert sc['D01']['group'] == 'cnc-demo' and sc['D01']['machine'] == 'cnc' and sc['F01']['machine'] == 'printer'
    d = c.post('/sim/run', json=dict(scenario='D01', seed=0, n_pairs=30)).json()
    assert d['machine'] == 'cnc' and d['control'] == 'closed_loop' and d['agents']['check']['identical'] is True
    assert d['kpis']['conservation_ok'] and [e['type'] for e in d['line_events']].count('CORRECTION_APPLIED') == 2
    assert d['waste']['halts'] == 2 and d['loop']['audit_interval_s'] is None
    ch = [p for p in d['parts'] if p['chamber']]
    assert ch and all(p['flagged'] and p['measured_mm'] is not None for p in ch)
    assert any(p['measured_mm'] is None and not p['flagged'] for p in d['parts'])
    prop = next(e for e in d['line_events'] if e['type'] == 'CORRECTION_PROPOSED')
    assert prop['gcode_before'] and prop['gcode_after'] and prop['gcode_diff']
    today = c.post('/sim/run', json=dict(scenario='D01', seed=0, n_pairs=30, policy='rules', pairing='fifo', audit_interval_s=900)).json()
    assert today['control'] == 'audit' and today['loop']['audit_interval_s'] == 900 and today['kpis']['truth_sha256'] == d['kpis']['truth_sha256']
    assert today['waste']['parts_made_before_correction'] > d['waste']['parts_made_before_correction']
    reg = c.post('/sim/run', json=dict(scenario='F02', policy='bayes', pairing='optimized', seed=1, n_pairs=30)).json()
    assert reg['machine'] == 'printer' and reg['control'] == 'none' and reg['line_events'] == [] and reg['waste']['halts'] == 0
    assert all(p['measured_mm'] is not None for p in reg['parts'])
    assert c.post('/sim/run', json=dict(scenario='D01', control='bogus')).status_code == 422
