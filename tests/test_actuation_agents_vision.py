import pytest
import numpy as np
from qualityrelay17.actuation import SorterInterlock,RouteRequest
from qualityrelay17.agent_tools import execute
from qualityrelay17.roles import ROLES,plan_roles
from qualityrelay17.nebius import NebiusExpert
from qualityrelay17.vision import compare_reference,silhouette_iou

def req(**kw):return RouteRequest(**{'action_id':'a1','specimen_id':'p1','bin':'HOLD','decision':'HOLD',**kw})
def test_stage_does_not_actuate():assert SorterInterlock().stage(req(),'human')['hardware_command_emitted'] is False
def test_staged_no_confirmation():assert SorterInterlock().stage(req(),'human')['status']=='STAGED_ONLY'
def test_no_operator():
    with pytest.raises(PermissionError):SorterInterlock().stage(req(),'')
def test_no_synthetic_route():  # the evidence gate (api.evidence_gate reads ledger tiers) can veto any route
    with pytest.raises(PermissionError):SorterInterlock(evidence_gate=lambda r:['SIMULATED evidence']).stage(req(),'human')
def test_no_unapproved_pass():
    with pytest.raises(PermissionError):SorterInterlock(evidence_gate=lambda r:[]).stage(req(bin='PASS'),'human')
def test_no_unconfirmed_reject():
    with pytest.raises(PermissionError):SorterInterlock(evidence_gate=lambda r:[]).stage(req(bin='REJECT'),'human')
def test_pass_refused_without_evidence_gate():
    with pytest.raises(PermissionError,match='evidence gate'):SorterInterlock().stage(req(bin='PASS',decision='AUTHORIZED_PASS'),'human')
def test_physical_ack_and_dedup():
    s=SorterInterlock();s.stage(req(),'human');assert s.acknowledge('a1','HOLD','beam-1')['status']=='PHYSICAL_ROUTE_CONFIRMED'
    assert s.acknowledge('a1','HOLD','beam-1')['status']=='DUPLICATE_ACK_IGNORED'
def test_misroute_detected():
    s=SorterInterlock();s.stage(req(),'human')
    with pytest.raises(ValueError):s.acknowledge('a1','PASS','beam')
def test_21_roles():assert len(ROLES)==21
def test_role_selection_bounded():assert 1<=len(plan_roles(True,True,7))<=7
def test_role_tool_allowed():
    r=execute('assembly_engineer','check_clearance',{'slot_width_mm':21,'tab_width_mm':20},{})
    assert r['clearance_mm']==1

def test_role_tool_denied():
    with pytest.raises(PermissionError):execute('materials_engineer','check_clearance',{'slot_width_mm':21,'tab_width_mm':20},{})
def test_nebius_requires_opt_in():assert NebiusExpert(enabled=False).review('quality_inspector',[])['status']=='DISABLED_NO_LIVE_MODEL'
def test_reference_comparison_same():
    a=np.zeros((30,30),dtype='uint8');assert compare_reference(a,a)['difference_fraction']==0

def test_reference_comparison_shape():
    with pytest.raises(ValueError):compare_reference(np.zeros((3,3),dtype='uint8'),np.zeros((2,2),dtype='uint8'))
def test_mask_iou():
    a=np.ones((4,4),dtype='uint8');assert silhouette_iou(a,a)==1

def test_mask_empty_raises():
    with pytest.raises(ValueError):silhouette_iou(np.zeros((3,3)),np.zeros((3,3)))

def test_cad_projection_from_original_stl():
    from qualityrelay17.vision import cad_projection_from_stl
    import tempfile,trimesh,os
    m=trimesh.creation.box(extents=(2,3,1))
    with tempfile.NamedTemporaryFile(suffix='.stl',delete=False) as f: path=f.name
    try:
        m.export(path)
        out=cad_projection_from_stl(path,pixels=100)
        assert out.shape==(100,100) and out.max()==255 and out.min()==0
    finally:os.unlink(path)
