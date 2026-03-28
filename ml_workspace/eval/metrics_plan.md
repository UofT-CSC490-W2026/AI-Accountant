# Metrics Plan

## Required Metrics

1. Intent classification
   - accuracy
   - macro F1

2. Bank category classification
   - macro F1

3. CCA match classification
   - accuracy

4. Entity extraction
   - per-field precision / recall / F1

5. Routing quality
   - percent auto-posted
   - percent clarified
   - wrong auto-post count

## Release Gate Suggestion

Do not switch the backend default provider away from `heuristic` until:
- validation metrics are stable
- artifact loading works locally
- hybrid provider outputs match the expected backend contract
