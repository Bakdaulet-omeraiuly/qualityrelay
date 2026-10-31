"""REL-01: release validation record and SHA256 manifest of every packaged file.

Packaged files = git-tracked + untracked-but-not-ignored, minus the manifest itself.
Hashes are over canonical bytes: text files (no NUL in the first 8000 bytes, git's own
heuristic) have CRLF normalised to LF, so a Windows checkout with core.autocrlf=true and a
Linux checkout of the same commit produce the same manifest. Binary files are hashed as-is."""
from __future__ import annotations
import hashlib, json, platform, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'FILE_SHA256_MANIFEST.json'
VALIDATION = 'RELEASE_VALIDATION.json'
OPENAPI_SNAPSHOT = 'schemas/openapi_demo.json'
EXCLUDED = {MANIFEST}

# Declared, not measured: what this package does NOT contain. Change only with evidence.
DECLARED_SCOPE = {
    'status': 'reference_implementation_only',
    'original_baseline_5_files': 33,
    'external_repos_bundled': False,
    'live_nebius_run': False,
    'trained_nvidia_weights': False,
    'physical_validation': False,
    'simulation_only': True,
    'scientific_superiority_proven': False,
}


def _git(*args, root=ROOT):
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, check=True).stdout


def packaged_files(root=ROOT):
    out = _git('ls-files', '-z', '--cached', '--others', '--exclude-standard', root=root)
    paths = {p for p in out.split('\0') if p}
    return sorted(p for p in paths if p not in EXCLUDED and (root / p).is_file())


def canonical_bytes(data: bytes) -> bytes:
    return data if b'\0' in data[:8000] else data.replace(b'\r\n', b'\n')


def file_entry(path, root=ROOT):
    b = canonical_bytes((root / path).read_bytes())
    return {'path': path, 'size': len(b), 'sha256': hashlib.sha256(b).hexdigest()}


def build_manifest(root=ROOT):
    return [file_entry(p, root) for p in packaged_files(root)]


def write_json(path, obj, root=ROOT):
    (root / path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def verify_manifest(root=ROOT):
    """-> dict(ok, checked, mismatched, missing, unlisted)."""
    listed = json.loads((root / MANIFEST).read_text(encoding='utf-8'))
    mismatched, missing = [], []
    for e in listed:
        if not (root / e['path']).is_file():
            missing.append(e['path'])
        elif file_entry(e['path'], root) != e:
            mismatched.append(e['path'])
    unlisted = sorted(set(packaged_files(root)) - {e['path'] for e in listed})
    return dict(ok=not (mismatched or missing or unlisted), checked=len(listed),
                mismatched=mismatched, missing=missing, unlisted=unlisted)


def write_openapi_snapshot(root=ROOT):
    from .api import app
    write_json(OPENAPI_SNAPSHOT, app.openapi(), root)


def run_tests(root=ROOT):
    """Run the real suite; -> (exit_code, summary_line, counts)."""
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider'],
                       cwd=root, capture_output=True, text=True)
    lines = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    summary = next((l.strip('= ') for l in reversed(lines) if re.search(r'\d+ (passed|failed|error)', l)), '')
    counts = {k: int(n) for n, k in re.findall(r'(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|warnings?)', summary)}
    return r.returncode, summary, counts


def build_validation(root=ROOT):
    code, summary, counts = run_tests(root)
    commit = _git('rev-parse', 'HEAD', root=root).strip()
    dirty = sorted(l[3:] for l in _git('status', '--porcelain', '--untracked-files=all', root=root).splitlines()
                   if l[3:] not in {MANIFEST, VALIDATION, OPENAPI_SNAPSHOT})
    return {
        'release': __version__,
        'generated_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'git_commit': commit,
        'working_tree_dirty': bool(dirty),
        'uncommitted_paths': len(dirty),
        'python': platform.python_version(),
        'platform': platform.platform(),
        'pytest_exit_code': code,
        'pytest_passed': code == 0,
        'pytest_result': summary,
        'pytest_counts': counts,
        'total_manifest_files': len(packaged_files(root)),
        'manifest_hashing': 'sha256 over canonical bytes (text: CRLF->LF; binary: raw); excludes ' + MANIFEST,
        **DECLARED_SCOPE,
    }
