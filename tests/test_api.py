from fastapi.testclient import TestClient
from qualityrelay17.api import app
c=TestClient(app)

def test_health_discloses_limits():
    r=c.get('/health');assert r.status_code==200 and not r.json()['factory_connected']

def test_website():
    r=c.get('/');assert r.status_code==200 and 'QualityRelay 17' in r.text

def test_simulation_api():
    r=c.post('/simulation/compare',json={'n':30,'seed':42});assert r.status_code==200 and r.json()['origin']=='SIMULATED'

def test_reject_huge_simulation():
    assert c.post('/simulation/compare',json={'n':1000000}).status_code==422

def test_line_sim():
    r=c.get('/simulation/factory-line?n=30&lines=2');assert r.status_code==200 and r.json()['completed']==30

def test_nvidia_truth():
    r=c.get('/integrations/nvidia');assert all(x['state']=='NOT_CONFIGURED' for x in r.json().values())

def test_claims_truth():
    assert c.get('/research/claims').json()['proven_new_discovery'] is False

def test_cad_static_route():
    assert c.get('/examples/cad/slot_nominal_21p00_top_projected.png').status_code==200

def test_no_arbitrary_file_route():
    assert c.get('/examples/cad/secrets.txt').status_code==404

def test_caliper_reading_refused_without_provisioned_key():
    r=c.post('/hardware/caliper-reading',json={'event_id':'e1','specimen_id':'S-1','station_id':'slot',
             'adc_value':2048,'uncertainty_mm':0.03,'calibration_id':'cal-1'})
    assert r.status_code==503

def test_bin_ack_refused_without_provisioned_key():
    r=c.post('/hardware/bin-ack',json={'event_id':'e2','specimen_id':'S-1','station_id':'sorter',
             'bin_name':'PASS','photoresistor_blocked':True})
    assert r.status_code==503

def test_caliper_reading_signed_once_key_provisioned():
    import qualityrelay17.api as api_module
    api_module.HARDWARE_STATION_KEYS['slot']='test-only-key'
    try:
        r=c.post('/hardware/caliper-reading',json={'event_id':'e3','specimen_id':'S-1','station_id':'slot',
                 'adc_value':2048,'uncertainty_mm':0.03,'calibration_id':'cal-1'})
        assert r.status_code==200 and r.json()['origin']=='PHYSICAL_CAPTURE' and r.json()['signature']
    finally:
        api_module.HARDWARE_STATION_KEYS.pop('slot',None)
