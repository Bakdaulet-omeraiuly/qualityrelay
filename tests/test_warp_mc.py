"""NVIDIA Warp Monte Carlo must make EXACTLY the CPU decisions and draw the same distributions."""
from math import sqrt

import numpy as np
import pytest

wp = pytest.importorskip('warp')

from qualityrelay17.factory import seeded_scenario, apply_policy  # noqa: E402
from qualityrelay17.calibration import estimate_likelihoods  # noqa: E402
from qualityrelay17.experiments.belief import calibrate_belief_model  # noqa: E402
from qualityrelay17.experiments.collective_env import CollectiveScenario, CollectiveEnv, make_cases  # noqa: E402
from qualityrelay17.experiments.collective_baselines import POLICIES as GATE_A  # noqa: E402
from qualityrelay17.gpu.warp_mc import decide_arrays, make_params, run_mc, GRID, WarpScenario  # noqa: E402

LK = estimate_likelihoods()
BM = calibrate_belief_model()
P = make_params(GRID[0], lk=LK, bm=BM)


def _holds_cpu(rows, policy):
    return np.array([r['outcome'] == 'hold' for r in apply_policy(rows, policy, likelihoods=LK)], dtype=int)


@pytest.mark.parametrize('seed', [0, 7, 29])
def test_warp_decisions_equal_factory_policies_part_for_part(seed):
    rows = seeded_scenario(3000, seed, camera_noise=0.10, network_outage=0.2)
    h = decide_arrays([r['phone_suspect'] for r in rows], [r['pi_suspect'] for r in rows],
                      [r['measured_clearance'] for r in rows], [r['network_down'] for r in rows], [0] * len(rows), P)
    assert (h[:, 0] == _holds_cpu(rows, 'conservative_rules')).all()
    assert (h[:, 1] == _holds_cpu(rows, 'collective_fusion')).all()


@pytest.mark.parametrize('dup', [0.0, 0.5])
def test_warp_B1_equals_gate_a_B1_including_lineage(dup):
    sc = CollectiveScenario('T', 't', duplicate_photo_p=dup, network_outage=0.2)
    cases = make_cases(3000, 5, sc)
    ref = np.array([GATE_A['B1_single_agent_fixed'](CollectiveEnv(c), sc, BM)['outcome'] == 'hold' for c in cases], dtype=int)
    h = decide_arrays([c['draws']['phone'][0] for c in cases], [c['draws']['pi'][0] for c in cases],
                      [c['draws']['caliper'][0] for c in cases], [not c['pi_available'] for c in cases],
                      [c['duplicate_pi'] for c in cases], P)
    assert (h[:, 2] == ref).all()


def test_warp_generator_matches_cpu_generator_distribution():
    rows = [r for s in range(30) for r in seeded_scenario(1000, 100 + s)]
    n = len(rows)
    safe = sum(r['safe'] for r in rows) / n
    b0 = apply_policy(rows, 'conservative_rules', likelihoods=LK)
    b0_hold = sum(x['outcome'] == 'hold' for x in b0) / n
    w = run_mc(GRID[0], 2_000_000, device='cpu', P=P)
    for cpu, gpu in ((safe, w['truly_safe_rate']), (b0_hold, w['policies']['B0_rules']['hold_rate'])):
        assert abs(cpu - gpu) < 4 * sqrt(cpu * (1 - cpu) / n)


def test_counts_are_conserved_and_paired_differences_consistent():
    w = run_mc(WarpScenario('T', 't', duplicate_p=0.3), 500_000, lots=50, device='cpu')
    assert w['parts'] == 500_000
    for name, pr in w['paired_vs_B0'].items():
        d = w['policies'][name]['unsafe_pass_rate'] - w['policies']['B0_rules']['unsafe_pass_rate']
        assert pr['unsafe_pass_rate']['diff'] == pytest.approx(d, abs=1e-12)
    assert 0.25 < w['duplicate_rate'] < 0.35


def test_importance_sampling_is_unbiased_and_common_mode_fit_recovers_c():
    from qualityrelay17.gpu.warp_mc import run_is, fit_common_mode
    sc = WarpScenario('T', 'shared', shared_noise=0.15)
    cm = fit_common_mode(sc, seeds=range(4000, 4004))
    assert abs(cm['c'] - 0.15) <= 0.03
    a = run_is(sc, 400_000, device='cpu', common=cm)
    b = run_is(sc, 400_000, q_surface=0.3, q_noise=0.25, device='cpu', common=cm, seed=5)
    for k in a['policies']:
        x, y = a['policies'][k], b['policies'][k]
        assert abs(x['unsafe_pass_rate'] - y['unsafe_pass_rate']) < 4 * (x['se'] ** 2 + y['se'] ** 2) ** 0.5
