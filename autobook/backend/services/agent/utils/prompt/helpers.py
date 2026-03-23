"""Generic prompt content helpers.

Used by all agent build_prompt functions to build fix context and RAG
example content blocks.
"""


def build_fix_context(fix_context: str | None) -> list[dict]:
    """Build fix context block (rerun guidance from diagnostician).

    Returns:
        List with one content block if fix_context provided, empty list otherwise.
    """
    if not fix_context:
        return []
    return [{"text": f"<fix_context>{fix_context}</fix_context>"}]


def build_rag_examples(rag_examples: list[dict], label: str,
                       fields: list[str]) -> list[dict]:
    """Build RAG examples content block.

    Args:
        rag_examples: List of example dicts from RAG retrieval.
        label: Description of what these examples are, e.g.
               "similar past transactions with correct debit tuples".
        fields: Keys to extract from each example dict, e.g.
                ["transaction", "debit_tuple"].

    Returns:
        List with one content block if examples provided, empty list otherwise.
    """
    if not rag_examples:
        return []

    text = f"These are {label}:\n<examples>\n"
    for ex in rag_examples:
        for field in fields:
            val = ex.get(field, "")
            text += f"  {field}: {val}\n"
        text += "\n"
    text += "</examples>"
    return [{"text": text}]
