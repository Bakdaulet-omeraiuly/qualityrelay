import pytest
from qualityrelay17.benchmark import paired_cluster_bootstrap_ci, run_benchmark


def test_cluster_interval_is_reproducible():
    assert paired_cluster_bootstrap_ci([1., 3., 5.], draws=250) == paired_cluster_bootstrap_ci([1., 3., 5.], draws=250)


def test_cluster_interval_constant_paired_differences():
    assert paired_cluster_bootstrap_ci([2., 2., 2.]) == [2., 2.]


def test_cluster_interval_rejects_invalid_sample():
    with pytest.raises(ValueError):
        paired_cluster_bootstrap_ci([])


def test_benchmark_explicit_release_and_cluster_ci():
    report = run_benchmark(range(4), 25)
    assert report['origin'] == 'SIMULATED'
    assert 'paired_cost_difference_cluster_bootstrap_95' in report
    for p in report['summary'].values():
        assert 0 <= p['released_good_rate'] <= 1


def test_reference_policy_still_does_not_prove_advantage():
    report = run_benchmark(range(4), 25)
    assert report['paired_cost_difference_safe_mesh_minus_rules'] >= 0
    assert report['paired_unsafe_pass_rate_difference'] == 0
