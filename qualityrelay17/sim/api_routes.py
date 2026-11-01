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
from .engine import Factory, calibrate_part_model, POLICIES, PAIRINGS, CONTROLS
from .scenarios import GRID, MULTI, CNC, BY_ID

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / 'examples' / 'results'
router = APIRouter(prefix='/sim', tags=['simulation-18.1'])
CHARTS = {'good_per_hour', 'delta_profit_interval', 'hold_all_throughput', 'scale'}


@lru_cache(maxsize=1)
def _model():
    return calibrate_part_model()


@router.get('/scenarios')
def scenarios():
    group = {'F': 'single-site', 'M': 'multi-site', 'D': 'cnc-demo'}
    return [dict(sid=s.sid, title=s.title, group=group[s.sid[0]], machine=s.machine, caliper_mode=s.caliper_mode)
            for s in list(GRID) + list(MULTI) + list(CNC)]


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
          'Pass.js', 'CopyShader.js', 'LuminosityHighPassShader.js', 'OutputShader.js', 'GTAOPass.js', 'GTAOShader.js', 'PoissonDenoiseShader.js', 'SimplexNoise.js',
          'SMAAPass.js', 'SMAAShader.js', 'RGBELoader.js', 'camera-controls.module.js', 'three-mesh-bvh.module.js', 'three-gpu-pathtracer.module.js', 'qrcode.js', 'site.js', 'site.css'}


@router.get('/assets/{name}')
def asset(name: str):
    if name not in ASSETS:
        raise HTTPException(404, 'unknown asset')
    base = VENDOR if name not in ('site.js', 'site.css') else ROOT / 'web'
    media = 'text/css' if name.endswith('.css') else 'text/javascript'
    return FileResponse(base / name, media_type=media)


@router.get('/hdri/warehouse.hdr')
def hdri():
    return FileResponse(VENDOR / 'hdri' / 'empty_warehouse_01_1k.hdr', media_type='application/octet-stream')


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
    agents: bool = True      # decisions made by the six agents (sim/agents.py); a reference run checks they match
    # CNC demo (D01). 'auto': closed loop for the QualityRelay policies, scheduled audit for today's rule; 'none' elsewhere.
    control: str = Field('auto', pattern='^(auto|none|closed_loop|audit)$')
    halt_on_flags: int = Field(6, ge=1, le=20)                 # D01: camera-detected defects that stop the line (machine scope: flags in a row)
    confirm_n: int = Field(3, ge=1, le=20)                     # chamber confirmations before a correction is proposed
    max_correction_mm: float = Field(2.0, gt=0, le=10)         # a larger proposed change is refused (machine stays stopped)
    audit_interval_s: float = Field(1800.0, ge=60, le=8 * 3600)  # today's line: the chamber findings reach the machine at the next audit
    planner: str = 'fixed'   # 'fixed' | 'llm_cached': Assembly's requests from the cached LLM planner (replay only, never calls the API)


def _who(key: str):
    kind, _, rest = key.partition(':')
    if rest.startswith('P-'):
        a, _, b = rest[2:].partition('+')
        return kind, [a, b]
    return kind, [rest]


STATION_OF = {'phone': 'phone', 'pi': 'pi', 'cal': 'caliper', 'pl': 'phone_local', 'cl': 'caliper_local',
              'rv': 'review', 'rvp': 'review', 'rw': 'rework', 'as': 'assembly', 'so': 'sorting', 'ch': 'chamber', 'ap': 'approval'}


def _control(req: RunRequest, sc) -> str:
    if req.control != 'auto':
        return req.control
    if sc.machine != 'cnc':
        return 'none'
    return 'audit' if req.policy == 'rules' else 'closed_loop'


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
    planner = None
    if req.planner == 'llm_cached':
        from .llm_cache import CachingPlanner
        planner = CachingPlanner(mode='replay')  # the website never spends: misses fall back to the fixed order, counted
    elif req.planner != 'fixed':
        raise HTTPException(422, 'planner must be fixed|llm_cached')
    control = _control(req, sc)
    assert control in CONTROLS
    loop = dict(control=control, halt_on_flags=req.halt_on_flags, confirm_n=req.confirm_n, max_correction_mm=req.max_correction_mm,
                audit_interval_s=req.audit_interval_s)
    f = Factory(sc, req.seed, req.policy, req.pairing, model=_model(), keep_log=True, reprint=req.reprint,
                lane_by_kind=req.two_lanes, agents=req.agents, planner=planner, **loop)
    summary = f.run()
    agents_out = None
    if req.agents:
        # reference line without agents, same seed: every agent decision must equal the built-in computation
        ref = Factory(sc, req.seed, req.policy, req.pairing, model=_model(), keep_log=True, reprint=req.reprint, lane_by_kind=req.two_lanes, **loop)
        ref.run()
        key = lambda p: (p['pair_id'], p['decision'], p.get('p_unsafe'), p.get('fate'))  # noqa: E731
        a_, r_ = [key(p) for p in f.pairs], [key(p) for p in ref.pairs]
        agents_out = f.agents.export()
        agents_out['check'] = dict(pairs=len(a_), equal=sum(x == y for x, y in zip(a_, r_)) if len(a_) == len(r_) else 0,
                                   identical=a_ == r_, note=('LLM-planned requests vs the fixed-order line, same seed: a difference means the planner changed what was asked'
                                         if planner else 'agent decisions vs the line\'s built-in computation, same seed'))
        agents_out['policy_inside'] = {'bayes': 'Bayes expected-cost threshold', 'rules': 'fixed rule (today\'s practice)',
                                       'hold_all': 'hold everything for review'}[req.policy]
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
    r3 = lambda v: None if v is None else round(v, 3)  # noqa: E731  an unmeasured part (caliper_mode flagged_only) stays None
    parts = []
    for p in f.parts:
        pr = pair_of.get(p['part_id'], {})
        raw = p.get('obs_raw', {})
        ps = surface_posterior(raw, m, tuple(raw)) if raw else None
        parts.append(dict(id=p['part_id'], kind=p['kind'], site=p['site'], lot=p['lot_id'], print_t=p['t_print_s'],
                          crack=p['crack'], warped=p['warped'], fate=p.get('fate', 'unpaired'),
                          width_mm=round(p['printed_width_mm'], 3), measured_mm=r3(p.get('measured_mm')),
                          caliper_sd=p.get('caliper_sd'), cams={k: (None if v is None else bool(v)) for k, v in raw.items()},
                          surface_posterior=None if ps is None else round(ps, 5), reviewed=bool(p.get('reviewed')),
                          reprint_of=p.get('reprint_of'), reprinted_as=p.get('reprinted_as'), root_id=p.get('root_id'),
                          line=p.get('line', 0),
                          events=sorted(tl[p['part_id']], key=lambda e: e[1]),
                          pair=pr.get('pair_id'), decision=pr.get('decision'), escaped=bool(pr.get('escaped')),
                          flagged=bool(p.get('flagged')), offset_mm=round(p.get('offset_mm', 0.0), 4), machine_s=p.get('machine_s'),
                          chamber=p.get('chamber'), contained=bool(p.get('contained'))))
    pairs = []
    for pr in f.pairs:
        s, t = by_id.get(pr['slot_id']), by_id.get(pr['tab_id'])
        ev = dict(pair_id=pr['pair_id'], slot=pr['slot_id'], tab=pr['tab_id'], decision=pr.get('decision'),
                  reason=pr.get('reason'), fate=pr.get('fate'), escaped=bool(pr.get('escaped')), shipped_s=pr.get('shipped_s'),
                  formed_s=pr.get('formed_s'), truly_safe=pr.get('truly_safe'), true_clearance_mm=pr.get('true_clearance_mm'),
                  threshold=round(f.costs.hold / (f.costs.hold + f.costs.escaped_defect), 5))
        if s and t and 'measured_mm' in s and 'measured_mm' in t:
            (ms, vs), (mt, vt) = width_posterior(s['measured_mm'], 'slot', m, s['caliper_sd']), width_posterior(t['measured_mm'], 'tab', m, t['caliper_sd'])
            ev.update(measured_clearance_mm=round(f._m(s) - f._m(t), 4), both_measured=s['measured_mm'] is not None and t['measured_mm'] is not None,
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
                machine=sc.machine, caliper_mode=sc.caliper_mode, control=control, tool_offset_fault_mm=sc.tool_offset_fault_mm,
                loop=dict(halt_on_flags=req.halt_on_flags, confirm_n=req.confirm_n, max_correction_mm=req.max_correction_mm,
                          audit_interval_s=req.audit_interval_s if control == 'audit' else None),
                line_events=summary['line_events'], waste=summary['waste'],
                halt_scope=sc.halt_scope, contain_suspect=sc.contain_suspect, chamber_csv=summary['chamber_csv'],
                nominal=dict(slot=f.design['slot_opening_mm'], tab=f.design['tab_width_mm']),
                kpis={k: summary[k] for k in keep}, parts=parts, pairs=pairs, stations=stations, agents=agents_out,
                costs=dict(hold=f.costs.hold, escaped_defect=f.costs.escaped_defect),
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
DEFECT_TYPES = ('warp', 'stringing', 'chip', 'hole', 'crack', 'layer_shift', 'under_extrusion', 'wrong_size', 'other')


class CaptureRequest(BaseModel):
    lane: str = Field('slot', pattern='^(slot|tab)$')
    label: str = Field('inbox', pattern='^(good|defect|inbox)$')
    image_b64: str = Field(..., min_length=32, max_length=12_000_000)
    # PHOTO_CAPTURE_GUIDE.md: purpose decides the folder; specimen ID and defect type are required
    # bookkeeping for honest results; caliper_mm (optional) validates the photo measurement.
    purpose: str = Field('training', pattern='^(training|measurement)$')
    specimen_id: str | None = Field(None, pattern='^[A-Za-z0-9_-]{1,40}$')
    defect_type: str | None = Field(None, pattern='^(' + '|'.join(DEFECT_TYPES) + ')$')
    caliper_mm: float | None = Field(None, gt=0, lt=100)


PRINTS = ROOT / 'data' / 'prints'   # data/ is git-ignored; the anomaly pipeline reads data/prints/good|defect


CAPTURE_LOG_FIELDS = ('saved_at', 'file', 'purpose', 'label', 'defect_type', 'specimen_id', 'lane', 'caliper_mm',
                      'photo_width_mm', 'photo_kind', 'photo_px_per_mm', 'sha256', 'label_checked_by')


def _log_capture(path, req, sha, img):
    """Append one row to data/prints/capture_log.csv. label_checked_by stays empty until a second person
    checks the label (required before reporting PHYSICAL_CAPTURE results)."""
    import csv as _csv, time
    from ..vision_measure import measure_part_width
    try:
        m = measure_part_width(img)
    except Exception:  # noqa: BLE001
        m = {}
    log = PRINTS / 'capture_log.csv'
    new = not log.exists()
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'a', newline='') as fh:
        w = _csv.DictWriter(fh, fieldnames=CAPTURE_LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow(dict(saved_at=time.strftime('%Y-%m-%dT%H:%M:%S'), file=path.name, purpose=req.purpose, label=req.label,
                        defect_type=req.defect_type or '', specimen_id=req.specimen_id or '', lane=req.lane,
                        caliper_mm='' if req.caliper_mm is None else req.caliper_mm,
                        photo_width_mm=m.get('width_mm', ''), photo_kind=m.get('kind', ''), photo_px_per_mm=m.get('photo_px_per_mm', ''),
                        sha256=sha, label_checked_by=''))


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
    if req.label == 'defect' and req.purpose == 'training' and not req.defect_type:
        raise HTTPException(422, 'a defect photo for training needs defect_type (see PHOTO_CAPTURE_GUIDE.md)')
    # training photos -> data/prints/{good,defect,inbox}; measurement / reference photos -> data/measure/
    folder = (PRINTS / req.label) if req.purpose == 'training' else (PRINTS.parent / 'measure')
    folder.mkdir(parents=True, exist_ok=True)
    tag = req.defect_type if req.label == 'defect' and req.defect_type else req.label
    # hash prefix first: the trainer takes the first 70% of good/ by filename, so names must not sort by
    # time or by part type (avoids a biased train/test split); the defect type stays readable in the name
    path = folder / f"{sha[:6]}_{tag}_{req.specimen_id or 'noid'}_{req.lane}_{time.strftime('%Y%m%dT%H%M%S')}{ext}"
    path.write_bytes(data)
    counts = {k: len([f for f in (PRINTS / k).glob('*') if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp')]) if (PRINTS / k).exists() else 0
              for k in ('good', 'defect', 'inbox')}
    ready = counts['good'] >= 30 and counts['defect'] >= 10
    saved = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    _log_capture(path, req, sha, img)
    from ..vision_measure import measure_part_width
    try:
        measurement = measure_part_width(img)
    except Exception as e:  # noqa: BLE001 -- a failed measurement must not lose the saved photo
        measurement = dict(status='ERROR', note=str(e)[:200])
    return dict(source_tier='PHYSICAL_CAPTURE', saved=saved, sha256=sha, width=int(img.shape[1]),
                height=int(img.shape[0]), lane=req.lane, label=req.label, dataset_counts=counts, measurement=measurement,
                purpose=req.purpose, specimen_id=req.specimen_id, defect_type=req.defect_type, caliper_mm=req.caliper_mm,
                photo_minus_caliper_mm=(round(measurement['width_mm'] - req.caliper_mm, 3) if req.caliper_mm and measurement.get('status') == 'MEASURED' else None),
                nvidia_anomaly=dict(status='NOT_CONFIGURED',
                                    reason='The STFPM model has only been trained on synthetic CAD renders and MVTec; scoring a real '
                                           'photo with it would be out of domain. Train it on these PHYSICAL_CAPTURE photos first.',
                                    ready_to_train=ready, need=dict(good=30, defect=10), recommended=dict(good=50, defect=20),
                                    train_command='python scripts/train_anomaly.py --data captured --root data/prints --epochs 100 --size 256  (Brev L4)'))


# ---- I9 active learning: which photo to label next ------------------------------------------------
@router.get('/vision/suggest')
def vision_suggest(limit: int = 10):
    """Uncertainty sampling for the dimensional model: unlabelled photos whose measured width is
    closest to the decision boundary (tab ~20.5 mm / slot ~20.5 mm for the 0.5 mm clearance at the
    nominal partner) are the most informative to label first. Unmeasurable photos come last."""
    from ..vision_measure import measure_part_width
    import cv2
    inbox = PRINTS / 'inbox'
    files = sorted(inbox.glob('*')) if inbox.exists() else []
    d = nominal_design(); boundary = {'tab_width': d['slot_opening_mm'] - 0.5, 'slot_opening': d['tab_width_mm'] + 0.5}
    rows = []
    for f in files[:200]:
        img = cv2.imread(str(f))
        m = measure_part_width(img) if img is not None else dict(status='UNREADABLE')
        if m.get('status') == 'MEASURED':
            margin = abs(m['width_mm'] - boundary[m['kind']])
            rows.append(dict(file=f.name, kind=m['kind'], width_mm=m['width_mm'], margin_mm=round(margin, 3),
                             reason=f"width {m['width_mm']} mm is {margin:.2f} mm from the {boundary[m['kind']]:.2f} mm boundary"))
        else:
            rows.append(dict(file=f.name, kind=None, width_mm=None, margin_mm=None, reason=f"{m.get('status')}: label by eye"))
    rows.sort(key=lambda r: (r['margin_mm'] is None, r['margin_mm'] if r['margin_mm'] is not None else 0))
    return dict(source_tier='PHYSICAL_CAPTURE', inbox=len(files), suggestions=rows[:limit],
                method='uncertainty sampling on the measured width vs the clearance boundary')


# ---- I8 live mode: physical station events -> browser (Server-Sent Events, no extra dependency) ------
import asyncio
from collections import deque
from fastapi import Request
from fastapi.responses import StreamingResponse

LIVE = deque(maxlen=500)
_LIVE_SEQ = [0]


class LiveEvent(BaseModel):
    """Shared integration-contract fields (QUALITYRELAY_18_1_TEAM_TASKS_EN.md section 4). A
    self-declared station is NOT a verified identity: events are displayed, never acted on, and
    keep their declared tier (adilnurgg's authenticated ingest replaces this in production)."""
    event_id: str = Field(..., max_length=120)
    specimen_id: str = Field(..., max_length=120)
    station_id: str = Field(..., pattern='^(phone|pi|caliper|assembly|sorter|virtual-station)$')
    source_tier: str = Field('PHYSICAL_CAPTURE', pattern='^(SIMULATED|PHYSICAL_CAPTURE)$')
    observed_at: str = Field(..., max_length=40)
    lane: str = Field('slot', pattern='^(slot|tab)$')
    value: str | float | bool | None = None
    note: str | None = Field(None, max_length=200)


@router.post('/live/event')
def live_event(ev: LiveEvent):
    _LIVE_SEQ[0] += 1
    rec = dict(seq=_LIVE_SEQ[0], verified=False, **ev.model_dump())
    LIVE.append(rec)
    return dict(accepted=True, seq=rec['seq'], verified=False)


@router.get('/live/recent')
def live_recent(after: int = 0):
    return [e for e in LIVE if e['seq'] > after]


@router.get('/live/stream')
async def live_stream(request: Request, after: int = 0):
    async def gen():
        last = after
        while not await request.is_disconnected():
            for e in [e for e in list(LIVE) if e['seq'] > last]:
                last = e['seq']
                yield f"data: {json.dumps(e)}\n\n"
            yield ': keep-alive\n\n'
            await asyncio.sleep(0.5)
    return StreamingResponse(gen(), media_type='text/event-stream')


# ---- PR #8 visual-inspection tools, wired into the camera panel ----------------------------------
REFS = ROOT / 'data' / 'reference'   # git-ignored, per-lane GOOD reference photos (registered)


class InspectRequest(BaseModel):
    lane: str = Field('slot', pattern='^(slot|tab)$')
    action: str = Field('quality', pattern='^(quality|set_reference|compare|roboflow)$')
    image_b64: str = Field(..., min_length=32, max_length=12_000_000)
    roboflow_json: str | None = Field(None, max_length=2_000_000)
    model_id: str = Field('roboflow-unspecified', max_length=160)
    threshold: int = Field(40, ge=1, le=255)
    edge_band_px: int = Field(2, ge=0, le=8)


def _decode(b64: str):
    import base64, cv2, numpy as np
    raw = b64.split(',', 1)[1] if b64.startswith('data:') else b64
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception:  # noqa: BLE001
        raise HTTPException(422, 'image_b64 is not valid base64')
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(422, 'not a decodable image')
    return data, img


def _jpeg_b64(img, max_w=900):
    import base64, cv2
    if img.shape[1] > max_w:
        img = cv2.resize(img, (max_w, int(img.shape[0] * max_w / img.shape[1])), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.tobytes()).decode()


@router.post('/vision/inspect')
def vision_inspect(req: InspectRequest):
    """Quality gate, registered reference comparison (heatmap + candidate boxes) and Roboflow-JSON box
    rendering, using qualityrelay17.inspection_visuals (PR #8). Every result is an
    UNVERIFIED_VISUAL_CANDIDATE that requires review; nothing here passes or rejects a part."""
    import hashlib, json as _json, time, cv2, numpy as np
    from ..inspection_visuals import image_quality, reference_difference, roboflow_predictions, overlay_heatmap, draw_candidate_boxes, candidate_regions
    from ..vision_measure import rectify_by_marker
    data, img = _decode(req.image_b64)
    sha = hashlib.sha256(data).hexdigest()
    out = dict(source_tier='PHYSICAL_CAPTURE', lane=req.lane, action=req.action, image_sha256=sha, quality=image_quality(img),
               anomaly_model=dict(status='NOT_CONFIGURED', note='STFPM/Anomalib score maps are shown once a model is trained on real photos; '
                                                               'offline: scripts/inspect_visual.py --mode anomaly-map'))
    if req.action == 'quality':
        return out
    if req.action == 'roboflow':
        if not req.roboflow_json:
            raise HTTPException(422, 'paste the Roboflow prediction JSON')
        try:
            payload = _json.loads(req.roboflow_json)
            rep, _, _ = roboflow_predictions(img, payload, specimen_id=f'{req.lane}-photo', image_event_id=f'img-{sha[:12]}', source_root=f'root-{sha[:12]}',
                                             station_id='PHONE', source_tier='PHYSICAL_CAPTURE', model_id=req.model_id)
        except (ValueError, TypeError) as e:
            raise HTTPException(422, str(e)[:200])
        out.update(report=rep, boxes=_jpeg_b64(draw_candidate_boxes(img, rep)))
        return out
    rect, info = rectify_by_marker(img)
    out['registration'] = info
    if rect is None:
        raise HTTPException(422, 'ArUco marker not found: registration (and reference comparison) needs the printed marker sheet in the photo')
    REFS.mkdir(parents=True, exist_ok=True)
    ref_path, meta_path = REFS / f'{req.lane}.png', REFS / f'{req.lane}.json'
    if req.action == 'set_reference':
        cv2.imwrite(str(ref_path), rect)
        meta_path.write_text(_json.dumps(dict(sha256=sha, saved=time.strftime('%Y-%m-%dT%H:%M:%S'), registration=info)))
        out.update(reference_saved=True, preview=_jpeg_b64(rect))
        return out
    if not ref_path.exists():
        raise HTTPException(409, f'no GOOD reference for the {req.lane} lane yet: save one first')
    ref = cv2.imread(str(ref_path)); meta = _json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if meta.get('sha256') == sha:
        raise HTTPException(422, 'this is the reference photo itself; take a new photo of the part to inspect')
    blur = lambda im: cv2.GaussianBlur(im, (5, 5), 0)  # noqa: E731
    rep, diff, mask = reference_difference(blur(ref), blur(rect), specimen_id=f'{req.lane}-photo', image_event_id=f'img-{sha[:12]}',
                                           source_root=f'root-{sha[:12]}', reference_event_id=f'ref-{meta.get("sha256", "unknown")[:12]}',
                                           reference_root=f'refroot-{meta.get("sha256", "unknown")[:12]}', station_id='PHONE',
                                           source_tier='PHYSICAL_CAPTURE', aligned=True, threshold=req.threshold, min_area_px=40)
    if req.edge_band_px:
        g = cv2.GaussianBlur(cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        band = cv2.dilate(cv2.Canny(g, 40, 120), np.ones((2 * req.edge_band_px + 1,) * 2, np.uint8)) > 0
        mask = mask.copy(); mask[band] = 0
        rep['regions'] = candidate_regions(mask, min_area_px=40)
        rep['warnings'] = sorted(set(rep['warnings'] + [f'EDGE_BAND_{req.edge_band_px}PX_SUPPRESSED_DEFECTS_ON_EDGES_CAN_BE_MISSED']))
    rep['registration'] = 'ArUco homography to a shared metric frame (lighting differences are not corrected)'
    out.update(report=rep, heatmap=_jpeg_b64(overlay_heatmap(rect, diff, mask=mask)), boxes=_jpeg_b64(draw_candidate_boxes(rect, rep)),
               reference_saved_at=meta.get('saved'))
    return out


# ---- physical data (HyorinmaruK's measurement logger) and the physical demo pages -------------------
MEASUREMENTS = ROOT / 'data' / 'measurements'   # put exported measurement_logger CSVs here (git-ignored)
PHYSICAL_PAGES = {'manual_track_visualizer', 'measurement_logger', 'physical_build_guide', 'tabletop_demo'}


@router.get('/physical/summary')
def physical_summary():
    """Caliper calibration from data/measurements/*.csv and the photo-vs-caliper check. Runs with the
    fitted values stay SIMULATED (physically calibrated); the caliper is authoritative."""
    from .physical_data import load_measurements, calibrate, photo_vs_caliper
    files = sorted(MEASUREMENTS.glob('*.csv')) if MEASUREMENTS.exists() else []
    if not files:
        return dict(status='NOT_AVAILABLE', files=[], hint='Export the CSV from web/measurement_logger.html into data/measurements/')
    rows = load_measurements(files)
    return dict(files=[f.name for f in files], rows=len(rows), calibration=calibrate(rows),
                photo_vs_caliper=photo_vs_caliper(rows, PRINTS / 'capture_log.csv'))


@router.get('/physical/page/{name}')
def physical_page(name: str):
    if name not in PHYSICAL_PAGES:
        raise HTTPException(404, 'unknown page')
    return FileResponse(ROOT / 'web' / f'{name}.html', media_type='text/html')
