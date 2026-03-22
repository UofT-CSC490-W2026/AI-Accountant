# Transaction Lifecycle

`transactions` is the canonical normalized transaction record.

## Ownership

Normalizer-owned fields:
- `description`
- `normalized_description`
- `currency`
- `date`
- `source`
- normalization mention candidates:
  - `amount_mentions`
  - `date_mentions`
  - `party_mentions`
  - `quantity_mentions`

Conditionally normalizer-owned scalars:
- `amount` only when the source provides it explicitly or unambiguously
- `counterparty` only when the source provides it explicitly or unambiguously

ML-owned enrichment fields:
- `intent_label`
- `entities`
- `bank_category`
- `cca_class_match`

## Intended flow

1. `parse` accepts raw input and enqueues it.
2. `normalizer` converts raw input into a canonical transaction candidate.
3. `normalizer` persists the initial `transactions` row and attaches `transaction_id` to the pipeline message.
4. `precedent` and `ml_inference` read that normalized transaction context.
5. ML updates enrichment fields on the existing `transactions` row.
6. Later stages consume the enriched transaction and produce clarification or posting outputs.

## Notes

- The canonical transaction row should exist before posting or clarification persistence.
- Later stages may still backfill missing normalized values defensively, but they are not the primary owners of transaction creation.
- `normalized_description` is a normalized text form for downstream ML and rule consumption. It is not an ML output.
- For free-text input, mention candidates are the primary normalization output; ML resolves their semantic roles later.
