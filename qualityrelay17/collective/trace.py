"""Explainable interaction trace (task board AGENT-03): every message with its provenance and
signature result, every technical outcome, every VERIFY decision, belief before/after, chosen
inspection, decision before/after. JSON for the API and a narrative for the Evidence Room."""
from __future__ import annotations
from dataclasses import dataclass, field

ROLE_SHORT = {'quality_inspector': 'Quality', 'metrology_engineer': 'Metrology', 'additive_manufacturing_expert': 'Pi/AM',
              'design_geometry': 'CAD', 'assembly_engineer': 'Assembly', 'inspection_planner': 'Planner',
              'safety_governance': 'Safety', 'process_engineer': 'Process'}


@dataclass
class Trace:
    now: float
    entries: list[dict] = field(default_factory=list)

    def _add(self, entry: dict) -> dict:
        entry = {'seq': len(self.entries), 't': self.now, **entry}
        self.entries.append(entry); return entry

    def message(self, m, *, signature_valid: bool, outcome: str | None = None):
        self._add({'type': 'MESSAGE', 'message_id': m.message_id, 'kind': m.kind, 'sender_role': m.sender_role,
                   'recipient_role': m.recipient_role, 'correlation_id': m.correlation_id,
                   'signature_valid': signature_valid, 'outcome': outcome, 'body': m.body})

    def event(self, type_: str, **fields):
        self._add({'type': type_, **fields})

    def to_dict(self) -> dict:
        return {'schema_version': '17.1', 'entries': self.entries}

    # ----------------------------------------------------------------- Evidence Room narrative
    def narrative(self) -> list[str]:
        out = []
        for e in self.entries:
            s = ROLE_SHORT.get(e.get('sender_role', ''), e.get('sender_role', ''))
            r = ROLE_SHORT.get(e.get('recipient_role', ''), e.get('recipient_role', ''))
            t = e['type']
            if t == 'MESSAGE':
                b = e['body']; k = e['kind']
                if not e['signature_valid']:
                    out.append(f'{s} -> {r}: {k} REJECTED (bad sender signature)'); continue
                if k == 'FIND_MISSING_EVIDENCE':
                    out.append(f'{s}: missing {", ".join(b.get("missing", [])) or "nothing"}; hypotheses {b.get("hypotheses")}')
                elif k == 'REQUEST_EVIDENCE':
                    out.append(f'{s} -> {r}: REQUEST_EVIDENCE {b["requested_kind"]} (reason: {b["reason_code"]}, max ${b.get("max_cost")}, {b.get("deadline_ms")} ms)')
                elif k == 'EVIDENCE_RESPONSE':
                    ids = ', '.join(f'{x["event_id"]} [{x["verification_status"].lower()} / source_root={x["source_root"]}]' for x in b['summaries'])
                    out.append(f'{s} -> {r}: EVIDENCE_RESPONSE {b["outcome"]} {ids or b["reason"]} (charged ${b["cost_charged"]})')
                elif k == 'HYPOTHESIS_UPDATE':
                    out.append(f'{s}: belief {b["belief_before"]:.3f} -> {b["belief_after"]:.3f} [{b["note"]}]')
                elif k == 'PROPOSE_INSPECTION':
                    out.append(f'{s}: next {b["chosen"]}, NetVOI={b["net_voi"]:+.3f} [{b["likelihood_source"]}]')
                elif k == 'DECISION_PROPOSAL':
                    out.append(f'{s}: {b["state"]} {list(b["reasons"])}; without requests: {b["control_state"]}; changed={b["decision_changed"]}')
            elif t == 'VERIFY':
                out.append(f'VERIFY {e.get("event_id")}: {e["outcome"]}' + (f' ({e["note"]})' if e.get('note') else ''))
            elif t == 'LLM_CALL':
                cost = 'unpriced' if e.get('cost_usd') is None else f"${e['cost_usd']:.5f}"
                out.append(f"LLM {e['provider']}:{e['model']} round {e['round']}: {e['prompt_tokens']}+{e['completion_tokens']} tokens, {e['latency_ms']:.0f} ms, {cost}")
            elif t == 'PROPOSAL_REJECTED':
                out.append(f"{e['planner']} proposal REJECTED before sending: {e['reason']}")
            elif t == 'PLANNER_FINISHED':
                out.append(f"{e['planner']} finished requesting: {e.get('reason') or 'no reason given'}")
            elif t == 'PLANNER_STOPPED':
                out.append(f"{e['planner']} STOPPED: {e['detail']} (deciding on evidence already held)")
            elif t == 'ERROR':
                out.append(f'ERROR: {e.get("detail")}')
        return out
