"""REL-02 schema gate: every JSON Schema in schemas/ is valid against its declared metaschema,
and schemas/openapi_demo.json is exactly what the current API generates (no contract drift).

  python scripts/check_schemas.py          # exit 1 on any problem
  python scripts/check_schemas.py --fix    # regenerate the OpenAPI snapshot, then check
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema.validators import validator_for  # noqa: E402
from jsonschema.exceptions import SchemaError  # noqa: E402

from qualityrelay17 import release  # noqa: E402


def check_json_schemas(root=ROOT) -> list[str]:
    problems = []
    paths = sorted((root / 'schemas').glob('*.schema.json'))
    if not paths:
        problems.append('no *.schema.json files found in schemas/')
    for p in paths:
        rel = p.relative_to(root).as_posix()
        try:
            schema = json.loads(p.read_text(encoding='utf-8'))
        except ValueError as ex:
            problems.append(f'{rel}: invalid JSON: {ex}'); continue
        if '$schema' not in schema:
            problems.append(f'{rel}: missing $schema (metaschema must be explicit)'); continue
        try:
            validator_for(schema).check_schema(schema)
        except SchemaError as ex:
            problems.append(f'{rel}: not a valid schema: {ex.message}')
    return problems


def check_openapi_snapshot(root=ROOT) -> list[str]:
    from qualityrelay17.api import app
    snap = root / release.OPENAPI_SNAPSHOT
    if not snap.exists():
        return [f'{release.OPENAPI_SNAPSHOT}: missing']
    if json.loads(snap.read_text(encoding='utf-8')) != app.openapi():
        return [f'{release.OPENAPI_SNAPSHOT}: stale; the API changed. Run `python scripts/check_schemas.py --fix` and commit it.']
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--fix', action='store_true', help='regenerate the OpenAPI snapshot before checking')
    if ap.parse_args(argv).fix:
        release.write_openapi_snapshot()
    problems = check_json_schemas() + check_openapi_snapshot()
    for p in problems:
        print(f'SCHEMA FAIL {p}')
    if not problems:
        print('schemas OK')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
