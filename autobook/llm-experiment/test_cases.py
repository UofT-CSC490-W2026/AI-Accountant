"""15 test transactions with expected debit/credit tuples.

Design-agnostic — reused across all pipeline variants.
From agent-pipeline.md Test Data table.
"""
from dataclasses import dataclass


@dataclass
class TestCase:
    id: str
    transaction_text: str
    user_context: dict
    expected_debit_tuple: tuple[int, ...]
    expected_credit_tuple: tuple[int, ...]


_DEFAULT_CTX = {"business_type": "general", "province": "ON", "ownership": "corporation"}

TEST_CASES: list[TestCase] = [
    TestCase(
        id="01_inventory_cash",
        transaction_text="Purchase inventory for $100 cash",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
    ),
    TestCase(
        id="02_inventory_on_account",
        transaction_text="Purchase inventory $300 on account",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
    ),
    TestCase(
        id="03_issue_stock_with_apic",
        transaction_text="Issue common stock for $180 cash ($100 par, $80 APIC)",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        # APIC is equity → 2 equity increases
        expected_credit_tuple=(0, 2, 0, 0, 0, 0),
    ),
    TestCase(
        id="04_sell_inventory",
        transaction_text="Sell inventory (cost $300) for $500 cash",
        user_context=_DEFAULT_CTX,
        # Cash + COGS
        expected_debit_tuple=(1, 0, 1, 0, 0, 0),
        # Revenue + Inventory out
        expected_credit_tuple=(0, 0, 1, 1, 0, 0),
    ),
    TestCase(
        id="05_pay_accounts_payable",
        transaction_text="Pay accounts payable $50",
        user_context=_DEFAULT_CTX,
        # Liability decrease (paying off AP)
        expected_debit_tuple=(0, 0, 0, 1, 0, 0),
        # Asset decrease (cash leaving)
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
    ),
    TestCase(
        id="06_refinance_loan",
        transaction_text="Refinance bank loan — old $100 note replaced by new $100 note",
        user_context=_DEFAULT_CTX,
        # Old liability removed
        expected_debit_tuple=(0, 0, 0, 1, 0, 0),
        # New liability created
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
    ),
    TestCase(
        id="07_loan_to_equity",
        transaction_text="Convert $200 loan to equity",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 1, 0, 0),
        expected_credit_tuple=(0, 1, 0, 0, 0, 0),
    ),
    TestCase(
        id="08_deliver_service_against_deposit",
        transaction_text="Deliver service against $100 customer deposit",
        user_context=_DEFAULT_CTX,
        # Unearned Revenue = liability decrease
        expected_debit_tuple=(0, 0, 0, 1, 0, 0),
        expected_credit_tuple=(0, 0, 1, 0, 0, 0),
    ),
    TestCase(
        id="09_repurchase_stock",
        transaction_text="Repurchase $200 of company stock",
        user_context=_DEFAULT_CTX,
        # Treasury Stock = equity decrease (contra-equity)
        expected_debit_tuple=(0, 0, 0, 0, 1, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
    ),
    TestCase(
        id="10_declare_dividend",
        transaction_text="Declare $50 dividend",
        user_context=_DEFAULT_CTX,
        # Retained Earnings debit = dividend increase (slot b), NOT equity decrease
        expected_debit_tuple=(0, 1, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
    ),
    TestCase(
        id="11_convert_preferred_to_common",
        transaction_text="Convert $100 preferred stock to common",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 0, 1, 0),
        expected_credit_tuple=(0, 1, 0, 0, 0, 0),
    ),
    TestCase(
        id="12_pay_salaries",
        transaction_text="Pay $100 salaries",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
    ),
    TestCase(
        id="13_accrue_utility",
        transaction_text="Accrue $50 utility bill",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
    ),
    TestCase(
        id="14_casualty_loss",
        transaction_text="Inventory destroyed by typhoon, $2000 loss",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
    ),
    TestCase(
        id="15_no_entry",
        transaction_text="Board resolution (no financial impact)",
        user_context=_DEFAULT_CTX,
        # No journal entry — pipeline should return empty
        expected_debit_tuple=(0, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 0, 0, 0),
    ),
]
