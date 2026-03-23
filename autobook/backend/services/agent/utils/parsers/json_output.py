import json

from services.agent.graph.state import ENTRY_BUILDER, APPROVER, DIAGNOSTICIAN

# Required fields per agent output schema
_SCHEMAS: dict[str, dict] = {
    ENTRY_BUILDER: {
        "required": ["date", "description", "lines"],
        "types": {"lines": list},
    },
    APPROVER: {
        "required": ["approved", "confidence", "reason"],
        "types": {"approved": bool, "confidence": (int, float), "reason": str},
    },
    DIAGNOSTICIAN: {
        "required": ["decision", "fix_plans"],
        "types": {"fix_plans": list},
        "enums": {"decision": ("FIX", "STUCK")},
    },
}


def parse_json_output(agent_name: str, raw: str) -> dict | None:
    """Parse an LLM JSON output string and validate against agent schema.

    Args:
        agent_name: One of "entry_builder", "approver", "diagnostician".
        raw: Raw LLM output string (expected to be JSON).

    Returns:
        Parsed dict if valid, None if parsing or schema check fails.
    """
    try:
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        data = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        return None

    if not isinstance(data, dict):
        return None

    schema = _SCHEMAS.get(agent_name)
    if schema is None:
        return None

    # Check required fields
    for field in schema["required"]:
        if field not in data:
            return None

    # Check types
    for field, expected in schema.get("types", {}).items():
        if field in data and not isinstance(data[field], expected):
            return None

    # Check enums
    for field, allowed in schema.get("enums", {}).items():
        if field in data and data[field] not in allowed:
            return None

    return data
