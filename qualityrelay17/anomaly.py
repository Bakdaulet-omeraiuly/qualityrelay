"""Anomaly-detection reference pipeline (Bakdaulet, 31 Oct) — STFPM student–teacher.

Student–Teacher Feature Pyramid Matching (Wang et al., BMVC 2021): a frozen ImageNet
ResNet-18 "teacher" and a trainable ResNet-18 "student" see only GOOD images; the student
learns to reproduce the teacher's multi-scale features; at test time the feature discrepancy
is the anomaly map. Chosen over PatchCore because it exports as two plain CNNs to ONNX — the
only form Hailo-8L can compile — whereas a kNN memory bank cannot.

Three data sources, three honesty tiers (never promote one into another):
  synthetic-cad -> SIMULATED          silhouettes rendered from our own STLs + synthetic defects
  mvtec         -> EXTERNAL_DATASET   MVTec AD category folder (user downloads; CC BY-NC-SA)
  captured      -> PHYSICAL_CAPTURE   our printed parts, good/ and defect/ folders

Everything a run needs to be audited goes into run_manifest.json in the Resource-ledger
format of docs/engineering/GPU_AND_SPONSOR_EXECUTION_PLAN.md. A missing GPU is recorded,
never faked. Heavy deps (torch, torchvision) are imported lazily so the rest of the package
keeps working without them.
"""
from __future__ import annotations
import hashlib, json, platform, random, subprocess, sys, time
from dataclasses import dataclass, asdict, field
from pathlib import Path
import numpy as np

TIERS = {'synthetic-cad': 'SIMULATED', 'mvtec': 'EXTERNAL_DATASET', 'captured': 'PHYSICAL_CAPTURE'}
LEDGER_FIELDS = ('run_id', 'provider', 'instance_type', 'GPU_model', 'gpu_count', 'driver', 'CUDA', 'docker_digest',
                 'tool_version', 'price_per_hour', 'start', 'end', 'total_spend', 'dataset_hash', 'model_hash', 'seed',
                 'git_commit', 'source_origin')
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# ----------------------------------------------------------------------------- data

def _augment_good(mask255, rng, size):
    """Mild pose/illumination variation of a GOOD silhouette: what a real camera would see of a
    conforming part. Returns uint8 HxW."""
    import cv2
    h, w = mask255.shape
    angle = rng.uniform(-10, 10); scale = rng.uniform(0.9, 1.1)
    tx, ty = rng.uniform(-0.04, 0.04) * w, rng.uniform(-0.04, 0.04) * h
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale); M[:, 2] += (tx, ty)
    img = cv2.warpAffine(mask255, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    fg, bg = rng.uniform(150, 230), rng.uniform(20, 70)
    img = np.where(img > 127, fg, bg).astype(np.float32)
    # illumination ramp + sensor noise + optical blur
    ramp = np.linspace(rng.uniform(-25, 25), rng.uniform(-25, 25), w, dtype=np.float32)[None, :]
    img = img + ramp + rng.normal(0, rng.uniform(2, 8), img.shape).astype(np.float32)
    k = int(rng.choice([1, 3, 5]))
    if k > 1:
        img = cv2.GaussianBlur(img, (k, k), 0)
    img = np.clip(img, 0, 255).astype(np.uint8)
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)


def _inject_defect(mask255, rng, kind):
    """Return (defective_mask255, defect_mask01) at render resolution. Defect geometry is
    synthetic and illustrative — it does not model PLA print physics."""
    import cv2
    h, w = mask255.shape
    out = mask255.copy()
    ys, xs = np.nonzero(mask255 > 127)
    if len(xs) == 0:
        raise ValueError('empty silhouette')
    if kind == 'chip':  # material missing at the boundary
        i = rng.integers(len(xs)); cx, cy = int(xs[i]), int(ys[i])
        axes = (int(rng.integers(w // 40, w // 12)), int(rng.integers(h // 40, h // 12)))
        cv2.ellipse(out, (cx, cy), axes, float(rng.uniform(0, 180)), 0, 360, 0, -1)
    elif kind == 'hole':  # material missing inside
        cx, cy = int(np.median(xs) + rng.uniform(-0.2, 0.2) * np.ptp(xs)), int(np.median(ys) + rng.uniform(-0.2, 0.2) * np.ptp(ys))
        r = int(rng.integers(w // 50, w // 16))
        cv2.circle(out, (cx, cy), r, 0, -1)
    elif kind == 'stringing':  # thin extra filament threads
        for _ in range(int(rng.integers(2, 6))):
            p1 = (int(rng.integers(xs.min(), xs.max())), int(rng.integers(ys.min(), ys.max())))
            p2 = (int(np.clip(p1[0] + rng.integers(-w // 4, w // 4), 0, w - 1)), int(np.clip(p1[1] + rng.integers(-h // 4, h // 4), 0, h - 1)))
            cv2.line(out, p1, p2, 255, int(rng.integers(1, 3)))
    elif kind == 'warp':  # strong shear the good-augmentation never applies
        shear = rng.choice([-1, 1]) * rng.uniform(0.18, 0.3)
        M = np.float32([[1, shear, -shear * h / 2], [0, 1, 0]])
        out = cv2.warpAffine(mask255, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    else:
        raise ValueError(f'unknown defect kind {kind}')
    defect = ((out > 127) != (mask255 > 127)).astype(np.uint8)
    return out, defect


def synthetic_cad_dataset(stl_dir, *, n_train=200, n_test_good=50, n_test_defect=50, size=128, seed=0,
                          render_px=256, good_patterns=('nominal', 'good')):
    """Render our own STL specimens to silhouettes and build a SIMULATED anomaly set.
    Returns dict with uint8 arrays: train [N,S,S], test [M,S,S], labels [M] (1 = defect),
    masks [M,S,S], and defect_types list. Deterministic for a given seed."""
    import cv2
    from .vision import cad_projection_from_stl
    stl_dir = Path(stl_dir)
    files = sorted(p for p in stl_dir.glob('*.stl') if any(g in p.stem for g in good_patterns))
    if not files:
        raise FileNotFoundError(f'no good/nominal STL files in {stl_dir}')
    base = [cad_projection_from_stl(str(p), pixels=render_px) for p in files]
    rng = np.random.default_rng(seed)
    kinds = ('chip', 'hole', 'stringing', 'warp')
    train = np.stack([_augment_good(base[rng.integers(len(base))], rng, size) for _ in range(n_train)])
    test, labels, masks, types = [], [], [], []
    for _ in range(n_test_good):
        test.append(_augment_good(base[rng.integers(len(base))], rng, size)); labels.append(0)
        masks.append(np.zeros((size, size), np.uint8)); types.append('good')
    for j in range(n_test_defect):
        kind = kinds[j % len(kinds)]
        defective, dmask = _inject_defect(base[rng.integers(len(base))], rng, kind)
        # Apply the SAME augmentation parameters to image and mask by reseeding a child generator.
        child = np.random.default_rng(rng.integers(2**32))
        img = _augment_good(defective, child, size)
        child2 = np.random.default_rng(child.bit_generator.state['state']['state'] % (2**32))  # distinct stream for mask warp
        m = cv2.resize(dmask * 255, (size, size), interpolation=cv2.INTER_NEAREST)
        test.append(img); labels.append(1); masks.append((m > 127).astype(np.uint8)); types.append(kind)
        del child2
    return {'train': train, 'test': np.stack(test), 'labels': np.array(labels, np.int64), 'masks': np.stack(masks),
            'defect_types': types, 'source_files': [p.name for p in files], 'size': size}


def folder_dataset(root, *, size=128, limit=None):
    """MVTec-AD category layout (train/good, test/<kind>, ground_truth/<kind>) or our captured
    layout (good/, defect/). Grayscale, resized. Returns the same dict as synthetic_cad_dataset."""
    import cv2
    root = Path(root)
    def load(p):
        im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if im is None:
            raise ValueError(f'unreadable image {p}')
        return cv2.resize(im, (size, size), interpolation=cv2.INTER_AREA)
    exts = ('*.png', '*.jpg', '*.jpeg', '*.bmp')
    def imgs(d):
        return sorted(p for e in exts for p in Path(d).glob(e))[:limit]
    if (root / 'train' / 'good').is_dir():  # MVTec
        train = [load(p) for p in imgs(root / 'train' / 'good')]
        test, labels, masks, types = [], [], [], []
        for kind_dir in sorted((root / 'test').iterdir()):
            for p in imgs(kind_dir):
                test.append(load(p)); is_def = kind_dir.name != 'good'
                labels.append(int(is_def)); types.append(kind_dir.name)
                gt = root / 'ground_truth' / kind_dir.name / (p.stem + '_mask.png')
                masks.append((load(gt) > 127).astype(np.uint8) if is_def and gt.exists() else np.zeros((size, size), np.uint8))
    elif (root / 'good').is_dir():  # captured
        good = [load(p) for p in imgs(root / 'good')]
        if len(good) < 4:
            raise ValueError('need at least 4 good captures')
        n_tr = max(2, int(0.7 * len(good)))
        train, test = good[:n_tr], good[n_tr:]
        labels = [0] * len(test); types = ['good'] * len(test)
        for p in imgs(root / 'defect') if (root / 'defect').is_dir() else []:
            test.append(load(p)); labels.append(1); types.append('defect')
        masks = [np.zeros((size, size), np.uint8) for _ in test]
    else:
        raise FileNotFoundError(f'{root}: expected MVTec layout (train/good, test/...) or captured layout (good/, defect/)')
    if not test:
        raise ValueError('empty test set')
    return {'train': np.stack(train), 'test': np.stack(test), 'labels': np.array(labels, np.int64),
            'masks': np.stack(masks), 'defect_types': types, 'source_files': [str(root)], 'size': size}


def dataset_hash(ds) -> str:
    h = hashlib.sha256()
    for k in ('train', 'test', 'labels', 'masks'):
        h.update(np.ascontiguousarray(ds[k]).tobytes())
    return 'sha256:' + h.hexdigest()[:16]


# ----------------------------------------------------------------------------- metrics

def auroc(scores, labels) -> float:
    """Rank-based (Mann–Whitney) image-level AUROC; no sklearn dependency. Ties averaged."""
    scores = np.asarray(scores, float); labels = np.asarray(labels, int)
    pos, neg = scores[labels == 1], scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        raise ValueError('AUROC needs both classes')
    order = np.argsort(scores, kind='mergesort'); ranks = np.empty(len(scores), float)
    sorted_scores = scores[order]; i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[labels == 1].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


# ----------------------------------------------------------------------------- model

def _device(prefer=None):
    import torch
    if prefer:
        return torch.device(prefer)
    if torch.cuda.is_available():
        return torch.device('cuda')
    if getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available():
        return torch.device('mps')
    return torch.device('cpu')


def _to_tensor(batch_u8):
    import torch
    x = batch_u8.astype(np.float32) / 255.0
    x = np.repeat(x[:, None, :, :], 3, axis=1)
    x = (x - IMAGENET_MEAN[None, :, None, None]) / IMAGENET_STD[None, :, None, None]
    return torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32))


def build_resnet18_pyramid(pretrained: bool):
    """ResNet-18 trunk returning layer1..layer3 feature maps (STFPM's pyramid)."""
    import torch.nn as nn, torchvision
    weights = torchvision.models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
    net = torchvision.models.resnet18(weights=weights)

    class Pyramid(nn.Module):
        def __init__(self, r):
            super().__init__()
            self.stem = nn.Sequential(r.conv1, r.bn1, r.relu, r.maxpool)
            self.layer1, self.layer2, self.layer3 = r.layer1, r.layer2, r.layer3
        def forward(self, x):
            x = self.stem(x); f1 = self.layer1(x); f2 = self.layer2(f1); f3 = self.layer3(f2)
            return [f1, f2, f3]
    return Pyramid(net)


def _feature_loss(t_feats, s_feats):
    import torch.nn.functional as F
    loss = 0.0
    for t, s in zip(t_feats, s_feats):
        loss = loss + 0.5 * ((F.normalize(t, dim=1) - F.normalize(s, dim=1)) ** 2).sum(1).mean()
    return loss


def anomaly_maps(teacher, student, x, out_size):
    """Per-pixel discrepancy summed over pyramid levels, upsampled to out_size. [B,H,W] numpy."""
    import torch, torch.nn.functional as F
    with torch.no_grad():
        tf, sf = teacher(x), student(x)
        total = torch.zeros(x.shape[0], 1, out_size, out_size, device=x.device)
        for t, s in zip(tf, sf):
            d = 0.5 * ((F.normalize(t, dim=1) - F.normalize(s, dim=1)) ** 2).sum(1, keepdim=True)
            total = total + F.interpolate(d, size=(out_size, out_size), mode='bilinear', align_corners=False)
    return total[:, 0].cpu().numpy()


@dataclass
class TrainConfig:
    epochs: int = 20
    batch_size: int = 16
    lr: float = 0.4
    momentum: float = 0.9
    weight_decay: float = 1e-4
    pretrained: bool = True
    device: str | None = None
    seed: int = 0
    gaussian_sigma: float = 4.0


def train_stfpm(ds, cfg: TrainConfig, *, log=print):
    """Train student on ds['train'] (good only). Returns (teacher, student, history)."""
    import torch, torch.optim as optim
    torch.manual_seed(cfg.seed); random.seed(cfg.seed); np.random.seed(cfg.seed)
    dev = _device(cfg.device)
    teacher = build_resnet18_pyramid(cfg.pretrained).to(dev).eval()
    for p in teacher.parameters():
        p.requires_grad_(False)
    student = build_resnet18_pyramid(False).to(dev).train()
    opt = optim.SGD(student.parameters(), lr=cfg.lr, momentum=cfg.momentum, weight_decay=cfg.weight_decay)
    X = ds['train']; n = len(X); history = []
    g = np.random.default_rng(cfg.seed)
    for ep in range(cfg.epochs):
        perm = g.permutation(n); running = 0.0; steps = 0
        for i in range(0, n, cfg.batch_size):
            xb = _to_tensor(X[perm[i:i + cfg.batch_size]]).to(dev)
            with torch.no_grad():
                tf = teacher(xb)
            loss = _feature_loss(tf, student(xb))
            opt.zero_grad(); loss.backward(); opt.step()
            running += loss.detach().item(); steps += 1
        history.append({'epoch': ep + 1, 'loss': running / max(1, steps)})
        log(f'epoch {ep + 1}/{cfg.epochs} loss {running / max(1, steps):.5f}')
    student.eval()
    return teacher, student, history


def evaluate(teacher, student, ds, cfg: TrainConfig):
    """Image-level AUROC (max of smoothed map) and pixel-level AUROC where masks exist."""
    import cv2, torch
    dev = _device(cfg.device); size = ds['size']
    maps = []
    with torch.no_grad():
        for i in range(0, len(ds['test']), cfg.batch_size):
            xb = _to_tensor(ds['test'][i:i + cfg.batch_size]).to(dev)
            maps.append(anomaly_maps(teacher, student, xb, size))
    maps = np.concatenate(maps)
    if cfg.gaussian_sigma > 0:
        maps = np.stack([cv2.GaussianBlur(m, (0, 0), cfg.gaussian_sigma) for m in maps])
    image_scores = maps.reshape(len(maps), -1).max(1)
    out = {'image_auroc': auroc(image_scores, ds['labels']), 'n_test': int(len(maps)),
           'n_defect': int(ds['labels'].sum()), 'score_good_mean': float(image_scores[ds['labels'] == 0].mean()),
           'score_defect_mean': float(image_scores[ds['labels'] == 1].mean()) if ds['labels'].any() else None}
    has_masks = ds['masks'][ds['labels'] == 1].sum() > 0
    if has_masks:
        sub = np.random.default_rng(0).choice(maps.size, size=min(maps.size, 200_000), replace=False)
        out['pixel_auroc'] = auroc(maps.reshape(-1)[sub], ds['masks'].reshape(-1)[sub])
    per_type = {}
    for t in sorted(set(ds['defect_types'])):
        idx = [i for i, k in enumerate(ds['defect_types']) if k == t]
        per_type[t] = {'n': len(idx), 'score_mean': float(image_scores[idx].mean())}
    out['per_type'] = per_type
    return out, image_scores, maps


def export_onnx(teacher, student, size, out_dir: Path, device=None):
    """Two plain CNNs -> ONNX (opset 17, static [1,3,S,S]) for the Hailo Dataflow Compiler.
    Returns status dict; failure is recorded, not hidden."""
    import copy, torch
    out_dir = Path(out_dir); status = {}
    dummy = torch.zeros(1, 3, size, size)  # export always from a CPU copy: MPS/CUDA tensors are not traceable here
    for name, net in (('teacher', teacher), ('student', student)):
        path = out_dir / f'{name}.onnx'
        try:
            cpu_net = copy.deepcopy(net).cpu().eval()
            try:
                torch.onnx.export(cpu_net, dummy, str(path), opset_version=17, input_names=['image'],
                                  output_names=['f1', 'f2', 'f3'], dynamo=False)
            except TypeError:  # older torch without the dynamo kwarg
                torch.onnx.export(cpu_net, dummy, str(path), opset_version=17, input_names=['image'], output_names=['f1', 'f2', 'f3'])
            status[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()[:16], 'ok': True}
        except Exception as e:  # noqa: BLE001
            status[name] = {'path': str(path), 'ok': False, 'error': f'{type(e).__name__}: {e}'[:300]}
    return status


# ----------------------------------------------------------------------------- manifest

def _git(*args):
    try:
        return subprocess.check_output(['git', *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return 'UNKNOWN'


def gpu_info():
    info = {'GPU_model': 'NONE', 'gpu_count': 0, 'driver': 'UNKNOWN', 'CUDA': 'UNKNOWN', 'device_used': 'cpu'}
    try:
        import torch
        if torch.cuda.is_available():
            info.update(GPU_model=torch.cuda.get_device_name(0), gpu_count=torch.cuda.device_count(),
                        CUDA=str(torch.version.cuda), device_used='cuda')
        elif getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available():
            info.update(GPU_model='Apple MPS (not an NVIDIA GPU)', gpu_count=1, device_used='mps')
        info['torch'] = torch.__version__
    except Exception:  # noqa: BLE001
        pass
    try:
        drv = subprocess.check_output(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'], text=True, stderr=subprocess.DEVNULL)
        info['driver'] = drv.strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        pass
    return info


def build_manifest(*, run_id, data_source, ds, cfg: TrainConfig, metrics, export_status, start, end,
                   provider='local', instance_type='UNKNOWN', price_per_hour=None, docker_digest='none', extra=None):
    hours = (end - start) / 3600.0
    g = gpu_info()
    try:  # what was actually used, not merely what the machine offers
        g['device_used'] = str(_device(cfg.device))
    except Exception:  # noqa: BLE001
        pass
    model_hash = ','.join(v.get('sha256', 'FAILED') for v in export_status.values()) if export_status else 'NOT_EXPORTED'
    m = {
        'run_id': run_id, 'provider': provider, 'instance_type': instance_type,
        'GPU_model': g['GPU_model'], 'gpu_count': g['gpu_count'], 'driver': g['driver'], 'CUDA': g['CUDA'],
        'docker_digest': docker_digest, 'tool_version': f"python {sys.version.split()[0]}; torch {g.get('torch', 'UNKNOWN')}",
        'price_per_hour': price_per_hour,
        'start': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start)), 'end': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(end)),
        'total_spend': round(hours * price_per_hour, 4) if price_per_hour is not None else 'UNKNOWN (price_per_hour not given)',
        'dataset_hash': dataset_hash(ds), 'model_hash': model_hash, 'seed': cfg.seed, 'git_commit': _git('rev-parse', 'HEAD'),
        'source_origin': TIERS[data_source],
        # beyond the ledger minimum:
        'data_source': data_source, 'source_files': ds['source_files'], 'n_train': int(len(ds['train'])),
        'n_test': int(len(ds['test'])), 'image_size': ds['size'], 'method': 'STFPM resnet18 layer1-3',
        'config': asdict(cfg), 'device_used': g['device_used'], 'elapsed_s': round(end - start, 1),
        'metrics': metrics, 'export': export_status, 'platform': platform.platform(),
        'claim_boundary': 'Reference anomaly detector on the stated data source only. Not validated on any physical '
                          'QualityRelay specimen unless source_origin == PHYSICAL_CAPTURE with independent labels.',
    }
    if extra:
        m.update(extra)
    missing = [k for k in LEDGER_FIELDS if k not in m]
    if missing:
        raise RuntimeError(f'manifest missing ledger fields {missing}')
    return m


def run(data_source, *, root=None, out_dir='runs/anomaly', cfg: TrainConfig | None = None, size=128, seed=0,
        n_train=200, n_test_good=50, n_test_defect=50, provider='local', instance_type='UNKNOWN',
        price_per_hour=None, export=True, log=print):
    """End-to-end: data -> train -> evaluate -> export -> manifest. Returns (run_dir, manifest)."""
    cfg = cfg or TrainConfig(seed=seed)
    start = time.time()
    run_id = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(start)) + f'-{data_source}-s{cfg.seed}'
    run_dir = Path(out_dir) / run_id; run_dir.mkdir(parents=True, exist_ok=True)
    if data_source == 'synthetic-cad':
        ds = synthetic_cad_dataset(root or Path(__file__).resolve().parents[1] / 'examples' / 'cad' / 'stl',
                                   n_train=n_train, n_test_good=n_test_good, n_test_defect=n_test_defect, size=size, seed=seed)
    elif data_source in ('mvtec', 'captured'):
        if not root:
            raise ValueError(f'{data_source} needs --root')
        ds = folder_dataset(root, size=size)
    else:
        raise ValueError(f'unknown data source {data_source}')
    log(f'[{run_id}] {data_source}: train {len(ds["train"])}, test {len(ds["test"])} ({int(ds["labels"].sum())} defect), size {size}, tier {TIERS[data_source]}')
    teacher, student, history = train_stfpm(ds, cfg, log=log)
    metrics, scores, maps = evaluate(teacher, student, ds, cfg)
    metrics['history'] = history
    log(f'image AUROC {metrics["image_auroc"]:.4f}' + (f', pixel AUROC {metrics["pixel_auroc"]:.4f}' if 'pixel_auroc' in metrics else ''))
    export_status = export_onnx(teacher, student, size, run_dir, cfg.device) if export else {}
    import torch
    torch.save(student.state_dict(), run_dir / 'student.pt')
    np.save(run_dir / 'test_scores.npy', scores)
    end = time.time()
    manifest = build_manifest(run_id=run_id, data_source=data_source, ds=ds, cfg=cfg, metrics=metrics, export_status=export_status,
                              start=start, end=end, provider=provider, instance_type=instance_type, price_per_hour=price_per_hour)
    (run_dir / 'run_manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True, default=str))
    (run_dir / 'metrics.json').write_text(json.dumps(metrics, indent=1, default=str))
    return run_dir, manifest
