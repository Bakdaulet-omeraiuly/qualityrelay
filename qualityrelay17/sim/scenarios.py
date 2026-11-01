"""SIM-02: scenario definitions, the part-truth generator, and scenario_manifest.json.

Every scenario persists its seed and ALL ground-truth generator parameters, and each run's
manifest records a SHA-256 of the full per-part truth table, so a result can be traced to
exactly the parts it was computed on. Every value is an ILLUSTRATIVE ASSUMPTION until
PHY-03 caliper data arrives (`cad.calibrate_from_caliper`).
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, asdict
from random import Random



@dataclass(frozen=True)
class SiteConfig:
    name: str = 'site-A'
    makes: str = 'both'               # 'slot' | 'tab' | 'both'
    printers: int = 4
    print_batch: int = 4              # parts per print job (= one lot)
    print_setup_s: float = 30.0
    print_per_part_s: float = 18.0
    printer_bias_mm: float = 0.0      # systematic width bias of this site's printers
    width_sd_mm: float = 0.12
    caliper_sd_mm: float = 0.05       # this site's instrument uncertainty
    inspection_lines: int = 1         # phone + Pi + metrology stations per line


@dataclass(frozen=True)
class FactoryScenario:
    sid: str
    title: str
    n_pairs: int = 400
    process_drift_mm_per_h: float = 0.0       # tab widens / slot narrows over time
    warp_p: float = 0.02
    warp_mm: float = 0.35
    crack_p: float = 0.03
    camera_noise: float = 0.04
    lot_lighting_flip_p: float = 0.0          # common-mode camera error shared by a whole lot
    missing_obs_p: float = 0.0                # a camera capture silently fails
    partition_windows_s: tuple = ()           # (start, end): Pi evidence unreachable
    failure_scale: float = 1.0                # multiplies every station's failure rate
    mtbf_s: float = 4 * 3600.0
    mttr_s: float = 600.0
    operators: int = 2
    review_capacity: int = 1
    wip_cap: int = 60
    transport_s: float = 20.0
    sites: tuple = (SiteConfig(),)
    assembly_site: str = 'site-A'
    inter_site_transport_s: float = 0.0
    evidence_latency_s: float = 0.0           # supplier evidence reaches the assembly decision late
    evidence_deadline_s: float = 120.0        # SAFE-MESH: older/missing evidence -> HOLD
    evidence_sharing: str = 'full'            # 'full' | 'summary' | 'none'
    cost_shock_at_s: float | None = None
    cost_shock_escape_multiplier: float = 1.0
    assembly_capacity: int = 1
    cameras: tuple = ('phone', 'pi')         # surface cameras on each inspection line
    # ---- CNC cell demo (D01). All of this is off for the registered F/M scenarios, whose truth tables are unchanged.
    machine: str = 'printer'                  # 'printer' | 'cnc': what the 3D Lab draws. The engine models both as a batch machine.
    tool_offset_fault_mm: float = 0.0         # wrong tool/wear offset from the first part: slot opening narrower and tab wider by
                                              # this much (the S-DEF / T-DEF specimens are 1.6 mm). Persists until a correction is applied.
    camera_gross_dim_mm: float | None = None  # the camera also flags a part whose functional width is off by more than this
    camera_gross_sens: float = 0.9            # ... with this sensitivity. None: camera checks the surface only (registered behaviour).
    caliper_mode: str = 'every_part'          # 'every_part': inline caliper on every part. 'flagged_only': no inline caliper; a caliper
                                              # chamber measures every dimension of camera-flagged parts only (unflagged parts are not measured).

    def as_dict(self):
        return asdict(self)


STATION_S = dict(phone=5.0, pi=6.0, caliper=7.0, assembly=9.0, sorting=3.0, review=45.0, rework=120.0,
                 chamber=60.0,     # caliper chamber: an operator measures every dimension of one flagged part
                 approval=30.0)    # an operator reads the chamber measurements and the program change before it is applied

# Coupon geometry (examples/cad/generate_specimen_stl.py) for the caliper chamber: every dimension, with its tolerance.
# The functional width (slot opening / tab width) comes from the measured STL; these are the other dimensions.
COUPON_DIMS = {'slot': dict(length_mm=(60.0, 0.30), height_mm=(6.0, 0.30), base_length_mm=(12.0, 0.30), rail_width_mm=(6.0, 0.30)),
               'tab': dict(length_mm=(60.0, 0.30), height_mm=(6.0, 0.30))}
FUNCTIONAL_TOL_MM = 0.30          # slot opening / tab width tolerance used by the chamber verdict (ILLUSTRATIVE)
DIM_PROCESS_SD_MM = 0.04          # process scatter of the non-functional dimensions (ILLUSTRATIVE)


def draw_part(sc: FactoryScenario, seed: int, kind: str, idx: int, site: SiteConfig, t_print_s: float, lot_id: str,
              design: dict, *, seq_idx: int | None = None, corrected: bool = False, offset_mm: float = 0.0) -> dict:
    """Ground truth + the observations each sensor WOULD produce, from part-keyed streams so every
    policy sees identical parts and identical sensor noise (common random numbers)."""
    rng = Random(f'part:{seed}:{kind}:{idx}')
    nominal = design['slot_opening_mm'] if kind == 'slot' else design['tab_width_mm']
    # Drift is indexed by PRODUCTION SEQUENCE (planned print time of part idx), not by the actual
    # print time: actual time depends on the policy (WIP blocking), and drift keyed to it would give
    # each policy different parts. Tool wear by part count is the physical reading of this.
    seq = idx if seq_idx is None else seq_idx  # a reprint keeps the production position of the part it replaces
    t_planned = seq * (site.print_setup_s / site.print_batch + site.print_per_part_s) * 2 / max(1, site.printers)
    drift = sc.process_drift_mm_per_h * t_planned / 3600.0
    bias = 0.0 if corrected else site.printer_bias_mm  # reprint: printer re-zeroed to the nominal CAD model
    # CNC demo: a wrong tool/wear offset is a machine state, so it stays on a re-machined part too (same sign convention as drift)
    fault = sc.tool_offset_fault_mm * (-1.0 if kind == 'slot' else 1.0)
    width = rng.gauss(nominal + bias + fault + (-drift / 2 if kind == 'slot' else drift), site.width_sd_mm)
    warped = rng.random() < sc.warp_p
    if warped:
        width += -sc.warp_mm if kind == 'slot' else sc.warp_mm
    latent = width          # process outcome before any printer correction (truth-hash basis)
    width = latent + offset_mm  # closed-loop printer correction (0 unless feedback is on)
    crack = rng.random() < sc.crack_p
    lot_flip = Random(f'lot:{seed}:{lot_id}').random() < sc.lot_lighting_flip_p
    cams = {}
    for cam in ('phone', 'pi', 'phone_local'):
        missing = rng.random() < sc.missing_obs_p
        flag = bool(crack ^ (rng.random() < sc.camera_noise) ^ lot_flip)
        cams[cam] = None if missing else flag
    readings = [width + rng.gauss(0, site.caliper_sd_mm) for _ in range(3)]  # supplier, assembly re-measure, review
    p = dict(part_id=f'{kind[0].upper()}-{seed}-{idx:06d}', idx=idx, seq_idx=seq, kind=kind, site=site.name, lot_id=lot_id,
             t_print_s=round(t_print_s, 3), true_width_mm=width, printed_width_mm=width, latent_width_mm=latent, offset_mm=offset_mm, warped=warped, crack=crack, lot_lighting_flip=lot_flip,
             cam=cams, caliper=readings, expert_crack_seen=crack if rng.random() > 0.02 else False,
             expert_width_mm=width + rng.gauss(0, 0.01), rework_ok=rng.random() < 0.8)
    # The CNC-demo observations come from their own part-keyed streams, so the streams above (and every
    # registered truth table) are untouched when these features are off.
    if sc.camera_gross_dim_mm is not None:
        g = Random(f'gross:{seed}:{kind}:{idx}')
        gross = abs(width - nominal) > sc.camera_gross_dim_mm      # the part as made, after any correction
        p['gross_dim'] = gross
        for cam in ('phone', 'pi', 'phone_local'):
            seen = g.random() < sc.camera_gross_sens
            if cams[cam] is not None and gross and seen:
                cams[cam] = True
    if sc.caliper_mode == 'flagged_only':
        d = Random(f'dims:{seed}:{kind}:{idx}')
        dims = {}
        for name, (nom, tol) in COUPON_DIMS[kind].items():
            true = nom + d.gauss(0, DIM_PROCESS_SD_MM)
            dims[name] = dict(nominal_mm=nom, tol_mm=tol, true_mm=true, reading_mm=true + d.gauss(0, site.caliper_sd_mm))
        p['dims'] = dims
    return p


def truth_hash(parts: list[dict]) -> str:
    parts = [p for p in parts if not p.get('root_id')]  # originals only: reprints depend on the policy by design
    keys = ('part_id', 'kind', 'site', 'lot_id', 'latent_width_mm', 'warped', 'crack')  # latent = before correction / rework
    blob = json.dumps([[p[k] if not isinstance(p[k], float) else round(p[k], 9) for k in keys] for p in parts])
    return hashlib.sha256(blob.encode()).hexdigest()


def _two_sites(**kw):
    return (SiteConfig('supplier-S', makes='slot', printers=2, **kw.get('s', {})),
            SiteConfig('supplier-T', makes='tab', printers=2, **kw.get('t', {})))


GRID = (
    FactoryScenario('F01', 'nominal single site'),
    FactoryScenario('F02', 'process drift 0.15 mm/h', process_drift_mm_per_h=0.15),
    FactoryScenario('F03', 'warping burst (warp_p 0.10)', warp_p=0.10),
    FactoryScenario('F04', 'crack burst (crack_p 0.10)', crack_p=0.10),
    FactoryScenario('F05', 'camera noise 0.12 + lot lighting flips 0.10', camera_noise=0.12, lot_lighting_flip_p=0.10),
    FactoryScenario('F06', 'missing observations 0.15', missing_obs_p=0.15),
    FactoryScenario('F07', 'network partition: Pi unreachable 30-90 min', partition_windows_s=((1800.0, 5400.0),)),
    FactoryScenario('F08', 'station failures x4', failure_scale=4.0),
    FactoryScenario('F09', 'quality bottleneck: 1 operator', operators=1),
    FactoryScenario('F10', 'cost shock: escape cost x3 after 1 h', cost_shock_at_s=3600.0, cost_shock_escape_multiplier=3.0),
)
BY_ID = {s.sid: s for s in GRID}


# ---- SIM-06: multi-site and scale ------------------------------------------------------------
_TWO = dict(sites=_two_sites(), assembly_site='assembly-site', inter_site_transport_s=900.0, n_pairs=300)
MULTI = (
    FactoryScenario('M01', 'two suppliers -> assembly site, full evidence sharing', **_TWO),
    FactoryScenario('M02', 'two suppliers, summary-only sharing (no raw frames cross sites)', evidence_sharing='summary', **_TWO),
    FactoryScenario('M03', 'two suppliers, sharing lost: assembly re-inspects locally', evidence_sharing='none', **_TWO),
    FactoryScenario('M04', 'two suppliers, evidence lags capture by 1200 s (300 s after the part arrives; deadline 120 s)', evidence_latency_s=1200.0, **_TWO),
    FactoryScenario('M05', 'supplier-T printers +0.15 mm bias and 0.10 mm caliper',
                    **{**_TWO, 'sites': _two_sites(t=dict(printer_bias_mm=0.15, caliper_sd_mm=0.10))}),
)
BY_ID.update({s.sid: s for s in MULTI})


# ---- CNC cell demo (D01): the closed-loop story shown in the 3D Lab ------------------------------------
# Two CNC machines (one per part kind), each loaded from a stock crate by a robot, start the shift with a wrong
# tool offset, so the first parts are out of tolerance by 1.6 mm (the size of the seeded S-DEF / T-DEF specimens).
# The camera flags gross size errors as well as surface defects; flagged parts go to a caliper chamber where every
# dimension is measured against the CAD nominal; unflagged parts are not measured. What happens next depends on
# the control mode chosen at run time (engine.Factory: control='closed_loop' | 'audit' | 'none').
CNC = (
    FactoryScenario('D01', 'CNC cell: wrong tool offset from the first part (slot −1.6 / tab +1.6 mm); camera gate, caliper chamber for flagged parts only',
                    machine='cnc', tool_offset_fault_mm=1.6, camera_gross_dim_mm=0.8, caliper_mode='flagged_only', warp_p=0.0,
                    n_pairs=60, transport_s=15.0,
                    sites=(SiteConfig(printers=2, print_batch=1, print_setup_s=12.0, print_per_part_s=48.0),)),
)
BY_ID.update({s.sid: s for s in CNC})


def scale_scenario(stations: int) -> FactoryScenario:
    """Production stations = printers + 3 per inspection line + assembly + sorting (the
    digital_line.py 6-station line is the smallest tier). Operators and review capacity scale with
    lines; assembly is scaled too so the tier measures the inspection cell, not one assembler."""
    tiers = {6: (1, 1), 10: (2, 2), 50: (12, 12)}
    if stations not in tiers:
        raise ValueError('tiers: 6, 10, 50')
    printers, lines = tiers[stations]
    site = SiteConfig(printers=printers, inspection_lines=lines)
    return FactoryScenario(f'SC{stations:02d}', f'{stations} production stations', sites=(site,),
                           n_pairs=150 * lines, operators=lines + 1, review_capacity=max(1, -(-lines // 4)),
                           wip_cap=40 + 30 * lines, assembly_capacity=max(1, -(-lines // 3)))
