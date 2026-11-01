"""SIM-05: CPU optimisation baselines (SciPy). OR-Tools / cuOpt are optional and reported
NOT_CONFIGURED when absent; they must use the same objective and constraints if added.

1. `match_batch`: pair k measured slots with k measured tabs (linear assignment). Objective =
   expected decision loss of each pair under the SAME posterior and threshold the pair gate
   uses. Safety constraint (06 doc): matching only chooses partners -- the pair gate still
   decides, so a pair whose P(unsafe) is above the threshold is HELD whatever it saves.
2. `plan_capacity`: integer staffing/equipment plan (scipy.optimize.milp) -- minimum cost of
   printers, inspection lines and operators so that every station's utilisation stays below
   rho_max at a target throughput. Checked by brute force on small instances in tests.
"""
from __future__ import annotations
import importlib.util
from math import ceil

import numpy as np
from scipy.optimize import linear_sum_assignment, milp, LinearConstraint, Bounds

from .scenarios import STATION_S

BIG = 1e6


def _pair_cost(factory, s, t):
    c = factory.costs
    if factory.policy in ('rules', 'hold_all'):
        clearance = factory._m(s) - factory._m(t)  # an unmeasured part (caliper_mode flagged_only) counts as nominal for the rule
        # the rule will hold anything below tolerance; prefer the design clearance (1.0 mm)
        return (c.hold if clearance < 0.5 else 0.0) + abs(clearance - 1.0) * 1e-3
    p = factory.pair_risk(s, t)
    return min(p * c.escaped_defect, (1 - p) * c.hold)


def match_batch(slots, tabs, factory):
    if len(slots) != len(tabs):
        raise ValueError('equal batch sizes required')
    cost = np.array([[_pair_cost(factory, s, t) for t in tabs] for s in slots])
    r, c = linear_sum_assignment(cost)
    return [(slots[i], tabs[j]) for i, j in zip(r, c)]


def match_value(slots, tabs, factory, pairs):
    return float(sum(_pair_cost(factory, s, t) for s, t in pairs))


# ---- capacity planning -------------------------------------------------------------------

def plan_capacity(target_pairs_per_hour: float, *, rho_max=0.85, print_per_part_s=18.0, print_batch=4, print_setup_s=30.0,
                  costs_per_shift=None, review_rate=0.15, rework_rate=0.03):
    """Decision variables (integers >= 1): printers, inspection_lines, operators.
    Load per hour (seconds of work) is derived from the same STATION_S the engine uses.
    Operators serve caliper + review + rework. Returns plan, cost, utilisations, solver status."""
    costs_per_shift = costs_per_shift or dict(printer=40.0, line=60.0, operator=200.0)
    parts_h = 2 * target_pairs_per_hour
    print_load = parts_h * (print_per_part_s + print_setup_s / print_batch)       # printer-seconds / h
    line_load = parts_h * max(STATION_S['phone'], STATION_S['pi'], STATION_S['caliper'])  # bottleneck station of a line
    op_load = parts_h * STATION_S['caliper'] + target_pairs_per_hour * (review_rate * STATION_S['review'] + rework_rate * STATION_S['rework'])
    cap = 3600 * rho_max
    c = np.array([costs_per_shift['printer'], costs_per_shift['line'], costs_per_shift['operator']])
    A = np.eye(3)
    lb = np.array([ceil(print_load / cap - 1e-9), ceil(line_load / cap - 1e-9), ceil(op_load / cap - 1e-9)], dtype=float)
    lb = np.maximum(lb, 1)
    res = milp(c, constraints=[LinearConstraint(A, lb, np.inf)], integrality=np.ones(3), bounds=Bounds(1, 500))
    if not res.success:
        return dict(status='INFEASIBLE', message=res.message)
    x = [int(round(v)) for v in res.x]
    return dict(status='OPTIMAL', solver='scipy.optimize.milp (HiGHS)', target_pairs_per_hour=target_pairs_per_hour,
                printers=x[0], inspection_lines=x[1], operators=x[2], cost_per_shift=float(c @ res.x),
                utilisation=dict(printer=print_load / (3600 * x[0]), line_bottleneck=line_load / (3600 * x[1]),
                                 operator=op_load / (3600 * x[2])),
                assumptions=dict(rho_max=rho_max, review_rate=review_rate, rework_rate=rework_rate, station_s=STATION_S,
                                 costs_per_shift=costs_per_shift, status='ILLUSTRATIVE_ASSUMPTION'))


def solver_status():
    return dict(scipy_linear_sum_assignment='WORKING', scipy_milp_highs='WORKING',
                ortools='INSTALLED_NOT_WIRED' if importlib.util.find_spec('ortools') else 'NOT_CONFIGURED',
                cuopt='INSTALLED_NOT_WIRED' if importlib.util.find_spec('cuopt') else 'NOT_CONFIGURED')
