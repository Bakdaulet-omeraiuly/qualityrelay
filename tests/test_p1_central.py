"""P1 central architecture: default behaviour unchanged; uplink and outage mechanics."""
from dataclasses import replace
from qualityrelay17.sim.engine import Factory, calibrate_part_model
from qualityrelay17.sim.scenarios import BY_ID

M = calibrate_part_model()
SC = replace(BY_ID['F01'], n_pairs=40)


def test_fast_uplink_central_equals_local_decisions():
    a = Factory(SC, 1, 'bayes', 'optimized', model=M); a.run()
    b = Factory(SC, 1, 'bayes', 'optimized', model=M, architecture='central', uplink_mbps=10_000); rb = b.run()
    assert [p['decision'] for p in a.pairs] == [p['decision'] for p in b.pairs]
    assert rb['net_bytes'] > 40 * 2 * 2_000_000 and rb['holds_missing_central'] == 0


def test_advance_skips_outage_windows():
    f = Factory(SC, 1, 'bayes', 'optimized', model=M, architecture='central', central_outages=((10.0, 20.0), (30.0, 40.0)))
    assert f._advance(0.0, 5.0) == 5.0
    assert f._advance(8.0, 5.0) == 23.0      # 2 s before the outage, 3 s after it
    assert f._advance(15.0, 12.0) == 42.0    # starts in an outage, crosses the second one
    assert f._central_up_at(35.0) == 40.0 and f._central_up_at(25.0) == 25.0


def test_slow_uplink_causes_missing_evidence_holds():
    r = Factory(SC, 1, 'bayes', 'optimized', model=M, architecture='central', uplink_mbps=1.0).run()
    assert r['holds_missing_central'] > 0 and r['conservation_ok']
