# tests/queues/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | sqs_enqueue | queues/sqs.py · enqueue | enqueue sends message body to SQS queue and returns message ID | test_sqs.py | passed | needs moto |
| 2 | sqs_dequeue_empty | queues/sqs.py · dequeue | dequeue returns None when queue is empty | test_sqs.py | passed | needs moto |
| 3 | sqs_dequeue_message | queues/sqs.py · dequeue | dequeue returns parsed message body and deletes it from queue | test_sqs.py | passed | needs moto |
| 4 | redis_publish | queues/redis.py · publish | publish sends message to Redis channel | test_redis.py | passed | needs fakeredis |
| 5 | redis_publish_sync | queues/redis.py · publish_sync | publish_sync sends message to Redis channel synchronously | test_redis.py | passed | needs fakeredis |
| 6 | redis_subscribe | queues/redis.py · subscribe | subscribe receives messages published to channel | test_redis.py | passed | needs fakeredis |
