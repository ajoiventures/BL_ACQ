"""Read back all persisted inputs and results for a completed acquisition run."""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from backend.core.acquisition_runs import sha


def verify(database, run_id):
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        run = db.execute("SELECT snapshot_id,state,total,cursor FROM acq_runs WHERE id=?", (run_id,)).fetchone()
        if not run or run[1] != "COMPLETED" or run[2] != run[3]:
            raise ValueError("Expected a completed run")
        snapshot, _, total, _ = run
        rows = db.execute("""
            SELECT p.ordinal,p.parcel_key,p.record,r.result
            FROM acq_parcels p LEFT JOIN acq_results r
                ON r.run_id=? AND r.parcel_key=p.parcel_key
            WHERE p.snapshot_id=? ORDER BY p.ordinal
        """, (run_id, snapshot)).fetchall()
        count = db.execute("SELECT count(*) FROM acq_results WHERE run_id=?", (run_id,)).fetchone()[0]
        if count != total or len(rows) != total or len({row[1] for row in rows}) != total:
            raise ValueError("Parcel and result cardinality mismatch")
        cursor, checkpoints = 0, []
        screens = Counter()
        for start, end, encoded in db.execute(
            "SELECT start,end,receipt FROM acq_batches WHERE run_id=? ORDER BY start", (run_id,)
        ):
            if start != cursor or not start < end <= total:
                raise ValueError("Checkpoint overlap or gap")
            batch = rows[start:end]
            if any(ordinal != start + i or result is None
                   for i, (ordinal, _, _, result) in enumerate(batch)):
                raise ValueError("Missing ordinal or result")
            records = [json.loads(row[2]) for row in batch]
            results = [json.loads(row[3]) for row in batch]
            if any(row[1] != result["parcel_key"] for row, result in zip(batch, results)):
                raise ValueError("Result key mismatch")
            receipt = json.loads(encoded)
            expected = dict(start=start,end=end,snapshot_id=snapshot,input_sha256=sha(records),results_sha256=sha(results))
            if any(receipt.get(key) != value for key, value in expected.items()):
                raise ValueError("Checkpoint receipt does not match persisted rows")
            screens.update(result["screen"] for result in results)
            checkpoints.append(expected)
            cursor = end
        if cursor != total:
            raise ValueError("Checkpoints do not cover the completed run")
        return dict(run_id=run_id, snapshot_id=snapshot, verified_unique_results=count,
                    checkpoints=checkpoints, screens=dict(screens))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database",type=Path)
    parser.add_argument("run_id")
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    result = verify(args.database,args.run_id)
    with args.output.open("x",encoding="utf-8") as file:
        json.dump(result,file,indent=2)
        file.write("\n")
    print(result["verified_unique_results"],len(result["checkpoints"]),result["screens"])
