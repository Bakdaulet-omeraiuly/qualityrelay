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

**Before either new endpoint will sign anything**, `adilnurgg` has to populate
`HARDWARE_STATION_KEYS` in `api.py` with real per-station secrets (it's intentionally empty —
both endpoints currently return `503` by design, confirmed by `tests/test_api.py`). Agree on
station secrets as a team before the demo, not during it.

## 3. The physical acceptance tests to actually run

A subset of `docs/research/EXPERIMENT_PROTOCOL.md`'s E01–E15 can and should be run physically,
not just in code:

| Test | What to do | Expected |
|---|---|---|
| E02 — Pi offline | Unplug the Pi mid-run, keep sending slot/tab readings | Slot/tab stations keep accepting readings; `safe_mesh.evaluate` returns `HOLD` with `MISSING_CAMERA_EVIDENCE`, not a crash |
| E07 — blurred image | Deliberately defocus the phone or ESP32-CAM shot | `vision.compare_reference` output is `calibrated:false`; disposition is HOLD/recapture, never a confident pass |
| E12 — wrong physical bin | Stage a `PASS` route, physically drop the part in the `HOLD` bin instead | `actuation.SorterInterlock.acknowledge` must raise on the bin mismatch — confirm it actually does, live |
| E13 — duplicate ACK | Trigger the bin sensor twice for one part (e.g., let it settle and jostle) | Second `bin-ack` POST for the same `action_id` must come back `DUPLICATE_ACK_IGNORED`, not double-counted |
| New — isolation check | With the ESP32 actuation/status logic intentionally powered off or disconnected, confirm the bin sensor circuit still independently reports a block | This is your concrete proof that the ACK path is actually isolated from the command path, not just documented as isolated |

Run each of these **once well before judges arrive** and again as part of your dry run — a
test you've only run once isn't a reliable live demo.

## 4. Safety notes specific to these parts

- PN2222 collector current is limited (~600 mA absolute max, far less sustained) — fine for
  LEDs/buzzer, not for a motor or solenoid. Don't wire a real sorter motor through it.
- Put a diode across the buzzer leads if it has any internal coil (most small "active"
  buzzers do) — flyback protection, cheap insurance.
- `actuation.py` currently has *no GPIO path at all* ("No hardware IO" is in its own
  docstring) — it only stages requests and waits for an ACK. Keep it that way for the demo;
  do not add a live servo/relay command path under time pressure. A human physically moving
  the part after seeing the dashboard's recommendation is the correct, already-designed
  behavior, not a missing feature.
- Never power the ESP32 logic pins from anything other than 3.3V; the 74HC595 and LEDs are
  fine at 3.3V logic level but double-check your specific LED forward voltages against the
  resistor values you picked out of the 120-piece pack.
