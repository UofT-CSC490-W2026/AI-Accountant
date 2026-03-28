"""LLM-as-judge for entry and clarification accuracy."""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

ENTRY_PROMPT = """\
Compare the actual journal entry against the expected entry.

Rules:
1. Account names may differ in wording but must be semantically equivalent \
(e.g., "Inventory" = "Inventories — Merchandise", "Cash" = "Cash — chequing").
2. Each line must have the correct type (debit/credit) and amount.
3. Same number of lines required.
4. Order does not matter.

Expected:
{expected}

Actual:
{actual}

Output JSON only: {{"match": true/false, "reason": "one sentence"}}"""

CLARIFICATION_PROMPT = """\
A transaction has multiple valid interpretations. The pipeline asked a \
clarification question instead of guessing.

A good clarification question:
1. Targets the specific ambiguity between the listed interpretations.
2. Its answer would determine which interpretation applies.
3. Is answerable by someone who knows the business context.

Possible interpretations:
{cases}

Question asked:
{question}

Output JSON only: {{"relevant": true/false, "reason": "one sentence"}}"""


def _call_judge(prompt: str) -> dict | None:
    """Call Haiku as judge. Returns parsed JSON or None on failure."""
    try:
        import boto3
        client = boto3.client("bedrock-runtime", region_name="ca-central-1")
        response = client.converse(
            modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 200},
        )
        text = response["output"]["message"]["content"][0]["text"]
        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("```"))
        return json.loads(text)
    except Exception as e:
        logger.warning("Judge call failed: %s", e)
        return None


def judge_entry(expected_entry: dict | None, actual_entry: dict | None) -> bool:
    """Judge if actual entry semantically matches expected. Returns match bool."""
    if expected_entry is None and actual_entry is None:
        return True
    if expected_entry is None or actual_entry is None:
        return False

    prompt = ENTRY_PROMPT.format(
        expected=json.dumps(expected_entry, indent=2),
        actual=json.dumps(actual_entry, indent=2),
    )
    result = _call_judge(prompt)
    if result is None:
        return False
    return result.get("match", False)


def judge_clarification(expected_cases: dict | None,
                        questions: list | None) -> bool:
    """Judge if clarification question is relevant to the ambiguity."""
    if not expected_cases or not questions:
        return False

    cases_str = "\n".join(f"- {name}" for name in expected_cases.keys())
    question_str = "\n".join(f"- {q}" for q in questions)

    prompt = CLARIFICATION_PROMPT.format(
        cases=cases_str,
        question=question_str,
    )
    result = _call_judge(prompt)
    if result is None:
        return False
    return result.get("relevant", False)
