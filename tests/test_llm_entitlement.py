"""LLM-01 entitlement check, offline: a fake OpenAI-format client stands in for Nebius."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace as NS
import pytest
from qualityrelay17 import llm_entitlement as le

KEY = 'nb-secret-key-never-written-0123456789'
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
GOOD_ARGS = {'requested_kind': 'caliper', 'recipient_role': 'metrology_engineer', 'reason_code': 'SLOT_WIDTH', 'hypotheses': ['OK', 'OVERSIZE']}


def _msg(content=None, tool=None):
    calls = None if tool is None else [NS(id='c1', function=NS(name=tool[0], arguments=tool[1]))]
    return NS(choices=[NS(message=NS(content=content, tool_calls=calls))], usage=NS(prompt_tokens=10, completion_tokens=5), model='m')


class Fake:
    def __init__(self, models, replies=None, models_error=None):
        self.replies, self.sent = list(replies or []), []
        def _list():
            if models_error: raise models_error
            return [NS(id=x) for x in models]
        self.models = NS(list=_list)
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.sent.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception): raise r
        return r


def good_replies():
    return [_msg(le.TEXT_TOKEN), _msg(tool=('request_evidence', json.dumps(GOOD_ARGS))), _msg('Requested the caliper reading.')]


def run(client, **kw):
    return le.verify_entitlement(key=KEY, client=client, now=NOW, **kw)


def test_no_key_is_not_configured_and_calls_nothing():
    m = le.verify_entitlement(key='', client=Fake([], models_error=AssertionError('must not call')), now=NOW)
    assert m['verdict'] == 'NOT_CONFIGURED' and m['missing'] == ['NEBIUS_API_KEY'] and 'tested' not in m


def test_listing_without_confirm_spend_makes_no_chat_call():
    f = Fake(['Qwen/Qwen3-30B-A3B-Instruct-2507', 'other/x'])
    m = run(f)
    assert m['verdict'] == 'MODELS_LISTED_ONLY' and f.sent == []
    assert m['candidate_entitlement'] == {'zai-org/GLM-5.3-Flash': False, 'Qwen/Qwen3-30B-A3B-Instruct-2507': True, 'zai-org/GLM-5.3': False}
    assert m['would_test'] == ['Qwen/Qwen3-30B-A3B-Instruct-2507']


def test_full_roundtrip_verified_and_manifest_redacted(tmp_path):
    f = Fake(list(le.CANDIDATES), good_replies())
    m = run(f, confirm_spend=True)
    assert m['verdict'] == 'VERIFIED' and m['verified_models'] == ['zai-org/GLM-5.3-Flash']
    r = m['tested']['zai-org/GLM-5.3-Flash']
    assert r['tool_call_valid'] and r['tool_call']['matches_expected_request'] and r['total_tokens'] == 45
    # the tool result was actually fed back before the final answer
    assert f.sent[2]['messages'][-1]['role'] == 'tool' and f.sent[2]['messages'][-2]['tool_calls'][0]['id'] == 'c1'
    path = le.write_manifest(m, tmp_path)
    text = path.read_text()
    assert KEY not in text and m['key_fingerprint'] in text and path.name == 'nebius_20261031T120000Z.json'
    assert le.latest_status('zai-org/GLM-5.3-Flash', tmp_path)['state'] == 'VERIFIED'
    assert le.latest_status('zai-org/GLM-5.3', tmp_path)['state'] == 'NOT_VERIFIED_FOR_THIS_MODEL'


@pytest.mark.parametrize('bad_args,problem', [
    ({**GOOD_ARGS, 'requested_kind': 'xray'}, 'not in enum'),
    ({k: v for k, v in GOOD_ARGS.items() if k != 'hypotheses'}, 'missing hypotheses'),
    ({**GOOD_ARGS, 'event_id': 'e1'}, 'unexpected event_id'),
    ({**GOOD_ARGS, 'hypotheses': []}, 'too few'),
])
def test_schema_invalid_tool_call_fails(bad_args, problem):
    replies = [_msg(le.TEXT_TOKEN), _msg(tool=('request_evidence', json.dumps(bad_args))), _msg('done')]
    m = run(Fake(list(le.CANDIDATES), replies), confirm_spend=True)
    assert m['verdict'] == 'FAILED' and any(problem in p for p in m['tested']['zai-org/GLM-5.3-Flash']['tool_call']['problems'])


def test_text_only_answer_or_garbage_arguments_fail():
    m = run(Fake(list(le.CANDIDATES), [_msg(le.TEXT_TOKEN), _msg('I would ask for a caliper.')]), confirm_spend=True)
    assert m['verdict'] == 'FAILED' and 'no tool call' in m['tested']['zai-org/GLM-5.3-Flash']['tool_call']['problems'][0]
    m = run(Fake(list(le.CANDIDATES), [_msg(le.TEXT_TOKEN), _msg(tool=('request_evidence', '{not json'))]), confirm_spend=True)
    assert m['verdict'] == 'FAILED' and 'unparseable' in m['tested']['zai-org/GLM-5.3-Flash']['tool_call']['problems'][0]


def test_auth_failure_and_unlisted_model_and_error_redaction():
    err = Exception(f'401 bad key {KEY}'); err.status_code = 401
    m = run(Fake([], models_error=err))
    assert m['verdict'] == 'AUTH_FAILED' and KEY not in json.dumps(m)
    m = run(Fake(['other/x']), model='zai-org/GLM-5.3-Flash', confirm_spend=True)
    assert m['verdict'] == 'NOT_ENTITLED' and m['tested'] == {}
    m = run(Fake(['other/x']), confirm_spend=True)
    assert m['verdict'] == 'NOT_ENTITLED'
    crash = RuntimeError(f'boom {KEY}')
    m = run(Fake(list(le.CANDIDATES), [crash, crash]), confirm_spend=True)
    assert m['verdict'] == 'FAILED' and KEY not in json.dumps(m)


def test_latest_status_never_checked(tmp_path):
    assert le.latest_status('m', tmp_path / 'none') == {'state': 'NEVER_CHECKED'}


def test_openai_provider_checks_the_configured_model_with_gpt5_call_parameters(tmp_path):
    client = Fake(['gpt-5.6-luna', 'other'], good_replies())
    extra = le.call_kwargs('openai', {'OPENAI_REASONING_EFFORT': 'none'})
    m = run(client, provider='openai', model='gpt-5.6-luna', confirm_spend=True, extra=extra)
    assert m['verdict'] == 'VERIFIED' and m['provider'] == 'openai' and m['candidates'] == ['gpt-5.6-luna']
    assert all(c['max_completion_tokens'] == le.MAX_TOKENS and c['reasoning_effort'] == 'none' and 'max_tokens' not in c
               for c in client.sent)
    path = le.write_manifest(m, tmp_path)
    assert path.name.startswith('openai_') and KEY not in path.read_text()
    assert le.latest_status('gpt-5.6-luna', tmp_path, provider='openai')['state'] == 'VERIFIED'
    assert le.latest_status('x', tmp_path, provider='nebius') == {'state': 'NEVER_CHECKED'}


def test_openai_provider_without_key_names_the_openai_variable():
    m = le.verify_entitlement(key='', provider='openai', model='gpt-5.6-luna', now=NOW)
    assert m['verdict'] == 'NOT_CONFIGURED' and m['missing'] == ['OPENAI_API_KEY']
