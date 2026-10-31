"""BACK-04 operator identity: bearer tokens from env/.env, stored as digests, compared in constant time."""
import subprocess, sys
import pytest
from qualityrelay17 import operator_auth
from qualityrelay17.api import read_dotenv

TOK = 'a' * 64


def test_tokens_load_from_env_and_dotenv_real_env_wins():
    t = operator_auth.load_operator_tokens({'OPERATOR_ALICE_TOKEN': TOK}, {'OPERATOR_ALICE_TOKEN': 'b' * 64, 'OPERATOR_BOB_TOKEN': 'c' * 64})
    assert set(t) == {'alice', 'bob'}
    assert operator_auth.authenticate('Bearer ' + TOK, t) == 'alice'
    assert operator_auth.authenticate('Bearer ' + 'b' * 64, t) is None


def test_tokens_are_not_kept_in_plaintext():
    t = operator_auth.load_operator_tokens({'OPERATOR_ALICE_TOKEN': TOK}, {})
    assert TOK.encode() not in t['alice'] and len(t['alice']) == 32


def test_short_token_refused_blank_ignored_other_vars_ignored():
    with pytest.raises(RuntimeError):
        operator_auth.load_operator_tokens({'OPERATOR_ALICE_TOKEN': 'short'}, {})
    assert operator_auth.load_operator_tokens({'OPERATOR_ALICE_TOKEN': '  ', 'SLOT_STATION_KEY': TOK}, {}) == {}


@pytest.mark.parametrize('header', [None, '', TOK, 'Basic ' + TOK, 'Bearer ', 'Bearer wrong'])
def test_malformed_or_wrong_headers_fail(header):
    assert operator_auth.authenticate(header, {'alice': operator_auth._digest(TOK)}) is None


def test_provision_script_generates_operator_tokens_without_echoing(tmp_path):
    env_file = tmp_path / '.env'
    cmd = [sys.executable, 'scripts/provision_station_keys.py', '--env-file', str(env_file)]
    out = subprocess.run(cmd + ['--stations', 'slot', '--operators', 'alice'], capture_output=True, text=True, check=True).stdout
    tok = read_dotenv(env_file)['OPERATOR_ALICE_TOKEN']
    assert len(tok) == 64 and tok not in out
    shown = subprocess.run(cmd + ['--show-operator-token', 'alice'], capture_output=True, text=True, check=True).stdout.strip()
    assert shown == tok
    assert subprocess.run(cmd + ['--operators', 'bad-name'], capture_output=True).returncode != 0
