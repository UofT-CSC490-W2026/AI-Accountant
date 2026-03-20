# =============================================================================
# SQS QUEUES — message passing between the 8 ECS services
# =============================================================================
# Autobook uses a 4-tier cascade (cache → model → LLM → human) where each
# tier is an independent ECS service. Services communicate by passing messages
# through SQS queues — the API enqueues, workers dequeue, process, and enqueue
# to the next queue. SQS is fully managed: no servers, no brokers, no Redis
# BRPOP loops. Messages are durable (replicated across AZs), and if a worker
# crashes mid-processing, the message reappears after the visibility timeout.
#
# 7 queues, one per handoff point in the pipeline:
#   files      — API → File Worker (raw file/text input)
#   precedent  — File Worker → Precedent Matcher (normalized transaction)
#   model      — Precedent Matcher → Model Worker (cache miss)
#   llm        — Model Worker → LLM Worker (low-confidence classification)
#   resolution — LLM Worker → Resolution Worker (stuck/fixable → human)
#   post       — All tier workers → Posting Service (validated journal entry)
#   flywheel   — Posting Service → Flywheel Worker (learning feedback)
#
# Each queue has a dead-letter queue (DLQ) that catches messages that fail
# processing repeatedly. This prevents poison messages from looping forever
# and gives you a place to inspect failures.

locals {
  name = "${var.project}-${var.environment}" # e.g. "autobook-dev"

  # The 7 queues in the pipeline — order matches the data flow
  queue_names = ["files", "precedent", "model", "llm", "resolution", "post", "flywheel"]
}

# =============================================================================
# DEAD-LETTER QUEUES — catch messages that fail processing repeatedly
# =============================================================================
# Created first because the main queues reference DLQ ARNs in their redrive
# policy. DLQs use 14-day retention (max) to give you time to investigate
# failures. In normal operation, DLQs should be empty — a non-empty DLQ
# means something is broken and needs attention.
resource "aws_sqs_queue" "dlq" {
  for_each = toset(local.queue_names)

  # e.g. "autobook-dev-files-dlq"
  name = "${local.name}-${each.key}-dlq"

  # How long failed messages stay in the DLQ before auto-deletion.
  # 14 days (max) gives enough time to investigate and replay.
  message_retention_seconds = var.dlq_retention_seconds

  # Encrypt messages at rest using SQS-managed keys (SSE-SQS).
  # No KMS key management needed — AWS handles rotation automatically.
  sqs_managed_sse_enabled = true

  tags = { Name = "${local.name}-${each.key}-dlq" }
}

# =============================================================================
# MAIN QUEUES — one per handoff point in the pipeline
# =============================================================================
# Standard queues (not FIFO) — we don't need strict ordering because each
# transaction is independent. Standard queues offer higher throughput and
# at-least-once delivery, which is fine since our workers are idempotent
# (posting the same journal entry twice is caught by the DB).
resource "aws_sqs_queue" "main" {
  for_each = toset(local.queue_names)

  # e.g. "autobook-dev-files"
  name = "${local.name}-${each.key}"

  # How long a message is hidden after a worker receives it.
  # If the worker doesn't delete the message within this time, SQS makes it
  # visible again for another worker to retry. Must be longer than your
  # slowest processing time — the LLM pipeline (tier 3) takes up to ~3s
  # with retries, so 30s gives plenty of headroom.
  visibility_timeout_seconds = var.visibility_timeout_seconds

  # How long unprocessed messages stay in the queue before auto-deletion.
  # 4 days (default) is reasonable — if a message sits this long, something
  # is seriously wrong and alerts should have fired long before.
  message_retention_seconds = var.message_retention_seconds

  # Long polling — workers wait up to 20s for a message instead of returning
  # immediately with nothing. Reduces empty responses (fewer API calls = lower
  # cost) and reduces latency (message is delivered as soon as it arrives,
  # no polling interval gap).
  receive_wait_time_seconds = var.receive_wait_time_seconds

  # Redrive policy — after max_receive_count failed processing attempts,
  # move the message to the dead-letter queue instead of retrying forever.
  # A "receive" counts each time a worker calls ReceiveMessage and gets this
  # message. If the worker crashes or doesn't delete the message before the
  # visibility timeout expires, the receive count increments.
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = var.max_receive_count
  })

  # Encrypt messages at rest using SQS-managed keys (SSE-SQS)
  sqs_managed_sse_enabled = true

  tags = { Name = "${local.name}-${each.key}" }
}

# =============================================================================
# REDRIVE ALLOW POLICIES — restrict which queues can send to each DLQ
# =============================================================================
# Without this, any queue in the account could use our DLQs as their dead-letter
# target. This locks each DLQ to only accept messages from its corresponding
# main queue. Defined as a separate resource (not inline on the DLQ) to avoid
# circular dependencies between the main queue and DLQ.
resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  for_each = toset(local.queue_names)

  # Apply this policy to the DLQ
  queue_url = aws_sqs_queue.dlq[each.key].id

  # Only the corresponding main queue can redrive to this DLQ
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.main[each.key].arn]
  })
}
