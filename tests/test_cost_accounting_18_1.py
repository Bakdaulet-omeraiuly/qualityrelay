"""18.1 SCI-01/02: every consumed observation and every peer request is charged exactly once."""
import pytest

from qualityrelay17.economics import Costs, calculate
from qualityrelay17.factory import seeded_scenario, apply_policy, POLICIES


@pytest.mark.parametrize('policy', POLICIES)
def test_every_policy_pays_for_exactly_the_signals_it_consumed(policy):
    rows = apply_policy(seeded_scenario(300, 5), policy)
    for r in rows:
        assert len(r['observations']) == r['inspections'], (policy, r)
    calculate(rows, Costs())  # the guard inside calculate must not fire


def test_structured_request_cost_is_charged_separately_from_the_pi_observation():
    rows = apply_policy(seeded_scenario(1000, 3), 'structured_request_lite')
    n_req = sum(r['peer_requests'] for r in rows)
    assert n_req > 0
    c = Costs()
    out = calculate(rows, c)
    assert out['peer_requests'] == n_req
    assert out['request_cost'] == pytest.approx(n_req * c.peer_request)
    assert out['inspection_cost'] == pytest.approx(out['inspections'] * c.inspection)
    assert out['total_cost'] == pytest.approx(out['inspection_cost'] + out['request_cost'] + out['outcome_cost'] + c.platform)
    # every requested Pi reading is in BOTH lines: one observation and one request
    for r in rows:
        assert ('pi' in r['observations']) == r['requested_pi_evidence'] == bool(r['peer_requests'])
        assert r['request_cost_paid'] == (c.peer_request if r['requested_pi_evidence'] else 0.0)


def test_zero_cost_request_only_when_configured_explicitly():
    rows = apply_policy(seeded_scenario(500, 3), 'structured_request_lite')
    assert Costs().peer_request > 0
    assert calculate(rows, Costs(peer_request=0.0))['request_cost'] == 0


def test_calculate_rejects_undercharged_observations():
    rows = [dict(specimen_id='a', outcome='pass', inspections=2, observations=['phone', 'pi', 'caliper'])]
    with pytest.raises(ValueError, match='consumed 3 observations but is charged for 2'):
        calculate(rows, Costs())


def test_calculate_rejects_request_policy_that_hides_its_requests():
    rows = [dict(specimen_id='a', outcome='pass', inspections=3, requested_pi_evidence=True)]
    with pytest.raises(ValueError, match='peer_requests'):
        calculate(rows, Costs())


def test_voi_driven_pays_for_free_reads_plus_the_purchase():
    rows = apply_policy(seeded_scenario(1000, 7), 'voi_driven')
    for r in rows:
        assert r['inspections'] == 3 + int(r['chosen_action'] != 'NO_ACTION')
