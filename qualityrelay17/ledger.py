"""Local append-only ledger; NOT a distributed database, blockchain, or PKI."""
import sqlite3, json, threading
from dataclasses import asdict
from .contracts import Evidence

class EvidenceLedger:
    def __init__(self, path=':memory:'):
        # check_same_thread=False + a lock: FastAPI runs sync endpoints on a threadpool, so the
        # process-level ledger in api.py is appended from many threads. One connection, serialized.
        self.db=sqlite3.connect(path,check_same_thread=False)
        self._lock=threading.Lock()
        with self._lock:
            self.db.execute('CREATE TABLE IF NOT EXISTS evidence(event_id TEXT PRIMARY KEY, station_id TEXT NOT NULL, specimen_id TEXT NOT NULL, payload TEXT NOT NULL)')
            self.db.commit()

    def append(self,e:Evidence):
        """Append-only. event_id is the primary key, so a replayed event is refused here --
        this is the single place replay protection lives; callers must not swallow it."""
        try:
            with self._lock:
                self.db.execute('INSERT INTO evidence VALUES (?,?,?,?)',(e.event_id,e.station_id,e.specimen_id,json.dumps(asdict(e),sort_keys=True)))
                self.db.commit()
        except sqlite3.IntegrityError as ex:
            raise ValueError('duplicate event_id') from ex

    def get_event(self, event_id:str)->dict|None:
        """Exact-id lookup (no specimen enumeration), for SorterInterlock.acknowledge to confirm
        a sensor_event_id is a recorded ROUTE_ACK rather than a caller-supplied string."""
        with self._lock:
            row=self.db.execute('SELECT payload FROM evidence WHERE event_id=?',(event_id,)).fetchone()
        return json.loads(row[0]) if row else None

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
