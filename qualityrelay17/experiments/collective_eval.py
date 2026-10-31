"""Paired-seed runner for B0..B7 (SCI-05/07/08). Same cases, same prices, same budget for every
policy within a (scenario, seed); uncertainty is a cluster bootstrap over seeds (a seed = one
simulated lot), never over individual parts. origin = SIMULATED on every number.
"""
from __future__ import annotations
from statistics import mean

from ..benchmark import paired_cluster_bootstrap_ci
from ..calibration import wilson_interval
from ..economics import calculate
from .belief import BeliefModel
from .collective_baselines import POLICIES, UPPER_BOUND, NOT_CONFIGURED
from .collective_env import CollectiveEnv, CollectiveScenario, make_cases

# (A, B, question). Registered in COLLECTIVE_GATE_A_REGISTRATION.md.
CONTRASTS = (
    ('B7_safe_mesh_voi', 'B0_rules', 'does the full method beat the fixed rule?'),
    ('B7_safe_mesh_voi', 'B5_structured_fixed', 'contribution of adaptive VOI (= ablation B7-adaptive_VOI)'),
    ('B7_safe_mesh_voi', 'B6_single_agent_voi', 'price of decentralised ownership (messages) vs one central agent'),
    ('B5_structured_fixed', 'B3_majority_vote', 'communication + fusion vs independent voting'),
    ('B6_single_agent_voi', 'B1_single_agent_fixed', 'adaptive vs fixed inspection, single agent'),
    ('B7_safe_mesh_voi', 'B7-provenance', 'contribution of lineage dedupe'),
    ('B7_safe_mesh_voi', 'B7-cost_awareness', 'expected-loss vs entropy selection'),
    ('B7_safe_mesh_voi', 'B7-hard_gate', 'what the hard gate costs / buys'),
    ('B7_safe_mesh_voi', 'B7-peer_exchange', 'contribution of peer exchange'),
)
SAFETY_MARGIN = 0.001       # unsafe-pass rate, absolute
THROUGHPUT_MARGIN = -0.01   # released-good rate, absolute


def run_seed(sc: CollectiveScenario, seed: int, n: int, model: BeliefModel, *, keep_traces=0):
    cases = make_cases(n, seed, sc)
    out = {}
    for name, policy in POLICIES.items():
        recs, traces = [], []
        for i, case in enumerate(cases):
            env = CollectiveEnv(case, run_id=f'{sc.sid}/s{seed}/{name}')
            rec = policy(env, sc, model)
            recs.append(rec)
            if i < keep_traces:
                traces.append(dict(specimen_id=case['specimen_id'], decision=rec['outcome'] if rec['outcome'] == 'hold' else 'pass_review',
                                   hard_gate=rec['hard_gate'], messages=env.trace))
        cost = calculate(recs, sc.costs)
        passed = [r for r in recs if r['outcome'] != 'hold']
        good = sum(r['outcome'] == 'pass' for r in recs)
        lat = sorted(r['latency_s'] for r in recs)
        safe_n = sum(r['truly_safe'] for r in recs)
        m = dict(seed=seed, n=n,
                 unsafe_pass=sum(r['unsafe_pass'] for r in recs),
                 released_good=good,
                 hold=sum(r['outcome'] == 'hold' for r in recs),
                 false_hold=sum(r['false_hold'] for r in recs),
                 truly_safe=safe_n,
                 passed=len(passed),
                 inspections=cost['inspections'], peer_requests=cost['peer_requests'],
                 timeouts=sum(r['timeouts'] for r in recs),
                 inspection_cost=cost['inspection_cost'], request_cost=cost['request_cost'],
                 compute_cost=cost['compute_cost'], outcome_cost=cost['outcome_cost'],
                 cost=cost['total_cost'],
                 latency_mean_s=mean(lat), latency_p95_s=lat[min(len(lat) - 1, int(0.95 * len(lat)))],
                 latency_total_s=sum(lat),
                 flips_with_new_fact=sum(r['flips_with_new_fact'] for r in recs),
                 flips_without_new_fact=sum(r['flips_without_new_fact'] for r in recs),
                 duplicates_received=sum(r['duplicates_received'] for r in recs),
                 hard_gate_triggered=sum(bool(r['hard_gate']) for r in recs))
        out[name] = (m, traces)
    return out


def summarise(sc: CollectiveScenario, per_seed: dict, n: int):
    summary = {}
    for name, recs in per_seed.items():
        tot = len(recs) * n
        unsafe = sum(r['unsafe_pass'] for r in recs)
        good = sum(r['released_good'] for r in recs)
        passed = sum(r['passed'] for r in recs)
        safe_n = sum(r['truly_safe'] for r in recs)
        cost = sum(r['cost'] for r in recs)
        summary[name] = dict(
            upper_bound_context_only=name in UPPER_BOUND,
            unsafe_pass_rate=unsafe / tot,
            unsafe_pass_wilson_95_descriptive_only=[round(x, 6) for x in wilson_interval(unsafe, tot)],
            conditional_risk_unsafe_given_pass=(unsafe / passed) if passed else None,
            false_hold_rate=sum(r['false_hold'] for r in recs) / safe_n if safe_n else None,
            hold_rate=sum(r['hold'] for r in recs) / tot,
            released_good_rate=good / tot,
            mean_inspections=sum(r['inspections'] for r in recs) / tot,
            mean_peer_requests=sum(r['peer_requests'] for r in recs) / tot,
            timeouts_per_part=sum(r['timeouts'] for r in recs) / tot,
            cost_per_unit=cost / tot,
            inspection_cost_per_unit=sum(r['inspection_cost'] for r in recs) / tot,
            request_cost_per_unit=sum(r['request_cost'] for r in recs) / tot,
            compute_cost_per_unit=sum(r['compute_cost'] for r in recs) / tot,
            outcome_cost_per_unit=sum(r['outcome_cost'] for r in recs) / tot,
            cost_per_good_unit=(cost / good) if good else None,
            latency_mean_s=mean(r['latency_mean_s'] for r in recs),
            latency_p95_s_mean_over_lots=mean(r['latency_p95_s'] for r in recs),
            serial_cell_good_per_hour=3600 * good / sum(r['latency_total_s'] for r in recs),
            decision_flips_with_new_fact_per_part=sum(r['flips_with_new_fact'] for r in recs) / tot,
            decision_flips_without_new_fact_per_part=sum(r['flips_without_new_fact'] for r in recs) / tot,
            duplicate_evidence_received_per_part=sum(r['duplicates_received'] for r in recs) / tot,
            hard_gate_triggered_rate=sum(r['hard_gate_triggered'] for r in recs) / tot,
        )
    contrasts = []
    for a, b, q in CONTRASTS:
        pairs = list(zip(per_seed[a], per_seed[b]))
        cost_d = [(x['cost'] - y['cost']) / n for x, y in pairs]
        unsafe_d = [(x['unsafe_pass'] - y['unsafe_pass']) / n for x, y in pairs]
        good_d = [(x['released_good'] - y['released_good']) / n for x, y in pairs]
        uc, cc, gc = (paired_cluster_bootstrap_ci(d) for d in (unsafe_d, cost_d, good_d))
        contrasts.append(dict(
            a=a, b=b, question=q,
            cost_per_unit_diff=mean(cost_d), cost_per_unit_diff_ci95=cc,
            unsafe_pass_rate_diff=mean(unsafe_d), unsafe_pass_rate_diff_ci95=uc,
            released_good_rate_diff=mean(good_d), released_good_rate_diff_ci95=gc,
            verdict=dict(non_inferior_on_safety=uc[1] <= SAFETY_MARGIN, cheaper=cc[1] < 0,
                         throughput_preserved=gc[0] >= THROUGHPUT_MARGIN)))
    return summary, contrasts


def run_scenario(sc: CollectiveScenario, model: BeliefModel, *, seeds=range(30), n=1000, keep_traces=0):
    per_seed = {name: [] for name in POLICIES}
    traces = {}
    for seed in seeds:
        res = run_seed(sc, int(seed), n, model, keep_traces=keep_traces if seed == min(seeds) else 0)
        for name, (m, tr) in res.items():
            per_seed[name].append(m)
            if tr:
                traces[name] = tr
    summary, contrasts = summarise(sc, per_seed, n)
    return dict(origin='SIMULATED', scenario=sc.as_dict(), seeds=[int(s) for s in seeds], n_per_seed=n,
                belief_model=model.as_dict(), not_configured=NOT_CONFIGURED,
                summary=summary, contrasts=contrasts, per_seed=per_seed), traces
