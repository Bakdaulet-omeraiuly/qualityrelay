"""Record once, replay for free: a decision cache around adilnurgg's LLM request planner.

The LLM planner (qualityrelay17/collective/llm_planner.py, unchanged) proposes which evidence the
Assembly agent should request next. On a line, the same situation repeats for hundreds of parts, so
the planner's answer is stored under a key made from the situation, not from the part:

    model + prompt/tool version + requester role + missing kinds + visible evidence (kind, verdict,
    verification status, who holds it) + outcomes of requests so far + affordable requests left +
    belief rounded to 0.001

Part ids, event ids and timestamps are left out on purpose. A repeat situation is answered from the
cache with no API call. Modes:

    replay  (default; the website)  cache only, never calls the API. A miss falls back to the
            deterministic planner and is counted as a fallback, so nothing is ever silently 'LLM'.
    record  (script, explicit spend cap)  a miss calls the LLM once and appends the answer.

Honest reading: an LLM is not deterministic; the cache fixes ONE sampled answer per situation. A
cached decision is labelled 'LLM (cached)', with hit / miss / fallback counts and dollars spent.
The planner only proposes requests; the bus, VERIFY and the safety gate stay deterministic.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from ..collective.planner import DeterministicPlanner, PlannerUnavailable, HYPOTHESES
from ..collective.llm_planner import SYSTEM_PROMPT, _tools

PROMPT_VERSION = hashlib.sha256((SYSTEM_PROMPT + json.dumps(_tools({'peers': {}}), sort_keys=True)).encode()).hexdigest()[:12]
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / 'examples' / 'llm_cache' / 'planner_cache.jsonl'


def state_key(state: dict, model: str) -> tuple[str, dict]:
    vis = sorted((v.get('kind'), v.get('verdict'), v.get('verification_status', 'OWN'), v.get('held_by')) for v in state['visible_evidence'])
    rc = state['request_cost'] or 0.0
    norm = {'model': model, 'prompt': PROMPT_VERSION, 'role': state['requester_role'],
            'missing': sorted(state['missing_kinds']), 'peers': dict(sorted(state['peers'].items())), 'visible': vis,
            'history': [(h['kind'], h['outcome']) for h in state['requests_so_far']],
            'affordable': int(state['budget_remaining'] // rc) if rc > 0 else 99, 'belief': round(float(state['belief']), 3)}
    return hashlib.sha256(json.dumps(norm, sort_keys=True).encode()).hexdigest(), norm


class CachingPlanner:
    def __init__(self, inner=None, *, model: str | None = None, path: Path | str = DEFAULT_CACHE, mode: str = 'replay'):
        if mode not in ('replay', 'record'):
            raise ValueError('mode must be replay|record')
        if mode == 'record' and inner is None:
            raise ValueError('record mode needs a configured LLM planner')
        self.inner, self.mode, self.path = inner, mode, Path(path)
        self.model = model or getattr(inner, 'model', None) or self._model_in_file() or 'unknown-model'
        self.name = f'cached:{self.model}'
        self.fallback = DeterministicPlanner()
        self.cache: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    if r.get('prompt') == PROMPT_VERSION and r.get('model') == self.model:
                        self.cache[r['key']] = r['action']
        self.stats = dict(hits=0, misses=0, fallbacks=0, llm_calls=0, usd=0.0, tokens=0, entries=len(self.cache))
        self.last_usage = None
        self.last_source = None

    def _model_in_file(self):
        if not self.path.exists():
            return None
        for line in self.path.read_text().splitlines():
            if line.strip():
                return json.loads(line).get('model')
        return None

    def next_action(self, state: dict) -> dict | None:
        key, norm = state_key(state, self.model)
        self.last_usage = None
        if key in self.cache:
            self.stats['hits'] += 1; self.last_source = 'cache'
            return self._bind(self.cache[key], state)
        self.stats['misses'] += 1
        if self.mode == 'replay':
            self.stats['fallbacks'] += 1; self.last_source = 'fallback'
            return self.fallback.next_action(state)
        try:
            action = self.inner.next_action(state)
        except PlannerUnavailable:
            self.stats['fallbacks'] += 1; self.last_source = 'fallback'
            return self.fallback.next_action(state)
        u = getattr(self.inner, 'last_usage', None) or {}
        self.stats['llm_calls'] += 1
        self.stats['usd'] += u.get('cost_usd') or 0.0
        self.stats['tokens'] += (u.get('prompt_tokens') or 0) + (u.get('completion_tokens') or 0)
        self.last_usage, self.last_source = u, 'llm'
        if action and action.get('action') in ('request', 'finish'):
            stored = {k: action.get(k) for k in ('action', 'requested_kind', 'reason_code', 'hypotheses', 'reason') if action.get(k) is not None}
            self.cache[key] = stored
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a') as fh:
                fh.write(json.dumps({'key': key, 'model': self.model, 'prompt': PROMPT_VERSION, 'state': norm, 'action': stored}) + '\n')
            self.stats['entries'] = len(self.cache)
        return action

    @staticmethod
    def _bind(action: dict, state: dict) -> dict:
        """A cached request is re-addressed to the peer that owns the kind in THIS state."""
        if action.get('action') != 'request':
            return dict(action)
        kind = action.get('requested_kind')
        return {'action': 'request', 'requested_kind': kind, 'recipient_role': state['peers'].get(kind),
                'reason_code': action.get('reason_code') or 'NEED_EVIDENCE', 'hypotheses': action.get('hypotheses') or list(HYPOTHESES)}

    def describe(self) -> dict:
        s = dict(self.stats); s['usd'] = round(s['usd'], 6)
        n = s['hits'] + s['misses']
        return {'planner': 'llm_cached', 'model': self.model, 'mode': self.mode, 'prompt_version': PROMPT_VERSION,
                'hit_rate': round(s['hits'] / n, 4) if n else None, **s}
