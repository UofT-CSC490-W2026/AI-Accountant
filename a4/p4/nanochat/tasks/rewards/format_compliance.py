"""Reward A: Format Compliance — 1.0 if response contains #### <number>, 0.0 otherwise."""

from tasks.rewards.gsm8k_utils import GSM_RE


def reward_format_compliance(conversation, assistant_response):
    match = GSM_RE.search(assistant_response)
    return 1.0 if match else 0.0
