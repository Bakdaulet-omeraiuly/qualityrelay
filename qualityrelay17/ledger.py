"""Local append-only ledger; NOT a distributed database, blockchain, or PKI.

Three append-only tables in one SQLite file:
  evidence        signed Evidence + the station the BACK-01 envelope proved (auth_station, NULL if
                  the record was not station-authenticated at ingest)
  verifications   human/instrument ground-truth checks (BACK-02); VERIFIED_PHYSICAL is derived
                  from these, never stored on an evidence row
  route_events    sorter action journal (BACK-03/04); UNIQUE(sensor_event_id) means one physical
                  sensor event can bind at most one action, across restarts
"""
import sqlite3, json, threading
from dataclasses import asdict
from .contracts import Evidence, signature_valid
from . import verification

class EvidenceLedger:
    def __init__(self, path=':memory:'):
        # check_same_thread=False + a lock: FastAPI runs sync endpoints on a threadpool, so the
        # process-level ledger in api.py is appended from many threads. One connection, serialized.
        self.db=sqlite3.connect(path,check_same_thread=False)
        self._lock=threading.Lock()
        with self._lock:
            self.db.execute('CREATE TABLE IF NOT EXISTS evidence(event_id TEXT PRIMARY KEY, station_id TEXT NOT NULL, specimen_id TEXT NOT NULL, payload TEXT NOT NULL)')
            if 'auth_station' not in {r[1] for r in self.db.execute('PRAGMA table_info(evidence)')}:
                self.db.execute('ALTER TABLE evidence ADD COLUMN auth_station TEXT')  # older files: rows stay unauthenticated
            self.db.execute('CREATE TABLE IF NOT EXISTS verifications(seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL, outcome TEXT NOT NULL, record TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS route_events(seq INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT NOT NULL, kind TEXT NOT NULL, sensor_event_id TEXT UNIQUE, record TEXT NOT NULL)')
            self.db.commit()

    def append(self,e:Evidence,*,authenticated_station:str|None=None):
        """Append-only. event_id is the primary key, so a replayed event is refused here --
        this is the single place replay protection lives; callers must not swallow it.
        authenticated_station is the station the request envelope proved; pass it only from a
        verified ingest path. VERIFIED_PHYSICAL is derived (see verification.py), never written."""
        if e.origin=='VERIFIED_PHYSICAL':
            raise PermissionError('VERIFIED_PHYSICAL is derived from recorded ground-truth checks; it cannot be written')
        if authenticated_station is not None and authenticated_station!=e.station_id:
            raise PermissionError('authenticated station does not match evidence station_id')
        try:
            with self._lock:
                self.db.execute('INSERT INTO evidence VALUES (?,?,?,?,?)',(e.event_id,e.station_id,e.specimen_id,json.dumps(asdict(e),sort_keys=True),authenticated_station))
                self.db.commit()
        except sqlite3.IntegrityError as ex:
            raise ValueError('duplicate event_id') from ex

    def get_event(self, event_id:str)->dict|None:
        """Exact-id lookup (no specimen enumeration), for SorterInterlock.acknowledge to confirm
        a sensor_event_id is a recorded ROUTE_ACK rather than a caller-supplied string.
        The returned dict carries `auth_station` (None if not station-authenticated)."""
        with self._lock:
            row=self.db.execute('SELECT payload,auth_station FROM evidence WHERE event_id=?',(event_id,)).fetchone()
        if not row:return None
        return {**json.loads(row[0]),'auth_station':row[1]}

    def recent_event_ids(self, limit:int=50)->list[str]:
        """Newest first, by append order (rowid). Ids only: callers derive tiers via evidence_status."""
        with self._lock:
            rows=self.db.execute('SELECT event_id FROM evidence ORDER BY rowid DESC LIMIT ?',(int(limit),)).fetchall()
        return [r[0] for r in rows]

    def count_events(self)->int:
        with self._lock:
            return self.db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0]

    def get_specimen(self, specimen_id, *, requester=None, allowed_stations=None):
        if requester is None or allowed_stations is None:
            raise PermissionError('explicit requester and station ACL required')
        if requester not in {'inspector','researcher','chief_readonly'}:
            raise PermissionError('unknown requester')
        with self._lock:
            rows=self.db.execute('SELECT payload FROM evidence WHERE specimen_id=? ORDER BY event_id',(specimen_id,)).fetchall()
        result=[]
        for (x,) in rows:
            d=json.loads(x)
            if d['station_id'] in allowed_stations:
                if requester == 'chief_readonly':
                    # prevent unrestricted original source payload access
                    d['payload']={k:v for k,v in d['payload'].items() if k in {'measurement_mm','uncertainty_mm','unit','threshold_mm','validated'}}
                result.append(d)
        return result

    # ------------------------------------------------------------------ BACK-02 ground truth
    def _verifications(self, event_id:str)->list[dict]:
        with self._lock:
            rows=self.db.execute('SELECT record FROM verifications WHERE event_id=? ORDER BY seq',(event_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def _row_context(self, event_id:str, station_keys:dict[str,str]):
        d=self.get_event(event_id)
        if d is None:return None
        auth=d.pop('auth_station')
        e=Evidence(**d)
        ok=signature_valid(e,station_keys)
        return {**d,'digest':e.digest()},auth,ok

    def evidence_status(self, event_id:str, *, station_keys:dict[str,str])->dict|None:
        """Derived tier of one record: effective_origin is VERIFIED_PHYSICAL only after an agreeing
        ground-truth check of a station-authenticated, validly signed, calibrated capture."""
        ctx=self._row_context(event_id,station_keys)
        if ctx is None:return None
        d,auth,ok=ctx
        return verification.effective_tier(d,auth_station=auth,signature_ok=ok,verifications=self._verifications(event_id))

    def record_verification(self, event_id:str, request:dict, *, verifier_id:str, station_keys:dict[str,str],
                            station_ids:set[str], now:float, max_age_s:float=verification.DEFAULT_MAX_AGE_S)->dict:
        """Evaluate and append one ground-truth check. Raises verification.VerificationRefused
        (nothing written) when the record is not a candidate or the request is incomplete."""
        ctx=self._row_context(event_id,station_keys)
        if ctx is None:raise verification.VerificationRefused(404,'unknown event_id')
        d,auth,ok=ctx
        rec=verification.evaluate(d,auth_station=auth,signature_ok=ok,request=request,verifier_id=verifier_id,
                                  station_ids=set(station_ids)|set(station_keys),now=now,max_age_s=max_age_s)
        with self._lock:
            self.db.execute('INSERT INTO verifications(event_id,outcome,record) VALUES (?,?,?)',(event_id,rec['outcome'],json.dumps(rec,sort_keys=True)))
            self.db.commit()
        return {'verification':rec,'status':self.evidence_status(event_id,station_keys=station_keys)}

    # ------------------------------------------------------------------ BACK-03/04 route journal
    def append_route_event(self, action_id:str, kind:str, record:dict, *, sensor_event_id:str|None=None):
        """Append-only. A sensor_event_id already bound to any action raises ValueError."""
        try:
            with self._lock:
                self.db.execute('INSERT INTO route_events(action_id,kind,sensor_event_id,record) VALUES (?,?,?,?)',
                                (action_id,kind,sensor_event_id,json.dumps(record,sort_keys=True)))
                self.db.commit()
        except sqlite3.IntegrityError as ex:
            raise ValueError('sensor event already bound to an action') from ex

    def sensor_event_bound(self, sensor_event_id:str)->bool:
        with self._lock:
            return self.db.execute('SELECT 1 FROM route_events WHERE sensor_event_id=?',(sensor_event_id,)).fetchone() is not None

    def route_events(self, action_id:str|None=None)->list[dict]:
        with self._lock:
            if action_id is None:
                rows=self.db.execute('SELECT action_id,kind,record FROM route_events ORDER BY seq').fetchall()
            else:
                rows=self.db.execute('SELECT action_id,kind,record FROM route_events WHERE action_id=? ORDER BY seq',(action_id,)).fetchall()
        return [{'action_id':a,'kind':k,**json.loads(r)} for a,k,r in rows]
