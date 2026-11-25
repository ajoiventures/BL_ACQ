"""Index supplied PDFs without claiming that extraction is semantic review.

The output contains private source text. Keep it outside the repository.
Every extracted character belongs to exactly one candidate sentence/fragment.
The splitter is deliberately lossless, not a linguistic sentence verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def candidate_units(text: str):
    """Yield contiguous spans, including headers, fragments and whitespace.

    Page boundaries, abbreviations, lists, tables and equations can split a
    grammatical sentence. The audit must resolve those cases; no span is dropped.
    """
    start = 0
    for match in re.finditer(r"(?<=[.!?])\s+|\n\s*\n", text):
        end = match.end()
        if end > start:
            yield start, end, text[start:end]
            start = end
    if start < len(text):
        yield start, len(text), text[start:]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def index_pdf(path: Path, destination: Path, library_file_id=None):
    import fitz  # Optional offline audit dependency; not an application import.

    source_hash = sha256(path.read_bytes())
    source_id = "BRS-" + source_hash[:16]
    out = destination / source_id
    out.mkdir(parents=True, exist_ok=True)
    pages = []
    unit_count = 0
    word_count = 0
    with fitz.open(path) as document, (out / "pages.jsonl").open("w", encoding="utf-8") as pf, (out / "units.jsonl").open("w", encoding="utf-8") as uf:
        for index, page in enumerate(document):
            text = page.get_text("text", sort=True)
            page_no = index + 1
            spans = list(candidate_units(text))
            assert "".join(span[2] for span in spans) == text
            assert all(a[1] == b[0] for a, b in zip(spans, spans[1:]))
            text_hash = sha256(text.encode("utf-8"))
            unit_ids = []
            for ordinal, (start, end, fragment) in enumerate(spans, 1):
                unit_id = f"{source_id}.p{page_no:04d}.u{ordinal:04d}"
                unit_ids.append(unit_id)
                uf.write(json.dumps({"unit_id": unit_id, "source_sha256": source_hash,
                    "pdf_page": page_no, "start": start, "end": end, "text": fragment,
                    "text_sha256": sha256(fragment.encode("utf-8")),
                    "unit_kind": "CANDIDATE_SENTENCE_OR_FRAGMENT",
                    "status": "EXTRACTED_NOT_SEMANTICALLY_REVIEWED"}, ensure_ascii=False) + "\n")
            row = {"source_id": source_id, "pdf_page": page_no, "characters": len(text),
                "words": len(text.split()), "text_sha256": text_hash,
                "first_unit_id": unit_ids[0] if unit_ids else None,
                "last_unit_id": unit_ids[-1] if unit_ids else None,
                "unit_count": len(unit_ids), "low_text_flag": len(text.strip()) < 80,
                "visual_review_status": "NOT_REVIEWED_BY_INDEXER",
                "semantic_review_status": "NOT_REVIEWED_BY_INDEXER"}
            pages.append(row)
            pf.write(json.dumps({**row, "text": text}, ensure_ascii=False) + "\n")
            unit_count += len(spans)
            word_count += len(text.split())
    manifest = {"schema_version": 1, "source_id": source_id, "filename": path.name,
        "library_file_id": library_file_id, "source_sha256": source_hash,
        "physical_pdf_pages": len(pages), "extracted_words": word_count,
        "candidate_units": unit_count, "extracted_character_coverage": 1.0,
        "semantic_coverage_verified": False, "visual_coverage_verified": False,
        "complete_book_verified": False, "pages": pages,
        "limitations": ["This is text extraction and indexing, not book reading.",
            "No OCR, equation reconstruction or figure interpretation is performed.",
            "Candidate units are not guaranteed to be grammatical sentences.",
            "A PDF can be incomplete even if all of its pages are indexed."]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in manifest.items() if key != "pages"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in inventory:
        result = index_pdf(Path(row["local_path"]), args.output, row.get("library_file_id"))
        rows.append(result)
        print(json.dumps(result), flush=True)
    (args.output / "corpus-manifest.json").write_text(json.dumps({"schema_version": 1,
        "sources": rows, "source_count": len(rows),
        "physical_pdf_pages": sum(r["physical_pdf_pages"] for r in rows),
        "candidate_units": sum(r["candidate_units"] for r in rows),
        "extracted_words": sum(r["extracted_words"] for r in rows),
        "semantic_coverage_verified": False, "visual_coverage_verified": False}, indent=2) + "\n")


if __name__ == "__main__":
    main()
