"""Local append-only ledger; NOT a distributed database, blockchain, or PKI."""
import sqlite3, json
from dataclasses import asdict
from .contracts import Evidence

class EvidenceLedger:
    def __init__(self, path=':memory:'):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS evidence(event_id TEXT PRIMARY KEY, station_id TEXT NOT NULL, specimen_id TEXT NOT NULL, payload TEXT NOT NULL)')
        self.db.commit()

    def append(self,e:Evidence):
        try:
            self.db.execute('INSERT INTO evidence VALUES (?,?,?,?)',(e.event_id,e.station_id,e.specimen_id,json.dumps(asdict(e),sort_keys=True)))
            self.db.commit()
        except sqlite3.IntegrityError as ex:
            raise ValueError('duplicate event_id') from ex

    def get_specimen(self, specimen_id, *, requester=None, allowed_stations=None):
        if requester is None or allowed_stations is None:
            raise PermissionError('explicit requester and station ACL required')
        if requester not in {'inspector','researcher','chief_readonly'}:
            raise PermissionError('unknown requester')
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
