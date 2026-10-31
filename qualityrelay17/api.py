"""Restricted demo API; deploy only behind authentication before adding PHYSICAL inputs."""
import os
from collections.abc import Mapping
from pathlib import Path
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from .factory import compare_policies
from .vder import Inspection,action_scores
from .demo import run_demo
from .ledger import EvidenceLedger
from .actuation import SorterInterlock,RouteRequest

app=FastAPI(title='QualityRelay17 research API',version='0.1.0')
class SimRequest(BaseModel):
    n:int=Field(default=1000,ge=1,le=50000)
    seed:int=2026
    process_shift_mm:float=Field(default=0.10,ge=-1,le=1)
    camera_noise:float=Field(default=0.04,ge=0,le=1)
    network_outage:float=Field(default=0.05,ge=0,le=1)

@app.get('/health')
def health():return {'status':'reference_demo','factory_connected':False,'actuator_connected':False,
                     'hardware_stations_provisioned':sorted(HARDWARE_STATION_KEYS),
                     'hardware_ledger':'memory' if HARDWARE_LEDGER_PATH==':memory:' else 'file'}
@app.get('/demo')
def demo():return run_demo()
@app.post('/simulation/compare')
def simulation(req:SimRequest):
    return compare_policies(n=req.n,seed=req.seed,process_shift_mm=req.process_shift_mm,
                            camera_noise=req.camera_noise,network_outage=req.network_outage)
@app.get('/research/claims')
def claims():
    return {'proven_new_discovery':False,'simulated_only':True,'camera_model_trained':False,'factory_validation':False,
            'novelty_candidate':'assured physical intervention + provenance-aware decentralized evidence + decision-aware inspection'}

@app.get('/simulation/factory-line')
def factory_line(n:int=100,seed:int=2026,lines:int=1):
    if n<1 or n>10000 or lines<1 or lines>12:raise HTTPException(422,'invalid range')
    from .digital_line import run_line
    return run_line(n,seed,lines=lines)

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
STATION_KEY_ENV:dict[str,str]={'slot':'SLOT_STATION_KEY','tab':'TAB_STATION_KEY','sorter':'SORTER_STATION_KEY',
                               'phone':'PHONE_STATION_KEY','pi':'PI_STATION_KEY','cad':'CAD_STATION_KEY'}
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

def load_station_keys(env:Mapping[str,str]|None=None,dotenv:Mapping[str,str]|None=None)->dict[str,str]:
    """Real environment wins over .env; blank values mean 'not provisioned' for that station.
    A present-but-short value is a configuration error, not a key, so it is refused loudly
    rather than silently signing with something guessable."""
    env=os.environ if env is None else env
    dotenv=read_dotenv() if dotenv is None else dotenv
    keys:dict[str,str]={}
    for station,var in STATION_KEY_ENV.items():
        value=(env.get(var) or dotenv.get(var) or '').strip()
        if not value:continue
        if len(value)<MIN_STATION_KEY_CHARS:
            raise RuntimeError(f'{var} is shorter than {MIN_STATION_KEY_CHARS} chars; generate it with scripts/provision_station_keys.py')
        keys[station]=value
    return keys

HARDWARE_STATION_KEYS:dict[str,str]=load_station_keys()

# Boundary decision (TOMORROW_TASKS item 2): hardware_ingest.py stays a pure payload->signed
# Evidence transform; persistence and replay rejection happen HERE, at the API, through the
# ledger. In-memory unless HARDWARE_LEDGER_PATH points at a SQLite file (set it for any run
# whose evidence you want to survive a restart). Still local SQLite, not a distributed ledger.
HARDWARE_LEDGER_PATH:str=(os.environ.get('HARDWARE_LEDGER_PATH') or read_dotenv().get('HARDWARE_LEDGER_PATH') or ':memory:').strip() or ':memory:'
HARDWARE_LEDGER=EvidenceLedger(HARDWARE_LEDGER_PATH)

# Process-level interlock. The lookup resolves HARDWARE_LEDGER at call time so a sensor_event_id
# can only ever acknowledge a route if that exact event was recorded through /hardware/bin-ack.
SORTER=SorterInterlock(sensor_lookup=lambda event_id:HARDWARE_LEDGER.get_event(event_id))

def _persist(evidence):
    """Append or refuse. A replayed event_id is a 409, never a second signed copy."""
    try:
        HARDWARE_LEDGER.append(evidence)
    except ValueError:
        raise HTTPException(409,f'duplicate event_id {evidence.event_id!r}; replay refused, nothing re-signed')

@app.post('/hardware/caliper-reading')
def hardware_caliper_reading(r:CaliperReading):
    """Reference ingestion only -- same 'authenticate before PHYSICAL input' warning as
    the rest of this file. Turns one ESP32 potentiometer ADC reading into a signed
    PHYSICAL_CAPTURE CALIPER Evidence item, appends it to HARDWARE_LEDGER (409 on a replayed
    event_id) and returns it. It does not decide anything by itself."""
    from dataclasses import asdict
    from .hardware_ingest import caliper_evidence
    key=HARDWARE_STATION_KEYS.get(r.station_id)
    if not key:
        raise HTTPException(503,'station key not provisioned; see PHYSICAL_TEST_PLAYBOOK.md')
    try:
        evidence=caliper_evidence(event_id=r.event_id,specimen_id=r.specimen_id,station_id=r.station_id,
                                  adc_value=r.adc_value,uncertainty_mm=r.uncertainty_mm,
                                  calibration_id=r.calibration_id,key=key)
    except ValueError as ex:
        raise HTTPException(422,str(ex))  # ingest-layer refusal: nothing signed, nothing persisted
    _persist(evidence)
    return asdict(evidence)

class BinAck(BaseModel):
    event_id:str
    specimen_id:str
    station_id:str
    bin_name:str
    photoresistor_blocked:bool

@app.post('/hardware/bin-ack')
def hardware_bin_ack(r:BinAck):
    """Reference ingestion for the photoresistor+4N35 independent bin sensor (H5/E12/E13
    in docs/research/EXPERIMENT_PROTOCOL.md). Signing a false reading is refused below the
    hardware_ingest layer, not just here -- see bin_ack_evidence().

    Sensor fired -> route confirmed: once the ROUTE_ACK is persisted, its event_id is handed
    to SORTER.acknowledge() for the specimen's pending route. The response carries both the
    evidence and the interlock outcome; E12 (wrong bin) is ROUTE_MISMATCH and latches the action
    as FAULTED, E13 (second trigger for a confirmed part) is DUPLICATE_ACK_IGNORED."""
    from dataclasses import asdict
    from .hardware_ingest import bin_ack_evidence
    key=HARDWARE_STATION_KEYS.get(r.station_id)
    if not key:
        raise HTTPException(503,'station key not provisioned; see PHYSICAL_TEST_PLAYBOOK.md')
    try:
        evidence=bin_ack_evidence(event_id=r.event_id,specimen_id=r.specimen_id,station_id=r.station_id,
                                  bin_name=r.bin_name,photoresistor_blocked=r.photoresistor_blocked,key=key)
    except ValueError as ex:
        raise HTTPException(422,str(ex))  # ingest-layer refusal: nothing signed, nothing persisted
    _persist(evidence)
    return {'evidence':asdict(evidence),'interlock':_route_ack(evidence)}

def _route_ack(evidence)->dict:
    """Feed a persisted ROUTE_ACK to the interlock. Never raises: the sensor reading is already
    recorded, and a mismatch is a result the operator must see, not a failed request."""
    pending=SORTER.pending_for_specimen(evidence.specimen_id)
    if not pending:
        return {'status':'NO_PENDING_ACTION','specimen_id':evidence.specimen_id,'hardware_command_emitted':False}
    req=pending[0]
    out={'action_id':req.action_id,'expected_bin':req.bin,'actual_bin':evidence.payload['bin'],
         'sensor_event_id':evidence.event_id,'hardware_command_emitted':False}
    if len(pending)>1:out['warning']=f'{len(pending)} pending routes for this specimen; acknowledged the oldest'
    try:
        out.update(SORTER.acknowledge(req.action_id,evidence.payload['bin'],evidence.event_id))
    except ValueError as ex:
        out.update(status='ROUTE_MISMATCH' if str(ex)=='route mismatch' else 'ACK_REFUSED',detail=str(ex))
    return out

class StageRequest(BaseModel):
    action_id:str
    specimen_id:str
    bin:str
    decision:str
    operator_id:str
    approved:bool
    origin:str

@app.post('/actuation/stage')
def actuation_stage(r:StageRequest):
    """Stage a route in the no-IO interlock (STAGED_ONLY; nothing moves). Same caveat as the
    module docstring: approval/origin here are asserted by the caller, so this must sit behind
    real authentication before any physical sorter is attached."""
    try:
        return SORTER.stage(RouteRequest(**r.model_dump()))
    except PermissionError as ex:
        raise HTTPException(403,str(ex))
    except ValueError as ex:
        raise HTTPException(409,str(ex))

@app.get('/actuation/{action_id}')
def actuation_status(action_id:str):
    return SORTER.status(action_id)

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

@app.get('/examples/cad/{filename}',include_in_schema=False)
def cad_example(filename:str):
    from fastapi.responses import FileResponse
    from pathlib import Path
    if filename not in {'slot_nominal_21p00_top_projected.png','tab_nominal_20p00_top_projected.png'}:
        raise HTTPException(404,'unknown example')
    return FileResponse(Path(__file__).resolve().parent.parent/'examples'/'cad'/filename)
