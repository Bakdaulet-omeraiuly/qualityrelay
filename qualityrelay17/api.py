"""Restricted demo API. Hardware ingestion (/hardware/*) is authenticated per device by a signed
envelope (station_auth.py, BACK-01). Human actions -- staging/approving routes, arming, E-stop
reset, ground-truth verification -- need an operator bearer token (operator_auth.py, BACK-02/04).
VERIFIED_PHYSICAL is derived from recorded ground-truth checks, never written (verification.py).
Still missing before a physical sorter is attached: TLS / server authenticity (CLOUD-01) and the
hardware interlocks in PHYSICAL_TEST_PLAYBOOK.md section 4."""
import os
from collections.abc import Mapping
from pathlib import Path
import time
from fastapi import FastAPI,HTTPException,Request,Depends,Header
from pydantic import BaseModel,Field,ConfigDict
from .factory import compare_policies
from .demo import run_demo
from .ledger import EvidenceLedger
from .actuation import SorterInterlock,RouteRequest,MACHINE_SOURCE
from .station_auth import verify as verify_envelope,EnvelopeError,NonceCache,DEFAULT_TTL_S,HEADER_TS
from . import operator_auth
from .verification import PROCEDURES,VerificationRefused
from .results_api import router as _results_router,legacy_provenance
from . import __version__

app=FastAPI(title=f'QualityRelay {__version__} research API',version=__version__)
class SimRequest(BaseModel):
    n:int=Field(default=1000,ge=1,le=50000)
    seed:int=2026
    process_shift_mm:float=Field(default=0.10,ge=-1,le=1)
    camera_noise:float=Field(default=0.04,ge=0,le=1)
    network_outage:float=Field(default=0.05,ge=0,le=1)

@app.get('/health')
def health():return {'status':'reference_demo','release':__version__,'factory_connected':False,'actuator_connected':False,
                     'hardware_stations_provisioned':sorted(HARDWARE_STATION_KEYS),
                     'device_authenticated_stations':sorted(HARDWARE_DEVICE_KEYS),
                     'station_auth':'per-device signed envelope (X-Station-*), nonce + timestamp window','station_auth_ttl_s':STATION_AUTH_TTL_S,
                     'hardware_ledger':'memory' if HARDWARE_LEDGER_PATH==':memory:' else 'file',
                     'operators_provisioned':len(OPERATOR_TOKENS),'actuation':SORTER.safety()}
@app.get('/demo')
def demo():return run_demo()
@app.post('/simulation/compare')
def simulation(req:SimRequest):
    out=compare_policies(n=req.n,seed=req.seed,process_shift_mm=req.process_shift_mm,
                         camera_noise=req.camera_noise,network_outage=req.network_outage)
    return legacy_provenance(out,run_id=f'compare/n{req.n}/s{req.seed}/shift{req.process_shift_mm}/cam{req.camera_noise}/net{req.network_outage}',
                             assumption_set='economics.Costs@defaults')
@app.get('/research/claims')
def claims():
    return {'proven_new_discovery':False,'simulated_only':True,'camera_model_trained':False,'factory_validation':False,
            'novelty_candidate':'assured physical intervention + provenance-aware decentralized evidence + decision-aware inspection'}

@app.get('/simulation/factory-line')
def factory_line(n:int=100,seed:int=2026,lines:int=1):
    if n<1 or n>10000 or lines<1 or lines>12:raise HTTPException(422,'invalid range')
    from .digital_line import run_line
    return legacy_provenance(run_line(n,seed,lines=lines),run_id=f'factory-line/n{n}/s{seed}/l{lines}',
                             assumption_set='digital_line.stations@defaults')

class CaliperReading(BaseModel):
    event_id:str
    specimen_id:str
    station_id:str
    adc_value:int=Field(ge=0,le=4095)
    uncertainty_mm:float=Field(ge=0)
    calibration_id:str

# Per-station HMAC signing secrets. Never hard-code real values here: they are read from
# the environment (or a git-ignored .env at the repo root) at import time. Generate them with
# scripts/provision_station_keys.py; see docs/engineering/PHYSICAL_TEST_PLAYBOOK.md. With no
# keys provisioned both hardware endpoints return 503, which is the intended cold state.
STATIONS=('slot','tab','sorter','phone','pi','cad')
STATION_KEY_ENV:dict[str,str]={s:f'{s.upper()}_STATION_KEY' for s in STATIONS}   # server-only: signs Evidence
DEVICE_KEY_ENV:dict[str,str]={s:f'{s.upper()}_DEVICE_KEY' for s in STATIONS}     # on the device: authenticates sender
MIN_STATION_KEY_CHARS=32
DOTENV_PATH=Path(__file__).resolve().parent.parent/'.env'

def read_dotenv(path:Path=DOTENV_PATH)->dict[str,str]:
    """Minimal KEY=VALUE reader (no dependency on python-dotenv). Comments and blanks skipped."""
    out:dict[str,str]={}
    if not path.is_file():return out
    for line in path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        k,v=line.split('=',1);out[k.strip()]=v.strip().strip('"').strip("'")
    return out

def load_station_keys(env:Mapping[str,str]|None=None,dotenv:Mapping[str,str]|None=None,
                      env_map:Mapping[str,str]=STATION_KEY_ENV)->dict[str,str]:
    """Real environment wins over .env; blank values mean 'not provisioned' for that station.
    A present-but-short value is a configuration error, not a key, so it is refused loudly
    rather than silently signing with something guessable."""
    env=os.environ if env is None else env
    dotenv=read_dotenv() if dotenv is None else dotenv
    keys:dict[str,str]={}
    for station,var in env_map.items():
        value=(env.get(var) or dotenv.get(var) or '').strip()
        if not value:continue
        if len(value)<MIN_STATION_KEY_CHARS:
            raise RuntimeError(f'{var} is shorter than {MIN_STATION_KEY_CHARS} chars; generate it with scripts/provision_station_keys.py')
        keys[station]=value
    return keys

HARDWARE_STATION_KEYS:dict[str,str]=load_station_keys()
HARDWARE_DEVICE_KEYS:dict[str,str]=load_station_keys(env_map=DEVICE_KEY_ENV)

# BACK-01: which authenticated station may post to which hardware endpoint. A valid sorter
# envelope cannot be replayed as a caliper reading and vice versa.
STATION_ENDPOINT_ACL:dict[str,set[str]]={'/hardware/caliper-reading':{'slot','tab'},'/hardware/bin-ack':{'sorter'},
                                         '/hardware/sorter/next-command':{'sorter'}}
STATION_AUTH_TTL_S=float(os.environ.get('STATION_AUTH_TTL_S') or read_dotenv().get('STATION_AUTH_TTL_S') or DEFAULT_TTL_S)
NONCES=NonceCache(ttl_s=STATION_AUTH_TTL_S)

async def authenticated_station(request:Request)->str:
    """FastAPI dependency: verify the per-device signed envelope (see station_auth.py) and
    return the proven station id. Reads the raw body so the signature covers exactly the
    bytes Pydantic will parse afterwards (Starlette caches request.body())."""
    body=await request.body()
    try:
        return verify_envelope(request.headers,request.method,request.url.path,body,
                               device_keys=HARDWARE_DEVICE_KEYS,acl=STATION_ENDPOINT_ACL,
                               nonce_cache=NONCES,ttl_s=STATION_AUTH_TTL_S)
    except EnvelopeError as ex:
        raise HTTPException(ex.status,ex.detail)

def _require_station_match(claimed:str,authenticated:str)->None:
    if claimed!=authenticated:
        raise HTTPException(403,f'body station_id {claimed!r} does not match authenticated station {authenticated!r}')

def _envelope_time(request:Request)->float:
    """Device clock at send time. Only call after authenticated_station: the signature covers it
    and the window check bounds it, so it is the authenticated sensing time (BACK-03)."""
    return float(int(request.headers[HEADER_TS]))

# BACK-04: human operators. Digests only; see operator_auth.py. No operators = 503 on human routes.
OPERATOR_TOKENS:dict[str,bytes]=operator_auth.load_operator_tokens(os.environ,read_dotenv())

def authenticated_operator(authorization:str|None=Header(default=None))->str:
    if not OPERATOR_TOKENS:
        raise HTTPException(503,'no operators provisioned; see scripts/provision_station_keys.py --operators')
    op=operator_auth.authenticate(authorization,OPERATOR_TOKENS)
    if op is None:
        raise HTTPException(401,'operator bearer token missing or invalid',headers={'WWW-Authenticate':'Bearer'})
    return op

def optional_operator(authorization:str|None=Header(default=None))->str|None:
    return operator_auth.authenticate(authorization,OPERATOR_TOKENS) if authorization else None

# Boundary decision (TOMORROW_TASKS item 2): hardware_ingest.py stays a pure payload->signed
# Evidence transform; persistence and replay rejection happen HERE, at the API, through the
# ledger. In-memory unless HARDWARE_LEDGER_PATH points at a SQLite file (set it for any run
# whose evidence you want to survive a restart). Still local SQLite, not a distributed ledger.
HARDWARE_LEDGER_PATH:str=(os.environ.get('HARDWARE_LEDGER_PATH') or read_dotenv().get('HARDWARE_LEDGER_PATH') or ':memory:').strip() or ':memory:'
HARDWARE_LEDGER=EvidenceLedger(HARDWARE_LEDGER_PATH)

def _env_flag(name:str)->bool:
    return (os.environ.get(name) or read_dotenv().get(name) or '').strip().lower() in {'1','true','yes'}

def _env_float(name:str,default:float)->float:
    return float(os.environ.get(name) or read_dotenv().get(name) or default)

def evidence_gate(req:RouteRequest)->list[str]:
    """BACK-02 meets BACK-04: what the cited evidence must be before a human may approve a route.
    Every bin: each cited record exists, belongs to this specimen and is a station-authenticated
    physical capture (the part is real). PASS/REJECT additionally: at least one cited record is
    effectively VERIFIED_PHYSICAL and none is DISPUTED. Tiers come from the ledger, not the caller."""
    if not req.evidence_ids:return ['no evidence_ids cited']
    problems,verified=[],0
    for eid in req.evidence_ids:
        st=HARDWARE_LEDGER.evidence_status(eid,station_keys=HARDWARE_STATION_KEYS)
        if st is None:problems.append(f'{eid}: not in ledger');continue
        if st['specimen_id']!=req.specimen_id:problems.append(f'{eid}: belongs to {st["specimen_id"]}');continue
        if not st['station_authenticated']:problems.append(f'{eid}: not station-authenticated');continue
        if st['verification_status']=='DISPUTED':problems.append(f'{eid}: ground truth DISPUTED')
        verified+=st['effective_origin']=='VERIFIED_PHYSICAL'
    if req.bin in ('PASS','REJECT') and not verified:
        problems.append(f'{req.bin} needs at least one cited VERIFIED_PHYSICAL record (ground-truth check recorded)')
    return problems

def build_sorter()->SorterInterlock:
    """Process-level interlock. The lookup resolves HARDWARE_LEDGER at call time so a sensor_event_id
    can only ever acknowledge a route if that exact event was recorded through /hardware/bin-ack.
    Hardware gate is OFF unless ACTUATION_HARDWARE_ENABLED=1; even then an operator must arm it."""
    return SorterInterlock(sensor_lookup=lambda event_id:HARDWARE_LEDGER.get_event(event_id),evidence_gate=evidence_gate,
                           journal=HARDWARE_LEDGER,hardware_enabled=_env_flag('ACTUATION_HARDWARE_ENABLED'),
                           stage_ttl_s=_env_float('ACTUATION_STAGE_TTL_S',600),ack_timeout_s=_env_float('ACTUATION_ACK_TIMEOUT_S',30),
                           command_ttl_s=_env_float('ACTUATION_COMMAND_TTL_S',10))
SORTER=build_sorter()

def _persist(evidence,station:str):
    """Append or refuse. A replayed event_id is a 409, never a second signed copy. `station` is
    the envelope-proven station, recorded so the record can become a VERIFIED_PHYSICAL candidate."""
    try:
        HARDWARE_LEDGER.append(evidence,authenticated_station=station)
    except ValueError:
        raise HTTPException(409,f'duplicate event_id {evidence.event_id!r}; replay refused, nothing re-signed')

@app.post('/hardware/caliper-reading')
def hardware_caliper_reading(r:CaliperReading,station:str=Depends(authenticated_station)):
    """Reference ingestion. The sender is authenticated by the per-device envelope BEFORE the
    body is trusted (BACK-01); body.station_id must equal the proven station. Turns one ESP32
    potentiometer ADC reading into a signed
    PHYSICAL_CAPTURE CALIPER Evidence item, appends it to HARDWARE_LEDGER (409 on a replayed
    event_id) and returns it. It does not decide anything by itself."""
    from dataclasses import asdict
    from .hardware_ingest import caliper_evidence
    _require_station_match(r.station_id,station)
    key=HARDWARE_STATION_KEYS.get(r.station_id)
    if not key:
        raise HTTPException(503,'station key not provisioned; see PHYSICAL_TEST_PLAYBOOK.md')
    try:
        evidence=caliper_evidence(event_id=r.event_id,specimen_id=r.specimen_id,station_id=r.station_id,
                                  adc_value=r.adc_value,uncertainty_mm=r.uncertainty_mm,
                                  calibration_id=r.calibration_id,key=key)
    except ValueError as ex:
        raise HTTPException(422,str(ex))  # ingest-layer refusal: nothing signed, nothing persisted
    _persist(evidence,station)
    return asdict(evidence)

class BinAck(BaseModel):
    event_id:str
    specimen_id:str
    station_id:str
    bin_name:str
    photoresistor_blocked:bool
    action_id:str|None=None  # optional: binds the ACK to one action instead of 'the in-flight one for this specimen'

@app.post('/hardware/bin-ack')
def hardware_bin_ack(r:BinAck,request:Request,station:str=Depends(authenticated_station)):
    """Reference ingestion for the photoresistor+4N35 independent bin sensor (H5/E12/E13
    in docs/research/EXPERIMENT_PROTOCOL.md). Signing a false reading is refused below the
    hardware_ingest layer, not just here -- see bin_ack_evidence().

    Sensor fired -> route confirmed: once the ROUTE_ACK is persisted, its event_id is handed
    to SORTER.acknowledge() for the specimen's pending route. The response carries both the
    evidence and the interlock outcome; E12 (wrong bin) is ROUTE_MISMATCH and latches the action
    as FAULTED, E13 (second trigger for a confirmed part) is DUPLICATE_ACK_IGNORED."""
    from dataclasses import asdict
    from .hardware_ingest import bin_ack_evidence
    _require_station_match(r.station_id,station)
    key=HARDWARE_STATION_KEYS.get(r.station_id)
    if not key:
        raise HTTPException(503,'station key not provisioned; see PHYSICAL_TEST_PLAYBOOK.md')
    try:
        evidence=bin_ack_evidence(event_id=r.event_id,specimen_id=r.specimen_id,station_id=r.station_id,
                                  bin_name=r.bin_name,photoresistor_blocked=r.photoresistor_blocked,key=key)
    except ValueError as ex:
        raise HTTPException(422,str(ex))  # ingest-layer refusal: nothing signed, nothing persisted
    _persist(evidence,station)
    return {'evidence':asdict(evidence),'interlock':_route_ack(evidence,r.action_id,_envelope_time(request))}

def _route_ack(evidence,action_id:str|None,sensed_at:float)->dict:
    """Feed a persisted ROUTE_ACK to the interlock (BACK-03). Never raises: the sensor reading is
    already recorded, and a mismatch is a result the operator must see, not a failed request.
    Binding: the named action_id if given, else the single in-flight action for this specimen.
    Two in-flight actions for one specimen are AMBIGUOUS_ACK -- guessing would be a false binding."""
    if action_id is None:
        in_flight=SORTER.in_flight_for_specimen(evidence.specimen_id)
        if not in_flight:
            return {'status':'NO_PENDING_ACTION','specimen_id':evidence.specimen_id,'hardware_command_emitted':False}
        if len(in_flight)>1:
            return {'status':'AMBIGUOUS_ACK','specimen_id':evidence.specimen_id,'candidates':[x.action_id for x in in_flight],
                    'detail':'more than one in-flight route for this specimen; resend with action_id','hardware_command_emitted':False}
        req=in_flight[0]
    else:
        found=SORTER.request_for(action_id)
        if found is None:
            return {'status':'ACK_REFUSED','action_id':action_id,'detail':'unknown action','hardware_command_emitted':False}
        req=found
    out={'action_id':req.action_id,'specimen_id':req.specimen_id,'station_id':evidence.station_id,'expected_bin':req.bin,
         'actual_bin':evidence.payload['bin'],'sensor_event_id':evidence.event_id,'sensed_at':sensed_at,'hardware_command_emitted':False}
    try:
        out.update(SORTER.acknowledge(req.action_id,evidence.payload['bin'],evidence.event_id,sensed_at=sensed_at))
    except ValueError as ex:
        out.update(status='ROUTE_MISMATCH' if str(ex)=='route mismatch' else 'ACK_REFUSED',detail=str(ex))
    return out

class SorterPoll(BaseModel):
    station_id:str
    estop_loop_ok:bool=False   # hard-wired E-stop chain closed (read from the loop, not a software flag)
    guard_closed:bool=False    # guard / cover interlock switch closed
    position:str='UNKNOWN'     # what the device believes its gate is at; logged, not trusted

def command_canonical(station:str,cmd:dict)->bytes:
    """Byte string the sorter verifies before moving. Keep in sync with any sorter firmware."""
    return '\n'.join(['ROUTE',station,cmd['action_id'],cmd['specimen_id'],cmd['bin'],cmd['command_nonce'],
                      str(cmd['issued_at']),str(cmd['expires_at'])]).encode()

@app.post('/hardware/sorter/next-command')
def sorter_next_command(r:SorterPoll,station:str=Depends(authenticated_station)):
    """Pull model (BACK-04): the sorter asks; the default answer is HOLD. A ROUTE command is signed
    with this station's device key (the device already holds it) so the device can check
    authenticity and expires_at before moving. No firmware consumes this yet; with
    ACTUATION_HARDWARE_ENABLED unset it never returns anything but HOLD."""
    import hmac,hashlib
    _require_station_match(r.station_id,station)
    cmd=SORTER.next_command(station,r.model_dump())
    if cmd['command']=='ROUTE':
        cmd['signature']=hmac.new(HARDWARE_DEVICE_KEYS[station].encode(),command_canonical(station,cmd),hashlib.sha256).hexdigest()
    return cmd

class StageRequest(BaseModel):
    # extra='forbid': the old caller-asserted operator_id / approved / origin fields are refused
    # loudly (422) instead of being silently ignored by a client that thinks they still mean something.
    model_config=ConfigDict(extra='forbid')
    action_id:str=Field(min_length=1,max_length=128)
    specimen_id:str=Field(min_length=1,max_length=128)
    bin:str
    decision:str
    evidence_ids:list[str]=Field(default_factory=list,max_length=32)

class ProposeRequest(StageRequest):
    recommended_by:str=Field(description="machine source: 'safe_mesh', 'llm:<provider>', 'agent:<role>' or 'ai:<name>'")

def _actuation_call(fn,*a,**kw):
    try:
        return fn(*a,**kw)
    except PermissionError as ex:
        raise HTTPException(403,str(ex))
    except ValueError as ex:
        raise HTTPException(409,str(ex))

def _route_request(r:StageRequest,recommended_by:str='human')->RouteRequest:
    return RouteRequest(action_id=r.action_id,specimen_id=r.specimen_id,bin=r.bin,decision=r.decision,
                        recommended_by=recommended_by,evidence_ids=tuple(r.evidence_ids))

@app.post('/actuation/stage')
def actuation_stage(r:StageRequest,operator:str=Depends(authenticated_operator)):
    """Human one-step route: propose + approve by the authenticated operator (STAGED_ONLY; nothing
    moves). The evidence gate reads tiers from the ledger; PASS/REJECT need cited VERIFIED_PHYSICAL."""
    return _actuation_call(SORTER.stage,_route_request(r),operator)

@app.post('/actuation/propose')
def actuation_propose(r:ProposeRequest):
    """AI/agent recommendation. Records a PROPOSED action; it cannot stage, dispatch or move
    anything and needs POST /actuation/{id}/approve by a human. recommended_by is caller-asserted
    advisory provenance, restricted to machine sources so it cannot impersonate a human approval."""
    if not MACHINE_SOURCE.match(r.recommended_by):
        raise HTTPException(422,"recommended_by must be 'safe_mesh', 'llm:<x>', 'agent:<x>' or 'ai:<x>'; humans use /actuation/stage")
    return _actuation_call(SORTER.propose,_route_request(r,r.recommended_by))

class EstopRequest(BaseModel):
    reason:str=Field(default='',max_length=200)

# Fixed paths are registered before /actuation/{action_id}/... so 'estop', 'arm', etc. never
# parse as an action id.
@app.post('/actuation/estop')
def actuation_estop(r:EstopRequest|None=None,operator:str|None=Depends(optional_operator)):
    """Software E-stop. Deliberately needs NO token: stopping is the fail-safe direction, and anyone
    at the cell must be able to do it. It complements, never replaces, the hard-wired E-stop."""
    return SORTER.emergency_stop(f'operator:{operator}' if operator else 'unauthenticated',(r.reason if r else ''))

@app.post('/actuation/estop/reset')
def actuation_estop_reset(operator:str=Depends(authenticated_operator)):
    return _actuation_call(SORTER.reset_estop,operator)

@app.post('/actuation/arm')
def actuation_arm(operator:str=Depends(authenticated_operator)):
    return _actuation_call(SORTER.arm,operator)

@app.post('/actuation/disarm')
def actuation_disarm(operator:str|None=Depends(optional_operator)):
    return SORTER.disarm(f'operator:{operator}' if operator else 'unauthenticated')

@app.get('/actuation/safety')
def actuation_safety():
    return SORTER.safety()

@app.get('/actuation/journal/{action_id}')
def actuation_journal(action_id:str):
    """Append-only route journal for one action (every transition, with the full binding)."""
    return {'action_id':action_id,'events':HARDWARE_LEDGER.route_events(action_id)}

@app.post('/actuation/{action_id}/approve')
def actuation_approve(action_id:str,operator:str=Depends(authenticated_operator)):
    return _actuation_call(SORTER.approve,action_id,operator)

class IdentityCheck(BaseModel):
    observed_specimen_id:str=Field(min_length=1,max_length=128)

@app.post('/actuation/{action_id}/identity')
def actuation_identity(action_id:str,r:IdentityCheck,operator:str=Depends(authenticated_operator)):
    """Operator reads the label/QR of the part in the bin (BACK-03). Mismatch latches FAULTED."""
    return _actuation_call(SORTER.confirm_identity,action_id,operator,r.observed_specimen_id)

@app.get('/actuation/{action_id}')
def actuation_status(action_id:str):
    return SORTER.status(action_id)

# ---------------------------------------------------------------- BACK-02: ground-truth verification
class VerifyRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    procedure_id:str
    observed_specimen_id:str
    reference_value_mm:float|None=None
    reference_uncertainty_mm:float|None=Field(default=None,ge=0)
    reference_instrument_id:str|None=None
    reference_calibration_id:str|None=None
    observed_verdict:str|None=None
    notes:str=Field(default='',max_length=500)

@app.get('/evidence/procedures')
def evidence_procedures():
    return {pid:{'title':p.title,'kinds':sorted(p.kinds),'required_fields':list(p.required_fields),'doc':p.doc_section}
            for pid,p in PROCEDURES.items()}

@app.get('/evidence/{event_id}/status')
def evidence_status(event_id:str):
    st=HARDWARE_LEDGER.evidence_status(event_id,station_keys=HARDWARE_STATION_KEYS)
    if st is None:raise HTTPException(404,'unknown event_id')
    return st

@app.post('/evidence/{event_id}/verify')
def evidence_verify(event_id:str,r:VerifyRequest,operator:str=Depends(authenticated_operator)):
    """Record one human/instrument ground-truth check (see GROUND_TRUTH_VERIFICATION_PROCEDURE.md).
    Disagreement is recorded as DISPUTED (200) and latches; refused preconditions record nothing."""
    try:
        return HARDWARE_LEDGER.record_verification(event_id,r.model_dump(),verifier_id=operator,
                                                   station_keys=HARDWARE_STATION_KEYS,station_ids=set(STATIONS),now=time.time())
    except VerificationRefused as ex:
        raise HTTPException(ex.status,ex.detail)

# ---------------------------------------------------------------- WEB-01: Live Physical Inspection view
# Read-only. Only the hardware ledger feeds this view: no simulator, fixture or LLM output is ever
# listed here. Tiers are derived per row (evidence_status), so VERIFIED_PHYSICAL appears only after a
# recorded ground-truth check. The unauthenticated /sim/live feed is a separate, labelled channel.
PHYSICAL_DISPLAY_FIELDS=('measurement_mm','uncertainty_mm','unit','bin','temperature_c')

@app.get('/physical/status')
def physical_status():
    st=SORTER.safety()
    return {'view':'PHYSICAL','source':'hardware_ledger','factory_connected':False,
            'hardware_stations_provisioned':sorted(HARDWARE_STATION_KEYS),
            'device_authenticated_stations':sorted(HARDWARE_DEVICE_KEYS),
            'operators_provisioned':len(OPERATOR_TOKENS),
            'hardware_ledger':'memory' if HARDWARE_LEDGER_PATH==':memory:' else 'file',
            'ledger_events':HARDWARE_LEDGER.count_events(),'actuation':st}

@app.get('/physical/events')
def physical_events(limit:int=50):
    if limit<1 or limit>200:raise HTTPException(422,'limit must be 1..200')
    rows:list[dict]=[];tiers:dict[str,int]={}
    for eid in HARDWARE_LEDGER.recent_event_ids(limit):
        ev=HARDWARE_LEDGER.get_event(eid)
        st=HARDWARE_LEDGER.evidence_status(eid,station_keys=HARDWARE_STATION_KEYS)
        if ev is None or st is None:continue
        tier=st['effective_origin']
        tiers[tier]=tiers.get(tier,0)+1
        rows.append({'event_id':eid,'specimen_id':st['specimen_id'],'station_id':st['station_id'],'kind':st['kind'],
                     'observed_at':ev.get('observed_at'),'verdict':ev.get('verdict'),'calibration_id':ev.get('calibration_id') or None,
                     'stored_origin':st['stored_origin'],'source_tier':tier,'verification_status':st['verification_status'],
                     'station_authenticated':st['station_authenticated'],'candidate_problems':st['candidate_problems'],
                     'values':{k:v for k,v in (ev.get('payload') or {}).items() if k in PHYSICAL_DISPLAY_FIELDS}})
    return {'view':'PHYSICAL','source':'hardware_ledger','count':len(rows),'tiers':tiers,'events':rows,
            'routes':HARDWARE_LEDGER.route_events()[-limit:][::-1]}

# ---------------------------------------------------------------- research: structured collaboration
# Plan section 7.3 routes. In-process, TEST_FIXTURE evidence, deterministic roles, no LLM, no actuation.
COLLECTIVE_RUNS:dict[str,dict]={}

class CollectiveRunRequest(BaseModel):
    scenario:str='pi_suspect'
    request_cost:float=Field(default=0.3,ge=0,le=10)
    budget:float=Field(default=1.0,ge=0,le=100)
    planner:str=Field(default='deterministic',description="'deterministic' or a provider in collective.llm_planner.PROVIDERS")

def _llm_env()->dict[str,str]:
    """Real environment wins over the git-ignored .env, same rule as the station keys."""
    return {**read_dotenv(),**{k:v for k,v in os.environ.items() if v}}

def _resolve_planner(name:str):
    if name=='deterministic':return None,{'planner':'deterministic'}
    from .collective.llm_planner import PROVIDERS
    factory=PROVIDERS.get(name)
    if factory is None:raise HTTPException(422,f'unknown planner {name!r}; one of {["deterministic",*sorted(PROVIDERS)]}')
    planner,status=factory(_llm_env())
    if planner is None:raise HTTPException(503,f'{name} planner not configured: {status}')
    return planner,status

@app.get('/integrations/llm')
def llm_status():
    """Configuration only; no paid call is made here. CONFIGURED_NOT_VERIFIED until a run succeeds."""
    from .collective.llm_planner import PROVIDERS
    out={}
    for name,factory in PROVIDERS.items():
        try:out[name]=factory(_llm_env())[1]
        except Exception as ex:out[name]={'provider':name,'state':'ERROR','detail':type(ex).__name__}
    if 'nebius' in out:  # LLM-01: last recorded entitlement check (scripts/verify_nebius_entitlement.py); never a live call
        from .llm_entitlement import latest_status
        try:out['nebius']['entitlement']=latest_status(out['nebius'].get('model'))
        except (OSError,ValueError) as ex:out['nebius']['entitlement']={'state':'ERROR','detail':type(ex).__name__}
    return {'providers':out,'decision_authority':'none: LLM planners only propose evidence requests; safe_mesh decides'}

@app.get('/research/collective/scenarios')
def collective_scenarios():
    from .collective.scenarios import SCENARIOS
    return {'origin':'TEST_FIXTURE','scenarios':SCENARIOS,
            'note':'deterministic roles over fixture evidence; demonstrates the protocol, ACL, VERIFY and trace, not LLM reasoning'}

@app.post('/research/collective/run')
def collective_run(req:CollectiveRunRequest):
    import secrets
    from .collective.scenarios import build
    planner,planner_status=_resolve_planner(req.planner)
    try:
        result=build(req.scenario,request_cost=req.request_cost,budget=req.budget,planner=planner)
    except ValueError as ex:
        raise HTTPException(422,str(ex))
    run_id=f'col-{secrets.token_hex(4)}'
    run={'run_id':run_id,'origin':'TEST_FIXTURE','scenario':req.scenario,'request_cost':req.request_cost,'budget':req.budget,
         'cases':{result.case_id:result.to_dict()},
         'manifest':{'origin':'TEST_FIXTURE','planner':result.planner or planner_status,
                     'roles_are_code_not_llm':req.planner=='deterministic','likelihoods':result.proposal.get('likelihood_source'),
                     'comparison_is_single_case':'no claim of improvement from one narrative trace'}}
    COLLECTIVE_RUNS[run_id]=run
    if len(COLLECTIVE_RUNS)>200:COLLECTIVE_RUNS.pop(next(iter(COLLECTIVE_RUNS)))
    return {'run_id':run_id,'origin':'TEST_FIXTURE','case_id':result.case_id,'decision':result.decision['state'],
            'control_decision':result.control_decision['state'],'decision_changed':result.decision_changed,
            'criteria':result.criteria,'planner':result.planner,'narrative':result.narrative}

@app.get('/research/collective/runs/{run_id}')
def collective_run_get(run_id:str):
    run=COLLECTIVE_RUNS.get(run_id)
    if not run:raise HTTPException(404,'unknown run')
    return {k:v for k,v in run.items() if k!='cases'}|{'case_ids':list(run['cases'])}

@app.get('/research/collective/runs/{run_id}/traces/{part_id}')
def collective_trace(run_id:str,part_id:str):
    run=COLLECTIVE_RUNS.get(run_id)
    if not run or part_id not in run['cases']:raise HTTPException(404,'unknown run or part')
    return run['cases'][part_id]

@app.get('/research/collective/runs/{run_id}/manifest')
def collective_manifest(run_id:str):
    run=COLLECTIVE_RUNS.get(run_id)
    if not run:raise HTTPException(404,'unknown run')
    return run['manifest']

@app.get('/integrations')
def integrations_status():
    """REL-03: every adapter's evidence-backed status (WORKING / TESTED / NOT_CONFIGURED) from
    THIRD_PARTY_MANIFEST.json. A record, not a live probe; `scope` says what each status covers."""
    from dataclasses import asdict
    from .external_adapters import adapters,summary
    return {'adapters':{k:asdict(v.health()) for k,v in adapters().items()}}|summary()

@app.get('/integrations/nvidia')
def nvidia_status():
    from dataclasses import asdict
    from .external_adapters import NVIDIA_ADAPTERS
    return {k:asdict(v.health()) for k,v in NVIDIA_ADAPTERS.items()}

@app.get('/',include_in_schema=False)
def website():
    from fastapi.responses import FileResponse
    from pathlib import Path
    return FileResponse(Path(__file__).resolve().parent.parent/'web'/'index.html')

@app.get('/legacy',include_in_schema=False)
def website_legacy():
    from fastapi.responses import FileResponse
    from pathlib import Path
    return FileResponse(Path(__file__).resolve().parent.parent/'web'/'legacy_17.html')

# 18.1 science/simulation read-only routes (Bakdaulet; proposal for adilnurgg's API-01)
from .sim.api_routes import router as _sim_router  # noqa: E402
app.include_router(_sim_router)
# API-01: /simulation/*, /benchmark/*, /economics/* over the registered 18.1 results (results_api.py)
app.include_router(_results_router)

@app.get('/examples/cad/{filename}',include_in_schema=False)
def cad_example(filename:str):
    from fastapi.responses import FileResponse
    from pathlib import Path
    if filename not in {'slot_nominal_21p00_top_projected.png','tab_nominal_20p00_top_projected.png'}:
        raise HTTPException(404,'unknown example')
    return FileResponse(Path(__file__).resolve().parent.parent/'examples'/'cad'/filename)
