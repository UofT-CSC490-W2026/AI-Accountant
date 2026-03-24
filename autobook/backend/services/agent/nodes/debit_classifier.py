"""Agent 1 — Debit Classifier node.

Classifies debit-side journal lines into 6 directional categories.
Output: DebitClassifierOutput {"tuple": [int*6], "reason": str}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, DEBIT_CLASSIFIER, COMPLETE,
)
from services.agent.prompts.debit_classifier import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import DebitClassifierOutput


def debit_classifier_node(state: PipelineState, config: RunnableConfig) -> dict:
    i = state["iteration"]
    history = list(state.get("output_debit_classifier", []))

    if state.get("status_debit_classifier") == COMPLETE:
        history.append(history[i - 1])
    else:
        rag_examples = retrieve_transaction_examples(state, "rag_cache_debit_classifier")
        fix_ctx = (state.get("fix_context_debit_classifier") or [None])[-1]

        messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
        structured_llm = get_llm(DEBIT_CLASSIFIER, config).with_structured_output(DebitClassifierOutput)
        result = structured_llm.invoke(messages)
        history.append(result.model_dump())

    return {
        "output_debit_classifier": history,
        "rag_cache_debit_classifier": rag_examples if 'rag_examples' in dir() else state.get("rag_cache_debit_classifier", []),
        "status_debit_classifier": COMPLETE,
    }
