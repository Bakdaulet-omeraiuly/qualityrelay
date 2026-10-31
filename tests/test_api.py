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
    r=c.get('/integrations/nvidia').json()  # REL-03: only Warp runs, and only on CPU
    assert {k for k,x in r.items() if x['state']!='NOT_CONFIGURED'}=={'warp'} and 'CPU backend only' in r['warp']['scope']

def test_claims_truth():
    assert c.get('/research/claims').json()['proven_new_discovery'] is False

def test_cad_static_route():
    assert c.get('/examples/cad/slot_nominal_21p00_top_projected.png').status_code==200

def test_no_arbitrary_file_route():
    assert c.get('/examples/cad/secrets.txt').status_code==404

import pytest
import qualityrelay17.api as api_module

import json
from qualityrelay17 import station_auth

DEVICE={'slot':'dev-slot-'+'a'*32,'tab':'dev-tab-'+'b'*32,'sorter':'dev-sorter-'+'c'*32}

def signed_post(path,body,station=None,*,device_key=None,timestamp=None,nonce=None,raw=None):
    """POST with a valid per-device envelope (BACK-01). station defaults to body['station_id']."""
    station=station or body['station_id']
    raw=json.dumps(body).encode() if raw is None else raw
    hdr=station_auth.sign(device_key or DEVICE[station],'POST',path,station,raw,timestamp=timestamp,nonce=nonce)
    return c.post(path,content=raw,headers={**hdr,'Content-Type':'application/json'})

@pytest.fixture
def devices(monkeypatch):
    """Device keys + fresh nonce cache, but NO station signing keys: the 503 cold state must hold
    regardless of what the developer's own .env provisions."""
    monkeypatch.setattr(api_module,'HARDWARE_DEVICE_KEYS',dict(DEVICE))
    monkeypatch.setattr(api_module,'NONCES',station_auth.NonceCache(ttl_s=api_module.STATION_AUTH_TTL_S))

@pytest.fixture
def no_station_keys(devices,monkeypatch):
    monkeypatch.setattr(api_module,'HARDWARE_STATION_KEYS',{})

@pytest.fixture
def slot_key(devices,monkeypatch):
    monkeypatch.setattr(api_module,'HARDWARE_STATION_KEYS',{'slot':'test-only-key-'+'x'*32,'sorter':'test-only-key-'+'y'*32})
    monkeypatch.setattr(api_module,'HARDWARE_LEDGER',api_module.EvidenceLedger())  # fresh per test
    monkeypatch.setattr(api_module,'SORTER',api_module.build_sorter())  # wired to the fresh ledger + evidence gate
    monkeypatch.setattr(api_module,'OPERATOR_TOKENS',{'alice':api_module.operator_auth._digest(OP_TOKEN)})

OP_TOKEN='op-alice-'+'t'*40
OP={'Authorization':'Bearer '+OP_TOKEN}

def verify_caliper(event_id='e3',specimen='S-1',reference=20.0,headers=None):
    """GT-CAL-01 against the 20.0005 mm reading CAL produces (adc 2048 on the 18-22 mm map)."""
    return c.post(f'/evidence/{event_id}/verify',headers=OP if headers is None else headers,
                  json={'procedure_id':'GT-CAL-01','observed_specimen_id':specimen,'reference_value_mm':reference,
                        'reference_uncertainty_mm':0.01,'reference_instrument_id':'mitutoyo-500-196','reference_calibration_id':'cert-2026-07'})

def verified_part(event_id='e3',specimen='S-1'):
    assert signed_post('/hardware/caliper-reading',{**CAL,'event_id':event_id,'specimen_id':specimen}).status_code==200
    r=verify_caliper(event_id,specimen); assert r.status_code==200 and r.json()['status']['effective_origin']=='VERIFIED_PHYSICAL',r.json()

CAL={'event_id':'e3','specimen_id':'S-1','station_id':'slot','adc_value':2048,'uncertainty_mm':0.03,'calibration_id':'cal-1'}
ACK={'event_id':'ack-1','specimen_id':'S-1','station_id':'sorter','bin_name':'PASS','photoresistor_blocked':True}

def test_caliper_reading_refused_without_provisioned_key(no_station_keys):
    r=signed_post('/hardware/caliper-reading',{'event_id':'e1','specimen_id':'S-1','station_id':'slot',
             'adc_value':2048,'uncertainty_mm':0.03,'calibration_id':'cal-1'})
    assert r.status_code==503

def test_bin_ack_refused_without_provisioned_key(no_station_keys):
    r=signed_post('/hardware/bin-ack',{'event_id':'e2','specimen_id':'S-1','station_id':'sorter',
             'bin_name':'PASS','photoresistor_blocked':True})
    assert r.status_code==503

def test_caliper_reading_signed_once_key_provisioned(slot_key):
    r=signed_post('/hardware/caliper-reading',{'event_id':'e3','specimen_id':'S-1','station_id':'slot',
             'adc_value':2048,'uncertainty_mm':0.03,'calibration_id':'cal-1'})
    assert r.status_code==200 and r.json()['origin']=='PHYSICAL_CAPTURE' and r.json()['signature']

def test_health_lists_provisioned_stations(slot_key):
    h=c.get('/health').json()
    assert h['hardware_stations_provisioned']==['slot','sorter'] and h['device_authenticated_stations']==['slot','sorter','tab']

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
    assert signed_post('/hardware/caliper-reading',CAL).status_code==200
    assert signed_post('/hardware/bin-ack',ACK).status_code==200
    rows=api_module.HARDWARE_LEDGER.get_specimen('S-1',requester='inspector',allowed_stations={'slot','sorter'})
    assert {r['kind'] for r in rows}=={'CALIPER','ROUTE_ACK'}
    assert api_module.HARDWARE_LEDGER.get_event('ack-1')['payload']['bin']=='PASS'

STAGE={'action_id':'act-1','specimen_id':'S-1','bin':'PASS','decision':'AUTHORIZED_PASS','evidence_ids':['e3']}

def stage(body=STAGE,headers=OP):
    return c.post('/actuation/stage',json=body,headers=headers)

def test_bin_ack_without_staged_route_is_recorded_but_unmatched(slot_key):
    r=signed_post('/hardware/bin-ack',ACK).json()
    assert r['evidence']['kind']=='ROUTE_ACK' and r['interlock']['status']=='NO_PENDING_ACTION'

def test_sensor_fired_confirms_staged_route(slot_key):
    verified_part()
    r=stage(); assert r.status_code==200 and r.json()['status']=='STAGED_ONLY' and r.json()['hardware_command_emitted'] is False
    assert c.get('/actuation/act-1').json()['state']=='STAGED'
    r=signed_post('/hardware/bin-ack',ACK).json()
    assert r['interlock']['status']=='PHYSICAL_ROUTE_CONFIRMED'
    assert r['interlock']['sensor_event_id']==r['evidence']['event_id']=='ack-1'
    assert r['interlock']['hardware_command_emitted'] is False
    assert r['interlock']['specimen_identity']=='NOT_PROVEN'  # an object in the bin is not proof of which part
    st=c.get('/actuation/act-1').json()
    assert {k:st[k] for k in ('action_id','state','bin','sensor_event_id')}=={'action_id':'act-1','state':'CONFIRMED','bin':'PASS','sensor_event_id':'ack-1'}
    b=st['binding']  # BACK-03: the full tuple, server-derived
    assert (b['specimen_id'],b['requested_bin'],b['actual_bin'],b['sensor_station'],b['approved_by'])==('S-1','PASS','PASS','sorter','alice')
    assert b['sensed_at'] is not None and b['approved_at'] is not None

def test_e12_wrong_physical_bin_is_route_mismatch_and_faults(slot_key):
    verified_part(); stage()
    r=signed_post('/hardware/bin-ack',{**ACK,'bin_name':'HOLD'})
    assert r.status_code==200  # the sensor reading itself is real and stays recorded
    assert r.json()['interlock']['status']=='ROUTE_MISMATCH'
    assert r.json()['interlock']['expected_bin']=='PASS' and r.json()['interlock']['actual_bin']=='HOLD'
    assert c.get('/actuation/act-1').json()['state']=='FAULTED'
    assert api_module.HARDWARE_LEDGER.get_event('ack-1') is not None

def test_e13_second_sensor_trigger_is_duplicate_not_double_count(slot_key):
    verified_part(); stage()
    assert signed_post('/hardware/bin-ack',ACK).json()['interlock']['status']=='PHYSICAL_ROUTE_CONFIRMED'
    again=signed_post('/hardware/bin-ack',{**ACK,'event_id':'ack-2'}).json()  # bounce: new event id, same part
    assert again['interlock']['status']=='NO_PENDING_ACTION'  # route already confirmed; nothing left to count
    replay=signed_post('/hardware/bin-ack',ACK)  # exact same event id
    assert replay.status_code==409
    assert c.get('/actuation/act-1').json()['state']=='CONFIRMED'

def test_stage_requires_operator_and_physical_origin(slot_key):
    verified_part()
    assert stage(headers={}).status_code==401                                   # no operator token
    assert stage(headers={'Authorization':'Bearer '+'x'*40}).status_code==401   # wrong token
    old={**STAGE,'operator_id':'human','approved':True,'origin':'VERIFIED_PHYSICAL'}
    assert stage(old).status_code==422  # caller-asserted approval/origin fields are refused, not ignored
    assert stage({**STAGE,'bin':'PASS','decision':'HOLD'}).status_code==403
    first=stage(); assert first.status_code==200
    again=stage(); assert again.status_code==200 and again.json()['idempotent_replay'] is True  # same request = idempotent
    assert stage({**STAGE,'bin':'HOLD','decision':'HOLD'}).status_code==409  # same id, different request
    assert api_module.HARDWARE_LEDGER.get_event('never-posted') is None

def test_human_routes_are_503_without_provisioned_operators(slot_key,monkeypatch):
    monkeypatch.setattr(api_module,'OPERATOR_TOKENS',{})
    assert stage().status_code==503 and c.post('/actuation/arm',headers=OP).status_code==503

def test_replayed_event_id_is_409_not_resigned(slot_key):
    first=signed_post('/hardware/caliper-reading',CAL)
    assert first.status_code==200
    replay=signed_post('/hardware/caliper-reading',{**CAL,'adc_value':100})  # same id, different reading
    assert replay.status_code==409
    rows=api_module.HARDWARE_LEDGER.get_specimen('S-1',requester='inspector',allowed_stations={'slot'})
    assert len(rows)==1 and rows[0]['payload']['measurement_mm']==first.json()['payload']['measurement_mm']

def test_rejected_bin_ack_is_not_persisted(slot_key):
    r=signed_post('/hardware/bin-ack',{**ACK,'photoresistor_blocked':False})
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


# ---------------------------------------------------------------- BACK-01: per-device signed envelope
def test_unsigned_hardware_post_is_401_even_with_keys(slot_key):
    assert c.post('/hardware/caliper-reading',json=CAL).status_code==401
    assert c.post('/hardware/bin-ack',json=ACK).status_code==401
    assert api_module.HARDWARE_LEDGER.get_specimen('S-1',requester='inspector',allowed_stations={'slot','sorter'})==[]

def test_wrong_device_key_is_401(slot_key):
    assert signed_post('/hardware/caliper-reading',CAL,device_key='not-the-device-key'+'z'*20).status_code==401

def test_unknown_station_is_401_not_503(slot_key):
    body={**CAL,'station_id':'ghost'}
    r=signed_post('/hardware/caliper-reading',body,station='ghost',device_key='whatever'+'q'*30)
    assert r.status_code==401  # identity fails before the signing-key check can leak station existence

def test_body_station_must_match_authenticated_station(slot_key):
    # valid tab envelope carrying a body that claims to be the slot station
    r=signed_post('/hardware/caliper-reading',CAL,station='tab')
    assert r.status_code==403 and 'does not match' in r.json()['detail']

def test_endpoint_acl_sorter_cannot_submit_caliper_reading(slot_key):
    r=signed_post('/hardware/caliper-reading',{**CAL,'station_id':'sorter'},station='sorter')
    assert r.status_code==403
    r=signed_post('/hardware/bin-ack',{**ACK,'station_id':'slot'},station='slot')
    assert r.status_code==403

def test_tampered_body_fails_signature(slot_key):
    raw=json.dumps(CAL).encode()
    hdr=station_auth.sign(DEVICE['slot'],'POST','/hardware/caliper-reading','slot',raw)
    tampered=json.dumps({**CAL,'adc_value':4000}).encode()
    r=c.post('/hardware/caliper-reading',content=tampered,headers={**hdr,'Content-Type':'application/json'})
    assert r.status_code==401

def test_signature_bound_to_path(slot_key):
    raw=json.dumps(ACK).encode()
    hdr=station_auth.sign(DEVICE['sorter'],'POST','/hardware/caliper-reading','sorter',raw)  # signed for the other path
    r=c.post('/hardware/bin-ack',content=raw,headers={**hdr,'Content-Type':'application/json'})
    assert r.status_code==401

def test_stale_or_future_timestamp_is_401(slot_key):
    import time
    assert signed_post('/hardware/caliper-reading',CAL,timestamp=int(time.time())-3600).status_code==401
    assert signed_post('/hardware/caliper-reading',CAL,timestamp=int(time.time())+3600).status_code==401

def test_nonce_replay_is_401_even_with_new_event_id(slot_key):
    nonce='deadbeefdeadbeefdeadbeef'
    assert signed_post('/hardware/caliper-reading',CAL,nonce=nonce).status_code==200
    r=signed_post('/hardware/caliper-reading',{**CAL,'event_id':'e-new'},nonce=nonce)
    assert r.status_code==401 and 'nonce' in r.json()['detail']
    rows=api_module.HARDWARE_LEDGER.get_specimen('S-1',requester='inspector',allowed_stations={'slot'})
    assert len(rows)==1

def test_failed_signature_does_not_consume_nonce(slot_key):
    nonce='cafebabecafebabecafebabe'
    assert signed_post('/hardware/caliper-reading',CAL,nonce=nonce,device_key='wrong'+'w'*30).status_code==401
    assert signed_post('/hardware/caliper-reading',CAL,nonce=nonce).status_code==200  # legit sender still gets through

def test_valid_envelope_then_unprovisioned_signing_key_is_503(devices,monkeypatch):
    monkeypatch.setattr(api_module,'HARDWARE_STATION_KEYS',{})
    assert signed_post('/hardware/caliper-reading',CAL).status_code==503  # identity ok, gateway cannot sign yet

def test_device_keys_loaded_from_env_separately_from_station_keys():
    keys=api_module.load_station_keys(env={'SLOT_DEVICE_KEY':'d'*64,'SLOT_STATION_KEY':'s'*64},dotenv={},env_map=api_module.DEVICE_KEY_ENV)
    assert keys=={'slot':'d'*64}


# ---------------------------------------------------------------- AGENT-04: planner selection over the API
def test_collective_openai_planner_not_configured_is_503(monkeypatch):
    monkeypatch.setattr(api_module,'_llm_env',lambda:{})
    r=c.post('/research/collective/run',json={'scenario':'pi_clear','planner':'openai'})
    assert r.status_code==503 and 'NOT_CONFIGURED' in r.json()['detail']

def test_collective_unknown_planner_is_422():
    assert c.post('/research/collective/run',json={'scenario':'pi_clear','planner':'gpt-in-a-hat'}).status_code==422

def test_collective_openai_planner_runs_and_is_recorded(monkeypatch):
    from tests.test_collective_llm_planner import FakeClient,req,fin,PI
    from qualityrelay17.collective import llm_planner
    fake=FakeClient([req('PI_IMAGE',PI),fin()])
    monkeypatch.setattr(api_module,'_llm_env',lambda:{'OPENAI_API_KEY':'sk-test-never-shown','OPENAI_MODEL':'test-model'})
    monkeypatch.setitem(llm_planner.PROVIDERS,'openai',lambda env:llm_planner.openai_planner_from_env(env,client=fake))
    r=c.post('/research/collective/run',json={'scenario':'pi_suspect','planner':'openai'})
    assert r.status_code==200
    j=r.json()
    assert j['planner']['provider']=='openai' and j['planner']['model']=='test-model' and j['decision']=='HOLD'
    assert 'sk-test-never-shown' not in r.text
    m=c.get(f"/research/collective/runs/{j['run_id']}/manifest").json()
    assert m['planner']['provider']=='openai' and m['roles_are_code_not_llm'] is False

def test_llm_status_reports_without_calling_or_leaking(monkeypatch):
    monkeypatch.setattr(api_module,'_llm_env',lambda:{'OPENAI_API_KEY':'sk-test-never-shown','OPENAI_MODEL':'m'})
    r=c.get('/integrations/llm')
    assert r.json()['providers']['openai']['state']=='CONFIGURED_NOT_VERIFIED' and 'sk-test' not in r.text
    monkeypatch.setattr(api_module,'_llm_env',lambda:{})
    assert c.get('/integrations/llm').json()['providers']['openai']['state']=='NOT_CONFIGURED'
    assert 'state' in c.get('/integrations/llm').json()['providers']['nebius']['entitlement']  # LLM-01, read from manifest only


# ---------------------------------------------------------------- BACK-02/03/04 over the API
def test_verify_needs_operator_and_unverified_evidence_cannot_back_a_pass(slot_key):
    assert signed_post('/hardware/caliper-reading',CAL).status_code==200
    assert verify_caliper(headers={}).status_code==401
    st=c.get('/evidence/e3/status').json()
    assert st['station_authenticated'] and st['effective_origin']=='PHYSICAL_CAPTURE' and st['verification_status']=='AWAITING_GROUND_TRUTH'
    r=stage(); assert r.status_code==403 and 'VERIFIED_PHYSICAL' in r.json()['detail']
    assert stage({**STAGE,'bin':'HOLD','decision':'HOLD'}).status_code==200  # HOLD only needs an authenticated capture

def test_disputed_ground_truth_blocks_pass(slot_key):
    assert signed_post('/hardware/caliper-reading',CAL).status_code==200
    r=verify_caliper(reference=20.6); assert r.status_code==200 and r.json()['verification']['outcome']=='DISPUTED'
    r=stage(); assert r.status_code==403 and 'DISPUTED' in r.json()['detail']

def test_evidence_of_another_specimen_or_missing_evidence_is_refused(slot_key):
    verified_part()
    assert stage({**STAGE,'specimen_id':'S-2'}).status_code==403
    assert stage({**STAGE,'evidence_ids':[]}).status_code==403
    assert stage({**STAGE,'evidence_ids':['ghost']}).status_code==403

def test_procedures_are_published(slot_key):
    p=c.get('/evidence/procedures').json()
    assert set(p)=={'GT-CAL-01','GT-VIS-01'} and all(v['doc'].startswith('docs/engineering/GROUND_TRUTH') for v in p.values())

def test_ai_proposal_needs_human_approval_and_cannot_pose_as_human(slot_key):
    verified_part()
    body={**STAGE,'recommended_by':'llm:openai'}
    r=c.post('/actuation/propose',json=body); assert r.status_code==200 and r.json()['status']=='PROPOSED'
    assert c.post('/actuation/propose',json={**body,'action_id':'x','recommended_by':'human:alice'}).status_code==422
    assert signed_post('/hardware/bin-ack',ACK).json()['interlock']['status']=='NO_PENDING_ACTION'  # proposal is not in flight
    assert c.post('/actuation/act-1/approve').status_code==401
    r=c.post('/actuation/act-1/approve',headers=OP); assert r.status_code==200 and r.json()['status']=='STAGED_ONLY'
    assert c.get('/actuation/act-1').json()['binding']['recommended_by']=='llm:openai'

def test_ambiguous_ack_is_not_guessed_and_action_id_binds(slot_key):
    verified_part()
    stage({**STAGE,'bin':'HOLD','decision':'HOLD'}); stage({**STAGE,'action_id':'act-2','bin':'HOLD','decision':'HOLD'})
    r=signed_post('/hardware/bin-ack',{**ACK,'bin_name':'HOLD'}).json()['interlock']
    assert r['status']=='AMBIGUOUS_ACK' and set(r['candidates'])=={'act-1','act-2'}
    r=signed_post('/hardware/bin-ack',{**ACK,'event_id':'ack-2','bin_name':'HOLD','action_id':'act-2'}).json()['interlock']
    assert r['status']=='PHYSICAL_ROUTE_CONFIRMED' and r['action_id']=='act-2' and r['station_id']=='sorter'
    assert c.get('/actuation/act-1').json()['state']=='STAGED'

def test_identity_confirmation_over_api(slot_key):
    verified_part(); stage(); signed_post('/hardware/bin-ack',ACK)
    assert c.post('/actuation/act-1/identity',json={'observed_specimen_id':'S-1'}).status_code==401
    r=c.post('/actuation/act-1/identity',json={'observed_specimen_id':'S-1'},headers=OP)
    assert r.status_code==200 and r.json()['specimen_identity']=='OPERATOR_CONFIRMED'
    kinds=[e['kind'] for e in c.get('/actuation/journal/act-1').json()['events']]
    assert kinds==['PROPOSED','STAGED','CONFIRMED','IDENTITY_CONFIRMED']

POLL={'station_id':'sorter','estop_loop_ok':True,'guard_closed':True,'position':'HOLD'}

def test_sorter_poll_defaults_to_hold_with_hardware_disabled(slot_key):
    verified_part(); stage()
    r=signed_post('/hardware/sorter/next-command',POLL)
    assert r.status_code==200 and r.json()['command']=='HOLD' and r.json()['reason']=='HARDWARE_DISABLED'
    assert c.post('/actuation/arm',headers=OP).status_code==403
    assert c.post('/hardware/sorter/next-command',json=POLL).status_code==401  # unsigned poll
    assert signed_post('/hardware/sorter/next-command',{**POLL,'station_id':'slot'},station='slot').status_code==403  # ACL

def test_armed_sorter_gets_signed_short_lived_command_then_estop(slot_key,monkeypatch):
    import hmac,hashlib
    monkeypatch.setattr(api_module.SORTER,'hardware_enabled',True)
    verified_part(); stage()
    assert signed_post('/hardware/sorter/next-command',POLL).json()['reason']=='NOT_ARMED'
    assert c.post('/actuation/arm').status_code==401
    assert c.post('/actuation/arm',headers=OP).json()['armed'] is True
    cmd=signed_post('/hardware/sorter/next-command',POLL).json()
    assert cmd['command']=='ROUTE' and cmd['bin']=='PASS' and cmd['expires_at']-cmd['issued_at']==10
    want=hmac.new(DEVICE['sorter'].encode(),api_module.command_canonical('sorter',cmd),hashlib.sha256).hexdigest()
    assert hmac.compare_digest(cmd['signature'],want)
    assert signed_post('/hardware/sorter/next-command',POLL).json()['reason']=='AWAITING_ACK'
    r=c.post('/actuation/estop',json={'reason':'test'})  # no token needed to stop
    assert r.status_code==200 and r.json()['faulted']==['act-1']
    assert signed_post('/hardware/sorter/next-command',POLL).json()['reason']=='ESTOP_LATCHED'
    assert c.post('/actuation/estop/reset').status_code==401
    assert c.post('/actuation/estop/reset',headers=OP).json()['armed'] is False
    assert c.get('/actuation/safety').json()['estop'] is None

# ---------------------------------------------------------------- WEB-01: separated views
def test_website_has_three_separated_views():
    html=c.get('/').text
    for fam in ('physical','sim','agents'):
        assert f'data-family="{fam}"' in html
    for view in ('view-physical','view-lab','view-agents','view-science'):
        assert f'id="{view}"' in html
    assert 'Live Physical Inspection' in html and 'Digital Factory Simulation' in html and 'Agent Collaboration &amp; Benchmark' in html

def test_physical_view_cold_state_is_empty_not_simulated(slot_key):
    r=c.get('/physical/events').json()
    assert r['view']=='PHYSICAL' and r['source']=='hardware_ledger' and r['events']==[] and r['routes']==[]
    assert c.get('/physical/status').json()['ledger_events']==0

def test_physical_view_lists_only_ledger_records_with_derived_tier(slot_key):
    # synthetic, fixture and unauthenticated-feed outputs must never appear in the physical view
    assert c.post('/simulation/compare',json={'n':20,'seed':1}).status_code==200
    assert c.post('/research/collective/run',json={'scenario':'pi_suspect'}).status_code==200
    assert c.post('/sim/live/event',json={'event_id':'live-1','specimen_id':'S-9','station_id':'caliper','observed_at':'2026-10-31T00:00:00Z'}).status_code==200
    assert c.get('/physical/events').json()['events']==[]
    assert signed_post('/hardware/caliper-reading',CAL).status_code==200
    ev=c.get('/physical/events').json()
    assert [e['event_id'] for e in ev['events']]==['e3'] and ev['tiers']=={'PHYSICAL_CAPTURE':1}
    row=ev['events'][0]
    assert row['source_tier']=='PHYSICAL_CAPTURE' and row['verification_status']=='AWAITING_GROUND_TRUTH' and row['station_authenticated']
    assert set(row['values'])<={'measurement_mm','uncertainty_mm','unit'} and 'signature' not in row and 'payload' not in row
    assert verify_caliper().status_code==200
    row=c.get('/physical/events').json()['events'][0]
    assert row['source_tier']=='VERIFIED_PHYSICAL' and row['stored_origin']=='PHYSICAL_CAPTURE'
    assert c.get('/physical/status').json()['ledger_events']==1

def test_physical_events_newest_first_and_bounded(slot_key):
    for i in range(3):
        assert signed_post('/hardware/caliper-reading',{**CAL,'event_id':f'e{i}'}).status_code==200
    assert [e['event_id'] for e in c.get('/physical/events?limit=2').json()['events']]==['e2','e1']
    assert c.get('/physical/events?limit=0').status_code==422 and c.get('/physical/events?limit=201').status_code==422
