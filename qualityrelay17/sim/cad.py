"""SIM-03: CAD/STL geometry for the simulator + the sim-to-real calibration interface.

Nominal widths are MEASURED from the STL meshes (cross-section at mid-length), not read from
file names, so a re-exported CAD revision changes the simulator automatically. Physical
calibration (`calibrate_from_caliper`) accepts only records whose source_tier is
PHYSICAL_CAPTURE or VERIFIED_PHYSICAL and never relabels its output as physical: the fitted
generator parameters are still used to produce SIMULATED parts.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
from statistics import mean, stdev

STL_DIR = Path(__file__).resolve().parents[2] / 'examples' / 'cad' / 'stl'
PHYSICAL_TIERS = {'PHYSICAL_CAPTURE', 'OPERATOR_CONFIRMED', 'VERIFIED_PHYSICAL'}  # OPERATOR_CONFIRMED: typed caliper reading (AGENTS.md)


def _material_intervals(mesh):
    lo, hi = mesh.bounds
    sec = mesh.section(plane_origin=[(lo[0] + hi[0]) / 2, 0, (lo[2] + hi[2]) / 2], plane_normal=[1, 0, 0])
    if sec is None:
        raise ValueError('mid-length section is empty')
    spans = sorted((float(loop[:, 1].min()), float(loop[:, 1].max())) for loop in sec.discrete)
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1] + 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def measure_stl(path) -> dict:
    """{'kind': 'slot'|'tab'|'bar', 'functional_width_mm': ..., 'revision': sha256[:12]}.
    Slot: width of the opening between its two walls. Tab/bar: overall width."""
    import trimesh
    path = Path(path)
    mesh = trimesh.load(path)
    spans = _material_intervals(mesh)
    if len(spans) == 2:
        kind, width = 'slot', spans[1][0] - spans[0][1]
    elif len(spans) == 1:
        kind = 'tab' if path.name.startswith('tab') else 'bar'
        width = spans[0][1] - spans[0][0]
    else:
        raise ValueError(f'{path.name}: unexpected cross-section with {len(spans)} material spans')
    return dict(file=path.name, kind=kind, functional_width_mm=round(width, 4),
                extents_mm=[round(float(x), 4) for x in mesh.extents], watertight=bool(mesh.is_watertight),
                revision=hashlib.sha256(path.read_bytes()).hexdigest()[:12])


def cad_catalogue(stl_dir=STL_DIR) -> list[dict]:
    return [measure_stl(p) for p in sorted(Path(stl_dir).glob('*.stl'))]


def nominal_design(stl_dir=STL_DIR) -> dict:
    """Nominal slot opening / tab width and the design clearance, from the *_nominal_* meshes."""
    cat = {c['file']: c for c in cad_catalogue(stl_dir)}
    slot = next(c for f, c in cat.items() if f.startswith('slot_nominal'))
    tab = next(c for f, c in cat.items() if f.startswith('tab_nominal'))
    return dict(slot_opening_mm=slot['functional_width_mm'], tab_width_mm=tab['functional_width_mm'],
                design_clearance_mm=round(slot['functional_width_mm'] - tab['functional_width_mm'], 4),
                cad_revision=f"slot:{slot['revision']}+tab:{tab['revision']}", source='CAD_STL_MEASURED')


def calibrate_from_caliper(records: list[dict]) -> dict:
    """Fit per-part-type mean/sd from physical caliper records. Returns status NOT_AVAILABLE when
    there are no admissible physical records (the case on 31 Oct: no PHY-03 data yet)."""
    admissible = [r for r in records if r.get('source_tier') in PHYSICAL_TIERS]
    rejected = len(records) - len(admissible)
    out = dict(status='NOT_AVAILABLE', admissible=len(admissible), rejected_non_physical=rejected, fits={})
    for kind in ('slot', 'tab'):
        xs = [float(r['width_mm']) for r in admissible if r.get('kind') == kind]
        if len(xs) >= 3:
            out['fits'][kind] = dict(n=len(xs), mean_mm=round(mean(xs), 4), sd_mm=round(stdev(xs), 4))
    if out['fits']:
        out['status'] = 'FITTED_FROM_PHYSICAL_RECORDS'
        out['note'] = 'Generator parameters only; simulated parts drawn from them remain SIMULATED.'
    return out


ADAPTERS = {  # SIM-03 / P2 roadmap: honest adapter status, checked at call time
    'simpy': 'simpy', 'factorysimpy': 'factorysimpy', 'ortools': 'ortools', 'cadquery': 'cadquery',
    'cuopt': 'cuopt', 'isaacsim': 'isaacsim', 'omni.replicator': 'omni', 'warp': 'warp', 'newton': 'newton',
}


def adapter_status() -> dict:
    out = {}
    for name, module in ADAPTERS.items():
        installed = importlib.util.find_spec(module) is not None
        out[name] = 'INSTALLED_NOT_WIRED' if installed else 'NOT_CONFIGURED'
    out['trimesh'] = 'WORKING' if importlib.util.find_spec('trimesh') else 'NOT_CONFIGURED'
    out['scipy'] = 'WORKING' if importlib.util.find_spec('scipy') else 'NOT_CONFIGURED'
    return out
