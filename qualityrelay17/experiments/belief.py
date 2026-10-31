"""Calibrated belief over the two fault axes + non-myopic (two-step look-ahead) VOI.

Surface axis: binary camera flags, sens/spec estimated on HELD-OUT calibration lots
(calibration.estimate_likelihoods). First capture and recaptures have separate parameters.

Dimensional axis: the caliper reading is used as a CONTINUOUS measurement, not a thresholded
bit. True clearance has a Gaussian prior estimated on the same held-out lots; each reading is
true + N(0, sigma_meas^2) with sigma_meas the instrument's stated uncertainty. Conjugate
update -> P(clearance < tolerance) = Phi((tol - mu) / sd). This is what lets the planner see
"near tolerance + uncertain" and value a retake correctly.

Belief is recomputed from the evidence ledger after EVERY observation (SCI-06). With
`dedupe=True` two items sharing a source_root count once (lineage, AGENT-05 / 17.1 sec 4.3);
`dedupe=False` exists only for the provenance ablation in simulation.

Known modelling assumption, stress-tested rather than hidden: camera flags are treated as
conditionally independent given the true state. Scenarios with shared_camera_noise > 0 or
duplicated photos violate it on purpose.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import erf, sqrt, log2
from statistics import mean, pvariance

from ..calibration import estimate_likelihoods
from ..economics import Costs

TOLERANCE_MM = 0.5
MAX_DRAWS = 3  # captures per sensor per part available in the simulated world (k = 0, 1, 2)
# 5-point Gauss-Hermite (probabilists' form): nodes z_i, weights w_i with sum w_i = 1.
_GH = ((-2.8569700138728056, 0.011257411327720691), (-1.355626179974266, 0.22207592200561266),
       (0.0, 0.5333333333333333), (1.355626179974266, 0.22207592200561266),
       (2.8569700138728056, 0.011257411327720691))


def phi(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


@dataclass(frozen=True)
class BeliefModel:
    phone_sens: float; phone_spec: float
    pi_sens: float; pi_spec: float
    phone_re_sens: float; phone_re_spec: float
    pi_re_sens: float; pi_re_spec: float
    surface_prior: float
    clearance_prior_mean: float
    clearance_prior_var: float
    sigma_meas_mm: float
    calibration_id: str
    source: str = 'HELD_OUT_SYNTHETIC_CALIBRATION'

    def camera(self, kind: str, index: int):
        if kind == 'phone':
            return (self.phone_sens, self.phone_spec) if index == 0 else (self.phone_re_sens, self.phone_re_spec)
        return (self.pi_sens, self.pi_spec) if index == 0 else (self.pi_re_sens, self.pi_re_spec)

    def as_dict(self):
        return asdict(self)


def calibrate_belief_model(seeds=range(1000, 1010), n=1000, *, sigma_meas_mm=0.05, **scenario) -> BeliefModel:
    """Held-out calibration. sigma_meas_mm is the instrument's STATED uncertainty (a spec-sheet
    value, as a real caliper certificate would give), not read from the generator."""
    from ..factory import seeded_scenario
    lk = estimate_likelihoods(seeds=seeds, n=n, **scenario)
    measured = [r['measured_clearance'] for s in seeds for r in seeded_scenario(n, int(s), **scenario)]
    var_true = max(1e-6, pvariance(measured) - sigma_meas_mm ** 2)
    return BeliefModel(
        phone_sens=lk.phone_sens, phone_spec=lk.phone_spec, pi_sens=lk.pi_sens, pi_spec=lk.pi_spec,
        phone_re_sens=lk.phone_recapture_sens, phone_re_spec=lk.phone_recapture_spec,
        pi_re_sens=lk.pi_recapture_sens, pi_re_spec=lk.pi_recapture_spec,
        surface_prior=lk.surface_prior, clearance_prior_mean=round(mean(measured), 10),
        clearance_prior_var=round(var_true, 10), sigma_meas_mm=sigma_meas_mm,
        calibration_id=lk.calibration_id + f'+gauss-sigma{sigma_meas_mm}')


# ---- state = (surface_p, clearance_mu, clearance_var) -------------------------------------

def camera_update(p: float, sens: float, spec: float, flagged: bool) -> float:
    ld = sens if flagged else 1 - sens
    lg = 1 - spec if flagged else spec
    d = p * ld + (1 - p) * lg
    return p * ld / d if d > 0 else p


def caliper_update(mu: float, var: float, reading: float, sigma: float):
    s2 = sigma * sigma
    new_var = var * s2 / (var + s2)
    new_mu = new_var * (mu / var + reading / s2)
    return new_mu, new_var


def p_dimensional(mu: float, var: float) -> float:
    return phi((TOLERANCE_MM - mu) / sqrt(var))


def p_unsafe(state) -> float:
    ps, mu, var = state
    return 1 - (1 - ps) * (1 - p_dimensional(mu, var))


def risk(p: float, costs: Costs) -> float:
    """Bayes decision risk of the better of PASS (escape cost) and HOLD (hold cost)."""
    return min(p * costs.escaped_defect, (1 - p) * costs.hold)


def hold_threshold(costs: Costs) -> float:
    return costs.hold / (costs.hold + costs.escaped_defect)


def entropy(p: float) -> float:
    return 0.0 if p <= 0 or p >= 1 else -p * log2(p) - (1 - p) * log2(1 - p)


def belief_from(evidence, model: BeliefModel, *, dedupe: bool = True):
    """Recompute the full belief from the ledger. Returns (state, n_unique_surface, n_unique_dim)."""
    ps = model.surface_prior
    mu, var = model.clearance_prior_mean, model.clearance_prior_var
    seen = set(); ns = nd = 0
    for e in evidence:
        if dedupe and e['source_root'] in seen:
            continue
        seen.add(e['source_root'])
        if e['kind'] == 'caliper':
            mu, var = caliper_update(mu, var, e['value'], model.sigma_meas_mm); nd += 1
        else:
            sens, spec = model.camera(e['kind'], e['index'])
            ps = camera_update(ps, sens, spec, bool(e['value'])); ns += 1
    return (ps, mu, var), ns, nd


def outcomes(state, kind: str, index: int, model: BeliefModel):
    """Predictive distribution of the next observation of `kind`: [(prob, new_state)]."""
    ps, mu, var = state
    if kind == 'caliper':
        sd_pred = sqrt(var + model.sigma_meas_mm ** 2)
        return [(w, (ps, *caliper_update(mu, var, mu + z * sd_pred, model.sigma_meas_mm))) for z, w in _GH]
    sens, spec = model.camera(kind, index)
    p_flag = ps * sens + (1 - ps) * (1 - spec)
    return [(p_flag, (camera_update(ps, sens, spec, True), mu, var)),
            (1 - p_flag, (camera_update(ps, sens, spec, False), mu, var))]


def lookahead_value(state, candidates, price, model, costs, depth):
    """Expected loss of acting optimally for `depth` more purchases (expectimax), where
    `candidates` maps kind -> next index available. Returns (value, best_kind_or_None)."""
    r = risk(p_unsafe(state), costs)
    if depth == 0 or not candidates:
        return r, None
    best, best_kind = r, None
    for kind, idx in candidates.items():
        nxt = dict(candidates)
        if idx + 1 < MAX_DRAWS:
            nxt[kind] = idx + 1
        else:
            del nxt[kind]
        exp = 0.0
        for prob, s2 in outcomes(state, kind, idx, model):
            v, _ = lookahead_value(s2, nxt, price, model, costs, depth - 1)
            exp += prob * v
        total = price(kind) + exp
        if total < best - 1e-12:
            best, best_kind = total, kind
    return best, best_kind


def entropy_choice(state, candidates, model):
    """Cost-blind ablation: the kind with the largest expected entropy reduction of p_unsafe."""
    h0 = entropy(p_unsafe(state)); best, best_kind = 0.0, None
    for kind, idx in sorted(candidates.items()):
        eh = sum(prob * entropy(p_unsafe(s2)) for prob, s2 in outcomes(state, kind, idx, model))
        if h0 - eh > best + 1e-12:
            best, best_kind = h0 - eh, kind
    return best, best_kind
