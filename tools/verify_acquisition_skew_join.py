"""Measure a bounded reported-unit join with a tiled public parcel fixture."""
import argparse
import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from time import perf_counter

import numpy as np

from backend.core.acquisition_batch import backend

BATCH = 100_000


def verify(inventory, count, checkpoint_db=None):
    with inventory.open(encoding="utf-8", newline="") as stream:
        rows = sorted((int(row["ALT_KEY"]), int(row["NO_RES_UNTS"])) for row in csv.DictReader(stream))
    if len({key for key, _ in rows}) != len(rows) or not rows:
        raise ValueError("Expected a distinct parcel lookup")
    keys, units = np.asarray(rows, dtype=np.int64).T.copy()
    cp = backend("cuda")
    device_keys, device_units = cp.asarray(keys), cp.asarray(units)
    reference_seconds = gpu_seconds = 0.0
    unmatched = 0
    counts = np.zeros(5, dtype=np.int64)
    digest = hashlib.sha256()
    peak_reserved = 0
    persistence_seconds = 0.0

    def join(xp, lookup, lookup_units, query):
        idx = xp.minimum(xp.searchsorted(lookup, query), len(lookup) - 1)
        return xp.where(lookup[idx] == query, lookup_units[idx], -1)

    for start in range(0, count, BATCH):
        ordinal = np.arange(start, min(start + BATCH, count), dtype=np.int64)
        query = keys[np.where(ordinal % 4 == 0, 0, ordinal % len(keys))].copy()
        query[ordinal % 17 == 0] = -1
        began = perf_counter()
        expected = join(np, keys, units, query)
        reference_seconds += perf_counter() - began
        began = perf_counter()
        actual = cp.asnumpy(join(cp, device_keys, device_units, cp.asarray(query)))
        gpu_seconds += perf_counter() - began
        if not np.array_equal(actual, expected):
            raise ValueError(f"CPU/CUDA join mismatch at row {start}")
        unmatched += int(np.count_nonzero(actual == -1))
        counts += np.bincount(actual[actual >= 0], minlength=5)
        payload = actual.astype("<i8", copy=False).tobytes()
        digest.update(payload)
        if checkpoint_db is not None:
            began = perf_counter()
            with checkpoint_db:
                checkpoint_db.execute("INSERT INTO checkpoints VALUES (?,?,?)",
                                      (start, start + len(actual), payload))
            persistence_seconds += perf_counter() - began
        peak_reserved = max(peak_reserved, cp.get_default_memory_pool().total_bytes())
    if unmatched + int(counts.sum()) != count:
        raise ValueError("Join population mismatch")
    return dict(source_sha256=hashlib.sha256(inventory.read_bytes()).hexdigest(), source_parcels=len(rows),
                workload_rows=count, synthetic_tiled=True, batch_limit=BATCH,
                skew_rule="Every fourth query uses one fixed key; every seventeenth is unmatched and overrides skew.",
                unmatched=unmatched, matched_by_reported_units={n:int(counts[n]) for n in (2,3,4)},
                exact_cpu_cuda_parity=True, result_sha256=digest.hexdigest(),
                cpu_join_seconds=reference_seconds,cuda_join_copy_seconds=gpu_seconds,
                max_observed_reserved_pool_bytes=peak_reserved,
                checkpoint_write_seconds=persistence_seconds if checkpoint_db is not None else None,
                timing_scope="Bounded numeric join including CUDA copy and readback; excludes persistence and geometry.")


def verify_saved(database, expected_rows, expected_digest):
    digest = hashlib.sha256()
    cursor = batches = 0
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as saved:
        for start, end, payload in saved.execute("SELECT start, end, payload FROM checkpoints ORDER BY start"):
            if start != cursor or not 0 < end - start <= BATCH or len(payload) != (end - start) * 8:
                raise ValueError("Checkpoint range or size mismatch")
            digest.update(payload)
            cursor = end
            batches += 1
    if cursor != expected_rows or digest.hexdigest() != expected_digest:
        raise ValueError("Saved results differ from the verified CUDA output")
    return batches


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--count",type=int,default=2_000_000,choices=(2_000_000,5_000_000,10_000_000))
    parser.add_argument("--checkpoint-db", type=Path)
    args=parser.parse_args()
    if args.checkpoint_db is None:
        result=verify(args.inventory,args.count)
    else:
        with args.checkpoint_db.open("xb"):
            pass
        with closing(sqlite3.connect(args.checkpoint_db)) as db:
            db.execute("CREATE TABLE checkpoints(start INTEGER PRIMARY KEY, end INTEGER NOT NULL, payload BLOB NOT NULL)")
            result=verify(args.inventory,args.count,db)
        began=perf_counter()
        result["verified_persisted_batches"]=verify_saved(args.checkpoint_db,args.count,result["result_sha256"])
        result["checkpoint_readback_seconds"]=perf_counter()-began
        result["timing_scope"] += " SQLite checkpoint write and readback are timed separately."
    with args.output.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2)
        f.write("\n")
    print(result)
