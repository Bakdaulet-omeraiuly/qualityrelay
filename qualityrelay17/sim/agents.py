"""The six QualityRelay agents, running inside the simulated line (Bakdaulet, 31 Oct).

Each agent is code (a calibrated statistic, a rule or a decision formula), not an LLM. Each keeps a
private store and learns about other stations only through messages. The simulator calls the team
at the moments a real line would:

  part inspected   -> Vision + Metrology store their own readings; Metrology notifies Process
  part gate        -> Vision computes P(surface defect) and asks Cost for PASS / HOLD
  pair formed      -> Assembly asks Vision and Metrology for evidence on both parts, combines it,
                      asks Cost for the decision (missing / late evidence -> HOLD, SAFE-MESH rule)
  review outcome   -> the expert's verdict goes to Learning and back to Vision
  shipped          -> Learning is told (no ground truth: agents never see it)

Message kinds follow the shared contract (REQUEST_EVIDENCE, EVIDENCE_RESPONSE, DECISION_REQUEST,
DECISION, ...). Every message is recorded with its size in bytes.

Honesty: in this simulation the agents compute exactly what the line's built-in policy computes;
`/sim/run` runs the reference line alongside and reports whether every decision matches. What the
agent version adds is the separation of knowledge, the message trace, the Process agent's drift
alarms and the Learning agent's check of the camera calibration on expert-confirmed cases.
Everything is SIMULATED.
"""
from __future__ import annotations
import json
import secrets
from math import sqrt

from .engine import surface_posterior, width_posterior, phi, TOL
from ..contracts import Evidence, sign_evidence
from ..collective.peer_protocol import PeerBus
from ..collective.trace import Trace

# adilnurgg's collaboration protocol (qualityrelay17/collective, AGENT-01..05) carries every evidence
# exchange between agents: role-signed messages, ACL from roles.py, ownership, VERIFY of station
# signature / staleness / lineage, and a trace. Our agents are bound to his registered roles:
ROLE_OF = {'vision': 'quality_inspector', 'vision_pi': 'additive_manufacturing_expert', 'metrology': 'metrology_engineer',
           'assembly': 'assembly_engineer', 'cost': 'operations_research', 'process': 'spc_agent',
           'learning': 'bayesian_statistician', 'governance': 'safety_governance'}
AGENT_OF = {v: (k if k != 'vision_pi' else 'vision') for k, v in ROLE_OF.items()}
OWNERSHIP = {'PHONE_IMAGE': 'quality_inspector', 'PI_IMAGE': 'additive_manufacturing_expert', 'CALIPER': 'metrology_engineer'}
STATION_KEYS = {st: f'sim-station-key-{st}' for st in ('phone', 'pi', 'phone_local', 'caliper', 'caliper_local')}
# Simulated parts can wait in the buffer for a long time; age is handled by the line's own SAFE-MESH
# evidence deadline (engine), so the bus freshness window is set to one shift.
BUS_MAX_AGE_S = 8 * 3600.0

AGENTS = {
    'vision': dict(name='Vision agent', inside='statistic', what='calibrated camera likelihoods -> P(surface defect)'),
    'metrology': dict(name='Metrology agent', inside='statistic', what='caliper reading -> Gaussian width posterior'),
    'process': dict(name='Process agent', inside='statistic', what='EWMA + two-sided CUSUM on caliper residuals per printer'),
    'assembly': dict(name='Assembly agent', inside='decision rule', what='combines both parts\' evidence into P(unsafe pair)'),
    'cost': dict(name='Cost agent', inside='decision rule', what='expected cost of PASS vs HOLD; threshold = hold / (hold + escape)'),
    'learning': dict(name='Learning agent', inside='statistic', what='camera flag vs expert verdict, Wilson interval vs calibration'),
    'governance': dict(name='Safety gate', inside='rule', what='receives every DECISION_PROPOSAL (SAFE-MESH role); missing or late evidence -> HOLD'),
}
for _k, _r in ROLE_OF.items():
    if _k in AGENTS:
        AGENTS[_k]['role'] = _r
KINDS = ('OBSERVATION', 'MEASUREMENT', 'REQUEST_EVIDENCE', 'EVIDENCE_RESPONSE', 'HYPOTHESIS_UPDATE', 'DECISION_PROPOSAL', 'DECISION_REQUEST', 'DECISION',
         'ALARM', 'PROPOSE_SETPOINT', 'REVIEW_OUTCOME', 'SHIPPED', 'PROPOSE_RECALIBRATION')


def _wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


class AgentTeam:
    def __init__(self, factory):
        self.f = factory
        self.messages = []          # [t, kind, sender, recipient, case, body, bytes]
        self.decisions = {}         # pair_id / part_id -> agent decision record
        # private stores: an agent reads only its own
        self.vision_store = {}      # part_id -> {'cams': {cam: flag}, 'site':, 'expert_cleared': bool}
        self.metrology_store = {}   # part_id -> (reading_mm, caliper_sd)
        self.process_state = {'cusum': {}, 'bias': {}, 'offset': {}}
        self.learning = {'flagged': 0, 'flag_confirmed': 0, 'predicted_sum': 0.0, 'reviews': 0, 'shipped': 0, 'proposals': []}
        self.alarms, self.setpoints = [], []
        # signed Evidence per part, owned by the role of the station that captured it
        self.evidence = {}          # part_id -> list[Evidence]
        self.role_keys = {r: secrets.token_hex(16) for r in set(ROLE_OF.values())}
        self.protocol = dict(requests=0, outcomes={}, verify={}, signatures_checked=0, cost_charged=0.0, decision_proposals=0)

    # ---- bus --------------------------------------------------------------------------
    def _send(self, kind, sender, recipient, case, body):
        b = len(json.dumps(body, separators=(',', ':'), default=str))
        self.messages.append([round(self.f.env.now, 3), kind, sender, recipient, case, body, b])
        return body

    # ---- inspection -------------------------------------------------------------------
    def on_inspected(self, p, site, obs, *, local=False):
        pid = p['part_id']
        cams = {c: v for c, (v, _t) in obs.items()}
        prev = self.vision_store.get(pid, {})
        # an expert clearance stays valid when the part is re-inspected at the assembly site
        self.vision_store[pid] = {'cams': cams, 'site': p['site'], 'expert_cleared': prev.get('expert_cleared', False)}
        self.metrology_store[pid] = (p['measured_mm'], p['caliper_sd'])
        now, cal = self.f.env.now, self.f.model.calibration_id
        ev = []
        for cam, v in cams.items():
            if v is None:
                continue  # a failed capture produces no evidence (SENSOR_FAILURE on request), never a 'clear'
            kind = 'PI_IMAGE' if cam == 'pi' else 'PHONE_IMAGE'
            ev.append(sign_evidence(Evidence(f'{pid}:{cam}:{now:.3f}', pid, cam, kind, 'SIMULATED', f'frame:{pid}:{cam}:{now:.3f}', now,
                                             'suspect' if v else 'clear', {}, calibration_id=cal), STATION_KEYS[cam]))
        st = 'caliper_local' if local else 'caliper'
        ev.append(sign_evidence(Evidence(f'{pid}:{st}:{now:.3f}', pid, st, 'CALIPER', 'SIMULATED', f'reading:{pid}:{st}:{now:.3f}', now,
                                         'verified', {'measurement_mm': p['measured_mm'], 'uncertainty_mm': p['caliper_sd'],
                                                      'unit': 'mm', 'validated': True}, calibration_id='caliper-sim'), STATION_KEYS[st]))
        self.evidence[pid] = ev
        where = 'assembly-site re-inspection' if local else site.name
        self._send('OBSERVATION', 'vision', 'vision', pid, {'cams': {c: (None if v is None else ('suspect' if v else 'clear')) for c, v in cams.items()},
                                                            'where': where})
        self._send('MEASUREMENT', 'metrology', 'process', pid, {'kind': p['kind'], 'site': site.name, 'reading_mm': round(p['measured_mm'], 4),
                                                                'offset_mm': round(p.get('offset_mm', 0.0), 4)})
        if not local:
            self._process_observe(p, site)

    def _process_observe(self, p, site):
        """Same EWMA / CUSUM as the line monitor (engine._monitor); the team test checks they agree."""
        f, st = self.f, self.process_state
        key = (site.name, p['kind'])
        nominal = f.design['slot_opening_mm'] if p['kind'] == 'slot' else f.design['tab_width_mm']
        r = p['measured_mm'] - nominal - p.get('offset_mm', 0.0)
        r_c = max(-0.2, min(0.2, r))
        sigma = (site.width_sd_mm ** 2 + site.caliper_sd_mm ** 2) ** 0.5
        hi, lo = st['cusum'].get(key, (0.0, 0.0))
        z = r_c / sigma
        hi, lo = max(0.0, hi + z - 0.5), max(0.0, lo - z - 0.5)
        if hi > 5 or lo > 5:
            a = dict(t=round(f.env.now, 1), site=site.name, kind=p['kind'], direction='wide' if hi > 5 else 'narrow', part=p['part_id'])
            self.alarms.append(a)
            self._send('ALARM', 'process', 'assembly', p['part_id'], {'site': site.name, 'kind': p['kind'], 'direction': a['direction'],
                                                                      'cusum': round(max(hi, lo), 2)})
            hi = lo = 0.0
        st['cusum'][key] = (hi, lo)
        if f.feedback != 'ewma':
            return
        est = (1 - f.ewma_lambda) * st['bias'].get(key, 0.0) + f.ewma_lambda * r_c
        st['bias'][key] = est
        new = -est if abs(est) > f.deadband else st['offset'].get(key, 0.0)
        if abs(new - st['offset'].get(key, 0.0)) > 0.02:
            st['offset'][key] = new
            self.setpoints.append(dict(t=round(f.env.now, 1), site=site.name, kind=p['kind'], estimate_mm=round(est, 4), offset_mm=round(new, 4)))
            self._send('PROPOSE_SETPOINT', 'process', 'process', p['part_id'], {'site': site.name, 'kind': p['kind'],
                                                                               'estimate_mm': round(est, 4), 'offset_mm': round(new, 4)})

    # ---- vision side ------------------------------------------------------------------
    def _vision_surface(self, pid):
        """Vision answers from its own store only."""
        f, rec = self.f, self.vision_store.get(pid)
        if rec is None:
            return None, 'NO_OBSERVATION'
        if rec['expert_cleared']:
            return 0.001, 'EXPERT_CLEARED'
        if f.sc.evidence_sharing == 'summary' and rec['site'] != f.sc.assembly_site:
            return f.model.p_crack_given_supplier_pass, 'SUPPLIER_SUMMARY'
        return surface_posterior(rec['cams'], f.model, tuple(rec['cams'])), 'CAMERAS'

    def part_gate(self, p, cams, threshold):
        """Vision asks Cost whether a part may continue on its surface evidence alone."""
        pid, f = p['part_id'], self.f
        vals = {c: p['obs'][c][0] for c in cams if c in p['obs']}
        if f.policy == 'hold_all':
            hold, reason, ps = not p.get('expert_cleared'), 'HOLD_ALL_POLICY', None
        elif f.policy == 'rules':
            hold, reason, ps = any(v is None or v for v in vals.values()), 'RULE_ANY_FLAG_OR_MISSING', None
        else:
            ps = surface_posterior(vals, f.model, tuple(vals))
            hold, reason = ps >= threshold, 'SURFACE_RISK'
        self._send('DECISION_REQUEST', 'vision', 'cost', pid, {'stage': 'part', 'p_surface': None if ps is None else round(ps, 6),
                                                               'flags': {c: v for c, v in vals.items()}})
        self._send('DECISION', 'cost', 'vision', pid, {'stage': 'part', 'decision': 'HOLD' if hold else 'PASS', 'reason': reason,
                                                       'threshold': round(threshold, 5),
                                                       'expected_cost_pass': None if ps is None else round(ps * f.costs.escaped_defect, 4),
                                                       'expected_cost_hold': f.costs.hold})
        self.decisions[pid] = dict(stage='part', t=round(f.env.now, 3), decision='HOLD' if hold else 'PASS', reason=reason,
                                   p=None if ps is None else round(ps, 6))
        return hold

    # ---- assembly side ----------------------------------------------------------------
    def pair_decision(self, s, t, *, stale, threshold, pair_id):
        f = self.f
        bus = self._bus()
        self._rejected = []
        ev = {}
        for part, kind in ((s, 'slot'), (t, 'tab')):
            pid = part['part_id']
            got = self._request(bus, pid, pair_id)
            # surface: Vision's calibrated likelihoods applied to the VERIFIED camera verdicts it received
            cams = {x['station_id']: x['verdict'] == 'suspect' for x in got if x['kind'] in ('PHONE_IMAGE', 'PI_IMAGE')}
            rec = self.vision_store.get(pid, {})
            if rec.get('expert_cleared'):
                ps, src = 0.001, 'EXPERT_CLEARED'
            elif f.sc.evidence_sharing == 'summary' and rec.get('site') != f.sc.assembly_site:
                ps, src = f.model.p_crack_given_supplier_pass, 'SUPPLIER_SUMMARY'
            else:
                ps, src = surface_posterior(cams, f.model, tuple(cams)), 'CAMERAS'
            cal = [x for x in got if x['kind'] == 'CALIPER']
            if cal:
                reading, sd = cal[0]['payload']['measurement_mm'], cal[0]['payload']['uncertainty_mm']
            else:  # no verified reading: fall back to the prior only (decision will be conservative)
                reading, sd = part['measured_mm'], part['caliper_sd']
            mu, var = width_posterior(reading, kind, f.model, sd)
            self._send('HYPOTHESIS_UPDATE', 'assembly', 'assembly', pair_id, {'part': pid, 'p_surface': round(ps, 6), 'source': src,
                                                                             'mean_mm': round(mu, 4), 'sd_mm': round(sqrt(var), 4)})
            ev[kind] = dict(ps=ps, mu=mu, var=var, reading=reading)
        measured_clear = ev['slot']['reading'] - ev['tab']['reading']
        p_dim = phi((TOL - (ev['slot']['mu'] - ev['tab']['mu'])) / sqrt(ev['slot']['var'] + ev['tab']['var']))
        p_unsafe = 1 - (1 - ev['slot']['ps']) * (1 - ev['tab']['ps']) * (1 - p_dim)
        if stale:
            hold, reason = True, 'STALE_OR_MISSING_EVIDENCE'
        elif self._rejected:  # VERIFY refused a record (forged, stale, duplicate source, ACL, timeout): SAFE-MESH -> HOLD
            hold, reason = True, 'UNVERIFIED_EVIDENCE'
        elif f.policy == 'rules':
            hold, reason = measured_clear < TOL, 'RULE_CLEARANCE'
        elif f.policy == 'hold_all':
            hold, reason = measured_clear < TOL, 'RULE_CLEARANCE_AFTER_REVIEW'
        else:
            hold = p_unsafe >= threshold
            # which evidence drives the risk (for the Pareto of HOLD reasons)
            parts = {'DIMENSIONAL_RISK': p_dim, 'SURFACE_RISK_SLOT': ev['slot']['ps'], 'SURFACE_RISK_TAB': ev['tab']['ps']}
            reason = max(parts, key=parts.get) if hold else 'BAYES_THRESHOLD'
        self._send('DECISION_REQUEST', 'assembly', 'cost', pair_id, {'stage': 'pair', 'p_unsafe': round(p_unsafe, 6), 'p_dimensional': round(p_dim, 6),
                                                                     'measured_clearance_mm': round(measured_clear, 4), 'stale': stale})
        self._send('DECISION', 'cost', 'assembly', pair_id, {'stage': 'pair', 'decision': 'HOLD' if hold else 'PASS', 'reason': reason,
                                                             'threshold': round(threshold, 5),
                                                             'expected_cost_pass': round(p_unsafe * f.costs.escaped_defect, 4),
                                                             'expected_cost_hold': f.costs.hold})
        prop = bus.make('DECISION_PROPOSAL', 'assembly_engineer', 'safety_governance', pair_id,
                        {'state': 'HOLD' if hold else 'PASS_REVIEW', 'reasons': [reason], 'p_unsafe': round(p_unsafe, 6),
                         'decided_by': 'operations_research (Cost agent)'})
        bus.send(prop)
        self.protocol['decision_proposals'] += 1
        self._log_bus(prop, 'governance')
        self.decisions[pair_id] = dict(stage='pair', t=round(f.env.now, 3), decision='HOLD' if hold else 'PASS', reason=reason,
                                       p=round(p_unsafe, 6), p_dim=round(p_dim, 6), slot=s['part_id'], tab=t['part_id'],
                                       measured_clearance_mm=round(measured_clear, 4))
        return hold, ('STALE_OR_MISSING_EVIDENCE' if stale else reason if reason == 'UNVERIFIED_EVIDENCE' else
                      ('BAYES_THRESHOLD' if f.policy == 'bayes' else reason)), p_unsafe

    # ---- adilnurgg's PeerBus ------------------------------------------------------------------
    def _bus(self):
        now = self.f.env.now
        bus = PeerBus(role_keys=self.role_keys, station_keys=STATION_KEYS, ownership=OWNERSHIP, now=now,
                      max_age_s=BUS_MAX_AGE_S, trace=Trace(now=now), request_cost=self.f.costs.peer_request)
        for role in ('assembly_engineer', 'quality_inspector', 'additive_manufacturing_expert', 'metrology_engineer', 'safety_governance'):
            bus.register(role, [])
        return bus

    def _log_bus(self, m, recipient_agent=None):
        d = m.to_dict()
        b = len(json.dumps(d, separators=(',', ':'), default=str))
        frm, to = AGENT_OF.get(m.sender_role, m.sender_role), recipient_agent or AGENT_OF.get(m.recipient_role, m.recipient_role)
        body = {**m.body, 'protocol': 'PeerBus', 'roles': f'{m.sender_role}->{m.recipient_role}', 'signed': bool(m.signature)}
        if 'summaries' in body:  # keep the UI light: identifiers and verdicts, not the full records
            body['summaries'] = [{k: x.get(k) for k in ('kind', 'station_id', 'verdict', 'verification_status', 'payload')} for x in body['summaries']]
        self.messages.append([round(self.f.env.now, 3), m.kind, frm, to, m.case_id, body, b])

    def _request(self, bus, pid, case_label):
        """assembly_engineer asks each owner for this part's evidence through the bus; returns VERIFIED summaries."""
        own = {'quality_inspector': [], 'additive_manufacturing_expert': [], 'metrology_engineer': []}
        for e in self.evidence.get(pid, []):
            own[OWNERSHIP[e.kind]].append(e)
        for role, evs in own.items():
            bus.store(role).own = evs
        before = bus.cost_charged
        kinds = ['PHONE_IMAGE'] + (['PI_IMAGE'] if 'pi' in self.f.sc.cameras else []) + ['CALIPER']
        got = []
        for kind in kinds:
            req = bus.make('REQUEST_EVIDENCE', 'assembly_engineer', OWNERSHIP[kind], pid,
                           {'requested_kind': kind, 'reason_code': 'PAIR_GATE', 'hypotheses': ['surface_defect', 'clearance_below_0.5mm'],
                            'max_cost': self.f.costs.peer_request, 'deadline_ms': 1500, 'pair': case_label})
            reply = bus.send(req)
            self._log_bus(req); self._log_bus(reply)
            P = self.protocol
            P['requests'] += 1; P['signatures_checked'] += 2
            out = reply.body['outcome']; P['outcomes'][out] = P['outcomes'].get(out, 0) + 1
            if out not in ('GRANTED', 'SENSOR_FAILURE'):  # SENSOR_FAILURE = a capture that never happened (treated as no reading)
                self._rejected.append((pid, kind, out))
            for x in reply.body['summaries']:
                P['verify'][x['verification_status']] = P['verify'].get(x['verification_status'], 0) + 1
                if x['verification_status'] == 'VERIFIED':
                    got.append(x)
        self.protocol['cost_charged'] += bus.cost_charged - before
        return got

    # ---- outcomes -----------------------------------------------------------------------
    def on_review(self, case, outcome, *, flagged_parts=(), confirmed_parts=()):
        """Expert verdict after a HOLD. Learning compares the share of surface holds the expert confirmed
        with the share the Vision agent predicted (mean P(surface defect) at the hold): a calibration check."""
        L = self.learning
        L['reviews'] += 1
        for pid in flagged_parts:
            L['flagged'] += 1
            L['predicted_sum'] += (self.decisions.get(pid) or {}).get('p') or 0.0
            if pid in confirmed_parts:
                L['flag_confirmed'] += 1
        self._send('REVIEW_OUTCOME', 'assembly', 'learning', case, {'outcome': outcome, 'flagged': list(flagged_parts),
                                                                    'confirmed': list(confirmed_parts)})
        if outcome == 'cleared':
            for pid in flagged_parts or ():
                if pid in self.vision_store:
                    self.vision_store[pid]['expert_cleared'] = True
            self._send('REVIEW_OUTCOME', 'learning', 'vision', case, {'expert_cleared': list(flagged_parts)})
        # precision of a camera flag on confirmed cases vs what the calibration predicts
        if L['flagged'] >= 10 and L['flagged'] % 5 == 0:
            lo, hi = _wilson(L['flag_confirmed'], L['flagged'])
            expected = L['predicted_sum'] / L['flagged']
            if not (lo <= expected <= hi):
                prop = dict(t=round(self.f.env.now, 1), flagged=L['flagged'], confirmed=L['flag_confirmed'], ci=[round(lo, 3), round(hi, 3)],
                            expected=round(expected, 3))
                L['proposals'].append(prop)
                self._send('PROPOSE_RECALIBRATION', 'learning', 'vision', case, prop)

    def on_shipped(self, rec):
        self.learning['shipped'] += 1
        self._send('SHIPPED', 'assembly', 'learning', rec['pair_id'], {'pair': rec['pair_id']})

    # ---- export -----------------------------------------------------------------------
    def export(self):
        senders = {}
        for m in self.messages:
            d = senders.setdefault(m[2], dict(sent=0, bytes=0)); d['sent'] += 1; d['bytes'] += m[6]
        f = self.f
        spc = {'nominal_mm': {'slot': f.design['slot_opening_mm'], 'tab': f.design['tab_width_mm']},
               'sigma_mm': {s.name: round((s.width_sd_mm ** 2 + s.caliper_sd_mm ** 2) ** 0.5, 4) for s in f.sc.sites},
               'cusum': {'k': 0.5, 'h': 5}, 'clip_mm': 0.2}
        self.protocol['cost_charged'] = round(self.protocol['cost_charged'], 4)
        return dict(roster=AGENTS, kinds=list(KINDS), messages=self.messages, decisions=self.decisions, spc=spc, protocol=self.protocol,
                    protocol_source='qualityrelay17/collective (adilnurgg): PeerBus, role-signed messages, ACL, VERIFY',
                    alarms=self.alarms, setpoints=self.setpoints, learning=self.learning, per_agent=senders,
                    total_messages=len(self.messages), total_bytes=sum(m[6] for m in self.messages))
