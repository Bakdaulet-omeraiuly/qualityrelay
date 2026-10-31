"""Deterministic safety-first policy; deliberately conservative, not claimed optimal."""
from __future__ import annotations
from .contracts import Evidence, Decision, signature_valid

VISUAL={'PHONE_IMAGE':'phone','PI_IMAGE':'pi'}

def evaluate(specimen_id: str, records:list[Evidence], keys:dict[str,str], *, now:float,
             max_age_s:float=600, require_two_cameras=True, require_cad=True, require_assembly=True) -> Decision:
    reasons=[]; used=[]
    items=[x for x in records if x.specimen_id==specimen_id]
    if not items: return Decision(specimen_id,'HOLD',('NO_EVIDENCE',),())
    origins={x.origin for x in items}
    mode=next(iter(origins)) if len(origins)==1 else 'TEST_FIXTURE'
    if len(origins)>1: reasons.append('MIXED_ORIGINS')
    if len({x.event_id for x in items})!=len(items): reasons.append('DUPLICATE_EVENT')
    trusted=[]
    for x in items:
        if not signature_valid(x,keys):
            reasons.append('BAD_SIGNATURE:'+x.event_id);continue
        if x.observed_at>now+10 or now-x.observed_at>max_age_s:
            reasons.append('STALE_OR_FUTURE:'+x.event_id);continue
        trusted.append(x);used.append(x.event_id)
    # A source_root appearing at different stations is not two independent measurements.
    visual={}
    for kind, station in VISUAL.items():
        group=[x for x in trusted if x.kind==kind]
        if len(group)!=1:
            reasons.append('REQUIRED_'+station.upper()+'_COUNT');continue
        visual[station]=group[0]
        if group[0].verdict!='clear': reasons.append('VISUAL_'+station.upper()+'_'+group[0].verdict.upper())
        if not group[0].calibration_id: reasons.append('UNCALIBRATED_'+station.upper())
    if 'phone' in visual and 'pi' in visual:
        if visual['phone'].station_id==visual['pi'].station_id: reasons.append('SAME_STATION')
        if visual['phone'].source_root==visual['pi'].source_root: reasons.append('SHARED_IMAGE_ROOT')
    if require_two_cameras and len(visual)<2: reasons.append('MISSING_CAMERA_EVIDENCE')
    cad=[x for x in trusted if x.kind=='CAD_IMAGE']
    if require_cad and len(cad)!=1: reasons.append('MISSING_CAD_COMPARISON')
    for x in cad:
        if x.verdict!='clear' or not x.calibration_id: reasons.append('UNCERTAIN_CAD')
    met=[x for x in trusted if x.kind=='CALIPER' and x.verdict=='verified']
    if len(met)!=1: reasons.append('MISSING_VERIFIED_METROLOGY')
    else:
        x=met[0]
        if not x.payload.get('validated') or x.payload.get('unit')!='mm': reasons.append('UNVERIFIED_METROLOGY')
        u=x.payload.get('uncertainty_mm')
        if not isinstance(x.payload.get('measurement_mm'),(int,float)) or not isinstance(u,(int,float)) or u<0:
            reasons.append('INVALID_METROLOGY')
    assembly=[x for x in trusted if x.kind=='ASSEMBLY']
    if require_assembly and len(assembly)!=1:reasons.append('MISSING_ASSEMBLY')
    for x in assembly:
        if x.verdict!='pass' or not x.payload.get('validated'): reasons.append('ASSEMBLY_NOT_VERIFIED')
    # Only approve a REVIEW (never PASS or actuation), no rejected output solely from ML classification.
    available=sum([len(visual)>=2,len(cad)==1,len(met)==1,len(assembly)==1])/4
    return Decision(specimen_id,'HOLD' if reasons else 'PASS_REVIEW',tuple(sorted(set(reasons))),tuple(sorted(used)),
                    action_requested='REVIEW_OR_REINSPECT' if reasons else 'HUMAN_AUTHORIZATION',
                    evidence_coverage=available,mode=mode)
