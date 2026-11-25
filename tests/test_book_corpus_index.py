from tools.audit_book_corpus import candidate_units


def test_every_extracted_character_has_one_contiguous_span():
    text = "Header\n\nDr. LaGro’s example.\nA table: 1.2  4.5\n\nα = β + 1\nUnfinished page"
    units = list(candidate_units(text))
    assert ''.join(item[2] for item in units) == text
    assert units[0][0] == 0 and units[-1][1] == len(text)
    assert all(left[1] == right[0] for left, right in zip(units, units[1:]))
    assert all(text[start:end] == fragment for start, end, fragment in units)


def test_blank_and_whitespace_pages_are_not_silently_lost():
    assert list(candidate_units('')) == []
    for text in ['  ', '\n\n', 'Last sentence.   ', 'No terminator']:
        assert ''.join(row[2] for row in candidate_units(text)) == text
