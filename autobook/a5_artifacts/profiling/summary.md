# A5 Profiling Summary

Profiled with Python's `profile` module against 3,000 representative transaction messages.

Optimizations applied before this run:
- precompiled regex patterns for amount, date, party, and quantity extraction
- `normalize_text` switched to split/join whitespace collapsing
- `normalize()` now reuses precomputed date mentions instead of reparsing the description

Measured wall-clock times:
- `normalize`: 447.69 ms
- `extract_party_mentions`: 115.05 ms
- `extract_amount_mentions`: 103.63 ms
- `extract_date_mentions`: 66.86 ms
- `normalize_text`: 18.42 ms
