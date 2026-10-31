"""Generate per-station HMAC signing secrets into a git-ignored .env file.

Usage (from the repo root):
    python scripts/provision_station_keys.py                 # slot tab sorter
    python scripts/provision_station_keys.py --stations slot tab sorter phone pi cad
    python scripts/provision_station_keys.py --rotate        # replace keys that already exist

Writes <STATION>_STATION_KEY=<64 hex chars> lines into .env (created from .env.example if
absent), leaving every other line untouched. Existing non-empty keys are kept unless
--rotate is given. Key values are never printed; share them out-of-band, never in git.
qualityrelay17/api.py reads these at import time (see load_station_keys)."""
from __future__ import annotations
import argparse, re, secrets, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from qualityrelay17.api import STATION_KEY_ENV  # noqa: E402  station id -> env var name


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--stations', nargs='+', default=['slot', 'tab', 'sorter'], choices=sorted(STATION_KEY_ENV))
    ap.add_argument('--env-file', type=Path, default=ROOT / '.env')
    ap.add_argument('--rotate', action='store_true', help='replace keys that are already set')
    a = ap.parse_args()

    if a.env_file.exists():
        lines = a.env_file.read_text(encoding='utf-8').splitlines()
    else:
        example = ROOT / '.env.example'
        lines = example.read_text(encoding='utf-8').splitlines() if example.exists() else []

    written, kept = [], []
    for station in a.stations:
        var = STATION_KEY_ENV[station]
        pat = re.compile(rf'^\s*{re.escape(var)}\s*=\s*(.*)$')
        idx = next((i for i, l in enumerate(lines) if pat.match(l)), None)
        current = pat.match(lines[idx]).group(1).strip() if idx is not None else ''
        if current and not a.rotate:
            kept.append(station)
            continue
        new_line = f'{var}={secrets.token_hex(32)}'
        if idx is None:
            lines.append(new_line)
        else:
            lines[idx] = new_line
        written.append(station)

    a.env_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'env file: {a.env_file}')
    if written:
        print('generated:', ' '.join(written))
    if kept:
        print('kept existing (use --rotate to replace):', ' '.join(kept))
    print('reminder: .env is git-ignored; never paste these values into chat, docs, or firmware.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
