import pytest
from qualityrelay17.digital_line import StationConfig,run_line
from qualityrelay17.benchmark import run_benchmark,wilson_interval
from qualityrelay17.external_adapters import NVIDIA_ADAPTERS

def test_line_reproducible():assert run_line(20,2)==run_line(20,2)
def test_line_multi():
    x=run_line(30,3,lines=3);assert x['completed']==30 and len(x['station_summary'])==18

def test_line_throughput_positive():assert run_line(4)['throughput_per_hour']>0

def test_line_without_failure():
    x=run_line(3,1,stations=[StationConfig('A',1)]);assert not any(s['downtime'] for r in x['sample_routes'] for s in r['station_trace'])

def test_line_invalid_probability():
    with pytest.raises(ValueError):run_line(1,stations=[StationConfig('A',1,downtime_probability=1.3)])
def test_line_positive_queue():
    x=run_line(8,0,arrival_every_s=.01)
    assert any(s['queue_wait_s']>0 for r in x['sample_routes'] for s in r['station_trace'])

def test_benchmark_paired():
    x=run_benchmark(range(3),20);assert x['seeds']==3 and x['origin']=='SIMULATED'

def test_reference_not_superior_when_identical_decisions():
    x=run_benchmark(range(3),30)
    assert x['paired_cost_difference_safe_mesh_minus_rules']>=0

def test_wilson():
    lo,hi=wilson_interval(0,100);assert lo==0 and hi>0

def test_nvidia_slots_not_misrepresented():
    # the eight plan slots, with 'Warp/Newton' split because only Warp is used (REL-03)
    assert set(NVIDIA_ADAPTERS)=={'warp','newton','cuopt','isaac_sim','replicator','physicsnemo','deepstream','cosmos','metropolis_vss'}
    live={k:x.health() for k,x in NVIDIA_ADAPTERS.items() if x.health().state!='NOT_CONFIGURED'}
    assert set(live)=={'warp'} and 'CPU backend only' in live['warp'].scope and 'Never run on a CUDA GPU' in live['warp'].scope
