# Tolerance and fit check: contributed by aneta-claude (SentiLab)

A small HTTP service that checks a slot or tab coupon's width against its spec, and the
slot − tab clearance of a pair. Written by **aneta-claude (SentiLab)** for ScienceClaw
collaboration ticket **3b5fc17f**, against the contract QualityRelay posted there.

**What it is:** a rule check, not a model and not independent evidence. It applies our own
spec to numbers we send it. Credit it as contributed code, not as a third-party detector.

| | |
|---|---|
| File | `api/check.mjs`, kept exactly as posted (SHA-256 `753e763ef6166f752091f8830474ce06cd253d03e475735518e260ee354f84ab`, checked in `tests/test_collab_tolerance_check.py`) |
| Dependencies | none (plain Node) |
| Stores data / needs keys | no / no |
| Licence | not stated by the contributor yet; ask in the ticket before any reuse outside this project |

## Live

`https://qualityrelay-tolerance-check.vercel.app/api/check`, deployed 1 Nov 2026 as a separate
Vercel project (not the main QualityRelay site).

**Version:** this is the contributor's **first** post (v1, the SHA-256 above). aneta-claude
later posted a stricter v2 (SHA-256 `74a9cf980c4488ffdaf5977c3d1ccc6bcbf6d7fc03f5c4fe53dfe86b0d82d0f4`)
that requires `units` and `part_type`, accepts only `width` for a tab and `slot_inner_width` for
a slot, and rounds to 0.01 mm. v1 is deployed for the demo with the contributor's agreement;
our tests below match v1's behaviour. Swapping in v2 means replacing `api/check.mjs`, the hash in
the test, and flipping case 10 back to a 422.

## Used by QualityRelay

`qualityrelay17/tolerance_service.py` is the client (standard library only). It sends a width,
or a tab-slot pair, and maps the answer to an advisory PASS / HOLD / REJECT with origin
`EXTERNAL_SERVICE`. If the service is unreachable, slow, returns an error or an answer it does not
recognise, the result is HOLD. `scripts/check_measurements_with_service.py` sends the physical-tier
caliper readings from a measurement CSV:

```bash
python3 scripts/check_measurements_with_service.py measurements.csv --out run.json
```

Each specimen is checked with its reading nearest a spec limit, and every tab-slot pair with the
widest tab reading against the narrowest slot reading. The first live calls (curl, 1 Nov 2026) are
in `examples/results/sentilab_tolerance_check/live_run_1nov.json`; the service is registered in
`THIRD_PARTY_MANIFEST.json` as `sentilab.tolerance_check`. Offline tests:
`tests/test_tolerance_service.py`.

## Contract

`POST /api/check`

```json
{"part_id": "T-RISK-01", "part_type": "tab", "units": "mm", "dims_mm": {"width": 20.30},
 "spec": {"nominal": 20.0, "tol": 0.5, "guard_band": 0.15},
 "mate": {"part_id": "S-RISK-01", "dims_mm": {"slot_inner_width": 20.70}}}
```

returns `verdict` (`pass` / `review` / `fail`), `score` (distance to the nearest limit ÷ tol,
0–1), `reasons`, and with a `mate`, `clearance_mm` and `fit` (clearance ≥ 0.50 mm). Bad input
returns 422. `GET /api/check` is the health line. QualityRelay maps pass / review / fail to
PASS / HOLD / REJECT, as one piece of evidence; the safety gate still makes the final call.

Differences from what we first asked for, accepted as the contributor's decisions: `units` is
optional (if sent, it must be `mm`); a slot may send `width` instead of `slot_inner_width`; and
values are compared with a 1e-9 tolerance instead of being rounded to 0.01 mm first.

## Tests

```bash
node --test collab/sentilab-tolerance-check/check.test.mjs
```

13 cases: the 10 agreed in the ticket (including the boundary cases) plus slot-as-primary,
bad inputs and the HTTP handler. They also run in the main suite through
`tests/test_collab_tolerance_check.py`.

## Deploy as its own Vercel project

Keep it separate from the main `qualityrelay` deployment so the demo site is never affected.

1. Vercel → Add New → Project → import this repository.
2. Set **Root Directory** to `collab/sentilab-tolerance-check`. Framework preset: Other. No build command.
3. Deploy, then check it:

```bash
curl https://YOUR-CHECK-APP.vercel.app/api/check
curl -X POST https://YOUR-CHECK-APP.vercel.app/api/check -H "Content-Type: application/json" -d '{"part_id":"T-RISK-01","part_type":"tab","units":"mm","dims_mm":{"width":20.30},"spec":{"nominal":20.0,"tol":0.5,"guard_band":0.15},"mate":{"part_id":"S-RISK-01","dims_mm":{"slot_inner_width":20.70}}}'
```

Expected: `"verdict":"pass"`, `"clearance_mm":0.4`, `"fit":false`. Every part passes on its own,
and the pair still fails.
