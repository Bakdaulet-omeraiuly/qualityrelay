"""Read-only website API for the 18.1 science + simulation results (Bakdaulet).

Mounted by api.py with one include_router line; adilnurgg owns api.py and the final API.
Everything returned is SIMULATED; file access is allow-listed (no path traversal).
"""
from __future__ import annotations
import csv, json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import SOURCE_TIER, MODEL_VERSION
from .cad import cad_catalogue, nominal_design, STL_DIR
from .engine import Factory, calibrate_part_model, POLICIES, PAIRINGS
from .scenarios import GRID, MULTI, BY_ID

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / 'examples' / 'results'
router = APIRouter(prefix='/sim', tags=['simulation-18.1'])
CHARTS = {'good_per_hour', 'delta_profit_interval', 'hold_all_throughput', 'scale'}


@lru_cache(maxsize=1)
def _model():
    return calibrate_part_model()


@router.get('/scenarios')
def scenarios():
    return [dict(sid=s.sid, title=s.title, group='single-site' if s.sid.startswith('F') else 'multi-site')
            for s in list(GRID) + list(MULTI)]


@router.get('/cad')
def cad():
    return dict(nominal=nominal_design(), catalogue=cad_catalogue(), source_tier='CAD_STL_MEASURED')


@router.get('/stl/{name}')
def stl(name: str):
    allowed = {p.name for p in STL_DIR.glob('*.stl')}
    if name not in allowed:
        raise HTTPException(404, 'unknown STL')
    return FileResponse(STL_DIR / name, media_type='model/stl')


VENDOR = ROOT / 'web' / 'vendor'
ASSETS = {'three.module.js', 'OrbitControls.js', 'STLLoader.js', 'CSS2DRenderer.js', 'RoomEnvironment.js',
          'EffectComposer.js', 'RenderPass.js', 'UnrealBloomPass.js', 'OutputPass.js', 'ShaderPass.js', 'MaskPass.js',
          'Pass.js', 'CopyShader.js', 'LuminosityHighPassShader.js', 'OutputShader.js', 'site.js', 'site.css'}


@router.get('/assets/{name}')
def asset(name: str):
    if name not in ASSETS:
        raise HTTPException(404, 'unknown asset')
    base = VENDOR if name not in ('site.js', 'site.css') else ROOT / 'web'
    media = 'text/css' if name.endswith('.css') else 'text/javascript'
    return FileResponse(base / name, media_type=media)


@router.get('/charts/{name}.svg')
def chart(name: str):
    if name not in CHARTS:
        raise HTTPException(404, 'unknown chart')
    return FileResponse(RES / 'sim_18_1' / 'charts' / f'{name}.svg', media_type='image/svg+xml')


class RunRequest(BaseModel):
    scenario: str = 'F01'
    policy: str = 'bayes'
    pairing: str = 'optimized'
    seed: int = Field(0, ge=0, le=10_000)
    n_pairs: int = Field(60, ge=10, le=150)
    reprint: bool = True  # website default: closed-loop reprint of confirmed defects
    phone_only: bool = True  # website default: one iPhone camera per lane (registered results use phone + Pi)
    two_lanes: bool = True   # website default: separate slot and tab conveyor lanes


def _who(key: str):
    kind, _, rest = key.partition(':')
    if rest.startswith('P-'):
        a, _, b = rest[2:].partition('+')
        return kind, [a, b]
    return kind, [rest]


STATION_OF = {'phone': 'phone', 'pi': 'pi', 'cal': 'caliper', 'pl': 'phone_local', 'cl': 'caliper_local',
              'rv': 'review', 'rvp': 'review', 'rw': 'rework', 'as': 'assembly', 'so': 'sorting'}


@router.post('/run')
def run(req: RunRequest):
    from dataclasses import replace
    if req.scenario not in BY_ID or req.policy not in POLICIES or req.pairing not in PAIRINGS:
        raise HTTPException(422, 'unknown scenario/policy/pairing')
    sc = replace(BY_ID[req.scenario], n_pairs=req.n_pairs)
    if req.phone_only:
        sc = replace(sc, cameras=('phone',))
    if req.two_lanes:
        sc = replace(sc, sites=tuple(replace(s, inspection_lines=max(2, s.inspection_lines)) if s.makes == 'both' else s for s in sc.sites))
    f = Factory(sc, req.seed, req.policy, req.pairing, model=_model(), keep_log=True, reprint=req.reprint,
                lane_by_kind=req.two_lanes)
    summary = f.run()
    tl = {p['part_id']: [] for p in f.parts}
    for start, end, station, key in f.events:
        kind, ids = _who(key)
        for pid in ids:
            if pid in tl:
                tl[pid].append([STATION_OF.get(kind, station), start, end])
    from math import sqrt
    from .engine import surface_posterior, width_posterior, phi, TOL
    pair_of = {}
    for pr in f.pairs:
        pair_of[pr['slot_id']] = pr
        pair_of[pr['tab_id']] = pr
    by_id = {p['part_id']: p for p in f.parts}
    m = f.model
    parts = []
    for p in f.parts:
        pr = pair_of.get(p['part_id'], {})
        raw = p.get('obs_raw', {})
        ps = surface_posterior(raw, m, tuple(raw)) if raw else None
        parts.append(dict(id=p['part_id'], kind=p['kind'], site=p['site'], lot=p['lot_id'], print_t=p['t_print_s'],
                          crack=p['crack'], warped=p['warped'], fate=p.get('fate', 'unpaired'),
                          width_mm=round(p['printed_width_mm'], 3), measured_mm=round(p.get('measured_mm', 0.0), 3),
                          caliper_sd=p.get('caliper_sd'), cams={k: (None if v is None else bool(v)) for k, v in raw.items()},
                          surface_posterior=None if ps is None else round(ps, 5), reviewed=bool(p.get('reviewed')),
                          reprint_of=p.get('reprint_of'), reprinted_as=p.get('reprinted_as'), root_id=p.get('root_id'),
                          line=p.get('line', 0),
                          events=sorted(tl[p['part_id']], key=lambda e: e[1]),
                          pair=pr.get('pair_id'), decision=pr.get('decision'), escaped=bool(pr.get('escaped'))))
    pairs = []
    for pr in f.pairs:
        s, t = by_id.get(pr['slot_id']), by_id.get(pr['tab_id'])
        ev = dict(pair_id=pr['pair_id'], slot=pr['slot_id'], tab=pr['tab_id'], decision=pr.get('decision'),
                  reason=pr.get('reason'), fate=pr.get('fate'), escaped=bool(pr.get('escaped')), shipped_s=pr.get('shipped_s'),
                  formed_s=pr.get('formed_s'), truly_safe=pr.get('truly_safe'), true_clearance_mm=pr.get('true_clearance_mm'),
                  threshold=round(f.costs.hold / (f.costs.hold + f.costs.escaped_defect), 5))
        if s and t and 'measured_mm' in s and 'measured_mm' in t:
            (ms, vs), (mt, vt) = width_posterior(s['measured_mm'], 'slot', m, s['caliper_sd']), width_posterior(t['measured_mm'], 'tab', m, t['caliper_sd'])
            ev.update(measured_clearance_mm=round(s['measured_mm'] - t['measured_mm'], 4),
                      posterior_clearance_mm=round(ms - mt, 4), posterior_clearance_sd=round(sqrt(vs + vt), 4),
                      p_dimensional=round(phi((TOL - (ms - mt)) / sqrt(vs + vt)), 6),
                      p_surface_slot=round(f._ps(s), 6), p_surface_tab=round(f._ps(t), 6),
                      p_unsafe=pr.get('p_unsafe', round(f.pair_risk(s, t), 6)))
        pairs.append(ev)
    stations = {}
    line_of = {p['part_id']: p.get('line', 0) for p in f.parts}
    for start, end, station, key in f.events:
        st_ = STATION_OF.get(key.partition(':')[0], station)
        if st_ in ('phone', 'pi', 'caliper'):  # per-lane stations: key them by inspection line
            st_ = f"{st_}_{line_of.get(_who(key)[1][0], 0)}"
        d = stations.setdefault(st_, dict(visits=0, busy_s=0.0))
        d['visits'] += 1; d['busy_s'] += end - start
    for d in stations.values():
        d['busy_share'] = round(d['busy_s'] / max(1e-9, summary['makespan_s']), 4); d['busy_s'] = round(d['busy_s'], 2)
    keep = ('makespan_s', 'shipped', 'shipped_good', 'escaped', 'good_per_hour', 'mean_cycle_s', 'part_holds', 'pair_holds',
            'holds_stale_evidence', 'scrapped_parts', 'reworks', 'downtime_s', 'conservation_ok', 'truth_sha256', 'reprints')
    return dict(source_tier=SOURCE_TIER, model_version=MODEL_VERSION, scenario=req.scenario, title=sc.title, reprint=req.reprint,
                cameras=list(sc.cameras), two_lanes=req.two_lanes,
                policy=req.policy, pairing=req.pairing, seed=req.seed, n_pairs=req.n_pairs,
                kpis={k: summary[k] for k in keep}, parts=parts, pairs=pairs, stations=stations,
                model=dict(calibration_id=m.calibration_id, phone_sens=m.phone_sens, phone_spec=m.phone_spec,
                           pi_sens=m.pi_sens, pi_spec=m.pi_spec, crack_prior=m.crack_prior))


def _csv(path):
    with open(path) as fh:
        return list(csv.DictReader(fh))


@lru_cache(maxsize=1)
def _results_bundle():
    s = RES / 'sim_18_1'
    summary = _csv(s / 'factory_summary.csv')
    contrasts = [r for r in _csv(s / 'factory_contrasts.csv') if r['question'] == 'product configuration vs today']
    roi = json.loads((s / 'roi.json').read_text())['by_scenario']
    gate = json.loads((RES / 'collective_gate_a' / 'S01.json').read_text())
    gate_c = {}
    for sid in ('S01', 'S11', 'S12', 'S13'):
        g = json.loads((RES / 'collective_gate_a' / f'{sid}.json').read_text())
        gate_c[sid] = [dict(a=c['a'], b=c['b'], question=c['question'], verdict=c['verdict'],
                            cost=c['cost_per_unit_diff'], unsafe=c['unsafe_pass_rate_diff'], good=c['released_good_rate_diff'])
                       for c in g['contrasts']]
    warp = {}
    for p in sorted((RES / 'warp_mc' / 'cpu').glob('S0*.json')):
        w = json.loads(p.read_text())
        warp[w['scenario']['sid']] = dict(title=w['scenario']['title'], parts=w['parts'],
                                          unsafe_per_1000={k: 1000 * v['unsafe_pass_rate'] for k, v in w['policies'].items()},
                                          b1_minus_b0_ci=[1000 * x for x in w['paired_vs_B0']['B1_single_agent_fixed']['unsafe_pass_rate']['ci95']],
                                          f_minus_b0_ci=[1000 * x for x in w['paired_vs_B0']['F_collective_fusion']['unsafe_pass_rate']['ci95']],
                                          parts_per_second=w['parts_per_second'])
    tuning_path = RES / 'sim_18_1_tuning' / 'tuning.json'
    tuning = json.loads(tuning_path.read_text()) if tuning_path.exists() else {}
    return dict(
        source_tier=SOURCE_TIER,
        factory=dict(summary=[{k: r[k] for k in ('scenario', 'title', 'config', 'good_per_hour', 'escapes_per_1000_shipped',
                                                 'cost_per_good_unit', 'profit_per_hour', 'holds')} for r in summary],
                     product_vs_today=[dict(scenario=r['scenario'], good_per_hour_diff=float(r['good_per_hour_diff']),
                                            escapes_diff=float(r['escapes_per_1000_shipped_diff']),
                                            cost_per_good_diff=float(r['cost_per_good_unit_diff']),
                                            safe=r['safety_non_inferior'] == 'True', throughput=r['throughput_preserved'] == 'True',
                                            cheaper=r['cheaper_per_good_unit'] == 'True') for r in contrasts],
                     roi={k: dict(p05=v['delta_profit_per_hour']['p05'], p50=v['delta_profit_per_hour']['p50'],
                                  p95=v['delta_profit_per_hour']['p95'], p_worse=v['p_qr_worse']) for k, v in roi.items()},
                     hold_all=json.loads((s / 'hold_all.json').read_text()),
                     scale=json.loads((s / 'scale.json').read_text())['tiers']),
        gate_a=dict(summary=gate['summary'], contrasts=gate_c),
        warp=warp,
        tuning=dict(chosen=tuning.get('chosen', {}).get('setting'), better_on_all_three=tuning.get('better_on_all_three')),
    )


@router.get('/results')
def results():
    return _results_bundle()


# ---- camera captures (real photos) -> training folders for VISION-04 -------------------------
class CaptureRequest(BaseModel):
    lane: str = Field('slot', pattern='^(slot|tab)$')
    label: str = Field('inbox', pattern='^(good|defect|inbox)$')
    image_b64: str = Field(..., min_length=32, max_length=12_000_000)


PRINTS = ROOT / 'data' / 'prints'   # data/ is git-ignored; the anomaly pipeline reads data/prints/good|defect


@router.post('/vision/capture')
def vision_capture(req: CaptureRequest):
    """Save one real iPhone/webcam photo as PHYSICAL_CAPTURE training data and report the NVIDIA
    anomaly model status. No score is invented: until a model is trained on PHYSICAL_CAPTURE photos
    (VISION-04 on the Brev L4), the status is NOT_CONFIGURED."""
    import base64, hashlib, time
    raw = req.image_b64.split(',', 1)[1] if req.image_b64.startswith('data:') else req.image_b64
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception:  # noqa: BLE001
        raise HTTPException(422, 'image_b64 is not valid base64')
    if len(data) > 8_000_000:
        raise HTTPException(413, 'image larger than 8 MB')
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(422, 'not a decodable image')
    sha = hashlib.sha256(data).hexdigest()
    ext = '.png' if data[:8] == b'\x89PNG\r\n\x1a\n' else '.jpg'
    folder = PRINTS / req.label
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{time.strftime('%Y%m%dT%H%M%S')}_{req.lane}_{sha[:10]}{ext}"
    path.write_bytes(data)
    counts = {k: len(list((PRINTS / k).glob('*'))) if (PRINTS / k).exists() else 0 for k in ('good', 'defect', 'inbox')}
    ready = counts['good'] >= 30 and counts['defect'] >= 10
    saved = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return dict(source_tier='PHYSICAL_CAPTURE', saved=saved, sha256=sha, width=int(img.shape[1]),
                height=int(img.shape[0]), lane=req.lane, label=req.label, dataset_counts=counts,
                nvidia_anomaly=dict(status='NOT_CONFIGURED',
                                    reason='The STFPM model has only been trained on synthetic CAD renders and MVTec; scoring a real '
                                           'photo with it would be out of domain. Train it on these PHYSICAL_CAPTURE photos first.',
                                    ready_to_train=ready, need=dict(good=30, defect=10),
                                    train_command='python scripts/train_anomaly.py --data captured --root data/prints --epochs 100 --size 256  (Brev L4)'))
