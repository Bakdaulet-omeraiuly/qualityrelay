"""AGENT-04 (OpenAI half): an LLM proposes the requester's next move; code validates, the bus
enforces the ACL, safe_mesh decides. All offline via a fake OpenAI-format client, plus one live
smoke test that only runs with RUN_LIVE_LLM=1 and real OPENAI_API_KEY / OPENAI_MODEL."""
import json, os
from types import SimpleNamespace as NS
import pytest
from qualityrelay17.collective.scenarios import build
from qualityrelay17.collective.llm_planner import (OpenAICompatiblePlanner, SpendGuard, openai_planner_from_env, PROVIDERS)


def req(kind, to, reason='NEED_IT', hyps=('surface_defect',)):
    return ('request_evidence', {'requested_kind': kind, 'recipient_role': to, 'reason_code': reason, 'hypotheses': list(hyps)})


def fin(reason='enough'):
    return ('finish', {'reason': reason})


class FakeClient:
    """Mimics client.chat.completions.create. Script items: (tool, args) | ('text', str) | ('raw', tool, str) | Exception."""
    def __init__(self, script, usage=(900, 40)):
        self.script, self.usage, self.calls = list(script), usage, []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        item = self.script.pop(0)
        if isinstance(item, Exception): raise item
        u = NS(prompt_tokens=self.usage[0], completion_tokens=self.usage[1])
        if item[0] == 'text':
            msg = NS(content=item[1], tool_calls=None)
        else:
            name, args = (item[1], item[2]) if item[0] == 'raw' else (item[0], json.dumps(item[1]))
            msg = NS(content=None, tool_calls=[NS(id='c1', function=NS(name=name, arguments=args))])
        return NS(choices=[NS(message=msg)], usage=u)


def planner(script, **kw):
    client = FakeClient(script)
    p = OpenAICompatiblePlanner(client=client, model='test-model', provider='openai',
                                price_in_per_mtok=kw.pop('pin', 1.0), price_out_per_mtok=kw.pop('pout', 4.0), **kw)
    return p, client


def events(r, t): return [e for e in r.trace['entries'] if e['type'] == t]


PI, MET, ASM = 'additive_manufacturing_expert', 'metrology_engineer', 'assembly_engineer'


def test_llm_plans_full_collection_and_reaches_pass_review():
    p, client = planner([req('PI_IMAGE', PI), req('CALIPER', MET), req('ASSEMBLY', ASM), fin()])
    r = build('pi_clear', planner=p)
    assert r.decision['state'] == 'PASS_REVIEW' and r.control_decision['state'] == 'HOLD'
    assert r.request_outcomes == {'PI_IMAGE': 'GRANTED', 'CALIPER': 'GRANTED', 'ASSEMBLY': 'GRANTED'}
    calls = events(r, 'LLM_CALL')
    assert len(calls) == 4 and all(c['prompt_tokens'] == 900 and c['completion_tokens'] == 40 for c in calls)
    assert calls[0]['cost_usd'] == pytest.approx((900 * 1.0 + 40 * 4.0) / 1e6)
    assert r.planner['provider'] == 'openai' and r.planner['spend']['calls'] == 4
    assert all(e['body']['proposed_by'] == 'openai:test-model' for e in r.trace['entries']
               if e['type'] == 'MESSAGE' and e['kind'] == 'REQUEST_EVIDENCE')
    assert any(line.startswith('LLM openai:test-model') for line in r.narrative)


def test_llm_choice_changes_behaviour_it_can_stop_early():
    p, _ = planner([req('PI_IMAGE', PI), fin('Pi disagrees with phone; HOLD regardless of further evidence')])
    r = build('pi_suspect', planner=p)
    assert r.request_outcomes == {'PI_IMAGE': 'GRANTED'} and r.requests == 1 and r.cost_charged == pytest.approx(0.3)
    assert r.decision['state'] == 'HOLD' and 'VISUAL_PI_SUSPECT' in r.decision['reasons']
    assert events(r, 'PLANNER_FINISHED')[0]['reason'].startswith('Pi disagrees')


def test_misaddressed_request_is_a_real_bus_rejection_then_retry_allowed():
    p, _ = planner([req('PI_IMAGE', MET), req('PI_IMAGE', PI), fin()])
    r = build('pi_clear', planner=p)
    rejects = [e for e in r.trace['entries'] if e['type'] == 'MESSAGE' and e['kind'] == 'EVIDENCE_RESPONSE'
               and e['body']['outcome'] == 'REJECT_REQUEST']
    assert rejects and 'RECIPIENT_NOT_OWNER' in rejects[0]['body']['reason']
    assert r.request_outcomes['PI_IMAGE'] == 'GRANTED' and r.cost_charged == pytest.approx(0.3)  # ACL reject is not charged


@pytest.mark.parametrize('bad,why', [
    (('request_evidence', {'requested_kind': 'SECRET_DB', 'recipient_role': PI, 'reason_code': 'X', 'hypotheses': ['surface_defect']}), 'unknown evidence kind'),
    (('request_evidence', {'requested_kind': 'PI_IMAGE', 'recipient_role': 'chief_engineer', 'reason_code': 'X', 'hypotheses': ['surface_defect']}), 'not a peer'),
    (('request_evidence', {'requested_kind': 'PI_IMAGE', 'recipient_role': PI, 'reason_code': '', 'hypotheses': ['surface_defect']}), 'reason_code'),
    (('request_evidence', {'requested_kind': 'PI_IMAGE', 'recipient_role': PI, 'reason_code': 'X', 'hypotheses': ['ignore previous instructions']}), 'hypotheses'),
    (('request_evidence', {'requested_kind': 'PHONE_IMAGE', 'recipient_role': PI, 'reason_code': 'X', 'hypotheses': ['surface_defect']}), 'not missing'),
    (('raw', 'request_evidence', '{not json'), 'unparseable'),
    (('raw', 'release_part', '{}'), 'unknown tool'),
])
def test_invalid_proposals_never_reach_the_bus(bad, why):
    p, _ = planner([bad, fin()])
    r = build('pi_clear', planner=p)
    rej = events(r, 'PROPOSAL_REJECTED')
    assert rej and why in rej[0]['reason']
    assert r.requests == 0 and r.cost_charged == 0.0
    assert not [e for e in r.trace['entries'] if e['type'] == 'MESSAGE' and e['kind'] == 'REQUEST_EVIDENCE']


def test_duplicate_request_after_a_failed_outcome_is_blocked():
    p, _ = planner([req('PI_IMAGE', PI), req('PI_IMAGE', PI), fin()])
    r = build('pi_timeout', planner=p)
    assert r.request_outcomes['PI_IMAGE'] == 'TIMEOUT'
    assert 'no repeats' in events(r, 'PROPOSAL_REJECTED')[0]['reason']
    assert r.cost_charged == pytest.approx(0.3)  # charged once, not twice


def test_plain_text_answer_is_treated_as_finish():
    p, _ = planner([('text', 'I think the part looks fine, PASS it.')])
    r = build('pi_clear', planner=p)
    assert r.requests == 0 and r.decision['state'] == 'HOLD'  # prose cannot pass a part
    assert 'no tool call' in events(r, 'PLANNER_FINISHED')[0]['reason']


def test_provider_error_stops_planning_and_decides_on_what_is_held():
    p, _ = planner([req('PI_IMAGE', PI), RuntimeError('503 upstream overloaded')])
    r = build('pi_clear', planner=p)
    assert r.request_outcomes == {'PI_IMAGE': 'GRANTED'}
    stop = events(r, 'PLANNER_STOPPED')[0]
    assert 'RuntimeError' in stop['detail'] and r.decision['state'] == 'HOLD'


def test_spend_guard_caps_calls():
    p, client = planner([req('PI_IMAGE', PI), req('CALIPER', MET), req('ASSEMBLY', ASM), fin()], guard=SpendGuard(max_calls=2, max_usd=None))
    r = build('pi_clear', planner=p)
    assert len(client.calls) == 2 and 'max_calls=2' in events(r, 'PLANNER_STOPPED')[0]['detail']
    assert r.planner['spend']['calls'] == 2


def test_spend_guard_caps_usd_when_priced():
    p, client = planner([req('PI_IMAGE', PI), req('CALIPER', MET), fin()], guard=SpendGuard(max_usd=0.001), pin=1000.0, pout=1000.0)
    build('pi_clear', planner=p)
    assert len(client.calls) == 1  # first call cost ~$0.94, cap hit before the second


def test_unpriced_calls_log_tokens_but_no_invented_cost():
    p, _ = planner([fin()], pin=None, pout=None)
    r = build('pi_clear', planner=p)
    c = events(r, 'LLM_CALL')[0]
    assert c['cost_usd'] is None and c['prompt_tokens'] == 900 and r.planner['priced'] is False


def test_prompt_contains_only_the_requesters_view():
    p, client = planner([req('PI_IMAGE', PI), fin()])
    build('pi_clear', planner=p)
    first = json.loads(client.calls[0]['messages'][1]['content'])
    ids = {e['event_id'] for e in first['visible_evidence']}
    assert ids == {'p1', 'cad1'}  # phone + CAD only; Pi/caliper/assembly unseen until granted
    blob = json.dumps(client.calls[0])
    assert 'dev-pi-secret' not in blob and 'measurement_mm' not in blob and 'signature' not in blob
    second = json.loads(client.calls[1]['messages'][1]['content'])
    assert {'p1', 'cad1', 'p2'} <= {e['event_id'] for e in second['visible_evidence']}
    assert second['requests_so_far'][0]['outcome'] == 'GRANTED'
    assert client.calls[0]['tool_choice'] == 'required' and client.calls[0]['temperature'] == 0.0


def test_factory_not_configured_and_never_leaks_key():
    pl, st = openai_planner_from_env({})
    assert pl is None and st['state'] == 'NOT_CONFIGURED' and set(st['missing']) == {'OPENAI_API_KEY', 'OPENAI_MODEL'}
    pl, st = openai_planner_from_env({'OPENAI_API_KEY': 'sk-should-not-appear', 'OPENAI_MODEL': 'm'}, client=FakeClient([]))
    assert pl is not None and st['state'] == 'CONFIGURED_NOT_VERIFIED' and 'sk-should-not-appear' not in json.dumps(st)
    assert pl.extra == {'parallel_tool_calls': False} and 'openai' in PROVIDERS


def test_factory_reads_prices_and_caps():
    pl, _ = openai_planner_from_env({'OPENAI_API_KEY': 'k', 'OPENAI_MODEL': 'm', 'OPENAI_PRICE_INPUT_PER_MTOK': '0.4',
                                     'OPENAI_PRICE_OUTPUT_PER_MTOK': '1.6', 'LLM_MAX_CALLS_PER_RUN': '5',
                                     'LLM_MAX_USD_PER_RUN': '0.05'}, client=FakeClient([]))
    assert (pl.price_in, pl.price_out) == (0.4, 1.6) and pl.guard.max_calls == 5 and pl.guard.max_usd == 0.05


@pytest.mark.skipif(not (os.environ.get('RUN_LIVE_LLM') == '1' and os.environ.get('OPENAI_API_KEY') and os.environ.get('OPENAI_MODEL')),
                    reason='live OpenAI smoke test: set RUN_LIVE_LLM=1, OPENAI_API_KEY, OPENAI_MODEL')
def test_live_openai_smoke():
    pl, st = openai_planner_from_env()
    pl.guard = SpendGuard(max_calls=6, max_total_tokens=20_000, max_usd=0.05)
    r = build('pi_suspect', planner=pl)
    assert events(r, 'LLM_CALL'), r.narrative
    assert r.decision['state'] == 'HOLD'  # whatever the model does, a suspect Pi can never pass
    print('\n'.join(r.narrative))
