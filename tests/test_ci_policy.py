"""REL-02: the CI / review policy is itself tested, so it cannot silently drift."""
import re
from pathlib import Path

import pytest

from scripts.review_gate import evaluate, is_safety_path, load_safety_paths
from scripts.github_board import REQUIRED_CHECKS, parse_tasks

ROOT = Path(__file__).resolve().parents[1]
SAFETY = load_safety_paths()
HEAD, OLD = 'a' * 40, 'b' * 40


def review(user, state, commit=HEAD):
    return {'user': {'login': user}, 'state': state, 'commit_id': commit}


# ---------------------------------------------------------------- safety path list
def test_every_safety_path_exists():
    missing = [p for p in SAFETY if not (ROOT / p).exists()]
    assert not missing, f'stale entries in .github/safety-paths.txt: {missing}'


def test_core_safety_modules_are_listed():
    for f in ('qualityrelay17/actuation.py', 'qualityrelay17/station_auth.py', 'qualityrelay17/operator_auth.py',
              'firmware/esp32_station/esp32_station.ino', '.github/workflows/tests.yml', '.github/safety-paths.txt'):
        assert is_safety_path(f, SAFETY), f


def test_codeowners_covers_every_safety_path_with_two_or_more_owners():
    rules = {}
    for line in (ROOT / '.github' / 'CODEOWNERS').read_text(encoding='utf-8').splitlines():
        parts = line.split()
        if parts and not parts[0].startswith('#'):
            rules[parts[0].lstrip('/')] = [p for p in parts[1:] if p.startswith('@')]
    for p in SAFETY:
        assert p in rules, f'{p} is safety-critical but has no CODEOWNERS rule'
        assert len(rules[p]) >= 3, f'{p}: list every owner so any non-author owner can review'


def test_no_safety_module_is_exempt_from_mypy():
    tomllib = pytest.importorskip('tomllib')
    cfg = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    exempt = {m for o in cfg['tool']['mypy'].get('overrides', []) if o.get('ignore_errors') for m in o['module']}
    safety_modules = {p[:-3].replace('/', '.') for p in SAFETY if p.startswith('qualityrelay17/') and p.endswith('.py')}
    assert not exempt & safety_modules, f'safety modules on the mypy ratchet: {exempt & safety_modules}'


def test_required_checks_exist_as_jobs():
    wf = (ROOT / '.github' / 'workflows' / 'tests.yml').read_text(encoding='utf-8')
    gate = (ROOT / '.github' / 'workflows' / 'review-gate.yml').read_text(encoding='utf-8')
    jobs = set(re.findall(r'^  ([a-z][\w-]*):\s*$', wf, re.M)) | set(re.findall(r'^  ([a-z][\w-]*):\s*$', gate, re.M))
    for check in REQUIRED_CHECKS:
        assert check.split(' (')[0] in jobs, check
    for v in re.findall(r"test \(([\d.]+)\)", ' '.join(REQUIRED_CHECKS)):
        assert f"'{v}'" in wf, f'test matrix lacks Python {v}'


def test_review_gate_reads_rules_from_base_commit():
    gate = (ROOT / '.github' / 'workflows' / 'review-gate.yml').read_text(encoding='utf-8')
    assert 'ref: ${{ github.event.pull_request.base.sha }}' in gate


# ---------------------------------------------------------------- two-review gate
def test_non_safety_pr_passes_without_extra_reviews():
    r = evaluate(['docs/research/x.md', 'qualityrelay17/sim/engine.py'], [], 'alice', HEAD, SAFETY)
    assert r['ok'] and r['safety_files'] == []


def test_safety_pr_needs_two_approvals():
    files = ['qualityrelay17/actuation.py', 'README_START_HERE.md']
    assert not evaluate(files, [review('bob', 'APPROVED')], 'alice', HEAD, SAFETY)['ok']
    r = evaluate(files, [review('bob', 'APPROVED'), review('carol', 'APPROVED')], 'alice', HEAD, SAFETY)
    assert r['ok'] and r['approvers'] == ['bob', 'carol'] and r['safety_files'] == ['qualityrelay17/actuation.py']


def test_author_cannot_approve_own_safety_change():
    reviews = [review('alice', 'APPROVED'), review('bob', 'APPROVED')]
    assert not evaluate(['qualityrelay17/station_auth.py'], reviews, 'alice', HEAD, SAFETY)['ok']


def test_same_reviewer_twice_counts_once():
    reviews = [review('bob', 'APPROVED'), review('bob', 'APPROVED')]
    assert not evaluate(['firmware/esp32_station/bin_sensor.ino'], reviews, 'alice', HEAD, SAFETY)['ok']


def test_approval_on_older_commit_does_not_count():
    reviews = [review('bob', 'APPROVED', OLD), review('carol', 'APPROVED')]
    r = evaluate(['qualityrelay17/ledger.py'], reviews, 'alice', HEAD, SAFETY)
    assert not r['ok'] and 'stale' in r['detail'] and 'bob' in r['detail']


def test_changes_requested_blocks_until_superseded():
    files = ['qualityrelay17/actuation.py']
    base = [review('bob', 'APPROVED'), review('carol', 'APPROVED'), review('dave', 'CHANGES_REQUESTED')]
    assert not evaluate(files, base, 'alice', HEAD, SAFETY)['ok']
    assert evaluate(files, base + [review('dave', 'APPROVED')], 'alice', HEAD, SAFETY)['ok']


def test_comment_does_not_reset_approval_but_dismissal_does():
    files = ['qualityrelay17/actuation.py']
    approved = [review('bob', 'APPROVED'), review('carol', 'APPROVED')]
    assert evaluate(files, approved + [review('bob', 'COMMENTED')], 'alice', HEAD, SAFETY)['ok']
    assert not evaluate(files, approved + [review('bob', 'DISMISSED')], 'alice', HEAD, SAFETY)['ok']


def test_directory_prefix_matching_is_not_substring_matching():
    assert is_safety_path('.github/workflows/new.yml', SAFETY)
    assert not is_safety_path('docs/.github/x', SAFETY)
    assert not is_safety_path('qualityrelay17/actuation.py.bak', SAFETY)


# ---------------------------------------------------------------- task board -> issues
BOARD = """
## CAPE addendum
- [ ] **CAPE-04 — adilnurgg:** Supply scoped traces.
## 1. Bakdaulet — Research
### P0 — Fix errors
- [ ] **SCI-01 — Fair cost accounting:** charge once.
### P1 — Vision
- [x] **VISION-01** *(done 1 Nov: see `x.py` (fixture))*: Registration.
- [ ] **VISION-02:** Photo↔CAD.
## 2. adilnurgg — Backend
- [ ] **BACK-04 — Safety enforcement** *(software half done)*: hardware half.
## 6. Final demonstration
- [ ] **Unified trace:** joint item without an ID.
"""


def test_board_parser_assigns_owner_priority_and_status():
    t = {x['id']: x for x in parse_tasks(BOARD)}
    assert set(t) == {'CAPE-04', 'SCI-01', 'VISION-01', 'VISION-02', 'BACK-04'}
    assert t['CAPE-04']['owner'] == 'adilnurgg' and t['CAPE-04']['title'] == '[CAPE-04] Supply scoped traces.'
    assert t['SCI-01']['owner'] == 'Bakdaulet-omeraiuly' and t['SCI-01']['priority'] == 'P0'
    assert t['SCI-01']['title'] == '[SCI-01] Fair cost accounting: charge once.'
    assert t['VISION-01']['done'] and t['VISION-02']['priority'] == 'P1'
    assert t['BACK-04']['safety'] and t['BACK-04']['title'] == '[BACK-04] Safety enforcement: hardware half.'


def test_real_task_board_has_an_owner_for_every_open_task():
    tasks = parse_tasks((ROOT / 'QUALITYRELAY_18_1_TEAM_TASKS_EN.md').read_text(encoding='utf-8'))
    assert tasks and all(t['owner'] for t in tasks if not t['done'])
    assert len({t['id'] for t in tasks}) == len(tasks), 'duplicate task IDs on the board'
