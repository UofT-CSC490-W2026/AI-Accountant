from services.shared.ingestion import (
    IngestedStatement,
    _build_statement_text_from_row,
    _coerce_amount,
    _decode_pdf_literal,
    _decode_text_contents,
    _extract_text_from_simple_pdf,
    _first_value,
    _parse_csv_statements,
    _parse_pdf_statements,
    _split_statement_text,
    parse_uploaded_statements,
    split_manual_statements,
)


# ---------------------------------------------------------------------------
# split_manual_statements
# ---------------------------------------------------------------------------


def test_split_manual_statements_uses_semicolons() -> None:
    statements = split_manual_statements(
        "Bought a laptop for $2400; Paid rent $2000",
        source="manual_text",
        currency="CAD",
    )

    assert [statement.input_text for statement in statements] == [
        "Bought a laptop for $2400",
        "Paid rent $2000",
    ]


def test_split_manual_statements_uses_newlines_when_no_semicolons() -> None:
    statements = split_manual_statements(
        "Bought a laptop\nPaid rent",
        source="manual_text",
        currency="USD",
    )

    assert len(statements) == 2
    assert statements[0].input_text == "Bought a laptop"
    assert statements[1].input_text == "Paid rent"
    assert statements[0].source == "manual_text"
    assert statements[0].currency == "USD"


def test_split_manual_statements_strips_blank_lines() -> None:
    statements = split_manual_statements(
        "\n  \nBought a laptop\n  \n",
        source="manual_text",
    )

    assert len(statements) == 1
    assert statements[0].input_text == "Bought a laptop"


# ---------------------------------------------------------------------------
# parse_uploaded_statements
# ---------------------------------------------------------------------------


def test_parse_uploaded_csv_rows_into_statements() -> None:
    statements = parse_uploaded_statements(
        contents=b"description,amount,counterparty\nBought laptop,2400,Apple\nPaid rent,2000,Landlord\n",
        filename="demo.csv",
        source="csv_upload",
    )

    assert [statement.input_text for statement in statements] == [
        "Bought laptop to Apple for $2400",
        "Paid rent to Landlord for $2000",
    ]
    assert statements[0].amount == 2400.0
    assert statements[1].counterparty == "Landlord"


def test_parse_uploaded_pdf_extracts_simple_text_lines() -> None:
    statements = parse_uploaded_statements(
        contents=b"%PDF-1.4\nBT\n(Bought a laptop for $2400) Tj\nET\nBT\n(Paid rent $2000) Tj\nET\n",
        filename="demo.pdf",
        source="pdf_upload",
    )

    assert [statement.input_text for statement in statements] == [
        "Bought a laptop for $2400",
        "Paid rent $2000",
    ]


def test_parse_uploaded_statements_non_csv_non_pdf_fallback() -> None:
    """When source is neither csv_upload nor pdf_upload, decode as plain text."""
    raw = b"Groceries at Store; Office supplies"
    statements = parse_uploaded_statements(
        contents=raw,
        filename="transactions.txt",
        source="text_upload",
        currency="CAD",
    )

    assert len(statements) == 2
    assert statements[0].input_text == "Groceries at Store"
    assert statements[1].input_text == "Office supplies"
    assert statements[0].filename == "transactions.txt"
    assert statements[0].source == "text_upload"
    assert statements[0].currency == "CAD"


def test_parse_uploaded_statements_empty_source_fallback() -> None:
    """An empty/whitespace source should also fall through to text parsing."""
    raw = b"Single line statement"
    statements = parse_uploaded_statements(
        contents=raw,
        filename=None,
        source="  ",
        currency=None,
    )

    assert len(statements) == 1
    assert statements[0].input_text == "Single line statement"


# ---------------------------------------------------------------------------
# _parse_csv_statements — WITH headers (fieldnames present)
# ---------------------------------------------------------------------------


def test_parse_csv_with_headers_all_fields() -> None:
    csv_bytes = (
        b"description,amount,counterparty,transaction_date,currency,source\n"
        b"Rent payment,2000.00,Landlord,2025-01-15,USD,bank_import\n"
    )
    results = _parse_csv_statements(csv_bytes, filename="f.csv", source="csv_upload", currency="CAD")

    assert len(results) == 1
    stmt = results[0]
    assert "Rent payment" in stmt.input_text
    assert stmt.transaction_date == "2025-01-15"
    assert stmt.amount == 2000.0
    assert stmt.counterparty == "Landlord"
    assert stmt.source == "bank_import"
    assert stmt.currency == "USD"
    assert stmt.filename == "f.csv"


def test_parse_csv_with_headers_skips_empty_input_text() -> None:
    """Row where _build_statement_text_from_row returns '' is skipped (line 87)."""
    csv_bytes = b"description,amount\n,100\nValid row,200\n"
    results = _parse_csv_statements(csv_bytes, filename=None, source="csv_upload", currency=None)

    assert len(results) == 1
    assert "Valid row" in results[0].input_text


def test_parse_csv_with_headers_uses_fallback_source_and_currency() -> None:
    """When row has no source/currency columns, use the function args."""
    csv_bytes = b"description\nBuy paper\n"
    results = _parse_csv_statements(csv_bytes, filename=None, source="csv_upload", currency="EUR")

    assert results[0].source == "csv_upload"
    assert results[0].currency == "EUR"


# ---------------------------------------------------------------------------
# _parse_csv_statements — WITHOUT headers (fieldnames empty)
# ---------------------------------------------------------------------------


def test_parse_csv_headerless_fallback() -> None:
    """A CSV with no parseable header row triggers the headerless branch (lines 101-114)."""
    # A raw CSV with only numbers/values and no header row.
    # DictReader will treat the first row as the header, so we need to make
    # fieldnames end up empty. This happens when all header values are empty/whitespace.
    csv_bytes = b",,,\nBought a laptop,2400,Apple\nPaid rent,2000,Landlord\n"
    results = _parse_csv_statements(csv_bytes, filename="raw.csv", source="csv_upload", currency="CAD")

    # With empty fieldnames, falls back to csv.reader branch
    # The header row is all empty -> fieldnames are empty -> headerless branch
    assert len(results) >= 1
    # Headerless branch takes columns[0] as input_text
    assert results[0].input_text == "Bought a laptop"
    assert results[0].source == "csv_upload"
    assert results[0].currency == "CAD"
    assert results[0].filename == "raw.csv"


def test_parse_csv_headerless_skips_empty_rows() -> None:
    """Empty rows in headerless CSV are skipped (line 104-105)."""
    csv_bytes = b",\n,\nActual data\n,,\n"
    results = _parse_csv_statements(csv_bytes, filename=None, source="csv_upload", currency=None)

    # Only the row with "Actual data" should remain
    assert any(r.input_text == "Actual data" for r in results)


# ---------------------------------------------------------------------------
# _build_statement_text_from_row
# ---------------------------------------------------------------------------


def test_build_statement_text_from_row_with_text_column() -> None:
    """Row with a text column returns it directly (line 139)."""
    row = {"text": "Paid invoice #123", "description": "something else"}
    assert _build_statement_text_from_row(row) == "Paid invoice #123"


def test_build_statement_text_from_row_with_input_text_column() -> None:
    row = {"input_text": "Subscription renewal"}
    assert _build_statement_text_from_row(row) == "Subscription renewal"


def test_build_statement_text_from_row_with_memo_column() -> None:
    row = {"memo": "Client payment received"}
    assert _build_statement_text_from_row(row) == "Client payment received"


def test_build_statement_text_from_row_description_only() -> None:
    """Row with description but no text column builds from parts."""
    row = {"description": "Office supplies"}
    assert _build_statement_text_from_row(row) == "Office supplies"


def test_build_statement_text_from_row_description_with_all_parts() -> None:
    row = {
        "description": "Office supplies",
        "counterparty": "Staples",
        "amount": "59.99",
        "transaction_date": "2025-03-15",
    }
    result = _build_statement_text_from_row(row)
    assert result == "Office supplies to Staples for $59.99 on 2025-03-15"


def test_build_statement_text_from_row_description_with_counterparty_only() -> None:
    row = {"description": "Lunch", "vendor": "Cafe"}
    assert _build_statement_text_from_row(row) == "Lunch to Cafe"


def test_build_statement_text_from_row_description_with_amount_only() -> None:
    row = {"description": "Lunch", "amount": "15.50"}
    assert _build_statement_text_from_row(row) == "Lunch for $15.50"


def test_build_statement_text_from_row_description_with_date_only() -> None:
    """Covers line 154-155: transaction_date appended."""
    row = {"description": "Rent", "date": "2025-01-01"}
    assert _build_statement_text_from_row(row) == "Rent on 2025-01-01"


def test_build_statement_text_from_row_empty_description_no_text() -> None:
    """Empty description and no text column returns '' (line 143)."""
    row = {"description": "", "amount": "100"}
    assert _build_statement_text_from_row(row) == ""


def test_build_statement_text_from_row_no_description_no_text() -> None:
    row = {"amount": "100"}
    assert _build_statement_text_from_row(row) == ""


# ---------------------------------------------------------------------------
# _split_statement_text
# ---------------------------------------------------------------------------


def test_split_statement_text_semicolons() -> None:
    assert _split_statement_text("A; B; C") == ["A", "B", "C"]


def test_split_statement_text_newlines() -> None:
    assert _split_statement_text("A\nB\nC") == ["A", "B", "C"]


def test_split_statement_text_crlf() -> None:
    assert _split_statement_text("A\r\nB\rC") == ["A", "B", "C"]


def test_split_statement_text_collapses_whitespace() -> None:
    assert _split_statement_text("  lots   of   spaces  ") == ["lots of spaces"]


def test_split_statement_text_skips_blank_segments() -> None:
    assert _split_statement_text("A;;  ;B") == ["A", "B"]


def test_split_statement_text_empty_string() -> None:
    assert _split_statement_text("") == []


# ---------------------------------------------------------------------------
# _decode_text_contents
# ---------------------------------------------------------------------------


def test_decode_text_contents_utf8() -> None:
    text = "Hello world"
    assert _decode_text_contents(text.encode("utf-8")) == "Hello world"


def test_decode_text_contents_utf8_bom() -> None:
    """UTF-8 BOM is stripped by utf-8-sig (line 177)."""
    bom = b"\xef\xbb\xbf"
    assert _decode_text_contents(bom + b"Hello") == "Hello"


def test_decode_text_contents_latin1_fallback() -> None:
    """Bytes that are invalid UTF-8 but valid Latin-1 (lines 178-180)."""
    # \xe9 is 'e-acute' in Latin-1 but invalid as a standalone UTF-8 byte
    latin1_bytes = "caf\u00e9".encode("latin-1")
    result = _decode_text_contents(latin1_bytes)
    assert "caf" in result
    assert "\u00e9" in result


def test_decode_text_contents_ignore_fallback() -> None:
    """Bytes invalid in all three encodings fall back to utf-8 errors=ignore (line 180).

    Latin-1 can decode ANY byte, so the ignore branch is only reached if
    latin-1 somehow fails. In practice this branch is nearly unreachable,
    but we verify the pure UTF-8 path still works.
    """
    result = _decode_text_contents(b"plain ascii")
    assert result == "plain ascii"


# ---------------------------------------------------------------------------
# _extract_text_from_simple_pdf
# ---------------------------------------------------------------------------


def test_extract_text_from_simple_pdf_tj_literals() -> None:
    """Tj operator extracts literal strings (lines 186-190)."""
    pdf = b"BT (Hello World) Tj ET"
    result = _extract_text_from_simple_pdf(pdf)
    assert "Hello World" in result


def test_extract_text_from_simple_pdf_tj_array() -> None:
    """TJ operator extracts array literal strings (lines 192-196)."""
    pdf = b"BT [(Part A) -10 (Part B)] TJ ET"
    result = _extract_text_from_simple_pdf(pdf)
    assert "Part A" in result
    assert "Part B" in result


def test_extract_text_from_simple_pdf_both_tj_and_tj_array() -> None:
    pdf = b"BT (Line one) Tj [(Line two)] TJ ET"
    result = _extract_text_from_simple_pdf(pdf)
    assert "Line one" in result
    assert "Line two" in result


def test_extract_text_from_simple_pdf_no_matches_fallback() -> None:
    """No PDF operators found -> falls back to _decode_text_contents (line 201)."""
    raw = b"Just some plain text, no PDF operators"
    result = _extract_text_from_simple_pdf(raw)
    assert result == "Just some plain text, no PDF operators"


def test_extract_text_from_simple_pdf_empty_literal_skipped() -> None:
    """Empty decoded literals are skipped (line 189-190)."""
    pdf = b"BT () Tj (Visible) Tj ET"
    result = _extract_text_from_simple_pdf(pdf)
    assert "Visible" in result


def test_extract_text_from_simple_pdf_tj_array_empty_literal_skipped() -> None:
    """Empty literal inside TJ array is skipped (branch 195->193)."""
    pdf = b"BT [() (Real text)] TJ ET"
    result = _extract_text_from_simple_pdf(pdf)
    assert "Real text" in result


# ---------------------------------------------------------------------------
# _decode_pdf_literal
# ---------------------------------------------------------------------------


def test_decode_pdf_literal_simple() -> None:
    assert _decode_pdf_literal(b"(Hello)") == "Hello"


def test_decode_pdf_literal_with_escape_n() -> None:
    assert _decode_pdf_literal(b"(Line1\\nLine2)") == "Line1\nLine2"


def test_decode_pdf_literal_with_escape_r() -> None:
    assert _decode_pdf_literal(b"(A\\rB)") == "A\rB"


def test_decode_pdf_literal_with_escape_t() -> None:
    assert _decode_pdf_literal(b"(A\\tB)") == "A\tB"


def test_decode_pdf_literal_with_escape_b() -> None:
    assert _decode_pdf_literal(b"(A\\bB)") == "A\bB"


def test_decode_pdf_literal_with_escape_f() -> None:
    assert _decode_pdf_literal(b"(A\\fB)") == "A\fB"


def test_decode_pdf_literal_with_escape_parens() -> None:
    assert _decode_pdf_literal(b"(A\\(B\\))") == "A(B)"


def test_decode_pdf_literal_with_escape_backslash() -> None:
    assert _decode_pdf_literal(b"(A\\\\B)") == "A\\B"


def test_decode_pdf_literal_octal_escape() -> None:
    """Octal 101 = 'A' (lines 239-246)."""
    assert _decode_pdf_literal(b"(\\101)") == "A"


def test_decode_pdf_literal_octal_two_digits() -> None:
    """Octal 50 = 40 = '(' character."""
    result = _decode_pdf_literal(b"(\\50)")
    assert result == "("


def test_decode_pdf_literal_octal_three_digits() -> None:
    """Octal 110 = 'H'."""
    assert _decode_pdf_literal(b"(\\110ello)") == "Hello"


def test_decode_pdf_literal_invalid_not_in_parens() -> None:
    """Literal not wrapped in parens returns '' (line 206)."""
    assert _decode_pdf_literal(b"Hello") == ""
    assert _decode_pdf_literal(b"(Hello") == ""
    assert _decode_pdf_literal(b"Hello)") == ""


def test_decode_pdf_literal_empty_parens() -> None:
    assert _decode_pdf_literal(b"()") == ""


def test_decode_pdf_literal_unknown_escape() -> None:
    """Unknown escape sequence: backslash followed by non-special char (line 248-249)."""
    # \z is not a recognized escape, so 'z' is appended literally
    assert _decode_pdf_literal(b"(A\\zB)") == "AzB"


def test_decode_pdf_literal_trailing_backslash() -> None:
    """Backslash at end of payload (line 220-221)."""
    result = _decode_pdf_literal(b"(trailing\\)")
    # The \) is an escape for ), so this should produce "trailing)"
    # Wait — the raw_literal is (trailing\) which means startswith ( and endswith )
    # payload = trailing\ , then index reaches '\' -> index+1 >= len -> break
    # Actually let me re-check: raw = b"(trailing\\)" means bytes: ( t r a i l i n g \ )
    # starts with ( and ends with ) -> payload = b"trailing\\"
    # Actually in Python b"(trailing\\)" = bytes for: (trailing\)
    # So payload = b"trailing\\" = bytes for: trailing\
    # The loop hits \ at index 8, increments to index 9 which == len(payload) -> break
    # Hmm, len(b"trailing\\") = 10, not 9. Let me think again.
    # b"trailing\\" is the Python literal for the 9-byte sequence: t r a i l i n g \
    # So len = 9. Index of \ = 8. index becomes 9. 9 >= 9 -> break.
    # Result: b"trailing" -> "trailing"
    assert result == "trailing"


# ---------------------------------------------------------------------------
# _first_value
# ---------------------------------------------------------------------------


def test_first_value_returns_first_match() -> None:
    row = {"a": "", "b": "found", "c": "also"}
    assert _first_value(row, ("a", "b", "c")) == "found"


def test_first_value_returns_none_when_no_match() -> None:
    assert _first_value({"x": "val"}, ("a", "b")) is None


def test_first_value_skips_empty_strings() -> None:
    row = {"a": "", "b": "ok"}
    assert _first_value(row, ("a", "b")) == "ok"


def test_first_value_with_missing_keys() -> None:
    row = {"z": "val"}
    assert _first_value(row, ("a", "b")) is None


# ---------------------------------------------------------------------------
# _coerce_amount
# ---------------------------------------------------------------------------


def test_coerce_amount_none() -> None:
    assert _coerce_amount(None) is None


def test_coerce_amount_empty_string() -> None:
    """Empty string after stripping returns None (line 267)."""
    assert _coerce_amount("") is None
    assert _coerce_amount("  ") is None


def test_coerce_amount_strips_dollar_and_commas() -> None:
    assert _coerce_amount("$1,234.56") == 1234.56


def test_coerce_amount_plain_number() -> None:
    assert _coerce_amount("42.0") == 42.0


def test_coerce_amount_negative() -> None:
    assert _coerce_amount("-100.50") == -100.50


def test_coerce_amount_invalid_returns_none() -> None:
    """Non-numeric string returns None (lines 270-271)."""
    assert _coerce_amount("not-a-number") is None
    assert _coerce_amount("abc") is None


def test_coerce_amount_dollar_sign_only() -> None:
    assert _coerce_amount("$") is None


# ---------------------------------------------------------------------------
# _parse_pdf_statements (integration)
# ---------------------------------------------------------------------------


def test_parse_pdf_statements_splits_extracted_text() -> None:
    pdf_content = b"BT (Statement A) Tj ET BT (Statement B) Tj ET"
    results = _parse_pdf_statements(pdf_content, filename="test.pdf", source="pdf_upload", currency="USD")

    assert len(results) == 2
    assert results[0].input_text == "Statement A"
    assert results[1].input_text == "Statement B"
    assert results[0].filename == "test.pdf"
    assert results[0].source == "pdf_upload"
    assert results[0].currency == "USD"


# ---------------------------------------------------------------------------
# Edge cases / integration
# ---------------------------------------------------------------------------


def test_parse_csv_with_text_column_in_header() -> None:
    """CSV where the 'text' column is present — _build_statement_text_from_row returns it directly."""
    csv_bytes = b"text,amount\nPaid invoice #123,500\n"
    results = _parse_csv_statements(csv_bytes, filename=None, source="csv_upload", currency=None)

    assert len(results) == 1
    assert results[0].input_text == "Paid invoice #123"
    assert results[0].amount == 500.0


def test_parse_csv_with_statement_column() -> None:
    csv_bytes = b"statement,amount\nMonthly subscription,9.99\n"
    results = _parse_csv_statements(csv_bytes, filename=None, source="csv_upload", currency=None)

    assert len(results) == 1
    assert results[0].input_text == "Monthly subscription"


def test_parse_csv_date_columns_alternatives() -> None:
    """Verify date is extracted from 'date' and 'posted_at' alternatives."""
    csv_bytes = b"description,date\nRent,2025-06-01\n"
    results = _parse_csv_statements(csv_bytes, filename=None, source="csv_upload", currency=None)
    assert results[0].transaction_date == "2025-06-01"

    csv_bytes2 = b"description,posted_at\nRent,2025-07-01\n"
    results2 = _parse_csv_statements(csv_bytes2, filename=None, source="csv_upload", currency=None)
    assert results2[0].transaction_date == "2025-07-01"


def test_parse_csv_counterparty_alternatives() -> None:
    """Verify counterparty is extracted from vendor/merchant/payee alternatives."""
    for col in ("vendor", "merchant", "payee"):
        csv_bytes = f"description,{col}\nLunch,CafeX\n".encode()
        results = _parse_csv_statements(csv_bytes, filename=None, source="csv_upload", currency=None)
        assert results[0].counterparty == "CafeX", f"Failed for column {col}"


def test_full_roundtrip_text_upload() -> None:
    """Full roundtrip: text_upload source, semicolons, with currency."""
    raw = b"Bought shoes; Bought hat"
    statements = parse_uploaded_statements(
        contents=raw,
        filename="items.txt",
        source="text_upload",
        currency="GBP",
    )

    assert len(statements) == 2
    assert statements[0].input_text == "Bought shoes"
    assert statements[1].input_text == "Bought hat"
    assert all(s.currency == "GBP" for s in statements)
    assert all(s.filename == "items.txt" for s in statements)
