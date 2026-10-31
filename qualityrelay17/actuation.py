"""No hardware IO. Safety state machine and idempotent route acknowledgments only.

'Sensor fired' -> 'route confirmed' wiring (TOMORROW_TASKS item 3): acknowledge() takes a
sensor_event_id. When the interlock is built with a sensor_lookup (api.py passes the evidence
ledger's get_event), that id must resolve to a *recorded* ROUTE_ACK for the same specimen and
the same bin -- a caller-supplied string is no longer enough. Without a lookup (unit tests,
offline use) the id is trusted as given, which is why the API always supplies one.
"""
import threading
from dataclasses import dataclass
from typing import Callable, Optional

SensorLookup = Callable[[str], Optional[dict]]  # event_id -> stored Evidence dict, or None

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
    def __init__(self, sensor_lookup:SensorLookup|None=None):
        self.pending={};self.acked={};self.faulted={}
        self.used_sensor_events:set[str]=set()
        self.sensor_lookup=sensor_lookup
        # One lock for every state transition. FastAPI handles bounce edges on parallel threads
        # and sensor_lookup does I/O (GIL released) between the 'already acked?' check and the
        # write, so without this two edges for one arrival can both confirm -- found by
        # tests/test_actuation_sensor_wiring.py::test_concurrent_bounce_edges_confirm_exactly_once.
        self._lock=threading.RLock()

    def stage(self, request:RouteRequest):
        with self._lock:return self._stage(request)

    def _stage(self, request:RouteRequest):
        if request.action_id in self.pending or request.action_id in self.acked or request.action_id in self.faulted:raise ValueError('duplicate action id')
        if not request.approved or not request.operator_id:raise PermissionError('operator approval required')
        if request.origin!='VERIFIED_PHYSICAL':raise PermissionError('cannot route non-physical evidence')
        if request.bin=='PASS' and request.decision!='AUTHORIZED_PASS':raise PermissionError('PASS needs independent release authorization')
        if request.bin=='REJECT' and request.decision!='CONFIRMED_REJECT':raise PermissionError('REJECT needs confirmed nonconformance')
        if request.bin=='HOLD' and request.decision not in {'HOLD','AUTHORIZED_PASS','CONFIRMED_REJECT'}:raise PermissionError('unknown decision')
        if request.bin not in {'PASS','HOLD','REJECT'}:raise ValueError('bin invalid')
        self.pending[request.action_id]=request
        return {'status':'STAGED_ONLY','hardware_command_emitted':False}

    def pending_for_specimen(self, specimen_id:str)->list[RouteRequest]:
        """Oldest first. The API acknowledges the first one; more than one pending route for
        a single specimen is itself a staging error worth surfacing, not silently resolving."""
        with self._lock:return [r for r in self.pending.values() if r.specimen_id==specimen_id]

    def _verify_sensor_event(self, req:RouteRequest, actual_bin:str, sensor_event_id:str):
        if self.sensor_lookup is None:return
        ev=self.sensor_lookup(sensor_event_id)
        if ev is None:raise ValueError('sensor event not recorded in ledger')
        if ev.get('kind')!='ROUTE_ACK':raise ValueError('sensor event is not a ROUTE_ACK')
        if ev.get('specimen_id')!=req.specimen_id:raise ValueError('sensor event belongs to a different specimen')
        if ev.get('payload',{}).get('bin')!=actual_bin:raise ValueError('sensor event bin does not match reported bin')

    def acknowledge(self, action_id:str, actual_bin:str, sensor_event_id:str):
        with self._lock:return self._acknowledge(action_id,actual_bin,sensor_event_id)

    def _acknowledge(self, action_id:str, actual_bin:str, sensor_event_id:str):
        if action_id in self.acked:return {'status':'DUPLICATE_ACK_IGNORED','hardware_command_emitted':False}
        if action_id in self.faulted:raise ValueError('action faulted after route mismatch; operator must re-stage')
        req=self.pending.get(action_id)
        if not req:raise ValueError('unknown action')
        if not sensor_event_id:raise ValueError('physical sensor acknowledgment needed')
        if sensor_event_id in self.used_sensor_events:raise ValueError('sensor event already consumed by another action')  # E13
        self._verify_sensor_event(req,actual_bin,sensor_event_id)
        if actual_bin!=req.bin:  # E12: discrepancy is latched, never counted, never auto-recovered
            self.faulted[action_id]=(req.bin,actual_bin,sensor_event_id);self.pending.pop(action_id)
            raise ValueError('route mismatch')
        self.used_sensor_events.add(sensor_event_id)
        self.acked[action_id]=(actual_bin,sensor_event_id);self.pending.pop(action_id)
        return {'status':'PHYSICAL_ROUTE_CONFIRMED','hardware_command_emitted':False}

    def status(self, action_id:str)->dict:
        with self._lock:return self._status(action_id)

    def _status(self, action_id:str)->dict:
        if action_id in self.acked:
            b,s=self.acked[action_id];return {'action_id':action_id,'state':'CONFIRMED','bin':b,'sensor_event_id':s}
        if action_id in self.faulted:
            exp,act,s=self.faulted[action_id];return {'action_id':action_id,'state':'FAULTED','expected_bin':exp,'actual_bin':act,'sensor_event_id':s}
        if action_id in self.pending:
            return {'action_id':action_id,'state':'PENDING','bin':self.pending[action_id].bin}
        return {'action_id':action_id,'state':'UNKNOWN'}
