"""Runs the Node acceptance tests for the contributed tolerance check (collab/sentilab-tolerance-check)."""
import shutil
import subprocess
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COLLAB = ROOT / 'collab' / 'sentilab-tolerance-check'
# The exact bytes posted in ticket 3b5fc17f; a mismatch means the contributed file was edited.
PUBLISHED_SHA256 = '753e763ef6166f752091f8830474ce06cd253d03e475735518e260ee354f84ab'


def test_contributed_file_is_unmodified():
    assert hashlib.sha256((COLLAB / 'api' / 'check.mjs').read_bytes()).hexdigest() == PUBLISHED_SHA256


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is not installed')
def test_contract_cases_pass_in_node():
    r = subprocess.run(['node', '--test', str(COLLAB / 'check.test.mjs')],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
