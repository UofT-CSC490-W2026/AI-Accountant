# with_disambiguation: Stage 2 vs Stage 3 Failure Analysis

Union of all entry failures across stage 2 and stage 3 (11 total: 10 entry + 1 clarification).

## Workflow

For each test case:

1. **Read results** — compare expected vs stage 2 vs stage 3 outputs
2. **Build Result Table** — side-by-side comparison with 🟢 (matches expected) / 🔴 (differs from expected)
3. **Build Failure Table (columns: Stage, Failure, Evidence)** — one row per 🔴. If both stages share the same 🔴, Stage = "Both". Evidence points to which row in the result table.
4. **Inspect Stage 2 reasoning** — run `python3 code/analysis/trace.py` on stage 2 result. For each Stage 2 / Both failure, trace through the agent outputs to identify which agent caused it and why. Fill in Source Agent and Failure Mode columns.
5. **Inspect Stage 3 reasoning** — same for stage 3. Fill in Source Agent and Failure Mode for Stage 3 / Both failures.
6. **Split "Both" rows if needed** — if the source agent or failure mode differs between stages for the same failure, split into two rows (one per stage).

## Table Definitions

### Result Table

Side-by-side comparison of Expected, Stage 2, and Stage 3 outputs. Grouped by: Decision → Debit lines → Credit lines → Structure → Evaluation.

| Column | Description |
|--------|-------------|
| Expected | 🟢 Ground truth from test case definition |
| Stage 2 / Stage 3 | 🟢 matches expected, 🔴 differs (strict — exact account name and amount) |
| Note | Brief comparison across the three columns |

### Failure Table

One row per 🔴 in the result table.

| Column | Description |
|--------|-------------|
| Stage | "Both", "Stage 2", or "Stage 3" — which stage(s) this failure appears in |
| Failure | What is wrong: [Wrong/Missing/Extra] [field] [actual] vs [expected] |
| Evidence | Which row in the result table shows this 🔴 |
| Source Agent | Which agent's output introduced this error (from trace inspection) |
| Failure Mode | Why the agent produced the wrong output — its reasoning and where it went wrong |

---

## 1. int_11_land_instalment_discount

### Result Table

|                  | Expected                                      | Stage 2                            | Stage 3                            | Note                                          |
|------------------|-----------------------------------------------|------------------------------------|------------------------------------|-----------------------------------------------|
| **Decision**     | 🟢 APPROVED                                   | 🟢 APPROVED                       | 🟢 APPROVED                       | All agree                                     |
|                  |                                               |                                    |                                    |                                               |
| **Dr line 1**    | 🟢 Land $49,173,000                           | 🔴 Land $49,173,240               | 🔴 Land $49,173,200               | PV rounding (~$200 diff)                      |
| **Dr line 2**    | 🟢 Discount on LT payables $10,827,000        | 🔴 *(missing)*                    | 🔴 *(missing)*                    | Both omit contra-liability                    |
|                  |                                               |                                    |                                    |                                               |
| **Cr line 1**    | 🟢 LT payables $60,000,000                    | 🔴 Note Payable $49,173,240       | 🔴 Note Payable $49,173,200       | PV instead of face value                      |
|                  |                                               |                                    |                                    |                                               |
| **Debit tuple**  | 🟢 (1,0,0,1,0,0)                             | 🔴 (1,0,0,0,0,0)                 | 🔴 (2,0,0,0,0,0)                 | S2 misses discount; S3 counts 2 but doesn't materialize |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                             | 🔴 (1,0,0,1,0,0)                 | 🟢 (1,0,0,0,0,0)                 | S3 correct; S2 hallucinated asset decrease    |
|                  |                                               |                                    |                                    |                                               |
| **match**        | 🟢 ground truth                               | 🔴 false                          | 🔴 false                          | Both use net method                           |
| **tax_relaxed**  | 🟢 ground truth                               | 🔴 false                          | 🔴 false                          | Not a tax issue                               |


### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Wrong Dr amount: ~$49.17M vs expected $49,173,000 | Dr line 1 | Entry builder | Used higher precision annuity factor than expected table |
| Stage 2 | Missing Dr Discount on LT payables $10,827,000 | Dr line 2 absent | Debit classifier | Knew discount exists but placed it on credit side: "financing component handled on the credit side" |
| Stage 3 | Missing Dr Discount on LT payables $10,827,000 | Dr line 2 absent | Entry builder | Received structure (2,0,0,0,0,0) indicating 2 debit lines. Acknowledged "two asset increases" in rationale but only produced 1 line. Ignored its own structure. |
| Both | Wrong Cr account: "Note Payable" vs "Long-term payables" | Cr line 1 account | Entry builder | Assumed promissory note when transaction describes instalment payments |
| Both | Wrong Cr amount: ~$49.2M vs $60,000,000 | Cr line 1 amount | Entry builder | Recorded liability at PV instead of face value |
| Stage 2 | Wrong debit structure: (1,0,0,0,0,0) vs (1,0,0,1,0,0) | Debit structure | Debit classifier | Excluded discount from debit: "only the asset acquisition is debited here" |
| Stage 2 | Wrong credit structure: (1,0,0,1,0,0) vs (1,0,0,0,0,0) | Credit structure | Credit classifier | Assumed first instalment paid at acquisition — payments start at year end |
| Stage 3 | Wrong debit structure: (2,0,0,0,0,0) vs (1,0,0,1,0,0) | Debit structure | Debit classifier | Recognized discount on debit side but classified as asset increase (slot a) instead of liability decrease (slot d). Said "contra-liability, which behaves as an asset increase." |


---

## 2. int_12_site_improvements

|                  | Expected                                    | Stage 2                            | Stage 3                            | Note                                          |
|------------------|---------------------------------------------|------------------------------------|------------------------------------|-----------------------------------------------|
| **Decision**     | 🟢 APPROVED                                 | 🔴 INCOMPLETE_INFORMATION         | 🟢 APPROVED                       | S2 refused; S3 built entry                    |
|                  |                                             |                                    |                                    |                                               |
| **Dr line 1**    | 🟢 PP&E Site improvements $1,750,000        | 🔴 *(no entry)*                   | 🔴 Land Improvements $1,750,000   | S3 wrong account name                         |
| **Dr line 2**    | 🟢 Land $2,360,000                          | 🔴 *(no entry)*                   | 🔴 Land Improvements $2,360,000   | Should be "Land" not "Land Improvements"      |
|                  |                                             |                                    |                                    |                                               |
| **Cr line 1**    | 🟢 Cash $1,750,000                          | 🔴 *(no entry)*                   | 🟢 Cash $1,750,000                | S3 correct                                    |
| **Cr line 2**    | 🟢 Cash—chequing $2,360,000                | 🔴 *(no entry)*                   | 🔴 Cash $2,360,000                | S3 wrong account (Cash vs Cash—chequing)      |
|                  |                                             |                                    |                                    |                                               |
| **Debit tuple**  | 🟢 (2,0,0,0,0,0)                           | 🟢 (2,0,0,0,0,0)                 | 🟢 (2,0,0,0,0,0)                 | Both correct                                  |
| **Credit tuple** | 🟢 (0,0,0,2,0,0)                           | 🟢 (0,0,0,2,0,0)                 | 🟢 (0,0,0,2,0,0)                 | Both correct                                  |
|                  |                                             |                                    |                                    |                                               |
| **match**        |                                             | 🔴 false                          | 🔴 false                          | S2: no entry; S3: wrong account names         |
| **tax_relaxed**  |                                             | 🔴 false                          | 🔴 false                          | Not a tax issue                               |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Stage 2 | Wrong decision: INCOMPLETE_INFORMATION vs APPROVED | Decision | Entry builder | Disambiguator flagged unresolved ambiguity. Entry builder set action="incomplete" — refused to build. |
| Stage 2 | Missing all entry lines | Dr/Cr lines absent | Entry builder | Consequence of INCOMPLETE_INFORMATION decision — no entry produced |
| Stage 3 | Wrong Dr line 1 account: "Land Improvements" vs "PP&E Site improvements" | Dr line 1 | Entry builder | Classified fencing/walkways as "Land Improvements" instead of "Site improvements." Disambiguator response action="proceed" citing IAS 16 component accounting. |
| Stage 3 | Wrong Dr line 2 account: "Land Improvements" vs "Land" | Dr line 2 | Entry builder | Classified permanent landscaping as "Land Improvements" (depreciable) instead of "Land" (non-depreciable). Rationale: "Both are depreciable land improvements with finite useful lives." |
| Stage 3 | Wrong Cr line 2 account: "Cash" vs "Cash—chequing" | Cr line 2 | Entry builder | Used generic "Cash" when transaction says "paid by cheque" |

---

## 3. int_18_multiple_assets

|                  | Expected                              | Stage 2                            | Stage 3                            | Note                                          |
|------------------|---------------------------------------|------------------------------------|------------------------------------|-----------------------------------------------|
| **Decision**     | 🟢 APPROVED                           | 🟢 APPROVED                       | 🟢 APPROVED                       | All agree                                     |
|                  |                                       |                                    |                                    |                                               |
| **Dr line 1**    | 🟢 PP&E Office equipment $5,500       | 🔴 Office Furniture $2,000        | 🔴 Furniture and Fixtures $2,000  | Both over-split                               |
| **Dr line 2**    | 🟢 PP&E Vehicles $250,000             | 🔴 Computer Equipment $3,500      | 🔴 Computer Equipment $3,500      | Extra line not in expected                    |
| **Dr line 3**    |                                       | 🔴 Vehicles $250,000              | 🔴 Vehicles $250,000              | Vehicle correct but 3 lines instead of 2      |
|                  |                                       |                                    |                                    |                                               |
| **Cr line 1**    | 🟢 Cash $5,500                        | 🟢 Cash $5,500                    | 🟢 Cash $5,500                    | Match                                         |
| **Cr line 2**    | 🟢 Trade payables $250,000            | 🟢 Accounts Payable $250,000      | 🟢 Accounts Payable $250,000      | Synonym OK                                    |
|                  |                                       |                                    |                                    |                                               |
| **Debit tuple**  | 🟢 (2,0,0,0,0,0)                     | 🔴 (3,0,0,0,0,0)                 | 🔴 (3,0,0,0,0,0)                 | 3 assets instead of 2                         |
| **Credit tuple** | 🟢 (1,0,0,1,0,0)                     | 🔴 (1,0,0,2,0,0)                 | 🔴 (1,0,0,2,0,0)                 | 2 asset decreases instead of 1                |
|                  |                                       |                                    |                                    |                                               |
| **match**        | 🟢 ground truth                       | 🔴 false                          | 🔴 false                          | Over-split office assets                      |
| **tax_relaxed**  | 🟢 ground truth                       | 🔴 false                          | 🔴 false                          | Not a tax issue                               |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Wrong Dr: 3 lines ($2K + $3.5K + $250K) vs expected 2 lines ($5.5K + $250K) | Dr lines 1-3 | Debit classifier | Counted "three distinct asset purchases" with "different useful lives and depreciation schedules." Didn't combine desks + computers into office equipment. |
| Both | Wrong debit structure: (3,0,0,0,0,0) vs (2,0,0,0,0,0) | Debit structure | Debit classifier | Same — 3 asset increases instead of 2 |
| Both | Wrong credit structure: (1,0,0,2,0,0) vs (1,0,0,1,0,0) | Credit structure | Credit classifier | Counted 2 asset decreases (cash for desks + cash for computers) instead of 1 combined cash payment |

---

## 4. int_23_split_electricity

|                  | Expected                                    | Stage 2                            | Stage 3                            | Note                                          |
|------------------|---------------------------------------------|------------------------------------|------------------------------------|-----------------------------------------------|
| **Decision**     | 🟢 APPROVED                                 | 🟢 APPROVED                       | 🟢 APPROVED                       | All agree                                     |
|                  |                                             |                                    |                                    |                                               |
| **Dr line 1**    | 🟢 WIP Manufacturing overhead $15,000       | 🔴 Factory Overhead $15,000       | 🔴 Factory Overhead $15,000       | Same output both stages                       |
| **Dr line 2**    | 🟢 Utilities expense $5,500                 | 🟢 Utilities Expense $5,500       | 🟢 Utilities Expense $5,500       | Match                                         |
|                  |                                             |                                    |                                    |                                               |
| **Cr line 1**    | 🟢 Credit card payable $20,500              | 🟢 Credit Card Payable $20,500    | 🟢 Credit Card Payable $20,500    | Match                                         |
|                  |                                             |                                    |                                    |                                               |
| **Debit tuple**  | 🟢 (1,0,1,0,0,0)                           | 🔴 (0,0,2,0,0,0)                 | 🔴 (0,0,2,0,0,0)                 | Factory overhead as expense not asset          |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                           | 🟢 (1,0,0,0,0,0)                 | 🟢 (1,0,0,0,0,0)                 | Both correct                                  |
|                  |                                             |                                    |                                    |                                               |
| **match**        | 🟢 ground truth                             | 🔴 false                          | 🟢 **true**                       | **Evaluator disagreement** — identical output  |
| **tax_relaxed**  | 🟢 ground truth                             | 🔴 false                          | 🟢 **true**                       | S2 rejected "Factory Overhead"; S3 accepted    |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Wrong Dr line 1 account: "Factory Overhead" vs "WIP Manufacturing overhead" | Dr line 1 | Debit classifier → Entry builder | Debit classifier: "Factory electricity = manufacturing overhead expense increase." Classified as expense (slot c) instead of asset (slot a). Entry builder followed with "Factory Overhead" account name. |
| Both | Wrong debit structure: (0,0,2,0,0,0) vs (1,0,1,0,0,0) | Debit structure | Debit classifier | Factory electricity in slot c (expense) instead of slot a (asset/WIP). "Both are expense increases." |

> **Note**: Evaluator disagreement — S2 evaluator marked match=false, S3 evaluator marked match=true. Pipeline output identical. The account name "Factory Overhead" is debatable as synonym for "WIP Manufacturing overhead."

---

## 5. int_24_advertising

|                  | Expected                            | Stage 2                            | Stage 3                            | Note                                          |
|------------------|-------------------------------------|------------------------------------|------------------------------------|-----------------------------------------------|
| **Decision**     | 🟢 APPROVED                         | 🟢 APPROVED                       | 🟢 APPROVED                       | All agree                                     |
|                  |                                     |                                    |                                    |                                               |
| **Dr line 1**    | 🟢 Advertising expense $22,000      | 🔴 Marketing Expense $19,469.03   | 🔴 Marketing Expense $19,469.03   | Base reduced by HST extraction                |
| **Dr line 2**    |                                     | 🔴 HST Receivable $2,530.97       | 🔴 HST Receivable $2,530.97       | Extra tax line                                |
|                  |                                     |                                    |                                    |                                               |
| **Cr line 1**    | 🟢 Cash $22,000                     | 🟢 Cash $22,000                   | 🟢 Cash $22,000                   | Match                                         |
|                  |                                     |                                    |                                    |                                               |
| **Debit tuple**  | 🟢 (0,0,1,0,0,0)                   | 🟢 (0,0,1,0,0,0)                 | 🟢 (0,0,1,0,0,0)                 | Both correct                                  |
| **Credit tuple** | 🟢 (0,0,0,1,0,0)                   | 🟢 (0,0,0,1,0,0)                 | 🟢 (0,0,0,1,0,0)                 | Both correct                                  |
|                  |                                     |                                    |                                    |                                               |
| **match**        | 🟢 ground truth                     | 🔴 false                          | 🔴 false                          | HST extraction from "inclusive" amount         |
| **tax_relaxed**  | 🟢 ground truth                     | 🟢 true                           | 🟢 true                           | Removing HST restores expected entry           |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Wrong Dr line 1 account: "Marketing Expense" vs "Advertising expense" | Dr line 1 | Entry builder | Used "Marketing Expense" instead of "Advertising expense." Minor naming difference. |
| Both | Wrong Dr line 1 amount: $19,469.03 vs $22,000 | Dr line 1 | Entry builder | Extracted 13% HST from "inclusive of sales tax" amount: $22,000 / 1.13 = $19,469.03. Disambiguator resolved: "Ontario — HST at 13% applies." |
| Both | Extra Dr line: HST Receivable $2,530.97 | Dr line 2 | Entry builder | Added HST Receivable for recoverable input tax credit. Not in expected. |

> **Note**: Tax-relaxed = true. Removing HST line and restoring base to $22,000 matches expected. Realistic Canadian treatment.

---

## 6. int_26a_payroll_recognition

|                  | Expected                                      | Stage 2                              | Stage 3                              | Note                                  |
|------------------|-----------------------------------------------|--------------------------------------|--------------------------------------|---------------------------------------|
| **Decision**     | 🟢 APPROVED                                   | 🟢 APPROVED                         | 🟢 APPROVED                         | All agree                             |
|                  |                                               |                                      |                                      |                                       |
| **Dr line 1**    | 🟢 WIP Direct labour $25,000                  | 🔴 Work-in-Process Inventory $25,000 | 🔴 Work-in-Process Inventory $25,000 | Different account (WIP Direct labour vs WIP Inventory) |
| **Dr line 2**    | 🟢 Salaries expense $20,000                   | 🟢 Salaries Expense $20,000         | 🟢 Salaries Expense $20,000         | Match                                 |
|                  |                                               |                                      |                                      |                                       |
| **Cr line 1**    | 🟢 Statutory withholdings payable $7,750       | 🔴 Pension Payable $2,000           | 🔴 Pension Payable $2,000           | Split into 4 lines                    |
| **Cr line 2**    | 🟢 Cash—chequing $37,250                     | 🔴 Health Insurance Payable $3,250   | 🔴 Health Insurance Payable $3,250   |                                       |
| **Cr line 3**    |                                               | 🔴 EI Payable $1,050                | 🔴 EI Payable $1,050                |                                       |
| **Cr line 4**    |                                               | 🔴 Income Tax Payable $1,450        | 🔴 Income Tax Payable $1,450        |                                       |
| **Cr line 5**    |                                               | 🔴 Cash $37,250                     | 🔴 Cash $37,250                     | Expected Cash—chequing, got Cash      |
|                  |                                               |                                      |                                      |                                       |
| **Debit tuple**  | 🟢 (1,0,1,0,0,0)                             | 🔴 (0,0,2,0,0,0)                   | 🔴 (0,0,2,0,0,0)                   | WIP classified as expense not asset   |
| **Credit tuple** | 🟢 (1,0,0,1,0,0)                             | 🔴 (4,0,0,1,0,0)                   | 🔴 (4,0,0,1,0,0)                   | 4 liabilities instead of 1            |
|                  |                                               |                                      |                                      |                                       |
| **match**        | 🟢 ground truth                               | 🔴 false                            | 🔴 false                            | Over-split withholdings               |
| **tax_relaxed**  | 🟢 ground truth                               | 🔴 false                            | 🔴 false                            | Not a tax issue                       |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Wrong Dr line 1 account: "Work-in-Process Inventory" vs "WIP Direct labour" | Dr line 1 | Entry builder | Used generic WIP account instead of specific "Direct labour" sub-account. Disambiguator flagged wage allocation; entry builder proceeded citing IAS 2. |
| Both | Wrong Cr: 4 liability lines vs expected 1 consolidated ($7,750) | Cr lines 1-4 | Credit classifier | "4 liability increases: pension, health, EI, income tax." Counted each statutory deduction as separate payable instead of 1 consolidated "Statutory withholdings payable." |
| Both | Wrong Cr line 5 account: "Cash" vs "Cash—chequing" | Cr line 5 | Entry builder | Used generic "Cash" when transaction says "transferred from chequing account" |
| Both | Wrong debit structure: (0,0,2,0,0,0) vs (1,0,1,0,0,0) | Debit structure | Debit classifier | "Production worker wages = expense increase." Classified WIP as expense (slot c=2) instead of 1 asset + 1 expense (a=1, c=1). |
| Both | Wrong credit structure: (4,0,0,1,0,0) vs (1,0,0,1,0,0) | Credit structure | Credit classifier | 4 liability increases instead of 1 consolidated |

---

## 7. int_26b_payroll_remittance

|                  | Expected                                      | Stage 2                              | Stage 3                                  | Note                                  |
|------------------|-----------------------------------------------|--------------------------------------|------------------------------------------|---------------------------------------|
| **Decision**     | 🟢 APPROVED                                   | 🟢 APPROVED                         | 🟢 APPROVED                             | All agree                             |
|                  |                                               |                                      |                                          |                                       |
| **Dr line 1**    | 🟢 Statutory withholdings payable $7,750       | 🔴 Pension Payable $4,000           | 🔴 Pension Contributions Payable $4,000 | 4 lines instead of 1                  |
| **Dr line 2**    | 🟢 Employee benefits expense $6,300            | 🔴 Health Insurance Payable $6,500  | 🔴 Health Insurance Payable $6,500      | Missing — all as liabilities          |
| **Dr line 3**    |                                               | 🔴 EI Payable $2,100                | 🔴 EI Payable $2,100                    |                                       |
| **Dr line 4**    |                                               | 🔴 Income Tax Payable $1,450        | 🔴 Income Tax Payable $1,450            |                                       |
|                  |                                               |                                      |                                          |                                       |
| **Cr line 1**    | 🟢 Cash $14,050                               | 🟢 Cash $14,050                     | 🟢 Cash $14,050                         | Match                                 |
|                  |                                               |                                      |                                          |                                       |
| **Debit tuple**  | 🟢 (0,0,1,1,0,0)                             | 🔴 (0,0,0,4,0,0)                   | 🔴 (0,0,0,4,0,0)                       | All 4 as liab decrease, no expense    |
| **Credit tuple** | 🟢 (0,0,0,1,0,0)                             | 🟢 (0,0,0,1,0,0)                   | 🟢 (0,0,0,1,0,0)                       | Both correct                          |
|                  |                                               |                                      |                                          |                                       |
| **match**        | 🟢 ground truth                               | 🔴 false                            | 🔴 false                                | Missing employer expense              |
| **tax_relaxed**  | 🟢 ground truth                               | 🔴 false                            | 🔴 false                                | Not a tax issue                       |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Missing Dr Employee benefits expense $6,300 | Dr line 2 absent | Debit classifier | Treated all $14,050 as liability decreases. "4 separate liability accounts being reduced." Did not recognize employer matching portion ($6,300) as new expense. |
| Both | Wrong Dr: 4 liability lines totaling $14,050 vs expected 1 line $7,750 | Dr lines 1-4 | Debit classifier → Entry builder | Classifier counted 4 liabilities; entry builder followed with 4 separate payable accounts. Expected: 1 consolidated "Statutory withholdings payable" for $7,750. |
| Both | Wrong debit structure: (0,0,0,4,0,0) vs (0,0,1,1,0,0) | Debit structure | Debit classifier | All 4 as liability decrease (slot d=4). Expected: 1 expense + 1 liability decrease (c=1, d=1). |

---

## 8. int_hard_27b_meal_meeting

|                  | Expected                            | Stage 2                                    | Stage 3                                    | Note                                  |
|------------------|-------------------------------------|--------------------------------------------|--------------------------------------------|---------------------------------------|
| **Decision**     | 🟢 APPROVED                         | 🟢 APPROVED                               | 🟢 APPROVED                               | All agree                             |
|                  |                                     |                                            |                                            |                                       |
| **Dr line 1**    | 🟢 Meeting expense $125             | 🔴 Meals and Entertainment Expense $125    | 🔴 Meals and Entertainment Expense $125    | Same wrong account both stages        |
|                  |                                     |                                            |                                            |                                       |
| **Cr line 1**    | 🟢 Credit card payable $125         | 🟢 Credit Card Payable $125               | 🟢 Credit Card Payable $125               | Match                                 |
|                  |                                     |                                            |                                            |                                       |
| **Debit tuple**  | 🟢 (0,0,1,0,0,0)                   | 🟢 (0,0,1,0,0,0)                         | 🟢 (0,0,1,0,0,0)                         | Both correct                          |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                   | 🟢 (1,0,0,0,0,0)                         | 🟢 (1,0,0,0,0,0)                         | Both correct                          |
|                  |                                     |                                            |                                            |                                       |
| **match**        | 🟢 ground truth                     | 🟢 **true**                               | 🔴 **false**                              | **Evaluator disagreement**            |
| **tax_relaxed**  | 🟢 ground truth                     | 🟢 **true**                               | 🔴 **false**                              | S2 accepted synonym; S3 rejected      |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Wrong Dr line 1 account: "Meals and Entertainment Expense" vs "Meeting expense" | Dr line 1 | Entry builder | Transaction says "working meeting among employees." Entry builder used generic "Meals and Entertainment" category instead of specific "Meeting expense." |

> **Note**: Evaluator disagreement — S2 accepted as synonym (match=true), S3 rejected as different category (match=false). Pipeline output identical. Amounts correct.

---

## 9. int_hard_32a_grocery_entertainment

|                  | Expected                              | Stage 2                            | Stage 3                            | Note                                  |
|------------------|---------------------------------------|------------------------------------|------------------------------------|---------------------------------------|
| **Decision**     | 🟢 APPROVED                           | 🟢 APPROVED                       | 🟢 APPROVED                       | All agree                             |
|                  |                                       |                                    |                                    |                                       |
| **Dr line 1**    | 🟢 Entertainment expense $1,320       | 🔴 Entertainment Expense $1,200   | 🔴 Entertainment Expense $1,200   | Base reduced by tax split             |
| **Dr line 2**    |                                       | 🔴 Sales Tax Receivable $120      | 🔴 Sales Tax Receivable $120      | Extra tax line                        |
|                  |                                       |                                    |                                    |                                       |
| **Cr line 1**    | 🟢 Credit card payable $1,320         | 🟢 Credit Card Payable $1,320     | 🟢 Credit Card Payable $1,320     | Match                                 |
|                  |                                       |                                    |                                    |                                       |
| **Debit tuple**  | 🟢 (0,0,1,0,0,0)                     | 🔴 (0,0,2,0,0,0)                 | 🔴 (0,0,2,0,0,0)                 | Counts tax as 2nd expense             |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                     | 🔴 (2,0,0,0,0,0)                 | 🔴 (2,0,0,0,0,0)                 | Counts tax payable as 2nd liability   |
|                  |                                       |                                    |                                    |                                       |
| **match**        | 🟢 ground truth                       | 🔴 false                          | 🔴 false                          | Tax split from stated total           |
| **tax_relaxed**  | 🟢 ground truth                       | 🟢 true                           | 🟢 true                           | Removing tax line restores expected   |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Wrong Dr line 1 amount: $1,200 vs $1,320 | Dr line 1 | Entry builder | Split $120 sales tax from $1,320 total. Base expense reduced to $1,200. |
| Both | Extra Dr line: Sales Tax Receivable $120 | Dr line 2 | Entry builder | Treated 10% tax as recoverable. Not in expected entry (full $1,320 as expense). |
| Both | Wrong debit structure: (0,0,2,0,0,0) vs (0,0,1,0,0,0) | Debit structure | Debit classifier | Counted tax as 2nd expense line |
| Both | Wrong credit structure: (2,0,0,0,0,0) vs (1,0,0,0,0,0) | Credit structure | Credit classifier | Counted tax payable as 2nd liability |

> **Note**: Tax-relaxed = true. Correct account name (Entertainment). Removing tax line and restoring to $1,320 matches expected.

---

## 10. int_hard_32b_grocery_breakroom

|                  | Expected                                | Stage 2                            | Stage 3                            | Note                                     |
|------------------|-----------------------------------------|------------------------------------|------------------------------------|------------------------------------------|
| **Decision**     | 🟢 APPROVED                             | 🟢 APPROVED                       | 🟢 APPROVED                       | All agree                                |
|                  |                                         |                                    |                                    |                                          |
| **Dr line 1**    | 🟢 Employee benefits expense $1,320     | 🔴 Office Supplies Expense $1,200 | 🔴 Office Supplies Expense $1,200 | Wrong account + base reduced             |
| **Dr line 2**    |                                         | 🔴 HST Receivable $120            | 🔴 HST Receivable $120            | Extra tax line                           |
|                  |                                         |                                    |                                    |                                          |
| **Cr line 1**    | 🟢 Credit card payable $1,320           | 🟢 Credit Card Payable $1,320     | 🟢 Credit Card Payable $1,320     | Match                                    |
|                  |                                         |                                    |                                    |                                          |
| **Debit tuple**  | 🟢 (0,0,1,0,0,0)                       | 🔴 (0,0,2,0,0,0)                 | 🔴 (0,0,2,0,0,0)                 | Counts tax as 2nd expense                |
| **Credit tuple** | 🟢 (1,0,0,0,0,0)                       | 🔴 (2,0,0,0,0,0)                 | 🔴 (2,0,0,0,0,0)                 | Counts tax payable as 2nd liability      |
|                  |                                         |                                    |                                    |                                          |
| **match**        | 🟢 ground truth                         | 🔴 false                          | 🔴 false                          | Wrong account + tax split                |
| **tax_relaxed**  | 🟢 ground truth                         | 🟢 true                           | 🟢 true                           | Questionable — account category differs  |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Wrong Dr line 1 account: "Office Supplies Expense" vs "Employee benefits expense" | Dr line 1 | Entry builder | Classified breakroom refreshments by item description (office supplies) instead of business purpose (employee welfare). |
| Both | Wrong Dr line 1 amount: $1,200 vs $1,320 | Dr line 1 | Entry builder | Split $120 HST from $1,320 total. |
| Both | Extra Dr line: HST Receivable $120 | Dr line 2 | Entry builder | Treated tax as recoverable. Not in expected. |
| Both | Wrong debit structure: (0,0,2,0,0,0) vs (0,0,1,0,0,0) | Debit structure | Debit classifier | Counted tax as 2nd expense line |
| Both | Wrong credit structure: (2,0,0,0,0,0) vs (1,0,0,0,0,0) | Credit structure | Credit classifier | Counted tax payable as 2nd liability |

> **Note**: Tax-relaxed = true. Questionable — "Office Supplies" vs "Employee benefits" is a category error, not a tax difference. Both evaluators forgave it under tax-relaxed.

---

## 11. hard_16_rent_treatment

|                  | Expected                                    | Stage 2                                                          | Stage 3                                                    | Note                                     |
|------------------|---------------------------------------------|------------------------------------------------------------------|------------------------------------------------------------|------------------------------------------|
| **Decision**     | 🟢 INCOMPLETE_INFORMATION                   | 🟢 INCOMPLETE_INFORMATION                                       | 🟢 INCOMPLETE_INFORMATION                                 | All agree — correct decision             |
|                  |                                             |                                                                  |                                                            |                                          |
| **Entry**        | 🟢 *(none — should ask question)*           | 🟢 *(empty lines)*                                              | 🟢 *(empty lines)*                                        | Both correctly refuse to build           |
|                  |                                             |                                                                  |                                                            |                                          |
| **Question**     | 🟢 Business fact distinguishing prepaid vs expense | 🔴 "Has the company elected the IFRS 16 exemption?" + follow-up | 🔴 "Does your company apply the IFRS 16 exemption...?"   | Both ask about accounting policy         |
|                  |                                             |                                                                  |                                                            |                                          |
| **Debit tuple**  | 🟢 (0,0,0,0,0,0)                           | 🔴 (1,0,0,0,0,0)                                               | 🔴 (1,0,0,0,0,0)                                         | Classifier assumed prepaid               |
| **Credit tuple** | 🟢 (0,0,0,0,0,0)                           | 🔴 (0,0,0,1,0,0)                                               | 🔴 (0,0,0,1,0,0)                                         | Classifier assumed cash payment          |
|                  |                                             |                                                                  |                                                            |                                          |
| **relevant**     |                                             | 🔴 false                                                        | 🔴 false                                                  | Question type is wrong                   |

### Failure Table

| Stage | Failure | Evidence | Source Agent | Failure Mode |
|-------|---------|----------|-------------|--------------|
| Both | Wrong question type: asks about IFRS 16 policy vs business fact | Question | Entry builder | Question: "Does your company apply the IFRS 16 exemption...?" Asks about accounting policy election, not a business fact. A relevant question would ask about lease arrangement (e.g., "What is the expected duration?"). |
| Both | Wrong debit structure: (1,0,0,0,0,0) vs (0,0,0,0,0,0) | Debit structure | Debit classifier | Classified as prepaid asset before knowing if INCOMPLETE. Should be (0,0,0,0,0,0) for ambiguous cases. |
| Both | Wrong credit structure: (0,0,0,1,0,0) vs (0,0,0,0,0,0) | Credit structure | Credit classifier | Classified cash payment before knowing if INCOMPLETE. Should be (0,0,0,0,0,0) for ambiguous cases. |

> **Note**: Decision is correct (INCOMPLETE_INFORMATION). Entry is correctly empty. The failure is only in question quality — asks about accounting treatment instead of business facts.



## Failure Patterns

Grouped by source agent, deduplicated across test cases.

### Debit Classifier (10 unique)

1. Excluded discount from debit side — placed it on credit side instead (int_11 S2)
2. Classified contra-liability as asset increase (slot a) instead of liability decrease (slot d) (int_11 S3)
3. Over-split: counted items with same treatment as separate assets instead of combining (int_18)
4. Classified manufacturing overhead (factory electricity, production wages) as expense instead of WIP asset (int_23, int_26a)
5. Over-split: counted each statutory deduction as separate liability decrease instead of consolidating (int_26a, int_26b)
6. Missed employer matching expense — treated entire remittance as liability decreases (int_26b)
7. Counted tax as separate expense line when tax is part of the stated total (int_hard_32a, int_hard_32b)
8. Classified transaction before knowing it is INCOMPLETE — should be zero structure for ambiguous cases (hard_16)

### Credit Classifier (4 unique)

1. Assumed cash payment at acquisition when payments start at year end (int_11 S2)
2. Over-split: counted each cash payment as separate asset decrease instead of combining (int_18)
3. Over-split: counted each statutory deduction as separate liability increase instead of consolidating (int_26a, int_26b)
4. Counted tax payable as separate liability when tax is part of a single credit card payment (int_hard_32a, int_hard_32b)

### Entry Builder (14 unique)

1. PV rounding — used higher precision annuity factor than expected table (int_11)
2. Ignored its own structure — received 2 debit lines in structure but only produced 1 (int_11 S3)
3. Recorded liability at PV instead of face value (int_11)
4. Wrong account name: "Note Payable" instead of "Long-term payables" (int_11)
5. Refused to build when disambiguator flagged debatable ambiguity (int_12 S2) ✅ 
6. Failed to separate depreciable improvements from non-depreciable land — both as "Land Improvements" (int_12 S3) ✅ 
7. Used generic "Cash" instead of "Cash—chequing" when transaction specifies cheque/bank transfer (int_12 S3, int_26a)
8. Wrong account name: "Marketing Expense" instead of "Advertising expense" (int_24)
9. Extracted HST from "inclusive of sales tax" amount — split base and tax (int_24, int_hard_32a, int_hard_32b) ✅ 
10. Used generic WIP account instead of specific sub-account (int_26a) ✅ 
11. Wrong account name: "Meals and Entertainment" instead of "Meeting expense" (int_hard_27b) ✅ 
12. Classified by item description instead of business purpose — "Office Supplies" instead of "Employee benefits"  ✅ (int_hard_32b)
13. Clarification question asks about accounting policy (IFRS 16) instead of business fact (hard_16) ✅ 
14. Over-split: followed classifier's 4 separate payable lines instead of consolidating (int_26a, int_26b)
