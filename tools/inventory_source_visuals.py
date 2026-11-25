"""Inventory visual review signals without treating them as verified document content."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def inventory(pdf, dispositions):
    import pymupdf

    labels = Counter()
    with dispositions.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["provisional_disposition"] == "TABLE_OR_NOTE_REQUIRES_CELL_VALIDATION":
                labels[row["pdf_page"]] += 1
    rows = []
    with pymupdf.open(pdf) as doc:
        for number, page in enumerate(doc, 1):
            images = len(page.get_image_info())
            paths = len(page.get_drawings())
            rows.append(dict(page=number, displayed_image_occurrences=images,
                             vector_paths=paths, table_note_candidates=labels[number],
                             visual_review_status="PENDING"))
    if set(labels) - {row["page"] for row in rows}:
        raise ValueError("Disposition page outside source PDF")
    with pdf.open("rb") as f:
        source_sha = hashlib.file_digest(f,"sha256").hexdigest()
    with dispositions.open("rb") as f:
        disposition_sha = hashlib.file_digest(f,"sha256").hexdigest()
    return dict(source_sha256=source_sha, dispositions_sha256=disposition_sha,
                physical_pages=len(rows), pages_with_vectors_and_no_images=sum(
                    row["vector_paths"] > 0 and row["displayed_image_occurrences"] == 0 for row in rows),
                table_note_candidates=sum(labels.values()), pages=rows, visually_verified_items=0)


if __name__ == "__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ("pdf","dispositions","output"):
        cli.add_argument(name,type=Path)
    args=cli.parse_args()
    result=inventory(args.pdf,args.dispositions)
    with args.output.open("x",encoding="utf-8") as out:
        json.dump(result,out,indent=2)
        out.write("\n")
    print(result["physical_pages"],result["pages_with_vectors_and_no_images"],result["table_note_candidates"])
