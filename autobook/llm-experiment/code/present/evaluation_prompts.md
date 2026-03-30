# Post-Hoc Evaluation Prompts

Evaluate experiment results. Write evaluation JSON files into each variant's result directory.

---

## 1. Entry Accuracy Evaluation

For each variant directory in `results/<experiment>/`, read every `*.json` file starting with `basic_*` or `int_*` (56 non-ambiguous test cases). Compare the `journal_entry` field against the expected entry. Write one `entry_accuracy.json` per variant directory.

### Scoring

For each test case, produce two scores:

1. **match** — Does the actual journal entry match the expected entry? Use your accounting judgment to determine if accounts are semantically equivalent. Amounts must be exact (allow minor rounding on present value calculations).

2. **tax_relaxed_match** — Same comparison, but if the only differences are tax-related (added/removed tax lines of any kind — HST, GST, VAT, sales tax — or amounts adjusted for tax), would an accountant consider the actual entry to be a realistic and correct treatment?

### Expected Entries

#### Basic (15 cases)

**basic_01_inventory_cash**: Dr Inventories $100 / Cr Cash $100
**basic_02_inventory_on_account**: Dr Inventories $300 / Cr Trade payables $300
**basic_03_issue_stock_with_apic**: Dr Cash $180 / Cr Share capital—Common $100 / Cr APIC $80
**basic_04_sell_inventory**: Dr Cash $500 / Dr COGS $300 / Cr Revenue $500 / Cr Inventories $300
**basic_05_pay_accounts_payable**: Dr Trade payables $50 / Cr Cash $50
**basic_06_refinance_loan**: Dr Notes payable $100 / Cr Notes payable $100
**basic_07_loan_to_equity**: Dr Notes payable $200 / Cr Share capital—Common $200
**basic_08_deliver_service_against_deposit**: Dr Contract liabilities $100 / Cr Revenue $100
**basic_09_repurchase_stock**: Dr Treasury shares $200 / Cr Cash $200
**basic_10_declare_dividend**: Dr Retained earnings $500,000 / Cr Dividends payable $500,000
**basic_11_convert_preferred_to_common**: Dr Share capital—Preferred $100 / Cr Share capital—Common $100
**basic_12_pay_salaries**: Dr Salaries expense $100 / Cr Cash $100
**basic_13_accrue_utility**: Dr Utilities expense $50 / Cr Accrued liabilities $50
**basic_14_casualty_loss**: Dr Casualty loss $2,000 / Cr Inventories $2,000
**basic_15_no_entry**: null (no journal entry)

#### Intermediate (28 cases)

**int_03_machinery_purchase**: Dr PP&E Machinery $800,000 / Cr Trade payables $700,000 / Cr Cash $100,000
**int_04_major_overhaul**: Dr PP&E Machinery $200,000 / Cr Cash $200,000
**int_05_bond_issuance_discount**: Dr Cash $2,657,510 / Dr Discount on bonds payable $342,490 / Cr Bonds payable $3,000,000
**int_06_warranty_provision**: Dr Warranty expense $900,000 / Cr Provision for warranties $900,000
**int_07_decommissioning_provision**: Dr PP&E Marine structures $5,950,000 / Cr Trade payables $4,000,000 / Cr Decommissioning provision $1,950,000
**int_08_share_repurchase_cancel**: Dr Share capital $50,000 / Dr Retained earnings $10,000 / Cr Cash $60,000
**int_09_merchandise_with_costs**: Dr Inventories $1,150,000 / Dr Warehousing expense $20,000 / Dr Distribution costs $50,000 / Cr Trade payables $1,000,000 / Cr Cash $220,000
**int_10_prepayment**: Dr Prepayments $1,000,000 / Cr Cash $1,000,000
**int_11_land_instalment_discount**: Dr Land $49,173,000 / Dr Discount on long-term payables $10,827,000 / Cr Long-term payables $60,000,000
**int_12_site_improvements**: Dr PP&E Site improvements $1,750,000 / Dr Land $2,360,000 / Cr Cash $1,750,000 / Cr Cash—chequing $2,360,000
**int_13_donation_note**: Dr Donations expense $1,000,000 / Cr Notes payable $1,000,000
**int_14_vehicle_mixed_payment**: Dr PP&E Vehicles $40,000 / Cr Cash $20,000 / Cr Notes payable $20,000
**int_15_bank_loan**: Dr Cash $200,000 / Cr Long-term borrowings $200,000
**int_17_customer_deposit**: Dr Cash—chequing $5,000 / Cr Contract liabilities $5,000
**int_18_multiple_assets**: Dr PP&E Office equipment $5,500 / Dr PP&E Vehicles $250,000 / Cr Cash $5,500 / Cr Trade payables $250,000
**int_19_service_revenue_cash**: Dr Cash $25,500 / Cr Revenue—Service revenue $25,500
**int_20_service_revenue_credit**: Dr Trade receivables $31,500 / Cr Revenue—Service revenue $31,500
**int_21_rd_expense**: Dr R&D expense $50,000 / Cr Cash—chequing $50,000
**int_22_compound_sale_with_tax**: Dr Cash—chequing $45,900 / Dr Trade receivables $30,000 / Dr COGS $55,500 / Cr Revenue $69,000 / Cr Sales tax payable $6,900 / Cr Inventories $55,500
**int_23_split_electricity**: Dr WIP Manufacturing overhead $15,000 / Dr Utilities expense $5,500 / Cr Credit card payable $20,500
**int_24_advertising**: Dr Advertising expense $22,000 / Cr Cash $22,000
**int_25_building_purchase_allocation**: Dr Land $6,000,000 / Dr Building $3,000,000 / Dr VAT receivable $300,000 / Cr Cash—chequing $4,800,000 / Cr Other payables $4,500,000
**int_26a_payroll_recognition**: Dr WIP Direct labour $25,000 / Dr Salaries expense $20,000 / Cr Statutory withholdings payable $7,750 / Cr Cash—chequing $37,250
**int_26b_payroll_remittance**: Dr Statutory withholdings payable $7,750 / Dr Employee benefits expense $6,300 / Cr Cash $14,050
**int_28_promotional_literature**: Dr Advertising expense $7,000 / Cr Cash $7,000
**int_29_security_deposit_received**: Dr Cash $25,000 / Cr Rental deposits received $25,000
**int_30_short_term_loan_advance**: Dr Short-term loans receivable $2,000,000 / Cr Cash—chequing $2,000,000
**int_31_vehicle_nonrecoverable_tax**: Dr PP&E Vehicles $52,800 / Cr Other payables $52,800

#### Intermediate from Hard (13 cases)

**int_hard_01a_note_derecognition**: Dr Cash $98,356 / Dr Loss on derecognition $1,644 / Cr Trade receivables $100,000
**int_hard_01b_note_collateralized**: Dr Cash $98,356 / Dr Interest expense $1,644 / Cr Short-term borrowings $100,000
**int_hard_02a_investment_fvtpl**: Dr Financial assets at FVTPL $3,000,000 / Dr Investment transaction costs $100,000 / Cr Cash $3,100,000
**int_hard_02b_investment_fvoci**: Dr Financial assets at FVOCI $3,100,000 / Cr Cash $3,100,000
**int_hard_02c_investment_equity_method**: Dr Investment in associate $3,100,000 / Cr Cash $3,100,000
**int_hard_27a_meal_overtime**: Dr Employee benefits expense $125 / Cr Credit card payable $125
**int_hard_27b_meal_meeting**: Dr Meeting expense $125 / Cr Credit card payable $125
**int_hard_27c_meal_entertainment**: Dr Entertainment expense $125 / Cr Credit card payable $125
**int_hard_27d_meal_factory**: Dr WIP Manufacturing overhead $125 / Cr Credit card payable $125
**int_hard_32a_grocery_entertainment**: Dr Entertainment expense $1,320 / Cr Credit card payable $1,320
**int_hard_32b_grocery_breakroom**: Dr Employee benefits expense $1,320 / Cr Credit card payable $1,320
**int_hard_16a_rent_prepaid**: Dr Prepaid rent $24,000 / Cr Cash—chequing $24,000
**int_hard_16b_rent_expense**: Dr Rent expense $24,000 / Cr Cash—chequing $24,000

### Output

Write one file per variant: `results/<experiment>/<variant>/entry_accuracy.json`

```json
{
  "evaluator": "claude",
  "evaluated_at": "<ISO timestamp>",
  "prompt_version": "v3",
  "results": {
    "test_case_id": {
      "match": true,
      "tax_relaxed_match": true,
      "reason": "brief explanation"
    }
  }
}
```

---

## 2. Clarification Relevance Evaluation

For each variant directory, read the 5 files starting with `hard_*`. Evaluate whether the pipeline correctly identified the ambiguity and asked a useful clarification question. Write one `clarification_relevance.json` per variant directory.

### Expected Ambiguities

**hard_01_note_discounting** — Derecognition (sale of receivable) vs Collateralized borrowing (loan secured by receivable)
**hard_02_investment_classification** — FVTPL (short-term trading) vs FVOCI (long-term strategic) vs Equity method (significant influence)
**hard_27_meal_purpose** — Overtime meal vs Working meeting vs Client entertainment vs Factory staff meal (production overhead)
**hard_32_grocery_purpose** — Client entertainment vs Employee break room supplies
**hard_16_rent_treatment** — Prepaid asset vs Immediate expense (short-term lease exemption)

### Scoring

**relevant = true** when ALL hold:
1. `final_decision` = "INCOMPLETE_INFORMATION"
2. At least one clarification question was produced
3. The question distinguishes between the listed interpretations
4. The question is about business facts, not accounting treatment

**relevant = false** otherwise.

### Output

Write one file per variant: `results/<experiment>/<variant>/clarification_relevance.json`

```json
{
  "evaluator": "claude",
  "evaluated_at": "<ISO timestamp>",
  "prompt_version": "v1",
  "results": {
    "test_case_id": {
      "actual_decision": "...",
      "actual_questions": ["..."],
      "expected_cases": ["..."],
      "relevant": true,
      "reason": "brief explanation"
    }
  }
}
```

---

## Workflow

1. `./run_experiment.sh` — runs pipeline, saves result JSONs
2. Evaluate using this prompt — write `entry_accuracy.json` + `clarification_relevance.json` per variant
3. `./run_analysis.sh` — merges evaluation files, computes metrics
4. `./run_present.sh` — generates report
