# baseline_v3: Stage 6 Failure Analysis

15 failing test cases: 12 entry failures + 3 clarification failures.

## Workflow

For each test case:

1. **Read results** -- compare expected vs stage 6 output
2. **Build Result Table** -- side-by-side comparison with 🟢 (matches expected) / 🔴 (differs from expected)
3. **Build Failure Table (columns: Failure, Evidence, Source Agent, Failure Mode)** -- one row per 🔴. Evidence points to which row in the result table.
4. **Inspect reasoning** -- trace through agent outputs (ambiguity_detector, complexity_detector, debit_classifier, credit_classifier, tax_specialist, decision_maker, entry_drafter) to identify which agent caused each failure and why. Fill in Source Agent and Failure Mode columns.

## Table Definitions

### Result Table

Side-by-side comparison of Expected and Stage 6 outputs. Grouped by: Decision → Debit lines → Credit lines → Structure → Evaluation.

| Column | Description |
|--------|-------------|
| Expected | 🟢 Ground truth from test case definition |
| Stage 6 | 🟢 matches expected, 🔴 differs (strict — exact account name and amount) |
| Note | Brief comparison across the two columns |

### Failure Table

One row per 🔴 in the result table.

| Column | Description |
|--------|-------------|
| Failure | What is wrong: [Wrong/Missing/Extra] [field] [actual] vs [expected] |
| Evidence | Which row in the result table shows this 🔴 |
| Source Agent | Which agent's output introduced this error (from trace inspection) |
| Failure Mode | Why the agent produced the wrong output — its reasoning and where it went wrong |

---

## 1. int_05_bond_issuance_discount

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Cash $2,657,510                       | 🔴 Cash $2,283,105                       | Wrong amount — PV calculation error      |
| **Dr line 2**    | 🟢 Discount on bonds $342,490            | 🔴 Discount on Bonds Payable $716,895    | Wrong amount (follows from PV error)     |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Bonds payable $3,000,000              | 🟢 Bonds Payable $3,000,000              | Match                                    |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (2,0,0,0,0,0)                         | 🟢 (2,0,0,0,0,0)                         | Both correct                             |
| **Credit tuple** | 🟢 (2,0,0,1,0,0)                         | 🟢 (2,0,0,1,0,0)                         | Both correct                             |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | PV amounts wrong                         |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not a tax issue                          |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr amount: Cash $2,283,105 vs expected $2,657,510 | Dr line 1 | entry_drafter | Computed PV using wrong methodology. Expected: PV of principal + PV of annuity at 15% for 3 years = $2,657,510. Got $2,283,105, which is simply $3,000,000 / 1.15^3 (PV of principal only, ignoring interest annuity). The decision_maker noted the calculation was "straightforward" but the entry_drafter omitted the coupon annuity component. |
| Wrong Dr amount: Discount $716,895 vs expected $342,490 | Dr line 2 | entry_drafter | Flows from the PV error above. Discount = Face - Cash = $3,000,000 - $2,283,105 = $716,895 instead of $342,490. |

---

## 2. int_08_share_repurchase_cancel

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Share capital $50,000                  | 🟢 Common Shares $50,000                 | Semantically equivalent                  |
| **Dr line 2**    | 🟢 Retained earnings $10,000             | 🔴 Additional Paid-in Capital $10,000    | Wrong account                            |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Cash $60,000                           | 🟢 Cash $60,000                           | Match                                    |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (0,0,0,0,2,0)                         | 🟢 (0,0,0,0,2,0)                         | Both correct                             |
| **Credit tuple** | 🟢 (0,0,0,1,0,0)                         | 🟢 (0,0,0,1,0,0)                         | Both correct                             |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Wrong equity account for excess          |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not a tax issue                          |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr account: "Additional Paid-in Capital" vs expected "Retained earnings" | Dr line 2 | entry_drafter | The debit_classifier correctly identified 2 equity decreases. The decision_maker approved and noted IFRS (IAS 32) guidance: excess first to contributed surplus, remainder to retained earnings. The entry_drafter chose "Additional Paid-in Capital" (US GAAP term for contributed surplus), but the expected answer uses "Retained earnings." The pipeline assumed APIC was available for this share class, but the ground truth treats the entire excess as coming from retained earnings. |

---

## 3. int_11_land_instalment_discount

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Land $49,173,000                      | 🔴 Land $49,173,240                      | PV rounding (~$240 diff)                 |
| **Dr line 2**    | 🟢 Discount on LT payables $10,827,000   | 🔴 *(missing)*                           | Missing contra-liability line            |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 LT payables $60,000,000               | 🔴 Note Payable $49,173,240              | Wrong account and wrong amount           |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (1,0,0,1,0,0)                         | 🔴 (1,0,0,0,0,0)                         | Missing liability decrease slot          |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                         | 🟢 (1,0,0,0,0,0)                         | Match                                    |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Net method instead of gross              |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not a tax issue                          |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr amount: Land $49,173,240 vs expected $49,173,000 | Dr line 1 | entry_drafter | Used higher-precision annuity factor (4.917324) than expected table factor. Minor rounding difference. |
| Missing Dr Discount on LT payables $10,827,000 | Dr line 2 absent | debit_classifier | Classified only 1 asset increase. Failed to recognize the discount on LT payables as a separate debit line (liability decrease). The decision_maker approved this classification without override. |
| Wrong Cr account: "Note Payable" vs "LT payables" | Cr line 1 | entry_drafter | Used "Note Payable" instead of "Long-term payables." Assumed promissory note when transaction describes instalment payments. |
| Wrong Cr amount: $49,173,240 vs $60,000,000 | Cr line 1 | entry_drafter | Recorded liability at PV (net method) instead of face value (gross method). The expected answer uses gross method: Cr LT payables at face $60M with Dr Discount $10.8M as contra. The pipeline used net method throughout — no agent flagged the gross vs net choice. |

---

## 4. int_12_site_improvements

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 PP&E Site improvements $1,750,000     | 🔴 Land Improvements $4,110,000          | Wrong account, wrong amount (combined)   |
| **Dr line 2**    | 🟢 Land $2,360,000                       | 🔴 *(missing)*                           | Missing line                             |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Cash $1,750,000                       | 🔴 Cash $4,110,000                       | Wrong amount (combined)                  |
| **Cr line 2**    | 🟢 Cash—chequing $2,360,000             | 🔴 *(missing)*                           | Missing line                             |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (2,0,0,0,0,0)                         | 🟢 (2,0,0,0,0,0)                         | Match (but decision_maker overrode to 1) |
| **Credit tuple** | 🟢 (0,0,0,2,0,0)                         | 🟢 (0,0,0,2,0,0)                         | Match (but decision_maker overrode to 1) |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Combined into single lines               |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not a tax issue                          |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr: "Land Improvements" $4,110,000 vs "PP&E Site improvements" $1,750,000 + "Land" $2,360,000 | Dr line 1/2 | decision_maker | The debit_classifier correctly counted 2 asset increases (depreciable infrastructure vs non-depreciable landscaping). The credit_classifier correctly counted 2 asset decreases (cash vs cheque). The decision_maker **overrode both** to 1 each, reasoning that all items are depreciable land improvements and payment method doesn't warrant separate lines. This lost the required separation between site improvements and land. |
| Missing Dr Land $2,360,000 | Dr line 2 | decision_maker | Same override. The expected answer separates landscaping (capitalized to Land, non-depreciable) from infrastructure (PP&E Site improvements, depreciable). The decision_maker collapsed them. |
| Wrong Cr: Cash $4,110,000 vs Cash $1,750,000 + Cash—chequing $2,360,000 | Cr lines | decision_maker | Same override collapsed the two credit lines into one. The expected answer preserves the distinction between cash and chequing accounts. |

---

## 5. int_18_multiple_assets

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 PP&E Office equipment $5,500          | 🔴 Office Furniture $2,000               | Split into two lines                     |
| **Dr line 2**    | 🟢 PP&E Vehicles $250,000               | 🔴 Computer Equipment $3,500             | Extra granularity                        |
| **Dr line 3**    |                                          | 🔴 Vehicles $250,000                     | Extra line (3 vs 2)                      |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Cash $5,500                            | 🟢 Cash $5,500                            | Match                                    |
| **Cr line 2**    | 🟢 Trade payables $250,000               | 🟢 Accounts Payable $250,000             | Synonym OK                               |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (2,0,0,0,0,0)                         | 🔴 (3,0,0,0,0,0)                         | Over-split: 3 vs expected 2             |
| **Credit tuple** | 🟢 (1,0,0,1,0,0)                         | 🟢 (1,0,0,1,0,0)                         | Match                                    |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Office equipment split                   |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not a tax issue                          |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Extra Dr lines: Furniture $2,000 + Computer $3,500 vs combined Office equipment $5,500 | Dr line 1/2/3 | debit_classifier | Counted 3 asset increases, splitting "office desks" and "computers" into separate asset classes based on different depreciation schedules. The expected answer combines them as "PP&E Office equipment" $5,500. No decision_maker was invoked (status=0) to correct this over-split. |

---

## 6. int_24_advertising

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Advertising expense $22,000           | 🔴 Marketing Expense $19,469.03          | Wrong account, wrong amount              |
| **Dr line 2**    |                                          | 🔴 HST Receivable $2,530.97              | Extra tax line                           |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Cash $22,000                           | 🟢 Cash $22,000                           | Match                                    |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (0,0,1,0,0,0)                         | 🔴 (0,0,2,0,0,0)                         | Extra expense slot                       |
| **Credit tuple** | 🟢 (0,0,0,1,0,0)                         | 🟢 (0,0,0,1,0,0)                         | Match                                    |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Tax split out                            |
| **tax_relaxed**  | 🟢 ground truth                           | 🟢 true                                  | Tax-only difference                      |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr account: "Marketing Expense" vs "Advertising expense" | Dr line 1 | entry_drafter | Used "Marketing Expense" instead of "Advertising expense." Both are valid but don't match the expected account name. |
| Wrong Dr amount: $19,469.03 vs $22,000 | Dr line 1 | tax_specialist | The tax_specialist detected "inclusive of sales tax" and back-calculated 13% HST, splitting $22,000 into $19,469.03 base + $2,530.97 tax. The expected answer records the full $22,000 as expense (no tax split). The debit_classifier then counted 2 expenses based on the tax specialist's guidance. |
| Extra Dr HST Receivable $2,530.97 | Dr line 2 | tax_specialist | Tax specialist added a recoverable HST line. The expected answer does not split tax. Since tax_relaxed_match = true, this is a tax-only difference. |

> **Note**: Tax-relaxed = true. Removing HST line and restoring base to $22,000 matches expected. Realistic Canadian treatment.

---

## 7. int_26b_payroll_remittance

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Statutory withholdings payable $7,750  | 🔴 Pension Payable $4,000                | Over-split into 4 lines                 |
| **Dr line 2**    | 🟢 Employee benefits expense $6,300      | 🔴 Health Insurance Payable $6,500       | Wrong: expense missing entirely          |
| **Dr line 3**    |                                          | 🔴 Employment Insurance Payable $2,100   | Extra line                               |
| **Dr line 4**    |                                          | 🔴 Income Tax Withholdings Payable $1,450 | Extra line                              |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Cash $14,050                           | 🟢 Cash $14,050                           | Match                                    |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (0,0,1,1,0,0)                         | 🔴 (0,0,0,4,0,0)                         | Missing expense, over-counted liabilities |
| **Credit tuple** | 🟢 (0,0,0,1,0,0)                         | 🟢 (0,0,0,1,0,0)                         | Match                                    |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Substantive error                        |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not a tax issue                          |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Missing Dr Employee benefits expense $6,300 | Dr line 2 | debit_classifier | Classified all $14,050 as 4 liability decreases with 0 expenses. The transaction involves both employee withholdings ($7,750 liability) and employer matching ($6,300 expense), but the classifier treated the entire remittance as liability settlement only. It said: "The company's matching contributions were already expensed when payroll was recorded." This is correct for employee portions but wrong for the employer's matching amount on the remittance entry — the expected answer shows $6,300 as a new expense line on the remittance. |
| Over-split Dr: 4 liability lines vs 1 consolidated "Statutory withholdings payable" $7,750 | Dr lines 1-4 | debit_classifier | Split payroll liabilities into 4 separate accounts (pension, health, EI, tax). The expected answer consolidates employee withholdings into a single "Statutory withholdings payable" $7,750. Additionally, amounts don't reconcile: pipeline total $14,050 (all liability) vs expected $7,750 liability + $6,300 expense. |

---

## 8. int_28_promotional_literature

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Advertising expense $7,000            | 🔴 Promotional Literature $7,000         | Wrong account (asset vs expense)         |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Cash $7,000                            | 🟢 Cash $7,000                            | Match                                    |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (0,0,1,0,0,0)                         | 🔴 (1,0,0,0,0,0)                         | Asset instead of expense                 |
| **Credit tuple** | 🟢 (0,0,0,1,0,0)                         | 🟢 (0,0,0,1,0,0)                         | Match                                    |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Asset vs expense classification          |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not a tax issue                          |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr account: "Promotional Literature" (asset) vs "Advertising expense" | Dr line 1 | debit_classifier | Classified as 1 asset increase instead of 1 expense increase. Reasoning: "items to be displayed for ongoing customer reference, indicating they are capitalized as assets rather than immediately expensed." The expected treatment is to expense promotional literature as advertising. The classifier over-interpreted "displayed" as indicating future economic benefit, but promotional materials are typically period expenses under IAS 38 (advertising and promotional costs are expensed when incurred). |

---

## 9. int_hard_01b_note_collateralized

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Cash $98,356                           | 🔴 Cash $98,333.33                       | Wrong amount (day-count error)           |
| **Dr line 2**    | 🟢 Interest expense $1,644               | 🔴 Interest Expense $1,666.67            | Wrong amount (follows from day-count)    |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Short-term borrowings $100,000        | 🟢 Bank Loan Payable $100,000            | Semantically equivalent                  |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (1,0,1,0,0,0)                         | 🟢 (1,0,1,0,0,0)                         | Both correct                             |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                         | 🟢 (1,0,0,0,0,0)                         | Both correct                             |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Day-count methodology difference         |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not a tax issue                          |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr amount: Cash $98,333.33 vs expected $98,356 | Dr line 1 | entry_drafter | Used 360-day year ($100,000 x 15% x 40/360 = $1,666.67) instead of 365-day year ($100,000 x 15% x 40/365 = $1,643.84). The decision_maker even wrote the correct formula with /365 but the entry_drafter used /360. |
| Wrong Dr amount: Interest $1,666.67 vs expected $1,644 | Dr line 2 | entry_drafter | Same day-count error. Computed $100,000 x 15% x 40/360 instead of 40/365. |

---

## 10. int_hard_27b_meal_meeting

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Meeting expense $125                  | 🔴 Meals and Entertainment Expense $125  | Wrong account name                       |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Credit card payable $125              | 🟢 Corporate Credit Card Payable $125    | Semantically equivalent                  |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (0,0,1,0,0,0)                         | 🟢 (0,0,1,0,0,0)                         | Both correct                             |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                         | 🟢 (1,0,0,0,0,0)                         | Both correct                             |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Wrong expense classification             |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not a tax issue                          |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr account: "Meals and Entertainment Expense" vs "Meeting expense" | Dr line 1 | entry_drafter | The test case context specifies this is a working meeting among employees (int_hard_27b), which should be classified as "Meeting expense." The entry_drafter used the generic "Meals and Entertainment Expense" instead. The disambiguated context (meeting purpose) was available but the drafter defaulted to a generic meal account rather than the specific meeting expense account. |

---

## 11. int_hard_32a_grocery_entertainment

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Entertainment expense $1,320          | 🔴 Entertainment Expense $1,200          | Wrong amount (tax split out)             |
| **Dr line 2**    |                                          | 🔴 Input Tax Credit Receivable $120      | Extra tax line                           |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Credit card payable $1,320            | 🟢 Corporate Credit Card Payable $1,320  | Semantically equivalent                  |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (0,0,1,0,0,0)                         | 🔴 (1,0,2,0,0,0)                         | Extra asset + extra expense              |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                         | 🟢 (1,0,0,0,0,0)                         | Match                                    |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Tax split out                            |
| **tax_relaxed**  | 🟢 ground truth                           | 🟢 true                                  | Tax-only difference                      |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr amount: Entertainment Expense $1,200 vs expected $1,320 | Dr line 1 | tax_specialist | Tax specialist detected "plus 10% sales tax" and split the amount into $1,200 base + $120 recoverable ITC. The expected answer records the full $1,320 as entertainment expense. Since tax_relaxed_match = true, this is a tax-only difference. |
| Extra Dr Input Tax Credit Receivable $120 | Dr line 2 | tax_specialist | Added recoverable tax line. Not expected by ground truth. Tax-only difference. |

> **Note**: Tax-relaxed = true. Correct account name (Entertainment). Removing tax line and restoring to $1,320 matches expected.

---

## 12. int_hard_32b_grocery_breakroom

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                              | 🟢 APPROVED                              | All agree                                |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 Employee benefits expense $1,320      | 🔴 Office Supplies Expense $1,200        | Wrong account + wrong amount             |
| **Dr line 2**    |                                          | 🔴 Input Tax Credit Receivable $120      | Extra tax line                           |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 Credit card payable $1,320            | 🟢 Corporate Credit Card Payable $1,320  | Semantically equivalent                  |
|                  |                                          |                                          |                                          |
| **Debit tuple**  | 🟢 (0,0,1,0,0,0)                         | 🔴 (1,0,2,0,0,0)                         | Extra asset + wrong expense count        |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                         | 🔴 (2,0,0,0,0,0)                         | Over-counted liability                   |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 ground truth                           | 🔴 false                                 | Wrong account + tax split                |
| **tax_relaxed**  | 🟢 ground truth                           | 🔴 false                                 | Not only tax — account also wrong        |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong Dr account: "Office Supplies Expense" vs "Employee benefits expense" | Dr line 1 | entry_drafter | The disambiguated context specifies this is for employee break room supplies. The expected account is "Employee benefits expense" (treating break room supplies as an employee benefit). The entry_drafter chose "Office Supplies Expense" — a reasonable but incorrect classification. The debit_classifier described these as "Employee refreshments/supplies expense" but the entry_drafter rendered it as "Office Supplies Expense." |
| Wrong Dr amount: $1,200 vs $1,320 | Dr line 1 | tax_specialist | Tax specialist split out 10% sales tax as recoverable ITC ($120). Expected answer records gross $1,320 as expense. |
| Extra Dr Input Tax Credit Receivable $120 | Dr line 2 | tax_specialist | Added recoverable tax line not in expected answer. |
| Wrong credit_tuple: (2,0,0,0,0,0) vs (1,0,0,0,0,0) | Credit tuple | credit_classifier | Counted 2 liability increases (credit card payable + sales tax payable), but the entry_drafter correctly rendered only 1 credit line. The tuple mismatch is a classifier error that did not propagate to the final entry. |

---

## 13. hard_02_investment_classification (Clarification Failure)

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 INCOMPLETE_INFORMATION                | 🔴 APPROVED                              | Wrong — should have asked for clarification |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 *(should not produce entry)*          | 🔴 Investment in Ford $3,000,000         | Entry produced despite ambiguity         |
| **Dr line 2**    |                                          | 🔴 Investment Transaction Fees $100,000  | Entry produced despite ambiguity         |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 *(should not produce entry)*          | 🔴 Cash $3,000,000                       | Entry produced despite ambiguity         |
| **Cr line 2**    |                                          | 🔴 Cash $100,000                         | Entry produced despite ambiguity         |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 INCOMPLETE_INFORMATION                | 🔴 false                                 | Wrong decision                           |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong decision: APPROVED vs expected INCOMPLETE_INFORMATION | Decision | decision_maker | The complexity_detector correctly flagged FVTPL vs FVOCI vs equity method ambiguity at 10% ownership. The ambiguity_detector found no ambiguities. The decision_maker dismissed the complexity flag, reasoning: "At 10% ownership with no stated influence factors, IFRS 9 default treatment is FVTPL." It concluded the system could resolve the ambiguity by convention. However, the ground truth requires asking the user because management intent and significant influence at 10% cannot be determined without clarification. The pipeline failed to surface a clarification question. |

---

## 14. hard_16_rent_treatment (Clarification Failure)

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 INCOMPLETE_INFORMATION                | 🔴 APPROVED                              | Wrong — should have asked for clarification |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 *(should not produce entry)*          | 🔴 Prepaid Rent $24,000                  | Entry produced despite ambiguity         |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 *(should not produce entry)*          | 🔴 Cash $24,000                           | Entry produced despite ambiguity         |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 INCOMPLETE_INFORMATION                | 🔴 false                                 | Wrong decision                           |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong decision: APPROVED vs expected INCOMPLETE_INFORMATION | Decision | decision_maker | The ambiguity_detector flagged timing uncertainty (prepaid vs arrears). The disambiguator produced a question: "Does the $24,000 cover upcoming or past 12 months?" The decision_maker overrode the ambiguity, reasoning that accounting convention resolves it as prepayment. However, the ground truth ambiguity is not about timing — it is about whether a 12-month prepayment should be recorded as a prepaid asset or expensed immediately under the IFRS 16 short-term lease exemption. The decision_maker missed the core ambiguity entirely, and the ambiguity_detector asked the wrong question. |

---

## 15. hard_27_meal_purpose (Clarification Failure)

### Result Table

|                  | Expected                                 | Stage 6                                  | Note                                     |
|------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 INCOMPLETE_INFORMATION                | 🔴 APPROVED                              | Wrong — should have asked for clarification |
|                  |                                          |                                          |                                          |
| **Dr line 1**    | 🟢 *(should not produce entry)*          | 🔴 Meals and Entertainment Expense $125  | Entry produced despite ambiguity         |
|                  |                                          |                                          |                                          |
| **Cr line 1**    | 🟢 *(should not produce entry)*          | 🔴 Corporate Credit Card Payable $125    | Entry produced despite ambiguity         |
|                  |                                          |                                          |                                          |
| **match**        | 🟢 INCOMPLETE_INFORMATION                | 🔴 false                                 | Wrong decision                           |

### Failure Table

| Failure | Evidence | Source Agent | Failure Mode |
|---------|----------|-------------|--------------|
| Wrong decision: APPROVED vs expected INCOMPLETE_INFORMATION | Decision | decision_maker | The ambiguity_detector correctly identified meal purpose ambiguity with 5 options (travel, client entertainment, team meeting, employee benefit, owner personal). The disambiguator produced a question. The decision_maker dismissed the ambiguity, arguing: "the entry structure is identical regardless — debit expense, credit liability — only the sub-account name differs." It concluded the system could use a generic "Meals and Entertainment" account. However, the ground truth requires asking for clarification because the meal purpose materially affects the expense classification (meeting vs entertainment vs employee benefits vs overhead). |

---

## Failure Patterns

Grouped by source agent, deduplicated across test cases.

### decision_maker (5 unique)

1. Dismissed valid investment classification ambiguity — assumed FVTPL default when management intent needed (hard_02)
2. Dismissed valid rent treatment ambiguity — resolved as prepayment when IFRS 16 exemption is the real question (hard_16)
3. Dismissed valid meal purpose ambiguity — argued "structure identical" when sub-account differs materially (hard_27)
4. Overrode correct classifier counts — collapsed 2 debit asset lines into 1, losing land vs site improvements distinction (int_12)
5. Overrode correct classifier counts — collapsed 2 credit lines into 1, losing cash vs chequing distinction (int_12)

### entry_drafter (5 unique)

1. PV calculation error — computed PV of principal only, ignoring coupon annuity component (int_05)
2. Wrong equity account — used "Additional Paid-in Capital" (APIC) instead of "Retained earnings" for share repurchase excess (int_08)
3. Day-count error — used 360-day year instead of 365-day year for interest computation (int_hard_01b)
4. Wrong account name — used generic "Meals and Entertainment" instead of specific "Meeting expense" (int_hard_27b)
5. Wrong account name — used "Office Supplies Expense" instead of "Employee benefits expense" for breakroom supplies (int_hard_32b)

### tax_specialist (3 unique)

1. Extracted HST from "inclusive of sales tax" amount — split $22,000 into base + tax (int_24)
2. Split "plus 10% sales tax" into base + recoverable ITC for entertainment (int_hard_32a)
3. Split "plus 10% sales tax" into base + recoverable ITC for breakroom supplies (int_hard_32b)

### debit_classifier (3 unique)

1. Failed to recognize discount on LT payables as separate debit line — missed contra-liability (int_11)
2. Over-split office equipment into furniture + computers — counted 3 assets instead of 2 (int_18)
3. Missed employer matching expense on remittance — treated entire amount as 4 liability decreases (int_26b)

### credit_classifier (1 unique)

1. Over-counted liabilities — counted credit card payable + sales tax payable as 2 instead of 1 (int_hard_32b)

---

## Summary

### Entry Failures by Root Cause

| Failure Mode | Count | Test Cases |
|--------------|-------|------------|
| **Computation error** (PV, day-count) | 3 | int_05, int_11 (amount), int_hard_01b |
| **Tax split** (tax-only difference) | 2 | int_24, int_hard_32a |
| **Account name** (wrong classification) | 4 | int_08, int_28, int_hard_27b, int_hard_32b |
| **Structural** (net vs gross, over-split, under-split) | 3 | int_11 (structure), int_12, int_18 |
| **Missing expense line** | 1 | int_26b |

### Clarification Failures by Root Cause

| Failure Mode | Count | Test Cases |
|--------------|-------|------------|
| **decision_maker override** — dismissed valid ambiguity | 3 | hard_02, hard_16, hard_27 |

### Source Agent Frequency

| Agent | Failures Caused |
|-------|----------------|
| decision_maker | 5 (3 clarification overrides + int_12 structural override + 1 passthrough) |
| entry_drafter | 5 (int_05 PV, int_08 account, int_hard_01b day-count, int_hard_27b account, int_hard_32b account) |
| tax_specialist | 3 (int_24, int_hard_32a, int_hard_32b tax splits) |
| debit_classifier | 3 (int_11 missing discount, int_18 over-split, int_26b missing expense) |
| credit_classifier | 1 (int_hard_32b over-counted liability) |
