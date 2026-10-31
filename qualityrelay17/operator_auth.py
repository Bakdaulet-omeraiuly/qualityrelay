"""Human operator authentication (task board BACK-04, and the verifier identity for BACK-02).

Each operator has one bearer token, provisioned into the real environment or the git-ignored .env
as OPERATOR_<NAME>_TOKEN (>= 32 chars; `python scripts/provision_station_keys.py --operators alice`).
Requests carry `Authorization: Bearer <token>`. The server keeps only SHA-256 digests of the tokens
in memory and compares in constant time; the operator id is the lower-cased <NAME>.

This replaces the caller-asserted `operator_id` / `approved` / `origin` body fields that
/actuation/stage used to accept. It is a shared-secret scheme for a bench demo, not SSO or MFA;
without TLS (CLOUD-01) a token on the wire can be sniffed.
"""
from __future__ import annotations
import hashlib, hmac, re
from collections.abc import Mapping

TOKEN_VAR = re.compile(r'^OPERATOR_([A-Z0-9_]{1,32})_TOKEN$')
MIN_TOKEN_CHARS = 32


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def load_operator_tokens(env: Mapping[str, str], dotenv: Mapping[str, str]) -> dict[str, bytes]:
    """operator_id -> sha256(token). Real environment wins over .env; blank = not provisioned;
    a present-but-short token is a configuration error and refused loudly."""
    out: dict[str, bytes] = {}
    for var in sorted(set(env) | set(dotenv)):
        m = TOKEN_VAR.match(var)
        if not m:
            continue
        value = (env.get(var) or dotenv.get(var) or '').strip()
        if not value:
            continue
        if len(value) < MIN_TOKEN_CHARS:
            raise RuntimeError(f'{var} is shorter than {MIN_TOKEN_CHARS} chars; generate it with scripts/provision_station_keys.py --operators')
        out[m.group(1).lower()] = _digest(value)
    return out


def authenticate(authorization: str | None, tokens: Mapping[str, bytes]) -> str | None:
    """Return the operator id for a valid `Bearer <token>` header, else None. Every provisioned
    digest is compared so timing does not reveal which operator matched."""
    if not authorization or not authorization.startswith('Bearer '):
        return None
    got = _digest(authorization[7:].strip())
    match = None
    for operator_id, want in tokens.items():
        if hmac.compare_digest(got, want):
            match = operator_id
    return match
