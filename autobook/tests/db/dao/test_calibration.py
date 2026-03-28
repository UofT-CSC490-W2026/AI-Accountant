from __future__ import annotations

from db.dao.calibration import CalibrationDAO
from db.models.calibration import CalibrationParams


def test_calibration_model():
    assert CalibrationParams.__tablename__ == "calibration_params"
    assert hasattr(CalibrationParams, "a")
    assert hasattr(CalibrationParams, "b")
    assert hasattr(CalibrationParams, "sample_count")


def test_calibration_insert(db_session):
    row = CalibrationDAO.insert(db_session, a=1.5, b=-0.3, sample_count=50)
    assert row.id is not None
    assert row.a == 1.5
    assert row.b == -0.3
    assert row.sample_count == 50


def test_calibration_get_latest(db_session):
    CalibrationDAO.insert(db_session, a=1.0, b=0.0, sample_count=30)
    CalibrationDAO.insert(db_session, a=1.5, b=-0.3, sample_count=60)
    latest = CalibrationDAO.get_latest(db_session)
    assert latest is not None
    assert latest.sample_count in {30, 60}


def test_calibration_get_latest_empty(db_session):
    result = CalibrationDAO.get_latest(db_session)
    assert result is None
