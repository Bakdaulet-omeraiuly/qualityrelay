"""LLM-01: Nebius Token Factory entitlement and model verification.

Answers three questions with real calls, and writes a redacted run manifest:
  1. Does the team key list models at all?            GET /v1/models
  2. Which of the task-board candidate ids are listed? (listing = entitlement; nothing is assumed)
  3. Does the chosen model complete one plain-text roundtrip and one JSON tool-call roundtrip
     (call -> schema-valid arguments -> tool result -> final answer)?

Verdicts: NOT_CONFIGURED (no key, nothing called), AUTH_FAILED, MODELS_LISTED_ONLY (listing done,
paid calls not confirmed), NOT_ENTITLED (requested model not listed), FAILED (a roundtrip failed),
VERIFIED. The manifest never contains the key; only a short SHA-256 fingerprint so rotation is visible.
Nothing here can approve, decide or actuate: the probe tool only echoes a request back.
"""
from __future__ import annotations
import hashlib, json, time
from typing import Any
from datetime import datetime, timezone
from pathlib import Path

NEBIUS_BASE_URL = 'https://api.tokenfactory.nebius.com/v1/'
# Task board candidates, in preference order. Availability is checked, never assumed.
CANDIDATES = ('zai-org/GLM-5.3-Flash', 'Qwen/Qwen3-30B-A3B-Instruct-2507', 'zai-org/GLM-5.3')
MANIFEST_DIR = Path(__file__).resolve().parent.parent / 'examples' / 'results' / 'llm_01_entitlement'
SCHEMA_VERSION = 'llm01-manifest-v1'
TEXT_TOKEN = 'QR-LLM01-OK'
MAX_TOKENS = 512  # per call; reasoning models need room before they emit a tool call

PROBE_TOOL: dict[str, Any] = {'type': 'function', 'function': {
    'name': 'request_evidence',
    'description': 'Ask one peer role for one missing evidence kind for this specimen.',
    'parameters': {'type': 'object', 'additionalProperties': False,
                   'required': ['requested_kind', 'recipient_role', 'reason_code', 'hypotheses'],
                   'properties': {
                       'requested_kind': {'type': 'string', 'enum': ['caliper', 'phone', 'pi', 'cad']},
                       'recipient_role': {'type': 'string', 'enum': ['metrology_engineer', 'vision_engineer', 'design_geometry']},
                       'reason_code': {'type': 'string', 'maxLength': 64},
                       'hypotheses': {'type': 'array', 'minItems': 1,
                                      'items': {'type': 'string', 'enum': ['OK', 'OVERSIZE', 'UNDERSIZE', 'SURFACE_DEFECT']}}}}}}
PROBE_SYSTEM = ('You are the quality_inspector role in a manufacturing inspection mesh. You hold one phone photo '
                'of specimen SLOT-07 that suggests the slot width may be out of tolerance, and no measurement. '
                'The metrology_engineer owns the caliper. Call request_evidence exactly once to ask for the '
                'missing caliper reading. Never invent measurements.')
PROBE_EXPECT = {'requested_kind': 'caliper', 'recipient_role': 'metrology_engineer'}


def key_fingerprint(key: str) -> str:
    return 'sha256:' + hashlib.sha256(key.encode()).hexdigest()[:12]


def _redact(text: str, key: str) -> str:
    text = str(text)
    return text.replace(key, '[REDACTED]') if key else text


def validate_args(args, schema: dict) -> list[str]:
    """Small validator for the JSON-schema subset the probe tool uses. Returns problems ([] = valid)."""
    if not isinstance(args, dict): return ['arguments are not a JSON object']
    props, problems = schema['properties'], []
    problems += [f'missing {k}' for k in schema.get('required', []) if k not in args]
    if schema.get('additionalProperties') is False:
        problems += [f'unexpected {k}' for k in args if k not in props]
    for k, v in args.items():
        p = props.get(k)
        if p is None: continue
        if p['type'] == 'string':
            if not isinstance(v, str): problems.append(f'{k} is not a string'); continue
            if 'enum' in p and v not in p['enum']: problems.append(f'{k}={v!r} not in enum')
            if 'maxLength' in p and len(v) > p['maxLength']: problems.append(f'{k} too long')
        elif p['type'] == 'array':
            if not isinstance(v, list): problems.append(f'{k} is not an array'); continue
            if len(v) < p.get('minItems', 0): problems.append(f'{k} has too few items')
            enum = p.get('items', {}).get('enum')
            if enum: problems += [f'{k} item {x!r} not in enum' for x in v if x not in enum]
    return problems


def _usage(resp, t0: float) -> dict:
    u = getattr(resp, 'usage', None)
    return {'latency_ms': round((time.perf_counter() - t0) * 1000, 1),
            'prompt_tokens': int(getattr(u, 'prompt_tokens', 0) or 0),
            'completion_tokens': int(getattr(u, 'completion_tokens', 0) or 0)}


def _call(client, **kw):
    t0 = time.perf_counter()
    resp = client.chat.completions.create(temperature=0, max_tokens=MAX_TOKENS, **kw)
    return resp, _usage(resp, t0)


def text_roundtrip(client, model: str) -> dict:
    resp, use = _call(client, model=model, messages=[
        {'role': 'system', 'content': 'You are a connectivity check. Follow the instruction exactly.'},
        {'role': 'user', 'content': f'Reply with exactly this token and nothing else: {TEXT_TOKEN}'}])
    text = (resp.choices[0].message.content or '').strip()
    return {'ok': TEXT_TOKEN in text, 'response_excerpt': text[:80], 'response_model': getattr(resp, 'model', None), **use}


def tool_roundtrip(client, model: str) -> dict:
    """Call 1 must produce exactly one schema-valid request_evidence call; call 2 feeds back a tool
    result and must produce a final text answer. Both calls' usage is recorded."""
    messages: list[dict[str, Any]] = [{'role': 'system', 'content': PROBE_SYSTEM},
                {'role': 'user', 'content': 'Specimen SLOT-07: phone photo flags possible OVERSIZE. What is your next step?'}]
    resp, use1 = _call(client, model=model, messages=messages, tools=[PROBE_TOOL], tool_choice='auto')
    msg = resp.choices[0].message
    calls = list(getattr(msg, 'tool_calls', None) or [])
    out: dict[str, Any] = {'ok': False, 'calls': [use1], 'tool_calls_returned': len(calls), 'problems': []}
    if not calls:
        out['problems'].append('no tool call; model answered in text: ' + (msg.content or '')[:120]); return out
    call = calls[0]
    out['tool_name'] = call.function.name
    if call.function.name != 'request_evidence': out['problems'].append(f'unknown tool {call.function.name!r}')
    if len(calls) > 1: out['problems'].append(f'{len(calls)} tool calls, expected 1')
    try:
        args = json.loads(call.function.arguments or '{}')
    except (ValueError, TypeError) as ex:
        out['problems'].append(f'unparseable arguments: {ex}'); out['raw_arguments'] = str(call.function.arguments)[:200]; return out
    out['arguments'] = args
    out['problems'] += validate_args(args, PROBE_TOOL['function']['parameters'])
    out['matches_expected_request'] = isinstance(args, dict) and all(args.get(k) == v for k, v in PROBE_EXPECT.items())
    messages += [{'role': 'assistant', 'content': msg.content or '',
                  'tool_calls': [{'id': call.id, 'type': 'function',
                                  'function': {'name': call.function.name, 'arguments': call.function.arguments or '{}'}}]},
                 {'role': 'tool', 'tool_call_id': call.id,
                  'content': json.dumps({'status': 'REQUEST_ACCEPTED_FOR_PROBE', 'note': 'connectivity probe; no evidence returned'})}]
    resp2, use2 = _call(client, model=model, messages=messages, tools=[PROBE_TOOL], tool_choice='auto')
    out['calls'].append(use2)
    final = resp2.choices[0].message
    out['final_answer_excerpt'] = (final.content or '')[:120]
    if getattr(final, 'tool_calls', None): out['problems'].append('second turn issued another tool call instead of answering')
    elif not (final.content or '').strip(): out['problems'].append('empty final answer after tool result')
    out['ok'] = not out['problems']
    return out


def verify_entitlement(*, key: str, client=None, model: str | None = None, all_candidates: bool = False,
                       confirm_spend: bool = False, now: datetime | None = None) -> dict:
    """Run the LLM-01 checks and return the manifest (not yet written). `client` is injectable for tests."""
    now = now or datetime.now(timezone.utc)
    m: dict[str, Any] = {'schema_version': SCHEMA_VERSION, 'task': 'LLM-01', 'provider': 'nebius', 'base_url': NEBIUS_BASE_URL,
         'checked_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'candidates': list(CANDIDATES), 'source_tier': 'LIVE_API_CHECK',
         'decision_authority': 'none: probe only; no evidence, verdict or actuation is produced'}
    if not key:
        return {**m, 'verdict': 'NOT_CONFIGURED', 'missing': ['NEBIUS_API_KEY'], 'key_fingerprint': None}
    m['key_fingerprint'] = key_fingerprint(key)
    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=NEBIUS_BASE_URL, timeout=30, max_retries=0)
    try:
        t0 = time.perf_counter()
        listed = sorted(x.id for x in client.models.list())
        m['models_endpoint'] = {'ok': True, 'count': len(listed), 'latency_ms': round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as ex:
        status = getattr(ex, 'status_code', None)
        m['models_endpoint'] = {'ok': False, 'error': _redact(f'{type(ex).__name__}: {str(ex)[:200]}', key), 'http_status': status}
        return {**m, 'verdict': 'AUTH_FAILED' if status in (401, 403) else 'FAILED'}
    m['listed_models'] = listed
    m['candidate_entitlement'] = {c: c in listed for c in CANDIDATES}
    if model: targets, m['selection'] = [model], 'explicit (--model or NEBIUS_MODEL)'
    elif all_candidates: targets, m['selection'] = [c for c in CANDIDATES if c in listed], 'all listed candidates'
    else:
        targets = [c for c in CANDIDATES if c in listed][:1]; m['selection'] = 'first listed candidate in preference order'
    m['tested'] = {}
    if not targets:
        return {**m, 'verdict': 'NOT_ENTITLED', 'detail': 'none of the candidate models is listed for this key'}
    if model and model not in listed:
        return {**m, 'verdict': 'NOT_ENTITLED', 'detail': f'{model!r} is not listed for this key'}
    if not confirm_spend:
        return {**m, 'verdict': 'MODELS_LISTED_ONLY', 'would_test': targets,
                'detail': 'paid roundtrips skipped; rerun with --confirm-spend'}
    for t in targets:
        r: dict = {}
        for name, fn in (('text', text_roundtrip), ('tool_call', tool_roundtrip)):
            try: r[name] = fn(client, t)
            except Exception as ex:
                r[name] = {'ok': False, 'error': _redact(f'{type(ex).__name__}: {str(ex)[:200]}', key),
                           'http_status': getattr(ex, 'status_code', None)}
        tokens = sum(c.get('prompt_tokens', 0) + c.get('completion_tokens', 0)
                     for c in [r['text'], *r['tool_call'].get('calls', [])])
        r['total_tokens'] = tokens
        r['tool_call_valid'] = bool(r['tool_call'].get('ok'))
        r['ok'] = bool(r['text'].get('ok') and r['tool_call'].get('ok'))
        m['tested'][t] = r
    m['verified_models'] = [t for t, r in m['tested'].items() if r['ok']]
    m['verdict'] = 'VERIFIED' if m['verified_models'] else 'FAILED'
    return m


def write_manifest(manifest: dict, out_dir: Path = MANIFEST_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = manifest['checked_at'].replace('-', '').replace(':', '')
    path = out_dir / f'nebius_{stamp}.json'
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path


def latest_status(model: str | None, out_dir: Path = MANIFEST_DIR) -> dict:
    """What /integrations/llm reports: the newest manifest's verdict for this model. No call is made."""
    files = sorted(out_dir.glob('nebius_*.json')) if out_dir.is_dir() else []
    if not files: return {'state': 'NEVER_CHECKED'}
    m = json.loads(files[-1].read_text(encoding='utf-8'))
    out = {'checked_at': m.get('checked_at'), 'manifest': files[-1].name, 'verdict': m.get('verdict'),
           'key_fingerprint': m.get('key_fingerprint')}
    if model and m.get('verdict') in ('VERIFIED', 'FAILED'):
        out['state'] = 'VERIFIED' if model in m.get('verified_models', []) else 'NOT_VERIFIED_FOR_THIS_MODEL'
    else:
        out['state'] = m.get('verdict')
    return out
