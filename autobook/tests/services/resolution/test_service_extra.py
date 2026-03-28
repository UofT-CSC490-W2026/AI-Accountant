from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import services.resolution.service as resolution_svc


def test_is_resolved_approved():
    assert resolution_svc._is_resolved({"clarification": {"status": "approved"}}) is True


def test_is_resolved_posted():
    assert resolution_svc._is_resolved({"clarification": {"status": "posted"}}) is True


def test_is_resolved_false():
    assert resolution_svc._is_resolved({"clarification": {"status": "pending"}}) is False


def test_is_resolved_no_clarification():
    assert resolution_svc._is_resolved({}) is False


def test_is_rejected_true():
    assert resolution_svc._is_rejected({"clarification": {"status": "rejected"}}) is True


def test_is_rejected_false():
    assert resolution_svc._is_rejected({"clarification": {"status": "approved"}}) is False
