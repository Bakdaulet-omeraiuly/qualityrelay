"""Run via `python -m qualityrelay17.demo` from project root."""
import json, time
from .contracts import Evidence,sign_evidence
from .safe_mesh import evaluate
from .factory import compare_policies
from .matching import optimize_pairs
from .vder import Inspection,action_scores

def example_evidence(suspect_pi=True,origin='TEST_FIXTURE'):
    now=1000.
    keys={'phone':'dev-phone-secret','pi':'dev-pi-secret','cad':'dev-cad-secret','met':'dev-met-secret','assembly':'dev-assembly-secret'}
    row=[('p1','phone','PHONE_IMAGE','clear','capture-phone-1','ref-good'),('p2','pi','PI_IMAGE','suspect' if suspect_pi else 'clear','capture-pi-1','ref-good'),
         ('cad1','cad','CAD_IMAGE','clear','cad-pj-1','revision-1'),('m1','met','CALIPER','verified','met-1','caliper-2026'),
         ('a1','assembly','ASSEMBLY','pass','assembly-1','assembly-fixture')]
    ev=[]
    for event_id,station,kind,verdict,root,cal in row:
        payload={}
        if kind=='CALIPER':payload={'measurement_mm':20.1,'uncertainty_mm':0.05,'unit':'mm','validated':True}
        if kind=='ASSEMBLY':payload={'validated':True}
        e=Evidence(event_id,'TAB-B12',station,kind,origin,root,now,verdict,payload,calibration_id=cal)
        ev.append(sign_evidence(e,keys[station]))
    return ev,keys,now

def run_demo():
    evidence,keys,now=example_evidence(suspect_pi=True)
    decision=evaluate('TAB-B12',evidence,keys,now=now)
    slots=[{'id':'A1','width_mm':21.0},{'id':'A2','width_mm':20.6}]
    tabs=[{'id':'B1','width_mm':20.2},{'id':'B2','width_mm':19.9}]
    return {'source_status':'SYNTHETIC_DEMO_NOT_REAL_FACTORY_RESULT',
            'two_camera_conflict':decision.to_dict(),
            'matching':optimize_pairs(slots,tabs),
            'active_inspection':action_scores(0.08,[Inspection('CALIPER',.99,.99,.5),Inspection('PHOTO',.8,.8,.1)]),
            'simulated_comparison':compare_policies(1000,2026)}

if __name__=='__main__':print(json.dumps(run_demo(),indent=2))
