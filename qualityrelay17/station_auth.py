"""Per-device signed envelope for hardware stations (task board BACK-01).

Two secrets per station, deliberately distinct:
  * DEVICE key  -- lives on the ESP32. Proves "this request came from station X". Used only to
                   verify the envelope below; never signs evidence.
  * STATION key -- server-only gateway identity (api.HARDWARE_STATION_KEYS). Signs the Evidence
                   record *after* the envelope verified. A stolen device key therefore cannot
                   forge ledger signatures, and a leaked station key cannot impersonate a device.

Envelope (HTTP headers on every POST /hardware/*):
  X-Station-Id         station id the sender claims (must also equal body.station_id)
  X-Station-Timestamp  unix seconds on the device (NTP-synced); |server_now - ts| <= ttl_s
  X-Station-Nonce      >= 16 hex chars of device randomness; accepted once per station per ttl
  X-Station-Signature  hex HMAC-SHA256(device_key, canonical(method, path, station, ts, nonce, sha256(body)))

Binding the body hash into the signature means a measurement cannot be altered in flight; binding
the path means a signature for /hardware/bin-ack cannot be replayed to /hardware/caliper-reading.
Order of checks: headers present -> station known -> ACL for this path -> timestamp window ->
nonce well-formed -> signature -> nonce unused. The nonce is consumed only after the signature
verifies, so unauthenticated traffic cannot fill the cache.

Not provided here: server-to-device authentication (that is TLS, task CLOUD-01) and proof that the
sensor behind the device is honest (that is the physical ground-truth procedure, BACK-02).
"""
from __future__ import annotations
import hashlib, hmac, secrets, threading, time
from collections.abc import Mapping

HEADER_ID = 'X-Station-Id'
HEADER_TS = 'X-Station-Timestamp'
HEADER_NONCE = 'X-Station-Nonce'
HEADER_SIG = 'X-Station-Signature'
MIN_NONCE_HEX = 16
DEFAULT_TTL_S = 60


class EnvelopeError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail); self.status, self.detail = status, detail


def canonical(method: str, path: str, station_id: str, timestamp: int, nonce: str, body: bytes) -> bytes:
    """The exact byte string both sides HMAC. Keep in sync with firmware/esp32_station/*.ino."""
    return '\n'.join([method.upper(), path, station_id, str(int(timestamp)), nonce,
                      hashlib.sha256(body).hexdigest()]).encode()


def sign(device_key: str, method: str, path: str, station_id: str, body: bytes, *,
         timestamp: int | None = None, nonce: str | None = None) -> dict[str, str]:
    """Client side: headers to attach. Used by tests, the rehearsal script, and any Python station."""
    ts = int(time.time()) if timestamp is None else int(timestamp)
    nonce = nonce or secrets.token_hex(16)
    sig = hmac.new(device_key.encode(), canonical(method, path, station_id, ts, nonce, body), hashlib.sha256).hexdigest()
    return {HEADER_ID: station_id, HEADER_TS: str(ts), HEADER_NONCE: nonce, HEADER_SIG: sig}


class NonceCache:
    """Bounded, thread-safe (station, nonce) -> expiry. Entries older than ttl are purged on
    insert; anything outside the timestamp window is rejected before reaching here, so the
    cache only ever has to remember one window's worth of traffic."""

    def __init__(self, ttl_s: float = DEFAULT_TTL_S, max_entries: int = 100_000):
        self.ttl_s, self.max_entries = ttl_s, max_entries
        self._seen: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def add(self, station_id: str, nonce: str, *, now: float | None = None) -> bool:
        """True if the nonce was fresh and is now consumed; False if it was already used."""
        now = time.time() if now is None else now
        key = (station_id, nonce)
        with self._lock:
            if len(self._seen) >= self.max_entries or len(self._seen) % 1024 == 0:
                cutoff = now - 2 * self.ttl_s
                for k in [k for k, exp in self._seen.items() if exp < cutoff]: del self._seen[k]
            if key in self._seen and self._seen[key] >= now - 2 * self.ttl_s:
                return False
            if len(self._seen) >= self.max_entries:
                raise EnvelopeError(503, 'nonce cache full; refusing rather than accepting replays')
            self._seen[key] = now
            return True


def verify(headers: Mapping[str, str], method: str, path: str, body: bytes, *,
           device_keys: Mapping[str, str], acl: Mapping[str, set[str]], nonce_cache: NonceCache,
           ttl_s: float = DEFAULT_TTL_S, now: float | None = None) -> str:
    """Server side. Returns the authenticated station_id or raises EnvelopeError(status, detail).
    `headers` may be case-insensitive (Starlette) or a plain dict with canonical names."""
    def h(name: str) -> str | None:
        v = headers.get(name)
        return v if v is not None else headers.get(name.lower())
    station, ts_raw, nonce, sig = h(HEADER_ID), h(HEADER_TS), h(HEADER_NONCE), h(HEADER_SIG)
    if not (station and ts_raw and nonce and sig):
        raise EnvelopeError(401, 'missing station envelope headers')
    key = device_keys.get(station)
    if not key:
        raise EnvelopeError(401, 'unknown station or device key not provisioned')
    if station not in acl.get(path, set()):
        raise EnvelopeError(403, f'station {station!r} is not permitted to post to {path}')
    try:
        ts = int(ts_raw)
    except ValueError:
        raise EnvelopeError(401, 'timestamp must be unix seconds')
    now = time.time() if now is None else now
    if abs(now - ts) > ttl_s:
        raise EnvelopeError(401, f'timestamp outside +/-{int(ttl_s)}s window; check device NTP')
    if len(nonce) < MIN_NONCE_HEX or any(c not in '0123456789abcdefABCDEF' for c in nonce):
        raise EnvelopeError(401, f'nonce must be >= {MIN_NONCE_HEX} hex chars')
    expected = hmac.new(key.encode(), canonical(method, path, station, ts, nonce, body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig.lower()):
        raise EnvelopeError(401, 'bad station signature')
    if not nonce_cache.add(station, nonce, now=now):
        raise EnvelopeError(401, 'nonce already used; replay refused')
    return station
