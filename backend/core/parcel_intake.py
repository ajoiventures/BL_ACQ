"""Import the November 18 Orange County screening snapshot. Run from repository root."""
import csv
import sqlite3
from contextlib import closing
from pathlib import Path

def ingest(database, snapshot):
    with closing(sqlite3.connect(database)) as db, db, Path(snapshot).open(encoding='utf-8-sig', newline='') as source:
        db.execute('BEGIN IMMEDIATE')
        db.execute("""CREATE TABLE IF NOT EXISTS acquisition_parcel_observations
                    (county TEXT, snapshot TEXT, object_id INTEGER, parcel TEXT NOT NULL,
                    situs TEXT, city TEXT, zip TEXT, dor_code TEXT,
                    PRIMARY KEY(county,snapshot,object_id))""")
        scope = ('12095', '2026-11-18')
        existing = db.execute('SELECT COUNT(*) FROM acquisition_parcel_observations '
                              'WHERE county=? AND snapshot=?', scope).fetchone()[0]
        seen = set()
        for row in csv.DictReader(source):
            if len(row['PARCEL'])!=15 or not row['PARCEL'].isascii() or not row['PARCEL'].isdigit():
                raise ValueError('Invalid county parcel key')
            object_id = int(row['OBJECTID'])
            if object_id < 1 or object_id in seen:
                raise ValueError('Invalid or duplicate county feature ID')
            seen.add(object_id)
            observation = (*scope,object_id,row['PARCEL'],row['SITUS'],row['SITUS_CITY'],row['SITUS_ZIP'],row['DOR_CODE'])
            inserted = db.execute('INSERT INTO acquisition_parcel_observations VALUES(?,?,?,?,?,?,?,?) '
                                  'ON CONFLICT(county,snapshot,object_id) DO NOTHING', observation)
            if inserted.rowcount and existing:
                raise ValueError('County feature was not part of the retained snapshot')
            if not inserted.rowcount:
                stored = db.execute('SELECT * FROM acquisition_parcel_observations '
                                    'WHERE county=? AND snapshot=? AND object_id=?', observation[:3]).fetchone()
                if stored != observation:
                    raise ValueError('County feature conflicts with the retained snapshot')
        if not seen or (existing and len(seen) != existing):
            raise ValueError('County source is empty or omits retained snapshot features')
        return db.execute('SELECT COUNT(*),COUNT(DISTINCT parcel) FROM acquisition_parcel_observations WHERE county=? AND snapshot=?',scope).fetchone()

if __name__=='__main__':
    import os
    print(ingest(os.getenv('BR_DB','data/command.db'),'docs/orange-parcels.csv'))
