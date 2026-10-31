"""Who decides the requester's next move: the RequestPlanner interface.

The engine asks a planner, one round at a time, "given what this role can see right now, which
evidence do you want next, from whom, and why -- or are you done?". The planner only PROPOSES.
The engine validates the proposal, the bus applies the ACL / budget / deadline / VERIFY, and
safe_mesh makes the decision. A planner can never sign a message, see another role's raw data,
supply event ids, or approve anything.

Implementations
  DeterministicPlanner  the fixed procedure the engine used before (ask each missing kind's owner)
  llm_planner.OpenAICompatiblePlanner  an LLM behind any OpenAI-format endpoint (OpenAI, Nebius, vLLM)
"""
from __future__ import annotations
from typing import Protocol

HYPOTHESES = ('surface_defect', 'clearance_violation')
REASON_FOR = {'PI_IMAGE': 'NEED_INDEPENDENT_SURFACE_EVIDENCE', 'CAD_IMAGE': 'NEED_GEOMETRY_REFERENCE',
              'CALIPER': 'NEED_VERIFIED_METROLOGY', 'ASSEMBLY': 'NEED_FIT_RESULT', 'PHONE_IMAGE': 'NEED_SURFACE_EVIDENCE',
              'PROCESS': 'NEED_PROCESS_CONTEXT'}


class PlannerUnavailable(Exception):
    """The planner cannot continue (provider error, spend cap). The engine stops requesting and
    decides on what it has; it never treats this as an observation."""


class RequestPlanner(Protocol):
    name: str
    def next_action(self, state: dict) -> dict | None:
        """Return {'action': 'request', 'requested_kind', 'recipient_role', 'reason_code', 'hypotheses'},
        {'action': 'finish', 'reason'}, {'action': 'invalid', 'error', 'raw'}, or None (= finish)."""
        ...


class DeterministicPlanner:
    """Ask the owner of each still-missing kind, in NEEDED_KINDS order, once each."""
    name = 'deterministic'
    last_usage = None

    def next_action(self, state: dict) -> dict | None:
        tried = {r['kind'] for r in state['requests_so_far']}
        for kind in state['missing_kinds']:
            if kind in tried or kind not in state['peers']:
                continue
            return {'action': 'request', 'requested_kind': kind, 'recipient_role': state['peers'][kind],
                    'reason_code': REASON_FOR.get(kind, 'NEED_EVIDENCE'), 'hypotheses': list(HYPOTHESES)}
        return {'action': 'finish', 'reason': 'every missing kind with a registered owner has been requested'}
