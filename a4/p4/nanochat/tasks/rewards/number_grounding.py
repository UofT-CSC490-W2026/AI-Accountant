"""Reward E: Number Grounding — rewards using numbers from the question.

Extracts all numbers from the question and checks what fraction appear in the
response. Forces the model to work with the given problem's data rather than
fabricated values.

Returns float in [0, 1]:
  - Response uses all question numbers -> 1.0
  - Response uses none -> 0.0
  - Question with no numbers -> 1.0 (conservative fallback, rare in GSM8K)
"""

import re


def reward_number_grounding(conversation, assistant_response):
    question = conversation['messages'][0]['content']

    q_numbers = set(re.findall(r'\b\d+\.?\d*\b', question))
    if not q_numbers:
        return 1.0

    r_numbers = set(re.findall(r'\b\d+\.?\d*\b', assistant_response))
    overlap = q_numbers & r_numbers
    return len(overlap) / len(q_numbers)
