#!/usr/bin/env python
"""LLM-01: verify the team's Nebius Token Factory entitlement and one model's text + tool-call roundtrip.

  python scripts/verify_nebius_entitlement.py                       # list models only (free), record entitlement
  python scripts/verify_nebius_entitlement.py --confirm-spend       # + text and tool-call roundtrip, first listed candidate
  python scripts/verify_nebius_entitlement.py --confirm-spend --all-candidates
  python scripts/verify_nebius_entitlement.py --confirm-spend --model zai-org/GLM-5.3-Flash

Key from the environment or the git-ignored .env (NEBIUS_API_KEY); NEBIUS_MODEL is used as --model if set.
A full check is 3 chat calls per model at max_tokens=512 each. Writes a redacted manifest to
examples/results/llm_01_entitlement/nebius_<UTC>.json (the key itself is never written or printed).
Exit: 0 VERIFIED, 3 NOT_CONFIGURED, 4 MODELS_LISTED_ONLY, 2 anything else.
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17.api import read_dotenv  # noqa: E402
from qualityrelay17.llm_entitlement import verify_entitlement, write_manifest, MANIFEST_DIR  # noqa: E402

EXIT = {'VERIFIED': 0, 'NOT_CONFIGURED': 3, 'MODELS_LISTED_ONLY': 4}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--model', help='model id to test (default: NEBIUS_MODEL, else first listed candidate)')
    ap.add_argument('--all-candidates', action='store_true', help='test every listed candidate model')
    ap.add_argument('--confirm-spend', action='store_true', help='allow the paid chat roundtrips')
    ap.add_argument('--out-dir', type=Path, default=MANIFEST_DIR)
    a = ap.parse_args(argv)
    env = {**read_dotenv(), **{k: v for k, v in os.environ.items() if v}}
    model = a.model or (None if a.all_candidates else (env.get('NEBIUS_MODEL') or '').strip() or None)
    m = verify_entitlement(key=(env.get('NEBIUS_API_KEY') or '').strip(), model=model,
                           all_candidates=a.all_candidates, confirm_spend=a.confirm_spend)
    path = write_manifest(m, a.out_dir)
    print(f"verdict: {m['verdict']}")
    if 'candidate_entitlement' in m:
        for c, ok in m['candidate_entitlement'].items(): print(f"  {'listed    ' if ok else 'NOT listed'}  {c}")
        print(f"  ({m['models_endpoint']['count']} models listed for this key)")
    for t, r in m.get('tested', {}).items():
        print(f"  {t}: text={'ok' if r['text'].get('ok') else 'FAIL'} tool_call={'ok' if r['tool_call_valid'] else 'FAIL'} "
              f"tokens={r['total_tokens']} problems={r['tool_call'].get('problems') or r['tool_call'].get('error') or []}")
    if m.get('detail'): print(f"  {m['detail']}")
    if m.get('models_endpoint', {}).get('error'): print(f"  {m['models_endpoint']['error']}")
    print(f'manifest: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}')
    return EXIT.get(m['verdict'], 2)


if __name__ == '__main__':
    sys.exit(main())
