# Annotation Guidelines

This document defines how to label transaction records for the Autobook ML layer.

The goal is consistency. If two people label the same input, they should produce the same `labels` object.

## General Rule

Each dataset record contains:
- `features`: what the ML layer sees
- `labels`: what the ML layer should predict

Do not label downstream system behavior here:
- no `precedent_match`
- no `proposed_entry`
- no journal lines
- no clarification status
- no posting status

## Labeling Order

When labeling a record, use this order:
1. determine `intent_label`
2. determine `bank_category`
3. determine `cca_class_match`
4. fill `entities`

## Intent Labels

Use exactly one of these values:
- `asset_purchase`
- `software_subscription`
- `rent_expense`
- `meals_entertainment`
- `professional_fees`
- `bank_fee`
- `transfer`
- `bank_transaction`
- `general_expense`

### `asset_purchase`

Use when the transaction is clearly for acquiring a capital asset such as:
- laptop
- computer
- printer
- desk
- chair
- equipment

Examples:
- "Bought a laptop from Apple for $2400"
- "Purchased office chair from Staples"

Do not use this for small consumable office supplies.

### `software_subscription`

Use when the transaction is clearly recurring or software-related.

Examples:
- Slack subscription
- Figma plan
- QuickBooks monthly fee

### `rent_expense`

Use when the text clearly refers to rent or lease expense.

Examples:
- "Paid office rent"
- "Lease payment for workspace"

### `meals_entertainment`

Use for meals, coffee, restaurants, team lunch, entertainment-type business spending.

Examples:
- "Team lunch at cafe"
- "Client dinner"

### `professional_fees`

Use for outside professional services.

Examples:
- contractor
- consultant
- lawyer
- accountant
- bookkeeper

### `bank_fee`

Use when the transaction is explicitly a bank or service fee.

Examples:
- monthly bank fee
- NSF fee
- wire fee
- service charge

### `transfer`

Use when funds are moved between accounts or destinations rather than spent as an expense.

Examples:
- "Transferred $1500 to savings"
- "E-transfer to reserve account"

If the transaction is clearly a transfer, do not label it as `general_expense`.

### `bank_transaction`

Use when the source is bank-like or uploaded transaction data, but the semantic intent is still too generic to place into a more specific category.

Example:
- "Bank debit 2400" from `csv_upload`

Use this mainly when a bank row is real but under-specified.

### `general_expense`

Use only when the transaction is an expense but none of the more specific categories above clearly applies.

Examples:
- office supplies
- generic business purchase with no stronger class

Do not use `general_expense` if a more specific label is defensible.

## Bank Category

Allowed values:
- `transfer`
- `equipment`
- `software_subscription`
- `rent`
- `meals_entertainment`
- `professional_fees`
- `bank_fees`
- `null`

### Mapping Rule

`bank_category` should usually align with `intent_label`:
- `asset_purchase` -> `equipment`
- `software_subscription` -> `software_subscription`
- `rent_expense` -> `rent`
- `meals_entertainment` -> `meals_entertainment`
- `professional_fees` -> `professional_fees`
- `bank_fee` -> `bank_fees`
- `transfer` -> `transfer`

Use `null` when:
- the record is only a generic `bank_transaction`
- the record is `general_expense`
- there is not enough evidence for a bank-facing category

## CCA Class Match

Allowed values:
- `class_50`
- `class_8`
- `null`

Use this only for capital assets.

### `class_50`

Use for computer-related assets such as:
- laptop
- computer
- printer

### `class_8`

Use for general furniture or equipment such as:
- desk
- chair

### `null`

Use `null` when:
- the record is not an asset purchase
- the asset class is not applicable

Do not guess a CCA class for non-capital expenses.

## Entity Labels

The `entities` object currently includes:
- `amount`
- `vendor`
- `asset_name`
- `quantity`
- `mentioned_date`
- `transfer_destination`

If an entity is not supported by the text or reliable features, set it to `null`.

### `entity_spans`

When training a DeBERTa token-classification entity model, add `labels.entity_spans` whenever possible.

Each span should include:
- `label`
- `text`
- `start`
- `end`

Recommended labels:
- `VENDOR`
- `ASSET_NAME`
- `TRANSFER_DESTINATION`
- `MENTIONED_DATE`

Example:

```json
{
  "label": "VENDOR",
  "text": "Apple",
  "start": 21,
  "end": 26
}
```

If explicit spans are unavailable, weak alignment can still be used for smoke experiments, but explicit spans are preferred for real training.

### `amount`

Label the primary transaction amount when it is clear.

Use `null` when:
- multiple competing amounts appear
- the amount is ambiguous
- no amount is present

### `vendor`

Label the business or party being paid.

Examples:
- Apple
- Slack
- Staples

Do not put transfer destinations here. For transfers, use `transfer_destination`.

### `asset_name`

Use a short normalized asset noun.

Examples:
- `laptop`
- `printer`
- `chair`
- `desk`

Do not use long phrases unless the asset is only identifiable that way.

### `quantity`

Label the numeric quantity only when clearly present.

Examples:
- `1`
- `100`

If quantity is implied but not explicit, use `null`.

### `mentioned_date`

Use the explicitly mentioned transaction-related date from the text or extracted mentions.

Do not automatically copy `features.transaction_date` into this field unless the date is actually mentioned in the source text.

### `transfer_destination`

Use for the destination of a transfer.

Examples:
- Savings
- Reserve Account
- Payroll Account

Do not use this for normal merchants or vendors.

## Ambiguity Rules

### Multiple amounts

If there are multiple amount mentions and the primary amount is not obvious:
- set `entities.amount` to `null`
- keep mentions in `features.amount_mentions`

### Weak vendor evidence

If the counterparty is unclear:
- set `vendor` to `null`

Do not guess from weak hints.

### Mixed-purpose description

If a transaction could fit multiple labels, choose the most specific defensible one.

Priority:
1. `transfer`
2. `bank_fee`
3. `asset_purchase`
4. `software_subscription`
5. `rent_expense`
6. `meals_entertainment`
7. `professional_fees`
8. `bank_transaction`
9. `general_expense`

## Source-Specific Notes

### `manual_text`

Expect richer natural language. Entity labeling should rely on the text first, then mentions.

### `csv_upload` and `bank_feed`

Expect terse descriptions. Use `bank_transaction` when the row is real but under-specified.

### `pdf_upload`

Treat extracted text the same way as other text, but expect OCR or extraction noise.

## Normalization Style

For labeled entity values:
- use title case for vendor and transfer destination when appropriate
- use lowercase canonical nouns for `asset_name`
- use numeric values for `amount` and `quantity`
- use ISO `YYYY-MM-DD` for `mentioned_date`

## Examples

### Asset purchase

Input:
- "Bought a laptop from Apple for $2400"

Labels:
- `intent_label = asset_purchase`
- `bank_category = equipment`
- `cca_class_match = class_50`
- `entities.vendor = Apple`
- `entities.asset_name = laptop`
- `entities.amount = 2400.0`

### Transfer

Input:
- "Transferred $1500 to savings"

Labels:
- `intent_label = transfer`
- `bank_category = transfer`
- `cca_class_match = null`
- `entities.transfer_destination = Savings`
- `entities.amount = 1500.0`

### Generic bank row

Input:
- "Bank debit 2400" from `csv_upload`

Labels:
- `intent_label = bank_transaction`
- `bank_category = null`
- `cca_class_match = null`
- `entities.amount = 2400.0`
