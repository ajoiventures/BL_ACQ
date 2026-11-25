"""Profile a complete Sunbiz corporate quarterly Deflate64 archive without export."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import zipfile
import zlib

import numpy as np

from tools.verify_orange_sales_and_sunbiz import digest

EXPECTED = [f"cordata{index}.txt" for index in range(10)]
WIDTH = 1442  # 1440 published payload bytes plus verified CRLF


def profile_member(path, info, consume=None):
    from inflate64 import Inflater

    decoder = Inflater()
    crc = size = rows = non_ascii = mispartitioned = lowercase_keys = 0
    status = Counter()
    tail = b""
    with path.open("rb") as stream:
        stream.seek(info.header_offset)
        header = stream.read(30)
        if header[:4] != b"PK\x03\x04":
            raise ValueError(f"Invalid local ZIP header: {info.filename}")
        name_size, extra_size = struct.unpack_from("<HH", header, 26)
        if stream.read(name_size) != info.filename.encode("ascii"):
            raise ValueError(f"ZIP member name mismatch: {info.filename}")
        stream.seek(extra_size, 1)
        left = info.compress_size
        while left:
            chunk = stream.read(min(left, 262144))
            if not chunk:
                raise ValueError(f"Truncated compressed member: {info.filename}")
            left -= len(chunk)
            block = decoder.inflate(chunk)
            size += len(block)
            if size > info.file_size or len(block) > 64_000_000:
                raise ValueError(f"Member exceeds expected size: {info.filename}")
            crc = zlib.crc32(block, crc)
            data = tail + block
            complete = len(data) // WIDTH * WIDTH
            tail = data[complete:]
            values = np.frombuffer(data, dtype=np.uint8, count=complete).reshape(-1, WIDTH)
            if not len(values):
                continue
            if np.any(values[:, -2] != 13) or np.any(values[:, -1] != 10):
                raise ValueError(f"Invalid fixed-width framing: {info.filename}")
            if consume is not None:
                consume(rows, values)
            rows += len(values)
            non_ascii += int(np.count_nonzero(np.any(values[:, :-2] >= 128, axis=1)))
            chars = values[:, 204]
            active = int(np.count_nonzero(chars == ord("A")))
            inactive = int(np.count_nonzero(chars == ord("I")))
            status.update(A=active, I=inactive, other=len(values) - active - inactive)
            ids = values[:, :12]
            lowercase_keys += int(np.count_nonzero(np.any((ids >= ord('a')) & (ids <= ord('z')), axis=1)))
            positions = np.where(ids != 32, np.arange(12), 0).max(axis=1)
            last = ids[np.arange(len(ids)), positions]
            mispartitioned += int(np.count_nonzero(last != ord(info.filename[7])))
    if tail or not decoder.eof or crc != info.CRC or size != info.file_size:
        raise ValueError(f"Member checksum or size mismatch: {info.filename}")
    return {
        "member": info.filename, "crc32": f"{crc:08x}", "bytes": size,
        "member_modified_local_zip": list(info.date_time), "records": rows,
        "status": dict(status), "non_ascii_records": non_ascii,
        "lowercase_document_key_rows": lowercase_keys,
        "document_ids_outside_declared_suffix_partition": mispartitioned,
    }


def archive_members(path):
    if path.stat().st_size > 2_000_000_000:
        raise ValueError("Quarterly archive exceeds size limit")
    with zipfile.ZipFile(path) as archive:
        items = sorted(archive.infolist(), key=lambda item: item.filename)
    if [item.filename for item in items] != EXPECTED or any(
        item.compress_type != 9 or item.file_size > 2_000_000_000 or item.file_size % WIDTH
        for item in items
    ):
        raise ValueError("Unexpected Sunbiz archive layout")
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    items = archive_members(args.archive)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda item: profile_member(args.archive, item), items))
    status = Counter()
    for item in results:
        status.update(item["status"])
    report = {
        "portal": "https://sftp.floridados.gov/", "artifact": "doc/Quarterly/Cor/cordata.zip",
        "archive_bytes": args.archive.stat().st_size, "archive_sha256": digest(args.archive),
        "status": dict(status), "records": sum(item["records"] for item in results),
        "all_member_crcs_verified": True, "members": results,
        "contains_active_and_inactive_records": bool(status["A"] and status["I"]),
        "commercial_release_authorized": False,
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(report["records"], report["status"])


if __name__ == "__main__":
    main()
