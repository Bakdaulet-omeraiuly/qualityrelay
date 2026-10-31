"""REL-02 safety review gate (runs in GitHub Actions as the `safety-review-gate` check).

If a pull request touches any path in .github/safety-paths.txt, it needs at least two APPROVED
reviews from distinct people other than the PR author, given on the PR's current head commit,
and no outstanding CHANGES_REQUESTED. Otherwise the check passes (the normal one-review branch
protection rule still applies). Approvals on an older commit do not count: a push after review
re-opens the gate.

Reads GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_EVENT_PATH (set by Actions). Standard library only.
  python scripts/review_gate.py
"""
from __future__ import annotations
import json, os, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFETY_PATHS_FILE = ROOT / '.github' / 'safety-paths.txt'
REQUIRED_APPROVALS = 2


def load_safety_paths(path=SAFETY_PATHS_FILE) -> list[str]:
    lines = (ln.strip() for ln in Path(path).read_text(encoding='utf-8').splitlines())
    return [ln for ln in lines if ln and not ln.startswith('#')]


def is_safety_path(file: str, patterns: list[str]) -> bool:
    return any(file.startswith(p) if p.endswith('/') else file == p for p in patterns)


def safety_files(changed: list[str], patterns: list[str]) -> list[str]:
    return sorted(f for f in set(changed) if is_safety_path(f, patterns))


def evaluate(changed: list[str], reviews: list[dict], author: str, head_sha: str,
             patterns: list[str], required: int = REQUIRED_APPROVALS) -> dict:
    """Pure decision. `reviews` are GitHub review objects in chronological order."""
    hit = safety_files(changed, patterns)
    if not hit:
        return {'ok': True, 'safety_files': [], 'approvers': [], 'blocking': [],
                'detail': 'no safety-critical paths touched; standard review rule applies'}
    latest: dict[str, dict] = {}
    for r in reviews:  # a reviewer's latest decisive review wins; plain comments do not reset it
        login = (r.get('user') or {}).get('login')
        if login and login != author and r.get('state') in ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'):
            latest[login] = r
    approvers = sorted(u for u, r in latest.items() if r['state'] == 'APPROVED' and r.get('commit_id') == head_sha)
    stale = sorted(u for u, r in latest.items() if r['state'] == 'APPROVED' and r.get('commit_id') != head_sha)
    blocking = sorted(u for u, r in latest.items() if r['state'] == 'CHANGES_REQUESTED')
    ok = len(approvers) >= required and not blocking
    detail = (f'{len(approvers)}/{required} approvals on head commit {head_sha[:7]}'
              + (f'; stale approvals (re-review needed): {", ".join(stale)}' if stale else '')
              + (f'; changes requested by: {", ".join(blocking)}' if blocking else ''))
    return {'ok': ok, 'safety_files': hit, 'approvers': approvers, 'blocking': blocking, 'detail': detail}


def _get_all(url: str, token: str) -> list:
    out, page = [], 1
    while True:
        req = urllib.request.Request(f'{url}?per_page=100&page={page}', headers={
            'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'})
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
            batch = json.load(resp)
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def main() -> int:
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
    pr = event['pull_request']
    api = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/pulls/{pr['number']}"
    token = os.environ['GITHUB_TOKEN']
    changed = []
    for f in _get_all(f'{api}/files', token):  # a rename out of a safety path still counts
        changed += [f['filename']] + ([f['previous_filename']] if f.get('previous_filename') else [])
    result = evaluate(changed, _get_all(f'{api}/reviews', token), pr['user']['login'], pr['head']['sha'],
                      load_safety_paths())
    for f in result['safety_files']:
        print(f'safety-critical: {f}')
    print(('PASS ' if result['ok'] else 'FAIL ') + result['detail'])
    if result['approvers']:
        print('approved by: ' + ', '.join(result['approvers']))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
