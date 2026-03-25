"""Prompt message part builders.

Each function returns list[dict] — content blocks for Bedrock Converse API.
All are pure functions with no side effects.
"""
import json

from services.agent.utils.prompt.reasoning import compile_reasoning_trace

CACHE_POINT = {"cachePoint": {"type": "default"}}


def build_transaction(state: dict) -> list[dict]:
    """Transaction text (always raw, not enriched — stable for RAG + caching)."""
    return [{"text": f"<transaction>{state['transaction_text']}</transaction>"}]


def build_user_context(state: dict) -> list[dict]:
    """User business context (business type, province, ownership)."""
    ctx = state.get("user_context", {})
    return [{"text": (
        f"<context>\n"
        f"  Business type: {ctx.get('business_type', 'unknown')}\n"
        f"  Province: {ctx.get('province', 'unknown')}\n"
        f"  Ownership: {ctx.get('ownership', 'unknown')}\n"
        f"</context>"
    )}]


def build_tuples(debit, credit) -> list[dict]:
    """Debit and credit tuples. Takes values directly (not state keys)."""
    return [{"text": (
        f"<debit_tuple>{debit}</debit_tuple>\n"
        f"<credit_tuple>{credit}</credit_tuple>"
    )}]


def build_labeled_tuples(debit, credit) -> list[dict]:
    """Tuples with inline slot labels for corrector agents."""
    return [{"text": (
        "Initial debit classification from the previous classifier:\n"
        "<initial_debit_tuple>\n"
        f"  {debit}\n"
        "  Slots: a=asset increase, b=dividend increase, c=expense increase, "
        "d=liability decrease, e=equity decrease, f=revenue decrease\n"
        "</initial_debit_tuple>\n\n"
        "Credit classification from a separate classifier (for cross-validation only):\n"
        "<credit_tuple>\n"
        f"  {credit}\n"
        "  Slots: a=liability increase, b=equity increase, c=revenue increase, "
        "d=asset decrease, e=dividend decrease, f=expense decrease\n"
        "</credit_tuple>"
    )}]


def build_journal(journal: dict) -> list[dict]:
    """Journal entry as formatted JSON."""
    return [{"text": (
        f"<journal_entry>\n{json.dumps(journal, indent=2)}\n</journal_entry>"
    )}]


def build_reasoning(state: dict, iteration: int) -> list[dict]:
    """Labeled reasoning trace from all generator agents, full history."""
    return [{"text": (
        f"<generator_reasoning>\n{compile_reasoning_trace(state, iteration)}\n</generator_reasoning>"
    )}]


def build_rejection(approval: dict) -> list[dict]:
    """Approver rejection output."""
    return [{"text": (
        f"<rejection>\n{json.dumps(approval, indent=2)}\n</rejection>"
    )}]


def build_coa(coa_results: list[dict] | None) -> list[dict]:
    """Chart of accounts lookup results."""
    if not coa_results:
        return []
    coa_text = "\n".join(
        f"  {a['account_code']} — {a['account_name']} ({a['account_type']})"
        for a in coa_results
    )
    return [{"text": f"<chart_of_accounts>\n{coa_text}\n</chart_of_accounts>"}]


def build_tax(tax_results: dict | None) -> list[dict]:
    """Tax rules lookup results."""
    if not tax_results:
        return []
    return [{"text": (
        f"<tax_rules>rate={tax_results.get('rate', 0)}, "
        f"taxable={tax_results.get('taxable', False)}</tax_rules>"
    )}]


def build_vendor(vendor_results: list[dict] | None) -> list[dict]:
    """Vendor history lookup results."""
    if not vendor_results:
        return []
    vendor_text = "\n".join(
        f"  {v.get('account_name', '')} — {v.get('type', '')} ${v.get('amount', '')}"
        for v in vendor_results
    )
    return [{"text": f"<vendor_history>\n{vendor_text}\n</vendor_history>"}]


def build_fix_context(fix_context: str | None) -> list[dict]:
    """Fix context block (rerun guidance from diagnostician)."""
    if not fix_context:
        return []
    return [{"text": (
        "A previous review rejected this classification. "
        "The following guidance explains what to fix:\n"
        f"<fix_context>{fix_context}</fix_context>"
    )}]


def build_rag_examples(rag_examples: list[dict], label: str,
                       fields: list[str]) -> list[dict]:
    """RAG examples content block.

    Args:
        rag_examples: List of example dicts from RAG retrieval.
        label: Description, e.g. "similar past transactions with correct debit tuples".
        fields: Keys to extract from each example dict.
    """
    if not rag_examples:
        return []

    text = f"Reference: {label}:\n<examples>\n"
    for ex in rag_examples:
        for field in fields:
            val = ex.get(field, "")
            text += f"  {field}: {val}\n"
        text += "\n"
    text += "</examples>"
    return [{"text": text}]


# ── Section builders for HumanMessage structure ─────────────────────────

def build_context_section(fix: list[dict], rag: list[dict]) -> list[dict]:
    """## Context section — only present when fix_context or rag_examples exist."""
    if not fix and not rag:
        return []
    return [{"text": "## Context"}] + fix + rag


def build_input_section(*content_blocks: list[dict]) -> list[dict]:
    """## Input section — wraps transaction + tuples or other input data."""
    blocks: list[dict] = [{"text": "## Input"}]
    for block in content_blocks:
        blocks.extend(block)
    return blocks


