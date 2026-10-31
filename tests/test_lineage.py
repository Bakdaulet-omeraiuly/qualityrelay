from qualityrelay17.lineage import lineage_groups,effective_source_count
import pytest

def e(i,root,parents=None):return {'event_id':i,'source_root':root,'parent_source_roots':parents or []}
def test_source_count_two_independent():assert effective_source_count([e('p','photo-1'),e('q','photo-2')])==2
def test_derived_cad_does_not_double_count():assert effective_source_count([e('p','photo-1'),e('cad','render-2',['photo-1'])])==1
def test_chained_derivations_transitive():assert effective_source_count([e('a','root'),e('b','x',['root']),e('c','y',['x'])])==1
def test_two_clusters():assert lineage_groups([e('a','r1'),e('b','r1'),e('c','r2')])==[['a','b'],['c']]
def test_duplicate_events():
    with pytest.raises(ValueError):lineage_groups([e('a','r1'),e('a','r2')])
