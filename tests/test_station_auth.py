"""Unit tests for the per-device signed envelope (BACK-01), independent of FastAPI."""
import pytest
from qualityrelay17.station_auth import (sign, verify, canonical, NonceCache, EnvelopeError,
                                         HEADER_ID, HEADER_TS, HEADER_NONCE, HEADER_SIG)

KEYS = {'slot': 'k-slot-' + 'a' * 32, 'sorter': 'k-sorter-' + 'b' * 32}
ACL = {'/hardware/caliper-reading': {'slot', 'tab'}, '/hardware/bin-ack': {'sorter'}}
PATH = '/hardware/caliper-reading'
BODY = b'{"station_id":"slot","adc_value":2048}'


def ok(**kw):
    cache = kw.pop('cache', NonceCache())
    now = kw.pop('now', 1_000_000)
    hdr = sign(KEYS['slot'], 'POST', PATH, 'slot', BODY, timestamp=now, **kw)
    return hdr, cache, now


def test_roundtrip():
    hdr, cache, now = ok()
    assert verify(hdr, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, now=now) == 'slot'


def test_canonical_is_deterministic_and_binds_body_hash():
    a = canonical('post', PATH, 'slot', 5, 'n' * 16, b'x')
    assert a == canonical('POST', PATH, 'slot', 5, 'n' * 16, b'x') and a != canonical('POST', PATH, 'slot', 5, 'n' * 16, b'y')


def test_lowercase_headers_accepted():
    hdr, cache, now = ok()
    low = {k.lower(): v for k, v in hdr.items()}
    assert verify(low, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, now=now) == 'slot'


@pytest.mark.parametrize('missing', [HEADER_ID, HEADER_TS, HEADER_NONCE, HEADER_SIG])
def test_missing_header_401(missing):
    hdr, cache, now = ok(); hdr.pop(missing)
    with pytest.raises(EnvelopeError) as e:
        verify(hdr, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, now=now)
    assert e.value.status == 401


def test_check_order_unknown_station_before_acl():
    hdr, cache, now = ok(); hdr[HEADER_ID] = 'ghost'
    with pytest.raises(EnvelopeError) as e:
        verify(hdr, 'POST', '/hardware/bin-ack', BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, now=now)
    assert e.value.status == 401


def test_acl_403():
    hdr = sign(KEYS['sorter'], 'POST', PATH, 'sorter', BODY, timestamp=1_000_000)
    with pytest.raises(EnvelopeError) as e:
        verify(hdr, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=NonceCache(), now=1_000_000)
    assert e.value.status == 403


def test_timestamp_window_both_sides():
    for skew in (-61, 61):
        hdr, cache, now = ok()
        with pytest.raises(EnvelopeError, match='timestamp'):
            verify(hdr, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, ttl_s=60, now=now + skew)
    hdr, cache, now = ok()
    assert verify(hdr, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, ttl_s=60, now=now + 60) == 'slot'


def test_short_or_non_hex_nonce_rejected():
    for bad in ('abc', 'zz' * 10):
        hdr, cache, now = ok(nonce=bad)
        with pytest.raises(EnvelopeError, match='nonce'):
            verify(hdr, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, now=now)


def test_signature_covers_method_path_station_ts_nonce_body():
    base, cache, now = ok()
    variants = [('POST', '/hardware/bin-ack', BODY), ('PUT', PATH, BODY), ('POST', PATH, BODY + b' ')]
    for method, path, body in variants:
        with pytest.raises(EnvelopeError, match='signature'):
            verify(base, method, path, body, device_keys=KEYS, acl={**ACL, '/hardware/bin-ack': {'slot'}}, nonce_cache=NonceCache(), now=now)
    for field in (HEADER_TS, HEADER_NONCE):
        hdr = dict(base); hdr[field] = str(int(hdr[field], 16) + 1) if field == HEADER_NONCE else str(int(hdr[field]) + 1)
        if field == HEADER_NONCE: hdr[field] = 'f' * 32
        with pytest.raises(EnvelopeError, match='signature'):
            verify(hdr, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=NonceCache(), now=now)


def test_nonce_single_use_per_station_and_not_consumed_on_bad_signature():
    hdr, cache, now = ok(nonce='0123456789abcdef0123456789abcdef')
    bad = dict(hdr); bad[HEADER_SIG] = '0' * 64
    with pytest.raises(EnvelopeError, match='signature'):
        verify(bad, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, now=now)
    assert verify(hdr, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, now=now) == 'slot'
    with pytest.raises(EnvelopeError, match='replay'):
        verify(hdr, 'POST', PATH, BODY, device_keys=KEYS, acl=ACL, nonce_cache=cache, now=now)


def test_nonce_cache_scoped_per_station_and_expires():
    cache = NonceCache(ttl_s=10)
    assert cache.add('slot', 'n1', now=0) and cache.add('tab', 'n1', now=0)
    assert not cache.add('slot', 'n1', now=5)
    assert cache.add('slot', 'n1', now=100)  # far outside the window: a timestamp check would reject the request anyway


def test_nonce_cache_refuses_rather_than_overflows():
    cache = NonceCache(ttl_s=10, max_entries=3)
    for i in range(3): assert cache.add('slot', f'n{i}', now=0)
    with pytest.raises(EnvelopeError) as e:
        cache.add('slot', 'n3', now=1)
    assert e.value.status == 503
