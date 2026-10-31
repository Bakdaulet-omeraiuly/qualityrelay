#!/usr/bin/env python
"""NVIDIA Warp rare-event Monte Carlo over the Gate-A S01..S08 generator settings.

  python scripts/run_warp_mc.py --device cpu  --parts 10000000      # any machine
  python scripts/run_warp_mc.py --device cuda --parts 1000000000    # NVIDIA GPU (Brev L4)

Writes examples/results/warp_mc/<device-tag>/: S0x.json, summary.csv, manifest.json.
Everything is SIMULATED. Decisions are proven identical to the CPU code by tests/test_warp_mc.py.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, platform, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import warp as wp  # noqa: E402
from qualityrelay17.gpu.warp_mc import run_mc, make_params, GRID, POLICY_NAMES  # noqa: E402


def _git(*a):
    try:
        return subprocess.check_output(['git', *a], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return 'UNKNOWN'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--parts', type=int, default=10_000_000)
    ap.add_argument('--lots', type=int, default=100)
    ap.add_argument('--seed', type=int, default=2026)
    ap.add_argument('--tag', default=None)
    a = ap.parse_args()
    wp.init()
    dev = wp.get_device(a.device)
    tag = a.tag or ('cpu' if dev.is_cpu else dev.name.replace(' ', '_'))
    out = ROOT / 'examples' / 'results' / 'warp_mc' / tag
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    started = time.time()
    for sc in GRID:
        P = make_params(sc)
        run_mc(sc, 10_000, lots=10, device=dev, P=P)  # warm-up: kernel compile/load excluded from timing
        res = run_mc(sc, a.parts, lots=a.lots, seed=a.seed, device=dev, P=P)
        (out / f'{sc.sid}.json').write_text(json.dumps(res, indent=1, sort_keys=True))
        for name in POLICY_NAMES:
            p = res['policies'][name]
            pr = res['paired_vs_B0'].get(name, {}).get('unsafe_pass_rate', {})
            rows.append(dict(scenario=sc.sid, title=sc.title, policy=name, parts=res['parts'],
                             unsafe_per_1000=round(1000 * p['unsafe_pass_rate'], 4),
                             unsafe_wilson95_per_1000=[round(1000 * x, 4) for x in p['unsafe_pass_wilson95']],
                             released_good=round(p['released_good_rate'], 5), hold=round(p['hold_rate'], 5),
                             diff_vs_B0_per_1000=round(1000 * pr['diff'], 4) if pr else '',
                             diff_ci95_per_1000=[round(1000 * x, 4) for x in pr['ci95']] if pr else '',
                             parts_per_second=res['parts_per_second']))
        print(sc.sid, res['parts'], f"{res['kernel_seconds']:.2f}s", f"{res['parts_per_second']:,}/s", flush=True)
    with open(out / 'summary.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    code = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ('qualityrelay17/gpu/warp_mc.py', 'scripts/run_warp_mc.py')}
    (out / 'manifest.json').write_text(json.dumps(dict(
        origin='SIMULATED', engine='nvidia-warp', warp_version=wp.config.version, device=str(dev), device_name=dev.name,
        is_cuda=dev.is_cuda, parts_per_scenario=a.parts, lots=a.lots, seed=a.seed,
        git_commit=_git('rev-parse', 'HEAD'), host=platform.node(), python=platform.python_version(),
        started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)), runtime_s=round(time.time() - started, 1),
        code_sha256=code, equivalence_tests='tests/test_warp_mc.py'), indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
