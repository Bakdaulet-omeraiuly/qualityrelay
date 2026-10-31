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
    python scripts/rehearse_e12_e13.py live --server http://192.168.1.20:8000 --specimen S-7 --bin PASS
"""
from __future__ import annotations
import argparse, json, os, random, secrets, socket, subprocess, sys, threading, time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'examples' / 'results' / 'rehearsal_e12_e13'


# ----------------------------------------------------------------------------- sensor model
class FakeBinSensor:
    """Mimics bin_sensor.ino's observable behaviour: a POST per rising edge, event_id built from
    STATION_ID + millis(). millis() restarts from ~0 on reboot(), which is exactly the id-reuse
    hazard the firmware comment warns about."""

    def __init__(self, client: httpx.Client, bin_name: str, rng: random.Random):
        self.client, self.bin_name, self.rng = client, bin_name, rng
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
        r = self.client.post('/hardware/bin-ack', json=body, timeout=10)
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
def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


def git_commit() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except Exception:
        return 'unknown'


def stage(client: httpx.Client, action_id: str, specimen_id: str, bin_name: str, operator: str) -> dict:
    decision = {'PASS': 'AUTHORIZED_PASS', 'REJECT': 'CONFIRMED_REJECT', 'HOLD': 'HOLD'}[bin_name]
    r = client.post('/actuation/stage', json={'action_id': action_id, 'specimen_id': specimen_id, 'bin': bin_name,
                                              'decision': decision, 'operator_id': operator, 'approved': True,
                                              'origin': 'VERIFIED_PHYSICAL'}, timeout=10)
    r.raise_for_status(); return r.json()


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
    env = {**os.environ, 'SORTER_STATION_KEY': secrets.token_hex(32), 'SLOT_STATION_KEY': secrets.token_hex(32),
           'HARDWARE_LEDGER_PATH': ':memory:'}
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

            pass_sensor = FakeBinSensor(c, 'PASS', rng)
            hold_sensor = FakeBinSensor(c, 'HOLD', rng)
            per_part: list[dict] = []

            # --- E13 under bounce: many parts, each one staged PASS route, each arrival bounces
            for i in range(a.parts):
                sid, aid = f'S-{i:03d}', f'act-{i:03d}'
                stage(c, aid, sid, 'PASS', 'rehearsal')
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
            rep = c.post('/hardware/bin-ack', json={'event_id': first['event_id'], 'specimen_id': first['specimen_id'],
                                                    'station_id': 'sorter', 'bin_name': 'PASS', 'photoresistor_blocked': True})
            if rep.status_code != 409:
                failures.append(f'exact replay of {first["event_id"]} returned {rep.status_code}, expected 409')

            # --- reboot id reuse: a fresh part arriving with an already-used millis() value
            reused = pass_sensor.posted[0]['event_id']
            stage(c, 'act-reuse', 'S-reuse', 'PASS', 'rehearsal')
            r = c.post('/hardware/bin-ack', json={'event_id': reused, 'specimen_id': 'S-reuse', 'station_id': 'sorter',
                                                  'bin_name': 'PASS', 'photoresistor_blocked': True})
            reuse_result = {'http': r.status_code, 'route_state': status(c, 'act-reuse')['state']}
            if not (r.status_code == 409 and reuse_result['route_state'] == 'PENDING'):
                failures.append(f'reused event id after reboot: {reuse_result} (expected 409 + route left PENDING)')

            # --- E12: staged PASS, part lands in HOLD (bouncing), then is moved to PASS
            stage(c, 'act-e12', 'S-e12', 'PASS', 'rehearsal')
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

        total_posts = len(pass_sensor.posted) + len(hold_sensor.posted)
        manifest = {
            'origin': 'TEST_FIXTURE', 'what_this_proves': 'server-side single-count / mismatch / replay behaviour under '
            'bounce, concurrency and millis() reset, over real HTTP. It does NOT exercise the photoresistor, the 4N35, '
            'or WiFi. Task item 4 (physical E12/E13) remains open until a `live` manifest exists.',
            'git_commit': git_commit(), 'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)),
            'seed': a.seed, 'parts': a.parts, 'total_sensor_posts': total_posts, 'elapsed_s': round(time.time() - started, 1),
            'per_part': per_part, 'exact_replay_http': rep.status_code, 'reboot_id_reuse': reuse_result, 'e12': e12,
            'stray_arrival': stray['interlock'], 'failures': failures, 'verdict': 'PASS' if not failures else 'FAIL',
        }
        path = write_manifest('simulate', manifest)
        confirmed_total = sum(p['confirmed_count'] for p in per_part)
        print(f'parts={a.parts} sensor_posts={total_posts} confirmations={confirmed_total} '
              f'replay={rep.status_code} reboot_reuse={reuse_result["http"]} e12={e12_state_after_wrong["state"]}->{e12_state_after_move["state"]}')
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
        if 'sorter' not in health.get('hardware_stations_provisioned', []):
            print('server has no sorter key provisioned; see PHYSICAL_TEST_PLAYBOOK.md'); return 2
        action_id = a.action_id or f'live-{int(time.time())}'
        print(stage(c, action_id, a.specimen, a.bin, a.operator))
        print(f'\nStaged {a.bin} for specimen {a.specimen} as {action_id}.')
        print('  E12: now physically drop the part in the WRONG bin.   expect FAULTED')
        print('  E13: drop it in the RIGHT bin and jostle it.           expect CONFIRMED, exactly once')
        print(f'Polling /actuation/{action_id} for {a.timeout}s ...')
        deadline = time.time() + a.timeout; final = status(c, action_id)
        while time.time() < deadline and final['state'] == 'PENDING':
            time.sleep(0.5); final = status(c, action_id)
        rows = c.get('/health').json()  # placeholder for future ledger read endpoint
        manifest = {'origin': 'PHYSICAL_CAPTURE', 'git_commit': git_commit(), 'server': a.server, 'health': health,
                    'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)), 'action_id': action_id,
                    'specimen': a.specimen, 'staged_bin': a.bin, 'operator': a.operator, 'final': final,
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
    live.add_argument('--bin', default='PASS', choices=['PASS', 'HOLD', 'REJECT']); live.add_argument('--operator', default=os.environ.get('USERNAME') or 'operator')
    live.add_argument('--action-id'); live.add_argument('--timeout', type=float, default=120); live.add_argument('--notes', default='')
    # allow bare `--seed/--parts` without the subcommand word
    argv = sys.argv[1:]
    if not argv or argv[0].startswith('-'): argv = ['simulate', *argv]
    a = ap.parse_args(argv)
    return run_live(a) if a.mode == 'live' else run_simulate(a)


if __name__ == '__main__':
    raise SystemExit(main())
