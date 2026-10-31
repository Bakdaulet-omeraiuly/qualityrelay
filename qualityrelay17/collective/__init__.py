"""Structured evidence-request collaboration between specialist roles (task board AGENT-01..05;
research plan docs/research/COLLECTIVE_17_1_BAKDAULET.md section 3).

Honest scope: this is ONE process with per-role private stores and a signed message bus, not a
network of machines. The transport is a Python call; every message is still a serializable,
role-signed record, so the protocol can be moved onto a real transport without changing the
types. Roles are deterministic code here (no LLM); the point is the protocol, the ACL, the
verification and the trace, which an LLM-backed role would have to go through unchanged.

Modules
  messages        six message kinds, role signatures, admissible evidence summaries
  peer_protocol   PeerBus: private stores, ACL, deadlines, VERIFY (signature/stale/lineage)
  belief          BeliefModel interface; reference implementation on vder (Bakdaulet swaps it)
  trace           message-level provenance, belief before/after, decision before/after
  planner         RequestPlanner interface; DeterministicPlanner (default)
  llm_planner     OpenAICompatiblePlanner + openai_planner_from_env (Nebius plugs into the same class)
  engine          one case: FIND_MISSING -> REQUEST -> RESPONSE -> VERIFY -> UPDATE -> PROPOSE -> DECISION
  scenarios       TEST_FIXTURE cases for the API / web viewer / tests
"""
from .messages import Message, sign_message, message_valid, KINDS, OUTCOMES
from .peer_protocol import PeerBus
from .belief import BeliefModel, ReferenceBelief, from_likelihoods
from .trace import Trace
from .planner import RequestPlanner, DeterministicPlanner, PlannerUnavailable
from .engine import CollaborationEngine, CaseResult

__all__ = ['Message', 'sign_message', 'message_valid', 'KINDS', 'OUTCOMES', 'PeerBus', 'BeliefModel',
           'ReferenceBelief', 'from_likelihoods', 'Trace', 'CollaborationEngine', 'CaseResult',
           'RequestPlanner', 'DeterministicPlanner', 'PlannerUnavailable']
