"""Inspect the Orange FDOR geometry release without writing raw attribute rows."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def inspect(path):
    if path.stat().st_size > 400_000_000:
        raise ValueError("unexpected Orange parcel archive size")
    with zipfile.ZipFile(path) as archive:
        items = archive.infolist()
        if any(i.file_size > 1_000_000_000 for i in items) or sum(i.file_size for i in items)> 2_000_000_000:
            raise ValueError("unexpected geometry expansion")
        ids = {suffix: [i for i in items if i.filename.lower().endswith("." + suffix)]
               for suffix in ("dbf", "shp", "shx", "prj", "cpg")}
        if any(len(ids[suffix]) != 1 for suffix in ("dbf", "shp", "shx", "prj")):
            raise ValueError("expected one layer with matching shape, index and DBF")
        layer = {Path(ids[suffix][0].filename).with_suffix("").name.lower()
                 for suffix in ("dbf", "shp", "shx", "prj")}
        if len(layer) != 1:
            raise ValueError("geometry archive has inconsistent layer names")
        failed = archive.testzip()
        if failed:
            raise ValueError(f"archive CRC failed for {failed}")
        with archive.open(ids["dbf"][0]) as dbf:
            header = dbf.read(32)
            population, header_size, length = struct.unpack_from("<IHH", header, 4)
            if not 32 < header_size <= 20_000 or not 0 < length <= 10_000:
                raise ValueError("invalid DBF headers")
            fields_raw = dbf.read(header_size - 32)
        fields = []
        for offset in range(0, len(fields_raw), 32):
            if fields_raw[offset] == 13:
                break
            descriptor = fields_raw[offset:offset+32]
            if len(descriptor) != 32:
                raise ValueError("partial DBF field descriptor")
            fields.append({
                "name": descriptor[:11].split(b"\0", 1)[0].decode("ascii"),
                "type": chr(descriptor[11]), "width": descriptor[16],
            })
        with archive.open(ids["shp"][0]) as shp:
            shape_header = shp.read(100)
        index_count, remainder = divmod(ids["shx"][0].file_size - 100, 8)
        if index_count != population or remainder or sum(f["width"] for f in fields) + 1 != length:
            raise ValueError("inconsistent shape index and DBF record layout")
        codepage = archive.read(ids["cpg"][0]).decode("ascii").strip() if len(ids["cpg"]) == 1 else None
        projection = archive.read(ids["prj"][0]).decode("ascii").strip()
        result = {
            "members": [{"name": i.filename, "bytes": i.file_size, "crc32": f"{i.CRC:08x}"}
                        for i in items],
            "archive_crc_verified": True, "dbf_declared_records": population,
            "shape_index_records": index_count, "dbf_record_bytes": length,
            "dbf_language_driver_byte": header[29], "codepage_file_value": codepage,
            "geometry_type_code": struct.unpack_from("<I",shape_header,32)[0],
            "projection_wkt": projection, "dbf_fields": fields,
        }
    with path.open("rb") as stream:
        result["archive_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    result["archive_bytes"] = path.stat().st_size
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = inspect(args.archive)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(report["dbf_declared_records"], report["archive_sha256"])


if __name__ == "__main__":
    main()
