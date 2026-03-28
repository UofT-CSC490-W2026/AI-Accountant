from __future__ import annotations

from services.flywheel.service import execute


def test_process_runs():
    execute({"parse_id": "p1"})
