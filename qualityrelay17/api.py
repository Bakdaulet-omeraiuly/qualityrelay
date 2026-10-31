"""Restricted demo API; deploy only behind authentication before adding PHYSICAL inputs."""
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from .factory import compare_policies
from .vder import Inspection,action_scores
from .demo import run_demo

app=FastAPI(title='QualityRelay17 research API',version='0.1.0')
class SimRequest(BaseModel):
    n:int=Field(default=1000,ge=1,le=50000)
    seed:int=2026
    process_shift_mm:float=Field(default=0.10,ge=-1,le=1)
    camera_noise:float=Field(default=0.04,ge=0,le=1)
    network_outage:float=Field(default=0.05,ge=0,le=1)

@app.get('/health')
def health():return {'status':'reference_demo','factory_connected':False,'actuator_connected':False}
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

# Empty by design: provision real per-station secrets yourself before this endpoint
# can sign anything. See docs/engineering/PHYSICAL_TEST_PLAYBOOK.md.
HARDWARE_STATION_KEYS:dict[str,str]={}

@app.post('/hardware/caliper-reading')
def hardware_caliper_reading(r:CaliperReading):
    """Reference ingestion only -- same 'authenticate before PHYSICAL input' warning as
    the rest of this file. Turns one ESP32 potentiometer ADC reading into a signed
    PHYSICAL_CAPTURE CALIPER Evidence item; it does not append to a ledger or decide
    anything by itself."""
    from dataclasses import asdict
    from .hardware_ingest import caliper_evidence
    key=HARDWARE_STATION_KEYS.get(r.station_id)
    if not key:
        raise HTTPException(503,'station key not provisioned; see PHYSICAL_TEST_PLAYBOOK.md')
    evidence=caliper_evidence(event_id=r.event_id,specimen_id=r.specimen_id,station_id=r.station_id,
                              adc_value=r.adc_value,uncertainty_mm=r.uncertainty_mm,
                              calibration_id=r.calibration_id,key=key)
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
    hardware_ingest layer, not just here -- see bin_ack_evidence()."""
    from dataclasses import asdict
    from .hardware_ingest import bin_ack_evidence
    key=HARDWARE_STATION_KEYS.get(r.station_id)
    if not key:
        raise HTTPException(503,'station key not provisioned; see PHYSICAL_TEST_PLAYBOOK.md')
    evidence=bin_ack_evidence(event_id=r.event_id,specimen_id=r.specimen_id,station_id=r.station_id,
                              bin_name=r.bin_name,photoresistor_blocked=r.photoresistor_blocked,key=key)
    return asdict(evidence)

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
