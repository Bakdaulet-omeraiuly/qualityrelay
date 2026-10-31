"""NVIDIA Warp rare-event Monte Carlo for the paired policy comparison (Bakdaulet, 31 Oct).

Why: unsafe PASS is rare (1-4 per 1000), so the 30x1000 CPU benchmarks leave wide intervals on
exactly the metric that matters. This module runs the SAME Level-0 part generator and the SAME
decision rules as kernels, so 10^7-10^9 parts per scenario are cheap -- on CPU (Warp's CPU
backend, used in CI) or on an NVIDIA GPU (CUDA build of warp-lang, e.g. a Brev L4).

What is identical to the CPU code, and how that is proven (tests/test_warp_mc.py):
- Decisions: `decide_arrays` evaluates B0 (= factory.conservative_rules / Gate-A B0),
  F (= factory.collective_fusion) and B1 (= Gate-A B1, Gaussian caliper posterior, Pi only when
  its station is up) on caller-supplied inputs in float64; they must equal the CPU decisions
  part-for-part on seeded_scenario rows.
- Generator: same distributions and parameters as factory.seeded_scenario, but Warp's own
  counter-based RNG, so individual parts differ; distributional equality is tested.

Every number is SIMULATED. A bigger sample tightens the interval of the SIMULATED estimate; it
does not make the toy generator any more realistic.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import sqrt
import time

import numpy as np
import warp as wp

wp.config.quiet = True

N_POL = 3                 # 0 = B0 rules, 1 = F collective_fusion (factory), 2 = B1 Gaussian (Gate-A)
POLICY_NAMES = ('B0_rules', 'F_collective_fusion', 'B1_single_agent_fixed')
# per-policy counters: unsafe_pass, hold, released_good, false_hold
K_PER = 4
# paired discordance vs B0 for policy 1 and 2: unsafe (a_only, b_only), good (a_only, b_only)
K_PAIR = 4
K_TOTAL = 1 + N_POL * K_PER + 2 * K_PAIR + 2   # [n] + per-policy + pairs + [truly_safe, duplicates]


@wp.struct
class Params:
    shift: wp.float64
    camera_noise: wp.float64
    network_outage: wp.float64
    shared_noise: wp.float64
    caliper_sigma: wp.float64
    duplicate_p: wp.float64
    # binary likelihoods (factory.collective_fusion)
    phone_sens: wp.float64
    phone_spec: wp.float64
    pi_sens: wp.float64
    pi_spec: wp.float64
    cal_sens: wp.float64
    cal_spec: wp.float64
    surface_prior: wp.float64
    dim_prior: wp.float64
    # Gaussian belief (Gate-A B1)
    b_phone_sens: wp.float64
    b_phone_spec: wp.float64
    b_pi_sens: wp.float64
    b_pi_spec: wp.float64
    b_surface_prior: wp.float64
    clr_mean: wp.float64
    clr_var: wp.float64
    sigma_model: wp.float64
    threshold: wp.float64


@wp.func
def bayes(p: wp.float64, sens: wp.float64, spec: wp.float64, flag: wp.int32) -> wp.float64:
    ld = sens
    lg = wp.float64(1.0) - spec
    if flag == 0:
        ld = wp.float64(1.0) - sens
        lg = spec
    d = p * ld + (wp.float64(1.0) - p) * lg
    if d > wp.float64(0.0):
        return p * ld / d
    return p


@wp.func
def decide(phone: wp.int32, pi: wp.int32, measured: wp.float64, down: wp.int32, dup: wp.int32, P: Params) -> wp.vec3i:
    one = wp.float64(1.0)
    # B0: conservative OR rule
    h0 = 0
    if phone == 1 or pi == 1 or measured < wp.float64(0.5) or down == 1:
        h0 = 1
    # F: factory.collective_fusion -- binary caliper flag, reads pi regardless of outage (as the CPU
    # reference does), no lineage: a duplicated Pi frame is counted again
    s = bayes(P.surface_prior, P.phone_sens, P.phone_spec, phone)
    s = bayes(s, P.pi_sens, P.pi_spec, pi)
    cf = 0
    if measured < wp.float64(0.5):
        cf = 1
    d = bayes(P.dim_prior, P.cal_sens, P.cal_spec, cf)
    h1 = 0
    if one - (one - s) * (one - d) >= P.threshold:
        h1 = 1
    # B1: Gate-A single agent -- Pi only if its station is up; lineage drops a duplicated frame;
    # Gaussian caliper posterior
    s2 = bayes(P.b_surface_prior, P.b_phone_sens, P.b_phone_spec, phone)
    if down == 0 and dup == 0:
        s2 = bayes(s2, P.b_pi_sens, P.b_pi_spec, pi)
    s2v = P.sigma_model * P.sigma_model
    v = P.clr_var * s2v / (P.clr_var + s2v)
    mu = v * (P.clr_mean / P.clr_var + measured / s2v)
    pd = wp.float64(0.5) * (one + wp.erf((wp.float64(0.5) - mu) / wp.sqrt(wp.float64(2.0) * v)))
    h2 = 0
    if one - (one - s2) * (one - pd) >= P.threshold:
        h2 = 1
    return wp.vec3i(h0, h1, h2)


@wp.kernel
def decide_kernel(phone: wp.array(dtype=wp.int32), pi: wp.array(dtype=wp.int32), measured: wp.array(dtype=wp.float64),
                  down: wp.array(dtype=wp.int32), dup: wp.array(dtype=wp.int32), P: Params, out: wp.array(dtype=wp.vec3i)):
    i = wp.tid()
    out[i] = decide(phone[i], pi[i], measured[i], down[i], dup[i], P)


@wp.func
def flip(p: wp.float64, st: wp.uint32) -> wp.int32:
    return wp.where(wp.float64(wp.randf(st)) < p, 1, 0)


@wp.kernel
def mc_kernel(seed: wp.int32, per_lot: wp.int64, P: Params, counts: wp.array2d(dtype=wp.int64)):
    tid = wp.tid()
    st = wp.rand_init(seed, tid)
    lot = wp.int32(wp.int64(tid) / per_lot)
    slot = wp.float64(21.0) - wp.float64(0.5) * P.shift + wp.float64(0.12) * wp.float64(wp.randn(st))
    tab = wp.float64(20.0) + P.shift + wp.float64(0.12) * wp.float64(wp.randn(st))
    surface = wp.where(wp.float64(wp.randf(st)) < wp.float64(0.06), 1, 0)
    common = wp.where(wp.float64(wp.randf(st)) < P.shared_noise, 1, 0)
    phone = surface ^ wp.where(wp.float64(wp.randf(st)) < P.camera_noise, 1, 0) ^ common
    pi = surface ^ wp.where(wp.float64(wp.randf(st)) < P.camera_noise, 1, 0) ^ common
    measured = (slot - tab) + P.caliper_sigma * wp.float64(wp.randn(st))
    down = wp.where(wp.float64(wp.randf(st)) < P.network_outage, 1, 0)
    dup = wp.where(wp.float64(wp.randf(st)) < P.duplicate_p, 1, 0)
    if dup == 1:
        pi = phone
    safe = 0
    if slot - tab >= wp.float64(0.5) and surface == 0:
        safe = 1
    h = decide(phone, pi, measured, down, dup, P)
    wp.atomic_add(counts, lot, 0, wp.int64(1))
    wp.atomic_add(counts, lot, 1 + N_POL * K_PER + 2 * K_PAIR, wp.int64(safe))
    wp.atomic_add(counts, lot, 2 + N_POL * K_PER + 2 * K_PAIR, wp.int64(dup))
    u = wp.vec3i(0, 0, 0)
    g = wp.vec3i(0, 0, 0)
    for k in range(N_POL):
        unsafe_k = 0
        good_k = 0
        if h[k] == 0 and safe == 0:
            unsafe_k = 1
        if h[k] == 0 and safe == 1:
            good_k = 1
        u[k] = unsafe_k
        g[k] = good_k
        base = 1 + k * K_PER
        wp.atomic_add(counts, lot, base + 0, wp.int64(unsafe_k))
        wp.atomic_add(counts, lot, base + 1, wp.int64(h[k]))
        wp.atomic_add(counts, lot, base + 2, wp.int64(good_k))
        wp.atomic_add(counts, lot, base + 3, wp.int64(h[k] * safe))
    for j in range(2):
        a = j + 1
        base = 1 + N_POL * K_PER + j * K_PAIR
        wp.atomic_add(counts, lot, base + 0, wp.int64(u[a] * (1 - u[0])))
        wp.atomic_add(counts, lot, base + 1, wp.int64(u[0] * (1 - u[a])))
        wp.atomic_add(counts, lot, base + 2, wp.int64(g[a] * (1 - g[0])))
        wp.atomic_add(counts, lot, base + 3, wp.int64(g[0] * (1 - g[a])))


# ---- host side --------------------------------------------------------------------------------

@dataclass(frozen=True)
class WarpScenario:
    sid: str
    title: str
    shift: float = 0.10
    camera_noise: float = 0.04
    network_outage: float = 0.05
    shared_noise: float = 0.0
    caliper_sigma: float = 0.05
    duplicate_p: float = 0.0


GRID = (  # mirrors Gate-A S01..S08 where the Level-0 generator can express them
    WarpScenario('S01', 'nominal'),
    WarpScenario('S02', 'process drift (shift 0.25 mm)', shift=0.25),
    WarpScenario('S03', 'noisy cameras', camera_noise=0.15),
    WarpScenario('S04', 'shared lighting', shared_noise=0.15),
    WarpScenario('S05', 'duplicated photo 0.5', duplicate_p=0.5),
    WarpScenario('S06', 'Pi offline', network_outage=1.0),
    WarpScenario('S07', 'partial partition 0.3', network_outage=0.30),
    WarpScenario('S08', 'noisy caliper 0.15 (model assumes 0.05)', caliper_sigma=0.15),
)


def make_params(sc: WarpScenario | None = None, *, lk=None, bm=None, costs=None) -> Params:
    from ..calibration import estimate_likelihoods
    from ..economics import Costs
    from ..experiments.belief import calibrate_belief_model
    sc = sc or GRID[0]
    lk = lk or estimate_likelihoods()
    bm = bm or calibrate_belief_model()
    costs = costs or Costs()
    P = Params()
    for k, v in dict(shift=sc.shift, camera_noise=sc.camera_noise, network_outage=sc.network_outage,
                     shared_noise=sc.shared_noise, caliper_sigma=sc.caliper_sigma, duplicate_p=sc.duplicate_p,
                     phone_sens=lk.phone_sens, phone_spec=lk.phone_spec, pi_sens=lk.pi_sens, pi_spec=lk.pi_spec,
                     cal_sens=lk.caliper_sens, cal_spec=lk.caliper_spec, surface_prior=lk.surface_prior,
                     dim_prior=lk.dimensional_prior, b_phone_sens=bm.phone_sens, b_phone_spec=bm.phone_spec,
                     b_pi_sens=bm.pi_sens, b_pi_spec=bm.pi_spec, b_surface_prior=bm.surface_prior,
                     clr_mean=bm.clearance_prior_mean, clr_var=bm.clearance_prior_var, sigma_model=bm.sigma_meas_mm,
                     threshold=costs.hold / (costs.hold + costs.escaped_defect)).items():
        setattr(P, k, float(v))
    return P


def decide_arrays(phone, pi, measured, down, dup, P: Params, device='cpu'):
    n = len(phone)
    arrs = [wp.array(np.asarray(x, dtype=np.int32), dtype=wp.int32, device=device) for x in (phone, pi)]
    m = wp.array(np.asarray(measured, dtype=np.float64), dtype=wp.float64, device=device)
    dn, du = (wp.array(np.asarray(x, dtype=np.int32), dtype=wp.int32, device=device) for x in (down, dup))
    out = wp.zeros(n, dtype=wp.vec3i, device=device)
    wp.launch(decide_kernel, dim=n, inputs=[arrs[0], arrs[1], m, dn, du, P, out], device=device)
    return out.numpy()


def run_mc(sc: WarpScenario, n_parts: int, *, lots: int = 100, seed: int = 2026, device=None, P: Params | None = None):
    """n_parts split into `lots` equal lots (a lot = one cluster for the between-lot interval)."""
    device = device or wp.get_preferred_device()
    per_lot = n_parts // lots
    n = per_lot * lots
    P = P or make_params(sc)
    counts = wp.zeros((lots, K_TOTAL), dtype=wp.int64, device=device)
    wp.synchronize_device(device)
    t0 = time.perf_counter()
    wp.launch(mc_kernel, dim=n, inputs=[seed, per_lot, P, counts], device=device)
    wp.synchronize_device(device)
    secs = time.perf_counter() - t0
    c = counts.numpy()
    return summarise(sc, c, secs, str(device), seed)


def _wilson(k, n, z=1.959964):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    den = 1 + z * z / n
    cen = (p + z * z / (2 * n)) / den
    rad = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0.0, cen - rad), min(1.0, cen + rad)]


def summarise(sc, c, secs, device, seed):
    tot = c.sum(axis=0)
    n = int(tot[0])
    out = dict(origin='SIMULATED', engine='nvidia-warp', device=device, scenario=asdict(sc), seed=seed,
               parts=n, lots=int(c.shape[0]), kernel_seconds=round(secs, 4),
               parts_per_second=round(n / secs) if secs > 0 else None,
               truly_safe_rate=float(tot[1 + N_POL * K_PER + 2 * K_PAIR]) / n,
               duplicate_rate=float(tot[2 + N_POL * K_PER + 2 * K_PAIR]) / n, policies={}, paired_vs_B0={})
    for k, name in enumerate(POLICY_NAMES):
        b = 1 + k * K_PER
        unsafe, hold, good, fhold = (int(tot[b + i]) for i in range(4))
        lot_rates = c[:, b] / c[:, 0]
        out['policies'][name] = dict(unsafe_pass=unsafe, unsafe_pass_rate=unsafe / n, unsafe_pass_wilson95=_wilson(unsafe, n),
                                     unsafe_pass_rate_between_lot_se=float(np.std(lot_rates, ddof=1) / sqrt(len(lot_rates))),
                                     hold_rate=hold / n, released_good_rate=good / n, false_hold_rate=fhold / n)
    for j, name in enumerate(POLICY_NAMES[1:]):
        b = 1 + N_POL * K_PER + j * K_PAIR
        ua, ub, ga, gb = (int(tot[b + i]) for i in range(4))

        def paired(a_only, b_only):
            d = (a_only - b_only) / n
            se = sqrt(max(0.0, (a_only + b_only) / n - d * d) / n)
            return dict(diff=d, ci95=[d - 1.959964 * se, d + 1.959964 * se], discordant=[a_only, b_only])
        lot_d = (c[:, b] - c[:, b + 1]) / c[:, 0]
        out['paired_vs_B0'][name] = dict(unsafe_pass_rate=paired(ua, ub), released_good_rate=paired(ga, gb),
                                         unsafe_diff_between_lot_se=float(np.std(lot_d, ddof=1) / sqrt(len(lot_d))))
    return out
