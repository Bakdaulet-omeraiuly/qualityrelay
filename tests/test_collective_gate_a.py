"""18.1 SCI-05..08 / 17.1 sec 9 acceptance checks for the Gate-A B0..B7 environment."""
import json
from dataclasses import replace


from qualityrelay17.economics import Costs
from qualityrelay17.factory import seeded_scenario, apply_policy
from qualityrelay17.experiments.belief import (calibrate_belief_model, belief_from, lookahead_value)
from qualityrelay17.experiments.collective_env import CollectiveScenario, CollectiveEnv, make_cases
from qualityrelay17.experiments.collective_baselines import POLICIES, gate_reasons
from qualityrelay17.experiments.collective_eval import run_seed

MODEL = calibrate_belief_model(n=300)
NOMINAL = CollectiveScenario('T', 'test')
CHEAP_MSG = CollectiveScenario('T', 'cheap msgs', costs=Costs(peer_request=0.05))
TRUTH_KEYS = {'safe', 'surface_defect', 'true_clearance', '_truth', 'truly_safe'}


def _run(policy, sc, n=300, seed=4):
    out = []
    for case in make_cases(n, seed, sc):
        env = CollectiveEnv(case)
        out.append((POLICIES[policy](env, sc, MODEL), env))
    return out


def test_evaluator_truth_never_reaches_agent_visible_data():
    for policy in POLICIES:
        for rec, env in _run(policy, CHEAP_MSG, n=80):
            blob = json.dumps([env.evidence, env.trace, env.observe('quality_agent')])
            assert not any(f'"{k}"' in blob for k in TRUTH_KEYS), policy


def test_role_views_are_scoped_to_owned_sensor():
    rec, env = _run('B2_full_information_upper_bound', NOMINAL, n=1)[0]
    assert {e['kind'] for e in env.observe('pi_agent')} <= {'pi'}
    assert {e['kind'] for e in env.observe('metrology_agent')} == {'caliper'}
    assert len(env.observe('quality_agent')) == len(env.evidence)


def test_B0_reproduces_conservative_rules_dispositions_on_identical_parts():
    rows = seeded_scenario(500, 11)
    ref = [r['outcome'] for r in apply_policy(rows, 'conservative_rules')]
    ours = [rec['outcome'] for rec, _ in _run('B0_rules', NOMINAL, n=500, seed=11)]
    assert ours == ref


def test_same_seed_same_results_for_every_policy():
    a = run_seed(NOMINAL, 3, 150, MODEL)
    b = run_seed(NOMINAL, 3, 150, MODEL)
    assert {k: v[0] for k, v in a.items()} == {k: v[0] for k, v in b.items()}


def test_charges_match_messages_and_evidence_exactly():
    for policy in POLICIES:
        for rec, env in _run(policy, CHEAP_MSG, n=120):
            assert rec['inspections'] == len(env.evidence) == len(rec['observations'])
            assert rec['peer_requests'] == sum(t['type'] == 'REQUEST_EVIDENCE' for t in env.trace)


def test_belief_is_recomputed_after_every_observation():
    for policy in ('B5_structured_fixed', 'B6_single_agent_voi', 'B7_safe_mesh_voi', 'B7-cost_awareness'):
        for rec, env in _run(policy, CHEAP_MSG, n=120):
            updates = [t for t in env.trace if t['type'] == 'UPDATE_BELIEF']
            assert len(updates) == rec['inspections'] + rec['timeouts']


def test_budget_is_respected():
    tight = replace(CHEAP_MSG, budget=2)
    for policy in ('B5_structured_fixed', 'B6_single_agent_voi', 'B7_safe_mesh_voi', 'B7-cost_awareness', 'B7-provenance'):
        assert all(rec['inspections'] <= 2 for rec, _ in _run(policy, tight, n=150))


def test_voi_picks_different_inspection_when_belief_changes():
    cand = {'phone': 0, 'pi': 0, 'caliper': 0}
    price = lambda k: 0.5  # noqa: E731
    near_tol = (0.0005, 0.6, 0.003)                         # surface already clean, clearance near tolerance
    _, k1 = lookahead_value(near_tol, cand, price, MODEL, Costs(), 1)
    camera_doubt = (0.03, 1.2, 0.0004)                       # dimension certain, surface in doubt
    _, k2 = lookahead_value(camera_doubt, cand, price, MODEL, Costs(), 1)
    assert k1 == 'caliper' and k2 in ('phone', 'pi')


def test_voi_can_stop_and_hold_when_no_test_pays():
    expensive = CollectiveScenario('T', 'expensive', costs=Costs(inspection=50.0))
    for rec, env in _run('B6_single_agent_voi', expensive, n=60):
        assert rec['inspections'] == 0 and rec['outcome'] == 'hold'


def test_duplicate_photo_adds_no_independent_evidence_with_lineage():
    case = make_cases(1, 0, NOMINAL)[0]
    case['draws']['phone'][0] = True
    case['draws']['pi'][0] = True
    case['roots']['pi'][0] = case['roots']['phone'][0]           # Pi frame = phone re-upload
    env = CollectiveEnv(case)
    env.capture('phone'); env.capture('pi')
    with_lineage, ns, _ = belief_from(env.evidence, MODEL, dedupe=True)
    only_phone, _, _ = belief_from(env.evidence[:1], MODEL, dedupe=True)
    no_lineage, ns_raw, _ = belief_from(env.evidence, MODEL, dedupe=False)
    assert ns == 1 and with_lineage == only_phone
    assert ns_raw == 2 and no_lineage[0] > with_lineage[0]
    assert env.evidence[1]['parent_source_roots'] == [env.evidence[0]['source_root']]


def test_lineage_blocks_flips_without_new_facts():
    dup = replace(CHEAP_MSG, duplicate_photo_p=1.0)
    for policy in ('B7_safe_mesh_voi', 'B5_structured_fixed'):
        assert all(rec['flips_without_new_fact'] == 0 for rec, _ in _run(policy, dup, n=300))


def test_timeout_is_never_turned_into_a_clear_reading():
    offline = replace(CHEAP_MSG, network_outage=1.0)
    saw_timeout = False
    for rec, env in _run('B7_safe_mesh_voi', offline, n=300):
        assert all(e['kind'] != 'pi' for e in env.evidence)
        if rec['timeouts']:
            saw_timeout = True
            # the timed-out request is still charged as a message, but not as an observation
            assert rec['peer_requests'] == len(env.evidence) + rec['timeouts']
    for rec, env in _run('B5_structured_fixed', offline, n=300):
        if rec['timeouts']:
            saw_timeout = True
            assert any(t['type'] == 'TIMEOUT' for t in env.trace)
    assert saw_timeout


def test_hard_gate_never_lets_a_pass_through_on_missing_evidence():
    for sc in (CHEAP_MSG, replace(CHEAP_MSG, network_outage=1.0), replace(CHEAP_MSG, budget=1)):
        for policy in ('B5_structured_fixed', 'B7_safe_mesh_voi', 'B7-provenance', 'B7-cost_awareness'):
            for rec, env in _run(policy, sc, n=200):
                if rec['outcome'] != 'hold':
                    kinds = {e['kind'] for e in env.evidence}
                    assert 'caliper' in kinds and kinds & {'phone', 'pi'}, (policy, rec)
                    assert gate_reasons(env, MODEL) == []


def test_a_peer_response_brings_a_new_fact_that_changes_the_decision():
    found = False
    for rec, env in _run('B7_safe_mesh_voi', CHEAP_MSG, n=400):
        tr = env.trace
        for i, t in enumerate(tr):
            if t['type'] == 'UPDATE_BELIEF' and t['new_independent_fact'] and t['disposition_before'] != t['disposition_after']:
                assert tr[i - 1]['type'] == 'RESPONSE_EVIDENCE' and tr[i - 2]['type'] == 'REQUEST_EVIDENCE'
                found = True
    assert found


def test_hold_all_is_what_registered_costs_make_rational_for_B7():
    """Documented negative finding: at message price 0.3 + inspection 0.5 the cheapest action
    at the prior is HOLD. If this ever changes, the results doc must be re-checked."""
    recs = [rec for rec, _ in _run('B7_safe_mesh_voi', NOMINAL, n=100)]
    assert all(r['outcome'] == 'hold' and r['inspections'] == 0 for r in recs)
