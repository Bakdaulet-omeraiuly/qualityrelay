"""SIM-01: Digital Factory engine (level 1.5) -- the physical Slot/Tab story as a factory.

    Slot printers ┐                                        ┌-> Assembly -> Sorting -> ship
                  ├-> transport -> Phone -> Pi -> Metrology -> part gate -> pairing buffer -> pair gate
    Tab printers  ┘                       (operator)            |                          |
                                                                 └-> Review (operator) <---┘ HOLD
                                                                       ├-> back to buffer / assembly
                                                                       ├-> Rework (operator) -> assembly | scrap
                                                                       └-> scrap
Modelled: batch printing (one print job = one lot), CONWIP cap (finite system buffer), printer
and station failures (exponential MTBF / MTTR), transport time, a shared operator pool for
Metrology/Review/Rework, rework, scrap, part genealogy, multiple inspection lines, multiple
supplier sites with inter-site transport, evidence latency and three evidence-sharing modes.

Policies: 'rules' (fixed OR rule, the B0 analogue) and 'bayes' (calibrated posterior + Bayes
break-even threshold, the B1 analogue). Pairing: 'fifo' or 'optimized' (SIM-05,
optimization.match_batch). Common random numbers: identical parts, sensor noise, service noise
and failure times for every policy. Every output is SIMULATED; timings are ILLUSTRATIVE.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import sqrt
from random import Random
from statistics import mean, pvariance

from ..economics import Costs
from . import SOURCE_TIER, MODEL_VERSION
from .cad import nominal_design
from .des import Env, Signal
from .scenarios import FactoryScenario, SiteConfig, STATION_S, draw_part, truth_hash

TOL = 0.5
POLICIES = ('rules', 'bayes', 'hold_all')  # hold_all: the Gate-A B7 degenerate optimum, run through a real review station
PAIRINGS = ('fifo', 'optimized')


def phi(x):
    from math import erf
    return 0.5 * (1 + erf(x / sqrt(2)))


@dataclass(frozen=True)
class PartModel:
    """Held-out calibration of the bayes policy (nominal scenario, seeds 1000-1009)."""
    crack_prior: float
    phone_sens: float; phone_spec: float
    pi_sens: float; pi_spec: float
    slot_mean: float; slot_var: float
    tab_mean: float; tab_var: float
    p_crack_given_supplier_pass: float
    calibration_id: str


def calibrate_part_model(seeds=range(1000, 1010), n=600) -> PartModel:
    sc = FactoryScenario('CAL', 'calibration'); design = nominal_design(); site = SiteConfig()
    tp = {'phone': [0, 0], 'pi': [0, 0]}; tn = {'phone': [0, 0], 'pi': [0, 0]}
    cracks = total = 0; widths = {'slot': [], 'tab': []}; passed = passed_crack = 0
    for s in seeds:
        for kind in ('slot', 'tab'):
            for i in range(n):
                p = draw_part(sc, s, kind, i, site, 0.0, f'cal-{s}-{i // 4}', design)
                total += 1; cracks += p['crack']; widths[kind].append(p['caliper'][0])
                for cam in ('phone', 'pi'):
                    f = p['cam'][cam]
                    if p['crack']:
                        tp[cam][0] += bool(f); tp[cam][1] += 1
                    else:
                        tn[cam][0] += (not f); tn[cam][1] += 1
                if not (p['cam']['phone'] or p['cam']['pi']):
                    passed += 1; passed_crack += p['crack']
    r = lambda k, n_: (k + 0.5) / (n_ + 1)  # noqa: E731  Jeffreys-smoothed
    sd = site.caliper_sd_mm ** 2
    m = PartModel(crack_prior=r(cracks, total), phone_sens=r(*tp['phone']), phone_spec=r(*tn['phone']),
                  pi_sens=r(*tp['pi']), pi_spec=r(*tn['pi']),
                  slot_mean=mean(widths['slot']), slot_var=max(1e-4, pvariance(widths['slot']) - sd),
                  tab_mean=mean(widths['tab']), tab_var=max(1e-4, pvariance(widths['tab']) - sd),
                  p_crack_given_supplier_pass=r(passed_crack, passed), calibration_id=f'partcal-{min(seeds)}-{max(seeds)}-{n}')
    return m


def surface_posterior(cams: dict, m: PartModel, which=('phone', 'pi')) -> float:
    p = m.crack_prior
    for cam in which:
        f = cams.get(cam)
        if f is None:
            continue
        sens, spec = (m.phone_sens, m.phone_spec) if cam.startswith('phone') else (m.pi_sens, m.pi_spec)
        ld, lg = (sens, 1 - spec) if f else (1 - sens, spec)
        p = p * ld / (p * ld + (1 - p) * lg)
    return p


def width_posterior(reading: float, kind: str, m: PartModel, caliper_sd: float):
    mu0, v0 = (m.slot_mean, m.slot_var) if kind == 'slot' else (m.tab_mean, m.tab_var)
    s2 = caliper_sd ** 2
    v = v0 * s2 / (v0 + s2)
    return v * (mu0 / v0 + reading / s2), v


def pair_unsafe_probability(slot_post, tab_post, ps_slot, ps_tab):
    (ms, vs), (mt, vt) = slot_post, tab_post
    p_dim = phi((TOL - (ms - mt)) / sqrt(vs + vt))
    return 1 - (1 - ps_slot) * (1 - ps_tab) * (1 - p_dim)


class Factory:
    def __init__(self, sc: FactoryScenario, seed: int, policy: str, pairing: str = 'fifo', *, costs: Costs | None = None,
                 model: PartModel | None = None, batch_k: int = 8, keep_log: bool = True,
                 pair_timeout_s: float | None = None, reprint: bool = False, max_reprints: int = 2):
        if policy not in POLICIES or pairing not in PAIRINGS:
            raise ValueError('unknown policy/pairing')
        if sc.evidence_sharing not in ('full', 'summary', 'none'):
            raise ValueError('evidence_sharing')
        self.sc, self.seed, self.policy, self.pairing = sc, seed, policy, pairing
        self.costs = costs or Costs(); self.model = model or calibrate_part_model()
        self.batch_k, self.keep_log = batch_k, keep_log
        # Optimised pairing waits for batch_k of each kind. pair_timeout_s (None = registered
        # behaviour) releases a partial batch once a part has waited that long.
        self.pair_timeout_s = pair_timeout_s
        # Closed loop: a confirmed-defective part is replaced by a reprint from the nominal CAD model
        # (printer re-zeroed), which goes through the full inspection again. Off by default so the
        # registered SIM results are unchanged.
        self.reprint, self.max_reprints = reprint, max_reprints
        self.design = nominal_design()
        self.env = env = Env()
        self.site = {s.name: s for s in sc.sites}
        if sc.assembly_site not in self.site and len(sc.sites) > 1:
            self.site[sc.assembly_site] = SiteConfig(sc.assembly_site, makes='none', printers=1)
        mk = lambda n, c: env.resource(n, c)  # noqa: E731
        # Kit-based CONWIP: one token pool per part kind. A single shared pool deadlocks when it
        # fills with one kind (all slots, no tabs): nothing can pair, nothing frees a token.
        self.wip = {k: mk(f'WIP-{k}', max(8, sc.wip_cap // 2)) for k in ('slot', 'tab')}
        self.res = {}
        for s in self.site.values():
            if s.makes != 'none':
                self.res[(s.name, 'printer')] = mk(f'{s.name}:printer', s.printers)
                for line in range(s.inspection_lines):
                    for st in ('phone', 'pi', 'caliper'):
                        self.res[(s.name, st, line)] = mk(f'{s.name}:{st}:{line}', 1)
            self.res[(s.name, 'operator')] = mk(f'{s.name}:operator', sc.operators)
        a = sc.assembly_site
        for st in ('phone_local', 'caliper_local'):
            self.res[(a, st)] = mk(f'{a}:{st}', 1)
        self.res[(a, 'assembly')] = mk(f'{a}:assembly', sc.assembly_capacity)
        self.res[(a, 'sorting')] = mk(f'{a}:sorting', sc.assembly_capacity)
        self.res[(a, 'review')] = mk(f'{a}:review', sc.review_capacity)
        self.res[(a, 'rework')] = mk(f'{a}:rework', 1)
        self._next_fail = {}
        self.parts, self.pairs, self.events = [], [], []
        self.buffer = {'slot': [], 'tab': []}
        self.down_s = 0.0
        self.upstream = 0
        self.upstream_done = Signal()
        self.hold_part_seconds = 0.0
        self.stats = dict(part_reviews=0, pair_reviews=0, reworks=0, rework_ok=0, scrapped_parts=0, scrapped_good_parts=0,
                          shipped=0, escaped=0, shipped_good=0, holds_stale_evidence=0, part_holds=0, pair_holds=0,
                          local_reinspections=0, released_after_review=0, reprints=0)

    # ---- helpers -------------------------------------------------------------------
    def _svc(self, key, mean_s):
        r = Random(f'svc:{self.seed}:{key}')
        return max(0.05 * mean_s, r.lognormvariate(0, 0.16) * mean_s)

    def _failure_delay(self, res):
        """Repair time to add if this resource has failed since its last use (exponential MTBF)."""
        sc = self.sc
        if res.name.startswith('WIP') or 'operator' in res.name:
            return 0.0
        mtbf = sc.mtbf_s / max(1e-9, sc.failure_scale)
        rng = self._next_fail.setdefault(res.name, [Random(f'fail:{self.seed}:{res.name}'), None])
        if rng[1] is None:
            rng[1] = rng[0].expovariate(1 / mtbf)
        delay = 0.0
        while self.env.now >= rng[1]:
            rep = rng[0].expovariate(1 / sc.mttr_s)
            delay += rep
            rng[1] = self.env.now + delay + rng[0].expovariate(1 / mtbf)
        self.down_s += delay
        return delay

    def _work(self, resources, key, mean_s, station):
        req = {r: 1 for r in resources}
        yield ('acquire', req)
        start = self.env.now
        delay = self._failure_delay(resources[0])
        yield ('timeout', delay + self._svc(key, mean_s))
        yield ('release', req)
        if self.keep_log:
            self.events.append((round(start, 3), round(self.env.now, 3), station, key))

    def _threshold(self):
        esc = self.costs.escaped_defect
        if self.sc.cost_shock_at_s is not None and self.env.now >= self.sc.cost_shock_at_s:
            esc *= self.sc.cost_shock_escape_multiplier
        return self.costs.hold / (self.costs.hold + esc)

    # ---- processes -----------------------------------------------------------------
    def printer(self, site: SiteConfig, jobs):
        pr = self.res[(site.name, 'printer')]
        for job_id, kind, idxs in jobs:
            yield ('acquire', {self.wip[kind]: len(idxs)})
            yield ('acquire', {pr: 1})
            t0 = self.env.now
            delay = self._failure_delay(pr)
            yield ('timeout', delay + self._svc(f'print:{job_id}', site.print_setup_s + site.print_per_part_s * len(idxs)))
            yield ('release', {pr: 1})
            for k, i in enumerate(idxs):
                p = draw_part(self.sc, self.seed, kind, i, site, t0, f'{site.name}:{job_id}', self.design)
                p['line'] = i % site.inspection_lines
                self.parts.append(p)
                self.env.process(self.part(p, site))

    def part(self, p, site):
        sc, m = self.sc, self.model
        yield ('timeout', self._svc(f'tr:{p["part_id"]}', sc.transport_s))
        line = p['line']
        obs = {}
        for st in ('phone', 'pi'):
            yield from self._work([self.res[(site.name, st, line)]], f'{st}:{p["part_id"]}', STATION_S[st], st)
            val = p['cam'][st]
            if st == 'pi' and any(a <= self.env.now < b for a, b in sc.partition_windows_s):
                val = None  # Pi edge unreachable: no reading, never a 'clear'
            obs[st] = (val, self.env.now)
        yield from self._work([self.res[(site.name, 'caliper', line)], self.res[(site.name, 'operator')]],
                              f'cal:{p["part_id"]}', STATION_S['caliper'], 'caliper')
        p['obs'] = obs
        p['obs_raw'] = {k: v for k, (v, _t) in obs.items()}  # display copy; review may clear p['obs']
        p['measured_mm'] = p['caliper'][0]
        p['caliper_sd'] = site.caliper_sd_mm
        p['evidence_at'] = self.env.now + sc.evidence_latency_s
        # supplier-side part gate
        if self._part_hold(p, ('phone', 'pi')):
            self.stats['part_holds'] += 1
            ok = yield from self._review_part(p)
            if not ok:
                self._upstream_exit(); return
        if site.name != sc.assembly_site:
            yield ('timeout', sc.inter_site_transport_s)
            if sc.evidence_sharing == 'none':
                # coordinator/sharing lost: assembly site re-inspects with its own camera + caliper
                self.stats['local_reinspections'] += 1
                a = sc.assembly_site
                yield from self._work([self.res[(a, 'phone_local')]], f'pl:{p["part_id"]}', STATION_S['phone'], 'phone_local')
                yield from self._work([self.res[(a, 'caliper_local')], self.res[(a, 'operator')]], f'cl:{p["part_id"]}',
                                      STATION_S['caliper'], 'caliper_local')
                p['obs'] = {'phone_local': (p['cam']['phone_local'], self.env.now)}
                p['obs_raw'] = {'phone_local': p['cam']['phone_local']}
                p['measured_mm'] = p['caliper'][1]
                p['caliper_sd'] = self.site[a].caliper_sd_mm if a in self.site else 0.05
                p['evidence_at'] = self.env.now
                if self._part_hold(p, ('phone_local',)):
                    self.stats['part_holds'] += 1
                    ok = yield from self._review_part(p)
                    if not ok:
                        self._upstream_exit(); return
        self.buffer[p['kind']].append(p)
        self._upstream_exit()
        self._try_pair()
        if self.pairing == 'optimized' and self.pair_timeout_s is not None:
            self.env.process(self._pair_timer(p))

    def _upstream_exit(self):
        self.upstream -= 1
        if self.upstream == 0:
            self.env.fire(self.upstream_done)
            self._try_pair(flush=True)

    def _part_hold(self, p, cams):
        vals = {c: p['obs'][c][0] for c in cams if c in p['obs']}
        if self.policy == 'hold_all':
            return not p.get('expert_cleared')
        if self.policy == 'rules':
            return any(v is None or v for v in vals.values())
        return surface_posterior(vals, self.model, tuple(vals)) >= self._threshold()

    def _review_part(self, p):
        self.stats['part_reviews'] += 1
        a = self.sc.assembly_site
        t0 = self.env.now
        yield from self._work([self.res[(a, 'review')], self.res[(a, 'operator')]], f'rv:{p["part_id"]}', STATION_S['review'], 'review')
        self.hold_part_seconds += self.env.now - t0
        if p['expert_crack_seen'] or abs(p['expert_width_mm'] - (self.design['slot_opening_mm'] if p['kind'] == 'slot' else self.design['tab_width_mm'])) > 0.6:
            self._scrap(p); return False
        p['reviewed'] = True
        p['obs'] = {}  # expert cleared the surface; fused below as 'cleared'
        p['expert_cleared'] = True
        self.stats['released_after_review'] += 1
        return True

    def _scrap(self, p):
        self.stats['scrapped_parts'] += 1
        if not p['crack'] and not p['warped']:
            self.stats['scrapped_good_parts'] += 1
        p['fate'] = 'scrap'
        self.env.process(self._release_wip(p['kind'], 1))
        if self.reprint and p.get('reprints', 0) < self.max_reprints:
            self.upstream += 1  # the replacement must pass the line before the buffer is flushed
            self.stats['reprints'] += 1
            self.env.process(self._reprint(p))

    def _reprint(self, old):
        site = self.site[old['site']]
        pr = self.res[(site.name, 'printer')]
        n = old.get('reprints', 0) + 1
        root = old.get('root_id', old['part_id'])
        yield ('acquire', {self.wip[old['kind']]: 1})
        yield ('acquire', {pr: 1})
        t0 = self.env.now
        delay = self._failure_delay(pr)
        yield ('timeout', delay + self._svc(f'reprint:{root}:{n}', site.print_setup_s + site.print_per_part_s))
        yield ('release', {pr: 1})
        p = draw_part(self.sc, self.seed, old['kind'], 10_000_000 * n + old['idx'], site, t0, f'{site.name}:reprint',
                      self.design, seq_idx=old['seq_idx'], corrected=True)
        p.update(part_id=f'{root}-R{n}', root_id=root, reprints=n, reprint_of=old['part_id'], line=old['line'])
        old['reprinted_as'] = p['part_id']
        self.parts.append(p)
        self.env.process(self.part(p, site))

    def _release_wip(self, kind, n):
        yield ('release', {self.wip[kind]: n})

    def _try_pair(self, flush=False):
        S, T = self.buffer['slot'], self.buffer['tab']
        if self.pairing == 'fifo':
            while S and T:
                self._spawn_pair(S.pop(0), T.pop(0))
            return
        from .optimization import match_batch
        k = self.batch_k
        while (len(S) >= k and len(T) >= k) or (flush or self.upstream == 0) and S and T:
            take = min(k, len(S), len(T))
            ss, ts = S[:take], T[:take]
            del S[:take]; del T[:take]
            for s, t in match_batch(ss, ts, self):
                self._spawn_pair(s, t)

    def _pair_timer(self, p):
        yield ('timeout', self.pair_timeout_s)
        if p in self.buffer[p['kind']]:
            self._try_pair(flush=True)

    def _ps(self, p):
        if p.get('expert_cleared'):
            return 0.001
        if self.sc.evidence_sharing == 'summary' and p['site'] != self.sc.assembly_site:
            return self.model.p_crack_given_supplier_pass
        vals = {c: v for c, (v, _) in p['obs'].items()}
        return surface_posterior(vals, self.model, tuple(vals))

    def pair_risk(self, s, t):
        return pair_unsafe_probability(width_posterior(s['measured_mm'], 'slot', self.model, s['caliper_sd']),
                                       width_posterior(t['measured_mm'], 'tab', self.model, t['caliper_sd']),
                                       self._ps(s), self._ps(t))

    def _spawn_pair(self, s, t):
        self.env.process(self.pair(s, t))

    def pair(self, s, t):
        sc = self.sc
        pid = f'P-{s["part_id"]}+{t["part_id"]}'
        rec = dict(pair_id=pid, slot_id=s['part_id'], tab_id=t['part_id'], slot_lot=s['lot_id'], tab_lot=t['lot_id'],
                   slot_site=s['site'], tab_site=t['site'], formed_s=round(self.env.now, 3))
        ready = max(s['evidence_at'], t['evidence_at'])
        stale = ready - self.env.now > sc.evidence_deadline_s
        yield ('timeout', min(max(0.0, ready - self.env.now), sc.evidence_deadline_s))
        true_clear = s['true_width_mm'] - t['true_width_mm']
        safe = true_clear >= TOL and not s['crack'] and not t['crack']
        if stale:
            hold, reason = True, 'STALE_OR_MISSING_EVIDENCE'
            self.stats['holds_stale_evidence'] += 1
        elif self.policy == 'rules':
            hold, reason = (s['measured_mm'] - t['measured_mm']) < TOL, 'RULE_CLEARANCE'
        elif self.policy == 'hold_all':
            hold, reason = (s['measured_mm'] - t['measured_mm']) < TOL, 'RULE_CLEARANCE_AFTER_REVIEW'
        else:
            p = self.pair_risk(s, t)
            rec['p_unsafe'] = round(p, 6)
            hold, reason = p >= self._threshold(), 'BAYES_THRESHOLD'
        rec.update(decision='HOLD' if hold else 'PASS_REVIEW', reason=reason, truly_safe=safe,
                   true_clearance_mm=round(true_clear, 4))
        if hold:
            self.stats['pair_holds'] += 1
            outcome = yield from self._review_pair(s, t, rec)
            if outcome != 'assemble':
                self.pairs.append(rec); return
        yield from self._assemble(s, t, rec)
        self.pairs.append(rec)

    def _review_pair(self, s, t, rec):
        self.stats['pair_reviews'] += 1
        a = self.sc.assembly_site
        t0 = self.env.now
        yield from self._work([self.res[(a, 'review')], self.res[(a, 'operator')]], f'rvp:{rec["pair_id"]}', STATION_S['review'], 'review')
        self.hold_part_seconds += 2 * (self.env.now - t0)
        bad = [p for p in (s, t) if p['expert_crack_seen']]
        for p in bad:
            self._scrap(p)
        if bad:
            for p in (s, t):
                if p not in bad:
                    self.buffer[p['kind']].insert(0, p)  # partner returns to the buffer (re-pairable)
            self._try_pair(flush=self.upstream == 0)
            rec['fate'] = 'split_after_review'
            return 'split'
        if s['expert_width_mm'] - t['expert_width_mm'] >= TOL:
            self.stats['released_after_review'] += 1
            rec['fate'] = 'released_after_review'
            return 'assemble'
        self.stats['reworks'] += 1
        t1 = self.env.now
        yield from self._work([self.res[(a, 'rework')], self.res[(a, 'operator')]], f'rw:{rec["pair_id"]}', STATION_S['rework'], 'rework')
        self.hold_part_seconds += 2 * (self.env.now - t1)
        if t['rework_ok']:
            self.stats['rework_ok'] += 1
            t['true_width_mm'] = s['true_width_mm'] - 0.8  # tab sanded to the design clearance
            rec['fate'] = 'reworked'
            return 'assemble'
        self._scrap(t)
        self.buffer['slot'].insert(0, s)
        self._try_pair(flush=self.upstream == 0)
        rec['fate'] = 'rework_failed'
        return 'split'

    def _assemble(self, s, t, rec):
        a = self.sc.assembly_site
        yield from self._work([self.res[(a, 'assembly')]], f'as:{rec["pair_id"]}', STATION_S['assembly'], 'assembly')
        yield from self._work([self.res[(a, 'sorting')]], f'so:{rec["pair_id"]}', STATION_S['sorting'], 'sorting')
        safe_now = (s['true_width_mm'] - t['true_width_mm']) >= TOL and not s['crack'] and not t['crack']
        self.stats['shipped'] += 1
        if safe_now:
            self.stats['shipped_good'] += 1
        else:
            self.stats['escaped'] += 1
        rec.update(fate=rec.get('fate', 'shipped'), shipped_s=round(self.env.now, 3), escaped=not safe_now,
                   escape_cost_multiplier=(self.sc.cost_shock_escape_multiplier if self.sc.cost_shock_at_s is not None
                                           and self.env.now >= self.sc.cost_shock_at_s else 1.0),
                   cycle_s=round(self.env.now - min(s['t_print_s'], t['t_print_s']), 3))
        s['fate'] = t['fate'] = 'shipped'
        yield ('release', {self.wip['slot']: 1, self.wip['tab']: 1})

    # ---- run -------------------------------------------------------------------------
    def run(self):
        sc = self.sc
        jobs = {s.name: [] for s in sc.sites}
        makers = {'slot': [s for s in sc.sites if s.makes in ('slot', 'both')],
                  'tab': [s for s in sc.sites if s.makes in ('tab', 'both')]}
        for kind in ('slot', 'tab'):
            sites = makers[kind]
            for j, start in enumerate(range(0, sc.n_pairs, sites[0].print_batch)):
                site = sites[j % len(sites)]
                idxs = list(range(start, min(sc.n_pairs, start + site.print_batch)))
                jobs[site.name].append((f'{kind}-job{j:04d}', kind, idxs))
        self.upstream = 2 * sc.n_pairs
        for s in sc.sites:
            # interleave slot/tab jobs so both kinds flow; split across the site's printers
            js = sorted(jobs[s.name], key=lambda x: (int(x[0].split('job')[1]), x[1]))
            for k in range(s.printers):
                self.env.process(self.printer(s, js[k::s.printers]))
        end = self.env.run()
        return self.summary(end)

    def summary(self, end):
        st = self.stats; n_parts = len(self.parts)
        shipped = [p for p in self.pairs if 'shipped_s' in p]
        leftover = len(self.buffer['slot']) + len(self.buffer['tab'])
        conserved = 2 * st['shipped'] + st['scrapped_parts'] + leftover == n_parts == 2 * self.sc.n_pairs + st['reprints']
        cyc = sorted(p['cycle_s'] for p in shipped) or [0.0]
        util = {r.name: round(r.busy_time / (end * r.capacity), 5) if end > 0 else 0.0 for r in self.env.resources}
        decided = [p for p in self.pairs]
        return dict(
            origin=SOURCE_TIER, model_version=MODEL_VERSION, generator='qr-factory-engine-v1',
            scenario=self.sc.sid, seed=self.seed, policy=self.policy, pairing=self.pairing,
            costs=asdict(self.costs), calibration_id=self.model.calibration_id, cad_revision=self.design['cad_revision'],
            truth_sha256=truth_hash(sorted(self.parts, key=lambda p: p['part_id'])),
            makespan_s=round(end, 3), parts=n_parts, leftover_unpaired=leftover, conservation_ok=conserved,
            shipped=st['shipped'], shipped_good=st['shipped_good'], escaped=st['escaped'],
            escape_rate=st['escaped'] / st['shipped'] if st['shipped'] else 0.0,
            good_per_hour=3600 * st['shipped_good'] / end if end else 0.0,
            mean_cycle_s=mean(cyc), p95_cycle_s=cyc[min(len(cyc) - 1, int(0.95 * len(cyc)))],
            mean_wip=sum(cyc) * 2 / end if end else 0.0,
            pair_decisions=len(decided), pair_holds=st['pair_holds'], part_holds=st['part_holds'],
            false_pair_holds=sum(1 for p in decided if p['decision'] == 'HOLD' and p['truly_safe']),
            holds_stale_evidence=st['holds_stale_evidence'],
            part_reviews=st['part_reviews'], pair_reviews=st['pair_reviews'], reworks=st['reworks'], rework_ok=st['rework_ok'],
            scrapped_parts=st['scrapped_parts'], scrapped_good_parts=st['scrapped_good_parts'],
            released_after_review=st['released_after_review'], local_reinspections=st['local_reinspections'], reprints=st['reprints'],
            hold_inventory_part_hours=self.hold_part_seconds / 3600, downtime_s=round(self.down_s, 3),
            operator_seconds=sum(r.busy_time for r in self.env.resources if 'operator' in r.name),
            utilization=util,
            escape_cost_units=sum(p['escape_cost_multiplier'] for p in shipped if p['escaped']),
            genealogy=shipped[:50] if self.keep_log else [],
        )


def run_factory(sc: FactoryScenario, seed: int, policy: str, pairing: str = 'fifo', **kw):
    return Factory(sc, seed, policy, pairing, **kw).run()
