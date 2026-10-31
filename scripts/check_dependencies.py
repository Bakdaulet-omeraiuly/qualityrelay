"""REL-03: dependency / license manifest, pinned requirements and honest adapter statuses.

THIRD_PARTY_MANIFEST.json is the versioned, human-reviewed record. requirements-*.txt are the
supported version ranges; requirements-lock.txt is the exact, transitive pin set CI installs.

  python scripts/check_dependencies.py check   # offline: manifest <-> requirements <-> lock, adapter evidence
  python scripts/check_dependencies.py env     # after `pip install -r requirements-lock.txt`: lock is complete,
                                               # every installed license is known and allowed and unchanged
  python scripts/check_dependencies.py lock    # network: re-resolve requirements-lock.txt (Linux x86_64, py3.11)

Statuses (see docs/engineering/DEPENDENCIES_AND_ADAPTERS.md):
  WORKING         ran on its real backend outside unit tests; a committed run artifact records where
  TESTED          wired, and CI tests exercise it with offline stand-ins; never run against the live thing
  NOT_CONFIGURED  not wired, not installed, or no credentials/hardware; nothing is claimed
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17.external_adapters import STATUSES, load_manifest  # noqa: E402

LOCK = 'requirements-lock.txt'
LOCKED_SPECS = ['requirements-demo.txt', 'requirements-dev.txt']  # what CI and the demo install
ALL_SPECS = LOCKED_SPECS + ['requirements-optional.txt', 'requirements-gpu.txt', 'requirements-vision-optional.txt']
LOCK_PYTHON, LOCK_ALSO = '3.11', ['3.13']  # resolve at the oldest CI Python, prove it installs on the rest
LOCK_PLATFORMS = ['manylinux_2_28_x86_64', 'manylinux_2_17_x86_64', 'manylinux2014_x86_64']
NOT_LOCKED = {'pip', 'setuptools', 'wheel'}
# Strong copyleft / source-available / non-commercial: not acceptable in what we install and ship.
DENY = re.compile(r'(?<!\w)A?GPL|GNU General Public|Affero|SSPL|BUSL|Business Source|Commons Clause|-NC\b|NonCommercial', re.I)
CLASSIFIER_SPDX = {'MIT License': 'MIT', 'BSD License': 'BSD', 'Apache Software License': 'Apache-2.0',
                   'ISC License (ISCL)': 'ISC', 'Python Software Foundation License': 'PSF-2.0',
                   'Mozilla Public License 2.0 (MPL 2.0)': 'MPL-2.0', 'The Unlicense (Unlicense)': 'Unlicense'}


def norm(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def read_requirements(path: Path) -> dict[str, str]:
    """{normalised name: specifier} from one requirements file; follows `-r`."""
    out: dict[str, str] = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if line.startswith('-r '):
            out.update(read_requirements(path.parent / line[3:].strip()))
            continue
        m = re.match(r'^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$', line)
        if not m:
            raise ValueError(f'{path.name}: cannot parse {raw!r}')
        out[norm(m.group(1))] = m.group(2).replace(' ', '')
    return out


def read_lock(root=ROOT) -> dict[str, str]:
    pins = read_requirements(root / LOCK)
    bad = {n: s for n, s in pins.items() if not re.fullmatch(r'==[^,;]+', s)}
    if bad:
        raise ValueError(f'{LOCK}: not exact pins: {bad}')
    return {n: s[2:] for n, s in pins.items()}


# ---------------------------------------------------------------------------- offline check
def check(root=ROOT, manifest: dict | None = None) -> list[str]:
    from jsonschema import Draft202012Validator
    from packaging.specifiers import SpecifierSet
    problems: list[str] = []
    man = load_manifest(root) if manifest is None else manifest
    schema = json.loads((root / 'schemas' / 'third_party_manifest.schema.json').read_text(encoding='utf-8'))
    problems += [f'manifest schema: {"/".join(map(str, e.path))}: {e.message}'
                 for e in Draft202012Validator(schema).iter_errors(man)]
    if problems:
        return problems
    pkgs = {norm(p['name']): p for p in man['python_packages']}
    lock = read_lock(root)

    declared: dict[str, str] = {}
    for spec in ALL_SPECS:
        for name, rng in read_requirements(root / spec).items():
            declared.setdefault(name, rng)
            if name not in pkgs:
                problems.append(f'{spec}: {name} has no entry in THIRD_PARTY_MANIFEST.json python_packages (license review)')
            elif pkgs[name]['requirement'] != rng:
                problems.append(f'{name}: manifest says {pkgs[name]["requirement"]!r}, {spec} says {rng!r}')
    for name in pkgs.keys() - declared.keys():
        problems.append(f'{name}: in the manifest but in no requirements file (stale entry)')

    for spec in LOCKED_SPECS:
        for name, rng in read_requirements(root / spec).items():
            if name not in lock:
                problems.append(f'{LOCK}: {name} (from {spec}) is not pinned; run `check_dependencies.py lock`')
            elif rng and lock[name] not in SpecifierSet(rng):
                problems.append(f'{LOCK}: {name}=={lock[name]} violates {spec} range {rng!r}')
    for name, p in pkgs.items():
        if name in lock and p.get('pinned') != lock[name]:
            problems.append(f'{name}: manifest pinned={p.get("pinned")!r} but {LOCK} has {lock[name]!r}')
        if name not in lock and p.get('pinned') is not None:
            problems.append(f'{name}: optional (not in {LOCK}) so manifest pinned must be null')

    comps = {c['id'] for c in man['upstream_components']}
    for a in man['adapters']:
        aid, st, ev = a['id'], a['status'], a['evidence']
        if a['upstream'] not in comps and norm(a['upstream']) not in pkgs:
            problems.append(f'adapter {aid}: upstream {a["upstream"]!r} is neither a component nor a package')
        for t in ev.get('tests', []):
            if not (root / t.split('::')[0]).is_file():
                problems.append(f'adapter {aid}: evidence test {t} does not exist')
        for art in ev.get('artifacts', []):
            if not (root / art).is_file():
                problems.append(f'adapter {aid}: evidence artifact {art} does not exist')
        if st == 'WORKING' and not ev.get('artifacts'):
            problems.append(f'adapter {aid}: WORKING needs a committed run artifact')
        if st in ('WORKING', 'TESTED'):
            if not ev.get('tests'):
                problems.append(f'adapter {aid}: {st} needs CI tests')
            missing = [r for r in a.get('requires_packages', []) if norm(r) not in lock]
            if missing:  # the tests would importorskip in CI: that is not TESTED
                problems.append(f'adapter {aid}: {st} but {missing} not in {LOCK}, so its tests are skipped in CI')
    return problems


# ---------------------------------------------------------------------------- installed env
def resolved_license(meta) -> str:
    """What the installed wheel says, in the most specific form it offers."""
    if meta.get('License-Expression'):
        return meta['License-Expression'].strip()
    lic = (meta.get('License') or '').strip()
    if lic and '\n' not in lic and len(lic) <= 80:
        return lic
    cls = [c.split(' :: ')[-1] for c in meta.get_all('Classifier') or [] if c.startswith('License :: OSI Approved ::')
           or c.startswith('License :: ') and 'OSI Approved' not in c]
    cls = [CLASSIFIER_SPDX.get(c, c) for c in cls if c != 'OSI Approved']
    return ' OR '.join(sorted(set(cls))) if cls else 'UNKNOWN'


def env(root=ROOT) -> tuple[list[str], list[dict]]:
    import importlib.metadata as md
    problems: list[str] = []
    man = load_manifest(root)
    lock = read_lock(root)
    reviewed = {norm(p['name']): p for p in man['python_packages']} | {norm(t['name']): t for t in man['transitive_license_review']}
    rows = []
    installed = {norm(d.metadata['Name']): d for d in md.distributions()}
    for name, d in sorted(installed.items()):
        if name in NOT_LOCKED:
            continue
        version, lic = d.version, resolved_license(d.metadata)
        rows.append({'name': name, 'version': version, 'license': lic})
        if name not in lock:
            problems.append(f'{name}=={version} is installed but not in {LOCK} (lock incomplete)')
        elif lock[name] != version:
            problems.append(f'{name}: installed {version}, locked {lock[name]}')
        r = reviewed.get(name)
        if r is not None and r.get('license_metadata') != lic:
            problems.append(f'{name}: wheel now reports license {lic!r}, reviewed as {r.get("license_metadata")!r}; re-review')
        effective = r['license'] if r is not None else lic
        if effective == 'UNKNOWN':
            problems.append(f'{name}: license UNKNOWN in metadata; add a reviewed entry to transitive_license_review')
        elif DENY.search(effective):
            problems.append(f'{name}: license {effective!r} is not allowed (copyleft / non-commercial / source-available)')
    for name in lock.keys() - installed.keys():
        problems.append(f'{name} is in {LOCK} but not installed')
    return problems, rows


# ---------------------------------------------------------------------------- re-lock (network)
def _resolve(python: str, reqs: list[str], *, no_deps=False) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / 'report.json'
        cmd = [sys.executable, '-m', 'pip', 'install', '--dry-run', '--ignore-installed', '--quiet', '--report', str(report),
               '--python-version', python, '--only-binary=:all:', '--target', str(Path(tmp) / 't')]
        cmd += [a for p in LOCK_PLATFORMS for a in ('--platform', p)] + (['--no-deps'] if no_deps else [])
        for r in reqs:
            cmd += ['-r', r]
        subprocess.run(cmd, cwd=ROOT, check=True)  # nosec B603
        data = json.loads(report.read_text(encoding='utf-8'))
    return {norm(i['metadata']['name']): i['metadata']['version'] for i in data['install']}


def lock() -> None:
    pins = {n: v for n, v in _resolve(LOCK_PYTHON, LOCKED_SPECS).items() if n not in NOT_LOCKED}
    body = '\n'.join(f'{n}=={pins[n]}' for n in sorted(pins))
    head = (f'# GENERATED by `python scripts/check_dependencies.py lock`; do not edit by hand.\n'
            f'# Exact transitive pins of {" + ".join(LOCKED_SPECS)} for Linux x86_64, resolved at Python {LOCK_PYTHON}\n'
            f'# and checked to install on Python {", ".join(LOCK_ALSO)}. CI installs exactly this. The ranges in the\n'
            f'# requirements-*.txt files say what we support; this file says what we tested.\n')
    (ROOT / LOCK).write_text(head + body + '\n', encoding='utf-8', newline='\n')
    for py in LOCK_ALSO:
        _resolve(py, [LOCK], no_deps=True)
    print(f'{LOCK}: {len(pins)} pins; installs on Python {LOCK_PYTHON}, {", ".join(LOCK_ALSO)}')
    man = load_manifest()
    for p in man['python_packages']:
        p['pinned'] = pins.get(norm(p['name']))
    (ROOT / 'THIRD_PARTY_MANIFEST.json').write_text(json.dumps(man, indent=2, ensure_ascii=False) + '\n',
                                                     encoding='utf-8', newline='\n')
    print('THIRD_PARTY_MANIFEST.json: pinned versions updated; re-review licenses of anything that changed')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['check', 'env', 'lock'])
    ap.add_argument('--report', help='env: also write the installed-license table to this JSON file')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[union-attr]
    if a.step == 'lock':
        lock(); return 0
    if a.step == 'check':
        problems = check()
    else:
        problems, rows = env()
        if a.report:
            Path(a.report).write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
        print(f'{len(rows)} installed distributions checked')
    for p in problems:
        print(f'DEPENDENCY FAIL {p}')
    print('dependencies OK' if not problems else f'{len(problems)} problem(s)')
    if a.step == 'check' and not problems:
        man = load_manifest()
        counts: dict[str, int] = {}
        for ad in man['adapters']:
            counts[ad['status']] = counts.get(ad['status'], 0) + 1
        print('adapters: ' + ', '.join(f'{s}={counts.get(s, 0)}' for s in STATUSES))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
