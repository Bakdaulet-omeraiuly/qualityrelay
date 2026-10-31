#!/usr/bin/env python
"""Train / evaluate / export the STFPM anomaly detector and write a Resource-ledger manifest.

Examples
  # local smoke test (Mac/CPU), SIMULATED tier
  python scripts/train_anomaly.py --data synthetic-cad --epochs 3 --size 96 --n-train 64

  # Brev L4/A100, MVTec category (download MVTec AD yourself, CC BY-NC-SA), EXTERNAL_DATASET tier
  python scripts/train_anomaly.py --data mvtec --root /data/mvtec/screw --epochs 100 --size 256 \
      --provider brev --instance-type "L4 x1" --price-per-hour 0.70

  # our own prints, PHYSICAL_CAPTURE tier (folders good/ and defect/)
  python scripts/train_anomaly.py --data captured --root data/prints --epochs 100 --size 256
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17.anomaly import run, TrainConfig  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', choices=('synthetic-cad', 'mvtec', 'captured'), required=True)
    ap.add_argument('--root', help='dataset folder for mvtec/captured (or STL dir override for synthetic-cad)')
    ap.add_argument('--out', default=str(ROOT / 'runs' / 'anomaly'))
    ap.add_argument('--epochs', type=int, default=20)
    ap.add_argument('--batch-size', type=int, default=16)
    ap.add_argument('--lr', type=float, default=0.4)
    ap.add_argument('--size', type=int, default=128)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--n-train', type=int, default=200, help='synthetic-cad only')
    ap.add_argument('--n-test-good', type=int, default=50, help='synthetic-cad only')
    ap.add_argument('--n-test-defect', type=int, default=50, help='synthetic-cad only')
    ap.add_argument('--device', help='cuda | mps | cpu (default: auto)')
    ap.add_argument('--no-pretrained', action='store_true', help='random teacher (smoke tests only; result is meaningless)')
    ap.add_argument('--no-export', action='store_true')
    ap.add_argument('--provider', default='local', help='brev | nebius | local | ...')
    ap.add_argument('--instance-type', default='UNKNOWN')
    ap.add_argument('--price-per-hour', type=float, help='USD/h from the provider console; needed for total_spend')
    a = ap.parse_args(argv)
    cfg = TrainConfig(epochs=a.epochs, batch_size=a.batch_size, lr=a.lr, pretrained=not a.no_pretrained, device=a.device, seed=a.seed)
    run_dir, manifest = run(a.data, root=a.root, out_dir=a.out, cfg=cfg, size=a.size, seed=a.seed, n_train=a.n_train,
                            n_test_good=a.n_test_good, n_test_defect=a.n_test_defect, provider=a.provider,
                            instance_type=a.instance_type, price_per_hour=a.price_per_hour, export=not a.no_export)
    print(f'run dir: {run_dir}')
    print(f'tier: {manifest["source_origin"]}  GPU: {manifest["GPU_model"]}  image AUROC: {manifest["metrics"]["image_auroc"]:.4f}  export: '
          + ', '.join(f'{k}={"ok" if v.get("ok") else "FAILED"}' for k, v in manifest['export'].items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
