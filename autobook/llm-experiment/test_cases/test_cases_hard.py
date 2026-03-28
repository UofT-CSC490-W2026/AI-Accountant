"""Hard test cases — ambiguous transactions requiring clarification.

The pipeline should output a best-guess journal entry AND flag as ambiguous
with a clarification question that distinguishes between the possible cases.

When ambiguous=True:
- expected_debit_tuple / expected_credit_tuple / expected_entry are NOT used
- expected_cases maps each possible interpretation to its correct answer
- The pipeline should route to clarification, not auto-post

From hard_examples.md in test-source/.
"""
from test_cases_basic import TestCase

_DEFAULT_CTX = {"business_type": "general", "province": "ON", "ownership": "corporation"}

HARD_TEST_CASES: list[TestCase] = [

    # ── Hard #1: Note discounting — derecognition vs collateralized borrowing
    TestCase(
        id="hard_01_note_discounting",
        transaction_text="Ford received a 90-day, non-interest-bearing promissory note with a face value of $100,000 as settlement of a trade receivable. Fifty days after the note's issue date, Ford discounted the note at the bank at an annual discount rate of 15%, receiving the net proceeds in cash after deducting the discount charges.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 0, 0, 0),
        ambiguous=True,
        expected_cases={
            "Derecognition (sale)": {
                "debit_tuple": (1, 0, 1, 0, 0, 0),
                "credit_tuple": (0, 0, 0, 1, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Cash", "type": "debit", "amount": 98356},
                    {"account_name": "Loss on derecognition of receivables", "type": "debit", "amount": 1644},
                    {"account_name": "Trade receivables", "type": "credit", "amount": 100000},
                ]},
            },
            "Collateralized borrowing": {
                "debit_tuple": (1, 0, 1, 0, 0, 0),
                "credit_tuple": (1, 0, 0, 0, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Cash", "type": "debit", "amount": 98356},
                    {"account_name": "Interest expense", "type": "debit", "amount": 1644},
                    {"account_name": "Short-term borrowings", "type": "credit", "amount": 100000},
                ]},
            },
        },
    ),

    # ── Hard #2: Investment classification — 3 possible treatments
    TestCase(
        id="hard_02_investment_classification",
        transaction_text="BlackRock acquired 10% of Ford's outstanding common shares for $3,000,000 and paid a transaction fee of $100,000 by cheque.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 0, 0, 0),
        ambiguous=True,
        expected_cases={
            "Short-term trading (FVTPL)": {
                "debit_tuple": (1, 0, 1, 0, 0, 0),
                "credit_tuple": (0, 0, 0, 1, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Financial assets at FVTPL", "type": "debit", "amount": 3000000},
                    {"account_name": "Investment transaction costs", "type": "debit", "amount": 100000},
                    {"account_name": "Cash", "type": "credit", "amount": 3100000},
                ]},
            },
            "Long-term strategic (FVOCI)": {
                "debit_tuple": (1, 0, 0, 0, 0, 0),
                "credit_tuple": (0, 0, 0, 1, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Financial assets at FVOCI", "type": "debit", "amount": 3100000},
                    {"account_name": "Cash", "type": "credit", "amount": 3100000},
                ]},
            },
            "Significant influence (Equity method)": {
                "debit_tuple": (1, 0, 0, 0, 0, 0),
                "credit_tuple": (0, 0, 0, 1, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Investment in associate", "type": "debit", "amount": 3100000},
                    {"account_name": "Cash", "type": "credit", "amount": 3100000},
                ]},
            },
        },
    ),

    # ── Hard #27: Meal expense — purpose determines account
    TestCase(
        id="hard_27_meal_purpose",
        transaction_text="Mondelez paid $125 for a meal using the corporate credit card.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 0, 0, 0),
        ambiguous=True,
        expected_cases={
            "Overtime meal (employee benefit)": {
                "debit_tuple": (0, 0, 1, 0, 0, 0),
                "credit_tuple": (1, 0, 0, 0, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Employee benefits expense", "type": "debit", "amount": 125},
                    {"account_name": "Credit card payable", "type": "credit", "amount": 125},
                ]},
            },
            "Working meeting": {
                "debit_tuple": (0, 0, 1, 0, 0, 0),
                "credit_tuple": (1, 0, 0, 0, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Meeting expense", "type": "debit", "amount": 125},
                    {"account_name": "Credit card payable", "type": "credit", "amount": 125},
                ]},
            },
            "Client entertainment": {
                "debit_tuple": (0, 0, 1, 0, 0, 0),
                "credit_tuple": (1, 0, 0, 0, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Entertainment expense", "type": "debit", "amount": 125},
                    {"account_name": "Credit card payable", "type": "credit", "amount": 125},
                ]},
            },
            "Factory staff meal (production overhead)": {
                "debit_tuple": (1, 0, 0, 0, 0, 0),
                "credit_tuple": (1, 0, 0, 0, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Work in process — Manufacturing overhead", "type": "debit", "amount": 125},
                    {"account_name": "Credit card payable", "type": "credit", "amount": 125},
                ]},
            },
        },
    ),

    # ── Hard #32: Grocery purchase — purpose determines account
    TestCase(
        id="hard_32_grocery_purpose",
        transaction_text="Target purchased tea, beverages, and refreshments from a grocery store for $1,200 plus 10% sales tax, totalling $1,320, paid by corporate credit card.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 0, 0, 0),
        ambiguous=True,
        expected_cases={
            "Client entertainment": {
                "debit_tuple": (0, 0, 1, 0, 0, 0),
                "credit_tuple": (1, 0, 0, 0, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Entertainment expense", "type": "debit", "amount": 1320},
                    {"account_name": "Credit card payable", "type": "credit", "amount": 1320},
                ]},
            },
            "Employee break room supplies": {
                "debit_tuple": (0, 0, 1, 0, 0, 0),
                "credit_tuple": (1, 0, 0, 0, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Employee benefits expense", "type": "debit", "amount": 1320},
                    {"account_name": "Credit card payable", "type": "credit", "amount": 1320},
                ]},
            },
        },
    ),

    # ── Hard #16: Lease payment — prepaid asset vs immediate expense
    TestCase(
        id="hard_16_rent_treatment",
        transaction_text="Atlas Van Lines leased office space and paid $24,000 by cheque, representing 12 months of rent.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 0, 0, 0),
        ambiguous=True,
        expected_cases={
            "Prepaid (asset recognition)": {
                "debit_tuple": (1, 0, 0, 0, 0, 0),
                "credit_tuple": (0, 0, 0, 1, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Prepaid rent", "type": "debit", "amount": 24000},
                    {"account_name": "Cash — chequing", "type": "credit", "amount": 24000},
                ]},
            },
            "Expense (short-term lease exemption)": {
                "debit_tuple": (0, 0, 1, 0, 0, 0),
                "credit_tuple": (0, 0, 0, 1, 0, 0),
                "entry": {"lines": [
                    {"account_name": "Rent expense", "type": "debit", "amount": 24000},
                    {"account_name": "Cash — chequing", "type": "credit", "amount": 24000},
                ]},
            },
        },
    ),
]
