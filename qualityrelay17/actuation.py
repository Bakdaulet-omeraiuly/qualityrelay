"""No hardware IO. Safety state machine and idempotent route acknowledgments only."""
from dataclasses import dataclass

@dataclass(frozen=True)
class RouteRequest:
    action_id:str
    specimen_id:str
    bin:str
    decision:str
    operator_id:str
    approved:bool
    origin:str

class SorterInterlock:
    def __init__(self):self.pending={};self.acked={}
    def stage(self, request:RouteRequest):
        if request.action_id in self.pending or request.action_id in self.acked:raise ValueError('duplicate action id')
        if not request.approved or not request.operator_id:raise PermissionError('operator approval required')
        if request.origin!='VERIFIED_PHYSICAL':raise PermissionError('cannot route non-physical evidence')
        if request.bin=='PASS' and request.decision!='AUTHORIZED_PASS':raise PermissionError('PASS needs independent release authorization')
        if request.bin=='REJECT' and request.decision!='CONFIRMED_REJECT':raise PermissionError('REJECT needs confirmed nonconformance')
        if request.bin=='HOLD' and request.decision not in {'HOLD','AUTHORIZED_PASS','CONFIRMED_REJECT'}:raise PermissionError('unknown decision')
        if request.bin not in {'PASS','HOLD','REJECT'}:raise ValueError('bin invalid')
        self.pending[request.action_id]=request
        return {'status':'STAGED_ONLY','hardware_command_emitted':False}
    def acknowledge(self, action_id:str, actual_bin:str, sensor_event_id:str):
        if action_id in self.acked:return {'status':'DUPLICATE_ACK_IGNORED','hardware_command_emitted':False}
        req=self.pending.get(action_id)
        if not req:raise ValueError('unknown action')
        if not sensor_event_id:raise ValueError('physical sensor acknowledgment needed')
        if actual_bin!=req.bin:raise ValueError('route mismatch')
        self.acked[action_id]=(actual_bin,sensor_event_id)
        return {'status':'PHYSICAL_ROUTE_CONFIRMED','hardware_command_emitted':False}
