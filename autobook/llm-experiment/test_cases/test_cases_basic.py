"""15 test transactions with expected debit/credit tuples and journal entries.

Design-agnostic — reused across all pipeline variants.
From basic_examples.md in test-source/.
"""
from dataclasses import dataclass, field


@dataclass
class TestCase:
    id: str
    transaction_text: str
    user_context: dict
    expected_debit_tuple: tuple[int, ...]
    expected_credit_tuple: tuple[int, ...]
    expected_entry: dict | None = None  # {"lines": [{"account_name", "type", "amount"}]}
    ambiguous: bool = False
    # When ambiguous=True: dict mapping case name → {"debit_tuple", "credit_tuple", "entry"}
    expected_cases: dict | None = None

    @property
    def tier(self) -> str:
        """Derive difficulty tier from test case ID prefix."""
        if self.id.startswith("hard_"):
            return "hard"
        if self.id.startswith("int_"):
            return "intermediate"
        return "basic"

    @property
    def expected_decision(self) -> str:
        """Derive expected pipeline decision."""
        if self.ambiguous:
            return "INCOMPLETE_INFORMATION"
        return "APPROVED"


_DEFAULT_CTX = {"business_type": "general", "province": "ON", "ownership": "corporation"}

TEST_CASES: list[TestCase] = [
    TestCase(
        id="basic_01_inventory_cash",
        transaction_text="Purchase inventory for $100 cash",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Inventories — Merchandise", "type": "debit", "amount": 100},
            {"account_name": "Cash", "type": "credit", "amount": 100},
        ]},
    ),
    TestCase(
        id="basic_02_inventory_on_account",
        transaction_text="Purchase inventory $300 on account",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Inventories — Merchandise", "type": "debit", "amount": 300},
            {"account_name": "Trade payables", "type": "credit", "amount": 300},
        ]},
    ),
    TestCase(
        id="basic_03_issue_stock_with_apic",
        transaction_text="Issue common stock for $180 cash ($100 par, $80 APIC)",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 2, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash", "type": "debit", "amount": 180},
            {"account_name": "Share capital — Common", "type": "credit", "amount": 100},
            {"account_name": "Additional paid-in capital", "type": "credit", "amount": 80},
        ]},
    ),
    TestCase(
        id="basic_04_sell_inventory",
        transaction_text="Sell inventory (cost $300) for $500 cash",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 1, 0, 0, 0),
        expected_credit_tuple=(0, 0, 1, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash", "type": "debit", "amount": 500},
            {"account_name": "Cost of goods sold", "type": "debit", "amount": 300},
            {"account_name": "Revenue — Product sales", "type": "credit", "amount": 500},
            {"account_name": "Inventories — Merchandise", "type": "credit", "amount": 300},
        ]},
    ),
    TestCase(
        id="basic_05_pay_accounts_payable",
        transaction_text="Issued a cheque for $50 to settle accounts payable",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 1, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Trade payables", "type": "debit", "amount": 50},
            {"account_name": "Cash", "type": "credit", "amount": 50},
        ]},
    ),
    TestCase(
        id="basic_06_refinance_loan",
        transaction_text="Refinance bank loan — old $100 note replaced by new $100 note",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 1, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Notes payable", "type": "debit", "amount": 100},
            {"account_name": "Notes payable", "type": "credit", "amount": 100},
        ]},
    ),
    TestCase(
        id="basic_07_loan_to_equity",
        transaction_text="Converted a $200 bank loan to equity, issuing 400 common shares",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 1, 0, 0),
        expected_credit_tuple=(0, 1, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Notes payable", "type": "debit", "amount": 200},
            {"account_name": "Share capital — Common", "type": "credit", "amount": 200},
        ]},
    ),
    TestCase(
        id="basic_08_deliver_service_against_deposit",
        transaction_text="Deliver service against $100 customer deposit",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 1, 0, 0),
        expected_credit_tuple=(0, 0, 1, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Contract liabilities", "type": "debit", "amount": 100},
            {"account_name": "Revenue — Product sales", "type": "credit", "amount": 100},
        ]},
    ),
    TestCase(
        id="basic_09_repurchase_stock",
        transaction_text="Bought back 100 shares from shareholders for $200 cash",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 0, 1, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Treasury shares", "type": "debit", "amount": 200},
            {"account_name": "Cash", "type": "credit", "amount": 200},
        ]},
    ),
    TestCase(
        id="basic_10_declare_dividend",
        transaction_text="Board declared a $500,000 cash dividend, payable in 30 days",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 1, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Retained earnings", "type": "debit", "amount": 500000},
            {"account_name": "Dividends payable", "type": "credit", "amount": 500000},
        ]},
    ),
    TestCase(
        id="basic_11_convert_preferred_to_common",
        transaction_text="Converted 50 preferred shares (carrying value $100) to 25 common shares",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 0, 1, 0),
        expected_credit_tuple=(0, 1, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Share capital — Preferred", "type": "debit", "amount": 100},
            {"account_name": "Share capital — Common", "type": "credit", "amount": 100},
        ]},
    ),
    TestCase(
        id="basic_12_pay_salaries",
        transaction_text="Paid employee salaries of $100 in cash",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Salaries expense", "type": "debit", "amount": 100},
            {"account_name": "Cash", "type": "credit", "amount": 100},
        ]},
    ),
    TestCase(
        id="basic_13_accrue_utility",
        transaction_text="Accrue $50 utility bill",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Utilities expense", "type": "debit", "amount": 50},
            {"account_name": "Accrued liabilities", "type": "credit", "amount": 50},
        ]},
    ),
    TestCase(
        id="basic_14_casualty_loss",
        transaction_text="Inventory destroyed by typhoon, $2000 loss",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Casualty loss", "type": "debit", "amount": 2000},
            {"account_name": "Inventories — Merchandise", "type": "credit", "amount": 2000},
        ]},
    ),
    TestCase(
        id="basic_15_no_entry",
        transaction_text="Board resolution (no financial impact)",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 0, 0, 0),
        expected_entry=None,
    ),
]
