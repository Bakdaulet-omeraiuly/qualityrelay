"""Record-once / replay cache around adilnurgg's LLM planner (sim/llm_cache.py). No network: fake client."""
import json
from dataclasses import replace
from types import SimpleNamespace as NS
from qualityrelay17.collective.llm_planner import OpenAICompatiblePlanner, SpendGuard
from qualityrelay17.sim.engine import Factory, calibrate_part_model
from qualityrelay17.sim.llm_cache import CachingPlanner, state_key
from qualityrelay17.sim.scenarios import BY_ID

M = calibrate_part_model()
SC = replace(BY_ID['F01'], n_pairs=20)


class FakeOpenAI:
    """Asks for the first missing kind, then finishes; counts calls."""
    def __init__(self, finish_always=False):
        self.calls, self.finish_always = 0, finish_always
        self.chat = NS(completions=NS(create=self.create))

    def create(self, *, model, messages, tools, **kw):
        self.calls += 1
        st = json.loads(messages[1]['content'])
        if self.finish_always or not st['missing_kinds']:
            fn = NS(name='finish', arguments=json.dumps({'reason': 'enough'}))
        else:
            k = st['missing_kinds'][0]
            fn = NS(name='request_evidence', arguments=json.dumps({'requested_kind': k, 'recipient_role': st['peers'][k],
                                                                   'reason_code': 'NEED_' + k, 'hypotheses': ['surface_defect']}))
        return NS(choices=[NS(message=NS(tool_calls=[NS(function=fn)], content=None))], usage=NS(prompt_tokens=400, completion_tokens=20))


def _llm(client):
    return OpenAICompatiblePlanner(client=client, model='fake-model', provider='openai', price_in_per_mtok=1.0, price_out_per_mtok=4.0,
                                   guard=SpendGuard(max_calls=10_000, max_total_tokens=10**9, max_usd=10.0))


def _decisions(f):
    return [(p['pair_id'], p['decision'], p.get('p_unsafe')) for p in f.pairs]


def test_record_then_replay_makes_no_second_call_and_keeps_decisions(tmp_path):
    path = tmp_path / 'cache.jsonl'
    ref = Factory(SC, 4, 'bayes', 'optimized', model=M); ref.run()
    client = FakeOpenAI()
    rec = CachingPlanner(_llm(client), path=path, mode='record')
    a = Factory(SC, 4, 'bayes', 'optimized', model=M, agents=True, planner=rec); a.run()
    assert _decisions(a) == _decisions(ref)
    d = rec.describe()
    assert d['llm_calls'] == client.calls == d['misses'] and d['hits'] > d['misses']  # situations repeat across parts
    assert d['usd'] > 0
    calls_after_record = client.calls
    rep = CachingPlanner(path=path, mode='replay', model='fake-model')
    b = Factory(SC, 4, 'bayes', 'optimized', model=M, agents=True, planner=rep); b.run()
    assert _decisions(b) == _decisions(ref) and client.calls == calls_after_record
    r = rep.describe()
    assert r['misses'] == 0 and r['fallbacks'] == 0 and r['llm_calls'] == 0 and r['hit_rate'] == 1.0


def test_empty_cache_in_replay_falls_back_to_deterministic_and_says_so(tmp_path):
    rep = CachingPlanner(path=tmp_path / 'none.jsonl', mode='replay', model='fake-model')
    f = Factory(SC, 4, 'bayes', 'optimized', model=M, agents=True, planner=rep); f.run()
    ref = Factory(SC, 4, 'bayes', 'optimized', model=M); ref.run()
    assert _decisions(f) == _decisions(ref)
    assert rep.describe()['fallbacks'] == rep.describe()['misses'] > 0 and rep.describe()['hits'] == 0


def test_key_ignores_part_identity():
    base = dict(requester_role='assembly_engineer', visible_evidence=[], missing_kinds=['PHONE_IMAGE', 'CALIPER'],
                peers={'PHONE_IMAGE': 'quality_inspector', 'CALIPER': 'metrology_engineer'}, requests_so_far=[],
                budget_remaining=0.6, request_cost=0.3, belief=0.0304)
    assert state_key(dict(base, case_id='S-1-000001'), 'm')[0] == state_key(dict(base, case_id='T-9-000777'), 'm')[0]
    assert state_key(dict(base, case_id='x'), 'm')[0] != state_key(dict(base, case_id='x', missing_kinds=['CALIPER']), 'm')[0]


def test_a_planner_that_skips_evidence_can_only_make_things_safer(tmp_path):
    rec = CachingPlanner(_llm(FakeOpenAI(finish_always=True)), path=tmp_path / 'c.jsonl', mode='record')
    f = Factory(SC, 4, 'bayes', 'optimized', model=M, agents=True, planner=rec); f.run()
    assert f.pairs and all(p['decision'] == 'HOLD' for p in f.pairs)  # no verified evidence -> SAFE-MESH hold
    assert f.agents.export()['planner']['assembly_rounds']['finishes'] > 0
