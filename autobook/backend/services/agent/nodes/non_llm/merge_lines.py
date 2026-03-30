"""Merge duplicate journal lines — runs after entry drafter.

Pure Python, no LLM. Combines lines that share the same account name
and type (debit/credit) by summing their amounts.
"""
from services.agent.graph.state import PipelineState


def merge_lines_node(state: PipelineState) -> dict:
    """Merge journal lines with the same account name and type."""
    entry_out = state.get("output_entry_drafter", [])
    if not entry_out:
        return {}

    entry = entry_out[-1]
    if entry is None or not entry.get("lines"):
        return {}

    merged: dict[tuple[str, str], float] = {}
    order: list[tuple[str, str]] = []
    for line in entry["lines"]:
        key = (line["type"], line["account_name"])
        if key not in merged:
            merged[key] = 0.0
            order.append(key)
        merged[key] += line["amount"]

    if len(order) == len(entry["lines"]):
        return {}  # nothing to merge

    new_lines = [
        {"type": t, "account_name": name, "amount": round(amt, 2)}
        for (t, name), amt in ((k, merged[k]) for k in order)
    ]

    new_entry = {**entry, "lines": new_lines}
    history = list(entry_out)
    history[-1] = new_entry

    return {"output_entry_drafter": history}
