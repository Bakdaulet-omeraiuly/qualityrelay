import pytest
from qualityrelay17.vder import Inspection,action_scores,risk,posterior,entropy
from qualityrelay17.matching import optimize_pairs
from qualityrelay17.economics import Costs,calculate,compare
from qualityrelay17.factory import seeded_scenario,apply_policy,compare_policies

def test_vder_no_action_available():assert 'NO_ACTION' in [r['name'] for r in action_scores(.1,[])]
def test_vder_perfect_cheap_test():assert action_scores(.1,[Inspection('PERFECT',1,1,0.0)])[0]['name']=='PERFECT'
def test_vder_expensive_no_action():assert action_scores(.1,[Inspection('EXPENSIVE',1,1,999.)])[0]['name']=='NO_ACTION'
def test_vder_numerical_risk():assert risk(.5,100,3)==1.5
def test_posterior_zero_positive():assert posterior(.1,1,1,True)==1.0
def test_entropy_bounds():assert entropy(0)==0 and entropy(1)==0
def test_bad_params():
    with pytest.raises(ValueError):action_scores(.5,[Inspection('BAD',1.5,.8,1)])
def test_matching_safe():
    result=optimize_pairs([{'id':'a','width_mm':21.0}],[{'id':'b','width_mm':20.1}]);assert result['risk_penalty']==0

def test_matching_too_many():
    with pytest.raises(ValueError):optimize_pairs([{'id':str(i),'width_mm':21} for i in range(13)],[{'id':str(i),'width_mm':20} for i in range(13)])
def test_cost_unique_terminal():
    with pytest.raises(ValueError):calculate([{'specimen_id':'a','outcome':'pass'},{'specimen_id':'a','outcome':'scrap'}],Costs())
def test_cost_avoids_double_counting():
    v=calculate([{'specimen_id':'a','outcome':'scrap','inspections':2}],Costs());assert v['total_cost']==21.0

def test_paired_comparison():
    a=[{'specimen_id':'a','outcome':'scrap'}];b=[{'specimen_id':'a','outcome':'pass'}]
    assert compare(a,b,Costs(),Costs())['net_savings']==20

def test_unmatched_population():
    with pytest.raises(ValueError):compare([{'specimen_id':'a','outcome':'pass'}],[{'specimen_id':'b','outcome':'pass'}],Costs(),Costs())
def test_simulation_repeatable():assert seeded_scenario(25,22)==seeded_scenario(25,22)
def test_simulation_different_seed():assert seeded_scenario(25,22)!=seeded_scenario(25,23)
def test_simulator_labels():assert seeded_scenario(2)[0]['origin']=='SIMULATED'
def test_simulator_paired():
    rows=seeded_scenario(100)
    assert [x['specimen_id'] for x in apply_policy(rows,'phone_only')]==[x['specimen_id'] for x in apply_policy(rows,'safe_mesh_reference')]
def test_comparison_not_claiming_superiority():
    out=compare_policies(100,1)
    assert out['origin']=='SIMULATED' and 'conservative_rules' in out['policies']
