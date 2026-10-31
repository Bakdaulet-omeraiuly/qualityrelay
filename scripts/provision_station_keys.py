"""Generate per-station HMAC signing secrets into a git-ignored .env file.

Usage (from the repo root):
    python scripts/provision_station_keys.py                 # slot tab sorter
    python scripts/provision_station_keys.py --stations slot tab sorter phone pi cad
    python scripts/provision_station_keys.py --rotate        # replace keys that already exist

Writes two lines per station into .env (created from .env.example if absent), leaving every
other line untouched:
    <STATION>_STATION_KEY  server-only gateway identity that signs Evidence
    <STATION>_DEVICE_KEY   goes onto that station's ESP32; authenticates the request envelope
Existing non-empty keys are kept unless --rotate is given. Key values are never printed unless
you ask for exactly one device key to paste into firmware:
    python scripts/provision_station_keys.py --show-device-key sorter
Human operator bearer tokens (BACK-04; staging, arming, E-stop reset, ground-truth checks):
    python scripts/provision_station_keys.py --operators alice bob    # OPERATOR_ALICE_TOKEN, ...
    python scripts/provision_station_keys.py --show-operator-token alice
qualityrelay17/api.py reads these at import time (see load_station_keys / station_auth.py)."""
from __future__ import annotations
import argparse, re, secrets, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from qualityrelay17.api import STATION_KEY_ENV, DEVICE_KEY_ENV  # noqa: E402  station id -> env var name


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--stations', nargs='+', default=['slot', 'tab', 'sorter'], choices=sorted(STATION_KEY_ENV))
    ap.add_argument('--env-file', type=Path, default=ROOT / '.env')
    ap.add_argument('--rotate', action='store_true', help='replace keys that are already set')
    ap.add_argument('--show-device-key', metavar='STATION', choices=sorted(DEVICE_KEY_ENV),
                    help='print ONE device key value (for flashing); nothing else is written')
    ap.add_argument('--operators', nargs='+', default=[], metavar='NAME',
                    help='also generate OPERATOR_<NAME>_TOKEN bearer tokens (letters, digits, underscore)')
    ap.add_argument('--show-operator-token', metavar='NAME', help='print ONE operator token; nothing else is written')
    a = ap.parse_args()
    bad = [n for n in a.operators if not re.fullmatch(r'[A-Za-z0-9_]{1,32}', n)]
    if bad:
        ap.error(f'operator names must be letters/digits/underscore: {bad}')

    if a.show_operator_token:
        from qualityrelay17.api import read_dotenv
        var = f'OPERATOR_{a.show_operator_token.upper()}_TOKEN'
        val = read_dotenv(a.env_file).get(var, '')
        if not val:
            print(f'{var} not set in {a.env_file}; run with --operators {a.show_operator_token} first', file=sys.stderr)
            return 1
        print(val)
        return 0

    if a.show_device_key:
        from qualityrelay17.api import read_dotenv
        val = read_dotenv(a.env_file).get(DEVICE_KEY_ENV[a.show_device_key], '')
        if not val:
            print(f'{DEVICE_KEY_ENV[a.show_device_key]} not set in {a.env_file}; run without --show-device-key first', file=sys.stderr)
            return 1
        print(val)
        return 0

    if a.env_file.exists():
        lines = a.env_file.read_text(encoding='utf-8').splitlines()
    else:
        example = ROOT / '.env.example'
        lines = example.read_text(encoding='utf-8').splitlines() if example.exists() else []

    written, kept = [], []
    targets = [v for st in a.stations for v in (STATION_KEY_ENV[st], DEVICE_KEY_ENV[st])]
    targets += [f'OPERATOR_{n.upper()}_TOKEN' for n in a.operators]
    for var in targets:
        pat = re.compile(rf'^\s*{re.escape(var)}\s*=\s*(.*)$')
        idx = next((i for i, l in enumerate(lines) if pat.match(l)), None)
        current = pat.match(lines[idx]).group(1).strip() if idx is not None else ''
        if current and not a.rotate:
            kept.append(var)
            continue
        new_line = f'{var}={secrets.token_hex(32)}'
        if idx is None:
            lines.append(new_line)
        else:
            lines[idx] = new_line
        written.append(var)

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
