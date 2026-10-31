"""SIM-02: scenario definitions, the part-truth generator, and scenario_manifest.json.

Every scenario persists its seed and ALL ground-truth generator parameters, and each run's
manifest records a SHA-256 of the full per-part truth table, so a result can be traced to
exactly the parts it was computed on. Every value is an ILLUSTRATIVE ASSUMPTION until
PHY-03 caliper data arrives (`cad.calibrate_from_caliper`).
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field, asdict, replace
from random import Random

from .cad import nominal_design


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

    def as_dict(self):
        return asdict(self)


STATION_S = dict(phone=5.0, pi=6.0, caliper=7.0, assembly=9.0, sorting=3.0, review=45.0, rework=120.0)


def draw_part(sc: FactoryScenario, seed: int, kind: str, idx: int, site: SiteConfig, t_print_s: float, lot_id: str,
              design: dict) -> dict:
    """Ground truth + the observations each sensor WOULD produce, from part-keyed streams so every
    policy sees identical parts and identical sensor noise (common random numbers)."""
    rng = Random(f'part:{seed}:{kind}:{idx}')
    nominal = design['slot_opening_mm'] if kind == 'slot' else design['tab_width_mm']
    # Drift is indexed by PRODUCTION SEQUENCE (planned print time of part idx), not by the actual
    # print time: actual time depends on the policy (WIP blocking), and drift keyed to it would give
    # each policy different parts. Tool wear by part count is the physical reading of this.
    t_planned = idx * (site.print_setup_s / site.print_batch + site.print_per_part_s) * 2 / max(1, site.printers)
    drift = sc.process_drift_mm_per_h * t_planned / 3600.0
    width = rng.gauss(nominal + site.printer_bias_mm + (-drift / 2 if kind == 'slot' else drift), site.width_sd_mm)
    warped = rng.random() < sc.warp_p
    if warped:
        width += -sc.warp_mm if kind == 'slot' else sc.warp_mm
    crack = rng.random() < sc.crack_p
    lot_flip = Random(f'lot:{seed}:{lot_id}').random() < sc.lot_lighting_flip_p
    cams = {}
    for cam in ('phone', 'pi', 'phone_local'):
        missing = rng.random() < sc.missing_obs_p
        flag = bool(crack ^ (rng.random() < sc.camera_noise) ^ lot_flip)
        cams[cam] = None if missing else flag
    readings = [width + rng.gauss(0, site.caliper_sd_mm) for _ in range(3)]  # supplier, assembly re-measure, review
    return dict(part_id=f'{kind[0].upper()}-{seed}-{idx:06d}', kind=kind, site=site.name, lot_id=lot_id,
                t_print_s=round(t_print_s, 3), true_width_mm=width, printed_width_mm=width, warped=warped, crack=crack, lot_lighting_flip=lot_flip,
                cam=cams, caliper=readings, expert_crack_seen=crack if rng.random() > 0.02 else False,
                expert_width_mm=width + rng.gauss(0, 0.01), rework_ok=rng.random() < 0.8)


def truth_hash(parts: list[dict]) -> str:
    keys = ('part_id', 'kind', 'site', 'lot_id', 'printed_width_mm', 'warped', 'crack')  # printed, not post-rework
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
