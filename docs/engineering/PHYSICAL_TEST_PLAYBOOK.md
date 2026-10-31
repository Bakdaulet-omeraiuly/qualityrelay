# Physical test playbook — ESP32/Pi hardware, 31 October 2026

Owner for execution: **HyorinmaruK** (physical test + sorter per `TEAM_OWNERSHIP_AND_GITHUB.md`).
Anything here that touches `qualityrelay17/{api,hardware_ingest,actuation}.py` is
**adilnurgg's** reviewed module; anything touching `factory`/`benchmark`/`vder` is
**Bakdaulet's** — wire the hardware, but route code changes through the normal PR review,
same as any other change (2 reviewers for anything actuation/auth/safety-adjacent).

This playbook assumes the code changes already in this ZIP: `qualityrelay17/hardware_ingest.py`,
the two new endpoints in `api.py` (`/hardware/caliper-reading`, `/hardware/bin-ack`), and the
two reference sketches in `firmware/esp32_station/`.

## 0. An honest note on the potentiometer before you build anything

A panel-mount "precision potentiometer" is not automatically a dimensional sensor — it only
measures shaft rotation. There are two legitimate ways to use it, and they are **not
interchangeable**:

- **Tier A (today, no mechanical build required):** keep using the real digital caliper for
  the actual ground-truth width. The potentiometer becomes a live **fault-injection dial** —
  turning it shifts a simulated process mean on the dashboard during the demo, or lets an
  operator manually dial in the number they just read off the caliper. This is honest, fast,
  and matches everything this project already says about not pretending synthetic/manual
  input is a calibrated instrument.
- **Tier B (stretch, only if time remains):** build an actual feeler-arm linkage (a small
  printed or bent-wire lever, spring-loaded against the specimen, turning the pot shaft
  proportionally to width) so the pot becomes a real analog proxy transducer. **If you do
  this, it still has to pass the exact same repeatability screen as any other instrument below
  before a single reading from it is trusted as evidence** — a mechanical linkage you built in
  an afternoon is not assumed-accurate just because it is "hardware."

Pick Tier A unless Tier B is clearly finished and screened with hours to spare. Don't let a
half-built linkage become your single point of failure for the live demo.

## 1. Before anything is wired: the repeatability screen (do this first, always)

This produces the `uncertainty_mm` value the firmware currently sends as a placeholder
(`0.05`, in `esp32_station.ino`) — replace that literal with your measured number before
trusting a single live reading as more than a reference wiring demo.

1. Pick one specimen. Measure it with the real caliper, write the number down.
2. Reseat and re-read **10 times**, fully removing and repositioning the caliper (or the
   Tier-A dial, or the Tier-B linkage) between reads. Do not just loosen and re-tighten.
3. Compute the sample standard deviation of those 10 reads. That is your `uncertainty_mm` —
   not a guess, not the previous blueprint's illustrative `0.05`.
4. If your intended demo fault magnitude is not comfortably larger (3–5×) than this number,
   you will not be able to tell signal from your own measurement noise on stage. Fix the
   fixture or the magnitude now, not during the demo.
5. Do the same 10-read screen with a **second operator or instrument** if you have time —
   operator-to-operator variation is usually larger than either operator's own repeatability.

## 2. Station wiring (matches `firmware/esp32_station/`)

| Station | Hardware | Produces | API route |
|---|---|---|---|
| Slot / Tab (Tier A) | ESP32, button, 74HC595+LEDs, buzzer, (potentiometer as fault dial, Tier A) | `CALIPER` evidence, `origin=PHYSICAL_CAPTURE` | `POST /hardware/caliper-reading` |
| Sorter bin ACK | Photoresistor + 4N35 (isolated), separate ESP32 or shared one on another pin | `ROUTE_ACK` evidence | `POST /hardware/bin-ack` |
| Phone Vision | Phone camera, existing web upload path | `PHONE_IMAGE` evidence | existing site/API |
| Pi Vision | Raspberry Pi 5 + Hailo-8L + ESP32 camera module | `PI_IMAGE` evidence | existing site/API (wire once the model is ready — see `TOMORROW_TASKS.md`) |

**Before either new endpoint will sign anything**, per-station secrets must be provisioned.
They are never written into `api.py`: `HARDWARE_STATION_KEYS` is loaded at import time from
`SLOT_STATION_KEY`, `TAB_STATION_KEY`, `SORTER_STATION_KEY` (and `PHONE_/PI_/CAD_STATION_KEY`
once those stations are wired), taken from the real environment first and a git-ignored `.env`
at the repo root second. Generate them on the demo server with

```
python scripts/provision_station_keys.py            # slot tab sorter; add --rotate to replace
```

A station with no key answers `503` (the cold state `tests/test_api.py` pins); a key shorter
than 32 chars is refused at startup rather than used. `GET /health` lists which stations are
provisioned so you can check from the floor without reading the file.

**Every hardware POST must carry the per-device signed envelope** (task board BACK-01,
`qualityrelay17/station_auth.py`). Each station has *two* secrets: a `*_DEVICE_KEY` that is
flashed onto its ESP32 and only proves "this came from station X", and the server-only
`*_STATION_KEY` that signs the Evidence afterwards. Flash the device key with

```
python scripts/provision_station_keys.py --show-device-key sorter   # paste into STATION_DEVICE_KEY
```

The sketches add `X-Station-Id / -Timestamp / -Nonce / -Signature` (HMAC-SHA256 over method, path,
station, unix time, nonce and the body hash) and refuse to send until NTP has set the clock.
What the codes mean on the floor: `401` = envelope rejected (wrong device key, clock more than
60 s off, nonce reused, body altered in flight); `403` = that station is not allowed on that path
(e.g. the sorter posting a caliper reading) or the body's `station_id` disagrees with the
authenticated one. Both happen *before* anything is signed or stored. `GET /health` lists
`device_authenticated_stations` next to `hardware_stations_provisioned`; both lists must contain a
station for its readings to be accepted.

Every accepted reading is appended to the API's evidence ledger (`api.HARDWARE_LEDGER`) before
the signed object is returned. The ledger is in-memory by default, so **set
`HARDWARE_LEDGER_PATH` to a file in `.env` for any session whose readings you want to keep**
(the repeatability screen, the E12/E13 bin tests). A repeated `event_id` gets `409` and is not
re-signed: that is the replay guard, so a `409` during a live run means a duplicate POST or a
rebooted ESP32 re-using `millis()`-based IDs, not a server fault. A `422` means the ingest
layer refused the reading (e.g. bin-ack with no part detected) and nothing was recorded.

### Sensor fired -> route confirmed (the live loop)

0. Have a provisioned operator token (`python scripts/provision_station_keys.py --operators <you>`,
   then `--show-operator-token <you>`) and export it as `QR_OPERATOR_TOKEN`. Approval and identity come
   from that token now. The old `operator_id` / `approved` / `origin` body fields are refused with `422` (BACK-04).
1. For PASS or REJECT, verify the reading you will cite first: take the caliper reading at the station, then
   follow `GROUND_TRUTH_VERIFICATION_PROCEDURE.md` (GT-CAL-01) so that `GET /evidence/<event_id>/status` shows
   `effective_origin: VERIFIED_PHYSICAL`. A HOLD route only needs the authenticated reading (BACK-02).
2. Stage the route (STAGED_ONLY, nothing moves). It expires after `ACTUATION_STAGE_TTL_S`, 600 s by default:
   `POST /actuation/stage` with header `Authorization: Bearer $QR_OPERATOR_TOKEN` and body
   `{"action_id":"act-1","specimen_id":"S-7","bin":"PASS","decision":"AUTHORIZED_PASS","evidence_ids":["<event_id>"]}`.
   `403` means the evidence gate refused: the detail says which record and why.
3. Drop the part **after** staging. The bin sensor ESP32 posts `/hardware/bin-ack` with its own `event_id`.
   Its signed envelope timestamp is the sensing time. A detection from before the approval (for example a
   part already sitting in the bin) cannot confirm the route.
4. The server persists that ROUTE_ACK and binds it to the single in-flight route for that specimen (or to
   `action_id` if the sketch sends one). It only accepts a *recorded*, station-authenticated ROUTE_ACK for the
   same specimen and bin, inside the action's time window. One sensor event can bind at most one action, and
   that holds across restarts. If two routes are in flight for one specimen, the response is `AMBIGUOUS_ACK`
   and the server does not guess.
5. `GET /actuation/act-1` -> `CONFIRMED` / `FAULTED` / `STAGED` / `EXPIRED`, with the full `binding`
   (action, specimen, sorter station, requested vs actual bin, sensor event, sensed/approved times, approver).
   Read it out loud on stage; it is the proof the ACK path is independent of the command path.
6. **Identity:** `specimen_identity` stays `NOT_PROVEN`, because the LDR only proves that *an object* arrived.
   Pick the part out of the bin, read its label, and
   `POST /actuation/act-1/identity {"observed_specimen_id":"S-7"}` (same bearer token). A different label
   latches `FAULTED / IDENTITY_MISMATCH`. `GET /actuation/journal/act-1` shows every transition.

If the sensor fires with nothing staged for that specimen you get `NO_PENDING_ACTION`: the reading
is kept, but there was no route to confirm — usually a `specimen_id` mismatch between the two sketches.

### Running E12/E13 for real (`scripts/rehearse_e12_e13.py live`)

```
python scripts/rehearse_e12_e13.py live --server http://<server>:8000 --specimen S-7 --bin PASS
```

It stages the route, prints what to do physically, polls `/actuation/{id}` until `CONFIRMED` or
`FAULTED`, and writes a `PHYSICAL_CAPTURE` manifest to `examples/results/rehearsal_e12_e13/`.
Run it once per case: E12 (drop in the wrong bin -> `FAULTED`), E13 (right bin, jostle ->
`CONFIRMED` once). Write down how many `ACK POST ->` lines the ESP32 serial monitor printed for
each drop — that number, next to the server's single confirmation, is the bounce evidence.

The same script with no subcommand is the hardware-free rehearsal (fake sensor with bounce,
concurrency and `millis()` reset against a real local server). It passed 31 Oct and caught a
concurrency bug in the interlock; its manifests are `TEST_FIXTURE`, not a physical result.

Known firmware gaps that the live run will hit (owner: HyorinmaruK, `bin_sensor.ino`):
- `specimen_id` is a local counter (`S-1`, `S-2`, ...). It will never match a staged specimen,
  so every real ACK is `NO_PENDING_ACTION` until the sketch carries the real specimen id. For the
  demo, stage with the id the sketch will send next, or hard-code one for the rehearsal part.
- `event_id` is `millis()`-based with no boot nonce; after a reboot ids repeat and the server
  answers `409`. Add `esp_random()` (or chip id + boot counter) to the id string.
- No debounce window: a 50 ms poll with rising-edge detection will post several times per
  arrival if the LDR hovers at threshold. The server counts once regardless, but add a
  ~300 ms lockout after a rising edge to keep the serial log readable. Provisioned on
adilnurgg's machine 31 Oct for `slot`, `tab`, `sorter`; the server that runs the demo needs its
own run of the script (or the same `.env` copied over out-of-band, never through git).

## 3. The physical acceptance tests to actually run

A subset of `docs/research/EXPERIMENT_PROTOCOL.md`'s E01–E15 can and should be run physically,
not just in code:

| Test | What to do | Expected |
|---|---|---|
| E02 — Pi offline | Unplug the Pi mid-run, keep sending slot/tab readings | Slot/tab stations keep accepting readings; `safe_mesh.evaluate` returns `HOLD` with `MISSING_CAMERA_EVIDENCE`, not a crash |
| E07 — blurred image | Deliberately defocus the phone or ESP32-CAM shot | `vision.compare_reference` output is `calibrated:false`; disposition is HOLD/recapture, never a confident pass |
| E12 — wrong physical bin | `POST /actuation/stage` a `PASS` route for the part, physically drop it in the `HOLD` bin instead | `bin-ack` response `interlock.status` is `ROUTE_MISMATCH` (HTTP 200: the sensor reading is real and stays in the ledger); `GET /actuation/{action_id}` shows `FAULTED`; a later drop into `PASS` does **not** recover it — re-stage under a new `action_id` |
| E13 — duplicate ACK | Trigger the bin sensor twice for one part (e.g., let it settle and jostle) | First trigger: `PHYSICAL_ROUTE_CONFIRMED`. Second trigger (new `event_id`): `NO_PENDING_ACTION`, route still counted once. Exact replay of the same `event_id`: HTTP `409`. Never a second confirmation |
| New — isolation check | With the ESP32 actuation/status logic intentionally powered off or disconnected, confirm the bin sensor circuit still independently reports a block | This is your concrete proof that the ACK path is actually isolated from the command path, not just documented as isolated |

Run each of these **once well before judges arrive** and again as part of your dry run — a
test you've only run once isn't a reliable live demo.

## 4. Safety notes specific to these parts

- PN2222 collector current is limited (~600 mA absolute max, far less sustained) — fine for
  LEDs/buzzer, not for a motor or solenoid. Don't wire a real sorter motor through it.
- Put a diode across the buzzer leads if it has any internal coil (most small "active"
  buzzers do) — flyback protection, cheap insurance.
- `actuation.py` still has *no GPIO path at all*. The server never drives a pin. For the demo, keep the
  designed behaviour: a human moves the part after seeing the approved route. Do not add a servo/relay under
  time pressure.
- **An AI never moves a part.** LLM planners and `safe_mesh` can at most `POST /actuation/propose`, which
  creates a `PROPOSED` action that has no timer and no command. Only an authenticated operator can approve it
  (`POST /actuation/{id}/approve`), and the evidence gate runs again at approval. Machine identities
  (`llm:*`, `agent:*`, `ai:*`, `safe_mesh`) are refused as approvers. `tests/test_actuation_safety.py` also
  checks statically that no collective/LLM/agent module imports the interlock.
- **If a powered sorter is ever attached (owner HyorinmaruK, reviewed by adilnurgg), it must meet ALL of
  these. Software cannot provide any of them:**
  1. A hard-wired E-stop (latching mushroom button) that cuts **actuator power** directly, not through the ESP32.
     Its auxiliary contact is read by the ESP32 and reported as `estop_loop_ok`.
  2. A guard/cover switch in series with actuator power, reported as `guard_closed`.
  3. Mechanical default to HOLD: spring-return or gravity so that an unpowered gate diverts to HOLD. Power loss
     or a brown-out then lands parts in HOLD.
  4. On boot, the firmware drives the gate to HOLD before connecting to WiFi. Any error, lost connection, or
     invalid or expired command also means HOLD.
  5. Pull model only. The device polls `POST /hardware/sorter/next-command` with its signed envelope and
     `{"station_id","estop_loop_ok","guard_closed","position"}`. It moves only for `"command":"ROUTE"`, only
     if `signature` = HMAC-SHA256(device key, `ROUTE\n<station>\n<action_id>\n<specimen_id>\n<bin>\n<command_nonce>\n<issued_at>\n<expires_at>`)
     verifies, only if `expires_at` has not passed on its NTP clock, and only if it has not executed that
     `command_nonce` before.
  6. The bin-ACK sensor stays a separate circuit. The sorter does not report its own success.
- **Server-side gates (already enforced):** `ACTUATION_HARDWARE_ENABLED` is off by default, and while it is
  off every poll answers `HOLD / HARDWARE_DISABLED`. Even with it on, an operator must `POST /actuation/arm`.
  `POST /actuation/estop` needs **no token** (stopping is the fail-safe direction). It latches, disarms, aborts
  staged routes and faults any route in motion. A device reporting `estop_loop_ok:false` latches it too.
  Reset needs a token and does **not** re-arm. Only one route is in motion at a time. A dispatched route with
  no bin ACK within `ACTUATION_ACK_TIMEOUT_S` (30 s) → `FAULTED / ACK_TIMEOUT` plus disarm. A server restart
  closes every non-terminal route as `EXPIRED` or `FAULTED / SERVER_RESTART_DURING_MOTION`, so nothing
  resumes without a new approval.
- Never power the ESP32 logic pins from anything other than 3.3V; the 74HC595 and LEDs are
  fine at 3.3V logic level but double-check your specific LED forward voltages against the
  resistor values you picked out of the 120-piece pack.
