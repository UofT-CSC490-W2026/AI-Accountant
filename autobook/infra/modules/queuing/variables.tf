# =============================================================================
# REQUIRED INPUTS — caller must provide these
# =============================================================================

# Used in queue names like "autobook-dev-normalizer"
variable "project" {
  type        = string
  description = "Project name, used in queue naming"
}

# Used in queue names like "autobook-dev-normalizer"
variable "environment" {
  type        = string
  description = "Deployment environment, used in queue naming"
}

# =============================================================================
# OPTIONAL INPUTS — safe defaults for most deployments
# =============================================================================

# How many times a worker can receive a message before it's moved to the DLQ.
# Each "receive" = one ReceiveMessage API call that returns this message.
# If the worker crashes or doesn't delete the message before the visibility
# timeout, the count increments. 3 attempts balances retry tolerance with
# fast failure detection — a truly bad message hits the DLQ in ~90s (3 × 30s).
variable "max_receive_count" {
  type        = number
  description = "Max processing attempts before moving a message to the dead-letter queue"
  default     = 3

  validation {
    condition     = var.max_receive_count >= 1 && var.max_receive_count <= 1000
    error_message = "max_receive_count must be between 1 and 1000."
  }
}

# How long a message stays invisible after a worker receives it.
# Must be longer than the slowest worker's processing time.
# LLM pipeline (tier 3): ~3s per transaction with retries.
# 30s gives 10x headroom for slow responses or cold starts.
variable "visibility_timeout_seconds" {
  type        = number
  description = "Seconds a message is hidden after being received (must exceed worker processing time)"
  default     = 30

  validation {
    condition     = var.visibility_timeout_seconds >= 0 && var.visibility_timeout_seconds <= 43200
    error_message = "visibility_timeout_seconds must be between 0 and 43200 (12 hours)."
  }
}

# How long unprocessed messages stay in the main queue before auto-deletion.
# 4 days is the SQS default. Messages stuck this long indicate a systemic
# issue — alerts should fire well before this.
variable "message_retention_seconds" {
  type        = number
  description = "Seconds before unprocessed messages are auto-deleted from the main queue"
  default     = 345600 # 4 days

  validation {
    condition     = var.message_retention_seconds >= 60 && var.message_retention_seconds <= 1209600
    error_message = "message_retention_seconds must be between 60 (1 min) and 1209600 (14 days)."
  }
}

# How long failed messages stay in the DLQ before auto-deletion.
# 14 days (max) gives the team time to investigate failures, fix the bug,
# and replay the messages. DLQ messages are evidence — don't lose them too fast.
variable "dlq_retention_seconds" {
  type        = number
  description = "Seconds before messages are auto-deleted from the dead-letter queue"
  default     = 1209600 # 14 days (maximum)

  validation {
    condition     = var.dlq_retention_seconds >= 60 && var.dlq_retention_seconds <= 1209600
    error_message = "dlq_retention_seconds must be between 60 (1 min) and 1209600 (14 days)."
  }
}

# How long ReceiveMessage waits for a message before returning empty.
# 20s (max) = long polling. Reduces empty responses and API call costs.
# Without this (0s = short polling), workers spam ReceiveMessage and get
# empty responses most of the time, wasting API calls.
variable "receive_wait_time_seconds" {
  type        = number
  description = "Seconds ReceiveMessage waits for a message (20 = long polling, 0 = short polling)"
  default     = 20

  validation {
    condition     = var.receive_wait_time_seconds >= 0 && var.receive_wait_time_seconds <= 20
    error_message = "receive_wait_time_seconds must be between 0 and 20."
  }
}
