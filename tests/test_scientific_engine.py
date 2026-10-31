"""Scientific-engine tests added 31 Oct (Bakdaulet): calibration, two-axis VOI, fresh-evidence
policies, and byte-identity of the 17.0 generator columns after the second RNG stream."""
import json
from pathlib import Path

import pytest

from qualityrelay17.vder import (Inspection, action_scores, combined_defect_probability,
                                 two_axis_action_scores, risk, entropy)
from qualityrelay17.calibration import estimate_likelihoods, Likelihoods
from qualityrelay17.factory import (seeded_scenario, apply_policy, compare_policies,
                                    LIKELIHOODS_PLACEHOLDER_17_0, POLICIES)
from qualityrelay17.benchmark import run_benchmark
from qualityrelay17.economics import Costs, calculate

SNAPSHOT = json.loads((Path(__file__).parent / 'fixtures' / 'policy_snapshot_17_0.json').read_text())


# ---------- 17.0 regression: primary columns and rule policies must be byte-identical ----------

@pytest.mark.parametrize('key', sorted(SNAPSHOT))
def test_rule_policies_unchanged_by_second_rng_stream(key):
    policy, seed, n = key.split(':')
    rows = seeded_scenario(int(n), int(seed))
    out = apply_policy(rows, policy)
    got = {'unsafe_pass': sum(r['unsafe_pass'] for r in out),
           'hold': sum(r['outcome'] == 'hold' for r in out),
           'total_cost': calculate(out, Costs())['total_cost']}
    assert got == SNAPSHOT[key]


def test_fresh_columns_exist_and_differ_from_free_columns():
    rows = seeded_scenario(2000, 7)
    assert all({'phone_recapture_suspect', 'pi_recapture_suspect', 'retake_clearance'} <= r.keys() for r in rows)
    # Fresh draws are genuinely new observations, not copies of the free ones.
    assert any(r['phone_recapture_suspect'] != r['phone_suspect'] for r in rows)
    assert any(r['pi_recapture_suspect'] != r['pi_suspect'] for r in rows)
    assert all(r['retake_clearance'] != r['measured_clearance'] for r in rows)


def test_fresh_columns_reproducible():
    assert seeded_scenario(50, 3) == seeded_scenario(50, 3)


# ---------- vder: two-axis combination and properties ----------

def test_combined_defect_probability_bounds_and_identities():
    assert combined_defect_probability(0.0, 0.0) == 0.0
    assert combined_defect_probability(1.0, 0.0) == 1.0
    assert combined_defect_probability(0.0, 0.3) == pytest.approx(0.3)
    assert combined_defect_probability(0.5, 0.5) == pytest.approx(0.75)
    with pytest.raises(ValueError):
        combined_defect_probability(1.2, 0.1)


def test_two_axis_no_action_equals_current_risk():
    out = two_axis_action_scores(0.1, 0.05, [], [], false_pass_cost=150., false_hold_cost=2.)
    assert [r['name'] for r in out] == ['NO_ACTION']
    assert out[0]['expected_loss'] == pytest.approx(risk(combined_defect_probability(0.1, 0.05), 150., 2.))
    assert out[0]['net_voi'] == 0.0


def test_two_axis_free_perfect_test_is_chosen_and_has_nonnegative_voi():
    out = two_axis_action_scores(0.2, 0.01, [Inspection('perfect_surface', 1, 1, 0.0)], [],
                                 false_pass_cost=150., false_hold_cost=2.)
    assert out[0]['name'] == 'perfect_surface'
    assert out[0]['net_voi'] >= 0


def test_two_axis_net_voi_never_exceeds_current_risk():
    # Information cannot be worth more than the risk it could eliminate.
    for ps in (0.001, 0.01, 0.1, 0.5):
        for pd in (0.0, 0.02, 0.3):
            r0 = risk(combined_defect_probability(ps, pd), 150., 2.)
            for row in two_axis_action_scores(ps, pd, [Inspection('a', .9, .9, .5)], [Inspection('b', .95, .97, .5)],
                                              false_pass_cost=150., false_hold_cost=2.):
                assert row['net_voi'] <= r0 + 1e-12
                assert 0 <= row['expected_entropy_reduction'] <= 1 + 1e-12


def test_action_scores_monotone_in_prior_for_expected_entropy_bounds():
    # Fourth-teammate task 1 from TOMORROW_TASKS, done here: expected_entropy in [0,1].
    a = [Inspection('x', .8, .9, 1.0)]
    for prior in (0.0, 0.01, 0.2, 0.5, 0.9, 1.0):
        for row in action_scores(prior, a):
            assert 0 <= row['expected_entropy'] <= 1 + 1e-12
    # expected loss of NO_ACTION is risk(prior): rises from 0 then falls -- check the pieces.
    assert risk(0.0) == 0 and risk(1.0) == 0 and risk(0.01) > 0


# ---------- calibration ----------

def test_calibration_recovers_generator_noise_within_interval():
    lk = estimate_likelihoods(seeds=range(1000, 1010), n=1000, camera_noise=0.04)
    assert isinstance(lk, Likelihoods)
    assert lk.source == 'HELD_OUT_SYNTHETIC_CALIBRATION'
    # generator flips each camera with p=0.04 symmetric -> sens = spec = 0.96 in expectation.
    # ~650 defects in the calibration lot -> sensitivity SE ~0.008; allow 0.03 so a 2-sigma
    # draw does not fail the suite (a 5-seed lot gave pi_sens 0.924 once -- sampling, not a bug).
    for name in ('phone', 'pi', 'phone_recapture', 'pi_recapture'):
        assert abs(getattr(lk, f'{name}_sens') - 0.96) < 0.03, (name, getattr(lk, f'{name}_sens'))
        assert abs(getattr(lk, f'{name}_spec') - 0.96) < 0.03, (name, getattr(lk, f'{name}_spec'))
        lo, hi = lk.intervals[f'{name}_spec']
        assert lo < hi
    assert 0 < lk.surface_prior < 0.15 and 0 < lk.dimensional_prior < 0.5
    assert lk.calibration_id and lk.counts


def test_calibration_is_deterministic_and_scenario_sensitive():
    a = estimate_likelihoods(seeds=range(1000, 1003), n=500)
    b = estimate_likelihoods(seeds=range(1000, 1003), n=500)
    c = estimate_likelihoods(seeds=range(1000, 1003), n=500, camera_noise=0.15)
    assert a == b and a.calibration_id == b.calibration_id
    assert c.phone_sens < a.phone_sens and c.calibration_id != a.calibration_id


# ---------- voi_driven / entropy_driven ----------

def test_voi_driven_paired_and_reports_fields():
    rows = seeded_scenario(300, 5)
    out = apply_policy(rows, 'voi_driven')
    assert [r['specimen_id'] for r in out] == [r['specimen_id'] for r in rows]
    for r in out:
        assert r['chosen_action'] in ('phone_recapture', 'pi_recapture', 'caliper_retake', 'NO_ACTION')
        assert r['inspections'] == 3 + int(r['chosen_action'] != 'NO_ACTION')
        assert 0 <= r['p_unsafe'] <= 1
        assert isinstance(r['decision_flip_from_fresh_evidence'], bool)
        assert (not r['decision_flip_from_fresh_evidence']) or r['chosen_action'] != 'NO_ACTION'


def test_voi_driven_actually_acts_sometimes_and_uses_fresh_evidence():
    rows = seeded_scenario(3000, 9)
    out = apply_policy(rows, 'voi_driven')
    acted = [r for r in out if r['chosen_action'] != 'NO_ACTION']
    assert acted, 'VOI never bought evidence -- step is dead'
    assert any(r['decision_flip_from_fresh_evidence'] for r in out), 'fresh evidence never changed a disposition'


def test_voi_driven_uses_benchmark_costs_not_vder_defaults():
    # Raising escaped_defect cost must not make VOI *less* willing to act.
    rows = seeded_scenario(2000, 11)
    cheap = sum(r['chosen_action'] != 'NO_ACTION' for r in apply_policy(rows, 'voi_driven', costs=Costs(escaped_defect=20.)))
    dear = sum(r['chosen_action'] != 'NO_ACTION' for r in apply_policy(rows, 'voi_driven', costs=Costs(escaped_defect=1500.)))
    assert dear >= cheap


def test_entropy_driven_differs_only_in_selection_rule():
    rows = seeded_scenario(1000, 2)
    v = apply_policy(rows, 'voi_driven')
    e = apply_policy(rows, 'entropy_driven')
    assert [r['specimen_id'] for r in v] == [r['specimen_id'] for r in e]
    # Same rows where both chose the same action must give the same disposition.
    for a, b in zip(v, e):
        if a['chosen_action'] == b['chosen_action']:
            assert a['outcome'] == b['outcome']


def test_collective_fusion_is_voi_without_adaptive_step():
    rows = seeded_scenario(1000, 4)
    fusion = apply_policy(rows, 'collective_fusion')
    voi = apply_policy(rows, 'voi_driven')
    for f, v in zip(fusion, voi):
        if v['chosen_action'] == 'NO_ACTION':
            assert f['outcome'] == v['outcome']


def test_compare_policies_and_registry_include_new_policies():
    assert {'voi_driven', 'entropy_driven', 'collective_fusion', 'structured_request_lite'} <= set(POLICIES)
    out = compare_policies(100, 1)
    assert {'voi_driven', 'entropy_driven'} <= set(out['policies'])


# ---------- benchmark ----------

def test_benchmark_accepts_scenario_and_reports_calibration_and_paired_blocks():
    out = run_benchmark(range(3), 100, camera_noise=0.10, shared_camera_noise=0.05,
                        calibration_seeds=range(1000, 1002))
    assert out['scenario']['camera_noise'] == 0.10 and out['scenario']['shared_camera_noise'] == 0.05
    assert out['calibration']['source'] == 'HELD_OUT_SYNTHETIC_CALIBRATION'
    assert out['costs']['escaped_defect'] == 150.0
    for alias in ('voi', 'entropy', 'fusion', 'request', 'safe_mesh'):
        assert f'paired_cost_difference_{alias}_minus_rules' in out
        lo, hi = out[f'paired_unsafe_pass_rate_{alias}_minus_rules_cluster_bootstrap_95']
        assert lo <= out[f'paired_unsafe_pass_rate_difference_{alias}_minus_rules'] <= hi
    # legacy keys still present for older tests/docs
    assert 'paired_cost_difference_safe_mesh_minus_rules' in out
    assert 'paired_cost_difference_cluster_bootstrap_95' in out
    assert 'mean_inspections' in out['summary']['voi_driven']
    assert 'brier_p_unsafe' in out['summary']['voi_driven']
    assert out['summary']['voi_driven']['action_distribution']


def test_benchmark_explicit_likelihoods_are_echoed():
    out = run_benchmark(range(2), 50, likelihoods=LIKELIHOODS_PLACEHOLDER_17_0)
    assert out['calibration']['source'] == 'PLACEHOLDER_17_0'
