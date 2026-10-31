from fastapi.testclient import TestClient
from qualityrelay17.api import app
c=TestClient(app)

def test_health_discloses_limits():
    r=c.get('/health');assert r.status_code==200 and not r.json()['factory_connected']

def test_website():
    r=c.get('/');assert r.status_code==200 and 'QualityRelay' in r.text and 'SIMULATED' in r.text
    r=c.get('/legacy');assert r.status_code==200 and 'QualityRelay 17' in r.text  # 17.0 page kept at /legacy

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

import pytest
import qualityrelay17.api as api_module

@pytest.fixture
def no_station_keys(monkeypatch):
    """The 503 cold state must hold regardless of what the developer's own .env provisions."""
    monkeypatch.setattr(api_module,'HARDWARE_STATION_KEYS',{})

@pytest.fixture
def slot_key(monkeypatch):
    monkeypatch.setattr(api_module,'HARDWARE_STATION_KEYS',{'slot':'test-only-key-'+'x'*32,'sorter':'test-only-key-'+'y'*32})
    monkeypatch.setattr(api_module,'HARDWARE_LEDGER',api_module.EvidenceLedger())  # fresh per test
    monkeypatch.setattr(api_module,'SORTER',api_module.SorterInterlock(sensor_lookup=lambda e:api_module.HARDWARE_LEDGER.get_event(e)))

CAL={'event_id':'e3','specimen_id':'S-1','station_id':'slot','adc_value':2048,'uncertainty_mm':0.03,'calibration_id':'cal-1'}
ACK={'event_id':'ack-1','specimen_id':'S-1','station_id':'sorter','bin_name':'PASS','photoresistor_blocked':True}

def test_caliper_reading_refused_without_provisioned_key(no_station_keys):
    r=c.post('/hardware/caliper-reading',json={'event_id':'e1','specimen_id':'S-1','station_id':'slot',
             'adc_value':2048,'uncertainty_mm':0.03,'calibration_id':'cal-1'})
    assert r.status_code==503

def test_bin_ack_refused_without_provisioned_key(no_station_keys):
    r=c.post('/hardware/bin-ack',json={'event_id':'e2','specimen_id':'S-1','station_id':'sorter',
             'bin_name':'PASS','photoresistor_blocked':True})
    assert r.status_code==503

def test_caliper_reading_signed_once_key_provisioned(slot_key):
    r=c.post('/hardware/caliper-reading',json={'event_id':'e3','specimen_id':'S-1','station_id':'slot',
             'adc_value':2048,'uncertainty_mm':0.03,'calibration_id':'cal-1'})
    assert r.status_code==200 and r.json()['origin']=='PHYSICAL_CAPTURE' and r.json()['signature']

def test_health_lists_provisioned_stations(slot_key):
    assert c.get('/health').json()['hardware_stations_provisioned']==['slot','sorter']

def test_station_keys_come_from_environment_not_source():
    assert api_module.load_station_keys(env={},dotenv={})=={}
    keys=api_module.load_station_keys(env={'SLOT_STATION_KEY':'a'*64},dotenv={'TAB_STATION_KEY':'b'*64})
    assert keys=={'slot':'a'*64,'tab':'b'*64}

def test_real_environment_wins_over_dotenv():
    keys=api_module.load_station_keys(env={'SLOT_STATION_KEY':'a'*64},dotenv={'SLOT_STATION_KEY':'b'*64})
    assert keys['slot']=='a'*64

def test_blank_station_key_means_unprovisioned():
    assert api_module.load_station_keys(env={'SORTER_STATION_KEY':'  '},dotenv={})=={}

def test_short_station_key_is_refused_not_used():
    with pytest.raises(RuntimeError):
        api_module.load_station_keys(env={'SLOT_STATION_KEY':'test-only-key'},dotenv={})

def test_dotenv_reader_skips_comments_and_quotes(tmp_path):
    f=tmp_path/'.env'; f.write_text('# c\nA=1\n\nB="two"\nbad line\n',encoding='utf-8')
    assert api_module.read_dotenv(f)=={'A':'1','B':'two'}

def test_provision_script_writes_only_gitignored_env(tmp_path):
    import subprocess,sys
    env_file=tmp_path/'.env'
    cmd=[sys.executable,'scripts/provision_station_keys.py','--env-file',str(env_file)]
    out=subprocess.run(cmd+['--stations','slot','sorter'],capture_output=True,text=True,check=True).stdout
    text=env_file.read_text(encoding='utf-8')
    keys=api_module.load_station_keys(env={},dotenv=api_module.read_dotenv(env_file))
    assert set(keys)=={'slot','sorter'} and all(len(v)==64 for v in keys.values())
    assert keys['slot'] not in out and keys['sorter'] not in out  # values never echoed
    subprocess.run(cmd+['--stations','slot'],check=True,capture_output=True)
    assert env_file.read_text(encoding='utf-8')==text  # second run keeps existing keys
    subprocess.run(cmd+['--stations','slot','--rotate'],check=True,capture_output=True)
    assert api_module.read_dotenv(env_file)['SLOT_STATION_KEY']!=keys['slot']

def test_hardware_evidence_is_persisted_to_ledger(slot_key):
    assert c.post('/hardware/caliper-reading',json=CAL).status_code==200
    assert c.post('/hardware/bin-ack',json=ACK).status_code==200
    rows=api_module.HARDWARE_LEDGER.get_specimen('S-1',requester='inspector',allowed_stations={'slot','sorter'})
    assert {r['kind'] for r in rows}=={'CALIPER','ROUTE_ACK'}
    assert api_module.HARDWARE_LEDGER.get_event('ack-1')['payload']['bin']=='PASS'

STAGE={'action_id':'act-1','specimen_id':'S-1','bin':'PASS','decision':'AUTHORIZED_PASS','operator_id':'human','approved':True,'origin':'VERIFIED_PHYSICAL'}

def test_bin_ack_without_staged_route_is_recorded_but_unmatched(slot_key):
    r=c.post('/hardware/bin-ack',json=ACK).json()
    assert r['evidence']['kind']=='ROUTE_ACK' and r['interlock']['status']=='NO_PENDING_ACTION'

def test_sensor_fired_confirms_staged_route(slot_key):
    assert c.post('/actuation/stage',json=STAGE).json()=={'status':'STAGED_ONLY','hardware_command_emitted':False}
    assert c.get('/actuation/act-1').json()['state']=='PENDING'
    r=c.post('/hardware/bin-ack',json=ACK).json()
    assert r['interlock']['status']=='PHYSICAL_ROUTE_CONFIRMED'
    assert r['interlock']['sensor_event_id']==r['evidence']['event_id']=='ack-1'
    assert r['interlock']['hardware_command_emitted'] is False
    assert c.get('/actuation/act-1').json()=={'action_id':'act-1','state':'CONFIRMED','bin':'PASS','sensor_event_id':'ack-1'}

def test_e12_wrong_physical_bin_is_route_mismatch_and_faults(slot_key):
    c.post('/actuation/stage',json=STAGE)
    r=c.post('/hardware/bin-ack',json={**ACK,'bin_name':'HOLD'})
    assert r.status_code==200  # the sensor reading itself is real and stays recorded
    assert r.json()['interlock']['status']=='ROUTE_MISMATCH'
    assert r.json()['interlock']['expected_bin']=='PASS' and r.json()['interlock']['actual_bin']=='HOLD'
    assert c.get('/actuation/act-1').json()['state']=='FAULTED'
    assert api_module.HARDWARE_LEDGER.get_event('ack-1') is not None

def test_e13_second_sensor_trigger_is_duplicate_not_double_count(slot_key):
    c.post('/actuation/stage',json=STAGE)
    assert c.post('/hardware/bin-ack',json=ACK).json()['interlock']['status']=='PHYSICAL_ROUTE_CONFIRMED'
    again=c.post('/hardware/bin-ack',json={**ACK,'event_id':'ack-2'}).json()  # bounce: new event id, same part
    assert again['interlock']['status']=='NO_PENDING_ACTION'  # route already confirmed; nothing left to count
    replay=c.post('/hardware/bin-ack',json=ACK)  # exact same event id
    assert replay.status_code==409
    assert c.get('/actuation/act-1').json()['state']=='CONFIRMED'

def test_stage_requires_operator_and_physical_origin(slot_key):
    assert c.post('/actuation/stage',json={**STAGE,'approved':False}).status_code==403
    assert c.post('/actuation/stage',json={**STAGE,'origin':'SIMULATED'}).status_code==403
    assert c.post('/actuation/stage',json={**STAGE,'bin':'PASS','decision':'HOLD'}).status_code==403
    assert c.post('/actuation/stage',json=STAGE).status_code==200
    assert c.post('/actuation/stage',json=STAGE).status_code==409  # duplicate action id
    assert api_module.HARDWARE_LEDGER.get_event('never-posted') is None

def test_replayed_event_id_is_409_not_resigned(slot_key):
    first=c.post('/hardware/caliper-reading',json=CAL)
    assert first.status_code==200
    replay=c.post('/hardware/caliper-reading',json={**CAL,'adc_value':100})  # same id, different reading
    assert replay.status_code==409
    rows=api_module.HARDWARE_LEDGER.get_specimen('S-1',requester='inspector',allowed_stations={'slot'})
    assert len(rows)==1 and rows[0]['payload']['measurement_mm']==first.json()['payload']['measurement_mm']

def test_rejected_bin_ack_is_not_persisted(slot_key):
    r=c.post('/hardware/bin-ack',json={**ACK,'photoresistor_blocked':False})
    assert r.status_code==422 and 'refusing' in r.json()['detail']
    assert api_module.HARDWARE_LEDGER.get_event('ack-1') is None

def test_ledger_survives_threadpool_use():
    import threading
    from qualityrelay17.contracts import Evidence,sign_evidence
    led=api_module.EvidenceLedger()
    def worker(i):
        e=Evidence(f'ev-{i}','S-9','slot','CALIPER','PHYSICAL_CAPTURE','r',1.0,'verified',{})
        led.append(sign_evidence(e,'k'*32))
    ts=[threading.Thread(target=worker,args=(i,)) for i in range(20)]
    [t.start() for t in ts];[t.join() for t in ts]
    assert len(led.get_specimen('S-9',requester='inspector',allowed_stations={'slot'}))==20

def test_health_reports_ledger_mode(slot_key):
    assert c.get('/health').json()['hardware_ledger'] in {'memory','file'}
