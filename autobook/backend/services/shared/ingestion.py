from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass


TEXT_COLUMNS = ("input_text", "statement", "text", "memo")
DATE_COLUMNS = ("transaction_date", "date", "posted_at")
AMOUNT_COLUMNS = ("amount", "value")
COUNTERPARTY_COLUMNS = ("counterparty", "vendor", "merchant", "payee")
CURRENCY_COLUMNS = ("currency",)
SOURCE_COLUMNS = ("source",)

PDF_LITERAL_REGEX = re.compile(rb"\((?:\\.|[^\\)])*\)\s*Tj")
PDF_ARRAY_REGEX = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)
PDF_ARRAY_LITERAL_REGEX = re.compile(rb"\((?:\\.|[^\\)])*\)")


@dataclass(frozen=True)
class IngestedStatement:
    input_text: str
    source: str
    currency: str | None = None
    filename: str | None = None
    transaction_date: str | None = None
    amount: float | None = None
    counterparty: str | None = None


def split_manual_statements(input_text: str, *, source: str, currency: str | None = None) -> list[IngestedStatement]:
    parts = _split_statement_text(input_text)
    return [
        IngestedStatement(
            input_text=part,
            source=source,
            currency=currency,
        )
        for part in parts
    ]


def parse_uploaded_statements(
    *,
    contents: bytes,
    filename: str | None,
    source: str,
    currency: str | None = None,
) -> list[IngestedStatement]:
    normalized_source = (source or "").strip().lower()
    if normalized_source == "csv_upload":
        return _parse_csv_statements(contents, filename=filename, source=source, currency=currency)
    if normalized_source == "pdf_upload":
        return _parse_pdf_statements(contents, filename=filename, source=source, currency=currency)

    text = _decode_text_contents(contents)
    return [
        IngestedStatement(
            input_text=statement,
            source=source,
            currency=currency,
            filename=filename,
        )
        for statement in _split_statement_text(text)
    ]


def _parse_csv_statements(
    contents: bytes,
    *,
    filename: str | None,
    source: str,
    currency: str | None,
) -> list[IngestedStatement]:
    text = _decode_text_contents(contents)
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = [str(name).strip().lower() for name in (reader.fieldnames or []) if name]
    rows = list(reader)

    if fieldnames:
        statements: list[IngestedStatement] = []
        for row in rows:
            normalized_row = {str(key).strip().lower(): (value or "").strip() for key, value in row.items() if key}
            input_text = _build_statement_text_from_row(normalized_row)
            if not input_text:
                continue
            statements.append(
                IngestedStatement(
                    input_text=input_text,
                    source=normalized_row.get("source") or source,
                    currency=normalized_row.get("currency") or currency,
                    filename=filename,
                    transaction_date=_first_value(normalized_row, DATE_COLUMNS),
                    amount=_coerce_amount(_first_value(normalized_row, AMOUNT_COLUMNS)),
                    counterparty=_first_value(normalized_row, COUNTERPARTY_COLUMNS),
                )
            )
        return statements

    statements = []
    for row in csv.reader(io.StringIO(text)):
        columns = [column.strip() for column in row if column and column.strip()]
        if not columns:
            continue
        statements.append(
            IngestedStatement(
                input_text=columns[0],
                source=source,
                currency=currency,
                filename=filename,
            )
        )
    return statements


def _parse_pdf_statements(
    contents: bytes,
    *,
    filename: str | None,
    source: str,
    currency: str | None,
) -> list[IngestedStatement]:
    extracted_text = _extract_text_from_simple_pdf(contents)
    return [
        IngestedStatement(
            input_text=statement,
            source=source,
            currency=currency,
            filename=filename,
        )
        for statement in _split_statement_text(extracted_text)
    ]


def _build_statement_text_from_row(row: dict[str, str]) -> str:
    text_value = _first_value(row, TEXT_COLUMNS)
    if text_value:
        return text_value

    description = row.get("description", "").strip()
    if not description:
        return ""

    parts = [description]
    counterparty = _first_value(row, COUNTERPARTY_COLUMNS)
    amount = _first_value(row, AMOUNT_COLUMNS)
    transaction_date = _first_value(row, DATE_COLUMNS)

    if counterparty:
        parts.append(f"to {counterparty}")
    if amount:
        parts.append(f"for ${amount}")
    if transaction_date:
        parts.append(f"on {transaction_date}")
    return " ".join(parts).strip()


def _split_statement_text(raw_text: str) -> list[str]:
    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    if ";" in normalized:
        chunks = normalized.split(";")
    else:
        chunks = normalized.split("\n")

    statements: list[str] = []
    for chunk in chunks:
        cleaned = " ".join(chunk.strip().split())
        if cleaned:
            statements.append(cleaned)
    return statements


def _decode_text_contents(contents: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return contents.decode(encoding)
        except UnicodeDecodeError:
            continue
    return contents.decode("utf-8", errors="ignore")


def _extract_text_from_simple_pdf(contents: bytes) -> str:
    chunks: list[str] = []

    for match in PDF_LITERAL_REGEX.finditer(contents):
        literal = match.group(0).rsplit(b")", 1)[0] + b")"
        decoded = _decode_pdf_literal(literal)
        if decoded:
            chunks.append(decoded)

    for match in PDF_ARRAY_REGEX.finditer(contents):
        for literal in PDF_ARRAY_LITERAL_REGEX.finditer(match.group(1)):
            decoded = _decode_pdf_literal(literal.group(0))
            if decoded:
                chunks.append(decoded)

    if chunks:
        return "\n".join(chunks)

    return _decode_text_contents(contents)


def _decode_pdf_literal(raw_literal: bytes) -> str:
    if not raw_literal.startswith(b"(") or not raw_literal.endswith(b")"):
        return ""

    payload = raw_literal[1:-1]
    result = bytearray()
    index = 0

    while index < len(payload):
        current = payload[index]
        if current != 92:
            result.append(current)
            index += 1
            continue

        index += 1
        if index >= len(payload):
            break

        escaped = payload[index]
        escapes = {
            110: b"\n",
            114: b"\r",
            116: b"\t",
            98: b"\b",
            102: b"\f",
            40: b"(",
            41: b")",
            92: b"\\",
        }
        if escaped in escapes:
            result.extend(escapes[escaped])
            index += 1
            continue

        if 48 <= escaped <= 55:
            octal_digits = bytes([escaped])
            index += 1
            while index < len(payload) and len(octal_digits) < 3 and 48 <= payload[index] <= 55:
                octal_digits += bytes([payload[index]])
                index += 1
            result.append(int(octal_digits, 8))
            continue

        result.append(escaped)
        index += 1

    return result.decode("utf-8", errors="ignore").strip()


def _first_value(row: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for key in candidates:
        value = row.get(key)
        if value:
            return value
    return None


def _coerce_amount(raw_amount: str | None) -> float | None:
    if raw_amount is None:
        return None
    normalized = raw_amount.replace("$", "").replace(",", "").strip()
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None
