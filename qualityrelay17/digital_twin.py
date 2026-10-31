"""Level-1 digital factory twin (docs/architectures/05_DIGITAL_FACTORY_TWIN.md), Bakdaulet 31 Oct.

Couples the two simulations that 17.0 kept apart: the seeded specimen stream + inspection
policies of `factory.py` (Level 0, *what* is decided) and a flow-shop discrete-event line
(`digital_line.py`'s approach, *when* things happen). Every specimen flows

    Print -> Phone_Vision -> Pi_Vision -> Caliper -> [extra visit bought by the policy]
          -> Decision -> Sorting -> (HOLD only) Review

so an inspection policy's choices become **time**: a VOI recapture re-queues the part at a
camera station, a caliper retake re-queues it at Caliper, and every HOLD occupies the Review
(quarantine) station. Same seed -> same specimens AND same service-time noise for every policy
(common random numbers), so differences between policies are the policies, not the dice.

Mirrors the physical Slot/Tab demo line station-for-station (acceptance 1 of the 05 doc). All
service times are **illustrative assumptions** (`TwinTiming`, echoed in every output as
`ILLUSTRATIVE_ASSUMPTION`) until someone measures the real station; the generator is the
same toy as `factory.py`. origin = SIMULATED on everything. No SimPy dependency on purpose.
"""
from __future__ import annotations
import csv, json, time
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from random import Random
from statistics import mean

from .factory import seeded_scenario, apply_policy, POLICIES, default_likelihoods
from .economics import Costs, calculate
from .calibration import estimate_likelihoods

STATIONS = ('Print', 'Phone_Vision', 'Pi_Vision', 'Caliper', 'Decision', 'Sorting', 'Review')
# Which stations a policy reads "for free" (its baseline evidence), in line order.
_FREE_VISITS = {
    'phone_only': ('Phone_Vision',),
    'metrology_only': ('Caliper',),
    'structured_request_lite': ('Phone_Vision', 'Caliper'),
}
_DEFAULT_FREE = ('Phone_Vision', 'Pi_Vision', 'Caliper')
_NOISE_KEYS = ('Print', 'Phone_Vision', 'Pi_Vision', 'Caliper', 'Decision', 'Sorting', 'Review', 'extra0', 'extra1', 'downtime')
REFERENCE = 'conservative_rules'


@dataclass(frozen=True)
class TwinTiming:
    """Seconds. Illustrative assumptions for a one-operator Slot/Tab demo line -- NOT measured."""
    arrival_every_s: float = 10.0
    print_s: float = 18.0
    print_capacity: int = 2       # two printers feed one inspection line (utilisation 0.9, not a runaway queue)
    phone_s: float = 5.0
    pi_s: float = 6.0
    caliper_s: float = 7.0
    recapture_s: float = 5.0      # phone/Pi recapture bought by voi_driven / entropy_driven
    retake_s: float = 7.0         # caliper retake bought by voi_driven / entropy_driven
    decision_s: float = 1.0
    sort_s: float = 3.0
    review_s: float = 45.0        # manual review / quarantine handling per HOLD
    review_capacity: int = 1
    print_downtime_p: float = 0.03
    print_downtime_s: float = 25.0
    lognorm_sigma: float = 0.16
    status: str = 'ILLUSTRATIVE_ASSUMPTION'

    def service_mean(self, station: str) -> float:
        return {'Print': self.print_s, 'Phone_Vision': self.phone_s, 'Pi_Vision': self.pi_s, 'Caliper': self.caliper_s,
                'Decision': self.decision_s, 'Sorting': self.sort_s, 'Review': self.review_s}[station]

    def capacity(self, station: str) -> int:
        return {'Review': self.review_capacity, 'Print': self.print_capacity}.get(station, 1)


def _noise(seed: int, i: int, sigma: float) -> dict:
    """Per-specimen service multipliers, drawn in a fixed order from a specimen-keyed stream so
    every policy sees identical noise (common random numbers)."""
    rng = Random(f'twin:{seed}:{i}')
    out = {k: rng.lognormvariate(0, sigma) for k in _NOISE_KEYS if k != 'downtime'}
    out['downtime'] = rng.random()
    return out


def _plan_visits(policy: str, row: dict, decision: dict, timing: TwinTiming):
    """Ordered (station, mean_service_s, is_extra) visits for one specimen under one policy."""
    free = _FREE_VISITS.get(policy, _DEFAULT_FREE)
    visits = [('Print', timing.print_s, False)]
    for st in free:
        if st == 'Pi_Vision' and row['network_down']:
            continue  # Pi evidence unavailable this cycle: no visit, the policy already saw it as missing
        visits.append((st, timing.service_mean(st), False))
    extras = []
    action = decision.get('chosen_action')
    if action == 'phone_recapture':
        extras.append(('Phone_Vision', timing.recapture_s))
    elif action == 'pi_recapture':
        extras.append(('Pi_Vision', timing.recapture_s))
    elif action == 'caliper_retake':
        extras.append(('Caliper', timing.retake_s))
    if decision.get('requested_pi_evidence'):
        extras.append(('Pi_Vision', timing.pi_s))
    # Any inspection the policy counted beyond its free reads and the above (safe_mesh_reference's
    # disagreement re-check) is modelled as extra operator time at Decision.
    accounted = len(free) + len(extras) - (1 if ('Pi_Vision' in free and row['network_down']) else 0)
    for _ in range(max(0, int(decision.get('inspections', len(free))) - accounted)):
        extras.append(('Decision', timing.recapture_s))
    visits += [(st, s, True) for st, s in extras[:2]]  # at most two purchased visits per part
    visits.append(('Decision', timing.decision_s, False))
    visits.append(('Sorting', timing.sort_s, False))
    if decision['outcome'] == 'hold':
        visits.append(('Review', timing.review_s, False))
    return visits


def run_twin(n=200, seed=2026, policy='conservative_rules', *, timing: TwinTiming | None = None, likelihoods=None,
             costs: Costs | None = None, review_capacity=None, review_s=None, **scenario):
    """Run one policy through the line on one seeded specimen stream. `scenario` kwargs go to
    factory.seeded_scenario (process_shift_mm, camera_noise, network_outage, shared_camera_noise)."""
    if n < 1:
        raise ValueError('n >= 1')
    if policy not in POLICIES:
        raise ValueError(f'unknown policy {policy}')
    timing = timing or TwinTiming()
    if review_capacity is not None or review_s is not None:
        timing = replace(timing, review_capacity=review_capacity or timing.review_capacity, review_s=review_s or timing.review_s)
    costs = costs or Costs()
    rows = seeded_scenario(n, seed, **scenario)
    lk = likelihoods or default_likelihoods()
    decisions = apply_policy(rows, policy, costs=costs, likelihoods=lk)
    # Event-driven discrete-event core: per-station FIFO queues ordered by the time a part actually
    # reaches the station. (Processing parts in arrival order, as digital_line.py does, is wrong as
    # soon as a part can REVISIT a station for a purchased recapture/retake -- it blocks later
    # parts behind a revisit that happens much later in time.)
    import heapq
    from collections import deque
    plans = [_plan_visits(policy, row, dec, timing) for row, dec in zip(rows, decisions)]
    noises = [_noise(seed, i, timing.lognorm_sigma) for i in range(n)]
    free = {st: timing.capacity(st) for st in STATIONS}; queue = {st: deque() for st in STATIONS}
    busy = {st: 0.0 for st in STATIONS}; waits = {st: [] for st in STATIONS}; visits_n = {st: 0 for st in STATIONS}
    records = [[None] * len(p) for p in plans]; finish = [None] * n; inspection_time = 0.0
    seq = 0; heap = []
    DEPART, ARRIVE = 0, 1

    def push(t, kind, i, v):
        nonlocal seq
        seq += 1
        heapq.heappush(heap, (t, kind, seq, i, v))

    def start_service(st, i, v, now):
        nonlocal inspection_time
        station, mean_s, is_extra = plans[i][v]
        extra_idx = sum(1 for x in plans[i][:v] if x[2])
        key = f'extra{min(1, extra_idx)}' if is_extra else station
        service = max(0.05, noises[i][key] * mean_s)
        downtime = station == 'Print' and noises[i]['downtime'] < timing.print_downtime_p
        end = now + service + (timing.print_downtime_s if downtime else 0.0)
        rec = records[i][v]
        rec.update(start=round(now, 4), end=round(end, 4), queue_wait_s=round(now - rec['arrival'], 4), downtime=downtime)
        free[st] -= 1; busy[st] += service; waits[st].append(now - rec['arrival']); visits_n[st] += 1
        if station in ('Phone_Vision', 'Pi_Vision', 'Caliper') or is_extra:
            inspection_time += service
        push(end, DEPART, i, v)

    for i in range(n):
        push(i * timing.arrival_every_s, ARRIVE, i, 0)
    while heap:
        t, kind, _, i, v = heapq.heappop(heap)
        st = plans[i][v][0]
        if kind == ARRIVE:
            records[i][v] = {'station': st, 'arrival': round(t, 4), 'extra': plans[i][v][2]}
            if free[st] > 0:
                start_service(st, i, v, t)
            else:
                queue[st].append((i, v))
        else:  # DEPART
            free[st] += 1
            if queue[st]:
                j, w = queue[st].popleft()
                start_service(st, j, w, t)
            if v + 1 < len(plans[i]):
                push(t, ARRIVE, i, v + 1)
            else:
                finish[i] = t
    routes = []
    for i, (row, dec) in enumerate(zip(rows, decisions)):
        arrival = i * timing.arrival_every_s
        routes.append({'specimen_id': row['specimen_id'], 'arrival': round(arrival, 4), 'finish': round(finish[i], 4),
                       'cycle_time_s': round(finish[i] - arrival, 4), 'outcome': dec['outcome'], 'unsafe_pass': dec['unsafe_pass'],
                       'extra_visits': sum(1 for x in plans[i] if x[2]), 'visits': records[i], 'origin': 'SIMULATED'})
    makespan = max(r['finish'] for r in routes)
    cycles = sorted(r['cycle_time_s'] for r in routes)
    # WIP: +1 at arrival, -1 at finish; time-average via Little's law over [0, makespan].
    events = sorted([(r['arrival'], 1) for r in routes] + [(r['finish'], -1) for r in routes], key=lambda e: (e[0], e[1]))
    wip = 0; max_wip = 0
    for _, d in events:
        wip += d; max_wip = max(max_wip, wip)
    counts = {'pass': 0, 'hold': 0, 'escaped_defect': 0}
    for r in routes:
        counts[r['outcome']] += 1
    station_summary = {st: {'visits': visits_n[st], 'capacity': timing.capacity(st),
                            'utilization': round(min(1.0, busy[st] / (makespan * timing.capacity(st))), 5) if visits_n[st] else 0.0,
                            'mean_wait_s': round(mean(waits[st]), 4) if waits[st] else 0.0,
                            'max_wait_s': round(max(waits[st]), 4) if waits[st] else 0.0} for st in STATIONS}
    return {
        'generator': 'digital_twin_level1_v1', 'origin': 'SIMULATED', 'policy': policy, 'seed': seed, 'n': n,
        'scenario': {'process_shift_mm': 0.10, 'camera_noise': 0.04, 'network_outage': 0.05, 'shared_camera_noise': 0.0, **scenario},
        'timing': asdict(timing), 'calibration_id': lk.calibration_id, 'costs': asdict(costs),
        'completed': len(routes), 'counts': counts, 'unsafe_pass': sum(r['unsafe_pass'] for r in routes),
        'conservation_ok': counts['pass'] + counts['hold'] + counts['escaped_defect'] == n and wip == 0, 'wip_end': wip,
        'makespan_s': round(makespan, 4), 'throughput_per_hour': round(n / makespan * 3600, 4),
        'mean_cycle_time_s': round(mean(cycles), 4), 'p95_cycle_time_s': round(cycles[min(len(cycles) - 1, int(0.95 * len(cycles)))], 4),
        'mean_wip': round(sum(cycles) / makespan, 4), 'max_wip': max_wip,
        'inspection_time_s': round(inspection_time, 4), 'review_time_s': round(busy['Review'], 4),
        'economics': calculate(decisions, costs), 'station_summary': station_summary, 'routes': routes,
    }


_PAIRED_METRICS = ('mean_cycle_time_s', 'p95_cycle_time_s', 'throughput_per_hour', 'mean_wip', 'max_wip',
                   'unsafe_pass', 'hold', 'inspection_time_s', 'review_time_s', 'total_cost')


def _flat(out):
    return {**{k: out[k] for k in _PAIRED_METRICS if k in out}, 'hold': out['counts']['hold'], 'total_cost': out['economics']['total_cost']}


def compare_twin(n=200, seed=2026, policies=POLICIES, *, likelihoods=None, **kwargs):
    """All policies on the same specimen stream and the same service noise; paired differences vs
    conservative_rules. Routes are dropped from the per-policy output to keep it small."""
    lk = likelihoods or default_likelihoods()
    outs = {p: run_twin(n, seed, p, likelihoods=lk, **kwargs) for p in policies}
    ref = _flat(outs[REFERENCE])
    return {'origin': 'SIMULATED', 'seed': seed, 'n': n, 'scenario': outs[REFERENCE]['scenario'], 'timing': outs[REFERENCE]['timing'],
            'policies': {p: {k: v for k, v in o.items() if k != 'routes'} for p, o in outs.items()},
            'paired_vs_conservative_rules': {p: {k: round(_flat(o)[k] - ref[k], 6) for k in ref} for p, o in outs.items()}}


DEFAULT_SCENARIOS = {
    'baseline': {},
    'large_shift': {'process_shift_mm': 0.20},
    'noisy_correlated_cameras': {'camera_noise': 0.10, 'shared_camera_noise': 0.05},
    'outage_heavy': {'network_outage': 0.20},
    'tight_review': {'review_capacity': 1, 'review_s': 90.0},
    # Sensitivity: what if the cost table priced an inspection closer to its station time?
    # (Costs.inspection 0.5 -> 5.0; affects only the posterior-based policies' purchase decisions.)
    'inspection_cost_x10': {'inspection_cost': 5.0},
}


def run_twin_scenarios(seeds=range(10), n=1000, scenarios=None, out_dir='examples/results/digital_twin_31oct',
                       calibration_seeds=range(1000, 1010)):
    """>= 3 seeded fault scenarios, common random numbers across policies, paired cluster-bootstrap
    CIs over seeds vs conservative_rules. Writes <scenario>.json, summary.csv, manifest.json."""
    from .benchmark import paired_cluster_bootstrap_ci
    scenarios = scenarios or DEFAULT_SCENARIOS
    seed_values = [int(s) for s in seeds]
    if len(scenarios) < 3:
        raise ValueError('the 05 architecture doc requires at least 3 fault scenarios')
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time(); result = {'origin': 'SIMULATED', 'seeds': seed_values, 'n': n, 'scenarios': {}}
    rows_csv = []
    for sid, params in scenarios.items():
        gen = {k: v for k, v in params.items() if k in ('process_shift_mm', 'camera_noise', 'network_outage', 'shared_camera_noise')}
        lk = estimate_likelihoods(seeds=calibration_seeds, n=n, **gen)
        run_kwargs = {k: v for k, v in params.items() if k != 'inspection_cost'}
        if 'inspection_cost' in params:
            run_kwargs['costs'] = Costs(inspection=float(params['inspection_cost']))
        per_seed = {p: [] for p in POLICIES}
        for seed in seed_values:
            cmp_ = compare_twin(n, seed, likelihoods=lk, **run_kwargs)
            for p in POLICIES:
                per_seed[p].append(_flat(cmp_['policies'][p]))
        means = {p: {k: round(mean(r[k] for r in recs), 4) for k in recs[0]} for p, recs in per_seed.items()}
        paired = {}
        for p in POLICIES:
            paired[p] = {}
            for k in per_seed[p][0]:
                diffs = [a[k] - b[k] for a, b in zip(per_seed[p], per_seed[REFERENCE])]
                paired[p][k] = {'mean': round(mean(diffs), 6), 'ci95': paired_cluster_bootstrap_ci(diffs) if len(diffs) > 1 else [round(diffs[0], 6)] * 2}
        scen = {'scenario_id': sid, 'params': params, 'calibration_id': lk.calibration_id, 'mean_by_policy': means,
                'paired_vs_rules': paired, 'per_seed': per_seed}
        (out_dir / f'{sid}.json').write_text(json.dumps(scen, indent=1, sort_keys=True))
        result['scenarios'][sid] = scen
        for p, m in means.items():
            rows_csv.append({'scenario': sid, 'policy': p, **m})
    with (out_dir / 'summary.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_csv[0].keys())); w.writeheader(); w.writerows(rows_csv)
    manifest = {'origin': 'SIMULATED', 'generator': 'digital_twin_level1_v1', 'seeds': seed_values, 'n': n,
                'scenarios': {k: v for k, v in scenarios.items()}, 'timing': asdict(TwinTiming()),
                'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)), 'elapsed_s': round(time.time() - started, 1),
                'policies': list(POLICIES), 'reference': REFERENCE,
                'claim_boundary': 'Service times are illustrative assumptions; specimens come from the factory.py toy generator. '
                                  'Operational numbers are SIMULATED and not a factory measurement.'}
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
    result['manifest'] = manifest
    return result
