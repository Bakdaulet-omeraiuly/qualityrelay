"""E12 / E13 rehearsal against a REAL HTTP server, with a sensor model that bounces like the
firmware will -- and a --live mode for the day the physical bin sensor exists.

Modes
  simulate (default)  Starts uvicorn on a free port with throwaway station keys, then drives it
                      with a fake sensor that behaves like firmware/esp32_station/bin_sensor.ino:
                      one POST per rising edge, millis()-based event_ids, bounce bursts of several
                      edges per arrival, a mid-run "reboot" that resets millis() (so ids repeat),
                      concurrent edges (worst case: two sensors / async firmware), and a misroute.
                      Asserts: exactly one PHYSICAL_ROUTE_CONFIRMED per staged route, never two;
                      misroute -> ROUTE_MISMATCH and FAULTED, not recovered by a later correct drop.
  live                Points at an already-running server (--server URL) whose bin sensor is real.
                      Stages a route for --specimen, tells you what to do physically, polls
                      /actuation/{id} until CONFIRMED/FAULTED or timeout, and records the outcome.

Both modes write a manifest under examples/results/rehearsal_e12_e13/. The simulate manifest is
origin TEST_FIXTURE -- it proves server timing/concurrency behaviour, NOT the sensor. Only a
live run with the real photoresistor + 4N35 is a physical result for task item 4.

    python scripts/rehearse_e12_e13.py                       # simulate, seed 2026
    python scripts/rehearse_e12_e13.py --seed 7 --parts 40
    python scripts/rehearse_e12_e13.py live --server http://192.168.1.20:8000 --specimen S-7 --bin PASS \
        --evidence-id evt-slot-...        # QR_OPERATOR_TOKEN in the environment = your operator token

Staging needs an operator bearer token and cited evidence (BACK-02/04): PASS/REJECT routes must
cite a station-authenticated reading with a recorded ground-truth check (VERIFIED_PHYSICAL). The
simulate mode does that per part over HTTP: signed caliper reading -> GT-CAL-01 check -> stage.
"""
from __future__ import annotations
import argparse, json, os, random, secrets, socket, subprocess, sys, threading, time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from qualityrelay17 import station_auth  # noqa: E402
OUT_DIR = ROOT / 'examples' / 'results' / 'rehearsal_e12_e13'


# ----------------------------------------------------------------------------- sensor model
class FakeBinSensor:
    """Mimics bin_sensor.ino's observable behaviour: a POST per rising edge, event_id built from
    STATION_ID + millis(). millis() restarts from ~0 on reboot(), which is exactly the id-reuse
    hazard the firmware comment warns about."""

    def __init__(self, client: httpx.Client, bin_name: str, rng: random.Random, device_key: str):
        self.client, self.bin_name, self.rng, self.device_key = client, bin_name, rng, device_key
        self.boot_t = time.monotonic() - rng.uniform(5, 50)  # board has been up a while
        self.posted: list[dict] = []
        self._lock = threading.Lock()

    def millis(self) -> int:
        return int((time.monotonic() - self.boot_t) * 1000)

    def reboot(self):
        self.boot_t = time.monotonic()

    def edge(self, specimen_id: str, *, fixed_millis: int | None = None) -> dict:
        ms = self.millis() if fixed_millis is None else fixed_millis
        body = {'event_id': f'evt-bin-sorter-{ms}', 'specimen_id': specimen_id, 'station_id': 'sorter',
                'bin_name': self.bin_name, 'photoresistor_blocked': True}
        r = post_signed(self.client, '/hardware/bin-ack', body, 'sorter', self.device_key)
        rec = {'event_id': body['event_id'], 'specimen_id': specimen_id, 'bin': self.bin_name, 'http': r.status_code,
               'interlock': (r.json().get('interlock', {}).get('status') if r.status_code == 200 else None),
               'detail': (r.json().get('detail') if r.status_code != 200 else None)}
        with self._lock:
            self.posted.append(rec)
        return rec

    def bounce_burst(self, specimen_id: str, *, edges: int, concurrent: bool) -> list[dict]:
        """`edges` rising edges for one physical arrival. Sequential = what the blocking HTTP
        call in the sketch produces (>= one POST round-trip apart). Concurrent = worst case."""
        if not concurrent:
            out = []
            for _ in range(edges):
                out.append(self.edge(specimen_id))
                time.sleep(self.rng.uniform(0.0, 0.12))  # 50 ms poll + LDR settling jitter
            return out
        results: list[dict] = []
        base = self.millis()
        # distinct millis per edge, as distinct edges would get; fired at the same instant
        ts = [threading.Thread(target=lambda i=i: results.append(self.edge(specimen_id, fixed_millis=base + i)))
              for i in range(edges)]
        [t.start() for t in ts]; [t.join() for t in ts]
        return results


# ----------------------------------------------------------------------------- helpers
def post_signed(client: httpx.Client, path: str, body: dict, station: str, device_key: str) -> httpx.Response:
    """Exactly what the ESP32 does: serialize, sign the bytes, send bytes + X-Station-* headers."""
    raw = json.dumps(body).encode()
    hdr = station_auth.sign(device_key, 'POST', path, station, raw)
    return client.post(path, content=raw, headers={**hdr, 'Content-Type': 'application/json'}, timeout=10)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


def git_commit() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except Exception:
        return 'unknown'


def stage(client: httpx.Client, action_id: str, specimen_id: str, bin_name: str, token: str, evidence_ids: list[str]) -> dict:
    decision = {'PASS': 'AUTHORIZED_PASS', 'REJECT': 'CONFIRMED_REJECT', 'HOLD': 'HOLD'}[bin_name]
    r = client.post('/actuation/stage', json={'action_id': action_id, 'specimen_id': specimen_id, 'bin': bin_name,
                                              'decision': decision, 'evidence_ids': evidence_ids},
                    headers={'Authorization': f'Bearer {token}'}, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f'stage {action_id}: HTTP {r.status_code} {r.text}')
    return r.json()


def verified_reading(client: httpx.Client, specimen_id: str, slot_device_key: str, token: str) -> str:
    """Rehearsal stand-in for a real measurement + GT-CAL-01 check. TEST_FIXTURE: the 'reference'
    is the reading itself, so this proves the server path, not any instrument."""
    eid = f'evt-slot-{specimen_id}-{secrets.token_hex(4)}'
    r = post_signed(client, '/hardware/caliper-reading', {'event_id': eid, 'specimen_id': specimen_id, 'station_id': 'slot',
                    'adc_value': 2048, 'uncertainty_mm': 0.03, 'calibration_id': 'rehearsal-cal'}, 'slot', slot_device_key)
    r.raise_for_status()
    v = client.post(f'/evidence/{eid}/verify', headers={'Authorization': f'Bearer {token}'}, timeout=10,
                    json={'procedure_id': 'GT-CAL-01', 'observed_specimen_id': specimen_id, 'reference_value_mm': r.json()['payload']['measurement_mm'],
                          'reference_uncertainty_mm': 0.01, 'reference_instrument_id': 'rehearsal-fixture', 'reference_calibration_id': 'n/a',
                          'notes': 'TEST_FIXTURE rehearsal, not a real ground-truth check'})
    v.raise_for_status()
    return eid


def status(client: httpx.Client, action_id: str) -> dict:
    return client.get(f'/actuation/{action_id}', timeout=10).json()


def write_manifest(name: str, body: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f'{name}_{time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())}.json'
    path.write_text(json.dumps(body, indent=2), encoding='utf-8')
    return path


# ----------------------------------------------------------------------------- simulate
def run_simulate(a) -> int:
    rng = random.Random(a.seed)
    port = free_port()
    sorter_device_key, slot_device_key, token = secrets.token_hex(32), secrets.token_hex(32), secrets.token_hex(32)
    env = {**os.environ, 'SORTER_STATION_KEY': secrets.token_hex(32), 'SLOT_STATION_KEY': secrets.token_hex(32),
           'SORTER_DEVICE_KEY': sorter_device_key, 'SLOT_DEVICE_KEY': slot_device_key,
           'OPERATOR_REHEARSAL_TOKEN': token, 'ACTUATION_HARDWARE_ENABLED': '0',
           'HARDWARE_LEDGER_PATH': ':memory:'}
    stage_verified = lambda aid, sid, b: stage(c, aid, sid, b, token, [verified_reading(c, sid, slot_device_key, token)])
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'qualityrelay17.api:app', '--port', str(port),
                               '--host', '127.0.0.1', '--log-level', 'warning'], cwd=ROOT, env=env)
    base = f'http://127.0.0.1:{port}'
    failures: list[str] = []
    started = time.time()
    try:
        with httpx.Client(base_url=base) as c:
            for _ in range(100):
                try:
                    if c.get('/health', timeout=1).status_code == 200: break
                except httpx.HTTPError:
                    time.sleep(0.1)
            else:
                print('server did not come up'); return 2
            health = c.get('/health').json()
            assert 'sorter' in health['hardware_stations_provisioned'], health

            pass_sensor = FakeBinSensor(c, 'PASS', rng, sorter_device_key)
            hold_sensor = FakeBinSensor(c, 'HOLD', rng, sorter_device_key)
            per_part: list[dict] = []

            # --- E13 under bounce: many parts, each one staged PASS route, each arrival bounces
            for i in range(a.parts):
                sid, aid = f'S-{i:03d}', f'act-{i:03d}'
                stage_verified(aid, sid, 'PASS')
                edges = rng.choice([1, 1, 2, 3, 5])              # most arrivals are clean; some chatter
                concurrent = rng.random() < 0.4
                if i == a.parts // 2:
                    pass_sensor.reboot()                          # millis() resets mid-run
                res = pass_sensor.bounce_burst(sid, edges=edges, concurrent=concurrent)
                confirmed = sum(r['interlock'] == 'PHYSICAL_ROUTE_CONFIRMED' for r in res)
                st = status(c, aid)
                per_part.append({'specimen': sid, 'edges': edges, 'concurrent': concurrent, 'confirmed_count': confirmed,
                                 'statuses': [r['interlock'] or f"HTTP{r['http']}" for r in res], 'final_state': st['state']})
                if confirmed != 1:
                    failures.append(f'{sid}: {confirmed} confirmations for one route (edges={edges}, concurrent={concurrent})')
                if st['state'] != 'CONFIRMED':
                    failures.append(f'{sid}: final state {st["state"]}')
                others = {s for s in per_part[-1]['statuses'] if s != 'PHYSICAL_ROUTE_CONFIRMED'}
                if not others <= {'NO_PENDING_ACTION', 'DUPLICATE_ACK_IGNORED', 'HTTP409'}:
                    failures.append(f'{sid}: unexpected statuses {sorted(others)}')

            # --- E13 explicit: exact replay of a consumed event id must be a 409, not a count
            first = next(r for r in pass_sensor.posted if r['interlock'] == 'PHYSICAL_ROUTE_CONFIRMED')
            rep = post_signed(c, '/hardware/bin-ack', {'event_id': first['event_id'], 'specimen_id': first['specimen_id'],
                              'station_id': 'sorter', 'bin_name': 'PASS', 'photoresistor_blocked': True}, 'sorter', sorter_device_key)
            if rep.status_code != 409:
                failures.append(f'exact replay of {first["event_id"]} returned {rep.status_code}, expected 409')

            # --- reboot id reuse: a fresh part arriving with an already-used millis() value
            reused = pass_sensor.posted[0]['event_id']
            stage_verified('act-reuse', 'S-reuse', 'PASS')
            r = post_signed(c, '/hardware/bin-ack', {'event_id': reused, 'specimen_id': 'S-reuse', 'station_id': 'sorter',
                            'bin_name': 'PASS', 'photoresistor_blocked': True}, 'sorter', sorter_device_key)
            reuse_result = {'http': r.status_code, 'route_state': status(c, 'act-reuse')['state']}
            if not (r.status_code == 409 and reuse_result['route_state'] == 'STAGED'):
                failures.append(f'reused event id after reboot: {reuse_result} (expected 409 + route left STAGED)')

            # --- E12: staged PASS, part lands in HOLD (bouncing), then is moved to PASS
            stage_verified('act-e12', 'S-e12', 'PASS')
            wrong = hold_sensor.bounce_burst('S-e12', edges=3, concurrent=rng.random() < 0.5)
            e12_state_after_wrong = status(c, 'act-e12')
            recover = pass_sensor.bounce_burst('S-e12', edges=2, concurrent=False)
            e12_state_after_move = status(c, 'act-e12')
            e12 = {'wrong_bin_statuses': [r['interlock'] for r in wrong], 'state_after_wrong': e12_state_after_wrong,
                   'after_move_statuses': [r['interlock'] for r in recover], 'state_after_move': e12_state_after_move['state']}
            if wrong[0]['interlock'] != 'ROUTE_MISMATCH' and 'ROUTE_MISMATCH' not in e12['wrong_bin_statuses']:
                failures.append(f'E12: no ROUTE_MISMATCH in {e12["wrong_bin_statuses"]}')
            if sum(s == 'ROUTE_MISMATCH' for s in e12['wrong_bin_statuses']) != 1:
                failures.append(f'E12: mismatch reported {e12["wrong_bin_statuses"].count("ROUTE_MISMATCH")} times, expected once')
            if e12_state_after_wrong['state'] != 'FAULTED' or e12_state_after_move['state'] != 'FAULTED':
                failures.append(f'E12: route state {e12_state_after_wrong["state"]} -> {e12_state_after_move["state"]}, expected FAULTED -> FAULTED')
            if any(s == 'PHYSICAL_ROUTE_CONFIRMED' for s in e12['after_move_statuses']):
                failures.append('E12: moving the part to the right bin afterwards produced a confirmation')

            # --- sensor fires with nothing staged (specimen_id mismatch between sketches)
            stray = pass_sensor.edge('S-never-staged')
            if stray['interlock'] != 'NO_PENDING_ACTION':
                failures.append(f'stray arrival: {stray}')

            # --- BACK-01 over the wire: unsigned, forged-key and replayed-envelope POSTs must bounce
            body = {'event_id': 'forged-1', 'specimen_id': 'S-000', 'station_id': 'sorter', 'bin_name': 'PASS', 'photoresistor_blocked': True}
            unsigned = c.post('/hardware/bin-ack', json=body).status_code
            forged = post_signed(c, '/hardware/bin-ack', body, 'sorter', secrets.token_hex(32)).status_code
            raw = json.dumps({**body, 'event_id': 'replay-env-1'}).encode()
            hdr = station_auth.sign(sorter_device_key, 'POST', '/hardware/bin-ack', 'sorter', raw)
            first_env = c.post('/hardware/bin-ack', content=raw, headers={**hdr, 'Content-Type': 'application/json'}).status_code
            replayed_env = c.post('/hardware/bin-ack', content=raw, headers={**hdr, 'Content-Type': 'application/json'}).status_code
            auth = {'unsigned': unsigned, 'forged_key': forged, 'first_envelope': first_env, 'replayed_envelope': replayed_env}
            if not (unsigned == 401 and forged == 401 and first_env == 200 and replayed_env == 401):
                failures.append(f'BACK-01 envelope checks: {auth}')

            # --- BACK-02/04 over the wire: no token / old asserted fields / unverified PASS refused; sorter poll = HOLD
            plain = {'action_id': 'act-gate', 'specimen_id': 'S-gate', 'bin': 'PASS', 'decision': 'AUTHORIZED_PASS', 'evidence_ids': []}
            raw_eid = 'evt-slot-unverified'
            post_signed(c, '/hardware/caliper-reading', {'event_id': raw_eid, 'specimen_id': 'S-gate', 'station_id': 'slot', 'adc_value': 2048,
                        'uncertainty_mm': 0.03, 'calibration_id': 'rehearsal-cal'}, 'slot', slot_device_key).raise_for_status()
            bearer = {'Authorization': f'Bearer {token}'}
            poll = post_signed(c, '/hardware/sorter/next-command', {'station_id': 'sorter', 'estop_loop_ok': True, 'guard_closed': True}, 'sorter', sorter_device_key)
            gates = {'no_token': c.post('/actuation/stage', json=plain).status_code,
                     'asserted_fields': c.post('/actuation/stage', json={**plain, 'approved': True, 'operator_id': 'x', 'origin': 'VERIFIED_PHYSICAL'}, headers=bearer).status_code,
                     'unverified_pass': c.post('/actuation/stage', json={**plain, 'evidence_ids': [raw_eid]}, headers=bearer).status_code,
                     'sorter_poll': poll.json().get('reason')}
            if gates != {'no_token': 401, 'asserted_fields': 422, 'unverified_pass': 403, 'sorter_poll': 'HARDWARE_DISABLED'}:
                failures.append(f'BACK-02/04 gate checks: {gates}')

        total_posts = len(pass_sensor.posted) + len(hold_sensor.posted)
        manifest = {
            'origin': 'TEST_FIXTURE', 'what_this_proves': 'server-side single-count / mismatch / replay behaviour under '
            'bounce, concurrency and millis() reset, over real HTTP. It does NOT exercise the photoresistor, the 4N35, '
            'or WiFi. Task item 4 (physical E12/E13) remains open until a `live` manifest exists.',
            'git_commit': git_commit(), 'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)),
            'seed': a.seed, 'parts': a.parts, 'total_sensor_posts': total_posts, 'elapsed_s': round(time.time() - started, 1),
            'per_part': per_part, 'exact_replay_http': rep.status_code, 'reboot_id_reuse': reuse_result, 'e12': e12,
            'stray_arrival': stray['interlock'], 'station_auth': auth, 'safety_gates': gates, 'failures': failures, 'verdict': 'PASS' if not failures else 'FAIL',
        }
        path = write_manifest('simulate', manifest)
        confirmed_total = sum(p['confirmed_count'] for p in per_part)
        print(f'parts={a.parts} sensor_posts={total_posts} confirmations={confirmed_total} '
              f'replay={rep.status_code} reboot_reuse={reuse_result["http"]} e12={e12_state_after_wrong["state"]}->{e12_state_after_move["state"]} '
              f'auth={auth} gates={gates}')
        for f in failures: print('FAIL', f)
        print(f'{manifest["verdict"]}  manifest: {path.relative_to(ROOT)}')
        return 0 if not failures else 1
    finally:
        server.terminate()
        try: server.wait(5)
        except subprocess.TimeoutExpired: server.kill()


# ----------------------------------------------------------------------------- live
def run_live(a) -> int:
    started = time.time()
    with httpx.Client(base_url=a.server) as c:
        health = c.get('/health', timeout=5).json()
        if 'sorter' not in health.get('hardware_stations_provisioned', []) or 'sorter' not in health.get('device_authenticated_stations', []):
            print('server lacks the sorter station key and/or device key; see PHYSICAL_TEST_PLAYBOOK.md'); return 2
        action_id = a.action_id or f'live-{int(time.time())}'
        if not a.operator_token:
            print('set QR_OPERATOR_TOKEN (or --operator-token) to your operator bearer token'); return 2
        print(stage(c, action_id, a.specimen, a.bin, a.operator_token, a.evidence_id))
        print(f'\nStaged {a.bin} for specimen {a.specimen} as {action_id}.')
        print('  E12: now physically drop the part in the WRONG bin.   expect FAULTED')
        print('  E13: drop it in the RIGHT bin and jostle it.           expect CONFIRMED, exactly once')
        print(f'Polling /actuation/{action_id} for {a.timeout}s ...')
        deadline = time.time() + a.timeout; final = status(c, action_id)
        while time.time() < deadline and final['state'] == 'STAGED':
            time.sleep(0.5); final = status(c, action_id)
        c.get('/health').json()  # placeholder for future ledger read endpoint
        manifest = {'origin': 'PHYSICAL_CAPTURE', 'git_commit': git_commit(), 'server': a.server, 'health': health,
                    'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)), 'action_id': action_id,
                    'specimen': a.specimen, 'staged_bin': a.bin, 'evidence_ids': a.evidence_id,
                    'operator': (final.get('binding') or {}).get('approved_by'), 'final': final,
                    'elapsed_s': round(time.time() - started, 1), 'operator_notes': a.notes,
                    'reminder': 'record the number of ACK POSTs seen on the ESP32 serial monitor for this drop; '
                                'server single-count is only meaningful alongside that number'}
        path = write_manifest('live', manifest)
        print(json.dumps(final, indent=2)); print(f'manifest: {path.relative_to(ROOT)}')
        return 0 if final['state'] in {'CONFIRMED', 'FAULTED'} else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='mode')
    sim = sub.add_parser('simulate'); sim.add_argument('--seed', type=int, default=2026); sim.add_argument('--parts', type=int, default=30)
    live = sub.add_parser('live'); live.add_argument('--server', required=True); live.add_argument('--specimen', required=True)
    live.add_argument('--bin', default='PASS', choices=['PASS', 'HOLD', 'REJECT'])
    live.add_argument('--operator-token', default=os.environ.get('QR_OPERATOR_TOKEN'), help='operator bearer token (default $QR_OPERATOR_TOKEN)')
    live.add_argument('--evidence-id', action='append', default=[], help='ledger event_id to cite; PASS/REJECT need a VERIFIED_PHYSICAL one')
    live.add_argument('--action-id'); live.add_argument('--timeout', type=float, default=120); live.add_argument('--notes', default='')
    # allow bare `--seed/--parts` without the subcommand word
    argv = sys.argv[1:]
    if not argv or argv[0].startswith('-'): argv = ['simulate', *argv]
    a = ap.parse_args(argv)
    return run_live(a) if a.mode == 'live' else run_simulate(a)


if __name__ == '__main__':
    raise SystemExit(main())
