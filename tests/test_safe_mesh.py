from dataclasses import replace
from qualityrelay17.demo import example_evidence
from qualityrelay17.contracts import sign_evidence
from qualityrelay17.safe_mesh import evaluate

def make(suspect=False):
    ev,keys,now=example_evidence(suspect_pi=suspect)
    return ev,keys,now

def decide(ev,keys,now):return evaluate('TAB-B12',ev,keys,now=now)

def resign(e,keys,**changes):
    d=e.unsigned();d.update(changes)
    return sign_evidence(type(e)(**d),keys[e.station_id])

def test_two_clear_requires_human_review():
    e,k,t=make(); assert decide(e,k,t).state=='PASS_REVIEW'

def test_one_suspect_is_hold():
    e,k,t=make(True);d=decide(e,k,t);assert d.state=='HOLD';assert 'VISUAL_PI_SUSPECT' in d.reasons

def test_second_camera_missing():
    e,k,t=make();d=decide([x for x in e if x.kind!='PI_IMAGE'],k,t);assert d.state=='HOLD'

def test_caliper_missing():
    e,k,t=make();assert decide([x for x in e if x.kind!='CALIPER'],k,t).state=='HOLD'

def test_cad_missing():
    e,k,t=make();assert decide([x for x in e if x.kind!='CAD_IMAGE'],k,t).state=='HOLD'

def test_assembly_missing():
    e,k,t=make();assert decide([x for x in e if x.kind!='ASSEMBLY'],k,t).state=='HOLD'

def test_duplicate_camera_image_root():
    e,k,t=make();pi=next(x for x in e if x.kind=='PI_IMAGE');e=[resign(pi,k,source_root='capture-phone-1') if x.event_id==pi.event_id else x for x in e]
    assert 'SHARED_IMAGE_ROOT' in decide(e,k,t).reasons

def test_bad_signature():
    e,k,t=make();e[0]=replace(e[0],verdict='clear',signature='bad')
    assert decide(e,k,t).state=='HOLD'

def test_stale_reading():
    e,k,t=make();d=decide(e,k,t+800);assert d.state=='HOLD'

def test_future_timestamp():
    e,k,t=make();d=decide(e,k,t-800);assert d.state=='HOLD'

def test_mixed_physical_and_synthetic():
    e,k,t=make();e[0]=resign(e[0],k,origin='SIMULATED')
    assert 'MIXED_ORIGINS' in decide(e,k,t).reasons

def test_no_real_pass_even_when_all_clear():
    e,k,t=make();assert decide(e,k,t).state!='PASS'

def test_ocr_not_verified():
    e,k,t=make();met=next(x for x in e if x.kind=='CALIPER');e=[resign(met,k,verdict='ocr_unverified') if x.event_id==met.event_id else x for x in e]
    assert decide(e,k,t).state=='HOLD'

def test_visual_quality_unusable():
    e,k,t=make();ph=next(x for x in e if x.kind=='PHONE_IMAGE');e=[resign(ph,k,verdict='unusable') if x.event_id==ph.event_id else x for x in e]
    assert decide(e,k,t).state=='HOLD'

def test_deduplicate_event_id():
    e,k,t=make();assert 'DUPLICATE_EVENT' in decide(e+[e[0]],k,t).reasons
