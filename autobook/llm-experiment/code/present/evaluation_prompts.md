# Post-Hoc Evaluation Prompts

Claude Code evaluates entry accuracy and clarification relevance after experiment runs. Reads result JSONs + test case definitions, writes evaluation files to the analysis directory.

---

## 1. Entry Accuracy Evaluation

### Procedure

For each variant, for each non-ambiguous test case:

1. Read `expected_entry` from test case definition (`test_cases/`)
2. Read `journal_entry` from result JSON (`results/<experiment>/<variant>/<test_case>.json`)
3. Compare using the criteria below

### Criteria

**Match** — ALL must hold:
- **Account equivalence**: Semantically equivalent accounts. Common equivalences:
  - "Inventory" = "Inventories — Merchandise" = "Inventories — Finished goods"
  - "Cash" = "Cash — chequing" = "Bank"
  - "AP" = "Accounts Payable" = "Trade payables"
  - "AR" = "Accounts Receivable" = "Trade receivables"
  - "Revenue" = "Revenue — Product sales" = "Sales Revenue" = "Revenue — Service revenue"
  - "COGS" = "Cost of goods sold" = "Cost of sales"
  - "Land Improvements" = "PP&E — Site improvements" (for depreciable improvements)
  - "Meals and Entertainment Expense" = "Meeting Expense" = "Entertainment Expense" (same expense category)
  - Any reasonable accounting synonym is acceptable
- **Type correct**: Correct debit/credit direction per line
- **Amount correct**: Exact amount per line
- **Line consolidation**: Multiple lines to the same account that sum to the expected amount = match (e.g., two Cash credits of $1,750,000 + $2,360,000 = one Cash credit of $4,110,000)

**Partial match** — entry is substantively correct but has minor differences:
- Account name differs but same account category (e.g., "Office Supplies" vs "Employee Benefits" = NOT partial, different category)
- Line count differs due to consolidation (same totals per side)
- PV calculation differs by < 1% (rounding)

**Not a match** — ANY of:
- Wrong account category (e.g., expense instead of asset)
- Wrong amount (> 1% difference, excluding PV rounding)
- Wrong debit/credit direction
- Missing economic event (e.g., missing COGS on a sale)
- INCOMPLETE_INFORMATION when entry was expected

**Edge cases:**
- Both null → match (and tax_relaxed_match = true)
- One null, one not → not match
- Extra tax lines (not in expected) → don't penalize if base amounts correct

### Two accuracy metrics

For each entry, evaluate BOTH:
1. **match** — strict criteria above
2. **tax_relaxed_match** — same criteria but with these additional tolerances:
   - Extra HST/GST Receivable or Payable lines not in expected → OK
   - Base amount reduced by extracted tax (e.g., $22,000 → $19,469 + $2,531 HST) → OK if the pre-tax economic event is correct
   - Tax rate differs from expected (e.g., 13% HST vs 10% stated) → OK if the non-tax lines are correct
   - Tax applied when expected has none → OK if removing the tax lines would produce the expected entry
   - In short: ignore all tax-related differences and evaluate only the underlying economic transaction

### Output

```json
{
  "evaluator": "claude",
  "evaluated_at": "<ISO timestamp>",
  "prompt_version": "v2",
  "results": {
    "full_pipeline": {
      "basic_01_inventory_cash": {
        "match": true,
        "tax_relaxed_match": true,
        "reason": "Semantically equivalent accounts. Same types and amounts."
      }
    },
    "baseline": {
      "basic_01_inventory_cash": {
        "match": false,
        "tax_relaxed_match": false,
        "reason": "Missing COGS line."
      }
    }
  }
}
```

---

## 2. Clarification Relevance Evaluation

### Procedure

For each variant, for each ambiguous test case:

1. Read `expected_cases` from test case definition — the possible valid interpretations
2. Read `final_decision` and pipeline state from result JSON
3. Evaluate using the criteria below

### Criteria

**Relevant** — ALL must hold:
- Pipeline output `final_decision: "INCOMPLETE_INFORMATION"`
- At least one clarification question was produced
- The question **distinguishes between the listed interpretations** — answering it determines which `expected_case` applies
- The question is **about business facts**, not accounting knowledge

**Not relevant** — ANY of:
- Pipeline did not output INCOMPLETE_INFORMATION (guessed instead)
- No clarification question produced
- Question too generic ("Can you provide more details?")
- Question asks about accounting treatment ("Should this be capitalized or expensed?")

### Reference: expected_cases

**hard_01_note_discounting:**
- Derecognition (sale)
- Collateralized borrowing

**hard_02_investment_classification:**
- Short-term trading (FVTPL)
- Long-term strategic (FVOCI)
- Significant influence (Equity method)

**hard_27_meal_purpose:**
- Overtime meal (employee benefit)
- Working meeting
- Client entertainment
- Factory staff meal (production overhead)

**hard_32_grocery_purpose:**
- Client entertainment
- Employee break room supplies

**hard_16_rent_treatment:**
- Prepaid (asset recognition)
- Expense (short-term lease exemption)

### Output

```json
{
  "evaluator": "claude",
  "evaluated_at": "<ISO timestamp>",
  "prompt_version": "v1",
  "results": {
    "full_pipeline": {
      "hard_27_meal_purpose": {
        "actual_decision": "INCOMPLETE_INFORMATION",
        "actual_questions": ["What was the purpose of this meal?"],
        "expected_cases": ["Overtime meal", "Working meeting", "Client entertainment", "Factory staff meal"],
        "relevant": true,
        "reason": "Question directly targets the ambiguity — answer determines which of the four interpretations applies."
      }
    },
    "baseline": {
      "hard_27_meal_purpose": {
        "actual_decision": "APPROVED",
        "actual_questions": null,
        "expected_cases": ["Overtime meal", "Working meeting", "Client entertainment", "Factory staff meal"],
        "relevant": false,
        "reason": "Pipeline guessed instead of asking — output APPROVED, not INCOMPLETE_INFORMATION."
      }
    }
  }
}
```

---

## Workflow

1. `./run_experiment.sh` — runs pipeline, saves results
2. `./run_analysis.sh` — computes automated metrics (decision, tuple, tokens, cost)
3. Claude reads results + test cases, evaluates using prompts above
4. Claude writes `entry_accuracy.json` + `clarification_relevance.json` to `results/<experiment>/<variant>/`
5. `./run_analysis.sh` merges evaluation files at load time
6. `./run_present.sh` generates report
