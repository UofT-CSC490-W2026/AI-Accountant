"""Agent 2 — Credit Classifier node.

Classifies credit-side journal lines into 6 directional categories.
Output: CreditClassifierOutput {"tuple": [int*6], "reason": str}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, CREDIT_CLASSIFIER, COMPLETE,
)
from services.agent.prompts.credit_classifier import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import CreditClassifierOutput


def credit_classifier_node(state: PipelineState, config: RunnableConfig) -> dict:
    i = state["iteration"]
    history = list(state.get("output_credit_classifier", []))

    if state.get("status_credit_classifier") == COMPLETE:
        history.append(history[i - 1])
    else:
        rag_examples = retrieve_transaction_examples(state, "rag_cache_credit_classifier")
        fix_ctx = (state.get("fix_context_credit_classifier") or [None])[-1]

        messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
        structured_llm = get_llm(CREDIT_CLASSIFIER, config).with_structured_output(CreditClassifierOutput)
        result = structured_llm.invoke(messages)
        history.append(result.model_dump())

    return {
        "output_credit_classifier": history,
        "rag_cache_credit_classifier": rag_examples if 'rag_examples' in dir() else state.get("rag_cache_credit_classifier", []),
        "status_credit_classifier": COMPLETE,
    }
