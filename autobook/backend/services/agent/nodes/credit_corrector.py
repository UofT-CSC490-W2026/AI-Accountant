"""Agent 4 — Credit Corrector node.

Cross-validates credit tuple using debit side. Fixes misclassifications.
Output: CreditCorrectorOutput {"tuple": [int*6], "reason": str}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, CREDIT_CORRECTOR, COMPLETE,
)
from services.agent.prompts.credit_corrector import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.rag.correction import retrieve_correction_examples
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import CreditCorrectorOutput


def credit_corrector_node(state: PipelineState, config: RunnableConfig) -> dict:
    i = state["iteration"]
    history = list(state.get("output_credit_corrector", []))

    if state.get("status_credit_corrector") == COMPLETE:
        history.append(history[i - 1])
    else:
        # Ablation check
        configurable = (config or {}).get("configurable", {})
        if not configurable.get("correction_pass", True):
            classifier_output = state["output_credit_classifier"][i]
            history.append({"tuple": classifier_output["tuple"], "reason": "correction pass disabled"})
            return {
                "output_credit_corrector": history,
                "status_credit_corrector": COMPLETE,
            }

        cache_key = "rag_cache_credit_corrector"
        if i == 0:
            rag_examples = retrieve_transaction_examples(state, cache_key)
        else:
            rag_examples = retrieve_correction_examples(state, cache_key)

        fix_ctx = (state.get("fix_context_credit_corrector") or [None])[-1]

        messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
        structured_llm = get_llm(CREDIT_CORRECTOR, config).with_structured_output(CreditCorrectorOutput)
        result = structured_llm.invoke(messages)
        history.append(result.model_dump())

    return {
        "output_credit_corrector": history,
        "rag_cache_credit_corrector": rag_examples if 'rag_examples' in dir() else state.get("rag_cache_credit_corrector", []),
        "status_credit_corrector": COMPLETE,
    }
