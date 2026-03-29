from services.shared.ingestion import parse_uploaded_statements, split_manual_statements


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
