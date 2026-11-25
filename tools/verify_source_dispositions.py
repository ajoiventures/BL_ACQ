"""Reconcile every indexed page span against its provisional disposition."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def read_lines(path):
    with path.open(encoding="utf-8") as stream:
        yield from map(json.loads, stream)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify(index, dispositions):
    manifest = json.loads((index / "manifest.json").read_bytes())
    pairs = iter(zip(read_lines(index / "units.jsonl"), read_lines(dispositions), strict=True))
    pages = characters = words = units = 0
    counts = Counter()
    for page in read_lines(index / "pages.jsonl"):
        pages += 1
        text = page["text"]
        if (page["pdf_page"] != pages or page["source_id"] != manifest["source_id"]
                or digest(text) != page["text_sha256"]):
            raise ValueError(f"Page identity or hash mismatch on {pages}")
        cursor = 0
        for ordinal in range(1, page["unit_count"] + 1):
            unit, label = next(pairs, (None, None))
            expected_id = f"{manifest['source_id']}.p{pages:04d}.u{ordinal:04d}"
            if unit is None or any(row["unit_id"] != expected_id or row["pdf_page"] != pages
                                   for row in (unit, label)):
                raise ValueError(f"Unmatched disposition for {expected_id}")
            end = unit["end"]
            if (unit["source_sha256"] != manifest["source_sha256"] or unit["start"] != cursor
                    or not cursor < end <= len(text) or unit["text"] != text[cursor:end]
                    or digest(unit["text"]) != unit["text_sha256"]
                    or label["text_sha256"] != unit["text_sha256"]):
                raise ValueError(f"Span or hash mismatch for {expected_id}")
            if label["status"] != "AUTOMATED_TRIAGE_NOT_INDIVIDUALLY_REVIEWED" or label["training_label_eligible"]:
                raise ValueError(f"Unexpected promotion for {expected_id}")
            cursor = end
            units += 1
            counts[label["provisional_disposition"]] += 1
        if cursor != len(text) or cursor != page["characters"] or len(text.split()) != page["words"]:
            raise ValueError(f"Incomplete spans on page {pages}")
        characters += cursor
        words += page["words"]
    if next(pairs, None) is not None or (pages, units, words) != tuple(
        manifest[key] for key in ("physical_pdf_pages", "candidate_units", "extracted_words")
    ):
        raise ValueError("Disposition totals differ from the source manifest")
    return dict(source_sha256=manifest["source_sha256"], pages=pages, units=units,
                characters=characters, words=words, provisional_counts=dict(counts),
                individually_verified_units=0, units_pending_individual_review=units)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("dispositions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = verify(args.index, args.dispositions)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(result)
