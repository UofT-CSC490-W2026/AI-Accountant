from __future__ import annotations

from api.routes.parse import _infer_upload_source


def test_infer_csv():
    assert _infer_upload_source("transactions.csv") == "csv_upload"


def test_infer_pdf():
    assert _infer_upload_source("invoice.pdf") == "pdf_upload"


def test_infer_unknown():
    assert _infer_upload_source("data.xlsx") == "upload"


def test_infer_none():
    assert _infer_upload_source(None) == "upload"
