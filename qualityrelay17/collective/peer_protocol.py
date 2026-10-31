"""PeerBus: private evidence stores per role, ACL, deadlines, and deterministic VERIFY.

Everything the plan says must be checked by code and not trusted to an agent happens here:
sender identity (signature), duplicate message ids, who may ask for what (roles.py
required_sources), who owns what (station ownership), deadline vs. responder latency,
evidence signature against station keys, staleness, and lineage against what the requester
already holds. A role never reads another role's store directly; it gets admissible summaries
through a granted request, and the bus keeps the full signed Evidence in a per-requester
verified pool so safe_mesh can later re-check signatures itself.
"""
from __future__ import annotations
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from ..contracts import Evidence, signature_valid
from ..roles import ROLES
from ..lineage import lineage_groups
from .messages import Message, sign_message, message_valid, admissible_summary, SOURCE_FAMILY
from .trace import Trace

# responder(kind, request_body) -> (evidence list, latency_ms). Default: look in the owner's own store.
Responder = Callable[[str, dict], tuple[list[Evidence], float]]


@dataclass
class PrivateStore:
    role: str
    own: list[Evidence] = field(default_factory=list)       # what this role observed itself
    received: list[dict] = field(default_factory=list)     # admissible summaries granted to it
    verified_pool: list[Evidence] = field(default_factory=list)  # full records VERIFY admitted (bus-held)

    def visible_kinds(self) -> set[str]:
        return {e.kind for e in self.own} | {s['kind'] for s in self.received if s['verification_status'] == 'VERIFIED'}

    def known_roots(self) -> set[str]:
        roots = {e.source_root for e in self.own} | {s['source_root'] for s in self.received}
        for e in self.own: roots |= set(e.payload.get('parent_source_roots', []) or [])
        return roots

    def evidence_for_decision(self) -> list[Evidence]:
        return list(self.own) + list(self.verified_pool)


class PeerBus:
    def __init__(self, *, role_keys: dict[str, str], station_keys: dict[str, str], ownership: dict[str, str],
                 now: float, max_age_s: float = 600.0, trace: Trace | None = None, request_cost: float = 0.3):
        """ownership: evidence kind -> role that owns that source (the only valid recipient)."""
        self.role_keys, self.station_keys, self.ownership = role_keys, station_keys, ownership
        self.now, self.max_age_s, self.request_cost = now, max_age_s, request_cost
        self.trace = trace or Trace(now=now)
        self.stores: dict[str, PrivateStore] = {}
        self.responders: dict[str, Responder] = {}
        self._seen_ids: set[str] = set()
        self.cost_charged: float = 0.0

    # ----------------------------------------------------------------- setup
    def register(self, role: str, evidence: list[Evidence] | None = None, responder: Responder | None = None):
        if role not in ROLES: raise ValueError(f'unknown role {role!r}')
        if role not in self.role_keys: raise ValueError(f'no signing key for role {role!r}')
        self.stores[role] = PrivateStore(role, list(evidence or []))
        if responder: self.responders[role] = responder
        return self.stores[role]

    def store(self, role: str) -> PrivateStore:
        return self.stores[role]

    # ----------------------------------------------------------------- messages
    def make(self, kind: str, sender: str, recipient: str, case_id: str, body: dict, correlation_id: str = '') -> Message:
        m = Message(message_id=f'msg-{secrets.token_hex(6)}', case_id=case_id, kind=kind, sender_role=sender,
                    recipient_role=recipient, sent_at=self.now, body=body, correlation_id=correlation_id)
        return sign_message(m, self.role_keys[sender])

    def send(self, m: Message) -> Message | None:
        """Deliver one signed message. Returns the reply for REQUEST_EVIDENCE, else None."""
        valid = message_valid(m, self.role_keys)
        self.trace.message(m, signature_valid=valid)
        if not valid:
            raise PermissionError(f'message {m.message_id} failed sender signature check; not from {m.sender_role!r}')
        if m.message_id in self._seen_ids:
            raise ValueError(f'duplicate message id {m.message_id}')
        self._seen_ids.add(m.message_id)
        if m.recipient_role not in self.stores:
            raise ValueError(f'recipient {m.recipient_role!r} is not registered on this bus')
        if m.kind == 'REQUEST_EVIDENCE':
            return self._handle_request(m)
        return None

    # ----------------------------------------------------------------- request handling
    def _reply(self, req: Message, outcome: str, reason: str, summaries: list[dict] | None = None, cost: float = 0.0) -> Message:
        body = {'outcome': outcome, 'reason': reason, 'requested_kind': req.body.get('requested_kind'),
                'summaries': summaries or [], 'cost_charged': round(cost, 4)}
        reply = self.make('EVIDENCE_RESPONSE', req.recipient_role, req.sender_role, req.case_id, body, correlation_id=req.message_id)
        self.trace.message(reply, signature_valid=True, outcome=outcome)
        return reply

    def _handle_request(self, req: Message) -> Message:
        kind: str = req.body.get('requested_kind', '')
        requester, owner = req.sender_role, req.recipient_role
        if not req.body.get('hypotheses') or not req.body.get('reason_code'):
            return self._reply(req, 'REJECT_REQUEST', 'UNTARGETED_REQUEST: hypotheses and reason_code are mandatory')
        family = SOURCE_FAMILY.get(kind)
        if family is None or family not in ROLES[requester].required_sources:
            return self._reply(req, 'REJECT_REQUEST', f'ACL_REQUESTER_NOT_ENTITLED: {requester} may not request {kind}')
        if self.ownership.get(kind) != owner:
            return self._reply(req, 'REJECT_REQUEST', f'RECIPIENT_NOT_OWNER: {owner} does not own {kind}')
        # the request itself is a charged act (task board SCI-02), whatever comes back
        cost = min(self.request_cost, float(req.body.get('max_cost', self.request_cost)))
        self.cost_charged += cost
        responder = self.responders.get(owner) or (lambda k, _b: ([e for e in self.stores[owner].own if e.kind == k], 0.0))
        try:
            found, latency_ms = responder(kind, req.body)
        except Exception as ex:  # a sensor/adapter error is a technical outcome, not a measurement
            return self._reply(req, 'SENSOR_FAILURE', f'{type(ex).__name__}: {ex}', cost=cost)
        if latency_ms > float(req.body.get('deadline_ms', 1500)):
            return self._reply(req, 'TIMEOUT', f'responder took {latency_ms:.0f} ms > deadline', cost=cost)
        found = [e for e in found if e.specimen_id == req.case_id]
        if not found:
            return self._reply(req, 'SENSOR_FAILURE', f'{owner} has no {kind} for {req.case_id}', cost=cost)
        summaries, requester_store = [], self.stores[requester]
        for e in found:
            status, new = self._verify(e, requester_store)
            summaries.append(admissible_summary(e, verification_status=status, new_source=new))
            if status == 'VERIFIED':
                requester_store.verified_pool.append(e)
        requester_store.received.extend(summaries)
        verified = [s for s in summaries if s['verification_status'] == 'VERIFIED']
        if not verified:
            worst = summaries[0]['verification_status']
            return self._reply(req, worst if worst in ('STALE_EVIDENCE', 'BAD_SIGNATURE') else 'DUPLICATE_SOURCE',
                               'no admissible new evidence', summaries, cost)
        return self._reply(req, 'GRANTED', f'{len(verified)} verified record(s)', summaries, cost)

    def _verify(self, e: Evidence, requester_store: PrivateStore) -> tuple[str, bool]:
        """Deterministic VERIFY. Returns (status, is_new_source)."""
        if not signature_valid(e, self.station_keys):
            self.trace.event('VERIFY', outcome='BAD_SIGNATURE', event_id=e.event_id, station_id=e.station_id)
            return 'BAD_SIGNATURE', False
        if not (self.now - self.max_age_s <= e.observed_at <= self.now + 5):
            self.trace.event('VERIFY', outcome='STALE_EVIDENCE', event_id=e.event_id, observed_at=e.observed_at)
            return 'STALE_EVIDENCE', False
        before = [{'event_id': x.event_id, 'source_root': x.source_root,
                   'parent_source_roots': x.payload.get('parent_source_roots', [])} for x in requester_store.evidence_for_decision()]
        after = before + [{'event_id': e.event_id, 'source_root': e.source_root,
                           'parent_source_roots': e.payload.get('parent_source_roots', [])}]
        new = len(lineage_groups(after)) > len(lineage_groups(before)) if before else True
        if not new:
            self.trace.event('VERIFY', outcome='DUPLICATE_SOURCE', event_id=e.event_id, source_root=e.source_root,
                             note='shares an ancestor with evidence the requester already holds; not an independent source')
            return 'DUPLICATE_SOURCE', False
        self.trace.event('VERIFY', outcome='VERIFIED', event_id=e.event_id, source_root=e.source_root, new_source=True)
        return 'VERIFIED', True
