# tests/services/ml_inference/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | handler_delegates | services/ml_inference/handler.py · handler | handler parses SQS event records and delegates to process | test_handler.py | passed | |
| 2 | process_enriches | services/ml_inference/process.py · process | process enriches message and forwards to agent queue | test_process.py | passed | |
| 3 | classify_intent_transfer | services/ml_inference/service.py · classify_intent | classify_intent returns transfer for transfer-related text | test_service.py | passed | |
| 4 | classify_intent_bank_fee | services/ml_inference/service.py · classify_intent | classify_intent returns bank_fee for fee-related text | test_service.py | passed | |
| 5 | cca_match_none | services/ml_inference/service.py · match_cca_class | match_cca_class returns None for non-asset intent | test_service.py | passed | |
| 6 | extract_entities_no_amounts | services/ml_inference/service.py · extract_entities | extract_entities handles missing amount_mentions gracefully | test_service.py | passed | |
| 7 | extract_entities_no_parties | services/ml_inference/service.py · extract_entities | extract_entities handles missing party_mentions gracefully | test_service.py | passed | |
| 8 | score_confidence_perfect | services/ml_inference/service.py · score_confidence | score_confidence returns 1.0 when all component scores are perfect | test_service.py | passed | |
| 9 | extract_entities_vendor_pattern | services/ml_inference/service.py · extract_entities | extract_entities prefers explicit vendor from party_mentions | test_service.py | passed | |
| 10 | extract_entities_ignores_date_tokens | services/ml_inference/service.py · extract_entities | extract_entities ignores date tokens when extracting amount | test_service.py | passed | |
| 11 | extract_entities_transfer_destination | services/ml_inference/service.py · extract_entities | extract_entities extracts transfer destination from text | test_service.py | passed | |
| 12 | extract_entities_prefers_mentions | services/ml_inference/service.py · extract_entities | extract_entities prefers normalizer mentions over reparsing raw text | test_service.py | passed | |
| 13 | classify_asset_purchase_and_cca | services/ml_inference/service.py · classify_intent | classify_intent returns asset_purchase for printer purchase, cca_match returns class_50 | test_service.py | passed | |
| 14 | classify_software_subscription | services/ml_inference/service.py · classify_intent | classify_intent returns software_subscription for vendor keyword text | test_service.py | passed | |
| 15 | enrich_message_transfer | services/ml_inference/service.py · enrich_message | enrich_message returns transfer intent with None cca_class_match | test_service.py | passed | |
