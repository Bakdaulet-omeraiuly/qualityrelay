"""REL-01: one release label everywhere; manifest hashing is line-ending independent."""
import json, re, subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qualityrelay17 import __version__, release
from qualityrelay17.api import app

ROOT = Path(__file__).resolve().parents[1]


def test_release_label_is_18_1():
    assert __version__ == '18.1'


def test_pyproject_matches_package_version():
    assert re.search(r'^version="([^"]+)"', (ROOT / 'pyproject.toml').read_text(), re.M).group(1) == __version__


def test_api_title_version_and_health_carry_release():
    assert app.version == __version__ and __version__ in app.title
    assert TestClient(app).get('/health').json()['release'] == __version__


def test_readme_title_carries_release():
    first = (ROOT / 'README_START_HERE.md').read_text(encoding='utf-8').splitlines()[0]
    assert first.startswith(f'# QualityRelay {__version__} ')


def test_openapi_snapshot_names_this_release():
    # RELEASE_VALIDATION.json is not checked here: it is written from the result of this very run.
    assert json.loads((ROOT / release.OPENAPI_SNAPSHOT).read_text(encoding='utf-8'))['info']['version'] == __version__


def test_canonical_bytes_normalises_text_only():
    assert release.canonical_bytes(b'a\r\nb\n') == b'a\nb\n'
    binary = b'\0\x01\r\n'
    assert release.canonical_bytes(binary) == binary


@pytest.fixture
def repo(tmp_path):
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    (tmp_path / '.gitignore').write_text('ignored.txt\n')
    (tmp_path / 'a.txt').write_bytes(b'one\ntwo\n')
    (tmp_path / 'b.txt').write_text('b')
    (tmp_path / 'ignored.txt').write_text('x')
    return tmp_path


def test_manifest_round_trip_survives_crlf_checkout(repo):
    release.write_json(release.MANIFEST, release.build_manifest(repo), repo)
    listed = {e['path'] for e in json.loads((repo / release.MANIFEST).read_text())}
    assert listed == {'.gitignore', 'a.txt', 'b.txt'}  # ignored files and the manifest itself excluded
    (repo / 'a.txt').write_bytes(b'one\r\ntwo\r\n')  # what core.autocrlf=true produces on Windows
    assert release.verify_manifest(repo)['ok']


def test_verify_reports_edits_deletions_and_new_files(repo):
    release.write_json(release.MANIFEST, release.build_manifest(repo), repo)
    (repo / 'a.txt').write_text('changed\n')
    (repo / 'b.txt').unlink()
    (repo / 'new.txt').write_text('n')
    r = release.verify_manifest(repo)
    assert not r['ok'] and r['mismatched'] == ['a.txt'] and r['missing'] == ['b.txt'] and r['unlisted'] == ['new.txt']
