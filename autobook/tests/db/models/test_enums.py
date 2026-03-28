from __future__ import annotations

from db.models.enums import (
    AccountType, AccountSubType, JournalEntryStatus,
    AssetStatus, ScheduleFrequency, IntegrationPlatform,
)


def test_enum_account_type():
    assert AccountType.ASSET == "asset"
    assert len(AccountType) == 5


def test_enum_account_subtype():
    assert AccountSubType.CURRENT_ASSET == "current_asset"
    assert len(AccountSubType) >= 10


def test_enum_journal_entry_status():
    assert JournalEntryStatus.POSTED == "posted"
    assert len(JournalEntryStatus) == 4


def test_enum_asset_status():
    assert AssetStatus.ACTIVE == "active"
    assert len(AssetStatus) == 2


def test_enum_schedule_frequency():
    assert ScheduleFrequency.MONTHLY == "monthly"
    assert len(ScheduleFrequency) == 3


def test_enum_integration_platform():
    assert IntegrationPlatform.STRIPE == "stripe"
    assert len(IntegrationPlatform) >= 4
