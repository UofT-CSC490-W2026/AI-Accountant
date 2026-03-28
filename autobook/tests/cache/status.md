# tests/cache/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | cache_get_miss | cache/redis.py · cache_get | cache_get returns None when key is missing | test_redis.py | passed | needs fakeredis |
| 2 | cache_get_hit | cache/redis.py · cache_get | cache_get returns deserialized value when key is present | test_redis.py | passed | needs fakeredis |
| 3 | cache_set_no_ttl | cache/redis.py · cache_set | cache_set stores value without TTL | test_redis.py | passed | needs fakeredis |
| 4 | cache_set_with_ttl | cache/redis.py · cache_set | cache_set stores value with TTL and key expires after | test_redis.py | passed | needs fakeredis |
