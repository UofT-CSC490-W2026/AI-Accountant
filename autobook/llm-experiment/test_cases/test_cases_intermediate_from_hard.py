"""Hard examples with determining context added to the transaction description.

With context provided, these become intermediate-level problems — one correct answer.
Each hard case produces multiple test cases (one per interpretation).
From hard_examples.md in test-source/.
"""
from test_cases_basic import TestCase

_DEFAULT_CTX = {"business_type": "general", "province": "ON", "ownership": "corporation"}

INTERMEDIATE_FROM_HARD_TEST_CASES: list[TestCase] = [

    # ── Hard #1: Note discounting — derecognition vs collateralized borrowing
    TestCase(
        id="int_hard_01a_note_derecognition",
        transaction_text="Ford received a 90-day, non-interest-bearing promissory note with a face value of $100,000 as settlement of a trade receivable. Fifty days after the note's issue date, Ford discounted the note at the bank at an annual discount rate of 15%, receiving the net proceeds in cash after deducting the discount charges. Management has determined that this qualifies as derecognition (transfer of risks and rewards) under IFRS 9.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (cash) + 1 expense (loss on derecognition)
        expected_debit_tuple=(1, 0, 1, 0, 0, 0),
        # 1 asset decrease (trade receivables)
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash", "type": "debit", "amount": 98356},
            {"account_name": "Loss on derecognition of receivables", "type": "debit", "amount": 1644},
            {"account_name": "Trade receivables", "type": "credit", "amount": 100000},
        ]},
    ),
    TestCase(
        id="int_hard_01b_note_collateralized",
        transaction_text="Ford received a 90-day, non-interest-bearing promissory note with a face value of $100,000 as settlement of a trade receivable. Fifty days after the note's issue date, Ford discounted the note at the bank at an annual discount rate of 15%, receiving the net proceeds in cash after deducting the discount charges. Management has determined that this is a collateralized borrowing (risks and rewards not transferred).",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (cash) + 1 expense (interest)
        expected_debit_tuple=(1, 0, 1, 0, 0, 0),
        # 1 liability increase (short-term borrowings)
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash", "type": "debit", "amount": 98356},
            {"account_name": "Interest expense", "type": "debit", "amount": 1644},
            {"account_name": "Short-term borrowings", "type": "credit", "amount": 100000},
        ]},
    ),

    # ── Hard #2: Investment classification — FVTPL vs FVOCI vs Equity method
    TestCase(
        id="int_hard_02a_investment_fvtpl",
        transaction_text="BlackRock acquired 10% of Ford's outstanding common shares for $3,000,000 and paid a transaction fee of $100,000 by cheque. Management's intent is short-term trading, classified as FVTPL under IFRS 9.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (FVTPL at fair value, no transaction costs capitalized) + 1 expense (transaction costs)
        expected_debit_tuple=(1, 0, 1, 0, 0, 0),
        # 1 asset decrease (cash)
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Financial assets at FVTPL", "type": "debit", "amount": 3000000},
            {"account_name": "Investment transaction costs", "type": "debit", "amount": 100000},
            {"account_name": "Cash", "type": "credit", "amount": 3100000},
        ]},
    ),
    TestCase(
        id="int_hard_02b_investment_fvoci",
        transaction_text="BlackRock acquired 10% of Ford's outstanding common shares for $3,000,000 and paid a transaction fee of $100,000 by cheque. Management elected the FVOCI option for this long-term strategic equity investment under IFRS 9.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (FVOCI at cost + transaction costs)
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Financial assets at FVOCI", "type": "debit", "amount": 3100000},
            {"account_name": "Cash", "type": "credit", "amount": 3100000},
        ]},
    ),
    TestCase(
        id="int_hard_02c_investment_equity_method",
        transaction_text="BlackRock acquired 10% of Ford's outstanding common shares for $3,000,000 and paid a transaction fee of $100,000 by cheque. BlackRock has significant influence over Ford and will account for this using the equity method under IAS 28.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (investment in associate at cost + transaction costs)
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Investment in associate", "type": "debit", "amount": 3100000},
            {"account_name": "Cash", "type": "credit", "amount": 3100000},
        ]},
    ),

    # ── Hard #27: Meal expense — purpose determines account
    TestCase(
        id="int_hard_27a_meal_overtime",
        transaction_text="Mondelez paid $125 for a meal using the corporate credit card. The meal was provided to employees working overtime as an employee benefit.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Employee benefits expense", "type": "debit", "amount": 125},
            {"account_name": "Credit card payable", "type": "credit", "amount": 125},
        ]},
    ),
    TestCase(
        id="int_hard_27b_meal_meeting",
        transaction_text="Mondelez paid $125 for a meal using the corporate credit card. The meal was for a working meeting among employees.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Meeting expense", "type": "debit", "amount": 125},
            {"account_name": "Credit card payable", "type": "credit", "amount": 125},
        ]},
    ),
    TestCase(
        id="int_hard_27c_meal_entertainment",
        transaction_text="Mondelez paid $125 for a meal using the corporate credit card. The meal was for client entertainment.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Entertainment expense", "type": "debit", "amount": 125},
            {"account_name": "Credit card payable", "type": "credit", "amount": 125},
        ]},
    ),
    TestCase(
        id="int_hard_27d_meal_factory",
        transaction_text="Mondelez paid $125 for a meal using the corporate credit card. The meal was provided to factory production staff and is classified as manufacturing overhead.",
        user_context=_DEFAULT_CTX,
        # Asset increase (WIP), not expense
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Work in process — Manufacturing overhead", "type": "debit", "amount": 125},
            {"account_name": "Credit card payable", "type": "credit", "amount": 125},
        ]},
    ),

    # ── Hard #32: Grocery purchase — purpose determines account
    TestCase(
        id="int_hard_32a_grocery_entertainment",
        transaction_text="Target purchased tea, beverages, and refreshments from a grocery store for $1,200 plus 10% sales tax, totalling $1,320, paid by corporate credit card. The purchase was for client entertainment.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Entertainment expense", "type": "debit", "amount": 1320},
            {"account_name": "Credit card payable", "type": "credit", "amount": 1320},
        ]},
    ),
    TestCase(
        id="int_hard_32b_grocery_breakroom",
        transaction_text="Target purchased tea, beverages, and refreshments from a grocery store for $1,200 plus 10% sales tax, totalling $1,320, paid by corporate credit card. The purchase was for the employee break room.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Employee benefits expense", "type": "debit", "amount": 1320},
            {"account_name": "Credit card payable", "type": "credit", "amount": 1320},
        ]},
    ),

    # ── Hard #16: Lease payment — prepaid asset vs immediate expense
    TestCase(
        id="int_hard_16a_rent_prepaid",
        transaction_text="Atlas Van Lines leased office space and paid $24,000 by cheque, representing 12 months of rent. The entity's accounting policy is to recognize the payment as a prepaid asset.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Prepaid rent", "type": "debit", "amount": 24000},
            {"account_name": "Cash — chequing", "type": "credit", "amount": 24000},
        ]},
    ),
    TestCase(
        id="int_hard_16b_rent_expense",
        transaction_text="Atlas Van Lines leased office space and paid $24,000 by cheque, representing 12 months of rent. The entity elected the short-term lease exemption under IFRS 16 and expenses the payment immediately.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Rent expense", "type": "debit", "amount": 24000},
            {"account_name": "Cash — chequing", "type": "credit", "amount": 24000},
        ]},
    ),
]
