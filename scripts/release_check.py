#!/usr/bin/env python
"""REL-01: regenerate and verify the 18.1 release records.

  python scripts/release_check.py validate   # regenerate schemas/openapi_demo.json, run pytest, write RELEASE_VALIDATION.json
  python scripts/release_check.py manifest   # regenerate FILE_SHA256_MANIFEST.json
  python scripts/release_check.py verify     # check every packaged file against FILE_SHA256_MANIFEST.json
  python scripts/release_check.py all        # validate -> manifest -> verify (use after the final commit)

Exit: 0 ok, 1 tests failed or manifest does not verify.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17 import release  # noqa: E402


def validate() -> bool:
    release.write_openapi_snapshot()  # before pytest, so the run covers the snapshot it ships with
    v = release.build_validation()
    release.write_json(release.VALIDATION, v)
    print(f"{release.VALIDATION}: release {v['release']} @ {v['git_commit'][:12]}"
          f"{' (dirty: %d paths)' % v['uncommitted_paths'] if v['working_tree_dirty'] else ''} -- {v['pytest_result']}")
    return v['pytest_passed']


def manifest() -> bool:
    m =release.build_manifest()
    release.write_json(release.MANIFEST, m)
    print(f'{release.MANIFEST}: {len(m)} files')
    return True


def verify() -> bool:
    r = release.verify_manifest()
    for k in ('mismatched', 'missing', 'unlisted'):
        for p in r[k]:
            print(f'{k.upper():10} {p}')
    print(f"verify: {'OK' if r['ok'] else 'FAILED'} ({r['checked']} listed)")
    return r['ok']


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['validate', 'manifest', 'verify', 'all'])
    step = ap.parse_args(argv).step
    steps = {'validate': [validate], 'manifest': [manifest], 'verify': [verify],
             'all': [validate, manifest, verify]}[step]
    ok = all([s() for s in steps])  # run every step even if tests fail, so the record is written
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
