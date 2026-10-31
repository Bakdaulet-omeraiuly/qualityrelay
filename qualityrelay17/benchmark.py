"""Paired synthetic comparison; NEVER interpret these results as observed factory impact.

Finite simulated populations are seeded and policy-paired. For interval estimates,
resample independent scenario/seed clusters rather than treating frames as independent.
"""
from math import sqrt
from statistics import mean
from random import Random
from .factory import seeded_scenario, apply_policy
from .economics import Costs, calculate


def wilson_interval(k, n, z=1.9599639845):
    if n < 1:
        return (0, 1)
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    radius = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return (max(0, center - radius), min(1, center + radius))


def paired_cluster_bootstrap_ci(paired_differences, *, draws=2000, seed=12577, confidence=.95):
    """Resample scenario-level paired differences. Diagnostic, not independent factory evidence."""
    values = [float(v) for v in paired_differences]
    if not values:
        raise ValueError('at least one paired scenario is required')
    if draws < 100 or not 0 < confidence < 1:
        raise ValueError('invalid bootstrap settings')
    rng = Random(seed)
    n = len(values)
    results = sorted(mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(draws))
    alpha = (1 - confidence) / 2
    lower = results[min(draws - 1, max(0, int(alpha * draws)))]
    upper = results[min(draws - 1, max(0, int((1 - alpha) * draws) - 1))]
    return [round(lower, 6), round(upper, 6)]


def run_benchmark(seeds=range(30), n_per_seed=1000, shift=0.1):
    policies = ('phone_only', 'metrology_only', 'conservative_rules', 'safe_mesh_reference', 'voi_driven', 'collective_fusion', 'structured_request_lite')
    results = {p: [] for p in policies}
    seed_values = list(seeds)
    if not seed_values or n_per_seed < 1:
        raise ValueError('positive scenarios and specimen count required')
    request_rate_by_seed = []
    for seed in seed_values:
        rows = seeded_scenario(n_per_seed, int(seed), process_shift_mm=shift)
        for policy in policies:
            outcomes = apply_policy(rows, policy)
            released_good = sum(row['outcome'] == 'pass' for row in outcomes)
            results[policy].append({
                'seed': int(seed),
                'unsafe_pass': sum(row['unsafe_pass'] for row in outcomes),
                'released_good': released_good,
                'hold': sum(row['outcome'] == 'hold' for row in outcomes),
                'cost': calculate(outcomes, Costs())['total_cost'],
            })
            if policy == 'structured_request_lite':
                request_rate_by_seed.append(sum(row.get('requested_pi_evidence', False) for row in outcomes) / n_per_seed)
    summary = {}
    for policy, rows in results.items():
        total = len(rows) * n_per_seed
        failures = sum(row['unsafe_pass'] for row in rows)
        # Wilson is only a descriptive per-specimen interval. The clustered
        # scenario bootstrap below is the proper uncertainty comparison for policies.
        summary[policy] = {
            'unsafe_pass_count': failures,
            'unsafe_pass_rate': failures / total,
            'unsafe_pass_wilson_95_descriptive_only': wilson_interval(failures, total),
            'released_good_rate': sum(row['released_good'] for row in rows) / total,
            'mean_holds': mean(row['hold'] for row in rows),
            'mean_cost': mean(row['cost'] for row in rows),
        }
    cost_differences = [a['cost'] - b['cost'] for a, b in zip(results['safe_mesh_reference'], results['conservative_rules'])]
    unsafe_differences = [(a['unsafe_pass'] - b['unsafe_pass']) / n_per_seed for a, b in zip(results['safe_mesh_reference'], results['conservative_rules'])]
    release_differences = [(a['released_good'] - b['released_good']) / n_per_seed for a, b in zip(results['safe_mesh_reference'], results['conservative_rules'])]
    # H2 (PRIOR_ART_AND_RESEARCH_QUESTIONS.md): does VOI-driven inspection selection change
    # cost/unsafe-pass/throughput versus the fixed conservative_rules reference, same seeds?
    voi_cost_differences = [a['cost'] - b['cost'] for a, b in zip(results['voi_driven'], results['conservative_rules'])]
    voi_unsafe_differences = [(a['unsafe_pass'] - b['unsafe_pass']) / n_per_seed for a, b in zip(results['voi_driven'], results['conservative_rules'])]
    voi_release_differences = [(a['released_good'] - b['released_good']) / n_per_seed for a, b in zip(results['voi_driven'], results['conservative_rules'])]
    # H1-collective-adjacent: does fusing two independently-sourced votes beat the
    # naive OR rule at matched inspection budget and matched/better unsafe-pass rate?
    fusion_cost_differences = [a['cost'] - b['cost'] for a, b in zip(results['collective_fusion'], results['conservative_rules'])]
    fusion_unsafe_differences = [(a['unsafe_pass'] - b['unsafe_pass']) / n_per_seed for a, b in zip(results['collective_fusion'], results['conservative_rules'])]
    fusion_release_differences = [(a['released_good'] - b['released_good']) / n_per_seed for a, b in zip(results['collective_fusion'], results['conservative_rules'])]
    # Bakdaulet's 17.1 control (docs/research/COLLECTIVE_17_1_BAKDAULET.md, section 3.4
    # point 5): does SELECTIVELY requesting Pi evidence lose much against always having it
    # for free (collective_fusion), while still requesting far less than every time?
    request_vs_fusion_cost = [a['cost'] - b['cost'] for a, b in zip(results['structured_request_lite'], results['collective_fusion'])]
    request_vs_fusion_unsafe = [(a['unsafe_pass'] - b['unsafe_pass']) / n_per_seed for a, b in zip(results['structured_request_lite'], results['collective_fusion'])]
    return {
        'origin': 'SIMULATED',
        'seeds': len(seed_values),
        'n_per_seed': n_per_seed,
        'mean_pi_request_rate_structured_request_lite': mean(request_rate_by_seed),
        'method': 'identical_seed_paired_policy_comparison_cluster_bootstrap_over_seed',
        'pre_registered_claim': 'NO SUPERIORITY EXPECTED; compare conservative rule reference honestly',
        'summary': summary,
        'paired_cost_difference_safe_mesh_minus_rules': mean(cost_differences),
        'paired_cost_difference_cluster_bootstrap_95': paired_cluster_bootstrap_ci(cost_differences),
        'paired_unsafe_pass_rate_difference': mean(unsafe_differences),
        'paired_unsafe_pass_rate_cluster_bootstrap_95': paired_cluster_bootstrap_ci(unsafe_differences),
        'paired_released_good_rate_difference': mean(release_differences),
        'paired_released_good_rate_cluster_bootstrap_95': paired_cluster_bootstrap_ci(release_differences),
        'paired_cost_difference_voi_minus_rules': mean(voi_cost_differences),
        'paired_cost_difference_voi_minus_rules_cluster_bootstrap_95': paired_cluster_bootstrap_ci(voi_cost_differences),
        'paired_unsafe_pass_rate_difference_voi_minus_rules': mean(voi_unsafe_differences),
        'paired_unsafe_pass_rate_voi_minus_rules_cluster_bootstrap_95': paired_cluster_bootstrap_ci(voi_unsafe_differences),
        'paired_released_good_rate_difference_voi_minus_rules': mean(voi_release_differences),
        'paired_released_good_rate_voi_minus_rules_cluster_bootstrap_95': paired_cluster_bootstrap_ci(voi_release_differences),
        'paired_cost_difference_fusion_minus_rules': mean(fusion_cost_differences),
        'paired_cost_difference_fusion_minus_rules_cluster_bootstrap_95': paired_cluster_bootstrap_ci(fusion_cost_differences),
        'paired_unsafe_pass_rate_difference_fusion_minus_rules': mean(fusion_unsafe_differences),
        'paired_unsafe_pass_rate_fusion_minus_rules_cluster_bootstrap_95': paired_cluster_bootstrap_ci(fusion_unsafe_differences),
        'paired_released_good_rate_difference_fusion_minus_rules': mean(fusion_release_differences),
        'paired_released_good_rate_fusion_minus_rules_cluster_bootstrap_95': paired_cluster_bootstrap_ci(fusion_release_differences),
        'paired_cost_difference_request_minus_fusion': mean(request_vs_fusion_cost),
        'paired_cost_difference_request_minus_fusion_cluster_bootstrap_95': paired_cluster_bootstrap_ci(request_vs_fusion_cost),
        'paired_unsafe_pass_rate_difference_request_minus_fusion': mean(request_vs_fusion_unsafe),
        'paired_unsafe_pass_rate_request_minus_fusion_cluster_bootstrap_95': paired_cluster_bootstrap_ci(request_vs_fusion_unsafe),
        'warning': 'Toy generated data and assumed costs; no real-world improvement or scientific novelty established. '
                   'collective_fusion advantage over conservative_rules was measured only under shared_camera_noise=0 '
                   '(independent cameras) -- it shrinks under correlated camera noise; re-run before presenting either number alone.',
    }
