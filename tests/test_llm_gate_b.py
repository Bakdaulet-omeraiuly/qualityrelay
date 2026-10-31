"""Gate B adapter: an LLM replaces B7's VOI selector inside Bakdaulet's Gate-A environment.
Belief, hard gate and decision stay in Python. All offline via a scripted fake client."""
import json
from types import SimpleNamespace as NS
import pytest
from qualityrelay17.collective.llm_planner import OpenAICompatiblePlanner, SpendGuard, nebius_planner_from_env, PROVIDERS
from qualityrelay17.experiments.belief import calibrate_belief_model
from qualityrelay17.experiments.collective_baselines import POLICIES, B7_safe_mesh_voi
from qualityrelay17.experiments.collective_env import CollectiveEnv, make_cases
from qualityrelay17.experiments.collective_eval import run_seed, run_scenario
from qualityrelay17.experiments.llm_policies import make_llm_policy, MAX_INVALID, LLM_CONTRASTS
from qualityrelay17.experiments.scenarios import BY_ID

MODEL = calibrate_belief_model()


class FakeClient:
    """Script items: ('request', kind, to) | ('finish',) | ('text', str) | ('raw', str) | Exception."""
    def __init__(self, script, usage=(700, 30)):
        self.script, self.usage, self.calls = list(script), usage, []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        item = self.script.pop(0) if self.script else ('finish',)
        if isinstance(item, Exception): raise item
        u = NS(prompt_tokens=self.usage[0], completion_tokens=self.usage[1])
        if item[0] == 'text':
            return NS(choices=[NS(message=NS(content=item[1], tool_calls=None))], usage=u)
        if item[0] == 'request':
            name, args = 'request_evidence', json.dumps({'kind': item[1], 'recipient_role': item[2], 'reason_code': 'NEED'})
        elif item[0] == 'raw':
            name, args = 'request_evidence', item[1]
        else:
            name, args = 'finish', json.dumps({'reason': 'done'})
        return NS(choices=[NS(message=NS(content=None, tool_calls=[NS(id='c', function=NS(name=name, arguments=args))]))], usage=u)


def planner(script, **kw):
    client = FakeClient(script)
    return OpenAICompatiblePlanner(client=client, model='fake', provider='openai', price_in_per_mtok=1.0,
                                   price_out_per_mtok=4.0, **kw), client


def case(sid='S13', where=lambda c: True):
    sc = BY_ID[sid]
    return sc, next(c for c in make_cases(200, 0, sc) if where(c))


def run(script, sid='S13', variant='role', where=lambda c: True):
    sc, c = case(sid, where)
    p, client = planner(script)
    env = CollectiveEnv(c, run_id='t')
    rec = make_llm_policy(p, variant)(env, sc, MODEL)
    return rec, env, client


def types(env): return [t['type'] for t in env.trace]


MET, PHONE, PI = 'metrology_agent', 'phone_agent', 'pi_agent'


def test_llm_requests_are_executed_through_owners_and_logged():
    rec, env, client = run([('request', 'caliper', MET), ('request', 'phone', PHONE), ('finish',)])
    assert rec['observations'][:2] == ['caliper0', 'phone0'] and rec['peer_requests'] >= 2
    assert rec['compute_calls'] == len(client.calls) and rec['llm_prompt_tokens'] == 700 * len(client.calls)
    assert rec['llm_usd'] == pytest.approx(len(client.calls) * (700 * 1.0 + 30 * 4.0) / 1e6)
    assert rec['planner'] == 'openai:fake' and rec['prompt_variant'] == 'role' and not rec['planner_stopped']
    assert types(env)[:4] == ['LLM_CALL', 'REQUEST_EVIDENCE', 'RESPONSE_EVIDENCE', 'UPDATE_BELIEF']
    reasons = [t['reason'] for t in env.trace if t['type'] == 'UPDATE_BELIEF']
    assert reasons[:2] == ['LLM:NEED', 'LLM:NEED']


def test_finish_without_evidence_holds_without_inspecting():
    # prior p_unsafe is above the HOLD threshold, so (as in B7) nothing is bought and the part is held
    rec, env, client = run([('finish',)])
    assert rec['outcome'] == 'hold' and rec['inspections'] == 0 and len(client.calls) == 1
    assert set(rec['hard_gate']) == {'NO_INDEPENDENT_SURFACE_EVIDENCE', 'NO_DIMENSIONAL_EVIDENCE'}


def test_hard_gate_buys_missing_caliper_then_reasks_the_model():
    # two clear camera frames push p_unsafe under the threshold with no caliper: the gate fixes that
    clear_cams = lambda c: c['pi_available'] and not c['draws']['phone'][0] and not c['draws']['pi'][0] and not c['duplicate_pi']
    rec, env, client = run([('request', 'phone', PHONE), ('request', 'pi', PI), ('finish',), ('finish',)], where=clear_cams)
    gate = [t for t in env.trace if t['type'] == 'UPDATE_BELIEF' and t['reason'].startswith('HARD_GATE:')]
    assert [t['kind'] for t in gate] == ['caliper'] and gate[0]['reason'] == 'HARD_GATE:NO_DIMENSIONAL_EVIDENCE'
    assert len(client.calls) == 4, 'model is asked again after the gate added evidence'
    assert rec['observations'] == ['phone0', 'pi0', 'caliper0']


@pytest.mark.parametrize('bad, why', [
    (('request', 'caliper', PHONE), 'does not own'),
    (('request', 'xray', MET), 'unknown sensor'),
    (('raw', '{not json'), 'unparseable'),
])
def test_invalid_proposals_are_rejected_and_never_charged(bad, why):
    rec, env, _ = run([bad, ('finish',)])
    rej = [t for t in env.trace if t['type'] == 'PROPOSAL_REJECTED']
    assert len(rej) == 1 and why in rej[0]['reason'] and rec['invalid_proposals'] == 1
    llm_charged = [t for t in env.trace if t['type'] == 'UPDATE_BELIEF' and t['reason'].startswith('LLM:')]
    assert llm_charged == []


def test_too_many_invalid_proposals_stops_asking():
    rec, env, client = run([('request', 'caliper', PI)] * (MAX_INVALID + 3))
    assert rec['invalid_proposals'] == MAX_INVALID
    assert sum(t['type'] == 'LLM_CALL' for t in env.trace) == MAX_INVALID


def test_timed_out_owner_cannot_be_asked_again():
    rec, env, _ = run([('request', 'pi', PI), ('request', 'pi', PI), ('finish',)], sid='S06')
    assert 'TIMEOUT' in types(env)
    rej = [t for t in env.trace if t['type'] == 'PROPOSAL_REJECTED']
    assert rej and 'timed out' in rej[0]['reason'] and rec['timeouts'] >= 1


def test_provider_failure_stops_planner_and_decides_on_held_evidence():
    rec, env, _ = run([('request', 'caliper', MET), RuntimeError('503 upstream')])
    assert rec['planner_stopped'] and '503' in rec['planner_stop_reason'] and 'PLANNER_STOPPED' in types(env)
    assert rec['outcome'] in ('hold', 'pass', 'escaped_defect')


def test_spend_cap_is_a_stop_not_a_crash():
    sc, c = case('S13')
    p, _ = planner([('request', 'caliper', MET)] * 5, guard=SpendGuard(max_calls=1))
    rec = make_llm_policy(p)(CollectiveEnv(c, run_id='t'), sc, MODEL)
    assert rec['planner_stopped'] and 'max_calls' in rec['planner_stop_reason'] and rec['compute_calls'] == 1


def test_model_never_sees_hidden_truth():
    _, env, client = run([('request', 'caliper', MET), ('finish',)])
    for call in client.calls:
        user = call['messages'][-1]['content']
        for leak in ('_truth', 'true_clearance', '"surface_defect"', '"safe"', 'duplicate_pi', 'pi_available'):
            assert leak not in user
        state = json.loads(user)
        assert set(state) == {'specimen_id', 'source_tier', 'evidence', 'belief', 'caliper_tolerance_mm', 'available',
                              'requests_so_far', 'budget', 'prices'}


def test_generic_variant_changes_only_the_prompt():
    _, _, role = run([('finish',)], variant='role')
    _, _, gen = run([('finish',)], variant='generic')
    r, g = role.calls[0], gen.calls[0]
    assert 'quality_inspector' in r['messages'][0]['content'] and 'quality_inspector' not in g['messages'][0]['content']
    assert r['tools'] == g['tools'] and r['messages'][1] == g['messages'][1]


def test_registered_runner_is_unchanged_by_default_and_accepts_llm_policies():
    sc = BY_ID['S13']
    assert set(run_seed(sc, 0, 5, MODEL)) == set(POLICIES)
    p, _ = planner([])  # empty script -> always finish
    pols = {'B0_rules': POLICIES['B0_rules'], 'B5_structured_fixed': POLICIES['B5_structured_fixed'],
            'B7_safe_mesh_voi': B7_safe_mesh_voi, 'B7_llm': make_llm_policy(p),
            'B7_llm-specialist_roles': make_llm_policy(p, 'generic')}
    res, _ = run_scenario(sc, MODEL, seeds=range(2), n=10, policies=pols, contrasts=LLM_CONTRASTS)
    assert set(res['summary']) == set(pols) and len(res['contrasts']) == len(LLM_CONTRASTS)


def test_nebius_factory_registered_not_configured_and_never_leaks_key():
    assert PROVIDERS['nebius'] is nebius_planner_from_env
    p, st = nebius_planner_from_env({})
    assert p is None and st == {'provider': 'nebius', 'state': 'NOT_CONFIGURED', 'missing': ['NEBIUS_API_KEY', 'NEBIUS_MODEL']}
    p, st = nebius_planner_from_env({'NEBIUS_API_KEY': 'sk-secret', 'NEBIUS_MODEL': 'org/m', 'NEBIUS_PRICE_INPUT_PER_MTOK': '0.1',
                                     'NEBIUS_PRICE_OUTPUT_PER_MTOK': '0.4'}, client=FakeClient([]))
    assert p.name == 'nebius:org/m' and p.tool_choice == 'auto' and 'parallel_tool_calls' not in p.extra
    assert st['state'] == 'CONFIGURED_NOT_VERIFIED' and st['priced'] and 'sk-secret' not in json.dumps(st)


def test_openai_reasoning_effort_is_sent_only_when_configured():
    from qualityrelay17.collective.llm_planner import openai_planner_from_env
    base = {'OPENAI_API_KEY': 'sk-x', 'OPENAI_MODEL': 'gpt-5.6-luna'}
    p, _ = openai_planner_from_env(base, client=FakeClient([]))
    assert 'reasoning_effort' not in p.extra
    p, _ = openai_planner_from_env({**base, 'OPENAI_REASONING_EFFORT': 'none'}, client=FakeClient([]))
    assert p.extra == {'parallel_tool_calls': False, 'reasoning_effort': 'none'}
