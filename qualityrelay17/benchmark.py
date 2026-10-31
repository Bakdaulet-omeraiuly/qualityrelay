"""Paired synthetic comparison; NEVER interpret these results as observed factory impact.

Finite simulated populations are seeded and policy-paired. For interval estimates,
resample independent scenario/seed clusters rather than treating frames as independent.

31 Oct: scenario parameters, calibration and costs are explicit inputs and are echoed in the
output so every number carries the assumptions it was computed under
(docs/research/PROTOCOL_REGISTRATION_31OCT.md). Paired blocks are produced for every
policy against conservative_rules with the legacy key names preserved.
"""
from collections import Counter
from dataclasses import asdict
from statistics import mean
from random import Random
from .factory import seeded_scenario, apply_policy, POLICIES
from .economics import Costs, calculate
from .calibration import estimate_likelihoods, wilson_interval  # noqa: F401 (wilson re-exported)

REFERENCE = 'conservative_rules'
ALIASES = {'safe_mesh_reference': 'safe_mesh', 'voi_driven': 'voi', 'entropy_driven': 'entropy',
           'collective_fusion': 'fusion', 'structured_request_lite': 'request'}


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


def _paired_block(results, a, b, alias_a, alias_b, n_per_seed):
    out = {}
    pairs = list(zip(results[a], results[b]))
    for metric, key, scale in (('cost', 'paired_cost_difference_{}_minus_{}', 1),
                               ('unsafe_pass', 'paired_unsafe_pass_rate_difference_{}_minus_{}', n_per_seed),
                               ('released_good', 'paired_released_good_rate_difference_{}_minus_{}', n_per_seed)):
        diffs = [(x[metric] - y[metric]) / scale for x, y in pairs]
        name = key.format(alias_a, alias_b)
        out[name] = mean(diffs)
        ci_name = name.replace('_difference_', '_') + '_cluster_bootstrap_95' if metric != 'cost' \
            else f'paired_cost_difference_{alias_a}_minus_{alias_b}_cluster_bootstrap_95'
        out[ci_name] = paired_cluster_bootstrap_ci(diffs)
    return out


def run_benchmark(seeds=range(30), n_per_seed=1000, shift=0.1, *, camera_noise=0.04, network_outage=0.05,
                  shared_camera_noise=0.0, likelihoods=None, costs=None, calibration_seeds=range(1000, 1010),
                  calibration_n=None):
    scenario = dict(process_shift_mm=shift, camera_noise=camera_noise, network_outage=network_outage,
                    shared_camera_noise=shared_camera_noise)
    costs = costs or Costs()
    seed_values = [int(s) for s in seeds]
    if not seed_values or n_per_seed < 1:
        raise ValueError('positive scenarios and specimen count required')
    cal_seeds = [int(s) for s in calibration_seeds]
    if set(cal_seeds) & set(seed_values):
        raise ValueError('calibration seeds must be disjoint from test seeds')
    lk = likelihoods or estimate_likelihoods(seeds=cal_seeds, n=calibration_n or n_per_seed, **scenario)
    results = {p: [] for p in POLICIES}
    request_rate_by_seed = []
    for seed in seed_values:
        rows = seeded_scenario(n_per_seed, seed, **scenario)
        for policy in POLICIES:
            outcomes = apply_policy(rows, policy, costs=costs, likelihoods=lk)
            rec = {
                'seed': seed,
                'unsafe_pass': sum(row['unsafe_pass'] for row in outcomes),
                'released_good': sum(row['outcome'] == 'pass' for row in outcomes),
                'hold': sum(row['outcome'] == 'hold' for row in outcomes),
                'inspections': sum(row['inspections'] for row in outcomes),
                'cost': calculate(outcomes, costs)['total_cost'],
            }
            if 'p_unsafe' in outcomes[0]:
                truth = {r['specimen_id']: int(not r['safe']) for r in rows}
                rec['brier'] = mean((row['p_unsafe'] - truth[row['specimen_id']]) ** 2 for row in outcomes)
            if 'chosen_action' in outcomes[0]:
                rec['actions'] = Counter(row['chosen_action'] for row in outcomes)
                rec['flips'] = sum(row['decision_flip_from_fresh_evidence'] for row in outcomes)
            results[policy].append(rec)
            if policy == 'structured_request_lite':
                request_rate_by_seed.append(sum(row.get('requested_pi_evidence', False) for row in outcomes) / n_per_seed)
    summary = {}
    for policy, recs in results.items():
        total = len(recs) * n_per_seed
        failures = sum(r['unsafe_pass'] for r in recs)
        # Wilson is only a descriptive per-specimen interval. The clustered
        # scenario bootstrap below is the proper uncertainty comparison for policies.
        s = {
            'unsafe_pass_count': failures,
            'unsafe_pass_rate': failures / total,
            'unsafe_pass_wilson_95_descriptive_only': wilson_interval(failures, total),
            'released_good_rate': sum(r['released_good'] for r in recs) / total,
            'mean_holds': mean(r['hold'] for r in recs),
            'mean_inspections': mean(r['inspections'] for r in recs),
            'mean_cost': mean(r['cost'] for r in recs),
        }
        if 'brier' in recs[0]:
            s['brier_p_unsafe'] = mean(r['brier'] for r in recs)
        if 'actions' in recs[0]:
            acts = sum((r['actions'] for r in recs), Counter())
            s['action_distribution'] = {k: v / total for k, v in sorted(acts.items())}
            s['fresh_evidence_flip_rate'] = sum(r['flips'] for r in recs) / total
        summary[policy] = s
    out = {
        'origin': 'SIMULATED',
        'seeds': len(seed_values),
        'seed_values': seed_values,
        'n_per_seed': n_per_seed,
        'scenario': scenario,
        'costs': asdict(costs),
        'calibration': lk.as_dict(),
        'mean_pi_request_rate_structured_request_lite': mean(request_rate_by_seed),
        'method': 'identical_seed_paired_policy_comparison_cluster_bootstrap_over_seed',
        'pre_registered_claim': 'NO SUPERIORITY EXPECTED; compare conservative rule reference honestly',
        'summary': summary,
        'per_seed': {p: [{k: (dict(v) if isinstance(v, Counter) else v) for k, v in r.items()} for r in recs]
                     for p, recs in results.items()},
    }
    for policy, alias in ALIASES.items():
        out.update(_paired_block(results, policy, REFERENCE, alias, 'rules', n_per_seed))
    # Legacy key names from 17.0 (safe_mesh_reference vs rules) kept for older docs/tests.
    out['paired_cost_difference_cluster_bootstrap_95'] = out['paired_cost_difference_safe_mesh_minus_rules_cluster_bootstrap_95']
    out['paired_unsafe_pass_rate_difference'] = out['paired_unsafe_pass_rate_difference_safe_mesh_minus_rules']
    out['paired_unsafe_pass_rate_cluster_bootstrap_95'] = out['paired_unsafe_pass_rate_safe_mesh_minus_rules_cluster_bootstrap_95']
    out['paired_released_good_rate_difference'] = out['paired_released_good_rate_difference_safe_mesh_minus_rules']
    out['paired_released_good_rate_cluster_bootstrap_95'] = out['paired_released_good_rate_safe_mesh_minus_rules_cluster_bootstrap_95']
    # 17.1 control (section 3.4 point 5): selective request vs always-free Pi.
    out.update(_paired_block(results, 'structured_request_lite', 'collective_fusion', 'request', 'fusion', n_per_seed))
    # Ablation B7 - cost_awareness: expected-loss selection vs entropy selection, same everything else.
    out.update(_paired_block(results, 'voi_driven', 'entropy_driven', 'voi', 'entropy', n_per_seed))
    # Ablation B7 - adaptive step: voi_driven vs the same posteriors with no purchase.
    out.update(_paired_block(results, 'voi_driven', 'collective_fusion', 'voi', 'fusion', n_per_seed))
    out['warning'] = ('Toy generated data and assumed costs; no real-world improvement or scientific novelty '
                      'established. Likelihoods are a held-out SYNTHETIC calibration unless calibration.source says '
                      'otherwise; results under shared_camera_noise > 0 test the independence assumption the '
                      'posterior policies rely on -- report those alongside, never the baseline alone.')
    return out
