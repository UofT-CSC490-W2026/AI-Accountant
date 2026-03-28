# Testing Workflow

This is a repeating loop. Run it after every batch of tests written and after every codebase change.

---

## The Loop

```
Check Status → Identify Gap → Fill Gap → Run & Update → (codebase change?) → repeat
```

---

## Step 1 — Check Current Status

Read the existing reports — do not rerun pytest here:

```bash
open autobook/htmlcov/index.html
```

Or read `autobook/tests/overall-status.md` for the last recorded numbers.

Key things to note:
- Current coverage % and how far from 96%
- Which directories have the most missing lines

---

## Step 2 — Identify Gap

From the HTML report, drill into the backend file with the most missing lines. Find the exact uncovered lines.

Identify each **uncovered behavior** — a group of related uncovered lines that can be verified by a single test function. One behavior = one row in status.md = one `def test_*`.

Cross-reference with the relevant `autobook/tests/<dir>/status.md`:
- Rows marked `pending` that correspond to uncovered behaviors → these are the next targets
- Uncovered behavior with NO row in status.md → new gap found, add a row

To add a new gap to status.md:
1. Find the backend file and function with uncovered lines
2. Group related lines into one testable behavior
3. Add a new row to the correct `autobook/tests/<dir>/status.md` with status `pending`

---

## Step 3 — Fill Gap (one directory at a time)

Work on one directory at a time. Do not start a new directory until it is complete.

For each directory, run this cycle:

### 3a — Reconcile existing tests with status.md

Check if test files already exist in the target directory:

```bash
ls autobook/tests/<dir>/
```

For each existing test function, find the matching row in `autobook/tests/<dir>/status.md`:
- Match found → mark that row as `written`
- No matching row → add a new row with status `written`
- Row with no matching test → leave as `pending`

### 3b — Write pending tests

For each remaining `pending` row:
1. Write the test in `autobook/tests/<dir>/<test_file>` — append if file exists, create if not
2. Mark the row as `written`

### 3c — Run tests for this directory

```bash
cd autobook
uv run pytest tests/<dir>/ --tb=short -q
```

Mark each row as `passed` or `failed` based on the result.

**If a test fails**, determine the root cause:

- **Code issue** — the backend code does not behave as the test expects.
  → Fix the code. The test describes correct behavior and must not be changed to accommodate broken code.
- **Test issue** — the test itself is wrong (bad assertion, incorrect setup, wrong assumption).
  → Fix the test until it correctly and precisely describes the intended behavior.
  → Do not weaken a test just to make it pass. A passing test that checks the wrong thing is worse than a failing one.

**Move on** when all rows for this directory are `passed` (or `failed` due to a code issue that is deferred).

Proceed to the next directory and repeat 3a–3c.

---

## Step 4 — Full Suite Run & Update Overall Status

After all directories are done (or at a natural checkpoint), run the full suite:

```bash
cd autobook
uv run pytest --tb=short -q
```

Update `autobook/tests/overall-status.md` with new coverage numbers.

---

## Codebase Change (new feature, refactor, etc.)

After any backend change:

1. Run Step 1 — new lines will appear as uncovered
2. Run Step 2 — identify which new lines are gaps
3. Add rows to the relevant status.md files
4. Run Steps 3 and 4 to fill and verify

The loop restarts from Step 1.
