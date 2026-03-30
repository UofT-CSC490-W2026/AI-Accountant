"""30 intermediate test transactions with expected debit/credit tuples and journal entries.

More complex than basic: multi-line entries, capitalization rules, cost allocation,
compound entries, tax handling, present value calculations.
From intermediate_examples.md in test-source/.
"""
from test_cases_basic import TestCase

_DEFAULT_CTX = {"business_type": "general", "province": "ON", "ownership": "corporation"}

INTERMEDIATE_TEST_CASES: list[TestCase] = [
    # ── IAS 16: Property, Plant & Equipment ──────────────────────────────
    TestCase(
        id="int_03_machinery_purchase",
        transaction_text="Clorox purchased machinery from Ford for $700,000 on account for factory expansion. Clorox also paid by cheque $30,000 in freight, $20,000 in installation, and $50,000 in testing and commissioning costs.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (machinery capitalized at $800,000)
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        # 1 liability increase (AP) + 1 asset decrease (cash)
        expected_credit_tuple=(1, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "PP&E — Machinery", "type": "debit", "amount": 800000},
            {"account_name": "Trade payables", "type": "credit", "amount": 700000},
            {"account_name": "Cash", "type": "credit", "amount": 100000},
        ]},
    ),
    TestCase(
        id="int_04_major_overhaul",
        transaction_text="Clorox originally purchased machinery for $800,000, intending to use it for 10 years. In year 5, Clorox spent $200,000 in cash on a major overhaul, which extended the remaining useful life by an additional 2 years.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "PP&E — Machinery", "type": "debit", "amount": 200000},
            {"account_name": "Cash", "type": "credit", "amount": 200000},
        ]},
    ),
    TestCase(
        id="int_12_site_improvements",
        transaction_text="Ford incurred $1,750,000 in cash for the construction of fencing, streetlights, and walkways surrounding the newly constructed factory. Additionally, Ford paid $2,360,000 by cheque for permanent landscaping installations.",
        user_context=_DEFAULT_CTX,
        # 2 asset increases (site improvements + land)
        expected_debit_tuple=(2, 0, 0, 0, 0, 0),
        # 2 asset decreases (cash + cheque)
        expected_credit_tuple=(0, 0, 0, 2, 0, 0),
        expected_entry={"lines": [
            {"account_name": "PP&E — Site improvements", "type": "debit", "amount": 1750000},
            {"account_name": "Land", "type": "debit", "amount": 2360000},
            {"account_name": "Cash", "type": "credit", "amount": 1750000},
            {"account_name": "Cash — chequing", "type": "credit", "amount": 2360000},
        ]},
    ),
    TestCase(
        id="int_14_vehicle_mixed_payment",
        transaction_text="Atlas Van Lines purchased a delivery vehicle for $40,000. The company paid 50% in cash and issued a 2-month promissory note for the remainder.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "PP&E — Vehicles", "type": "debit", "amount": 40000},
            {"account_name": "Cash", "type": "credit", "amount": 20000},
            {"account_name": "Notes payable", "type": "credit", "amount": 20000},
        ]},
    ),
    TestCase(
        id="int_18_multiple_assets",
        transaction_text="Atlas Van Lines purchased office desks for $2,000 and computers for $3,500, both paid in cash. Additionally, Atlas purchased a crane-equipped truck for $250,000 on account for use in moving operations.",
        user_context=_DEFAULT_CTX,
        # 2 asset increases (office equipment + vehicles)
        expected_debit_tuple=(2, 0, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "PP&E — Office equipment", "type": "debit", "amount": 5500},
            {"account_name": "PP&E — Vehicles", "type": "debit", "amount": 250000},
            {"account_name": "Cash", "type": "credit", "amount": 5500},
            {"account_name": "Trade payables", "type": "credit", "amount": 250000},
        ]},
    ),
    TestCase(
        id="int_31_vehicle_nonrecoverable_tax",
        transaction_text="Target purchased a sedan from Ford for $48,000 (exclusive of sales tax) for an executive's commuting and business use. The total amount of $52,800 (including 10% non-recoverable sales tax) was financed through a 3-month dealer payment plan.",
        user_context=_DEFAULT_CTX,
        # Non-recoverable tax capitalized into asset
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "PP&E — Vehicles", "type": "debit", "amount": 52800},
            {"account_name": "Other payables", "type": "credit", "amount": 52800},
        ]},
    ),

    # ── IAS 16: Land + building allocation ───────────────────────────────
    TestCase(
        id="int_25_building_purchase_allocation",
        transaction_text="Mondelez purchased land and a building from a vendor for $9,000,000 (exclusive of sales tax) to be used as a product storage warehouse. Fifty percent of the purchase price is due in 6 months, and the balance plus 10% sales tax on the building was paid by cheque. At the date of acquisition, the fair values of the land and building components were $8,000,000 and $4,000,000, respectively.",
        user_context=_DEFAULT_CTX,
        # 3 asset increases: land, building, VAT receivable (on building only)
        expected_debit_tuple=(3, 0, 0, 0, 0, 0),
        # 1 asset decrease (cash) + 1 liability increase (payable)
        expected_credit_tuple=(1, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Land", "type": "debit", "amount": 6000000},
            {"account_name": "Building", "type": "debit", "amount": 3000000},
            {"account_name": "VAT receivable", "type": "debit", "amount": 300000},
            {"account_name": "Cash — chequing", "type": "credit", "amount": 4800000},
            {"account_name": "Other payables", "type": "credit", "amount": 4500000},
        ]},
    ),

    # ── IFRS 9: Financial instruments ────────────────────────────────────
    TestCase(
        id="int_05_bond_issuance_discount",
        transaction_text="Clorox issued bonds with a face value of $3,000,000, a 3-year term, and a coupon rate of 10% with interest payable annually on December 31. The bonds were issued at a discount to reflect the market interest rate of 15%, and the proceeds were received in cash.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (cash) + 1 contra-liability (discount)
        expected_debit_tuple=(1, 0, 0, 1, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash", "type": "debit", "amount": 2657510},
            {"account_name": "Discount on bonds payable", "type": "debit", "amount": 342490},
            {"account_name": "Bonds payable", "type": "credit", "amount": 3000000},
        ]},
    ),
    TestCase(
        id="int_11_land_instalment_discount",
        transaction_text="At the beginning of the year, Ford acquired land with an existing building for $60,000,000 for the purpose of constructing a new factory. The purchase price is to be paid in 6 equal annual instalments of $10,000,000, commencing at the end of the year of acquisition. The existing building will be demolished immediately upon purchase. The market interest rate at the date of acquisition was 6%.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (land) + 1 contra-liability (discount)
        expected_debit_tuple=(1, 0, 0, 1, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Land", "type": "debit", "amount": 49173000},
            {"account_name": "Discount on long-term payables", "type": "debit", "amount": 10827000},
            {"account_name": "Long-term payables", "type": "credit", "amount": 60000000},
        ]},
    ),
    TestCase(
        id="int_15_bank_loan",
        transaction_text="Atlas Van Lines borrowed $200,000 in cash from its bank at an annual interest rate of 6% for a term of 3 years. Interest is payable semi-annually.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash", "type": "debit", "amount": 200000},
            {"account_name": "Long-term borrowings", "type": "credit", "amount": 200000},
        ]},
    ),
    TestCase(
        id="int_30_short_term_loan_advance",
        transaction_text="Target advanced a short-term loan of $2,000,000 to a business partner for a term of one year, transferring the funds from Target's chequing account to the partner's chequing account. Interest is charged at an annual rate of 4.5%, receivable at the end of each month.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Short-term loans receivable", "type": "debit", "amount": 2000000},
            {"account_name": "Cash — chequing", "type": "credit", "amount": 2000000},
        ]},
    ),

    # ── IAS 37: Provisions ───────────────────────────────────────────────
    TestCase(
        id="int_06_warranty_provision",
        transaction_text="Ford has a product warranty policy under which it repairs or replaces any defective products within one year of sale. If repair is required, the estimated cost is $2,000,000; if replacement is required, the estimated cost is $10,000,000. Based on historical experience, the probability of a repair claim is 20% and the probability of a replacement claim is 5%.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Warranty expense", "type": "debit", "amount": 900000},
            {"account_name": "Provision for warranties", "type": "credit", "amount": 900000},
        ]},
    ),
    TestCase(
        id="int_07_decommissioning_provision",
        transaction_text="Tidewater acquired an offshore marine structure for $4,000,000 on account. The structure is subject to a 10-year operating permit, which requires full site restoration at the end of the permit term. Tidewater estimated the future restoration cost and determined its present value to be $1,950,000.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (structure at $5,950,000 = cost + provision)
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        # 2 liability increases (AP + provision)
        expected_credit_tuple=(2, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "PP&E — Marine structures", "type": "debit", "amount": 5950000},
            {"account_name": "Trade payables", "type": "credit", "amount": 4000000},
            {"account_name": "Decommissioning provision", "type": "credit", "amount": 1950000},
        ]},
    ),

    # ── IAS 32: Equity transactions ──────────────────────────────────────
    TestCase(
        id="int_08_share_repurchase_cancel",
        transaction_text="Eagle Bulk Shipping repurchased 10,000 of its own common shares (par value $5.00 per share) from shareholders at $6.00 per share in cash and immediately cancelled the shares.",
        user_context=_DEFAULT_CTX,
        # 2 equity decreases (share capital + retained earnings)
        expected_debit_tuple=(0, 0, 0, 0, 2, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Share capital", "type": "debit", "amount": 50000},
            {"account_name": "Retained earnings", "type": "debit", "amount": 10000},
            {"account_name": "Cash", "type": "credit", "amount": 60000},
        ]},
    ),

    # ── IAS 2: Inventories ───────────────────────────────────────────────
    TestCase(
        id="int_09_merchandise_with_costs",
        transaction_text="Target, a retailer, purchased merchandise from a supplier for $1,000,000 on account. Target also paid cash for the following: freight to warehouse $120,000, shipping insurance $30,000, post-acquisition warehouse storage $20,000, and outbound delivery freight $50,000.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (inventory) + 2 expense (warehousing + distribution)
        expected_debit_tuple=(1, 0, 2, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Inventories — Merchandise", "type": "debit", "amount": 1150000},
            {"account_name": "Warehousing expense", "type": "debit", "amount": 20000},
            {"account_name": "Distribution costs", "type": "debit", "amount": 50000},
            {"account_name": "Trade payables", "type": "credit", "amount": 1000000},
            {"account_name": "Cash", "type": "credit", "amount": 220000},
        ]},
    ),
    TestCase(
        id="int_10_prepayment",
        transaction_text="Target paid $1,000,000 in cash to a supplier as a prepayment for raw materials, in anticipation of recent price surges and supply shortages.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Prepayments", "type": "debit", "amount": 1000000},
            {"account_name": "Cash", "type": "credit", "amount": 1000000},
        ]},
    ),

    # ── IFRS 15: Revenue ─────────────────────────────────────────────────
    TestCase(
        id="int_17_customer_deposit",
        transaction_text="Atlas Van Lines entered into a contract with a customer to provide moving services in one month for a total contract price of $17,700. Upon signing, Atlas received $5,000 as a deposit via bank transfer to its chequing account.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash — chequing", "type": "debit", "amount": 5000},
            {"account_name": "Contract liabilities", "type": "credit", "amount": 5000},
        ]},
    ),
    TestCase(
        id="int_19_service_revenue_cash",
        transaction_text="Atlas Van Lines provided moving services to a customer for $25,500 and received a certified cheque as payment.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 1, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash", "type": "debit", "amount": 25500},
            {"account_name": "Revenue — Service revenue", "type": "credit", "amount": 25500},
        ]},
    ),
    TestCase(
        id="int_20_service_revenue_credit",
        transaction_text="Atlas Van Lines provided office relocation services to a customer for $31,500. Payment is due in 10 days.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(0, 0, 1, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Trade receivables", "type": "debit", "amount": 31500},
            {"account_name": "Revenue — Service revenue", "type": "credit", "amount": 31500},
        ]},
    ),
    TestCase(
        id="int_22_compound_sale_with_tax",
        transaction_text="Mondelez sold 300 cases of snack products to a customer at $230 per case (cost: $185 per case). The total selling price of $69,000 plus 10% sales tax resulted in a gross amount of $75,900. Mondelez received $45,900 via bank transfer to its chequing account, with the remainder on credit.",
        user_context=_DEFAULT_CTX,
        # 2 asset increases (cash + receivable) + 1 expense (COGS)
        expected_debit_tuple=(2, 0, 1, 0, 0, 0),
        # 1 revenue + 1 liability (tax) + 1 asset decrease (inventory)
        expected_credit_tuple=(1, 0, 1, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash — chequing", "type": "debit", "amount": 45900},
            {"account_name": "Trade receivables", "type": "debit", "amount": 30000},
            {"account_name": "Cost of goods sold", "type": "debit", "amount": 55500},
            {"account_name": "Revenue — Product sales", "type": "credit", "amount": 69000},
            {"account_name": "Sales tax payable", "type": "credit", "amount": 6900},
            {"account_name": "Inventories — Finished goods", "type": "credit", "amount": 55500},
        ]},
    ),

    # ── IAS 19 / IAS 2: Payroll & Manufacturing overhead ────────────────
    TestCase(
        id="int_23_split_electricity",
        transaction_text="Mondelez paid factory electricity charges of $15,000 and office electricity charges of $5,500 using the corporate credit card.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (WIP overhead) + 1 expense (office utilities)
        expected_debit_tuple=(1, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Work in process — Manufacturing overhead", "type": "debit", "amount": 15000},
            {"account_name": "Utilities expense", "type": "debit", "amount": 5500},
            {"account_name": "Credit card payable", "type": "credit", "amount": 20500},
        ]},
    ),
    TestCase(
        id="int_26a_payroll_recognition",
        transaction_text="Mondelez recognized January payroll: production worker wages of $25,000 (5 employees) and administrative salaries of $20,000 (5 employees). The following employee-borne statutory deductions were withheld: pension contributions $2,000, health insurance premiums $3,250, employment insurance premiums $1,050, and income tax withholdings $1,450. The net amount was transferred from the chequing account to employees' personal accounts.",
        user_context=_DEFAULT_CTX,
        # 1 asset increase (WIP direct labour) + 1 expense (admin salaries)
        expected_debit_tuple=(1, 0, 1, 0, 0, 0),
        # 1 liability increase (withholdings) + 1 asset decrease (cash)
        expected_credit_tuple=(1, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Work in process — Direct labour", "type": "debit", "amount": 25000},
            {"account_name": "Salaries expense", "type": "debit", "amount": 20000},
            {"account_name": "Statutory withholdings payable", "type": "credit", "amount": 7750},
            {"account_name": "Cash — chequing", "type": "credit", "amount": 37250},
        ]},
    ),
    TestCase(
        id="int_26b_payroll_remittance",
        transaction_text="Mondelez remitted January statutory deductions to the respective government agencies in cash, combining the employee withholdings with the company's matching contributions: pension $4,000, health insurance $6,500, employment insurance $2,100. Mondelez also remitted employee income tax withholdings of $1,450.",
        user_context=_DEFAULT_CTX,
        # 1 liability decrease (withholdings) + 1 expense (employer portions)
        expected_debit_tuple=(0, 0, 1, 1, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Statutory withholdings payable", "type": "debit", "amount": 7750},
            {"account_name": "Employee benefits expense", "type": "debit", "amount": 6300},
            {"account_name": "Cash", "type": "credit", "amount": 14050},
        ]},
    ),

    # ── Expenses ─────────────────────────────────────────────────────────
    TestCase(
        id="int_13_donation_note",
        transaction_text="Target pledged a donation of $1,000,000 to a humanitarian food aid program in Somalia and issued a 1-month promissory note for the full amount.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Donations expense", "type": "debit", "amount": 1000000},
            {"account_name": "Notes payable", "type": "credit", "amount": 1000000},
        ]},
    ),
    TestCase(
        id="int_21_rd_expense",
        transaction_text="Mondelez purchased raw materials from a supplier for research and development of a new snack product, paying $50,000 by cheque.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Research and development expense", "type": "debit", "amount": 50000},
            {"account_name": "Cash — chequing", "type": "credit", "amount": 50000},
        ]},
    ),
    TestCase(
        id="int_24_advertising",
        transaction_text="Mondelez commissioned a digital marketing campaign for its snack products, paying $22,000 in cash (inclusive of sales tax).",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Advertising expense", "type": "debit", "amount": 22000},
            {"account_name": "Cash", "type": "credit", "amount": 22000},
        ]},
    ),
    TestCase(
        id="int_28_promotional_literature",
        transaction_text="Mondelez purchased 15 titles of promotional literature for $7,000 in cash from a bookstore, to be displayed in the sales department for customer reference.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(0, 0, 1, 0, 0, 0),
        expected_credit_tuple=(0, 0, 0, 1, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Advertising expense", "type": "debit", "amount": 7000},
            {"account_name": "Cash", "type": "credit", "amount": 7000},
        ]},
    ),

    # ── IFRS 16: Leases ──────────────────────────────────────────────────
    TestCase(
        id="int_29_security_deposit_received",
        transaction_text="Mondelez leased a vacant portion of its building to a tenant for a 1-year term at a monthly rent of $10,000 (exclusive of sales tax). Upon signing the lease, Mondelez received a security deposit of $25,000 in cash.",
        user_context=_DEFAULT_CTX,
        expected_debit_tuple=(1, 0, 0, 0, 0, 0),
        expected_credit_tuple=(1, 0, 0, 0, 0, 0),
        expected_entry={"lines": [
            {"account_name": "Cash", "type": "debit", "amount": 25000},
            {"account_name": "Rental deposits received", "type": "credit", "amount": 25000},
        ]},
    ),
]
