"""REL-03: dependency/licence manifest, pinned requirements and evidence-backed adapter statuses."""
import copy
from email.message import Message
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qualityrelay17.api import app
from qualityrelay17.external_adapters import NVIDIA_ADAPTERS, STATUSES, adapters, load_manifest
from scripts.check_dependencies import DENY, check, read_lock, resolved_license

ROOT = Path(__file__).resolve().parents[1]
MAN = load_manifest()


def mutated(adapter_id, **changes):
    m = copy.deepcopy(MAN)
    a = next(x for x in m['adapters'] if x['id'] == adapter_id)
    a.update(changes)
    return m


# ---------------------------------------------------------------- the real repo is consistent
def test_manifest_requirements_lock_and_evidence_agree():
    assert check() == []


def test_lock_is_exact_and_covers_ci():
    lock = read_lock()
    for name in ('fastapi', 'numpy', 'pytest', 'warp-lang', 'openai', 'ruff'):
        assert name in lock, name


def test_ci_installs_the_lock_not_the_ranges():
    wf = (ROOT / '.github' / 'workflows' / 'tests.yml').read_text(encoding='utf-8')
    assert 'pip install -r requirements-lock.txt' in wf
    assert 'pip install -r requirements-dev.txt' not in wf and 'pip install -r requirements-demo.txt' not in wf


# ---------------------------------------------------------------- statuses must be earned
def test_working_without_a_run_artifact_is_rejected():
    problems = check(manifest=mutated('nvidia.cuopt', status='WORKING', evidence={'tests': ['tests/test_warp_mc.py']}))
    assert any('nvidia.cuopt: WORKING needs a committed run artifact' in p for p in problems)


def test_tested_whose_tests_would_skip_in_ci_is_rejected():
    problems = check(manifest=mutated('vision.anomaly_stfpm', status='TESTED'))
    assert any('vision.anomaly_stfpm: TESTED but' in p and 'skipped in CI' in p for p in problems)


def test_evidence_must_exist():
    problems = check(manifest=mutated('nvidia.warp', evidence={'tests': ['tests/test_nope.py'], 'artifacts': ['x/none.json']}))
    assert any('test_nope.py does not exist' in p for p in problems)
    assert any('none.json does not exist' in p for p in problems)


def test_unknown_status_is_rejected_by_schema():
    problems = check(manifest=mutated('cloud.gcp', status='RUNNING'))
    assert problems and 'manifest schema' in problems[0]


def test_unreviewed_requirement_is_rejected():
    m = copy.deepcopy(MAN)
    m['python_packages'] = [p for p in m['python_packages'] if p['name'] != 'trimesh']
    assert any('trimesh has no entry' in p for p in check(manifest=m))


def test_range_drift_between_manifest_and_requirements_is_rejected():
    m = copy.deepcopy(MAN)
    next(p for p in m['python_packages'] if p['name'] == 'numpy')['requirement'] = '>=1'
    assert any('numpy: manifest says' in p for p in check(manifest=m))


# ---------------------------------------------------------------- honesty about NVIDIA
def test_not_all_nvidia_services_are_claimed_running():
    states = {k: a.health().state for k, a in NVIDIA_ADAPTERS.items()}
    assert len(states) >= 8
    assert [k for k, s in states.items() if s == 'WORKING'] == ['warp']
    assert sum(s == 'NOT_CONFIGURED' for s in states.values()) == len(states) - 1


def test_website_claim_matches_the_registry():
    html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
    configured = {k for k, a in NVIDIA_ADAPTERS.items() if a.health().state != 'NOT_CONFIGURED'}
    claim = 'Warp is used; the other adapters are <code>NOT_CONFIGURED</code>'
    assert (claim in html) == (configured == {'warp'}), 'web/index.html "Not claimed" card is out of date'


def test_api_reports_registry_without_upgrading_anything():
    c = TestClient(app)
    body = c.get('/integrations').json()
    assert set(body['adapters']) == set(adapters())
    assert all(a['state'] in STATUSES and a['scope'] for a in body['adapters'].values())
    assert body['counts'] == {s: sum(a['state'] == s for a in body['adapters'].values()) for s in STATUSES}
    nv = c.get('/integrations/nvidia').json()
    assert nv['warp']['state'] == 'WORKING' and nv['cuopt']['state'] == 'NOT_CONFIGURED'
    assert body['adapters']['llm.nebius_planner']['state'] == 'TESTED'  # not WORKING: no live call recorded


# ---------------------------------------------------------------- licence resolution and policy
def meta(**fields):
    m = Message()
    for k, v in fields.items():
        for item in (v if isinstance(v, list) else [v]):
            m[k.replace('_', '-')] = item
    return m


def test_license_expression_wins_then_short_field_then_classifier():
    assert resolved_license(meta(License_Expression='MIT', License='whatever')) == 'MIT'
    assert resolved_license(meta(License='Apache 2.0')) == 'Apache 2.0'
    long_text = meta(License='Copyright (c) 2001\nlong licence text ' * 5,
                     Classifier=['License :: OSI Approved :: BSD License'])
    assert resolved_license(long_text) == 'BSD'
    assert resolved_license(meta()) == 'UNKNOWN'


@pytest.mark.parametrize('lic, denied', [
    ('GPL-3.0-only', True), ('AGPL-3.0', True), ('GNU General Public License v3 (GPLv3)', True),
    ('CC-BY-NC-SA-4.0', True), ('SSPL-1.0', True),
    ('LGPL-2.1-or-later', False), ('MPL-2.0', False), ('MIT', False), ('Apache-2.0 OR BSD-2-Clause', False),
    ('BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0', False)])
def test_license_policy(lic, denied):
    assert bool(DENY.search(lic)) is denied


def test_reviewed_licences_of_locked_packages_are_allowed():
    for p in MAN['python_packages']:
        if p['pinned']:
            assert not DENY.search(p['license']), p['name']
